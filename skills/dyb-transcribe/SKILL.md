---
name: dyb-transcribe
description: Transcribe and proofread Douyin videos or local audio/video, handle related subtitles, and export transcripts. Explicit invocation also supports existing text and subtitles.
license: MIT
---

# 抖音脑 · 转写与校对

按用户要求提取、校对和整理抖音或本地音视频文字，或处理相关字幕与导出。显式调用本 Skill 时也可处理已有文稿和字幕。

先运行 `& '<当前子 Skill>/scripts/invoke.ps1' guide`。成功时从 JSON 的 `references.suite` 读取共用规则，从 `references.runtime` 或 `references.content` 按需读取命令与交付细节；后续命令仍可经本子 Skill 的 `scripts/invoke.ps1` 透传。`guide` 返回错误或非零退出时，报告实际问题并停止，不能猜测共享目录或继续使用不一致的安装。

- 音视频按运行指南获取音轨、使用豆包识别，由当前 Agent 通读并根据实际看图／听音能力校对。保留机器原文，检查依据与未解疑点按文稿指南记录。
- 已有文字直接处理，不调用识别；已有 SRT 直接处理并另存，保留时间码等未要求修改的结构。识别结果有分句时间时才能导出 SRT。
- 按要求给出正文和文件；不因转写自动分析、改写或入库。其他目标明确同时提出时，按共用路由组合处理。
