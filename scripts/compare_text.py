"""Measure a script revision without modifying its source or judging its meaning."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def measure(path: Path, pace_min: float, pace_max: float) -> dict:
    path = path.expanduser().resolve()
    data = path.read_bytes()
    text = data.decode("utf-8-sig")
    count = sum(character.isalnum() for character in text)
    if count == 0:
        raise ValueError("正文没有可计数字符：" + str(path))
    return {"file": str(path), "sha256": hashlib.sha256(data).hexdigest(),
            "characters": count,
            "estimated_seconds": {"min": math.ceil(count / pace_max * 60),
                                  "max": math.ceil(count / pace_min * 60)}}


def compare(before: Path, after: Path, pace_min: float = 220, pace_max: float = 280) -> dict:
    if not all(math.isfinite(value) for value in (pace_min, pace_max)) or not 0 < pace_min <= pace_max:
        raise ValueError("语速应为有限正数，且最低语速不大于最高语速")
    original, revised = [measure(path, pace_min, pace_max) for path in (before, after)]
    return {"counting_method": "中英文及数字逐字符计数，忽略空白、标点和符号；输入应为独立正文",
            "pace_characters_per_minute": {"min": pace_min, "max": pace_max},
            "timing_note": "按所列语速估算，未计入主播实际停顿、数字及英文读法差异；不是实测时长",
            "before": original, "after": revised,
            "reduction_percent": round((1 - revised["characters"] / original["characters"]) * 100, 1)}


def main() -> int:
    parser = argparse.ArgumentParser(description="计算独立正文改稿前后字数与估算时长；内容保留情况由 Agent 核对")
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--pace-min", type=float, default=220)
    parser.add_argument("--pace-max", type=float, default=280)
    parser.add_argument("--output", type=Path, help="另存统计 JSON；不同内容使用新文件名")
    args = parser.parse_args()
    try:
        result = compare(args.before, args.after, args.pace_min, args.pace_max)
        data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if args.output:
            output = args.output.expanduser().resolve()
            if output.exists():
                if output.read_bytes() != data:
                    raise ValueError("已有统计内容不同，请另存版本：" + str(output))
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("xb") as handle:
                    handle.write(data)
        print(data.decode("utf-8"), end="")
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
