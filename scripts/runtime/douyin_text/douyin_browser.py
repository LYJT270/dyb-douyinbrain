"""Read public Douyin page responses using the user's dedicated browser session.

This adapter is independently implemented. It does not contain the old vendored
downloader, generated signatures, CAPTCHA solving, or cookies from other browsers.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def resolve_url(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    if not any(host == d or host.endswith("." + d) for d in ("douyin.com", "iesdouyin.com")):
        raise ValueError("链接不是抖音地址")
    if host == "v.douyin.com" or "/share/" in urlsplit(url).path:
        with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=30) as response:
            resolved = response.geturl()
        end_host = (urlsplit(resolved).hostname or "").lower()
        if not any(end_host == d or end_host.endswith("." + d) for d in ("douyin.com", "iesdouyin.com")):
            raise ValueError("抖音短链跳转到不支持的站点")
        return resolved
    return url


def normalize(item: dict) -> dict | None:
    """Normalize actual video metadata. Missing time remains unknown, never invented."""
    ident = str(item.get("aweme_id") or "")
    video = item.get("video") or {}
    if not ident.isdigit() or not isinstance(video, dict) or item.get("images"):
        return None
    addresses = []
    for key in ("play_addr", "play_addr_h264", "play_addr_265"):
        address = video.get(key) or {}
        if isinstance(address, dict):
            addresses.extend(address.get("url_list") or [])
    media = next((u for u in addresses if isinstance(u, str) and u.startswith("https://")), None)
    if not media:
        media = next((u for u in addresses if isinstance(u, str) and u.startswith("http://")), None)
    if not media:
        return None
    author = item.get("author") or {}
    published = None
    timestamp = item.get("create_time")
    if isinstance(timestamp, (int, float)) and timestamp > 0:
        try:
            published = datetime.fromtimestamp(timestamp, timezone(timedelta(hours=8))).isoformat(timespec="seconds")
        except (OverflowError, OSError, ValueError):
            pass
    duration = video.get("duration", item.get("duration"))
    return {"id": "douyin-" + ident, "title": item.get("desc") or ident,
            "author": author.get("nickname") or "未知作者", "source": "https://www.douyin.com/video/" + ident,
            "media": media, "duration": float(duration) / 1000 if isinstance(duration, (int, float)) else None,
            "published": published}


def video_records(value):
    """Read hydration JSON without executing scripts or accepting instructions in it."""
    pending = [value]
    visited = 0
    while pending and visited < 100000:
        item = pending.pop()
        visited += 1
        if isinstance(item, dict):
            if "aweme_id" in item and "video" in item:
                yield item
            pending.extend(v for v in item.values() if isinstance(v, (dict, list)))
        elif isinstance(item, list):
            pending.extend(v for v in item if isinstance(v, (dict, list)))


class ProfileFeed:
    def __init__(self):
        self.items: dict[str, dict] = {}
        self.complete = False
        self.responses = 0
        self.unsupported: set[str] = set()
        self.unresolved: set[str] = set()

    def accept(self, payload: dict) -> None:
        if not isinstance(payload, dict) or payload.get("status_code", 0) != 0:
            return
        values = payload.get("aweme_list")
        if not isinstance(values, list):
            return
        self.responses += 1
        for value in values:
            if not isinstance(value, dict):
                continue
            ident = str(value.get("aweme_id") or "unknown")
            record = normalize(value)
            if record:
                self.items[record["id"]] = record
            elif value.get("images") or value.get("aweme_type") in (68, 150):
                self.unsupported.add(ident)
            else:
                self.unresolved.add(ident)
        # Absence of has_more, a login wall, or an empty page is NOT completion.
        if "has_more" in payload and payload["has_more"] in (0, False):
            self.complete = True

    def finish(self) -> list[dict]:
        if not self.complete or not self.responses:
            raise RuntimeError("主页发现不完整：未收到作品列表的分页结束标志。请检查专用浏览器登录／验证状态；尚未调用语音识别。")
        if self.unresolved:
            raise RuntimeError("主页部分作品元数据缺失，无法保证所选范围；尚未调用语音识别。")
        if not self.items:
            raise ValueError("当前登录会话可见的主页作品中没有可处理的视频（图文不送入语音识别）")
        return list(self.items.values())


def _context(playwright, profile: Path, *, headless=True):
    profile.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(str(profile), headless=headless,
        viewport={"width": 1440, "height": 1000}, locale="zh-CN", user_agent=USER_AGENT)


def _hydrate(page) -> list[dict]:
    records = []
    for ident in ("RENDER_DATA", "SIGI_STATE", "__UNIVERSAL_DATA_FOR_REHYDRATION__"):
        element = page.locator("script#" + ident)
        if element.count():
            try:
                raw = element.first.text_content(timeout=3000) or ""
                records.extend(video_records(json.loads(unquote(raw))))
            except (ValueError, TypeError):
                pass
    return records


def _yt_dlp_video(url: str, cookies: list[dict] | None = None) -> dict:
    """Single-video fallback through the separately installed, licensed dependency."""
    import yt_dlp

    class Quiet:
        def debug(self, message): pass
        def warning(self, message): pass
        def error(self, message): pass

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True,
                          "noplaylist": True, "logger": Quiet(), "socket_timeout": 25}) as reader:
        from http.cookiejar import Cookie
        for cookie in cookies or []:
            domain = cookie.get("domain", "")
            if domain.lstrip(".") not in ("douyin.com", "www.douyin.com"):
                continue
            expires = cookie.get("expires", -1)
            reader.cookiejar.set_cookie(Cookie(0, cookie["name"], cookie["value"], None, False,
                domain, True, domain.startswith("."), cookie.get("path", "/"), True,
                cookie.get("secure", False), int(expires) if expires > 0 else None,
                expires <= 0, None, None, {}, False))
        value = reader.extract_info(url, download=False)
    if not value or value.get("_type") == "playlist":
        raise ValueError("没有取得单条视频元数据")
    media = value.get("url")
    if not media:
        formats = [f for f in value.get("formats", []) if f.get("url") and f.get("acodec") != "none"]
        media = formats[-1]["url"] if formats else None
    if not media or not str(value.get("id", "")).isdigit():
        raise ValueError("视频地址缺失")
    timestamp = value.get("timestamp")
    published = datetime.fromtimestamp(timestamp, timezone(timedelta(hours=8))).isoformat(timespec="seconds") if timestamp else None
    return {"id": "douyin-" + value["id"], "title": value.get("title") or value["id"],
            "author": value.get("uploader") or "未知作者", "source": "https://www.douyin.com/video/" + value["id"],
            "media": media, "duration": value.get("duration"), "published": published}


def videos(urls: list[str], profile: Path) -> tuple[list[dict], list[dict]]:
    from playwright.sync_api import sync_playwright
    results, failures = [], []
    with sync_playwright() as playwright:
        context = _context(playwright, profile)
        try:
            for url in urls:
                match = re.search(r"/(?:share/)?video/(\d+)", urlsplit(url).path)
                wanted = "douyin-" + match.group(1) if match else ""
                found = {}
                page = context.new_page()

                def capture(response):
                    if "/aweme/" not in response.url or response.status != 200:
                        return
                    try:
                        for item in video_records(response.json()):
                            normalized = normalize(item)
                            if normalized:
                                found[normalized["id"]] = normalized
                    except Exception:
                        # Responses include non-JSON endpoints; they are not evidence of failure/success.
                        return

                page.on("response", capture)
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    for _ in range(20):
                        if wanted in found:
                            break
                        page.wait_for_timeout(500)
                    for item in _hydrate(page):
                        record = normalize(item)
                        if record:
                            found[record["id"]] = record
                    record = found.get(wanted)
                    if not record:
                        record = _yt_dlp_video(url, context.cookies(["https://www.douyin.com/"]))
                    if record["id"] != wanted:
                        raise ValueError("解析到的视频与输入不一致")
                    results.append(record)
                except Exception:
                    failures.append({"input_url": url, "stage": "metadata",
                                     "reason": "请完成专用抖音浏览器的登录或验证后重试；也可提供本地视频。"})
                finally:
                    page.close()
        finally:
            context.close()
    return results, failures


def profile_videos(url: str, profile: Path, report: Path, *, max_scrolls=240) -> list[dict]:
    from playwright.sync_api import sync_playwright
    from .common import write_json

    feed = ProfileFeed()
    user_id = urlsplit(url).path.rstrip("/").split("/")[-1]
    with sync_playwright() as playwright:
        context = _context(playwright, profile)
        page = context.new_page()

        def capture(response):
            if "/aweme/post/" not in response.url or response.status != 200:
                return
            from urllib.parse import parse_qs
            queried = parse_qs(urlsplit(response.url).query).get("sec_user_id", [None])[0]
            if queried and queried != user_id:
                return
            try:
                feed.accept(response.json())
            except Exception:
                return

        page.on("response", capture)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            idle, previous = 0, -1
            for _ in range(max_scrolls):
                page.wait_for_timeout(1000)
                if feed.complete:
                    break
                current = len(feed.items) + len(feed.unsupported) + len(feed.unresolved)
                idle = idle + 1 if current == previous else 0
                previous = current
                if idle >= 15:
                    break
                page.mouse.move(1100, 750)
                page.mouse.wheel(0, 1800)
        finally:
            context.close()
            write_json(report, {"complete": feed.complete, "response_count": feed.responses,
                "video_count": len(feed.items), "non_video_count": len(feed.unsupported),
                "unresolved_count": len(feed.unresolved), "coverage": "visible_to_current_session"})
    return feed.finish()


def login(profile: Path) -> int:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        context = _context(playwright, profile, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        print("请在专用浏览器完成抖音登录／验证。完成后关闭这个浏览器窗口，登录状态会保留在本机。", flush=True)
        try:
            while context.pages:
                page.wait_for_timeout(1000)
        except Exception:
            pass
        finally:
            try:
                context.close()
            except Exception:
                pass
    return 0
