from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from support import WorkspaceCase
import test_suite_install as suite_tests
from douyin_text import personal_vault as kb, setup
from douyin_text.common import digest, read_json, write_json
from douyin_text.identity import env_value, state_root


class NamingCompatibilityTests(WorkspaceCase):
    def test_old_environment_and_registered_state_are_reused_but_new_overrides_win(self):
        with patch.dict(os.environ, {'LOCALAPPDATA': str(self.parent), 'DYB_WORKSPACE': str(self.root)}, clear=True):
            old = self.parent / 'dyb-douyinbrain'
            old.mkdir()
            (old / 'settings.json').write_text('{}')
            self.assertEqual(old, state_root())
            self.assertEqual(str(self.root), env_value('WORKSPACE'))
            os.environ['CY_WORKSPACE'] = str(self.parent / 'preferred')
            self.assertEqual(str(self.parent / 'preferred'), env_value('WORKSPACE'))
            os.environ['CY_STATE_DIR'] = str(self.parent / 'explicit')
            self.assertEqual(self.parent / 'explicit', state_root())

    def test_legacy_hooks_profile_and_collection_survive_registration_and_correction(self):
        vault = self.parent / 'vault'
        kb.enable(self.root, vault=vault, create=True, evidence='帮我配置个人知识库')
        kb.answer({'answer': '叫我阿林，我做解说。', 'fields': {'name': '阿林', 'background': '游戏解说'}}, self.root)
        profile = vault / kb.PROFILE
        # Persist an earlier branding layout, including its actual integrity records.
        for path in (profile, vault / 'index.md', self.root / 'AGENTS.md'):
            path.write_text(path.read_text(encoding='utf-8').replace('cy-', 'dyb-'), encoding='utf-8')
        marker = read_json(vault / '.cy-vault.json')
        marker['product'] = 'dyb-vault'
        write_json(vault / '.dyb-vault.json', marker)
        (vault / '.cy-vault.json').unlink()
        (vault / '.cy-vault-runtime').rename(vault / '.dyb-vault-runtime')
        state = kb.state(self.root)
        state['profile_sha256'] = digest(profile)
        kb.save(state, self.root)
        originals = {p: p.read_bytes() for p in (vault / '素材/个人建档').glob('*.md')}
        with patch.dict(os.environ, {'CY_STATE_DIR': str(self.parent / 'state')}):
            setup.initialize(self.root, register=True)
        self.assertTrue(kb.context(self.root)['hook']['block_matches'])
        self.assertEqual(1, (self.root / 'AGENTS.md').read_text(encoding='utf-8').count(kb.HOOK_START))
        result = kb.answer({'answer': '更正，我现在做剪辑。', 'fields': {'background': '视频剪辑'}}, self.root)
        self.assertEqual('saved', result['saving']['status'])
        text = profile.read_text(encoding='utf-8')
        self.assertIn('阿林', text)
        self.assertIn('视频剪辑', text)
        self.assertNotIn('游戏解说', text)
        self.assertTrue(all(p.read_bytes() == data for p, data in originals.items()))
        self.assertFalse((vault / '.cy-vault-runtime').exists(), 'reuse one catalog and lock')


@unittest.skipUnless(os.name == 'nt', 'Windows rename migration')
class BrandInstallTests(unittest.TestCase):
    # Share setup helpers without inheriting and rerunning the whole suite.
    setUp = suite_tests.SuiteInstallTests.setUp
    source = suite_tests.SuiteInstallTests.source
    install = suite_tests.SuiteInstallTests.install
    invoke = suite_tests.SuiteInstallTests.invoke
    snapshot = suite_tests.SuiteInstallTests.snapshot

    def legacy(self):
        self.workspace.mkdir(parents=True)
        self.state.mkdir(parents=True)
        names = ['dyb-douyinbrain', 'dyb-transcribe', 'dyb-analyze', 'dyb-download', 'dyb-write', 'dyb-knowledge']
        for name in names:
            folder = self.skills / name
            folder.mkdir(parents=True)
            (folder / 'SKILL.md').write_text('old ' + name, encoding='utf-8')
            (folder / 'user-notes.txt').write_text('keep custom additions', encoding='utf-8')
            marker = 'bundle.json' if name == 'dyb-douyinbrain' else '.dyb-member.json'
            write_json(folder / marker, {'name': name, 'product': 'dyb-douyinbrain', 'version': '1.5.0'})
        write_json(self.state / 'settings.json', {'workspace': str(self.workspace), 'skill_root': str(self.skills / names[0])})
        (self.workspace / 'AGENTS.md').write_text('User rules\n<!-- dyb-douyinbrain:execution:start -->\nold entry\n<!-- dyb-douyinbrain:execution:end -->\n', encoding='utf-8')
        write_json(self.workspace / 'config.json', {'custom_setting': 'keep'})
        credentials = self.workspace / '.local/doubao.dpapi'
        credentials.parent.mkdir()
        credentials.write_bytes(b'synthetic-encrypted-fixture-not-a-key')
        return names

    def test_every_existing_alias_forwards_to_new_suite_and_repeat_install_stays_usable(self):
        names = self.legacy()
        credential = (self.workspace / '.local/doubao.dpapi').read_bytes()
        source = self.source('1.6.0')
        for attempt in range(2):
            result = self.install(source)
            self.assertEqual(6, len(result['migration']['aliases']))
            for name in names[1:]:
                shown = self.invoke(name, 'guide')
                self.assertEqual(name.replace('dyb-', 'cy-'), shown['skill'])
                self.assertEqual(str(self.skills / 'cy-charmyee'), shown['shared_root'])
        self.assertEqual(credential, (self.workspace / '.local/doubao.dpapi').read_bytes())
        self.assertEqual('keep', read_json(self.workspace / 'config.json')['custom_setting'])
        body = (self.workspace / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertIn('User rules', body)
        self.assertNotIn('dyb-douyinbrain:execution', body)
        self.assertEqual(1, body.count('<!-- cy-charmyee:execution:start -->'))

    def test_locked_late_legacy_alias_restores_earlier_aliases_and_registration(self):
        self.legacy()
        before = self.snapshot()
        settings = (self.state / 'settings.json').read_bytes()
        rules = (self.workspace / 'AGENTS.md').read_bytes()
        config = (self.workspace / 'config.json').read_bytes()
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateFileW(str(self.skills / 'dyb-write/SKILL.md'), 0x80000000, 1, None, 3, 0x80, None)
        self.assertNotEqual(ctypes.c_void_p(-1).value, handle)
        try:
            result = self.install(self.source('1.6.0'), expected=1)
            self.assertEqual('rolled_back', result['suite_rollback']['status'])
            self.assertEqual(before, self.snapshot())
            self.assertEqual(settings, (self.state / 'settings.json').read_bytes())
            self.assertEqual(rules, (self.workspace / 'AGENTS.md').read_bytes())
            self.assertEqual(config, (self.workspace / 'config.json').read_bytes())
        finally:
            kernel.CloseHandle(handle)
