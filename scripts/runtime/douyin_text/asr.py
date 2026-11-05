from __future__ import annotations

import base64
import hashlib
import json
import socket
import uuid
from pathlib import Path
from urllib import error, request

from .common import write_json

ENDPOINT = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
RESOURCE = "volc.bigasr.auc_turbo"
PARAMETERS = {"model_name": "bigmodel", "enable_ddc": False, "enable_punc": True,
              "enable_itn": False, "show_utterances": True}
PROFILE = hashlib.sha256(json.dumps({"resource": RESOURCE, **PARAMETERS},
                                    sort_keys=True).encode()).hexdigest()[:12]


class ASRError(RuntimeError):
    pass


class OutcomeUnknown(ASRError):
    pass


def recognize(audio: Path, credentials: dict, response_path: Path, *, timeout: int = 300,
              request_id: str | None = None) -> dict:
    if audio.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("音频超过豆包单次大小限制，请先分片")
    headers = {"Content-Type": "application/json", "X-Api-Resource-Id": RESOURCE,
               "X-Api-Request-Id": request_id or str(uuid.uuid4()), "X-Api-Sequence": "-1"}
    if credentials.get("api_key"):
        headers["X-Api-Key"] = credentials["api_key"]
    else:
        headers["X-Api-App-Key"] = credentials["app_id"]
        headers["X-Api-Access-Key"] = credentials["access_key"]
    payload = {"user": {"uid": "douyin-transcript-local"},
               "audio": {"data": base64.b64encode(audio.read_bytes()).decode("ascii")},
               "request": PARAMETERS}
    req = request.Request(ENDPOINT, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            code = str(response.headers.get("X-Api-Status-Code", ""))
            log_id = response.headers.get("X-Tt-Logid", "")
            body = response.read()
    except error.HTTPError as exc:
        detail = " ".join(value for value in (
            str(exc.headers.get("X-Api-Status-Code", "")),
            str(exc.headers.get("X-Api-Message", "")),
            exc.read().decode("utf-8", errors="replace")[:2000]) if value)
        for value in credentials.values():
            if value:
                detail = detail.replace(value, "[redacted]")
        write_json(response_path, {"http_status": exc.code,
                                  "request_id": headers["X-Api-Request-Id"],
                                  "log_id": exc.headers.get("X-Tt-Logid", ""),
                                  "error_detail": detail})
        raise ASRError(f"豆包 HTTP {exc.code}：{detail or '请检查服务权限、额度和凭据'}") from None
    except (error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError):
        raise OutcomeUnknown("豆包请求连接中断或超时，结果未知；不会自动重提。请核对后明确要求重试") from None
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        raise OutcomeUnknown("豆包响应无法解析，结果未知；保留请求 ID 供核对") from None
    write_json(response_path, {"request_id": headers["X-Api-Request-Id"],
                              "service_status": code, "log_id": log_id, "response": data})
    if code != "20000000":
        raise ASRError(f"豆包识别失败，服务状态码：{code or '缺失'}，Log ID：{log_id}")
    result = data.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("text"), str):
        raise ASRError("豆包响应缺少完整识别文本")
    utterances = result.get("utterances", [])
    if not isinstance(utterances, list):
        raise ASRError("豆包分句格式无效")
    segments = []
    for item in utterances:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            raise ASRError("豆包分句格式无效")
        start, end = item.get("start_time"), item.get("end_time")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end < start:
            raise ASRError("豆包分句时间无效")
        segments.append({"start": start / 1000, "end": end / 1000, "text": item["text"]})
    return {"text": result["text"], "segments": segments, "request_id": headers["X-Api-Request-Id"]}
