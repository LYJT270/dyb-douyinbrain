# 程序来源与第三方依赖

抖音脑公开版在 Windows 本地运行，程序与用户工作数据分离。自有代码由 LYJT270 按项目根目录的 MIT License 发布。豆包语音识别的接口契约见[录音文件识别极速版官方文档](https://www.volcengine.com/docs/6561/1631584?lang=zh)；实际请求参数由 `scripts/runtime/douyin_text/asr.py` 维护。

历史本地版本曾使用 [douyin-video-transcript](https://github.com/a550752845-hue/douyin-video-transcript) 的两个下载相关文件，参考来源为提交 [`692b064b50fe78f1194c6a243632a6b09e49d658`](https://github.com/a550752845-hue/douyin-video-transcript/commit/692b064b50fe78f1194c6a243632a6b09e49d658)。该来源快照未提供 LICENSE／COPYING；**公开版不包含旧的 `douyin_dantiao.py` 和 `work_links.py` 文件**。公开版下载实现为独立编写，使用 Playwright 浏览器页面的网络响应解析，必要时使用 yt-dlp 回退单条作品。

Playwright、yt-dlp、Python、FFmpeg、Chromium 等第三方组件按其各自的许可证提供或安装，不因本项目的 MIT License 改变。依赖版本以运行时配置为准，许可证及获取方式见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。Key、Cookie、媒体、缓存和历史任务不属于源码或安装包。
