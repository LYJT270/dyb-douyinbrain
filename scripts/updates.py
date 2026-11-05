"""Update notices and explicit in-place upgrades, keeping workspace data separate."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
import uuid

from release_assets import download_release, extract_verified, latest_release, version_tuple

CACHE_SECONDS = 24 * 60 * 60


class InstallationStillRunning(ValueError):
    """Keep the lock and installation in place until the process has stopped."""


def state_root() -> Path:
    return Path(os.environ.get("DYB_STATE_DIR") or
                Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "dyb-douyinbrain").resolve()


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


def check_updates(skill: Path, state: Path, *, force: bool = False, notify: bool = False) -> dict:
    current = (skill / "VERSION").read_text().strip()
    version_tuple(current)
    if not force and os.environ.get("DYB_UPDATE_CHECK") == "0":
        return {"status": "disabled", "current_version": current, "should_notify": False}
    path = state / "update-cache.json"
    cache = read_cache(path)
    now = time.time()
    checked_at = cache.get("checked_at", 0)
    fresh = isinstance(checked_at, (int, float)) and 0 <= now - checked_at < CACHE_SECONDS
    try:
        if force or not fresh:
            info = latest_release()
            cache.update(checked_at=now, release=info, error=None)
            save_json(path, cache)
        elif cache.get("error"):
            return {"status": "unavailable", "current_version": current, "should_notify": False, "cached": True}
        info = cache["release"]
        latest = info["version"]
        available = version_tuple(latest) > version_tuple(current)
        should_notify = available and (cache.get("notified_version") != latest or
                                      now - cache.get("notified_at", 0) >= CACHE_SECONDS)
        if notify and should_notify:
            cache.update(notified_version=latest, notified_at=now)
            save_json(path, cache)
        return {"status": "update_available" if available else "up_to_date", "current_version": current,
                "latest_version": latest, "release_url": info["url"], "should_notify": should_notify,
                "cached": fresh and not force, "update_instruction": "@dyb-douyinbrain 更新"}
    except (ValueError, KeyError, TypeError, OSError, URLError) as exc:
        try:
            cache.update(checked_at=now, error=str(exc))
            save_json(path, cache)
        except OSError:
            pass
        return {"status": "unavailable", "current_version": current, "should_notify": False,
                "error": str(exc), "continue_current_task": True}


def notify_on_task(skill: Path, state: Path) -> None:
    try:
        result = check_updates(skill, state, notify=True)
    except (ValueError, OSError):
        return
    if result.get("should_notify"):
        print(f"抖音脑有新版本 {result['latest_version']}（当前 {result['current_version']}）。"
              "需要更新时请说：@dyb-douyinbrain 更新。当前任务可以继续。", file=sys.stderr)


def run_installer(source: Path, skill: Path, state: Path, workspace: Path, log: Path) -> dict:
    result_path = state / "install-result.json"
    operation = uuid.uuid4().hex
    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               str(source / "scripts/install.ps1"), "-Agent", "custom", "-SkillsRoot", str(skill.parent),
               "-StateDirectory", str(state), "-Workspace", str(workspace),
               "-PythonExecutable", sys.executable, "-NoApiWindow"]
    environment = {**os.environ, "DYB_UPDATE_CHECK": "0", "DYB_STATE_DIR": str(state), "DYB_UPDATE_ID": operation}
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
    if backup.parent != trash or not backup.is_dir() or skill.name != "dyb-douyinbrain":
        raise ValueError("Unexpected rollback path; preserved the installation for inspection")
    manifest = json.loads((backup / "bundle.json").read_text(encoding="utf-8-sig"))
    if manifest.get("name") != "dyb-douyinbrain" or manifest.get("version") != old_version:
        raise ValueError("Rollback backup does not match the previous installation")
    failed = (trash / (time.strftime("%Y-%m-%d") + "_failed-update_" + uuid.uuid4().hex[:8])).resolve()
    # Validate absolute source and destination before Windows directory moves.
    if failed.parent != trash or skill.resolve().parent != skill.parent.resolve():
        raise ValueError("Unexpected rollback destination")
    if skill.exists():
        skill.rename(failed)
    backup.rename(skill)
    return str(failed)


def apply_update(skill: Path, state: Path, workspace: Path) -> dict:
    skill, state, workspace = skill.resolve(), state.resolve(), workspace.resolve()
    if (skill / ".git").exists():
        raise ValueError("This is a source checkout. Follow docs/RELEASING.md; do not overwrite it with an installation ZIP.")
    if skill.name != "dyb-douyinbrain" or workspace == skill or workspace.is_relative_to(skill) or skill.is_relative_to(workspace):
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
        if not success:
            failed = restore_program(skill, result.get("backup"), old_version)
            failure = {"status": "failed", "stage": "install", "previous_version": old_version,
                       "program_restored": failed is not None, "failed_program_backup": failed,
                       "install_result": result, "log": str(stage / "install.log")}
            save_json(state / "update-result.json", failure)
            return failure
        installed_version = (skill / "VERSION").read_text().strip()
        completed = {"status": "updated", "previous_version": old_version, "current_version": installed_version,
                     "workspace": str(workspace), "skill_file": str(skill / "SKILL.md"), "backup": result.get("backup"),
                     "local_entry_verified": True, "live_asr_requests": 0,
                     "next_action": "重新读取新版 SKILL.md 和 references/runtime.md；Agent 若仍缓存旧指令，请新建会话。"}
        save_json(state / "update-result.json", completed)
        return completed
    finally:
        if not keep_lock:
            lock.unlink(missing_ok=True)
