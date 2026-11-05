from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from .common import ROOT, digest, read_json, write_json
from . import acquisition, douyin_browser

MEDIA_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
                  ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wma"}


def inputs(values: list[str], *, allow_list: bool = True) -> list[str]:
    items = []
    for value in values:
        try:
            path = Path(value).expanduser()
            exists = path.is_file()
        except OSError:
            exists = False
        if exists:
            if path.suffix.lower() == ".txt":
                if not allow_list:
                    raise ValueError("链接列表中应直接填写链接或媒体路径，不嵌套其他列表")
                items.extend(inputs([line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines()
                                     if line.strip()], allow_list=False))
            elif path.suffix.lower() in MEDIA_SUFFIXES:
                items.append(str(path.resolve()))
            else:
                raise ValueError("不支持的本地媒体格式：" + path.suffix)
            continue
        urls = re.findall(r'https?://[^\s<>\]）)"\'，。；！]+', value)
        if not urls:
            raise ValueError("未找到本地音视频或抖音链接")
        for url in urls:
            url = url.rstrip(".,;!?)）]")
            host = (urlsplit(url).hostname or "").lower()
            if not any(host == domain or host.endswith("." + domain)
                       for domain in ("douyin.com", "iesdouyin.com")):
                raise ValueError("当前仅支持抖音链接及本地音视频")
            items.append(url)
    return list(dict.fromkeys(items))


def has_profile(value: str) -> bool:
    return bool(re.search(r"/(?:user|share/user)/", urlsplit(value).path))


def scope_selected(scope: dict) -> bool:
    return bool(scope.get("all") or scope.get("latest") or scope.get("start"))


def select_jobs(jobs: list[dict], scope: dict) -> list[dict]:
    if scope.get("all"):
        return jobs
    if not scope_selected(scope):
        raise ValueError("作者主页尚未确认范围：请选择最新 N 条、日期范围或全部")
    if any(not job.get("published") for job in jobs):
        raise ValueError("部分作品缺少发布时间，无法保证所选范围；尚未调用转写")
    ordered = sorted(jobs, key=lambda job: (job["published"], job["id"]), reverse=True)
    if scope.get("latest"):
        return ordered[:scope["latest"]]
    return [job for job in ordered if scope["start"] <= job["published"][:10] <= scope["end"]]


def metadata(urls: list[str], profile: Path, report: Path, *, anonymous_only=False) -> tuple[list[dict], list[dict]]:
    result, public_failures = acquisition.public_metadata(urls)
    attempts = [{"backend": "public_share", "access": "anonymous", "resolved_count": len(result),
                 "failed_count": len(public_failures)}]
    diagnostics = [acquisition.clean_failure(item, backend="public_share", access="anonymous")
                   for item in public_failures]
    seen = {job["id"] for job in result}
    pending = [url for url in urls if "douyin-" + acquisition.video_id(url) not in seen]
    contexts = [("anonymous", None)]
    if not anonymous_only and profile.is_dir():
        contexts.append(("existing_profile", profile))
    for access, state in contexts:
        if not pending:
            break
        try:
            jobs, failures = douyin_browser.videos(pending, state)
        except Exception as exc:
            jobs = []
            failures = [{"input_url": url, "reason": "browser_error", "message": str(exc)} for url in pending]
        attempts.append({"backend": "playwright_with_ytdlp_fallback", "access": access,
                         "resolved_count": len(jobs), "failed_count": len(failures)})
        diagnostics.extend(acquisition.clean_failure(item, backend="playwright_with_ytdlp_fallback", access=access)
                           for item in failures)
        result.extend(jobs)
        seen.update(job["id"] for job in jobs)
        pending = [url for url in pending if "douyin-" + acquisition.video_id(url) not in seen]
    unresolved = {acquisition.video_id(url) for url in pending}
    failures = [item for item in diagnostics if acquisition.video_id(item["input_url"]) in unresolved]
    write_json(report, {"failures": failures, "attempt_failures": diagnostics, "attempts": attempts,
                        "resolved": len(result), "anonymous_first": True, "anonymous_only": anonymous_only})
    return result, failures


