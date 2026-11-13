# 组合任务与续办

先按[恢复与复用](continuation.md)用 `resume --task <workID>` 获取当前目标、有效成果和下一步；未知 ID 时先 `resume` 查候选。它从现有总记录与原生记录计算摘要，不建立另一套任务状态。

跨功能的组合任务，或续办时需要串联多个原生任务，用 `work` 保存轻量总记录；普通单步任务不必额外创建。续办先用 `work list` 查找，必要时用 `--task <原生任务 ID>` 筛选，再 `work show <workID>` 读取步骤、依赖、原生产物和当前有效性。输出的 `steps[].effective_status`、`ready`、`blocked_by`、`source_artifacts`、`artifact_issues`、`dependency_issues`、`native_status` 及顶层 `ready_steps` 供选择下一步；继续前仍需读取实际原生任务中的授权与产物。命令只读计算状态，不联网或发起付费请求。

新建组合记录时，在 workspace 准备计划 JSON，`request` 保留用户原话，`inputs` 写实际素材，步骤按展示及依赖顺序排列；依赖必须指向较早的步骤。例如：

```json
{
  "request": "<用户实际要求>",
  "inputs": ["<实际链接或文件路径>"],
  "steps": [
    {"id": "extract", "skill": "cy-transcribe", "instruction": "<本步骤目标>", "depends_on": [], "accept_partial": false},
    {"id": "rewrite", "skill": "cy-write", "instruction": "<本步骤目标>", "depends_on": ["extract"], "accept_partial": false}
  ]
}
```

```powershell
& $dyRun work list                         # 续办先查；可加 --task <原生任务 ID>
& $dyRun work create --file '<计划.json>'   # 从实际输出取得 workID
& $dyRun work link <workID> <stepID> --task <dy-或creator-任务ID>
& $dyRun work record <workID> <stepID> --file '<步骤结果.json>'
& $dyRun work show <workID>
```

`link` 只关联已存在的原生任务，不改原记录；同一原生任务可按实际情况关联多个步骤，旧任务无需批量迁移。每次登记前在 workspace 准备结果 JSON：

```json
{
  "status": "completed",
  "summary": "<实际结果和缺口>",
  "coverage": "<实际覆盖范围>",
  "artifacts": [{"file": "<workspace 内真实文件路径>", "role": "review"}]
}
```

状态可为 `running`、`completed`、`partial`、`blocked`、`pending`；`completed` 或 `partial` 至少登记一个已存在的产物，程序保存 SHA。角色可用 `raw`、`review`、`report`、`rewrite`、`subtitle`、`video`、`catalog`、`receipt`、`other`。外部源素材可保留原路径；登记产物须在 workspace 内，例如原生任务目录或 `runs/work-<ID>/`。知识库外部目标以 workspace 内真实回执关联。

完成步骤前需满足依赖，默认只接受已完成的前序步骤；只有用户明确允许用部分材料时才设置 `accept_partial: true`，并在结果中写清范围，整个任务不能因此说成全量完成。`work show` 校验当前状态与文件有效性，文件存在不证明内容质量、知识库发布或用户验收。`work` 不识别意图、不执行步骤、不授权或扩大语音用量；实际操作仍按各原生入口及现有授权执行。

已完成或部分完成的步骤若发现上游产物路径或哈希与登记时的快照不一致（例如上游产出新版本），`dependency_issues` 会标记 `upstream_artifacts_changed`，该步骤的 `effective_status` 为 `stale`。先读取当前有效的上游材料并检查受影响的成果，按需重做后再登记；文件校验通过也不意味着旧结果仍适用于新材料。
