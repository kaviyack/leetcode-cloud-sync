from unittest.mock import MagicMock, patch
import os
from src.main import run
from src.config import Config
from src.deduplication import DeduplicationStore
from src.organizer import SubmissionRecord

def test_targeted_execution(tmp_path):
    # Setup config
    state_file = tmp_path / "state.json"
    cfg = Config(
        leetcode_username="testuser",
        leetcode_session="testsession",
        github_token="testtoken",
        github_repo="test/repo",
    )
    store = DeduplicationStore(str(state_file))

    mock_record = SubmissionRecord(
        submission_id="12345",
        problem_id=1,
        problem_title="Two Sum",
        problem_slug="two-sum",
        difficulty="Easy",
        language="python3",
        status="Accepted",
        timestamp=1000000,
        code="print('hello')",
        runtime="50 ms",
        memory="14.2 MB",
    )

    with patch.dict(os.environ, {"TARGET_SUBMISSION_ID": "12345"}):
        with patch("src.main.LeetCodeClient") as MockLCClass, \
             patch("src.main.GitHubClient") as MockGHClass:

            mock_lc = MockLCClass.return_value
            mock_lc.fetch_submission_by_id.return_value = mock_record

            mock_gh = MockGHClass.return_value
            mock_gh.write_file_if_new.return_value = True

            count = run(cfg, store)
            assert count == 1
            mock_lc.fetch_submission_by_id.assert_called_once_with("12345")
            mock_gh.write_file_if_new.assert_called_once()
            assert store.is_seen("12345") is True
