# Third-party components / 第三方组件

The MIT license at the repository root applies to this project's own code and documentation. Dependencies retain their own licenses. The installation ZIP contains source, documentation and artwork; Python, FFmpeg, Chromium and Python dependencies are installed separately.

根目录 MIT 许可适用于本项目自有代码与文档。依赖保留各自许可；安装包不内置 Python、FFmpeg、Chromium 或 Python 依赖的二进制文件。

| Component | Role | License / authoritative source |
|---|---|---|
| certifi | Mozilla root certificates for verified release downloads when Windows trust-store verification fails | [MPL-2.0](https://github.com/certifi/python-certifi/blob/master/LICENSE) |
| Playwright for Python | Headless Douyin page acquisition; a visible dedicated browser for explicitly requested login or verification | [Apache-2.0](https://github.com/microsoft/playwright-python/blob/main/LICENSE) |
| yt-dlp | Single-video extraction fallback | [Unlicense](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE); see its [third-party licensing notes](https://github.com/yt-dlp/yt-dlp#license) for bundled components |
| greenlet | Playwright dependency | [MIT and PSF-derived portions](https://github.com/python-greenlet/greenlet/blob/master/LICENSE) |
| pyee | Playwright dependency | [MIT](https://github.com/jfhbrook/pyee/blob/main/LICENSE) |
| typing_extensions | Python typing support | [PSF-2.0](https://github.com/python/typing_extensions/blob/main/LICENSE) |
| Python | Local runtime | [PSF license](https://docs.python.org/3/license.html) |
| FFmpeg / ffprobe | Audio extraction, media checks and preparation of review frames | [LGPL/GPL depending on build](https://ffmpeg.org/legal.html); Windows installer uses the [Gyan.FFmpeg WinGet package](https://github.com/microsoft/winget-pkgs/tree/master/manifests/g/Gyan/FFmpeg) |
| Chromium | Playwright-managed browser | [Chromium and third-party notices](https://www.chromium.org/developers/how-tos/get-the-code/) included with its distribution |

Exact Python package versions are pinned in `scripts/runtime/requirements.lock.txt`.

## Source history / 来源历史

An earlier private, local-only workflow used two files from `a550752845-hue/douyin-video-transcript` at commit `692b064b50fe78f1194c6a243632a6b09e49d658`. That snapshot did not provide an explicit license. **Neither file is included in this public repository or its installation package.** The independently implemented adapter uses HTTP share pages and headless Playwright. The page loads its own visitor SDK at runtime, and the adapter sends an ordinary XHR from that page's context to retrieve post data; that SDK is not bundled by this project. The adapter contains no copy of a signature-generation algorithm, does not automatically solve CAPTCHA or use a third-party paid parsing service, and retains the separately installed yt-dlp fallback for individual videos. No upstream authorization is implied.

早期本地工作流使用过上述仓库中的两份文件，该快照未提供明确许可。公开版不包含这两份文件；下载适配器独立实现。无头页面在运行时加载网站自身的访客 SDK，适配器在页面上下文中发起普通 XHR 请求获取作品数据；本项目不打包该 SDK，不复制签名生成算法，不自动处理验证码，也不使用第三方付费解析服务。单条视频仍保留单独安装的 yt-dlp 回退；不声称已获得旧上游授权。

Doubao ASR is an external service governed by its provider's terms. Each user supplies their own account and API credentials. Douyin, DeepSeek, Codex, Claude, Gemini, Cursor and OpenCode names identify interoperability targets; this project is not an official product of those providers.

The hero illustration was generated for this project with OpenAI image generation. The workflow diagrams are project-authored SVGs. A configuration screenshot, when included, shows the project's own empty local dialog.

Personal-vault instruction adapters are independently implemented from the published [OpenAI AGENTS.md](https://developers.openai.com/codex/guides/agents-md/) and [Claude Code memory](https://code.claude.com/docs/en/memory) interfaces. No third-party implementation code is included. / 个人知识库宿主适配独立实现，参考官方入口约定，不包含第三方实现代码。
