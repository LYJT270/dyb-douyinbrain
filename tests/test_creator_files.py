from __future__ import annotations

import http.server
import threading
from unittest.mock import patch

from support import WorkspaceCase, write_json
from douyin_text import creator_files


class DownloadTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.payload = bytes(range(256)) * 32
        self.requests = []
        owner = self
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(dict(self.headers))
                if self.path == '/forbidden':
                    self.send_error(403)
                    return
                offset = int(self.headers.get('Range', 'bytes=0-').split('=')[1].split('-')[0])
                partial = bool(self.headers.get('Range'))
                self.send_response(206 if partial else 200)
                if partial:
                    self.send_header('Content-Range', f'bytes {offset}-{len(owner.payload)-1}/{len(owner.payload)}')
                self.send_header('Content-Length', str(len(owner.payload) - offset))
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('ETag', 'fixture-v1')
                self.end_headers()
                self.wfile.write(owner.payload[offset:])
            def log_message(self, *args):
                pass
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.probe = patch.object(creator_files, 'inspect_file', return_value={
            'width': 1280, 'height': 720, 'duration': 2, 'has_audio': True})
        self.probe.start()

    def tearDown(self):
        self.probe.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        super().tearDown()

    def test_resume_real_http_range_and_reuse_without_network(self):
        folder = self.root / '.cache/download'
        folder.mkdir(parents=True)
        (folder / 'source.part').write_bytes(self.payload[:111])
        write_json(folder / 'transfer.json', {'etag': 'fixture-v1', 'expected_bytes': len(self.payload)})
        result = creator_files.download([self.url + '/video'], folder, self.root)
        self.assertEqual(self.payload, self.path(result['file']).read_bytes())
        self.assertEqual('bytes=111-', self.requests[0]['Range'])
        self.assertEqual('fixture-v1', self.requests[0]['If-Range'])
        again = creator_files.download([self.url + '/video'], folder, self.root)
        self.assertTrue(again['reused'])
        self.assertEqual(1, len(self.requests))

    def test_alternate_url_after_403_and_corrupt_cache_is_preserved(self):
        folder = self.root / '.cache/download'
        result = creator_files.download([self.url + '/forbidden', self.url + '/video'], folder, self.root)
        self.assertEqual(2, len(self.requests))
        self.path(result['file']).write_bytes(b'user changed file')
        with self.assertRaisesRegex(RuntimeError, '缓存'):
            creator_files.download([self.url + '/video'], folder, self.root)
        self.assertEqual(b'user changed file', self.path(result['file']).read_bytes())
        self.assertEqual(2, len(self.requests))

    def test_completed_partial_recovers_after_disconnect_without_http_416(self):
        folder = self.root / '.cache/download'
        folder.mkdir(parents=True)
        (folder / 'source.part').write_bytes(self.payload)
        write_json(folder / 'transfer.json', {'etag': 'fixture-v1', 'expected_bytes': len(self.payload)})
        result = creator_files.download([self.url + '/video'], folder, self.root)
        self.assertEqual(self.payload, self.path(result['file']).read_bytes())
        self.assertEqual([], self.requests)

    def test_mismatched_resume_version_does_not_join_bytes(self):
        folder = self.root / '.cache/download'
        folder.mkdir(parents=True)
        original = b'previous-version'
        (folder / 'source.part').write_bytes(original)
        write_json(folder / 'transfer.json', {'etag': 'old-version', 'expected_bytes': len(self.payload)})
        with self.assertRaisesRegex(RuntimeError, '版本已变化'):
            creator_files.download([self.url + '/video'], folder, self.root)
        self.assertEqual(original, (folder / 'source.part').read_bytes())
