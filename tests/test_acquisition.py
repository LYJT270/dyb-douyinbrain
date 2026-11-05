from __future__ import annotations

import io
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.parse import quote

import support  # noqa: F401
from support import WorkspaceCase
from test_douyin_browser import video
from douyin_text import acquisition, asr, cli, douyin_browser as browser, media, review, workflow
from douyin_text.common import read_json

URL = "https://www.douyin.com/video/123"


class AcquisitionTests(WorkspaceCase):
    def test_public_json_matches_only_requested_video(self):
        value = {"nested": [video("456"), video()]}
        router = "<script>window._ROUTER_DATA = " + json.dumps(value) + ";ignore()</script>"
        self.assertEqual("123", acquisition.parse_public_detail(router, "123")["aweme_id"])
        self.assertIsNone(acquisition.parse_public_detail(router, "789"))
        render = '<script id="RENDER_DATA">' + quote(json.dumps(value)) + '</script>'
        self.assertEqual("123", acquisition.parse_public_detail(render, "123")["aweme_id"])
        self.assertIsNone(acquisition.parse_public_detail("window._ROUTER_DATA = execute()", "123"))

    def test_http_public_request_needs_no_cookie_and_skips_browser(self):
        body = "window._ROUTER_DATA = " + json.dumps({"item": video()})
        with patch.object(acquisition.request, "urlopen", return_value=io.BytesIO(body.encode())) as fetch, \
                patch.object(browser, "videos", side_effect=AssertionError("browser must not run")):
            jobs, failures = media.metadata([URL], self.root / "profile", self.root / "report.json")
        self.assertEqual("douyin-123", jobs[0]["id"])
        self.assertFalse(failures)
        self.assertNotIn("Cookie", fetch.call_args.args[0].headers)
        self.assertFalse((self.root / "profile").exists())

    def test_anonymous_browser_precedes_existing_profile(self):
        profile = self.root / "profile"
        profile.mkdir()
        failure = {"input_url": URL, "reason": "metadata_unavailable"}
        with patch.object(acquisition, "public_metadata", return_value=([], [failure])), \
                patch.object(browser, "videos", side_effect=[([], [failure]), ([browser.normalize(video())], [])]) as fetch:
            jobs, failures = media.metadata([URL], profile, self.root / "report.json")
        self.assertEqual([None, profile], [call.args[1] for call in fetch.call_args_list])
        self.assertEqual(1, len(jobs))
        self.assertFalse(failures)
        self.assertEqual(2, len(read_json(self.root / "report.json")["attempt_failures"]))

    def test_anonymous_only_never_reads_saved_profile(self):
        profile = self.root / "profile"
        profile.mkdir()
        failure = {"input_url": URL, "reason": "metadata_unavailable"}
        with patch.object(acquisition, "public_metadata", return_value=([], [failure])), \
                patch.object(browser, "videos", return_value=([], [failure])) as fetch:
            _, failures = media.metadata([URL], profile, self.root / "report.json", anonymous_only=True)
        fetch.assert_called_once_with([URL], None)
        self.assertTrue(failures)

    def test_failures_keep_real_reason_and_remove_url_query(self):
        failure = {"input_url": URL + "?private=test", "reason": "navigation_timeout",
                   "message": "Timed out at " + URL + "?private=test"}
        with patch.object(acquisition, "public_metadata", return_value=([], [failure])), \
                patch.object(browser, "videos", return_value=([], [failure])):
            with self.assertRaises(acquisition.AcquisitionError) as caught:
                media.discover([URL], {}, self.root, self.root)
        self.assertEqual("navigation_timeout", caught.exception.code)
        self.assertNotIn("private", json.dumps(read_json(self.root / "metadata-0.json")))

    def test_unknown_data_is_not_reported_as_mandatory_login(self):
        failure = {"input_url": URL, "reason": "metadata_unavailable"}
        with patch.object(media, "metadata", return_value=([], [failure])):
            with self.assertRaises(acquisition.AcquisitionError) as caught:
                media.discover([URL], {}, self.root, self.root)
        self.assertEqual("metadata_unavailable", caught.exception.code)
        self.assertIn("尚不能判断", str(caught.exception))

    def test_only_explicit_visible_blockers_require_login_or_verification(self):
        self.assertIsNone(acquisition.visible_blocker("登录 视频数据加载中"))
        self.assertEqual("login_required", acquisition.visible_blocker("登录后才能观看"))
        self.assertEqual("verification_required", acquisition.visible_blocker("请完成安全验证"))
        self.assertEqual("media_unavailable", acquisition.visible_blocker("作品已删除"))

    def test_public_http_failure_has_status_code(self):
        with patch.object(acquisition, "fetch_share_page", side_effect=HTTPError(URL, 503, "offline", {}, None)):
            jobs, failures = acquisition.public_metadata([URL])
        self.assertFalse(jobs)
        self.assertEqual(503, failures[0]["http_status"])
        self.assertEqual("http_error", failures[0]["reason"])

    def test_background_sessions_never_open_visible_browser(self):
        driver = MagicMock()
        with browser._session(driver, None) as context:
            self.assertEqual(driver.chromium.launch.return_value.new_context.return_value, context)
        driver.chromium.launch.assert_called_once_with(headless=True)
        driver.chromium.launch_persistent_context.assert_not_called()
        driver.chromium.launch.return_value.close.assert_called_once()
        driver.reset_mock()
        with browser._session(driver, self.root / "profile"):
            pass
        self.assertTrue(driver.chromium.launch_persistent_context.call_args.kwargs["headless"])
        driver.chromium.launch.assert_not_called()
        driver.chromium.launch_persistent_context.return_value.close.assert_called_once()

    def test_browser_failure_reports_evidence_without_opening_login(self):
        page, context, manager = MagicMock(), MagicMock(), MagicMock()
        context.new_page.return_value = page
        manager.__enter__.return_value = context
        page.goto.return_value.status = 200
        fake_module = SimpleNamespace(sync_playwright=MagicMock())
        with patch.dict(sys.modules, {"playwright.sync_api": fake_module}), \
                patch.object(browser, "_session", return_value=manager), \
                patch.object(browser, "_hydrate", return_value=[]), \
                patch.object(browser, "_yt_dlp_video", side_effect=ValueError("no video data")), \
                patch.object(browser, "login", side_effect=AssertionError("must not open login")):
            for visible, expected in [("登录 视频数据加载中", "metadata_unavailable"),
                                      ("登录后观看", "login_required"), ("请完成安全验证", "verification_required")]:
                page.locator.return_value.inner_text.return_value = visible
                jobs, failures = browser.videos([URL], None)
                self.assertFalse(jobs)
                self.assertEqual(expected, failures[0]["reason"])

    def test_browser_failure_with_http_status_is_not_login(self):
        page, context, manager = MagicMock(), MagicMock(), MagicMock()
        context.new_page.return_value = page
        manager.__enter__.return_value = context
        page.goto.return_value.status = 503
        page.locator.return_value.inner_text.return_value = "Service unavailable"
        with patch.dict(sys.modules, {"playwright.sync_api": SimpleNamespace(sync_playwright=MagicMock())}), \
                patch.object(browser, "_session", return_value=manager), \
                patch.object(browser, "_hydrate", return_value=[]), \
                patch.object(browser, "_yt_dlp_video", side_effect=ValueError("no data")):
            _, failures = browser.videos([URL], None)
        self.assertEqual("http_error", failures[0]["reason"])
        self.assertEqual(503, failures[0]["http_status"])

    def test_failed_acquisition_preserves_task_diagnostic_without_asr(self):
        task = workflow.plan([URL], self.root)
        workflow.confirm(task["id"], "transcribe", "转成逐字稿", root=self.root)
        failure = {"input_url": URL, "reason": "metadata_unavailable"}
        with patch.object(acquisition, "public_metadata", return_value=([], [failure])), \
                patch.object(browser, "videos", return_value=([], [failure])), \
                patch.object(asr, "recognize", side_effect=AssertionError("no ASR on acquisition failure")):
            result = workflow.run(task["id"], self.root)
        self.assertEqual("failed", result["status"])
        self.assertEqual("metadata_unavailable", result["failures"][0]["reason"])
        self.assertTrue(self.path(result["failures"][0]["reports"][0]).is_file())

    def test_inspection_never_calls_asr_or_outputs_expiring_media_address(self):
        with patch.object(media, "metadata", return_value=([browser.normalize(video())], [])), \
                patch.object(asr, "recognize", side_effect=AssertionError("no ASR")):
            result = review.inspect_source([URL], self.root, anonymous_only=True)
        self.assertEqual("acquired", result["status"])
        self.assertFalse(result["cloud_asr_called"])
        self.assertNotIn("example.invalid", json.dumps(result))
        self.assertTrue((self.path(result["report_directory"]) / "jobs.json").is_file())

    def test_cli_exposes_review_capabilities_and_anonymous_inspection(self):
        args = cli.parser().parse_args(["prepare-review", "task", "--images", "--start", "0.5", "--end", "1", "--every-frame"])
        self.assertTrue(args.images and args.every_frame)
        self.assertFalse(args.audio)
        self.assertEqual(120, args.max_frames)
        self.assertTrue(cli.parser().parse_args(["inspect-source", URL, "--anonymous-only"]).anonymous_only)
