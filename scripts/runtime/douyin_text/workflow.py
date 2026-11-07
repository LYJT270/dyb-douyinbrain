from __future__ import annotations

import re
import time
import uuid
from datetime import date
from pathlib import Path

from . import acquisition, asr, credentials, media
from .common import ROOT, artifact_lock, config, digest, inside, now, read_json, relative, write_json

PURPOSES = {"transcribe": "只转写", "analyze": "总结／分析", "ingest": "原文留底与校对稿入库", "compile": "入库并编译", "rewrite": "口播改写"}


def task_path(task_id: str, root: Path = ROOT) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", task_id):
        raise ValueError("任务 ID 无效")
    return root / "runs" / task_id / "task.json"


def load(task_id: str, root: Path = ROOT) -> dict:
    return relocate(read_json(task_path(task_id, root)), root)


def relocate(task: dict, root: Path = ROOT) -> dict:
    """Express recorded workspace files relative to the workspace.

    Versions before 1.3.0 stored absolute paths. Once the folder is renamed or moved they point at
    the old location, which is recognised from the fixed layout of results and text snapshots.
    User inputs, vault targets and publisher manifests live outside the workspace and stay as they are.
    """
    imports = task.get("text_imports") or ([task["text_import"]] if task.get("text_import") else [])
    bases = [root.resolve()]
    for item in task.get("results", []):
        path = Path(item.get("result", ""))
        if path.is_absolute() and path.name == "result.json" and path.parts[-4:-2] == ("outputs", item.get("id")):
            bases.append(path.parents[3])
    for item in imports:
        path = Path(item.get("file", ""))
        if path.is_absolute() and path.parts[-4:-1] == ("runs", task.get("id"), "sources"):
            bases.append(path.parents[3])

    def convert(value: str) -> str:
        path = Path(value)
        for base in bases if path.is_absolute() else []:
            if path.is_relative_to(base):
                return path.relative_to(base).as_posix()
        return value

    publication = task.get("publication", {})
    fields = [(item, key) for item in task.get("results", []) for key in ("result", "markdown", "text")]
    fields += [(item, "file") for item in imports]
    fields += [(item, "file") for kind in ("review", "spoken", "archive") for item in task.get(kind, {}).get("files", [])]
    fields += [(task[key], "file") for key in ("delivery", "analysis") if key in task]
    fields += [(publication, "receipt_file")] + [(item, "source") for item in publication.get("files", [])]
    for holder, key in fields:
        if key in holder:
            holder[key] = convert(holder[key])
    return task


def save(task: dict, root: Path = ROOT) -> None:
    write_json(task_path(task["id"], root), task)


def plan(values: list[str], root: Path = ROOT) -> dict:
    normalized = media.inputs(values)
    if not normalized:
        raise ValueError("输入为空")
    task = {"id": "dy-" + uuid.uuid4().hex[:16], "created": now(), "status": "needs_intent",
            "inputs": normalized, "purpose": None, "results": [], "failures": [],
            "question": "本次要做什么？只转写、总结／分析、原稿入库，还是入库并编译？",
            "choices": PURPOSES}
    if any(media.has_profile(value) for value in normalized):
        task["scope_question"] = "作者主页请同时选择：最新 N 条、指定日期范围或全部可访问视频。"
    save(task, root)
    return task


def confirm(task_id: str, purpose: str, evidence: str, *, scope: dict | None = None,
            instruction: str = "", category: str = "reference", retranscribe: bool = False,
            root: Path = ROOT) -> dict:
    task = load(task_id, root)
    if task["status"] not in {"needs_intent", "confirmed", "needs_scope", "failed"}:
        raise ValueError("当前任务已执行，请为新的用途创建任务；已有转写结果可复用")
    if purpose not in PURPOSES or not evidence.strip():
        raise ValueError("必须记录本次明确选定的用途和用户确认原话")
    if purpose in {"analyze", "rewrite"} and not instruction.strip():
        raise ValueError("请通过 --instruction 记录用户已给出的具体分析或改稿要求；只有要求不清楚时才补问")
    if category not in {"reference", "benchmark", "own"}:
        raise ValueError("材料分类无效")
    scope = scope or {}
    modes = sum(bool(scope.get(key)) for key in ("all", "latest", "start"))
    if modes > 1 or scope.get("latest", 1) < 1:
        raise ValueError("主页范围应为最新 N 条、日期范围或全部之一")
    if scope.get("start") or scope.get("end"):
        if not scope.get("start") or not scope.get("end"):
            raise ValueError("日期范围需要起止日期")
        if date.fromisoformat(scope["start"]) > date.fromisoformat(scope["end"]):
            raise ValueError("开始日期晚于结束日期")
    if any(media.has_profile(value) for value in task["inputs"]) and not media.scope_selected(scope):
        raise ValueError("作者主页必须同时确认处理范围")
    if task.get("results") and retranscribe != bool(task.get("retranscribe")):
        raise ValueError("任务已有结果，重新识别请创建新任务")
    task.update(purpose=purpose, evidence=evidence, confirmed_at=now(), scope=scope,
                instruction=instruction, category=category, status="confirmed", retranscribe=retranscribe)
    if retranscribe and not task.get("revision"):
        task["revision"] = uuid.uuid4().hex[:12]
    save(task, root)
    return task


