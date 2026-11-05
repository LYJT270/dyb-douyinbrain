# Getting started with Douyin-brain on Windows

Douyin-brain works with an Agent that can read local files and run terminal commands. Its bundled engine processes media locally and sends audio to your own Doubao Speech account for recognition. You can work with existing text without configuring speech credentials.

## 1. Get the source or installation package

Use the repository source root, or download and extract the installation ZIP from [the latest Release](https://github.com/ScarfaceAI/dyb-douyinbrain/releases/latest). The folder to install from contains `SKILL.md` and `scripts/install.ps1`.

Python is not a prerequisite: the installer attempts to prepare Python, a virtual environment, dependencies, FFmpeg, and Chromium. Setup needs network access and may require you to resolve a Windows permission or package-manager problem.

## 2. Install

The simplest manual route is to double-click `install.cmd` in that folder. Alternatively, ask your Agent to read [INSTALL.md](../INSTALL.md) and install it. From the source or extracted folder, the Agent can run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\install.ps1'
```

The default `-Agent auto` uses the user's shared `.agents/skills` directory and attempts a Claude bridge when an existing configuration is detected. It preserves an independent installation with the same name. You may choose an adapter explicitly, for example `-Agent codex`, `-Agent claude`, or `-Agent gemini`; `deepseek`, `cursor`, `opencode`, `shared`, `all`, and `custom` are also available. Supply `-SkillsRoot 'D:\AgentSkills'` to choose a skills parent directory; an explicit root does not add a Claude bridge. See [INSTALL.md](../INSTALL.md) for examples.

All adapters use the same core engine. Automatic discovery varies by Agent and configuration; if a skill list does not refresh, ask the Agent to read the installed `SKILL.md` directly. Installation adapters and a common skill format do not, by themselves, prove that each Agent's real interactive session has been tested.

## 3. Configure Doubao Speech

You need a Volcengine account and your own speech-service credentials. Opening an account, accepting service or billing terms, and solving CAPTCHA are your decisions and actions.

1. Sign in to [Volcengine](https://signin.volcengine.com/auth/signup). Open the [speech service activation page](https://console.volcengine.com/speech/new/setting/activate?projectName=default).
2. Select the intended project and enable **recording file recognition, fast version** (`volc.bigasr.auc_turbo`). Review the quota and pricing shown for your account.
3. In the **same project**, create or copy a speech key from the [API key page](https://console.volcengine.com/speech/new/setting/apikeys?projectName=default). Switch away from `default` if your service uses another project. A Volcengine Ark chat-model key is not a speech key.
4. Paste the key into the local configuration window and save it. Do not send it in the Agent chat. If you skipped it during installation, reopen the window with `配置豆包.cmd`; for older APP ID plus Access Token credentials use `配置豆包旧版.cmd`.
5. Ask the Agent to transcribe a short recording you choose. This sends audio to the service and may use quota or incur charges. Compare the result with the audio.

The detailed [Doubao Speech guide](../references/doubao-setup.md) covers the Chinese-language console workflow, legacy credentials, and troubleshooting. The configuration dialog's tutorial button opens a native local guide window without relying on the default browser; a separate offline HTML version is also included. The official documentation was checked on November 5, 2026; that date does not imply an authenticated console walkthrough.

## 4. Understand the result

The installer writes `%LOCALAPPDATA%\dyb-douyinbrain\install-result.json`. The default workspace is `dyb-douyinbrain` under Windows Documents; a separate empty `dyb-douyinbrain-知识库` knowledge base is created when needed. Existing registered paths and user-specified paths take precedence.

| Status | Meaning |
|---|---|
| `installed` | Local installation and credential-presence checks completed. Cloud recognition has not thereby been verified. |
| `awaiting_api` | A speech credential has not been saved. Existing text work can continue; configure speech before transcribing media. |
| `dependencies_pending` | Dependencies were skipped for an isolated test; do not report this as a complete media environment. |
| `failed` | Inspect `stage` and the error and address the actual failure. |

`local_entry_verified` concerns the local entry point; `live_asr_requests=0` means installation did not make a live recognition request. The `doctor` command checks local dependencies and whether credentials exist. It does not log in to Douyin, validate cloud permissions, or call speech recognition.

The Agent can read the installed `skill_file` and `runtime_reference` from the result and use `entrypoint` in the current conversation. For example:

```powershell
& '<installed skill>\scripts\invoke.ps1' doctor
```

## 5. Use it

Send a link or file along with the desired outcome. For example: “Transcribe this link, proofread it, and do not add it to a knowledge base.” For a creator profile specify the latest number of posts, a date range, or all posts. If the platform prevents the program from reaching the end of a profile, the result is incomplete.

For existing text, ask for proofreading, analysis, or a spoken-script rewrite directly. Archiving occurs only when you request it; creating the empty default knowledge base does not import past work.

## Privacy and network access

Downloaded media, extracted audio, transcripts, browser state, and task records remain in the configured local workspace. Credentials are encrypted for the current Windows user using DPAPI; another Windows user or computer must configure them again. The installation ZIP does not carry your credentials, browser state, or task history.

The program contacts Douyin to acquire media, and sends audio to Doubao Speech when you request recognition. Installing dependencies also downloads components. The user handles any login or CAPTCHA. Failed or unknown paid requests should be checked before an explicitly requested retry.

If setup fails, inspect the reported stage, network availability, Windows permissions, and missing dependency. If speech authentication fails, check the correct project, the speech key, service activation and available quota; a local `doctor` success cannot establish any of these cloud-side conditions. Never share the key, cookies, or verification codes in a bug report.
