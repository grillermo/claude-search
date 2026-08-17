# Task 3 Report: Flask API and web form path support

## TDD evidence

### RED

Added `test_search_api_filters_by_project_path_and_echoes_requested_path` to
`tests/test_server.py`. It creates transcripts for `/tmp/app` and the similarly
prefixed `/tmp/application`, requests `/tmp/app/`, and asserts the exact path is
echoed and only the exact project matches. Extended the index markup contract to
require `id="project-path"` and `name="path"`.

Command:

```text
python_env/bin/python -m unittest tests.test_server -v
```

Result: failed as expected. The API test raised `KeyError: 'path'`; the API
filter was not applied, and the two new markup assertions failed. The other 8
server tests passed.

### GREEN

Implemented the minimal server forwarding/response echo and added the project
path text input. The focused command then passed:

```text
Ran 10 tests in 0.282s
OK
```

## Files changed

- `server.py`
  - Reads `request.args.get("path", "")`.
  - Passes the unchanged value as `path_prefix` to `search()`.
  - Echoes the unchanged value as `path` in successful JSON responses.
- `templates/index.html`
  - Adds the responsive `Project path` text input with `id="project-path"`,
    `name="path"`, and an optional-path placeholder.
- `tests/test_server.py`
  - Adds API path filtering/echo coverage and markup contract assertions.

## Tests

- `python_env/bin/python -m unittest tests.test_server -v` — 10 passed.
- `python_env/bin/python -m unittest tests.test_server tests.test_search_core` — 21 passed.
- `node --test tests/test_app.js` — 4 passed.
- `git diff --check` — passed.

The repository's default `python_env/bin/python -m unittest discover -v`
command found 0 tests because its default discovery pattern does not match the
project's test layout; it was not counted as a passing test run.

## Self-review

- Existing term validation, case-sensitive parsing, error responses, and result
  serialization remain unchanged.
- The API echoes the exact requested path, including trailing separators.
- Omitted and empty paths are passed as an empty `path_prefix`, preserving
  unfiltered search behavior.
- The diff is limited to the requested task files and has no whitespace errors.

## Concerns

None for the Task 3 scope. Static JavaScript request URL forwarding is outside
the files and implementation steps specified in this brief.
