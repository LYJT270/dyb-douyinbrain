# 更新记录

## 1.7.0 - 2026-11-13

- 个人知识库扩展为生活、工作、学习三个方向。新启用后默认都参与，起步选择顺序为 1 学习、2 工作、3 生活；选择只决定先从哪里聊，不限制其他方向。
- 访谈每次只问一个有用问题，基础资料齐全后仍可继续，直到用户暂停、停止或换话题。明确任务优先；相关日常任务会读取并使用已有资料，并在开启范围内积累明确的新信息和实际成果。
- 旧收录范围继续有效，`creative` 作为 `work` 的兼容别名。已有知识库的完整重分类先生成映射预览，经用户一次确认后再备份并迁移；预览会拒绝重复的规则或导航替换目标（Windows 大小写等价也视为重复）。迁移修复受支持的链接、索引和运行状态，历史回执保持不变，且可恢复；目标库规则和现行写入入口不能绕过。
- 新版提醒按参与的聊天分别去重，每个聊天对同一新版提醒一次；24 小时 Release 缓存独立于聊天提醒。只读通知状态不可写时仍保留提醒信息；只有用户明确要求才安装。已安装承意 1.6.0 可正常使用 `update --apply`；旧品牌首次切换仍需运行新安装器。安装不会自动迁移真实知识库或扩大收录范围。
- 发布前最终全量 246 项通过，包含重复迁移目标回归；迁移专项 11 项通过，独立复审通过。GitHub CI 与公开安装包证据见正式 Release 的公开验证附录。实际 Codex CLI 主动读用并保存虚构资料通过；隔离安装保留既有文件、注册 7 个入口，安装布局下迁移与回滚通过。终版可见提醒、真实语音、抖音全量处理和真实知识库迁移未验证。

功能、升级条件和验证边界见[1.7.0 版本说明](docs/releases/v1.7.0.md)与[三方向候选验证记录](docs/verification/three-domains-candidate.md)。

- Extend the personal vault to life, work, and learning. All three participate by default when newly enabled; the starting choices are 1 Learning, 2 Work, and 3 Life. The choice sets the first interview focus, not an exclusive scope.
- Ask one useful interview question at a time and continue after basic profile fields are complete until the user pauses, stops, or changes topic. Handle explicit tasks first. Relevant everyday tasks can read and use existing context, then collect explicit new information and real outcomes within the enabled scope.
- Preserve existing collection scope and accept `creative` as a compatibility alias for `work`. Existing libraries require a complete mapping preview and one user confirmation before backup and reclassification. The preview rejects duplicate rule or navigation replacement targets, including Windows case-equivalent paths. Repair supported links, indexes, and runtime state; keep historical receipts unchanged and allow recovery. Do not bypass target-library rules or its current write entrypoint.
- Check for updates independently in participating chats and remind once per chat for the same release. The 24-hour Release cache is separate from chat-level reminders. Preserve notice information when the read-only notice store cannot be written; install only on explicit request. Installed CY-CharmYee 1.6.0 can use its normal `update --apply` path. Old-brand installations still need the new installer for their first migration. Installation does not migrate a real library or expand its collection scope.
- Final pre-release regression passed 246 tests, including duplicate migration targets; all 11 migration tests and independent re-review passed. Final CI and public-package evidence is recorded in the formal Release verification appendix. A real Codex CLI read/use/save trial with synthetic data passed; isolated installation preserved existing files and registered 7 entries, and installed-layout migration and rollback passed. Final user-visible reminders, live speech, full Douyin processing, and migration of a real library remain unverified.

See the [1.7.0 release notes](docs/releases/v1.7.0.md) and [three-domain candidate verification](docs/verification/three-domains-candidate.md) for upgrade guidance and evidence boundaries.

## 1.6.0 - 2026-11-13

