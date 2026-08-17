import json
import tempfile
import unittest
from pathlib import Path

from server import create_app, parse_args


def write_transcript(projects_dir, project_name, conversation_id, messages):
    project_dir = projects_dir / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / f"{conversation_id}.jsonl"
    path.write_text(
        "".join(
            json.dumps({"type": "user", "message": {"content": message}})
            + "\n"
            for message in messages
        )
    )
    return path


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.temp_dir.name) / "projects"
        self.projects_dir.mkdir()
        self.app = create_app(projects_dir=self.projects_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_search_api_returns_serialized_results(self):
        write_transcript(self.projects_dir, "-tmp", "one", ["Find needle"])

        response = self.app.test_client().get(
            "/api/search?term=needle&case_sensitive=false"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["case_sensitive"], False)
        self.assertEqual(payload["results"][0]["conv_id"], "one")
        self.assertEqual(
            payload["results"][0]["title_segments"],
            [
                {"text": "Find ", "highlighted": False},
                {"text": "needle", "highlighted": True},
            ],
        )

    def test_invalid_and_oversized_terms_return_json_400_errors(self):
        for term in ("[", "x" * 501):
            with self.subTest(term=term):
                response = self.app.test_client().get(
                    "/api/search", query_string={"term": term}
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

    def test_missing_history_returns_json_503_error(self):
        app = create_app(projects_dir=self.projects_dir / "missing")

        response = app.test_client().get("/api/search?term=needle")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json()["error"]["code"], "history_unavailable"
        )

    def test_no_match_returns_an_empty_results_list(self):
        write_transcript(self.projects_dir, "-tmp", "one", ["different"])

        response = self.app.test_client().get("/api/search?term=needle")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["results"], [])

    def test_case_sensitive_true_is_passed_to_shared_search(self):
        write_transcript(self.projects_dir, "-tmp", "one", ["Needle"])

        response = self.app.test_client().get(
            "/api/search?term=needle&case_sensitive=true"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["case_sensitive"], True)
        self.assertEqual(response.get_json()["results"], [])

    def test_index_renders_the_search_interface_contract(self):
        response = self.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        for required_markup in (
            "<form",
            'id="search-term"',
            'id="case-sensitive"',
            "Regular expressions are supported",
            'id="result-viewport"',
            'id="copy-command"',
            'id="previous-result"',
            'id="next-result"',
            "https://cdn.tailwindcss.com",
        ):
            with self.subTest(required_markup=required_markup):
                self.assertIn(required_markup, page)

    def test_app_javascript_is_served_and_targets_the_search_api(self):
        response = self.app.test_client().get("/static/app.js")
        self.addCleanup(response.close)

        self.assertEqual(response.status_code, 200)
        self.assertIn("/api/search", response.get_data(as_text=True))

    def test_parse_args_supports_bind_and_port(self):
        args = parse_args(["-b", "0.0.0.0", "-p", "5050"])

        self.assertEqual(args.bind, "0.0.0.0")
        self.assertEqual(args.port, 5050)


if __name__ == "__main__":
    unittest.main()
