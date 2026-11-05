from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from unittest.mock import patch

import support  # noqa: F401  # must precede douyin_text: sets the runtime path and a guarded default workspace
from douyin_text import asr, content, setup, workflow
from douyin_text.common import read_json, write_json
from support import WorkspaceCase

START, END = "<!-- dyb-douyinbrain:execution:start -->", "<!-- dyb-douyinbrain:execution:end -->"


class ContentTests(WorkspaceCase):
    def text_task(self, *bodies: str, purpose: str = "transcribe") -> dict:
        sources = []
        for number, body in enumerate(bodies, 1):
            source = self.parent / f"已有文稿{number}.txt"
            source.write_text(body, encoding="utf-8")
            sources.append(source)
        task = content.plan_text(sources, self.root)
        workflow.confirm(task["id"], purpose, "本次" + workflow.PURPOSES[purpose], root=self.root)
        with patch.object(asr, "recognize", side_effect=AssertionError("provided text must not reach ASR")):
            return workflow.run(task["id"], self.root)

    def archived_ingest(self) -> dict:
        task = self.recognize_run(self.task("ingest"))
        self.register_review(task)
        return content.archive(task["id"], self.root)

    def test_plan_text_snapshots_sources_without_asr(self):
        task = self.text_task("第一篇正文。", "第二篇正文。")
        self.assertEqual("awaiting_review", task["status"])
        self.assertEqual(["第一篇正文。", "第二篇正文。"],
                         [read_json(self.path(item["result"]))["text"] for item in task["results"]])
        self.assertEqual("第一篇正文。", (self.parent / "已有文稿1.txt").read_text(encoding="utf-8"))

    def test_review_needs_one_separate_file_per_result(self):
        task = self.text_task("第一篇正文。", "第二篇正文。")
        first, second = self.write_texts(task, "review")
        with self.assertRaisesRegex(ValueError, "每条成功素材"):
            content.register_content(task["id"], [first], "review", self.root)
        with self.assertRaisesRegex(ValueError, "另存"):
            content.register_content(task["id"], [first, self.path(task["results"][1]["text"])], "review", self.root)
        second.write_text("  \n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "正文为空"):
            content.register_content(task["id"], [first, second], "review", self.root)
        second.write_text("第二篇校对稿。", encoding="utf-8")
        self.assertEqual("ready_to_deliver", content.register_content(task["id"], [first, second], "review", self.root)["status"])

    def test_spoken_rewrite_of_a_transcription_needs_the_users_words(self):
        task = self.text_task("原稿正文。")
        files = self.write_texts(task, "spoken")
        with self.assertRaisesRegex(ValueError, "实际指令"):
            content.register_content(task["id"], files, "spoken", self.root)
        task = content.register_content(task["id"], files, "spoken", self.root, evidence="改成口播稿")
        self.assertEqual("改成口播稿", task["spoken"]["evidence"])

    def test_delivery_merges_numbered_paragraphs_with_bom_and_crlf(self):
        task = self.text_task("原稿一。", "原稿二。")
        first, second = self.write_texts(task, "review")
        first.write_text("第一行\n第二行", encoding="utf-8")
        second.write_text("第三行", encoding="utf-8")
        content.register_content(task["id"], [first, second], "review", self.root)
        task = content.deliver(task["id"], "review", self.root)
        data = (self.root / task["delivery"]["file"]).read_bytes()
        self.assertEqual(b"\xef\xbb\xbf" + "1.第一行 第二行\r\n\r\n2.第三行\r\n".encode("utf-8"), data)
        self.assertEqual("校对逐字稿-" + hashlib.sha256(data).hexdigest()[:10] + ".txt", Path(task["delivery"]["file"]).name)
        self.assertEqual("completed", task["status"])

    def test_changed_registered_text_blocks_delivery(self):
        task = self.text_task("原稿。")
        files = self.write_texts(task, "review")
        content.register_content(task["id"], files, "review", self.root)
        files[0].write_text("登记后又改过", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "已登记正文发生变化"):
            content.deliver(task["id"], "review", self.root)

    def test_archive_pairs_raw_and_reviewed_with_mutual_links(self):
        task = self.archived_ingest()
        raw, reviewed = (self.path(item["file"]) for item in task["archive"]["files"])
        original = read_json(self.path(task["results"][0]["result"]))["text"]
        self.assertIn(original, raw.read_text(encoding="utf-8"))
        self.assertIn("第1条review正文", reviewed.read_text(encoding="utf-8"))
        self.assertIn(reviewed.name, raw.read_text(encoding="utf-8"))
        self.assertIn(raw.name, reviewed.read_text(encoding="utf-8"))
        self.assertEqual([f"素材/文档/{task['id']}/原文留底.md", f"素材/文档/{task['id']}/校对逐字稿.md"],
                         [item["target"] for item in task["archive"]["files"]])
        with self.assertRaisesRegex(ValueError, "点名收录"):
            content.archive(task["id"], self.root, include_spoken=True)

    def test_record_publication_reads_back_the_vault_files(self):
        task = self.archived_ingest()
        vault = self.parent / "vault"
        files = []
        for item in task["archive"]["files"]:
            target = vault / item["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.path(item["file"]), target)
            files.append({"source": item["file"], "target": item["target"]})
        receipt = self.root / "runs" / task["id"] / "receipt.json"
        write_json(receipt, {"files": files})
        (vault / files[0]["target"]).write_text("写入时被改动", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "内容不一致"):
            content.record_publication(task["id"], receipt, self.root)
        shutil.copyfile(self.path(files[0]["source"]), vault / files[0]["target"])
        published = content.record_publication(task["id"], receipt, self.root)
        self.assertEqual("published", published["status"])
        self.assertEqual(files[0]["source"], published["publication"]["files"][0]["source"])
        self.assertEqual(str((vault / files[0]["target"]).resolve()), published["publication"]["files"][0]["target"])


class SetupTests(WorkspaceCase):
    def test_init_registers_the_workspace_and_keeps_user_rules(self):
        rules = self.root / "AGENTS.md"
        rules.write_text("# 我的规则\n\n保留这一段。\n", encoding="utf-8")
        appdata = self.parent / "appdata"
        with patch.dict(os.environ, {"LOCALAPPDATA": str(appdata)}):
            setup.initialize(self.root, register=True)
            setup.initialize(self.root, register=True)
        body = rules.read_text(encoding="utf-8")
        self.assertTrue(body.startswith("# 我的规则\n\n保留这一段。\n"))
        self.assertEqual(1, body.count(START))
        self.assertEqual(1, body.count(END))
        self.assertIn(f"工作目录：`{self.root.resolve().as_posix()}`", body)
        settings = read_json(appdata / "dyb-douyinbrain" / "settings.json")
        self.assertEqual(str(self.root.resolve()), settings["workspace"])
        self.assertEqual(str(rules.resolve()), settings["workspace_entry"])

    def test_init_keeps_the_vault_outside_the_workspace(self):
        with self.assertRaisesRegex(ValueError, "分别放置"):
            setup.initialize(self.root, vault=self.root / "vault")
