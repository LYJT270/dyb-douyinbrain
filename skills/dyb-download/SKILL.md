---
name: dyb-download
description: Batch-download accessible videos and captions from a Douyin creator profile, preserving reported quality and download status.
license: MIT
---

# 抖音脑 · 主页视频下载

按用户要求发现并下载抖音主页可访问的视频和发布文案，报告发现范围、成功／失败数量、实际画质和保存位置。

先运行 `& '<当前子 Skill>/scripts/invoke.ps1' guide`。成功时从 JSON 的 `references.suite` 读取共用规则，再读 `references.creator` 的独立下载流程；后续命令可经本子 Skill 的 `scripts/invoke.ps1` 透传。`guide` 返回错误或非零退出时，报告实际问题并停止，不能猜测共享目录或继续使用不一致的安装。

使用 `creator` 的 `download` 模式；默认选择平台返回的最高可用版本，实际画质以结果为准。此模式不调用语音识别，不自动处理图文、分析或入库。发现未到末页或个别视频失败时说明缺口；可复用通过校验的有效媒体。
