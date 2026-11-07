from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path
from unittest.mock import patch

from support import Response, WorkspaceCase, read_json, write_json
from douyin_text import asr, catalog, creator, creator_files, creator_review, credentials, workflow
from douyin_text.common import digest, relative


def post(ident='100', *, timestamp=1700000000, images=False, duration=1000, **extra):
    value = {'aweme_id': ident, 'create_time': timestamp, 'desc': '测试选题：如何练习',
             'author': {'nickname': '公开作者', 'sec_uid': 'MS4test'},
             'statistics': {'digg_count': 12},
             'video': {'duration': duration, 'play_addr': {'uri': 'video-' + ident,
                        'width': 1920, 'height': 1080, 'url_list': ['https://example.invalid/' + ident]}}}
    if images:
        value['images'] = [{'uri': 'image-' + ident, 'url_list': ['https://example.invalid/image']}]
    return {**value, **extra}


class CreatorTests(WorkspaceCase):
    def make(self, mode='analyze', **kwargs):
        return creator.plan('https://www.douyin.com/user/MS4test', mode=mode, images=True,
                            parallel_vision=True, root=self.root, **kwargs)['task']

    def feed(self, task, values, complete=True, fail=False):
        def scan(url, profile, callback, **kwargs):
            callback({'aweme_list': values, 'has_more': not complete, 'cursor': 99},
                     {'complete': complete, 'pages': 1})
            if fail:
                raise RuntimeError('network interrupted after durable page')
            return {'complete': complete, 'pages': 1, 'elapsed_seconds': 0.1}
        return creator.discover(task, root=self.root, scanner=scan)

    def material(self, value, task, root, timeout):
        folder = root / '.cache/test-material' / value['id']
        folder.mkdir(parents=True, exist_ok=True)
        image = value['kind'] == 'images'
        file = folder / ('image.png' if image else 'source.mp4')
        if not file.exists():
            file.write_bytes(b'fixture-content-' + value['id'].encode())
        asset = {'file': relative(root, file), 'sha256': digest(file), 'bytes': file.stat().st_size,
                 'width': 1280, 'height': 720, 'has_audio': True, 'duration': value.get('duration') or 1}
        return {'kind': value['kind'], 'complete': True, **({'images': [{**asset, 'index': 1}], 'errors': []}
                if image else {'asset': asset, 'quality': task['quality']})}

    def recognition(self, value, material, root, retry):
        folder = root / 'outputs' / value['id'] / workflow.version_for(creator.speech_task(value))
        folder.mkdir(parents=True, exist_ok=True)
        for suffix in ('txt', 'md'):
            (folder / ('transcript.' + suffix)).write_text('完整测试口播。', encoding='utf-8')
        write_json(folder / 'result.json', {'engine': 'doubao-auc-turbo', 'parameters': asr.PARAMETERS,
            'source': {'id': value['id']}, 'source_media_sha256': material['asset']['sha256'],
            'text': '完整测试口播。', 'segments': [],
            'output_sha256': {s: digest(folder / ('transcript.' + s)) for s in ('txt', 'md')}})
        return creator.cached_speech(value, root)

    def approve(self, task, **kwargs):
        quote = creator.preflight(task, root=self.root)['usage']
        return creator.authorize(task, quote['token'], '用户授权本批测试识别', root=self.root, **kwargs)

    def test_share_profile_short_link_is_canonical_and_plan_is_unpaid(self):
        with patch.object(creator.douyin_browser, 'resolve_url', return_value='https://www.iesdouyin.com/share/user/MS4test/?source=share'), \
             patch.object(credentials, 'load', side_effect=AssertionError('paid access')):
            result = creator.plan('长按复制 https://v.douyin.com/test/ 查看作品', mode='download', root=self.root)
        self.assertEqual('https://www.douyin.com/user/MS4test', creator.load(result['task'], self.root)['source'])
        self.assertFalse(result['complete'])

    def test_catalog_keeps_undownloadable_and_image_posts_and_original_fields(self):
        raw = post(video={}, text_extra=[{'hashtag_name': '教学'}])
        result = catalog.normalize_post(raw)
        self.assertEqual(raw, result['raw'])
        self.assertEqual([], result['media_variants'])
        self.assertEqual('images', catalog.normalize_post(post(images=True))['kind'])
        self.assertNotIn('play_count', result['statistics'])
        changed = catalog.normalize_post({**raw, 'statistics': {'digg_count': 999}})
        self.assertEqual(result['content_fingerprint'], changed['content_fingerprint'])

    def test_best_and_compact_choose_different_complete_renditions(self):
        values = catalog.variants({'bit_rate': [
            {'format': 'mp4', 'play_addr': {'uri': 'a', 'width': 720, 'height': 1280, 'data_size': 200, 'url_list': ['https://x/a']}},
            {'format': 'mp4', 'play_addr': {'uri': 'b', 'width': 1080, 'height': 1920, 'data_size': 900, 'url_list': ['https://x/b']}},
            {'format': 'dash', 'play_addr': {'width': 4000, 'height': 4000, 'url_list': ['https://x/no-audio']}}]})
        self.assertEqual('b', catalog.select_variant(values, 'best')['uri'])
        self.assertEqual('a', catalog.select_variant(values, 'compact')['uri'])

    def test_image_background_music_cdn_rotation_does_not_invalidate_content(self):
        first = post(images=True)
        first['video']['play_addr']['uri'] = 'https://cdn-a.example/obj/music/42.mp3'
        second = copy.deepcopy(first)
        second['video']['play_addr']['uri'] = 'https://cdn-b.example/obj/music/42.mp3'
        self.assertEqual(catalog.normalize_post(first)['content_fingerprint'],
                         catalog.normalize_post(second)['content_fingerprint'])
        second['images'][0]['uri'] = 'new-image-content'
        self.assertNotEqual(catalog.normalize_post(first)['content_fingerprint'],
                            catalog.normalize_post(second)['content_fingerprint'])

    def test_partial_discovery_survives_exception_and_refresh_deduplicates_and_orders(self):
        task = self.make()
        first = self.feed(task, [post('200', timestamp=1700000100), post('100')], complete=False, fail=True)
        self.assertFalse(first['discovery_complete'])
        self.assertEqual(2, first['counts']['discovered'])
        self.assertEqual(['douyin-100', 'douyin-200'], [p['id'] for p in creator.records(creator.load(task, self.root), self.root)])
        self.feed(task, [post('200', timestamp=1700000100), post('100'), post('200')])
        self.assertEqual(2, creator.summary(creator.load(task, self.root), self.root)['counts']['discovered'])
        self.assertEqual(2, len(list((self.root / 'runs' / task / 'pages').glob('*/*.json'))))

    def test_complete_refresh_excludes_unseen_but_retains_previous_raw_page(self):
        task = self.make()
        self.feed(task, [post('100'), post('200')])
        self.feed(task, [post('100')])
        self.assertEqual(['douyin-100'], [p['id'] for p in creator.records(creator.load(task, self.root), self.root)])
        pages = list((self.root / 'runs' / task / 'pages').glob('*/*.json'))
        self.assertTrue(any(len(read_json(p)['aweme_list']) == 2 for p in pages))

    def test_download_mode_never_loads_credentials_or_calls_recognition(self):
        task = self.make('download')
        self.feed(task, [post('100'), post('200', images=True)])
        with patch.object(credentials, 'load', side_effect=AssertionError('credentials')), \
             patch.object(asr, 'recognize', side_effect=AssertionError('ASR')):
            result = creator.run(task, root=self.root, fetcher=self.material,
                                 recognizer=lambda *a: self.fail('recognizer called'))
        self.assertTrue(result['complete'])
        value = creator.load(task, self.root)
        target = self.path(value['items']['douyin-100']['download_file'])
        self.assertTrue(target.is_file())
        self.assertTrue(target.with_suffix('.txt').is_file())
        self.assertNotIn('douyin-200', value['items'])

    def test_free_material_preparation_waits_for_frozen_batch_authorization(self):
        task = self.make()
        self.feed(task, [post()])
        creator.run(task, root=self.root, fetcher=self.material, recognizer=lambda *a: self.fail('unapproved ASR'))
        self.assertEqual('awaiting_usage_confirmation', creator.load(task, self.root)['items']['douyin-100']['speech']['status'])
        self.approve(task)
        creator.run(task, root=self.root, fetcher=self.material, recognizer=self.recognition)
        self.assertEqual(1, creator.summary(creator.load(task, self.root), self.root)['counts']['speech_ready'])
        creator.run(task, root=self.root, fetcher=self.material, recognizer=lambda *a: self.fail('cached item rebilled'))

    def test_changed_quote_and_new_posts_do_not_inherit_old_authorization(self):
        task = self.make()
        self.feed(task, [post()])
        quote = creator.preflight(task, root=self.root)['usage']
        self.feed(task, [post(), post('200')])
        with self.assertRaisesRegex(ValueError, '变化'):
            creator.authorize(task, quote['token'], '原来的授权', root=self.root)
        selected = creator.preflight(task, item_ids=['douyin-100'], root=self.root)['usage']
        creator.authorize(task, selected['token'], '只识别第一条', root=self.root)
        called = []
        def recognize(value, *args):
            called.append(value['id'])
            return self.recognition(value, *args)
        creator.run(task, root=self.root, fetcher=self.material, recognizer=recognize)
        self.assertEqual(['douyin-100'], called)

    def test_audio_budget_stops_new_requests_and_unknown_requests_are_not_retried(self):
        task = self.make()
        self.feed(task, [post('100'), post('200')])
        self.approve(task, max_audio_seconds=1)
        called = []
        def recognize(value, *args):
            called.append(value['id'])
            return self.recognition(value, *args)
        creator.run(task, root=self.root, fetcher=self.material, recognizer=recognize)
        self.assertEqual(1, len(called))
        blocked = next(p for p in creator.records(creator.load(task, self.root), self.root) if p['id'] not in called)
        ledger = self.root / '.cache' / blocked['id'] / workflow.version_for(creator.speech_task(blocked)) / 'chunk-00000.json'
        write_json(ledger, {'status': 'outcome_unknown', 'request_id': 'not-resubmit'})
        creator.run(task, root=self.root, fetcher=self.material, recognizer=lambda *a: self.fail('unknown request retried'))
        self.assertEqual('not-resubmit', read_json(ledger)['request_id'])

    def audio_material(self, value, task, root, timeout):
        result = self.material(value, task, root, timeout)
        path = root / result['asset']['file']
        path.write_bytes(self.wav.read_bytes())
        result['asset'].update(sha256=digest(path), bytes=path.stat().st_size, duration=3.2)
        return result

    def test_pre_submission_failure_releases_budget_for_same_authorized_item(self):
        task = self.make()
        self.feed(task, [post(duration=3200)])
        self.approve(task, max_audio_seconds=3.2)
        with patch.object(credentials, 'load', side_effect=RuntimeError('credentials missing')), \
                patch.object(asr, 'recognize', side_effect=AssertionError('must not submit')):
            creator.run(task, root=self.root, fetcher=self.audio_material)
        self.assertEqual(0, creator.load(task, self.root)['authorizations'][0]['reserved_audio_seconds'])
        with patch.object(credentials, 'load', return_value={'api_key': 'fixture'}), \
                patch.object(asr.request, 'urlopen', side_effect=lambda *a, **k: Response()):
            result = creator.run(task, root=self.root, fetcher=self.audio_material)
        self.assertEqual(1, result['counts']['speech_ready'])

    def test_partial_submission_only_releases_provably_unsubmitted_audio(self):
        task = self.make()
        self.feed(task, [post(duration=3200)])
        self.approve(task, max_audio_seconds=3.2)
        with patch.object(credentials, 'load', side_effect=[{'api_key': 'fixture'}, RuntimeError('credentials missing')]), \
                patch.object(asr.request, 'urlopen', side_effect=lambda *a, **k: Response()):
            creator.run(task, root=self.root, fetcher=self.audio_material)
        value = creator.records(creator.load(task, self.root), self.root)[0]
        receipts = creator.prior_requests(value, self.root)
        self.assertEqual(1, len(receipts))
        self.assertEqual('succeeded', receipts[0]['status'])
        self.assertLess(receipts[0]['audio_duration'], 3.2)
        self.assertAlmostEqual(receipts[0]['audio_duration'], creator.load(task, self.root)['authorizations'][0]['reserved_audio_seconds'])
        with patch.object(credentials, 'load', return_value={'api_key': 'fixture'}), \
                patch.object(asr.request, 'urlopen', side_effect=lambda *a, **k: Response()) as submitted:
            result = creator.run(task, root=self.root, fetcher=self.audio_material)
        self.assertEqual(3, submitted.call_count)
        self.assertEqual(1, result['counts']['speech_ready'])
        self.assertAlmostEqual(3.2, creator.load(task, self.root)['authorizations'][0]['reserved_audio_seconds'])

    def test_unknown_submission_keeps_reserved_budget_and_is_not_retried(self):
        task = self.make()
        self.feed(task, [post(duration=3200)])
        self.approve(task, max_audio_seconds=3.2)
        with patch.object(credentials, 'load', return_value={'api_key': 'fixture'}), \
                patch.object(asr, 'recognize', side_effect=asr.OutcomeUnknown('connection lost')):
            creator.run(task, root=self.root, fetcher=self.audio_material)
        value = creator.records(creator.load(task, self.root), self.root)[0]
        receipts = creator.prior_requests(value, self.root)
        self.assertEqual(1, len(receipts))
        self.assertEqual('outcome_unknown', receipts[0]['status'])
        self.assertLess(receipts[0]['audio_duration'], 3.2)
        self.assertAlmostEqual(receipts[0]['audio_duration'], creator.load(task, self.root)['authorizations'][0]['reserved_audio_seconds'])
        with patch.object(asr, 'recognize', side_effect=AssertionError('unknown request retried')):
            result = creator.run(task, root=self.root, fetcher=self.audio_material)
        self.assertEqual(0, result['counts']['speech_ready'])
        self.assertEqual(1, result['counts']['failed_items'])

    def test_export_detects_missing_or_changed_delivered_video_without_overwriting(self):
        task = self.make(mode='download')
        self.feed(task, [post()])
        result = creator.run(task, root=self.root, fetcher=self.material)
        self.assertTrue(result['complete'])
        target = self.root / creator.load(task, self.root)['items']['douyin-100']['download_file']
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    target.unlink()
                else:
                    target.write_bytes(b'user modification')
                shown = creator.summary(creator.load(task, self.root), self.root)
                exported = creator.export(task, root=self.root)
                self.assertFalse(shown['complete'])
                self.assertFalse(exported['complete'])
                self.assertEqual(0, exported['counts']['downloaded'])
                self.assertEqual(1, exported['counts']['failed_items'])
                self.assertEqual('douyin-100', exported['delivery_gaps'][0]['id'])
                csv_text = (self.root / exported['delivery_directory'] / '作品明细.csv').read_text(encoding='utf-8-sig')
                self.assertIn(exported['delivery_gaps'][0]['error'], csv_text)
                self.assertEqual(not missing, target.exists())
                if not missing:
                    self.assertEqual(b'user modification', target.read_bytes())

    def test_limited_download_advances_and_recovers_only_invalid_deliveries(self):
        task = self.make(mode='download')
        self.feed(task, [post('100'), post('200', timestamp=1700000100)])
        fetched = []
        def fetch(value, *args):
            fetched.append(value['id'])
            return self.material(value, *args)
        creator.run(task, root=self.root, limit_items=1, fetcher=fetch)
        completed = creator.run(task, root=self.root, limit_items=1, fetcher=fetch)
        self.assertEqual(['douyin-100', 'douyin-200'], fetched)
        self.assertTrue(completed['complete'])
        target = self.root / creator.load(task, self.root)['items']['douyin-100']['download_file']
        target.unlink()
        self.assertTrue(creator.run(task, root=self.root, limit_items=1, fetcher=fetch)['complete'])
        self.assertEqual(['douyin-100', 'douyin-200', 'douyin-100'], fetched)
        target.write_bytes(b'preserve user changes')
        self.assertTrue(creator.run(task, root=self.root, limit_items=1, fetcher=fetch)['complete'])
        replacement = self.root / creator.load(task, self.root)['items']['douyin-100']['download_file']
        self.assertNotEqual(target, replacement)
        self.assertEqual(b'preserve user changes', target.read_bytes())
        self.assertEqual(['douyin-100', 'douyin-200', 'douyin-100', 'douyin-100'], fetched)

    def test_download_and_recognition_overlap_with_bounded_parallelism(self):
        task = self.make()
        self.feed(task, [post('100'), post('200'), post('300')])
        self.approve(task)
        recognition_started = threading.Event()
        active, peak, lock = 0, 0, threading.Lock()
        def fetch(value, *args):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            if value['id'] == 'douyin-200':
                self.assertTrue(recognition_started.wait(5), 'recognition waited for every download')
            result = self.material(value, *args)
            with lock:
                active -= 1
            return result
        def recognize(value, *args):
            recognition_started.set()
            return self.recognition(value, *args)
        creator.run(task, root=self.root, download_workers=2, fetcher=fetch, recognizer=recognize)
        self.assertLessEqual(peak, 2)
        self.assertEqual(3, creator.summary(creator.load(task, self.root), self.root)['counts']['speech_ready'])

    def test_missing_duration_stays_unknown_and_csv_does_not_invent_zero(self):
        task = self.make()
        self.feed(task, [post(duration=None, desc='=dangerous_formula')])
        quote = creator.preflight(task, price_per_hour=2, root=self.root)['usage']
        self.assertEqual(1, quote['unknown_duration_items'])
        self.assertIsNone(quote['estimated_cost'])
        exported = creator.export(task, root=self.root)
        destination = self.root / exported['delivery_directory']
        import csv
        with (destination / '作品明细.csv').open(encoding='utf-8-sig', newline='') as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual('', row['play_count'])
        self.assertEqual("'=dangerous_formula", row['description'])
        self.assertEqual('=dangerous_formula', json.loads((destination / '原始作品.jsonl').read_text())['raw']['desc'])

    def ready_images(self, count=1):
        task = self.make()
        self.feed(task, [post(str(100 + i), images=True, timestamp=1700000000 + i) for i in range(count)])
        creator.run(task, root=self.root, fetcher=self.material)
        prepared = creator_review.prepare(task, batch_size=1, root=self.root)
        return task, prepared

    def answer(self, task, packet, worker='tester', viewed=True):
        source = read_json(self.path(packet['file']))
        rows = []
        for item in source['items']:
            rows.append({'id': item['id'], 'basis_sha256': item['basis_sha256'],
                'review': {'read_full_transcript': True, 'text': item['transcript'], 'corrections': [],
                           'unresolved': [], 'viewed_images': [p['file'] for p in item['images']] if viewed else []},
                'analysis': {'category': '教学', 'topic': '练习方法', 'angle': '可操作步骤',
                             'summary': '介绍练习方法。', 'opening': '直接说明主题', 'format': '图文',
                             'evidence': [{'kind': 'caption', 'quote': '如何练习'}]}})
        path = self.root / 'runs' / task / f'answer-{worker}.json'
        write_json(path, {'packet': source['id'], 'items': rows})
        return path

    def test_visual_claims_are_bounded_and_preparing_is_not_reviewing(self):
        task, prepared = self.ready_images(3)
        self.assertEqual(0, prepared['counts']['visual_reviewed'])
        first = creator_review.claim(task, 'a', root=self.root)
        second = creator_review.claim(task, 'b', root=self.root)
        self.assertNotEqual(first['packet']['id'], second['packet']['id'])
        self.assertEqual('capacity_full', creator_review.claim(task, 'c', root=self.root)['status'])
        creator_review.release(task, first['packet']['id'], 'a', root=self.root)
        self.assertEqual('claimed', creator_review.claim(task, 'c', root=self.root)['status'])

    def test_no_image_attestation_cannot_complete_visual_analysis(self):
        task, _ = self.ready_images()
        claimed = creator_review.claim(task, 'tester', root=self.root)
        path = self.answer(task, claimed['packet'], viewed=False)
        result = creator_review.record(task, path, 'tester', root=self.root)
        self.assertEqual(1, result['counts']['analyzed'])
        self.assertEqual(0, result['counts']['fully_analyzed'])
        self.assertFalse(result['complete'])

    def test_fabricated_quote_or_cross_item_image_is_rejected(self):
        task, _ = self.ready_images()
        claimed = creator_review.claim(task, 'tester', root=self.root)
        path = self.answer(task, claimed['packet'])
        data = read_json(path)
        data['items'][0]['analysis']['evidence'][0]['quote'] = '不存在于原文'
        write_json(path, data)
        with self.assertRaisesRegex(ValueError, '引用文字'):
            creator_review.record(task, path, 'tester', root=self.root)
        data['items'][0]['analysis']['evidence'][0]['quote'] = '如何练习'
        data['items'][0]['review']['viewed_images'].append('another-item.png')
        write_json(path, data)
        with self.assertRaisesRegex(ValueError, '不属于'):
            creator_review.record(task, path, 'tester', root=self.root)

    def test_final_report_requires_visual_work_and_reuses_analysis_after_new_scan(self):
        task, _ = self.ready_images()
        claimed = creator_review.claim(task, 'tester', root=self.root)
        creator_review.record(task, self.answer(task, claimed['packet']), 'tester', root=self.root)
        report = self.root / 'report.json'
        write_json(report, {'account': '教学类账号。', 'content': '展示练习方法。', 'topics': '练习选题。',
            'stages': [{'title': '当前阶段', 'summary': '围绕练习方法展开。', 'item_ids': ['douyin-100']}]})
        result = creator_review.report(task, report, root=self.root)
        self.assertTrue(result['complete'])
        another = self.make()
        self.feed(another, [post(images=True)])
        prepared = creator_review.prepare(another, root=self.root)
        self.assertEqual(['douyin-100'], prepared['preparation']['reused_analysis'])
        self.assertEqual([], prepared['packets'])
        self.assertFalse(prepared['complete'], 'fresh report still required for fresh metrics')

    def test_workspace_move_preserves_packets_and_downloads(self):
        task, _ = self.ready_images()
        original = self.root
        self.move_workspace()
        claimed = creator_review.claim(task, 'tester', root=self.root)
        self.assertTrue(self.path(claimed['packet']['file']).is_file())
        result = creator_review.record(task, self.answer(task, claimed['packet']), 'tester', root=self.root)
        self.assertNotIn(str(original), json.dumps(creator.load(task, self.root)))
        self.assertEqual(1, result['counts']['fully_analyzed'])

    def test_ready_only_preparation_and_completed_analysis_skip_all_media_work(self):
        task, _ = self.ready_images()
        claimed = creator_review.claim(task, 'tester', root=self.root)
        creator_review.record(task, self.answer(task, claimed['packet']), 'tester', root=self.root)
        self.feed(task, [post(images=True), post('200')])
        result = creator.run(task, item_ids=['douyin-100'], root=self.root,
                             fetcher=lambda *args: self.fail('unchanged analysis fetched media'),
                             recognizer=lambda *args: self.fail('unchanged analysis submitted ASR'))
        self.assertEqual(1, result['counts']['fully_analyzed'])
        with patch.object(creator_review, '_packet_input', side_effect=AssertionError('unready item prepared')):
            prepared = creator_review.prepare(task, root=self.root)
        self.assertEqual(['douyin-100'], prepared['preparation']['reused_analysis'])
        self.assertEqual(['douyin-200'], prepared['preparation']['waiting_materials_or_speech'])

    def test_limited_run_advances_past_completed_analysis(self):
        task, _ = self.ready_images()
        claimed = creator_review.claim(task, 'tester', root=self.root)
        creator_review.record(task, self.answer(task, claimed['packet']), 'tester', root=self.root)
        self.feed(task, [post(images=True), post('200', timestamp=1700000100, images=True)])
        fetched = []
        def fetch(value, *args):
            fetched.append(value['id'])
            return self.material(value, *args)
        creator.run(task, limit_items=1, root=self.root, fetcher=fetch)
        self.assertEqual(['douyin-200'], fetched)
        prepared = creator_review.prepare(task, root=self.root)
        self.assertEqual(['douyin-100'], prepared['preparation']['reused_analysis'])
        self.assertTrue(prepared['packets'])

    def test_reanalysis_uses_exact_recognized_source_after_high_quality_download(self):
        task = self.make()
        self.feed(task, [post()])
        original_task = creator.load(task, self.root)
        value = creator.records(original_task, self.root)[0]
        original = self.material(value, original_task, self.root, 30)
        speech = self.recognition(value, original, self.root, '')
        manifest = self.root / '.cache/creator-media' / value['id'] / value['media_fingerprint'][:20] / 'compact/asset.json'
        write_json(manifest, original['asset'])
        hd = self.root / 'hd.mp4'
        hd.write_bytes(b'another complete rendition')
        item = {'speech': speech, 'media': {'asset': {'file': 'hd.mp4', 'sha256': digest(hd)}}}
        bound = creator.review_material(value, item, self.root)
        self.assertEqual(original['asset']['sha256'], bound['asset']['sha256'])
        with patch.object(creator_files, 'fetch_post', side_effect=AssertionError('unnecessary network')):
            fetched = creator._fetch(value, original_task, self.root, 30)
        self.assertEqual(original['asset']['sha256'], fetched['asset']['sha256'])

    def test_altered_analysis_is_not_exported_or_counted_as_completed(self):
        task, _ = self.ready_images()
        claimed = creator_review.claim(task, 'tester', root=self.root)
        creator_review.record(task, self.answer(task, claimed['packet']), 'tester', root=self.root)
        item = creator.load(task, self.root)['items']['douyin-100']
        self.path(item['analysis']['file']).write_text('{}', encoding='utf-8')
        result = creator.export(task, root=self.root)
        self.assertEqual(0, result['counts']['fully_analyzed'])
        self.assertFalse(result['complete'])
        exported = self.root / result['delivery_directory']
        self.assertIsNone(json.loads((exported / '分析与核对.jsonl').read_text(encoding='utf-8'))['result'])

    def test_empty_feed_cannot_be_a_completed_download(self):
        task = self.make('download')
        result = self.feed(task, [], complete=True)
        self.assertFalse(result['complete'])

    def test_unidentified_record_is_preserved_and_prevents_full_discovery_claim(self):
        task = self.make()
        result = self.feed(task, [post(), {'desc': '缺少 ID 的原始记录'}, 'malformed'], complete=True)
        self.assertFalse(result['discovery_complete'])
        saved = creator.load(task, self.root)
        self.assertTrue(saved['discovery']['pagination_complete'])
        self.assertEqual(2, len(saved['discovery']['unresolved_records']))
        exported = creator.export(task, root=self.root)
        rows = [json.loads(line) for line in (self.root / exported['delivery_directory'] / '原始作品.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(3, len(rows))
        self.assertEqual({'desc': '缺少 ID 的原始记录'}, rows[1]['raw'])
        self.assertIsNone(rows[1]['id'])

    def test_catalog_length_mismatch_cannot_be_successful_video(self):
        value = catalog.normalize_post(post())
        value['media_variants'][0]['bytes'] = 100
        with patch.object(creator_files, 'download', return_value={'bytes': 10}):
            with self.assertRaisesRegex(RuntimeError, '长度'):
                creator_files.fetch_post(value, self.root)

    def test_new_analysis_instruction_keeps_transcript_but_uses_a_new_analysis_key(self):
        original = self.make(instruction='分析教学方法')
        self.feed(original, [post()])
        self.approve(original)
        creator.run(original, root=self.root, fetcher=self.material, recognizer=self.recognition)
        prior = creator.load(original, self.root)
        row = creator.records(prior, self.root)[0]
        another = self.make(instruction='分析开头和表达结构')
        self.feed(another, [post()])
        creator.run(another, root=self.root, fetcher=self.material,
                    recognizer=lambda *args: self.fail('new analysis instruction must not resubmit speech'))
        current = creator.load(another, self.root)
        self.assertEqual(prior['items'][row['id']]['speech']['result'], current['items'][row['id']]['speech']['result'])
        self.assertNotEqual(creator.analysis_key(row, prior), creator.analysis_key(row, current))
        self.assertEqual('分析教学方法', creator.load(original, self.root)['instruction'])
