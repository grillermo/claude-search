# Flask Search Web Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal Flask web interface that reuses the Claude search functions and presents one navigable result at a time.

**Architecture:** Move transcript scanning and result construction into an importable `claude_search.py` module. Keep `claude-search.py` as a terminal formatter over that module, and add a Flask `server.py` that calls the same functions directly through a small JSON API. A vanilla JavaScript frontend renders the API data with Tailwind loaded from its public CDN.

**Tech Stack:** Python 3, Flask 3.x, `unittest`, vanilla JavaScript, Tailwind CDN.

## Global Constraints

- Flask calls shared Python search functions directly; it does not launch the CLI and there is no `--json` CLI mode.
- The CLI remains a supported interface and keeps its current human-readable output.
- The browser searches when the user presses Enter.
- Search terms remain Python regular expressions, with a 500-character maximum.
- Searches are case-insensitive by default and expose the existing `--case-sensitive` behavior as a checkbox beside the search field.
- The server binds to `127.0.0.1` by default. `-b` changes the bind address and `-p` changes the port.
- No authentication is added for the local-only default use case.
- The frontend uses vanilla JavaScript and Tailwind from its public CDN only; no additional JavaScript or CSS framework is introduced.
- Results remain sorted newest first and use transcript modification time for relative dates.
- User input is passed as data to Python functions and is never assembled into a shell command.
- Conversation text is rendered as text, not unsanitized HTML.
- `requirements.txt` contains Flask as the only Python web dependency.

---

## File map

- Create: `claude_search.py` — importable search domain functions, validation, result dataclasses, relative dates, and highlight segments.
- Modify: `claude-search.py` — CLI argument handling and terminal formatting over `claude_search.py`.
- Create: `server.py` — Flask app factory, API route, CLI bind/port parsing, and server entry point.
- Create: `templates/index.html` — page shell, search controls, result viewport, navigation, and Tailwind CDN include.
- Create: `static/app.js` — browser state, API requests, safe result rendering, navigation, keyboard handling, and clipboard behavior.
- Create: `requirements.txt` — Flask dependency constraint.
- Create: `serve` — executable virtual-environment bootstrapper and server launcher.
- Modify: `tests/test_claude_search.py` — import the shared module while preserving CLI output coverage.
- Create: `tests/test_search_core.py` — shared search contract and validation tests.
- Create: `tests/test_server.py` — Flask page/API and argument parsing tests.
- Modify: `README.md` — document web-service startup and browser behavior.

---

### Task 1: Define the shared search contract with failing tests

**Files:**
- Create: `tests/test_search_core.py`

**Interfaces:**
- Consumes: temporary Claude-style project directories containing JSONL transcripts.
- Produces: failing tests for `SearchResult`, `HighlightSegment`, `search()`, `compile_pattern()`, `time_ago()`, and the search exceptions that later tasks implement.

- [ ] **Step 1: Add the temporary transcript fixture helper**

Create a `unittest.TestCase` helper that writes JSONL user messages under an
explicit projects directory. Keep tests independent of the real home
directory:

```python
import json
import tempfile
import time
import unittest
from pathlib import Path

from claude_search import (
    HighlightSegment,
    InvalidSearchTerm,
    ProjectsDirectoryNotFound,
    SearchResult,
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
```

- [ ] **Step 2: Write the result-shape and newest-first tests**

Add a test that creates two matching transcripts with controlled mtimes,
calls `search("needle", projects_dir=projects_dir, now=260)`, and asserts:

```python
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
            self.assertEqual(results[0].resume_command,
                             "cd /work && claude --resume newer")
```

Import `os` at the top of the test file. The test also establishes that the
optional `now` parameter is part of the deterministic search contract.

- [ ] **Step 3: Write matching, case-sensitivity, and highlight tests**

Add tests for case-insensitive default matching, case-sensitive matching, and
the exact safe highlight segment shape:

```python
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
            self.assertNotIn("<", "".join(segment.text for segment in result.title_segments))
```

- [ ] **Step 4: Write validation, empty-result, missing-history, and date tests**

Add focused tests that assert `search()` raises `InvalidSearchTerm` for an
empty term, a term longer than 500 characters, and an invalid regex; returns an
empty list when the directory exists but nothing matches; raises
`ProjectsDirectoryNotFound` when it does not exist; and preserves the existing
`time_ago()` unit boundaries.

