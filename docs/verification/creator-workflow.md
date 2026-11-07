# 博主工作流本机验证（进行中） / Creator workflow local verification

本记录只保留本轮匿名汇总，不列账号、作品 ID、原始链接、个人路径或凭据。本地候选尚未公开发布；单次运行、自动化测试和准备材料都不等于整号验收或用户验收。

## 中文

### 主页发现与素材获取

- 用户提供的主页短链已成功解析。一次后台发现使用本机已有的专用浏览器状态，在 **9.625 秒**内收到分页末尾，得到 **69 条**本次会话可见作品：**66 条视频、3 条图文**。这是单次结果，只证明当时该会话的可见范围，不代表其他账号、其他时间或其他运行都能达到相同覆盖与速度。
- 匿名路径首次未收到作品列表，第二轮也未完成。两次情况不能据此认定需要登录，也不能用上述已有浏览器状态的结果替代匿名成功。
- 已有少量真实媒体免费获取成功；这不代表主页所有视频和图文已获取或逐条分析。

### 已授权的语音与视觉试验

- 用户授权了一批约 **65 秒**的两条视频；本轮 **2 次豆包请求均成功**，回执中的音频总时长为 **64.97225 秒**。该批一次 `run` 阶段约 **6.5 秒**，包含提取音轨并复用已有素材；不包含整号素材获取或视觉分析，不能当作平均速度或全流程耗时。
- 两位视觉核对者实际并行处理该两条视频，分别约 **2 分 40 秒**、**2 分 23 秒**，实际查看 **12 张**、**14 张**图片（含定点补帧）；两条结果均已成功登记。两人均未听音，看图不能证明实际说话内容。
- 另有一条图文样本实际查看 **1 张图**，未调用 ASR；调整图文来源标识后再次登记成功。目前已分析 **3／69 条**，并已登记并输出明确标注为两条视频样本的报告。以上结果不能写成整号视觉分析、完整口播校对或账号总评已通过。

### 独立下载与增量复用

- 独立下载对两条视频进行了非缓存真实获取，分辨率均为 **1440 × 2560**，文件约 **3.51 MB** 和 **3.26 MB**；一次 `run` 阶段约 **1.25 秒**。两条均通过整段 FFmpeg 解码，配套 TXT 与原发布文案一致，下载未发起 ASR。该耗时是本次样本，不代表平均速度。
- 再次刷新主页后，对两条视频运行增量任务：`run` 复用已完成分析，没有重新下载或调用 ASR；`prepare` 复用两条分析且未产生新核对包。两条原语音请求回执仍为 `succeeded`，请求 ID 前后未变；结果只说明此样本的复用行为。
- 交付检查中，作品明细 CSV、原始作品 JSONL 和分析与核对 JSONL 各有 **69 行作品记录**，其中 **3 条有实际分析结果**；作品按发布时间排列，3 个校对正文链接存在。报告说明样本覆盖范围，整体 `complete=false`。

### 本地测试与待验证

- 本轮最终全套测试 **127 项通过**，耗时 **57.289 秒**；专项运行中 **27 项 creator 测试、13 项浏览器测试通过**。离线测试不能代替真实主页或完整交付验收。
- 失效地址刷新、断点续传和封面获取仍需结合真实运行及测试证据判断；整号分析、其他账户、跨 Agent 及完整端到端结果尚待验证。真实语音服务已按上述两条范围验证，不代表其余作品均已识别。
- 本候选尚无本轮 GitHub CI 或公开发布证据。各本机安装状态以安装器回执为准，本记录不代表其他用户的安装验收；用户验收与样本结果分别判断。

## English

### Profile discovery and acquisition

- A user-provided profile short link resolved successfully. One background scan used an existing dedicated browser state, reached the pagination end in **9.625 seconds**, and returned **69 posts** visible in that session: **66 videos and 3 image posts**. This is one observation, limited to that session; it does not establish coverage or speed for other accounts, times, or runs.
- The first anonymous attempt received no post list and the second did not finish. Neither establishes that login was required, and the scan using existing browser state does not prove anonymous acquisition succeeded.
- A small number of real media files were acquired without paid speech recognition. This does not establish that every profile item has been acquired or analyzed.

### Authorized speech and visual trial

- The user authorized two videos totaling approximately **65 seconds**. Both Doubao requests succeeded, with **64.97225 seconds** of audio in their receipts. One `run` stage took approximately **6.5 seconds**, including audio extraction and reuse of existing media; it excludes full-profile acquisition and visual analysis and is not an average or end-to-end duration.
- Two reviewers actually worked in parallel on those videos, taking approximately **2 minutes 40 seconds** and **2 minutes 23 seconds** and inspecting **12** and **14** images respectively, including targeted supplemental frames; both results were registered successfully. Neither listened to the audio, so images cannot establish what was spoken.
- A separate image-post trial involved actually viewing **one image**, no speech API call, and successful registration again after the image-source identity change. **Three of 69 posts** have been analyzed, and a report explicitly scoped to the two video samples was registered and exported. These samples do not establish completed whole-profile visual analysis, transcript review, or account assessment.

### Independent download and incremental reuse

- Two videos were acquired through real, fresh independent downloads, both at **1440 × 2560** and approximately **3.51 MB** and **3.26 MB**. One `run` stage took approximately **1.25 seconds**. Both passed full-length FFmpeg decoding; the companion TXT files matched their published captions, and download made no speech calls. The timing is a sample, not an average.
- After refreshing the profile, an incremental `run` reused the completed analyses for those two videos without another download or speech call; `prepare` reused both analyses and produced no new review packet. Both original speech receipts remained `succeeded`, with unchanged request IDs. This establishes reuse for these samples only.
- Delivery checks found **69 post records** each in the post-details CSV, raw-post JSONL, and analysis-and-review JSONL, with **3 actual analysis results**. Posts were ordered by publication time and all three reviewed-text links existed. The report states its sample coverage, and overall `complete=false`.

### Local tests and remaining verification

- The final full suite passed **127 tests** in **57.289 seconds**. Targeted runs passed **27 creator tests and 13 browser tests**. Offline tests do not replace live-profile or complete-delivery verification.
- Expired-address refresh, resumed downloads, and cover acquisition still need to be assessed with live-run and test evidence. Whole-profile analysis, other accounts, cross-Agent sessions, and the complete end-to-end outcome remain unverified. Live speech was verified only for the two items above.
- This candidate has no evidence of a GitHub CI run or public release for this round. Each machine's installation status is determined by its installer receipt; this record does not establish installation acceptance for other users. User acceptance is distinct from these sample results.
