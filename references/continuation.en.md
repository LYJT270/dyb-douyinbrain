# Resume tasks and reuse existing material

Resume is triggered by the current Agent in the same workspace, including after a new conversation or application restart. There is no background service. Continue the requested end-to-end outcome within valid authorization without asking again at each intermediate step.

## Find and continue

```powershell
& $dyRun resume
& $dyRun resume --input '<original input>' --purpose rewrite --instruction '<original goal>'
& $dyRun resume --input '<original input>' --request '<full combined request>'
& $dyRun resume --task <dy-, creator-, or work-ID>
```

This reads local records and files only: no network, recognition, execution, or new authority. `matched` requires an unambiguous source and goal; `choose_task` returns candidates for the Agent to inspect. Ask the user only if ambiguity remains. Semantic matching and short-link resolution are not performed by this command; select an explicit ID after inspecting candidates when appropriate.

Read `recovery.next_actions`, the actual native task authorization, and valid artifacts, perform the applicable action, record the result, and resume again. Independent work can continue; blocked dependencies retain their gaps. Resuming uses the saved scope and observation time. Only an explicit update request refreshes a profile. Ordinary media recovery uses `run <task> --saved-scope`, limited to saved jobs; creator recovery uses its saved catalog without calling `discover`. Failed or unknown paid submissions still require investigation and explicit retry instructions.

## Save individual items and preserve edits

`register-review` and `register-spoken` accept repeated `--item <media-ID>` paired in order with `--file <file>`. They update only those successful items and preserve the others. Omitting `--item` retains whole-batch registration.

New registrations store immutable version snapshots and source dependencies. Recovery distinguishes valid, edited, missing, stale, unreadable, and unregistered working files. Read edits against `snapshot_file` before continuing; `diff` is only a bounded excerpt. Keep user edits and save new output separately. Legacy records without snapshots cannot reconstruct overwritten text; inspect an old delivery if available. Recheck affected downstream outputs when inputs change. Independent items proceed; a whole-batch conclusion waits for missing material or an explicit decision to accept partial coverage.

## Ask a new question of saved material

```powershell
& $dyRun reanalyze <dy-task> --instruction '<new user-requested question>'
& $dyRun creator reanalyze <creator-task> --instruction '<new question>'
```

Both create separate native tasks and retain the parent. Ordinary tasks reuse verified text and reviewed copies. Creator tasks freeze the catalog, observation times, and available material, without carrying paid authorization. Offline tasks cannot discover, acquire, or request speech; explain additional needs before creating an appropriately authorized online task.

Creator analysis continues through `prepare`, `claim`, actual analysis, `record`, and `report`. Offline preparation uses local material only; normal tasks can opt into the same boundary with `prepare --cached-only`. Repeated preparation retains valid pending/claimed packets. Finish or release active claims before forced reanalysis.

New tasks do not inherit a previous session's tool capabilities. When the current Agent can actually inspect images, pass `--images` to `creator reanalyze` or set `creator capabilities <task> --images` before preparation. Declare optional parallel vision only when currently available.

A packet with `previous_review` allows `review: {"reuse_previous": true}` after reading its real evidence. The runtime checks source, text, and image versions and records `reused_from`. This reuses historical review and never asserts that the current Agent saw the images again. Record newly inspected images explicitly; targeted local supplements still use `creator detail` and registered manifests. Each new question requires its own grounded item analyses and report.

When evidence is insufficient, inspect available local material with actual tools, then report supported findings and remaining gaps. A request for complete coverage remains incomplete. Save incremental results, give concise meaningful progress, show interim content on request, and deliver the final requested result in chat with files as supplements.
