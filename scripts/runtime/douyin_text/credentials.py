"""Windows-user-bound DPAPI storage. Secret values never enter task records."""
from __future__ import annotations

import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path

from .common import ROOT
from .credential_dialog import ask


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def validate(values: dict) -> dict:
    token = values.get("api_key") or values.get("access_key") or ""
    if len(token) < 8:
        raise ValueError("语音凭据过短，请重新配置完整 API Key 或 Access Token；输入不回显")
    return values


def protect(data: bytes, *, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise RuntimeError("本机密钥存储需要 Windows；其他环境请使用 ASR 环境变量")
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    method = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    method.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    method.restype = wintypes.BOOL
    if not method(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError("Windows 密钥解密失败，请在当前 Windows 用户下重新配置" if decrypt
                           else "Windows 密钥加密失败")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


def load(root: Path = ROOT) -> dict:
    api_key = os.environ.get("DOUBAO_ASR_API_KEY", "").strip()
    app_id = os.environ.get("DOUBAO_ASR_APP_ID", "").strip()
    access_key = os.environ.get("DOUBAO_ASR_ACCESS_KEY", "").strip()
    if api_key:
        return validate({"api_key": api_key})
    if app_id and access_key:
        return validate({"app_id": app_id, "access_key": access_key})
    path = root / ".local" / "doubao.dpapi"
    if not path.exists():
        raise RuntimeError("尚未配置豆包语音识别凭据。请运行 brain.py configure，在本机窗口填写")
    values = json.loads(protect(path.read_bytes(), decrypt=True))
    if not values.get("api_key") and not (values.get("app_id") and values.get("access_key")):
        raise RuntimeError("豆包凭据字段不完整，请重新配置")
    return validate(values)


def configure(root: Path = ROOT, *, legacy: bool = False) -> None:
    values = ask(legacy=legacy, validate=validate)
    if values is None:
        print("已取消，凭据未更新。")
        return
    if not all(values.values()):
        raise ValueError("凭据为空，未保存")
    validate(values)
    path = root / ".local" / "doubao.dpapi"
    encrypted = protect(json.dumps(values).encode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encrypted)
    print("凭据已加密保存在本机，尚未验证语音服务权限。")
