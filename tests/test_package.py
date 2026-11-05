from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

import support  # noqa: F401  # must precede douyin_text: sets the runtime path and a guarded default workspace
from support import SKILL_ROOT


def load_packager():
    spec = importlib.util.spec_from_file_location("package_under_test", SKILL_ROOT / "scripts" / "package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackageTests(unittest.TestCase):
    def test_repository_dist_is_allowed_and_never_reenters_next_package(self):
        with tempfile.TemporaryDirectory() as temp:
            copy = Path(temp) / "dyb-douyinbrain"
            shutil.copytree(SKILL_ROOT, copy, ignore=shutil.ignore_patterns(".git", "dist", ".trash", ".scratch", "__pycache__"))
            package = load_packager()
            first = package.build(copy, copy / "dist", "8.0.0")
            Path(first["zip"]).with_suffix(".zip.sha256").write_text("old checksum")
            second = package.build(copy, copy / "dist", "8.0.1")
            with zipfile.ZipFile(second["zip"]) as archive:
                self.assertFalse(any("/dist/" in name or "/.trash/" in name for name in archive.namelist()))
            self.assertEqual(["dyb-douyinbrain-windows-v8.0.1.zip"], [p.name for p in (copy / "dist").iterdir()])
            self.assertTrue(any(Path(p).suffix == ".sha256" for p in second["moved_to_trash"]))

    def test_migration_package_leaves_out_the_test_suite(self):
        with tempfile.TemporaryDirectory() as temp:
            copy = Path(temp) / "dyb-douyinbrain"
            shutil.copytree(SKILL_ROOT, copy, ignore=shutil.ignore_patterns("__pycache__"))
            result = load_packager().build(copy, Path(temp) / "exports", "9.9.9")
            with zipfile.ZipFile(result["zip"]) as archive:
                names = archive.namelist()
                manifest = json.loads(archive.read("dyb-douyinbrain/bundle.json"))
        self.assertIn("dyb-douyinbrain/scripts/brain.py", names)
        self.assertFalse([name for name in names if name.startswith("dyb-douyinbrain/tests/")])
        self.assertFalse([name for name in manifest["file_sha256"] if name.startswith("tests/")])
