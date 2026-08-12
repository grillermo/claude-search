#!/usr/bin/env python3
"""shh - Search Claude conversation history across all projects."""

import json
import os
import shlex
import sys
import re
from pathlib import Path


def dir_to_path(dirname):
    """Convert project dir name back to filesystem path.

    Encoding: leading / -> -, each / -> -, each /. -> --
    Reverse: -- -> /., then - -> /
    """
    # Step 1: strip leading -
    s = dirname.lstrip("-")
    s = "-" + s  # put one back so substitution works uniformly
    # Step 2: -- means /.
    s = s.replace("--", "/.")
    # Step 3: - means /
    s = s.replace("-", "/")
    return s


class Color:
    """ANSI styling, disabled when output is not a terminal or NO_COLOR is set."""

    BOLD = "1"
    YELLOW = "33"
    MATCH = "1;33"

    def __init__(self, enabled=None):
        if enabled is None:
            enabled = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
        self.enabled = enabled

    def paint(self, text, style):
        if not self.enabled or not text:
            return text
        return f"\033[{style}m{text}\033[0m"

    def bold(self, text):
        return self.paint(text, self.BOLD)

    def chevron(self):
        return self.paint(">", self.YELLOW)

    def highlight(self, text, pattern):
        """Style every occurrence of pattern within text."""
        if not self.enabled:
            return text
        return pattern.sub(lambda m: self.paint(m.group(0), self.MATCH), text)


SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)


def user_texts(jsonl_path):
    """Yield text the user actually typed, in order.

    Skips tool results, injected system reminders and local-command output,
    which live in "user" entries but were not written by the user.
    """
    try:
        with open(jsonl_path, errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "user" or obj.get("isMeta"):
                    continue
                content = obj.get("message", {}).get("content", "")
                if isinstance(content, str):
                    blocks = [content]
                elif isinstance(content, list):
                    blocks = [
                        c["text"]
                        for c in content
                        if isinstance(c, dict) and c.get("type") == "text"
                    ]
                else:
                    continue
                for block in blocks:
                    text = SYSTEM_REMINDER.sub("", block).strip()
                    if text and not text.startswith("<local-command"):
                        yield text
    except (IOError, OSError):
        pass


def scan_file(jsonl_path, pattern):
    """Return (title, match) for a conversation.

    title is the first message the user wrote, match is the first one
    containing the pattern (possibly the title itself). match is None when
    the conversation does not match at all.
    """
    title = None
    for text in user_texts(jsonl_path):
        if title is None:
            title = text
        if pattern.search(text):
            return title, text
    return title, None


def main():
    if len(sys.argv) < 2:
        print("Usage: shh <search_term> [--case-sensitive]", file=sys.stderr)
        sys.exit(1)

    term = sys.argv[1]
    case_sensitive = "--case-sensitive" in sys.argv
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(term, flags)
    except re.error as e:
        print(f"Invalid regex: {e}", file=sys.stderr)
        sys.exit(1)

    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        print("No projects directory found.", file=sys.stderr)
        sys.exit(1)

    results = []

    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        cwd = dir_to_path(project_dir.name)

        for jsonl_file in project_dir.glob("*.jsonl"):
            title, match = scan_file(jsonl_file, pattern)
            if match is not None:
                conv_id = jsonl_file.stem
                mtime = jsonl_file.stat().st_mtime
                results.append((mtime, cwd, conv_id, title, match))

    if not results:
        print(f"No conversations found matching: {term}")
        sys.exit(0)

    # Sort newest first
    results.sort(reverse=True)

    color = Color()

    def show(text, prefix):
        for line in text.splitlines() or [text]:
            print(f"{prefix}{color.highlight(line, pattern)}")

    print(f"Found {len(results)} conversation(s) matching '{color.highlight(term, pattern)}':\n")
    for i, (mtime, cwd, conv_id, title, match) in enumerate(results, 1):
        print(color.bold(f"{i}. cd {shlex.quote(cwd)} && claude --resume {conv_id}"))
        show(title or "(no title)", "   ")
        if match != title:
            print()
            show(match, f"   {color.chevron()} ")
        print()


if __name__ == "__main__":
    main()
