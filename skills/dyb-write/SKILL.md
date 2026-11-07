---
name: dyb-write
description: Rewrite or shorten Douyin or audio/video-derived transcripts as spoken scripts while preserving requested facts and source text. Explicit invocation also supports existing text.
license: MIT
---

# 抖音脑 · 口播改写

根据用户要求改写、润色或压缩抖音及音视频相关文稿；显式调用本 Skill 时，也可处理用户提供的现有文字。原稿与改稿分别保存，不虚构经历、数据或权益。

先运行 `& '<当前子 Skill>/scripts/invoke.ps1' guide`。成功时从 JSON 的 `references.suite` 读取共用规则，并读 `references.content` 的文稿协作与交付说明；需要先转写媒体时再读 `references.runtime`。后续命令可经本子 Skill 的 `scripts/invoke.ps1` 透传。`guide` 返回错误或非零退出时，报告实际问题并停止，不能猜测共享目录或继续使用不一致的安装。

按已明确的目标、受众、风格和格式直接处理，未指定的细节结合原稿判断；用户要求试稿时先交试稿。压缩或明显删减时按文稿指南记录前后字数、估算时长与关键内容保留情况。已有文字不调用识别；聊天先交正文或标明节选，再附完整文件。
