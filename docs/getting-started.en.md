# Getting started with Douyin-brain on Windows

Douyin-brain works with an Agent that can read local files and run terminal commands. Its bundled engine processes media locally and sends audio to your own Doubao Speech account for recognition. You can work with existing text without configuring speech credentials.

> The first-use introduction, creator analysis, independent profile video downloads, and specialized suite entries described here belong to the current unreleased source candidate. An official Release may have a different feature set.

Before configuration, the Agent introduces the capabilities, examples, outputs, and when speech setup is needed in chat. You can simply describe your goal; see the [first-use guide](../references/onboarding.en.md) for all routes. The installer can also print an introduction to its terminal, but that does not count as a chat presentation.

## 1. Get the source or installation package

Use the repository source root, or download and extract the installation ZIP from [the latest Release](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest). The folder to install from contains `SKILL.md` and `scripts/install.ps1`.

Python and Douyin login are not installation prerequisites: the installer attempts to prepare Python, a virtual environment, dependencies, FFmpeg, and Chromium. Setup needs network access and may require you to resolve a Windows permission or package-manager problem.

## 2. Install

The simplest manual route is to double-click `install.cmd` in that folder. Alternatively, ask your Agent to read [INSTALL.md](../INSTALL.md) and install it. From the source or extracted folder, the Agent can run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\install.ps1'
```

The default `-Agent auto` uses the user's shared `.agents/skills` directory and attempts a Claude bridge when an existing configuration is detected. It preserves an independent installation with the same name. You may choose an adapter explicitly, for example `-Agent codex`, `-Agent claude`, or `-Agent gemini`; `deepseek`, `cursor`, `opencode`, `shared`, `all`, and `custom` are also available. Supply `-SkillsRoot 'D:\AgentSkills'` to choose a skills parent directory; an explicit root does not add a Claude bridge. See [INSTALL.md](../INSTALL.md) for examples.

All adapters use the same core engine. Automatic discovery varies by Agent and configuration; if a skill list does not refresh, ask the Agent to read the installed `SKILL.md` directly. Installation adapters and a common skill format do not, by themselves, prove that each Agent's real interactive session has been tested.

The candidate installs one suite: the `dyb-douyinbrain` main entry and five child Skills for transcription, analysis, profile downloads, rewriting, and knowledge work. Source and installation packages keep the children under `skills/`; installation places them in separate sibling directories and does not retain nested child entries under the main Skill, avoiding duplicate recursive discovery. A shared manifest verifies consistency. They share one workspace, configuration, and update path rather than requiring five setups. Child `guide` commands locate the shared runtime; inspect the actual installation and host discovery instead of assuming either succeeded. See [suite routing](../references/suite.en.md).

When upgrading from the old `douyin-brain` name under the same Windows user, the installer can discover a single old configuration and reuse its workspace, encrypted key, and tasks. It backs up the old configuration and Skill and retains a compatibility entry under the old name. If it finds multiple different workspaces, it returns `needs_workspace_choice` with candidates. The Agent should present them, ask once which one to use, and rerun the installer with that path; workspaces and tasks are not merged:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\install.ps1' -Workspace '<chosen workspace>'
```

## 3. Configure Doubao Speech when needed

To transcribe media, you need a Volcengine account and your own speech-service credentials. Existing-text tasks and independent creator video downloads do not call speech recognition. The installer does not open the key window by default; configure it when you need it. Opening an account, accepting service or billing terms, and solving CAPTCHA are your decisions and actions.

