from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from support import WorkspaceCase
from douyin_text import personal_vault as kb, setup, vault_migration as migration
from douyin_text.common import artifact_lock, digest, read_json, write_json


class VaultMigrationTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.vault = self.parent / "vault"

    def connect_local(self):
        setup.initialize(self.root, vault=self.vault, create_vault=True)
        kb.save({
            "schema": 1,
            "id": "test-local-vault",
            "vault_root": str(self.vault.resolve()),
            "profile_entry": str((self.vault / "个人/档案/基本资料.md").resolve()),
            "scope": "workspace",
            "host": "custom",
            "evidence": "隔离迁移测试 fixture",
            "write_mode": "local",
            "rules": kb.rules(self.vault),
            "modules": ["life", "work", "learning"],
            "fields": {},
            "answers": [],
            "skipped": [],
            "temporary_tasks": [],
            "profile_sha256": "-",
            "focus": "life",
            "selected": "life",
            "pending_domains": [],
            "domain_started": {},
            "progress": {"topics": {}},
            "collection_paused": False,
            "interview_paused": False,
        }, self.root)

    def write_manifest(self, rows, replacements=None, name="migration.json"):
        path = self.root / "manifests" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, {"files": rows, "replacements": replacements or []})
        return path

    def profile_row(self, target="生活/个人档案/基本资料.md"):
        profile = self.vault / "个人/档案/基本资料.md"
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_bytes(("# 个人基本资料\r\n\r\n"
                             "<!-- cy-profile:background:start -->\r\n"
                             "## 背景\r\n\r\n原始个人档案。\r\n\r\n"
                             "<!-- cy-profile:background:end -->\r\n").encode("utf-8"))
        state = kb.state(self.root)
        state["profile_sha256"] = digest(profile)
        kb.save(state, self.root)
        return {"source": "个人/档案/基本资料.md", "target": target}

    def test_complete_mapping_repairs_links_metadata_and_keeps_history_bytes(self):
        self.connect_local()
        self.profile_row()
        profile = self.vault / "个人/档案/基本资料.md"
        article = self.vault / "旧/原文.md"
        article.parent.mkdir(parents=True)
        article.write_bytes(("---\r\nsources:\r\n  - 方法/主题.md\r\n---\r\n"
                             "[主题](../方法/主题.md)\r\n[[方法/主题.md|主题]]\r\n").encode("utf-8"))
        topic = self.vault / "方法/主题.md"
        topic.parent.mkdir(parents=True)
        topic.write_bytes(b"\xef\xbb\xbf" + "主题内容\r\n".encode("utf-8"))
        index = self.vault / "index.md"
        index.write_bytes("[原文](旧/原文.md)\n[主题](方法/主题.md)\n".encode("utf-8"))
        runtime = self.vault / ".dyb-vault-runtime"
        runtime.mkdir()
        write_json(runtime / "catalog.json", {
            "旧/原文.md": {"target": "旧/原文.md", "sha256": digest(article), "role": "knowledge",
                           "sources": ["方法/主题.md"]},
            "方法/主题.md": {"target": "方法/主题.md", "sha256": digest(topic), "role": "knowledge"},
        })
        receipt = self.root / ".local/vault/transactions/old/transaction.json"
        receipt.parent.mkdir(parents=True)
        receipt_bytes = b'{ "status": "saved", "task": "past receipt", "profile": false, "module": "life" }\r\n'
        receipt.write_bytes(receipt_bytes)
        original_article, original_topic, original_profile = article.read_bytes(), topic.read_bytes(), profile.read_bytes()
        hashes = {"旧/原文.md": digest(article), "方法/主题.md": digest(topic),
                  "个人/档案/基本资料.md": digest(profile)}
        manifest = self.write_manifest([
            {"source": "旧/原文.md", "target": "学习/资料/原文.md"},
            {"source": "方法/主题.md", "target": "工作/方法/主题.md"},
            {"source": "个人/档案/基本资料.md", "target": "生活/个人档案/基本资料.md"},
        ])

        prepared = migration.plan(self.root, manifest)
        self.assertEqual("ready", prepared["status"])
        self.assertEqual(prepared["id"], prepared["migration_id"])
        result = migration.apply(self.root, prepared["id"], "用户明确确认该预览清单")
        self.assertEqual("complete", result["status"], result)

        moved_article = self.vault / "学习/资料/原文.md"
        moved_topic = self.vault / "工作/方法/主题.md"
        moved_profile = self.vault / "生活/个人档案/基本资料.md"
        self.assertFalse(article.exists())
        self.assertFalse(topic.exists())
        self.assertFalse(profile.exists())
        self.assertFalse((self.vault / "旧").exists())
        self.assertFalse((self.vault / "方法").exists())
        self.assertFalse((self.vault / "个人").exists())
        article_text = moved_article.read_bytes().decode("utf-8")
        self.assertIn("sources:\r\n  - 工作/方法/主题.md", article_text)
        self.assertIn("[主题](" + quote("../../工作/方法/主题.md", safe="/.-_~") + ")", article_text)
        self.assertIn("[[工作/方法/主题.md|主题]]", article_text)
        self.assertEqual(original_topic, moved_topic.read_bytes())
        self.assertEqual(original_profile, moved_profile.read_bytes())
        index_text = index.read_text(encoding="utf-8")
        self.assertIn(quote("学习/资料/原文.md", safe="/.-_~"), index_text)
        self.assertIn(quote("工作/方法/主题.md", safe="/.-_~"), index_text)
        updated_catalog = read_json(runtime / "catalog.json")
        self.assertIn("学习/资料/原文.md", updated_catalog)
        self.assertIn("工作/方法/主题.md", updated_catalog)
        self.assertEqual(["工作/方法/主题.md"], updated_catalog["学习/资料/原文.md"]["sources"])
        self.assertEqual(receipt_bytes, receipt.read_bytes())

        path_map = read_json(runtime / "path-migrations.json")
        self.assertTrue(any(row["source"] == "@profile" and row["target"] == "生活/个人档案/基本资料.md"
                            for row in path_map["entries"]))
        self.assertEqual(("学习/资料/原文.md", digest(moved_article)),
                         migration.resolve_reference(self.vault, "旧/原文.md", hashes["旧/原文.md"]))
        self.assertEqual(("生活/个人档案/基本资料.md", digest(moved_profile)),
                         migration.resolve_reference(self.vault, "@profile", hashes["个人/档案/基本资料.md"]))
        state = kb.state(self.root)
        self.assertEqual(str(moved_profile), state["profile_entry"])
        self.assertEqual(digest(moved_profile), state["profile_sha256"])
        backup = Path(result["backup"])
        self.assertEqual(original_article, (backup / "files/旧/原文.md").read_bytes())
        self.assertEqual(original_topic, (backup / "files/方法/主题.md").read_bytes())
        self.assertEqual(original_profile, (backup / "files/个人/档案/基本资料.md").read_bytes())
        answer = kb.answer({"answer": "迁移后继续确认背景。", "domain": "life",
                            "fields": {"background": "迁移后更新的背景"}}, self.root)
        self.assertEqual("saved", answer["saving"]["status"], answer)

    def test_collision_and_concurrent_content_change_block_apply(self):
        self.connect_local()
        self.profile_row()
        profile = self.vault / "个人/档案/基本资料.md"
        source = self.vault / "旧.md"
        source.write_text("原文", encoding="utf-8")
        (self.vault / "生活").mkdir(exist_ok=True)
        (self.vault / "生活/已占用.md").write_text("目标", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "目标文件已存在"):
            migration.plan(self.root, self.write_manifest([
                {"source": "旧.md", "target": "生活/已占用.md"},
                {"source": "个人/档案/基本资料.md", "target": "生活/个人档案/档案.md"},
            ], name="collision.json"))
        with self.assertRaisesRegex(ValueError, "大小写不敏感碰撞"):
            migration.plan(self.root, self.write_manifest([
                {"source": "旧.md", "target": "学习/A.md"},
                {"source": "个人/档案/基本资料.md", "target": "学习/a.md"},
            ], name="case-collision.json"))

        manifest = self.write_manifest([
            {"source": "旧.md", "target": "学习/旧.md"},
            {"source": "个人/档案/基本资料.md", "target": "生活/个人档案/档案.md"},
            {"source": "生活/已占用.md", "target": "生活/已占用.md"},
        ], name="concurrent.json")
        prepared = migration.plan(self.root, manifest)
        source.write_text("人工并发修改", encoding="utf-8")
        result = migration.apply(self.root, prepared["id"], "确认")
        self.assertEqual("interrupted", result["status"])
        self.assertTrue(source.exists())
        self.assertFalse((self.vault / "学习/旧.md").exists())
        self.assertIn("发生变化", result["error"])

    def test_moved_owner_rebases_relative_links_and_root_paths_keep_root_semantics(self):
        self.connect_local()
        self.profile_row()
        index = self.vault / "index.md"
        index.write_text("[概念](旧知识/概念.md)\n", encoding="utf-8")
        owner = self.vault / "旧知识/概念.md"
        owner.parent.mkdir(parents=True)
        owner.write_text(
            "---\n"
            "sources: [旧资料/原文.md]\n"
            "---\n"
            "[索引](../index.md)\n"
            "[规则](../AGENTS.md)\n"
            "[保留资料](../生活/留存.md)\n"
            "[[旧资料/原文.md]]\n"
            "[带空格路径](<../旧资料/a b (copy).md>)\n",
            encoding="utf-8",
        )
        source = self.vault / "旧资料/原文.md"
        source.parent.mkdir(parents=True)
        source.write_text("原文", encoding="utf-8")
        spaced = self.vault / "旧资料/a b (copy).md"
        spaced.write_text("带空格和括号", encoding="utf-8")
        retained = self.vault / "生活/留存.md"
        retained.write_text("保留原位置", encoding="utf-8")
        manifest = self.write_manifest([
            {"source": "旧知识/概念.md", "target": "学习/资料/概念.md"},
            {"source": "旧资料/原文.md", "target": "工作/资料/原文.md"},
            {"source": "旧资料/a b (copy).md", "target": "学习/来源/a b (copy).md"},
            {"source": "生活/留存.md", "target": "生活/留存.md"},
            {"source": "个人/档案/基本资料.md", "target": "生活/个人档案/基本资料.md"},
        ])
        prepared = migration.plan(self.root, manifest)
        self.assertEqual("ready", prepared["status"])
        result = migration.apply(self.root, prepared["id"], "确认链接和来源路径")
        self.assertEqual("complete", result["status"], result)
        moved = (self.vault / "学习/资料/概念.md").read_text(encoding="utf-8")
        self.assertIn("sources: [工作/资料/原文.md]", moved)
        self.assertIn("[索引](../../index.md)", moved)
        self.assertIn("[规则](../../AGENTS.md)", moved)
        self.assertIn("[保留资料](" + quote("../../生活/留存.md", safe="/.-_~") + ")", moved)
        self.assertIn("[[工作/资料/原文.md]]", moved)
        self.assertIn("[带空格路径](<../来源/a b (copy).md>)", moved)
        self.assertIn(quote("学习/资料/概念.md", safe="/.-_~"), index.read_text(encoding="utf-8"))

    def test_interrupted_apply_resumes_then_rolls_back_from_full_backup(self):
        self.connect_local()
        self.profile_row()
        profile = self.vault / "个人/档案/基本资料.md"
        first = self.vault / "旧/一.md"
        first.parent.mkdir(parents=True)
        first.write_bytes(b"first\r\n")
        second = self.vault / "旧/二.md"
        second.write_bytes(b"second\r\n")
        original = {"旧/一.md": first.read_bytes(), "旧/二.md": second.read_bytes(),
                    "个人/档案/基本资料.md": profile.read_bytes()}
        manifest = self.write_manifest([
            {"source": "旧/一.md", "target": "学习/一.md"},
            {"source": "旧/二.md", "target": "工作/二.md"},
            {"source": "个人/档案/基本资料.md", "target": "生活/个人档案/档案.md"},
        ])
        prepared = migration.plan(self.root, manifest)
        original_apply_file = migration._apply_file
        calls = {"count": 0}

        def interrupt_after_one(*args, **kwargs):
            original_apply_file(*args, **kwargs)
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("simulated process interruption")

        with patch.object(migration, "_apply_file", side_effect=interrupt_after_one):
            interrupted = migration.apply(self.root, prepared["id"], "确认全量映射")
        self.assertEqual("interrupted", interrupted["status"])
        self.assertTrue((self.vault / "学习/一.md").is_file())
        resumed = migration.apply(self.root, prepared["id"], "确认续办")
        self.assertEqual("complete", resumed["status"], resumed)
        rolled = migration.rollback(self.root, prepared["id"])
        self.assertEqual("rolled_back", rolled["status"], rolled)
        self.assertEqual(original["旧/一.md"], first.read_bytes())
        self.assertEqual(original["旧/二.md"], second.read_bytes())
        self.assertEqual(original["个人/档案/基本资料.md"], profile.read_bytes())
        self.assertFalse((self.vault / "学习/一.md").exists())
        self.assertFalse((self.vault / "工作/二.md").exists())
        self.assertTrue(first.parent.is_dir())
        self.assertTrue(second.parent.is_dir())
        self.assertTrue(Path(resumed["backup"]).is_dir())

    def test_multiple_rule_partial_write_and_metadata_resume_then_repeat_rollback(self):
        self.connect_local()
        self.profile_row()
        article = self.vault / "旧/文章.md"
        article.parent.mkdir(parents=True)
        article.write_text("[档案](../个人/档案/基本资料.md)\n", encoding="utf-8")
        index = self.vault / "index.md"
        index.write_text("[文章](旧/文章.md)\n", encoding="utf-8")
        runtime = self.vault / ".dyb-vault-runtime"
        runtime.mkdir()
        write_json(runtime / "catalog.json", {
            "旧/文章.md": {"target": "旧/文章.md", "sha256": digest(article),
                           "role": "knowledge", "sources": ["旧/文章.md"]}
        })
        old_rules = {name: (self.vault / name).read_bytes() for name in ("AGENTS.md", "SCHEMA.md")}
        old_index = index.read_bytes()
        old_catalog = (runtime / "catalog.json").read_bytes()
        old_marker = (self.vault / ".cy-vault.json").read_bytes()
        old_profile = self.vault / "个人/档案/基本资料.md"
        old_profile_hash = digest(old_profile)
        prepared_dir = self.root / "prepared"
        prepared_dir.mkdir()
        (prepared_dir / "AGENTS.md").write_text("新规则 A\n", encoding="utf-8")
        (prepared_dir / "SCHEMA.md").write_text("新规则 S\n", encoding="utf-8")
        manifest = self.write_manifest([
            {"source": "旧/文章.md", "target": "工作/文章.md"},
            {"source": "个人/档案/基本资料.md", "target": "生活/个人档案/基本资料.md"},
        ], replacements=[
            {"source": "prepared/AGENTS.md", "target": "AGENTS.md",
             "expected_sha256": digest(self.vault / "AGENTS.md")},
            {"source": "prepared/SCHEMA.md", "target": "SCHEMA.md",
             "expected_sha256": digest(self.vault / "SCHEMA.md")},
        ])
        prepared = migration.plan(self.root, manifest)
        original_write = migration._apply_write

        def interrupt_after_first_rule(*args, **kwargs):
            original_write(*args, **kwargs)
            if kwargs.get("key") == "replacement:AGENTS.md":
                raise RuntimeError("simulated interruption between rule writes")

        with patch.object(migration, "_apply_write", side_effect=interrupt_after_first_rule):
            first = migration.apply(self.root, prepared["id"], "确认规则和迁移")
        self.assertEqual("interrupted", first["status"])
        self.assertEqual("新规则 A\n", (self.vault / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertEqual(old_rules["SCHEMA.md"], (self.vault / "SCHEMA.md").read_bytes())

        original_cleanup = migration._cleanup_old_directories

        def interrupt_after_metadata(*args, **kwargs):
            original_cleanup(*args, **kwargs)
            raise RuntimeError("simulated interruption after catalog, index and rules")

        with patch.object(migration, "_cleanup_old_directories", side_effect=interrupt_after_metadata):
            second = migration.apply(self.root, prepared["id"], "续办")
        self.assertEqual("interrupted", second["status"])
        self.assertEqual("新规则 S\n", (self.vault / "SCHEMA.md").read_text(encoding="utf-8"))
        self.assertIn(quote("工作/文章.md", safe="/.-_~"), index.read_text(encoding="utf-8"))
        self.assertIn("工作/文章.md", read_json(runtime / "catalog.json"))

        completed = migration.apply(self.root, prepared["id"], "完成续办")
        self.assertEqual("complete", completed["status"], completed)
        self.assertEqual("complete", migration.apply(self.root, prepared["id"], "重复apply")["status"])
        self.assertEqual(digest(self.vault / "生活/个人档案/基本资料.md"), kb.state(self.root)["profile_sha256"])

        rolled = migration.rollback(self.root, prepared["id"])
        self.assertEqual("rolled_back", rolled["status"], rolled)
        self.assertEqual(old_rules["AGENTS.md"], (self.vault / "AGENTS.md").read_bytes())
        self.assertEqual(old_rules["SCHEMA.md"], (self.vault / "SCHEMA.md").read_bytes())
        self.assertEqual(old_index, index.read_bytes())
        self.assertEqual(old_catalog, (runtime / "catalog.json").read_bytes())
        self.assertEqual(old_marker, (self.vault / ".cy-vault.json").read_bytes())
        restored_state = kb.state(self.root)
        self.assertEqual(str(old_profile), restored_state["profile_entry"])
        self.assertEqual(old_profile_hash, restored_state["profile_sha256"])
        self.assertEqual("rolled_back", migration.rollback(self.root, prepared["id"])["status"])
        answer = kb.answer({"answer": "回退后继续补充。", "domain": "life",
                            "fields": {"background": "回退后更新的背景"}}, self.root)
        self.assertEqual("saved", answer["saving"]["status"], answer)

    def test_duplicate_prepared_replacement_targets_are_rejected_without_mutation(self):
        self.connect_local()
        body = self.vault / "未分类内容.md"
        body.write_bytes("未分类内容\r\n".encode("utf-8"))
        prepared_dir = self.root / "prepared"
        prepared_dir.mkdir()
        (prepared_dir / "first.md").write_text("第一份规则\n", encoding="utf-8")
        (prepared_dir / "second.md").write_text("第二份规则\n", encoding="utf-8")
        body_before = body.read_bytes()
        rules_before = {name: (self.vault / name).read_bytes() for name in migration.RULES}
        state_path = kb.home(self.root) / "state.json"
        state_before = state_path.read_bytes()
        expected = digest(self.vault / "AGENTS.md")

        for case, targets in (
            ("identical", ("AGENTS.md", "AGENTS.md")),
            ("windows_case_equivalent", ("AGENTS.md", "agents.md")),
        ):
            with self.subTest(case=case):
                manifest = self.write_manifest([], replacements=[
                    {"source": "prepared/first.md", "target": targets[0], "expected_sha256": expected},
                    {"source": "prepared/second.md", "target": targets[1], "expected_sha256": expected},
                ], name=f"duplicate-{case}.json")
                with self.assertRaises(ValueError):
                    migration.plan(self.root, manifest)
                self.assertEqual(body_before, body.read_bytes())
                self.assertEqual(rules_before, {
                    name: (self.vault / name).read_bytes() for name in migration.RULES
                })
                self.assertEqual(state_before, state_path.read_bytes())

    def test_missing_profile_placeholder_inside_domain_needs_no_mapping(self):
        self.connect_local()
        state = kb.state(self.root)
        empty_profile = self.vault / "生活/个人档案/基本资料.md"
        self.assertFalse(empty_profile.exists())
        state["profile_entry"] = str(empty_profile)
        state["profile_sha256"] = "-"
        kb.save(state, self.root)
        source = self.vault / "旧.md"
        source.write_text("旧资料", encoding="utf-8")
        prepared = migration.plan(self.root, self.write_manifest([
            {"source": "旧.md", "target": "学习/旧.md"},
        ]))
        self.assertEqual("ready", prepared["status"], prepared)
        result = migration.apply(self.root, prepared["id"], "确认")
        self.assertEqual("complete", result["status"], result)

    def test_runtime_junction_to_outside_is_rejected_before_external_write(self):
        if os.name != "nt" or not hasattr(Path, "is_junction"):
            self.skipTest("Path.is_junction 仅在受支持的 Windows/Python 版本可验证")
        self.connect_local()
        self.profile_row()
        source = self.vault / "old.md"
        source.write_text("内容", encoding="utf-8")
        manifest = self.write_manifest([
            {"source": "old.md", "target": "学习/old.md"},
            {"source": "个人/档案/基本资料.md", "target": "生活/个人档案/基本资料.md"},
        ])
        outside = self.parent / "outside-runtime"
        outside.mkdir()
        junction = self.vault / ".dyb-vault-runtime"
        environment = os.environ.copy()
        environment["CY_MIGRATION_TEST_JUNCTION_LINK"] = str(junction)
        environment["CY_MIGRATION_TEST_JUNCTION_TARGET"] = str(outside)
        command = ("$ErrorActionPreference = 'Stop'; "
                   "New-Item -ItemType Junction -Path $env:CY_MIGRATION_TEST_JUNCTION_LINK "
                   "-Target $env:CY_MIGRATION_TEST_JUNCTION_TARGET | Out-Null")
        created = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                                 capture_output=True, text=True, env=environment)
        if created.returncode != 0:
            reason = (created.stderr or created.stdout).strip()
            if any(fragment in reason.casefold() for fragment in
                   ("access is denied", "required privilege", "权限不足", "拒绝访问")):
                self.skipTest("当前环境没有创建临时目录联接的权限：" + reason)
            self.fail("创建普通临时目录联接失败：" + reason)
        try:
            with self.assertRaisesRegex(ValueError, "目录联接"):
                migration.plan(self.root, manifest)
            self.assertFalse((outside / "work.lock").exists())
            self.assertTrue(source.exists())
            self.assertFalse((self.vault / "学习/old.md").exists())
        finally:
            junction.rmdir()

    def test_rollback_preserves_post_migration_human_edit(self):
        self.connect_local()
        self.profile_row()
        source = self.vault / "旧.md"
        source.write_text("原文", encoding="utf-8")
        manifest = self.write_manifest([
            {"source": "旧.md", "target": "学习/旧.md"},
            {"source": "个人/档案/基本资料.md", "target": "生活/个人档案/档案.md"},
        ])
        prepared = migration.plan(self.root, manifest)
        result = migration.apply(self.root, prepared["id"], "确认")
        self.assertEqual("complete", result["status"])
        moved = self.vault / "学习/旧.md"
        moved.write_text("迁移后人工改动", encoding="utf-8")
        conflict = migration.rollback(self.root, prepared["id"])
        self.assertEqual("rolled_back_with_conflicts", conflict["status"])
        self.assertIn("保留现场", "\n".join(conflict["conflicts"]))
        self.assertEqual("迁移后人工改动", moved.read_text(encoding="utf-8"))
        self.assertFalse(source.exists())

    def test_target_rules_preview_explains_entry_adaptation_and_blocks_apply(self):
        self.vault.mkdir()
        source = self.vault / "old.md"
        source.write_text("text", encoding="utf-8")
        manifest = self.write_manifest([{"source": "old.md", "target": "学习/old.md"}])
        prepared = migration.plan(self.root, manifest)
        self.assertEqual("awaiting_target_writer", prepared["status"])
        self.assertTrue(any("目标库入口适配" in note for note in prepared["diagnostics"]))
        result = migration.apply(self.root, prepared["id"], "确认")
        self.assertEqual("interrupted", result["status"])
        self.assertTrue(source.exists())
        self.assertFalse((self.vault / "学习/old.md").exists())

    def test_another_workspace_contending_for_library_lock_blocks_apply(self):
        self.connect_local()
        self.profile_row()
        source = self.vault / "old.md"
        source.write_text("text", encoding="utf-8")
        manifest = self.write_manifest([
            {"source": "old.md", "target": "学习/old.md"},
            {"source": "个人/档案/基本资料.md", "target": "生活/个人档案/档案.md"},
        ])
        prepared = migration.plan(self.root, manifest)
        held, read_started, progress_written, release = (
            threading.Event(), threading.Event(), threading.Event(), threading.Event())
        journal_path = Path(prepared["preview"]).parent / "journal.json"
        progress_bytes = []

        def competing_workspace_writer():
            other_workspace = self.parent / "another-workspace"
            other_workspace.mkdir()
            with artifact_lock(self.vault / ".cy-vault-runtime"):
                held.set()
                self.assertTrue(read_started.wait(5))
                folder, preview, journal = migration._read_record(self.root, prepared["id"])
                migration._backup(folder, self.vault, preview, journal, journal_path)
                lookup = migration._path_lookup(preview["files"], preview.get("identity_targets", []))
                migration._apply_file(preview["files"][0], self.vault, journal, journal_path,
                                      prepared["id"], lookup)
                journal["status"] = "interrupted"
                migration._save_journal(journal_path, journal, "competing_workspace_interrupted")
                progress_bytes.append(journal_path.read_bytes())
                progress_written.set()
                release.wait(5)

        thread = threading.Thread(target=competing_workspace_writer)
        thread.start()
        self.assertTrue(held.wait(2), "另一工作区未取得库级锁")
        original_read = migration._read_record
        first_read = {"pending": True}

        def interleave_after_stale_read(root, migration_id):
            record = original_read(root, migration_id)
            if threading.current_thread() is threading.main_thread() and first_read["pending"]:
                first_read["pending"] = False
                read_started.set()
                self.assertTrue(progress_written.wait(5), "持锁方没有写入进度 journal")
            return record

        try:
            with patch.object(migration, "_read_record", side_effect=interleave_after_stale_read):
                result = migration.apply(self.root, prepared["id"], "确认")
            self.assertEqual("busy", result["status"])
            self.assertEqual(progress_bytes[0], journal_path.read_bytes(),
                             "争锁失败方不能覆盖持锁方更新的journal")
        finally:
            release.set()
            thread.join(3)
        self.assertEqual("busy", result["status"])
        self.assertIn("正在处理同一媒体", result["error"])
        self.assertFalse(source.exists())
        self.assertTrue((self.vault / "学习/old.md").exists())
        resumed = migration.apply(self.root, prepared["id"], "锁释放后续办")
        self.assertEqual("complete", resumed["status"], resumed)
