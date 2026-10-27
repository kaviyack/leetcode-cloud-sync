"""Formats submission records as Markdown files."""

from __future__ import annotations

from datetime import datetime, timezone

from .organizer import SubmissionRecord

# Language → Markdown fence identifier map
_LANG_FENCE = {
    "python3": "python",
    "python": "python",
    "java": "java",
    "cpp": "cpp",
    "c": "c",
    "csharp": "csharp",
    "javascript": "javascript",
    "typescript": "typescript",
    "golang": "go",
    "go": "go",
    "rust": "rust",
    "kotlin": "kotlin",
    "swift": "swift",
    "scala": "scala",
    "ruby": "ruby",
    "php": "php",
    "bash": "bash",
    "mysql": "sql",
    "mssql": "sql",
    "oraclesql": "sql",
}


def _fence_id(language: str) -> str:
    return _LANG_FENCE.get(language.lower(), language.lower())


def _fmt_timestamp(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def render_submission(record: SubmissionRecord) -> str:
    """
    Render a SubmissionRecord as a Markdown string.

    All metadata fields are included when available.
    Missing optional fields are noted explicitly rather than silently omitted.
    Full problem statements are NOT included — only an original summary/link
    is provided to respect LeetCode's content restrictions.
    """
    lines: list[str] = []

    # Header
    title_str = f"#{record.problem_id} {record.problem_title}"
    lines.append(f"# {title_str}")
    lines.append("")

    # Metadata table
    problem_url = (
        record.url
        or f"https://leetcode.com/problems/{record.problem_slug}/"
    )
    lines.append("## Submission Metadata")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| **Problem** | [{title_str}]({problem_url}) |")
    lines.append(f"| **Difficulty** | {record.difficulty} |")
    lines.append(
        "| **Topics** | "
        + (", ".join(record.topic_tags) if record.topic_tags else "_Not available_")
        + " |"
    )
    lines.append(f"| **Language** | {record.language} |")
    lines.append(f"| **Submission ID** | {record.submission_id} |")
    lines.append(f"| **Submitted At** | {_fmt_timestamp(record.timestamp)} |")
    lines.append(f"| **Status** | {record.status} |")
    lines.append(
        "| **Runtime** | "
        + (record.runtime if record.runtime else "_Not available_")
        + " |"
    )
    lines.append(
        "| **Memory** | "
        + (record.memory if record.memory else "_Not available_")
        + " |"
    )
    lines.append("")

    # Problem summary note (NOT the full statement — redistribution not permitted)
    lines.append("## Problem")
    lines.append("")
    lines.append(
        f"> Full problem statement: [{title_str}]({problem_url})"
    )
    lines.append(">")
    lines.append(
        "> _LeetCode problem statements are not redistributed here. "
        "Visit the link above for the full description._"
    )
    lines.append("")

    # Solution code
    lines.append("## Solution")
    lines.append("")
    fence = _fence_id(record.language)
    if record.code:
        lines.append(f"```{fence}")
        lines.append(record.code)
        lines.append("```")
    else:
        lines.append(
            "_Source code is not available. "
            "Ensure `LEETCODE_SESSION` and `LEETCODE_CSRF_TOKEN` "
            "are configured to retrieve submission code._"
        )
    lines.append("")

    # Complexity section (clearly marked as estimates unless confirmed)
    lines.append("## Complexity")
    lines.append("")
    lines.append(
        "_Time and space complexity are not automatically determined. "
        "Edit this file to add your own analysis._"
    )
    lines.append("")

    # Footer
    lines.append("---")
    lines.append(
        "_Synced automatically by "
        "[LeetCode Cloud Sync](https://github.com/kaviyack/leetcode-cloud-sync)_"
    )
    lines.append("")

    return "\n".join(lines)
