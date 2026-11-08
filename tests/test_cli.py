import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from crondoc.cli import main


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def write_crontab(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "crontab"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_expr_text(self):
        code, out, _ = self.run_cli(
            "--expr", "0 3 * * *", "--from", "2026-01-01T04:00", "--next", "2"
        )

        self.assertEqual(code, 0)
        self.assertIn("每天 03:00", out)
        self.assertIn("2026-01-02 03:00", out)
        self.assertIn("2026-01-03 03:00", out)

    def test_json_format(self):
        code, out, _ = self.run_cli(
            "--expr",
            "*/15 * * * *",
            "--from",
            "2026-01-01T00:07",
            "--next",
            "2",
            "--format",
            "json",
        )

        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(
            payload["jobs"][0]["next_runs"],
            ["2026-01-01T00:15", "2026-01-01T00:30"],
        )

    def test_file_input(self):
        path = self.write_crontab("0 9 * * MON echo hi\n")

        code, out, _ = self.run_cli(
            path, "--from", "2026-01-01T00:00", "--next", "1"
        )

        self.assertEqual(code, 0)
        self.assertIn("第 1 行", out)
        self.assertIn("每周一 09:00", out)
        self.assertIn("echo hi", out)

    def test_invalid_expression_returns_two(self):
        code, _, err = self.run_cli("--expr", "60 * * * *")

        self.assertEqual(code, 2)
        self.assertIn("crondoc:", err)

    def test_never_running_returns_one(self):
        code, out, _ = self.run_cli(
            "--expr", "0 0 30 2 *", "--from", "2026-01-01"
        )

        self.assertEqual(code, 1)
        self.assertIn("不会执行", out)

    def test_requires_source_or_expr(self):
        code, _, err = self.run_cli()

        self.assertEqual(code, 2)
        self.assertIn("--expr", err)


if __name__ == "__main__":
    unittest.main()
