"""Tests for DeduplicationStore."""

from __future__ import annotations

import json

from src.deduplication import DeduplicationStore


class TestDeduplicationStore:
    # 7. Duplicate detection across runs
    def test_new_id_not_seen(self, tmp_path):
        store = DeduplicationStore(state_path=str(tmp_path / "state.json"))
        assert not store.is_seen("ABC123")

    def test_mark_seen_makes_seen(self, tmp_path):
        store = DeduplicationStore(state_path=str(tmp_path / "state.json"))
        store.mark_seen("ABC123")
        assert store.is_seen("ABC123")

    def test_persists_across_instances(self, tmp_path):
        path = str(tmp_path / "state.json")
        s1 = DeduplicationStore(state_path=path)
        s1.mark_seen("ID_PERSISTENT")
        s1.save()

        s2 = DeduplicationStore(state_path=path)
        assert s2.is_seen("ID_PERSISTENT")

    def test_separate_ids_tracked_independently(self, tmp_path):
        path = str(tmp_path / "state.json")
        store = DeduplicationStore(state_path=path)
        store.mark_seen("ID_A")
        assert store.is_seen("ID_A")
        assert not store.is_seen("ID_B")

    def test_count_increases(self, tmp_path):
        path = str(tmp_path / "state.json")
        store = DeduplicationStore(state_path=path)
        assert store.count() == 0
        store.mark_seen("X")
        assert store.count() == 1
        store.mark_seen("Y")
        assert store.count() == 2

    def test_starts_fresh_if_no_file(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        store = DeduplicationStore(state_path=path)
        assert store.count() == 0

    def test_handles_corrupt_state_file(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("NOT JSON {{{}}", encoding="utf-8")
        store = DeduplicationStore(state_path=str(path))
        assert store.count() == 0  # Starts fresh gracefully

    def test_save_creates_valid_json(self, tmp_path):
        path = str(tmp_path / "state.json")
        store = DeduplicationStore(state_path=path)
        store.mark_seen("SAVE_TEST")
        store.save()
        data = json.loads(open(path, encoding="utf-8").read())
        assert "SAVE_TEST" in data["synced_ids"]

    def test_duplicate_mark_does_not_inflate_count(self, tmp_path):
        store = DeduplicationStore(state_path=str(tmp_path / "state.json"))
        store.mark_seen("DUP")
        store.mark_seen("DUP")
        assert store.count() == 1
