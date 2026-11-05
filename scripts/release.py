"""Preflight a release from tested main; --publish explicitly creates and pushes its tag."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from check_release import check
from release_assets import REPOSITORY, REPOSITORY_URL, version_tuple


def run(root: Path, *command: str) -> str:
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise ValueError(f"{command[0]} {command[1]} failed: " + (result.stderr or result.stdout).strip())
    return result.stdout.strip()


def select_successful_run(runs: list[dict], commit: str) -> dict:
    candidates = [item for item in runs if item.get("head_sha") == commit and item.get("head_branch") == "main"
                  and item.get("event") == "push" and item.get("path") == ".github/workflows/check.yml"]
    candidates.sort(key=lambda item: item["id"], reverse=True)
    if not candidates or candidates[0].get("status") != "completed" or candidates[0].get("conclusion") != "success":
        raise ValueError("The latest check.yml push run for this exact main commit must finish successfully")
    return candidates[0]


def preflight(root: Path) -> dict:
    if run(root, "git", "status", "--porcelain"):
        raise ValueError("Commit or preserve working changes before release; the worktree must be clean")
    if run(root, "git", "branch", "--show-current") != "main":
        raise ValueError("Release from main after merging the PR")
    remote = run(root, "git", "remote", "get-url", "origin").removesuffix(".git").rstrip("/")
    if remote not in {REPOSITORY_URL, "git@github.com:" + REPOSITORY}:
        raise ValueError("origin does not match the official release repository")
    run(root, "git", "fetch", "origin", "main", "--tags")
    commit = run(root, "git", "rev-parse", "HEAD")
    if commit != run(root, "git", "rev-parse", "origin/main"):
        raise ValueError("Local main must equal origin/main; fetch and fast-forward it first")
    errors = check(root)
    if errors:
        raise ValueError("; ".join(errors))
    version = (root / "VERSION").read_text().strip()
    current = version_tuple(version)
    tags = run(root, "git", "ls-remote", "--tags", "--refs", "origin").splitlines()
    for line in tags:
        tag = line.split("refs/tags/", 1)[-1]
        if not tag.startswith("v"):
            continue
        try:
            previous = version_tuple(tag[1:])
        except ValueError:
            continue
        if current <= previous:
            raise ValueError("VERSION must be newer than every published stable tag; preserve existing tags: " + tag)
    runs = json.loads(run(root, "gh", "api", f"repos/{REPOSITORY}/actions/workflows/check.yml/runs?event=push&branch=main&head_sha={commit}&per_page=20"))
    checked = select_successful_run(runs["workflow_runs"], commit)
    return {"status": "ready", "version": version, "tag": "v" + version, "commit": commit,
            "checks_url": checked["html_url"], "release_url": REPOSITORY_URL + "/releases/tag/v" + version}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="Create and push the new annotated tag after preflight")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = preflight(root)
    if args.publish:
        run(root, "git", "tag", "-a", result["tag"], "-m", "Douyin-brain " + result["version"])
        run(root, "git", "push", "origin", result["tag"])
        result.update(status="tag_pushed", actions_url=REPOSITORY_URL + "/actions/workflows/check.yml",
                      next_action="Wait for the tagged workflow, then run scripts/verify_release.py --download")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
