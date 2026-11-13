"""Portable entrypoint. Resolve machine-local workspace before importing the engine."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from runtime.douyin_text.identity import env_value, state_root


def main() -> int:
    selector = argparse.ArgumentParser(add_help=False)
    selector.add_argument("--workspace", type=Path)
    args, remaining = selector.parse_known_args()
    workspace = args.workspace or env_value("WORKSPACE")
    if not workspace:
        settings = state_root() / "settings.json"
        if settings.exists():
            workspace = json.loads(settings.read_text(encoding="utf-8-sig"))["workspace"]
    workspace = Path(workspace or Path.home() / "Documents/cy-charmyee").expanduser().resolve()
    resource = Path(__file__).resolve().parent / "runtime"
    skill_root = resource.parent.parent
    if workspace == skill_root or workspace.is_relative_to(skill_root) or skill_root.is_relative_to(workspace):
        raise ValueError("工作目录应与 Skill 程序目录分开")
    os.environ["CY_WORKSPACE"] = str(workspace)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(workspace / ".local/browsers")
    links = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "Microsoft/WinGet/Links"
    os.environ["PATH"] = str(links) + os.pathsep + os.environ.get("PATH", "")
    sys.dont_write_bytecode = True
    if remaining and remaining[0] in {"check-update", "update"}:
        from updates import apply_update, check_updates
        update_parser = argparse.ArgumentParser(prog=remaining[0])
        update_parser.add_argument("--force", action="store_true")
        if remaining[0] == "update":
            update_parser.add_argument("--apply", action="store_true")
        options = update_parser.parse_args(remaining[1:])
        apply = getattr(options, "apply", False)
        result = apply_update(skill_root, state_root(), workspace) if apply else check_updates(
            skill_root, state_root(), force=options.force, notify=remaining[0] == "check-update")
        print(json.dumps(result, ensure_ascii=False))
        return int(apply and result["status"] not in {"updated", "up_to_date"})
    if remaining and (remaining[0] in {"plan", "plan-text"} or remaining[:2] == ['creator', 'plan']):
        from updates import notify_on_task
        notify_on_task(skill_root, state_root())
    sys.path.insert(0, str(resource))
    from douyin_text.cli import main as run
    return run(remaining)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
