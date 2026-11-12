# Combined work and resumption

Start with `resume --task <workID>` as described in [recovery](continuation.en.md) to inspect the goal, valid results, gaps, and next actions. Use `resume` to find candidates when the ID is unknown. This reads existing native and work records rather than maintaining a second task database.

Use a lightweight `work` record for combined goals or resumption across native tasks; ordinary single-step tasks do not need one. On resumption, search with `work list` (optionally `--task <native-task-ID>`), then use `work show <workID>` to inspect steps, dependencies, linked tasks, artifacts, and their current validity. The output's `steps[].effective_status`, `ready`, `blocked_by`, `source_artifacts`, `artifact_issues`, `dependency_issues`, `native_status`, and top-level `ready_steps` help select the next step; still read the actual native task's authorization and artifacts before continuing. Showing a record is read-only and makes no network or paid request.

For a new record, prepare a plan JSON in the workspace with the user's actual words and material. Steps appear in display order and may depend only on earlier steps:

```json
{
  "request": "<actual user request>",
  "inputs": ["<actual link or file path>"],
  "steps": [
    {"id": "extract", "skill": "dyb-transcribe", "instruction": "<step goal>", "depends_on": [], "accept_partial": false},
    {"id": "rewrite", "skill": "dyb-write", "instruction": "<step goal>", "depends_on": ["extract"], "accept_partial": false}
  ]
}
```

```powershell
& $dyRun work list                         # search first when resuming; optionally add --task <native ID>
& $dyRun work create --file '<plan.json>'  # take workID from the actual result
& $dyRun work link <workID> <stepID> --task <dy-or-creator-task-ID>
& $dyRun work record <workID> <stepID> --file '<step-result.json>'
& $dyRun work show <workID>
```

`link` associates an existing native task without changing it; a task may be linked to several steps when appropriate. There is no need to migrate old tasks in bulk. Prepare a step-result JSON in the workspace before recording it:

```json
{
  "status": "completed",
  "summary": "<actual result and gaps>",
  "coverage": "<actual coverage>",
  "artifacts": [{"file": "<real file path inside workspace>", "role": "review"}]
}
```

Status can be `running`, `completed`, `partial`, `blocked`, or `pending`. `completed` and `partial` require at least one existing artifact; the program records its SHA. Roles are `raw`, `review`, `report`, `rewrite`, `subtitle`, `video`, `catalog`, `receipt`, and `other`. External inputs may retain their original paths; registered artifacts must be inside the workspace, such as a native task directory or `runs/work-<ID>/`. Associate an external knowledge-base target through its real receipt inside the workspace.

Dependencies must be satisfied before marking a step complete, normally by completed earlier steps. Set `accept_partial: true` only when the user explicitly allows partial material; describe the coverage, and do not call the overall work complete in full. `work show` checks current status and file validity; file existence does not establish content quality, knowledge-base publication, or user acceptance. `work` does not classify intent, execute steps, authorize speech, or expand authorization. Execute each actual step through its native entry and existing authorization.

When a completed or partial step detects that an upstream artifact path or hash differs from its recorded input snapshot (for example, after an upstream result is revised), `dependency_issues` reports `upstream_artifacts_changed` and its `effective_status` becomes `stale`. Read the currently valid upstream material and inspect the affected result; redo the work as needed before recording it again. A valid file hash alone does not make the old result applicable to new material.
