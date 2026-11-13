"""A moved library must still recognize material represented by historical receipts."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote

from support import WorkspaceCase
from douyin_text import personal_vault as kb, vault_migration
from douyin_text.common import digest


class MigrationHistoryTests(WorkspaceCase):
    def test_reclassification_preserves_receipt_and_reuses_original_material(self):
        library = self.parent / 'library'
        kb.enable(self.root, vault=library, create=True, scope='workspace', host='codex',
                  evidence='This synthetic user opted into the three-domain library.')
        (self.root / 'original.md').write_text('合成资料：项目回顾。\n\n[方法](../方法/主题.md)\n', encoding='utf-8')
        (self.root / 'topic.md').write_text('合成资料：项目回顾的具体方法。\n', encoding='utf-8')
        manifest = {
            'task': 'synthetic-source', 'module': 'life', 'title': '项目回顾资料',
            'files': [
                {'source': 'original.md', 'target': '生活/资料/原文.md', 'role': 'source',
                 'sources': ['fixture:user']},
                {'source': 'topic.md', 'target': '生活/方法/主题.md', 'role': 'knowledge',
                 'sources': ['生活/资料/原文.md']},
            ],
        }
        transaction = kb.stage(manifest, self.root)
        saved = kb.apply(transaction['id'], self.root)
        self.assertEqual('saved', saved['status'])
        receipt = kb.home(self.root) / 'transactions' / saved['id'] / 'transaction.json'
        historical_bytes = receipt.read_bytes()
        mapping = self.root / 'migration.json'
        mapping.write_text(json.dumps({'files': [
            {'source': '生活/资料/原文.md', 'target': '学习/资料/原文.md'},
            {'source': '生活/方法/主题.md', 'target': '工作/方法/主题.md'},
        ]}, ensure_ascii=False), encoding='utf-8')
        preview = vault_migration.plan(self.root, mapping)
        result = vault_migration.apply(self.root, preview['id'], 'Apply this exact synthetic preview.')
        self.assertEqual('complete', result['status'], result)
        self.assertTrue((library / '学习/资料/原文.md').is_file())
        self.assertFalse((library / '生活/资料/原文.md').exists())
        # A rewritten relative link changes the current file's hash; it must not
        # invalidate the original evidence or create another copy of the source.
        current_source = library / '学习/资料/原文.md'
        destination = re.search(r'\[方法\]\(([^)]+)\)', current_source.read_text(encoding='utf-8'))
        self.assertIsNotNone(destination)
        self.assertEqual((library / '工作/方法/主题.md').resolve(),
                         (current_source.parent / unquote(destination.group(1))).resolve())
        reused = kb.stage({**manifest, 'task': 'same-material-again'}, self.root)
        self.assertTrue(reused.get('reused'), reused)
        self.assertEqual(saved['id'], reused['id'])
        self.assertEqual(historical_bytes, receipt.read_bytes())
        context = kb.context(self.root, query='项目 回顾')
        self.assertIn((library / '学习/资料/原文.md').resolve(),
                      {Path(item['file']).resolve() for item in context['matches']})
        self.assertFalse(any(p.name == '原文.md' for p in (library / '生活').rglob('*')))
        state = kb.state(self.root)
        state['write_mode'] = 'target_rules'
        kb.save(state, self.root)
        verified = kb.apply(saved['id'], self.root)
        self.assertEqual('saved', verified['status'], verified)
        self.assertTrue(verified['current_verified'])
        self.assertEqual(historical_bytes, receipt.read_bytes())

    def test_profile_move_is_readable_from_second_workspace_and_next_answer_saves(self):
        library = self.parent / 'library'
        kb.enable(self.root, vault=library, create=True, scope='workspace', host='codex',
                  evidence='Synthetic user opted into the library.')
        first_answer = {'answer': '虚构用户叫小陈，正在学习 Python。',
                        'fields': {'name': '小陈', 'learning.goal': '学习 Python'}}
        initial = kb.answer(first_answer, self.root)
        self.assertEqual('saved', initial['saving']['status'])
        historical = kb.home(self.root) / 'transactions' / initial['saving']['id'] / 'transaction.json'
        history_bytes = historical.read_bytes()
        other = self.parent / 'second-workspace'
        other.mkdir()
        kb.enable(other, vault=library, scope='workspace', host='codex',
                  evidence='The same synthetic user connects this workspace.')
        mappings = []
        new_profile = '生活/个人档案/归档/人物.md'
        for row in initial['saving']['files']:
            mappings.append({'source': row['target'],
                             'target': new_profile if row['role'] == 'profile' else row['target']})
        mapping = self.root / 'profile-migration.json'
        mapping.write_text(json.dumps({'files': mappings}, ensure_ascii=False), encoding='utf-8')
        preview = vault_migration.plan(self.root, mapping)
        moved = vault_migration.apply(self.root, preview['id'], 'Confirm the synthetic profile move.')
        self.assertEqual('complete', moved['status'], moved)
        self.assertIn('小陈', kb.context(other, query='Python')['profile']['text'])
        self.assertEqual(digest(library / new_profile), kb.state(self.root)['profile_sha256'])
        repeated = kb.answer(first_answer, self.root)
        self.assertTrue(repeated['saving'].get('reused'), repeated)
        self.assertEqual(initial['saving']['id'], repeated['saving']['id'])
        self.assertEqual(history_bytes, historical.read_bytes())
        later = kb.answer({'answer': '虚构用户希望每周做一个小练习。',
                           'domain': 'learning', 'topic': '学习方式',
                           'fields': {'learning.method': '每周做一个小练习'}}, self.root)
        self.assertEqual('saved', later['saving']['status'], later)
        self.assertIn('每周做一个小练习', (library / new_profile).read_text(encoding='utf-8'))
        self.assertEqual(history_bytes, historical.read_bytes())
