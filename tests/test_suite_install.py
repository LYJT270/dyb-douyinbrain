from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from support import SKILL_ROOT
import package
import suite_manifest
import updates


@unittest.skipUnless(os.name == 'nt', 'Windows suite installation')
class SuiteInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dyb-suite-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.skills, self.state, self.workspace = [self.base / x for x in ('skills', 'state', '工作区')]
        self.env = {**os.environ, 'USERPROFILE': str(self.base / 'profile'),
                    'LOCALAPPDATA': str(self.base / 'local'), 'DYB_STATE_DIR': str(self.state), 'DYB_UPDATE_CHECK': '0'}
        for key in ('DYB_WORKSPACE', 'DSH_AGENTS_HOME', 'DOUBAO_ASR_API_KEY', 'DOUBAO_ASR_APP_ID', 'DOUBAO_ASR_ACCESS_KEY'):
            self.env.pop(key, None)

    def source(self, version='1.3.1', broken_setup=False):
        source = self.base / ('source-' + version)
        shutil.copytree(SKILL_ROOT, source, ignore=shutil.ignore_patterns('.git', '.scratch', '.trash', 'dist', 'tests', '__pycache__'))
        (source / 'VERSION').write_text(version, encoding='utf-8')
        if broken_setup:
            script = source / 'scripts/setup.ps1'
            text = script.read_text(encoding='utf-8-sig')
            text = text.replace("$ErrorActionPreference = 'Stop'", "$ErrorActionPreference = 'Stop'\nthrow 'isolated setup failure before dependency work'", 1)
            script.write_text(text, encoding='utf-8-sig')
        package.write_manifest(source, version)
        return source

    def install(self, source, expected=0):
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                 str(source / 'scripts/install.ps1'), '-Agent', 'custom', '-SkillsRoot', str(self.skills),
                                 '-StateDirectory', str(self.state), '-Workspace', str(self.workspace),
                                 '-PythonExecutable', sys.executable, '-SkipDependencies', '-NoApiWindow'],
                                env=self.env, capture_output=True, timeout=90)
        receipt = json.loads((self.state / 'install-result.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(expected, result.returncode, receipt.get('error', result.stderr.decode('utf-8', 'replace')))
        return receipt

    def invoke(self, name, *args, expected=0):
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                 str(self.skills / name / 'scripts/invoke.ps1'), *args],
                                env=self.env, capture_output=True, timeout=30)
        self.assertEqual(expected, result.returncode, result.stdout.decode('utf-8', 'replace') + result.stderr.decode('utf-8', 'replace'))
        return json.loads(result.stdout.decode('utf-8-sig'))

    def snapshot(self):
        return {str(p.relative_to(self.skills)): p.read_bytes() for p in self.skills.rglob('*') if p.is_file()}

    def test_six_physical_entries_and_shared_first_use_without_speech_key(self):
        receipt = self.install(self.source())
        self.assertEqual(6, len(receipt['suite_members']))
        self.assertTrue(receipt['suite_verified'])
        check = suite_manifest.check_installed(self.skills / 'dyb-douyinbrain')
        self.assertEqual(5, len(check['members']))
        entry_files = list(self.skills.rglob('SKILL.md'))
        self.assertEqual(6, len(entry_files), 'recursive discovery must see each entrypoint exactly once')
        self.assertFalse((self.skills / 'dyb-douyinbrain/skills').exists())
        for row in check['members']:
            result = self.invoke(row['name'], 'guide')
            self.assertEqual('ready', result['status'])
            self.assertEqual('installed', result['layout'])
            self.assertEqual(str(self.skills / 'dyb-douyinbrain'), result['shared_root'])
        subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(self.workspace / '.venv')], check=True, capture_output=True)
        first = self.invoke('dyb-download', 'welcome')
        self.assertEqual('needs_speech_credentials', first['readiness']['new_speech'])
        self.assertEqual('available_to_agent', first['readiness']['existing_text'])
        self.assertTrue(first['onboarding']['due'])
        self.invoke('dyb-transcribe', 'welcome', '--acknowledge')
        self.assertFalse(self.invoke('dyb-write', 'welcome')['onboarding']['due'])
        self.assertFalse((self.workspace / '.local/doubao.dpapi').exists())

    def test_unowned_child_directory_is_preserved_before_any_program_swap(self):
        existing = self.skills / 'dyb-download/SKILL.md'
        existing.parent.mkdir(parents=True)
        existing.write_text('User-owned independent skill', encoding='utf-8')
        receipt = self.install(self.source(), expected=1)
        self.assertIn('同名目录', receipt['error'])
        self.assertEqual('User-owned independent skill', existing.read_text())
        self.assertFalse((self.skills / 'dyb-douyinbrain').exists())

    def test_failed_new_setup_restores_all_entries_and_user_edits(self):
        self.install(self.source())
        custom = self.skills / 'dyb-write/user-notes.txt'
        custom.write_text('Keep this local addition.', encoding='utf-8')
        preserved = self.snapshot()
        config = (self.workspace / 'config.json').read_bytes()
        receipt = self.install(self.source('1.3.2', broken_setup=True), expected=1)
        self.assertEqual('rolled_back', receipt['suite_rollback']['status'], json.dumps(receipt, ensure_ascii=False))
        self.assertEqual(preserved, self.snapshot())
        self.assertEqual(config, (self.workspace / 'config.json').read_bytes())
        self.assertEqual(6, len([x for x in receipt['suite_rollback']['entries'] if Path(x['failed_backup']).is_dir()]))
        self.assertFalse((self.skills / '.dyb-suite-installing.json').exists())

    def test_locked_child_rolls_back_the_already_swapped_earlier_members(self):
        self.install(self.source())
        preserved = self.snapshot()
        candidate = self.source('1.3.2')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateFileW(str(self.skills / 'dyb-download/SKILL.md'), 0x80000000, 1, None, 3, 0x80, None)
        self.assertNotEqual(ctypes.c_void_p(-1).value, handle)
        try:
            receipt = self.install(candidate, expected=1)
        finally:
            kernel.CloseHandle(handle)
        self.assertEqual('rolled_back', receipt['suite_rollback']['status'], json.dumps(receipt, ensure_ascii=False))
        self.assertEqual(preserved, self.snapshot())
        # The same version can be retried after the actual file lock is released.
        self.install(candidate)
        self.assertEqual('1.3.2', self.invoke('dyb-download', 'guide')['version'])

    def test_updater_recognizes_installer_suite_rollback_without_repeating_moves(self):
        self.install(self.source())
        preserved = self.snapshot()
        candidate = self.source('1.3.2', broken_setup=True)
        built = package.build(candidate, self.base / 'package', '1.3.2')
        archive = Path(built['zip'])
        archive.with_suffix('.zip.sha256').write_text(built['sha256'] + '  ' + archive.name)
        info = {'version': '1.3.2', 'tag': 'v1.3.2', 'url': 'https://github.com/ScarfaceAI/dyb-douyinbrain/releases/tag/v1.3.2'}
        def download(_, directory):
            directory.mkdir(parents=True)
            return archive
        with patch.dict(os.environ, self.env), patch.object(updates, 'latest_release', return_value=info), \
                patch.object(updates, 'download_release', side_effect=download):
            result = updates.apply_update(self.skills / 'dyb-douyinbrain', self.state, self.workspace)
        self.assertEqual('failed', result['status'])
        self.assertTrue(result['program_restored'])
        self.assertEqual('rolled_back', result['suite_rollback'])
        self.assertEqual(preserved, self.snapshot())

    def test_child_version_mismatch_stops_commands_until_suite_repair(self):
        self.install(self.source())
        marker_file = self.skills / 'dyb-analyze/.dyb-member.json'
        marker = json.loads(marker_file.read_text(encoding='utf-8-sig'))
        marker['version'] = '0.0.0'
        marker_file.write_text(json.dumps(marker), encoding='utf-8')
        result = self.invoke('dyb-write', 'guide', expected=1)
        self.assertEqual('error', result['status'])
        self.assertIn('版本不一致', result['error'])
