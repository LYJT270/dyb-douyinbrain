"""Generate the offline reader from the single Markdown tutorial source."""
from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path


def inline(text: str) -> str:
    result = []
    for part in re.split(r"(`[^`]+`|\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*)", text):
        link = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", part)
        if link:
            label, url = link.groups()
            result.append(f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(label)}</a>')
        elif part.startswith("`") and part.endswith("`"):
            result.append("<code>" + html.escape(part[1:-1]) + "</code>")
        elif part.startswith("**") and part.endswith("**"):
            result.append("<strong>" + html.escape(part[2:-2]) + "</strong>")
        else:
            result.append(html.escape(part))
    return "".join(result)


def render(text: str) -> tuple[str, str]:
    blocks, toc, paragraph, code = [], [], [], []
    listing = None
    in_code = False

    def flush():
        if paragraph:
            value = " ".join(paragraph)
            css = ' class="checkpoint"' if value.startswith("这一步的完成标志") else ""
            blocks.append(f"<p{css}>" + inline(value) + "</p>")
            paragraph.clear()

    def close_list():
        nonlocal listing
        if listing:
            blocks.append(f"</{listing}>")
            listing = None

    for line in text.splitlines():
        if line.startswith("```"):
            flush()
            close_list()
            if in_code:
                blocks.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
                code.clear()
            in_code = not in_code
            continue
        if in_code:
            code.append(line)
            continue
        if not line.strip():
            flush()
            close_list()
            continue
        heading = re.match(r"^(#{1,3}) (.+)$", line)
        if heading:
            flush()
            close_list()
            level, title = len(heading[1]), heading[2]
            anchor = f"section-{len(toc) + 1}" if level == 2 else ""
            if anchor:
                toc.append((anchor, title))
            attribute = f' id="{anchor}"' if anchor else ""
            blocks.append(f"<h{level}{attribute}>" + inline(title) + f"</h{level}>")
            continue
        item = re.match(r"^(\d+\.|-) (.+)$", line)
        if item:
            flush()
            kind = "ul" if item[1] == "-" else "ol"
            if listing != kind:
                close_list()
                listing = kind
                blocks.append(f"<{kind}>")
            blocks.append("<li>" + inline(item[2]) + "</li>")
            continue
        close_list()
        paragraph.append(line)
    flush()
    close_list()
    navigation = "\n".join(f'<a href="#{anchor}">{html.escape(title)}</a>' for anchor, title in toc)
    return "\n".join(blocks), navigation


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "references/doubao-setup.md"
    data = source.read_bytes()
    body, toc = render(data.decode("utf-8"))
    page = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>豆包语音配置：手把手教程 · cy-charmyee</title>
<style>
:root{color-scheme:light;font-family:"Microsoft YaHei UI","Microsoft YaHei",system-ui,sans-serif;color:#203047;background:#f3f5f9}
*{box-sizing:border-box}body{margin:0;line-height:1.85}.layout{display:grid;grid-template-columns:240px minmax(0,1fr);gap:28px;max-width:1150px;margin:32px auto;padding:0 24px}
aside{position:sticky;top:24px;align-self:start;background:#fff;border:1px solid #dee4ec;border-radius:14px;padding:20px;max-height:calc(100vh - 48px);overflow:auto}
.brand{font-weight:700;font-size:18px;color:#1557b0}.caption{font-size:13px;color:#64748b;margin:4px 0 18px}nav{display:grid;gap:8px}nav a{font-size:13px;line-height:1.65;text-decoration:none;padding:6px 8px;border-radius:6px}nav a:hover{background:#eef4ff}
main{background:white;border:1px solid #dee4ec;border-radius:16px;padding:36px 44px;min-width:0}h1{font-size:30px;line-height:1.4;margin:0 0 20px;letter-spacing:-.3px}h2{font-size:22px;margin:38px 0 16px;padding-top:28px;border-top:1px solid #e3e8ef;scroll-margin-top:24px}h3{font-size:17px;margin:26px 0 10px}
p{margin:14px 0}ol,ul{padding-left:26px}li{padding-left:5px;margin:10px 0}a{color:#1557b0;text-underline-offset:3px;overflow-wrap:anywhere}code{font-family:Consolas,monospace;font-size:.92em;background:#f0f3f8;color:#293d57;border-radius:4px;padding:2px 5px;overflow-wrap:anywhere}pre{white-space:pre-wrap;background:#f0f3f8;padding:16px;border-radius:10px;overflow:auto}
.checkpoint{background:#eff8f2;border-left:4px solid #3b8961;padding:12px 16px;border-radius:4px;color:#24543d}.foot{margin-top:36px;border-top:1px solid #e3e8ef;padding-top:18px;font-size:12px;color:#64748b}
@media(max-width:850px){.layout{display:block;margin:16px auto;padding:0 14px}aside{position:static;margin-bottom:16px;max-height:none}nav{grid-template-columns:repeat(2,minmax(0,1fr))}main{padding:26px 22px}h1{font-size:26px}}
@media print{body{background:white}.layout{display:block;margin:0;padding:0}aside{display:none}main{border:0;padding:0}h2{break-after:avoid}a{color:inherit}.checkpoint{break-inside:avoid}}
</style></head><body><div class="layout"><aside><div class="brand">cy-charmyee</div><p class="caption">首次配置 · 离线教程<br>按阶段完成，每步都有检查点</p><nav>__TOC__</nav></aside><main>__BODY__<p class="foot">本页由 references/doubao-setup.md 生成。教程可离线阅读；打开控制台和官方文档需要联网。</p></main></div></body></html>'''
    page = page.replace("__TOC__", toc).replace("__BODY__", body)
    page += "\n<!-- source_sha256=" + hashlib.sha256(data).hexdigest() + " -->\n"
    target = root / "豆包配置教程.html"
    target.write_text(page, encoding="utf-8")
    print(str(target))


if __name__ == "__main__":
    main()
