from __future__ import annotations

import contextlib
import re
import uuid
from datetime import date
from pathlib import Path

from . import acquisition, asr, credentials, media
from .common import ROOT, config, digest, inside, now, read_json, relative, write_json

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
        raise ValueError("请选择具体的总结或分析要求")
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


@contextlib.contextmanager
def artifact_lock(folder: Path):
    import msvcrt
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "work.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError("另一个任务正在处理同一媒体，请等待其完成，避免重复调用") from None
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def render_markdown(result: dict) -> str:
    job = result["source"]
    lines = ["# " + job["title"], "", "- 类型：机器语音识别原稿（未经人工校对）",
             "- 来源：" + job["source"], "- 作者：" + job.get("author", "未指定"),
             "- 转写时间：" + result["created"], "- 服务：豆包录音文件识别极速版",
             "- 处理：保留口头语和重复表达；开启标点；关闭语义顺滑和数字规整"]
    if job.get("published"):
        lines.append("- 视频发布时间：" + job["published"])
    return "\n".join(lines) + "\n\n## 逐字稿\n\n" + result["text"] + "\n"


def transcribe(job: dict, task: dict, root: Path = ROOT, *, retry_failed: bool = False) -> dict:
    version = asr.PROFILE + ("-" + task["revision"] if task.get("revision") else "")
    output = root / "outputs" / job["id"] / version
    folder = root / ".cache" / job["id"] / version
    result_path = output / "result.json"
    with artifact_lock(folder):
        if result_path.exists():
            result = read_json(result_path)
            for suffix in ("md", "txt"):
                path = output / ("transcript." + suffix)
                if not path.is_file() or digest(path) != result["output_sha256"][suffix]:
                    raise RuntimeError("已有原稿被修改，保留现场；请明确要求重新转写以另存新版本")
            return {"id": job["id"], "status": "reused", "result": relative(root, result_path),
                    "markdown": relative(root, output / "transcript.md"), "text": relative(root, output / "transcript.txt")}
        cfg = config(root)
        chunks = media.extract(job, folder / "audio", cfg["chunk_seconds"])
        recognized = []
        for index, chunk in enumerate(chunks):
            chunk_path = folder / f"chunk-{index:05d}.json"
            prior = read_json(chunk_path) if chunk_path.exists() else {}
            if prior.get("status") == "succeeded":
                recognized.append(prior["result"])
                continue
            if prior and not retry_failed:
                raise RuntimeError("本媒体有失败或结果未知的请求。请先核对，再明确重试；已成功片段会复用")
            auth = credentials.load(root)
            request_id = str(uuid.uuid4())
            attempt = {"status": "submitting", "request_id": request_id, "created": now(),
                       "audio_sha256": chunk["sha256"]}
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
        output.mkdir(parents=True, exist_ok=True)
        (output / "transcript.txt").write_text(text + "\n", encoding="utf-8")
        (output / "transcript.md").write_text(render_markdown(result), encoding="utf-8")
        result["output_sha256"] = {suffix: digest(output / ("transcript." + suffix)) for suffix in ("md", "txt")}
        write_json(result_path, result)
        return {"id": job["id"], "status": "transcribed", "result": relative(root, result_path),
                "markdown": relative(root, output / "transcript.md"), "text": relative(root, output / "transcript.txt")}


def run(task_id: str, root: Path = ROOT, *, retry_evidence: str = "") -> dict:
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
    task.update(status="running", failures=[], results=[])
    save(task, root)
    try:
        if task.get("input_kind") == "text":
            from .content import restore_text_result
            sources = task.get("text_imports") or [task["text_import"]]
            task["results"] = [restore_text_result(task, root, item) for item in sources]
            task["status"] = "awaiting_review"
            save(task, root)
            return task
        jobs = media.discover(task["inputs"], task["scope"], task_path(task_id, root).parent, root)
        if not jobs:
            raise ValueError("所选范围没有可处理的视频")
        write_json(task_path(task_id, root).parent / "jobs.json", jobs)
        for job in jobs:
            try:
                task["results"].append(transcribe(job, task, root, retry_failed=bool(retry_evidence)))
            except Exception as exc:
                task["failures"].append({"id": job["id"], "error": str(exc)})
            save(task, root)
        if task["failures"]:
            task["status"] = "incomplete"
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
        task.update(status="failed", failures=[failure])
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
