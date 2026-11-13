"""Update notices and explicit in-place upgrades, keeping workspace data separate."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
import uuid

from release_assets import download_release, extract_verified, latest_release, version_tuple
from suite_manifest import check_installed
from runtime.douyin_text.identity import env_value, state_root

CACHE_SECONDS = 24 * 60 * 60


class InstallationStillRunning(ValueError):
    """Keep the lock and installation in place until the process has stopped."""


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_cache(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def session_identity(explicit: str | None = None) -> str | None:
    """Use a real host/chat identity; never replace it with a global or daily ID."""
    if explicit is not None:
        return explicit.strip() or None
    for name in ("CY_SESSION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def check_updates(skill: Path, state: Path, *, force: bool = False, notify: bool = False,
                  session_id: str | None = None) -> dict:
    current = (skill / "VERSION").read_text().strip()
    version_tuple(current)
    if not force and env_value("UPDATE_CHECK") == "0":
        return {"status": "disabled", "current_version": current, "should_notify": False}
    path = state / "update-cache.json"
    cache = read_cache(path)
    now = time.time()
    checked_at = cache.get("checked_at", 0)
    fresh = isinstance(checked_at, (int, float)) and 0 <= now - checked_at < CACHE_SECONDS
    cached = fresh and not force
    if not cached:
        try:
            info = latest_release()
            cache.update(checked_at=now, release_checked_at=now, release=info, error=None)
            save_json(path, cache)
        except (ValueError, KeyError, TypeError, OSError, URLError) as exc:
            cache.update(checked_at=now, error=str(exc))
            try:
                save_json(path, cache)
            except OSError:
                pass
    try:
        info = cache["release"]
        latest = info["version"]
        release_url = info["url"]
        available = version_tuple(latest) > version_tuple(current)
        identity = session_identity(session_id)
        key = hashlib.sha256(identity.encode("utf-8")).hexdigest() if identity else None
        version_pair = {"current": current, "latest": latest}
        pair_key = hashlib.sha256((current + "\0" + latest).encode("utf-8")).hexdigest()
        claim = state / "update-notices" / key / (pair_key + ".json") if key else None
        notice_cache_error = None
        should_notify = available
        try:
            should_notify = available and (claim is None or not claim.is_file())
            if notify and should_notify and key:
                # Independent exclusive claims prevent parallel chats losing one another's
                # deduplication records during the shared metadata cache's read/modify/write.
                claim.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with claim.open("x", encoding="utf-8") as stream:
                        json.dump(version_pair, stream)
                except FileExistsError:
                    should_notify = False
        except OSError as exc:
            # A known newer release stays useful when only the notice store is
            # read-only. The Agent can still deduplicate inside this conversation.
            key = None
            should_notify = available
            notice_cache_error = str(exc)
        return {"status": "update_available" if available else "up_to_date", "current_version": current,
                "latest_version": latest, "release_url": release_url, "should_notify": should_notify,
                "cached": cached, "stale": bool(cache.get("error")), "check_error": cache.get("error"),
                "release_checked_at": cache.get("release_checked_at"),
                "notification_scope": "session" if key else "agent_conversation",
                "agent_deduplicate": key is None, "notice_cache_error": notice_cache_error,
                "update_instruction": "@cy-charmyee 更新"}
    except (ValueError, KeyError, TypeError, OSError, URLError) as exc:
        try:
            cache.update(checked_at=now, error=cache.get("error") or str(exc))
            save_json(path, cache)
        except OSError:
            pass
        return {"status": "unavailable", "current_version": current, "should_notify": False,
                "error": cache.get("error") or str(exc), "cached": cached, "continue_current_task": True}


def notify_on_task(skill: Path, state: Path) -> None:
    try:
        result = check_updates(skill, state, notify=True)
    except (ValueError, OSError):
        return
    if result.get("should_notify"):
        prefix = "上次检查确认承意有新版本" if result.get('stale') else "承意有新版本"
        print(f"{prefix} {result['latest_version']}（当前 {result['current_version']}）。"
              "需要更新时请说：@cy-charmyee 更新。当前任务可以继续。", file=sys.stderr)


def run_installer(source: Path, skill: Path, state: Path, workspace: Path, log: Path) -> dict:
    result_path = state / "install-result.json"
    operation = uuid.uuid4().hex
    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               str(source / "scripts/install.ps1"), "-Agent", "custom", "-SkillsRoot", str(skill.parent),
               "-StateDirectory", str(state), "-Workspace", str(workspace),
               "-PythonExecutable", sys.executable, "-NoApiWindow"]
    environment = {**os.environ, "CY_UPDATE_CHECK": "0", "CY_STATE_DIR": str(state), "CY_UPDATE_ID": operation}
    timed_out = False
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, env=environment)
        try:
            code = process.wait(timeout=1200)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            timed_out = isinstance(exc, subprocess.TimeoutExpired)
            # Stop only this updater's installer and its children before touching their files.
            try:
                stopped = subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            except OSError as exc:
                raise InstallationStillRunning(f"Cannot stop installer process tree {process.pid}; keep update.lock and inspect {log}") from exc
            if stopped.returncode != 0:
                raise InstallationStillRunning(f"Cannot confirm installer process tree {process.pid} stopped; keep update.lock and inspect {log}")
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired as exc:
                raise InstallationStillRunning(f"Installer {process.pid} has not exited; keep update.lock and inspect {log}") from exc
            code = 124 if timed_out else 130
    current = result_path.read_bytes() if result_path.exists() else b""
    try:
        result = json.loads(current.decode("utf-8-sig")) if current else {}
    except ValueError:
        result = {}
    if result.get("update_operation_id") != operation:
        result = {}
    result.update(exit_code=code, timed_out=timed_out)
    return result


def restore_program(skill: Path, backup: str | None, old_version: str) -> str | None:
    if not backup:
        return None
    backup = Path(backup).resolve()
    trash = (skill.parent.parent / ".trash").resolve()
    if not backup.exists() and (skill / "VERSION").is_file() and (skill / "VERSION").read_text().strip() == old_version:
        return None  # The installer stopped before the recorded atomic directory move.
    if backup.parent != trash or not backup.is_dir() or skill.name != "cy-charmyee":
        raise ValueError("Unexpected rollback path; preserved the installation for inspection")
    manifest = json.loads((backup / "bundle.json").read_text(encoding="utf-8-sig"))
    if manifest.get("name") != "cy-charmyee" or manifest.get("version") != old_version:
        raise ValueError("Rollback backup does not match the previous installation")
    failed = (trash / (time.strftime("%Y-%m-%d") + "_failed-update_" + uuid.uuid4().hex[:8])).resolve()
    # Validate absolute source and destination before Windows directory moves.
    if failed.parent != trash or skill.resolve().parent != skill.parent.resolve():
        raise ValueError("Unexpected rollback destination")
    if skill.exists():
        skill.rename(failed)
    backup.rename(skill)
    return str(failed)


def restore_suite(source: Path, skill: Path, state: Path, result: dict, old_version: str) -> dict:
    journal = Path(result['suite_transaction']).resolve()
    if journal != (state / 'suite-install.json').resolve():
        raise ValueError('Unexpected suite rollback journal')
    process = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                              str(source / 'scripts/restore-suite.ps1'), '-TransactionPath', str(journal),
                              '-SkillsRoot', str(skill.parent)], capture_output=True, timeout=120)
    restored = json.loads(process.stdout.decode('utf-8-sig'))
    if process.returncode or restored.get('status') != 'rolled_back':
        raise ValueError('Suite rollback did not complete: ' + restored.get('error', str(process.returncode)))
    intact = (skill / 'VERSION').is_file() and (skill / 'VERSION').read_text().strip() == old_version
    # Original directories may include user edits; restore them byte-for-byte, not to a release hash.
    failed = [row['failed_backup'] for row in restored['entries'] if Path(row['failed_backup']).is_dir()]
    return {'program_restored': intact, 'failed_program_backups': failed, 'suite_rollback': restored['status']}


def apply_update(skill: Path, state: Path, workspace: Path) -> dict:
    skill, state, workspace = skill.resolve(), state.resolve(), workspace.resolve()
    if (skill / ".git").exists():
        raise ValueError("This is a source checkout. Follow docs/RELEASING.md; do not overwrite it with an installation ZIP.")
    if skill.name != "cy-charmyee" or workspace == skill or workspace.is_relative_to(skill) or skill.is_relative_to(workspace):
        raise ValueError("The installed Skill and its workspace must be separate")
    settings = json.loads((state / "settings.json").read_text(encoding="utf-8-sig"))
    if Path(settings["workspace"]).resolve() != workspace:
        raise ValueError("Registered workspace differs; resolve the installation before updating")
    notice = check_updates(skill, state, force=True)
    if notice["status"] != "update_available":
        return notice
    old_version = notice["current_version"]
    state.mkdir(parents=True, exist_ok=True)
    lock = state / "update.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError("Another update is running. Check that process before retrying.") from exc
    os.close(descriptor)
    keep_lock = False
    stage = state / "updates" / ("v" + notice["latest_version"] + "-" + uuid.uuid4().hex[:8])
    try:
        # Use freshly fetched release metadata, not an untrusted URL from a local cache.
        info = latest_release(timeout=15)
        if version_tuple(info["version"]) <= version_tuple(old_version):
            return {"status": "up_to_date", "current_version": old_version, "latest_version": info["version"]}
        archive = download_release(info, stage)
        source = extract_verified(archive, stage / "unpacked", info["version"])
        try:
            result = run_installer(source, skill, state, workspace, stage / "install.log")
        except InstallationStillRunning as exc:
            keep_lock = True
            failure = {"status": "failed", "stage": "installer_still_running", "error": str(exc),
                       "program_restored": False, "log": str(stage / "install.log")}
            save_json(state / "update-result.json", failure)
            return failure
        except OSError as exc:
            result = {"status": "failed", "exit_code": 1, "error": str(exc)}
        success = (result.get("exit_code") == 0 and result.get("status") in {"installed", "awaiting_api"}
                   and result.get("local_entry_verified") is True and result.get("version") == info["version"]
                   and Path(result.get("skill", "")).resolve() == skill
                   and Path(result.get("workspace", "")).resolve() == workspace
                   and (skill / "VERSION").is_file() and (skill / "VERSION").read_text().strip() == info["version"])
        suite = None
        if success:
            try:
                suite = check_installed(skill)
            except (OSError, ValueError, KeyError) as exc:
                result['suite_error'] = str(exc)
                success = False
        if not success:
            if result.get('suite_transaction'):
                restored = restore_suite(source, skill, state, result, old_version)
            else:
                failed = restore_program(skill, result.get("backup"), old_version)
                restored = {'program_restored': failed is not None, 'failed_program_backup': failed}
            failure = {"status": "failed", "stage": "install", "previous_version": old_version,
                       **restored,
                       "install_result": result, "log": str(stage / "install.log")}
            save_json(state / "update-result.json", failure)
            return failure
        installed_version = (skill / "VERSION").read_text().strip()
        completed = {"status": "updated", "previous_version": old_version, "current_version": installed_version,
                     "workspace": str(workspace), "skill_file": str(skill / "SKILL.md"), "backup": result.get("backup"),
                     "local_entry_verified": True, "live_asr_requests": 0,
                     "suite": suite,
                     "next_action": "重新读取新版 SKILL.md 和 references/runtime.md；Agent 若仍缓存旧指令，请新建会话。"}
        save_json(state / "update-result.json", completed)
        return completed
    finally:
        if not keep_lock:
            lock.unlink(missing_ok=True)
