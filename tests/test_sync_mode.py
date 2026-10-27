"""
Tests for configurable sync mode (accepted vs all submissions).
"""

import pytest
import responses as resp_lib

from src.leetcode_client import LeetCodeClient


def _make_client(session="fake-session", csrf="fake-csrf", sync_mode="accepted"):
    return LeetCodeClient(
        username="testuser",
        session_cookie=session,
        csrf_token=csrf,
        fetch_limit=5,
        sync_mode=sync_mode,
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


class TestSyncModeAccepted:
    """Test sync_mode='accepted' filters out non-accepted submissions."""

    @resp_lib.activate
    def test_filters_out_wrong_answer(self):
        submissions = [
            {
                "id": "111",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "status": "WA",
                "statusDisplay": "Wrong Answer",
                "lang": "python3",
                "timestamp": "1761523200",
            },
            {
                "id": "222",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "status": "AC",
                "statusDisplay": "Accepted",
                "lang": "python3",
                "timestamp": "1761523300",
            },
        ]

        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response(submissions),
            status=200,
        )
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_detail_response(),
            status=200,
        )

        client = _make_client(sync_mode="accepted")
        records = client.fetch_recent_accepted_submissions()

        assert len(records) == 1
        assert records[0].submission_id == "222"
        assert records[0].status == "Accepted"

    @resp_lib.activate
    def test_filters_out_time_limit_exceeded(self):
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

        client = _make_client(sync_mode="accepted")
        records = client.fetch_recent_accepted_submissions()

        assert len(records) == 0


class TestSyncModeAll:
    """Test sync_mode='all' preserves all submission statuses."""

    @resp_lib.activate
    def test_includes_wrong_answer(self):
        submissions = [
            {
                "id": "111",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "status": "WA",
                "statusDisplay": "Wrong Answer",
                "lang": "python3",
                "timestamp": "1761523200",
            },
        ]

        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response(submissions),
            status=200,
        )
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_detail_response(),
            status=200,
        )

        client = _make_client(sync_mode="all")
        records = client.fetch_recent_accepted_submissions()

        assert len(records) == 1
        assert records[0].submission_id == "111"
        assert records[0].status == "Wrong Answer"

    @resp_lib.activate
    def test_includes_time_limit_exceeded(self):
        submissions = [
            {
                "id": "222",
                "title": "Problem B",
                "titleSlug": "problem-b",
                "status": "TLE",
                "statusDisplay": "Time Limit Exceeded",
                "lang": "java",
                "timestamp": "1761523300",
            },
        ]

        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response(submissions),
            status=200,
        )
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_detail_response(),
            status=200,
        )

        client = _make_client(sync_mode="all")
        records = client.fetch_recent_accepted_submissions()

        assert len(records) == 1
        assert records[0].submission_id == "222"
        assert records[0].status == "Time Limit Exceeded"

    @resp_lib.activate
    def test_includes_runtime_error(self):
        submissions = [
            {
                "id": "333",
                "title": "Problem C",
                "titleSlug": "problem-c",
                "status": "RE",
                "statusDisplay": "Runtime Error",
                "lang": "cpp",
                "timestamp": "1761523400",
            },
        ]

        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response(submissions),
            status=200,
        )
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_detail_response(),
            status=200,
        )

        client = _make_client(sync_mode="all")
        records = client.fetch_recent_accepted_submissions()

        assert len(records) == 1
        assert records[0].submission_id == "333"
        assert records[0].status == "Runtime Error"

    @resp_lib.activate
    def test_includes_compilation_error(self):
        submissions = [
            {
                "id": "444",
                "title": "Problem D",
                "titleSlug": "problem-d",
                "status": "CE",
                "statusDisplay": "Compilation Error",
                "lang": "java",
                "timestamp": "1761523500",
            },
        ]

        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response(submissions),
            status=200,
        )
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_detail_response(),
            status=200,
        )

        client = _make_client(sync_mode="all")
        records = client.fetch_recent_accepted_submissions()

        assert len(records) == 1
        assert records[0].submission_id == "444"
        assert records[0].status == "Compilation Error"

    @resp_lib.activate
    def test_mixed_statuses_all_preserved(self):
        """Test that all submission statuses are preserved in 'all' mode."""
        submissions = [
            {
                "id": "111",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "status": "AC",
                "statusDisplay": "Accepted",
                "lang": "python3",
                "timestamp": "1761523100",
            },
            {
                "id": "222",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "status": "WA",
                "statusDisplay": "Wrong Answer",
                "lang": "python3",
                "timestamp": "1761523200",
            },
            {
                "id": "333",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "status": "TLE",
                "statusDisplay": "Time Limit Exceeded",
                "lang": "python3",
                "timestamp": "1761523300",
            },
        ]

        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response(submissions),
            status=200,
        )
        # Three detail calls
        for _ in range(3):
            resp_lib.add(
                resp_lib.POST,
                _GQL_URL,
                json=_make_detail_response(),
                status=200,
            )

        client = _make_client(sync_mode="all")
        records = client.fetch_recent_accepted_submissions()

        assert len(records) == 3
        assert {r.submission_id for r in records} == {"111", "222", "333"}
        assert {r.status for r in records} == {"Accepted", "Wrong Answer", "Time Limit Exceeded"}


class TestDuplicateHandling:
    """Test that duplicate attempts with identical code are preserved separately."""

    @resp_lib.activate
    def test_identical_code_different_ids_both_preserved(self):
        """Two submissions with identical code but different IDs should both be returned."""
        submissions = [
            {
                "id": "111",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "status": "AC",
                "statusDisplay": "Accepted",
                "lang": "python3",
                "timestamp": "1761523100",
            },
            {
                "id": "222",
                "title": "Two Sum",
                "titleSlug": "two-sum",
                "status": "AC",
                "statusDisplay": "Accepted",
                "lang": "python3",
                "timestamp": "1761523200",
            },
        ]

        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response(submissions),
            status=200,
        )
        # Both submissions have identical code
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_detail_response(code="def solution(): return 42"),
            status=200,
        )
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_detail_response(code="def solution(): return 42"),
            status=200,
        )

        client = _make_client(sync_mode="all")
        records = client.fetch_recent_accepted_submissions()

        assert len(records) == 2
        assert records[0].submission_id == "111"
        assert records[1].submission_id == "222"
        assert records[0].code == records[1].code


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
