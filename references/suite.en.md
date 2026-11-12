# Douyin-brain suite: routing and shared rules

> The base suite starts at 1.4.0; recovery is available from 1.5.0. Availability depends on the actual installation, host discovery, and task results.

## Choose an entry

The entries are one product with shared installation, configuration, updates, workspace, and runtime. Route a clear single-purpose request directly to its child Skill. Use the `dyb-douyinbrain` main entry for combined or unclear requests, configuration, and maintenance. Explicitly invoked child Skills may handle existing text within their supported scope; this does not broaden automatic discovery to unrelated requests.

| Entry | Purpose |
|---|---|
| `dyb-transcribe` | Transcribe or proofread Douyin and local audio/video; handle related subtitles and exports. |
| `dyb-analyze` | Analyze an individual Douyin post, local audio/video, or a creator profile. |
| `dyb-download` | Batch-download creator-profile videos and captions. |
| `dyb-write` | Rewrite, polish, or shorten Douyin or audio/video-related spoken scripts. |
| `dyb-knowledge` | Archive materials or compile a knowledge topic when explicitly requested. |

Each child Skill's `scripts/invoke.ps1 guide` reports `shared_root`, `entrypoint`, `references`, version, and layout; a registered installation also reports `workspace`. Source and installed layouts differ, so use the actual output. On `status=error` or a nonzero exit, report the real error and stop rather than guessing paths or proceeding with an inconsistent installation. The same child entry forwards other commands to the shared runtime. Calling a child Skill means the current Agent reads and executes its instructions; it does not automatically spawn an Agent. The optional parallel visual-review conditions for creator analysis remain in [creator.en.md](creator.en.md).

## First introduction, updates, and configuration

The suite shares one first-introduction state. Before installation, introduce the eight capability groups, examples, outputs, and speech-setup needs in chat using [onboarding.en.md](onboarding.en.md); after installation use `welcome` to read `onboarding.due` and readiness. When an introduction is due or requested, present it in chat before `welcome --acknowledge`. This records presentation, not comprehension, authorization, or live cloud validation. An introduction through one entry need not be repeated for each child Skill. Continue an already clear request after the introduction.

At the start of a new task, run `check-update` as described in [runtime.md](runtime.md#版本检查与升级), and notify only when `should_notify=true`. If checking is unavailable, report the actual condition and continue work that does not depend on it. Apply an update through the main entry when the user explicitly requests it and reread the new instructions according to the result. Follow [setup.md](setup.md) and the installation guide for configuration or migration. All entries share settings and credentials; honor the user's chosen paths and do not configure each child separately. If no workspace is registered, the Agent can still handle existing text directly; configure the intended workspace or use the text-only entry in the runtime guide when a persistent task is needed.

## Execute and deliver

For continued work, repeated inputs, or edits to prior drafts, follow [recovery and reuse](continuation.en.md). Read the next-action summary and actual authority, then continue the requested outcome; resume preserves scope, while update refreshes it.

- Act on a clear goal and preserve still-valid authorization; ask the most important question only if material or intent is unclear. Ordinary profile transcription needs a scope, while an explicit full-profile analysis or download already supplies one.
- Process existing text directly, preserving the source and without speech recognition. For media, follow [runtime.md](runtime.md) to acquire audio, call Doubao Speech, and review using the Agent's actual capabilities. Its acquisition, login, paid-retry, and valid-cache rules continue to apply.
- Follow [creator.en.md](creator.en.md) for profile analysis or download. Preview and obtain authorization for each batch of new creator speech recognition; retain valid existing authorization. Metadata-only analysis and independent downloading do not call recognition.
- Archive or compile only when explicitly requested, following the destination library and [knowledge.md](knowledge.md). Ordinary `dy-...` and creator `creator-...` IDs are not interchangeable. For combined requests, read actual valid outputs; when no direct command exists, prepare, write, and read back under the user's authorization without fabricating a native task or publication.
- Give the actual result in chat first: text or a marked excerpt for transcription and rewriting, findings with evidence and coverage for analysis, successes/failures and quality for downloads, or actual write status for archiving; then attach files. State incomplete, uninspected, unverified, and failed parts accurately.

## Combined work and resumption

For combined goals or resumption across native tasks, use the lightweight `work` record described in [combined work](work.en.md) to link real tasks and artifacts. Ordinary single-step tasks need no such record. It does not execute steps, grant speech or publication authorization, or replace reading native tasks and checking results.
