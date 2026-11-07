# 博主全量分析与主页视频下载

> 本文对应当前源码候选，尚未公开发布。完整账号、真实语音与视觉核对是否通过，以本轮实际运行证据为准。

本入口处理一个抖音公开主页或含一个主页链接的分享文案。`analyze` 分析当前可访问的视频和图文；`download` 独立下载主页视频及发布文案，不处理图文、不调用语音识别。普通的指定范围转写仍使用 [runtime.md](runtime.md) 的流程。

命令使用安装后的 Skill 入口，`<task>`、`<token>`、`<packet>` 和作品 ID 从实际输出取得；结果中的路径相对返回的 `workspace`。

```powershell
$dyRun = '<skill>\scripts\invoke.ps1'
```

## 主页发现与续跑

```powershell
& $dyRun creator plan '<主页链接或分享文案>' --mode analyze --images --instruction '<用户的分析目标>'
& $dyRun creator discover <task>
& $dyRun creator show <task>
```

仅在当前会话实际具备打开并理解图片的工具时使用 `--images`。有独立并行视觉任务能力时，还可以加 `--parallel-vision`；之后能力变化用 `creator capabilities <task> --images [--parallel-vision]` 按实际工具更新。不能看图时仍可发现主页、准备免费素材并报告缺口，但不能授权此入口的完整视觉分析识别或声称视觉分析完成。

分析模式默认使用 `compact` 可用媒体版本；需要最高可获取画质时在 `plan` 中指定 `--quality best`。下载模式默认 `best`。

`plan` 不下载媒体、不调用语音识别；短链解析会发送普通 HTTP 请求。`discover` 后台逐页保存作品和进度，不调用语音识别；`--anonymous-only` 不使用已有专用浏览器状态，`--max-seconds N` 调整发现时间参数，默认 600 秒。未到分页末尾时，本次主页发现是不完整的，已发现的内容仍可处理和交付。

`pagination_complete` 只表示已到分页末尾；若有无法标准化的原始行，即使到末尾，`discovery_complete` 仍为 false。此类行记入 `discovery.unresolved_records`，原始行、所在页面文件及行内索引保存在 `原始作品.jsonl`，供核对而不凭猜测合并。

每次执行 `discover` 都重新刷新主页，然后判断作品缓存。未完成的刷新保留本任务既有作品，并标出本轮未见项目；完整刷新时，本轮未见的旧项不进入本次有效清单，旧原始页、旧任务和已有材料保留。这表示本轮未见，不能据此断言作品已删除。主页范围仅指当前会话实际可访问的公开作品。

## 只分析标题或发布文案

用户明确只需要主页标题、发布文案或元数据分析时，发现并导出后，由 Agent 实际阅读 `作品明细.csv` 中返回的字段，按要求归纳并引用具体作品及来源：

```powershell
& $dyRun creator plan '<主页链接或分享文案>' --mode analyze --instruction '<只分析标题／发布文案的实际要求>'
& $dyRun creator discover <task>
& $dyRun creator export <task>
```

此路线不运行 `creator run`，不下载作品或调用豆包语音；返回的清单取决于平台当前可访问数据。导出的 `报告.md` 不会自动生成语义结论，Agent 应另存自己的分析，聊天先给结论、例子及分页是否完整。标题和发布文案不能代表完整口播或画面，未读或未看的内容如实说明。

## 用量预览与批次授权

分析模式先查看新增豆包识别用量；预览不调用语音 API：

```powershell
& $dyRun creator preflight <task>
# 只预览指定作品时，可重复 --item：
& $dyRun creator preflight <task> --item douyin-<作品数字ID>
# 只在用户账户实际适用的每小时单价明确时填写：
& $dyRun creator preflight <task> --price-per-hour <实际每小时单价>
```

向用户展示待新增／剩余作品数、已知时长、未知时长数量及适用的预计用量，说明数字只覆盖当前已发现的作品；未知时长不计作零，平台返回的时长是估算依据。价格只有在实际适用单价和计费条件明确且时长可估时才展示。程序按时长乘每小时单价作线性估算，不自动计算套餐、阶梯、取整或抵扣，估算不是账单，币种和额度按用户账户说明。需要更准确时，可在尚无识别授权的情况下运行 `creator run <task>`，先免费准备媒体，再重新预览；已有授权的任务运行时可能提交该授权范围内的识别。

用户看过预览并明确授权该批次后，使用对应 `usage.token` 和用户实际原话登记；可选的上限单位为音频秒：

```powershell
& $dyRun creator authorize <task> --quote <token> --evidence '<用户确认本批识别的实际原话>'
# 按用户实际要求加 --max-audio-seconds <秒数>，不是默认价格或费用上限。
& $dyRun creator run <task>
```

