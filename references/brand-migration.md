# 承意命名与迁移

中文名：**承意**。英文名：**CY-CharmYee**。口号：**承你所想，会你所意**。

| 展示名称 | Skill ID / 目录 | 原入口 |
|---|---|---|
| 承意 · CY-CharmYee | `cy-charmyee` | `dyb-douyinbrain`、`douyin-brain` |
| CY-transcribe | `cy-transcribe` | `dyb-transcribe` |
| CY-analyze | `cy-analyze` | `dyb-analyze` |
| CY-download | `cy-download` | `dyb-download` |
| CY-write | `cy-write` | `dyb-write` |
| CY-knowledge | `cy-knowledge` | `dyb-knowledge` |
| CY-vault | `cy-vault` | `dyb-vault` |

Skill 标识、文件夹与 `$cy-*` 调用采用宿主要求的小写；产品名与界面展示保留 `CY-` 大写。`douyin_text` 仍是内部媒体处理模块名，不是用户入口。

从 1.6.0 起，新安装使用 `cy-charmyee` 工作目录和状态目录，安装 ZIP 名称为 `cy-charmyee-windows-v<版本>.zip`，包内根目录为 `cy-charmyee/`。历史 v1.5.0 及更早资产保持原名；旧包不会因仓库改名而变成新版承意包。

已有用户首次迁移由 Agent 运行承意 1.6.0 包或对应源码的 `scripts/install.ps1`。这也适用于已经具备更新功能的旧品牌 1.1.0–1.5.0：旧版更新器固定校验旧产品 ID、包名和包内目录，不能通过旧 `update --apply` 直接安装新品牌包。后续已安装承意的版本继续使用正常的 `update --apply`。

1. 从[官方 Release](https://github.com/ScarfaceAI/CY-CharmYee/releases/latest)取得承意安装 ZIP 与对应 SHA-256，校验后解压；先确认 `bundle.json` 中 `name=cy-charmyee`。
2. 用原 Windows 用户运行新安装器，保留自定义的 Agent 和 SkillsRoot 等参数。已有单一登记时无需重填 Workspace / StateDirectory；自定义状态位置继续使用原参数。
3. 核对安装回执中的工作区、版本、入口与备份；按 `entrypoint` 运行 `doctor`，再用已有文稿确认能继续同一任务。
4. 让 Agent 重读新 `SKILL.md` 或开启新会话。新入口采用 `cy-*`，旧路径按下面的兼容机制转发。

安装器沿用明确登记的工作区和已有凭据，先备份配置、受管理入口与旧程序。旧主入口和子入口改成转发入口，旧脚本路径可继续使用；这些入口在支持该设置的宿主中关闭自动发现，新的请求使用 `cy-*`。原有用户补充文件保存在安装回执列出的备份中。

`CY_WORKSPACE`、`CY_STATE_DIR`、`CY_UPDATE_CHECK` 优先，旧 `DYB_*` 仍可读取。已有旧状态目录、历史任务 ID、媒体缓存、知识库目录和持久化标记不强制改名。受管理的工作区与个人知识库入口在安装登记时更新；保留用户规则正文、原始回答、已有选择和积累状态。

出现多个登记工作区时只询问一次选择；安装失败时恢复已替换程序、兼容入口及登记文件。安装回执证明本地迁移结果，不代表云端识别或各宿主的新会话已经验收。

旧版本发布说明、校验文件、验证记录保留历史名称与当时事实。源码所在本地文件夹及用户自定义数据路径不会仅为品牌一致而搬动。

English: [Brand and migration](brand-migration.en.md).
