"""Anonymous public-page acquisition and factual, credential-free diagnostics."""
from __future__ import annotations

import json
import re
from urllib import error, request
from urllib.parse import unquote, urlsplit, urlunsplit


class AcquisitionError(RuntimeError):
    def __init__(self, failures: list[dict]):
        self.failures = failures
        reasons = {item.get("reason", "metadata_unavailable") for item in failures}
        self.code = next((code for code in (
            "verification_required", "login_required", "media_unavailable", "navigation_timeout",
            "http_error", "browser_error") if code in reasons), "metadata_unavailable")
        messages = {
            "verification_required": "页面明确要求完成验证，需由用户决定是否打开专用浏览器处理",
            "login_required": "页面明确要求登录后访问，需由用户决定是否打开专用浏览器登录",
            "media_unavailable": "页面提示作品不存在、已删除或不可用",
            "navigation_timeout": "页面访问超时，尚不能判断是否需要登录",
            "http_error": "素材页面返回 HTTP 错误，请查看获取报告中的状态码",
            "browser_error": "后台浏览器获取失败，请查看获取报告中的具体错误",
            "metadata_unavailable": "未取得可播放的作品数据，尚不能判断是否需要登录",
        }
        super().__init__(messages[self.code] + "；尚未调用该素材的语音识别")


def clean_url(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def clean_failure(item: dict, **context) -> dict:
    result = {**context, "stage": item.get("stage", "metadata"),
              "reason": item.get("reason", "metadata_unavailable")}
    if item.get("input_url"):
        result["input_url"] = clean_url(item["input_url"])
    if item.get("message"):
        result["message"] = re.sub(r"https?://[^\s\"<>]+", lambda m: clean_url(m[0]),
                                    str(item["message"]))[:1000]
    for key in ("http_status", "navigation_error_type"):
        if item.get(key) is not None:
            result[key] = item[key]
    return result


def video_id(url: str) -> str:
    match = re.search(r"/(?:share/)?video/(\d+)(?:/|$)", urlsplit(url).path)
    if not match:
        raise ValueError("链接不是单条抖音视频")
    return match.group(1)


def visible_blocker(text: str) -> str | None:
    # A generic login button or an empty response is not evidence of a login wall.
    if re.search(r"请完成.{0,12}验证|拖动滑块|安全验证|验证码|验证后继续", text):
        return "verification_required"
    if re.search(r"登录后才能观看|登录后观看|请登录后继续|登录后查看完整|登录后查看作品", text):
        return "login_required"
    if re.search(r"视频不存在|作品不存在|视频已删除|作品已删除|暂时无法播放|无权观看|仅作者可见", text):
        return "media_unavailable"
    return None


def parse_public_detail(body: str, wanted: str) -> dict | None:
    """Decode embedded JSON, never execute scripts or select a recommended video."""
    from .douyin_browser import video_records

    documents = []
    for match in re.finditer(r"window\._ROUTER_DATA\s*=\s*", body):
        try:
            document, _ = json.JSONDecoder().raw_decode(body[match.end():].lstrip())
            documents.append(document)
        except (ValueError, TypeError):
            continue
    for match in re.finditer(r'<script\b[^>]*\bid=["\']RENDER_DATA["\'][^>]*>(.*?)</script>', body, re.S):
        try:
            documents.append(json.loads(unquote(match[1].strip())))
        except ValueError:
            continue
    for document in documents:
        for value in video_records(document):
            if str(value.get("aweme_id", "")) == wanted:
                return value
    return None


def fetch_share_page(ident: str) -> str:
    req = request.Request(f"https://www.iesdouyin.com/share/video/{ident}/", headers={
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/125.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html", "Accept-Language": "zh-CN,zh;q=0.9",
    })
    # No Cookie header, cookie import, account credential or paid service.
    with request.urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8", "replace")


def public_metadata(urls: list[str]) -> tuple[list[dict], list[dict]]:
    from .douyin_browser import normalize

    jobs, failures = [], []
    for url in urls:
        try:
            wanted = video_id(url)
            detail = parse_public_detail(fetch_share_page(wanted), wanted)
            job = normalize(detail) if detail else None
            if job is None:
                failures.append({"input_url": url, "reason": "metadata_unavailable",
                                 "message": "公开分享页没有包含该作品的可播放数据"})
            else:
                jobs.append(job)
        except error.HTTPError as exc:
            failures.append({"input_url": url, "reason": "http_error", "http_status": exc.code,
                             "message": f"公开分享页返回 HTTP {exc.code}"})
        except (TimeoutError, error.URLError) as exc:
            failures.append({"input_url": url, "reason": "navigation_timeout" if isinstance(
                getattr(exc, "reason", exc), TimeoutError) else "http_error", "message": str(exc)})
        except (ValueError, RuntimeError) as exc:
            failures.append({"input_url": url, "reason": "metadata_unavailable", "message": str(exc)})
    return jobs, failures
