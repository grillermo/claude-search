import json
import os
import tempfile
import unittest
from pathlib import Path

from claude_search import (
    HighlightSegment,
    InvalidSearchTerm,
    ProjectsDirectoryNotFound,
    SearchResult,
    compile_pattern,
    search,
    time_ago,
)


def write_transcript(projects_dir, project_name, conversation_id, messages):
    project_dir = projects_dir / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / f"{conversation_id}.jsonl"
    path.write_text(
        "".join(
            json.dumps({"type": "user", "message": {"content": message}}) + "\n"
            for message in messages
        )
    )
    return path


class SearchCoreTests(unittest.TestCase):
    def test_returns_newest_results_with_structured_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_dir = Path(temp_dir)
            older = write_transcript(projects_dir, "-tmp", "older", [
                "older title",
                "needle appears later",
            ])
            newer = write_transcript(projects_dir, "-work", "newer", [
                "needle in title",
            ])
            os.utime(older, (100, 100))
            os.utime(newer, (200, 200))

            results = search("needle", projects_dir=projects_dir, now=260)

            self.assertEqual([result.conv_id for result in results], ["newer", "older"])
            self.assertIsInstance(results[0], SearchResult)
            self.assertEqual(results[0].cwd, "/work")
            self.assertEqual(results[0].title, "needle in title")
            self.assertEqual(results[1].match, "needle appears later")
            self.assertEqual(results[0].relative_date, "1 minute ago")
            self.assertEqual(results[1].relative_date, "2 minutes ago")
            self.assertEqual(
                results[0].resume_command,
                "cd /work && claude --resume newer",
            )

    def test_compile_pattern_controls_case_sensitivity(self):
        self.assertIsNotNone(compile_pattern("needle").search("Needle"))
        self.assertIsNone(
            compile_pattern("needle", case_sensitive=True).search("Needle")
        )

    def test_case_sensitive_flag_controls_matching(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_dir = Path(temp_dir)
            write_transcript(projects_dir, "-tmp", "one", ["Needle"])

            self.assertEqual(len(search("needle", projects_dir=projects_dir)), 1)
            self.assertEqual(
                search("needle", case_sensitive=True, projects_dir=projects_dir),
                [],
            )

    def test_result_contains_highlight_segments_without_html(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_dir = Path(temp_dir)
            write_transcript(projects_dir, "-tmp", "one", ["Find needle"])

            result = search("needle", projects_dir=projects_dir)[0]

            self.assertEqual(
                result.title_segments,
                (
                    HighlightSegment("Find ", False),
                    HighlightSegment("needle", True),
                ),
            )
            self.assertNotIn(
                "<", "".join(segment.text for segment in result.title_segments)
            )

    def test_rejects_empty_oversized_and_invalid_terms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_dir = Path(temp_dir)
            for term in ("", "x" * 501, "["):
                with self.subTest(term=term):
                    with self.assertRaises(InvalidSearchTerm):
                        search(term, projects_dir=projects_dir)

    def test_reports_empty_results_when_nothing_matches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_dir = Path(temp_dir)
            write_transcript(projects_dir, "-tmp", "one", ["different"])

            self.assertEqual(search("needle", projects_dir=projects_dir), [])

    def test_path_prefix_matches_exact_and_descendant_project_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_dir = Path(temp_dir)
            write_transcript(projects_dir, "-tmp-app", "exact", ["needle"])
            write_transcript(projects_dir, "-tmp-app-child", "descendant", ["needle"])
            write_transcript(projects_dir, "-tmp-application", "similar", ["needle"])

            results = search(
                "needle",
                projects_dir=projects_dir,
                path_prefix="/tmp/app",
            )

            self.assertEqual(
                {result.conv_id for result in results},
                {"exact", "descendant"},
            )

    def test_empty_and_omitted_path_prefixes_have_the_same_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_dir = Path(temp_dir)
            write_transcript(projects_dir, "-tmp-app", "app", ["needle"])
            write_transcript(projects_dir, "-tmp-other", "other", ["needle"])

            omitted = search("needle", projects_dir=projects_dir)
            empty = search("needle", projects_dir=projects_dir, path_prefix="")

            self.assertEqual(empty, omitted)

    def test_path_prefix_accepts_redundant_and_trailing_separators(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_dir = Path(temp_dir)
            write_transcript(projects_dir, "-tmp-app", "one", ["needle"])

            results = search(
                "needle",
                projects_dir=projects_dir,
                path_prefix="/tmp//app/",
            )

            self.assertEqual([result.conv_id for result in results], ["one"])

    def test_reports_missing_projects_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_projects_dir = Path(temp_dir) / "missing"
            with self.assertRaises(ProjectsDirectoryNotFound):
                search("needle", projects_dir=missing_projects_dir)

    def test_preserves_time_ago_unit_boundaries(self):
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
                self.assertEqual(time_ago(age), expected)


if __name__ == "__main__":
    unittest.main()
