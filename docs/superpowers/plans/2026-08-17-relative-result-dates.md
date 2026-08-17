# Relative Search Result Dates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prefix every search result with a human-readable relative age, including month-sized ages.

**Architecture:** Keep transcript modification time as the source of truth and add a pure `time_ago(age_seconds)` helper in `claude-search.py`. The CLI will compute the file age at render time and include the helper’s label in the existing result header; tests will load the script as a module and exercise both the helper and CLI output.

**Tech Stack:** Python 3 standard library, `unittest`, subprocess testing.

## Global Constraints

- Use transcript file modification time for the displayed age.
- Use `just now` below 60 seconds.
- Use minutes, hours, days, weeks, and months in that order; treat one month as 30 days.
- Preserve existing matching, highlighting, color, sorting, and resume-command behavior.
- Do not add dependencies.

---

### Task 1: Add relative-time behavior tests

**Files:**
- Create: `tests/test_claude_search.py`

**Interfaces:**
- Consumes: the module loaded from `claude-search.py`.
- Produces: failing tests defining `time_ago(age_seconds)` output and the CLI header contract.

- [ ] **Step 1: Write the failing tests**

Create a standard-library test module that imports the hyphenated script with
`importlib.util`, then add this helper test:

```python
class TimeAgoTests(unittest.TestCase):
    def test_formats_relative_age_units_and_boundaries(self):
        cases = {
            0: "just now", 59: "just now",
            60: "1 minute ago", 119: "1 minute ago", 120: "2 minutes ago",
            3600: "1 hour ago", 7200: "2 hours ago",
            86400: "1 day ago", 172800: "2 days ago",
            604800: "1 week ago", 1209600: "2 weeks ago",
            2592000: "1 month ago", 5184000: "2 months ago",
        }
        for age, expected in cases.items():
            with self.subTest(age=age):
                self.assertEqual(claude_search.time_ago(age), expected)
```

Add a CLI test that uses `tempfile.TemporaryDirectory`, sets `HOME` in the
subprocess environment, creates `$HOME/.claude/projects/-tmp/session-123.jsonl`
with one JSONL user message containing `needle`, sets its mtime to
`time.time() - 14 * 24 * 60 * 60`, and invokes `claude-search.py needle`.
Assert the output contains a line matching
`1. 2 weeks ago · cd /tmp && claude --resume session-123` and still contains
the message text. Use `subprocess.run(..., check=True, capture_output=True,
text=True)` and `assertRegex` for the header.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m unittest discover -s tests -v
```

Expected: the helper test fails because `time_ago` is not defined, and the
CLI test fails because the header has no relative-age prefix.

### Task 2: Implement and integrate the formatter

**Files:**
- Modify: `claude-search.py` near the imports and result-rendering loop

**Interfaces:**
- Consumes: transcript `mtime` values already collected by `main()`.
- Produces: `time_ago(age_seconds: float) -> str` and headers prefixed with the resulting label.

- [ ] **Step 1: Add the minimal `time_ago` helper**

Import `time` and add:

```python
def time_ago(age_seconds):
    """Return a compact human-readable age for a duration in seconds."""
    units = (
        (30 * 24 * 60 * 60, "month"),
        (7 * 24 * 60 * 60, "week"),
        (24 * 60 * 60, "day"),
        (60 * 60, "hour"),
        (60, "minute"),
    )
    for seconds, name in units:
        if age_seconds >= seconds:
            count = int(age_seconds // seconds)
            return f"{count} {name}{'' if count == 1 else 's'} ago"
    return "just now"
```

- [ ] **Step 2: Prefix the existing result header**

Inside the result loop, calculate `relative_date = time_ago(time.time() - mtime)`
and print:

```python
print(color.bold(f"{i}. {relative_date} · cd {shlex.quote(cwd)} && claude --resume {conv_id}"))
```

Keep all other output and sorting logic unchanged.

- [ ] **Step 3: Run the focused tests to verify they pass**

Run:

```bash
python3 -m unittest discover -s tests -v
```

Expected: all helper boundary/unit tests and the CLI output test pass.

- [ ] **Step 4: Run a syntax check**

Run:

```bash
python3 -m py_compile claude-search.py tests/test_claude_search.py
```

Expected: exit status 0 with no output.

- [ ] **Step 5: Review the diff and commit the implementation**

Run:

```bash
git diff --check
git diff -- claude-search.py tests/test_claude_search.py
git add claude-search.py tests/test_claude_search.py
git commit -m "feat: show relative dates in search results"
```

