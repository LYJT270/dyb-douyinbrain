from __future__ import annotations

import os
from pathlib import Path

from .common import ROOT, RESOURCE_ROOT, SKILL_ROOT, config, now, write_json
from .content import immutable
from . import onboarding
from .identity import state_root


def settings_path() -> Path:
    return state_root() / "settings.json"


def workspace_entry(root: Path) -> Path:
    """Keep a small installed-skill pointer beside data without replacing user rules."""
    path = root / "AGENTS.md"
    saved = path.read_bytes() if path.exists() else b""
    body = saved.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in body else "\n"
    start, end = "<!-- cy-charmyee:execution:start -->", "<!-- cy-charmyee:execution:end -->"
    block = "\n".join([
        start, "## cy-charmyee 执行入口", "",
        f"抖音链接、分享文案、本地音视频和文稿任务先读 [cy-charmyee](<{(SKILL_ROOT / 'SKILL.md').as_posix()}>)，具体命令见同 Skill 的 references/runtime.md。",
        f"命令入口：`{(SKILL_ROOT / 'scripts/invoke.ps1').as_posix()}`；工作目录：`{root.as_posix()}`。",
        "媒体转写走免登录优先获取公开素材 → FFmpeg 提取音轨 → 豆包语音 API → 当前 Agent 按实际看图／听音能力校对交付；不使用网页转写、网页字幕或其他识别服务替代豆包。",
        "常规获取与抽帧在后台执行，不调用 Computer Use，不自行打开可见浏览器；失败仅报告实际原因。只有用户明确要求登录、验证或界面排障时才打开对应窗口。",
        "只有页面明确要求时提示登录或验证，不把缺少数据一律归为登录。Key 在本机窗口保存，禁止在聊天索要；已有文字稿直接处理，不调用识别。",
        "只有素材或目标不清楚时问用途，明确任务直接执行；入库遵循明确指令或已通过 cy-vault 开启的自动积累范围；任务开始与交付时按 references/personal-vault.md 核对状态。", end,
    ]).replace("\n", newline)
    legacy_start, legacy_end = "<!-- dyb-douyinbrain:execution:start -->", "<!-- dyb-douyinbrain:execution:end -->"
    found_start, found_end = (start, end) if start in body else (legacy_start, legacy_end)
    if found_start in body:
        begin = body.index(found_start)
        if found_end not in body[begin:]:
            raise ValueError("工作区执行入口标记不完整，保留现有规则供 Agent 核对")
        finish = body.index(found_end, begin) + len(found_end)
        updated = body[:begin] + block + body[finish:]
    else:
        separator = "" if not body else newline if body.endswith("\n") else newline * 2
        updated = body + separator + block + newline
    data = (b"\xef\xbb\xbf" if saved.startswith(b"\xef\xbb\xbf") else b"") + updated.encode("utf-8")
    if data != saved:
        path.write_bytes(data)
    return path


def initialize(root: Path = ROOT, *, vault: Path | None = None, create_vault: bool = False,
               assistant: Path | None = None, register: bool = False) -> dict:
    root = root.expanduser().resolve()
    if root == SKILL_ROOT or SKILL_ROOT.is_relative_to(root) or root.is_relative_to(SKILL_ROOT):
        raise ValueError("工作目录应与 Skill 程序目录分开")
    cfg = config(root)
    created = False
    if create_vault and not vault:
        raise ValueError("创建知识库需要先确定目录")
    if vault:
        vault = vault.expanduser().resolve()
        if vault == root or root.is_relative_to(vault) or vault.is_relative_to(root):
            raise ValueError("知识库与运行工作目录分别放置，避免媒体和凭据混入知识库")
        if create_vault:
            if vault.exists() and any(vault.iterdir()):
                raise ValueError("目标目录已有内容，请按已有知识库配置，不覆盖其规则")
            for directory in ["生活/个人档案", "生活/资料", "工作/资料", "学习/资料"]:
                (vault / directory).mkdir(parents=True, exist_ok=True)
            for template in (SKILL_ROOT / "assets/vault").glob("*.md"):
                immutable(vault / template.name, template.read_bytes())
            from .personal_vault import rules
            write_json(vault / ".cy-vault.json", {"schema": 1, "product": "cy-vault", "rules": rules(vault)})
            created = True
        elif not vault.is_dir():
            raise ValueError("指定的知识库目录不存在；如需新建，明确使用 --create-vault")
        cfg["vault_root"] = str(vault)
    if assistant:
        assistant = assistant.expanduser().resolve()
        if not (assistant / "scripts/vault.py").is_file():
            raise ValueError("指定位置没有既有知识库发布入口")
        cfg["assistant_root"] = str(assistant)
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "config.json", cfg)
    entry = workspace_entry(root)
    if register:
        write_json(settings_path(), {"workspace": str(root), "skill_root": str(SKILL_ROOT),
                                    "entrypoint": str(SKILL_ROOT / "scripts/invoke.ps1"),
                                    "workspace_entry": str(entry), "updated_at": now()})
        from . import personal_vault
        previous = personal_vault.state(root)
        hook = previous.get('hook', {}).get('file')
        if hook and Path(hook).is_file():
            # Refresh an already opted-in hook without enabling any new scope.
            personal_vault.install_hook(root, previous, Path(hook))
    return {"status": "configured", "workspace": str(root), "vault_root": cfg.get("vault_root"),
            "vault_created": created, "registered": register, "workspace_entry": str(entry),
            "credentials": "not_read_or_changed", "onboarding": onboarding.status(root)}
