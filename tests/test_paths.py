from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import support  # noqa: F401  # must precede douyin_text: sets the runtime path and a guarded default workspace
from douyin_text import content, workflow
from douyin_text.common import read_json, write_json
from support import SKILL_ROOT, WorkspaceCase, stored_paths


class WorkspacePathTests(WorkspaceCase):
    def test_records_store_workspace_relative_paths(self):
        task = self.register_review(self.recognize_run(self.task()))
        task = content.deliver(task["id"], "review", self.root)
        saved = read_json(self.root / "runs" / task["id"] / "task.json")
        values = stored_paths(saved)
        self.assertEqual(5, len(values))  # result, markdown, text, review file, delivery file
        for value in values:
            self.assertFalse(Path(value).is_absolute(), value)
            self.assertTrue((self.root / value).is_file(), value)

    def test_moved_workspace_continues_delivery_and_srt(self):
        task = self.register_review(self.recognize_run(self.task()))
        moved = self.move_workspace()
        delivered = content.deliver(task["id"], "review", moved)
        self.assertEqual("completed", delivered["status"])
        self.assertTrue((moved / delivered["delivery"]["file"]).is_file())
        srt = workflow.export_srt(task["id"], moved)
        self.assertTrue(Path(srt[0]).is_relative_to(moved))

    def test_absolute_records_from_older_versions_resolve_after_move(self):
        task = self.register_review(self.recognize_run(self.task()))
        self.write_as_older_version(task)
        moved = self.move_workspace()
        loaded = workflow.load(task["id"], moved)
        self.assertEqual(4, len(stored_paths(loaded)))
        for value in stored_paths(loaded):
            self.assertFalse(Path(value).is_absolute(), value)
            self.assertTrue((moved / value).is_file(), value)
        self.assertEqual("completed", content.deliver(task["id"], "review", moved)["status"])
        self.assertFalse(Path(read_json(moved / "runs" / task["id"] / "task.json")["results"][0]["result"]).is_absolute())

    def test_paths_outside_the_workspace_stay_absolute(self):
        task = self.recognize_run(self.task())
        self.write_as_older_version(task)
        record = self.root / "runs" / task["id"] / "task.json"
        saved = read_json(record)
        manifest = str(self.parent / "assistant" / "runs" / "staging" / "x-publish" / "manifest.json")
        target = str(self.parent / "vault" / "素材" / "文档" / "原文留底.md")
        saved["publication"] = {"manifest": manifest, "receipt_file": str(self.root / "runs" / task["id"] / "receipt.json"),
                                "files": [{"target": target, "source": str(self.root / "runs" / task["id"] / "a.md")}]}
        write_json(record, saved)
        moved = self.move_workspace()
        loaded = workflow.load(task["id"], moved)
        self.assertEqual([str(self.wav)], loaded["inputs"])
        self.assertEqual(manifest, loaded["publication"]["manifest"])
        self.assertEqual(target, loaded["publication"]["files"][0]["target"])
        self.assertEqual(f"runs/{task['id']}/a.md", loaded["publication"]["files"][0]["source"])
        self.assertEqual(f"runs/{task['id']}/receipt.json", loaded["publication"]["receipt_file"])

    def test_text_import_keeps_the_users_source_path(self):
        source = self.parent / "已有文稿.txt"
        source.write_text("已有文稿正文。", encoding="utf-8")
        task = content.plan_text([source], self.root)
        self.assertEqual(str(source.resolve()), task["text_imports"][0]["source"])
        self.assertEqual(f"runs/{task['id']}/sources/0001.txt", task["text_imports"][0]["file"])

    def test_cli_output_names_the_workspace_for_relative_paths(self):
        task = self.recognize_run(self.task())
        process = subprocess.run([sys.executable, "-B", "-X", "utf8", str(SKILL_ROOT / "scripts" / "brain.py"),
                                  "--workspace", str(self.root), "show", task["id"]], capture_output=True, timeout=120)
        self.assertEqual(0, process.returncode, process.stdout.decode("utf-8", "replace"))
        shown = json.loads(process.stdout.decode("utf-8"))
        self.assertEqual(str(self.root.resolve()), shown["workspace"])
        self.assertTrue((Path(shown["workspace"]) / shown["results"][0]["result"]).is_file())
