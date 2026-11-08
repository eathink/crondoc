"""命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .crontab import Job, parse_crontab
from .expr import CronError, describe, next_runs, parse_expression

_HORIZON_YEARS = 5


def _positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是整数") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crondoc",
        description="解析 crontab，翻译成人话并计算下次执行时间。",
    )
    parser.add_argument("source", nargs="?", help="crontab 文件路径，- 表示标准输入")
    parser.add_argument("-e", "--expr", help="直接分析单个 cron 表达式")
    parser.add_argument(
        "--next",
        type=_positive_int,
        default=5,
        metavar="N",
        help="每个任务显示下次执行次数（默认 5）",
    )
    parser.add_argument(
        "--from",
        dest="start",
        metavar="ISO",
        help="计算起点，默认当前时间（本地时间，不带时区）",
    )
    parser.add_argument(
        "-f", "--format", choices=("text", "json"), default="text", help="输出格式"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _load_jobs(args: argparse.Namespace) -> tuple[str, list[Job]]:
    if args.expr:
        expression = args.expr.strip()
        return "--expr", [Job(0, expression, parse_expression(expression), "")]

    assert args.source is not None
    if args.source == "-":
        text = sys.stdin.read()
    else:
        try:
            text = Path(args.source).read_text(encoding="utf-8")
        except OSError as exc:
            raise CronError(
                f"无法读取 {args.source}: {exc.strerror or exc}"
            ) from exc
    return args.source, parse_crontab(text, args.source)


def _parse_start(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now()
    try:
        start = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise CronError(
            "--from 需要 ISO 格式，例如 2026-01-01T09:30"
        ) from exc
    if start.tzinfo is not None:
        raise CronError("--from 不支持时区，请传本地时间")
    return start


def _render_text(source: str, start: datetime, entries: list[dict]) -> str:
    lines = [f"来源 {source}，起点 {start:%Y-%m-%d %H:%M}", ""]
    if not entries:
        lines.append("没有可分析的任务。")
        return "\n".join(lines)

    for entry in entries:
        job = entry["job"]
        location = f"第 {job.line} 行" if job.line else "表达式"
        lines.append(f"{location}  {entry['description']}")
        schedule = job.expression
        if job.command:
            schedule = f"{schedule}  {job.command}"
        lines.append(f"  {schedule}")
        if entry["runs"]:
            formatted = "、".join(
                run.strftime("%Y-%m-%d %H:%M") for run in entry["runs"]
            )
            lines.append(f"  下次：{formatted}")
        else:
            lines.append(f"  下次：未来 {_HORIZON_YEARS} 年内不会执行")
        lines.append("")
    return "\n".join(lines).rstrip()


def _render_json(source: str, start: datetime, entries: list[dict]) -> str:
    payload = {
        "source": source,
        "from": start.isoformat(timespec="minutes"),
        "horizon_years": _HORIZON_YEARS,
        "jobs": [
            {
                "line": entry["job"].line,
                "expression": entry["job"].expression,
                "description": entry["description"],
                "command": entry["job"].command,
                "next_runs": [
                    run.isoformat(timespec="minutes") for run in entry["runs"]
                ],
                "never": not entry["runs"],
            }
            for entry in entries
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if bool(args.source) == bool(args.expr):
        print("crondoc: 需要且只能提供 SOURCE 或 --expr 之一", file=sys.stderr)
        return 2

    try:
        start = _parse_start(args.start)
        source, jobs = _load_jobs(args)
    except CronError as exc:
        print(f"crondoc: {exc}", file=sys.stderr)
        return 2

    entries = []
    never = False
    for job in jobs:
        runs = next_runs(job.expr, start, args.next, _HORIZON_YEARS)
        if not runs:
            never = True
        entries.append(
            {"job": job, "runs": runs, "description": describe(job.expr)}
        )

    if args.format == "json":
        print(_render_json(source, start, entries))
    else:
        print(_render_text(source, start, entries))

    return 1 if never else 0


if __name__ == "__main__":
    raise SystemExit(main())
