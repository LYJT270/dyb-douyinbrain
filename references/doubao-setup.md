# 豆包语音配置：手把手教程

抖音脑 Douyin-brain 使用你自己的豆包语音服务。开通语音识别、取得语音 API Key 并保存在本机后，可以用一小段录音检查是否真的能转写。

官方文档核对日期：2026 年 11 月 5 日。控制台菜单调整时，以当前页面和文末官方指引为准；此日期不代表已登录实测控制台。

## 配置时直接打开这些网址

下面都给出完整网址，可以点击，也可以复制到浏览器地址栏。先完成注册／登录，再开通语音服务，最后创建语音 API Key。

- 新用户注册：[https://signin.volcengine.com/auth/signup](https://signin.volcengine.com/auth/signup)
- 登录并返回语音 Key 页面：[https://signin.volcengine.com/auth/login?redirectURI=https%3A%2F%2Fconsole.volcengine.com%2Fspeech%2Fnew%2Fsetting%2Fapikeys](https://signin.volcengine.com/auth/login?redirectURI=https%3A%2F%2Fconsole.volcengine.com%2Fspeech%2Fnew%2Fsetting%2Fapikeys)
- 开通语音模型：[https://console.volcengine.com/speech/new/setting/activate?projectName=default](https://console.volcengine.com/speech/new/setting/activate?projectName=default)
- 创建／管理语音 API Key：[https://console.volcengine.com/speech/new/setting/apikeys?projectName=default](https://console.volcengine.com/speech/new/setting/apikeys?projectName=default)

带 `projectName=default` 的链接以 Default 默认项目为例。如果你使用其他项目，打开页面后先在左上角切回那个项目；开通服务和创建 Key 要在同一项目完成。

以上开通页和 Key 页面来自[官方控制台指引](https://docs.volcengine.com/docs/doubao-voice/console-guidance?lang=zh)及[官方 API Key 使用说明](https://docs.volcengine.com/docs/DoubaoVoice/APIKeyUsage?lang=en)。未登录时跳到火山引擎登录页属于正常流程，完成登录后返回语音页面。

## 第 0 步：先把本机环境准备好

1. 推荐把安装包内 `INSTALL.md` 的安装提示词发给有本地文件和终端能力的 Agent，或把 Release 安装包／仓库源码目录交给它。
2. Agent 会解压、安装程序、补齐依赖，并设置工作目录和知识库。你不需要手动选路径或执行命令。
3. 安装环境就绪后，如果尚无凭据会出现豆包语音配置窗口；准备好 Key 后，在这个窗口粘贴保存。暂时没有 Key 可以先跳过。

如果你选择手动安装，解压安装包后双击 `install.cmd`。若安装已经在运行，继续当前安装即可，不必再次启动。

如果环境已经配置好，直接从第 1 步开始。只处理已有文字稿时，可以暂不配置语音 Key。

这一步的完成标志：安装器或 Agent 报告本机运行环境准备完成；这还不代表语音服务已经验证通过。

## 第 1 步：登录豆包语音控制台

1. 没有火山引擎账号时，先打开注册页：[https://signin.volcengine.com/auth/signup](https://signin.volcengine.com/auth/signup)，按页面要求注册。
2. 已有账号时，直接打开语音服务开通页：[https://console.volcengine.com/speech/new/setting/activate?projectName=default](https://console.volcengine.com/speech/new/setting/activate?projectName=default)。如果跳到登录页，就在登录页完成账号登录。
3. 如果网页要求补充账号信息或完成认证，先按页面提示处理；完成后再次打开上面的语音服务开通网址。
4. 登录后核对浏览器地址，应回到 `console.volcengine.com/speech/` 下的页面。

需要单独打开登录页时，可以使用这个已带语音页面回跳目标的网址：[https://signin.volcengine.com/auth/login?redirectURI=https%3A%2F%2Fconsole.volcengine.com%2Fspeech%2Fnew%2Fsetting%2Fapikeys](https://signin.volcengine.com/auth/login?redirectURI=https%3A%2F%2Fconsole.volcengine.com%2Fspeech%2Fnew%2Fsetting%2Fapikeys)。登录后再进入第 3 步的开通管理页。

这里使用的是火山引擎的豆包语音服务。你在火山方舟大模型聊天页面创建的聊天 Key，不能直接填到这个语音配置窗口；也不需要在豆包聊天 App 中寻找 Key。

这一步的完成标志：你已进入语音控制台，可以找到项目切换、模型服务开通或 API Key 管理入口。

## 第 2 步：先确定使用哪个项目

本步继续在语音服务页面操作：[https://console.volcengine.com/speech/new/setting/activate?projectName=default](https://console.volcengine.com/speech/new/setting/activate?projectName=default)。

1. 看控制台左上角的项目切换位置，记住当前项目名称。
2. 第一次使用、没有其他项目需求时，可以使用页面默认的 Default 项目。
3. 如果你已在另一个项目开通过语音服务，就切换到那个项目。
4. 后面的“开通服务”和“创建 API Key”始终在这个项目下完成。

确实需要查看已有项目时，项目管理页的完整网址是：[https://console.volcengine.com/iam/resourcemanage/project](https://console.volcengine.com/iam/resourcemanage/project)。新用户按默认项目继续即可，不必为了本工具额外创建项目。

语音服务权限和 API Key 按项目隔离。Key 来自项目 A、服务却开在项目 B，是配置后仍然报权限错误的一个原因。[项目与服务管理的官方说明](https://docs.volcengine.com/docs/doubao-voice/console-guidance?lang=zh)

这一步的完成标志：你知道自己正在使用哪个项目，后面的页面没有切换到其他项目。

## 第 3 步：开通录音文件识别极速版

先直接打开开通管理页：

[https://console.volcengine.com/speech/new/setting/activate?projectName=default](https://console.volcengine.com/speech/new/setting/activate?projectName=default)

1. 页面打开后，先核对左上角项目；使用其他项目时切换到对应项目。
2. 你已进入语音模型的“开通管理”入口，在页面中找到录音文件识别相关模型／能力。
3. 核对目标为“录音文件识别极速版”，资源标识为 `volc.bigasr.auc_turbo`。此网址进入开通管理总页，仍需在列表中选择该语音识别能力。
4. 尚未开通时，点击该服务对应的“开通”，在弹窗中查看协议、计费或试用信息，再由你确认开通。
5. 已经开通的，查看服务详情，确认当前项目的极速版能力可用即可。

如果你看到的是旧版控制台“API 服务中心”，先按上面的完整网址进入新版开通管理，再按新版流程继续。不要把官方文档中的示例 AppID 或声音复刻 ResourceID 当作自己的语音识别配置。

本项目上传已有录音并取得文字，不需要为了转写另外购买语音合成、声音复刻或音色。资源标识是供核对服务用的，程序已经填好，你不用把它当作 API Key 输入。

页面如果提供试用，可按页面规则申请；是否有试用额度、是否需要补充余额，以你账号当前显示为准。教程不要求购买固定金额的资源包。

[官方控制台开通指引](https://docs.volcengine.com/docs/doubao-voice/console-usage-faq?lang=zh) · [极速版接口与资源标识](https://docs.volcengine.com/docs/DoubaoVoice/recording-file-recognition-lite-http?lang=zh)

这一步的完成标志：同一项目下，录音文件识别极速版已开通，并具备当前可用的调用额度或计费条件。

## 第 4 步：创建并复制语音 API Key

直接打开 API Key 管理页：

[https://console.volcengine.com/speech/new/setting/apikeys?projectName=default](https://console.volcengine.com/speech/new/setting/apikeys?projectName=default)

1. 页面应显示语音服务的“API 管理／API Key 管理”，这里就是创建和管理语音 Key 的位置。
2. 再看一眼左上角，确认仍是第 2 步选定的项目。
3. 点击页面中的创建 API Key 入口，按当前页面要求填写名称等信息；名称可以写 `dyb-douyinbrain`。
4. 创建后，通过页面的复制按钮复制完整的 API Key。已有可用的语音 Key，也可以直接复制已有 Key。
5. 复制的是 Key 的值，不是名称、项目名或模型名称。

上面网址中的 `default` 指默认项目；如果你的服务开在别的项目，先切换到那个项目，再创建／复制 Key。

Key 保留在你自己的电脑上，下一步粘贴到本机窗口；不用发到 Agent 聊天里。如果页面只显示掩码或提示完整值仅在创建时展示，请按控制台提示取得完整值，不把星号当作 Key。

这一步的完成标志：你已复制到完整的豆包语音 API Key，并确认它与已开通服务属于同一项目。

## 第 5 步：粘贴到本机配置窗口

1. 自动安装已经弹出配置窗口时，直接使用这个窗口。尚未打开时，让 Agent 打开；手动安装则回到 dyb-douyinbrain 文件夹双击“配置豆包.cmd”。
2. 看到标题为“配置豆包语音转写”的窗口后，点击 API Key 输入框旁的“粘贴”；也可以在框内按 Ctrl+V。
3. 输入框显示圆点是正常的。下方会显示“已输入 N 个字符”，检查是否确实粘贴了完整内容。
4. 不要在这里只输入一个字符。Key 的完整长度以控制台实际值为准，不要照抄网上某个固定长度。
5. 点击“保存”，等待窗口关闭，并查看命令窗口提示。

如果你还没拿到 Key，可以点击配置窗口里的“手把手教程”打开本机教程窗口，该窗口不依赖默认浏览器；也可以打开安装目录中的 `豆包配置教程.html`。点击“打开语音 Key 管理”可返回控制台。

正常提示为“凭据已加密保存在本机，尚未验证语音服务权限”。这说明保存完成；下一步才检查服务是否能真实调用。

Key 按当前 Windows 用户加密，保存在本机工作目录中。换一台电脑或换 Windows 用户时，在那台电脑重新填写，不把旧电脑的密文当作可迁移 Key。

这一步的完成标志：本机显示凭据已加密保存，没有“凭据过短”或“凭据为空”等提示。

自动安装时，保存后安装器会自行检查结果，不需要你再回复“已保存”。安装环境与凭据保存完成后，安装即告完成；真实语音权限用下一步的首次任务验收。

## 第 6 步：用一小段录音验证

这是安装后的真实识别验收，可以随第一次转写任务完成，不要求为了安装额外录音。

1. 准备一段约 10～20 秒、说话清楚的本地录音，MP3、WAV 或手机导出的常见音频都可以。
2. 把文件路径发给 Agent，并明确告诉它：“用 dyb-douyinbrain 转写这段短录音，只转写、校对，不入库，用来检查豆包配置。”
3. 等待这次真实任务返回文字和结果文件。先用本地录音，可以把语音服务问题与抖音登录、下载问题分开检查。
4. 对照原录音，看看正文是否基本对应，并让 Agent确认这次请求已成功完成。

例如可以录一句：“这是语音配置测试，今天准备吃鸡蛋和玉米。”录你自己的内容也可以，不需要使用固定测试文案。

真实识别会使用账号额度或按服务规则计费，只提交你这次明确选择的测试录音。配置窗口和环境检查本身不会发送语音识别请求。

这一步的完成标志：这次录音实际获得了完整识别结果，Agent 给出可打开的文字稿。仅看到“凭据存在”或“环境就绪”，还不能算真实识别通过。

## 已经拿到 APP ID 和 Access Token 怎么办

如果你在旧版语音控制台取得的是 APP ID 和 Access Token，而不是新版单个 API Key：

1. 双击同目录的“配置豆包旧版.cmd”。
2. 把语音应用的 APP ID 填到 APP ID 框。
3. 把对应 Access Token 粘贴到 Access Token 框，点击“保存”。
4. 同样确认该应用／项目已具备录音文件识别极速版权限，再做第 6 步测试。

两个字段需要配对使用，不要把 APP ID 当作 Token。新用户优先按新版语音控制台的 API Key 流程配置。[官方新旧鉴权说明](https://docs.volcengine.com/docs/DoubaoVoice/LargemodelrecordingfileLiterecognitionAPI?lang=en)

## 卡住时按现象检查

### 提示凭据过短，或者只显示输入了 0／1 个字符

回语音控制台重新复制完整 Key，再点本机窗口的“粘贴”。不要只按回车，也不要复制 Key 名称。确认字符数已变化再保存。

### 找不到“开通管理”或菜单与教程不同

先直接打开：[https://console.volcengine.com/speech/new/setting/activate?projectName=default](https://console.volcengine.com/speech/new/setting/activate?projectName=default)。未登录就先完成登录；登录后仍不能进入时，把当前页面的菜单名称和不含密钥的跳转网址告诉 Agent，让它按当前页面继续引导。

### 已保存，但调用提示认证或权限问题

依次核对：Key 是否来自语音控制台、是否完整、是否与服务属于同一项目、是否已开通极速版。若用旧版，核对 APP ID 与 Access Token 是否配对。仅凭 HTTP 400 不能断定是哪一项；让 Agent查看已脱敏的服务状态码和错误说明。

### 提示余额、额度或资源不可用

语音服务状态从开通管理页查看：[https://console.volcengine.com/speech/new/setting/activate?projectName=default](https://console.volcengine.com/speech/new/setting/activate?projectName=default)。账户费用总览的完整网址为：[https://console.volcengine.com/finance/account-overview](https://console.volcengine.com/finance/account-overview)。按账户实际情况选择试用、开通或补充资源，不反复提交大批视频来测试。

### 保存成功，但 Agent 说没有凭据

告诉 Agent你配置时使用的工作目录路径，让它核对“配置窗口”和“运行任务”是否指向同一个 workspace。无需把 Key 再发到聊天中。

### 请求超时或连接中断

保留本次任务和请求记录，让 Agent先核对状态。结果未知时，不自动把同一段录音反复提交；核对后再由你决定是否重试。

## 让 Agent 一步步带着配置

你可以直接说：“用 dyb-douyinbrain 带我配置豆包语音，从第一步开始。”

Agent 应先问你现在到哪一步，随后一次给出一个阶段的操作和完成标志，完成后再继续。注册／登录、确认服务计费协议、复制并粘贴 Key 由你在本机完成；Agent负责解释入口、判断下一步、检查不含密钥的状态与测试结果。

涉及网页操作时，Agent 每次都应直接给出该步骤的完整网址、要找的菜单或按钮、完成标志；不能只说“去控制台”。如果页面受登录限制，就说明先登录并回到哪个具体网址。

## 官方资料

- [新版控制台：项目、模型开通与 API Key](https://docs.volcengine.com/docs/doubao-voice/console-guidance?lang=zh)
- [语音控制台常见问题](https://docs.volcengine.com/docs/doubao-voice/console-usage-faq?lang=zh)
- [录音文件识别极速版 HTTP](https://docs.volcengine.com/docs/DoubaoVoice/recording-file-recognition-lite-http?lang=zh)
