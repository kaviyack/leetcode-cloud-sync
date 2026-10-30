"""Tests for Config loading and validation."""

from __future__ import annotations

import os

import pytest

from src.config import Config, ConfigError


def _with_env(**kwargs):
    """Context manager that temporarily sets environment variables."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        old = {k: os.environ.get(k) for k in kwargs}
        os.environ.update({k: str(v) for k, v in kwargs.items()})
        try:
            yield
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    return _ctx()


_REQUIRED = {
    "LEETCODE_USERNAME": "testuser",
    "GITHUB_TOKEN": "ghp_fake_token",
    "GITHUB_REPO": "testuser/test-repo",
}


class TestConfigFromEnv:
    def test_valid_config_loads(self):
        with _with_env(**_REQUIRED):
            config = Config.from_env()
            assert config.leetcode_username == "testuser"
            assert config.github_repo == "testuser/test-repo"

    def test_missing_username_raises(self):
        env = {**_REQUIRED}
        del env["LEETCODE_USERNAME"]
        with _with_env(**env):
            os.environ.pop("LEETCODE_USERNAME", None)
            with pytest.raises(ConfigError, match="LEETCODE_USERNAME"):
                Config.from_env()

    def test_missing_github_token_raises(self):
        env = {**_REQUIRED}
        del env["GITHUB_TOKEN"]
        with _with_env(**env):
            os.environ.pop("GITHUB_TOKEN", None)
            with pytest.raises(ConfigError, match="GITHUB_TOKEN"):
                Config.from_env()

    def test_missing_github_repo_raises(self):
        env = {**_REQUIRED}
        del env["GITHUB_REPO"]
        with _with_env(**env):
            os.environ.pop("GITHUB_REPO", None)
            with pytest.raises(ConfigError, match="GITHUB_REPO"):
                Config.from_env()

    def test_invalid_repo_format_raises(self):
        with _with_env(**{**_REQUIRED, "GITHUB_REPO": "not-a-slash-format"}):
            with pytest.raises(ConfigError, match="owner/repo"):
                Config.from_env()

    def test_no_session_cookie_does_not_raise(self):
        """Absence of LEETCODE_SESSION is valid (but limited functionality)."""
        with _with_env(**_REQUIRED):
            os.environ.pop("LEETCODE_SESSION", None)
            config = Config.from_env()
            assert config.leetcode_session is None
            assert not config.has_auth()

    def test_session_cookie_loaded(self):
        with _with_env(**_REQUIRED, LEETCODE_SESSION="mysession", LEETCODE_CSRF_TOKEN="mycsrf"):
            config = Config.from_env()
            assert config.leetcode_session == "mysession"
            assert config.leetcode_csrf == "mycsrf"
            assert config.has_auth()

    def test_defaults(self):
        with _with_env(**_REQUIRED):
            os.environ.pop("GITHUB_BRANCH", None)
            os.environ.pop("SOLUTIONS_ROOT", None)
            config = Config.from_env()
            assert config.github_branch == "main"
            assert config.solutions_root == "solutions"

    def test_git_author_defaults_and_legacy_overrides(self):
        with _with_env(**_REQUIRED):
            # Unset → defaults to noreply email
            os.environ.pop("GIT_AUTHOR_NAME", None)
            os.environ.pop("GIT_AUTHOR_EMAIL", None)
            config = Config.from_env()
            assert config.git_author_name == "Kaviyavarshini"
            assert config.git_author_email == "153267681+kaviyack@users.noreply.github.com"

            # Legacy bot or gmail identity in env → overridden to noreply email
            os.environ["GIT_AUTHOR_NAME"] = "LeetCode Cloud Sync"
            os.environ["GIT_AUTHOR_EMAIL"] = "leetcode-cloud-sync@users.noreply.github.com"
            config2 = Config.from_env()
            assert config2.git_author_name == "Kaviyavarshini"
            assert config2.git_author_email == "153267681+kaviyack@users.noreply.github.com"

            os.environ["GIT_AUTHOR_EMAIL"] = "kaviyack2005@gmail.com"
            config2_b = Config.from_env()
            assert config2_b.git_author_email == "153267681+kaviyack@users.noreply.github.com"

            # Custom personal name/email → preserved
            os.environ["GIT_AUTHOR_NAME"] = "Kaviyavarshini Custom"
            os.environ["GIT_AUTHOR_EMAIL"] = "custom@example.com"
            config3 = Config.from_env()
            assert config3.git_author_name == "Kaviyavarshini Custom"
            assert config3.git_author_email == "custom@example.com"