def render_markdown(result: dict) -> str:
    job = result["source"]
    lines = ["# " + job["title"], "", "- 类型：机器语音识别原稿（未经人工校对）",
             "- 来源：" + job["source"], "- 作者：" + job.get("author", "未指定"),
             "- 转写时间：" + result["created"], "- 服务：豆包录音文件识别极速版",
             "- 处理：保留口头语和重复表达；开启标点；关闭语义顺滑和数字规整"]
    if job.get("published"):
        lines.append("- 视频发布时间：" + job["published"])
    return "\n".join(lines) + "\n\n## 逐字稿\n\n" + result["text"] + "\n"


def version_for(task: dict) -> str:
    return asr.PROFILE + ("-" + task["revision"] if task.get("revision") else "")


def cached_result(job: dict, task: dict, root: Path) -> dict | None:
    output = root / 'outputs' / job['id'] / version_for(task)
    result_path = output / 'result.json'
    if not result_path.is_file():
        return None
    result = read_json(result_path)
    if (result.get('engine') != 'doubao-auc-turbo' or result.get('parameters') != asr.PARAMETERS
            or result.get('source', {}).get('id') != job['id']):
        raise RuntimeError('已有识别缓存的来源或识别参数不一致，保留现场；重新识别须另存版本')
    for suffix in ('md', 'txt'):
        path = output / ('transcript.' + suffix)
        if not path.is_file() or digest(path) != result.get('output_sha256', {}).get(suffix):
            raise RuntimeError('已有原稿被修改，保留现场；请明确要求重新转写以另存新版本')
    return {'id': job['id'], 'status': 'reused', 'result': relative(root, result_path),
            'markdown': relative(root, output / 'transcript.md'), 'text': relative(root, output / 'transcript.txt')}


def local_jobs(value: str, saved: list[dict], task: dict, root: Path) -> list[dict]:
    """Look up identity locally before attempting any remote metadata request."""
    matches = [job for job in saved if job.get('input') == value or job.get('source') == value]
    if not matches:
        try:
            ident = ('douyin-' + acquisition.video_id(value)) if value.startswith('http') else 'local-' + digest(Path(value))
        except (ValueError, OSError):
            return []
        matches = [job for job in saved if job['id'] == ident]
        if not matches:
            result = root / 'outputs' / ident / version_for(task) / 'result.json'
            if result.is_file():
                matches = [{**read_json(result)['source'], 'media': value}]
            else:
                source_manifest = root / '.cache' / ident / 'source/source.json'
                if source_manifest.is_file():
                    source = read_json(source_manifest)
                    if source.get('job'):
                        matches = [{**source['job'], 'media': value}]
    ready = []
    for job in matches:
        local_media = media.local_source(job, root)
        if local_media:
            job = {**job, 'media': str(local_media)}
        if cached_result(job, task, root) is not None or media.cached_chunks(
                root / '.cache' / job['id'] / version_for(task) / 'audio') is not None or local_media:
            ready.append(job)
    return ready if len(ready) == len(matches) else []


