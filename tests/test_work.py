from pathlib import Path
from unittest.mock import patch

from support import WorkspaceCase, content, credentials, asr, workflow, read_json, write_json
from douyin_text import work


class WorkTests(WorkspaceCase):
    def plan(self, partial=False):
        return work.create({'request': '校对这篇稿子，再改成口播；另存选题分析。', 'inputs': ['已有文稿'], 'steps': [
            {'id': 'review', 'skill': 'dyb-transcribe', 'instruction': '忠实校对'},
            {'id': 'write', 'skill': 'dyb-write', 'instruction': '改成口播', 'depends_on': ['review'], 'accept_partial': partial},
            {'id': 'analyze', 'skill': 'dyb-analyze', 'instruction': '独立分析选题'}]}, self.root)

    def outcome(self, name, text, status='completed'):
        file = self.root / 'outputs' / (name + '.txt')
        file.parent.mkdir(exist_ok=True)
        file.write_text(text, encoding='utf-8')
        return {'status': status, 'summary': text, 'coverage': '仅给定的这一篇稿件',
                'artifacts': [{'file': str(file), 'role': 'review'}]}

    def test_existing_native_task_is_reused_across_review_and_rewrite_without_asr(self):
        source = self.root / 'draft.txt'
        source.write_text('昨天整理了三段素材，花了二十分钟。', encoding='utf-8')
        native = content.plan_text(source, self.root)
        workflow.confirm(native['id'], 'rewrite', '校对这篇稿子，再改成口播', instruction='保留事实', root=self.root)
        with patch.object(credentials, 'load', side_effect=AssertionError('no credentials needed')), \
                patch.object(asr, 'recognize', side_effect=AssertionError('no speech call')):
            native = workflow.run(native['id'], self.root)
            reviewed = self.register_review(native)
            combined = self.plan()
            raw_before = workflow.task_path(native['id'], self.root).read_bytes()
            for step in ('review', 'write'):
                work.link(combined['id'], step, native['id'], self.root)
            review_file = content.checked_content(reviewed, 'review', self.root)[0]['file']
            work.record(combined['id'], 'review', {'status': 'completed', 'summary': '校对完成', 'coverage': '一篇',
                        'artifacts': [{'file': review_file, 'role': 'review'}]}, self.root)
            self.assertEqual(raw_before, workflow.task_path(native['id'], self.root).read_bytes())
            resumed = work.show(combined['id'], self.root)
            self.assertIn('write', resumed['ready_steps'])
            self.assertEqual(review_file, resumed['steps'][1]['source_artifacts'][0]['file'])
            self.assertEqual(1, work.list_works(self.root, task_id=native['id'])['total'])
            self.assertEqual(native['id'], resumed['steps'][1]['native_status'][0]['id'])

    def test_missing_dependency_blocks_only_its_dependent_and_completed_files_are_checked(self):
        combined = self.plan()
        with self.assertRaisesRegex(ValueError, '前序'):
            work.record(combined['id'], 'write', self.outcome('write', '稿件'), self.root)
        work.record(combined['id'], 'analyze', self.outcome('analysis', '独立分析'), self.root)
        work.record(combined['id'], 'review', self.outcome('review', '校对稿'), self.root)
        completed = work.record(combined['id'], 'write', self.outcome('write', '口播稿'), self.root)
        self.assertEqual('completed', completed['status'])
        (self.root / 'outputs/review.txt').write_text('changed', encoding='utf-8')
        before = work.path(combined['id'], self.root).read_bytes()
        stale = work.show(combined['id'], self.root)
        self.assertEqual('stale', stale['steps'][0]['effective_status'])
        self.assertEqual('blocked', stale['steps'][1]['effective_status'])
        self.assertEqual('completed', stale['steps'][2]['effective_status'])
        self.assertEqual(before, work.path(combined['id'], self.root).read_bytes())

    def test_partial_input_is_explicit_and_never_becomes_full_completion(self):
        combined = self.plan(partial=True)
        work.record(combined['id'], 'review', self.outcome('review', '部分校对', 'partial'), self.root)
        work.record(combined['id'], 'write', self.outcome('write', '基于部分材料的口播'), self.root)
        final = work.record(combined['id'], 'analyze', self.outcome('analysis', '分析'), self.root)
        self.assertEqual('partial', final['status'])
        other = self.plan()
        work.record(other['id'], 'review', self.outcome('other', '部分', 'partial'), self.root)
        self.assertNotIn('write', work.show(other['id'], self.root)['ready_steps'])

    def test_creator_authorization_is_referenced_without_modification_or_retry(self):
        task_id = 'creator-' + 'a' * 16
        native_file = self.root / 'runs' / task_id / 'task.json'
        write_json(native_file, {'id': task_id, 'mode': 'analyze', 'status': 'partial',
                                'authorization': {'seconds': 65, 'scope': ['one', 'two']},
                                'items': {'two': {'status': 'outcome_unknown'}}})
        saved = native_file.read_bytes()
        combined = self.plan()
        work.link(combined['id'], 'analyze', task_id, self.root)
        row = work.show(combined['id'], self.root)['steps'][2]['native_status'][0]
        self.assertEqual('partial', row['status'])
        self.assertEqual(f'runs/{task_id}/task.json', row['authorization_source'])
        self.assertEqual(saved, native_file.read_bytes())
        self.assertNotIn('authorization', row)

    def test_workspace_move_preserves_links_and_completed_artifacts(self):
        combined = self.plan()
        work.record(combined['id'], 'review', self.outcome('review', '校对'), self.root)
        self.move_workspace()
        resumed = work.show(combined['id'], self.root)
        self.assertEqual('completed', resumed['steps'][0]['effective_status'])
        self.assertTrue(resumed['steps'][1]['source_artifacts'][0]['absolute_file'].startswith(str(self.root)))

    def test_no_false_completion_missing_task_or_dependency_cycle(self):
        with self.assertRaisesRegex(ValueError, '前面'):
            work.create({'request': '测试', 'steps': [{'id': 'a', 'skill': 'dyb-write', 'instruction': '改稿', 'depends_on': ['a']}]}, self.root)
        combined = self.plan()
        with self.assertRaises(FileNotFoundError):
            work.link(combined['id'], 'review', 'dy-' + 'b' * 16, self.root)
        with self.assertRaisesRegex(ValueError, '实际产物'):
            work.record(combined['id'], 'review', {'status': 'completed', 'summary': '完成', 'coverage': '一篇'}, self.root)
        self.assertEqual([], work.load(combined['id'], self.root)['events'])

    def test_rerecord_keeps_prior_artifact_evidence(self):
        combined = self.plan()
        work.record(combined['id'], 'review', self.outcome('review-v1', '版本一'), self.root)
        work.record(combined['id'], 'review', self.outcome('review-v2', '版本二'), self.root)
        saved = work.load(combined['id'], self.root)
        previous = saved['events'][-1]['previous']['artifacts'][0]
        self.assertEqual('outputs/review-v1.txt', previous['file'])
        self.assertTrue((self.root / previous['file']).is_file())

    def test_new_upstream_revision_requires_downstream_reanalysis(self):
        combined = self.plan()
        work.record(combined['id'], 'review', self.outcome('review-v1', '版本一'), self.root)
        work.record(combined['id'], 'write', self.outcome('write', '基于版本一'), self.root)
        work.record(combined['id'], 'review', self.outcome('review-v2', '版本二'), self.root)
        state = work.show(combined['id'], self.root)
        self.assertEqual('stale', state['steps'][1]['effective_status'])
        self.assertEqual(['upstream_artifacts_changed'], state['steps'][1]['dependency_issues'])
