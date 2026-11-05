"""Verify a local package or download the current version without GitHub login."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import URLError
import uuid

from release_assets import API_URL, download_release, read_url, release_info, verify_archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--archive", type=Path)
    mode.add_argument("--download", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version = (root / "VERSION").read_text().strip()
    manifest = json.loads((root / "bundle.json").read_text(encoding="utf-8-sig"))
    archive = args.archive
    if args.download:
        info = release_info(json.loads(read_url(API_URL + "/releases/tags/v" + version)))
        archive = download_release(info, root / ".scratch" / ("verify-" + uuid.uuid4().hex))
    result = verify_archive(archive, expected_version=version, expected_manifest=manifest)
    result.pop("manifest")
    result.update(public_download=args.download, archive=str(archive.resolve()))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, URLError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
