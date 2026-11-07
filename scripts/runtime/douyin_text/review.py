"""Prepare local evidence for the tools available to the current Agent.

Preparation never performs a review, recognizes speech or changes the original transcript.
"""
from __future__ import annotations

import bisect
import json
import math
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

from . import acquisition, media, workflow
from .common import ROOT, digest, inside, read_json, relative, write_json


def command(args: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess:
    process = subprocess.run(args, capture_output=True, timeout=timeout, creationflags=media._hidden())
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


def source_file(job: dict, root: Path, *, cached_only: bool = False) -> Path:
    if job['id'].startswith('local-'):
        return media.materialize(job, root)
    cached = media.local_source(job, root)
    if cached:
        return cached
    if cached_only:
        raise ValueError('只使用已有材料：未找到原媒体缓存，未联网重新获取')
    # Older tasks may contain an expired media URL. Refresh metadata within the
    # same bounded acquisition path; never resubmit speech to prepare pictures.
    jobs = media.acquire_batch([job['source']], {}, root / '.scratch/review-source', root,
                                version='review-source', audio=True)
    if not jobs:
        raise RuntimeError('校对素材获取失败：' + str(jobs.failures))
    path = media.local_source(job, root)
    if path is None:
        raise RuntimeError('未保存可复用的原始媒体')
    return path


def cached_frames(path: Path, result: dict, root: Path, **options) -> dict:
    key_data = {'source_sha256': digest(path), 'segments': result.get('segments', []),
                'selector_version': 1, 'image_capability': True, **options}
    key = hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
    folder = root / '.cache/review-frames' / key
    manifest = folder / 'visual.json'
    if manifest.is_file():
        saved = read_json(manifest)
        images = saved.get('frames', [])
        if images and all(inside(root, item['file']).is_file() and
                          digest(inside(root, item['file'])) == item['sha256'] for item in images):
            return {**saved, 'reused': True, 'reviewed': False}
    # Keep edited/incomplete prior images; generate in a fresh attempt directory.
    visual = frames(path, result, folder / uuid.uuid4().hex[:10], root, **options)
    visual.update(reused=False, source_sha256=key_data['source_sha256'])
    write_json(manifest, visual)
    return visual


def timestamps(path: Path, *, origin: float = 0) -> list[float]:
    process = command([shutil.which("ffprobe"), "-v", "error", "-select_streams", "v:0",
                       "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(path)])
    decoded = json.loads(process.stdout).get("frames", [])
    if any("best_effort_timestamp_time" not in item for item in decoded):
        raise RuntimeError("部分视频帧缺少真实时间戳，不能保证逐帧定位")
    return [float(item["best_effort_timestamp_time"]) - origin for item in decoded]


def subtitle_changes(path: Path, start: float, end: float, *, whole_frame=False) -> list[float]:
    # A cheap visual heuristic, not OCR: sample the lower 45% twice per second and
    # retain substantial changes. ASR segment positions are added independently.
    region = 'scale=640:-2' if whole_frame else 'crop=iw:ih*0.45:0:ih*0.55'
    filters = f"trim=start={start}:end={end},fps=2,{region},select='gt(scene,0.08)',showinfo"
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
           end: float | None, every_frame: bool, maximum: int, strategy='subtitle') -> dict:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("缺少 FFmpeg 或 ffprobe")
    source_hash = digest(path)
    timeline_path = root / '.cache/review-timeline' / (source_hash + '.json')
    if timeline_path.is_file():
        timeline = read_json(timeline_path)
        info, points = timeline['info'], timeline['points']
    else:
        info = probe(path)
        points = timestamps(path, origin=float(info.get('format', {}).get('start_time') or 0))
        write_json(timeline_path, {'info': info, 'points': points})
    if not any(item.get("codec_type") == "video" for item in info.get("streams", [])):
        return {"status": "no_video", "frames": [], "reviewed": False}
    duration = float(info.get("format", {}).get("duration") or result.get("duration") or 0)
    finish = min(end if end is not None else duration, duration)
    if strategy not in ('subtitle', 'content', 'action'):
        raise ValueError('未知的画面取样策略')
    changes = ([] if every_frame else subtitle_changes(path, start, finish, whole_frame=True)
               if strategy != 'subtitle' else subtitle_changes(path, start, finish))
    segments = list(result.get('segments', []))
    if strategy != 'subtitle' and not every_frame:
        # Visual content can carry information between speech segments or without speech.
        count = max(3, min(maximum, math.ceil((finish - start) / (8 if strategy == 'action' else 20)) + 3))
        segments.extend({'start': start + (finish - start) * n / (count - 1),
                         'end': start + (finish - start) * n / (count - 1)} for n in range(count))
    selected, candidates = choose_frames(points, segments, changes,
                                         start, finish, every_frame, maximum)
    if not selected:
        raise ValueError("指定时间范围没有可提取的视频帧")
    # Cache individual original-frame identities as well as complete review
    # requests, so overlapping review ranges reuse the same verified pictures.
    index_path = root / '.cache/review-frame-index' / (source_hash + '-jpg-q3-v1.json')
    stored = read_json(index_path) if index_path.is_file() else {}
    available = {}
    for index in selected:
        item = stored.get(str(index))
        if item and item['time_seconds'] == points[index]:
            image = inside(root, item['file'])
            if image.is_file() and digest(image) == item['sha256']:
                available[index] = item
    missing = [index for index in selected if index not in available]
    reused_count = len(available)
    if missing:
        folder.mkdir(parents=True, exist_ok=True)
        first = missing[0]
        # Seek between the preceding frame and our first frame. This avoids
        # rounding a microsecond timestamp past the requested frame. FFmpeg
        # accurately decodes from the preceding keyframe before applying select.
        seek = max(0, (points[first - 1] + points[first]) / 2) if first else 0
        expression = "+".join(f"eq(n,{index - first})" for index in missing)
        command([shutil.which("ffmpeg"), "-nostdin", "-hide_banner", "-loglevel", "error",
                 "-ss", f"{seek:.9f}", "-i", str(path), "-map", "0:v:0", "-vf", f"select='{expression}'",
                 "-fps_mode", "vfr", "-q:v", "3", "-frames:v", str(len(missing)),
                 "-start_number", "0", str(folder / "frame-%06d.jpg")])
        images = sorted(folder.glob("frame-*.jpg"))
        if len(images) != len(missing):
            raise RuntimeError("实际导出的帧数与选定帧不一致，尚未完成画面准备")
        for index, file in zip(missing, images):
            available[index] = {'file': relative(root, file), 'frame_index': index,
                                'time_seconds': points[index], 'sha256': digest(file)}
        stored.update({str(index): item for index, item in available.items()})
        write_json(index_path, stored)
    return {"status": "prepared", "mode": "every_frame" if every_frame else "sampled",
            "range_seconds": [start, finish], "end_inclusive": True, "candidate_count": candidates,
            "selected_count": len(selected), "limited": len(selected) < candidates,
            "subtitle_change_method": None if every_frame else ("lower_region_change_at_2fps_plus_asr_segments"
                if strategy == 'subtitle' else "whole_frame_change_at_2fps_plus_speech_and_timeline"),
            'strategy': strategy,
            "reviewed": False, 'reused_frame_count': reused_count,
            "frames": [available[index] for index in selected]}


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
            every_frame: bool = False, max_frames: int = 120, cached_only: bool = False) -> dict:
    preparation_started = time.monotonic()
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
                path = source_file(jobs[item["id"]], root, cached_only=cached_only)
                if result.get('source_media_sha256'):
                    if digest(path) != result['source_media_sha256']:
                        raise RuntimeError('画面媒体与本版识别音轨的来源哈希不同，不能冒充同源校对材料')
                    entry['source_binding'] = 'verified'
                else:
                    entry['source_binding'] = 'legacy_unrecorded'
                    entry['gaps'].append({'capability': 'source_binding',
                        'error': '旧结果未记录音轨来源媒体哈希；画面只能作为同作品的辅助参考'})
                entry["visual"] = cached_frames(path, result, root,
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
    report['preparation_seconds'] = round(time.monotonic() - preparation_started, 3)
    write_json(report_path, report)
    return report


def inspect_source(values: list[str], root: Path = ROOT, *, anonymous_only: bool = False,
                   download_audio: bool = False) -> dict:
    folder = root / ".scratch" / ("source-check-" + uuid.uuid4().hex[:10])
    folder.mkdir(parents=True)
    try:
        inputs = media.inputs(values)
        if download_audio or any(value.startswith('http') for value in inputs):
            jobs = media.acquire_batch(inputs, {}, folder, root, anonymous_only=anonymous_only,
                                       version='inspection-' + folder.name, audio=download_audio)
        else:
            jobs = media.discover(inputs, {}, folder, root, anonymous_only=anonymous_only, keep_going=True)
        # Keep expiring media URLs in local task data, not the command's user-facing output.
        write_json(folder / "jobs.json", jobs)
        failures = getattr(jobs, 'failures', [])
        result = {"status": ('incomplete' if jobs else 'failed') if failures else 'acquired',
                  'failures': failures, 'audio_requested': download_audio,
                  "items": [{"id": job["id"], "title": job["title"],
                  "media_url_available": bool(job.get("media")), 'audio_verified': job.get('audio_verified', False),
                  'audio_duration': job.get('audio_duration')} for job in jobs]}
    except (OSError, ValueError, RuntimeError) as exc:
        result = {"status": "failed", "reason": getattr(exc, "code", type(exc).__name__),
                  "error": acquisition.clean_failure({"message": str(exc)})["message"]}
    result.update(anonymous_only=anonymous_only, cloud_asr_called=False,
                  report_directory=relative(root, folder))
    write_json(folder / "result.json", result)
    return result
