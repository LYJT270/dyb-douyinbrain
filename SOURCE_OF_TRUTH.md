# 项目事实来源

- 产品能力和实际行为以本仓库 `scripts/` 的实现、运行结果及相关测试为准；`SKILL.md` 是 Agent 使用入口，`references/` 存放按需操作细节。
- 安装参数以 `scripts/install.ps1` 为准，安装及用户使用说明为 `INSTALL.md`、`README.md`、`README.en.md` 与 `docs/`。涉及行为变更时同步相应文档。
- 当前本机 workspace 和知识库以用户设置和工作目录中的配置为准；安装状态以本机实际的 `install-result.json`、`settings.json` 和运行结果为准。公开源码不包含用户工作数据和密钥。
- 豆包服务的接口、控制台和计费以服务提供方当前官方资料和用户账户页面为准；`references/doubao-setup.md` 是指导使用的本地快照。
- 自有代码许可看 `LICENSE`，第三方组件、来源与许可看 `THIRD_PARTY_NOTICES.md` 和 `references/sources.md`。旧版历史只能说明来源，不能代替对公开版实际文件的检查。
- 测试、Release 构建和真实运行分别报告实际证据；本地安装或 `doctor` 成功不代表云端语音、抖音登录或所有 Agent 会话验收通过。
