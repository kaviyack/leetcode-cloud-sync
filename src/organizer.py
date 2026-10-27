"""Categorizes submissions by difficulty and determines file/directory paths."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

DIFFICULTY_DIRS = {
    "easy": "easy",
    "medium": "medium",
    "hard": "hard",
}


@dataclass
class SubmissionRecord:
    """Normalized representation of a single LeetCode submission."""

    submission_id: str          # Unique LeetCode submission ID (string)
    problem_id: int             # Problem number (e.g. 6)
    problem_title: str          # Human-readable title (e.g. "Zigzag Conversion")
    problem_slug: str           # URL slug (e.g. "zigzag-conversion")
    difficulty: str             # "Easy" | "Medium" | "Hard" | "Unknown"
    language: str               # e.g. "python3", "java", "cpp"
    status: str                 # e.g. "Accepted", "Wrong Answer"
    timestamp: int              # Unix epoch (seconds)
    code: Optional[str] = None
    runtime: Optional[str] = None
    memory: Optional[str] = None
    topic_tags: list[str] = None
    url: Optional[str] = None

    def __post_init__(self) -> None:
        if self.topic_tags is None:
            self.topic_tags = []
        # Normalise difficulty to title-case; fall back to "Unknown".
        self.difficulty = _normalise_difficulty(self.difficulty)


def _normalise_difficulty(raw: str) -> str:
    mapping = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}
    return mapping.get(raw.strip().lower(), "Unknown")


def difficulty_dir(difficulty: str) -> str:
    """Return the directory name for a given difficulty string."""
    return DIFFICULTY_DIRS.get(difficulty.lower(), "unknown")


def problem_slug_from_title(title: str) -> str:
    """
    Generate a URL-style slug from a problem title.
    Matches LeetCode's own slug format where possible.
    """
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def problem_dir_name(problem_id: int, slug: str) -> str:
    """Return padded directory name, e.g. '0006-zigzag-conversion'."""
    return f"{problem_id:04d}-{slug}"


def submission_filename(record: SubmissionRecord) -> str:
    """
    Return a filename for a submission Markdown file.

    Format: <ISO-date>_<HHMM>_<lang>_<submission_id>.md
    Example: 20261026_2015_python3_1234567890.md

    Using submission_id as part of the filename guarantees no collisions
    between repeated attempts at the same problem in the same language.
    """
    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(record.timestamp, tz=timezone.utc)
    date_part = dt.strftime("%Y%m%d_%H%M")
    lang_safe = re.sub(r"[^a-z0-9]", "", record.language.lower())
    return f"{date_part}_{lang_safe}_{record.submission_id}.md"


def submission_path(record: SubmissionRecord, solutions_root: str = "solutions") -> str:
    """
    Return the full relative repository path for a submission file.

    Example:
      solutions/medium/0006-zigzag-conversion/20261026_2015_python3_123456.md
    """
    diff = difficulty_dir(record.difficulty)
    slug = record.problem_slug or problem_slug_from_title(record.problem_title)
    dir_name = problem_dir_name(record.problem_id, slug)
    filename = submission_filename(record)
    return f"{solutions_root}/{diff}/{dir_name}/{filename}"
