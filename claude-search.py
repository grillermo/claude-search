#!/usr/bin/env python3
"""shh - Search Claude conversation history across all projects."""

import os
import sys
from claude_search import (
    InvalidSearchTerm,
    ProjectsDirectoryNotFound,
    compile_pattern,
    search,
)


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


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: shh <search_term> [--case-sensitive] [--path PATH]",
            file=sys.stderr,
        )
        sys.exit(1)

    term = sys.argv[1]
    option_args = sys.argv[2:]
    case_sensitive = "--case-sensitive" in option_args
    path_prefix = None
    if "--path" in option_args:
        path_index = option_args.index("--path")
        if path_index + 1 >= len(option_args) or option_args[path_index + 1].startswith("--"):
            print(
                "Usage: shh <search_term> [--case-sensitive] [--path PATH]",
                file=sys.stderr,
            )
            sys.exit(1)
        path_prefix = option_args[path_index + 1]
    try:
        pattern = compile_pattern(term, case_sensitive=case_sensitive)
    except InvalidSearchTerm as error:
        print(error, file=sys.stderr)
        sys.exit(1)

    try:
        results = search(
            term,
            case_sensitive=case_sensitive,
            path_prefix=path_prefix,
        )
    except ProjectsDirectoryNotFound:
        print("No projects directory found.", file=sys.stderr)
        sys.exit(1)

    if not results:
        print(f"No conversations found matching: {term}")
        sys.exit(0)

    color = Color()

    def show(text, prefix):
        for line in text.splitlines() or [text]:
            print(f"{prefix}{color.highlight(line, pattern)}")

    print(f"Found {len(results)} conversation(s) matching '{color.highlight(term, pattern)}':\n")
    for i, result in enumerate(results, 1):
        print(color.bold(f"{i}. {result.relative_date} · {result.resume_command}"))
        show(result.title, "   ")
        if result.match != result.title:
            print()
            show(result.match, f"   {color.chevron()} ")
        print()


if __name__ == "__main__":
    main()
