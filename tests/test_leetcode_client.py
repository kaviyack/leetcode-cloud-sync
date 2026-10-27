"""
Tests for LeetCodeClient using mocked HTTP responses.

No real credentials are used. All LeetCode API calls are intercepted
by the `responses` library.
"""

from __future__ import annotations

import pytest
import responses as resp_lib

from src.leetcode_client import AuthError, LeetCodeAPIError, LeetCodeClient


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

_RAW_SUB = {
    "id": "123456789",
    "title": "Two Sum",
    "titleSlug": "two-sum",
    "status": "AC",
    "statusDisplay": "Accepted",
    "lang": "python3",
    "langName": "Python 3",
    "runtime": "48 ms",
    "timestamp": "1761523200",
    "url": "/submissions/detail/123456789/",
    "isPending": "Not Pending",
    "memory": "16.2 MB",
    "submissionComment": None,
}


# ---------------------------------------------------------------------------
# 11. Expired / missing authentication
# ---------------------------------------------------------------------------

class TestAuth:
    def test_no_session_raises_auth_error(self):
        client = LeetCodeClient(username="u", session_cookie=None, csrf_token=None)
        with pytest.raises(AuthError, match="LEETCODE_SESSION"):
            client.fetch_recent_accepted_submissions()

    @resp_lib.activate
    def test_403_raises_auth_error(self):
        resp_lib.add(resp_lib.POST, _GQL_URL, status=403, body="Forbidden")
        client = _make_client()
        with pytest.raises(AuthError, match="403"):
            client.fetch_recent_accepted_submissions()

    @resp_lib.activate
    def test_graphql_auth_error_in_errors_array(self):
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json={"errors": [{"message": "Please login first"}]},
            status=200,
        )
        client = _make_client()
        with pytest.raises(AuthError, match="login"):
            client.fetch_recent_accepted_submissions()


# ---------------------------------------------------------------------------
# 10. API failures and malformed responses
# ---------------------------------------------------------------------------

class TestAPIFailures:
    @resp_lib.activate
    def test_429_raises_api_error(self):
        resp_lib.add(resp_lib.POST, _GQL_URL, status=429, body="Too Many Requests")
        client = _make_client()
        with pytest.raises(LeetCodeAPIError, match="429"):
            client.fetch_recent_accepted_submissions()

    @resp_lib.activate
    def test_invalid_json_raises_api_error(self):
        resp_lib.add(resp_lib.POST, _GQL_URL, status=200, body="NOT JSON {{{")
        client = _make_client()
        with pytest.raises(LeetCodeAPIError, match="JSON"):
            client.fetch_recent_accepted_submissions()

    @resp_lib.activate
    def test_null_submission_list_raises_auth_error(self):
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json={"data": {"submissionList": None}},
            status=200,
        )
        client = _make_client()
        with pytest.raises(AuthError, match="null"):
            client.fetch_recent_accepted_submissions()

    @resp_lib.activate
    def test_graphql_non_auth_error(self):
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json={"errors": [{"message": "Internal server error"}]},
            status=200,
        )
        client = _make_client()
        with pytest.raises(LeetCodeAPIError):
            client.fetch_recent_accepted_submissions()

    @resp_lib.activate
    def test_http_400_raises_api_error(self):
        """Test that HTTP 400 errors are properly reported."""
        resp_lib.add(resp_lib.POST, _GQL_URL, status=400, body="Bad Request")
        client = _make_client()
        with pytest.raises(LeetCodeAPIError, match="HTTP 400"):
            client.fetch_recent_accepted_submissions()


# ---------------------------------------------------------------------------
# Happy-path submission fetching
# ---------------------------------------------------------------------------

class TestFetchSubmissions:
    @resp_lib.activate
    def test_empty_submission_list(self):
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response([]),
            status=200,
        )
        client = _make_client()
        result = client.fetch_recent_accepted_submissions()
        assert result == []

    @resp_lib.activate
    def test_single_accepted_submission(self):
        # First call: submission list
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response([_RAW_SUB]),
            status=200,
        )
        # Second call: submission detail
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_detail_response(tags=["Array", "Hash Table"]),
            status=200,
        )
        client = _make_client()
        records = client.fetch_recent_accepted_submissions()
        assert len(records) == 1
        r = records[0]
        assert r.submission_id == "123456789"
        assert r.problem_title == "Two Sum"
        assert r.difficulty == "Easy"
        assert r.code == "return []"

    @resp_lib.activate
    def test_detail_failure_skips_submission_gracefully(self):
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response([_RAW_SUB]),
            status=200,
        )
        # Detail call returns 500
        resp_lib.add(resp_lib.POST, _GQL_URL, status=500, body="error")
        client = _make_client()
        records = client.fetch_recent_accepted_submissions()
        # Should return the record with code=None, not crash
        assert len(records) == 1
        assert records[0].code is None

    @resp_lib.activate
    def test_topic_tags_populated(self):
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response([_RAW_SUB]),
            status=200,
        )
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_detail_response(tags=["Dynamic Programming", "Memoization"]),
            status=200,
        )
        client = _make_client()
        records = client.fetch_recent_accepted_submissions()
        assert "Dynamic Programming" in records[0].topic_tags

    @resp_lib.activate
    def test_missing_id_skips_submission(self):
        bad_sub = {**_RAW_SUB, "id": ""}
        resp_lib.add(
            resp_lib.POST,
            _GQL_URL,
            json=_make_submission_list_response([bad_sub]),
            status=200,
        )
        client = _make_client()
        records = client.fetch_recent_accepted_submissions()
        assert records == []
