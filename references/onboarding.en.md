# First introduction and natural-language routing

> This guide describes current source capabilities. Availability of the new personal-vault feature depends on the installed version and actual task results.

## Introduce the capabilities first

On first installation, first use, or an explicit request for a tour, explain the following nine groups in chat, in the user's language. Give a purpose, a short example, the expected output, and when Doubao Speech is needed or can be skipped. Adapt the wording rather than pasting a manual. A file link or command alone is not an introduction, and a tour does not authorize performing every feature.

| Capability | Example | Output and speech setup |
|---|---|---|
| Transcribe and proofread | “Transcribe this clip and check the names.” | A readable transcript and file. Media transcription needs Doubao Speech; proofreading existing text does not. |
| Analyze content and creators | “Analyze this video's opening.” / “Analyze topic changes across this profile's videos and image posts.” | Evidence-based post or account findings. Video recognition needs Doubao Speech; creator batches also require usage approval. A titles-and-captions-only analysis uses metadata and no recognition. |
| Download creator videos | “Download this profile's videos and captions at the best available quality.” | Videos and captions with success, failure, and quality details; no Doubao Speech call. |
| Rewrite or shorten a spoken script | “Shorten this script but keep the opening hook.” | A separate rewrite with the source preserved. Existing text needs no speech setup; transcribing media first does. |
| Organize and export | “Combine these into a TXT.” / “Proofread this SRT and keep its timecodes.” | Ordered text delivery; the Agent handles existing SRT directly and saves a separate file with timecodes preserved. Exporting SRT from recognition needs segment times. Existing text needs no speech setup. |
| Archive on request | “Archive these originals and reviews and compile a topic page.” | Actual write status under the target knowledge base's rules. Archive or compile under explicit requests or enabled collection scope; speech needs depend on the source. |
| Personal knowledge base | “Build a knowledge base and learn about my background and goals.” | A resumable profile, creative/learning modules, and opted-in retrieval and collection. No speech credentials required. |
| Resume and reanalyze | “Continue the previous task and handle unfinished items.” | Reuse valid results; reanalysis does not automatically retranscribe, and a failed paid request is retried only on explicit instruction. |
| Setup and maintenance | “Help me set up speech.” / “Check the environment.” / “Update CY-CharmYee.” | Setup guidance, readiness, migration or update results; speech setup is needed only when relevant. |

Explain the capabilities before configuration. Reuse existing configuration and request only information required for the current goal. User-specified install, workspace, and knowledge-base paths take precedence. Without a speech key, existing text and creator video downloads remain available; Douyin login is not an installation prerequisite. When recognition is needed, help the user configure it locally, without requesting a key in chat. A personal knowledge base is optional: introduce cy-vault proactively, then enable it only when chosen. Creating an empty library does not authorize collection.

The main entry and six child Skills share introduction state, configuration, and workspace; an introduction completed through one entry does not need repeating for each child. Route clear single-purpose requests to `cy-transcribe`, `cy-analyze`, `cy-download`, `cy-write`, `cy-knowledge`, or `cy-vault`; use `cy-charmyee` for combined or unclear requests and maintenance. See [suite routing](suite.en.md) for responsibilities. Automatic discovery depends on the host; the current Agent executes child Skill instructions without automatically spawning another Agent.

When the user already gave a clear task, proceed after the introduction without asking their purpose again. Ask one consequential question only if the material or goal is genuinely ambiguous; for an unexplained link, ask whether they want transcription, analysis, or download. For ordinary profile transcription, ask for a latest count, date range, or all posts if the scope is missing. Do not re-ask scope for an explicit full-profile analysis or download.

## Triggering the introduction after installation

