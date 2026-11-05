"""Register agent-produced content, preserve sources, and verify real deliveries."""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from .common import ROOT, config, digest, inside, now, read_json, relative, write_json
from . import workflow


def immutable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"已有文件内容不同，请另存版本：{path}")
    else:
        with path.open("xb") as handle:
            handle.write(data)


def plan_text(source: Path | list[Path], root: Path = ROOT) -> dict:
    sources = [source] if isinstance(source, Path) else source
    if not sources:
        raise ValueError("文稿列表为空")
    prepared = []
    for value in sources:
        path = Path(value).expanduser().resolve()
        if path.suffix.lower() not in {".txt", ".md"}:
            raise ValueError("已有文稿使用 UTF-8 TXT 或 Markdown")
        data = path.read_bytes()
        if not data.decode("utf-8-sig").strip():
            raise ValueError("文稿为空")
        prepared.append((path, data))
    task_id = "dy-" + uuid.uuid4().hex[:16]
    snapshots = []
    for index, (path, data) in enumerate(prepared, 1):
        snapshot = root / "runs" / task_id / "sources" / (f"{index:04d}" + path.suffix.lower())
        immutable(snapshot, data)
        snapshots.append({"file": relative(root, snapshot), "sha256": digest(snapshot), "source": str(path)})
    task = {"id": task_id, "created": now(), "status": "needs_intent", "input_kind": "text",
            "inputs": [str(path) for path, _ in prepared], "purpose": None, "results": [], "failures": [],
            "text_imports": snapshots, "choices": workflow.PURPOSES,
            "question": "这批文稿需要校对、分析、口播改写或入库？"}
    workflow.save(task, root)
    return task


