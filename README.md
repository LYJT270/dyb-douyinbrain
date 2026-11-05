<div align="center">
  <img src="assets/hero.png" alt="抖音脑 Douyin-brain" width="100%">
  <h1>抖音脑 Douyin-brain</h1>
  <p>把抖音视频和本地音视频变成可校对、可分析、可继续创作的文字。</p>
  <p>中文 · <a href="README.en.md">English</a></p>
</div>

[![CI](https://github.com/ScarfaceAI/dyb-douyinbrain/actions/workflows/check.yml/badge.svg)](https://github.com/ScarfaceAI/dyb-douyinbrain/actions/workflows/check.yml)
[![License](https://img.shields.io/github/license/ScarfaceAI/dyb-douyinbrain)](https://github.com/ScarfaceAI/dyb-douyinbrain/blob/main/LICENSE)
[![Release](https://img.shields.io/github/v/release/ScarfaceAI/dyb-douyinbrain)](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest)

抖音脑是一个在 Windows 本地运行的 Agent Skill。你把链接、视频或现有文稿交给 Agent，说明想要什么，它就使用随包程序获取素材、调用你自己的豆包语音 API，并继续校对或处理文稿。你也可以只处理现成文字。

![从素材到交付的流程](assets/workflow.svg)

## 能做什么

- **视频转文字**：处理抖音作品链接、分享文案、作者主页、链接清单和本地音视频；使用豆包语音识别。
- **校对留底**：保留机器识别原文，另存校对稿；对人名、数字等疑点标明依据或不确定之处。
- **分析和改口播**：总结、分析、压缩、润色或改成口播稿，原稿和改写稿分别保存。
- **批量交付**：按原顺序合并为编号 TXT，失败的素材保留原序号并说明。
- **按需入库**：只有明确要求时才按目标知识库规则归档或编译；首次创建空库不会自动收录历史任务。

安装后可以直接跟 Agent 说：

> 把这个抖音链接转成文字，校对人名和数字，只交逐字稿，不入库：［链接］

> 把这几条视频分别改成自然口播，每条一段，按原顺序合成一个 TXT：［链接清单］

> 转写这个作者主页最近 10 条视频，标出不确定的地方：［主页链接］

> 把这份已有文稿整理成更精简的口播稿，保留开头钩子：［文件路径］

## 安装

**需要 Windows、可联网的环境，以及一个有本地文件和终端能力的 Agent。** 不需要提前安装 Python。媒体转写还需要你自己的豆包语音服务账号和 API Key；实际费用以服务提供方和你的账户为准。

### 方式一：交给 Agent

把下面这段发给你使用的 Agent：

```text
请在我的 Windows 电脑安装并启用抖音脑 dyb-douyinbrain。请获取 https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest 的安装 ZIP，或者使用我提供的仓库源码目录；阅读 INSTALL.md，自动处理解压、安装和依赖配置。在当前对话加载安装后的 SKILL.md。豆包语音 Key 由我在本机窗口填写，不要让我把 Key 发到聊天里。需要登录或验证码时请告诉我。
```

### 方式二：自己安装

1. 打开 [最新 Release](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest)，下载安装 ZIP 并解压；也可以使用本仓库的源码根目录。
2. 双击 `install.cmd`。安装器会尝试自动准备 Python、运行依赖、FFmpeg 和浏览器环境。
3. 在本机弹出的窗口填写自己的豆包语音 API Key。暂时没有 Key 可以先跳过，处理已有文稿不需要语音服务。
4. 让 Agent 读取安装后的 `SKILL.md`，然后直接发送素材和要求。

安装参数、默认目录和状态说明见[安装指南](INSTALL.md)。

### 更新已有安装

**1.0.0 和 1.0.1 用户先手动安装一次 1.1.0**（或已包含更新功能的较新版）：下载并解压[最新安装包](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest)，用原 Windows 用户重新运行安装器。自定义过 Agent 或目录时沿用原参数，让安装器复用已有数据和设置。完成本地 `doctor` 与功能检查后，让 Agent 重新读取安装后的 `SKILL.md`，或开启新会话。

从 1.1.0 起，新任务会检查最新正式版，有新版时提醒，不会擅自安装。需要更新时可以说「`@dyb-douyinbrain 更新`」或「`$dyb-douyinbrain 更新`」；不支持这些调用方式的 Agent，可说「使用 dyb-douyinbrain 更新自己」。Agent 会在你明确要求后验证官方包并更新。检查暂时无法联网时不会阻断原任务；下载素材和调用云语音仍需要网络。详见[升级步骤](docs/RELEASING.md#已有用户如何升级)。

## 配置豆包语音

![豆包语音配置流程](assets/setup-flow.svg)

1. 注册或登录[火山引擎](https://signin.volcengine.com/auth/signup)，进入[语音服务开通页面](https://console.volcengine.com/speech/new/setting/activate?projectName=default)。
2. 在选定项目中开通「录音文件识别极速版」，查看实际额度和计费条件。
3. 在**同一个项目**的[语音 API Key 管理页面](https://console.volcengine.com/speech/new/setting/apikeys?projectName=default)创建或复制 Key。
4. 将 Key 粘贴到本机配置窗口。之后也可以双击 `配置豆包.cmd` 打开窗口；不用把 Key 发给 Agent。
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
- 抖音解析使用 Playwright 浏览器中的页面网络响应；单条作品必要时使用 yt-dlp 回退。页面变化、访问限制、登录或验证码都可能影响获取；需要登录或验证码时由你在本机完成。
- 作者主页受分页和平台返回结果影响；未能翻到末尾时会报告不完整，不能把已获取部分当成全部作品。
- `doctor` 只检查本机依赖和凭据是否存在，不登录抖音，也不验证豆包云端权限。安装显示 `awaiting_api` 时仍可处理已有文字；转写需要之后完成语音配置。
- 识别结果可能有错，尤其是人名、数字和专业词；校对时应对照原音。失败或结果未知的付费请求需先核对，再按用户要求重试。

## 开源与贡献

抖音脑自有代码由 [ScarfaceAI](https://github.com/ScarfaceAI) 以 [MIT License](LICENSE) 发布。安装时使用的第三方组件遵循各自许可证，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；来源与历史见 [references/sources.md](references/sources.md)。欢迎阅读[贡献指南](CONTRIBUTING.md)、[维护与发布指南](docs/RELEASING.md)和[安全说明](SECURITY.md)。
