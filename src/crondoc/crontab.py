"""解析 crontab 文本。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .expr import CronError, CronExpr, parse_expression

_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*=")


@dataclass(frozen=True)
class Job:
    line: int
    expression: str
    expr: CronExpr
    command: str


def parse_crontab(text: str, source: str = "<crontab>") -> list[Job]:
    """解析 crontab：跳过注释与变量赋值，支持 @macro 行。"""
    jobs: list[Job] = []

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if _ENV_RE.match(line):
            continue

        if line.startswith("@"):
            parts = line.split(maxsplit=1)
            expression = parts[0]
            command = parts[1].strip() if len(parts) > 1 else ""
        else:
            parts = line.split(maxsplit=5)
            if len(parts) < 5:
                raise CronError(f"{source}:{lineno}: 至少需要 5 个时间字段")
            expression = " ".join(parts[:5])
            command = parts[5].strip() if len(parts) > 5 else ""

        if not command:
            raise CronError(f"{source}:{lineno}: 缺少命令")

        try:
            expr = parse_expression(expression)
        except CronError as exc:
            raise CronError(f"{source}:{lineno}: {exc}") from exc

        jobs.append(Job(lineno, expression, expr, command))

    return jobs
