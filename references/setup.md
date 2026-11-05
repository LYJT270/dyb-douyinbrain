# 首次配置与迁移

## 安装和位置

使用仓库源码根目录或 Release 安装 ZIP，按 [INSTALL.md](../INSTALL.md) 运行 `scripts/install.ps1`；手动安装可双击 `install.cmd`。默认 `-Agent auto` 使用共享 `.agents/skills`，检测到已有 Claude 配置时尝试桥接，保留同名独立安装；也可选择受支持的 Agent 或通过 `-SkillsRoot` 指定 Skill 父目录。所有入口使用相同核心引擎。自动发现取决于 Agent 的实际配置；当前对话可直接读取安装结果中的 `skill_file`。

自动安装默认准备完整 Python、虚拟环境、依赖、FFmpeg 和 Chromium，用户无需预先安装 Python。网络、WinGet、权限或依赖安装失败时检查实际错误；不将环境检查通过当作云端或登录可用。已有文稿无需语音 Key 和浏览器识别。

本机登记配置优先沿用。新电脑默认工作目录为 Windows「文档」下 `dyb-douyinbrain`，默认轻量知识库为同目录的 `dyb-douyinbrain-知识库`；用户明确指定的现有工作目录或知识库优先。安装器建立空库不授权收录历史任务；已有库按其现行规则和入口使用，不能覆盖已有内容。

本机非秘密位置设置在 `%LOCALAPPDATA%/dyb-douyinbrain/settings.json`。实际安装结果见同目录 `install-result.json`。程序与工作数据分开，迁移时不沿用其他电脑的绝对路径、登录状态或凭据；重新安装并在新电脑配置。

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

安装时尚无语音凭据会显示 `awaiting_api`；可稍后双击 `配置豆包.cmd`，或由 Agent 运行：

```powershell
& '<已安装 Skill>\scripts\invoke.ps1' configure
# 旧式 APP ID + Access Token：
& '<已安装 Skill>\scripts\invoke.ps1' configure --legacy
```

窗口接受粘贴，凭据使用当前 Windows 用户的 DPAPI 加密保存在工作目录的 `.local/doubao.dpapi`。旧式凭据也可通过 `配置豆包旧版.cmd` 填写。火山方舟聊天 Key 属于其他服务；不要在聊天、日志、Skill、报告或安装包中收集或输出 Key、Cookie、验证码。

可由用户在本机进程配置 `DOUBAO_ASR_API_KEY`，或 `DOUBAO_ASR_APP_ID` 和 `DOUBAO_ASR_ACCESS_KEY`；诊断只检查是否存在，不打印值。

抖音登录不是安装前置。常规获取在后台尝试公开素材并报告实际原因；普通登录按钮不能证明必须登录。只有用户明确要求登录、验证或界面排障时使用 `scripts/invoke.ps1 login`，由用户在可见的项目专用浏览器完成登录或验证码。`doctor` 只检查本地依赖与凭据是否存在，不登录、不校验云端权限、不发送识别请求。实际可用性以用户选择的任务结果为准。

## 知识库入口

已有受控发布入口时，只有 workspace 配置的 `assistant_root`、知识库路径与入口职责实际匹配才能使用 `publish`。其他电脑不要求安装个人助手；遵循目标库现有入口，新建轻量库按其规则写入并用 `record-publication` 读回核对。详情见 [knowledge.md](knowledge.md)。

## 迁移与隔离

安装包不包含工作数据、历史媒体、缓存、浏览器登录状态或凭据。换电脑后重新安装、重新配置语音凭据；抖音登录仅在用户明确要求时进行。`-StateDirectory` 供隔离测试使用，正常安装不需要；隔离结果不能证明真实用户目录已配置。

依赖来源与许可见 [sources.md](sources.md) 和项目的 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。
