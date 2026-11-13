"""Recovery scenarios use isolated files and forbidden network/ASR boundaries."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from support import WorkspaceCase, Response, credentials, content, workflow, read_json, write_json, SKILL_ROOT
from douyin_text import continuation, creator, creator_review, work
from douyin_text.common import digest
import test_creator


class ContinuationTests(WorkspaceCase):
    def text_task(self, count=1):
        files = []
        for i in range(count):
            file = self.root / f'input-{i}.txt'
            file.write_text(f'第 {i} 段原文。', encoding='utf-8')
            files.append(file)
        task = content.plan_text(files, self.root)
        workflow.confirm(task['id'], 'rewrite', '校对后改成口播', instruction='保留原意', root=self.root)
        return workflow.run(task['id'], self.root)

    def test_exact_matching_is_read_only_and_ambiguous_requests_are_not_guessed(self):
        task = self.text_task()
        before = workflow.task_path(task['id'], self.root).read_bytes()
        with patch.object(creator.douyin_browser, 'resolve_url', side_effect=AssertionError('network')):
            found = continuation.resume(inputs=task['inputs'], purpose='rewrite', instruction='保留原意', root=self.root)
            self.assertEqual('matched', found['status'])
            self.assertEqual(task['id'], found['recovery']['task'])
            self.assertEqual('review_items', found['recovery']['next_actions'][0]['action'])
            self.assertEqual('choose_task', continuation.resume(root=self.root)['status'])
            self.text_task()
            self.assertEqual('choose_task', continuation.resume(inputs=task['inputs'], purpose='rewrite',
                             instruction='保留原意', root=self.root)['status'])
        self.assertEqual(before, workflow.task_path(task['id'], self.root).read_bytes())

    def test_changed_source_is_not_automatically_reused_as_same_task(self):
        task = self.text_task()
        Path(task['inputs'][0]).write_text('新的源稿。', encoding='utf-8')
        found = continuation.resume(inputs=task['inputs'], purpose='rewrite', instruction='保留原意', root=self.root)
        self.assertEqual('choose_task', found['status'])
        self.assertTrue(found['candidates'][0]['source_changed'])
        # Explicitly continuing the frozen task still uses its original snapshot.
        self.assertEqual('selected', continuation.resume(task_id=task['id'], root=self.root)['status'])
        self.assertEqual('第 0 段原文。', content.originals(task, self.root)[0]['text'])

    def test_partial_registration_resumes_only_missing_items_and_preserves_independent_progress(self):
        task = self.text_task(2)
        files = self.write_texts(task, 'review')
        first, second = [x['id'] for x in task['results']]
        content.register_content(task['id'], files[:1], 'review', self.root, item_ids=[first])
        resumed = continuation.resume(task_id=task['id'], root=self.root)['recovery']
        actions = {x['action']: x for x in resumed['next_actions']}
        self.assertEqual([second], actions['review_items']['item_ids'])
        self.assertEqual([first], actions['rewrite_items']['item_ids'])
        content.register_content(task['id'], files[1:], 'review', self.root, item_ids=[second])
        self.assertEqual(2, len(content.checked_content(workflow.load(task['id'], self.root), 'review', self.root)))

    def test_edited_working_copy_keeps_old_snapshot_and_invalidates_derived_script(self):
        task = self.text_task()
        task = self.register_review(task)
        speech = self.write_texts(task, 'spoken')
        task = content.register_content(task['id'], speech, 'spoken', self.root)
        task = content.deliver(task['id'], 'spoken', self.root)
        old_delivery = copy.deepcopy(task['delivery'])
        entry = task['review']['files'][0]
        old_text = self.path(entry['snapshot_file']).read_text(encoding='utf-8')
        edited = self.path(entry['file'])
        edited.write_text('用户修正了关键事实。', encoding='utf-8')
        resumed = continuation.resume(task_id=task['id'], root=self.root)['recovery']
        changed = resumed['working_content']['review'][0]
        self.assertEqual('edited', changed['state'])
        self.assertIn('用户修正', changed['diff'])
        self.assertEqual(old_text, self.path(entry['snapshot_file']).read_text(encoding='utf-8'))
        task = content.register_content(task['id'], [edited], 'review', self.root)
        self.assertEqual('stale', content.inspect_content(task, 'spoken', self.root)[0]['state'])
        with self.assertRaisesRegex(ValueError, '依据已变化'):
            content.deliver(task['id'], 'spoken', self.root)
        self.assertEqual(old_delivery['sha256'], digest(self.path(old_delivery['file'])))
        self.assertEqual('review', task['content_history'][-1]['kind'])
        self.assertEqual(entry['sha256'], task['content_history'][-1]['files'][0]['sha256'])
        self.assertTrue(self.path(task['spoken']['files'][0]['snapshot_file']).is_file())

    def test_analysis_requires_every_review_and_rechecks_registered_files(self):
        task = self.text_task(2)
        task.update(purpose='analyze', instruction='分析两篇文稿')
        workflow.save(task, self.root)
        files = self.write_texts(task, 'review')
        first, second = [x['id'] for x in task['results']]
        task = content.register_content(task['id'], files[:1], 'review', self.root, item_ids=[first])
        self.assertEqual('awaiting_review', task['status'])
        report = self.root / 'analysis.md'
        report.write_text('两篇文稿的综合分析。', encoding='utf-8')
        with self.assertRaises(ValueError):
            workflow.finish_analysis(task['id'], report, self.root)
        # Older records may already have the premature ready status.
        task['status'] = 'awaiting_analysis'
        workflow.save(task, self.root)
        with self.assertRaisesRegex(ValueError, '完整登记'):
            workflow.finish_analysis(task['id'], report, self.root)
        task = content.register_content(task['id'], files[1:], 'review', self.root, item_ids=[second])
        self.assertEqual('awaiting_analysis', task['status'])
        files[0].write_text('登记后的人工作品修改。', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '已登记正文发生变化'):
            workflow.finish_analysis(task['id'], report, self.root)
        content.register_content(task['id'], files[:1], 'review', self.root, item_ids=[first])
        self.assertEqual('completed', workflow.finish_analysis(task['id'], report, self.root)['status'])

    def test_interrupted_batch_keeps_unfinished_scope_through_partial_delivery_and_fork(self):
        other = self.parent / 'second.wav'
        other.write_bytes(self.wav.read_bytes()[:-2] + b'\x01\x00')
        task = workflow.plan([str(self.wav), str(other)], self.root)
        workflow.confirm(task['id'], 'transcribe', '转写这两条', root=self.root)
        transcribe, calls = workflow.transcribe, []
        def interrupted(job, *args, **kwargs):
            calls.append(job['id'])
            if len(calls) == 2:
                raise KeyboardInterrupt('process stopped between saved jobs')
            return transcribe(job, *args, **kwargs)
        with patch.object(workflow, 'transcribe', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.recognize_run(task)
        task = workflow.load(task['id'], self.root)
        self.assertEqual('running', task['status'])
        self.assertEqual([], task['failures'])
        self.assertEqual(1, len(task['results']))
        before = workflow.task_path(task['id'], self.root).read_bytes()
        resumed = continuation.resume(task_id=task['id'], root=self.root)['recovery']
        self.assertEqual(before, workflow.task_path(task['id'], self.root).read_bytes())
        self.assertTrue(any(a['action'] == 'resume_saved_items' for a in resumed['next_actions']))
        self.assertIn(calls[1], [gap.get('id') for gap in resumed['coverage']['gaps']])
        task = self.register_review(task)
        self.assertEqual('incomplete', task['status'])
        partial = content.deliver(task['id'], 'review', self.root)
        self.assertFalse(partial['delivery']['complete'])
        self.assertEqual('incomplete', partial['status'])
        first_review = copy.deepcopy(partial['review']['files'][0])
        fork = workflow.reanalyze(task['id'], '分析已有部分', self.root)
        report = self.root / 'partial-analysis.md'
        report.write_text('只分析已取得的第一条，第二条缺失。', encoding='utf-8')
        self.assertEqual('incomplete', workflow.finish_analysis(fork['id'], report, self.root)['status'])
        with patch.object(workflow.media, 'discover', side_effect=AssertionError('new discovery')), \
             patch.object(credentials, 'load', return_value={'api_key': 'test-value'}), \
             patch.object(workflow.asr.request, 'urlopen', side_effect=lambda *a, **k: Response()):
            task = workflow.run(task['id'], self.root, saved_scope=True)
        self.assertEqual(2, len(task['results']))
        resumed = continuation.resume(task_id=task['id'], root=self.root)['recovery']
        self.assertEqual([], resumed['coverage']['gaps'])
        self.assertEqual([calls[1]], next(a['item_ids'] for a in resumed['next_actions'] if a['action'] == 'review_items'))
        self.assertEqual(first_review, task['review']['files'][0])
        new_review = self.root / 'second-review.txt'
        new_review.write_text('第二条校对稿。', encoding='utf-8')
        content.register_content(task['id'], [new_review], 'review', self.root, item_ids=[calls[1]])
        final = content.deliver(task['id'], 'review', self.root)
        self.assertTrue(final['delivery']['complete'])
        self.assertEqual(2, final['delivery']['count'])
        self.assertTrue(self.path(partial['delivery']['file']).is_file())

    def test_completed_delivery_is_reused_without_new_work(self):
        task = self.text_task()
        task = self.register_review(task)
        task = content.register_content(task['id'], self.write_texts(task, 'spoken'), 'spoken', self.root)
        content.deliver(task['id'], 'spoken', self.root)
        before = workflow.task_path(task['id'], self.root).read_bytes()
        result = continuation.resume(task_id=task['id'], root=self.root)
        self.assertTrue(result['recovery']['finished'])
        self.assertEqual([], result['recovery']['next_actions'])
        self.assertEqual(before, workflow.task_path(task['id'], self.root).read_bytes())

    def test_work_distinguishes_edited_and_missing_files_and_continues_independent_step(self):
        task = work.create({'request': '分别处理', 'inputs': [], 'steps': [
            {'id': 'a', 'skill': 'cy-write', 'instruction': '第一条'},
            {'id': 'b', 'skill': 'cy-write', 'instruction': '第二条'}]}, self.root)
        file = self.root / 'one.txt'
        file.write_text('初稿', encoding='utf-8')
        work.record(task['id'], 'a', {'status': 'completed', 'summary': '第一条完成', 'coverage': '一条',
            'artifacts': [{'file': str(file), 'role': 'rewrite'}]}, self.root)
        file.write_text('用户修改', encoding='utf-8')
        state = continuation.resume(task_id=task['id'], root=self.root)['recovery']
        self.assertEqual('edited', state['steps'][0]['artifacts'][0]['state'])
        self.assertTrue(any(a['action'] == 'continue_step' and a['step'] == 'b' for a in state['next_actions']))
        file.unlink()  # Throwaway test fixture, not user data.
        self.assertEqual('missing', work.show(task['id'], self.root)['steps'][0]['artifacts'][0]['state'])

    def test_cli_resume_after_process_restart_and_workspace_move(self):
        task = self.text_task()
        self.register_review(task)
        self.move_workspace()
        command = [sys.executable, '-B', '-X', 'utf8', str(SKILL_ROOT / 'scripts/brain.py'),
                   '--workspace', str(self.root), 'resume', '--task', task['id']]
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                env={**os.environ, 'CY_UPDATE_CHECK': '0'}, check=True)
        data = json.loads(result.stdout)
        self.assertEqual('rewrite_items', data['recovery']['next_actions'][0]['action'])
        self.assertFalse(data['network_called'])
        self.assertFalse(data['cloud_asr_called'])

    def test_document_new_question_is_an_independent_offline_task(self):
        task = self.text_task()
        task = self.register_review(task)
        before = workflow.task_path(task['id'], self.root).read_bytes()
        fork = workflow.reanalyze(task['id'], '分析开头写法', self.root)
        self.assertNotEqual(task['id'], fork['id'])
        self.assertEqual('awaiting_analysis', fork['status'])
        parent_review = self.path(task['review']['files'][0]['file'])
        parent_review.write_text('后来编辑的原任务稿件', encoding='utf-8')
        self.assertNotEqual(parent_review.read_text(encoding='utf-8'),
                            self.path(fork['review']['files'][0]['file']).read_text(encoding='utf-8'))
        report = self.root / 'new-analysis.md'
        report.write_text('基于已有文稿分析开头。', encoding='utf-8')
        self.assertEqual('completed', workflow.finish_analysis(fork['id'], report, self.root)['status'])
        self.assertEqual(before, workflow.task_path(task['id'], self.root).read_bytes())
        with self.assertRaisesRegex(ValueError, '离线'):
            workflow.run(fork['id'], self.root)

    def test_saved_scope_reuses_known_results_and_preserves_undiscovered_gap(self):
        task = self.recognize_run(self.task())
        original_ids = [x['id'] for x in task['results']]
        profile = 'https://www.douyin.com/user/MS4test'
        task.update(inputs=[profile], status='incomplete',
                    failures=[{'stage': 'acquisition', 'input_number': 1, 'error': '分页尚未完成'}])
        workflow.save(task, self.root)
        jobs_path = workflow.task_path(task['id'], self.root).parent / 'jobs.json'
        jobs = read_json(jobs_path)
        for job in jobs:
            job['input'] = profile
        write_json(jobs_path, jobs)
        with patch.object(workflow.media, 'acquire_batch', side_effect=AssertionError('profile refreshed')), \
             patch.object(workflow.media, 'discover', side_effect=AssertionError('new scope')), \
             patch.object(workflow.asr, 'recognize', side_effect=AssertionError('duplicate ASR')):
            resumed = workflow.run(task['id'], self.root, saved_scope=True)
        self.assertEqual(original_ids, [x['id'] for x in resumed['results']])
        self.assertEqual('incomplete', resumed['status'])
        self.assertIn('分页', resumed['failures'][0]['error'])

    def test_missing_native_record_is_reported_without_losing_independent_work(self):
        native = self.text_task()
        combined = work.create({'request': '继续改稿', 'steps': [
            {'id': 'write', 'skill': 'cy-write', 'instruction': '改稿'}]}, self.root)
        work.link(combined['id'], 'write', native['id'], self.root)
        workflow.task_path(native['id'], self.root).unlink()
        result = continuation.resume(task_id=combined['id'], root=self.root)
        self.assertEqual('inspect_native_gap',
            result['recovery']['next_actions'][0]['native_tasks'][0]['next_actions'][0]['action'])


class CreatorContinuationTests(WorkspaceCase):
    make = test_creator.CreatorTests.make
    feed = test_creator.CreatorTests.feed
    material = test_creator.CreatorTests.material
    ready_images = test_creator.CreatorTests.ready_images
    answer = test_creator.CreatorTests.answer

    def analyzed(self):
        task, _ = self.ready_images()
        packet = creator_review.claim(task, 'tester', root=self.root)['packet']
        creator_review.record(task, self.answer(task, packet), 'tester', root=self.root)
        return task

    def test_partial_review_rebuilds_after_missing_image_arrives(self):
        for force in (False, True):
            with self.subTest(reanalyze=force):
                task = self.make(instruction=f'补齐图片 {force}')
                value = test_creator.post(images=True)
                value['images'].append({'uri': 'second', 'url_list': ['https://example.invalid/second']})
                self.feed(task, [value])
                creator.run(task, root=self.root, fetcher=self.material)
                creator_review.prepare(task, root=self.root)
                packet = creator_review.claim(task, 'tester', root=self.root)['packet']
                result = creator_review.record(task, self.answer(task, packet), 'tester', root=self.root)
                self.assertEqual(0, result['counts']['fully_analyzed'])
                state = creator.load(task, self.root)
                item = state['items']['douyin-100']
                previous = copy.deepcopy(item['analysis'])
                image = self.root / f'second-{force}.png'
                image.write_bytes(b'new image')
                item['media']['images'].append({'file': image.name, 'sha256': digest(image), 'index': 2})
                item['media']['complete'] = True
                creator.save(state, self.root)
                creator_review.prepare(task, reanalyze=force, cached_only=True, root=self.root)
                packet = creator_review.claim(task, 'tester', root=self.root)['packet']
                source = read_json(self.path(packet['file']))['items'][0]
                self.assertEqual([], source['gaps'])
                self.assertEqual(2, len(source['images']))
                self.assertEqual(previous, source['previous_review'])
                answer = self.answer(task, packet)
                data = read_json(answer)
                data['items'][0]['review'].update(reuse_previous=True, viewed_images=[image.name])
                write_json(answer, data)
                result = creator_review.record(task, answer, 'tester', root=self.root)
                self.assertEqual(1, result['counts']['fully_analyzed'])
                self.assertEqual(previous['sha256'], digest(self.path(previous['file'])))

    def test_repreparation_uses_new_cover_and_requested_frames_with_old_provenance(self):
        task = self.make()
        value = test_creator.post()
        value['video']['cover'] = {'url_list': ['https://example.invalid/cover']}
        self.feed(task, [value])
        state = creator.load(task, self.root)
        post = creator.records(state, self.root)[0]
        state['items'][post['id']] = {'media': self.material(post, state, self.root, 60),
                                    'speech': {'status': 'no_speech_detected'}}
        creator.save(state, self.root)
        assets = []
        for name in ('old.png', 'new.png', 'cover.png'):
            file = self.root / name
            file.write_bytes(name.encode())
            assets.append({'file': name, 'sha256': digest(file), 'at': 0})
        with patch.object(creator_review.review, 'cached_frames', return_value={'frames': assets[:1]}), \
             patch.object(creator_review.creator_files, 'cached_asset', return_value=None):
            creator_review.prepare(task, cached_only=True, root=self.root)
        packet = creator_review.claim(task, 'tester', root=self.root)['packet']
        result = creator_review.record(task, self.answer(task, packet), 'tester', root=self.root)
        self.assertEqual(0, result['counts']['fully_analyzed'])
        with patch.object(creator_review.review, 'cached_frames', return_value={'frames': assets[1:2]}) as frames, \
             patch.object(creator_review.creator_files, 'cached_asset', return_value=assets[2]):
            creator_review.prepare(task, reanalyze=True, max_frames=12, strategy='action', cached_only=True, root=self.root)
        self.assertEqual(12, frames.call_args.kwargs['maximum'])
        self.assertEqual('action', frames.call_args.kwargs['strategy'])
        packet = creator_review.claim(task, 'tester', root=self.root)['packet']
        source = read_json(self.path(packet['file']))['items'][0]
        self.assertEqual([], source['gaps'])
        self.assertEqual({'new.png', 'cover.png'}, {i['file'] for i in source['images']})
        answer = self.answer(task, packet)
        data = read_json(answer)
        data['items'][0]['review']['reuse_previous'] = True
        write_json(answer, data)
        self.assertEqual(1, creator_review.record(task, answer, 'tester', root=self.root)['counts']['fully_analyzed'])
        with patch.object(creator_review.review, 'cached_frames', return_value={'frames': assets[1:2]}) as frames, \
             patch.object(creator_review.creator_files, 'cached_asset', return_value=assets[2]):
            creator_review.prepare(task, reanalyze=True, max_frames=2, cached_only=True, root=self.root)
        self.assertEqual(2, frames.call_args.kwargs['maximum'])

    def test_offline_new_question_reuses_review_with_provenance_and_never_calls_network(self):
        original = self.analyzed()
        old_bytes = creator.task_path(original, self.root).read_bytes()
        with patch.object(creator, 'discover', side_effect=AssertionError('refresh')), \
             patch.object(creator.creator_files, 'download', side_effect=AssertionError('download')), \
             patch.object(creator_review.review, 'cached_frames', side_effect=AssertionError('unnecessary frames')), \
             patch.object(creator.asr, 'recognize', side_effect=AssertionError('ASR')):
            task = creator.reanalyze(original, '只分析开头', images=True, root=self.root)['task']
            self.assertEqual([], creator.load(task, self.root)['authorizations'])
            state = creator_review.prepare(task, root=self.root)
            self.assertEqual(0, state['counts']['analyzed'])
            packet = creator_review.claim(task, 'tester', root=self.root)['packet']
            file = self.answer(task, packet, viewed=False)
            submitted = read_json(file)
            submitted['items'][0]['review'] = {'reuse_previous': True}
            write_json(file, submitted)
            result = creator_review.record(task, file, 'tester', root=self.root)
            self.assertEqual(1, result['counts']['review_reused'])
            self.assertEqual(1, result['counts']['fully_analyzed'])
            self.assertFalse(result['complete'], 'A new question still needs its own report')
            current = creator.load(task, self.root)
            row = creator.analysis_record(current['items']['douyin-100'], creator.records(current, self.root)[0], current, self.root)
            self.assertTrue(row['review']['reused_from'])
            self.assertEqual('只分析开头', row['source']['instruction'])
        self.assertEqual(old_bytes, creator.task_path(original, self.root).read_bytes())

    def test_offline_task_refuses_discovery_paid_auth_and_run(self):
        task = creator.reanalyze(self.analyzed(), '新问题', root=self.root)['task']
        self.assertFalse(creator.load(task, self.root)['capabilities']['images'], 'New session capabilities must be explicit')
        for action in (lambda: creator.discover(task, root=self.root),
                       lambda: creator.run(task, root=self.root),
                       lambda: creator.preflight(task, root=self.root),
                       lambda: creator.authorize(task, 'unused', 'new', root=self.root)):
            with self.assertRaisesRegex(ValueError, '离线'):
                action()

    def test_preparation_retains_claimed_packets_and_completed_item_progress(self):
        task, _ = self.ready_images(2)
        packet = creator_review.claim(task, 'tester', root=self.root)['packet']
        again = creator_review.prepare(task, root=self.root)
        self.assertIn(packet['id'], [p['id'] for p in again['packets']])
        creator_review.record(task, self.answer(task, packet), 'tester', root=self.root)
        next_packet = creator_review.claim(task, 'tester', root=self.root)['packet']
        self.assertNotEqual(packet['id'], next_packet['id'])
        self.assertNotEqual(packet['item_ids'], next_packet['item_ids'])

    def test_modified_review_cannot_be_reused_and_resume_never_refreshes(self):
        task = self.analyzed()
        state = creator.load(task, self.root)
        file = self.path(state['items']['douyin-100']['analysis']['review_file'])
        file.write_text('人工修订', encoding='utf-8')
        with patch.object(creator, 'discover', side_effect=AssertionError('refresh')):
            resumed = continuation.resume(task_id=task, root=self.root)['recovery']
            self.assertEqual(0, resumed['counts']['analyzed'])
            self.assertFalse(resumed['finished'])
        self.assertEqual('人工修订', file.read_text(encoding='utf-8'))
