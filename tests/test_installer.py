from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_package import load_packager
from support import SKILL_ROOT


@unittest.skipUnless(os.name == "nt", "Windows installer")
class InstallerTests(unittest.TestCase):
    def test_nested_legacy_workspace_stays_at_its_original_path(self):
        with tempfile.TemporaryDirectory(prefix='dyb-nested-migration-') as temp:
            base = Path(temp).resolve()
            old, target, state = base / 'skills/douyin-brain', base / 'skills/dyb-douyinbrain', base / 'state'
            workspace = old / 'workspace'
            for folder in (old / 'scripts', workspace / '.local', workspace / 'runs/prior'):
                folder.mkdir(parents=True, exist_ok=True)
            (old / 'SKILL.md').write_text('original legacy instructions', encoding='utf-8')
            (old / 'scripts/invoke.ps1').write_text('original legacy entry', encoding='utf-8')
            (workspace / '.local/doubao.dpapi').write_bytes(b'synthetic-encrypted-fixture-not-a-key')
            (workspace / 'runs/prior/task.json').write_bytes(b'{"history":"unchanged"}')
            quote = lambda value: "'" + str(value).replace("'", "''") + "'"
            script = '. ' + quote(SKILL_ROOT / 'scripts/migration.ps1') + '\n'
            script += '$plan=@{selected=@{legacy_skills=@(' + quote(old) + ')};workspace=' + quote(workspace) + ';aliases=@()}\n'
            script += 'Register-DybLegacyAliases $plan ' + quote(target) + ' ' + quote(state) + '\n'
            script += '$plan.aliases | ConvertTo-Json -Depth 6'
            process = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script], capture_output=True, timeout=30)
            self.assertEqual(0, process.returncode, process.stderr.decode('utf-8', 'replace') + process.stdout.decode('utf-8', 'replace')[-2500:])
            result = json.loads(process.stdout)
            self.assertTrue(result['workspace_preserved_in_place'])
            self.assertEqual(b'synthetic-encrypted-fixture-not-a-key', (workspace / '.local/doubao.dpapi').read_bytes())
            self.assertEqual(b'{"history":"unchanged"}', (workspace / 'runs/prior/task.json').read_bytes())
            self.assertEqual('original legacy instructions', (Path(result['backup']) / 'SKILL.md').read_text())
            self.assertEqual('original legacy entry', (Path(result['backup']) / 'scripts/invoke.ps1').read_text())
            self.assertIn(str(target / 'scripts/invoke.ps1'), (old / 'scripts/invoke.ps1').read_text(encoding='utf-8-sig'))

    def test_legacy_workspace_key_tasks_and_old_name_survive_automatic_migration(self):
        with tempfile.TemporaryDirectory(prefix='dyb-migration-') as temp:
            base = Path(temp).resolve()
            source = base / 'source'
            shutil.copytree(SKILL_ROOT, source, ignore=shutil.ignore_patterns('.git', '.trash', '.scratch', 'dist', '__pycache__'))
            (source / 'VERSION').write_text('1.3.0')
            load_packager().write_manifest(source, '1.3.0')
            state, legacy_state = base / 'state/dyb-douyinbrain', base / 'state/douyin-brain'
            workspace, skills = base / '已有 工作区', base / 'profile/.agents/skills'
            old = skills / 'douyin-brain'
            for folder in (legacy_state, old, workspace / '.local', workspace / 'runs/prior'):
                folder.mkdir(parents=True)
            (old / 'SKILL.md').write_text('---\nname: douyin-brain\n---\nlegacy local edits', encoding='utf-8')
            (legacy_state / 'settings.json').write_text(json.dumps({'workspace': str(workspace), 'skill_root': str(old)}), encoding='utf-8')
            (workspace / 'config.json').write_text(json.dumps({'chunk_seconds': 123, 'custom_value': 'keep'}), encoding='utf-8')
            (workspace / '.local/doubao.dpapi').write_bytes(b'synthetic-encrypted-fixture-not-a-key')
            (workspace / 'runs/prior/task.json').write_bytes(b'{"history":"unchanged"}')
            subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(workspace / '.venv')], check=True, capture_output=True)
            env = {**os.environ, 'USERPROFILE': str(base / 'profile'), 'LOCALAPPDATA': str(base / 'local'),
                   'DYB_STATE_DIR': str(state), 'DYB_UPDATE_CHECK': '0'}
            env.pop('DYB_WORKSPACE', None)
            env.pop('DSH_AGENTS_HOME', None)
            command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(source / 'scripts/install.ps1'),
                       '-SkillsRoot', str(skills), '-StateDirectory', str(state), '-DataDirectory', str(base / 'data'),
                       '-PythonExecutable', sys.executable, '-SkipDependencies', '-NoApiWindow']
            process = subprocess.run(command, env=env, capture_output=True, timeout=90)
            self.assertEqual(0, process.returncode, process.stderr.decode('utf-8', 'replace'))
            result = json.loads((state / 'install-result.json').read_text(encoding='utf-8-sig'))
            self.assertEqual(str(workspace), result['workspace'])
            self.assertEqual(b'synthetic-encrypted-fixture-not-a-key', (workspace / '.local/doubao.dpapi').read_bytes())
            self.assertEqual(b'{"history":"unchanged"}', (workspace / 'runs/prior/task.json').read_bytes())
            self.assertEqual('keep', json.loads((workspace / 'config.json').read_text())['custom_value'])
            self.assertTrue(Path(result['migration']['backup']).is_dir())
            self.assertIn('legacy local edits', (Path(result['migration']['aliases'][0]['backup']) / 'SKILL.md').read_text())
            self.assertTrue((old / 'scripts/invoke.ps1').read_bytes().startswith(b'\xef\xbb\xbf'))
            text_file = workspace / '原文.txt'
            text_file.write_text('已有文稿保留。', encoding='utf-8')
            invoked = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                str(old / 'scripts/invoke.ps1'), 'plan-text', str(text_file)], env=env, capture_output=True, timeout=30)
            planned = json.loads(invoked.stdout)
            self.assertEqual('text', planned['input_kind'])
            self.assertTrue((workspace / 'runs' / planned['id'] / 'task.json').is_file())

    def test_multiple_workspaces_require_one_choice_before_any_install_mutation(self):
        with tempfile.TemporaryDirectory(prefix='dyb-choice-') as temp:
            base = Path(temp).resolve()
            source = base / 'source'
            shutil.copytree(SKILL_ROOT, source, ignore=shutil.ignore_patterns('.git', '.trash', '.scratch', 'dist', '__pycache__'))
            (source / 'VERSION').write_text('1.3.0')
            load_packager().write_manifest(source, '1.3.0')
            state, legacy = base / 'state/dyb-douyinbrain', base / 'state/douyin-brain'
            for folder, workspace in ((state, base / 'first'), (legacy, base / 'second')):
                folder.mkdir(parents=True)
                workspace.mkdir()
                (folder / 'settings.json').write_text(json.dumps({'workspace': str(workspace)}), encoding='utf-8')
            env = {**os.environ, 'USERPROFILE': str(base / 'profile'), 'LOCALAPPDATA': str(base / 'local'), 'DYB_STATE_DIR': str(state)}
            env.pop('DSH_AGENTS_HOME', None)
            process = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                str(source / 'scripts/install.ps1'), '-StateDirectory', str(state), '-SkillsRoot', str(base / 'skills'),
                '-NoApiWindow'], env=env, capture_output=True, timeout=30)
            self.assertEqual(2, process.returncode, process.stderr.decode('utf-8', 'replace'))
            result = json.loads((state / 'install-result.json').read_text(encoding='utf-8-sig'))
            self.assertEqual('needs_workspace_choice', result['status'])
            self.assertEqual(2, len(result['candidates']))
            self.assertFalse((base / 'skills').exists())
            self.assertEqual(str(base / 'first'), json.loads((state / 'settings.json').read_text())['workspace'])

    def test_shared_install_can_be_reused_through_the_claude_junction(self):
        with tempfile.TemporaryDirectory(prefix="dyb-alias-") as temp:
            base = Path(temp).resolve()
            source = base / "source"
            shutil.copytree(SKILL_ROOT, source, ignore=shutil.ignore_patterns(".git", ".trash", ".scratch", "dist", "__pycache__"))
            (source / 'VERSION').write_text('1.0.0')
            load_packager().write_manifest(source, "1.0.0")
            env = {**os.environ, "USERPROFILE": str(base / "profile"), "DYB_STATE_DIR": str(base / "state")}
            env.pop("DYB_WORKSPACE", None)
            common = ["-StateDirectory", str(base / "state"), "-DataDirectory", str(base / "data"),
                      "-PythonExecutable", sys.executable, "-SkipDependencies", "-NoApiWindow"]
            alias = base / "profile/.claude/skills/dyb-douyinbrain"
            shared = base / "profile/.agents/skills/dyb-douyinbrain"
            for script, agent in ((source / "scripts/install.ps1", "all"),
                                  (source / "scripts/install.ps1", "claude"),
                                  (alias / "scripts/install.ps1", "claude")):
                command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Agent", agent, *common]
                process = subprocess.run(command, env=env, capture_output=True, timeout=90)
                self.assertEqual(0, process.returncode, process.stderr.decode("utf-8", "replace") + process.stdout.decode('utf-8', 'replace')[-2500:])
                result = json.loads((base / "state/install-result.json").read_text(encoding="utf-8-sig"))
                self.assertEqual(str(shared), result["skill"])
                self.assertEqual("dependencies_pending", result["status"])
            self.assertEqual(shared.resolve(), alias.resolve())

    def test_install_repeat_and_preserve_modified_install_in_isolation(self):
        with tempfile.TemporaryDirectory(prefix="dyb-install-") as temp:
            base = Path(temp).resolve()
            source = base / "source"
            shutil.copytree(SKILL_ROOT, source, ignore=shutil.ignore_patterns(".git", ".trash", ".scratch", "dist", "__pycache__"))
            (source / 'VERSION').write_text('1.0.0')
            load_packager().write_manifest(source, "1.0.0")
            state, skills, data = base / "state", base / "skills", base / "中文 data"
            env = {**os.environ, "USERPROFILE": str(base / "profile"), "DYB_STATE_DIR": str(state)}
            env.pop("DYB_WORKSPACE", None)
            command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                       str(source / "scripts/install.ps1"), "-SkillsRoot", str(skills),
                       "-StateDirectory", str(state), "-DataDirectory", str(data),
                       "-PythonExecutable", sys.executable, "-SkipDependencies", "-NoApiWindow"]
            for attempt in range(2):
                process = subprocess.run(command, env=env, capture_output=True, timeout=90)
                self.assertEqual(0, process.returncode, process.stderr.decode("utf-8", "replace") + process.stdout.decode('utf-8', 'replace')[-2500:])
                result = json.loads((state / "install-result.json").read_text(encoding="utf-8-sig"))
                self.assertEqual("dependencies_pending", result["status"])
                self.assertFalse(result["local_entry_verified"])
                self.assertEqual(str(data / "dyb-douyinbrain"), result["workspace"])
                self.assertIsNone(result["backup"])
                self.assertTrue(result['onboarding']['due'])
                self.assertEqual('welcome', result['welcome_command'])
                cfg = json.loads((Path(result['workspace']) / 'config.json').read_text(encoding='utf-8-sig'))
                self.assertFalse(cfg.get('vault_root'), 'default installation must not create a knowledge library')
                self.assertFalse((data / 'dyb-douyinbrain-知识库').exists())
                self.assertFalse((Path(result['workspace']) / '.local/onboarding.json').exists(),
                                 'terminal output is not an Agent presentation in chat')
            installed = skills / "dyb-douyinbrain"
            original = (installed / "SKILL.md").read_text(encoding="utf-8")
            (installed / "SKILL.md").write_text(original + "\nUser edit\n", encoding="utf-8")
            process = subprocess.run(command, env=env, capture_output=True, timeout=90)
            self.assertEqual(0, process.returncode, process.stderr.decode("utf-8", "replace"))
            result = json.loads((state / "install-result.json").read_text(encoding="utf-8-sig"))
            backup = Path(result["backup"])
            self.assertTrue(backup.is_relative_to(base))
            self.assertIn("User edit", (backup / "SKILL.md").read_text(encoding="utf-8"))
            self.assertEqual(original, (installed / "SKILL.md").read_text(encoding="utf-8"))
            self.assertFalse(list(base.rglob("*.dpapi")))
            self.assertFalse((base / "profile/.agents").exists())

    def test_shared_and_application_specific_discovery_paths(self):
        # Exercise actual PowerShell path selection without writing to any application.
        script = ". '" + str(SKILL_ROOT / "scripts/paths.ps1").replace("'", "''") + "'; "
        script += "$items=@{}; foreach($name in @('auto','shared','deepseek','codex','gemini','cursor','opencode','claude')) {$items[$name]=Get-DybSkillsRoot $name ''}; $items|ConvertTo-Json -Compress"
        with tempfile.TemporaryDirectory() as name:
            env = {**os.environ, "USERPROFILE": name}
            env.pop("DSH_AGENTS_HOME", None)
            process = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], env=env, capture_output=True, check=True)
            values = json.loads(process.stdout)
            for agent, target in values.items():
                expected = ".claude" if agent == "claude" else ".agents"
                self.assertEqual(str(Path(name) / expected / "skills"), target)
