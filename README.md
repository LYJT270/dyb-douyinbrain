<div align="center">
  <img src="assets/hero.png" alt="抖音脑 Douyin-brain" width="100%">
  <h1>抖音脑 Douyin-brain</h1>
  <p>把抖音视频和本地音视频变成可校对、可分析、可继续创作的文字。</p>
  <p>中文 · <a href="README.en.md">English</a></p>
</div>

[![CI](https://github.com/ScarfaceAI/dyb-douyinbrain/actions/workflows/check.yml/badge.svg)](https://github.com/ScarfaceAI/dyb-douyinbrain/actions/workflows/check.yml)
[![License](https://img.shields.io/github/license/ScarfaceAI/dyb-douyinbrain)](https://github.com/ScarfaceAI/dyb-douyinbrain/blob/main/LICENSE)
[![Release](https://img.shields.io/github/v/release/ScarfaceAI/dyb-douyinbrain)](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest)

抖音脑是一个在 Windows 本地运行的 Agent Skill。你把链接、视频或现有文稿交给 Agent，说明想要什么，它就后台获取素材、调用你自己的豆包语音 API，并继续校对或处理文稿。你也可以只处理现成文字。

> 1.5.0 增加恢复入口、逐条文稿版本和离线换角度分析，沿用统一套件与博主流程。安装时以所选 Release 的实际版本为准。详见[版本说明](docs/releases/v1.5.0.md)和[恢复与复用](references/continuation.md)。

抖音脑组织成一套产品：`dyb-douyinbrain` 处理组合需求、配置和维护；单项需求可用 `dyb-transcribe`（转写校对、字幕）、`dyb-analyze`（内容与博主分析）、`dyb-download`（主页视频下载）、`dyb-write`（口播改写）或 `dyb-knowledge`（按需归档、编译）。它们共用安装、配置、工作目录和更新，无需分别配置；具体能否自动发现取决于宿主 Agent。详见[套件路由](references/suite.md)。

![从素材到交付的流程](assets/workflow.svg)

## 能做什么

- **视频转文字**：处理抖音作品链接、分享文案、作者主页、链接清单和本地音视频；使用豆包语音识别。
- **校对留底**：保留机器识别原文，不覆盖已有原始素材，另存校对稿；先通读全文，再按 Agent 实际的看图、听音能力核查数字、专名等疑点，标明依据或不确定之处。
- **分析和改口播**：总结、分析、压缩、润色或改成口播稿，原稿和改写稿分别保存。
- **博主全量分析与视频下载**：按主页逐页整理可访问的视频和图文，结合口播与实际查看的画面按时间分析；也可独立批量下载主页视频及发布文案，不调用语音识别。详见[博主任务指南](references/creator.md)。
- **批量交付**：逐条隔离失败，按原顺序和原序号合并已完成内容，说明失败项；续跑时先复用有效成功缓存。已有 SRT 可让 Agent 直接校对并另存，保留时间码；从识别结果导出 SRT 需要已有分句时间。
- **按需入库**：只有明确要求时才按目标知识库规则归档或编译；首次创建空库不会自动收录历史任务。

安装后可以直接跟 Agent 说：

> 把这个抖音链接转成文字，校对人名和数字，只交逐字稿，不入库：［链接］

> 把这几条视频分别改成自然口播，每条一段，按原顺序合成一个 TXT：［链接清单］

> 转写这个作者主页最近 10 条视频，标出不确定的地方：［主页链接］

> 分析这个博主可访问的全部作品，按时间讲清选题和内容怎么变化：［主页链接］

> 只分析这个主页的标题和发布文案，看看常用选题：［主页链接］

> 批量下载这个主页的视频和发布文案，优先可获取的最高画质：［主页链接］

> 把这份已有文稿整理成更精简的口播稿，保留开头钩子：［文件路径］

> 校对这个 SRT 的文字，保留原来的时间码：［文件路径］

> 把这批原文和校对稿存入知识库，并编译成主题页：［素材］

安装或首次使用时，Agent 会先在聊天中介绍全部功能、示例、产出及语音配置需求，再按你当前的目标继续；无需记命令。只发链接而没说用途时，它会问一个关键问题。分析会先在聊天中给结论、例子和范围，转写或改稿会先给正文或标明节选，再附完整文件。详见[首次介绍](references/onboarding.md)。

## 安装

**需要 Windows、可联网的环境，以及一个有本地文件和终端能力的 Agent。** 不需要提前安装 Python。媒体转写还需要你自己的豆包语音服务账号和 API Key；实际费用以服务提供方和你的账户为准。

### 方式一：交给 Agent

把下面这段发给你使用的 Agent：

```text
请在我的 Windows 电脑安装并启用抖音脑 dyb-douyinbrain。请获取 https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest 的安装 ZIP，或者使用我提供的仓库源码目录；阅读 INSTALL.md，先在聊天中介绍功能与语音配置需求，再自动处理解压、安装和依赖配置。在当前对话加载安装后的 SKILL.md。豆包语音 Key 由我在本机窗口填写，不要让我把 Key 发到聊天里。抖音登录不是安装前置；只有我明确要求登录、验证或界面排障时才打开可见的抖音浏览器。
```

### 方式二：自己安装

1. 打开 [最新 Release](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest)，下载安装 ZIP 并解压；也可以使用本仓库的源码根目录。
2. 双击 `install.cmd`。安装器会尝试自动准备 Python、运行依赖、FFmpeg 和浏览器环境。
3. 让 Agent 读取安装后的 `SKILL.md`，然后直接发送素材和要求。首次使用时它会介绍功能并检查本机状态。
4. 需要转写音视频时再配置自己的豆包语音 API Key；默认不弹配置窗口。处理已有文稿或独立下载主页视频不需要语音 Key，知识库也只在需要入库时配置。

安装参数、默认目录和状态说明见[安装指南](INSTALL.md)。

### 更新已有安装

**1.0.0 和 1.0.1 用户需先手动安装一次最新正式版**：下载并解压[最新安装包](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest)，用原 Windows 用户重新运行安装器。自定义过 Agent 或目录时沿用原参数，让安装器复用已有数据和设置。完成本地 `doctor` 与功能检查后，让 Agent 重新读取安装后的 `SKILL.md`，或开启新会话。

从旧名称 `douyin-brain` 迁移时，安装器可发现单套旧设置并沿用原工作目录、Key 和任务，备份旧配置和 Skill，保留旧名兼容入口。若发现多个不同工作目录，会列出候选项，请你选择一个，不会自动合并。详见[迁移说明](INSTALL.md#从旧版-douyin-brain-迁移)。

从 1.1.0 起，新任务会检查最新正式版，有新版时提醒，不会擅自安装。需要更新时可以说「`@dyb-douyinbrain 更新`」或「`$dyb-douyinbrain 更新`」；不支持这些调用方式的 Agent，可说「使用 dyb-douyinbrain 更新自己」。Agent 会在你明确要求后验证官方包并更新。检查暂时无法联网时不会阻断原任务；下载素材和调用云语音仍需要网络。详见[升级步骤](docs/RELEASING.md#已有用户如何升级)。

## 配置豆包语音

![豆包语音配置流程](assets/setup-flow.svg)

1. 注册或登录[火山引擎](https://signin.volcengine.com/auth/signup)，进入[语音服务开通页面](https://console.volcengine.com/speech/new/setting/activate?projectName=default)。
2. 在选定项目中开通「录音文件识别极速版」，查看实际额度和计费条件。
3. 在**同一个项目**的[语音 API Key 管理页面](https://console.volcengine.com/speech/new/setting/apikeys?projectName=default)创建或复制 Key。
4. 双击 `配置豆包.cmd` 打开本机配置窗口并粘贴 Key；不用把 Key 发给 Agent。
5. 选择一小段本地录音完成真实转写，确认服务可用。真实识别可能消耗额度或产生费用。

页面链接默认进入 `default` 项目；如果服务在其他项目，先切换到实际项目。语音 Key 不是火山方舟聊天模型的 Key。更详细的步骤、旧版凭据和排障见[豆包语音配置教程](references/doubao-setup.md)。

配置窗口与本机教程的实际界面（未填写任何凭据）。点击配置窗口中的「手把手教程」可直接打开本机教程窗口，不依赖默认浏览器；安装目录还提供离线 HTML 版本。

<img src="assets/configuration-window.png" alt="本机 API Key 配置窗口" width="720">

<details><summary>查看本机配置教程窗口</summary>

![本机教程窗口](assets/configuration-guide.png)

</details>

## Agent 兼容

项目提供以下安装适配；所有入口使用同一个核心引擎。Skill 使用通用 `SKILL.md` 格式，但自动发现方式取决于各 Agent 的配置和版本。本版本的跨 Agent 真实会话尚未逐一验证。

| Agent 或方式 | 安装选择 | 说明 |
|---|---|---|
| 自动选择 | `auto` | 默认共享 `.agents/skills`；检测到已有 Claude 配置时尝试桥接，保留同名独立安装。 |
| 共享 Skill 目录 | `shared` | 适合读取共享目录的 Agent。 |
| DeepSeek Harness | `deepseek` | 提供安装适配。 |
| Codex | `codex` | 提供安装适配。 |
| Claude Code | `claude` | 提供安装适配。 |
| Gemini CLI | `gemini` | 提供安装适配。 |
| Cursor | `cursor` | 提供安装适配。 |
| OpenCode | `opencode` | 提供安装适配。 |
| 全部或自定义 | `all`／`custom` | 使用共享目录并尝试 Claude 桥接，或通过 `-SkillsRoot` 指定目录。 |

有本地文件和终端能力的其他兼容 Agent，可读取 `SKILL.md` 并运行随包入口。使用方法和 `-Agent` 示例见 [INSTALL.md](INSTALL.md)。

## 数据、网络与限制

- 默认工作数据在 Windows「文档」下的 `dyb-douyinbrain`；本机设置在 `%LOCALAPPDATA%\dyb-douyinbrain\settings.json`。凭据使用当前 Windows 用户的 DPAPI 加密保存在工作目录。安装包不包含你的 Key、登录状态或历史任务。
- 下载抖音素材时会访问抖音；识别时音频会发送给豆包语音服务。安装依赖时需要联网下载相应组件。请根据素材权限和服务条款选择处理内容。
- 单条公开视频先尝试普通 HTTP 分享页，再通过无登录态的无头页面获取；必要时可尝试本机已有的专用浏览器状态，单条作品也保留 yt-dlp 回退。常规获取在后台运行，不弹窗抢焦点，不使用 Computer Use，也不自动登录、处理验证码或使用第三方付费解析。1.3.0 本地候选曾对固定样本实测匿名获取、真实豆包识别和画面校对，但并非每条都能获取，且未做听音核对；详见[上一轮验收](docs/verification/v1.3.0.md)，正式版本的功能和验证范围见 [1.4.0 版本说明](docs/releases/v1.4.0.md)。
- 页面变化或访问限制可能影响获取，失败时按实际原因报告；只有可见阻挡容器明确提示才报告需要登录或验证，正文、标题中的相关词和普通登录按钮本身不能证明被阻挡。只有你明确要求登录、验证或界面排障时才打开可见的专用浏览器，登录和验证码由你在本机完成。
- 作者主页受分页和平台返回结果影响；未能翻到末尾时会报告不完整，不能把已获取部分当成全部作品。
- 博主分析的新增付费识别先展示当前批次数量、已知时长和未知项，由你确认后才提交；实际单价不明时不估算费用。只分析标题／发布文案不调用识别。图文只进入分析，独立下载入口只处理视频；视觉核对取决于当前 Agent 的实际看图能力。
- `doctor` 只检查本机依赖和凭据是否存在，不登录抖音，也不验证豆包云端权限。安装显示 `awaiting_api` 时仍可处理已有文字；转写需要之后完成语音配置。
- 识别结果可能有错，尤其是人名、数字和专业词。Agent 按当前可用的看图、听音工具核查并记录实际依据；抽样帧不是 OCR，准备材料不等于已校对。失败或结果未知的付费请求需先核对，再按用户要求重试。

## 开源与贡献

抖音脑自有代码由 [ScarfaceAI](https://github.com/ScarfaceAI) 以 [MIT License](LICENSE) 发布。安装时使用的第三方组件遵循各自许可证，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；来源与历史见 [references/sources.md](references/sources.md)。欢迎阅读[贡献指南](CONTRIBUTING.md)、[维护与发布指南](docs/RELEASING.md)和[安全说明](SECURITY.md)。
