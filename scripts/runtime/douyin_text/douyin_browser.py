"""Read Douyin page responses in a headless visitor or dedicated browser session.

This adapter is independently implemented. It does not contain the old vendored
downloader, generated signatures, CAPTCHA solving, or cookies from other browsers.
"""
from __future__ import annotations

import json
import re
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs
from urllib.request import Request, urlopen

from . import acquisition

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
_reusing = False
_shared_driver = None
_shared_browser = None


@contextmanager
def reuse_sessions():
    """One lazy browser per acquisition worker; every link gets a fresh context."""
    global _reusing, _shared_driver, _shared_browser
    _reusing = True
    try:
        yield
    finally:
        if _shared_browser is not None:
            _shared_browser.close()
        if _shared_driver is not None:
            _shared_driver.stop()
        _reusing, _shared_driver, _shared_browser = False, None, None


def _driver():
    global _shared_driver
    from playwright.sync_api import sync_playwright
    if not _reusing:
        return sync_playwright()
    if _shared_driver is None:
        _shared_driver = sync_playwright().start()
    return nullcontext(_shared_driver)


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
    # Prefer a complete, reasonably sized MP4 rendition. DASH entries may be
    # video-only; never mistake their missing voice track for transcription input.
    renditions = [entry.get('play_addr', {}) for entry in video.get('bit_rate', [])
                  if isinstance(entry, dict) and entry.get('format') == 'mp4']
    eligible = [entry for entry in renditions if isinstance(entry, dict)
                and min(entry.get('width', 0), entry.get('height', 0)) >= 540 and entry.get('url_list')]
    chosen = min(eligible, key=lambda entry: entry.get('data_size') or float('inf')) if eligible else None
    addresses = list(chosen.get('url_list', [])) if chosen else []
    for key in (() if chosen else ("play_addr", "play_addr_h264", "play_addr_265")):
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
    from .catalog import variants
    return {"id": "douyin-" + ident, "title": item.get("desc") or ident,
            "author": author.get("nickname") or "未知作者", "source": "https://www.douyin.com/video/" + ident,
            "media": media, "duration": float(duration) / 1000 if isinstance(duration, (int, float)) else None,
            "published": published, 'media_variant': {k: chosen.get(k) for k in ('width', 'height', 'data_size')} if chosen else None,
            'media_variants': variants(video)}


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
            raise RuntimeError("主页发现不完整：未收到作品列表的分页结束标志，尚不能判断是否需要登录；尚未调用语音识别。")
        if self.unresolved:
            raise RuntimeError("主页部分作品元数据缺失，无法保证所选范围；尚未调用语音识别。")
        if not self.items:
            raise ValueError("当前浏览器会话可见的主页作品中没有可处理的视频（图文不送入语音识别）")
        return list(self.items.values())


def _context(playwright, profile: Path, *, headless=True):
    profile.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(str(profile), headless=headless,
        viewport={"width": 1440, "height": 1000}, locale="zh-CN", user_agent=USER_AGENT)


@contextmanager
def _session(playwright, profile: Path | None):
    """Normal acquisition always stays headless; only explicit login opens a window."""
    global _shared_browser
    browser = None
    context = None
    try:
        if profile is not None:
            context = _context(playwright, profile, headless=True)
        else:
            if _reusing:
                if _shared_browser is None:
                    _shared_browser = playwright.chromium.launch(headless=True)
                browser = _shared_browser
            else:
                browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 1000},
                                          locale="zh-CN")
        yield context
    finally:
        if context is not None:
            context.close()
        if browser is not None and browser is not _shared_browser:
            browser.close()


def _visible_blocker(page) -> str | None:
    try:
        containers = page.locator('[role="dialog"], [aria-modal="true"], [id*="captcha"], '
                                  '[class*="captcha"], [data-e2e="video-error"]')
        for container in containers.all():
            if not container.is_visible():
                continue
            for line in container.inner_text(timeout=1000).splitlines():
                reason = acquisition.visible_blocker(line)
                if reason:
                    return reason
    except Exception:
        pass
    return None


