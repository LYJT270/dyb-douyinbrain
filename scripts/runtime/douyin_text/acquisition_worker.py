"""Acquisition-only subprocess. Never loads credentials or calls speech APIs."""
from __future__ import annotations

from pathlib import Path
import os
import sys
import time

from . import acquisition, douyin_browser, media
from .common import ArtifactBusyError, artifact_lock, config, read_json, write_json


def acquire(data):
    root, folder = Path(data['root']), Path(data['folder'])
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(root / '.local/browsers')
    started = time.monotonic()
    jobs = media.discover([data['value']], data.get('scope', {}), folder, root,
                         anonymous_only=data.get('anonymous_only', False), keep_going=True)
    metadata_seconds = time.monotonic() - started
    failures = list(jobs.failures)
    ready = []
    for job in jobs:
        try:
            if data.get('audio'):
                phase = time.monotonic()
                version_folder = root / '.cache' / job['id'] / data['version']
                with artifact_lock(version_folder):
                    with artifact_lock(root / '.cache' / job['id'] / 'source'):
                        source = media.materialize(job, root)
                    download_seconds = time.monotonic() - phase
                    phase = time.monotonic()
                    local_job = {**job, 'media': str(source)}
                    chunks = media.extract(local_job, version_folder / 'audio', config(root)['chunk_seconds'])
                job['audio_verified'] = True
                job['audio_duration'] = sum(x['duration'] for x in chunks)
                job['acquisition_timing'] = {'metadata_seconds': round(metadata_seconds, 3),
                    'download_seconds': round(download_seconds, 3), 'audio_seconds': round(time.monotonic() - phase, 3)}
            ready.append(job)
        except Exception as exc:
            failures.append({**acquisition.clean_failure({'reason': 'media_busy' if isinstance(exc, ArtifactBusyError) else 'media_unavailable', 'stage': 'audio',
                'message': str(exc)}), 'id': job['id'], 'error': str(exc), 'number': job.get('number', 1)})
    return {'jobs': ready, 'failures': failures, 'cloud_asr_called': False}


def main():
    # Nothing may spawn until the parent has assigned this process to its Job.
    with douyin_browser.reuse_sessions():
        for line in sys.stdin:
            data = read_json(Path(line.strip()))
            try:
                result = acquire(data)
            except Exception as exc:
                result = {'jobs': [], 'failures': [acquisition.clean_failure({'message': str(exc),
                    'reason': getattr(exc, 'code', 'metadata_unavailable')})], 'cloud_asr_called': False}
            write_json(Path(data['response_file']), result)


if __name__ == '__main__':
    main()
