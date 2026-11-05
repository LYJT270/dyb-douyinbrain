from __future__ import annotations

import unittest
from unittest.mock import patch

import support  # noqa: F401
from douyin_text import douyin_browser as browser, media


def video(ident="123", **extra):
    return {"aweme_id": ident, "desc": "公开测试标题", "author": {"nickname": "测试作者"},
            "create_time": 1700000000,
            "video": {"duration": 12345, "play_addr": {"url_list": ["https://example.invalid/video.mp4"]}}, **extra}


class BrowserMetadataTests(unittest.TestCase):
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
