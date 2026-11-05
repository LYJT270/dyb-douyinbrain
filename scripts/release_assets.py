"""Shared verification for official release downloads; standard library only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib import request
import zipfile

REPOSITORY = "ScarfaceAI/dyb-douyinbrain"
REPOSITORY_URL = "https://github.com/" + REPOSITORY
API_URL = "https://api.github.com/repos/" + REPOSITORY
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024


def version_tuple(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", value):
        raise ValueError("Expected a stable major.minor.patch version: " + value)
    return tuple(map(int, value.split(".")))


def read_url(url: str, timeout: float = 30, limit: int = MAX_DOWNLOAD_BYTES) -> bytes:
    req = request.Request(url, headers={"User-Agent": "dyb-douyinbrain", "Accept": "application/vnd.github+json"})
    with request.urlopen(req, timeout=timeout) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Release download exceeds the supported size")
    return data


def release_info(value: dict) -> dict:
    tag = value.get("tag_name", "")
    if value.get("draft") or value.get("prerelease") or not tag.startswith("v"):
        raise ValueError("Only published stable releases are supported")
    version = tag[1:]
    version_tuple(version)
    name = f"dyb-douyinbrain-windows-{tag}.zip"
    base = REPOSITORY_URL + f"/releases/download/{tag}/"
    assets = {asset["name"]: asset for asset in value.get("assets", [])}
    for filename in (name, name + ".sha256"):
        if assets.get(filename, {}).get("browser_download_url") != base + filename:
            raise ValueError("Official release assets are incomplete or have an unexpected URL")
    return {"version": version, "tag": tag, "url": REPOSITORY_URL + "/releases/tag/" + tag,
            "zip_name": name, "zip_url": base + name, "checksum_url": base + name + ".sha256"}


def latest_release(timeout: float = 3) -> dict:
    return release_info(json.loads(read_url(API_URL + "/releases/latest", timeout, 2 * 1024 * 1024)))


def verify_archive(archive_path: Path, *, expected_version: str | None = None,
                   expected_manifest: dict | None = None) -> dict:
    archive_path = Path(archive_path)
    checksum_path = archive_path.with_suffix(".zip.sha256")
    parts = checksum_path.read_text(encoding="ascii").split()
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if len(parts) != 2 or parts[0] != digest or parts[1] != archive_path.name:
        raise ValueError("Release ZIP SHA-256 or filename does not match its checksum file")
    prefix = "dyb-douyinbrain/"
    try:
        opened = zipfile.ZipFile(archive_path)
    except zipfile.BadZipFile as exc:
        raise ValueError("Downloaded file is not a valid release ZIP") from exc
    with opened as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Release ZIP contains duplicate paths")
        if sum(item.file_size for item in archive.infolist()) > MAX_DOWNLOAD_BYTES:
            raise ValueError("Unpacked release exceeds the supported size")
        if archive.testzip() is not None:
            raise ValueError("Release ZIP failed CRC verification")
        manifest = json.loads(archive.read(prefix + "bundle.json"))
        version = manifest["version"]
        version_tuple(version)
        if manifest.get("name") != "dyb-douyinbrain" or manifest.get("repository") != REPOSITORY_URL:
            raise ValueError("Unexpected release identity")
        if expected_version and version != expected_version:
            raise ValueError("Release version does not match the requested version")
        if expected_manifest is not None and manifest != expected_manifest:
            raise ValueError("Published manifest differs from the checked source")
        files = manifest["file_sha256"]
        if not {"SKILL.md", "VERSION", "scripts/install.ps1", "scripts/brain.py"} <= set(files):
            raise ValueError("Required installation files are missing")
        expected = {prefix + name for name in files} | {prefix + "bundle.json"}
        if set(names) != expected:
            raise ValueError("Release ZIP contains extra or missing files")
        for name, checksum in files.items():
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name or path.as_posix() != name:
                raise ValueError("Unsafe path in release manifest")
            if hashlib.sha256(archive.read(prefix + name)).hexdigest() != checksum:
                raise ValueError("Release payload checksum mismatch: " + name)
        if archive.read(prefix + "VERSION").decode("utf-8-sig").strip() != version:
            raise ValueError("VERSION differs from the release manifest")
    return {"status": "verified", "version": version, "sha256": digest, "files": len(names), "manifest": manifest}


def download_release(info: dict, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / info["zip_name"]
    archive.write_bytes(read_url(info["zip_url"]))
    archive.with_suffix(".zip.sha256").write_bytes(read_url(info["checksum_url"], limit=4096))
    verify_archive(archive, expected_version=info["version"])
    return archive


def extract_verified(archive_path: Path, directory: Path, version: str) -> Path:
    verify_archive(archive_path, expected_version=version)
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive_path) as archive:
        for name in archive.namelist():
            target = (directory / name).resolve()
            if not target.is_relative_to(directory):
                raise ValueError("Unpack target is outside the staging directory")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    return directory / "dyb-douyinbrain"
