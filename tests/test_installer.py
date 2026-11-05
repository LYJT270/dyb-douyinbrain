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
    def test_shared_install_can_be_reused_through_the_claude_junction(self):
        with tempfile.TemporaryDirectory(prefix="dyb-alias-") as temp:
            base = Path(temp).resolve()
            source = base / "source"
            shutil.copytree(SKILL_ROOT, source, ignore=shutil.ignore_patterns(".git", ".trash", ".scratch", "dist", "__pycache__"))
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
                self.assertEqual(0, process.returncode, process.stderr.decode("utf-8", "replace"))
                result = json.loads((base / "state/install-result.json").read_text(encoding="utf-8-sig"))
                self.assertEqual(str(shared), result["skill"])
                self.assertEqual("dependencies_pending", result["status"])
            self.assertEqual(shared.resolve(), alias.resolve())

    def test_install_repeat_and_preserve_modified_install_in_isolation(self):
        with tempfile.TemporaryDirectory(prefix="dyb-install-") as temp:
            base = Path(temp).resolve()
            source = base / "source"
            shutil.copytree(SKILL_ROOT, source, ignore=shutil.ignore_patterns(".git", ".trash", ".scratch", "dist", "__pycache__"))
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
                self.assertEqual(0, process.returncode, process.stderr.decode("utf-8", "replace"))
                result = json.loads((state / "install-result.json").read_text(encoding="utf-8-sig"))
                self.assertEqual("dependencies_pending", result["status"])
                self.assertFalse(result["local_entry_verified"])
                self.assertEqual(str(data / "dyb-douyinbrain"), result["workspace"])
                self.assertIsNone(result["backup"])
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
