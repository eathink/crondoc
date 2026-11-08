import unittest
from datetime import datetime

from crondoc.expr import CronError, describe, next_runs, parse_expression


class ParseTests(unittest.TestCase):
    def test_every_minute(self):
        expr = parse_expression("* * * * *")

        self.assertEqual(expr.minutes, frozenset(range(60)))
        self.assertEqual(expr.hours, frozenset(range(24)))
        self.assertEqual(expr.dom, frozenset(range(1, 32)))
        self.assertEqual(expr.months, frozenset(range(1, 13)))
        self.assertEqual(expr.dow, frozenset(range(7)))

    def test_steps_lists_ranges(self):
        expr = parse_expression("*/15 0-6/2 1,15 * MON-FRI")

        self.assertEqual(expr.minutes, frozenset({0, 15, 30, 45}))
        self.assertEqual(expr.hours, frozenset({0, 2, 4, 6}))
        self.assertEqual(expr.dom, frozenset({1, 15}))
        self.assertEqual(expr.months, frozenset(range(1, 13)))
        self.assertEqual(expr.dow, frozenset({1, 2, 3, 4, 5}))

    def test_sunday_seven(self):
        self.assertEqual(parse_expression("0 0 * * 7").dow, frozenset({0}))
        self.assertEqual(parse_expression("0 0 * * SUN").dow, frozenset({0}))

    def test_month_names(self):
        self.assertEqual(parse_expression("0 0 1 JAN *").months, frozenset({1}))

    def test_macros(self):
        expr = parse_expression("@daily")

        self.assertEqual(expr.macro, "@daily")
        self.assertEqual(expr.raw, ("0", "0", "*", "*", "*"))

    def test_invalid_expressions(self):
        for text in (
            "* * * *",
            "* * * * * *",
            "60 * * * *",
            "* 24 * * *",
            "*/0 * * * *",
            "5-1 * * * *",
            "@reboot",
            "@foo",
            "",
        ):
            with self.subTest(text=text):
                with self.assertRaises(CronError):
                    parse_expression(text)


class NextRunsTests(unittest.TestCase):
    def test_every_minute(self):
        runs = next_runs(
            parse_expression("* * * * *"), datetime(2026, 1, 1, 0, 0, 30), 3
        )

        self.assertEqual(
            [run.strftime("%H:%M") for run in runs], ["00:01", "00:02", "00:03"]
        )

    def test_every_15_minutes(self):
        runs = next_runs(
            parse_expression("*/15 * * * *"), datetime(2026, 1, 1, 0, 7), 3
        )

        self.assertEqual(
            [run.strftime("%H:%M") for run in runs], ["00:15", "00:30", "00:45"]
        )

    def test_daily(self):
        runs = next_runs(
            parse_expression("30 3 * * *"), datetime(2026, 1, 1, 4, 0), 2
        )

        self.assertEqual(
            [run.isoformat(timespec="minutes") for run in runs],
            ["2026-01-02T03:30", "2026-01-03T03:30"],
        )

    def test_weekly_monday(self):
        # 2026-01-01 是周四
        runs = next_runs(
            parse_expression("0 9 * * MON"), datetime(2026, 1, 1, 10, 0), 1
        )

        self.assertEqual(runs[0], datetime(2026, 1, 5, 9, 0))

    def test_monthly_first(self):
        runs = next_runs(
            parse_expression("0 0 1 * *"), datetime(2026, 1, 15), 1
        )

        self.assertEqual(runs[0], datetime(2026, 2, 1, 0, 0))

    def test_dom_and_dow_use_or_semantics(self):
        # 同时限定 1 号与周一：下一个匹配是周一（1/5），而不是 2/1
        runs = next_runs(
            parse_expression("0 0 1 * MON"), datetime(2026, 1, 2), 1
        )

        self.assertEqual(runs[0], datetime(2026, 1, 5, 0, 0))

    def test_never_runs(self):
        self.assertEqual(
            next_runs(parse_expression("0 0 30 2 *"), datetime(2026, 1, 1), 1),
            [],
        )

    def test_leap_day(self):
        runs = next_runs(
            parse_expression("0 0 29 2 *"), datetime(2026, 1, 1), 1
        )

        self.assertEqual(runs[0], datetime(2028, 2, 29, 0, 0))


class DescribeTests(unittest.TestCase):
    def test_simple_cases(self):
        cases = {
            "* * * * *": "每分钟",
            "*/5 * * * *": "每 5 分钟",
            "0 */2 * * *": "每 2 小时",
            "30 3 * * *": "每天 03:30",
            "0 9 * * MON": "每周一 09:00",
            "0 0 1 * *": "每月 1 日 00:00",
            "@daily": "每天 00:00",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(describe(parse_expression(text)), expected)

    def test_fallback(self):
        description = describe(parse_expression("5,10 * * * *"))

        self.assertIn("分 5,10", description)


if __name__ == "__main__":
    unittest.main()
