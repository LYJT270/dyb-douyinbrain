# Creator profile analysis and video downloads

> This guide describes the current local source candidate; it has not been publicly released. Check this round's actual evidence for real-account, paid-speech, and visual-review verification.

Give the Skill one public Douyin profile link or shared text containing one profile link. `analyze` covers accessible videos and image posts; `download` independently downloads profile videos and their captions, without image-post export or speech recognition. For ordinary scoped transcription, see [runtime.md](runtime.md).

Use the installed Skill's PowerShell entry point. Replace `<task>`, `<token>`, packet IDs, and post IDs with actual output values; returned artifact paths are relative to `workspace`.

```powershell
$dyRun = '<skill>\scripts\invoke.ps1'
& $dyRun creator plan '<profile link or shared text>' --mode analyze --images --instruction '<analysis request>'
& $dyRun creator discover <task>
& $dyRun creator show <task>
```

Use `--images` only when the current host can actually open and understand images. Add `--parallel-vision` only if it supports independent parallel visual tasks; later, update those declarations with `creator capabilities <task> --images [--parallel-vision]`. Without image capability, the task can still discover posts and prepare free media, but cannot authorize this workflow's complete visual analysis or claim it was completed.

Analysis defaults to an available `compact` media version; specify `--quality best` on `plan` when the highest available quality is needed. Download mode defaults to `best`.

`plan` does not download media or submit speech recognition; resolving a short link makes a normal HTTP request. `discover` saves each page in the background without speech recognition. `--anonymous-only` excludes an existing dedicated browser profile; `--max-seconds N` adjusts the discovery time parameter, default 600 seconds. A run that does not reach the pagination end is incomplete, though discovered items can still be processed and delivered.

`pagination_complete` indicates only that the final page was reached. If raw rows cannot be normalized, `discovery_complete` remains false even after that point. Such rows are recorded in `discovery.unresolved_records` and retained with their page-file references and row indexes in `原始作品.jsonl` for review rather than guessed or merged.

Every `discover` refreshes the profile before evaluating caches. An unfinished refresh retains the task's existing posts and marks items not seen in the current scan. A complete refresh excludes those not seen from the current effective catalog; old pages, tasks, and material are retained. Not seen is not proof of deletion. The scope is public content accessible to the current session.

## Titles or captions only

For an explicit titles-, captions-, or metadata-only analysis, discover and export the profile, then have the Agent actually read the available fields in `作品明细.csv` and cite relevant posts:

```powershell
& $dyRun creator plan '<profile link or shared text>' --mode analyze --instruction '<actual titles/captions-only request>'
& $dyRun creator discover <task>
& $dyRun creator export <task>
```

Do not run `creator run` for this route: it does not download posts or call Doubao Speech. The list depends on what the platform currently returns. The exported `报告.md` does not automatically contain semantic conclusions; the Agent saves its own analysis and presents conclusions, examples, and pagination coverage in chat. Titles and captions do not establish the full spoken or visual content.

## Preview and authorize speech

```powershell
& $dyRun creator preflight <task>
# Repeat --item to select particular discovered posts:
& $dyRun creator preflight <task> --item douyin-<numeric-post-ID>
# Supply an hourly price only when it actually applies to the user's account:
& $dyRun creator preflight <task> --price-per-hour <actual-hourly-price>
```

Preflight does not call the speech API. Show the user the number of new or remaining items, known duration, unknown-duration count, and estimated usage for currently discovered posts. Unknown duration is not zero, and platform-provided duration is an estimate. Estimate cost only when the applicable unit price, billing conditions, and duration are known. The program multiplies duration by the hourly price; it does not automatically account for plans, tiers, rounding, or credits, and the estimate is not a bill. Account currency and quota come from the user's account. Before any recognition authorization, `creator run <task>` can prepare media without paid recognition, then preflight can be repeated; a run on an already authorized task may submit recognition within that authorization.

After the user sees the preview and explicitly authorizes the batch, record its `usage.token` and the user's actual words:

