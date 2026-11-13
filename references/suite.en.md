# CY-CharmYee suite: routing and shared rules

> The base suite starts at 1.4.0; recovery is available from 1.5.0. Availability depends on the actual installation, host discovery, and task results.

## Choose an entry

The entries are one product with shared installation, configuration, updates, workspace, and runtime. Route a clear single-purpose request directly to its child Skill. Use the `cy-charmyee` main entry for combined or unclear requests, configuration, and maintenance. Explicitly invoked child Skills may handle existing text within their supported scope; this does not broaden automatic discovery to unrelated requests.

| Entry | Purpose |
|---|---|
| `cy-transcribe` | Transcribe or proofread Douyin and local audio/video; handle related subtitles and exports. |
| `cy-analyze` | Analyze an individual Douyin post, local audio/video, or a creator profile. |
| `cy-download` | Batch-download creator-profile videos and captions. |
| `cy-write` | Rewrite, polish, or shorten Douyin or audio/video-related spoken scripts. |
| `cy-knowledge` | Archive sources and synthesize topics under explicit requests or enabled collection scope. |
| `cy-vault` | Life, work, and learning knowledge, continuing interviews, and everyday context maintenance. |

Each child Skill's `scripts/invoke.ps1 guide` reports `shared_root`, `entrypoint`, `references`, version, and layout; a registered installation also reports `workspace`. Source and installed layouts differ, so use the actual output. On `status=error` or a nonzero exit, report the real error and stop rather than guessing paths or proceeding with an inconsistent installation. The same child entry forwards other commands to the shared runtime. Calling a child Skill means the current Agent reads and executes its instructions; it does not automatically spawn an Agent. The optional parallel visual-review conditions for creator analysis remain in [creator.en.md](creator.en.md).

## First introduction, updates, and configuration

The suite shares one first-introduction state. Before installation, introduce the nine capability groups, examples, outputs, and speech-setup needs in chat using [onboarding.en.md](onboarding.en.md); after installation use `welcome` to read `onboarding.due` and readiness. When an introduction is due or requested, present it in chat before `welcome --acknowledge`. This records presentation, not comprehension, authorization, or live cloud validation. An introduction through one entry need not be repeated for each child Skill. Continue an already clear request after the introduction.

For every chat in which the suite participates, run `check-update` as described in [runtime.md](runtime.md#版本检查与升级). Remind once per real chat when the official stable release is newer; repeated checks in that chat are deduplicated, while a new chat gets its own reminder. The 24-hour cache reuses Release-check results and does not suppress reminders across chats. Pass a real session ID when available; otherwise the Agent deduplicates within the conversation without inventing a global ID. Continue work that does not depend on an unavailable check, and identify previously confirmed release information as stale. Update only when the user explicitly requests it. Follow [setup.md](setup.md) and the installation guide for configuration or migration. All entries share settings and credentials; honor the user's chosen paths and do not configure each child separately. If no workspace is registered, the Agent can still handle existing text directly; configure the intended workspace or use the text-only entry in the runtime guide when a persistent task is needed.

## Execute and deliver

For continued work, repeated inputs, or edits to prior drafts, follow [recovery and reuse](continuation.en.md). Read the next-action summary and actual authority, then continue the requested outcome; resume preserves scope, while update refreshes it.

- Act on a clear goal and preserve still-valid authorization; ask the most important question only if material or intent is unclear. Ordinary profile transcription needs a scope, while an explicit full-profile analysis or download already supplies one.
- Process existing text directly, preserving the source and without speech recognition. For media, follow [runtime.md](runtime.md) to acquire audio, call Doubao Speech, and review using the Agent's actual capabilities. Its acquisition, login, paid-retry, and valid-cache rules continue to apply.
- Follow [creator.en.md](creator.en.md) for profile analysis or download. Preview and obtain authorization for each batch of new creator speech recognition; retain valid existing authorization. Metadata-only analysis and independent downloading do not call recognition.
- Archive or compile under explicit requests or enabled personal-vault scope, following the destination library and [knowledge.md](knowledge.md). Ordinary `dy-...` and creator `creator-...` IDs are not interchangeable. For combined requests, read actual valid outputs; when no direct command exists, prepare, write, and read back under the user's authorization without fabricating a native task or publication.
- Give the actual result in chat first: text or a marked excerpt for transcription and rewriting, findings with evidence and coverage for analysis, successes/failures and quality for downloads, or actual write status for archiving; then attach files. State incomplete, uninspected, unverified, and failed parts accurately.

## Combined work and resumption

For combined goals or resumption across native tasks, use the lightweight `work` record described in [combined work](work.en.md) to link real tasks and artifacts. Ordinary single-step tasks need no such record. It does not execute steps, grant speech or publication authorization, or replace reading native tasks and checking results.

## Personal knowledge integration

In relevant chats and tasks, each entry runs read-only `kb context --task <stable-id>`. When disabled, continue the original task. When enabled, retrieve and save only within authorized domains. New libraries enable life, work, and learning by default; existing users keep their prior collection scope. Legacy `creative` maps to `work`, and `pending_domains` marks new domains that are not authorized yet. Directory migration or a refreshed host entry does not expand scope; after explicit authorization, use the existing path and scope with `kb enable --vault <existing-path> --scope <workspace|agent> --all-domains --evidence ...`. Preserve explicit new facts, changed states or goals, actual outcomes, and reusable work, then update relevant topics and the index. Keep the user's words, facts, experiences, and unconfirmed inferences distinguishable; ordinary chat is not indiscriminately archived. Record a temporary no-save instruction with `kb skip-task` before collection. Deliver completed work even when storage remains pending, and retry from actual files. Follow [personal-vault](personal-vault.en.md) and [personal-domains](personal-domains.en.md) for interviews and migration.

Resume personal-vault interviews and generic collection with `kb context` / `kb retry`. Ordinary media `resume` does not search these records; not_found there does not imply lost knowledge progress.
