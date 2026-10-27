"""
Tests for main.run() — orchestration, deduplication, no-commit guard.

GitHub and LeetCode clients are mocked. No real credentials used.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.deduplication import DeduplicationStore, RemoteDeduplicationStore
from tests.conftest import make_record


def _make_config(**overrides):
    from src.config import Config
    defaults = dict(
        leetcode_username="testuser",
        github_token="ghp_fake",
        github_repo="testuser/test-repo",
        github_branch="main",
        solutions_root="solutions",
        leetcode_session="fake-session",
        leetcode_csrf="fake-csrf",
        fetch_limit=20,
        git_author_name="Bot",
        git_author_email="bot@example.com",
    )
    defaults.update(overrides)
    return Config(**defaults)


class TestRunOrchestration:
    def _run_with_mocks(self, submissions, already_seen=None, tmp_path=None):
        from src.main import run

        config = _make_config()
        state_path = str(tmp_path / "state.json") if tmp_path else ":memory:"
        store = DeduplicationStore(state_path=state_path if tmp_path else "/dev/null")
        if already_seen:
            for sid in already_seen:
                store.mark_seen(sid)

        with patch("src.main.LeetCodeClient") as MockLC, \
             patch("src.main.GitHubClient") as MockGH:

            mock_lc = MagicMock()
            mock_lc.fetch_recent_accepted_submissions.return_value = submissions
            MockLC.return_value = mock_lc

            mock_gh = MagicMock()
            mock_gh.write_file_if_new.return_value = True
            MockGH.return_value = mock_gh

            count = run(config, store)
            return count, mock_gh, store

    def test_new_submission_written(self, tmp_path):
        r = make_record(submission_id="NEW1")
        count, mock_gh, store = self._run_with_mocks([r], tmp_path=tmp_path)
        assert count == 1
        mock_gh.write_file_if_new.assert_called_once()

    # 7. Duplicate detection: same submission ID not written twice
    def test_already_seen_submission_skipped(self, tmp_path):
        r = make_record(submission_id="SEEN1")
        count, mock_gh, store = self._run_with_mocks(
            [r], already_seen=["SEEN1"], tmp_path=tmp_path
        )
        assert count == 0
        mock_gh.write_file_if_new.assert_not_called()

    # 13. No commit when no new files
    def test_no_new_submissions_returns_zero(self, tmp_path):
        count, mock_gh, _ = self._run_with_mocks([], tmp_path=tmp_path)
        assert count == 0
        mock_gh.write_file_if_new.assert_not_called()

    # 6. Different IDs for same problem both written
    def test_two_submissions_same_problem_both_written(self, tmp_path):
        r1 = make_record(submission_id="ID_A", problem_id=1, problem_slug="two-sum")
        r2 = make_record(submission_id="ID_B", problem_id=1, problem_slug="two-sum")
        count, mock_gh, _ = self._run_with_mocks([r1, r2], tmp_path=tmp_path)
        assert count == 2
        assert mock_gh.write_file_if_new.call_count == 2

    def test_submission_marked_seen_after_processing(self, tmp_path):
        r = make_record(submission_id="MARK_ME")
        _, _, store = self._run_with_mocks([r], tmp_path=tmp_path)
        assert store.is_seen("MARK_ME")

    # 12. Retry safety: GitHub write failure does not abort remaining submissions
    def test_github_write_failure_continues_other_submissions(self, tmp_path):
        from src.github_client import GitHubAPIError
        from src.main import run

        r1 = make_record(submission_id="FAIL1")
        r2 = make_record(submission_id="OK1", problem_id=2, problem_slug="add-two-numbers")

        config = _make_config()
        store = DeduplicationStore(state_path=str(tmp_path / "state.json"))

        with patch("src.main.LeetCodeClient") as MockLC, \
             patch("src.main.GitHubClient") as MockGH:

            mock_lc = MagicMock()
            mock_lc.fetch_recent_accepted_submissions.return_value = [r1, r2]
            MockLC.return_value = mock_lc

            mock_gh = MagicMock()
            # First call fails, second succeeds
            mock_gh.write_file_if_new.side_effect = [
                GitHubAPIError("network timeout"),
                True,
            ]
            MockGH.return_value = mock_gh

            count = run(config, store)
            # Only the successful write counts
            assert count == 1
            assert mock_gh.write_file_if_new.call_count == 2

    # 11. Auth error propagates with sys.exit
    def test_auth_error_exits_with_code_2(self, tmp_path):
        from src.leetcode_client import AuthError
        from src.main import run

        config = _make_config()
        store = DeduplicationStore(state_path=str(tmp_path / "state.json"))

        with patch("src.main.LeetCodeClient") as MockLC, \
             patch("src.main.GitHubClient"), \
             pytest.raises(SystemExit) as exc_info:

            mock_lc = MagicMock()
            mock_lc.fetch_recent_accepted_submissions.side_effect = AuthError("expired")
            MockLC.return_value = mock_lc

            run(config, store)

        assert exc_info.value.code == 2


class TestRunWithRemoteStore:
    """Tests for run() using RemoteDeduplicationStore (Mode B)."""

    def _make_remote_store(self, already_seen=None):
        store = MagicMock(spec=RemoteDeduplicationStore)
        seen = set(already_seen or [])
        store.is_seen.side_effect = lambda sid: sid in seen
        store.mark_seen.side_effect = lambda sid: seen.add(sid)
        store.save.return_value = None
        return store

    def test_mode_b_new_submission_written(self):
        from src.main import run
        r = make_record(submission_id="MODEB_NEW")
        config = _make_config()
        store = self._make_remote_store()

        with patch("src.main.LeetCodeClient") as MockLC, \
             patch("src.main.GitHubClient") as MockGH:
            mock_lc = MagicMock()
            mock_lc.fetch_recent_accepted_submissions.return_value = [r]
            MockLC.return_value = mock_lc

            mock_gh = MagicMock()
            mock_gh.write_file_if_new.return_value = True
            MockGH.return_value = mock_gh

            count = run(config, store)

        assert count == 1
        store.mark_seen.assert_called_once_with("MODEB_NEW")
        store.save.assert_called_once()

    def test_mode_b_failed_write_not_marked_seen(self):
        """A GitHub API failure must not mark the ID as seen (allows retry)."""
        from src.github_client import GitHubAPIError
        from src.main import run
        r = make_record(submission_id="FAIL_MODEB")
        config = _make_config()
        store = self._make_remote_store()

        with patch("src.main.LeetCodeClient") as MockLC, \
             patch("src.main.GitHubClient") as MockGH:
            mock_lc = MagicMock()
            mock_lc.fetch_recent_accepted_submissions.return_value = [r]
            MockLC.return_value = mock_lc

            mock_gh = MagicMock()
            mock_gh.write_file_if_new.side_effect = GitHubAPIError("timeout")
            MockGH.return_value = mock_gh

            count = run(config, store)

        assert count == 0
        store.mark_seen.assert_not_called()
        store.save.assert_called_once()

    def test_mode_b_already_seen_skipped(self):
        from src.main import run
        r = make_record(submission_id="OLD_MODEB")
        config = _make_config()
        store = self._make_remote_store(already_seen=["OLD_MODEB"])

        with patch("src.main.LeetCodeClient") as MockLC, \
             patch("src.main.GitHubClient") as MockGH:
            mock_lc = MagicMock()
            mock_lc.fetch_recent_accepted_submissions.return_value = [r]
            MockLC.return_value = mock_lc
            mock_gh = MagicMock()
            MockGH.return_value = mock_gh

            count = run(config, store)

        assert count == 0
        mock_gh.write_file_if_new.assert_not_called()

    def test_mode_b_save_called_even_with_no_new_submissions(self):
        from src.main import run
        config = _make_config()
        store = self._make_remote_store()

        with patch("src.main.LeetCodeClient") as MockLC, \
             patch("src.main.GitHubClient") as MockGH:
            mock_lc = MagicMock()
            mock_lc.fetch_recent_accepted_submissions.return_value = []
            MockLC.return_value = mock_lc
            MockGH.return_value = MagicMock()

            run(config, store)

        store.save.assert_called_once()

    def test_mode_b_existing_file_marks_seen_not_counted(self):
        """write_file_if_new returns False (file existed) → not counted, but marked seen."""
        from src.main import run
        r = make_record(submission_id="EXISTS_MODEB")
        config = _make_config()
        store = self._make_remote_store()

        with patch("src.main.LeetCodeClient") as MockLC, \
             patch("src.main.GitHubClient") as MockGH:
            mock_lc = MagicMock()
            mock_lc.fetch_recent_accepted_submissions.return_value = [r]
            MockLC.return_value = mock_lc

            mock_gh = MagicMock()
            mock_gh.write_file_if_new.return_value = False  # file already existed
            MockGH.return_value = mock_gh

            count = run(config, store)

        assert count == 0
        store.mark_seen.assert_called_once_with("EXISTS_MODEB")
