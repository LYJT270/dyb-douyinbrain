# 运行命令与状态

旧任务、重复素材或旧稿修改先用只读 `resume`，普通任务按保存范围继续用 `run <task> --saved-scope`；离线换问题用 `reanalyze <task> --instruction ...`。详细命令与授权边界见[恢复与复用](continuation.md)。

默认使用随包 PowerShell 入口，不先打开浏览器识别。`<skill>` 取安装结果的 skill 路径，或当前 SKILL.md 的所在目录；`<task>` 取真实任务 ID。

```powershell
$dyRun = '<skill>\scripts\invoke.ps1'
& $dyRun doctor
```

该入口从本机 settings.json 选取 workspace 和它的 Python，调用本 Skill 相对路径的 brain.py；无需猜测旧电脑盘符。doctor 的 `execution_route` 应为 `bundled_local_engine`／`doubao_voice_api`，`web_transcription_fallback=false`；这确认程序路线，不代表云端已识别成功。环境缺失先运行 install.ps1 补齐，不转向网页识别。

## 首次介绍与配置状态

```powershell
& $dyRun welcome                  # 只读取中文介绍与本机状态
& $dyRun welcome --lang en        # 英文介绍
# Agent 已在聊天中展示完整介绍后，才登记本版本已展示：
& $dyRun welcome --acknowledge    # 英文可另加 --lang en
```

`welcome` 返回 `message`、8 组 `capabilities`、`readiness` 和 `onboarding`，不读取用户意图，也不调用语音识别。功能目录来自 `assets/capabilities.json`；Agent 按[首次介绍](onboarding.md)在聊天中说明全部组别，再结合用户当前目标继续。安装前入口不可用时先读指南介绍，安装后再核对状态。

`onboarding` 包含 `revision`、`due`、`guide_file`、`welcome_command`、相对工作目录的 `state_file` 和 `meaning`。`doctor`／`init` 也回传该状态；安装结果包含 `onboarding_reference`、`welcome_command`、`onboarding` 和 `next_action_for_agent`（某些提前失败阶段可能尚未取得本机状态）。仅在已于聊天实际展示介绍后执行 `--acknowledge`，它向工作目录 `.local/onboarding.json` 写入 `presented_revision`、时间和语言，表示介绍已展示，不代表理解、验收或授权；其他命令不会自动登记。

`readiness.existing_text` 表示可由 Agent 处理现有文字；`download_environment` 是素材获取依赖状态；`new_speech` 只反映本地媒体音轨工具与凭据是否具备试用条件，抖音媒体还需要获取环境。`knowledge_destination` 不代表写入授权，视觉核对以当前 Agent 工具为准；`cloud_access` 和 `douyin_login` 均未测试。凭据存在或本机环境就绪不代表真实云端识别、登录或任务成功。

## 媒体获取与识别

单条公开视频先尝试普通 HTTP 分享页，再在无登录态的无头页面调用网站自身加载的访客能力获取作品数据；必要时尝试本机已有专用浏览器状态，保留 yt-dlp 的单视频回退。1.3.0 本地候选曾用固定样本实测匿名获取、真实语音识别和画面校对，部分素材获取失败，且未做听音核对；详见[上一轮验收记录](../docs/verification/v1.3.0.md)，该记录不代表 1.3.1 的本轮结果。实际任务按获取和识别结果报告。

常规获取在后台运行，浏览器使用 `headless=True`，不弹窗抢焦点，不调用 Computer Use，不自动登录或处理验证码，也不使用第三方付费解析。浏览器进程可以复用，每条链接使用新的浏览器上下文。仅当可见阻挡容器明确要求登录或验证时才报告相应原因；标题、正文里的相关词或普通登录按钮不能证明被阻挡。只有用户明确要求登录、验证或界面排障时才运行 `login` 打开可见专用浏览器，登录和验证码由用户本人完成。

普通 `plan`／`run` 流程中，每个输入链接开始处理后，从发现到音轨验证的获取时限为 90 秒，最多同时运行 2 个后台获取进程；排队时间不计入时限。主页是一个输入时，主页发现及其多个作品的准备可能共用这 90 秒。付费豆包识别由父进程单独执行，不受获取时限中断；失败或结果未知的付费请求按下文规则处理。

需要博主全量分析或独立批量下载主页视频时，使用 [creator 任务](creator.md)：主页分页与逐作品获取分别执行，获取参数默认每项 300 秒、2 路并发；语音识别单独计时并在授权范围内执行。

