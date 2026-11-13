# 三方向个人知识库候选验证（发布前快照）

## 中文

本记录冻结于 1.7.0 发布准备之前，记录当时工作分支中的源码候选，不代表后续发布或日常安装升级。当时未修改真实用户知识库、全局个人规则或生产任务，未推送、合并或发布；候选仍沿用 1.6.0 版本号。1.7.0 的最终 CI、标签、源码提交和公开包证据另记在正式 Release 的公开验证附录。

### 已实现

- 学习、工作、生活三种起步选择；知识内容顶层为生活、工作、学习。新启用默认参与三个方向，旧收录范围保留，显式授权后才扩展。
- 动态方向字段、话题和分支进度；固定字段齐全后仍可继续访谈；暂停、拒答、任务不保存和续接保持独立。
- 日常相关资料读取、明确新情况与成果积累；工作项目范围保留，学习进度依据实际反馈。
- 完整文件映射预览、本地授权库的备份与重分类、常见 Markdown/YAML sources/wikilink 路径更新、目录与运行入口同步、断点续办和冲突保护恢复。
- 独立路径及哈希投影保留历史回执；搬动后重复资料和回答仍复用原证据，其他工作区也可定位迁移后的档案。
- Release 元数据共享缓存与按会话提醒分开；同一会话不重复，其他会话独立提醒；支持真实宿主或显式会话 ID。没有会话 ID 时由 Agent 在当前对话去重。失去网络时可标明陈旧信息并使用此前确认的版本。

### 行为与审查证据

全套离线行为测试 244 项通过，耗时 185.368 秒。此后为提醒登记目录不可写的实际缺陷补充回归并通过更新提醒全部 24 项；最终日常入口文案调整后，个人知识库 33 项再次通过。三方向 10 项、迁移 10 项、历史与档案迁移集成 2 项、首次介绍 5 项均通过。没有把后续定点验证写成全套 245 项重跑。测试使用临时库、虚构人物和模拟 Release，不调用真实语音服务。

独立审查发现并修复旧基础字段、创作字段别名、既有页面更新、外部库历史回执以及迁移恢复相关问题。定点复审均通过，包含争锁不覆盖日志、完整备份不可变、多规则部分状态续办、marker 幂等和真实 Windows junction 拦截。

旧版与候选的同组运行时对比：旧版基础字段填齐后没有下一问，拒绝扩展生活字段；候选在全部固定字段齐全后仍返回持续访谈入口，扩展生活回答实际保存成功。

真实 Codex CLI 新会话中，用户未点名 Skill，Agent 主动执行上下文读取、使用虚构用户的零基础及周末两小时时间安排生成 Python 分类练习，并保存本轮原始要求和学习成果。读回文件哈希与保存回执一致；未把生成教程当成用户已掌握，进度仍为尚未开始。

最初的只读宿主尝试被执行策略拦截；另一轮未包含隔离库写入权限，只交付工作区成果并如实留待保存。这两轮均未计作完整保存成功。加入已授权隔离库范围后完成上述读、用、存验证。

更新提醒另以实际 CLI 和合成缓存验证：同一聊天连续调用的提醒结果为 true、false，另一个聊天为 true；无网络请求、无安装。实际 Agent 测试发现，提醒登记目录不可写会吞掉已确认的新版提示，已修复为保留版本信息并由当前对话去重，专项复审通过。

另一轮实际 Agent 能收到工具返回的更新提示，但用户可见回答遗漏提醒；随后在日常入口、子 Skill 和共享指南前置了明确可见提醒要求。最终新会话复验在读取指南时被宿主执行策略拦截，未计作可见提醒成功。因此程序去重、不可写回退和说明调整有证据，最终用户可见提醒仍待宿主验证，不能据工具输出声称已经完整验收。

### 分发与范围

隔离首次安装及已有文字校对交付通过，未配置语音凭据。隔离刷新安装保留 10 份配置、任务和成果文件，注册 7 个套件入口，首次介绍已为 revision 5。实际安装布局下，子 Skill 读取共享指南、三方向开启、回答保存、迁移、历史回执不变、回答复用和回滚均通过。

最终候选按项目分发检查、清单、安装布局和 ZIP 内容校验收尾；本地包沿用源码 1.6.0 文件名，仅为未发布候选，不是新的官方 Release。日常安装与工作区 exports 中的官方包保持原状。

项目的分发检查以 `scripts/check_release.py` 和安装包清单为准。通用单 Skill 校验器会把源码工作区名、既有中文显示名及未分发的历史缓存当成错误；没有为通过它而改名、清理历史或放宽项目检查。

目标库使用 target_rules 时，本地迁移返回需要目标入口适配的诊断；本候选没有绕过外部发布器。真实库迁移仍先交完整映射预览，由用户一次确认。Codex 桌面全局、Claude 和其他宿主的真实新会话未验证；静态入口配置不等于这些宿主已验收。

## English

This snapshot was frozen before 1.7.0 release preparation, while the unreleased source candidate still used the 1.6.0 version number. At that stage no production library, global personal entry, live speech request, push, merge or release was performed. Final 1.7.0 CI, tag, source commit and public-package evidence is maintained in the formal Release verification appendix. Existing collection scope remains intact until explicit expansion.

The full behavioral suite passed 244 tests in 185.368 seconds. A later read-only notice-store regression and fix passed all 24 update tests, and the final generated-entry wording passed all 33 personal-vault tests; this is not a claim that the full 245-test suite was rerun. Focused checks also cover ongoing domain interviews, legacy field and path compatibility, reclassification, recovery, contention, Windows junctions, immutable historical receipts, and introduction revision 5. Independent review findings were fixed and received passing focused re-reviews.

A real fresh Codex CLI workspace conversation, without naming the Skill, retrieved a synthetic profile, adapted a Python exercise to the user's stated background and available time, and saved the request and learning outcome. Stored files matched their receipts. Teaching output did not advance the user's actual learning progress. Earlier policy-blocked or insufficient-write-scope attempts were not counted as successful storage.

Actual CLI update checks with synthetic cached release data produced true/false within one chat and true in another. Release lookup caching and chat notice deduplication are independent. A real Agent exposed a read-only notice-store failure, now fixed with passing regression coverage. Another Agent omitted a returned notice from its visible answer, so explicit presentation instructions were moved into the daily entry, child Skill and shared guide. The final fresh-chat attempt was blocked by host policy before reading that guide, so final user-visible reminder behavior remains unverified; a returned notice alone is not proof of presentation.

An isolated installation and existing-text delivery passed. Refresh installation preserved ten fixture configuration/task/output files and registered seven suite entries with introduction revision 5. Installed-layout guide access, domain enablement, saving, migration, reuse, immutable receipts and rollback passed. Candidate manifest and ZIP verification are part of closeout; the 1.6.0 filename denotes an unreleased local candidate, not a new official Release. Daily installation and official export packages were not replaced. Global desktop Codex, Claude and other hosts remain unverified. Existing external writers must be adapted through their authorized entrypoints; real-library migration requires its concrete reviewed preview.