def transcribe(job: dict, task: dict, root: Path = ROOT, *, retry_failed: bool = False) -> dict:
    version = version_for(task)
    output = root / "outputs" / job["id"] / version
    folder = root / ".cache" / job["id"] / version
    result_path = output / "result.json"
    with artifact_lock(folder):
        cached = cached_result(job, task, root)
        if cached is not None:
            return cached
        cfg = config(root)
        chunks = media.extract(job, folder / "audio", cfg["chunk_seconds"])
        audio_source = folder / 'audio/source.json'
        binding = read_json(audio_source) if audio_source.is_file() else None
        if binding and (binding.get('media_id') != job['id'] or
                        binding.get('chunks_sha256') != [chunk['sha256'] for chunk in chunks]):
            raise RuntimeError('音轨来源绑定与分片不一致，保留现场；未提交豆包')
        recognized = []
        for index, chunk in enumerate(chunks):
            chunk_path = folder / f"chunk-{index:05d}.json"
            prior = read_json(chunk_path) if chunk_path.exists() else {}
            if prior.get("status") == "succeeded":
                if prior.get('audio_sha256') != chunk['sha256']:
                    raise RuntimeError('已成功请求的音轨与当前分片不一致，保留现场；未重复提交')
                recognized.append(prior["result"])
                continue
            if prior and not retry_failed:
                raise RuntimeError("本媒体有失败或结果未知的请求。请先核对，再明确重试；已成功片段会复用")
            auth = credentials.load(root)
            request_id = str(uuid.uuid4())
            attempt = {"status": "submitting", "request_id": request_id, "created": now(),
                       "audio_sha256": chunk["sha256"], "audio_duration": chunk['duration']}
            write_json(chunk_path, attempt)
            response_path = folder / "responses" / (request_id + ".json")
            try:
                result = asr.recognize(folder / "audio" / chunk["file"], auth, response_path,
                                       timeout=cfg["asr_timeout_seconds"], request_id=request_id)
            except Exception as exc:
                attempt["status"] = "outcome_unknown" if isinstance(exc, asr.OutcomeUnknown) else "failed"
                attempt["error"] = str(exc)
                write_json(chunk_path, attempt)
                raise
            attempt.update(status="succeeded", result=result, completed=now())
            write_json(chunk_path, attempt)
            recognized.append(result)
        text = "\n".join(item["text"] for item in recognized if item["text"])
        if not text.strip():
            raise RuntimeError("音频未识别到可用语音，未生成逐字稿；已保存识别结果")
        segments = [{**segment, "start": segment["start"] + chunk["offset"],
                     "end": segment["end"] + chunk["offset"]}
                    for chunk, item in zip(chunks, recognized) for segment in item["segments"]]
        result = {"created": now(), "source": {key: value for key, value in job.items() if key != "media"},
                  "engine": "doubao-auc-turbo", "parameters": asr.PARAMETERS, "text": text,
                  "segments": segments, "duration": sum(chunk["duration"] for chunk in chunks),
                  "request_ids": [item["request_id"] for item in recognized]}
        if binding:
            result['source_media_sha256'] = binding['source_sha256']
        output.mkdir(parents=True, exist_ok=True)
        (output / "transcript.txt").write_text(text + "\n", encoding="utf-8")
        (output / "transcript.md").write_text(render_markdown(result), encoding="utf-8")
        result["output_sha256"] = {suffix: digest(output / ("transcript." + suffix)) for suffix in ("md", "txt")}
        write_json(result_path, result)
        return {"id": job["id"], "status": "transcribed", "result": relative(root, result_path),
                "markdown": relative(root, output / "transcript.md"), "text": relative(root, output / "transcript.txt")}


