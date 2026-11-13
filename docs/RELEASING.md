# 维护与发布

[English](releasing.en.md)

本指南面向维护承意的人，也包含[已有用户升级](#已有用户如何升级)的步骤。公开仓库是发布源码的真源；安装后的 Skill 副本用于运行。

## 先分清修改与发布

日常修复和功能改进可以只完成代码、文档与必要验证，不要求每次都升版本。用户说“修改功能”时，完成修改和验证；只有用户明确要求发布或更新到 GitHub，才执行推送、合并和发布。已有明确授权的发布任务按授权连续完成。

如果改动最初发生在旧版私用 Skill，先逐项比较，再把需要的程序和文档改动移植到公开源码，核对兼容性并测试。不要直接用本机已安装目录覆盖仓库，也不要复制凭据、浏览器状态、媒体、缓存或任务数据。

## 开分支并提交 PR

1. 从当前 `main` 建立 `codex/...`、`feat/...` 或 `fix/...` 分支，完成改动并补充受影响的文档。
2. 执行与改动相称的本地检查。安装包包含的源码或文档有变化时，即使暂不发布，也要运行 `python -B -X utf8 scripts/package.py --manifest-only` 更新 `bundle.json`；提交前确认清单包含预期文件且没有用户数据。
3. 按[贡献指南](../CONTRIBUTING.md)创建 PR，说明改了什么、实际验证了什么，以及安装、配置或数据是否需要迁移。
4. 等待 PR 的 `Windows / Python 3.12` 检查成功，保持分支相对 `main` 最新，处理所有待解决对话，再使用 squash 合并。

当前 `main` 规则要求通过 PR、指定 Windows 检查、分支最新和对话解决；个人维护者没有额外的强制审批人数。仓库实际规则变化时，以 GitHub 当前设置为准。

## 准备版本

需要发布时，在 PR 中一起更新：

- `VERSION`：按[语义化版本](https://semver.org/lang/zh-CN/)选择版本。兼容修复增加 PATCH，向后兼容的新增功能增加 MINOR，不兼容变更加 MAJOR。安装参数、数据格式和已承诺的能力契约也按兼容性判断。
- `CHANGELOG.md` 和 `docs/releases/vX.Y.Z.md`：说明改动、已有用户需要注意的内容、实际验证及未验证场景；Release 说明包含中英文。
- `bundle.json`：所有打包文件定稿后运行 `python -B -X utf8 scripts/package.py --manifest-only` 同步清单。

按改动运行适当测试，并确认发布说明中的验证结果有证据；未测试的真实语音请求、主页完整分页或 Agent 会话不要写成已通过。检查和清单更新完成后再走 PR，避免合并后才补发布必需文件。

## 合并后发布

发布需要 Git、Python 3.12 或更高版本、GitHub CLI（`gh`）和网络；`gh` 需登录有该仓库读取和推送标签权限的账号。可用 `gh auth status` 检查登录状态。

PR squash 合并后，先确认 `main` 当前提交包含这次要发布的改动，并等待该提交的 `check.yml` **push** 工作流成功。PR 检查通过并不能代替合并后提交的检查。

在本地仓库使用干净且与 `origin/main` 一致的 `main`，先预检：

```powershell
git fetch origin main --tags
git switch main
git pull --ff-only origin main
python -B -X utf8 scripts/release.py
```

默认只做预检，不创建发布标签。脚本检查工作树和分支、`VERSION`、更新记录、对应的中英文 Release 说明、安装包清单、远端当前 `main` 提交的 `check.yml` push CI，以及版本是否高于历史正式标签。预检失败先处理具体问题，不丢弃已有改动。

用户已明确要求发布时，运行：

```powershell
python -B -X utf8 scripts/release.py --publish
```

该命令通过预检后创建并推送对应的 `vX.Y.Z` 标签，触发 GitHub Actions 自动构建和发布。根据输出的 Actions 链接找到本次标签对应的运行记录，在页面等待，或用 `gh run watch <run-id>` 等待；确认工作流成功并出现对应 Release 后，校验公开下载：

```powershell
python -B -X utf8 scripts/verify_release.py --download
```

脚本将当前 `VERSION` 的公开 ZIP 和 SHA 下载到 `.scratch`，检查 SHA、ZIP CRC、完整文件集合及包内 `bundle.json` 与源码一致性。验证指定的本地安装包时，将同名 `.zip.sha256` 校验文件放在 ZIP 同一目录；本地包也须与当前源码版本和清单一致：

```powershell
python -B -X utf8 scripts/verify_release.py --archive '<本地 ZIP 路径>'
```

只有公开下载校验成功，才报告该版本的发布与包验证完成；分别说明自动化检查无法证明的真实语音服务、主页完整分页和各 Agent 会话。

发布后的证据应把标签、源码提交、CI 和安装包 SHA 记录到正式文档，不能只留在 `.scratch`；参见 [1.1.1 验收快照](verification/v1.1.1.md)。

如果 `main` 已含发布后的文档改动，复验旧版公开包时应在对应标签的独立 checkout 中运行验证：`verify_release.py` 会严格比较当前源码清单，不要为了匹配清单覆盖旧 Release。独立构建的 ZIP 可能因时间戳不同而有不同整包 SHA；每份 ZIP 分别核验自己的 `.zip.sha256` 校验文件和对应标签的源码清单即可。

## 已有用户如何升级

### 旧品牌版本首次迁移到承意 1.6.0

旧品牌 `dyb-douyinbrain` 或 `douyin-brain` 首次切换到承意，都需要运行一次新安装器。1.0.0／1.0.1 没有自动更新入口；虽然 1.1.0–1.5.0 已提供更新功能，但其更新器固定校验旧产品 ID、包名和包内根目录，不能直接 `update --apply` 安装 1.6.0 新品牌包。

1. 从[官方 Release](https://github.com/ScarfaceAI/CY-CharmYee/releases/latest)下载承意安装 ZIP 和 `.zip.sha256`，核验后解压。1.6.0 的文件名为 `cy-charmyee-windows-v1.6.0.zip`，`bundle.json` 的产品 ID 为 `cy-charmyee`。
2. 用同一 Windows 用户运行新包中的安装器。默认安装可双击 `install.cmd`；此前指定过 Agent、SkillsRoot 或自定义 StateDirectory 的，沿用原参数，或让 Agent 按原参数运行。单套登记会自动沿用已有工作目录，多个工作目录由用户选择一次。不要先删除旧程序、配置或任务。
3. 根据安装结果中的 `entrypoint` 运行 `doctor`，再用自己选择的一小段已有文稿等低影响任务检查实际功能。需要验证语音服务时，另用用户授权的素材执行真实任务；服务可能计费。
4. 让 Agent 重新读取安装后的 `SKILL.md`，或开启新会话。已有对话不会因为文件更新就自动替换上下文中已加载的旧 Skill。

旧入口会转为兼容入口，任务、凭据和知识库选择继续沿用。详见[品牌迁移](../references/brand-migration.md)；历史 Release 资产及标签保持原样。

### 已安装承意 1.6.0 及以后

完成上述跨品牌迁移后，后续更新使用承意的正常更新入口。开始新任务时，Skill 会检查 GitHub 最新正式版；有新版就提醒，不自行安装。检查使用 24 小时缓存；`plan`／`plan-text` 对同一个新版每天最多提醒一次。检查断网或失败不阻断原任务，下载素材和云端语音等功能仍需各自的网络条件。

需要更新时可以对 Agent 说「`@cy-charmyee 更新`」或「`$cy-charmyee 更新`」；不支持这些调用方式时，说「使用 cy-charmyee 更新自己」。用户明确要求后，程序下载官方 Release ZIP，校验外部 SHA-256 和包内完整清单，使用当前 Skill 的真实位置、已有工作目录与本机状态运行安装器。已有本地程序改动会按安装器规则保留备份，原数据保留。完成后仍要做本地 `doctor` 与适当的功能检查，再让 Agent 重读新版 `SKILL.md` 或开启新会话。

需要手动检查或诊断时，通过已安装 Skill 的入口执行：

```powershell
$cyRun = '<已安装 cy-charmyee>\scripts\invoke.ps1'
& $cyRun check-update          # 使用 24 小时缓存
& $cyRun check-update --force  # 强制查询
& $cyRun update                # 只检查，不安装
& $cyRun update --apply        # 用户明确要求更新后执行
```

在当前 PowerShell 进程及其子进程中设置 `$env:CY_UPDATE_CHECK = '0'` 可以关闭日常检查；显式 `update --apply` 仍可使用。

安装结果和 `doctor` 只反映本机状态；`awaiting_api` 说明尚无语音凭据，不妨碍处理已有文字。具体配置和参数见[安装指南](../INSTALL.md)。

## 失败、修复与回退

- 如果 1.1.0 检查或更新时因 GitHub 证书链错误失败，可从[最新 Release](https://github.com/ScarfaceAI/CY-CharmYee/releases/latest)下载新版 ZIP，按上方手动升级步骤使用同一 Windows 用户和原安装参数运行安装器，再检查本地入口。
- `v*` 正式标签不可重写或删除，已发布的 Release 和资产保留。失败时不覆盖旧标签或资产。
- 标签推送或发布过程被中断时，先检查该标签对应的 Actions 和 Release，确认实际状态再决定后续操作，避免重复发布。
- 已发布版本有缺陷时，修复后走新的 PR 并发布新补丁；需要撤回某项功能时，使用 revert PR 并发布新版本。
- 用户需要回退旧 ZIP 时，先查看相应版本的迁移说明，保留数据和配置，再确认旧版兼容性。不要把删除用户数据当作回退步骤。

参考：[GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow)、[语义化版本 2.0.0](https://semver.org/lang/zh-CN/)。
