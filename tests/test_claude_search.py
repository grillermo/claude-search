import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import claude_search


SCRIPT = Path(__file__).parents[1] / "claude-search.py"


class TimeAgoTests(unittest.TestCase):
    def test_formats_relative_age_units_and_boundaries(self):
        cases = {
            0: "just now",
            59: "just now",
            60: "1 minute ago",
            119: "1 minute ago",
            120: "2 minutes ago",
            3600: "1 hour ago",
            7200: "2 hours ago",
            86400: "1 day ago",
            172800: "2 days ago",
            604800: "1 week ago",
            1209600: "2 weeks ago",
            2592000: "1 month ago",
            5184000: "2 months ago",
        }
        for age, expected in cases.items():
            with self.subTest(age=age):
                self.assertEqual(claude_search.time_ago(age), expected)


class CliOutputTests(unittest.TestCase):
    def test_invalid_regex_writes_error_and_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "["],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid regex:", result.stderr)

    def test_result_header_starts_with_relative_age_and_resume_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_dir = Path(temp_dir) / ".claude" / "projects" / "-tmp"
            projects_dir.mkdir(parents=True)
            transcript = projects_dir / "session-123.jsonl"
            transcript.write_text(
                json.dumps({
                    "type": "user",
                    "message": {"content": "Find needle"},
                })
                + "\n"
            )
            os.utime(transcript, (time.time() - 14 * 24 * 60 * 60,) * 2)

            environment = os.environ.copy()
            environment["HOME"] = temp_dir
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "needle"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertRegex(
                result.stdout,
                r"1\. 2 weeks ago · cd /tmp && claude --resume session-123",
            )
            self.assertIn("Find needle", result.stdout)


if __name__ == "__main__":
    unittest.main()
