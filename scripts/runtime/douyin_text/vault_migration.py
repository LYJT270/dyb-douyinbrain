"""Preview, apply and recover an explicit three-domain vault reclassification.

The Agent supplies every classification. This module only validates the plan,
backs up touched content, repairs supported path references, and records a
separate path map for historical readers.
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from . import personal_vault
from .common import ArtifactBusyError, ROOT, artifact_lock, config, digest, now, read_json, write_json

DOMAINS = {"生活", "工作", "学习"}
RULES = tuple(personal_vault.RULES)
ROOT_NAV = {"index.md", "使用说明.md"}
ROOT_EXEMPT = set(RULES) | ROOT_NAV | {"catalog.json"}
RUNTIME = ".cy-vault-runtime"
PATH_MAP = "path-migrations.json"
_UNSAFE_COMPONENTS = {".trash", ".cy-vault-runtime", ".dyb-vault-runtime"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _key(value: str) -> str:
    return value.replace("\\", "/").strip("/").casefold()


def _workspace(root: Path) -> Path:
    return root.expanduser().resolve()


def _is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


def _vault_for(root: Path) -> Path:
    value = personal_vault.state(root)
    configured = value.get("vault_root") or config(root).get("vault_root")
    if not configured:
        raise ValueError("工作区尚未连接知识库，无法生成迁移预览")
    vault = Path(configured).expanduser().resolve()
    if not vault.is_dir():
        raise ValueError("知识库目录当前不可用")
    return vault


def _safe_relative(raw: str, *, field: str) -> str:
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        raise ValueError(f"{field} 必须是非空相对路径")
    value = raw.replace("\\", "/")
    path = PurePosixPath(value)
    if path.is_absolute() or re.match(r"^[A-Za-z]:", value) or any(p in {"", ".", ".."} for p in value.split("/")):
        raise ValueError(f"{field} 不得逃出知识库：{raw}")
    if ":" in value:
        raise ValueError(f"{field} 包含不允许的路径分隔符：{raw}")
    return path.as_posix()


def _no_symlink(base: Path, relative_path: str, *, include_leaf=True) -> Path:
    """Resolve a library path while refusing symlinks at every existing component."""
    base = base.resolve()
    current = base
    parts = PurePosixPath(relative_path).parts
    for index, part in enumerate(parts):
        current = current / part
        if current.exists() or _is_reparse(current):
            if _is_reparse(current):
                raise ValueError(f"迁移路径包含软链接或目录联接：{relative_path}")
            if index < len(parts) - 1 and not current.is_dir():
                raise ValueError(f"目标父路径不是目录：{relative_path}")
    resolved = current.resolve(strict=False)
    if not resolved.is_relative_to(base):
        raise ValueError(f"迁移路径逃出知识库：{relative_path}")
    return current


def _workspace_file(workspace: Path, raw: str | Path, *, field: str) -> Path:
    requested = Path(raw)
    candidate = requested if requested.is_absolute() else workspace / requested
    candidate = candidate.absolute()
    try:
        relative_path = candidate.relative_to(workspace)
    except ValueError:
        raise ValueError(f"{field} 必须位于 workspace 内") from None
    current = workspace
    for part in relative_path.parts:
        current = current / part
        if current.exists() or _is_reparse(current):
            if _is_reparse(current):
                raise ValueError(f"{field} 路径包含软链接或目录联接")
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(workspace):
        raise ValueError(f"{field} 路径逃出 workspace")
    return resolved


def _is_root_exempt(relative_path: str) -> bool:
    return "/" not in relative_path and relative_path.casefold() in {x.casefold() for x in ROOT_EXEMPT}


def _inventory(vault: Path) -> tuple[dict[str, str], list[str], list[str]]:
    """Visible content hashes, visible directories and visible symlink issues."""
    files: dict[str, str] = {}
    dirs: list[str] = []
    symlinks: list[str] = []
    for current, child_dirs, names in os.walk(vault, topdown=True, followlinks=False):
        folder = Path(current)
        kept = []
        for name in child_dirs:
            path = folder / name
            rel = path.relative_to(vault).as_posix()
            if name.startswith(".") or name.casefold() in _UNSAFE_COMPONENTS:
                continue
            if _is_reparse(path):
                symlinks.append(rel)
                continue
            kept.append(name)
            dirs.append(rel)
        child_dirs[:] = kept
        for name in names:
            path = folder / name
            rel = path.relative_to(vault).as_posix()
            if name.startswith("."):
                continue
            if _is_reparse(path):
                symlinks.append(rel)
                continue
            if not path.is_file() or _is_root_exempt(rel):
                continue
            files[rel] = digest(path)
    return files, sorted(dirs, key=str.casefold), sorted(symlinks, key=str.casefold)


def _parse_manifest(path: Path) -> dict:
    value = read_json(path)
    if not isinstance(value, dict) or not isinstance(value.get("files"), list):
        raise ValueError("manifest 需要 files 列表")
    if not isinstance(value.get("replacements", []), list):
        raise ValueError("replacements 必须是列表")
    return value


def _marker(vault: Path) -> tuple[Path | None, dict]:
    for name in (".cy-vault.json", ".dyb-vault.json"):
        path = vault / name
        if _is_reparse(path):
            raise ValueError(f"本地知识库授权标记不能是软链接或目录联接：{name}")
        if path.is_file():
            return path, read_json(path)
    return None, {}


def _write_mode(root: Path, vault: Path) -> tuple[str, list[str]]:
    state = personal_vault.state(root)
    current_rules = personal_vault.rules(vault)
    diagnostics = []
    if not state or Path(state.get("vault_root", "")).resolve() != vault.resolve():
        diagnostics.append("awaiting_target_writer：需先通过本工作区知识库入口连接此目标库并完成目标库入口适配")
        return "target_rules", diagnostics
    if state.get("write_mode") != "local":
        diagnostics.append("awaiting_target_writer：目标库规则要求通过目标库入口写入，需先完成入口适配")
        return "target_rules", diagnostics
    if current_rules != state.get("rules"):
        diagnostics.append("知识库规则已变化；先读取并确认目标库规则，再更新本地授权状态")
        return "target_rules", diagnostics
    marker_path, marker = _marker(vault)
    if not marker_path or marker.get("product") not in {"cy-vault", "dyb-vault"} or marker.get("rules") != current_rules:
        diagnostics.append("awaiting_target_writer：目标库缺少匹配的本地写入授权标记，需完成目标库入口适配")
        return "target_rules", diagnostics
    return "local", diagnostics


def _mapping(manifest: dict, vault: Path, workspace: Path) -> tuple[list[dict], list[dict], list[str]]:
    raw_files = manifest["files"]
    seen_sources, seen_targets = set(), set()
    files: list[dict] = []
    issues: list[str] = []
    for index, item in enumerate(raw_files):
        if not isinstance(item, dict):
            raise ValueError(f"files[{index}] 必须是对象")
        source = _safe_relative(item.get("source"), field=f"files[{index}].source")
        target = _safe_relative(item.get("target"), field=f"files[{index}].target")
        if source.startswith(".") or any(part.startswith(".") for part in PurePosixPath(source).parts):
            raise ValueError(f"不能把隐藏工具配置或缓存作为分类内容：{source}")
        if _is_root_exempt(source):
            raise ValueError(f"根规则或导航需保留原职责，不可作为普通内容移动：{source}")
        if PurePosixPath(target).parts[0] not in DOMAINS:
            raise ValueError(f"新目标必须位于 生活/、工作/ 或 学习/ 下：{target}")
        source_key, target_key = _key(source), _key(target)
        if source_key in seen_sources:
            raise ValueError(f"源路径重复：{source}")
        if target_key in seen_targets:
            raise ValueError(f"目标路径发生大小写不敏感碰撞：{target}")
        seen_sources.add(source_key)
        seen_targets.add(target_key)
        source_path = _no_symlink(vault, source)
        if not source_path.is_file():
            raise ValueError(f"待分类源文件不存在：{source}")
        if source_key != target_key:
            target_path = _no_symlink(vault, target)
            if target_path.exists():
                raise ValueError(f"目标文件已存在，拒绝覆盖：{target}")
        elif source != target:
            raise ValueError(f"仅大小写不同的路径当前不支持迁移：{source} → {target}")
        files.append({"source": source, "target": target, "before_sha256": digest(source_path)})

    for row in files:
        if _key(row["target"]) in seen_sources and _key(row["source"]) != _key(row["target"]):
            raise ValueError(f"目标与另一条源路径冲突：{row['target']}")

    replacements: list[dict] = []
    seen_replacement_targets: set[str] = set()
    for index, item in enumerate(manifest.get("replacements", [])):
        if not isinstance(item, dict):
            raise ValueError(f"replacements[{index}] 必须是对象")
        source = item.get("source")
        target = _safe_relative(item.get("target"), field=f"replacements[{index}].target")
        target_key = _key(target)
        if target_key in seen_replacement_targets:
            raise ValueError(f"prepared replacement 目标重复：{target}")
        seen_replacement_targets.add(target_key)
        expected = item.get("expected_sha256")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"replacements[{index}].source 必须是 workspace 文件")
        source_path = _workspace_file(workspace, source, field=f"replacements[{index}].source")
        if not source_path.is_file():
            raise ValueError(f"准备好的替换文件不存在或是软链接：{source}")
        allowed = target in RULES or target in ROOT_NAV
        if not allowed:
            raise ValueError(f"prepared replacement 仅允许根规则或导航文件：{target}")
        target_path = _no_symlink(vault, target)
        actual = digest(target_path) if target_path.is_file() else "-"
        if expected != actual:
            raise ValueError(f"替换目标预期 hash 不匹配：{target}")
        replacements.append({"source": source_path.relative_to(workspace).as_posix(), "target": target,
                             "source_sha256": digest(source_path), "before_sha256": actual})
    return files, replacements, issues


def _replacement_bytes(workspace: Path, replacement: dict) -> bytes:
    path = _workspace_file(workspace, replacement["source"], field="prepared replacement")
    if not path.is_file() or digest(path) != replacement["source_sha256"]:
        raise ValueError(f"准备好的替换文件在预览后已改变：{replacement['source']}")
    return path.read_bytes()


def _path_lookup(files: list[dict], identity_targets=()) -> dict[str, str]:
    lookup = {_key(row["source"]): row["target"] for row in files}
    lookup.update({_key(target): target for target in identity_targets})
    return lookup


def _resolve_link(raw: str, owner_old: str, owner_new: str, lookup: dict[str, str], *, wiki=False,
                  root_relative=False, encode=True) -> str:
    if not raw or raw.startswith(("#", "//")):
        return raw
    parsed = urlsplit(raw)
    if parsed.scheme or (parsed.netloc and not wiki):
        return raw
    path_part = unquote(parsed.path).replace("\\", "/")
    if not path_part:
        return raw
    if path_part.startswith("/"):
        candidate = path_part.lstrip("/")
    elif root_relative or wiki:
        candidate = posixpath.normpath(path_part)
    else:
        candidate = posixpath.normpath(posixpath.join(posixpath.dirname(owner_old), path_part))
    mapped = lookup.get(_key(candidate))
    if not mapped and wiki:
        # Bare Obsidian names may be relative to the current page; full vault
        # paths are resolved above against the library root first.
        relative_candidate = posixpath.normpath(posixpath.join(posixpath.dirname(owner_old), path_part))
        mapped = lookup.get(_key(relative_candidate))
    if not mapped:
        return raw
    if root_relative or wiki:
        new_rel = mapped
    else:
        new_rel = posixpath.relpath(mapped, posixpath.dirname(owner_new) or ".")
        if new_rel == ".":
            new_rel = posixpath.basename(mapped)
    encoded = quote(new_rel, safe="/.-_~") if encode else new_rel
    return urlunsplit(("", "", encoded, parsed.query, parsed.fragment))


def _rewrite_text(data: bytes, owner_old: str, owner_new: str, lookup: dict[str, str]) -> bytes:
    bom = data.startswith(b"\xef\xbb\xbf")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data
    # Markdown links and images. Angle destinations accept spaces and nested
    # parenthesized names; plain destinations accept one parenthesis level.
    markdown = re.compile(
        r"(?P<prefix>\]\(\s*)(?:(?P<angle_open><)(?P<angle_path>[^>]+)(?P<angle_close>>)|"
        r"(?P<plain_path>(?:[^\s()]|\([^()]*\))+))"
        r"(?P<title>\s+(?:\"[^\"]*\"|'[^']*'|\([^()]*\)))?(?P<space>\s*)(?P<close>\))"
    )
    def md_sub(match):
        angled = match.group("angle_path") is not None
        old = match.group("angle_path") if angled else match.group("plain_path")
        path = _resolve_link(old, owner_old, owner_new, lookup, encode=not angled)
        if angled:
            path = "<" + path + ">"
        return (match.group("prefix") + path + (match.group("title") or "")
                + match.group("space") + match.group("close"))
    text = markdown.sub(md_sub, text)

    # Obsidian-style wikilinks; aliases and heading suffixes are retained.
    wiki = re.compile(r"\[\[([^\]|#]+)([|#][^\]]*)?\]\]")
    def wiki_sub(match):
        old = match.group(1).strip()
        rewritten = _resolve_link(old, owner_old, owner_new, lookup, wiki=True, encode=False)
        return "[[" + rewritten + (match.group(2) or "") + "]]"
    text = wiki.sub(wiki_sub, text)

    # YAML front matter `sources:` scalars only. Preserve indentation/quotes/comments.
    lines = text.splitlines(keepends=True)
    in_frontmatter = bool(lines and lines[0].strip() == "---")
    if in_frontmatter:
        end = next((i for i in range(1, len(lines)) if lines[i].strip() in {"---", "..."}), None)
        if end is not None:
            base = 0
            active = False
            for i in range(1, end):
                line = lines[i]
                source_key = re.match(r"^([ \t]*)sources([ \t]*):([ \t]*)(.*?)(\r?\n)?$", line)
                if source_key:
                    active = True
                    base = len(source_key.group(1))
                    tail = source_key.group(4)
                    newline = source_key.group(5) or ""
                    if tail.strip().startswith("["):
                        token = re.compile(r"(?P<q>['\"]?)(?P<path>[^,\[\]\s'\"]+)(?P=q)")
                        def inline_sub(m):
                            repl = _resolve_link(m.group("path"), owner_old, owner_new, lookup,
                                                 root_relative=True, encode=False)
                            return m.group("q") + repl + m.group("q")
                        tail = token.sub(inline_sub, tail)
                        lines[i] = (source_key.group(1) + "sources" + source_key.group(2) + ":"
                                    + source_key.group(3) + tail + newline)
                        active = False
                    elif tail.strip():
                        active = False
                    continue
                if active:
                    indent = len(line) - len(line.lstrip(" "))
                    if line.strip() and indent <= base:
                        active = False
                    elif line.lstrip().startswith("-"):
                        match = re.match(r"^(\s*-\s*)(['\"]?)([^\s#,'\"]+)(['\"]?)(\s*(?:#.*)?(?:\r?\n)?)$", line)
                        if match:
                            path = _resolve_link(match.group(3), owner_old, owner_new, lookup,
                                                 root_relative=True, encode=False)
                            lines[i] = match.group(1) + match.group(2) + path + match.group(4) + match.group(5)
            text = "".join(lines)
    encoded = text.encode("utf-8")
    return (b"\xef\xbb\xbf" + encoded) if bom else encoded


def _entry_after(files: list[dict], source: str) -> str | None:
    row = next((r for r in files if _key(r["source"]) == _key(source)), None)
    return row["target"] if row else None


def _verify_inventory(vault: Path, preview: dict, journal: dict) -> None:
    actual, dirs, symlinks = _inventory(vault)
    if symlinks:
        raise ValueError("库内出现可见软链接，停止迁移：" + ", ".join(symlinks[:10]))
    expected = dict(preview["inventory"])
    mapped_paths = set()
    for row in preview["files"]:
        mapped_paths.update((row["source"], row["target"]))
        expected.pop(row["source"], None)
        expected.pop(row["target"], None)
    if set(actual) - mapped_paths != set(expected):
        added = sorted((set(actual) - mapped_paths) - set(expected), key=str.casefold)
        missing = sorted(set(expected) - set(actual), key=str.casefold)
        raise ValueError("知识库目录清单已变化；新增/缺失：" + repr((added[:10], missing[:10])))
    for rel, hashes in expected.items():
        if actual.get(rel) != hashes:
            raise ValueError(f"预览后文件内容发生变化：{rel}")
    for row in preview["files"]:
        source, target = row["source"], row["target"]
        if source == target:
            if actual.get(source) not in {row["before_sha256"], row["after_sha256"]}:
                raise ValueError(f"预览后文件内容发生变化：{source}")
            continue
        source_hash, target_hash = actual.get(source), actual.get(target)
        if source_hash not in {None, row["before_sha256"]} or target_hash not in {None, row["after_sha256"]}:
            raise ValueError(f"迁移源或目标在续办前发生变化：{source} → {target}")
        if source_hash is None and target_hash is None:
            raise ValueError(f"迁移源和目标都不存在：{source} → {target}")
    planned_dirs = set(preview["directories"])
    for row in preview["files"]:
        parent = PurePosixPath(row["target"]).parent
        while str(parent) not in {".", ""}:
            planned_dirs.add(parent.as_posix())
            parent = parent.parent
    cleanup = set(preview.get("cleanup_directories", []))
    required_dirs = set(preview["directories"]) - cleanup
    if not set(dirs).issubset(planned_dirs) or not required_dirs.issubset(set(dirs)):
        raise ValueError("知识库目录清单已变化")


def _planned_navigation(vault: Path, replacements: list[dict], lookup: dict[str, str], workspace: Path) -> dict | None:
    replacement = next((r for r in replacements if r["target"] == "index.md"), None)
    path = vault / "index.md"
    if replacement:
        original = _replacement_bytes(workspace, replacement)
        before = replacement["before_sha256"]
        source_name = replacement["source"]
    elif path.is_file():
        original = path.read_bytes()
        before = _sha(original)
        source_name = "index.md"
    else:
        return None
    data = _rewrite_text(original, source_name if source_name == "index.md" else "index.md", "index.md", lookup)
    return {"path": "index.md", "before_sha256": before, "after_sha256": _sha(data), "data": data,
            "replacement_source": replacement["source"] if replacement else None}


def _planned_catalog(vault: Path, rows: list[dict], lookup: dict[str, str]) -> dict | None:
    runtime = vault / _runtime_name(vault)
    path = runtime / "catalog.json"
    if not path.is_file():
        return None
    catalog = read_json(path)
    if not isinstance(catalog, dict):
        raise ValueError("知识库运行时 catalog.json 不是对象，需先通过目标入口修复")
    mapped = {_key(r["source"]): r for r in rows}
    updated = {}
    for key, raw in catalog.items():
        row = mapped.get(_key(key))
        if row and not isinstance(raw, dict):
            raise ValueError(f"运行时 catalog 项不是对象：{key}")
        new_key = row["target"] if row else key
        if isinstance(raw, dict):
            value = dict(raw)
            if row:
                value["target"] = new_key
                value["sha256"] = row["after_sha256"]
            sources = value.get("sources")
            if isinstance(sources, list):
                value["sources"] = [
                    _resolve_link(source, "", "", lookup, root_relative=True, encode=False)
                    if isinstance(source, str) else source
                    for source in sources
                ]
        else:
            value = raw
        if row:
            value["target"] = new_key
        if isinstance(value, dict) and row:
            value["sha256"] = row["after_sha256"]
        if _key(new_key) in {_key(x) for x in updated}:
            raise ValueError(f"运行时 catalog 目标发生碰撞：{new_key}")
        updated[new_key] = value
    before = digest(path)
    after_data = _json_bytes(updated)
    if _sha(after_data) == before:
        return None
    return {"path": f"{_runtime_name(vault)}/catalog.json", "before_sha256": before,
            "after_sha256": _sha(after_data), "data": after_data}


def _path_entries(preview: dict) -> list[dict]:
    entries = []
    for row in preview["files"]:
        if row["source"] != row["target"] or row["before_sha256"] != row["after_sha256"]:
            entries.append({"source": row["source"], "target": row["target"],
                            "before_sha256": row["before_sha256"], "after_sha256": row["after_sha256"]})
    nav = preview.get("navigation")
    if nav and nav["before_sha256"] != nav["after_sha256"]:
        entries.append({"source": "index.md", "target": "index.md",
                        "before_sha256": nav["before_sha256"], "after_sha256": nav["after_sha256"]})
    profile_before = preview.get("profile_entry_before")
    profile_target = preview.get("profile_entry_target")
    if profile_before and profile_target:
        try:
            profile_rel = Path(profile_before).expanduser().resolve().relative_to(
                Path(preview["vault_root"]).resolve()).as_posix()
        except ValueError:
            profile_rel = None
        profile_row = next((r for r in preview["files"] if profile_rel and _key(r["source"]) == _key(profile_rel)), None)
        if profile_row and (profile_row["source"] != profile_row["target"]
                            or profile_row["before_sha256"] != profile_row["after_sha256"]):
            entries.append({"source": "@profile", "target": profile_row["target"],
                            "before_sha256": profile_row["before_sha256"],
                            "after_sha256": profile_row["after_sha256"]})
    # Prepared replacements that replace rule prose are path-neutral; an index
    # replacement is included above through navigation.
    return entries


def _prepare_path_map(vault: Path, preview: dict) -> dict:
    path = vault / _runtime_name(vault) / PATH_MAP
    prior = read_json(path) if path.is_file() else {"schema": 1, "entries": []}
    if not isinstance(prior, dict) or not isinstance(prior.get("entries", []), list):
        raise ValueError("path-migrations.json 格式无效，需人工检查")
    new_entries = _path_entries(preview)
    entries = list(prior.get("entries", []))
    entries.extend(new_entries)
    result = {"schema": 1, "entries": entries, "updated_at": preview["created_at"]}
    return {"path": f"{_runtime_name(vault)}/{PATH_MAP}",
            "before_sha256": digest(path) if path.is_file() else "-",
            "after_sha256": _sha(_json_bytes(result)), "data": _json_bytes(result), "result": result}


def _backup_paths(preview: dict) -> list[str]:
    values = set()
    values.update(row["source"] for row in preview["files"])
    values.update(r["target"] for r in preview["replacements"] if r["before_sha256"] != "-")
    if preview.get("navigation") and preview["navigation"]["before_sha256"] != "-":
        values.add("index.md")
    if preview.get("catalog"):
        values.add(preview["catalog"]["path"])
    path_map = preview["path_map"]
    if path_map["before_sha256"] != "-":
        values.add(path_map["path"])
    if preview.get("marker_path") and preview.get("rules_replaced"):
        values.add(preview["marker_path"])
    return sorted(values, key=str.casefold)


def _cleanup_candidates(files: list[dict], directories: list[str]) -> list[str]:
    candidates = set()
    for row in files:
        parts = PurePosixPath(row["source"]).parts
        for length in range(1, len(parts)):
            parent = PurePosixPath(*parts[:length]).as_posix()
            if PurePosixPath(parent).parts[0] not in DOMAINS:
                candidates.add(parent)
    existing = {_key(path): path for path in directories}
    return sorted((existing[key] for key in candidates if key in existing),
                  key=lambda path: (-len(PurePosixPath(path).parts), path.casefold()))


def _migration_dir(root: Path, migration_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", migration_id):
        raise ValueError("migration_id 格式无效")
    workspace = _workspace(root)
    folder = personal_vault.home(workspace) / "migrations" / migration_id
    return _workspace_file(workspace, folder.relative_to(workspace), field="migration record")


def plan(root: Path, manifest: Path) -> dict:
    """Validate a full mapping and persist a reviewable preview in the workspace."""
    workspace = _workspace(root)
    manifest_path = _workspace_file(workspace, manifest, field="manifest")
    if not manifest_path.is_file():
        raise ValueError("manifest 必须是 workspace 内的普通文件")
    payload = _parse_manifest(manifest_path)
    vault = _vault_for(workspace)
    inventory, directories, symlinks = _inventory(vault)
    mapped, replacements, _ = _mapping(payload, vault, workspace)
    # Compare case-insensitively on Windows semantics even when tests run elsewhere.
    mapped_keys = {_key(row["source"]) for row in mapped}
    unmapped = sorted((p for p in inventory if _key(p) not in mapped_keys), key=str.casefold)
    if symlinks:
        raise ValueError("库内存在可见软链接，需先由 Agent 检查：" + ", ".join(symlinks[:10]))
    identity_targets = [name for name in sorted(ROOT_EXEMPT, key=str.casefold) if (vault / name).is_file()]
    lookup = _path_lookup(mapped, identity_targets)
    for row in mapped:
        path = vault / row["source"]
        row["after_sha256"] = _sha(_rewrite_text(path.read_bytes(), row["source"], row["target"], lookup))
    # Prepared root rules/navigation are explicit replacements. Their expected
    # hashes refer to the currently installed library file.
    for replacement in replacements:
        target_path = vault / replacement["target"]
        data = _replacement_bytes(workspace, replacement)
        data = _rewrite_text(data, replacement["target"], replacement["target"], lookup)
        replacement["after_sha256"] = _sha(data)
    nav = _planned_navigation(vault, replacements, lookup, workspace)
    if nav:
        if nav.get("replacement_source"):
            prepared = next(r for r in replacements if r["source"] == nav["replacement_source"])
            raw = _replacement_bytes(workspace, prepared)
        else:
            raw = (vault / "index.md").read_bytes()
        nav["data"] = _rewrite_text(raw, "index.md", "index.md", lookup)
        nav["after_sha256"] = _sha(nav["data"])
    catalog = _planned_catalog(vault, mapped, lookup)
    state = personal_vault.state(workspace)
    profile_entry = state.get("profile_entry")
    profile_target = None
    profile_inside = False
    profile_external = False
    profile_exists = False
    profile_rel = None
    if profile_entry:
        profile_raw_path = Path(profile_entry).expanduser()
        profile_exists = profile_raw_path.exists()
        if profile_raw_path.is_symlink():
            raise ValueError("profile_entry 不能指向软链接")
        profile_path = profile_raw_path.resolve()
        try:
            profile_rel = profile_path.relative_to(vault).as_posix()
            profile_inside = True
        except ValueError:
            profile_rel = None
            profile_external = True
        if profile_rel:
            profile_target = _entry_after(mapped, profile_rel)
            if (profile_target is None and not profile_exists
                    and PurePosixPath(profile_rel).parts[0] in DOMAINS):
                # Current three-domain profiles are created on first real answer.
                # An absent placeholder already under a domain has no content to map.
                profile_target = profile_rel
    profile_row = next((row for row in mapped if profile_rel and _key(row["source"]) == _key(profile_rel)), None)
    marker_path, marker = _marker(vault)
    migration_id = uuid.uuid4().hex
    mode, mode_diagnostics = _write_mode(workspace, vault)
    pending = [t for t in personal_vault.transactions(workspace) if t.get("status") != "saved"]
    diagnostics = list(mode_diagnostics)
    if unmapped:
        diagnostics.append("needs_classification：仍有未映射内容文件")
    if profile_entry and profile_target is None and profile_inside:
        diagnostics.append("profile_entry_unmapped：知识库个人档案入口没有映射到生活/、工作/ 或学习/")
    if profile_external:
        diagnostics.append("profile_entry_external：个人档案入口位于知识库外，需由目标库入口适配后再迁移")
    if pending:
        diagnostics.append("pending_writes：先处理知识库待写入任务，不能移动其目标")
    preview = {
        "schema": 1, "migration_id": migration_id, "created_at": now(), "workspace_root": str(workspace),
        "manifest_path": str(manifest_path), "manifest_sha256": digest(manifest_path),
        "vault_root": str(vault), "write_mode": mode, "rules_before": personal_vault.rules(vault),
        "marker_path": marker_path.relative_to(vault).as_posix() if marker_path else None,
        "marker_before_sha256": digest(marker_path) if marker_path else "-",
        "marker_before": marker, "inventory": inventory, "directories": directories,
        "files": mapped, "replacements": replacements, "navigation": None, "catalog": None,
        "path_map": None, "identity_targets": identity_targets,
        "unmapped": unmapped, "pending": pending,
        "profile_entry_before": profile_entry, "profile_entry_target": profile_target,
        "profile_entry_inside": profile_inside,
        "profile_entry_external": profile_external,
        "profile_entry_exists": profile_exists,
        "profile_file_source": profile_row["source"] if profile_row else None,
        "profile_sha256_before_present": "profile_sha256" in state,
        "profile_sha256_before": state.get("profile_sha256"),
        "profile_sha256_after": profile_row["after_sha256"] if profile_row else state.get("profile_sha256"),
        "cleanup_directories": _cleanup_candidates(mapped, directories),
        "diagnostics": diagnostics,
    }
    preview["navigation"] = {k: v for k, v in nav.items() if k != "data"} if nav else None
    preview["catalog"] = {k: v for k, v in catalog.items() if k not in {"data", "result"}} if catalog else None
    preview["path_map"] = {k: v for k, v in _prepare_path_map(vault, preview).items() if k not in {"data", "result"}}
    preview["workspace_root"] = str(workspace)
    # Root index replacement is also a normal replacement operation.
    rules_replaced = any(r["target"] in RULES for r in replacements)
    preview["rules_replaced"] = rules_replaced
    preview["rules_after"] = dict(preview["rules_before"])
    for replacement in replacements:
        if replacement["target"] in RULES:
            preview["rules_after"][replacement["target"]] = replacement["after_sha256"]
    for replacement in replacements:
        if replacement["target"] == "index.md" and nav:
            replacement["after_sha256"] = nav["after_sha256"]
    preview["replacements"] = replacements
    if rules_replaced and marker_path:
        marker_after = dict(marker)
        marker_after["rules"] = preview["rules_after"]
        preview["marker_after_sha256"] = _sha(_json_bytes(marker_after))
    else:
        preview["marker_after_sha256"] = preview["marker_before_sha256"]
    preview["backup_paths"] = _backup_paths(preview)
    preview["backup_hashes"] = {}
    for rel in preview["backup_paths"]:
        backup_source = _no_symlink(vault, rel)
        preview["backup_hashes"][rel] = digest(backup_source) if backup_source.is_file() else "-"
    profile_blocked = profile_external or (profile_entry and profile_target is None)
    preview["status"] = "ready" if not unmapped and not pending and mode == "local" and not profile_blocked else (
        "needs_classification" if unmapped else "awaiting_target_writer" if mode != "local" else
        "blocked_pending_writes" if pending else "blocked_profile_entry")
    folder = _migration_dir(workspace, migration_id)
    folder.mkdir(parents=True, exist_ok=False)
    write_json(folder / "preview.json", preview)
    write_json(folder / "journal.json", {"status": "previewed", "operations": {}, "backup": {"status": "not_started"},
                                          "events": [{"at": now(), "event": "preview_created"}]})
    return {"status": preview["status"], "id": migration_id, "migration_id": migration_id,
            "preview": str(folder / "preview.json"),
            "unmapped": unmapped, "diagnostics": diagnostics, "files": len(mapped), "replacements": len(replacements)}


def _read_record(root: Path, migration_id: str) -> tuple[Path, dict, dict]:
    folder = _migration_dir(root, migration_id)
    preview = read_json(folder / "preview.json")
    journal = read_json(folder / "journal.json")
    return folder, preview, journal


def _save_journal(path: Path, journal: dict, event: str) -> None:
    journal.setdefault("events", []).append({"at": now(), "event": event})
    write_json(path, journal)


def _runtime_lock(vault: Path) -> Path:
    legacy = vault / ".dyb-vault-runtime"
    current = vault / RUNTIME
    chosen = legacy if legacy.exists() or _is_reparse(legacy) else current
    if _is_reparse(chosen):
        raise ValueError(f"知识库运行时目录不能是软链接或目录联接：{chosen.name}")
    return chosen


def _runtime_name(vault: Path) -> str:
    return _runtime_lock(vault).name


def _gate_apply(root: Path, preview: dict, vault: Path) -> None:
    if preview["unmapped"]:
        raise ValueError("迁移预览仍有未分类内容，先补全 manifest 并重新预览")
    if preview["pending"]:
        raise ValueError("预览时存在待处理知识库写入；处理完成后重新预览")
    if preview.get("profile_entry_inside") and not preview.get("profile_entry_target"):
        raise ValueError("profile_entry_unmapped：先把知识库档案入口映射到三域内")
    if preview.get("profile_entry_external"):
        raise ValueError("profile_entry_external：个人档案入口位于知识库外，需由目标库入口适配后再迁移")
    if preview["write_mode"] != "local":
        raise ValueError("awaiting_target_writer：当前规则要求目标库入口适配，不能绕过发布入口写入")
    state = personal_vault.state(root)
    current_rules = personal_vault.rules(vault)
    if state.get("write_mode") != "local" or Path(state.get("vault_root", "")).resolve() != vault.resolve():
        raise ValueError("awaiting_target_writer：当前知识库规则或本地授权状态已改变")
    allowed_rule_states = [preview["rules_before"]]
    if preview.get("rules_replaced"):
        allowed_rule_states.append(preview["rules_after"])
    marker_path, marker = _marker(vault)
    allowed_per_rule = {name: {preview["rules_before"].get(name)} for name in RULES}
    for replacement in preview["replacements"]:
        if replacement["target"] in RULES:
            allowed_per_rule[replacement["target"]].add(replacement["after_sha256"])
    rules_match_confirmed_progress = all(current_rules.get(name) in hashes
                                         for name, hashes in allowed_per_rule.items())
    if (not rules_match_confirmed_progress or not marker_path
            or marker.get("product") not in {"cy-vault", "dyb-vault"}
            or marker.get("rules") not in allowed_rule_states):
        raise ValueError("awaiting_target_writer：当前知识库规则或本地授权状态已改变")
    configured_vault = config(root).get("vault_root")
    if not configured_vault or Path(configured_vault).expanduser().resolve() != vault.resolve():
        raise ValueError("workspace 配置中的知识库路径已改变；重新生成迁移预览")
    if state.get("rules") not in allowed_rule_states:
        raise ValueError("workspace 知识库授权 hash 已改变；重新生成迁移预览")
    if preview.get("profile_entry_target"):
        expected_profile = str(vault / Path(*PurePosixPath(preview["profile_entry_target"]).parts))
        if state.get("profile_entry") not in {preview.get("profile_entry_before"), expected_profile}:
            raise ValueError("workspace profile_entry 在预览后已改变")
    if preview.get("profile_file_source"):
        allowed_profile_hashes = {preview.get("profile_sha256_before"), preview.get("profile_sha256_after")}
        if state.get("profile_sha256") not in allowed_profile_hashes:
            raise ValueError("workspace profile_sha256 在预览后已改变")
    if digest(Path(preview["manifest_path"])) != preview["manifest_sha256"]:
        raise ValueError("manifest 在预览后已改变；重新生成迁移预览")
    if any(t.get("status") != "saved" for t in personal_vault.transactions(root)):
        raise ValueError("仍有待处理知识库写入；先处理后再迁移")


def _backup(folder: Path, vault: Path, preview: dict, journal: dict, journal_path: Path) -> None:
    date = datetime.now().strftime("%Y-%m-%d")
    backup = vault / ".trash" / f"{date}_迁移前_{preview['migration_id']}"
    if journal.get("backup", {}).get("path"):
        backup = Path(journal["backup"]["path"])
    else:
        if backup.exists():
            raise ValueError("迁移备份目录已存在，拒绝覆盖：" + str(backup))
        _no_symlink(vault, backup.relative_to(vault).as_posix())
        backup.mkdir(parents=True, exist_ok=False)
        journal["backup"] = {"path": str(backup), "status": "copying", "files": {}}
        _save_journal(journal_path, journal, "backup_started")
    try:
        backup_rel = backup.absolute().relative_to(vault)
    except ValueError:
        raise ValueError("迁移备份必须位于知识库内的 .trash") from None
    backup_parts = backup_rel.parts
    if (len(backup_parts) != 2 or backup_parts[0] != ".trash"
            or not re.fullmatch(rf"\d{{4}}-\d{{2}}-\d{{2}}_迁移前_{preview['migration_id']}", backup_parts[1])):
        raise ValueError("迁移备份路径与当前 migration_id 不符")
    backup = _no_symlink(vault, backup_rel.as_posix())
    if journal.get("backup", {}).get("status") == "complete":
        saved_files = journal["backup"].get("files", {})
        for rel, expected_hash in preview["backup_hashes"].items():
            if expected_hash == "-":
                if rel in saved_files:
                    raise ValueError("备份日志与预览原件清单不符：" + rel)
                continue
            meta = saved_files.get(rel)
            if not meta:
                raise ValueError("完整备份缺少预览原件：" + rel)
            saved = backup / Path(*PurePosixPath(meta["path"]).parts)
            if not saved.is_file() or digest(saved) != expected_hash or meta.get("sha256") != expected_hash:
                raise ValueError("原始迁移备份 hash 校验失败：" + rel)
        return
    for rel in preview["backup_paths"]:
        source = _no_symlink(vault, rel)
        expected_hash = preview["backup_hashes"].get(rel, "-")
        actual_hash = digest(source) if source.is_file() else "-"
        if actual_hash != expected_hash:
            raise ValueError("完整备份前原件已改变，拒绝备份新内容：" + rel)
        if expected_hash == "-":
            # New path-migrations target and new replacement targets have no old bytes.
            continue
        saved_hash = expected_hash
        relative_backup = Path("files") / Path(*PurePosixPath(rel).parts)
        target = backup / relative_backup
        if target.is_file():
            if digest(target) != saved_hash:
                raise ValueError("备份文件与原件 hash 不符，保留现场：" + rel)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + ".partial")
            with temporary.open("wb") as handle:
                handle.write(source.read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
            if _sha(temporary.read_bytes()) != saved_hash:
                raise ValueError("备份读回校验失败：" + rel)
            os.replace(temporary, target)
        journal["backup"]["files"][rel] = {"path": relative_backup.as_posix(), "sha256": saved_hash}
        _save_journal(journal_path, journal, "backup_file:" + rel)
    journal["backup"]["status"] = "complete"
    _save_journal(journal_path, journal, "backup_complete")


def _backup_file(vault: Path, journal: dict, rel: str) -> bytes | None:
    meta = journal.get("backup", {}).get("files", {}).get(rel)
    if not meta:
        return None
    path = Path(journal["backup"]["path"]) / Path(*PurePosixPath(meta["path"]).parts)
    data = path.read_bytes()
    if _sha(data) != meta["sha256"]:
        raise ValueError("迁移备份内容损坏：" + rel)
    return data


def _atomic_new(path: Path, data: bytes, migration_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".cy-vault-migration-{migration_id}-{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if _sha(temporary.read_bytes()) != _sha(data):
            raise ValueError("临时写入读回校验失败：" + str(path))
        os.rename(temporary, path)  # refuses an existing destination on Windows
    finally:
        if temporary.exists():
            temporary.unlink()


def _map_data(row: dict, vault: Path, lookup: dict[str, str]) -> bytes:
    source = _no_symlink(vault, row["source"])
    data = source.read_bytes()
    if _sha(data) == row["after_sha256"] and row["source"] == row["target"]:
        return data
    if _sha(data) != row["before_sha256"]:
        raise ValueError(f"待迁移源文件 hash 已改变：{row['source']}")
    data = _rewrite_text(data, row["source"], row["target"], lookup)
    if _sha(data) != row["after_sha256"]:
        raise ValueError(f"重建内容 hash 与预览不符：{row['source']}")
    return data


def _apply_file(row: dict, vault: Path, journal: dict, journal_path: Path, migration_id: str,
                lookup: dict[str, str]) -> None:
    key = "file:" + row["source"]
    operation = journal.setdefault("operations", {}).setdefault(key, {"status": "planned", "steps": []})
    source = _no_symlink(vault, row["source"])
    target = _no_symlink(vault, row["target"])
    before, after = row["before_sha256"], row["after_sha256"]
    if row["source"] == row["target"]:
        actual = digest(source) if source.is_file() else "-"
        if actual == after:
            operation["status"] = "done"
            return
        if actual != before:
            raise ValueError(f"迁移目标已被修改，停止覆盖：{row['source']}")
        operation["steps"].append({"step": "rewrite", "before_location": row["source"],
                                   "before_sha256": actual, "status": "started"})
        operation["status"] = "rewriting"
        _save_journal(journal_path, journal, "rewrite_started:" + row["source"])
        data = _map_data(row, vault, lookup)
        personal_vault.atomic(source, data, before)
        operation["steps"][-1].update(status="done", after_location=row["target"], after_sha256=after)
        operation["status"] = "done"
        _save_journal(journal_path, journal, "rewrite_complete:" + row["source"])
        return

    source_hash = digest(source) if source.is_file() else "-"
    target_hash = digest(target) if target.is_file() else "-"
    if target_hash == after:
        if source_hash == before:
            operation["status"] = "target_written"
            operation["steps"].append({"step": "destination_readback", "before_location": row["source"],
                                       "before_sha256": before, "after_location": row["target"],
                                       "after_sha256": after, "status": "done"})
            _save_journal(journal_path, journal, "recovered_destination:" + row["source"])
        elif source_hash != "-":
            raise ValueError(f"迁移源文件在目标写入后发生变化，保留现场：{row['source']}")
        if source_hash == before:
            source.unlink()
            operation["steps"].append({"step": "source_remove", "before_location": row["source"],
                                       "before_sha256": before, "after_location": None,
                                       "after_sha256": None, "status": "done"})
            _save_journal(journal_path, journal, "source_removed:" + row["source"])
        operation["status"] = "done"
        _save_journal(journal_path, journal, "file_complete:" + row["source"])
        return
    if source_hash != before or target_hash != "-":
        raise ValueError(f"迁移源或目标已被修改，停止覆盖：{row['source']} → {row['target']}")
    operation["steps"].append({"step": "destination_write", "before_location": row["source"],
                               "before_sha256": before, "after_location": row["target"],
                               "after_sha256": after, "status": "started"})
    operation["status"] = "writing_target"
    _save_journal(journal_path, journal, "destination_write_started:" + row["source"])
    data = _map_data(row, vault, lookup)
    _atomic_new(target, data, migration_id)
    if digest(target) != after:
        raise ValueError(f"迁移目标读回 hash 不符：{row['target']}")
    operation["status"] = "target_written"
    operation["steps"][-1]["status"] = "done"
    _save_journal(journal_path, journal, "destination_written:" + row["target"])
    if digest(source) != before:
        raise ValueError(f"删除源文件前 hash 已改变，保留源与目标现场：{row['source']}")
    source.unlink()
    operation["steps"].append({"step": "source_remove", "before_location": row["source"],
                               "before_sha256": before, "after_location": None, "after_sha256": None,
                               "status": "done"})
    operation["status"] = "done"
    _save_journal(journal_path, journal, "file_complete:" + row["source"])


def _apply_write(vault: Path, rel: str, before_hash: str, after_hash: str, data: bytes,
                 journal: dict, journal_path: Path, migration_id: str, *, key: str) -> None:
    path = _no_symlink(vault, rel)
    actual = digest(path) if path.is_file() else "-"
    if actual == after_hash:
        journal.setdefault("operations", {}).setdefault(key, {"status": "done", "steps": []})["status"] = "done"
        return
    if actual != before_hash:
        raise ValueError(f"替换目标在迁移中被修改，保留现场：{rel}")
    operation = journal.setdefault("operations", {}).setdefault(key, {"status": "planned", "steps": []})
    operation["steps"].append({"step": "replace", "before_location": rel, "before_sha256": before_hash,
                               "after_location": rel, "after_sha256": after_hash, "status": "started"})
    operation["status"] = "writing"
    _save_journal(journal_path, journal, "replace_started:" + rel)
    if before_hash == "-":
        _atomic_new(path, data, migration_id)
    else:
        personal_vault.atomic(path, data, before_hash)
    if digest(path) != after_hash:
        raise ValueError(f"替换文件读回 hash 不符：{rel}")
    operation["steps"][-1]["status"] = "done"
    operation["status"] = "done"
    _save_journal(journal_path, journal, "replace_complete:" + rel)


def _cleanup_old_directories(vault: Path, preview: dict, journal: dict, journal_path: Path) -> None:
    statuses = journal.setdefault("directories", {})
    for rel in preview.get("cleanup_directories", []):
        path = _no_symlink(vault, rel)
        if not path.exists():
            statuses[rel] = {"status": "removed", "before_exists": True, "after_exists": False}
            _save_journal(journal_path, journal, "old_directory_already_removed:" + rel)
            continue
        if not path.is_dir():
            raise ValueError(f"旧内容目录路径被非目录占用：{rel}")
        try:
            path.rmdir()  # rmdir only: never recurse into remaining content
        except OSError:
            statuses[rel] = {"status": "kept_nonempty", "before_exists": True, "after_exists": True}
        else:
            statuses[rel] = {"status": "removed", "before_exists": True, "after_exists": False}
        _save_journal(journal_path, journal, "old_directory_cleanup:" + rel)


def _update_runtime_state(root: Path, vault: Path, preview: dict) -> None:
    state = personal_vault.state(root)
    if not state:
        return
    if preview.get("profile_entry_target"):
        state["profile_entry"] = str(vault / Path(*PurePosixPath(preview["profile_entry_target"]).parts))
    if preview.get("profile_file_source"):
        state["profile_sha256"] = preview["profile_sha256_after"]
    if preview.get("rules_replaced"):
        state["rules"] = personal_vault.rules(vault)
    personal_vault.save(state, root)


def _update_marker(vault: Path, preview: dict, journal: dict, journal_path: Path, migration_id: str) -> None:
    if not preview.get("rules_replaced") or not preview.get("marker_path"):
        return
    rel = preview["marker_path"]
    path = vault / rel
    actual = digest(path) if path.is_file() else "-"
    if actual == preview["marker_after_sha256"]:
        return
    if actual != preview["marker_before_sha256"]:
        raise ValueError("本地授权标记在预览后发生变化，拒绝覆盖")
    current = read_json(path)
    if current.get("rules") == personal_vault.rules(vault):
        if actual != preview["marker_after_sha256"]:
            raise ValueError("本地授权标记内容与迁移预期不符")
        return
    current["rules"] = personal_vault.rules(vault)
    data = _json_bytes(current)
    _apply_write(vault, rel, preview["marker_before_sha256"], preview["marker_after_sha256"], data,
                 journal, journal_path, migration_id, key="marker:" + rel)


def apply(root: Path, migration_id: str, evidence: str) -> dict:
    """Apply a reviewed preview. `evidence` records the concrete confirmation."""
    workspace = _workspace(root)
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError("迁移需要引用用户明确确认依据")
    folder, preview, _ = _read_record(workspace, migration_id)
    vault = Path(preview["vault_root"]).resolve()
    try:
        with artifact_lock(_runtime_lock(vault)):
            # Journal state is mutable: always reload it after acquiring the shared
            # library lock so a losing contender cannot overwrite the winner's work.
            folder, preview, journal = _read_record(workspace, migration_id)
            journal_path = folder / "journal.json"
            if journal["status"] == "complete":
                return {"status": "complete", "migration_id": migration_id,
                        "backup": journal.get("backup", {}).get("path"), "resumed": True}
            try:
                _gate_apply(workspace, preview, vault)
                _verify_inventory(vault, preview, journal)
                if journal.get("evidence") is None:
                    journal["evidence"] = evidence.strip()
                    journal["status"] = "applying"
                    _save_journal(journal_path, journal, "apply_confirmed")
                _backup(folder, vault, preview, journal, journal_path)
                lookup = _path_lookup(preview["files"], preview.get("identity_targets", []))
                for row in preview["files"]:
                    _apply_file(row, vault, journal, journal_path, migration_id, lookup)
                # Prepared replacements are read again and hash checked after preview.
                for replacement in preview["replacements"]:
                    prepared = _replacement_bytes(workspace, replacement)
                    data = _rewrite_text(prepared, replacement["target"], replacement["target"], lookup)
                    _apply_write(vault, replacement["target"], replacement["before_sha256"],
                                 replacement["after_sha256"], data, journal, journal_path, migration_id,
                                 key="replacement:" + replacement["target"])
                nav = preview.get("navigation")
                if nav:
                    replacement = next((r for r in preview["replacements"] if r["target"] == "index.md"), None)
                    if replacement:
                        data = _rewrite_text(_replacement_bytes(workspace, replacement), "index.md", "index.md", lookup)
                        before = replacement["before_sha256"]
                        after = replacement["after_sha256"]
                    else:
                        source = vault / "index.md"
                        data = _rewrite_text(source.read_bytes(), "index.md", "index.md", lookup)
                        before, after = nav["before_sha256"], nav["after_sha256"]
                    _apply_write(vault, "index.md", before, after, data, journal, journal_path, migration_id,
                                 key="navigation:index.md")
                catalog = preview.get("catalog")
                if catalog:
                    data = _planned_catalog(vault, preview["files"], lookup)
                    if data is None:
                        if digest(vault / catalog["path"]) != catalog["after_sha256"]:
                            raise ValueError("运行时 catalog 与预览不符")
                    else:
                        _apply_write(vault, catalog["path"], catalog["before_sha256"], catalog["after_sha256"],
                                     data["data"], journal, journal_path, migration_id,
                                     key="catalog:" + catalog["path"])
                path_map_data = _prepare_path_map(vault, preview)
                path_map_path = vault / path_map_data["path"]
                if not (path_map_path.is_file()
                        and digest(path_map_path) == preview["path_map"]["after_sha256"]):
                    if _sha(path_map_data["data"]) != preview["path_map"]["after_sha256"]:
                        raise ValueError("path-migrations 预览后发生变化，保留现场并重新检查")
                    _apply_write(vault, path_map_data["path"], preview["path_map"]["before_sha256"],
                                 preview["path_map"]["after_sha256"], path_map_data["data"],
                                 journal, journal_path, migration_id, key="path_map:" + PATH_MAP)
                _update_marker(vault, preview, journal, journal_path, migration_id)
                _update_runtime_state(workspace, vault, preview)
                _cleanup_old_directories(vault, preview, journal, journal_path)
                for row in preview["files"]:
                    target = _no_symlink(vault, row["target"])
                    if not target.is_file() or digest(target) != row["after_sha256"]:
                        raise ValueError("迁移后目标读回 hash 不符：" + row["target"])
                if digest(path_map_path) != preview["path_map"]["after_sha256"]:
                    raise ValueError("迁移映射文件读回 hash 不符")
                _verify_inventory(vault, preview, journal)
                journal["status"] = "complete"
                journal["completed_at"] = now()
                _save_journal(journal_path, journal, "migration_complete")
                return {"status": "complete", "migration_id": migration_id,
                        "backup": journal.get("backup", {}).get("path"), "path_migrations": str(path_map_path)}
            except (OSError, ValueError, RuntimeError) as exc:
                journal["status"] = "interrupted" if journal.get("backup", {}).get("status") == "complete" else journal.get("status", "previewed")
                journal["error"] = str(exc)
                _save_journal(journal_path, journal, "apply_interrupted")
                return {"status": "interrupted", "migration_id": migration_id, "error": str(exc),
                        "backup": journal.get("backup", {}).get("path")}
    except ArtifactBusyError as exc:
        # A competing writer owns the library lock. Do not persist the stale
        # journal loaded before the lock attempt; the owner may be progressing.
        return {"status": "busy", "migration_id": migration_id, "error": str(exc)}


def _restore_file(vault: Path, backup_root: Path, journal: dict, rel: str, *, expected_after: str | None,
                  remove_if_absent_before: bool = False) -> str | None:
    path = _no_symlink(vault, rel)
    actual = digest(path) if path.is_file() else "-"
    original = _backup_file(vault, journal, rel)
    before = _sha(original) if original is not None else "-"
    if actual == before:
        return None
    if expected_after is not None and actual != expected_after:
        return f"{rel} 已被迁移后修改（当前 {actual}，预期 {expected_after}），保留现场"
    if original is None:
        if actual == "-":
            return None
        if actual != expected_after:
            return f"{rel} 当前内容不属于本次迁移，保留现场"
        path.unlink()
        return None
    if actual == "-":
        _atomic_new(path, original, "rollback")
    else:
        personal_vault.atomic(path, original, actual)
    return None


def _rollback_state(root: Path, preview: dict) -> list[str]:
    state = personal_vault.state(root)
    if not state:
        return []
    conflicts = []
    if preview.get("profile_entry_target"):
        expected = str(Path(preview["vault_root"]) / Path(*PurePosixPath(preview["profile_entry_target"]).parts))
        if state.get("profile_entry") == expected:
            state["profile_entry"] = preview["profile_entry_before"]
        elif state.get("profile_entry") != preview["profile_entry_before"]:
            conflicts.append("workspace state.profile_entry 已被后续修改，未回退")
    if preview.get("profile_file_source"):
        current_profile_hash = state.get("profile_sha256")
        if current_profile_hash == preview.get("profile_sha256_after"):
            if preview.get("profile_sha256_before_present"):
                state["profile_sha256"] = preview.get("profile_sha256_before")
            else:
                state.pop("profile_sha256", None)
        elif current_profile_hash != preview.get("profile_sha256_before"):
            conflicts.append("workspace state.profile_sha256 已被后续修改，未回退")
    if preview.get("rules_replaced"):
        current_rules = personal_vault.rules(Path(preview["vault_root"]))
        if current_rules == preview["rules_before"] and state.get("rules") == preview["rules_after"]:
            state["rules"] = preview["rules_before"]
        elif state.get("rules") != preview["rules_before"]:
            conflicts.append("workspace state.rules 已被后续修改，未回退")
    if not conflicts:
        personal_vault.save(state, root)
    return conflicts


def _rollback_preflight(root: Path, vault: Path, preview: dict) -> list[str]:
    conflicts = []
    for row in preview["files"]:
        source = _no_symlink(vault, row["source"])
        target = _no_symlink(vault, row["target"])
        if row["source"] == row["target"]:
            actual = digest(source) if source.is_file() else "-"
            if actual not in {row["before_sha256"], row["after_sha256"]}:
                conflicts.append(f"{row['source']} 已被迁移后修改（当前 {actual}），保留现场")
            continue
        source_hash = digest(source) if source.is_file() else "-"
        target_hash = digest(target) if target.is_file() else "-"
        if source_hash not in {"-", row["before_sha256"]}:
            conflicts.append(f"{row['source']} 已被迁移后修改（当前 {source_hash}），保留现场")
        if target_hash not in {"-", row["after_sha256"]}:
            conflicts.append(f"{row['target']} 已被迁移后修改（当前 {target_hash}），保留现场")
        if source_hash == "-" and target_hash == "-":
            conflicts.append(f"{row['source']} 与 {row['target']} 均不存在，需人工恢复")

    expected_assets = [(r["target"], r["before_sha256"], r["after_sha256"])
                       for r in preview["replacements"]]
    nav = preview.get("navigation")
    if nav and not any(r["target"] == "index.md" for r in preview["replacements"]):
        expected_assets.append(("index.md", nav["before_sha256"], nav["after_sha256"]))
    if preview.get("catalog"):
        c = preview["catalog"]
        expected_assets.append((c["path"], c["before_sha256"], c["after_sha256"]))
    p = preview["path_map"]
    expected_assets.append((p["path"], p["before_sha256"], p["after_sha256"]))
    if preview.get("rules_replaced") and preview.get("marker_path"):
        expected_assets.append((preview["marker_path"], preview["marker_before_sha256"],
                                preview["marker_after_sha256"]))
    for rel, before, after in expected_assets:
        path = _no_symlink(vault, rel)
        actual = digest(path) if path.is_file() else "-"
        if actual not in {before, after}:
            conflicts.append(f"{rel} 已被迁移后修改（当前 {actual}），保留现场")

    state = personal_vault.state(root)
    if preview.get("profile_entry_target"):
        after_profile = str(vault / Path(*PurePosixPath(preview["profile_entry_target"]).parts))
        if state.get("profile_entry") not in {preview["profile_entry_before"], after_profile}:
            conflicts.append("workspace state.profile_entry 已被后续修改，保留现场")
    if preview.get("profile_file_source"):
        if state.get("profile_sha256") not in {
                preview.get("profile_sha256_before"), preview.get("profile_sha256_after")}:
            conflicts.append("workspace state.profile_sha256 已被后续修改，保留现场")
    if (preview.get("rules_replaced") and state.get("rules") != preview["rules_before"]
            and state.get("rules") != preview["rules_after"]):
        conflicts.append("workspace state.rules 已被后续修改，保留现场")
    return conflicts


def rollback(root: Path, migration_id: str) -> dict:
    """Restore the affected files from the migration backup without clobbering edits."""
    workspace = _workspace(root)
    _, preview, _ = _read_record(workspace, migration_id)
    vault = Path(preview["vault_root"]).resolve()
    try:
        with artifact_lock(_runtime_lock(vault)):
            # Reload after locking to avoid using another process's stale journal.
            folder, preview, journal = _read_record(workspace, migration_id)
            if journal.get("backup", {}).get("status") != "complete":
                if journal.get("status") == "previewed":
                    return {"status": "not_applied", "migration_id": migration_id, "conflicts": []}
                return {"status": "blocked", "migration_id": migration_id,
                        "conflicts": ["完整备份尚未完成，无法安全回退"]}
            journal_path = folder / "journal.json"
            conflicts = _rollback_preflight(workspace, vault, preview)
            if conflicts:
                journal["status"] = "rolled_back_with_conflicts"
                journal["rollback_at"] = now()
                journal["rollback_conflicts"] = conflicts
                _save_journal(journal_path, journal, "rollback_conflict")
                return {"status": journal["status"], "migration_id": migration_id, "conflicts": conflicts,
                        "backup": journal["backup"]["path"]}
            # Reverse operation order: generated indexes and maps, then moved files.
            for replacement in reversed(preview["replacements"]):
                rel = replacement["target"]
                conflict = _restore_file(vault, Path(journal["backup"]["path"]), journal, rel,
                                          expected_after=replacement["after_sha256"])
                if conflict:
                    conflicts.append(conflict)
            if preview.get("rules_replaced") and preview.get("marker_path"):
                conflict = _restore_file(vault, Path(journal["backup"]["path"]), journal,
                                          preview["marker_path"], expected_after=preview["marker_after_sha256"])
                if conflict:
                    conflicts.append(conflict)
            nav = preview.get("navigation")
            if nav and not any(r["target"] == "index.md" for r in preview["replacements"]):
                conflict = _restore_file(vault, Path(journal["backup"]["path"]), journal, "index.md",
                                          expected_after=nav["after_sha256"])
                if conflict:
                    conflicts.append(conflict)
            catalog = preview.get("catalog")
            if catalog:
                conflict = _restore_file(vault, Path(journal["backup"]["path"]), journal, catalog["path"],
                                          expected_after=catalog["after_sha256"])
                if conflict:
                    conflicts.append(conflict)
            path_map = preview["path_map"]
            conflict = _restore_file(vault, Path(journal["backup"]["path"]), journal, path_map["path"],
                                      expected_after=path_map["after_sha256"])
            if conflict:
                conflicts.append(conflict)
            for row in reversed(preview["files"]):
                source, target = row["source"], row["target"]
                before, after = row["before_sha256"], row["after_sha256"]
                if source == target:
                    conflict = _restore_file(vault, Path(journal["backup"]["path"]), journal, source,
                                              expected_after=after)
                    if conflict:
                        conflicts.append(conflict)
                    continue
                target_path = _no_symlink(vault, target)
                source_path = _no_symlink(vault, source)
                target_hash = digest(target_path) if target_path.is_file() else "-"
                source_hash = digest(source_path) if source_path.is_file() else "-"
                if target_hash not in {"-", after}:
                    conflicts.append(f"{target} 已被迁移后修改（当前 {target_hash}），保留现场")
                elif source_hash not in {"-", before}:
                    conflicts.append(f"{source} 已被迁移后修改（当前 {source_hash}），保留现场")
                else:
                    if source_hash == "-":
                        original = _backup_file(vault, journal, source)
                        if original is None:
                            conflicts.append(f"缺少原件备份：{source}")
                            continue
                        _atomic_new(source_path, original, "rollback")
                    if target_hash == after:
                        target_path.unlink()
            conflicts.extend(_rollback_state(workspace, preview))
            journal["status"] = "rolled_back_with_conflicts" if conflicts else "rolled_back"
            journal["rollback_at"] = now()
            journal["rollback_conflicts"] = conflicts
            _save_journal(journal_path, journal, "rollback_finished")
            return {"status": journal["status"], "migration_id": migration_id, "conflicts": conflicts,
                    "backup": journal["backup"]["path"]}
    except ArtifactBusyError as exc:
        return {"status": "busy", "migration_id": migration_id, "conflicts": [str(exc)]}


def resolve_reference(vault: Path, target: str, sha256: str | None = None) -> tuple[str, str | None]:
    """Resolve an old target/hash through the append-only migration chain."""
    relative_target = _safe_relative(target, field="target")
    vault = vault.expanduser().resolve()
    path = vault / _runtime_name(vault) / PATH_MAP
    if not path.is_file():
        alternate = vault / (".cy-vault-runtime" if path.parent.name == ".dyb-vault-runtime"
                             else ".dyb-vault-runtime") / PATH_MAP
        if not alternate.is_file():
            return relative_target, sha256
        path = alternate
    value = read_json(path)
    entries = value.get("entries") if isinstance(value, dict) else None
    if not isinstance(entries, list):
        raise ValueError("path-migrations.json 格式无效")
    current_target, current_hash = relative_target, sha256
    visited: set[tuple[str, str | None]] = set()
    while True:
        state = (_key(current_target), current_hash)
        if state in visited:
            raise ValueError("path-migrations 存在循环")
        visited.add(state)
        candidates = [e for e in entries if isinstance(e, dict) and _key(e.get("source", "")) == _key(current_target)]
        if current_hash is not None:
            candidates = [e for e in candidates if e.get("before_sha256") == current_hash]
        if not candidates:
            return current_target, current_hash
        if current_hash is None and len(candidates) > 1:
            raise ValueError("path-migrations 路径存在多条历史映射，需提供原 expected sha256")
        entry = candidates[-1]
        next_target = _safe_relative(entry.get("target"), field="mapped target")
        next_hash = entry.get("after_sha256")
        if current_hash is not None and not isinstance(next_hash, str):
            raise ValueError("path-migrations 缺少 after_sha256")
        if _key(next_target) == _key(current_target) and next_hash == current_hash:
            # Identity entries cannot make progress and may indicate corrupt loops.
            return current_target, current_hash
        current_target, current_hash = next_target, next_hash
