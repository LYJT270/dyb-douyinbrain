# 安装承意：给用户和 Agent

承意 CY-CharmYee 在 Windows 本机运行。可以使用 [GitHub 仓库](https://github.com/ScarfaceAI/CY-CharmYee)的源码或正式 Release 安装 ZIP。用户不需要预先安装 Python；安装器会尝试准备运行环境。语音识别使用用户自己的豆包语音服务，开通和计费以服务页面为准。

1.6.0 起使用承意品牌，安装包名为 `cy-charmyee-windows-v<版本>.zip`，包内根目录及 `bundle.json` 的 `name` 均为 `cy-charmyee`。旧 v1.5.0 资产 `dyb-douyinbrain-windows-v1.5.0.zip` 保留原名；首次跨品牌迁移需运行新安装器，不能通过旧更新器直接安装新品牌包。详见[品牌迁移](references/brand-migration.md)和 [1.6.0 版本说明](docs/releases/v1.6.0.md)。

本版新增可选个人知识库，并统一品牌与入口；首次介绍、主页分析、独立下载和既有媒体流程继续保留。

首次安装时，Agent 会先在聊天里介绍能做什么、例子、交付物以及什么时候需要豆包语音，再根据你的目标补必要配置。完整说明见[首次介绍与自然语言路由](references/onboarding.md)；你只需说想处理什么，不需要记命令。

## 让 Agent 自动安装

把以下内容发给有本地文件和终端能力的 Agent：

```text
请在我的 Windows 电脑安装并启用承意 CY-CharmYee（Skill ID：cy-charmyee）。从 https://github.com/ScarfaceAI/CY-CharmYee/releases 获取承意安装 ZIP 和对应 SHA-256，或使用我提供的源码；先校验下载包并核对 bundle.json 的 name 为 cy-charmyee。阅读 INSTALL.md，在聊天中介绍功能与语音配置需求，再自动处理解压、安装和依赖配置。首次从旧 dyb 版本迁移时运行新安装器，沿用已有工作区与自定义安装参数。在当前对话加载安装后的 SKILL.md。豆包语音 Key 由我在本机窗口填写，不要让我把 Key 发到聊天里。抖音登录不是安装前置；只有我明确要求登录、验证或界面排障时才打开可见的抖音浏览器。
```

Agent 可使用已取得的 Release ZIP 或源码根目录；解压后找到同时包含 `SKILL.md` 和 `scripts/install.ps1` 的目录，从该目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\install.ps1'
```

套件一次安装总入口和六个子 Skill：源码及安装包将子 Skill 放在 `skills/`；安装后六个子 Skill 与总入口是同级独立目录，总入口内不保留嵌套的子入口，避免递归发现时重复显示。共用清单核对各入口的一致性。它们共用一套工作目录、配置与更新，不需逐个安装或配置；实际安装结果和自动发现情况须按本机及宿主验证。[套件说明](references/suite.md)列出名称和路由，单个子入口通过自己的 `guide` 定位共用运行时。

默认 `-Agent auto` 安装到当前用户的 `.agents/skills/cy-charmyee`，检测到已有 Claude 配置时尝试建立对应桥接；已有同名独立安装会保留。已指定使用某个 Agent 时可显式选择；所有入口使用相同的核心引擎：

```powershell
# 可选：shared、deepseek、codex、claude、gemini、cursor、opencode、all 或 custom
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\install.ps1' -Agent codex

# 指定 Skill 的父目录；此参数覆盖默认位置
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\install.ps1' -Agent custom -SkillsRoot 'D:\AgentSkills'
```

不传 `-SkillsRoot` 时按所选 Agent 的适配位置安装。`all` 使用共享目录并尝试建立 Claude 桥接；若已有同名独立安装，保留它并按需要单独选择 `-Agent claude` 更新。指定 `-SkillsRoot` 时不额外创建 Claude 桥接。Agent 是否自动发现共享 Skill 还取决于其实际配置，必要时重启或在当前会话直接读取安装后的 `SKILL.md`。请勿把安装适配误报为所有 Agent 的真实运行已经通过验收。

## 自己安装

1. 从 [Release 页面](https://github.com/ScarfaceAI/CY-CharmYee/releases/latest)下载 `cy-charmyee-windows-v<版本>.zip` 及 `.zip.sha256`，核验 SHA-256 后解压，或者打开仓库源码根目录。
2. 双击 `install.cmd`，由安装器自动准备 Python、依赖、FFmpeg 和浏览器运行环境，并设置本机工作目录。网络、权限或系统环境阻断时按实际错误修复。
3. 按安装结果找到 Skill，交给 Agent；如当前 Agent 不自动发现，直接让它读取安装后的 `SKILL.md`，并请它在聊天中介绍功能。
4. 需要转写时再配置豆包语音；默认安装不弹 Key 窗口，现有文稿和主页视频下载无需 Key。可选 cy-vault 建立个人知识库，也可在明确需要入库时再配置。

首次申请或配置 Key，见[豆包语音配置教程](references/doubao-setup.md)。安装不要求先登录抖音，也不会替用户购买资源、自动录音或发送付费语音请求。豆包账号登录、服务开通／计费确认及验证码由用户处理。

用户已明确要求安装时配置语音时，安装器可加 `-ConfigureSpeech`；同传 `-NoApiWindow` 时不弹窗口。介绍应先在聊天实际展示，再按需要配置。

## 默认位置与配置

- 工作目录：Windows「文档」下的 `cy-charmyee`，保存任务、输出、媒体缓存和本机运行数据。
- 知识库：默认不创建。已有登记配置优先；用户选择个人知识库或明确要求入库时可指定已有库或创建空库，创建空库不代表将历史材料入库。
- 本机设置与安装结果：`%LOCALAPPDATA%\cy-charmyee\settings.json`、`%LOCALAPPDATA%\cy-charmyee\install-result.json`。
- 本机语音凭据使用当前 Windows 用户的 DPAPI 加密，保存在工作目录；换电脑或用户后重新配置。浏览器登录状态也留在本机，不属于安装包。

用户指定的已有工作目录或知识库优先，详见[配置与迁移](references/setup.md)。`-StateDirectory` 用于隔离验证，不是正常安装所必需；隔离状态不应覆盖实际安装设置。

## 从旧名称迁移

**旧品牌各版本均需运行一次新安装器，包括已具备更新功能的 1.1.0–1.5.0。** 从承意 1.6.0 包或对应源码根目录执行上方安装命令；保持同一 Windows 用户，沿用自定义的 `-Agent`、`-SkillsRoot` 等参数。已有单套登记无需重新传 `-Workspace` 或 `-StateDirectory`；使用过自定义状态位置的继续传原位置。不要先删除旧安装或工作区。

安装器会发现 `dyb-douyinbrain` 或更早的 `douyin-brain` 登记，沿用原工作目录及其中的凭据和任务，备份原配置与旧 Skill，并将已确认归属的旧主入口和 `dyb-*` 子入口转为兼容入口。同一 Windows 用户可继续使用原有本机加密的 Key；不需要把 Key 发到聊天中。

新安装的状态目录为 `%LOCALAPPDATA%\cy-charmyee`；已有 `%LOCALAPPDATA%\dyb-douyinbrain\settings.json` 且没有新登记时沿用旧状态目录。`CY_*` 环境变量优先，旧 `DYB_*` 继续可用。用户工作目录、知识库目录和历史任务 ID 不因改名搬动。旧版更新器校验固定的产品 ID 和 ZIP 名称，首次跨品牌迁移由 Agent 运行新安装器；之后通过承意的 `update --apply` 更新。

如果发现多个不同的工作目录，安装器返回 `needs_workspace_choice` 和候选项。Agent 展示候选项并询问用户选择一次，再用所选路径重新运行；不会自动合并工作目录或任务：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\install.ps1' -Workspace '<用户选择的工作目录>'
```

## 安装状态和后续使用

查看 `install-result.json` 或安装器输出：

| 状态 | 含义与处理 |
|---|---|
| `installed` | 本地安装与凭据存在性检查完成；不代表云端语音权限已验证。 |
| `awaiting_api` | 本地安装已推进但尚未保存语音凭据；可继续处理已有文字稿和下载主页视频，配置 Key 后再做媒体转写。 |
| `needs_workspace_choice` | 发现多个不同的工作目录；让用户选择候选路径，用 `-Workspace` 重新运行。 |
| `dependencies_pending` | 跳过依赖的隔离测试状态，不能当作完整环境已就绪。 |
| `failed` | 根据 `stage` 和错误处理实际缺项，再核对结果。 |

`local_entry_verified` 说明本地入口检查结果；`live_asr_requests=0` 表示安装没有发起真实识别。`doctor` 只做本地检查，不登录抖音、不验证云端 Key 或调用语音服务。首次真实转写以用户选择的任务结果判断；可按教程用短录音测试，可能产生服务费用。

Agent 在安装后应读取结果指向的 `skill_file`、`runtime_reference` 和 `onboarding_reference`，并使用 `entrypoint welcome` 获取功能介绍、本机准备状态及 `onboarding.due`，不依赖技能列表立即刷新。安装前已在聊天展示完整介绍的，安装完成后才执行 `welcome --acknowledge`；否则先实际展示再登记。安装器终端输出不等于聊天展示，标记也不代表用户读懂或授权付费。遇到 `awaiting_api` 时，用户可以稍后通过随包的 `配置豆包.cmd` 配置；旧式 APP ID 和 Access Token 使用 `配置豆包旧版.cmd`。不要索要或输出凭据、Cookie、验证码。

安装包不携带密钥、浏览器登录态、历史媒体、缓存或任务记录。更新已有安装时保留原安装备份；不要顺带清理用户工作数据。