1. Sign in to [Volcengine](https://signin.volcengine.com/auth/signup). Open the [speech service activation page](https://console.volcengine.com/speech/new/setting/activate?projectName=default).
2. Select the intended project and enable **recording file recognition, fast version** (`volc.bigasr.auc_turbo`). Review the quota and pricing shown for your account.
3. In the **same project**, create or copy a speech key from the [API key page](https://console.volcengine.com/speech/new/setting/apikeys?projectName=default). Switch away from `default` if your service uses another project. A Volcengine Ark chat-model key is not a speech key.
4. Open `配置豆包.cmd`, paste the key into the local configuration window, and save it. Do not send it in the Agent chat; for older APP ID plus Access Token credentials use `配置豆包旧版.cmd`. If you explicitly want the installer to open this window, the Agent can add `-ConfigureSpeech`; `-NoApiWindow` suppresses it if both are present.
5. Ask the Agent to transcribe a short recording you choose. This sends audio to the service and may use quota or incur charges. Compare the result with the audio.

The detailed [Doubao Speech guide](../references/doubao-setup.md) covers the Chinese-language console workflow, legacy credentials, and troubleshooting. The configuration dialog's tutorial button opens a native local guide window without relying on the default browser; a separate offline HTML version is also included. The official documentation was checked on November 5, 2026; that date does not imply an authenticated console walkthrough.

## 4. Understand the result

The installer writes `%LOCALAPPDATA%\dyb-douyinbrain\install-result.json`. The default workspace is `dyb-douyinbrain` under Windows Documents; no knowledge base is created by default. Existing registered paths and user-specified paths take precedence. Choose an existing library or create an empty one only when you request archiving; creating it does not archive past tasks.

| Status | Meaning |
|---|---|
| `installed` | Local installation and credential-presence checks completed. Cloud recognition has not thereby been verified. |
| `awaiting_api` | A speech credential has not been saved. Existing text work and independent profile downloads can continue; configure speech before transcribing media. This does not mean the entire local installation failed. |
| `needs_workspace_choice` | Several different workspaces were found. Choose a candidate and rerun with `-Workspace`. |
| `dependencies_pending` | Dependencies were skipped for an isolated test; do not report this as a complete media environment. |
| `failed` | Inspect `stage` and the error and address the actual failure. |

`local_entry_verified` concerns the local entry point; `live_asr_requests=0` means installation did not make a live recognition request. The `doctor` command checks local dependencies and whether credentials exist. It does not log in to Douyin, validate cloud permissions, or call speech recognition.

The Agent can read `skill_file`, `runtime_reference`, and `onboarding_reference` from the result and use `entrypoint` in the current conversation. `welcome` reads the introduction and local readiness; `onboarding.due` indicates whether the current introduction revision has been presented. After actually presenting it in chat, and only then, the Agent records it with `welcome --acknowledge`; this does not mean you understood it, approved paid work, or that cloud access has been verified. Neither installation nor diagnostics records presentation automatically. For example:

```powershell
& '<installed skill>\scripts\invoke.ps1' doctor
& '<installed skill>\scripts\invoke.ps1' welcome --lang en
```

## 5. Use it

Send a link or file along with the desired outcome. For example: “Transcribe this link, proofread it, and do not add it to a knowledge base.” Routine acquisition runs headlessly in the background. For ordinary creator-profile transcription, specify the latest number of posts, a date range, or all posts; an explicit full-profile analysis or download already supplies its scope. If the platform prevents the program from reaching the end of a profile, the result is incomplete.

For a title-and-caption-only profile analysis, the Agent uses available metadata without speech recognition. For full creator-content analysis, it previews new recognition usage and obtains authorization for that batch. Existing SRT files can be edited directly by the Agent and saved separately with their timecodes; `plan-text` only imports TXT or Markdown. In chat, expect actual findings and examples, readable text or a clearly marked excerpt, or download results before the detailed files.

Batch failures are isolated and successful items keep their original numbers. On resume, valid successful caches are checked before network acquisition. Read the whole transcript before focusing image or audio review on uncertain numbers, names, or conflicting details; the Agent records only evidence it actually checked. The 1.3.0 local candidate was tested on a fixed sample through anonymous acquisition, live recognition, and visual review; some acquisitions failed and audio was not listened to. See the [previous verification record](verification/v1.3.0.md); it does not establish the results of the current 1.3.1 round.

For each link, acquisition has 90 seconds from starting metadata retrieval through audio verification, with at most two background acquisition workers. The browser can be reused, but each link gets a fresh context. In link batches, verified audio can enter serial recognition in the parent process while other acquisition continues. Recognition is not interrupted by the acquisition limit; final results retain input order and failure positions. For an anonymous check without speech recognition, use `inspect-source <link> --anonymous-only`; add `--download-audio` to verify audio as well. Without it, the check covers metadata only. An existing task can use `run <task> --anonymous-only` to avoid saved login state.

New transcriptions record the local source-media hash so audio and images can be checked against the same source. Older results without that binding report `legacy_unrecorded` and cannot be claimed as verified to share a source. Complete prepared frame sets can be reused when the source hash, range, and parameters match and cached files pass validation. Overlapping ranges can also reuse verified pictures by source hash and original frame index; timestamps correspond to the original frames. Preparation alone does not complete review.

When the user asks to review only existing material, add `--cached-only` to `prepare-review`. It can extract frames from an existing local video; missing source media or audio is reported as a gap rather than fetched online. Without that option, if an older task needs pictures and lacks a complete video, the program may refresh the material through the time-limited acquisition path. Preparing review never calls speech recognition.

For existing text, ask for proofreading, analysis, or a spoken-script rewrite directly. Archiving occurs only when you request it; creating the empty default knowledge base does not import past work.

## Privacy and network access

Downloaded media, extracted audio, transcripts, browser state, and task records remain in the configured local workspace. Credentials are encrypted for the current Windows user using DPAPI; another Windows user or computer must configure them again. The installation ZIP does not carry your credentials, browser state, or task history.

The program contacts Douyin to acquire media, and sends audio to Doubao Speech when you request recognition. Installing dependencies also downloads components. Routine acquisition does not use Computer Use, automatically log in, solve CAPTCHA, or use a third-party paid parser. Login or verification is reported as required only when a visible blocking container explicitly asks for it; words in a title or post and an ordinary login button do not prove a block. A visible Douyin browser opens only when you explicitly request login, verification, or interface troubleshooting; you handle any login or CAPTCHA. Failed or unknown paid requests should be checked before an explicitly requested retry.

If setup fails, inspect the reported stage, network availability, Windows permissions, and missing dependency. If speech authentication fails, check the correct project, the speech key, service activation and available quota; a local `doctor` success cannot establish any of these cloud-side conditions. Never share the key, cookies, or verification codes in a bug report.
