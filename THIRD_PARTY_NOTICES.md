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

An earlier private, local-only workflow used two files from `a550752845-hue/douyin-video-transcript` at commit `692b064b50fe78f1194c6a243632a6b09e49d658`. That snapshot did not provide an explicit license. **Neither file is included in this public repository or its installation package.** The independently implemented public acquisition adapter uses HTTP share pages and headless Playwright responses, with a separately installed yt-dlp fallback for single videos. No upstream authorization is implied.

早期本地工作流使用过上述仓库中的两份文件，该快照未提供明确许可。公开版不包含这两份文件；新的下载适配器独立实现，不声称已获得旧上游授权。

Doubao ASR is an external service governed by its provider's terms. Each user supplies their own account and API credentials. Douyin, DeepSeek, Codex, Claude, Gemini, Cursor and OpenCode names identify interoperability targets; this project is not an official product of those providers.

The hero illustration was generated for this project with OpenAI image generation. The workflow diagrams are project-authored SVGs. A configuration screenshot, when included, shows the project's own empty local dialog.
