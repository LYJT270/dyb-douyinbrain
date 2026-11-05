# 更新记录

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