def _browser_detail(page, ident: str) -> dict:
    """Let the site's loaded visitor SDK prepare its own ordinary XHR request.

    No generated signatures, imported cookies, account login or CAPTCHA solving.
    Return response facts separately; an empty/forbidden API is not a login wall.
    """
    if not ident.isdigit():
        raise ValueError('视频 ID 无效')
    return page.evaluate('''id => new Promise(resolve => {
        const xhr = new XMLHttpRequest();
        xhr.timeout = 15000;
        xhr.open('GET', '/aweme/v1/web/aweme/detail/?device_platform=webapp&aid=6383&channel=channel_pc_web&aweme_id=' + id);
        xhr.onload = () => {let data=null; try {data=JSON.parse(xhr.responseText)} catch (_) {}
            resolve({http_status:xhr.status, data:data, response_bytes:xhr.responseText.length});};
        xhr.onerror = () => resolve({http_status:0, error:'network_error'});
        xhr.ontimeout = () => resolve({http_status:0, error:'navigation_timeout'});
        xhr.send();
    })''', ident)


def _browser_profile_page(page, user_id: str, cursor=0, template=None) -> dict:
    """Use the public site's own visitor XHR, without generating request signatures."""
    return page.evaluate('''args => new Promise(resolve => {
        const endpoint = args.template ? new URL(args.template, location.href) : null;
        const params = endpoint ? endpoint.searchParams : new URLSearchParams({device_platform:'webapp', aid:'6383', channel:'channel_pc_web'});
        for (const key of ['a_bogus','X-Bogus','x-bogus']) params.delete(key);
        params.set('sec_user_id', args.id); params.set('max_cursor', String(args.cursor || 0)); params.set('count', '20');
        const xhr = new XMLHttpRequest(); xhr.timeout = 15000;
        xhr.open('GET', '/aweme/v1/web/aweme/post/?' + params.toString());
        xhr.onload = () => {let data=null; try {data=JSON.parse(xhr.responseText)} catch (_) {}
            resolve({http_status:xhr.status, data, response_bytes:xhr.responseText.length});};
        xhr.onerror = () => resolve({http_status:0, error:'network_error'});
        xhr.ontimeout = () => resolve({http_status:0, error:'request_timeout'});
        xhr.send();
    })''', {'id': user_id, 'cursor': cursor, 'template': template})


def _profile_hydration(page, user_id):
    """Read only this author's public post records from page-provided hydration."""
    return page.evaluate('''wanted => {
        const pending = [window._ROUTER_DATA, window.__NEXT_DATA__, window.SIGI_STATE];
        for (const id of ['RENDER_DATA','SIGI_STATE','__UNIVERSAL_DATA_FOR_REHYDRATION__']) {
            const script=document.getElementById(id); if (!script) continue;
            try { pending.push(JSON.parse(decodeURIComponent(script.textContent))) } catch (_) {}
        }
        const seen = new Set(), posts = new Map(); let count=0;
        while (pending.length && count++ < 100000) {
            const value=pending.pop(); if (!value || typeof value!=='object' || seen.has(value)) continue;
            seen.add(value);
            if (value.aweme_id && value.author && value.author.sec_uid===wanted)
                posts.set(String(value.aweme_id), value);
            for (const child of Object.values(value)) if (child && typeof child==='object') pending.push(child);
        }
        return Array.from(posts.values());
    }''', user_id)


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