- 品牌统一为「承意 CY-CharmYee」，口号「承你所想，会你所意」。主 Skill ID 为 `cy-charmyee`，子入口统一为 `cy-*`；展示名称使用 `CY-*`。
- 安装、更新、打包、配置窗口和中英文文档同步改名；旧 `dyb-*` / `douyin-brain` 入口可迁移为兼容入口，保留工作区、凭据、任务和个人知识库启用状态。
- Rebranded as CY-CharmYee, with canonical `cy-*` entrypoints, reversible legacy aliases and preserved workspace registrations. The first cross-brand migration uses the new installer; old published assets remain unchanged.
- 新增 cy-vault：可选个人知识库、可续接对话建档、创作与学习模块、明确作用范围与主动积累。
- 本地写入带不可变快照、冲突检查、索引读回与失败续办；已有库沿用现行入口和权威档案。
- Added optional personal-vault setup, resumable profiles, creative/learning modules, scoped collection and verified recovery. Existing library rules and canonical profiles are preserved.
- 可跳过建档问题、暂停积累或将本次任务设为不保存；开启知识库不自动收录历史文件，也不启用定时任务或外部发布。
- 修正 Windows 文件名大小写等价检查，阻止用规则或索引的大小写变体作为普通材料写入目标。
- 用户再次明确恢复先前的个人资料答案时，纠正仍会生效并保留原始回答；紧邻的相同回答重试继续复用已有记录。
- 旧入口备份和恢复使用整目录改名，避免 Windows 遇到占用文件时逐文件移动造成部分文件留在备份、部分留在原位。
- 知识积累跳过过期分析；档案来源链接适配自定义位置；重复保存先确认当前索引可检索，缺失时进入修复或目标库写入续办。
- Allow skipped profile questions, paused collection, and unsaved tasks. Enabling a vault does not import historical files, start schedules, or publish externally.
- Protect library rules and indexes from ordinary material writes through case-equivalent Windows paths.
- Apply explicit profile corrections even when they return to an earlier answer, preserving original answers while reusing immediate identical retries.
- Rename legacy directories as a unit during backup and rollback, avoiding partial recursive moves when Windows encounters a locked file.
- Skip stale analyses during collection, resolve provenance from custom profile locations, and verify current index coverage before reusing saved material; missing links enter local or target-writer recovery.

首次跨品牌迁移由 Agent 运行承意 1.6.0 新安装器，旧版 `update --apply` 不支持跨产品标识直接升级。验证范围与迁移步骤见 [1.6.0 版本说明](docs/releases/v1.6.0.md)和[验收记录](docs/verification/v1.6.0.md)。

The first cross-brand migration runs the CY-CharmYee 1.6.0 installer; the legacy `update --apply` cannot cross product identities directly. See the [release notes](docs/releases/v1.6.0.md) and [verification record](docs/verification/v1.6.0.md) for migration steps and evidence boundaries.

## 1.5.0 - 2026-11-12

- 增加只读恢复入口，按来源和目标查找旧任务、显示有效成果与下一步；恢复沿用保存范围，普通任务可使用 `run --saved-scope`。
- 文稿支持逐条登记，保存独立版本快照并识别工作稿编辑、缺失和下游依据过期。
- 普通和博主任务支持独立离线换角度分析，复用经过校验的材料及历史核对依据；本地补查不自动扩展为获取或付费识别。
- Read-only recovery finds tasks by source and goal and reports valid results and next actions; `run --saved-scope` preserves ordinary task scope.
- Item-level text registration preserves immutable revisions and detects edits, missing files, and stale dependencies.
- Separate offline reanalysis tasks reuse verified material and historical review provenance without new acquisition or paid speech.

本地验证通过 177 项行为测试、独立 Agent 纯文稿跨进程试用和 12 个旧任务只读兼容检查。版本与升级说明见 [1.5.0](docs/releases/v1.5.0.md)。

