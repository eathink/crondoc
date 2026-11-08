import unittest

from crondoc.crontab import parse_crontab
from crondoc.expr import CronError


class CrontabTests(unittest.TestCase):
    def test_parses_jobs_and_skips_noise(self):
        text = """
# comment
SHELL=/bin/bash
MAILTO=""

0 3 * * * /usr/local/bin/backup.sh --full
@daily /usr/local/bin/rotate.sh
"""
        jobs = parse_crontab(text)

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].line, 6)
        self.assertEqual(jobs[0].expression, "0 3 * * *")
        self.assertEqual(jobs[0].command, "/usr/local/bin/backup.sh --full")
        self.assertEqual(jobs[1].expression, "@daily")
        self.assertEqual(jobs[1].command, "/usr/local/bin/rotate.sh")

    def test_missing_command(self):
        with self.assertRaises(CronError):
            parse_crontab("0 3 * * *\n")

    def test_invalid_expression_reports_line(self):
        with self.assertRaises(CronError) as ctx:
            parse_crontab("\n0 25 * * * echo hi\n")

        self.assertIn(":2:", str(ctx.exception))

    def test_empty(self):
        self.assertEqual(parse_crontab("# nothing\n"), [])


if __name__ == "__main__":
    unittest.main()