def videos(urls: list[str], profile: Path | None) -> tuple[list[dict], list[dict]]:
    results, failures = [], []
    with _driver() as playwright:
        with _session(playwright, profile) as context:
            for url in urls:
                match = re.search(r"/(?:share/)?video/(\d+)", urlsplit(url).path)
                wanted = "douyin-" + match.group(1) if match else ""
                found = {}
                initialized = False
                page = context.new_page()

                def capture(response):
                    nonlocal initialized
                    if "/aweme/" not in response.url or response.status != 200:
                        return
                    if 'uifid' in parse_qs(urlsplit(response.url).query):
                        initialized = True
                    try:
                        for item in video_records(response.json()):
                            normalized = normalize(item)
                            if normalized:
                                found[normalized["id"]] = normalized
                    except Exception:
                        # Responses include non-JSON endpoints; they are not evidence of failure/success.
                        return

                page.on("requestfinished", lambda req: capture(req.response()))
                http_status = None
                detail_status = None
                try:
                    navigation = page.goto(url, wait_until="commit", timeout=20000)
                    http_status = navigation.status if navigation is not None else None
                    for _ in range(50):
                        if wanted in found or initialized:
                            break
                        page.wait_for_timeout(500)
                    for item in _hydrate(page):
                        record = normalize(item)
                        if record:
                            found[record["id"]] = record
                    record = found.get(wanted)
                    if not record:
                        detail = _browser_detail(page, wanted.removeprefix('douyin-'))
                        if isinstance(detail, dict):
                            detail_status = detail.get('http_status')
                            for item in video_records(detail.get('data')):
                                normalized = normalize(item)
                                if normalized and normalized['id'] == wanted:
                                    record = normalized
                                    break
                    if not record:
                        record = _yt_dlp_video(url, context.cookies(["https://www.douyin.com/"]))
                    if record["id"] != wanted:
                        raise ValueError("解析到的视频与输入不一致")
                    results.append(record)
                except Exception as exc:
                    reason = _visible_blocker(page)
                    if not reason:
                        reason = "navigation_timeout" if "Timeout" in type(exc).__name__ else (
                            "http_error" if (detail_status or http_status or 0) >= 400 else "metadata_unavailable")
                    failures.append(acquisition.clean_failure({"input_url": url, "stage": "metadata",
                        "reason": reason, "message": str(exc), "http_status": detail_status or http_status,
                        "navigation_error_type": type(exc).__name__}))
                finally:
                    page.close()
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
            if not feed.complete:
                blocker = _visible_blocker(page)
                if blocker:
                    raise acquisition.AcquisitionError([{"input_url": url, "reason": blocker}])
        finally:
            context.close()
            write_json(report, {"complete": feed.complete, "response_count": feed.responses,
                "video_count": len(feed.items), "non_video_count": len(feed.unsupported),
                "unresolved_count": len(feed.unresolved), "coverage": "visible_to_current_session"})
    return feed.finish()