Local validation passed 177 behavioral tests, an independent text-only cross-process Agent trial, and read-only recovery checks for 12 existing tasks. See [1.5.0](docs/releases/v1.5.0.md) for scope and upgrade details.

## 1.4.0 - 2026-11-07

- 总入口与转写、分析、下载、改写、知识归档五个子 Skill 统一安装和更新，共用运行时、配置与任务数据；明确需求直接路由，组合需求通过共享工作记录衔接。
- 首次使用介绍全部功能与配置需求，结果先在聊天展示；语音和知识库按需配置，已有设置继续复用。
- 新增博主主页逐页发现、按时间分析和独立批量下载，分别报告可访问范围、素材状态与实际分析覆盖；新增付费识别先展示批次用量并取得授权。
- 后台获取采用有限并发、成功缓存和按需抽帧；修复重复链接争用、持久浏览器目录冲突、限量续跑、丢失失败作品和识别前失败占住用量的问题。
- 安装整套校验与失败回滚；下载完成状态核对实际文件与哈希，缺失或变化如实报告并保留用户修改。
- 从公开版 1.2.0 或本地 1.3.x 候选升级时保留原配置与任务。功能合并版本通过 159 项 Windows 测试、全新安装、文本交付和安装包校验；本版说明见 [1.4.0](docs/releases/v1.4.0.md)。

- Install and update one coordinator plus five specialized Skills together, sharing runtime, settings, and task data. Clear requests route directly; combined work links through shared records.
- Explain all capabilities and setup requirements at first use and deliver readable results in chat. Configure speech and knowledge storage only when needed, reusing existing settings.
- Add durable creator-profile discovery, chronological analysis, and independent video download. Report accessible scope, media readiness, and actual analysis coverage separately; preview and authorize new paid speech batches.
- Use bounded background acquisition, successful caches, and targeted frames. Fix duplicate-link and persistent-profile contention, bounded resumption, lost failed identities, and reservations left by pre-submission failures.
- Verify and roll back the suite as a unit. Validate downloaded deliverables against their hashes; report missing or changed files and preserve user edits.
- Preserve configuration and tasks when upgrading from public 1.2.0 or local 1.3.x candidates. The merged feature version passed 159 Windows tests, fresh installation, text delivery, and package verification. See the [1.4.0 release notes](docs/releases/v1.4.0.md).

## 1.3.1 - 2026-11-06

本条记录为本地候选，3 条真实语音和 Agent 校对任务已交付，最终本地全套回归通过 97 项；条件与结果见[本地验收记录](docs/verification/v1.3.1.md)。尚未推送、运行本次 GitHub CI 或发布。

- 批量链接中，已准备并验证音轨的素材可进入父进程串行识别，其余素材继续获取；重复素材去重，最终结果保持输入顺序及失败位置。
- 区间帧图提取按需定位并在输出所需帧后停止；重叠区间可按源文件哈希与原始帧序号复用已校验图片，沿用既有 JPEG 质量设置。

This entry describes a local candidate; 3 live speech and Agent review tasks have been delivered and the final full local regression passed 97 tests. See the [local verification record](docs/verification/v1.3.1.md) for conditions and results. It has not been pushed, run through this candidate's GitHub CI, or published.

- In link batches, audio that is ready and verified can enter serial recognition in the parent process while other acquisition continues. Duplicate media is deduplicated, and final results retain input order and failure positions.
- Seek to the required frames and stop after the selected frames are output. Overlapping ranges can reuse verified pictures by source hash and original frame index, using the existing JPEG quality setting.

## 1.3.0 - 2026-11-06

本条记录为本地候选，尚未推送、运行本次 GitHub CI 或发布。验收范围和未验证项见[本地验收记录](docs/verification/v1.3.0.md)。

