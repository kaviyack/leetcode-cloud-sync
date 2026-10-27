"""
Tests for GitHubClient — validation, read_file, update_file, and security.

All HTTP requests are mocked with the `responses` library.
No real network access, no real tokens.
"""

from __future__ import annotations

import base64
import json

import pytest
import responses as resp_lib

from src.github_client import GitHubAPIError, GitHubClient


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


class TestGitHubClientValidation:
    def test_invalid_repo_format_raises(self):
        with pytest.raises(ValueError, match="Invalid GITHUB_REPO"):
            GitHubClient(token="tok", repo="no-slash-here", branch="main")

    def test_invalid_repo_empty_raises(self):
        with pytest.raises(ValueError):
            GitHubClient(token="tok", repo="", branch="main")

    def test_invalid_branch_raises(self):
        with pytest.raises(ValueError, match="Invalid GITHUB_BRANCH"):
            GitHubClient(token="tok", repo="owner/repo", branch="branch with spaces")

    def test_valid_repo_and_branch_accepted(self):
        # Should not raise
        client = GitHubClient(token="tok", repo="owner/my-repo", branch="feature/my-fix")
        assert client is not None

    def test_token_not_in_exception_message(self):
        """Token must never appear in GitHubAPIError messages."""
        secret = "ghp_supersecret"
        client = GitHubClient(token=secret, repo="owner/repo", branch="main")
        with resp_lib.RequestsMock() as rsps:
            rsps.add(resp_lib.GET, "https://api.github.com/repos/owner/repo/contents/f.md",
                     status=500, body="server error")
            try:
                client.file_exists("f.md")
            except GitHubAPIError as exc:
                assert secret not in str(exc)


class TestGitHubClientReadFile:
    @resp_lib.activate
    def test_read_file_returns_content_and_sha(self):
        body = {"content": _b64("hello world") + "\n", "sha": "deadbeef"}
        resp_lib.add(resp_lib.GET,
                     "https://api.github.com/repos/owner/repo/contents/state.json",
                     json=body, status=200)
        client = GitHubClient(token="tok", repo="owner/repo", branch="main")
        result = client.read_file("state.json")
        assert result is not None
        content, sha = result
        assert content == "hello world"
        assert sha == "deadbeef"

    @resp_lib.activate
    def test_read_file_returns_none_on_404(self):
        resp_lib.add(resp_lib.GET,
                     "https://api.github.com/repos/owner/repo/contents/state.json",
                     status=404, json={"message": "Not Found"})
        client = GitHubClient(token="tok", repo="owner/repo", branch="main")
        result = client.read_file("state.json")
        assert result is None

    @resp_lib.activate
    def test_read_file_raises_on_unexpected_status(self):
        resp_lib.add(resp_lib.GET,
                     "https://api.github.com/repos/owner/repo/contents/state.json",
                     status=500, body="oops")
        client = GitHubClient(token="tok", repo="owner/repo", branch="main")
        with pytest.raises(GitHubAPIError, match="500"):
            client.read_file("state.json")


class TestGitHubClientUpdateFile:
    @resp_lib.activate
    def test_update_file_sends_sha(self):
        resp_lib.add(resp_lib.PUT,
                     "https://api.github.com/repos/owner/repo/contents/state.json",
                     json={"content": {}, "commit": {}}, status=200)
        client = GitHubClient(token="tok", repo="owner/repo", branch="main")
        client.update_file(
            path="state.json",
            content='{"synced_ids": ["A"]}',
            sha="abc123",
            commit_message="sync: update state",
            author_name="Bot",
            author_email="bot@example.com",
        )
        req_body = json.loads(resp_lib.calls[0].request.body)
        assert req_body["sha"] == "abc123"
        assert "content" in req_body

    @resp_lib.activate
    def test_update_file_raises_on_failure(self):
        resp_lib.add(resp_lib.PUT,
                     "https://api.github.com/repos/owner/repo/contents/state.json",
                     status=422, json={"message": "sha mismatch"})
        client = GitHubClient(token="tok", repo="owner/repo", branch="main")
        with pytest.raises(GitHubAPIError, match="422"):
            client.update_file(
                path="state.json",
                content="{}",
                sha="wrong_sha",
                commit_message="test",
                author_name="Bot",
                author_email="bot@example.com",
            )
