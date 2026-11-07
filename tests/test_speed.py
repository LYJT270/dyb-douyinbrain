"""Observable scheduling and equivalent-frame behavior; no network or paid API."""
from __future__ import annotations

import threading
from unittest.mock import patch

from support import Response, WorkspaceCase
from douyin_text import acquisition_worker, asr, credentials, media, workflow
from douyin_text.common import artifact_lock, read_json, write_json
from douyin_text.processes import Worker


class PipelineTests(WorkspaceCase):
    def test_worker_reports_media_lock_contention_with_resolved_identity(self):
        job = {'id': 'douyin-456', 'media': str(self.wav), 'number': 1}
        with artifact_lock(self.root / '.cache/douyin-456/test'), \
                patch.object(media, 'discover', return_value=media.Discovery([job])), \
                patch.object(media, 'materialize', side_effect=AssertionError('locked source acquired')):
            result = acquisition_worker.acquire({'root': str(self.root), 'folder': str(self.root / 'run'),
                'value': 'https://v.douyin.com/alias/', 'audio': True, 'version': 'test'})
        self.assertEqual('media_busy', result['failures'][0]['reason'])
        self.assertEqual('douyin-456', result['failures'][0]['id'])

    def test_duplicate_contention_reuses_ready_identity_in_original_input_order(self):
        urls = ['https://v.douyin.com/alias/', 'https://www.douyin.com/video/456']
        task = workflow.plan(urls, self.root)
        workflow.confirm(task['id'], 'transcribe', '转写两条链接', root=self.root)
        def acquire(worker, data, folder, timeout):
            if data['value'] == urls[0]:
                return {'jobs': [], 'failures': [{'id': 'douyin-456', 'reason': 'media_busy', 'stage': 'audio'}]}
            return {'jobs': [{'id': 'douyin-456', 'source': urls[1], 'input': urls[1],
                             'media': str(self.wav), 'author': 'fixture', 'title': 'same video',
                             'published': None, 'audio_verified': True}], 'failures': []}
        with patch.object(Worker, 'run', acquire), patch.object(credentials, 'load', return_value={'api_key': 'fixture'}), \
                patch.object(asr.request, 'urlopen', side_effect=lambda *a, **k: Response()) as submitted:
            result = workflow.run(task['id'], self.root)
        self.assertEqual('awaiting_review', result['status'])
        self.assertEqual([], result['failures'])
        self.assertEqual(1, len(result['results']))
        self.assertEqual(4, submitted.call_count, 'one set of four audio chunks, without duplicate requests')
        job = read_json(workflow.task_path(task['id'], self.root).parent / 'jobs.json')[0]
        self.assertEqual(1, job['input_number'])
        self.assertEqual(urls[0], job['input'])

    def test_unmatched_media_contention_remains_a_reported_gap(self):
        with patch.object(Worker, 'run', return_value={'jobs': [], 'failures': [
                {'id': 'douyin-456', 'reason': 'media_busy', 'stage': 'audio'}]}):
            result = media.acquire_batch(['https://v.douyin.com/alias/'], {}, self.root / 'run',
                                         self.root, version='test')
        self.assertEqual([], result)
        self.assertEqual('media_busy', result.failures[0]['reason'])

    def test_ready_audio_is_recognized_before_slow_acquisition_and_duplicate_is_not_paid_twice(self):
        write_json(self.root / 'config.json', {'chunk_seconds': 300, 'asr_timeout_seconds': 5})
        urls = ['https://www.douyin.com/video/' + n for n in ('123', '456', '789')]
        task = workflow.plan(urls, self.root)
        workflow.confirm(task['id'], 'transcribe', '按顺序转写', root=self.root)
        started = threading.Event()
        overlaps = []
        paid = []

        def acquire(worker, data, folder, timeout):
            ident = data['value'].rsplit('/', 1)[-1]
            if ident == '123':
                overlaps.append(started.wait(2))
            # Two different inputs resolve to the same media identity.
            ident = '456' if ident == '789' else ident
            return {'jobs': [{'id': 'douyin-' + ident, 'source': urls[0] if ident == '123' else urls[1],
                             'input': data['value'], 'media': str(self.wav), 'author': 'fixture',
                             'title': ident, 'published': None}], 'failures': []}

        def recognize(*args, **kwargs):
            paid.append(1)
            started.set()
            return Response()

        with patch.object(Worker, 'run', acquire), patch.object(credentials, 'load', return_value={'api_key': 'fixture'}), \
                patch.object(asr.request, 'urlopen', side_effect=recognize):
            result = workflow.run(task['id'], self.root)
        self.assertEqual([True], overlaps, 'ASR waited for the whole acquisition batch')
        self.assertEqual('awaiting_review', result['status'])
        self.assertEqual(2, len(paid))
        self.assertEqual(['douyin-123', 'douyin-456'], [x['id'] for x in result['results']])
        self.assertEqual([1, 2], [x['number'] for x in result['results']])
        with patch.object(media, 'acquire_batch', side_effect=AssertionError('unexpected reacquisition')), \
                patch.object(asr.request, 'urlopen', side_effect=AssertionError('duplicate payment')):
            again = workflow.run(task['id'], self.root)
        self.assertEqual(2, len(again['results']))

    def test_streamed_unknown_request_is_saved_before_interruption_and_not_retried(self):
        write_json(self.root / 'config.json', {'chunk_seconds': 300, 'asr_timeout_seconds': 5})
        task = workflow.plan(['https://www.douyin.com/video/456'], self.root)
        workflow.confirm(task['id'], 'transcribe', '转写', root=self.root)
        job = {'id': 'douyin-456', 'input': task['inputs'][0], 'source': task['inputs'][0],
               'media': str(self.wav), 'title': 'fixture', 'author': 'fixture', 'published': None, 'input_number': 1}

        def interrupted(*args, **kwargs):
            kwargs['on_ready']({'input_number': 1, 'jobs': [job], 'failures': []})
            raise KeyboardInterrupt()

        with patch.object(media, 'acquire_batch', side_effect=interrupted), \
                patch.object(credentials, 'load', return_value={'api_key': 'fixture'}), \
                patch.object(asr, 'recognize', side_effect=asr.OutcomeUnknown('connection lost')):
            with self.assertRaises(KeyboardInterrupt):
                workflow.run(task['id'], self.root)
        self.assertTrue((workflow.task_path(task['id'], self.root).parent / 'jobs.json').is_file())
        with patch.object(media, 'acquire_batch', side_effect=AssertionError('unexpected reacquisition')), \
                patch.object(asr, 'recognize', side_effect=AssertionError('duplicate payment')):
            result = workflow.run(task['id'], self.root)
        self.assertEqual('incomplete', result['status'])
        self.assertIn('失败或结果未知', result['failures'][0]['error'])