批量链接任务中，某项音轨获取并验证完成后，可进入父进程的串行识别，同时继续获取其他素材；识别顺序可能与输入顺序不同。重复素材按 ID 去重，最终结果按原输入顺序编号，失败项保留位置。

语音识别由随包 asr.py 请求豆包语音 HTTP 接口，不使用网页上传、网页字幕或其他识别服务替代，也不自动录音；付费重试遵守下文规则。

排查素材获取时可执行：

```powershell
& $dyRun inspect-source '<视频链接或本地媒体>' --anonymous-only
& $dyRun inspect-source '<视频链接或本地媒体>' --anonymous-only --download-audio
```

两种检查都不调用语音识别：不带 `--download-audio` 只检查元数据；加上该参数还会下载并验证音轨，但仍不代表云端识别成功。`--anonymous-only` 不使用已保存的账号或浏览器状态；去掉该参数才允许必要时尝试已有专用浏览器状态。依据输出及 `report_directory` 报告实际结果。此检查不用于证明作者主页分页完整。

## 版本检查与升级

```powershell
& $dyRun check-update          # 24 小时缓存；新任务先检查
& $dyRun check-update --force  # 用户明确要求立即检查时
& $dyRun update               # 只查询，不安装
& $dyRun update --apply       # 用户明确要求更新本 Skill 时
```

`check-update` 返回当前版本、最新版本及 `should_notify`。只有该值为 true 时主动提示；每个新版最多每天提醒一次。`unavailable` 表示暂时不能联网检查，继续原任务；设置 `DYB_UPDATE_CHECK=0` 可以停用日常检查，显式升级仍会联网查询。仅访问公开 GitHub Release 元数据，不发送文稿、Key 或登录状态。

`update --apply` 重新查询最新正式版，下载官方 ZIP 及 SHA-256 文件，校验压缩包和内部完整清单，调用安装器更新当前 Skill 的真实目录。继续使用原本机设置和工作目录；旧程序留备份，Key、素材和任务数据不属于替换范围。安装失败且已生成有效旧程序备份时恢复旧程序，失败版本留在 `.trash`；依赖安装若中断，按实际错误修复后再试。查看 `update-result.json` 和返回的日志路径，不自行清空数据或强行删除更新锁。

`updated` 表示新版程序及本地入口验证通过，随后重读新版 Skill；`up_to_date` 表示无需更新。它们都不代表付费语音或云端权限已实测。源代码 Git checkout 使用维护发布流程，不能被自更新安装包覆盖。首次从 1.0.x 升级需先通过新版 ZIP 安装一次，1.1.0 起支持以上命令。

## 建立与执行任务

```powershell
& $dyRun plan '<链接、分享文案、本地媒体或 TXT 链接清单>'
# 已有文稿；正文不是链接清单：
& $dyRun plan-text '<UTF-8 文稿1.txt>' '<文稿2.txt>'
& $dyRun confirm <task> --purpose transcribe --evidence '<用户实际原话>'
# 分析或改稿时，把用户已给出的具体要求同时传入；不重新询问已明确的目标：
& $dyRun confirm <task> --purpose rewrite --evidence '<用户实际原话>' --instruction '<具体改稿要求>'
# 上面两条 confirm 按实际用途选择其一，分析时 purpose 使用 analyze。
& $dyRun run <task>
# 或仅使用匿名路径（二选一）：
# & $dyRun run <task> --anonymous-only
& $dyRun show <task>
```

`plan` 不获取媒体、不调用语音识别；入口会进行上述可关闭的版本检查。`run --anonymous-only` 不使用已保存的账号或浏览器状态。批量任务逐条隔离失败，保留成功结果和原始序号，交付时说明未成功的条目。明确指令与后续用途回复都可以作为真实 evidence，不需要机械等待第二次确认。`purpose` 为 `transcribe`、`analyze`、`rewrite`、`ingest`、`compile`；分析与改写还需 `--instruction '<实际要求>'`。多个交付目标可记录在 instruction 中，涉及入库时 purpose 选择 ingest 或 compile。

作者主页在 confirm 选择 `--latest N`、`--start YYYY-MM-DD --end YYYY-MM-DD` 或 `--all`。短链解析后才发现是主页时，只补范围。日期含起止日，置顶顺序不代表发布时间。

`--category reference`（默认外部参考）、`benchmark`（明确对标）、`own`（用户明确说明本人原稿）决定素材类别。

输入清单只接受逐行链接或媒体路径，不能嵌套清单。已有普通正文用 plan-text，多条独立文稿按顺序一起传入，统一批次交付；粘贴稿先原样保存 UTF-8 文件再导入。源文稿快照和结果不能被校对覆盖。

