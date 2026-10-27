"""
GitHub repository file operations using the REST API.

Uses the GITHUB_TOKEN (automatically provided in GitHub Actions)
for authenticated writes. Does NOT require a personal access token
for writes within the same repository.
"""

from __future__ import annotations

import base64
import logging
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_REPO_RE = re.compile(r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9_.\-/]+$")


class GitHubAPIError(Exception):
    """Raised on unexpected GitHub API responses."""


def _validate_repo(repo: str) -> None:
    if not _REPO_RE.match(repo):
        raise ValueError(f"Invalid GITHUB_REPO format (expected owner/repo): {repo!r}")


def _validate_branch(branch: str) -> None:
    if not _BRANCH_RE.match(branch):
        raise ValueError(f"Invalid GITHUB_BRANCH (unsafe characters): {branch!r}")


class GitHubClient:
    """
    Thin wrapper around the GitHub Contents API.

    Only the methods needed for upsert-only file writing are implemented.
    No file is ever deleted or overwritten — only new paths are created.
    """

    def __init__(self, token: str, repo: str, branch: str = "main") -> None:
        _validate_repo(repo)
        _validate_branch(branch)
        self._token = token
        self._repo = repo   # "owner/repo"
        self._branch = branch
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "LeetCodeCloudSync/1.0",
            }
        )

    def _url(self, path: str) -> str:
        return f"{_GITHUB_API}/repos/{self._repo}/contents/{path}"

    def file_exists(self, path: str) -> bool:
        """Return True if the file already exists on the target branch."""
        resp = self._session.get(
            self._url(path), params={"ref": self._branch}, timeout=20
        )
        if resp.status_code == 200:
            return True
        if resp.status_code == 404:
            return False
        raise GitHubAPIError(
            f"Unexpected status checking {path}: HTTP {resp.status_code}"
        )

    def read_file(self, path: str) -> Optional[tuple[str, str]]:
        """
        Fetch a file's decoded text content and its SHA.

        Returns (content_str, sha) if found, None if the file does not exist.
        Raises GitHubAPIError on unexpected HTTP errors.
        """
        resp = self._session.get(
            self._url(path), params={"ref": self._branch}, timeout=20
        )
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise GitHubAPIError(
                f"Unexpected status reading {path}: HTTP {resp.status_code}"
            )
        data = resp.json()
        raw = base64.b64decode(data["content"]).decode("utf-8")
        return raw, data["sha"]

    def create_file(
        self,
        path: str,
        content: str,
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> None:
        """
        Create a new file in the repository.

        Raises GitHubAPIError if the file already exists (use file_exists first)
        or if the API call fails.
        """
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        payload: dict = {
            "message": commit_message,
            "content": encoded,
            "branch": self._branch,
            "committer": {"name": author_name, "email": author_email},
            "author": {"name": author_name, "email": author_email},
        }
        resp = self._session.put(self._url(path), json=payload, timeout=30)
        if resp.status_code in (200, 201):
            logger.info("Created: %s", path)
            return
        raise GitHubAPIError(
            f"Failed to create {path}: HTTP {resp.status_code} — {resp.text[:400]}"
        )

    def update_file(
        self,
        path: str,
        content: str,
        sha: str,
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> None:
        """
        Update an existing file in the repository.

        `sha` must be the blob SHA of the current file (from read_file).
        Raises GitHubAPIError on failure.
        """
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        payload: dict = {
            "message": commit_message,
            "content": encoded,
            "sha": sha,
            "branch": self._branch,
            "committer": {"name": author_name, "email": author_email},
            "author": {"name": author_name, "email": author_email},
        }
        resp = self._session.put(self._url(path), json=payload, timeout=30)
        if resp.status_code in (200, 201):
            logger.info("Updated: %s", path)
            return
        raise GitHubAPIError(
            f"Failed to update {path}: HTTP {resp.status_code} — {resp.text[:400]}"
        )

    def write_file_if_new(
        self,
        path: str,
        content: str,
        commit_message: str,
        author_name: str,
        author_email: str,
    ) -> bool:
        """
        Write a file only if it does not already exist.

        Returns True if the file was created, False if it already existed.
        This is the main safety guard against overwriting previous submissions.
        """
        if self.file_exists(path):
            logger.debug("Already exists, skipping: %s", path)
            return False
        self.create_file(path, content, commit_message, author_name, author_email)
        return True
