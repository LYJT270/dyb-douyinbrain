"""Observable scheduling and equivalent-frame behavior; no network or paid API."""
from __future__ import annotations

import threading
from unittest.mock import patch

from support import Response, WorkspaceCase
from douyin_text import asr, credentials, media, workflow
from douyin_text.common import read_json, write_json
from douyin_text.processes import Worker


class PipelineTests(WorkspaceCase):
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
