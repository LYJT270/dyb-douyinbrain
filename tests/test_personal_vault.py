from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from support import WorkspaceCase, SKILL_ROOT
from douyin_text import content, personal_vault as kb, workflow
from douyin_text.common import digest, read_json, relative, write_json


class PersonalVaultTests(WorkspaceCase):
    def enable(self, **kwargs):
        self.vault = self.parent / 'vault'
        return kb.enable(self.root, vault=self.vault, create=True, evidence='建立个人知识库', **kwargs)

    def module(self, name='creative'):
        kb.configure(self.root, module=name, evidence='我想做游戏解说' if name == 'creative' else '我要学剪辑')

    def manifest(self, *, task='task-1', target='素材/测试/原文.md', body='独立原文。', role='source', expected='-'):
        path = self.root / 'outputs' / (task + '.md')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding='utf-8')
        return {'task': task, 'module': 'creative', 'title': '测试材料', 'files': [{
            'source': relative(self.root, path), 'target': target, 'role': role,
            'sources': ['https://example.org/source'], 'expected_sha256': expected}]}

    def reply(self, text='我做游戏解说，希望回答直接点。', **fields):
        return kb.answer({'answer': text, 'fields': fields or {'background': '游戏解说', 'preferences': '直接'}}, self.root)

    def cli(self, *args):
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SKILL_ROOT / 'scripts/brain.py'),
            '--workspace', str(self.root), 'kb', *args], capture_output=True, env={**os.environ, 'CY_UPDATE_CHECK': '0'}, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout.decode('utf-8', 'replace') + result.stderr.decode('utf-8', 'replace'))
        return json.loads(result.stdout.decode('utf-8-sig'))

    def test_context_before_opt_in_is_read_only(self):
        before = set(self.root.rglob('*'))
        self.assertEqual('not_enabled', kb.context(self.root)['status'])
        self.assertEqual(before, set(self.root.rglob('*')))

    def test_reserved_files_cannot_be_overwritten_with_windows_case_variants(self):
        self.enable()
        self.module()
        protected = ['AGENTS.md', 'SCHEMA.md', 'SOURCE_OF_TRUTH.md', 'index.md', '使用说明.md']
        for name in protected:
            path = self.vault / name
            before = path.read_bytes()
            for target in {name, name.lower(), name.upper()}:
                with self.subTest(target=target):
                    manifest = self.manifest(task='case-' + target, target=target, role='knowledge', expected=digest(path))
                    with self.assertRaisesRegex(ValueError, '规则或索引'):
                        kb.stage(manifest, self.root)
                    self.assertEqual(before, path.read_bytes())

    def test_new_library_has_only_base_folders_and_optional_modules(self):
        shown = self.enable()
        self.assertEqual([], shown['modules'])
        self.assertEqual('background', shown['next_question']['field'])
        self.assertTrue((self.vault / '个人/档案').is_dir())
        self.assertFalse((self.vault / '素材/对标').exists())
        self.assertEqual([], kb.transactions(self.root))
        self.assertEqual('not_verified', shown['hook']['host_session'])

    def test_answers_fill_multiple_fields_skip_and_resume_from_disk(self):
        self.enable()
        shown = kb.answer({'answer': '我做解说，最近想稳定周更，叫我阿林。',
            'fields': {'background': '游戏解说', 'goal': '稳定周更', 'name': '阿林'}, 'skip': ['preferences']}, self.root)
        self.assertEqual('saved', shown['saving']['status'])
        self.assertIsNone(shown['onboarding']['next_question'])
        next_chat = self.cli('context')
        self.assertIn('阿林', next_chat['profile']['text'])
        self.assertEqual([], next_chat['missing_fields'])
        self.assertTrue(next_chat['hook']['block_matches'])
        original = list((self.vault / '素材/个人建档').glob('*.md'))[0].read_text(encoding='utf-8')
        self.assertIn('我做解说，最近想稳定周更，叫我阿林。', original)

    def test_paused_interview_does_not_prevent_correction(self):
        self.enable()
        kb.configure(self.root, pause='interview')
        self.assertIsNone(kb.status(self.root)['next_question'])
        self.reply(background='游戏解说')
        kb.configure(self.root, resume='interview')
        self.assertEqual('goal', kb.status(self.root)['next_question']['field'])

    def test_explicit_correction_updates_profile_and_retains_history(self):
        self.enable()
        first = self.reply()
        second = self.reply('改一下，我现在主要做剪辑。', background='视频剪辑')
        self.assertEqual('saved', second['saving']['status'])
        profile = (self.vault / kb.PROFILE).read_text(encoding='utf-8')
        self.assertIn('视频剪辑', profile)
        self.assertNotIn('游戏解说', profile)
        self.assertEqual(2, len(list((self.vault / '素材/个人建档').glob('*.md'))))
        self.assertTrue(list((kb.home(self.root) / 'transactions' / second['saving']['id']).glob('*.previous')))
        self.assertEqual('saved', read_json(kb.home(self.root) / 'transactions' / first['saving']['id'] / 'transaction.json')['status'])

    def test_inference_and_disabled_module_are_not_profile_facts(self):
        self.enable()
        with self.assertRaises(ValueError):
            kb.answer({'source': 'inference', 'answer': '作者说自己创业', 'fields': {'background': '创业者'}}, self.root)
        with self.assertRaises(ValueError):
            kb.answer({'answer': '想学剪辑', 'fields': {'learning.goal': '剪辑'}}, self.root)
        self.assertFalse((self.vault / kb.PROFILE).exists())

    def test_returning_to_an_earlier_answer_updates_profile_and_immediate_retry_reuses_it(self):
        self.enable()
        first = {'answer': '叫我阿林。', 'fields': {'name': '阿林'}}
        kb.answer(first, self.root)
        kb.answer({'answer': '叫我阿新。', 'fields': {'name': '阿新'}}, self.root)
        restored = kb.answer(first, self.root)
        self.assertEqual('saved', restored['saving']['status'])
        self.assertEqual('阿林', kb.state(self.root)['fields']['name']['value'])
        text = (self.vault / kb.PROFILE).read_text(encoding='utf-8')
        self.assertIn('阿林', text)
        self.assertNotIn('阿新', text)
        self.assertEqual(3, len(kb.state(self.root)['answers']))
        self.assertEqual(3, len(list((self.vault / '素材/个人建档').glob('*.md'))))
        retried = kb.answer(first, self.root)
        self.assertEqual(restored['saving']['id'], retried['saving']['id'])
        self.assertEqual(3, len(kb.state(self.root)['answers']))

    def test_manual_profile_edit_requires_real_merge(self):
        self.enable()
        self.reply()
        profile = self.vault / kb.PROFILE
        profile.write_text(profile.read_text(encoding='utf-8') + '\n用户手写：不要在周末安排任务。\n', encoding='utf-8')
        before = profile.read_bytes()
        result = self.reply('当前目标改为学习调色。', goal='学习调色')['saving']
        self.assertEqual('pending', result['status'])
        self.assertEqual(before, profile.read_bytes())
        merged = self.root / 'merged.md'
        merged.write_text(profile.read_text(encoding='utf-8') + '\n当前目标：学习调色。\n', encoding='utf-8')
        outcome = kb.revise(result['id'], [{'target': kb.PROFILE, 'source': 'merged.md', 'expected_sha256': digest(profile)}], self.root)
        self.assertEqual('saved', outcome['status'])
        self.assertIn('不要在周末安排任务', profile.read_text(encoding='utf-8'))
        self.assertTrue(outcome['revisions'])
        later = self.reply('以后回答短一点。', preferences='简短')
        self.assertEqual('saved', later['saving']['status'])
        self.assertIn('不要在周末安排任务', profile.read_text(encoding='utf-8'))

    def test_module_on_demand_and_no_inferred_learning_progress(self):
        self.enable()
        self.module('learning')
        result = kb.answer({'answer': '我要学剪辑，已经会基础切片，想通过练习学习。',
             'fields': {'learning.goal': '剪辑', 'learning.basis': '基础切片', 'learning.method': '练习'}}, self.root)
        self.assertEqual('saved', result['saving']['status'])
        self.assertIn('learning.progress', kb.status(self.root)['missing_fields'])
        self.assertNotIn('creative.direction', kb.status(self.root)['missing_fields'])

    def test_scope_requires_module_and_no_save_leaves_no_snapshot(self):
        self.enable()
        manifest = self.manifest()
        with self.assertRaisesRegex(ValueError, '模块尚未开启'):
            kb.stage(manifest, self.root)
        self.module()
        kb.configure(self.root, skip_task='task-1')
        with self.assertRaisesRegex(ValueError, '本次任务不保存'):
            kb.stage(manifest, self.root)
        self.assertFalse((kb.home(self.root) / 'transactions').exists())
        self.assertFalse(kb.context(self.root, task='task-1')['save_this_task'])

    def test_welcome_reports_existing_scope_without_requesting_permission_again(self):
        from douyin_text import onboarding
        self.enable()
        self.module()
        ready = onboarding.welcome({'vault_root': str(self.vault)}, self.root)['readiness']
        self.assertEqual('enabled_scope', ready['knowledge_destination'])
        self.assertEqual(['creative'], ready['knowledge_modules'])
        kb.configure(self.root, pause='collection')
        self.assertEqual('enabled_scope_paused', onboarding.welcome({'vault_root': str(self.vault)}, self.root)['readiness']['knowledge_destination'])

    def test_pause_blocks_queued_writes_until_requested_resume(self):
        self.enable()
        self.module()
        pending = kb.stage(self.manifest(), self.root)
        kb.configure(self.root, pause='collection')
        self.assertEqual('pending', kb.apply(pending['id'], self.root)['status'])
        self.assertFalse((self.vault / '素材/测试/原文.md').exists())
        kb.configure(self.root, resume='collection')
        self.assertEqual('saved', kb.apply(pending['id'], self.root)['status'])

    def test_generic_material_cannot_overwrite_profile_or_escape_vault(self):
        self.enable()
        self.module()
        for target in [kb.PROFILE, '个人/档案/另一份.md', '../outside.md', 'AGENTS.md', '.cy-vault.json']:
            with self.assertRaises(ValueError):
                kb.stage(self.manifest(target=target, role='knowledge'), self.root)
        with self.assertRaisesRegex(ValueError, '未知材料 role'):
            kb.stage(self.manifest(role='derived'), self.root)

    def test_save_updates_index_and_readonly_search_finds_material(self):
        self.enable()
        self.module()
        staged = kb.stage(self.manifest(body='游戏解说的开头案例。'), self.root)
        saved = kb.apply(staged['id'], self.root)
        self.assertEqual('saved', saved['status'])
        self.assertEqual(digest(self.vault / 'index.md'), saved['index_sha256'])
        matches = kb.context(self.root, query='解说')['matches']
        self.assertEqual(1, len(matches))
        self.assertIn('游戏解说', matches[0]['excerpt'])

    def test_same_material_new_task_and_target_reuses_verified_files(self):
        self.enable()
        self.module()
        first = kb.stage(self.manifest(), self.root)
        kb.apply(first['id'], self.root)
        repeated = kb.stage(self.manifest(task='task-2', target='素材/另一个名字.md'), self.root)
        self.assertTrue(repeated['reused'])
        self.assertEqual(first['id'], repeated['id'])
        self.assertFalse((self.vault / '素材/另一个名字.md').exists())
        self.assertEqual(1, len(kb.transactions(self.root)))

    def test_changed_or_missing_saved_destination_is_not_a_dedup_success(self):
        self.enable()
        self.module()
        first = kb.stage(self.manifest(), self.root)
        kb.apply(first['id'], self.root)
        (self.vault / '素材/测试/原文.md').write_text('人工变化', encoding='utf-8')
        repeated = kb.stage(self.manifest(task='task-2', target='素材/另一个名字.md'), self.root)
        self.assertFalse(repeated.get('reused', False))
        same_task = kb.stage(self.manifest(), self.root)
        self.assertEqual('pending', same_task['status'])
        self.assertNotEqual(first['id'], same_task['id'])
        self.assertEqual('pending', kb.apply(same_task['id'], self.root)['status'])

    def test_preflight_conflict_leaves_every_destination_untouched(self):
        self.enable()
        self.module()
        manifest = self.manifest()
        conflict = self.vault / '知识库/主题.md'
        conflict.parent.mkdir(exist_ok=True)
        conflict.write_text('人工正文', encoding='utf-8')
        manifest['files'].append({**manifest['files'][0], 'target': '知识库/主题.md', 'role': 'knowledge'})
        pending = kb.stage(manifest, self.root)
        self.assertEqual('pending', kb.apply(pending['id'], self.root)['status'])
        self.assertFalse((self.vault / '素材/测试/原文.md').exists())
        self.assertEqual('人工正文', conflict.read_text(encoding='utf-8'))

    def test_index_failure_after_files_are_written_resumes_without_duplicates(self):
        self.enable()
        self.module()
        item = kb.stage(self.manifest(), self.root)
        with patch.object(kb, 'write_index', side_effect=OSError('模拟磁盘暂时不可写')):
            result = kb.apply(item['id'], self.root)
        self.assertEqual('pending', result['status'])
        self.assertTrue((self.vault / '素材/测试/原文.md').is_file())
        self.assertEqual('saved', kb.retry(self.root)['items'][0]['status'])
        self.assertEqual([], kb.status(self.root)['pending'])
        self.assertEqual(1, len(list((self.vault / '素材/测试').glob('*.md'))))

    def test_raw_sources_cannot_be_updated_in_place(self):
        self.enable()
        self.module()
        with self.assertRaisesRegex(ValueError, '原始资料不可覆盖'):
            kb.stage(self.manifest(expected='a' * 64), self.root)

    def test_multiple_answers_during_storage_outage_replay_in_order(self):
        self.enable()
        with patch.object(kb, 'atomic', side_effect=OSError('磁盘暂不可写')):
            first = self.reply(background='游戏解说')
            second = self.reply('希望每周更新。', goal='每周更新')
        self.assertEqual('pending', first['saving']['status'])
        self.assertEqual('pending', second['saving']['status'])
        self.assertEqual(['saved', 'saved'], [x['status'] for x in kb.retry(self.root)['items']])
        profile = (self.vault / kb.PROFILE).read_text(encoding='utf-8')
        self.assertIn('游戏解说', profile)
        self.assertIn('每周更新', profile)
        self.assertEqual([], kb.status(self.root)['pending'])

    def test_rules_change_blocks_automatic_write(self):
        self.enable()
        self.module()
        item = kb.stage(self.manifest(), self.root)
        with (self.vault / 'AGENTS.md').open('a', encoding='utf-8') as out:
            out.write('\n新增规则：必须通过既有发布器。\n')
        result = kb.apply(item['id'], self.root)
        self.assertEqual('pending', result['status'])
        self.assertIn('规则已改变', result['error'])
        self.assertFalse((self.vault / '素材/测试/原文.md').exists())

    def test_existing_vault_and_external_profile_are_bound_without_reorganization(self):
        self.vault = self.parent / 'existing'
        self.vault.mkdir()
        (self.vault / 'AGENTS.md').write_text('保留我的规则。', encoding='utf-8')
        (self.vault / 'index.md').write_text('# 原有导航\n', encoding='utf-8')
        profile = self.parent / 'canonical.md'
        profile.write_text('已有真实档案', encoding='utf-8')
        before = {p.name: p.read_bytes() for p in self.vault.iterdir()}
        shown = kb.enable(self.root, vault=self.vault, profile=profile, evidence='接入我的现有库')
        self.assertEqual('target_rules', shown['write_mode'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.vault.iterdir()})
        self.assertIn('已有真实档案', kb.context(self.root)['profile']['text'])
        self.module()
        item = kb.stage(self.manifest(), self.root)
        self.assertEqual('awaiting_target_writer', kb.apply(item['id'], self.root)['status'])
        self.assertFalse((self.vault / '素材').exists())
        self.assertEqual('pending', kb.apply(item['id'], self.root, external=True)['status'])
        for row in item['files']:
            target = self.vault / row['target']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((self.root / row['snapshot']).read_bytes())
        self.assertEqual('pending', kb.apply(item['id'], self.root, external=True)['status'])
        (self.vault / 'index.md').write_text('# 原有导航\n[材料](素材/测试/原文.md)', encoding='utf-8')
        self.assertEqual('saved', kb.apply(item['id'], self.root, external=True)['status'])
        self.assertFalse((self.vault / '个人').exists())

    def test_agent_hook_preserves_global_rules_and_respects_codex_override(self):
        codex_home = self.parent / 'codex-home'
        codex_home.mkdir()
        regular = codex_home / 'AGENTS.md'
        regular.write_text('基础规则', encoding='utf-8')
        override = codex_home / 'AGENTS.override.md'
        override.write_bytes(b'\xef\xbb\xbf' + '用户规则\r\n'.encode('utf-8'))
        with patch.dict(os.environ, {'CODEX_HOME': str(codex_home)}):
            shown = self.enable(scope='agent', host='codex')
        self.assertEqual(str(override), shown['hook']['file'])
        self.assertEqual('基础规则', regular.read_text(encoding='utf-8'))
        self.assertTrue(override.read_bytes().startswith(b'\xef\xbb\xbf'))
        self.assertIn('用户规则', override.read_text(encoding='utf-8-sig'))
        self.assertTrue(list((kb.home(self.root) / 'entry-backups').glob('*.md')))

    def test_hook_for_other_workspace_is_not_overwritten(self):
        entry = self.parent / 'instructions.md'
        entry.write_text(kb.HOOK_START + '\ncy-vault-workspace: other\n' + kb.HOOK_END, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '另一个知识库'):
            self.enable(scope='agent', entry=entry)
        self.assertFalse((self.parent / 'vault').exists())

    def test_cli_reloads_paused_state_in_fresh_process(self):
        self.enable()
        self.cli('module', 'creative', '--evidence', '创作')
        self.cli('pause', 'collection')
        self.assertTrue(self.cli('status')['collection_paused'])
        self.cli('resume', 'collection')
        self.assertFalse(self.cli('status')['collection_paused'])

    def test_normal_task_collects_without_changing_purpose_or_calling_asr(self):
        self.enable()
        self.module()
        source = self.parent / 'input.txt'
        source.write_text('游戏解说原稿。', encoding='utf-8')
        task = content.plan_text([source], self.root)
        workflow.confirm(task['id'], 'transcribe', '转写这份稿', root=self.root)
        task = workflow.run(task['id'], self.root)
        self.register_review(task)
        content.deliver(task['id'], root=self.root)
        task_file = self.root / 'runs' / task['id'] / 'task.json'
        before = task_file.read_bytes()
        result = kb.collect(task['id'], 'creative', self.root)
        self.assertEqual('saved', result['status'])
        self.assertEqual(before, task_file.read_bytes())
        self.assertEqual(['source', 'reviewed'], [r['role'] for r in result['files']])
        self.assertIn('游戏解说原稿。', (self.vault / result['files'][0]['target']).read_text(encoding='utf-8'))
        self.assertTrue(kb.collect(task['id'], 'creative', self.root)['reused'])

    def test_new_spoken_revision_does_not_collect_stale_delivery(self):
        self.enable()
        self.module()
        task = self.recognize_run(self.task('rewrite'))
        self.register_review(task)
        files = self.write_texts(task, 'spoken')
        content.register_content(task['id'], files, 'spoken', self.root, evidence='改写')
        content.deliver(task['id'], 'spoken', self.root)
        newer = files[0].with_name('new-spoken.txt')
        newer.write_text('尚未交付的新版本。', encoding='utf-8')
        content.register_content(task['id'], [newer], 'spoken', self.root, evidence='再改短一点')
        outcome = kb.collect(task['id'], 'creative', self.root)
        self.assertEqual('saved', outcome['status'])
        self.assertEqual(['source', 'reviewed'], [row['role'] for row in outcome['files']])
