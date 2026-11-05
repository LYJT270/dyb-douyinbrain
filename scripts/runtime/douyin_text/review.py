"""Prepare local evidence for the tools available to the current Agent.

Preparation never performs a review, recognizes speech or changes the original transcript.
"""
from __future__ import annotations

import bisect
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
from urllib import request
import uuid

from . import acquisition, media, workflow
from .common import ROOT, digest, inside, read_json, relative, write_json


def command(args: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess:
    process = subprocess.run(args, capture_output=True, timeout=timeout)
    if process.returncode:
        message = process.stderr.decode("utf-8", "replace")[-2500:]
        raise RuntimeError(acquisition.clean_failure({"message": message})["message"])
    return process


def probe(path: Path) -> dict:
    executable = shutil.which("ffprobe")
    if not executable:
        raise RuntimeError("缺少 ffprobe")
    return json.loads(command([executable, "-v", "error", "-show_streams", "-show_format",
                               "-of", "json", str(path)]).stdout)


def source_file(job: dict, root: Path) -> Path:
    value = job["media"]
    if not value.startswith("http"):
        path = Path(value)
        if not path.is_file():
            raise ValueError("原始本地媒体不存在，无法准备画面")
        if job["id"].startswith("local-") and digest(path) != job["id"][6:]:
            raise RuntimeError("原始本地媒体在识别后发生变化，不能用于本版逐字稿的画面校对")
        return path
    folder = inside(root, Path(".cache") / job["id"] / "source")
    record = folder / "source.json"
    if record.is_file():
        saved = read_json(record)
        path = inside(root, saved["file"])
        if path.is_file() and digest(path) == saved["sha256"]:
            return path
        raise RuntimeError("已保存的视频来源发生变化，保留现场供核对")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ("video-" + uuid.uuid4().hex[:10] + ".media")
    req = request.Request(value, headers={"User-Agent": media.douyin_browser.USER_AGENT,
                                         "Referer": "https://www.douyin.com/"})
    with request.urlopen(req, timeout=30) as response, target.open("xb") as handle:
        shutil.copyfileobj(response, handle)
    info = probe(target)
    if not any(item.get("codec_type") == "video" for item in info.get("streams", [])):
        raise RuntimeError("下载结果没有视频流，不能进行画面校对")
    write_json(record, {"file": relative(root, target), "sha256": digest(target),
                        "source": job.get("source"), "media_id": job["id"]})
    return target


def timestamps(path: Path, *, origin: float = 0) -> list[float]:
    process = command([shutil.which("ffprobe"), "-v", "error", "-select_streams", "v:0",
                       "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(path)])
    decoded = json.loads(process.stdout).get("frames", [])
    if any("best_effort_timestamp_time" not in item for item in decoded):
        raise RuntimeError("部分视频帧缺少真实时间戳，不能保证逐帧定位")
    return [float(item["best_effort_timestamp_time"]) - origin for item in decoded]


def subtitle_changes(path: Path, start: float, end: float) -> list[float]:
    # A cheap visual heuristic, not OCR: sample the lower 45% twice per second and
    # retain substantial changes. ASR segment positions are added independently.
    filters = (f"trim=start={start}:end={end},fps=2,crop=iw:ih*0.45:0:ih*0.55,"
               "select='gt(scene,0.08)',showinfo")
    process = command([shutil.which("ffmpeg"), "-nostdin", "-hide_banner", "-i", str(path),
                       "-an", "-vf", filters, "-f", "null", "-"])
    return [float(value) for value in re.findall(r"pts_time:([0-9.+eE-]+)",
                                                process.stderr.decode("utf-8", "replace"))]


def choose_frames(points: list[float], segments: list[dict], changes: list[float],
                  start: float, end: float, every_frame: bool, maximum: int) -> tuple[list[int], int]:
    eligible = [index for index, value in enumerate(points) if start <= value <= end]
    if not eligible:
        return [], 0
    if every_frame:
        if len(eligible) > maximum:
            raise ValueError(f"指定范围有 {len(eligible)} 帧，超过本次 {maximum} 帧上限；缩小范围或明确提高 --max-frames")
        return eligible, len(eligible)
    marks = [points[eligible[0]], points[eligible[-1]], *changes]
    marks.extend((float(item["start"]) + float(item["end"])) / 2 for item in segments
                 if item.get("start") is not None and item.get("end") is not None)
    selected = {min(eligible[-1], max(eligible[0], bisect.bisect_left(points, value)))
                for value in marks if start <= value <= end}
    selected = sorted(selected)
    total = len(selected)
    if total > maximum:
        selected = [selected[round(index * (total - 1) / max(maximum - 1, 1))]
                    for index in range(maximum)]
    return selected, total


def frames(path: Path, result: dict, folder: Path, root: Path, *, start: float,
           end: float | None, every_frame: bool, maximum: int) -> dict:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("缺少 FFmpeg 或 ffprobe")
    info = probe(path)
    if not any(item.get("codec_type") == "video" for item in info.get("streams", [])):
        return {"status": "no_video", "frames": [], "reviewed": False}
    points = timestamps(path, origin=float(info.get("format", {}).get("start_time") or 0))
    duration = float(info.get("format", {}).get("duration") or result.get("duration") or 0)
    finish = min(end if end is not None else duration, duration)
    changes = [] if every_frame else subtitle_changes(path, start, finish)
    selected, candidates = choose_frames(points, result.get("segments", []), changes,
                                         start, finish, every_frame, maximum)
    if not selected:
        raise ValueError("指定时间范围没有可提取的视频帧")
    folder.mkdir(parents=True, exist_ok=True)
    expression = "+".join(f"eq(n,{index})" for index in selected)
    command([shutil.which("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(path),
             "-map", "0:v:0", "-vf", f"select='{expression}'", "-fps_mode", "vfr", "-q:v", "3",
             "-start_number", "0", str(folder / "frame-%06d.jpg")])
    images = sorted(folder.glob("frame-*.jpg"))
    if len(images) != len(selected):
        raise RuntimeError("实际导出的帧数与选定帧不一致，尚未完成画面准备")
    return {"status": "prepared", "mode": "every_frame" if every_frame else "sampled",
            "range_seconds": [start, finish], "end_inclusive": True, "candidate_count": candidates,
            "selected_count": len(selected), "limited": len(selected) < candidates,
            "subtitle_change_method": None if every_frame else "lower_region_change_at_2fps_plus_asr_segments",
            "reviewed": False, "frames": [{"file": relative(root, file), "frame_index": index,
                                           "time_seconds": points[index], "sha256": digest(file)}
                                          for file, index in zip(images, selected)]}


def audio_files(item: dict, root: Path, start: float, end: float | None) -> list[dict]:
    version = inside(root, item["result"]).parent.name
    folder = inside(root, Path(".cache") / item["id"] / version / "audio")
    manifest = folder / "chunks.json"
    if not manifest.is_file():
        raise ValueError("本任务没有可复用的本地音轨；未重新提交语音识别")
    output = []
    for chunk in read_json(manifest):
        offset, duration = float(chunk["offset"]), float(chunk["duration"])
        if offset + duration <= start or (end is not None and offset >= end):
            continue
        file = inside(folder, chunk["file"])
        if not file.is_file() or digest(file) != chunk["sha256"]:
            raise RuntimeError("音轨缓存缺失或已改变，保留现场供核对")
        output.append({"file": relative(root, file), "source_offset_seconds": offset,
                       "listen_from_seconds": max(0, start - offset),
                       "listen_until_seconds": min(duration, end - offset) if end is not None else duration,
                       "listened": False})
    if not output:
        raise ValueError("指定范围没有可复用的音轨")
    return output


def prepare(task_id: str, root: Path = ROOT, *, images: bool = False, audio: bool = False,
            item_number: int | None = None, start: float = 0, end: float | None = None,
            every_frame: bool = False, max_frames: int = 120) -> dict:
    if not math.isfinite(start) or start < 0 or (end is not None and (not math.isfinite(end) or end <= start)):
        raise ValueError("时间范围须为非负秒数，结束时间晚于开始时间")
    if max_frames < 1:
        raise ValueError("帧数上限必须大于 0")
    if every_frame and not images:
        raise ValueError("逐帧准备需要当前 Agent 的看图能力（--images）")
    task = workflow.load(task_id, root)
    items = task.get("results", [])
    if not items:
        raise ValueError("任务尚无成功识别或导入的正文，不能准备校对")
    if item_number is not None and not 1 <= item_number <= len(items):
        raise ValueError("素材序号超出任务成功结果范围")
    run_dir = workflow.task_path(task_id, root).parent
    jobs = {job["id"]: job for job in read_json(run_dir / "jobs.json")} if (run_dir / "jobs.json").is_file() else {}
    folder = run_dir / "checks" / ("prepared-" + uuid.uuid4().hex[:10])
    report = {"status": "prepared", "task": task_id, "capabilities_reported_by_agent": {
        "images": images, "audio": audio}, "cloud_asr_called": False, "review_completed": False, "items": []}
    for number, item in enumerate(items, 1):
        if item_number is not None and number != item_number:
            continue
        result = read_json(inside(root, item["result"]))
        entry = {"number": number, "id": item["id"], "text": item["text"], "result": item["result"],
                 "mode": "text", "gaps": []}
        if images:
            try:
                if item["id"] not in jobs:
                    raise ValueError("这是已有文稿或缺少原始素材记录，无法准备视频画面")
                path = source_file(jobs[item["id"]], root)
                entry["visual"] = frames(path, result, folder / f"item-{number}", root,
                                          start=start, end=end, every_frame=every_frame, maximum=max_frames)
                if entry["visual"]["status"] == "prepared":
                    entry["mode"] = "text_and_images"
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                entry["gaps"].append({"capability": "images", "error": acquisition.clean_failure({"message": str(exc)})["message"]})
        if audio:
            try:
                entry["audio"] = audio_files(item, root, start, end)
                entry["mode"] += "_and_audio"
            except (OSError, ValueError, RuntimeError) as exc:
                entry["gaps"].append({"capability": "audio", "error": str(exc)})
        if entry["gaps"]:
            report["status"] = "prepared_with_gaps"
        report["items"].append(entry)
    report_path = folder / "manifest.json"
    report["manifest"] = relative(root, report_path)
    write_json(report_path, report)
    return report


def inspect_source(values: list[str], root: Path = ROOT, *, anonymous_only: bool = False) -> dict:
    folder = root / ".scratch" / ("source-check-" + uuid.uuid4().hex[:10])
    folder.mkdir(parents=True)
    try:
        jobs = media.discover(media.inputs(values), {}, folder, root, anonymous_only=anonymous_only)
        # Keep expiring media URLs in local task data, not the command's user-facing output.
        write_json(folder / "jobs.json", jobs)
        result = {"status": "acquired", "items": [{"id": job["id"], "title": job["title"],
                  "media_url_available": bool(job.get("media"))} for job in jobs]}
    except (OSError, ValueError, RuntimeError) as exc:
        result = {"status": "failed", "reason": getattr(exc, "code", type(exc).__name__),
                  "error": acquisition.clean_failure({"message": str(exc)})["message"]}
    result.update(anonymous_only=anonymous_only, cloud_asr_called=False,
                  report_directory=relative(root, folder))
    write_json(folder / "result.json", result)
    return result
