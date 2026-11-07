from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
import wave
import time
from pathlib import Path
from urllib.parse import urlsplit

from .common import ROOT, digest, inside, read_json, relative, write_json
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
    result, attempts, diagnostics = [], [], []
    seen, pending = set(), list(urls)
    routes = [('public_share', 'anonymous', None), ('playwright_with_ytdlp_fallback', 'anonymous', None)]
    if not anonymous_only and profile.is_dir():
        routes.append(('playwright_with_ytdlp_fallback', 'existing_profile', profile))
    for backend, access, state in routes:
        if not pending:
            break
        started = time.monotonic()
        try:
            jobs, failures = (acquisition.public_metadata(pending) if backend == 'public_share'
                              else douyin_browser.videos(pending, state))
        except Exception as exc:
            jobs = []
            failures = [{"input_url": url, "reason": "browser_error", "message": str(exc)} for url in pending]
        attempts.append({"backend": backend, "access": access, 'elapsed_seconds': round(time.monotonic() - started, 3),
                         "resolved_count": len(jobs), "failed_count": len(failures)})
        diagnostics.extend(acquisition.clean_failure(item, backend=backend, access=access)
                           for item in failures)
        result.extend(jobs)
        seen.update(job["id"] for job in jobs)
        pending = [url for url in pending if "douyin-" + acquisition.video_id(url) not in seen]
    unresolved = {acquisition.video_id(url) for url in pending}
    failures = [item for item in diagnostics if acquisition.video_id(item["input_url"]) in unresolved]
    write_json(report, {"failures": failures, "attempt_failures": diagnostics, "attempts": attempts,
                        "resolved": len(result), "anonymous_first": True, "anonymous_only": anonymous_only})
    return result, failures


class Discovery(list):
    """Successful items in source order, with failures retained independently."""
    def __init__(self, values=(), failures=()):
        super().__init__(values)
        self.failures = list(failures)


def discover(values: list[str], scope: dict, run_dir: Path, root: Path = ROOT, *,
             anonymous_only=False, keep_going=False) -> list[dict]:
    result = Discovery()
    number = 1
    for index, value in enumerate(values):
        try:
            jobs = discover_one(value, scope, run_dir, root, index=index, anonymous_only=anonymous_only)
            for subindex, job in enumerate(jobs):
                if any(prior['id'] == job['id'] for prior in result):
                    continue
                result.append({**job, 'input': value, 'input_number': index + 1,
                               'input_item': subindex + 1, 'number': number})
                number += 1
        except Exception as exc:
            if not keep_going:
                raise
            failure = acquisition.clean_failure({'input_url': value if value.startswith('http') else '',
                'reason': getattr(exc, 'code', 'metadata_unavailable'), 'message': str(exc)},
                input_number=index + 1, number=number)
            failure['error'] = failure.get('message', str(exc))
            failure['reports'] = [str(p.relative_to(root)) for p in (run_dir / f'metadata-{index}.json',)
                                  if p.is_file() and p.is_relative_to(root)]
            result.failures.append(failure)
            number += 1
    return result


def discover_one(value: str, scope: dict, run_dir: Path, root: Path, *, index=0,
                 anonymous_only=False) -> list[dict]:
    if not value.startswith("http"):
        path = Path(value)
        return [{"id": "local-" + digest(path), "title": path.stem, "author": "未指定",
                 "source": str(path), "media": str(path), "published": None}]
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
    return jobs