def run(task_id: str, root: Path = ROOT, *, retry_evidence: str = "", anonymous_only: bool = False) -> dict:
    task = load(task_id, root)
    if not task.get("purpose") or not task.get("evidence"):
        raise ValueError("先询问并确认本次用途；未下载、未调用豆包、未入库")
    if task["status"] in {"completed", "published"}:
        return task
    if task["status"] in {"awaiting_review", "awaiting_edit", "awaiting_analysis", "awaiting_compile", "ready_for_ingest", "ready_to_deliver"}:
        return task
    if task["status"] in {"publishing", "publication_unknown", "publish_failed", "ready_to_publish"}:
        from .vault import publish
        return publish(task_id, root=root)
    if retry_evidence:
        task.setdefault("retry_confirmations", []).append({"evidence": retry_evidence, "at": now()})
    if anonymous_only:
        task['anonymous_only'] = True
    acquisition_stages = {'metadata', 'audio', 'acquisition'}
    prior_gaps = list(task.get('acquisition_gaps', []))
    for failure in task.get('failures', []):
        if failure.get('stage') in acquisition_stages and failure not in prior_gaps:
            prior_gaps.append(failure)
    task.update(status="running", failures=[], acquisition_gaps=prior_gaps)
    run_started = time.monotonic()
    task['run_timing'] = {'started': now(), 'events': []}
    save(task, root)
    try:
        if task.get("input_kind") == "text":
            from .content import restore_text_result
            sources = task.get("text_imports") or [task["text_import"]]
            task["results"] = [restore_text_result(task, root, item) for item in sources]
            task["status"] = "awaiting_review"
            save(task, root)
            return task
        run_dir = task_path(task_id, root).parent
        saved = read_json(run_dir / 'jobs.json') if (run_dir / 'jobs.json').is_file() else []
        jobs, pending, positions = [], [], []
        result_by_id = {item['id']: item for item in task.get('results', [])}
        for number, value in enumerate(task['inputs'], 1):
            try:
                cached_jobs = local_jobs(value, saved, task, root)
                unresolved_input = any(gap.get('input_number', number) == number for gap in prior_gaps)
                if cached_jobs and not unresolved_input:
                    for subindex, job in enumerate(cached_jobs, 1):
                        job = {**job, 'input': value, 'input_number': number, 'input_item': subindex}
                        jobs.append(job)
                        existing = cached_result(job, task, root)
                        if existing:
                            result_by_id[job['id']] = existing
                else:
                    pending.append(value)
                    positions.append(number)
            except (OSError, ValueError, RuntimeError) as exc:
                task['failures'].append({'input_number': number, 'number': number, 'stage': 'cache', 'error': str(exc)})
        task['results'] = list(result_by_id.values())
        save(task, root)
        attempted = set()

        def recognize_ready(job):
            if job['id'] in attempted:
                return
            attempted.add(job['id'])
            started = time.monotonic()
            event = {'id': job['id'], 'input_number': job['input_number'],
                     'ready_at_seconds': round(started - run_started, 3)}
            try:
                result_by_id[job['id']] = {**transcribe(job, task, root, retry_failed=bool(retry_evidence)),
                                            'number': job.get('number', job['input_number'])}
                event['status'] = result_by_id[job['id']]['status']
            except Exception as exc:
                task['failures'].append({'id': job['id'], 'input_number': job['input_number'],
                                        'number': job.get('number', job['input_number']), 'error': str(exc)})
                event['status'] = 'failed'
            event.update(finished_at_seconds=round(time.monotonic() - run_started, 3),
                         recognition_seconds=round(time.monotonic() - started, 3))
            task['run_timing']['events'].append(event)
            task['results'] = sorted(result_by_id.values(), key=lambda item: item.get('number', 0))
            save(task, root)

        def consume(outcome):
            number = positions[outcome['input_number'] - 1]
            ready_jobs = [{**job, 'input_number': number, 'input': pending[outcome['input_number'] - 1]}
                          for job in outcome['jobs']]
            jobs.extend(ready_jobs)
            # A profile can return successful jobs and unresolved identities in
            # the same outcome. Persist both before paid work or interruption.
            task['acquisition_gaps'] = [*task['acquisition_gaps'], *[
                {**failure, 'input_number': number, 'number': number} for failure in outcome.get('failures', [])]]
            save(task, root)
            # Persist identities before submitting anything paid. Resume can
            # find a completed/unknown receipt even after a process interruption.
            write_json(run_dir / 'jobs.json', jobs)
            for job in ready_jobs:
                recognize_ready(job)

        if pending:
            try:
                if any(value.startswith('http') for value in pending):
                    discovered = media.acquire_batch(pending, task['scope'], run_dir, root,
                        version=version_for(task), anonymous_only=task.get('anonymous_only', False), on_ready=consume)
                else:
                    discovered = media.discover(pending, task['scope'], run_dir, root, keep_going=True)
                jobs.extend({**job, 'input_number': positions[job.get('input_number', 1) - 1]} for job in discovered)
                for failure in getattr(discovered, 'failures', []):
                    task['failures'].append({**failure, 'input_number': positions[failure['input_number'] - 1],
                                             'number': positions[failure['input_number'] - 1]})
            except Exception as exc:
                task['failures'].append({'stage': 'metadata', 'reason': getattr(exc, 'code', type(exc).__name__),
                    'error': str(exc), 'reports': [relative(root, p) for p in run_dir.glob('metadata-*.json')]})
        ordered = {}
        for job in sorted(jobs, key=lambda x: (x['input_number'], x.get('input_item', 1))):
            ordered.setdefault(job['id'], job)
        jobs = list(ordered.values())
        for gap in prior_gaps:
            group = [job for job in jobs if gap.get('input_number', job['input_number']) == job['input_number']]
            resolved = (any(job['id'] == gap['id'] for job in group) if gap.get('id') else
                        bool(group) and not any(f.get('stage') in acquisition_stages and
                            f.get('input_number') == gap.get('input_number') for f in task['failures']))
            if not resolved and not any(f.get('id') == gap.get('id') and
                                       f.get('input_number') == gap.get('input_number') for f in task['failures']):
                task['failures'].append(gap)
        task['acquisition_gaps'] = [f for f in task['failures'] if f.get('stage') in acquisition_stages]
        # Reserve a slot for a failed input, including mixed profile/video batches.
        next_number = 1
        for position in range(1, len(task['inputs']) + 1):
            group = [job for job in jobs if job['input_number'] == position]
            for job in group:
                job['number'] = next_number
                next_number += 1
            if not group:
                for failure in task['failures']:
                    if failure.get('input_number') == position:
                        failure['number'] = next_number
                next_number += 1
        if not jobs:
            if not task['failures']:
                raise ValueError("所选范围没有可处理的视频")
        write_json(task_path(task_id, root).parent / "jobs.json", jobs)
        for job in jobs:
            recognize_ready(job)
            if job['id'] in result_by_id:
                result_by_id[job['id']]['number'] = job['number']
            for failure in task['failures']:
                if failure.get('id') == job['id']:
                    failure['number'] = job['number']
        task['results'] = sorted(result_by_id.values(), key=lambda x: x.get('number', 0))
        task['run_timing']['elapsed_seconds'] = round(time.monotonic() - run_started, 3)
        if task["failures"]:
            task["status"] = "incomplete" if task['results'] or jobs or any(
                failure.get('stage') == 'cache' for failure in task['failures']) else 'failed'
        else:
            task["status"] = "awaiting_review"
        save(task, root)
        if task["status"] == "ready_to_publish":
            from .vault import publish
            return publish(task_id, root=root)
    except Exception as exc:
        failure = {"stage": "prepare_or_publish", "error": str(exc)}
        if isinstance(exc, acquisition.AcquisitionError):
            failure["reason"] = exc.code
            failure["reports"] = [relative(root, path) for path in sorted(
                task_path(task_id, root).parent.glob("metadata-*.json"))]
        task.update(status="incomplete" if task.get('results') else "failed", failures=[*task['failures'], failure])
    save(task, root)
    return task


