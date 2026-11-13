from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from support import WorkspaceCase, SKILL_ROOT
from douyin_text import personal_vault as kb
from douyin_text.common import digest, relative, write_json


class VaultDomainRuntimeTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        self.vault = self.parent / 'vault'

    def enable(self, **kwargs):
        return kb.enable(self.root, vault=self.vault, create=True, evidence='请协助我安排生活、工作和学习', **kwargs)

    def test_new_vault_uses_three_domains_and_public_life_profile(self):
        result = self.enable(focus='learning')
        self.assertEqual(['life', 'work', 'learning'], result['modules'])
        self.assertEqual('learning', result['focus'])
        self.assertEqual('not_started', result['domains']['work']['status'])
        self.assertEqual('in_progress', result['domains']['learning']['status'])
        self.assertEqual(self.vault / '生活/个人档案/基本资料.md', Path(result['profile_entry']))
        self.assertTrue(all((self.vault / name).is_dir() for name in ('生活', '工作', '学习')))

    def test_existing_legacy_profile_is_read_without_reorganization(self):
        self.vault.mkdir()
        legacy = self.vault / '个人/档案/基本资料.md'
        legacy.parent.mkdir(parents=True)
        legacy.write_text('# 旧档案\n用户明确资料仍在这里。\n', encoding='utf-8')
        result = kb.enable(self.root, vault=self.vault, evidence='接入已有知识库')
        self.assertEqual('target_rules', result['write_mode'])
        self.assertEqual(legacy, Path(result['profile_entry']))
        self.assertIn('用户明确资料仍在这里', kb.context(self.root)['profile']['text'])
        self.assertFalse((self.vault / kb.PROFILE).exists())

    def test_free_topic_answer_tracks_branch_and_keeps_interview_open(self):
        self.enable(focus='work')
        recorded = kb.answer({
            'domain': 'work',
            'topic': '项目排期与精力',
            'topic_status': 'paused',
            'question': '最近哪种排期最难坚持？',
            'branch': {'id': '临时需求', 'status': 'paused'},
            'answer': '临时需求太多，常把原计划打断。',
            'fields': {'work.constraints': '临时需求常打断原计划'},
            'skip': ['work.tools'],
        }, self.root)
        self.assertEqual('saved', recorded['saving']['status'])
        state = kb.state(self.root)
        topic = state['progress']['topics']['work']['项目排期与精力']
        self.assertEqual(['work.constraints'], topic['fields'])
        self.assertEqual(['work.tools'], topic['skipped'])
        self.assertEqual('paused', topic['status'])
        self.assertEqual('paused', topic['branches']['临时需求']['status'])
        self.assertEqual('临时需求太多，常把原计划打断。', (self.vault / '工作/资料/建档' / f"{state['answers'][-1]}.md").read_text(encoding='utf-8').splitlines()[-1])
        status = kb.context(self.root)
        self.assertEqual('paused', status['domains']['work']['status'])
        self.assertTrue(status['interview_prompt'])
        self.assertIsNotNone(status['next_question'])

    def test_refused_topic_is_remembered_and_other_topics_can_continue(self):
        self.enable()
        kb.answer({'domain': 'life', 'topic': '家庭财务', 'topic_status': 'refused',
                   'answer': '这个话题先不聊。'}, self.root)
        status = kb.status(self.root)
        self.assertEqual([{'domain': 'life', 'topic': '家庭财务'}], status['refused_topics'])
        self.assertIn('家庭财务', status['domains']['life']['refused_topics'])
        self.assertEqual('in_progress', status['domains']['life']['status'])

    def test_legacy_state_reenable_keeps_scope_and_creative_alias_works(self):
        self.enable()
        value = kb.state(self.root)
        value['modules'] = ['creative', 'learning']
        value.pop('focus', None)
        value.pop('selected', None)
        value.pop('domain_started', None)
        value.pop('pending_domains', None)
        kb.save(value, self.root)

        result = kb.enable(self.root, vault=self.vault, evidence='重新连接已有资料库')
        self.assertEqual(['work', 'learning'], result['modules'])
        self.assertTrue(result['domains']['life']['awaiting_confirmation'])
        self.assertEqual(['life'], result['pending_domains'])
        cli = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SKILL_ROOT / 'scripts/brain.py'),
            '--workspace', str(self.root), 'kb', 'module', 'creative', '--evidence', '继续创作工作'],
            capture_output=True, env={**os.environ, 'CY_UPDATE_CHECK': '0'}, timeout=30)
        self.assertEqual(0, cli.returncode, cli.stderr.decode('utf-8', 'replace'))
        self.assertIn('work', json.loads(cli.stdout.decode('utf-8-sig'))['modules'])
        answer = kb.answer({'domain': 'creative', 'topic': '内容方向', 'answer': '现在重点做战术教学。',
                            'fields': {'creative.direction': '战术教学'}}, self.root)
        self.assertEqual('saved', answer['saving']['status'])
        self.assertTrue((self.vault / '工作/资料/建档').is_dir())
        self.assertIn('战术教学', (self.vault / kb.PROFILE).read_text(encoding='utf-8'))

    def test_legacy_common_field_without_focus_stays_in_an_open_domain(self):
        self.enable()
        value = kb.state(self.root)
        value['modules'] = ['creative', 'learning']
        value.pop('focus', None)
        value.pop('selected', None)
        value.pop('domain_started', None)
        value.pop('pending_domains', None)
        kb.save(value, self.root)

        recorded = kb.answer({'answer': '叫我阿明', 'fields': {'name': '阿明'}}, self.root)
        self.assertEqual('saved', recorded['saving']['status'])
        self.assertEqual(['creative', 'learning'], kb.state(self.root)['modules'])
        self.assertNotIn('life', kb.state(self.root).get('domain_started', {}))
        self.assertEqual('work', kb.state(self.root)['fields']['name']['domain'])
        answer_id = kb.state(self.root)['answers'][-1]
        self.assertTrue((self.vault / '工作/资料/建档' / f'{answer_id}.md').is_file())
        self.assertFalse((self.vault / '生活/资料/建档' / f'{answer_id}.md').exists())
        self.assertIn('阿明', (self.vault / kb.PROFILE).read_text(encoding='utf-8'))

    def test_legacy_creative_correction_replaces_one_current_profile_fact(self):
        self.enable()
        old_answer_id = 'legacy-answer'
        old_answer_dir = kb.home(self.root) / 'answers' / old_answer_id
        old_answer_dir.mkdir(parents=True)
        old_payload = {'answer': '以前主要做解说。', 'fields': {'creative.direction': '游戏解说'}}
        write_json(old_answer_dir / 'answer.json', {**old_payload, 'at': '2026-01-01T00:00:00Z'})
        legacy_raw = self.vault / '素材/个人建档' / f'{old_answer_id}.md'
        legacy_raw.parent.mkdir(parents=True)
        legacy_raw.write_text('# 建档原始回答\n\n以前主要做解说。\n', encoding='utf-8')
        profile = self.vault / kb.PROFILE
        profile.write_text(
            '# 个人基本资料\n人工备注：周末保留给家人。\n\n'
            '<!-- cy-profile:creative.direction:start -->\n## 内容方向\n\n游戏解说\n\n'
            '来源：[用户回答](../../素材/个人建档/legacy-answer.md)；记录于 2026-01-01。\n'
            '<!-- cy-profile:creative.direction:end -->\n\n'
            '另一条人工备注：保留。\n', encoding='utf-8')
        value = kb.state(self.root)
        value['modules'] = ['creative', 'learning']
        value['fields'] = {'creative.direction': {'value': '游戏解说', 'answer': old_answer_id,
            'at': '2026-01-01T00:00:00Z', 'answer_target': f'素材/个人建档/{old_answer_id}.md'}}
        value['answers'] = [old_answer_id]
        value['profile_sha256'] = digest(profile)
        kb.save(value, self.root)
        old_answer_bytes = (old_answer_dir / 'answer.json').read_bytes()

        result = kb.answer({'answer': '现在主要做战术教学。',
            'fields': {'creative.direction': '战术教学'}}, self.root)
        self.assertEqual('saved', result['saving']['status'])
        state = kb.state(self.root)
        self.assertNotIn('creative.direction', state['fields'])
        self.assertEqual('战术教学', state['fields']['work.direction']['value'])
        text = profile.read_text(encoding='utf-8')
        self.assertNotIn('creative.direction', text)
        self.assertNotIn('游戏解说', text)
        self.assertEqual(1, text.count('战术教学'))
        self.assertIn('周末保留给家人', text)
        self.assertIn('另一条人工备注：保留。', text)
        self.assertEqual(old_answer_bytes, (old_answer_dir / 'answer.json').read_bytes())

    def test_existing_legacy_page_update_keeps_path_and_hash_but_new_page_is_domain_scoped(self):
        self.enable()
        existing = self.vault / '知识库/主题.md'
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text('# 旧主题\n旧内容。\n', encoding='utf-8')
        old_hash = digest(existing)
        source = self.root / 'updated.md'
        source.write_text('# 旧主题\n更新后的内容。\n', encoding='utf-8')
        record = kb.stage({'task': 'legacy-page-update', 'module': 'work', 'files': [{
            'source': relative(self.root, source), 'target': '知识库/主题.md', 'role': 'knowledge',
            'expected_sha256': old_hash, 'sources': ['user:explicit-correction']}]}, self.root)
        self.assertEqual('知识库/主题.md', record['files'][0]['target'])
        self.assertEqual('saved', kb.apply(record['id'], self.root)['status'])
        self.assertIn('更新后的内容', existing.read_text(encoding='utf-8'))

        new_source = self.root / 'new-topic.md'
        new_source.write_text('# 新主题\n工作中新形成的成果。\n', encoding='utf-8')
        new_record = kb.stage({'task': 'new-domain-page', 'module': 'work', 'files': [{
            'source': relative(self.root, new_source), 'target': '知识库/新主题.md', 'role': 'knowledge',
            'sources': ['user:new-result']}]}, self.root)
        self.assertEqual('工作/资料/新主题.md', new_record['files'][0]['target'])
        self.assertEqual('saved', kb.apply(new_record['id'], self.root)['status'])

    def test_context_searches_related_work_learning_and_legacy_material(self):
        self.enable()
        materials = [
            ('work', '工作/资料/项目/overview.md', '工作复盘：服务边界和用户反馈。'),
            ('learning', '学习/资料/课程/notes.md', '学习笔记：服务边界与练习记录。'),
        ]
        for index, (domain, target, body) in enumerate(materials):
            source = self.root / f'material-{index}.md'
            source.write_text(body, encoding='utf-8')
            record = kb.stage({'task': f'context-{index}', 'module': domain, 'files': [{
                'source': relative(self.root, source), 'target': target, 'role': 'knowledge',
                'sources': ['user:explicit-result']}]}, self.root)
            self.assertEqual('saved', kb.apply(record['id'], self.root)['status'])

        legacy = self.vault / '素材/旧项目/历史结果.md'
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text('旧目录保存的服务边界案例。', encoding='utf-8')
        with (self.vault / 'index.md').open('a', encoding='utf-8') as index:
            index.write('\n[旧目录资料](素材/旧项目/历史结果.md)\n')
        context = kb.context(self.root, query='服务边界')
        self.assertEqual({'work', 'learning', None}, {row['domain'] for row in context['matches']})
        self.assertEqual(3, len(context['matches']))

    def test_direction_cannot_be_closed_all_at_once_and_cli_off_works(self):
        self.enable()
        first = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SKILL_ROOT / 'scripts/brain.py'),
            '--workspace', str(self.root), 'kb', 'module', 'work', '--off'],
            capture_output=True, env={**os.environ, 'CY_UPDATE_CHECK': '0'}, timeout=30)
        self.assertEqual(0, first.returncode, first.stderr.decode('utf-8', 'replace'))
        self.assertNotIn('work', json.loads(first.stdout.decode('utf-8-sig'))['modules'])
        kb.configure(self.root, disable_module='life')
        with self.assertRaisesRegex(ValueError, '至少保留一个'):
            kb.configure(self.root, disable_module='learning')