Run `welcome` to read the introduction and local readiness without changing state; see [runtime.md](runtime.md#首次介绍与配置状态) and the actual command output. Installer, `init`, and `doctor` hints can point to this guide and command. Before an entry point exists, introduce the capabilities from this guide and check readiness after installation.

If this version's introduction is due, or the user explicitly requests a tour, actually present the nine groups in chat and summarize readiness and missing prerequisites. Only after presenting it, run `welcome --acknowledge` to record that this version was shown. The marker means shown, not understood, paid usage approved, cloud access verified, or other actions authorized. Installer, `init`, `doctor`, and read-only `welcome` do not acknowledge automatically. If the command fails, use this guide directly and report why the marker could not be saved.

## Complete workflow

Introduce the capabilities when due or requested → identify the material and goal, asking one key question only if needed → configure only prerequisites for that goal → inspect existing results and valid caches, refreshing accessible posts for a new profile batch → perform the requested acquisition, recognition, review, analysis, rewrite, or archiving stages → check actual content and coverage → present the result in chat, then attach files → resume unfinished work when requested. Existing text skips media acquisition and speech; titles/captions-only analysis skips media downloads and speech; download-only skips recognition and analysis; archiving and compilation follow explicit requests or enabled collection scope. Preview and obtain batch authorization before new paid creator speech recognition. Check failed or unknown paid requests before an explicitly requested retry.

## Route the user's actual request

The host Agent interprets the material, conversation, and user intent. `welcome` supplies introduction and readiness; it is not a semantic classifier. Perform clear requests directly. Combine explicitly requested goals in order and reuse validated caches; collect proactively within enabled scope and do not add other unrequested steps. Creator and ordinary task IDs are not interchangeable: ordinary commands such as `export-srt` and `archive` cannot accept a `creator-...` ID. For goals spanning both, work from actually available source transcripts and the target library's rules; where no matching command exists, the Agent prepares, writes and reads back the result under those rules rather than inventing a command or receipt.

For combined steps or resumption across tasks, find or create a `work` record as described in [suite routing](work.en.md), linking real native tasks and files. Ordinary single-step work does not require one. It does not execute steps or replace paid-recognition authorization, content review, or publication receipts.

| Goal | Route and boundary |
|---|---|
| Transcribe one or many posts or local media | Follow [runtime.md](runtime.md#建立与执行任务): record the actual purpose, acquire audio, use Doubao Speech, then review with available tools and deliver. |
| Proofread or analyze existing text | Preserve the source and use [content.md](content.md); batch UTF-8 TXT or Markdown via `plan-text`, without speech recognition. |
| Analyze one post or local audio/video | Use existing text or transcribe and inspect images as needed. Cite available evidence and disclose missing audio, images, or acquisition. |
| Analyze all accessible profile content and topics | Follow [creator.en.md](creator.en.md): discover videos and image posts, assess coverage and image capability, preview new speech usage and obtain batch authorization, then aggregate evidence over time. |
| Analyze titles or published captions only | Follow [metadata-only analysis](creator.en.md#titles-or-captions-only): discover and export metadata, then analyze the returned text. Do not call recognition or imply that the complete posts were viewed. |
| Download profile videos only | Follow [independent downloads](creator.en.md#download-profile-videos-independently): download accessible videos and captions, with actual quality. Do not perform recognition or claim account analysis. |
| Rewrite or shorten spoken scripts | Follow [content.md](content.md#把改稿要求落实到本批); save a separate version and record before/after comparisons for significant shortening. |
| Batch TXT or work with an existing SRT | Batch TXT or Markdown and retain order. The Agent reads an existing SRT directly and saves a separate result, preserving cue numbers, timecodes, and unrequested structure. `plan-text` does not accept `.srt`; do not claim a dedicated SRT importer. `export-srt` requires recognition results with segment times. |
| Archive / archive and compile | Follow [knowledge.md](knowledge.md) for explicitly requested stages or [personal-vault](personal-vault.en.md) for enabled collection scope. Preserve sources and actually update relevant topic pages. Prepared files are not a completed write. |
| Resume, reanalyze, retranscribe, or retry | Resume with validated caches. For the same goal use `--reanalyze`; for a new angle on existing material only, read reviewed material and save a separate report with original coverage and observation time, without refreshing the profile or fabricating the old cache. Only if a new analysis of the current profile is requested, create a task with a new `instruction`, discover posts, and reuse valid media and transcripts. Retranscription creates a separate version. Check failed or unknown paid requests, then retry only on the user's explicit instruction. |
| Configure, learn, diagnose, or troubleshoot acquisition | Follow [setup.md](setup.md), [the speech guide](doubao-setup.md), and [runtime.md](runtime.md); address actual gaps. Routine acquisition is headless; open a visible browser only for an explicit request for login, verification, or interface troubleshooting. |
| Migrate, check updates, or upgrade | Follow [INSTALL.md](../INSTALL.md) for migration. Distinguish checking from installing an update; upgrade only when requested. |

## Deliver the result in chat first

Show actual results before linking files or operational records:

- Analysis: give conclusions, examples tied to posts, text or actually viewed images, and coverage or gaps.
- Transcription, proofreading, or rewriting: include readable text. For long work, mark an excerpt and state the total and unresolved or unfinished parts; attach the complete file.
- Downloads: report successful and failed counts, actual or unknown quality, destination, and discovery limitations.
- Knowledge work: summarize the material or topic and state whether files were written, merely prepared, or failed, with relevant paths or receipts.
- Setup and maintenance: state what changed, what is available, and what still needs configuration or real-world verification.

If results are unavailable, report the actual stage rather than inventing findings. Mark partial coverage; do not promise all platform posts or a permanently running background task. Files, statuses, and prepared materials do not replace a substantive chat result or user acceptance.

## Optional personal knowledge

Introduce cy-vault: “I can build a personal knowledge base through a brief conversation, then use it during creative and learning tasks and help accumulate useful results.” Let the user opt in without blocking current work. Follow [personal-vault](personal-vault.en.md) for scope selection, one-question-at-a-time profiles, modules, no-save tasks and failure recovery.
