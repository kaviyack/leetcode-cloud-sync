"""Configuration loading and validation for LeetCode Cloud Sync."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass
class Config:
    leetcode_username: str
    github_token: str
    github_repo: str  # "owner/repo"
    github_branch: str = "main"
    solutions_root: str = "solutions"
    # LeetCode session cookie (LEETCODE_SESSION) — required for submission data.
    # This is a browser-extracted cookie value. Treat as a secret.
    leetcode_session: Optional[str] = None
    # CSRF token paired with the session cookie.
    leetcode_csrf: Optional[str] = None
    # How many submissions to fetch per API call.
    fetch_limit: int = 20
    # Sync mode: 'accepted' (only accepted) or 'all' (all submission attempts)
    sync_mode: str = "accepted"
    # Committer identity for automated commits.
    git_author_name: str = "Kaviyavarshini"
    git_author_email: str = "kaviyack2005@gmail.com"
    log_level: str = "INFO"
    # Additional field for any optional env overrides.
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Config":
        """Load and validate configuration from environment variables."""
        errors: list[str] = []

        leetcode_username = os.environ.get("LEETCODE_USERNAME", "").strip()
        if not leetcode_username:
            errors.append("LEETCODE_USERNAME is required.")

        github_token = os.environ.get("GITHUB_TOKEN", "").strip()
        if not github_token:
            errors.append("GITHUB_TOKEN is required.")

        github_repo = os.environ.get("GITHUB_REPO", "").strip()
        if not github_repo:
            errors.append(
                "GITHUB_REPO is required (format: owner/repo, "
                "e.g. kaviyack/leetcode-cloud-sync)."
            )
        elif "/" not in github_repo:
            errors.append(
                f"GITHUB_REPO must be in 'owner/repo' format, got: {github_repo!r}."
            )

        if errors:
            raise ConfigError(
                "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        leetcode_session = os.environ.get("LEETCODE_SESSION", "").strip() or None
        leetcode_csrf = os.environ.get("LEETCODE_CSRF_TOKEN", "").strip() or None

        if not leetcode_session:
            logger.warning(
                "LEETCODE_SESSION is not set. Only public submission metadata "
                "will be available (no source code). "
                "Set LEETCODE_SESSION and LEETCODE_CSRF_TOKEN to enable full sync."
            )

        sync_mode = os.environ.get("SYNC_MODE", "accepted").strip().lower()
        if sync_mode not in ("accepted", "all"):
            logger.warning(
                "Invalid SYNC_MODE=%r; using 'accepted'. Valid: 'accepted', 'all'.",
                sync_mode,
            )
            sync_mode = "accepted"

        return cls(
            leetcode_username=leetcode_username,
            github_token=github_token,
            github_repo=github_repo,
            github_branch=os.environ.get("GITHUB_BRANCH", "main").strip(),
            solutions_root=os.environ.get("SOLUTIONS_ROOT", "solutions").strip(),
            leetcode_session=leetcode_session,
            leetcode_csrf=leetcode_csrf,
            fetch_limit=int(os.environ.get("FETCH_LIMIT", "20")),
            sync_mode=sync_mode,
            git_author_name=os.environ.get(
                "GIT_AUTHOR_NAME", "Kaviyavarshini"
            ).strip(),
            git_author_email=os.environ.get(
                "GIT_AUTHOR_EMAIL",
                "kaviyack2005@gmail.com",
            ).strip(),
            log_level=os.environ.get("LOG_LEVEL", "INFO").strip().upper(),
        )

    def has_auth(self) -> bool:
        """Return True if LeetCode session credentials are present."""
        return bool(self.leetcode_session)
