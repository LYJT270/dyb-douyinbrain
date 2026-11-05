"""Portable entrypoint. Resolve machine-local workspace before importing the engine."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    selector = argparse.ArgumentParser(add_help=False)
    selector.add_argument("--workspace", type=Path)
    args, remaining = selector.parse_known_args()
    workspace = args.workspace or os.environ.get("DYB_WORKSPACE")
    if not workspace:
        settings = Path(os.environ.get("DYB_STATE_DIR") or (Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "dyb-douyinbrain")) / "settings.json"
        if settings.exists():
            workspace = json.loads(settings.read_text(encoding="utf-8-sig"))["workspace"]
    workspace = Path(workspace or Path.home() / "Documents/dyb-douyinbrain").expanduser().resolve()
    resource = Path(__file__).resolve().parent / "runtime"
    skill_root = resource.parent.parent
    if workspace == skill_root or workspace.is_relative_to(skill_root) or skill_root.is_relative_to(workspace):
        raise ValueError("工作目录应与 Skill 程序目录分开")
    os.environ["DYB_WORKSPACE"] = str(workspace)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(workspace / ".local/browsers")
    links = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "Microsoft/WinGet/Links"
    os.environ["PATH"] = str(links) + os.pathsep + os.environ.get("PATH", "")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(resource))
    from douyin_text.cli import main as run
    return run(remaining)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