授权冻结本次预览对应的作品和内容版本；新增作品或内容变化需重新预览、取得相应授权。`--max-audio-seconds` 是该批次的用量上限，并非价格。失败或结果未知的付费请求先核对状态，再按用户实际重试指令使用 `creator run <task> --retry-evidence '<用户原话>'`；不得自动重提，已成功分片继续复用。

`run` 默认 2 路作品获取、1 路识别；`--download-workers` 可设为 1–4，`--asr-workers` 可设为 1–2，仅在豆包账户额度允许时增加识别并发。`--item-timeout` 是逐项获取时限参数，默认 300 秒，不限制豆包识别；`--item` 可重复选择作品，`--limit-items N` 仅限制本次处理数，不代表整个主页已完成。匹配且校验通过的完整逐条分析可直接复用；一个作品失败不应覆盖其他作品的结果。

## 实际阅读、校对和逐条分析

```powershell
& $dyRun creator prepare <task>
# 只准备指定作品时，可重复 --item：
# & $dyRun creator prepare <task> --item douyin-<作品数字ID> --item douyin-<另一个作品数字ID>
& $dyRun creator claim <task> --worker '<核对者标识>'
# 按返回路径读取核对包、完整文稿和图片；完成实际核对并写结果 JSON 后：
& $dyRun creator record <task> --worker '<同一核对者标识>' --file '<workspace 内结果.json>'
# 每个核对包重复 claim、阅读和 record；未做完可释放本人持有的包：
& $dyRun creator release <task> --packet <packet> --worker '<同一核对者标识>'
```

`prepare` 默认只为已有素材且语音状态就绪的作品准备核对包，未就绪作品列在 `waiting_materials_or_speech`；无需先为它们获取封面。图文图片仍可能有缺口，须按实际结果记录。可重复 `--item` 缩小本次准备范围，匹配的完整分析优先复用。

`prepare` 默认 `--strategy content`，也可按内容选择 `action` 或 `subtitle`；`--max-frames` 为每条视频的帧数上限（1–120），`--batch-size` 为每包作品数上限（1–16，默认 4），`--prepare-workers` 为本地准备并发（1–2，默认 2）。这是准备全文和原图，不代表任何图片已被看过。`--reanalyze` 只重做原 `instruction` 下的分析。若只要求对已有材料换角度，读取旧任务已核对材料并另存报告，注明原覆盖范围和观察时间，不刷新主页或伪造旧任务缓存／完成标记；当前没有离线更换 `instruction` 的原生命令。若要求基于当前主页重新分析，则用 `creator plan --instruction '<新要求>'` 创建新任务并 `discover`，再复用有效媒体和转写。重新准备会替换待领取的核对包，应先结束或释放旧包。

按包阅读标题／描述、完整口播、封面和实际准备的帧或图文图片；一次阅读分别写入 `review` 和 `analysis`。图片可按宿主能力批量输入。宿主确实支持独立视觉任务且核对者能实际看图时，可以先试最多 2 路并行领取不同包；工具或预算不足时顺序处理。Python 准备线程不是视觉模型调用。对视频疑点按时间点补查；看图不等于听音，无法听清或未听音的内容保留疑点。

视频需要定点补查时，指定作品 ID 和原视频时间（秒）：

```powershell
& $dyRun creator detail <task> --item douyin-<作品数字ID> --start 12 --end 14 --every-frame --max-frames 40
```

`detail` 只读取该作品已校验的本地原视频，不调用 ASR；`--every-frame` 可选，`--max-frames` 默认 40、范围为 1–240。输出的 `supplement.file` 是补查清单，`images` 是准备好的帧；应实际查看需要的帧并检查是否受帧数上限限制。生成或领取材料不等于已看图。

结果 JSON 保存在 workspace 内，必须包含当前包的全部作品，每条的 `id` 与 `basis_sha256` 从该包原样取得。以下只是结构示意，所有占位内容必须替换为实际材料；`read_full_transcript` 只能在实际通读后设为 `true`：

```json
{
  "packet": "<核对包 ID>",
  "items": [
    {
      "id": "<作品 ID>",
      "basis_sha256": "<该作品核对包中的 basis_sha256>",
      "review": {
        "read_full_transcript": true,
        "viewed_images": ["<该作品实际看过的图片 file>"],
        "supplement_manifests": [],
        "text": "<校对后完整正文；无口播时可为空>",
        "corrections": []
      },
      "analysis": {
        "category": "<类别>", "topic": "<选题>", "angle": "<角度>",
        "summary": "<逐条简析>", "opening": "<开头方式>", "format": "<内容形式>",
        "evidence": [{"kind": "caption", "quote": "<发布描述中的原文片段>"}]
      }
    }
  ]
}
```

