"""Tracks which submission IDs have already been synced to avoid duplicates."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .github_client import GitHubClient

logger = logging.getLogger(__name__)

_STATE_FILE = ".leetcode_sync_state.json"


def _parse_state(raw: str) -> set[str]:
    try:
        data = json.loads(raw)
        return set(data.get("synced_ids", []))
    except (json.JSONDecodeError, AttributeError):
        return set()


def _serialise_state(seen: set[str]) -> str:
    return json.dumps({"synced_ids": sorted(seen)}, indent=2)


class DeduplicationStore:
    """
    Persists the set of already-synced submission IDs to a local JSON file.

    The state file is committed as part of the repository so that every
    workflow run shares the same view of processed submissions, even across
    different runner instances.

    Deduplication key: LeetCode submission_id (string).
    This is intentionally NOT keyed on problem ID, language, or code content —
    so that every distinct submission (including repeated attempts) is preserved,
    but the same submission is not written twice.
    """

    def __init__(self, state_path: str = _STATE_FILE) -> None:
        self._path = Path(state_path)
        self._seen: set[str] = set()
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                raw = self._path.read_text(encoding="utf-8")
                self._seen = _parse_state(raw)
                if not self._seen and raw.strip():
                    logger.warning(
                        "Could not parse state file %s. Starting fresh.", self._path
                    )
                else:
                    logger.debug("Loaded %d known submission IDs.", len(self._seen))
            except OSError as exc:
                logger.warning(
                    "Could not load state file %s: %s. Starting fresh.", self._path, exc
                )
                self._seen = set()
        else:
            logger.debug("No state file found at %s. Starting fresh.", self._path)

    def is_seen(self, submission_id: str) -> bool:
        return submission_id in self._seen

    def mark_seen(self, submission_id: str) -> None:
        self._seen.add(submission_id)

    def save(self) -> None:
        try:
            self._path.write_text(_serialise_state(self._seen), encoding="utf-8")
            logger.debug("Saved %d submission IDs to state file.", len(self._seen))
        except OSError as exc:
            logger.error("Failed to save state file: %s", exc)

    def count(self) -> int:
        return len(self._seen)


class RemoteDeduplicationStore:
    """
    Mode B state store: reads and writes .leetcode_sync_state.json in the
    destination repository via the GitHub Contents API.

    State is loaded once at construction. After each batch of submission writes,
    call save() to push the updated state back. Failed submission writes must NOT
    be followed by mark_seen() — the caller is responsible for this ordering.

    Deduplication key: LeetCode submission_id (string), same as DeduplicationStore.
    """

    def __init__(
        self,
        gh: "GitHubClient",
        state_path: str = _STATE_FILE,
        author_name: str = "LeetCode Cloud Sync",
        author_email: str = "leetcode-cloud-sync@users.noreply.github.com",
    ) -> None:
        self._gh = gh
        self._state_path = state_path
        self._author_name = author_name
        self._author_email = author_email
        self._seen: set[str] = set()
        self._sha: str | None = None  # current blob SHA; None if file doesn't exist yet
        self._load()

    def _load(self) -> None:
        from .github_client import GitHubAPIError

        try:
            result = self._gh.read_file(self._state_path)
        except GitHubAPIError as exc:
            logger.warning(
                "Could not read remote state file %s: %s. Starting fresh.",
                self._state_path,
                exc,
            )
            return

        if result is None:
            logger.debug("No remote state file found. Starting fresh.")
            return

        raw, sha = result
        self._sha = sha
        self._seen = _parse_state(raw)
        if not self._seen and raw.strip():
            logger.warning("Remote state file was malformed; starting fresh.")
            self._seen = set()
        else:
            logger.debug("Loaded %d known submission IDs from remote.", len(self._seen))

    def is_seen(self, submission_id: str) -> bool:
        return submission_id in self._seen

    def mark_seen(self, submission_id: str) -> None:
        self._seen.add(submission_id)

    def save(self) -> None:
        from .github_client import GitHubAPIError

        content = _serialise_state(self._seen)
        commit_msg = "sync: update deduplication state"
        try:
            if self._sha is None:
                self._gh.create_file(
                    path=self._state_path,
                    content=content,
                    commit_message=commit_msg,
                    author_name=self._author_name,
                    author_email=self._author_email,
                )
            else:
                self._gh.update_file(
                    path=self._state_path,
                    content=content,
                    sha=self._sha,
                    commit_message=commit_msg,
                    author_name=self._author_name,
                    author_email=self._author_email,
                )
            # Refresh SHA after the write so a second save() in the same run is safe.
            result = self._gh.read_file(self._state_path)
            if result is not None:
                _, self._sha = result
            logger.debug("Saved %d submission IDs to remote state.", len(self._seen))
        except GitHubAPIError as exc:
            logger.error("Failed to save remote state file: %s", exc)

    def count(self) -> int:
        return len(self._seen)
