from __future__ import annotations

import tkinter as tk
import webbrowser
import re
from pathlib import Path
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText


def open_guide() -> bool:
    # Keep the guide usable when Windows has no working default HTML association.
    guide = Path(__file__).resolve().parents[3] / "references" / "doubao-setup.md"
    window = tk.Toplevel()
    window.title("抖音脑 · 豆包语音配置教程")
    window.geometry("900x700")
    window.minsize(640, 400)
    ttk.Label(window, text="按当前进度完成配置；网址可点击，也可选中复制。",
              padding=12).pack(anchor="w")
    body = ScrolledText(window, wrap="word", padx=20, pady=16,
                        font=("Microsoft YaHei UI", 11), relief="flat")
    body.pack(fill="both", expand=True)
    body.tag_configure("heading", font=("Microsoft YaHei UI", 14, "bold"), spacing1=12, spacing3=8)
    text = guide.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)",
                      lambda m: (m[2] if m[1] == m[2] else m[1] + "：" + m[2]) + " ", line)
        line = line.replace("**", "").replace("`", "")
        if line.startswith("- "):
            line = "• " + line[2:]
        start = body.index("end-1c")
        body.insert("end", line.lstrip("# ") if line.startswith("#") else line)
        if line.startswith("#"):
            body.tag_add("heading", start, "end-1c")
        body.insert("end", "\n")
    for number, match in enumerate(re.finditer(r"https?://[A-Za-z0-9:/?%&=._~+#@!$*;,-]+", body.get("1.0", "end-1c"))):
        tag, url = "link" + str(number), match.group().rstrip(".,;")
        body.tag_add(tag, f"1.0+{match.start()}c", f"1.0+{match.start() + len(url)}c")
        body.tag_configure(tag, foreground="#176ca4", underline=True)
        body.tag_bind(tag, "<Button-1>", lambda event, address=url: webbrowser.open(address))
    body.configure(state="disabled")
    ttk.Button(window, text="关闭教程", command=window.destroy).pack(pady=10)
    window.lift()
    return True


def ask(*, legacy: bool, validate) -> dict | None:
    window = tk.Tk()
    window.title("抖音脑 Douyin-brain · 配置豆包语音")
    window.resizable(False, False)
    window.option_add("*Font", "{Microsoft YaHei UI} 10")
    frame = ttk.Frame(window, padding=20)
    frame.grid(sticky="nsew")
    ttk.Label(frame, text="填写豆包语音服务凭据", font=("Microsoft YaHei UI", 13, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
    ttk.Label(frame, text="请使用豆包语音控制台的凭据。火山方舟聊天 Key 属于另一服务。",
              wraplength=600).grid(row=1, column=0, columnspan=3, sticky="w")
    links = ttk.Frame(frame)
    links.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 14))
    ttk.Button(links, text="手把手教程", command=open_guide).pack(side="left", padx=(0, 10))
    ttk.Button(links, text="打开语音 Key 管理", command=lambda: webbrowser.open(
        "https://console.volcengine.com/speech/new/setting/apikeys")).pack(side="left")
    values = {}
    row = 3
    if legacy:
        ttk.Label(frame, text="APP ID").grid(row=row, column=0, sticky="w", padx=(0, 12))
        app_id = tk.StringVar(window)
        ttk.Entry(frame, textvariable=app_id, width=48).grid(row=row, column=1, sticky="ew", pady=6)
        values["app_id"] = app_id
        row += 1
    token = tk.StringVar(window)
    token_field = "access_key" if legacy else "api_key"
    values[token_field] = token
    ttk.Label(frame, text="Access Token" if legacy else "API Key").grid(row=row, column=0, sticky="w", padx=(0, 12))
    entry = ttk.Entry(frame, textvariable=token, show="●", width=48)
    entry.grid(row=row, column=1, sticky="ew", pady=6)
    hint = tk.StringVar(window, value="支持 Ctrl+V、右键粘贴，或点击“粘贴”按钮。")
    length = tk.StringVar(window, value="已输入 0 个字符")
    token.trace_add("write", lambda *_: length.set(f"已输入 {len(token.get().strip())} 个字符"))

    def paste():
        try:
            text = window.clipboard_get().strip()
        except tk.TclError:
            hint.set("剪贴板里没有文字，请先从语音控制台复制完整凭据。")
            return
        token.set(text)
        entry.focus_set()
        hint.set("已粘贴。请核对字符数，再点击保存。")

    ttk.Button(frame, text="粘贴", command=paste).grid(row=row, column=2, padx=(10, 0))
    menu = tk.Menu(window, tearoff=False)
    menu.add_command(label="粘贴", command=paste)
    entry.bind("<Button-3>", lambda event: menu.tk_popup(event.x_root, event.y_root))
    ttk.Label(frame, textvariable=length).grid(row=row + 1, column=1, sticky="w")
    ttk.Label(frame, textvariable=hint, wraplength=600).grid(row=row + 2, column=0,
              columnspan=3, sticky="w", pady=(8, 10))
    ttk.Label(frame, text="凭据在本机加密保存，配置窗口不会调用语音接口。", wraplength=600).grid(
        row=row + 3, column=0, columnspan=3, sticky="w", pady=(0, 12))
    result = None

    def save():
        nonlocal result
        candidate = {name: variable.get().strip() for name, variable in values.items()}
        try:
            if not all(candidate.values()):
                raise ValueError("请填写完整凭据。")
            validate(candidate)
        except ValueError as exc:
            hint.set(str(exc))
            return
        result = candidate
        window.destroy()

    buttons = ttk.Frame(frame)
    buttons.grid(row=row + 4, column=0, columnspan=3, sticky="e")
    ttk.Button(buttons, text="取消", command=window.destroy).pack(side="left", padx=8)
    ttk.Button(buttons, text="保存", command=save).pack(side="left")
    window.bind("<Escape>", lambda _: window.destroy())
    window.bind("<Return>", lambda _: save())
    window.update_idletasks()
    window.geometry(f"+{max(0, (window.winfo_screenwidth() - window.winfo_width()) // 2)}"
                    f"+{max(0, (window.winfo_screenheight() - window.winfo_height()) // 2)}")
    window.lift()
    entry.focus_force()
    window.mainloop()
    return result
