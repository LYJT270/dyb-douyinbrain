<div align="center">
  <img src="assets/hero.png" alt="Douyin-brain" width="100%">
  <h1>Douyin-brain</h1>
  <p>Turn Douyin videos and local media into text you can review, analyze, and adapt.</p>
  <p><a href="README.md">中文</a> · English</p>
</div>

[![CI](https://github.com/ScarfaceAI/dyb-douyinbrain/actions/workflows/check.yml/badge.svg)](https://github.com/ScarfaceAI/dyb-douyinbrain/actions/workflows/check.yml)
[![License](https://img.shields.io/github/license/ScarfaceAI/dyb-douyinbrain)](https://github.com/ScarfaceAI/dyb-douyinbrain/blob/main/LICENSE)
[![Release](https://img.shields.io/github/v/release/ScarfaceAI/dyb-douyinbrain)](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest)

Douyin-brain is a Windows-local Agent Skill. Give an Agent a link, video, or existing transcript and tell it what you need. The bundled program acquires media and uses your own Doubao Speech API for recognition; the Agent then proofreads or works with the text. Existing text can be processed without speech recognition.

![Workflow from input to delivery](assets/workflow.svg)

## What it does

- **Transcribe:** Douyin post links, shared text, creator profiles, link lists, and local audio or video.
- **Preserve and proofread:** keep the machine transcript and save a separate reviewed version, with unresolved names or numbers identified.
- **Analyze and adapt:** summarize, analyze, shorten, or write spoken scripts without overwriting the source.
- **Deliver batches:** combine results into a numbered TXT in the original order and report failed items.
- **Archive on request:** follow the target knowledge base's rules only when you explicitly ask for archiving or compilation.

Try asking your Agent:

> Transcribe this Douyin link, check the names and numbers, and give me the transcript only. Do not add it to a knowledge base: [link]

> Turn these videos into natural spoken scripts, one paragraph each, and combine them in order into a TXT file: [links]

> Transcribe the 10 latest posts on this creator profile and flag uncertain words: [profile link]

> Shorten this existing transcript into a spoken script while keeping its opening hook: [file path]

## Install

You need **Windows, an internet connection, and an Agent that can access local files and a terminal**. Python does not need to be installed in advance. Media transcription also requires your own Doubao Speech account and API key; usage is subject to the provider's terms and your account's pricing.

### Ask an Agent to install it

Copy this prompt to your Agent:

```text
Please install and enable Douyin-brain (dyb-douyinbrain) on my Windows computer. Get the installation ZIP from https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest, or use the repository source folder I provide. Read INSTALL.md, handle extraction, installation, and dependency setup, and load the installed SKILL.md in this conversation. I will enter my Doubao Speech API key in the local configuration window; do not ask me to paste it into chat. Tell me when I need to complete a login or CAPTCHA.
```

### Install it yourself

1. Download and extract the installation ZIP from the [latest Release](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest), or use the repository source root.
2. Double-click `install.cmd`. The installer attempts to prepare Python, dependencies, FFmpeg, and the browser environment.
3. Enter your Doubao Speech API key in the local window. If you do not have one yet, you can defer it and still work with existing text.
4. Ask your Agent to read the installed `SKILL.md`, then send it your material and instructions.

For installation stages, options, setup, and troubleshooting, see the [English getting-started guide](docs/getting-started.en.md) and [INSTALL.md](INSTALL.md).

### Upgrade an existing installation

**Users of 1.0.0 and 1.0.1 must first manually install the latest stable release once**: download and extract the [latest installation ZIP](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest), then run the installer as the same Windows user. Reuse the original Agent and path arguments if you customized them, so the installer can use your existing data and settings. After a local `doctor` and a functional check, ask your Agent to reread the installed `SKILL.md` or start a new conversation.

Starting with 1.1.0, a new task checks for the latest stable release and notifies you of an update without installing it automatically. To update, say “`@dyb-douyinbrain 更新`” or “`$dyb-douyinbrain 更新`”; if your Agent does not support those invocation forms, say “Use dyb-douyinbrain to update itself.” The Agent verifies the official package and updates only when you explicitly request it. A failed network check does not block the original task; media downloads and cloud speech recognition still require network access. See the [upgrade steps](docs/releasing.en.md#upgrading-an-existing-installation).

## Configure Doubao Speech

![Doubao Speech setup flow](assets/setup-flow.svg)

1. Sign in to [Volcengine](https://signin.volcengine.com/auth/signup) and open the [speech service activation page](https://console.volcengine.com/speech/new/setting/activate?projectName=default).
2. In the selected project, enable **recording file recognition, fast version** and review the available quota and billing terms.
3. Create or copy a speech API key in the **same project** from the [API key page](https://console.volcengine.com/speech/new/setting/apikeys?projectName=default).
4. Paste the key into the local configuration window. You can later reopen it with `配置豆包.cmd`; do not send the key in chat.
5. Use a short recording for a real transcription to check service access. Recognition may use quota or incur charges.

The links open the `default` project; switch projects if appropriate. A speech key is different from a Volcengine Ark chat-model key. See the [step-by-step Chinese guide](references/doubao-setup.md) for legacy credentials and troubleshooting.

The actual local configuration dialog, with no credentials entered:

<img src="assets/configuration-window.png" alt="Empty local API key dialog" width="720">

The dialog's tutorial button opens a native local guide window without relying on the default browser. A separate offline HTML guide is also included. The desktop dialog and native guide are in Chinese; the [English getting-started guide](docs/getting-started.en.md) explains every step.

## Agent compatibility

The project provides installation adapters for these Agents; every entry uses the same core engine. The Skill uses the common `SKILL.md` format, but automatic discovery depends on each Agent's configuration and version. Real end-to-end sessions have not yet been individually verified across all Agents in this version.

| Agent or mode | `-Agent` | Notes |
|---|---|---|
| Automatic | `auto` | Uses shared `.agents/skills`; attempts a Claude bridge when detected and preserves an existing independent install. |
| Shared skills | `shared` | For Agents that read the shared directory. |
| DeepSeek Harness | `deepseek` | Installation adapter provided. |
| Codex | `codex` | Installation adapter provided. |
| Claude Code | `claude` | Installation adapter provided. |
| Gemini CLI | `gemini` | Installation adapter provided. |
| Cursor | `cursor` | Installation adapter provided. |
| OpenCode | `opencode` | Installation adapter provided. |
| All or custom | `all` / `custom` | Use the shared directory and attempt a Claude bridge, or choose a directory with `-SkillsRoot`. |

Other compatible Agents with local file and terminal access can read `SKILL.md` and run the bundled entry point. See [INSTALL.md](INSTALL.md) for options.

## Data, network access, and limits

- The default workspace is `dyb-douyinbrain` under Windows Documents; local settings are in `%LOCALAPPDATA%\dyb-douyinbrain\settings.json`. Credentials are encrypted using the current Windows user's DPAPI and stored in the workspace. Installation packages exclude your keys, browser login state, and task history.
- Acquiring media accesses Douyin; recognition sends audio to Doubao Speech. Installing dependencies also requires network downloads. Use material in accordance with applicable permissions and service terms.
- Douyin acquisition uses Playwright browser page responses, with yt-dlp as a fallback for individual posts where needed. Site changes, restrictions, login, or CAPTCHA can prevent acquisition; complete login or CAPTCHA yourself when required.
- Creator profiles depend on pagination and platform responses. A run that does not reach the end is reported as incomplete rather than presented as the full profile.
- `doctor` checks local dependencies and credential presence only; it does not log in to Douyin or validate cloud speech permissions. `awaiting_api` still allows existing-text work, while transcription needs speech configuration.
- Transcription can contain mistakes, particularly names, numbers, and specialist terms. Review uncertain sections against the audio. Check failed or unknown paid requests before asking for a retry.

## License and contributions

Project-owned code is released by [ScarfaceAI](https://github.com/ScarfaceAI) under the [MIT License](LICENSE). Third-party components have their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). For provenance and history, see [references/sources.md](references/sources.md). See [CONTRIBUTING.md](CONTRIBUTING.md), the [maintenance and release guide](docs/releasing.en.md), and [SECURITY.md](SECURITY.md).
