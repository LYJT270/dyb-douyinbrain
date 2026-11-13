"""Current names with read compatibility for existing local registrations."""
from __future__ import annotations

import os
from pathlib import Path

SKILL_ID = "cy-charmyee"
DISPLAY_NAME = "承意 CY-CharmYee"
SLOGAN = "承你所想，会你所意"


def env_value(suffix: str) -> str | None:
    return os.environ.get("CY_" + suffix) or os.environ.get("DYB_" + suffix)


def state_root() -> Path:
    explicit = env_value("STATE_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
    current = base / SKILL_ID
    legacy = base / "dyb-douyinbrain"
    # Reuse the registration and locks in place; do not create two active states.
    if not (current / "settings.json").is_file() and (legacy / "settings.json").is_file():
        return legacy.resolve()
    return current.resolve()
