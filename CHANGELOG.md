# 更新记录

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
