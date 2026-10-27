"""
Test client-side filtering of non-accepted submissions.

This verifies that the fix for HTTP 400 (removing server-side status filter)
works correctly with client-side filtering.
"""

import pytest
import responses as resp_lib

from src.leetcode_client import LeetCodeClient


def _make_client(session="fake-session", csrf="fake-csrf"):
    return LeetCodeClient(
        username="testuser",
        session_cookie=session,
        csrf_token=csrf,
        fetch_limit=5,
    )


def _make_submission_list_response(submissions: list[dict]) -> dict:
    return {
        "data": {
            "submissionList": {
                "lastKey": None,
                "hasNext": False,
                "submissions": submissions,
            }
        }
    }


def _make_detail_response(
    code="return []",
    runtime_display="48 ms",
    memory_display="16.2 MB",
    difficulty="Easy",
    tags=None,
    problem_id="1",
    slug="two-sum",
    title="Two Sum",
) -> dict:
    return {
        "data": {
            "submissionDetails": {
                "code": code,
                "runtimeDisplay": runtime_display,
                "memoryDisplay": memory_display,
                "timestamp": 1761523200,
                "question": {
                    "questionId": problem_id,
                    "frontendQuestionId": problem_id,
                    "titleSlug": slug,
                    "title": title,
                    "difficulty": difficulty,
                    "topicTags": [{"name": t, "slug": t.lower()} for t in (tags or [])],
                },
                "lang": {"name": "python3", "verboseName": "Python 3"},
                "notes": "",
            }
        }
    }


_GQL_URL = "https://leetcode.com/graphql"


class TestClientSideFiltering:
    """Test that client-side filtering correctly handles mixed submission statuses."""

    @resp_lib.activate
    def test_filters_out_wrong_answer_submissions(self):
        """Non-accepted submissions should be filtered out client-side."""
        submissions = [
            {
                "id": "111",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "status": "WA",
                "statusDisplay": "Wrong Answer",
                "lang": "python3",
                "langName": "Python 3",
                "timestamp": "1761523200",
            },
            {
                "id": "222",
                "title": "Add Two Numbers",
                "titleSlug": "add-two-numbers",
                "status": "AC",
                "statusDisplay": "Accepted",
                "lang": "python3",
                "langName": "Python 3",
                "timestamp": "1761523300",
            },
        ]

        # First call: submission list with mixed statuses
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response(submissions),
            status=200,
        )
        # Second call: submission detail for the accepted one
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_detail_response(
                problem_id="2",
                slug="add-two-numbers",
                title="Add Two Numbers",
            ),
            status=200,
        )

        client = _make_client()
        records = client.fetch_recent_accepted_submissions()

        # Should only return the accepted submission
        assert len(records) == 1
        assert records[0].submission_id == "222"
        assert records[0].problem_title == "Add Two Numbers"

    @resp_lib.activate
    def test_filters_out_time_limit_exceeded(self):
        """Time Limit Exceeded submissions should be filtered out."""
        submissions = [
            {
                "id": "333",
                "title": "Problem A",
                "titleSlug": "problem-a",
                "status": "TLE",
                "statusDisplay": "Time Limit Exceeded",
                "lang": "java",
                "timestamp": "1761523400",
            },
        ]

        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response(submissions),
            status=200,
        )

        client = _make_client()
        records = client.fetch_recent_accepted_submissions()

        # Should return empty list
        assert len(records) == 0

    @resp_lib.activate
    def test_accepts_both_ac_status_and_accepted_display(self):
        """Accept submissions with either status=AC or statusDisplay=Accepted."""
        submissions = [
            {
                "id": "444",
                "title": "Problem B",
                "titleSlug": "problem-b",
                "status": "AC",
                "statusDisplay": "Accepted",
                "lang": "cpp",
                "timestamp": "1761523500",
            },
            {
                "id": "555",
                "title": "Problem C",
                "titleSlug": "problem-c",
                "status": "10",  # Sometimes status is numeric
                "statusDisplay": "Accepted",
                "lang": "python3",
                "timestamp": "1761523600",
            },
        ]

        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response(submissions),
            status=200,
        )
        # Two detail calls
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_detail_response(
                problem_id="100",
                slug="problem-b",
                title="Problem B",
            ),
            status=200,
        )
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_detail_response(
                problem_id="101",
                slug="problem-c",
                title="Problem C",
            ),
            status=200,
        )

        client = _make_client()
        records = client.fetch_recent_accepted_submissions()

        # Should return both accepted submissions
        assert len(records) == 2
        assert records[0].submission_id == "444"
        assert records[1].submission_id == "555"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
