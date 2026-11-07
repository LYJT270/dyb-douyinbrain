"""Shared fixtures: import the Skill runtime and run it only against throwaway workspaces."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import uuid
import wave
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[1]
# Code that silently falls back to the default workspace would write here; every test checks it never appears.
DEFAULT_WORKSPACE = Path(tempfile.gettempdir()) / f"dyb-douyinbrain-tests-default-{uuid.uuid4().hex[:12]}"
os.environ["DYB_WORKSPACE"] = str(DEFAULT_WORKSPACE)
os.environ["DYB_UPDATE_CHECK"] = "0"  # Offline tests never query public releases.
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL_ROOT / "scripts" / "runtime"))
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from douyin_text import asr, content, credentials, vault, workflow  # noqa: E402
from douyin_text.common import read_json, write_json  # noqa: E402


class Response(io.BytesIO):
    def __init__(self, text="嗯，原文原文。", status="20000000"):
        super().__init__(json.dumps({"result": {"text": text, "utterances": [
            {"text": text, "start_time": 0, "end_time": 100}] if text else []}}).encode())
        self.headers = {"X-Api-Status-Code": status, "X-Tt-Logid": "test-log"}


def path_fields(task: dict):
    """Yield (holder, key) for every task-record field that points at a file inside the workspace."""
    for item in task.get("results", []):
        for key in ("result", "markdown", "text"):
            yield item, key
    for item in task.get("text_imports", []):
        yield item, "file"
    for kind in ("review", "spoken", "archive"):
        for item in task.get(kind, {}).get("files", []):
            yield item, "file"
    for key in ("delivery", "analysis"):
        if key in task:
            yield task[key], "file"
    publication = task.get("publication", {})
    if "receipt_file" in publication:
        yield publication, "receipt_file"
    for item in publication.get("files", []):
        yield item, "source"


def stored_paths(task: dict) -> list[str]:
    return [holder[key] for holder, key in path_fields(task)]


class WorkspaceCase(unittest.TestCase):
    """Each test gets a workspace inside a temporary parent, so the workspace itself can be moved."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        # Windows hosted runners may expose TEMP through an 8.3 alias.
        # Use the same canonical root as the runtime; preserve path and content assertions.
        self.parent = Path(self.temp.name).resolve()
        self.root = self.parent / "workspace"
        self.root.mkdir()
        self.wav = self.parent / "中文录音.wav"  # user media lives outside the workspace
        with wave.open(str(self.wav), "wb") as handle:
            handle.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            handle.writeframes(b"\x00\x00" * 51200)
        write_json(self.root / "config.json", {"chunk_seconds": 1, "asr_timeout_seconds": 5,
                   "assistant_root": str(self.parent / "assistant"), "vault_root": str(self.parent / "vault")})

    def tearDown(self):
        self.temp.cleanup()
        self.assertFalse(DEFAULT_WORKSPACE.exists(), "测试写入了默认 workspace")

    def path(self, value: str, root: Path | None = None) -> Path:
        # Records may hold workspace-relative paths or, from older versions, absolute ones.
        return (root or self.root) / value

    def task(self, purpose: str = "transcribe", **options) -> dict:
        task = workflow.plan([str(self.wav)], self.root)
        instruction = "总结核心观点" if purpose in {"analyze", "rewrite"} else ""
        return workflow.confirm(task["id"], purpose, "本次" + workflow.PURPOSES[purpose],
                                instruction=instruction, root=self.root, **options)

    def recognize_run(self, task: dict) -> dict:
        with patch.object(credentials, "load", return_value={"api_key": "test-value"}), \
                patch.object(asr.request, "urlopen", side_effect=lambda *a, **k: Response()), \
                patch.object(vault, "publish", side_effect=AssertionError("unexpected vault publish")):
            return workflow.run(task["id"], self.root)

    def write_texts(self, task: dict, kind: str) -> list[Path]:
        folder = self.root / "runs" / task["id"] / kind
        folder.mkdir(parents=True, exist_ok=True)
        files = []
        for number, _ in enumerate(task["results"], 1):
            path = folder / f"{number}-{kind}-v1.txt"
            path.write_text(f"第{number}条{kind}正文，保留原意。", encoding="utf-8")
            files.append(path)
        return files

    def register_review(self, task: dict) -> dict:
        return content.register_content(task["id"], self.write_texts(task, "review"), "review", self.root)

    def move_workspace(self) -> Path:
        moved = self.parent / "renamed workspace"
        self.root.rename(moved)
        self.root = moved
        return moved

    def write_as_older_version(self, task: dict) -> None:
        """Rewrite the saved record with absolute paths, as versions before 1.3.0 stored them."""
        record = self.root / "runs" / task["id"] / "task.json"
        saved = read_json(record)
        for holder, key in path_fields(saved):
            holder[key] = str((self.root / holder[key]).resolve())
        write_json(record, saved)
