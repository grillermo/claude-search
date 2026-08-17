# Literal Project-Path Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional literal project-path filter shared by the CLI and Flask web interface while preserving all-project searches when no path is supplied.

**Architecture:** `claude_search.search()` will normalize an optional `path_prefix` lexically and filter decoded project working directories with filesystem-boundary-aware matching before transcript scanning. The CLI and Flask endpoint will pass user input to that shared function; the web form and JavaScript will carry the same value through URL encoding.

**Tech Stack:** Python 3 standard library, Flask, unittest, Node.js built-in test runner.

## Global Constraints

- The CLI option is `--path PATH`.
- The web form field and API query parameter are both named `path`.
- The filter is a literal path prefix, not a regular expression.
- A project matches when its decoded working directory equals the filter or is below it in the filesystem hierarchy; path boundaries are significant.
- An omitted or empty path means no filtering.
- Normalize redundant separators and a trailing separator without resolving symlinks or requiring the path to exist.
- The shared Python search function owns filtering so CLI and web behavior stay consistent.
- The API echoes the requested path in every successful response.
- Existing search-term validation, error responses, result ordering, highlighting, case sensitivity, stale-response handling, formatting, and resume commands remain unchanged.
- User-provided paths remain data and must never be assembled into shell commands.
- Run Python and Node test suites, syntax checks, and `git diff --check` before completion.

---

### Task 1: Shared literal path filtering

**Files:**
- Modify: `claude_search.py`
- Test: `tests/test_search_core.py`

**Interfaces:**
- Consumes: existing decoded project working-directory strings from `dir_to_path()`.
- Produces: `search(term, case_sensitive=False, projects_dir=None, now=None, path_prefix=None) -> list[SearchResult]`; an empty or omitted `path_prefix` keeps the current all-project behavior.

- [ ] **Step 1: Write the failing tests**

Add focused tests using the existing `write_transcript()` helper. Cover an exact match, a descendant match, rejection of a similarly prefixed path such as `/tmp/application` for `/tmp/app`, empty and omitted filters returning the same results, and redundant separators/trailing separator being accepted without requiring the prefix to exist.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `python_env/bin/python -m unittest tests.test_search_core.SearchCoreTests -v`

Expected: the new calls fail because `search()` does not accept `path_prefix` and no path filtering exists.

- [ ] **Step 3: Implement the minimal shared filter**

Add a small lexical normalization/matching helper using `os.path.normpath()` and `os.path.commonpath()` (or an equivalent boundary-aware standard-library implementation). Treat falsey input as absent, normalize only the supplied string, and skip an out-of-prefix project before scanning its `*.jsonl` files. Do not call `resolve()`, `realpath()`, or filesystem checks on the prefix.

- [ ] **Step 4: Run the focused and existing Python tests**

Run: `python_env/bin/python -m unittest tests.test_search_core tests.test_claude_search -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add claude_search.py tests/test_search_core.py
git commit -m "feat: filter searches by project path"
```

### Task 2: CLI path option and documentation

**Files:**
- Modify: `claude-search.py`
- Modify: `README.md`
- Test: `tests/test_claude_search.py`

**Interfaces:**
- Consumes: `search(..., path_prefix=...)` from Task 1.
- Produces: `claude-search <term> [--case-sensitive] [--path PATH]` with existing output and exit behavior.

- [ ] **Step 1: Write the failing CLI test**

Create two temporary encoded project directories under a temporary `HOME`, write matching transcripts in the requested project and another project, invoke `claude-search.py needle --path /tmp/project`, and assert only the requested project appears. Add an assertion that the no-argument usage text contains `--path PATH`.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python_env/bin/python -m unittest tests.test_claude_search.CliOutputTests -v`

Expected: the usage assertion and/or filtering assertion fails because the CLI neither documents nor forwards a path.

- [ ] **Step 3: Implement CLI parsing and forwarding**

Read the `--path` option and its following value while retaining `--case-sensitive`, pass the value as `path_prefix` to `search()`, and update the existing usage text. Preserve current invalid-term, missing-history, no-results, and formatted-result behavior.

- [ ] **Step 4: Document the option**

Update the README usage synopsis and add a literal-path example explaining that descendants match and similarly prefixed paths do not.

- [ ] **Step 5: Run CLI tests**

Run: `python_env/bin/python -m unittest tests.test_claude_search -v`

Expected: all CLI tests pass.

- [ ] **Step 6: Commit**

```bash
git add claude-search.py README.md tests/test_claude_search.py
git commit -m "feat: add CLI project path option"
```

### Task 3: Flask API and web form path support

**Files:**
- Modify: `server.py`
- Modify: `templates/index.html`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `search(..., path_prefix=...)` from Task 1.
- Produces: `GET /api/search?term=...&path=...` with successful JSON containing the exact requested `path`, plus an HTML input named `path`.

- [ ] **Step 1: Write the failing API and markup tests**

Add an API test with transcripts in an exact project and a similarly prefixed project; request `path=/tmp/app/` and assert the matching project is returned and `payload["path"]` equals `/tmp/app/`. Extend the index contract test to require a project-path input with `id="project-path"` and `name="path"`.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `python_env/bin/python -m unittest tests.test_server -v`

Expected: the API response lacks `path`, returns unfiltered results, and the HTML lacks the project-path field.

- [ ] **Step 3: Implement API forwarding and response echo**

Read `request.args.get("path", "")`, pass it to `search()` as `path_prefix`, and add the unchanged requested value to the successful JSON object. Leave all existing error handling and term/case-sensitive processing untouched.

- [ ] **Step 4: Add the project-path form field**

Add a text input with `id="project-path"`, `name="path"`, and a clear project-path label/placeholder, preserving the existing responsive form behavior.

- [ ] **Step 5: Run server tests**

Run: `python_env/bin/python -m unittest tests.test_server -v`

Expected: all server tests pass.

- [ ] **Step 6: Commit**

```bash
git add server.py templates/index.html tests/test_server.py
git commit -m "feat: add web project path filter"
```

### Task 4: Encode the path in frontend requests

**Files:**
- Modify: `static/app.js`
- Test: `tests/test_app.js`

**Interfaces:**
- Consumes: the `#project-path` form control added in Task 3.
- Produces: every search request includes `path=${encodeURIComponent(projectPath)}` while preserving case-sensitive and stale-response behavior.

- [ ] **Step 1: Write the failing JavaScript test**

Add the project-path element to the test DOM, set it to a path containing spaces and a literal `?`, submit a search, and assert the fetch URL contains the encoded path query parameter. Update the existing URL expectations to include the empty `path=` parameter.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `node --test tests/test_app.js`

Expected: URL assertions fail because the frontend currently sends only `term` and `case_sensitive`.

- [ ] **Step 3: Implement the request parameter**

Read `#project-path` once with the other form controls and append `&path=${encodeURIComponent(projectPathInput.value)}` to the fetch URL for every submitted search, including an empty value.

- [ ] **Step 4: Run JavaScript tests**

Run: `node --test tests/test_app.js`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add static/app.js tests/test_app.js
git commit -m "feat: submit project path from web form"
```

### Final verification

- [ ] Run: `python_env/bin/python -m unittest discover -s tests -v`
- [ ] Run: `node --test tests/test_app.js`
- [ ] Run: `python_env/bin/python -m py_compile claude_search.py claude-search.py server.py`
- [ ] Run: `git diff --check`
- [ ] Re-read `docs/superpowers/specs/path_filter.md` and inspect the complete branch diff for every acceptance criterion.