def acquire_batch(values: list[str], scope: dict, run_dir: Path, root: Path, *,
                  version: str, audio=True, anonymous_only=False, timeout=90, on_ready=None) -> Discovery:
    """At most two acquisition workers; the deadline never encloses paid ASR."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from queue import Queue
    from .processes import Worker
    batch = run_dir / ('acquisition-' + uuid.uuid4().hex[:10])
    workers = [Worker(batch / f'worker-{n}.log') for n in range(min(2, len(values)))]
    available = Queue()
    for worker in workers:
        available.put(worker)

    def one(pair):
        index, value = pair
        folder = batch / f'input-{index + 1}'
        worker = available.get()
        started = time.monotonic()
        try:
            result = worker.run({'value': value, 'scope': scope, 'root': str(root), 'folder': str(folder),
                                 'audio': audio, 'version': version, 'anonymous_only': anonymous_only}, folder, timeout)
            result['input_number'] = index + 1
            return result
        except Exception as exc:
            return {'jobs': [], 'input_number': index + 1, 'elapsed_seconds': round(time.monotonic() - started, 3), 'failures': [
                {'reason': 'acquisition_timeout' if isinstance(exc, TimeoutError) else 'acquisition_error',
                 'error': str(exc), 'stage': 'acquisition', 'reports': [relative(root, folder)]}]}
        finally:
            available.put(worker)

    outcomes = []
    try:
        with ThreadPoolExecutor(max_workers=max(1, len(workers))) as executor:
            futures = [executor.submit(one, pair) for pair in enumerate(values)]
            for future in as_completed(futures):
                outcome = future.result()
                outcomes.append(outcome)
                if on_ready is not None:
                    # The parent consumes one item at a time; acquisition workers
                    # continue independently and never receive ASR credentials.
                    on_ready(outcome)
    finally:
        for worker in workers:
            worker.close()
        write_json(batch / 'process-receipts.json', [r for worker in workers for r in worker.receipts])
    outcomes.sort(key=lambda item: item['input_number'])
    # Distinct URLs may resolve to the same locked artifact. Only reconcile a
    # contention when this batch actually produced verified audio for that ID.
    ready_by_id = {job['id']: job for outcome in outcomes for job in outcome['jobs']
                   if job.get('audio_verified')}
    for outcome in outcomes:
        failures = []
        for failure in outcome['failures']:
            ready = ready_by_id.get(failure.get('id'))
            if failure.get('reason') == 'media_busy' and ready:
                outcome['jobs'].append({**ready, 'input': values[outcome['input_number'] - 1],
                                        'input_item': failure.get('number', 1)})
                outcome.setdefault('resolved_contention', []).append(failure)
            else:
                failures.append(failure)
        outcome['failures'] = failures
    result = Discovery()
    for outcome in outcomes:
        number = outcome['input_number']
        result.extend({**job, 'input_number': number} for job in outcome['jobs'])
        result.failures.extend({**failure, 'input_number': number, 'number': number}
                               for failure in outcome['failures'])
    write_json(batch / 'summary.json', {'outcomes': outcomes, 'limit_seconds': timeout,
               'max_parallel': 2, 'audio_requested': audio, 'acquisition_workers_call_asr': False,
               'parent_callback_enabled': on_ready is not None})
    return result


def local_source(job: dict, root: Path) -> Path | None:
    manifest = inside(root, Path('.cache') / job['id'] / 'source/source.json')
    if not manifest.is_file():
        return None
    record = read_json(manifest)
    path = inside(root, record['file'])
    if record.get('media_id') != job['id'] or not path.is_file() or digest(path) != record['sha256']:
        raise RuntimeError('已保存的媒体来源发生变化，保留现场供核对')
    return path


def materialize(job: dict, root: Path) -> Path:
    if job['id'].startswith('local-'):
        path = Path(job['media'])
        if not path.is_file() or digest(path) != job['id'][6:]:
            raise RuntimeError('原始本地媒体在识别后发生变化，不能用于本版逐字稿的校对')
        return path
    cached = local_source(job, root)
    if cached:
        return cached
    from urllib import request
    folder = inside(root, Path('.cache') / job['id'] / 'source')
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ('media-' + uuid.uuid4().hex[:10] + '.media')
    req = request.Request(job['media'], headers={'User-Agent': douyin_browser.USER_AGENT,
                                                'Referer': 'https://www.douyin.com/'})
    with request.urlopen(req, timeout=20) as response, target.open('xb') as handle:
        shutil.copyfileobj(response, handle)
        expected_size = response.headers.get('Content-Length')
        if expected_size and handle.tell() != int(expected_size):
            raise RuntimeError('下载文件不完整，未提取音轨或提交识别')
    executable = shutil.which('ffprobe')
    if not executable:
        raise RuntimeError('缺少 ffprobe')
    probe = subprocess.run([executable, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(target)],
                           capture_output=True, check=True, timeout=20, creationflags=_hidden())
    info = json.loads(probe.stdout)
    if not any(stream.get('codec_type') == 'audio' for stream in info.get('streams', [])):
        raise RuntimeError('下载素材没有音轨，未提交语音识别')
    write_json(folder / 'source.json', {'file': relative(root, target), 'sha256': digest(target),
        'source': job['source'], 'media_id': job['id'], 'job': {k: v for k, v in job.items() if k != 'media'}})
    return target


def _hidden():
    import os
    return subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def cached_chunks(folder: Path) -> list[dict] | None:
    manifest = folder / 'chunks.json'
    if not manifest.is_file():
        return None
    saved = read_json(manifest)
    if saved and all(inside(folder, item['file']).is_file() and
                     digest(inside(folder, item['file'])) == item['sha256'] for item in saved):
        return saved
    raise RuntimeError('音频缓存不完整或已被修改，请明确要求重新转写以创建新版本')


def extract(job: dict, folder: Path, chunk_seconds: int = 300) -> list[dict]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("缺少 FFmpeg 或 ffprobe，请先运行环境检查")
    manifest = folder / "chunks.json"
    saved = cached_chunks(folder)
    if saved is not None:
        return saved
    source_hash = digest(Path(job['media'])) if not job['media'].startswith('http') else None
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
        process = subprocess.run(command, capture_output=True, timeout=max(600, int(job.get("duration") or 600) * 3),
                                 creationflags=_hidden())
    except subprocess.TimeoutExpired:
        raise RuntimeError("音频提取超时，未提交豆包") from None
    if process.returncode:
        (attempt / "ffmpeg-error.txt").write_bytes(process.stderr)
        raise RuntimeError("FFmpeg 未能提取音轨，错误已保留在本地缓存")
    offset = 0.0
    chunks = []
    for path in sorted(attempt.glob("chunk_*.wav")):
        with wave.open(str(path), 'rb') as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
                raise RuntimeError('提取的音轨格式不符合识别要求')
            expected, actual = audio.getnframes(), 0
            while block := audio.readframes(65536):
                actual += len(block) // 2
            if actual != expected:
                raise RuntimeError('提取的 PCM 音轨不完整')
            duration = actual / 16000
        if duration <= 0:
            raise RuntimeError("提取的音频片段为空")
        chunks.append({"file": path.relative_to(folder).as_posix(), "offset": offset,
                       "duration": duration, "sha256": digest(path)})
        offset += duration
    if not chunks:
        raise RuntimeError("FFmpeg 未生成音频片段")
    write_json(manifest, chunks)
    if source_hash:
        write_json(folder / 'source.json', {'source_sha256': source_hash, 'media_id': job['id'],
                                           'chunks_sha256': [chunk['sha256'] for chunk in chunks]})
    return chunks