```powershell
& $dyRun creator authorize <task> --quote <token> --evidence '<actual user authorization>'
& $dyRun creator run <task>
```

Authorization binds the previewed posts and content versions. New or changed items require a new preview and authorization. If the user wants a batch usage cap, `authorize` accepts `--max-audio-seconds <seconds>`; this caps audio usage, not money. Check failed or unknown paid requests before retrying, then use `creator run <task> --retry-evidence '<actual user retry request>'`. Successful chunks are reused rather than silently resubmitted.

`run` defaults to 2 acquisition workers and 1 speech worker. `--download-workers` accepts 1–4; `--asr-workers` accepts 1–2 and should only be increased when account capacity permits. `--item-timeout` is the per-item acquisition timeout parameter, default 300 seconds, and does not interrupt speech recognition. Repeat `--item` to select posts, or use `--limit-items N` for a smaller run; neither makes the full profile complete. Matching, validated complete item analyses can be reused directly.

## Review packets and reporting

```powershell
& $dyRun creator prepare <task>
# Repeat --item to prepare only specific posts:
# & $dyRun creator prepare <task> --item douyin-<numeric-post-ID> --item douyin-<another-numeric-post-ID>
& $dyRun creator claim <task> --worker '<reviewer ID>'
# Read the packet and complete the review, then save the result JSON in the workspace:
& $dyRun creator record <task> --worker '<same reviewer ID>' --file '<workspace result.json>'
# Repeat for every packet; release an unfinished packet if needed:
& $dyRun creator release <task> --packet <packet> --worker '<same reviewer ID>'
```

By default, `prepare` creates review packets only for posts with available media and ready speech status. Items not ready appear in `waiting_materials_or_speech`; their covers are not fetched for preparation. Image posts may still have missing pictures, which must be reported. Repeat `--item` to narrow the selection; matching complete analyses are reused first.

`prepare` supplies full transcripts and images; it does not claim they were viewed. Strategies are `content`, `action`, and `subtitle`; `--max-frames` accepts 1–120, `--batch-size` accepts 1–16 (default 4), and `--prepare-workers` accepts 1–2 (default 2). `--reanalyze` repeats analysis under the existing `instruction` only. To apply a new angle only to existing material, read the previous task's reviewed material and save a separate report with its original coverage and observation time; do not refresh the profile or fabricate the old task's cache or completion state. There is no native offline command to change `instruction`. If the user requests a new analysis based on the current profile, create a task with `creator plan --instruction '<new request>'`, run `discover`, and reuse valid media and transcripts. Finish or release active packets before preparing again.

Read each post's description, complete transcript, cover, and prepared video frames or image-post pictures. Record review and item analysis separately in the same pass. On a host with independent visual tasks, image access, and sufficient resources, try at most two reviewers on different packets; otherwise work sequentially. Python preparation threads do not run a vision model. Investigate uncertain video moments with targeted checks; seeing an image does not mean the Agent listened to the audio.

For a targeted video check, use the post ID and times in source-video seconds:

```powershell
& $dyRun creator detail <task> --item douyin-<numeric-post-ID> --start 12 --end 14 --every-frame --max-frames 40
```

`detail` uses only the post's verified local source video and never calls speech recognition. `--every-frame` is optional; `--max-frames` defaults to 40 and accepts 1–240. The output's `supplement.file` identifies a supplementary manifest and `images` lists prepared frames. Inspect the needed frames and check whether the frame limit reduced coverage; preparation is not visual review.