每条 `analysis` 的六个文字字段和至少一项依据都要填写。依据可以是 `{"kind":"caption","quote":"原文片段"}`、`{"kind":"transcript","quote":"原文片段"}` 或 `{"kind":"frame","file":"实际看过的图片 file"}`；引文必须出现在对应原始材料中，画面引用必须在该条 `viewed_images` 中。使用补查帧时，将本作品的 `supplement.file` 加入 `review.supplement_manifests`，再把实际看过的补帧路径加入 `viewed_images`；基础核对包列出的图片仍须实际查看。更正正文时在 `corrections` 中逐项写 `before`、`after` 和同格式 `evidence`，并以有实际依据的内容更正。机器原文保留，校对稿另存。不能完成的作品仍须在 `items` 中登记 `id`、`basis_sha256`、`status: "unavailable"` 和真实 `reason`。

`record` 会核对包、作品和图片版本；要达到视觉核对完整，包内该作品列出的图片必须实际看完且没有来源缺口。未看过的图不填入 `viewed_images`，缺失的口播、封面或画面应如实保留为不完整。

## 时间归并与交付

完成可处理的逐条结果后，按发布时间从早到晚归并；置顶作品回到原发布时间，时间未知单列。分析互动时注明采集时间并考虑发布时间和内容形式。基于已登记作品在 workspace 内创建汇总 JSON：

```json
{
  "account": "<账号定位及依据>",
  "content": "<内容特点及依据>",
  "topics": "<选题方向及依据>",
  "stages": [
    {"title": "<时间阶段>", "summary": "<该阶段总结>", "item_ids": ["<依据作品 ID>"]}
  ]
}
```

`stages` 和每个 `item_ids` 按时间顺序排列，引用实际已分析的作品；结论标明作品及文字、图片或时间点依据。登记并检查状态：

```powershell
& $dyRun creator report <task> --file '<workspace 内汇总.json>'
& $dyRun creator export <task>
& $dyRun creator show <task>
```

`outputs/creators/<账号键>/reports/<task>/` 包含 `报告.md`、`作品明细.csv`、`原始作品.jsonl`、`分析与核对.jsonl` 和 `采集与处理状态.json`。报告的逐条内容包括选题、角度、开头、形式、校对正文链接和已记录的疑点；CSV 包括标题、原稿与校对稿路径、分析状态以及分类、选题、角度、摘要、开头和形式等字段。`分析与核对.jsonl` 按作品保存处理状态、互动快照及有效的核对／分析结果与画面依据，未完成的部分保持缺口。

任务记录位于 `runs/`，媒体缓存在 `.cache/`。报告、作品明细与状态需一并查看：已发现、下载、识别、视觉核对和分析分开计数；`discovery_complete` 与最终 `complete` 是不同状态。部分成果可交付，结论须说明覆盖范围与缺口。

聊天交付先说明账号与选题结论、具体作品依据、已处理范围和缺口，再附报告及明细；如果只完成发现或元数据分析，不称完整内容分析。

## 独立下载主页视频

```powershell
& $dyRun creator plan '<主页链接或分享文案>' --mode download
& $dyRun creator discover <task>
& $dyRun creator run <task>
& $dyRun creator show <task>
```

下载默认按平台返回的画质、码率等信息优先选择最高的可用版本；`--quality compact` 可在 `plan` 时明确选择省空间版本，可能改变实际画质，具体以输出元数据为准。这里选择已有版本，不自动转码或清理已有文件。独立视频、发布描述 `.txt` 与元数据 `.json` 在 `outputs/creators/<账号键>/videos/`；同 ID 不同内容可能带哈希后缀。下载不触发豆包识别，也不代表已分析、看图或完整发现主页。

视频地址失效等获取失败时，程序可尝试一次刷新来源地址；保留的部分文件可供续跑，已完整接收的文件需先校验。续传时若可核对的 ETag 显示版本变化，程序拒绝拼接不同版本并报告错误。

分析与下载可以复用匹配的媒体缓存，但下载高清版本不会替换原转写所用的媒体。重新分析优先使用可校验的 ASR 同源媒体；若同源材料缺失，保留原转写并报告画面无法同源核对，不把其他画质版本冒充原素材。图文只因背景音乐的 CDN 地址变化时，不应使其他内容未变的图片分析失效。

聊天先报告下载成功／失败数量、可核实的画质和保存位置，再给明细文件。发现未完整或画质信息缺失时如实说明。

## 与普通文稿任务组合

`creator-...` 与普通 `dy-...` 是不同任务类型。普通流程的 `export-srt`、`archive`、`publish` 等命令不能接收 `creator-...`，不要虚构博主任务的字幕导出或入库命令。用户明确要求组合时，检查实际可用的源转写和有效缓存，并按目标流程或目标库规则处理；没有直接入口时，Agent 按用户要求准备独立文件、实际写入并读回，清楚报告结果与缺口。入库或编译须有用户明确且仍有效的授权。

组合任务或跨任务续办可用[套件总记录](work.md)关联已有 `creator-...`、`dy-...` 与真实产物，保留各自记录；它不改变 ID 的适用范围，不会替换批次授权或生成离线换角度的原生任务。
