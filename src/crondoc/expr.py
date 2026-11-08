"""解析 cron 表达式、计算下次执行时间、生成中文描述。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

_FULL_DOM = frozenset(range(1, 32))
_FULL_DOW = frozenset(range(0, 7))

_MONTH_NAMES = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}
_DOW_NAMES = {
    "SUN": 0,
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
}
_CN_DAYS = ("日", "一", "二", "三", "四", "五", "六")

_MACROS = {
    "@yearly": ("0", "0", "1", "1", "*"),
    "@annually": ("0", "0", "1", "1", "*"),
    "@monthly": ("0", "0", "1", "*", "*"),
    "@weekly": ("0", "0", "*", "*", "0"),
    "@daily": ("0", "0", "*", "*", "*"),
    "@midnight": ("0", "0", "*", "*", "*"),
    "@hourly": ("0", "*", "*", "*", "*"),
}
_MACRO_DESC = {
    "@yearly": "每年 1 月 1 日 00:00",
    "@annually": "每年 1 月 1 日 00:00",
    "@monthly": "每月 1 日 00:00",
    "@weekly": "每周日 00:00",
    "@daily": "每天 00:00",
    "@midnight": "每天 00:00",
    "@hourly": "每小时整点",
}


class CronError(ValueError):
    """cron 表达式无法解析。"""


@dataclass(frozen=True)
class CronExpr:
    minutes: frozenset[int]
    hours: frozenset[int]
    dom: frozenset[int]
    months: frozenset[int]
    dow: frozenset[int]
    raw: tuple[str, str, str, str, str]
    macro: str | None = None


def _to_value(token: str, *, lo: int, hi: int, names: dict[str, int], field: str) -> int:
    token = token.strip().upper()
    if token in names:
        return names[token]
    if not token.isdigit():
        raise CronError(f"{field}: 无法识别的值 {token!r}")
    value = int(token)
    if not lo <= value <= hi:
        raise CronError(f"{field}: 值 {value} 超出范围 {lo}-{hi}")
    return value


def _parse_field(
    text: str,
    *,
    field: str,
    lo: int,
    hi: int,
    names: dict[str, int] | None = None,
    sunday: bool = False,
) -> frozenset[int]:
    names = names or {}
    text = text.strip().upper()
    if not text:
        raise CronError(f"{field}: 不能为空")

    if text == "*":
        values = set(range(lo, hi + 1))
    else:
        values = set()
        for part in text.split(","):
            part = part.strip()
            if not part:
                raise CronError(f"{field}: 列表中有空项")

            base, slash, step_text = part.partition("/")
            if slash:
                if not step_text.isdigit() or int(step_text) <= 0:
                    raise CronError(f"{field}: 步长必须是正整数")
                step = int(step_text)
            else:
                step = 1

            base = base.strip()
            if base == "*":
                start, end = lo, hi
            elif "-" in base:
                left, _, right = base.partition("-")
                start = _to_value(left, lo=lo, hi=hi, names=names, field=field)
                end = _to_value(right, lo=lo, hi=hi, names=names, field=field)
                if start > end:
                    raise CronError(f"{field}: 范围起点大于终点 {base!r}")
            else:
                start = end = _to_value(base, lo=lo, hi=hi, names=names, field=field)

            values.update(range(start, end + 1, step))

    if sunday:
        values = {0 if value == 7 else value for value in values}
    return frozenset(values)


def parse_expression(text: str) -> CronExpr:
    """解析 5 字段表达式或 @macro。"""
    original = text.strip()
    if not original:
        raise CronError("表达式不能为空")

    macro = None
    if original.startswith("@"):
        key = original.lower()
        if key == "@reboot":
            raise CronError("@reboot 没有可计算的时间语义")
        if key not in _MACROS:
            raise CronError(f"未知宏 {original!r}")
        fields = _MACROS[key]
        macro = key
    else:
        fields = tuple(original.split())
        if len(fields) != 5:
            raise CronError(f"需要 5 个字段，实际 {len(fields)} 个")

    minutes = _parse_field(fields[0], field="分钟", lo=0, hi=59)
    hours = _parse_field(fields[1], field="小时", lo=0, hi=23)
    dom = _parse_field(fields[2], field="日", lo=1, hi=31)
    months = _parse_field(fields[3], field="月", lo=1, hi=12, names=_MONTH_NAMES)
    dow = _parse_field(
        fields[4], field="星期", lo=0, hi=7, names=_DOW_NAMES, sunday=True
    )

    return CronExpr(minutes, hours, dom, months, dow, fields, macro)


def _day_matches(expr: CronExpr, day: date) -> bool:
    if day.month not in expr.months:
        return False

    dom_restricted = expr.dom != _FULL_DOM
    dow_restricted = expr.dow != _FULL_DOW
    dom_ok = day.day in expr.dom
    dow_ok = ((day.weekday() + 1) % 7) in expr.dow

    # 标准 cron 语义：日与星期都受限时取“或”，只限一个时取“与”。
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    if dom_restricted:
        return dom_ok
    if dow_restricted:
        return dow_ok
    return True


def next_runs(
    expr: CronExpr,
    start: datetime,
    count: int = 5,
    horizon_years: int = 5,
) -> list[datetime]:
    """返回严格晚于 start 的下 count 次执行时间；超过视界则返回空列表。"""
    if count <= 0:
        return []

    cursor = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
    day = cursor.date()
    last_day = day + timedelta(days=366 * horizon_years)
    hours = sorted(expr.hours)
    minutes = sorted(expr.minutes)
    results: list[datetime] = []

    while day <= last_day and len(results) < count:
        if _day_matches(expr, day):
            for hour in hours:
                for minute in minutes:
                    moment = datetime.combine(day, time(hour, minute))
                    if moment >= cursor:
                        results.append(moment)
                        if len(results) >= count:
                            break
                if len(results) >= count:
                    break
        day += timedelta(days=1)

    return results


def describe(expr: CronExpr) -> str:
    """生成简短的中文描述；复杂表达式回退为字段罗列。"""
    if expr.macro:
        return _MACRO_DESC[expr.macro]

    minute_raw, hour_raw, dom_raw, month_raw, dow_raw = expr.raw
    minute_step = re.fullmatch(r"\*/(\d+)", minute_raw)
    hour_step = re.fullmatch(r"\*/(\d+)", hour_raw)

    if all(field == "*" for field in expr.raw):
        return "每分钟"
    if (
        minute_step
        and hour_raw == "*"
        and dom_raw == "*"
        and month_raw == "*"
        and dow_raw == "*"
    ):
        return f"每 {minute_step.group(1)} 分钟"
    if (
        minute_raw == "0"
        and hour_step
        and dom_raw == "*"
        and month_raw == "*"
        and dow_raw == "*"
    ):
        return f"每 {hour_step.group(1)} 小时"

    if len(expr.minutes) == 1 and len(expr.hours) == 1:
        hour = next(iter(expr.hours))
        minute = next(iter(expr.minutes))
        clock = f"{hour:02d}:{minute:02d}"
        if dom_raw == "*" and month_raw == "*" and dow_raw == "*":
            return f"每天 {clock}"
        if dom_raw == "*" and month_raw == "*" and len(expr.dow) == 1:
            return f"每周{_CN_DAYS[next(iter(expr.dow))]} {clock}"
        if dow_raw == "*" and month_raw == "*" and len(expr.dom) == 1:
            return f"每月 {next(iter(expr.dom))} 日 {clock}"

    return f"分 {minute_raw}，时 {hour_raw}，日 {dom_raw}，月 {month_raw}，周 {dow_raw}"
