---
name: cy-vault
description: Set up or connect a personal knowledge base, learn about the user through a resumable conversation, enable creative or learning modules, and maintain opted-in knowledge during everyday tasks. Use for personal-vault setup, profile corrections, or continuing its maintenance.
license: MIT
---

# CY-vault · 个人知识库

通过简短对话了解用户，让资料在正常任务中逐渐积累。负责建库、接入、建档、模块增配、使用范围与续办；材料归档和主题整理可复用 cy-knowledge。共用套件配置和运行时，不创建额外 Agent。

先运行本子 Skill 的 `scripts/invoke.ps1 guide`，读取成功结果中的 `references.suite` 和 `references.personal-vault`；后续命令经同一入口透传。入口失败时报告真实问题，不猜共享目录。

- 首次主动介绍这项可选能力，不阻断转写等明确任务。用户选择后，使用已授权的范围连续完成配置；推荐在当前所选 Agent 的日常聊天使用，也可只在套件工作区使用。
- 先运行只读 `kb context`，复用明确已有资料与进度。建档一次问最有用的缺项，可跳过、暂停、续接；够用即展示简短资料卡并开始帮助，不要求先填完。
- 原始回答与个人事实可追溯；作者资料和 AI 推测不能写成用户事实。已有权威档案继续维护原位置，保留人工修改。
- 创作和学习模块按实际任务开启、按需补问。任务开始先查资料，可复用的成果主动保存并整理主题，交付时简短告知实际保存结果。开启范围后不逐次询问是否入库。
- 已有库先读取现行规则和索引，沿用既有入口；新库使用素材、知识库、个人/档案三层结构，目录按需生长。
- 尊重“本次不保存”和暂停。保存失败先交付已完成成果，留下真实待处理项，按文件现状补存。定时运行和外部发布不随建库自动开启。
