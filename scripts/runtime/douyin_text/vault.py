from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .common import ROOT, config, digest, inside, now, read_json, safe_name, write_json
from .workflow import load, save


def publication_plan(task: dict, root: Path = ROOT) -> list[dict]:
    if task.get("purpose") not in {"ingest", "compile"} or not task.get("evidence"):
        raise ValueError("本次未选择入库用途")
    if not task.get("results") or task.get("failures"):
        raise ValueError("转写尚未完整完成，暂不发布知识库")
    if not task.get("archive"):
        raise ValueError("请先完成校对并用 archive 登记成组的原文留底与校对稿")
    from .content import checked_archive
    return checked_archive(task, root)


def prepare(task: dict, root: Path = ROOT, *, pages: list[dict] | None = None,
            staging_root: Path | None = None) -> tuple[Path, dict]:
    cfg = config(root)
    vault = Path(cfg["vault_root"])
    staging = staging_root or Path(cfg["assistant_root"]) / "runs" / "staging"
    transaction = task["id"] + "-publish"
    folder = staging / transaction
    entries = publication_plan(task, root)
    if task["purpose"] == "compile" and not pages:
        raise ValueError("本任务需要 Agent 先生成知识页；可用 preview 查看原始材料的 sources 路径")
    if task["purpose"] == "ingest" and pages:
        raise ValueError("本次只授权原稿入库，请为编译用途创建新任务")
    copies = []
    files = []
    for index, entry in enumerate(entries):
        filename = f"raw-{index:04}.md"
        copies.append((filename, inside(root, entry["file"]).read_bytes()))
        files.append({"source": filename, "target": entry["target"], "expected_sha256": None})
    for index, page in enumerate(pages or []):
        source = inside(root, page["file"])
        target = inside(vault, page["target"])
        relative = target.relative_to(vault.resolve()).as_posix()
        if relative.split("/")[0] not in {"知识库", "个人"} or target.suffix != ".md":
            raise ValueError("知识页目标应位于知识库或个人目录，且为 Markdown")
        expected = page.get("expected_sha256")
        if target.is_file() and (not expected or digest(target) != expected):
            raise ValueError("更新已有知识页需要读取原页并提供匹配的 SHA-256")
        if not target.exists() and expected:
            raise ValueError("知识页目标已变化，请重新读取")
        filename = f"page-{index:04}.md"
        copies.append((filename, source.read_bytes()))
        files.append({"source": filename, "target": relative, "expected_sha256": expected})
    manifest = {"id": transaction, "action": "compile" if pages else "ingest",
                "object": f"视频逐字稿：{task['id']}", "files": files}
    manifest_path = folder / "manifest.json"
    if manifest_path.exists() and read_json(manifest_path) != manifest:
        raise ValueError("本事务已有其他发布输入，请保留现场并创建新任务")
    for filename, data in copies:
        path = folder / filename
        if path.exists() and path.read_bytes() != data:
            raise ValueError("发布暂存原件发生变化，请保留现场并创建新任务")
    folder.mkdir(parents=True, exist_ok=True)
    for filename, data in copies:
        path = folder / filename
        if not path.exists():
            path.write_bytes(data)
    if not manifest_path.exists():
        write_json(manifest_path, manifest)
    return manifest_path, manifest


def publish(task_id: str, root: Path = ROOT, *, pages: list[dict] | None = None) -> dict:
    task = load(task_id, root)
    if task.get("status") == "published":
        return task
    cfg = config(root)
    if not cfg.get("assistant_root"):
        raise ValueError("当前知识库未配置个人助手发布入口；按目标库现行规则收录后，用 record-publication 核对实际文件")
    assistant = Path(cfg["assistant_root"])
    owner = read_json(assistant / "config.json")
    if (owner.get("stage") != "production" or owner.get("ownership", {}).get("knowledge") is not True
            or not owner.get("collection_start")
            or Path(owner["production_vault"]).resolve() != Path(cfg["vault_root"]).resolve()):
        raise ValueError("现有知识库入口的职责或目标配置不匹配，请核对当前规则")
    publication_plan(task, root)
    manifest_path = assistant / "runs" / "staging" / (task["id"] + "-publish") / "manifest.json"
    if manifest_path.exists() and not pages and task.get("publication", {}).get("inputs"):
        manifest = read_json(manifest_path)
    else:
        manifest_path, manifest = prepare(task, root, pages=pages)
    hashes = {entry["source"]: digest(inside(manifest_path.parent, entry["source"]))
              for entry in manifest["files"]}
    prior_inputs = task.get("publication", {}).get("inputs")
    if prior_inputs and hashes != prior_inputs:
        raise ValueError("已提交事务的暂存文件发生变化，请保留现场并创建新任务")
    prior_manifest = task.get("publication", {}).get("manifest_sha256")
    if prior_manifest and digest(manifest_path) != prior_manifest:
        raise ValueError("已提交事务的发布清单发生变化，请保留现场")
    publication = {"manifest": str(manifest_path), "inputs": hashes,
                   "manifest_sha256": digest(manifest_path)}
    task.update(status="publishing", publication=publication)
    save(task, root)
    record_dir = root / "runs" / task_id
    # No shell interpolation; the existing publisher owns locking, indexing and commit semantics.
    try:
        process = subprocess.run([str(assistant / ".venv" / "Scripts" / "python.exe"), "-B", "-X", "utf8",
                                  str(assistant / "scripts" / "vault.py"), "publish", str(manifest_path)],
                                 cwd=assistant, capture_output=True, timeout=300)
    except subprocess.TimeoutExpired:
        task.update(status="publication_unknown", publication={**publication,
                    "error": "发布入口超时，请核对同一事务回执，再用原清单继续"})
        save(task, root)
        return task
    (record_dir / "publish.stdout.txt").write_bytes(process.stdout)
    (record_dir / "publish.stderr.txt").write_bytes(process.stderr)
    if process.returncode:
        task.update(status="publish_failed", publication={**publication,
                    "error": "统一发布入口未成功，请查看本任务 publish.stderr.txt；原稿已保留"})
        save(task, root)
        return task
    try:
        response = json.loads(process.stdout.decode("utf-8-sig"))
    except (ValueError, UnicodeError):
        task.update(status="publication_unknown", publication={**publication,
                    "error": "发布进程返回内容无法核对，请读取同一事务的实际回执"})
        save(task, root)
        return task
    if response.get("status") not in {"published", "already_published", "no_change"}:
        raise RuntimeError("知识库入口返回了未确认的发布状态")
    task.update(status="published", publication={**publication, "receipt": response,
                "targets": [entry["target"] for entry in manifest["files"]]}, published_at=now())
    save(task, root)
    return task
