"""Verify distributable content, local documentation links and the exact manifest."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

from package import collect, make_manifest


def check(root: Path) -> list[str]:
    errors = []
    version = (root / "VERSION").read_text().strip()
    payload = collect(root)
    current = json.loads((root / "bundle.json").read_text(encoding="utf-8-sig"))
    if current != make_manifest(root, version, payload):
        errors.append("bundle.json is stale; run scripts/package.py --manifest-only")
    skill = (root / "SKILL.md").read_text(encoding="utf-8-sig")
    frontmatter = skill.split("---", 2)[1] if skill.startswith("---") else ""
    if not re.search(r"^name: dyb-douyinbrain$", frontmatter, re.M):
        errors.append("Skill name does not match the published directory")
    if not re.search(r"^description: .+", frontmatter, re.M):
        errors.append("Skill description is missing")
    for name, data in payload.items():
        path = root / name
        if path.suffix == ".py":
            try:
                ast.parse(data.decode("utf-8-sig"), filename=name)
            except SyntaxError as exc:
                errors.append(str(exc))
        if path.suffix == ".svg":
            ET.fromstring(data)
        if path.suffix in {".png", ".jpg"}:
            continue
        text = data.decode("utf-8-sig")
        if re.search(r"(?:gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{30,})", text):
            errors.append("Possible credential in " + name)
        if re.search(r"(?:[CEF]:[/\\]Users[/\\]admin|F:[/\\]codex work|E:[/\\]JT知识库)", text, re.I):
            errors.append("Machine-specific private path in " + name)
        if path.suffix != ".md":
            continue
        readable = re.sub(r"```.*?```", "", text, flags=re.S)
        links = re.findall(r"\[[^\]]*\]\(([^)\n]+)\)", readable)
        links += re.findall(r'(?:src|href)="([^"]+)"', readable)
        for link in links:
            link = link.strip("<> ").split("#")[0]
            if not link or urlsplit(link).scheme or link.startswith("//"):
                continue
            target = (path.parent / unquote(link)).resolve()
            if not target.is_relative_to(root.resolve()) or not target.exists():
                errors.append(f"Broken local link in {name}: {link}")
    return errors


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    errors = check(root)
    print(json.dumps({"status": "failed" if errors else "passed", "errors": errors}, ensure_ascii=False))
    raise SystemExit(bool(errors))
