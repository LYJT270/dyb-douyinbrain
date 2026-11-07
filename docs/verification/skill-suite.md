# Skill 套件本地验收 / Local Skill suite verification

2026-11-07。本记录对应统一入口、五个子 Skill、新手引导和组合任务的本地验证。GitHub 检查以对应提交的 Actions 为准；源码合并与正式 Release 分别记录。

## 中文

- 最终本地回归 **147 项通过**，耗时 **119.942 秒**。新增测试覆盖组合任务的依赖、部分覆盖、上游产物变化、原生任务复用，以及整套安装、失败回滚、同名目录保护和成员版本不一致。
- 使用本机 Codex 的原生 `app-server skills/list` 强制刷新发现结果：总入口和五个子 Skill 共 **6 个启用入口**，无重复、无发现错误。最初发现的嵌套子 Skill 重复问题已修复：安装后的六个目录互为同级，主目录不再保留包内的嵌套子 Skill 副本。此次检查未启动模型会话，不能证明每种表达都能正确路由。
- 实际完成三个已有文本案例：校对后保存进度并续写、保留时间码的 SRT 错字修正、两条标题的有限范围分析。无关邮件、主页下载加分析、分析报告入库三个案例仅验证路由选择，未执行外部获取或入库。
- 本机整套安装成功，五个子入口均解析到同一主运行时。业务配置与 **11 个原生任务文件**的哈希保持不变，既有博主任务可读取；首次功能介绍状态由各入口共用。
- 本轮新增语音请求 **0 次**，知识库写入 **0 次**。没有重复执行此前的真实素材识别；博主样本的范围另见[博主工作流验证](creator-workflow.md)。
- 已验证本机 Codex 发现、子入口调用和隔离安装行为。其他 Agent 应用的真实发现与会话、其他机器以及整号端到端结果未验证。产物哈希与登记状态不替代内容审核、知识库实际发布或用户验收。

## English

- The final local regression passed **147 tests** in **119.942 seconds**. Added coverage exercises combined-work dependencies, partial coverage, changed upstream artifacts, native task reuse, whole-suite installation and rollback, conflicting directory protection, and inconsistent member versions.
- A forced native Codex `app-server skills/list` refresh discovered exactly **6 enabled entries**: the coordinator and five specialized Skills, without duplicates or discovery errors. An initial duplicate-discovery issue was corrected by installing six sibling directories without retaining nested child payloads under the main directory. No model turn was started by this inventory check; it does not establish correct routing for every request.
- Three existing-text cases produced actual artifacts: proofreading followed by saved progress and resumed rewriting, an SRT typo correction preserving timestamps, and analysis limited to two supplied titles. Unrelated email, profile download plus analysis, and report archiving were routing simulations only, without external acquisition or knowledge publication.
- The local suite installation succeeded and all five child entrypoints resolved to the shared runtime. Hashes of the business configuration and **11 native task files** were unchanged, an existing creator task remained readable, and first-use presentation state was shared across entrypoints.
- This round made **0 new speech requests** and **0 knowledge writes**. Earlier live recognition was not repeated; the creator samples have their own [verification scope](creator-workflow.md).
- Native discovery on this Codex installation, direct child entrypoints, and isolated installation behavior were verified. Real discovery and conversations in other Agent applications, other machines, and whole-profile end-to-end results remain unverified. Artifact hashes and recorded status do not replace semantic review, actual knowledge publication, or user acceptance.
