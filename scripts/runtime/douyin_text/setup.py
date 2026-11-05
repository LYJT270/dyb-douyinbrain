from __future__ import annotations

import os
from pathlib import Path

from .common import ROOT, RESOURCE_ROOT, SKILL_ROOT, config, now, write_json
from .content import immutable


def settings_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    return Path(os.environ.get("DYB_STATE_DIR") or (base / "dyb-douyinbrain")) / "settings.json"


def workspace_entry(root: Path) -> Path:
    """Keep a small installed-skill pointer beside data without replacing user rules."""
    path = root / "AGENTS.md"
    saved = path.read_bytes() if path.exists() else b""
    body = saved.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in body else "\n"
    start, end = "<!-- dyb-douyinbrain:execution:start -->", "<!-- dyb-douyinbrain:execution:end -->"
    block = "\n".join([
        start, "## dyb-douyinbrain 执行入口", "",
        f"抖音链接、分享文案、本地音视频和文稿任务先读 [dyb-douyinbrain](<{(SKILL_ROOT / 'SKILL.md').as_posix()}>)，具体命令见同 Skill 的 references/runtime.md。",
        f"命令入口：`{(SKILL_ROOT / 'scripts/invoke.ps1').as_posix()}`；工作目录：`{root.as_posix()}`。",
        "媒体转写固定走随包解析／下载 → FFmpeg 提取音轨 → 豆包语音 API → Agent 校对交付。浏览器仅用于凭据配置控制台、抖音登录和必要的素材解析／获取；不使用网页转写、网页字幕或其他识别服务替代豆包。",
        "依赖、登录或语音凭据缺失时按实际缺项修复；本机窗口保存 Key，禁止在聊天索要。已有文字稿直接处理，不调用识别。",
        "只有素材或目标不清楚时问用途，明确任务直接执行；仅明确要求入库时写知识库。", end,
    ]).replace("\n", newline)
    if start in body:
        begin = body.index(start)
        if end not in body[begin:]:
            raise ValueError("工作区执行入口标记不完整，保留现有规则供 Agent 核对")
        finish = body.index(end, begin) + len(end)
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
            for directory in ["素材/文档", "素材/对标", "素材/创作/工作资料", "知识库"]:
                (vault / directory).mkdir(parents=True, exist_ok=True)
            docs = {
                "AGENTS.md": "# 本地知识库约定\n\n本库保存用户明确要求收录的材料。先读 SCHEMA.md、SOURCE_OF_TRUTH.md 和 index.md。\n\n同批材料在素材目录成组保存原文留底和校对逐字稿，并互相链接；原文用于核查，日常检索优先校对稿。作者观点保留归属，不据此推断用户身份。\n\n主题知识页标注草稿并引用素材中的校对稿；原文可作为二级核查来源。收录后更新 index.md，按批次链接校对稿与原文，不重复拆散原文。\n\n已有文件更新前核对当前内容和版本，保留既有修改；新任务另存版本。只有本次明确要求入库才写入。普通文件写入不代表 Git 提交或用户已审。\n",
                "SCHEMA.md": "# 文件结构\n\n- 素材/文档/<批次>/原文留底.md：原始识别或输入文稿，归档参考。\n- 素材/文档/<批次>/校对逐字稿.md：校对后的来源正文，互链同组原文。\n- 素材/对标/：用户明确指定的对标材料，同样成组归档。\n- 素材/创作/工作资料/：用户明确说明属于本人创作的材料。\n- 知识库/<主题>.md：整合后的知识草稿。\n\nMarkdown 使用 UTF-8。来源材料记录标题、作者或文件来源、原链接、版本时间和批内序号。知识页记录状态“草稿”和库内 sources 路径。来源与改写分开，数字替换不应用到原文。\n",
                "SOURCE_OF_TRUTH.md": "# 真源\n\n用户本次指令决定用途和收录范围；本目录的 AGENTS.md、SCHEMA.md 决定组织方式。\n\n校对逐字稿是日常使用和知识编译的来源正文，原文留底是核查依据。两者保留独立版本与链接。主题页是可修订的草稿，不替代来源。\n\nindex.md 仅作导航，不能以索引存在推断材料已完整处理。当前库使用本地 Markdown 文件收录；写入后读回确认，Git 提交和用户审核单独报告。\n",
                "index.md": "# 知识库索引\n\n## 主题知识\n\n尚未收录主题页。\n\n## 来源材料\n\n按批次登记校对稿，并附同组原文留底链接。\n"}
            for name, text in docs.items():
                immutable(vault / name, text.encode("utf-8"))
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
    return {"status": "configured", "workspace": str(root), "vault_root": cfg.get("vault_root"),
            "vault_created": created, "registered": register, "workspace_entry": str(entry),
            "credentials": "not_read_or_changed"}
