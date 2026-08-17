"""Search Claude conversation history."""

import json
import os
import re
import shlex
import time
from dataclasses import dataclass
from pathlib import Path


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


SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)


def dir_to_path(dirname):
    """Convert a Claude project directory name back to a filesystem path."""
    s = dirname.lstrip("-")
    s = "-" + s
    s = s.replace("--", "/.")
    return s.replace("-", "/")


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


def compile_pattern(term, case_sensitive=False):
    """Validate and compile a user-supplied search pattern."""
    if not term:
        raise InvalidSearchTerm("Search term cannot be empty.")
    if len(term) > MAX_TERM_LENGTH:
        raise InvalidSearchTerm("Search term must be 500 characters or fewer.")

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        return re.compile(term, flags)
    except re.error as error:
        raise InvalidSearchTerm(f"Invalid regex: {error}") from error


def highlight_segments(text, pattern):
    """Split text into highlighted and unhighlighted regex-match segments."""
    segments = []
    position = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        if start > position:
            segments.append(HighlightSegment(text[position:start], False))
        if start != end:
            segments.append(HighlightSegment(text[start:end], True))
        position = end

    if position < len(text):
        segments.append(HighlightSegment(text[position:], False))
    if not segments:
        return (HighlightSegment(text, False),)
    return tuple(segments)


def user_texts(jsonl_path):
    """Yield text the user actually typed, in order."""
    try:
        with open(jsonl_path, errors="replace") as file:
            for line in file:
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
                        block["text"]
                        for block in content
                        if isinstance(block, dict) and block.get("type") == "text"
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
    """Return the first user message and its first matching user message."""
    title = None
    for text in user_texts(jsonl_path):
        if title is None:
            title = text
        if pattern.search(text):
            return title, text
    return title, None


def transcript_cwd(jsonl_path):
    """Return top-level transcript cwd metadata when it is available."""
    try:
        with open(jsonl_path, errors="replace") as file:
            for line in file:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cwd = obj.get("cwd")
                if isinstance(cwd, str):
                    return cwd
    except (IOError, OSError):
        pass
    return None


def path_matches_prefix(path, path_prefix):
    """Return whether a path is the prefix or a descendant of the prefix."""
    normalized_prefix = os.path.normpath(path_prefix)
    try:
        return os.path.commonpath((path, normalized_prefix)) == normalized_prefix
    except ValueError:
        return False


def search(
    term,
    case_sensitive=False,
    projects_dir=None,
    now=None,
    path_prefix=None,
) -> list[SearchResult]:
    """Return newest-first SearchResult values for a user-message regex."""
    pattern = compile_pattern(term, case_sensitive=case_sensitive)
    if projects_dir is None:
        projects_dir = Path.home() / ".claude" / "projects"
    else:
        projects_dir = Path(projects_dir)
    if not projects_dir.exists():
        raise ProjectsDirectoryNotFound

    matches = []
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        decoded_cwd = dir_to_path(project_dir.name)
        for jsonl_file in project_dir.glob("*.jsonl"):
            cwd = transcript_cwd(jsonl_file)
            if cwd is None:
                cwd = decoded_cwd
            if path_prefix and not path_matches_prefix(cwd, path_prefix):
                continue
            title, match = scan_file(jsonl_file, pattern)
            if match is not None:
                matches.append((
                    jsonl_file.stat().st_mtime,
                    cwd,
                    jsonl_file.stem,
                    title,
                    match,
                ))

    current_time = time.time() if now is None else now
    results = []
    for mtime, cwd, conv_id, title, match in sorted(matches, reverse=True):
        results.append(SearchResult(
            mtime=mtime,
            cwd=cwd,
            conv_id=conv_id,
            title=title,
            match=match,
            relative_date=time_ago(current_time - mtime),
            resume_command=f"cd {shlex.quote(cwd)} && claude --resume {conv_id}",
            title_segments=highlight_segments(title, pattern),
            match_segments=highlight_segments(match, pattern),
        ))
    return results
