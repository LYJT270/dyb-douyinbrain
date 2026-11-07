from __future__ import annotations

import unittest
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from unittest.mock import patch, MagicMock

import support  # noqa: F401
from support import WorkspaceCase, SKILL_ROOT
from douyin_text import douyin_browser as browser, media


def video(ident="123", **extra):
    return {"aweme_id": ident, "desc": "公开测试标题", "author": {"nickname": "测试作者"},
            "create_time": 1700000000,
            "video": {"duration": 12345, "play_addr": {"url_list": ["https://example.invalid/video.mp4"]}}, **extra}


class PersistentProfileTests(WorkspaceCase):
    def test_persistent_profile_is_owned_by_one_process_until_context_closes(self):
        profile = self.root / '.local/douyin-profile'
        code = """import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from douyin_text.douyin_browser import _session
context = SimpleNamespace(close=lambda: None)
playwright = SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=lambda *a, **k: context))
with _session(playwright, Path(sys.argv[2])):
    print('owned', flush=True)
    sys.stdin.readline()
"""
        child = subprocess.Popen([sys.executable, '-u', '-c', code, str(SKILL_ROOT / 'scripts/runtime'), str(profile)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        launched, attempting = threading.Event(), threading.Event()
        driver = MagicMock()
        context = MagicMock()
        driver.chromium.launch_persistent_context.side_effect = lambda *a, **k: (launched.set() or context)
        def use_profile():
            attempting.set()
            with browser._session(driver, profile):
                pass
        try:
            self.assertEqual('owned', child.stdout.readline().strip())
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(use_profile)
                try:
                    self.assertTrue(attempting.wait(2))
                    self.assertFalse(launched.wait(0.2), 'persistent profile opened while another process owned it')
                finally:
                    child.stdin.write('\n')
                    child.stdin.flush()
                future.result(timeout=5)
            self.assertTrue(launched.is_set())
            context.close.assert_called_once()
        finally:
            if child.poll() is None:
                child.communicate('\n', timeout=5)
            else:
                child.communicate()
        self.assertEqual(0, child.returncode)

    def test_failed_browser_launch_releases_profile_ownership(self):
        profile = self.root / '.local/douyin-profile'
        driver = MagicMock()
        context = MagicMock()
        driver.chromium.launch_persistent_context.side_effect = [RuntimeError('launch failed'), context]
        with self.assertRaisesRegex(RuntimeError, 'launch failed'):
            with browser._session(driver, profile):
                pass
        with browser._session(driver, profile):
            pass
        context.close.assert_called_once()


class BrowserMetadataTests(unittest.TestCase):
    def scan_pages(self, pages, callback):
        page = MagicMock()
        page.url = 'https://www.douyin.com/user/MS4test'
        page.title.return_value = '公开主页'
        listeners = {}
        page.on.side_effect = lambda event, fn: listeners.update({event: fn})
        def navigate(*args, **kwargs):
            for payload in pages:
                response = MagicMock()
                response.url = 'https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id=MS4test'
                response.status = 200
                response.json.return_value = payload
                listeners['response'](response)
        page.goto.side_effect = navigate
        context = MagicMock()
        context.new_page.return_value = page
        with patch('playwright.sync_api.sync_playwright'), \
             patch.object(browser, '_session', return_value=nullcontext(context)), \
             patch.object(browser, '_visible_blocker', return_value=None):
            return browser.scan_profile(page.url, None, callback, max_scrolls=1)

    def test_streaming_profile_retains_video_image_and_undownloadable_records(self):
        stored = []
        result = self.scan_pages([
            {'aweme_list': [video(), video('456', images=[{}])], 'has_more': 1, 'max_cursor': 9},
            {'aweme_list': [video('789', video={})], 'has_more': 0, 'max_cursor': 4}],
            lambda payload, state: stored.append(payload))
        self.assertTrue(result['complete'])
        self.assertEqual(3, result['post_count'])
        self.assertEqual([9, 4], [p['cursor'] for p in stored])

    def test_failed_checkpoint_cannot_claim_complete_profile(self):
        def fail(*args):
            raise OSError('checkpoint storage failed')
        result = self.scan_pages([{'aweme_list': [video()], 'has_more': 0}], fail)
        self.assertFalse(result['complete'])
        self.assertIn('checkpoint storage failed', result['error'])

    def test_empty_streaming_response_is_not_full_profile_evidence(self):
        result = self.scan_pages([{'aweme_list': [], 'has_more': 0}], lambda *args: None)
        self.assertFalse(result['complete'])

    def test_download_prefers_complete_mp4_rendition_and_ignores_video_only_dash(self):
        item = video()
        item['video']['bit_rate'] = [
            {'format': 'dash', 'play_addr': {'width': 1280, 'height': 720, 'data_size': 1, 'url_list': ['https://example.invalid/only-video']}},
            {'format': 'mp4', 'play_addr': {'width': 1280, 'height': 720, 'data_size': 100, 'url_list': ['https://example.invalid/complete.mp4']}},
            {'format': 'mp4', 'play_addr': {'width': 1920, 'height': 1080, 'data_size': 500, 'url_list': ['https://example.invalid/large.mp4']}}]
        self.assertEqual('https://example.invalid/complete.mp4', browser.normalize(item)['media'])

    def test_public_video_metadata_and_original_timestamp(self):
        result = browser.normalize(video())
        self.assertEqual("douyin-123", result["id"])
        self.assertEqual(12.345, result["duration"])
        self.assertEqual("2023-11-15T06:13:20+08:00", result["published"])
        self.assertEqual("https://www.douyin.com/video/123", result["source"])

    def test_images_are_never_submitted_as_audio(self):
        self.assertIsNone(browser.normalize(video(images=[{"url": "image"}])))

    def test_unknown_timestamp_cannot_satisfy_latest_scope(self):
        record = browser.normalize(video(create_time=None))
        with self.assertRaises(ValueError):
            media.select_jobs([record], {"latest": 1})

    def test_partial_page_and_login_response_do_not_imply_completion(self):
        feed = browser.ProfileFeed()
        feed.accept({"aweme_list": [video()], "has_more": 1})
        feed.accept({"status_code": 8, "aweme_list": [], "has_more": 0})
        with self.assertRaises(RuntimeError):
            feed.finish()

    def test_missing_pagination_flag_does_not_imply_completion(self):
        feed = browser.ProfileFeed()
        feed.accept({"aweme_list": [video()]})
        with self.assertRaises(RuntimeError):
            feed.finish()

    def test_complete_pages_deduplicate_pinned_posts_and_skip_images(self):
        feed = browser.ProfileFeed()
        feed.accept({"aweme_list": [video("123"), video("456")], "has_more": 1})
        feed.accept({"aweme_list": [video("123"), video("789", images=[{}])], "has_more": 0})
        self.assertEqual({"douyin-123", "douyin-456"}, {x["id"] for x in feed.finish()})
        self.assertEqual({"789"}, feed.unsupported)

    def test_unresolved_video_prevents_partial_batch_success(self):
        feed = browser.ProfileFeed()
        feed.accept({"aweme_list": [video(), {"aweme_id": "456", "video": {}}], "has_more": 0})
        with self.assertRaises(RuntimeError):
            feed.finish()

    def test_hydration_traverses_only_json_records(self):
        values = list(browser.video_records({"x": [{"other": "ignore instructions"}, video()]}))
        self.assertEqual(["123"], [x["aweme_id"] for x in values])

    def test_local_audio_discovery_never_imports_or_calls_remote_resolver(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "本地录音.wav"
            path.write_bytes(b"sample")
            with patch.object(browser, "resolve_url", side_effect=AssertionError("remote resolver called")):
                result = media.discover([str(path)], {}, Path(name))
            self.assertTrue(result[0]["id"].startswith("local-"))
