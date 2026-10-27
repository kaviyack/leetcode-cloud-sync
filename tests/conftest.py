"""Shared test fixtures and helpers."""

from __future__ import annotations

from src.organizer import SubmissionRecord


def make_record(
    submission_id: str = "111111111",
    problem_id: int = 1,
    problem_title: str = "Two Sum",
    problem_slug: str = "two-sum",
    difficulty: str = "Easy",
    language: str = "python3",
    status: str = "Accepted",
    timestamp: int = 1761523200,  # 2025-10-26 20:00:00 UTC
    code: str = "return []",
    runtime: str = "48 ms",
    memory: str = "16.2 MB",
    topic_tags: list[str] | None = None,
    url: str | None = None,
) -> SubmissionRecord:
    return SubmissionRecord(
        submission_id=submission_id,
        problem_id=problem_id,
        problem_title=problem_title,
        problem_slug=problem_slug,
        difficulty=difficulty,
        language=language,
        status=status,
        timestamp=timestamp,
        code=code,
        runtime=runtime,
        memory=memory,
        topic_tags=topic_tags if topic_tags is not None else ["Array", "Hash Table"],
        url=url or f"https://leetcode.com/problems/{problem_slug}/",
    )