def restore_text_result(task: dict, root: Path = ROOT, item: dict | None = None) -> dict:
    item = item or task.get("text_import") or task["text_imports"][0]
    source = inside(root, item["file"])
    if digest(source) != item["sha256"]:
        raise ValueError("原始文稿快照发生变化")
    text = source.read_text(encoding="utf-8-sig")
    identity = __import__("hashlib").sha256((item["sha256"] + item["source"]).encode("utf-8")).hexdigest()
    media_id = "text-" + identity
    folder = root / "outputs" / media_id / "provided-v1"
    if (folder / "result.json").exists():
        saved = read_json(folder / "result.json")
        if saved["text"] != text or any(digest(folder / ("transcript." + ext)) != saved["output_sha256"][ext] for ext in ("txt", "md")):
            raise ValueError("原始文稿缓存发生变化")
        return {"id": media_id, "status": "imported", "result": relative(root, folder / "result.json"),
                "markdown": relative(root, folder / "transcript.md"), "text": relative(root, folder / "transcript.txt")}
    result = {"created": task["created"], "engine": "provided-text", "parameters": {},
              "source": {"id": media_id, "title": Path(item["source"]).stem,
                         "author": "未指定", "source": item["source"]},
              "text": text, "segments": [], "duration": None}
    immutable(folder / "transcript.txt", text.encode("utf-8"))
    markdown = "# 原始文稿\n\n- 类型：用户提供文稿，原样留底\n- 来源：" + item["source"] + "\n\n" + text
    immutable(folder / "transcript.md", markdown.encode("utf-8"))
    result["output_sha256"] = {ext: digest(folder / ("transcript." + ext)) for ext in ("txt", "md")}
    immutable(folder / "result.json", (__import__("json").dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return {"id": media_id, "status": "imported", "result": relative(root, folder / "result.json"),
            "markdown": relative(root, folder / "transcript.md"), "text": relative(root, folder / "transcript.txt")}


def originals(task: dict, root: Path) -> list[dict]:
    if not task.get("results"):
        raise ValueError("没有可处理的原始文稿")
    values = []
    for item in task["results"]:
        value = read_json(inside(root, item["result"]))
        for key, ext in (("text", "txt"), ("markdown", "md")):
            if digest(inside(root, item[key])) != value["output_sha256"][ext]:
                raise ValueError("原稿已改变，停止处理并保留现场")
        values.append(value)
    return values


def register_content(task_id: str, files: list[Path], kind: str, root: Path = ROOT,
                     *, evidence: str = "") -> dict:
    task = workflow.load(task_id, root)
    originals(task, root)
    if not task.get("evidence"):
        raise ValueError("先记录用户本次用途")
    if kind not in {"review", "spoken"}:
        raise ValueError("内容类型无效")
    if kind == "spoken" and not (evidence.strip() or task.get("purpose") == "rewrite"):
        raise ValueError("口播改写需要用户实际指令，不能从纯转写自行扩展")
    if len(files) != len(task["results"]):
        raise ValueError("每条成功素材都需要一份独立正文，按 results 的顺序登记")
    sources = {inside(root, item[key]) for item in task["results"] for key in ("text", "markdown", "result")}
    entries = []
    for item, file in zip(task["results"], files):
        path = inside(root, file)
        if path in sources or path.suffix.lower() not in {".txt", ".md"}:
            raise ValueError("校对与改写必须另存为文稿文件")
        if not path.read_text(encoding="utf-8-sig").strip():
            raise ValueError("正文为空")
        entries.append({"id": item["id"], "file": relative(root, path), "sha256": digest(path)})
    task[kind] = {"files": entries, "registered": now(), "evidence": evidence or task["evidence"]}
    if kind == "review":
        task.pop("archive", None)
    if task.get("failures"):
        task["status"] = "incomplete"
    elif kind == "review":
        task["status"] = {"transcribe": "ready_to_deliver", "analyze": "awaiting_analysis",
                          "rewrite": "awaiting_edit", "ingest": "ready_for_ingest",
                          "compile": "awaiting_compile"}[task["purpose"]]
    workflow.save(task, root)
    return task


def checked_content(task: dict, kind: str, root: Path) -> list[dict]:
    entries = task.get(kind, {}).get("files", [])
    if [x["id"] for x in entries] != [x["id"] for x in task["results"]]:
        raise ValueError("尚未完整登记此版本的正文")
    for item in entries:
        if digest(inside(root, item["file"])) != item["sha256"]:
            raise ValueError("已登记正文发生变化，请另存并重新登记当前版本")
    return entries


def numbers(task: dict, root: Path) -> list[int]:
    jobs = root / "runs" / task["id"] / "jobs.json"
    order = {x["id"]: n for n, x in enumerate(read_json(jobs), 1)} if jobs.exists() else {}
    return [order.get(item["id"], n) for n, item in enumerate(task["results"], 1)]


def deliver(task_id: str, kind: str = "review", root: Path = ROOT) -> dict:
    task = workflow.load(task_id, root)
    originals(task, root)
    if kind == "raw":
        entries = [{"id": x["id"], "file": x["text"]} for x in task["results"]]
    else:
        entries = checked_content(task, kind, root)
    indices = numbers(task, root)
    bodies = [re.sub(r"\s+", " ", inside(root, x["file"]).read_text(encoding="utf-8-sig")).strip() for x in entries]
    text = "\r\n\r\n".join(f"{n}.{body}" for n, body in zip(indices, bodies)) + "\r\n"
    data = b"\xef\xbb\xbf" + text.encode("utf-8")
    checksum = __import__("hashlib").sha256(data).hexdigest()
    label = {"review": "校对逐字稿", "spoken": "口播稿", "raw": "机器原文"}[kind]
    file = root / "outputs" / "deliveries" / task_id / f"{label}-{checksum[:10]}.txt"
    immutable(file, data)
    task["delivery"] = {"file": relative(root, file), "sha256": checksum, "kind": kind,
                        "count": len(entries), "numbers": indices, "at": now(),
                        "complete": not bool(task.get("failures"))}
    if task["purpose"] in {"transcribe", "rewrite"} and not task.get("failures"):
        if (task["purpose"] == "transcribe" and kind in {"review", "raw"}) or kind == "spoken":
            task["status"] = "completed"
    workflow.save(task, root)
    return task


def relative_target(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or path.drive or ".." in path.parts or not value.strip():
        raise ValueError("知识库目标应为库内相对路径")
    return path.as_posix()


def archive(task_id: str, root: Path = ROOT, *, prefix: str = "", raw_file: Path | None = None,
            reviewed_file: Path | None = None, include_spoken: bool = False,
            spoken_file: Path | None = None, evidence: str = "") -> dict:
    task = workflow.load(task_id, root)
    if task.get("purpose") not in {"ingest", "compile"} or not task.get("evidence"):
        raise ValueError("本次未选择入库")
    if task.get("failures"):
        raise ValueError("本批尚未完整完成，先处理或明确缩小收录范围")
    values = originals(task, root)
    reviewed = checked_content(task, "review", root)
    folder = root / "runs" / task_id / "archive"
    if bool(raw_file) != bool(reviewed_file):
        raise ValueError("自定义归档时同时提供原文与校对稿")
    if not raw_file:
        raw_file, reviewed_file = folder / "原文留底.md", folder / "校对逐字稿.md"
        raw = ["# 原文留底", "", "本页仅作来源归档和核查，日常使用请读[校对逐字稿](校对逐字稿.md)。", ""]
        fixed = ["# 校对逐字稿", "", "原始内容见[原文留底](原文留底.md)，本页为校对后的来源正文。", ""]
        for n, value, review in zip(numbers(task, root), values, reviewed):
            source = value["source"]
            title = source["title"].replace("\n", " ")
            metadata = [f"## {n}. {title}", "", "- 来源：" + source["source"],
                        "- 作者：" + source.get("author", "未指定"), "- 版本时间：" + value["created"], ""]
            raw += metadata + [value["text"], ""]
            fixed += metadata + [inside(root, review["file"]).read_text(encoding="utf-8-sig"), ""]
        immutable(raw_file, "\n".join(raw).encode("utf-8"))
        immutable(reviewed_file, "\n".join(fixed).encode("utf-8"))
    raw_file, reviewed_file = inside(root, raw_file), inside(root, reviewed_file)
    if raw_file == reviewed_file or raw_file.parent != reviewed_file.parent:
        raise ValueError("原文与校对归档应是同一批次下的两个文件")
    raw_text, fixed_text = [x.read_text(encoding="utf-8-sig") for x in (raw_file, reviewed_file)]
    if any(value["text"] not in raw_text for value in values):
        raise ValueError("原文归档缺少原始内容，原文不能润色或删改")
    if any(inside(root, entry["file"]).read_text(encoding="utf-8-sig") not in fixed_text for entry in reviewed):
        raise ValueError("校对归档缺少已登记的正文")
    if reviewed_file.name not in raw_text or raw_file.name not in fixed_text:
        raise ValueError("原文与校对归档需要互相链接")
    default = {"reference": "素材/文档", "benchmark": "素材/对标", "own": "素材/创作/工作资料"}
    prefix = relative_target(prefix or default[task["category"]] + "/" + task_id)
    pairs = [(raw_file, "source_archive"), (reviewed_file, "reviewed_source")]
    if spoken_file and not include_spoken:
        raise ValueError("口播归档需要明确选择 --include-spoken")
    if include_spoken:
        if not evidence.strip():
            raise ValueError("收录口播改写稿需要用户点名收录的实际原话")
        spoken = checked_content(task, "spoken", root)
        if spoken_file:
            spoken_file = inside(root, spoken_file)
            if spoken_file.parent != raw_file.parent:
                raise ValueError("口播衍生稿应与本批来源归为同组")
        else:
            spoken_file = raw_file.parent / "口播改写稿.md"
            lines = ["# 口播改写稿", "", f"来源：[校对逐字稿]({reviewed_file.name})；核查：[原文留底]({raw_file.name})。", ""]
            for n, item in zip(numbers(task, root), spoken):
                lines += [f"## {n}", "", inside(root, item["file"]).read_text(encoding="utf-8-sig"), ""]
            immutable(spoken_file, "\n".join(lines).encode("utf-8"))
        body = spoken_file.read_text(encoding="utf-8-sig")
        if any(inside(root, entry["file"]).read_text(encoding="utf-8-sig") not in body for entry in spoken):
            raise ValueError("口播归档缺少已登记的正文")
        if reviewed_file.name not in body:
            raise ValueError("口播归档需要引用校对来源")
        pairs.append((spoken_file, "spoken_derivative"))
    task["archive"] = {"at": now(), "include_spoken_evidence": evidence if include_spoken else "", "files": [
        {"file": relative(root, path), "target": prefix + "/" + path.name, "sha256": digest(path), "role": role}
        for path, role in pairs]}
    workflow.save(task, root)
    return task


def checked_archive(task: dict, root: Path) -> list[dict]:
    originals(task, root)
    checked_content(task, "review", root)
    entries = task.get("archive", {}).get("files", [])
    roles = [item.get("role") for item in entries]
    if roles not in [["source_archive", "reviewed_source"], ["source_archive", "reviewed_source", "spoken_derivative"]]:
        raise ValueError("缺少成组的原文与校对归档")
    if len(entries) == 3:
        if not task["archive"].get("include_spoken_evidence"):
            raise ValueError("缺少口播稿收录指令")
        checked_content(task, "spoken", root)
    for item in entries:
        relative_target(item["target"])
        if digest(inside(root, item["file"])) != item["sha256"]:
            raise ValueError("归档格式已改变，请重新核对并登记归档版本")
    return entries


def record_publication(task_id: str, receipt_file: Path, root: Path = ROOT) -> dict:
    """Read back files written through the target vault's own permitted method."""
    task = workflow.load(task_id, root)
    if task.get("purpose") not in {"ingest", "compile"} or not task.get("evidence") or task.get("failures"):
        raise ValueError("本任务未满足入库条件")
    required = checked_archive(task, root)
    receipt_file = inside(root, receipt_file)
    receipt = read_json(receipt_file)
    vault_value = config(root).get("vault_root")
    if not vault_value:
        raise ValueError("先配置目标知识库目录")
    vault = Path(vault_value).resolve()
    files = receipt.get("files", [])
    targets = [relative_target(item["target"]) for item in files]
    if len(targets) != len(set(targets)) or not {x["target"] for x in required}.issubset(targets):
        raise ValueError("回执必须包含原文和校对稿，且目标不能重复")
    if task["purpose"] == "ingest" and set(targets) != {x["target"] for x in required}:
        raise ValueError("只入库任务不能借回执扩展为编译")
    if task["purpose"] == "compile" and len(files) <= len(required):
        raise ValueError("编译任务还需要实际知识页")
    checked = []
    for item in files:
        source = inside(root, item["source"])
        target = inside(vault, item["target"])
        if not target.is_file() or digest(source) != digest(target):
            raise ValueError("目标文件尚未实际写入或内容不一致：" + str(target))
        registered = next((x for x in required if x["target"] == item["target"]), None)
        if registered and digest(source) != registered["sha256"]:
            raise ValueError("回执中的来源与已登记归档不一致")
        checked.append({"target": str(target), "source": relative(root, source), "sha256": digest(target)})
    task.update(status="published", published_at=now(), publication={"method": "target_vault_rules",
                "files": checked, "receipt_file": relative(root, receipt_file), "commit_status": "not_checked"})
    workflow.save(task, root)
    return task
