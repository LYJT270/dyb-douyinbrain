from __future__ import annotations

import os
import subprocess
import sys
import time
from unittest.mock import patch

import support  # noqa: F401
from support import WorkspaceCase
from douyin_text import media
from douyin_text.processes import Worker, HIDDEN


class ProcessTests(WorkspaceCase):
    def helper(self):
        script = self.root / 'worker.py'
        script.write_text('''import json,os,sys,time,subprocess
from pathlib import Path
for line in sys.stdin:
    data=json.loads(Path(line.strip()).read_text(encoding='utf-8'))
    child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],creationflags=0x08000000)
    time.sleep(data.get('delay',0))
    target=Path(data['response_file'])
    temp=target.with_suffix('.tmp')
    temp.write_text(json.dumps({'pid':os.getpid(),'child':child.pid,'key_present':'DOUBAO_ASR_API_KEY' in os.environ}))
    temp.replace(target)
''', encoding='utf-8')
        return Worker(self.root / 'worker.log', [sys.executable, '-B', '-X', 'utf8', str(script)])

    def test_reuses_worker_and_closes_its_entire_tree_without_inheriting_asr_key(self):
        worker = self.helper()
        try:
            with patch.dict(os.environ, {'DOUBAO_ASR_API_KEY': 'synthetic'}):
                first = worker.run({}, self.root / 'one', 5)
                second = worker.run({}, self.root / 'two', 5)
            self.assertEqual(first['pid'], second['pid'])
            self.assertFalse(first['key_present'])
        finally:
            worker.close()
        self.assertEqual(0, worker.receipts[-1]['active_processes'])
        self.assertGreaterEqual(worker.receipts[-1]['total_processes'], 3)

    def test_total_deadline_kills_own_tree_and_worker_can_restart(self):
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'], creationflags=HIDDEN)
        worker = self.helper()
        try:
            started = time.monotonic()
            with self.assertRaises(TimeoutError):
                worker.run({'delay': 30}, self.root / 'slow', 0.8)
            self.assertLess(time.monotonic() - started, 5)
            self.assertEqual(0, worker.receipts[-1]['active_processes'])
            self.assertIsNone(unrelated.poll())
            self.assertIn('pid', worker.run({}, self.root / 'next', 5))
        finally:
            worker.close()
            unrelated.kill()
            unrelated.wait(timeout=5)

    def test_batch_caps_parallel_acquisitions_at_two_and_preserves_order(self):
        import threading
        active, peak = 0, 0
        lock = threading.Lock()
        def run(worker, data, folder, timeout):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(active, peak)
            time.sleep(0.08 if data['value'] == 'first' else 0.01)
            with lock:
                active -= 1
            return {'jobs': [{'id': data['value']}], 'failures': []}
        with patch.object(Worker, 'run', run):
            jobs = media.acquire_batch(['first', 'second', 'third'], {}, self.root / 'batch', self.root, version='test')
        self.assertEqual(2, peak)
        self.assertEqual(['first', 'second', 'third'], [x['id'] for x in jobs])
