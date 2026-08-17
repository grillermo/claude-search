# Flask Web Service for Claude Search

## Goal

Provide a focused browser interface for exploring Claude conversation search
results instead of displaying every result as a wall of terminal text. The
existing command-line behavior remains available, while the web server reuses
the same search functions directly.

## Decisions

- Flask calls shared Python search functions directly; it does not launch the
  CLI and there is no `--json` CLI mode.
- The CLI remains a supported interface and keeps its current human-readable
  output.
- The browser searches when the user presses Enter.
- Search terms remain Python regular expressions, with a 500-character maximum.
- Searches are case-insensitive by default and expose the existing
  `--case-sensitive` behavior as a checkbox beside the search field.
- The server binds to `127.0.0.1` by default. `-b` changes the bind address and
  `-p` changes the port.
- No authentication is added for the local-only default use case.
- The frontend uses vanilla JavaScript and Tailwind from its public CDN only;
  no additional JavaScript or CSS framework is introduced.

## Architecture

Extract the reusable search implementation into an importable
`claude_search.py` module. It owns transcript discovery, user-message
filtering, regex compilation, matching, result ordering, relative dates,
resume-command construction, and safe highlight segment generation.

`claude-search.py` remains the CLI entry point. It parses command-line options,
calls the shared module, and formats results using the existing terminal
output conventions. Existing CLI output, color behavior, and exit behavior are
preserved.

Add a small Flask server module. It imports the shared search module and
provides:

- `GET /` — renders the application shell.
- `GET /api/search?term=<regex>&case_sensitive=<boolean>` — validates the
  request, calls the search function, and returns structured results.

Add `templates/index.html` and a small static JavaScript file. Tailwind is
loaded from its public CDN in the template. The server does not need a
database, background worker, or client-side framework.

Add an executable `serve` script. It uses the existing `./python_env` virtual
environment, installs `requirements.txt` if Flask is not available, and starts
the Flask application. It accepts `-p` for port and `-b` for bind address.

`requirements.txt` contains Flask as the only Python web dependency.

## Search and result data

The shared search API returns structured result objects containing:

- transcript modification time and relative date;
- project working directory;
- conversation ID;
- shell-quoted resume command;
- the conversation's first user message;
- the first matching user message;
- highlight segments for the first and matching messages.

Results remain sorted newest first, matching the CLI. The first result is shown
after a successful search. The browser keeps the complete result list in its
state and displays one result at a time.

Highlight segments are produced by Python's compiled regex rather than by
reinterpreting the pattern in JavaScript. The browser renders ordinary text as
text nodes and creates highlight elements only for the marked segments; raw
conversation content is never inserted as HTML.

## Interface

The page has three vertical regions:

1. A top search bar containing the search field, a short regex hint, the
   case-sensitive checkbox, and the submit action.
2. A result viewport occupying the available window height. It displays one
   result at a time and scrolls internally when the messages overflow. The
   resume command and `Copy` button remain pinned at the top of this panel.
3. A bottom navigation bar with previous/next arrows and a `Result N of M`
   indicator. The arrows are disabled at the first and last result. Left and
   right keyboard arrow keys perform the same navigation.

On first load, the search field is focused and the result viewport shows an
empty prompt such as “Search your Claude history.”

The copy button writes the pinned resume command to the clipboard and gives a
brief visible confirmation. If clipboard access is unavailable, the command
remains selectable for manual copying.

## Validation and error handling

The API rejects empty terms, terms longer than 500 characters, and invalid
Python regular expressions with a friendly result-panel message. User input is
passed to the search functions as data, never assembled into a shell command.

Missing Claude history and zero matches are rendered as friendly empty states
inside the result viewport. Unexpected server errors produce a generic error
message in the panel without exposing filesystem details or tracebacks.

Because the default binding is loopback-only and the application has no
accounts or state-changing actions, authentication and CSRF protection are
outside this first version. Passing `-b` to expose the server beyond the local
machine is an explicit operator choice.

## Testing

Retain and update the existing CLI tests while moving shared logic into the
importable module. Add focused tests for:

- result discovery, newest-first ordering, and case sensitivity;
- regex validation and the 500-character limit;
- relative dates and highlight segments;
- preservation of CLI output and resume commands;
- Flask initial-page rendering;
- successful API searches, no matches, invalid patterns, oversized patterns,
  and missing history;
- `serve` argument handling for bind address and port.

## Acceptance criteria

- Running `./serve` starts the service using `./python_env` and
  `requirements.txt`.
- `./serve -p 5050 -b 127.0.0.1` changes the listening port and address.
- Pressing Enter performs a regex search and displays exactly one result at a
  time.
- Long messages scroll inside the result viewport without moving the page
  layout out of view.
- The resume command stays visible at the top of the result panel and can be
  copied.
- Previous/next arrows and left/right keys navigate correctly and stop at the
  ends.
- CLI behavior remains available and unchanged in substance.