The result JSON must include every item in the packet, with its actual `id` and `basis_sha256`. Use the schema and examples in the [Chinese creator guide](creator.md#实际阅读校对和逐条分析): each completed item has `review.read_full_transcript`, `review.viewed_images`, `review.text`, optional `review.corrections`, and `analysis` with `category`, `topic`, `angle`, `summary`, `opening`, `format`, and grounded `evidence`. Evidence is an exact `caption` or `transcript` quote, or a `frame` file actually viewed for that item. To use supplementary frames, add the matching `supplement.file` to that item's `review.supplement_manifests` and list actually viewed supplementary frames in `viewed_images`; the original packet's images still need to be inspected. Corrections require `before`, `after`, and evidence. Unavailable items retain their ID and basis hash with `status: "unavailable"` and a real `reason`. Never claim a picture was viewed unless it was actually inspected.

Combine recorded results chronologically, return pinned posts to their publication dates, and separate unknown dates. Interpret engagement with its observation time and content type. A workspace report JSON contains nonempty `account`, `content`, and `topics` strings plus chronological `stages`; each stage has `title`, `summary`, and chronologically ordered `item_ids` referring to analyzed posts. Include source evidence and uncertainties.

```powershell
& $dyRun creator report <task> --file '<workspace report.json>'
& $dyRun creator export <task>
& $dyRun creator show <task>
```

`outputs/creators/<account-key>/reports/<task>/` contains `报告.md` (report), `作品明细.csv` (post details), `原始作品.jsonl` (raw business data), `分析与核对.jsonl` (analysis and review), and `采集与处理状态.json` (status). Per-item report sections include topic, angle, opening, format, a link to reviewed text, and recorded uncertainties. The CSV includes title, transcript and reviewed-text paths, analysis status, category, topic, angle, summary, opening, and format. The analysis-and-review JSONL retains each post's processing state, engagement snapshot, and valid review, analysis, and visual evidence; unfinished work remains a gap.

Task records are in `runs/`; media are cached under `.cache/`. Discovery, downloads, speech, visual review, and analysis have separate counts. `discovery_complete` and final `complete` are distinct. Partial results can be delivered with their coverage and gaps stated.

In chat, first present the account and topic findings, examples grounded in specific posts, coverage, and gaps; then attach the report and details. Discovery or metadata-only analysis is not full content analysis.

## Download profile videos independently

```powershell
& $dyRun creator plan '<profile link or shared text>' --mode download
& $dyRun creator discover <task>
& $dyRun creator run <task>
& $dyRun creator show <task>
```

Download mode prioritizes the highest available version according to the quality and bitrate information returned by the platform. To choose a smaller available version, set `--quality compact` on `plan`; check the actual quality and format in the output metadata. This selects an existing version and does not automatically transcode or clean existing files. Independent videos, caption `.txt` files, and metadata `.json` files are saved under `outputs/creators/<account-key>/videos/`; a content hash may be added to a filename when an ID's content differs. Download mode never calls Doubao speech recognition.

When video acquisition fails, such as for an expired URL, the program can try refreshing its source address once. Retained partial files may be resumed, and a fully received file is validated before use. If comparable ETags show that the media changed, the resume is rejected rather than combining different versions.

Analysis and download can reuse matching media, but downloading a higher-quality version does not replace the source used for speech recognition. Reanalysis prefers the verified media bound to the transcript; if that source is missing, keep the transcript and report that the picture cannot be checked against the same source. A change limited to an image post's background-music CDN address should not invalidate otherwise unchanged image analysis.

In chat, report successful and failed download counts, verifiable quality, and destination before linking details. State incomplete discovery or unavailable quality metadata.

## Combining with ordinary text tasks

`creator-...` and ordinary `dy-...` tasks have different IDs. Ordinary `export-srt`, `archive`, and `publish` commands do not accept `creator-...`; do not invent a creator subtitle-export or publication command. For explicitly requested combined goals, inspect actual source transcripts and valid caches and follow the applicable workflow or target library rules. Where there is no direct command, the Agent prepares separate files, writes under the user's request and reads back the result, accurately reporting status and gaps. Archiving or compilation still requires an explicit request.

For combined work or resumption across tasks, the [suite work record](work.en.md) can link existing `creator-...` and `dy-...` tasks to real artifacts without changing those records. It does not make their IDs interchangeable, replace batch authorization, or create a native offline task for a new angle.
