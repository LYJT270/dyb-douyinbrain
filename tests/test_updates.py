from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import subprocess
import ssl
from types import SimpleNamespace
import tempfile
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.error import URLError
import zipfile

from support import SKILL_ROOT

sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import package
import release
import release_assets
import updates


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cy-update-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.skill = self.base / "profile/skills/cy-charmyee"
        self.state = self.base / "state"
        self.workspace = self.base / "中文 workspace"
        self.skill.mkdir(parents=True)
        self.workspace.mkdir()
        (self.skill / "VERSION").write_text("1.0.1\n")
        (self.skill / "SKILL.md").write_text("My local customization", encoding="utf-8")
        updates.save_json(self.skill / "bundle.json", {"name": "cy-charmyee", "version": "1.0.1"})
        updates.save_json(self.state / "settings.json", {"workspace": str(self.workspace), "skill_root": str(self.skill)})
        (self.workspace / "config.json").write_text('{"user_setting": true}')
        (self.workspace / "fake-credential.dpapi").write_bytes(b"isolated dummy fixture, not a credential")
        (self.workspace / "saved-task.txt").write_text("Preserve this task.")
        self.preserved = {path.name: path.read_bytes() for path in self.workspace.iterdir()}
        self.info = {"version": "1.1.0", "tag": "v1.1.0", "url": release_assets.REPOSITORY_URL + "/releases/tag/v1.1.0",
                     "zip_name": "cy-charmyee-windows-v1.1.0.zip"}
        self.environment = patch.dict("os.environ", {"CY_UPDATE_CHECK": "1"})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def make_archive(self):
        source = self.base / "release-source"
        (source / "scripts").mkdir(parents=True, exist_ok=True)
        for name, content in {"VERSION": "1.1.0\n", "SKILL.md": "new official instructions",
                              "INSTALL.md": "install", "LICENSE": "MIT", "scripts/brain.py": "# entry",
                              "scripts/install.ps1": "# installer"}.items():
            (source / name).write_text(content, encoding="utf-8")
        built = package.build(source, self.base / "downloads", "1.1.0")
        archive = Path(built["zip"])
        archive.with_suffix(".zip.sha256").write_text(built["sha256"] + "  " + archive.name + "\n")
        return archive

    def download_fixture(self, info, directory):
        archive = self.make_archive()
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / archive.name
        shutil.copy2(archive, target)
        shutil.copy2(archive.with_suffix(".zip.sha256"), target.with_suffix(".zip.sha256"))
        return target

    def install_fixture(self, source, skill, state, workspace, log):
        backup = skill.parent.parent / ".trash/2026-11-05_cy-charmyee_test"
        backup.parent.mkdir(parents=True)
        skill.rename(backup)
        shutil.copytree(source, skill)
        return {"status": "awaiting_api", "exit_code": 0, "local_entry_verified": True,
                "version": "1.1.0", "skill": str(skill), "workspace": str(workspace), "backup": str(backup)}

    def test_notice_is_once_per_chat_while_release_cache_is_shared(self):
        with patch.object(updates, "latest_release", return_value=self.info) as fetch, patch.object(updates.time, "time", return_value=100000):
            first = updates.check_updates(self.skill, self.state, notify=True, session_id="chat-a")
            second = updates.check_updates(self.skill, self.state, notify=True, session_id="chat-a")
            other = updates.check_updates(self.skill, self.state, notify=True, session_id="chat-b")
            self.assertTrue(first["should_notify"])
            self.assertFalse(second["should_notify"])
            self.assertTrue(other["should_notify"])
            self.assertTrue(other["cached"])
            self.assertEqual(1, fetch.call_count)
        with patch.object(updates, "latest_release", return_value=self.info) as fetch, patch.object(updates.time, "time", return_value=200000):
            self.assertFalse(updates.check_updates(self.skill, self.state, notify=True, session_id="chat-a")["should_notify"])
            self.assertTrue(updates.check_updates(self.skill, self.state, notify=True, session_id="chat-c")["should_notify"])
            fetch.assert_called_once()

    def test_unknown_chat_identity_leaves_deduplication_to_agent(self):
        with patch.object(updates, "latest_release", return_value=self.info):
            for _ in range(2):
                result = updates.check_updates(self.skill, self.state, notify=True, session_id="")
                self.assertTrue(result["should_notify"])
                self.assertTrue(result["agent_deduplicate"])
        self.assertNotIn("session_notices", updates.read_cache(self.state / "update-cache.json"))

    def test_new_release_can_notify_again_in_same_chat_and_caught_up_install_stops_notice(self):
        with patch.object(updates, "latest_release", return_value=self.info):
            self.assertTrue(updates.check_updates(self.skill, self.state, notify=True, session_id="chat")["should_notify"])
        newer = {**self.info, "version": "1.2.0"}
        with patch.object(updates, "latest_release", return_value=newer):
            self.assertTrue(updates.check_updates(self.skill, self.state, force=True, notify=True, session_id="chat")["should_notify"])
            (self.skill / "VERSION").write_text("1.2.0\n")
            result = updates.check_updates(self.skill, self.state, notify=True, session_id="new-chat")
            self.assertEqual("up_to_date", result["status"])
            self.assertFalse(result["should_notify"])

    def test_confirmed_new_release_still_notifies_in_new_chat_when_refresh_is_offline(self):
        with patch.object(updates, "latest_release", return_value=self.info), patch.object(updates.time, "time", return_value=100000):
            updates.check_updates(self.skill, self.state, notify=True, session_id="old-chat")
        with patch.object(updates, "latest_release", side_effect=URLError("offline")) as fetch, \
                patch.object(updates.time, "time", return_value=200000):
            result = updates.check_updates(self.skill, self.state, notify=True, session_id="new-chat")
            repeat = updates.check_updates(self.skill, self.state, notify=True, session_id="new-chat")
            self.assertTrue(result["should_notify"])
            self.assertTrue(result["stale"])
            self.assertIn("offline", result["check_error"])
            self.assertFalse(repeat["should_notify"])
            fetch.assert_called_once()

    def test_host_thread_is_used_without_exposing_it_in_cache(self):
        with patch.dict("os.environ", {"CY_SESSION_ID": "", "CODEX_THREAD_ID": "private-chat-id"}), \
                patch.object(updates, "latest_release", return_value=self.info):
            self.assertTrue(updates.check_updates(self.skill, self.state, notify=True)["should_notify"])
            self.assertFalse(updates.check_updates(self.skill, self.state, notify=True)["should_notify"])
        self.assertNotIn("private-chat-id", (self.state / "update-cache.json").read_text())

    def test_parallel_chats_keep_both_notice_claims(self):
        barrier = threading.Barrier(2)
        def fetch():
            barrier.wait(timeout=10)
            return self.info
        with patch.object(updates, "latest_release", side_effect=fetch):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda chat: updates.check_updates(
                    self.skill, self.state, force=True, notify=True, session_id=chat), ["chat-a", "chat-b"]))
        self.assertTrue(all(row["should_notify"] for row in results))
        for chat in ("chat-a", "chat-b"):
            self.assertFalse(updates.check_updates(self.skill, self.state, notify=True, session_id=chat)["should_notify"])

    def test_parallel_commands_in_one_chat_claim_only_one_notice(self):
        barrier = threading.Barrier(2)
        def fetch():
            barrier.wait(timeout=10)
            return self.info
        with patch.object(updates, "latest_release", side_effect=fetch):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: updates.check_updates(
                    self.skill, self.state, force=True, notify=True, session_id="one-chat"), range(2)))
        self.assertEqual(1, sum(row["should_notify"] for row in results))

    def test_legacy_daily_notice_does_not_suppress_new_chat_or_read_only_check(self):
        updates.save_json(self.state / "update-cache.json", {
            "checked_at": 100000, "release": self.info,
            "notified_version": "1.1.0", "notified_at": 100000})
        with patch.object(updates.time, "time", return_value=100001), patch.object(updates, "latest_release") as fetch:
            self.assertTrue(updates.check_updates(self.skill, self.state, session_id="new-chat")["should_notify"])
            self.assertTrue(updates.check_updates(self.skill, self.state, notify=True, session_id="new-chat")["should_notify"])
            self.assertFalse(updates.check_updates(self.skill, self.state, notify=True, session_id="new-chat")["should_notify"])
            fetch.assert_not_called()

    def test_read_only_notice_store_does_not_hide_confirmed_new_release(self):
        updates.save_json(self.state / 'update-cache.json', {
            'checked_at': updates.time.time(), 'release': self.info})
        original_mkdir = Path.mkdir
        def readonly_notices(path, *args, **kwargs):
            if 'update-notices' in path.parts:
                raise PermissionError('isolated read-only notification store')
            return original_mkdir(path, *args, **kwargs)
        with patch.object(Path, 'mkdir', new=readonly_notices), \
                patch.object(updates, 'latest_release') as fetch:
            result = updates.check_updates(self.skill, self.state, notify=True, session_id='restricted-chat')
        self.assertEqual('update_available', result['status'])
        self.assertTrue(result['should_notify'])
        self.assertTrue(result['agent_deduplicate'])
        self.assertIn('read-only', result['notice_cache_error'])
        fetch.assert_not_called()

    def test_offline_check_and_corrupt_cache_do_not_interrupt_task_notice(self):
        updates.save_json(self.state / "update-cache.json", {"checked_at": "damaged cache"})
        with patch.object(updates, "latest_release", side_effect=URLError("offline")) as fetch, patch("sys.stderr", new_callable=io.StringIO) as stderr:
            updates.notify_on_task(self.skill, self.state)
            updates.notify_on_task(self.skill, self.state)
            self.assertEqual("", stderr.getvalue())
            self.assertEqual(1, fetch.call_count)
        self.assertEqual(self.preserved, {p.name: p.read_bytes() for p in self.workspace.iterdir()})

    def test_explicit_force_overrides_disabled_daily_checks(self):
        with patch.dict("os.environ", {"CY_UPDATE_CHECK": "0"}), patch.object(updates, "latest_release", return_value=self.info) as fetch:
            self.assertEqual("disabled", updates.check_updates(self.skill, self.state)["status"])
            fetch.assert_not_called()
            self.assertEqual("update_available", updates.check_updates(self.skill, self.state, force=True)["status"])

    def test_update_preserves_workspace_and_modified_old_program_then_is_noop(self):
        with patch.object(updates, "latest_release", return_value=self.info), \
                patch.object(updates, "download_release", side_effect=self.download_fixture) as download, \
                patch.object(updates, "run_installer", side_effect=self.install_fixture):
            result = updates.apply_update(self.skill, self.state, self.workspace)
            again = updates.apply_update(self.skill, self.state, self.workspace)
        self.assertEqual("updated", result["status"])
        self.assertEqual("up_to_date", again["status"])
        self.assertEqual(1, download.call_count)
        self.assertEqual("My local customization", (Path(result["backup"]) / "SKILL.md").read_text())
        self.assertEqual(self.preserved, {p.name: p.read_bytes() for p in self.workspace.iterdir()})
        self.assertFalse((self.state / "update.lock").exists())

    def test_failed_installer_restores_old_program_and_keeps_failed_candidate(self):
        def fail(*args):
            result = self.install_fixture(*args)
            result.update(status="failed", exit_code=1, local_entry_verified=False)
            return result
        with patch.object(updates, "latest_release", return_value=self.info), \
                patch.object(updates, "download_release", side_effect=self.download_fixture), \
                patch.object(updates, "run_installer", side_effect=fail):
            result = updates.apply_update(self.skill, self.state, self.workspace)
        self.assertEqual("failed", result["status"])
        self.assertTrue(result["program_restored"])
        self.assertEqual("1.0.1", (self.skill / "VERSION").read_text().strip())
        self.assertEqual("1.1.0", (Path(result["failed_program_backup"]) / "VERSION").read_text().strip())
        self.assertEqual(self.preserved, {p.name: p.read_bytes() for p in self.workspace.iterdir()})

    def test_corrupt_package_stops_before_installer_and_keeps_current_program(self):
        def corrupt(*args):
            archive = self.download_fixture(*args)
            with archive.open("ab") as stream:
                stream.write(b"corrupt")
            return archive
        with patch.object(updates, "latest_release", return_value=self.info), \
                patch.object(updates, "download_release", side_effect=corrupt), patch.object(updates, "run_installer") as install:
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                updates.apply_update(self.skill, self.state, self.workspace)
            install.assert_not_called()
        self.assertEqual("My local customization", (self.skill / "SKILL.md").read_text())
        self.assertFalse((self.state / "update.lock").exists())

    def exercise_timeout(self, kill_result, kill_error=None):
        process = Mock(pid=24680)
        process.wait.side_effect = [subprocess.TimeoutExpired("installer", 1200), 0]
        def start(command, **kwargs):
            source = Path(command[command.index("-File") + 1]).parents[1]
            progress = self.install_fixture(source, self.skill, self.state, self.workspace, None)
            progress.update(status="installing", local_entry_verified=False,
                            update_operation_id=kwargs["env"]["CY_UPDATE_ID"])
            updates.save_json(self.state / "install-result.json", progress)
            return process
        with patch.object(updates, "latest_release", return_value=self.info), \
                patch.object(updates, "download_release", side_effect=self.download_fixture), \
                patch.object(updates.subprocess, "Popen", side_effect=start), \
                patch.object(updates.subprocess, "run", return_value=Mock(returncode=kill_result), side_effect=kill_error) as kill:
            result = updates.apply_update(self.skill, self.state, self.workspace)
            self.assertEqual(["taskkill.exe", "/PID", "24680", "/T", "/F"], kill.call_args.args[0])
        return result

    def test_timeout_stops_owned_process_tree_before_restoring_recorded_backup(self):
        result = self.exercise_timeout(0)
        self.assertTrue(result["program_restored"])
        self.assertEqual("1.0.1", (self.skill / "VERSION").read_text().strip())
        self.assertTrue(result["install_result"]["timed_out"])
        self.assertFalse((self.state / "update.lock").exists())
        self.assertEqual("failed", json.loads((self.state / "update-result.json").read_text())["status"])

    def test_unconfirmed_process_stop_keeps_lock_and_does_not_move_live_program(self):
        result = self.exercise_timeout(1)
        self.assertEqual("installer_still_running", result["stage"])
        self.assertFalse(result["program_restored"])
        self.assertTrue((self.state / "update.lock").exists())
        self.assertEqual("1.1.0", (self.skill / "VERSION").read_text().strip())

    def test_unavailable_taskkill_keeps_lock_and_reports_running_installer(self):
        result = self.exercise_timeout(1, PermissionError("isolated process termination denied"))
        self.assertEqual("installer_still_running", result["stage"])
        self.assertTrue((self.state / "update.lock").exists())
        self.assertFalse(result["program_restored"])

    def test_source_checkout_and_active_update_are_not_overwritten(self):
        (self.skill / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "source checkout"):
            updates.apply_update(self.skill, self.state, self.workspace)
        (self.skill / ".git").rmdir()
        (self.state / "update.lock").write_text("other updater")
        with patch.object(updates, "latest_release", return_value=self.info), patch.object(updates, "download_release") as download:
            with self.assertRaisesRegex(ValueError, "Another update"):
                updates.apply_update(self.skill, self.state, self.workspace)
            download.assert_not_called()
        self.assertEqual("other updater", (self.state / "update.lock").read_text())

    def test_archive_rejects_unlisted_payload_even_when_outer_hash_matches(self):
        archive = self.make_archive()
        with zipfile.ZipFile(archive, "a") as payload:
            payload.writestr("cy-charmyee/extra.txt", "unexpected")
        archive.with_suffix(".zip.sha256").write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name)
        with self.assertRaisesRegex(ValueError, "extra or missing"):
            release_assets.verify_archive(archive)

    def test_release_metadata_rejects_unofficial_asset_location(self):
        name = self.info["zip_name"]
        data = {"tag_name": "v1.1.0", "assets": [{"name": name, "browser_download_url": "https://example.com/installer.zip"}]}
        with self.assertRaisesRegex(ValueError, "unexpected URL"):
            release_assets.release_info(data)

    def test_release_gate_requires_latest_success_for_exact_main_commit(self):
        run = {"id": 1, "head_sha": "abc", "head_branch": "main", "event": "push", "path": ".github/workflows/check.yml",
               "status": "completed", "conclusion": "success"}
        self.assertEqual(1, release.select_successful_run([run], "abc")["id"])
        for rejected in ({**run, "head_sha": "other"}, {**run, "head_branch": "work"},
                         {**run, "event": "pull_request"}, {**run, "status": "in_progress"}):
            with self.subTest(rejected=rejected), self.assertRaises(ValueError):
                release.select_successful_run([rejected], "abc")
        with self.assertRaises(ValueError):
            release.select_successful_run([run, {**run, "id": 2, "conclusion": "failure"}], "abc")

    def test_certificate_fallback_still_verifies_chain_and_hostname(self):
        context = ssl.create_default_context()
        certificate_error = URLError(ssl.SSLCertVerificationError("issuer missing"))
        with patch.dict("os.environ", {"SSL_CERT_FILE": "", "SSL_CERT_DIR": ""}), \
                patch.dict(sys.modules, {"certifi": SimpleNamespace(where=lambda: "mozilla-roots.pem")}), \
                patch.object(release_assets.ssl, "create_default_context", return_value=context) as factory, \
                patch.object(release_assets.request, "urlopen", side_effect=[certificate_error, io.BytesIO(b"verified response")]) as fetch:
            self.assertEqual(b"verified response", release_assets.read_url(release_assets.API_URL))
            self.assertEqual(2, fetch.call_count)
            factory.assert_called_once_with(cafile="mozilla-roots.pem")
            retried = fetch.call_args.kwargs["context"]
            self.assertTrue(retried.check_hostname)
            self.assertEqual(ssl.CERT_REQUIRED, retried.verify_mode)

    def test_certificate_fallback_respects_explicit_trust_configuration(self):
        error = URLError(ssl.SSLCertVerificationError("organization trust error"))
        with patch.dict("os.environ", {"SSL_CERT_FILE": "organization-roots.pem"}), \
                patch.object(release_assets.ssl, "create_default_context") as factory, \
                patch.object(release_assets.request, "urlopen", side_effect=error) as fetch:
            with self.assertRaises(URLError):
                release_assets.read_url(release_assets.API_URL)
            self.assertEqual(1, fetch.call_count)
            factory.assert_not_called()

    def test_non_certificate_network_error_does_not_retry_with_other_roots(self):
        with patch.object(release_assets.ssl, "create_default_context") as factory, \
                patch.object(release_assets.request, "urlopen", side_effect=URLError("offline")) as fetch:
            with self.assertRaises(URLError):
                release_assets.read_url(release_assets.API_URL)
            self.assertEqual(1, fetch.call_count)
            factory.assert_not_called()
