"""Build a verified migration ZIP and keep only the current ZIP in its output directory."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import uuid
import zipfile

EXCLUDED = {".venv", ".local", ".cache", "__pycache__", "runs", "outputs", ".git", ".scratch", ".trash", "tests", "dist", "exports"}
SUFFIXES = {".md", ".py", ".ps1", ".cmd", ".txt", ".yaml", ".html", ".png", ".svg", ".json"}
ROOT_FILES = {"SKILL.md", "INSTALL.md", "README.md", "README.en.md", "LICENSE", "VERSION",
              "THIRD_PARTY_NOTICES.md", "CHANGELOG.md", "SECURITY.md", "SOURCE_OF_TRUTH.md",
              "CONTRIBUTING.md", "给Agent的安装提示词.txt", "豆包配置教程.html"}
PAYLOAD_DIRS = {"scripts", "references", "agents", "assets", "docs"}


def collect(skill: Path) -> dict[str, bytes]:
    payload = {}
    for file in sorted(skill.rglob("*")):
        relative = file.relative_to(skill)
        if not file.is_file() or any(part in EXCLUDED for part in relative.parts):
            continue
        if file.name == "bundle.json":
            continue
        admitted = relative.parts[0] in PAYLOAD_DIRS if len(relative.parts) > 1 else file.name in ROOT_FILES or file.suffix == ".cmd"
        if not admitted:
            continue
        if file.suffix.lower() not in SUFFIXES and file.name not in {"LICENSE", "VERSION"}:
            raise ValueError("Unrecognized distributable file: " + str(relative))
        payload[relative.as_posix()] = file.read_bytes()
    for required in ("SKILL.md", "INSTALL.md", "LICENSE", "scripts/install.ps1", "scripts/brain.py"):
        if required not in payload:
            raise ValueError("Missing required distributable file: " + required)
    return payload


def make_manifest(skill: Path, version: str, payload=None) -> dict:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Version must use major.minor.patch")
    payload = collect(skill) if payload is None else payload
    return {"name": "dyb-douyinbrain", "display_name": "抖音脑 Douyin-brain", "version": version,
            "platform": "windows", "license": "MIT", "repository": "https://github.com/LYJT270/dyb-douyinbrain",
            "file_sha256": {p: hashlib.sha256(data).hexdigest() for p, data in sorted(payload.items())}}


def write_manifest(skill: Path, version: str) -> dict:
    normalize_text_files(skill)
    manifest = make_manifest(skill, version)
    (skill / "bundle.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def normalize_text_files(skill: Path) -> None:
    """Match .gitattributes so source ZIPs and Git checkouts have identical hashes."""
    for name, data in collect(skill).items():
        if Path(name).suffix.lower() not in {".png", ".jpg"} and b"\r\n" in data:
            (skill / name).write_bytes(data.replace(b"\r\n", b"\n"))


def move_to_trash(source: Path, output: Path, trash: Path) -> Path:
    # Check both resolved absolute targets before any Windows move.
    source = source.resolve()
    output, trash = output.resolve(), trash.resolve()
    if source.parent != output or not source.is_file():
        raise ValueError("迁移包不在指定交付目录内")
    day = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    target = (trash / f"{day}_{source.name}").resolve()
    if target.exists():
        target = (trash / f"{day}_{source.stem}_{uuid.uuid4().hex[:8]}{source.suffix}").resolve()
    if target.parent != trash:
        raise ValueError("旧包移入目标超出 .trash")
    trash.mkdir(parents=True, exist_ok=True)
    source.rename(target)
    return target


def build(skill: Path, output: Path, version: str) -> dict:
    skill, output = skill.resolve(), output.resolve()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("版本号应为三段数字")
    if output.is_relative_to(skill) and output != skill / "dist":
        raise ValueError("安装包输出目录应使用仓库的 dist，或程序目录以外的位置")
    normalize_text_files(skill)
    payload = collect(skill)
    manifest = make_manifest(skill, version, payload)
    manifest_data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / (".dyb-douyinbrain-" + uuid.uuid4().hex + ".zip.tmp")
    trash = output.parent / ".trash"
    try:
        with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for relative, data in sorted(payload.items()):
                archive.writestr("dyb-douyinbrain/" + relative, data)
            archive.writestr("dyb-douyinbrain/bundle.json", manifest_data)
        # Validate before touching any previously delivered ZIP.
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError("新迁移包 CRC 校验失败，旧包尚未移动")
            packaged = json.loads(archive.read("dyb-douyinbrain/bundle.json"))
            for relative, checksum in packaged["file_sha256"].items():
                if hashlib.sha256(archive.read("dyb-douyinbrain/" + relative)).hexdigest() != checksum:
                    raise ValueError("新迁移包内容校验失败，旧包尚未移动")
    except Exception:
        if temporary.exists():
            move_to_trash(temporary, output, trash)
        raise
    target = output / f"dyb-douyinbrain-windows-v{version}.zip"
    moved = []
    if target.exists():
        moved.append(str(move_to_trash(target, output, trash)))
        old_checksum = target.with_suffix(".zip.sha256")
        if old_checksum.exists():
            moved.append(str(move_to_trash(old_checksum, output, trash)))
    temporary.replace(target)
    # Update the installed manifest only after a valid ZIP is available.
    (skill / "bundle.json").write_bytes(manifest_data)
    for previous in sorted(output.glob("dyb-douyinbrain-windows-*.zip")):
        if previous != target:
            moved.append(str(move_to_trash(previous, output, trash)))
            old_checksum = previous.with_suffix(".zip.sha256")
            if old_checksum.exists():
                moved.append(str(move_to_trash(old_checksum, output, trash)))
    remaining = sorted(p.name for p in output.glob("dyb-douyinbrain-windows-*.zip"))
    if remaining != [target.name]:
        raise RuntimeError("交付目录未收敛到当前迁移包，请查看残留文件")
    return {"status": "packaged", "version": version, "zip": str(target),
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "bytes": target.stat().st_size,
            "source_files": len(payload) + 1, "moved_to_trash": moved,
            "remaining_packages": remaining, "trash_minimum_retention_days": 30}


def main() -> None:
    parser = argparse.ArgumentParser(description="打包并校验新版；旧迁移包移入 .trash，交付目录只留当前包")
    parser.add_argument("--version", default=None)
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    skill = Path(__file__).resolve().parents[1]
    version = args.version or (skill / "VERSION").read_text().strip()
    if args.manifest_only:
        manifest = write_manifest(skill, version)
        print(json.dumps({"status": "manifest_updated", "version": version, "files": len(manifest["file_sha256"])}))
    else:
        if not args.output_dir:
            parser.error("--output-dir is required unless --manifest-only is used")
        result = build(skill, args.output_dir, version)
        zip_path = Path(result["zip"])
        checksum = zip_path.with_suffix(".zip.sha256")
        checksum.write_text(result["sha256"] + "  " + zip_path.name + "\n", encoding="ascii")
        result["checksum_file"] = str(checksum)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
