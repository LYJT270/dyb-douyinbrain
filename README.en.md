<div align="center">
  <img src="assets/hero.png" alt="Douyin-brain" width="100%">
  <h1>Douyin-brain</h1>
  <p>Turn Douyin videos and local media into text you can review, analyze, and adapt.</p>
  <p><a href="README.md">中文</a> · English</p>
</div>

[![CI](https://github.com/ScarfaceAI/dyb-douyinbrain/actions/workflows/check.yml/badge.svg)](https://github.com/ScarfaceAI/dyb-douyinbrain/actions/workflows/check.yml)
[![License](https://img.shields.io/github/license/ScarfaceAI/dyb-douyinbrain)](https://github.com/ScarfaceAI/dyb-douyinbrain/blob/main/LICENSE)
[![Release](https://img.shields.io/github/v/release/ScarfaceAI/dyb-douyinbrain)](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest)

Douyin-brain is a Windows-local Agent Skill. Give an Agent a link, video, or existing transcript and tell it what you need. The bundled program acquires media in the background and uses your own Doubao Speech API for recognition; the Agent then proofreads or works with the text. Existing text can be processed without speech recognition.

> This page includes an unreleased source candidate: the first-use introduction, full creator analysis, independent profile video downloads, and specialized suite entries. When installing an official Release, check the capabilities included in that version.

The candidate organizes Douyin-brain as one product. `dyb-douyinbrain` handles combined requests, setup, and maintenance; clear individual tasks can use `dyb-transcribe` (transcription and subtitles), `dyb-analyze` (post and creator analysis), `dyb-download` (profile videos), `dyb-write` (spoken-script rewriting), or `dyb-knowledge` (requested archiving and compilation). They share installation, configuration, workspace, and updates; automatic discovery depends on the host Agent. See [suite routing](references/suite.en.md).

![Workflow from input to delivery](assets/workflow.svg)

## What it does

- **Transcribe:** Douyin post links, shared text, creator profiles, link lists, and local audio or video.
- **Preserve and proofread:** keep the machine transcript and existing source media unchanged, save a separate reviewed version, and read the whole text before checking names, numbers, and other uncertainties using the Agent's available image and audio tools.
- **Analyze and adapt:** summarize, analyze, shorten, or write spoken scripts without overwriting the source.
- **Analyze a creator or download their videos** (local source candidate, not yet publicly released): discover accessible videos and image posts page by page and analyze the transcript and actually viewed images over time. A separate mode downloads profile videos and captions without speech recognition. See the [creator workflow](references/creator.en.md).
- **Deliver batches:** isolate failures, combine completed results in the original order with their original numbers, and report failed items. A resumed task first reuses valid successful caches. An Agent can directly proofread an existing SRT and save a copy with its timecodes; exporting SRT from recognition requires segment timing data.
- **Archive on request:** follow the target knowledge base's rules only when you explicitly ask for archiving or compilation.

Try asking your Agent:

> Transcribe this Douyin link, check the names and numbers, and give me the transcript only. Do not add it to a knowledge base: [link]

> Turn these videos into natural spoken scripts, one paragraph each, and combine them in order into a TXT file: [links]

> Transcribe the 10 latest posts on this creator profile and flag uncertain words: [profile link]

> Analyze all accessible posts on this creator profile and explain how the topics and content changed over time: [profile link]

> Analyze only the titles and captions on this profile and identify recurring topics: [profile link]

> Download this creator's videos and published captions at the best available quality: [profile link]

> Shorten this existing transcript into a spoken script while keeping its opening hook: [file path]

> Proofread this SRT and preserve its timecodes: [file path]

> Archive these originals and reviewed transcripts, then compile a topic page: [material]

At installation or first use, the Agent introduces the capabilities, examples, outputs, and speech-setup needs in chat, then continues your current task. You do not need to memorize commands. If you provide only a link without a goal, it asks one key question. Analysis starts with findings, examples, and coverage in chat; transcription or rewriting starts with readable text or a clearly marked excerpt before the file link. See the [first-use guide](references/onboarding.en.md).

## Install

You need **Windows, an internet connection, and an Agent that can access local files and a terminal**. Python does not need to be installed in advance. Media transcription also requires your own Doubao Speech account and API key; usage is subject to the provider's terms and your account's pricing.

### Ask an Agent to install it

Copy this prompt to your Agent:

```text
Please install and enable Douyin-brain (dyb-douyinbrain) on my Windows computer. Get the installation ZIP from https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest, or use the repository source folder I provide. Read INSTALL.md, explain the capabilities and speech-setup needs in chat first, then handle extraction, installation, and dependency setup, and load the installed SKILL.md in this conversation. I will enter my Doubao Speech API key in the local configuration window; do not ask me to paste it into chat. Douyin login is not a prerequisite for installation; open a visible Douyin browser only when I explicitly request login, verification, or interface troubleshooting.
```

### Install it yourself

1. Download and extract the installation ZIP from the [latest Release](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest), or use the repository source root.
2. Double-click `install.cmd`. The installer attempts to prepare Python, dependencies, FFmpeg, and the browser environment.
3. Ask your Agent to read the installed `SKILL.md`, then send it your material and instructions. On first use, it introduces the capabilities and checks local readiness.
4. Configure your Doubao Speech API key when you need media transcription; setup does not open the key window by default. Existing-text work and independent profile video downloads need no speech key. Configure a knowledge base only when archiving is requested.

For installation stages, options, setup, and troubleshooting, see the [English getting-started guide](docs/getting-started.en.md) and [INSTALL.md](INSTALL.md).

### Upgrade an existing installation

**Users of 1.0.0 and 1.0.1 must first manually install the latest stable release once**: download and extract the [latest installation ZIP](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest), then run the installer as the same Windows user. Reuse the original Agent and path arguments if you customized them, so the installer can use your existing data and settings. After a local `doctor` and a functional check, ask your Agent to reread the installed `SKILL.md` or start a new conversation.

When migrating from the old `douyin-brain` name, the installer can discover a single old configuration and reuse its workspace, key, and tasks. It backs up the old configuration and Skill and keeps the old name as a compatibility entry. If it finds multiple different workspaces, it lists the candidates and asks you to choose one; it does not merge them. See the [migration instructions](docs/getting-started.en.md#2-install).

Starting with 1.1.0, a new task checks for the latest stable release and notifies you of an update without installing it automatically. To update, say “`@dyb-douyinbrain 更新`” or “`$dyb-douyinbrain 更新`”; if your Agent does not support those invocation forms, say “Use dyb-douyinbrain to update itself.” The Agent verifies the official package and updates only when you explicitly request it. A failed network check does not block the original task; media downloads and cloud speech recognition still require network access. See the [upgrade steps](docs/releasing.en.md#upgrading-an-existing-installation).

## Configure Doubao Speech

![Doubao Speech setup flow](assets/setup-flow.svg)

1. Sign in to [Volcengine](https://signin.volcengine.com/auth/signup) and open the [speech service activation page](https://console.volcengine.com/speech/new/setting/activate?projectName=default).
2. In the selected project, enable **recording file recognition, fast version** and review the available quota and billing terms.
3. Create or copy a speech API key in the **same project** from the [API key page](https://console.volcengine.com/speech/new/setting/apikeys?projectName=default).
4. Open `配置豆包.cmd` and paste the key into the local configuration window; do not send the key in chat.
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
- For a single public video, acquisition first tries the ordinary HTTP share page, then a headless page without saved login state. It may use an existing dedicated browser state if needed; yt-dlp remains a fallback for individual posts. Routine acquisition runs in the background without stealing focus, using Computer Use, automatically logging in, solving CAPTCHA, or using a third-party paid parser. The 1.3.0 local candidate was tested on a fixed sample through anonymous acquisition, live Doubao recognition, and visual review; acquisition did not succeed for every item and audio was not listened to. See the [previous verification record](docs/verification/v1.3.0.md); it does not establish the results of the current 1.3.1 round.
- Site changes or access restrictions can prevent acquisition; failures report the actual cause. Login or verification is reported as required only when a visible blocking container explicitly requests it; words in a title or post and a normal login button do not prove a block. A visible dedicated browser opens only when you explicitly request login, verification, or interface troubleshooting; you complete any login or CAPTCHA locally.
- Creator profiles depend on pagination and platform responses. A run that does not reach the end is reported as incomplete rather than presented as the full profile.
- Creator analysis previews the number of new paid recognition items, known duration, and unknowns before you authorize a batch. No cost is estimated when the applicable unit price is unknown. Titles/captions-only analysis makes no recognition calls. Image posts are included in analysis; the independent download mode handles videos only. Visual review depends on the Agent's actual ability to inspect images.
- `doctor` checks local dependencies and credential presence only; it does not log in to Douyin or validate cloud speech permissions. `awaiting_api` still allows existing-text work, while transcription needs speech configuration.
- Transcription can contain mistakes, particularly names, numbers, and specialist terms. The Agent checks uncertainties using its actual image and audio tools and records the evidence used; sampled frames are not OCR, and preparing material is not a completed review. Check failed or unknown paid requests before asking for a retry.

## License and contributions

Project-owned code is released by [ScarfaceAI](https://github.com/ScarfaceAI) under the [MIT License](LICENSE). Third-party components have their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). For provenance and history, see [references/sources.md](references/sources.md). See [CONTRIBUTING.md](CONTRIBUTING.md), the [maintenance and release guide](docs/releasing.en.md), and [SECURITY.md](SECURITY.md).
