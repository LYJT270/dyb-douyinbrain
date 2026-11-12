from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

from . import asr, credentials, media, vault, workflow, content, setup, review
from . import creator_cli, onboarding, work, continuation
from .common import ROOT, RESOURCE_ROOT, SKILL_ROOT, config


def doctor() -> dict:
    checks = {name: bool(shutil.which(name)) for name in ("ffmpeg", "ffprobe")}
    checks["playwright"] = importlib.util.find_spec("playwright") is not None
    checks["yt_dlp"] = importlib.util.find_spec("yt_dlp") is not None
    checks["chromium"] = bool(list((ROOT / ".local/browsers").glob("chromium-*/chrome-win*/chrome.exe")))
    present = bool(os.environ.get("DOUBAO_ASR_API_KEY") or
                   (os.environ.get("DOUBAO_ASR_APP_ID") and os.environ.get("DOUBAO_ASR_ACCESS_KEY")) or
                   (ROOT / ".local/doubao.dpapi").is_file())
    cfg = config()
    assistant = Path(cfg["assistant_root"]) if cfg.get("assistant_root") else None
    return {"status": "environment_ready" if all(checks.values()) else "environment_incomplete",
            "workspace": str(ROOT), "resource_root": str(RESOURCE_ROOT), "checks": checks,
            "doubao_credentials_present": present, "doubao_api_status": "not_checked_by_doctor",
            "login_status": "not_checked_by_doctor", "vault_root": cfg.get("vault_root"),
            "native_vault_entry_present": bool(assistant and (assistant / "scripts/vault.py").is_file()),
            "entrypoint": str(SKILL_ROOT / "scripts/invoke.ps1"), "runtime_python": sys.executable,
            "execution_route": {"mode": "bundled_local_engine", "asr_provider": "doubao_voice_api",
                                "asr_endpoint": asr.ENDPOINT, "asr_module": str(Path(asr.__file__).resolve()),
                                "browser_role": "douyin_login_and_media_acquisition_only",
                                "acquisition": "anonymous_public_page_then_browser_then_existing_profile",
                                "acquisition_headless": True, "computer_use_required": False,
                                "review_capabilities": "reported_from_current_agent_tools_not_agent_name",
                                "web_transcription_fallback": False},
            "onboarding": onboarding.status(ROOT),
            "next": "凭据与登录需要时在本机配置；真实识别状态须看任务回执"}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="dyb-douyinbrain：需求路由、原文留底、校对与口播、知识归档")
    sub = root.add_subparsers(dest="command", required=True)
    creator_cli.add_parser(sub)
    work.add_parser(sub)
    continuation.add_parser(sub)
    sub.add_parser("doctor")
    welcome = sub.add_parser('welcome', help='显示功能与首次使用引导，不调用语音识别')
    welcome.add_argument('--lang', choices=('zh', 'en'), default='zh')
    welcome.add_argument('--acknowledge', action='store_true', help='仅在 Agent 已在聊天展示介绍后记录；不代表用户已理解')
    configure = sub.add_parser("configure", help="在本机安全填写豆包语音凭据")
    configure.add_argument("--legacy", action="store_true", help="旧控制台 APP ID + Access Token")
    sub.add_parser("login", help="打开项目专用抖音登录浏览器")
    inspect = sub.add_parser("inspect-source", help="只检查单条视频链接或本地素材获取，不调用语音识别")
    inspect.add_argument("inputs", nargs="+")
    inspect.add_argument("--anonymous-only", action="store_true", help="不使用已保存的账号或浏览器状态")
    inspect.add_argument('--download-audio', action='store_true', help='下载素材并验证新音轨；仍不调用语音识别')
    evidence = sub.add_parser("prepare-review", help="按当前 Agent 的实际能力准备画面／音轨，准备不等于已校对")
    evidence.add_argument("task")
    evidence.add_argument("--images", action="store_true", help="当前 Agent 有可用的图片查看及理解工具")
    evidence.add_argument("--audio", action="store_true", help="当前 Agent 有可用的音频输入／听音工具")
    evidence.add_argument("--item", type=int, help="任务成功结果中的序号，从 1 开始")
    evidence.add_argument("--start", type=float, default=0, help="原视频时间，单位秒")
    evidence.add_argument("--end", type=float, help="原视频结束时间，单位秒；帧图包含恰好位于结束点的帧")
    evidence.add_argument("--every-frame", action="store_true", help="提取指定范围全部视频帧，仍须 Agent 实际逐帧查看")
    evidence.add_argument("--max-frames", type=int, default=120)
    evidence.add_argument('--cached-only', action='store_true', help='只使用已有音画缓存；缺失时报告，不联网补取')
    plan = sub.add_parser("plan", help="创建待确认任务，不下载、不调用识别")
    plan.add_argument("inputs", nargs="+")
    confirm = sub.add_parser("confirm", help="记录用户本次明确选择")
    confirm.add_argument("task")
    confirm.add_argument("--purpose", choices=workflow.PURPOSES, required=True)
    confirm.add_argument("--evidence", required=True, help="用户确认用途的实际原话")
    scope = confirm.add_mutually_exclusive_group()
    scope.add_argument("--latest", type=int)
    scope.add_argument("--all", action="store_true")
    scope.add_argument("--start", help="日期范围起点 YYYY-MM-DD")
    confirm.add_argument("--end", help="日期范围终点 YYYY-MM-DD")
    confirm.add_argument("--instruction", default="")
    confirm.add_argument("--category", choices=["reference", "benchmark", "own"], default="reference")
    confirm.add_argument("--retranscribe", action="store_true", help="用户明确要求重新识别，另存新版本")
    run = sub.add_parser("run")
    run.add_argument("task")
    run.add_argument("--retry-evidence", default="", help="用户明确重试失败/未知请求的原话")
    run.add_argument('--anonymous-only', action='store_true', help='获取素材时不使用已保存的账号或浏览器状态')
    run.add_argument('--saved-scope', action='store_true', help='只处理 jobs.json 已保存的作品，不重新发现输入或主页')
    offline = sub.add_parser('reanalyze', help='基于普通任务的已有文稿建立独立离线分析')
    offline.add_argument('task')
    offline.add_argument('--instruction', required=True)
    for name in ("show", "preview", "export-srt"):
        sub.add_parser(name).add_argument("task")
    finish = sub.add_parser("finish-analysis")
    finish.add_argument("task")
    finish.add_argument("--file", type=Path, required=True)
    publish = sub.add_parser("publish")
    publish.add_argument("task")
    publish.add_argument("--page", action="append", type=Path, default=[])
    publish.add_argument("--target", action="append", default=[])
    publish.add_argument("--expected-sha256", action="append", default=[],
                         help="每页对应一个值；新增页填 -，更新页填读取原页时的 SHA-256")
    init = sub.add_parser("init", help="配置工作目录及已有或新建的知识库")
    init.add_argument("--vault", type=Path)
    init.add_argument("--create-vault", action="store_true")
    init.add_argument("--assistant", type=Path)
    init.add_argument("--register", action="store_true")
    sub.add_parser("plan-text", help="将一条或多条已有文稿原样快照，不调用 ASR").add_argument("file", type=Path, nargs="+")
    for command in ("register-review", "register-spoken"):
        edit = sub.add_parser(command, help="登记 Agent 已实际完成的独立正文")
        edit.add_argument("task")
        edit.add_argument("--file", action="append", type=Path, required=True)
        edit.add_argument("--evidence", default="")
        edit.add_argument('--item', action='append', help='按此顺序仅登记这些成功素材，保留其他条目的有效成果')
    deliver = sub.add_parser("deliver", help="按原顺序合并正文，每条一段")
    deliver.add_argument("task")
    deliver.add_argument("--kind", choices=["review", "spoken", "raw"], default="review")
    archive = sub.add_parser("archive", help="准备或登记互相链接的原文和校对稿")
    archive.add_argument("task")
    archive.add_argument("--target-prefix", default="")
    archive.add_argument("--raw-file", type=Path)
    archive.add_argument("--reviewed-file", type=Path)
    archive.add_argument("--include-spoken", action="store_true")
    archive.add_argument("--spoken-file", type=Path)
    archive.add_argument("--evidence", default="")
    record = sub.add_parser("record-publication", help="按目标库规则写入后，读回核对实际文件")
    record.add_argument("task")
    record.add_argument("--receipt", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == 'resume':
            result = continuation.resume(task_id=args.task, inputs=args.input, purpose=args.purpose,
                                         instruction=args.instruction, request=args.request)
        elif args.command == 'work':
            result = work.dispatch(args)
        elif args.command == 'creator':
            result = creator_cli.dispatch(args)
        elif args.command == "doctor":
            result = doctor()
        elif args.command == 'welcome':
            result = onboarding.acknowledge(language=args.lang) if args.acknowledge else onboarding.welcome(doctor(), language=args.lang)
        elif args.command == "configure":
            if onboarding.status(ROOT)['due']:
                print(onboarding.welcome(doctor())['message'])
            credentials.configure(legacy=args.legacy)
            return 0
        elif args.command == "login":
            return media.douyin_browser.login(ROOT / ".local" / "douyin-profile")
        elif args.command == "inspect-source":
            result = review.inspect_source(args.inputs, anonymous_only=args.anonymous_only, download_audio=args.download_audio)
        elif args.command == "prepare-review":
            result = review.prepare(args.task, images=args.images, audio=args.audio, item_number=args.item,
                                    start=args.start, end=args.end, every_frame=args.every_frame,
                                    max_frames=args.max_frames, cached_only=args.cached_only)
        elif args.command == "init":
            result = setup.initialize(vault=args.vault, create_vault=args.create_vault,
                                      assistant=args.assistant, register=args.register)
        elif args.command == "plan-text":
            result = content.plan_text(args.file)
        elif args.command in {"register-review", "register-spoken"}:
            result = content.register_content(args.task, args.file,
                "review" if args.command == "register-review" else "spoken", evidence=args.evidence, item_ids=args.item)
        elif args.command == "deliver":
            result = content.deliver(args.task, args.kind)
        elif args.command == "archive":
            result = content.archive(args.task, prefix=args.target_prefix,
                raw_file=args.raw_file, reviewed_file=args.reviewed_file, include_spoken=args.include_spoken,
                spoken_file=args.spoken_file, evidence=args.evidence)
        elif args.command == "record-publication":
            result = content.record_publication(args.task, args.receipt)
        elif args.command == "plan":
            result = workflow.plan(args.inputs)
        elif args.command == "confirm":
            scope = {key: value for key, value in {"all": args.all, "latest": args.latest,
                                                  "start": args.start, "end": args.end}.items() if value}
            result = workflow.confirm(args.task, args.purpose, args.evidence, scope=scope,
                                      instruction=args.instruction, category=args.category,
                                      retranscribe=args.retranscribe)
        elif args.command == "run":
            result = workflow.run(args.task, retry_evidence=args.retry_evidence, anonymous_only=args.anonymous_only,
                                  saved_scope=args.saved_scope)
        elif args.command == 'reanalyze':
            result = workflow.reanalyze(args.task, args.instruction)
        elif args.command == "show":
            result = workflow.load(args.task)
        elif args.command == "preview":
            result = {"sources": vault.publication_plan(workflow.load(args.task))}
        elif args.command == "export-srt":
            result = {"files": workflow.export_srt(args.task)}
        elif args.command == "finish-analysis":
            result = workflow.finish_analysis(args.task, args.file)
        else:
            if len(args.page) != len(args.target) or len(args.page) != len(args.expected_sha256):
                raise ValueError("每个知识页都需要对应的 --page、--target 和 --expected-sha256")
            pages = [{"file": file, "target": target, "expected_sha256": checksum if checksum != "-" else None}
                     for file, target, checksum in zip(args.page, args.target, args.expected_sha256)]
            result = vault.publish(args.task, pages=pages)
        # Recorded file paths are workspace-relative; name the workspace so they can be opened.
        result.setdefault("workspace", str(ROOT))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("status") in {"incomplete", "failed", "publish_failed", "publication_unknown",
                                            "environment_incomplete"} else 0
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1