`plan-text` 仅接受 UTF-8 `.txt`／`.md`。已有 `.srt` 由 Agent 直接按[字幕处理说明](content.md#批量文字和已有字幕)读取、另存并检查时码，不通过 `plan-text` 假装已支持专用导入。

## Agent 接力

run 完成识别／导入后进入 `awaiting_review`。先读 task.results 的全部相关正文，找出数字、专名和内容冲突等疑点，按[当前会话的实际能力](review-capabilities.md)针对需要的范围用 `prepare-review` 准备材料并实际完成校对；用户明确只看已有材料时加 `--cached-only`，缺失则报告，不联网补取。另存每条正文文件，再依 results 顺序传递多个 `--file`。准备材料不会调用 ASR 或登记完成状态：

```powershell
& $dyRun register-review <task> --file '<校对1.txt>' --file '<校对2.txt>'
& $dyRun deliver <task> --kind review
# 改稿另存，后续指令作为证据：
& $dyRun register-spoken <task> --file '<口播1.txt>' --file '<口播2.txt>' --evidence '<实际改稿原话>'
& $dyRun deliver <task> --kind spoken
```

文件位于 workspace 内，内容只放正文。命令校验数量、顺序、源文件哈希与版本分离，不生成校对／改写内容；内容质量仍由 Agent 负责。

任务记录中的结果、正文、交付与归档路径相对 workspace 保存，命令输出附带 `workspace`，向用户报告时拼成完整路径。目录改名或移动后用 `init --register` 重新登记，用户输入、知识库目标和发布清单仍按实际路径核对。

其他参考中的 `$dyPython` 可取 doctor 的 `runtime_python`，`$dyBrain` 为 `<skill>\scripts\brain.py`。纯文稿处理尚未安装完整媒体环境时，可用已有 Python 执行 `brain.py --workspace '<实际工作目录>' plan-text ...`，无需安装浏览器或语音 Key。媒体任务默认仍使用上述已登记入口。

每批校对完成后，按[文稿协作与交付](content.md#校对检查记录)在任务目录保存对应版本的检查记录；压缩或明显删减时按同文的“压缩前后对照”使用 `scripts/compare_text.py` 计算并保存对照。常规处理直接完成，不增加确认轮次。

`deliver --kind raw` 用于明确需要原文的交付。合并稿使用 UTF-8 BOM、Windows 换行，每条一段；来源与日志不混进正文。新版文件以内容哈希区分，旧版保留。

分析稿单独保存 Markdown，再调用 `finish-analysis <task> --file '<分析稿.md>'`。用户已经授权分析而任务 purpose 兼含入库时，在任务目录留分析稿并继续对应入库阶段，不伪造 finish-analysis 的状态。

| 状态 | 接下来做什么 |
|---|---|
| needs_intent | 目标不清时问；已清楚则记录实际指令 |
| confirmed | 执行 run |
| awaiting_review | Agent 完成并登记校对 |
| ready_to_deliver | 生成并检查交付文件 |
| awaiting_analysis | 完成分析稿并登记 |
| awaiting_edit | 依当前协作阶段完成样稿或整批改稿 |
| ready_for_ingest / awaiting_compile | 按知识库参考完成成组归档／编译／实际发布 |
| incomplete / failed | 保留结果、说明失败；需要重试时取得实际重试指令 |
| completed / published | 核对实际交付或发布回执，说明未验证部分 |

## 复用与重试

续跑先在本地检查成功缓存，符合媒体内容／ID、识别参数和版本时直接复用，再为未就绪素材联网；已成功分片也会复用。用户明确重新识别时，confirm 加 `--retranscribe`，另存版本。

失败或结果未知的付费请求不自动重提；核对后用户明确要求重试，用 `run <task> --retry-evidence '<用户实际原话>'`。成功分片仍复用。

SRT 用 `export-srt <task>` 从已存时间生成，不重新调用识别；原始文本没有时间信息时不能编造 SRT。用途改变可以建立新任务并复用成功缓存，用户真实后续指令已经足以记录用途，不重复问一遍。

普通 `dy-...` 与博主 `creator-...` 是不同任务：普通 `export-srt`、`archive`、`publish` 等命令不能直接接 `creator-...`。组合处理时检查实际可用的源转写及目标库规则；没有直接入口就由 Agent 按请求准备和核验独立文件，不伪造调用结果。具体见[博主任务组合说明](creator.md#与普通文稿任务组合)。
