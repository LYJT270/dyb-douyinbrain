---
name: cy-knowledge
description: Archive source materials and reviewed transcripts, and synthesize knowledge topics under explicit requests or an enabled cy-vault collection scope. Personal knowledge setup and profile interviews use cy-vault.
license: MIT
---

# CY-knowledge · 知识归档

按明确要求或已通过 cy-vault 开启的模块与范围，将材料归档到目标知识库并整理相关主题。先 kb context 核对范围；个人建档和知识库配置交给 cy-vault。

先运行 `& '<当前子 Skill>/scripts/invoke.ps1' guide`。成功时从 JSON 的 `references.suite` 读取共用规则，并读 `references.knowledge`；需要先获取或校对媒体时再读 `references.runtime` 和 `references.content`。后续命令可经本子 Skill 的 `scripts/invoke.ps1` 透传。`guide` 返回错误或非零退出时，报告实际问题并停止，不能猜测共享目录或继续使用不一致的安装。

先读目标库现行规则，保留来源并按其入口成组保存原文和校对稿；改写稿按用户点名或已开启范围内的实际交付记录收录；后者读 references.personal-vault 并使用 kb collect / kb stage，不把旧任务用途改成入库。编译要实际完成带来源的主题页，写入后按目标入口读回核对。区分待入库文件、实际发布回执与已完成编译；不得互换普通任务和博主任务 ID，也不得伪造发布。
