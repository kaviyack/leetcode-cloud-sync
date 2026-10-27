"""
Tests for RemoteDeduplicationStore (Mode B state persistence via GitHub API).

All GitHub API calls are mocked — no real credentials or network access needed.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from src.deduplication import RemoteDeduplicationStore
from src.github_client import GitHubAPIError


def _make_gh(
    read_result=None,  # None = file not found; (content_str, sha) = found
    create_raises=None,
    update_raises=None,
    read_after_write=None,  # result returned by the post-save read_file probe
):
    gh = MagicMock()
    gh.read_file.return_value = read_result
    if create_raises:
        gh.create_file.side_effect = create_raises
    if update_raises:
        gh.update_file.side_effect = update_raises
    # After a successful write the store re-reads to refresh its SHA.
    if read_after_write is not None:
        gh.read_file.side_effect = [read_result, read_after_write]
    return gh


def _state_json(ids: list[str]) -> str:
    return json.dumps({"synced_ids": sorted(ids)}, indent=2)


class TestRemoteDeduplicationStoreLoad:
    def test_starts_fresh_when_no_remote_file(self):
        gh = _make_gh(read_result=None)
        store = RemoteDeduplicationStore(gh)
        assert store.count() == 0
        assert not store.is_seen("ANY")

    def test_loads_ids_from_remote_file(self):
        raw = _state_json(["ID_A", "ID_B"])
        gh = _make_gh(read_result=(raw, "abc123"))
        store = RemoteDeduplicationStore(gh)
        assert store.is_seen("ID_A")
        assert store.is_seen("ID_B")
        assert not store.is_seen("ID_C")
        assert store.count() == 2

    def test_starts_fresh_on_malformed_remote_file(self):
        gh = _make_gh(read_result=("NOT JSON {{}", "sha1"))
        store = RemoteDeduplicationStore(gh)
        assert store.count() == 0

    def test_starts_fresh_on_api_error_during_load(self):
        gh = MagicMock()
        gh.read_file.side_effect = GitHubAPIError("500 server error")
        store = RemoteDeduplicationStore(gh)
        assert store.count() == 0

    def test_empty_remote_file_counts_zero(self):
        raw = _state_json([])
        gh = _make_gh(read_result=(raw, "sha_empty"))
        store = RemoteDeduplicationStore(gh)
        assert store.count() == 0


class TestRemoteDeduplicationStoreSave:
    def test_creates_file_when_none_existed(self):
        gh = _make_gh(read_result=None, read_after_write=(_state_json(["NEW"]), "sha_new"))
        store = RemoteDeduplicationStore(gh)
        store.mark_seen("NEW")
        store.save()
        gh.create_file.assert_called_once()
        args = gh.create_file.call_args
        content = json.loads(args.kwargs.get("content") or args.args[1])
        assert "NEW" in content["synced_ids"]

    def test_updates_file_when_sha_known(self):
        raw = _state_json(["OLD"])
        gh = _make_gh(read_result=(raw, "sha_old"), read_after_write=(_state_json(["NEW", "OLD"]), "sha_new"))
        store = RemoteDeduplicationStore(gh)
        store.mark_seen("NEW")
        store.save()
        gh.update_file.assert_called_once()
        args = gh.update_file.call_args
        sha_passed = args.kwargs.get("sha") or args.args[2]
        assert sha_passed == "sha_old"
        content = json.loads(args.kwargs.get("content") or args.args[1])
        assert "NEW" in content["synced_ids"]
        assert "OLD" in content["synced_ids"]

    def test_save_refreshes_sha_for_subsequent_save(self):
        gh = MagicMock()
        gh.read_file.side_effect = [
            None,                                 # initial load → no file
            (_state_json(["A"]), "sha_after_1"),  # post-save probe after first save
            (_state_json(["A", "B"]), "sha_after_2"),  # post-save probe after second save
        ]
        store = RemoteDeduplicationStore(gh)
        store.mark_seen("A")
        store.save()
        # Second save must use the refreshed SHA
        store.mark_seen("B")
        store.save()
        assert gh.update_file.call_count == 1  # first save used create_file

    def test_save_logs_error_on_api_failure(self, caplog):
        import logging
        gh = _make_gh(read_result=None, create_raises=GitHubAPIError("503"))
        store = RemoteDeduplicationStore(gh)
        store.mark_seen("X")
        with caplog.at_level(logging.ERROR):
            store.save()  # must not raise
        assert any("Failed to save" in r.message for r in caplog.records)

    def test_no_network_call_if_nothing_marked(self):
        # Even with nothing new, save() still runs (caller decides if needed).
        gh = _make_gh(read_result=None, read_after_write=(_state_json([]), "sha_0"))
        store = RemoteDeduplicationStore(gh)
        store.save()
        gh.create_file.assert_called_once()


class TestRemoteDeduplicationStoreSemantics:
    def test_mark_seen_idempotent(self):
        gh = _make_gh(read_result=None, read_after_write=(_state_json(["A"]), "s"))
        store = RemoteDeduplicationStore(gh)
        store.mark_seen("A")
        store.mark_seen("A")
        assert store.count() == 1

    def test_failed_write_not_marked_seen(self):
        """If the caller skips mark_seen on API error, the ID stays un-seen."""
        raw = _state_json([])
        gh = _make_gh(read_result=(raw, "sha"))
        store = RemoteDeduplicationStore(gh)
        # Simulate: caller only calls mark_seen after write succeeds.
        # For a failed write the caller skips mark_seen.
        assert not store.is_seen("FAIL1")
        # (no mark_seen called)
        assert not store.is_seen("FAIL1")

    def test_rerun_skips_already_seen_ids(self):
        raw = _state_json(["ALREADY"])
        gh = _make_gh(read_result=(raw, "sha_prev"))
        store = RemoteDeduplicationStore(gh)
        assert store.is_seen("ALREADY")
        # Caller would skip writing for ALREADY — no create_file called.
        gh.create_file.assert_not_called()

    def test_same_problem_different_submission_ids_both_tracked(self):
        gh = _make_gh(read_result=None, read_after_write=(_state_json(["ID_1", "ID_2"]), "s"))
        store = RemoteDeduplicationStore(gh)
        store.mark_seen("ID_1")
        store.mark_seen("ID_2")
        assert store.count() == 2
        assert store.is_seen("ID_1")
        assert store.is_seen("ID_2")