def discover(values: list[str], scope: dict, run_dir: Path, root: Path = ROOT, *, anonymous_only=False) -> list[dict]:
    result = []
    for index, value in enumerate(values):
        if not value.startswith("http"):
            path = Path(value)
            result.append({"id": "local-" + digest(path), "title": path.stem, "author": "未指定",
                           "source": str(path), "media": str(path), "published": None})
            continue
        resolved = douyin_browser.resolve_url(value) if urlsplit(value).hostname in {
            "v.douyin.com", "www.iesdouyin.com", "iesdouyin.com"} else value
        if not has_profile(resolved):
            if not re.search(r"/(?:share/)?video/\d+", urlsplit(resolved).path):
                raise ValueError("链接不是可识别的视频或作者主页；图文、文章不送入语音转写")
            options = {"anonymous_only": True} if anonymous_only else {}
            jobs, failures = metadata([resolved], root / ".local" / "douyin-profile",
                                      run_dir / f"metadata-{index}.json", **options)
            if failures or not jobs:
                raise acquisition.AcquisitionError(failures)
        else:
            if anonymous_only:
                raise ValueError("免登录单链接检查仅接受视频；作者主页须按实际分页与页面阻挡单独核验")
            if not scope_selected(scope):
                raise ValueError("该短链指向作者主页，请先补充处理范围，再执行")
            jobs = douyin_browser.profile_videos(resolved, root / ".local" / "douyin-profile",
                                                run_dir / f"profile-{index}.json")
            jobs = select_jobs(jobs, scope)
        result.extend(jobs)
    return list({job["id"]: job for job in result}.values())


def extract(job: dict, folder: Path, chunk_seconds: int = 300) -> list[dict]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("缺少 FFmpeg 或 ffprobe，请先运行环境检查")
    manifest = folder / "chunks.json"
    if manifest.exists():
        saved = read_json(manifest)
        if saved and all((folder / item["file"]).is_file() and
                         digest(folder / item["file"]) == item["sha256"] for item in saved):
            return saved
        raise RuntimeError("音频缓存不完整或已被修改，请明确要求重新转写以创建新版本")
    # A unique attempt directory keeps failed extraction fragments out of a later attempt.
    import uuid
    attempt = folder / uuid.uuid4().hex[:10]
    attempt.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error"]
    if job["media"].startswith("http"):
        command += ["-headers", "User-Agent: " + douyin_browser.USER_AGENT +
                    "\r\nReferer: https://www.douyin.com/\r\n"]
    command += ["-i", job["media"], "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000",
                "-c:a", "pcm_s16le", "-f", "segment", "-segment_time", str(chunk_seconds),
                "-reset_timestamps", "1", str(attempt / "chunk_%05d.wav")]
    try:
        process = subprocess.run(command, capture_output=True, timeout=max(600, int(job.get("duration") or 600) * 3))
    except subprocess.TimeoutExpired:
        raise RuntimeError("音频提取超时，未提交豆包") from None
    if process.returncode:
        (attempt / "ffmpeg-error.txt").write_bytes(process.stderr)
        raise RuntimeError("FFmpeg 未能提取音轨，错误已保留在本地缓存")
    offset = 0.0
    chunks = []
    for path in sorted(attempt.glob("chunk_*.wav")):
        probe = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                                "-of", "json", str(path)], capture_output=True, check=True)
        duration = float(json.loads(probe.stdout)["format"]["duration"])
        if duration <= 0:
            raise RuntimeError("提取的音频片段为空")
        chunks.append({"file": path.relative_to(folder).as_posix(), "offset": offset,
                       "duration": duration, "sha256": digest(path)})
        offset += duration
    if not chunks:
        raise RuntimeError("FFmpeg 未生成音频片段")
    write_json(manifest, chunks)
    return chunks
