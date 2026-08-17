# claude-search

Search your Claude Code conversation history across every project, and get a
ready-to-paste command to resume any match.

Claude Code stores each session as a JSONL transcript under
`~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`. `claude-search` walks all
of them and looks for your search term.

## What it searches

**Only messages you actually typed.** Transcripts contain a lot of text you did
not write — tool results, injected `<system-reminder>` blocks (your `CLAUDE.md`
lands in every session this way), and local-command output. All of that is
skipped, so a hit always corresponds to something you said. Without this, a
common word from your global instructions would match nearly every session.

## Usage

```bash
claude-search <term> [--case-sensitive]
```

`<term>` is a Python regular expression. Matching is case-insensitive unless
`--case-sensitive` is passed.

```bash
claude-search gworktree           # plain substring
claude-search 'stripe|checkout'   # regex alternation
claude-search Rails --case-sensitive
```

## Output

```
Found 2 conversation(s) matching 'gworktree':

1. 2 weeks ago · cd /Users/you/c/zsh && claude --resume bae8d4b3-ec79-4a23-8903-f9541b452074
   I want a function called gworktree {name} to create or jump into a .worktrees/{name}

2. 1 month ago · cd /Users/you/c/datacenters && claude --resume abe8114a-9bb1-46bd-8aec-b8ca705705fb
   set up the new deploy pipeline

   > can you run gworktree on the release branch first?
```

Each result is:

- **A bold header line** — how long ago the session was modified, followed by
  the exact command to resume it in the right working directory. Copy, paste,
  done. The path is shell-quoted.
- **The conversation's first message**, in full — no truncation, multi-line
  messages keep their line breaks.
- **The first matching message**, prefixed with a yellow `>`, shown only when the
  match is somewhere later in the conversation rather than in the first message.

The search term is highlighted wherever it appears, in either block. Results are
sorted newest first by transcript modification time. Relative ages are shown as
`just now`, minutes, hours, days, weeks, or months; months use a 30-day
approximation.

Color is disabled automatically when output is piped, or when `NO_COLOR` is set.

## Install

Requires Python 3 (standard library only) and Claude Code history in
`~/.claude/projects`.

```bash
git clone git@github.com:grillermo/claude-search.git ~/c/claude-search
chmod +x ~/c/claude-search/claude-search.py
ln -s ~/c/claude-search/claude-search.py ~/.local/bin/claude-search
```

Make sure `~/.local/bin` is on your `PATH`.

## Web service

The web service uses the repository's `python_env` environment. Start it from
the repository root with:

```bash
./serve
```

If Flask is not already installed in `python_env`, `./serve` installs it from
`requirements.txt` before starting the service. You can optionally choose the
bind address and port:

```bash
./serve -b 127.0.0.1 -p 5050
```

By default, the service binds to `127.0.0.1` and is available only on the
local machine. Changing `-b` can expose your local conversation history to
other machines, so do so only when that exposure is intended.

Open the displayed local address in a browser. Enter submits a search, and the
search term is interpreted as a Python regular expression. Matching is
case-insensitive by default; enable the **Case sensitive** checkbox for
case-sensitive matching.

The interface shows one result at a time. Use Previous and Next to navigate
between results, or use the Left and Right arrow keys when the search field is
not focused. The results area scrolls internally for long conversations. The
resume command stays pinned at the bottom of the results area; it is copyable
with the Copy button (and can be selected and copied manually if clipboard
access is unavailable). Tailwind CSS is loaded from its public CDN.
