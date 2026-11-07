"""Regression scenarios: mixed batches, offline resume and actual cached evidence."""
from unittest.mock import patch

import support  # noqa: F401
from support import WorkspaceCase
from test_douyin_browser import video
from douyin_text import acquisition, asr, content, douyin_browser, media, workflow
from douyin_text.common import read_json, write_json


class ReliabilityTests(WorkspaceCase):
    def test_audio_binding_mismatch_stops_before_a_paid_request(self):
        task = self.task()
        job = media.discover([str(self.wav)], {}, self.root, self.root)[0]
        folder = self.root / '.cache' / job['id'] / asr.PROFILE / 'audio'
        media.extract(job, folder, 1)
        binding = read_json(folder / 'source.json')
        binding['media_id'] = 'wrong-source'
        write_json(folder / 'source.json', binding)
        with patch.object(asr, 'recognize', side_effect=AssertionError('must not submit')):
            result = workflow.run(task['id'], self.root)
        self.assertEqual('incomplete', result['status'])
        self.assertIn('来源绑定', result['failures'][0]['error'])

    def test_middle_metadata_failure_keeps_both_successes_and_original_numbers(self):
        urls = ['https://www.douyin.com/video/' + n for n in ('123', '456', '789')]
        visited = []
        def metadata(values, profile, report, **kwargs):
            ident = acquisition.video_id(values[0])
            visited.append(ident)
            if ident == '456':
                return [], [{'input_url': values[0], 'reason': 'metadata_unavailable'}]
            return [douyin_browser.normalize(video(ident))], []
        with patch.object(media, 'metadata', side_effect=metadata):
            jobs = media.discover(urls, {}, self.root / 'check', self.root, keep_going=True)
        self.assertEqual(['123', '456', '789'], visited)
        self.assertEqual(['douyin-123', 'douyin-789'], [x['id'] for x in jobs])
        self.assertEqual([1, 3], [x['number'] for x in jobs])
        self.assertEqual(2, jobs.failures[0]['number'])

    def test_words_in_video_title_do_not_become_a_verification_wall(self):
        for text in ('视频标题：千万别把验证码告诉别人。', '安全验证是什么？今天来聊聊。',
                     '作者说：登录后才能观看，这是什么道理？', '视频已删除该怎么办？'):
            self.assertIsNone(acquisition.visible_blocker(text))
        self.assertEqual('verification_required', acquisition.visible_blocker('请完成安全验证'))

    def test_resume_reads_valid_completed_result_before_going_online(self):
        task = self.recognize_run(self.task())
        # A previous attempt completed this item before another item failed.
        url = 'https://www.douyin.com/video/123'
        task['inputs'].append(url)
        task['status'] = 'incomplete'
        workflow.save(task, self.root)
        prior = task['results'][0]
        def discover(values, *args, **kwargs):
            self.assertEqual([url], values)
            raise acquisition.AcquisitionError([{'input_url': url, 'reason': 'metadata_unavailable'}])
        with patch.object(media, 'acquire_batch', side_effect=discover), \
                patch.object(asr, 'recognize', side_effect=AssertionError('duplicate ASR')):
            again = workflow.run(task['id'], self.root)
        self.assertEqual(prior['id'], again['results'][0]['id'])
        self.assertEqual('incomplete', again['status'])
        self.assertTrue(self.path(prior['result']).is_file())

    def test_new_task_uses_canonical_video_cache_without_metadata(self):
        task = self.recognize_run(self.task())
        item = task['results'][0]
        old = self.path(item['result']).parent
        target = self.root / 'outputs/douyin-123' / old.name
        import shutil
        shutil.copytree(old, target)
        result = read_json(target / 'result.json')
        result['source'].update(id='douyin-123', source='https://www.douyin.com/video/123')
        write_json(target / 'result.json', result)
        new = workflow.plan(['https://www.douyin.com/video/123'], self.root)
        workflow.confirm(new['id'], 'transcribe', '转写这个链接', root=self.root)
        with patch.object(media, 'discover', side_effect=AssertionError('must stay offline')), \
                patch.object(asr, 'recognize', side_effect=AssertionError('duplicate ASR')):
            done = workflow.run(new['id'], self.root)
        self.assertEqual('awaiting_review', done['status'])
        self.assertEqual('reused', done['results'][0]['status'])
