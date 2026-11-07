# 更新记录

## 未发布／Unreleased — 博主工作流与 Skill 套件

本轮在源码中加入可访问主页的全量分析与独立视频批量下载入口；真实账号、视觉核对和付费语音的本轮验收状态以实际记录为准，尚未公开发布。

- 首次使用先介绍功能、示例、产出与语音配置需求；新增中英文自然语言路由和聊天先交结果说明。`welcome` 只读展示功能与本机状态，Agent 在聊天介绍后可登记本版已展示，不代表用户理解或云端验收。
- 安装默认不弹语音 Key 窗口，也不默认建立知识库；已有配置继续复用，仅按用户需求配置。主页标题／发布文案分析可停在元数据阶段；已有 SRT 由 Agent 直接处理并保留时码。
- 主页逐页落盘、按作品去重与续跑；视频和图文可进入分析，独立下载仅处理视频及发布文案，不调用语音识别。
- 付费识别按批次预览和授权；核对包由宿主 Agent 实际读取全文与画面，逐条留底后按时间形成报告。
- 本地候选拆分总入口和五个按单项需求路由的子 Skill，共用安装、配置、首次介绍和更新；安装时避免递归发现重复入口。组合任务使用 `work` 关联原生任务与实际产物。真实宿主发现及发布状态以实际验证为准。
- 套件本地回归通过 147 项；本机 Codex 原生发现恰好 6 个启用入口，五个子入口可共用运行时，既有配置和任务保持不变。范围与限制见[套件验收记录](docs/verification/skill-suite.md)。
- 上传准备阶段补齐 CI 依赖，修复文件占用时的整套回滚、限量分析续跑、同一作品不同链接的并发冲突、未提交识别的用量释放，以及交付视频缺失或变化后的完成状态；新增回归场景后，本地 155 项测试通过。

The source candidate adds creator-profile analysis and independent video batch download. Verification of the current round's real account, visual review, and paid speech is reported from actual evidence; this feature has not been publicly released.

- Introduce capabilities, examples, outputs, and speech-setup needs at first use; add bilingual natural-language routing and result-first chat delivery. Read-only `welcome` reports capabilities and local readiness; an Agent can record presentation only after showing it in chat. That record is not user comprehension or cloud verification.
- Installation no longer opens the speech-key window or creates a knowledge base by default; reuse existing settings and configure only for the requested task. Analyze profile titles/captions from metadata alone; the Agent handles existing SRT directly while preserving timecodes.
- Save profile pages as they are discovered, deduplicate posts, and resume. Analyze video and image posts; independent download handles videos and captions without speech recognition.
- Preview and authorize paid recognition in batches. The host Agent reads transcripts and images in review packets before recording per-item results and a chronological report.
- The local candidate separates the main entry and five specialized child Skills while sharing installation, configuration, introduction, and updates; the installed layout avoids duplicate recursive discovery. Combined work can link native tasks and actual artifacts with `work`. Real host discovery and release status depend on verification.
- The suite passed 147 local regression tests. Native discovery on the local Codex installation found exactly 6 enabled entries, the five child entrypoints shared the runtime, and existing configuration and tasks were unchanged. See the [suite verification record](docs/verification/skill-suite.md) for scope and limitations.
- Upload preparation adds pinned CI dependencies and fixes whole-suite rollback with locked files, bounded analysis resumption, contention between URLs for the same post, reservations for unsubmitted speech, and completion reporting for missing or changed delivered videos. With the added regression cases, 155 local tests passed.

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
