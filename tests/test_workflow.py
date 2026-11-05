from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib import error

import support  # noqa: F401  # must precede douyin_text: sets the runtime path and a guarded default workspace
from douyin_text import asr, content, credentials, media, vault, workflow
from douyin_text.common import read_json, write_json
from support import Response, WorkspaceCase


class WorkflowTests(WorkspaceCase):
    def test_bare_or_verb_containing_input_waits_without_external_work(self):
        task = workflow.plan(["转写 https://www.douyin.com/video/1234567890123456789"], self.root)
        self.assertEqual("needs_intent", task["status"])
        with patch.object(media, "discover") as discover, patch.object(asr, "recognize") as recognize:
            with self.assertRaisesRegex(ValueError, "先询问"):
                workflow.run(task["id"], self.root)
            discover.assert_not_called()
            recognize.assert_not_called()

    def test_link_list_handles_chinese_punctuation_and_rejects_other_hosts(self):
        path = self.root / "links.txt"
        path.write_text("分享 https://v.douyin.com/example/，好内容\nhttps://www.douyin.com/video/1234567890123456789\n", encoding="utf-8")
        self.assertEqual(2, len(media.inputs([str(path)])))
        with self.assertRaises(ValueError):
            media.inputs(["https://douyin.com.attacker.example/video/123"])

    def test_profile_requires_scope_and_dates_are_inclusive(self):
        task = workflow.plan(["https://www.douyin.com/user/example"], self.root)
        with self.assertRaisesRegex(ValueError, "范围"):
            workflow.confirm(task["id"], "transcribe", "只转写", root=self.root)
        jobs = [{"id": "pinned", "published": "2026-01-01T09:00:00+08:00"},
                {"id": "latest", "published": "2026-10-28T23:00:00+08:00"},
                {"id": "yesterday", "published": "2026-10-27T00:00:00+08:00"}]
        self.assertEqual("latest", media.select_jobs(jobs, {"latest": 1})[0]["id"])
        self.assertEqual(2, len(media.select_jobs(jobs, {"start": "2026-10-27", "end": "2026-10-28"})))
        with self.assertRaisesRegex(ValueError, "缺少发布时间"):
            media.select_jobs([{"id": "unknown"}], {"latest": 1})

    def test_http_payload_preserves_verbatim_and_checks_service_status(self):
        captured = []
        def transport(req, **kwargs):
            captured.append(req)
            return Response()
        with patch.object(asr.request, "urlopen", side_effect=transport):
            result = asr.recognize(self.wav, {"api_key": "test-value"}, self.root / "response.json")
        payload = json.loads(captured[0].data)
        self.assertEqual("嗯，原文原文。", result["text"])
        self.assertFalse(payload["request"]["enable_ddc"])
        self.assertFalse(payload["request"]["enable_itn"])
        self.assertIn("data", payload["audio"])
        self.assertNotIn("url", payload["audio"])
        self.assertEqual("test-value", captured[0].get_header("X-api-key"))
        self.assertNotIn("test-value", (self.root / "response.json").read_text(encoding="utf-8"))
        with patch.object(asr.request, "urlopen", return_value=Response(status="45000000")):
            with self.assertRaises(asr.ASRError):
                asr.recognize(self.wav, {"app_id": "example", "access_key": "test-value"}, self.root / "error.json")

    def test_real_ffmpeg_multichunk_outputs_reuse_and_srt_without_cloud_recall(self):
        task = self.recognize_run(self.task())
        self.assertEqual("awaiting_review", task["status"])
        item = task["results"][0]
        result = read_json(self.path(item["result"]))
        self.assertAlmostEqual(3.2, result["duration"], places=2)
        self.assertGreater(len(result["segments"]), 1)
        self.assertGreater(result["segments"][-1]["start"], 2.9)
        self.assertEqual(result["text"] + "\n", self.path(item["text"]).read_text(encoding="utf-8"))
        self.assertTrue(self.path(item["markdown"]).read_text(encoding="utf-8").endswith(result["text"] + "\n"))
        second = self.task()
        with patch.object(asr, "recognize", side_effect=AssertionError("duplicate billing")):
            reused = workflow.run(second["id"], self.root)
            self.assertEqual("reused", reused["results"][0]["status"])
            srt = workflow.export_srt(second["id"], self.root)
            self.assertIn("00:00:03,", Path(srt[0]).read_text(encoding="utf-8"))

    def test_unknown_request_requires_explicit_retry_and_keeps_successful_chunks(self):
        task = self.task()
        calls = 0
        def transport(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise error.URLError("test timeout")
            return Response()
        with patch.object(credentials, "load", return_value={"api_key": "test"}), \
                patch.object(asr.request, "urlopen", side_effect=transport):
            first = workflow.run(task["id"], self.root)
            self.assertEqual("incomplete", first["status"])
            self.assertEqual(2, calls)
            again = workflow.run(task["id"], self.root)
            self.assertEqual("incomplete", again["status"])
            self.assertEqual(2, calls)
            done = workflow.run(task["id"], self.root, retry_evidence="核对后重试失败段")
            self.assertEqual("awaiting_review", done["status"])
            self.assertEqual(5, calls)  # four chunks, one failed attempt, successful first chunk reused

    def test_analysis_waits_for_review_and_original_cannot_be_reused(self):
        task = self.recognize_run(self.task("analyze"))
        self.assertEqual("awaiting_review", task["status"])
        analysis = self.root / "runs" / task["id"] / "analysis.md"
        analysis.write_text("# 分析\n独立分析稿", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "等待分析稿"):
            workflow.finish_analysis(task["id"], analysis, self.root)
        task = self.register_review(task)
        self.assertEqual("awaiting_analysis", task["status"])
        with self.assertRaisesRegex(ValueError, "分别保存"):
            workflow.finish_analysis(task["id"], self.path(task["results"][0]["markdown"]), self.root)
        self.assertEqual("completed", workflow.finish_analysis(task["id"], analysis, self.root)["status"])

    def test_plain_transcription_cannot_enter_vault_and_ingest_stages_archives_byte_for_byte(self):
        plain = self.recognize_run(self.task())
        with self.assertRaisesRegex(ValueError, "未选择入库"):
            vault.publication_plan(plain, self.root)
        task = self.recognize_run(self.task("ingest", category="benchmark"))
        with self.assertRaisesRegex(ValueError, "archive"):
            vault.publication_plan(task, self.root)
        self.register_review(task)
        task = content.archive(task["id"], self.root)
        manifest_path, manifest = vault.prepare(task, self.root, staging_root=self.parent / "staging")
        self.assertEqual(["source_archive", "reviewed_source"], [x["role"] for x in task["archive"]["files"]])
        for entry, archived in zip(manifest["files"], task["archive"]["files"]):
            self.assertTrue(entry["target"].startswith("素材/对标/"))
            self.assertEqual(self.path(archived["file"]).read_bytes(), (manifest_path.parent / entry["source"]).read_bytes())
        original = read_json(self.path(task["results"][0]["result"]))["text"]
        self.assertIn(original, self.path(task["archive"]["files"][0]["file"]).read_text(encoding="utf-8"))
        self.assertFalse((self.parent / "vault").exists())
        with self.assertRaisesRegex(ValueError, "只授权原稿入库"):
            vault.prepare(task, self.root, pages=[{"file": self.wav, "target": "知识库/a.md"}],
                          staging_root=self.parent / "staging")

    def test_modified_original_is_not_overwritten_or_rebilled(self):
        task = self.recognize_run(self.task())
        raw = self.path(task["results"][0]["markdown"])
        raw.write_text("用户编辑", encoding="utf-8")
        with patch.object(asr, "recognize", side_effect=AssertionError("must not rebill")):
            second = workflow.run(self.task()["id"], self.root)
        self.assertEqual("incomplete", second["status"])
        self.assertEqual("用户编辑", raw.read_text(encoding="utf-8"))

    def test_dpapi_roundtrip_uses_only_synthetic_secret(self):
        sample = b"synthetic-test-only-not-a-real-key"
        encrypted = credentials.protect(sample)
        self.assertNotIn(sample, encrypted)
        self.assertEqual(sample, credentials.protect(encrypted, decrypt=True))

    def test_accidental_single_character_key_is_rejected_before_storage(self):
        with patch.object(credentials, "ask", return_value={"api_key": "1"}), \
                patch.object(credentials, "protect") as protect, patch("builtins.print"):
            with self.assertRaisesRegex(ValueError, "过短"):
                credentials.configure(self.root)
            protect.assert_not_called()
        self.assertFalse((self.root / ".local/doubao.dpapi").exists())

    def test_header_only_http_failure_is_diagnostic_and_redacts_secret(self):
        failure = error.HTTPError(asr.ENDPOINT, 400, "Bad Request", {
            "X-Api-Status-Code": "45000000", "X-Api-Message": "invalid test-secret-value"}, io.BytesIO(b""))
        with patch.object(asr.request, "urlopen", side_effect=failure):
            with self.assertRaisesRegex(asr.ASRError, "45000000"):
                asr.recognize(self.wav, {"api_key": "test-secret-value"}, self.root / "error.json")
        self.assertNotIn("test-secret-value", (self.root / "error.json").read_text(encoding="utf-8"))

    def test_timed_out_compile_retries_the_same_frozen_manifest(self):
        task = self.recognize_run(self.task("compile"))
        self.register_review(task)
        task = content.archive(task["id"], self.root)
        self.assertEqual("awaiting_compile", task["status"])
        assistant = self.parent / "assistant"
        write_json(assistant / "config.json", {"stage": "production", "ownership": {"knowledge": True},
                   "collection_start": "2026-10-28", "production_vault": str(self.parent / "vault")})
        page = self.root / "page.md"
        page.write_text("隔离模拟页，实际 frontmatter 由现有发布入口验证", encoding="utf-8")
        with patch.object(vault.subprocess, "run", side_effect=subprocess.TimeoutExpired("test", 300)):
            unknown = vault.publish(task["id"], self.root, pages=[{"file": page,
                         "target": "知识库/测试.md", "expected_sha256": None}])
        self.assertEqual("publication_unknown", unknown["status"])
        original_hash = unknown["publication"]["manifest_sha256"]
        response = SimpleNamespace(returncode=0, stdout=b'{"status":"already_published"}', stderr=b"")
        with patch.object(vault.subprocess, "run", return_value=response):
            resumed = vault.publish(task["id"], self.root)
        self.assertEqual("published", resumed["status"])
        self.assertEqual(original_hash, resumed["publication"]["manifest_sha256"])