- 批量素材逐条隔离失败并保留原序号；续跑先检查可用成功缓存，再为剩余素材联网。
- 优化匿名后台获取及阻挡提示判断；每条链接的获取阶段限时 90 秒，最多两个获取工作进程，豆包识别独立于获取超时。
- `run` 增加 `--anonymous-only`；`inspect-source` 增加 `--download-audio`，默认仅查元数据且不调用语音识别。
- 校对先通读并聚焦疑点，按实际看图／听音能力准备材料；按来源和参数复用，`--cached-only` 可限制为已有材料。
- 安装时可发现单套旧 `douyin-brain` 设置并保留数据与旧名入口；多个不同工作目录须由用户选择，不自动合并。

This entry describes a local candidate; it has not been pushed, run through this candidate's GitHub CI, or published. See the [local verification record](docs/verification/v1.3.0.md) for scope and remaining gaps.

- Isolate batch failures, retain original numbers, and check successful caches before network acquisition on resume.
- Improve anonymous background acquisition and blocking detection; limit acquisition to 90 seconds per link and two workers, separately from Doubao recognition.
- Add `run --anonymous-only` and `inspect-source --download-audio`; inspection checks metadata only by default and never calls speech recognition.
- Read the full transcript before focusing review on uncertainties. Prepare evidence using available image and audio capabilities, reuse matching material, or restrict preparation to existing material with `--cached-only`.
- Discover a single legacy `douyin-brain` setup while preserving data and the old-name entry; ask the user to choose when multiple workspaces differ, without merging them.

## 1.2.0 - 2026-11-05

- 单条公开视频优先尝试 HTTP 分享页和全新无登录态的无头浏览器，必要时使用已有专用浏览器状态，并保留 yt-dlp 单视频回退；常规获取在后台进行，失败按实际原因报告。
- 新增不调用语音识别的 `inspect-source` 和 `prepare-review`；后者按当前 Agent 实际的看图／听音能力准备材料，抽样或逐帧准备不等于完成校对。
- 优化安装和登录说明：抖音登录不是安装前置；只有用户明确要求登录、验证或界面排障时才打开可见专用浏览器。
- Acquire individual public videos through an HTTP share page and a fresh headless anonymous browser first, with existing dedicated browser state when needed and the existing yt-dlp fallback. Routine acquisition runs in the background and reports the actual cause of failure.
- Add `inspect-source` and `prepare-review` without invoking speech recognition. Review preparation follows the current Agent's actual image and audio capabilities and does not itself complete a review.
- Clarify that Douyin login is not an installation prerequisite and a visible dedicated browser opens only for explicitly requested login, verification, or interface troubleshooting.

## 1.1.1 - 2026-11-05

- 修复部分 Windows 环境因 GitHub 证书链校验失败而无法检查或下载更新的问题；符合条件时使用 certifi 的 Mozilla 信任根重试，仍校验证书和域名。
- Fix update checks and downloads affected by GitHub certificate-chain failures on some Windows systems, with a certifi Mozilla trust-root retry that retains certificate and hostname verification.

## 1.1.0 - 2026-11-05

- 增加新版检查和用户明确要求时的更新能力；补充版本发布、公开安装包校验与已有用户升级说明。
- Added update checks and user-requested upgrades, with documented release preparation, public package verification, and upgrade guidance.

## 1.0.1 - 2026-11-05

- GitHub 账号由 `LYJT270` 更名为 `ScarfaceAI`，更新当前仓库链接与署名；保留 1.0.0 标签和发布历史，功能与安装行为不变。
- Updated repository links and attribution after the GitHub account rename from `LYJT270` to `ScarfaceAI`; the 1.0.0 tag and release history remain, with no change to functionality or installation behavior.

## 1.0.0 - 2026-11-05

- 整理公开版抖音脑 Douyin-brain，提供 Windows 自动安装与多 Agent 安装适配。
- 保留转写、校对、分析、口播改稿、批量 TXT 和按需知识归档流程。
- 提供独立编写的抖音素材获取实现，并记录第三方运行依赖与许可。
- 补充中英文安装、配置、数据与限制说明。
