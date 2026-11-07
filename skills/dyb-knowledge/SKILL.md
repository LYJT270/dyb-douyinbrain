---
name: dyb-knowledge
description: Archive Douyin or audio/video-derived source and reviewed transcripts, and compile requested knowledge-base topics. Explicit invocation also supports existing text.
license: MIT
---

# 抖音脑 · 知识归档

按用户明确要求，将抖音或音视频相关材料归档到目标知识库，或进一步编译主题页；显式调用本 Skill 时，也可处理现有文字。归档与编译分别以用户指令为准。

先运行 `& '<当前子 Skill>/scripts/invoke.ps1' guide`。成功时从 JSON 的 `references.suite` 读取共用规则，并读 `references.knowledge`；需要先获取或校对媒体时再读 `references.runtime` 和 `references.content`。后续命令可经本子 Skill 的 `scripts/invoke.ps1` 透传。`guide` 返回错误或非零退出时，报告实际问题并停止，不能猜测共享目录或继续使用不一致的安装。

先读目标库现行规则，保留来源并按其入口成组保存原文和校对稿；改写稿只有用户点名时才收录。编译要实际完成带来源的主题页，写入后按目标入口读回核对。区分待入库文件、实际发布回执与已完成编译；不得互换普通任务和博主任务 ID，也不得伪造发布。
