# 安装抖音脑：给用户和 Agent

抖音脑在 Windows 本机运行。可以使用 [GitHub 仓库](https://github.com/ScarfaceAI/dyb-douyinbrain)源码根目录，也可以使用 [最新 Release](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest) 的安装 ZIP。用户不需要预先安装 Python；安装器会尝试准备运行环境。语音识别使用用户自己的豆包语音服务，开通和计费以服务页面为准。

> 当前源码候选的首次介绍、主页分析、独立下载与套件子入口尚未公开发布；安装正式 Release 时以其实际包含的功能为准。

首次安装时，Agent 会先在聊天里介绍能做什么、例子、交付物以及什么时候需要豆包语音，再根据你的目标补必要配置。完整说明见[首次介绍与自然语言路由](references/onboarding.md)；你只需说想处理什么，不需要记命令。

## 让 Agent 自动安装

把以下内容发给有本地文件和终端能力的 Agent：

```text
请在我的 Windows 电脑安装并启用抖音脑 dyb-douyinbrain。请获取 https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest 的安装 ZIP，或者使用我提供的仓库源码目录；阅读 INSTALL.md，先在聊天中介绍功能与语音配置需求，再自动处理解压、安装和依赖配置。在当前对话加载安装后的 SKILL.md。豆包语音 Key 由我在本机窗口填写，不要让我把 Key 发到聊天里。抖音登录不是安装前置；只有我明确要求登录、验证或界面排障时才打开可见的抖音浏览器。
```

Agent 可使用已取得的 Release ZIP 或源码根目录；解压后找到同时包含 `SKILL.md` 和 `scripts/install.ps1` 的目录，从该目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\install.ps1'
```

本源码候选按一次安装组织总入口和五个子 Skill：源码及安装包将子 Skill 放在 `skills/`；安装后五个子 Skill 与总入口是同级独立目录，总入口内不保留嵌套的子入口，避免递归发现时重复显示。共用清单核对各入口的一致性。它们共用一套工作目录、配置与更新，不需逐个安装或配置；实际安装结果和自动发现情况须按本机及宿主验证。[套件说明](references/suite.md)列出名称和路由，单个子入口通过自己的 `guide` 定位共用运行时。

默认 `-Agent auto` 安装到当前用户的 `.agents/skills/dyb-douyinbrain`，检测到已有 Claude 配置时尝试建立对应桥接；已有同名独立安装会保留。已指定使用某个 Agent 时可显式选择；所有入口使用相同的核心引擎：

```powershell
# 可选：shared、deepseek、codex、claude、gemini、cursor、opencode、all 或 custom
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\install.ps1' -Agent codex

# 指定 Skill 的父目录；此参数覆盖默认位置
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\install.ps1' -Agent custom -SkillsRoot 'D:\AgentSkills'
```

不传 `-SkillsRoot` 时按所选 Agent 的适配位置安装。`all` 使用共享目录并尝试建立 Claude 桥接；若已有同名独立安装，保留它并按需要单独选择 `-Agent claude` 更新。指定 `-SkillsRoot` 时不额外创建 Claude 桥接。Agent 是否自动发现共享 Skill 还取决于其实际配置，必要时重启或在当前会话直接读取安装后的 `SKILL.md`。请勿把安装适配误报为所有 Agent 的真实运行已经通过验收。

## 自己安装

1. 从 [Release 页面](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest)下载安装 ZIP 并解压，或者打开仓库源码根目录。
2. 双击 `install.cmd`，由安装器自动准备 Python、依赖、FFmpeg 和浏览器运行环境，并设置本机工作目录。网络、权限或系统环境阻断时按实际错误修复。
3. 按安装结果找到 Skill，交给 Agent；如当前 Agent 不自动发现，直接让它读取安装后的 `SKILL.md`，并请它在聊天中介绍功能。
4. 需要转写时再配置豆包语音；默认安装不弹 Key 窗口，现有文稿和主页视频下载无需 Key。知识库只在你明确需要入库时选择或创建。

首次申请或配置 Key，见[豆包语音配置教程](references/doubao-setup.md)。安装不要求先登录抖音，也不会替用户购买资源、自动录音或发送付费语音请求。豆包账号登录、服务开通／计费确认及验证码由用户处理。

用户已明确要求安装时配置语音时，安装器可加 `-ConfigureSpeech`；同传 `-NoApiWindow` 时不弹窗口。介绍应先在聊天实际展示，再按需要配置。

## 默认位置与配置

- 工作目录：Windows「文档」下的 `dyb-douyinbrain`，保存任务、输出、媒体缓存和本机运行数据。
- 知识库：默认不创建。已有登记配置优先；用户明确要求入库时可指定已有库或创建空库，创建空库不代表将历史材料入库。
- 本机设置与安装结果：`%LOCALAPPDATA%\dyb-douyinbrain\settings.json`、`%LOCALAPPDATA%\dyb-douyinbrain\install-result.json`。
- 本机语音凭据使用当前 Windows 用户的 DPAPI 加密，保存在工作目录；换电脑或用户后重新配置。浏览器登录状态也留在本机，不属于安装包。

用户指定的已有工作目录或知识库优先，详见[配置与迁移](references/setup.md)。`-StateDirectory` 用于隔离验证，不是正常安装所必需；隔离状态不应覆盖实际安装设置。

## 从旧版 `douyin-brain` 迁移

安装器会发现单套旧版设置，沿用原工作目录及其中的凭据和任务，备份原配置与旧 Skill，并保留旧名称兼容入口。同一 Windows 用户可继续使用原有本机加密的 Key；不需要把 Key 发到聊天中。

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
