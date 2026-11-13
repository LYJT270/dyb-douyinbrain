# 首次配置与迁移

## 安装和位置

首次安装或配置前，先按[首次介绍](onboarding.md)在聊天中说明能力、例子、产出和语音配置需求；用户已有明确目标时介绍后继续该目标。安装器的终端介绍不是聊天展示，也不会自动登记已展示。安装完成后读取结果指向的 `skill_file`，用 `welcome` 核对本机状态；实际展示介绍后再 `welcome --acknowledge`。这只登记展示，不代表用户理解或已授权其他操作。

使用仓库源码根目录或 Release 安装 ZIP，按 [INSTALL.md](../INSTALL.md) 运行 `scripts/install.ps1`；手动安装可双击 `install.cmd`。默认 `-Agent auto` 使用共享 `.agents/skills`，检测到已有 Claude 配置时尝试桥接，保留同名独立安装；也可选择受支持的 Agent 或通过 `-SkillsRoot` 指定 Skill 父目录。所有入口使用相同核心引擎。自动发现取决于 Agent 的实际配置；当前对话可直接读取安装结果中的 `skill_file`。

本源码为一次安装的套件：源码和安装包中的子 Skill 位于 `skills/`，安装后与总入口各有同级目录；总入口不保留嵌套的子入口，以避免递归发现时重复显示，共用清单负责一致性校验。各入口共享配置、工作目录、介绍状态和更新。子入口先调用自身 `guide` 取得共享位置，不根据安装或源码目录猜路径。具体路由与失败处理见[套件规则](suite.md)，安装和真实宿主发现情况以实际结果为准。

自动安装默认准备完整 Python、虚拟环境、依赖、FFmpeg 和 Chromium，用户无需预先安装 Python。网络、WinGet、权限或依赖安装失败时检查实际错误；不将环境检查通过当作云端或登录可用。已有文稿无需语音 Key 和浏览器识别。

本机登记配置优先沿用。新电脑默认工作目录为 Windows「文档」下 `cy-charmyee`；默认不创建知识库，用户选择配置个人知识库或明确要求入库时，再接入已有库或创建新库。用户明确指定的工作目录或知识库优先。创建空库不授权收录历史任务；已有库按其现行规则和入口使用，不能覆盖已有内容。

新安装的非秘密位置设置在 `%LOCALAPPDATA%/cy-charmyee/settings.json`；已有旧品牌登记时可继续使用 `%LOCALAPPDATA%/dyb-douyinbrain`。实际状态目录由安装回执及 `CY_STATE_DIR`（兼容 `DYB_STATE_DIR`）确定，结果见同目录 `install-result.json`。程序与工作数据分开，换电脑时重新安装并配置，不沿用其他电脑的登录状态或凭据。

同一 Windows 用户从 `dyb-douyinbrain` / `douyin-brain` 迁移时，安装器发现单套旧设置后沿用原 workspace、加密 Key 和任务，备份原配置与旧 Skill，保留旧主入口和已确认归属的子入口。发现多个不同 workspace 时返回 `needs_workspace_choice` 与候选项：向用户展示并询问一次，再用所选 `-Workspace` 重跑；不要自动合并数据。首次迁移与命名对照见[品牌迁移](brand-migration.md)，操作见 [INSTALL.md](../INSTALL.md#从旧名称迁移)。

## 指定工作目录或知识库

安装器接受 `-Workspace` 和 `-Vault`；用户明确给出路径时使用实际路径。已有库不要通过创建新库参数覆盖，按目标库规则操作。需要独立的新库时可使用 `-CreateVault`：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\install.ps1' -Workspace 'D:\MyBrain' -Vault 'D:\MyKnowledge'
# 为明确指定的新目录创建空库：
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\scripts\install.ps1' -Workspace 'D:\MyBrain' -Vault 'D:\NewKnowledge' -CreateVault
```

如只调整现有 workspace 的知识库，先读取目标库现行规则，再使用安装后入口的 `init`。不要因缺少某个约定文件擅自改造既有库；新库与现有库分别按[知识库适配](knowledge.md)处理。

## 语音凭据和登录

豆包开通、获取语音 Key、保存和短录音测试见[豆包语音配置教程](doubao-setup.md)。语音服务开通与 Key 必须在同一项目；已有进度只补缺项。账号注册／登录、服务开通与计费确认由用户本人完成。

安装默认不弹出语音配置窗口。没有凭据时安装状态为 `awaiting_api`，这表示语音待配置，不代表本地安装全部失败；已有文稿和独立视频下载不需要语音 Key。用户要转写时，可双击 `配置豆包.cmd`，或由 Agent 运行：

```powershell
& '<已安装 Skill>\scripts\invoke.ps1' configure
# 旧式 APP ID + Access Token：
& '<已安装 Skill>\scripts\invoke.ps1' configure --legacy
```

窗口接受粘贴，凭据使用当前 Windows 用户的 DPAPI 加密保存在工作目录的 `.local/doubao.dpapi`。旧式凭据也可通过 `配置豆包旧版.cmd` 填写。火山方舟聊天 Key 属于其他服务；不要在聊天、日志、Skill、报告或安装包中收集或输出 Key、Cookie、验证码。

如用户已明确要求在安装时配置语音，可给安装器传 `-ConfigureSpeech`；已有凭据时复用，`-NoApiWindow` 同时出现时优先抑制窗口。`configure` 的终端提示不会自动替代聊天介绍或登记已展示。

可由用户在本机进程配置 `DOUBAO_ASR_API_KEY`，或 `DOUBAO_ASR_APP_ID` 和 `DOUBAO_ASR_ACCESS_KEY`；诊断只检查是否存在，不打印值。

抖音登录不是安装前置。常规获取在后台尝试公开素材并报告实际原因；普通登录按钮不能证明必须登录。只有用户明确要求登录、验证或界面排障时使用 `scripts/invoke.ps1 login`，由用户在可见的项目专用浏览器完成登录或验证码。`doctor` 只检查本地依赖与凭据是否存在，不登录、不校验云端权限、不发送识别请求。实际可用性以用户选择的任务结果为准。

## 个人知识库

可选的 cy-vault 提供对话建档、模块增配与正常任务中的主动积累，见[个人知识库指南](personal-vault.md)。安装本身不启用收录；开启时选定工作区或当前 Agent 范围，沿用已有权威档案，创建新的轻量库才使用模板。

## 知识库入口

已有受控发布入口时，只有 workspace 配置的 `assistant_root`、知识库路径与入口职责实际匹配才能使用 `publish`。其他电脑不要求安装个人助手；遵循目标库现有入口，新建轻量库按其规则写入并用 `record-publication` 读回核对。详情见 [knowledge.md](knowledge.md)。

## 迁移与隔离

安装包不包含工作数据、历史媒体、缓存、浏览器登录状态或凭据。换电脑后重新安装、重新配置语音凭据；抖音登录仅在用户明确要求时进行。`-StateDirectory` 供隔离测试使用，正常安装不需要；隔离结果不能证明真实用户目录已配置。

依赖来源与许可见 [sources.md](sources.md) 和项目的 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。
