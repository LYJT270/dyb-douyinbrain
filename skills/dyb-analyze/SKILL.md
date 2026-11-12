---
name: dyb-analyze
description: Analyze a Douyin post, creator profile, or local audio/video using available transcripts and actually inspected images. Explicit invocation also supports existing text.
license: MIT
---

# 抖音脑 · 内容与博主分析

分析用户指定的抖音作品、主页或本地音视频；显式调用本 Skill 时，也可分析现有文稿。基于实际读到、看到或听到的材料给结论、具体例证与覆盖范围。

先运行 `& '<当前子 Skill>/scripts/invoke.ps1' guide`。成功时从 JSON 的 `references.suite` 读取共用规则；单条素材按需读 `references.runtime` 和 `references.content`，主页分析读 `references.creator`。后续命令可经本子 Skill 的 `scripts/invoke.ps1` 透传。`guide` 返回错误或非零退出时，报告实际问题并停止，不能猜测共享目录或继续使用不一致的安装。

- 单条作品可使用已有文字；需要时才先转写，并按当前 Agent 的实际能力核查画面或音频。未查看的内容和存疑之处如实标明。
- 只分析主页标题／发布文案时停在发现及元数据分析，不下载作品或调用语音识别；标题和文案不能代表完整作品。
- 分析主页作品时按博主指南逐条阅读与核对，再汇总。新增语音先展示本批用量并取得授权，已授权部分按原授权继续；发现或处理不完整时交付实际覆盖与缺口。
- 已有材料换角度时读 `references.continuation`，用 `reanalyze` 或 `creator reanalyze` 建立独立离线任务，复用有效核对依据；新问题生成新结论。用户要求更新当前主页才刷新，不能把历史核对说成本次重新看图。
