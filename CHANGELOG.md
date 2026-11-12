# 更新记录

## 1.5.0 - 2026-11-12

- 增加只读恢复入口，按来源和目标查找旧任务、显示有效成果与下一步；恢复沿用保存范围，普通任务可使用 `run --saved-scope`。
- 文稿支持逐条登记，保存独立版本快照并识别工作稿编辑、缺失和下游依据过期。
- 普通和博主任务支持独立离线换角度分析，复用经过校验的材料及历史核对依据；本地补查不自动扩展为获取或付费识别。
- Read-only recovery finds tasks by source and goal and reports valid results and next actions; `run --saved-scope` preserves ordinary task scope.
- Item-level text registration preserves immutable revisions and detects edits, missing files, and stale dependencies.
- Separate offline reanalysis tasks reuse verified material and historical review provenance without new acquisition or paid speech.

本地验证通过 173 项行为测试、独立 Agent 纯文稿跨进程试用和 12 个旧任务只读兼容检查。版本与升级说明见 [1.5.0](docs/releases/v1.5.0.md)。

Local validation passed 173 behavioral tests, an independent text-only cross-process Agent trial, and read-only recovery checks for 12 existing tasks. See [1.5.0](docs/releases/v1.5.0.md) for scope and upgrade details.

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
