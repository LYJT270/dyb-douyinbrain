from __future__ import annotations

import shutil
import subprocess
from unittest.mock import patch

import support  # noqa: F401
from douyin_text import asr, review, workflow
from douyin_text.common import digest, read_json
from support import WorkspaceCase


class ReviewTests(WorkspaceCase):
    def video_task(self):
        self.video = self.parent / "测试原视频.mp4"
        subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=4:duration=2",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000:duration=2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(self.video)],
                       check=True, capture_output=True)
        task = workflow.plan([str(self.video)], self.root)
        workflow.confirm(task["id"], "transcribe", "测试素材转写并校对", root=self.root)
        return self.recognize_run(task)

    def test_text_capability_needs_no_visual_or_audio_tools(self):
        task = self.recognize_run(self.task())
        before = digest(workflow.task_path(task["id"], self.root))
        with patch.object(review, "frames", side_effect=AssertionError("no image capability")), \
                patch.object(review, "audio_files", side_effect=AssertionError("no audio capability")), \
                patch.object(asr, "recognize", side_effect=AssertionError("no extra ASR")):
            report = review.prepare(task["id"], self.root)
        self.assertEqual("text", report["items"][0]["mode"])
        self.assertFalse(report["review_completed"])
        self.assertEqual(before, digest(workflow.task_path(task["id"], self.root)))

    def test_actual_frames_have_source_timestamps_and_do_not_claim_review(self):
        task = self.video_task()
        original_hash = digest(self.path(task["results"][0]["text"]))
        with patch.object(asr, "recognize", side_effect=AssertionError("no extra ASR")):
            report = review.prepare(task["id"], self.root, images=True, start=0.5, end=1.0,
                                    every_frame=True, max_frames=10)
        self.assertEqual("prepared", report["status"])
        visual = report["items"][0]["visual"]
        self.assertEqual([0.5, 0.75, 1.0], [item["time_seconds"] for item in visual["frames"]])
        self.assertEqual([2, 3, 4], [item["frame_index"] for item in visual["frames"]])
        self.assertTrue(visual["end_inclusive"])
        for item in visual["frames"]:
            image = self.path(item["file"])
            self.assertTrue(image.read_bytes().startswith(b"\xff\xd8"))
            self.assertEqual(160, review.probe(image)["streams"][0]["width"])
        self.assertFalse(visual["reviewed"])
        self.assertFalse(report["review_completed"])
        self.assertEqual(original_hash, digest(self.path(task["results"][0]["text"])))

    def test_visual_sampling_and_audio_reuse_run_without_cloud_calls(self):
        task = self.video_task()
        with patch.object(asr, "recognize", side_effect=AssertionError("no extra ASR")):
            report = review.prepare(task["id"], self.root, images=True, audio=True, max_frames=2)
        self.assertEqual("prepared", report["status"])
        item = report["items"][0]
        self.assertEqual("sampled", item["visual"]["mode"])
        self.assertLessEqual(len(item["visual"]["frames"]), 2)
        self.assertTrue(item["audio"])
        self.assertTrue(all(self.path(part["file"]).is_file() for part in item["audio"]))
        self.assertFalse(any(part["listened"] for part in item["audio"]))

    def test_frame_limit_cannot_be_reported_as_complete_coverage(self):
        task = self.video_task()
        report = review.prepare(task["id"], self.root, images=True, every_frame=True, max_frames=2)
        self.assertEqual("prepared_with_gaps", report["status"])
        self.assertNotIn("visual", report["items"][0])
        self.assertTrue(report["items"][0]["gaps"])
        self.assertFalse(report["review_completed"])

    def test_changed_original_cannot_verify_an_old_transcript(self):
        task = self.video_task()
        with self.video.open("ab") as handle:
            handle.write(b"changed")
        report = review.prepare(task["id"], self.root, images=True)
        self.assertEqual("prepared_with_gaps", report["status"])
        self.assertNotIn("visual", report["items"][0])

    def test_review_assets_follow_a_moved_workspace(self):
        task = self.video_task()
        self.move_workspace()
        report = review.prepare(task["id"], self.root, images=True, start=0.5, end=1.0,
                                every_frame=True, max_frames=10)
        saved = read_json(self.path(report["manifest"]))
        self.assertEqual("prepared", saved["status"])
        self.assertTrue(all(self.path(item["file"]).is_file() for item in saved["items"][0]["visual"]["frames"]))

    def test_nonzero_container_start_uses_playback_relative_timestamps(self):
        task = self.video_task()
        shifted = self.parent / "shifted.mp4"
        subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-i", str(self.video), "-map", "0", "-c", "copy", "-output_ts_offset", "4", str(shifted)],
                       check=True, capture_output=True)
        self.assertGreater(float(review.probe(shifted)["format"]["start_time"]), 3)
        visual = review.frames(shifted, {"duration": 2, "segments": []}, self.root / "shifted-frames", self.root,
                               start=0.5, end=1.0, every_frame=True, maximum=10)
        self.assertEqual(2, len(visual["frames"]))
        self.assertTrue(all(0.5 <= item["time_seconds"] < 1 for item in visual["frames"]))
