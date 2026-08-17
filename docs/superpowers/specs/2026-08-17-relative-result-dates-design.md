# Relative Dates on Search Results

## Goal

Show how long ago each matching Claude conversation was last modified at the
start of its search-result header.

## Design

Add a small `time_ago()` helper to `claude-search.py`. It will receive the
current age in seconds and return a singular/plural human-readable label using
these units, in order:

- seconds: `just now` for less than 60 seconds
- minutes: `1 minute ago`, `N minutes ago`
- hours: `1 hour ago`, `N hours ago`
- days: `1 day ago`, `N days ago`
- weeks: `1 week ago`, `N weeks ago`
- months: `1 month ago`, `N months ago`, treating a month as 30 days

The existing transcript modification time remains the source of truth. The
result header will prepend the relative label while preserving the existing
resume command and result ordering:

```text
1. 2 weeks ago · cd /Users/you/c/zsh && claude --resume <session-id>
```

The helper will be kept separate from output formatting so its threshold and
pluralization behavior can be tested directly. Existing highlighting, color
behavior, search matching, and sorting will remain unchanged.

## Testing

Add focused tests for each time unit, singular/plural output, the `just now`
boundary, and month conversion. Add an output-level assertion that a result
header begins with the relative date and still contains the resume command.

