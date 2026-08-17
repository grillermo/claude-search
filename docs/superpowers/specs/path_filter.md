# Literal Project-Path Filtering

## Goal

Allow searches to be restricted to one project path and its descendants from
both the command-line interface and the Flask web interface. Searches without
a path filter retain their current all-project behavior.

## Decisions

- The CLI option is `--path PATH`.
- The web form field and API query parameter are both named `path`.
- The filter is a literal path prefix, not a regular expression.
- A project matches when its decoded working directory equals the filter or is
  below it in the filesystem hierarchy. Path boundaries are significant, so
  `/tmp/app` does not match `/tmp/application`.
- An omitted or empty path means no filtering.
- The shared Python search function owns filtering so CLI and web behavior stay
  consistent.
- The API echoes the requested path in its successful response.

## Architecture

Extend `claude_search.search()` with an optional `path_prefix` argument. After
decoding each Claude project directory into its working-directory path, skip
projects that are outside the requested prefix before scanning their
transcripts. Normalize the supplied prefix for redundant separators and a
trailing separator without resolving symlinks or requiring the path to exist.

The CLI accepts `--path PATH`, passes it to the shared search function, and
keeps its existing result formatting and exit behavior. Its usage text and
README usage examples document the option.

The Flask endpoint accepts `path` from the query string and passes it to the
same shared function. The HTML form adds a project-path text field, and the
frontend includes its value in every search request using URL encoding. The
existing case-sensitive and stale-response behavior remains unchanged.

## Validation and error handling

Path filtering does not introduce regex validation. An empty value is treated
as absent. User-provided paths remain data passed to the search function and
are never assembled into shell commands. Existing search-term validation and
API error responses are unchanged.

## Testing

Add focused tests for:

- exact project-path matches;
- descendant project-path matches;
- path-boundary rejection for similarly prefixed paths;
- unchanged results when the path filter is empty or omitted;
- CLI filtering through `--path PATH`;
- API filtering and successful response echoing of `path`;
- presence of the project-path form field;
- JavaScript request URLs containing the encoded path.

Run the Python and Node test suites, plus syntax checks and `git diff --check`,
before declaring the feature complete.

## Acceptance criteria

- `claude-search needle --path /Users/me/project` searches that project and
  projects below it only.
- The web form can submit the same literal path filter.
- A path such as `/tmp/app` never includes `/tmp/application`.
- Existing searches, result ordering, highlighting, case sensitivity, and
  resume commands remain unchanged when no path is supplied.