def scan_profile(url: str, profile: Path | None, on_page, *, max_scrolls=600, max_seconds=600) -> dict:
    """Stream public post pages to durable storage; an unfinished scan retains its data.

    This is separate from the legacy all-or-error transcription discovery contract.
    No media, credentials or speech requests are processed here.
    """
    import time
    from playwright.sync_api import sync_playwright
    from urllib.parse import parse_qs
    state = {'complete': False, 'pages': 0, 'post_count': 0, 'reason': None,
             'coverage': 'visible_to_current_session'}
    seen, page_keys = set(), set()
    request_template = None
    user_id = urlsplit(url).path.rstrip('/').split('/')[-1]
    started = time.monotonic()
    try:
        with sync_playwright() as playwright:
            with _session(playwright, profile) as context:
                page = context.new_page()

                def capture(response):
                    nonlocal request_template
                    if '/aweme/post/' not in response.url or response.status != 200:
                        return
                    queried = parse_qs(urlsplit(response.url).query).get('sec_user_id', [None])[0]
                    if queried and queried != user_id:
                        return
                    request_template = response.url
                    try:
                        payload = response.json()
                    except Exception:
                        return
                    if not isinstance(payload, dict) or payload.get('status_code', 0) != 0:
                        return
                    posts = payload.get('aweme_list')
                    if not isinstance(posts, list):
                        return
                    from .catalog import fingerprint
                    page_key = fingerprint({'ids': [p.get('aweme_id') for p in posts if isinstance(p, dict)],
                        'cursor': payload.get('max_cursor', payload.get('cursor')), 'has_more': payload.get('has_more')})
                    if page_key in page_keys:
                        return
                    page_keys.add(page_key)
                    for post in posts:
                        if isinstance(post, dict) and post.get('aweme_id'):
                            seen.add(str(post['aweme_id']))
                    state.update(pages=state['pages'] + 1, post_count=len(seen),
                                 cursor=payload.get('max_cursor', payload.get('cursor')))
                    if seen and 'has_more' in payload and payload['has_more'] in (0, False):
                        state['complete'] = True
                    # Only public business records and pagination fields are retained.
                    on_page({'aweme_list': posts, 'has_more': payload.get('has_more'),
                             'cursor': state.get('cursor'), 'status_code': payload.get('status_code', 0)}, dict(state))

                page.on('response', capture)
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                idle, previous, api_failures = 0, -1, 0
                for _ in range(max_scrolls):
                    page.wait_for_timeout(600)
                    if state['complete']:
                        break
                    current = len(seen)
                    idle = idle + 1 if current == previous else 0
                    previous = current
                    if idle == 8 and api_failures < 2:
                        hydrated = _profile_hydration(page, user_id)
                        if hydrated:
                            for post in hydrated:
                                seen.add(str(post['aweme_id']))
                            state.update(post_count=len(seen), hydration_count=len(hydrated))
                            on_page({'aweme_list': hydrated, 'has_more': None, 'cursor': None,
                                     'source': 'public_page_hydration'}, dict(state))
                        response = _browser_profile_page(page, user_id, state.get('cursor', 0), request_template)
                        data = response.get('data') or {}
                        facts = {k: v for k, v in response.items() if k != 'data'}
                        facts.update(payload_keys=list(data) if isinstance(data, dict) else [],
                                     status_code=data.get('status_code'), status_msg=data.get('status_msg'),
                                     has_more=data.get('has_more'), aweme_list_type=type(data.get('aweme_list')).__name__)
                        state.setdefault('visitor_requests', []).append(facts)
                        if not isinstance(data.get('aweme_list'), list) or not data.get('aweme_list'):
                            api_failures += 1
                    if idle >= 25 or time.monotonic() - started >= max_seconds:
                        state['reason'] = _visible_blocker(page) or ('discovery_timeout' if time.monotonic() - started >= max_seconds else 'pagination_stalled')
                        break
                    page.mouse.move(1100, 750)
                    page.mouse.wheel(0, 1800)
                    if idle > 2:
                        page.evaluate('''() => {
                            const candidates=Array.from(document.querySelectorAll('*')).filter(e => {
                                const r=e.getBoundingClientRect(), s=getComputedStyle(e);
                                return r.width>400 && r.height>250 && r.bottom>0 && r.top<innerHeight &&
                                    /(auto|scroll)/.test(s.overflowY) && e.scrollHeight>e.clientHeight+100;
                            });
                            candidates.sort((a,b)=>b.clientWidth*b.clientHeight-a.clientWidth*a.clientHeight);
                            const container=candidates[0] || document.scrollingElement;
                            if(container) container.scrollTop=Math.min(container.scrollHeight, container.scrollTop+container.clientHeight);
                        }''')
                if not state['complete'] and not state['reason']:
                    state['reason'] = _visible_blocker(page) or 'pagination_limit'
                state['page_title'] = page.title()
                state['final_path'] = urlsplit(page.url).path
    except Exception as exc:
        state['complete'] = False
        state['reason'] = getattr(exc, 'code', 'discovery_error')
        state['error'] = str(exc)
    state['elapsed_seconds'] = round(time.monotonic() - started, 3)
    return state


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