def finish_analysis(task_id: str, file: Path, root: Path = ROOT) -> dict:
    task = load(task_id, root)
    if task["purpose"] != "analyze" or task["status"] != "awaiting_analysis":
        raise ValueError("本任务不在等待分析稿的阶段")
    source = inside(root, file)
    if source.suffix != ".md" or not source.is_file():
        raise ValueError("分析稿应为项目内已生成的 Markdown 文件")
    if any(source == inside(root, item["markdown"]) for item in task["results"]):
        raise ValueError("分析稿与转写原稿应分别保存")
    task.update(status="completed", analysis={"file": relative(root, source), "sha256": digest(source)}, completed=now())
    save(task, root)
    return task


def export_srt(task_id: str, root: Path = ROOT) -> list[str]:
    task = load(task_id, root)
    if not task.get("results"):
        raise ValueError("尚无完整转写结果")

    def stamp(seconds: float) -> str:
        milliseconds = round(seconds * 1000)
        hours, milliseconds = divmod(milliseconds, 3600000)
        minutes, milliseconds = divmod(milliseconds, 60000)
        seconds, milliseconds = divmod(milliseconds, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

    paths = []
    for item in task["results"]:
        result_path = inside(root, item["result"])
        result = read_json(result_path)
        if not result["segments"]:
            raise ValueError("已有识别结果没有分句时间，无法生成有效 SRT")
        path = result_path.with_name("transcript.srt")
        text = "\n\n".join(f"{index}\n{stamp(segment['start'])} --> {stamp(segment['end'])}\n{segment['text']}"
                             for index, segment in enumerate(result["segments"], 1)) + "\n"
        if path.exists() and path.read_text(encoding="utf-8") != text:
            raise ValueError("已有字幕被修改，保留现场，请另存后再导出")
        path.write_text(text, encoding="utf-8")
        paths.append(str(path))
    return paths
