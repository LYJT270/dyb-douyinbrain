from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

RESOURCE_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = RESOURCE_ROOT.parents[1]
ROOT = Path(os.environ.get("DYB_WORKSPACE", str(Path.home() / "Documents" / "dyb-douyinbrain"))).expanduser().resolve()
SHANGHAI = timezone(timedelta(hours=8))


def now() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     suffix=".tmp", delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = handle.name
    os.replace(temporary, path)


def config(root: Path = ROOT) -> dict:
    defaults = {"chunk_seconds": 300, "asr_timeout_seconds": 300, "vault_root": None, "assistant_root": None}
    path = root / "config.json"
    return {**defaults, **(read_json(path) if path.exists() else {})}


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def safe_name(value: str, limit: int = 55) -> str:
    name = re.sub(r'[\x00-\x1f\\/:*?"<>|]', "-", value).strip(". ")[:limit]
    if not name or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", name):
        name = "材料-" + name
    return name


def inside(base: Path, value: str | Path) -> Path:
    path = (base / value).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError("路径超出允许目录")
    return path


def relative(root: Path, value: str | Path) -> str:
    """Record a workspace file relative to the workspace, so the folder can be renamed or moved."""
    return inside(root, value).relative_to(root.resolve()).as_posix()