```python
    def test_rejects_empty_oversized_and_invalid_terms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_dir = Path(temp_dir)
            for term in ("", "x" * 501, "["):
                with self.subTest(term=term):
                    with self.assertRaises(InvalidSearchTerm):
                        search(term, projects_dir=projects_dir)

    def test_reports_missing_projects_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_projects_dir = Path(temp_dir) / "missing"
            with self.assertRaises(ProjectsDirectoryNotFound):
                search("needle", projects_dir=missing_projects_dir)
```

Use a unique missing path under `tempfile.TemporaryDirectory()` rather than a
fixed system path in the actual test so the assertion cannot collide with a
real directory.

- [ ] **Step 5: Run the new tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_search_core -v
```

Expected: collection fails because `claude_search.py` and its named interfaces
do not exist yet.

- [ ] **Step 6: Commit the contract tests**

```bash
git add tests/test_search_core.py
git commit -m "test: define shared search service contract"
```

### Task 2: Extract the search module and preserve the CLI

**Files:**
- Create: `claude_search.py`
- Modify: `claude-search.py:4-188`
- Modify: `tests/test_claude_search.py:1-73`

**Interfaces:**
- Consumes: JSONL transcripts under `<projects_dir>/*.jsonl`.
- Produces: `search(term, case_sensitive=False, projects_dir=None, now=None) -> list[SearchResult]`, `compile_pattern(term, case_sensitive=False)`, `time_ago(age_seconds)`, and the existing CLI output.

- [ ] **Step 1: Create the importable module with data types and exceptions**

Move the transcript parsing, project-path decoding, relative-date helper, and
matching logic from `claude-search.py` into `claude_search.py`. Define these
public interfaces:

```python
from dataclasses import dataclass


MAX_TERM_LENGTH = 500


class SearchError(Exception):
    """Base class for expected search failures."""


class InvalidSearchTerm(SearchError):
    """The requested pattern is empty, too long, or invalid."""


class ProjectsDirectoryNotFound(SearchError):
    """Claude history is not available at the configured path."""


@dataclass(frozen=True)
class HighlightSegment:
    text: str
    highlighted: bool


@dataclass(frozen=True)
class SearchResult:
    mtime: float
    cwd: str
    conv_id: str
    title: str
    match: str
    relative_date: str
    resume_command: str
    title_segments: tuple[HighlightSegment, ...]
    match_segments: tuple[HighlightSegment, ...]
```

Keep `dir_to_path()`, `user_texts()`, and `scan_file()` as focused helpers.
`scan_file()` should retain the current behavior of returning the first user
message and the first matching user message.

- [ ] **Step 2: Implement pattern validation and highlight segmentation**

Implement `compile_pattern(term, case_sensitive=False)` so it rejects an empty
term with `Search term cannot be empty.`, rejects any term longer than
`MAX_TERM_LENGTH` with `Search term must be 500 characters or fewer.`, compiles
with `re.IGNORECASE` by default, and translates `re.error` into
`InvalidSearchTerm(f"Invalid regex: {error}")`, preserving the original regex
error text in the message.

Implement `highlight_segments(text, pattern)` using `pattern.finditer(text)`.
Return a tuple of `HighlightSegment` values that covers the original text in
order. Add unhighlighted segments between matches and highlighted segments for
non-empty matches; do not produce HTML or ANSI escape sequences. A string with
no matches returns one unhighlighted segment containing the full string.

Keep the existing `time_ago()` implementation and its month approximation
unchanged.

- [ ] **Step 3: Implement `search()` with deterministic time and path inputs**

Implement:

```python
def search(term, case_sensitive=False, projects_dir=None, now=None):
    """Return newest-first SearchResult values for a user-message regex."""
```

Use `Path.home() / ".claude" / "projects"` when `projects_dir` is `None`.
Raise `ProjectsDirectoryNotFound` when that directory does not exist. Compile
the pattern once, scan each project directory and JSONL transcript, collect
matching files, and sort by the existing tuple ordering with newest mtime
first. Use `time.time()` when `now` is `None`, otherwise use the supplied
timestamp.

For each result, populate the shell-quoted resume command exactly as:

```python
f"cd {shlex.quote(cwd)} && claude --resume {conv_id}"
```

Generate `title_segments` and `match_segments` with the same compiled pattern.
The matching transcript always has a non-empty title and match, so the result
fields can be typed as strings even though `scan_file()` may return `None` for
an unmatched transcript.

- [ ] **Step 4: Run the shared tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_search_core -v
```

Expected: all shared search, validation, highlight, ordering, and relative-date
tests pass.

- [ ] **Step 5: Replace duplicated CLI search logic with the shared module**

Keep `Color` and terminal formatting in `claude-search.py`. Import
`InvalidSearchTerm`, `ProjectsDirectoryNotFound`, `compile_pattern`, and
`search` from `claude_search`.

Update `main()` to preserve these terminal outcomes:

- missing argument: print the current usage to stderr and exit 1;
- invalid regex: print `Invalid regex: <details>` to stderr and exit 1;
- missing history: print `No projects directory found.` to stderr and exit 1;
- no matches: print `No conversations found matching: <term>` and exit 0;
- matches: preserve the current count, relative-date header, title, optional
  matching-message block, ANSI behavior, and resume command.

Use the compiled pattern returned by `compile_pattern()` for terminal
highlighting and the `SearchResult` fields for rendering. Catch
`InvalidSearchTerm` and print its message directly to stderr, so invalid regex
queries retain the existing `Invalid regex: <details>` text. Do not
reintroduce filesystem scanning or JSONL parsing in the CLI wrapper.

- [ ] **Step 6: Update CLI tests to import the module without changing the subprocess contract**

Change `tests/test_claude_search.py` to import `claude_search` normally from the
repository root while continuing to execute `claude-search.py` as a subprocess
for CLI output assertions. Keep the existing `time_ago()` and relative-date
header assertions. Add one invalid-regex assertion that checks the stderr
message and non-zero exit code.

- [ ] **Step 7: Run all Python tests and syntax checks**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile claude_search.py claude-search.py tests/test_claude_search.py tests/test_search_core.py
```

Expected: all tests pass and compilation produces no output.

- [ ] **Step 8: Review and commit the shared module refactor**

```bash
git diff --check
git diff -- claude_search.py claude-search.py tests/test_claude_search.py tests/test_search_core.py
git add claude_search.py claude-search.py tests/test_claude_search.py tests/test_search_core.py
git commit -m "refactor: share Claude search functions"
```

### Task 3: Add the Flask API and server argument handling

**Files:**
- Create: `requirements.txt`
- Create: `server.py`
- Create: `tests/test_server.py`

**Interfaces:**
- Consumes: `claude_search.search`, `InvalidSearchTerm`, and `ProjectsDirectoryNotFound`.
- Produces: `create_app(projects_dir=None)`, `GET /api/search`, `parse_args(argv=None)`, and `main(argv=None)`.

- [ ] **Step 1: Add Flask as the only web dependency and install it in the project venv**

Create `requirements.txt` with:

```text
Flask>=3.1,<4
```

Install it using the existing environment:

```bash
./python_env/bin/python -m pip install -r requirements.txt
```

Expected: the command exits successfully and `./python_env/bin/python -c
'import flask'` succeeds.

- [ ] **Step 2: Write failing Flask route and argument tests**

Create `tests/test_server.py` using Flask’s built-in test client and define a
local `write_transcript()` helper with the JSONL fixture shape from Task 1.
Instantiate the application with
`create_app(projects_dir=projects_dir)` so tests never read the real history.

Cover the following exact contracts:

```python
class ServerTests(unittest.TestCase):
    def test_search_api_returns_serialized_results(self):
        write_transcript(self.projects_dir, "-tmp", "one", ["Find needle"])

        response = self.app.get("/api/search?term=needle&case_sensitive=false")

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
                response = self.app.get(
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

    def test_parse_args_supports_bind_and_port(self):
        args = parse_args(["-b", "0.0.0.0", "-p", "5050"])
        self.assertEqual(args.bind, "0.0.0.0")
        self.assertEqual(args.port, 5050)
```

Also test an existing directory with no match returns HTTP 200 and an empty
`results` list, and test that `case_sensitive=true` is passed through to the
shared search function.

- [ ] **Step 3: Run the server tests to verify they fail**

Run:

```bash
./python_env/bin/python -m unittest tests.test_server -v
```

Expected: collection fails because `server.py` and `requirements.txt` do not
exist yet.

- [ ] **Step 4: Implement `create_app()` and the JSON serializer**

In `server.py`, import Flask’s `Flask`, `jsonify`, `render_template`, and
`request`. Implement:

```python
def serialize_result(result):
    return {
        "mtime": result.mtime,
        "cwd": result.cwd,
        "conv_id": result.conv_id,
        "title": result.title,
        "match": result.match,
        "relative_date": result.relative_date,
        "resume_command": result.resume_command,
        "title_segments": [
            {"text": segment.text, "highlighted": segment.highlighted}
            for segment in result.title_segments
        ],
        "match_segments": [
            {"text": segment.text, "highlighted": segment.highlighted}
            for segment in result.match_segments
        ],
    }


def create_app(projects_dir=None):
    app = Flask(__name__)
    app.config["PROJECTS_DIR"] = projects_dir

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/search")
    def api_search():
        term = request.args.get("term", "")
        case_sensitive = request.args.get("case_sensitive", "false").lower() in {
            "true", "1", "on"
        }
        try:
            results = search(
                term,
                case_sensitive=case_sensitive,
                projects_dir=app.config["PROJECTS_DIR"],
            )
        except InvalidSearchTerm as error:
            return jsonify({
                "error": {"code": "invalid_search", "message": str(error)}
            }), 400
        except ProjectsDirectoryNotFound:
            return jsonify({
                "error": {
                    "code": "history_unavailable",
                    "message": "No Claude history found.",
                }
            }), 503
        except Exception:
            return jsonify({
                "error": {
                    "code": "server_error",
                    "message": "Search failed unexpectedly.",
                }
            }), 500

        return jsonify({
            "term": term,
            "case_sensitive": case_sensitive,
            "results": [serialize_result(result) for result in results],
        })

    return app
```

The API must read `term` as a string, treat only `true`, `1`, and `on`
case-insensitive values as true for `case_sensitive`, call
`claude_search.search(term, case_sensitive=case_sensitive, projects_dir=projects_dir)`, and return
this success shape:

```json
{
  "term": "needle",
  "case_sensitive": false,
  "results": [
    {
      "mtime": 200,
      "cwd": "/tmp",
      "conv_id": "one",
      "title": "Find needle",
      "match": "Find needle",
      "relative_date": "1 minute ago",
      "resume_command": "cd /tmp && claude --resume one",
      "title_segments": [
        {"text": "Find ", "highlighted": false},
        {"text": "needle", "highlighted": true}
      ],
      "match_segments": [
        {"text": "Find ", "highlighted": false},
        {"text": "needle", "highlighted": true}
      ]
    }
  ]
}
```

Serialize dataclasses explicitly so the API contract does not depend on
Flask’s treatment of tuples. Return HTTP 400 with an `error` object whose code
is `invalid_search` and whose message is the exception message for
`InvalidSearchTerm`. Return HTTP 503 with code `history_unavailable` for
`ProjectsDirectoryNotFound`, and HTTP 500 with the generic code
`server_error` for unexpected exceptions without including exception details.

- [ ] **Step 5: Implement server argument parsing and entry point**

Add:

```python
def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Serve Claude search results")
    parser.add_argument("-b", "--bind", default="127.0.0.1")
    parser.add_argument("-p", "--port", type=int, default=5000)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    app.run(host=args.bind, port=args.port)
```

Keep `app = create_app()` at module scope so Flask tests and the launcher can
import it. Add the normal `if __name__ == "__main__": main()` guard.

- [ ] **Step 6: Run the Flask tests and compile checks**

Run:

```bash
./python_env/bin/python -m unittest tests.test_server -v
./python_env/bin/python -m py_compile server.py tests/test_server.py
```

Expected: all API and argument tests pass.

- [ ] **Step 7: Review and commit the Flask backend**

```bash
git diff --check
git add requirements.txt server.py tests/test_server.py
git commit -m "feat: add Flask search API"
```

### Task 4: Build the one-result browser interface

**Files:**
- Create: `templates/index.html`
- Create: `static/app.js`
- Modify: `tests/test_server.py`

**Interfaces:**
- Consumes: the `/api/search` success and error JSON shapes from Task 3.
- Produces: an Enter-driven search UI with a scrollable one-result viewport, pinned resume command, copy action, arrows, result count, and keyboard navigation.

- [ ] **Step 1: Add static-asset and template contract tests**

Extend `tests/test_server.py` with assertions that `/` includes the form,
search input, case-sensitive checkbox, regex hint, result viewport, copy
button, previous/next buttons, and Tailwind CDN URL. Assert that
`/static/app.js` returns HTTP 200 and contains the API route string.

- [ ] **Step 2: Create the Tailwind page shell**

Create `templates/index.html` with a semantic layout using only Tailwind
utility classes and the public CDN include:

```html
<script src="https://cdn.tailwindcss.com"></script>
```

Build a full-window flex column with:

- a top form containing an input, submit button, regex hint, and checkbox;
- a middle `id="result-viewport"` region with `min-h-0 flex-1 overflow-y-auto`;
- a sticky command bar inside the viewport with `id="resume-command"` and
  `id="copy-command"`;
- title and matching-message containers using `whitespace-pre-wrap`;
- a bottom navigation bar with `id="previous-result"`,
  `id="result-position"`, and `id="next-result"`.

Include initial text “Search your Claude history” and focus the search field
after the DOM loads. Keep all dynamic conversation containers empty or filled
with placeholder text so `app.js` owns rendering.

- [ ] **Step 3: Implement fetch and state management in vanilla JavaScript**

Create `static/app.js` with this state shape:

```javascript
const state = {
  results: [],
  index: 0,
  loading: false,
};
```

On form submission, prevent the page reload, send the raw input value through
`encodeURIComponent` to `/api/search`, and send the checkbox as
`case_sensitive=true` or `false`. Show a loading message while awaiting the
response. On a successful response, replace `state.results`, set `index` to
zero, and render the first result. On a non-OK response, parse the JSON error
message and render it in the viewport without exposing a stack trace.

Do not trim the regex before sending it; use `term.trim() === ""` only for the
client-side empty check so meaningful regex whitespace is preserved. The server
remains the source of truth for validation.

- [ ] **Step 4: Implement safe result rendering and highlighting**

Implement a helper that appends each segment as a `Text` node and wraps only
segments with `highlighted: true` in a styled `<mark>` element. Use
`replaceChildren()` before every render and never assign conversation text to
`innerHTML`.

Render the current result’s relative date, project path, title, and matching
message. Omit the separate matching-message block when `match === title`.
Keep long content readable with Tailwind whitespace and word-break classes.

Render the resume command in the sticky command bar and keep the command text
selectable. The copy button should call `navigator.clipboard.writeText()` and
temporarily change its label to “Copied” for about one second. If clipboard
access rejects, select the command text and show “Select and copy the command.”

- [ ] **Step 5: Implement navigation and keyboard behavior**

Implement `renderNavigation()`, `showResult(index)`, and `moveResult(delta)`.
Disable the previous button at index zero and the next button at the final
index. Show `Result N of M` when results exist and hide or disable navigation
when there are no results.

Register click handlers for both buttons. Register a document `keydown`
handler for `ArrowLeft` and `ArrowRight`; ignore those keys while the search
input is focused so normal text cursor movement still works. Prevent the
default action and navigate only when results exist.

Use friendly states for empty results (“No conversations found.”), invalid
requests, missing history, loading, and unexpected request failures.

- [ ] **Step 6: Run the server/static tests and perform a local render smoke check**

Run:

```bash
./python_env/bin/python -m unittest discover -s tests -v
```

Start the app temporarily with:

```bash
./python_env/bin/python server.py -b 127.0.0.1 -p 5050
```

Open `http://127.0.0.1:5050/` and verify the initial focused state, an Enter
search, long-message scrolling, pinned command bar, copy feedback, result
navigation, disabled edge arrows, and keyboard navigation. Stop the temporary
server after the check.

- [ ] **Step 7: Review and commit the frontend**

```bash
git diff --check
git add templates/index.html static/app.js tests/test_server.py
git commit -m "feat: add one-result search interface"
```

### Task 5: Add the `./serve` launcher and dependency bootstrap

**Files:**
- Create: `serve`
- Modify: `tests/test_server.py`

**Interfaces:**
- Consumes: `python_env/bin/python`, `requirements.txt`, and the `server.py` command-line flags.
- Produces: executable `./serve`, with default `127.0.0.1:5000` and forwarded `-b`/`-p` options.

- [ ] **Step 1: Write launcher behavior tests**

Add a subprocess test that runs `./serve --help` with the repository as its
working directory and asserts exit code 0 plus both `--bind` and `--port` in
the help text. Keep the test from starting the server; parsing behavior is
already covered by `parse_args()`.

- [ ] **Step 2: Create the executable launcher**

Create a POSIX shell script with this behavior:

```sh
#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON="$ROOT/python_env/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "Missing Python environment: $PYTHON" >&2
    exit 1
fi

if ! "$PYTHON" -c 'import flask' >/dev/null 2>&1; then
    "$PYTHON" -m pip install -r "$ROOT/requirements.txt"
fi

exec "$PYTHON" "$ROOT/server.py" "$@"
```

Mark it executable with `chmod +x serve`. Do not use a broad path, shell
evaluation of user input, or a global Python installation.

- [ ] **Step 3: Run launcher tests and help smoke check**

Run:

```bash
./python_env/bin/python -m unittest tests.test_server -v
./serve --help
```

Expected: the tests pass and help shows the bind and port options without
starting Flask.

- [ ] **Step 4: Review and commit the launcher**

```bash
git diff --check
git add serve tests/test_server.py
git commit -m "chore: add Flask service launcher"
```

### Task 6: Document web-service usage

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: the final `./serve` command, flags, and browser behavior.
- Produces: user-facing setup and usage documentation without changing CLI examples.

- [ ] **Step 1: Add web-service installation instructions**

After the existing CLI installation section, document that the repository’s
`python_env` is used and that `./serve` installs Flask from `requirements.txt`
when needed:

```bash
./serve
```

Document the optional flags:

```bash
./serve -b 127.0.0.1 -p 5050
```

State that the default address is loopback-only and that changing `-b` can
expose local conversation history to other machines.

- [ ] **Step 2: Document the browser interaction**

Explain Enter-to-search, Python regex support, the case-sensitive checkbox,
one-result navigation, internal scrolling, keyboard arrows, and the pinned
copyable resume command. Mention that Tailwind is loaded from its public CDN.

- [ ] **Step 3: Run the full test suite and review the documentation diff**

Run:

```bash
./python_env/bin/python -m unittest discover -s tests -v
git diff --check
```

Expected: all tests pass and the README contains no contradictory startup
instructions.

- [ ] **Step 4: Commit the documentation**

```bash
git add README.md
git commit -m "docs: document Flask search service"
```

### Task 7: Final verification and handoff

**Files:**
- Verify: all tracked project files.

**Interfaces:**
- Consumes: the completed CLI, Flask API, frontend, launcher, tests, and docs.
- Produces: verified working tree and a concise handoff with test evidence.

- [ ] **Step 1: Run syntax checks for every Python entry point and test file**

```bash
./python_env/bin/python -m py_compile claude_search.py claude-search.py server.py tests/*.py
```

Expected: exit code 0 and no syntax errors.

- [ ] **Step 2: Run the complete unit test suite**

```bash
./python_env/bin/python -m unittest discover -s tests -v
```

Expected: all tests pass, including CLI subprocess tests and Flask test-client
tests.

- [ ] **Step 3: Verify the launcher and API without browser state**

Run:

```bash
./serve --help
./python_env/bin/python server.py -b 127.0.0.1 -p 5050
```

While the server is running, in another terminal request:

```bash
curl --fail http://127.0.0.1:5050/
curl --fail --get --data-urlencode 'term=needle' http://127.0.0.1:5050/api/search
```

Confirm the first response contains the search form and the second is valid
JSON. Stop the temporary server after the check.

- [ ] **Step 4: Review the final diff and status**

```bash
git diff --check
git status --short
git log -7 --oneline
```

Expected: no whitespace errors, only intentional commits/changes, and no
untracked runtime artifacts such as caches or virtual-environment files.
