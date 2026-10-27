"""
Main orchestrator for a LeetCode Cloud Sync run.

Sequence:
  1. Load and validate configuration.
  2. Load the deduplication store (list of already-synced IDs).
  3. Fetch recent accepted submissions from LeetCode.
  4. For each new submission:
     a. Determine file path (difficulty / problem directory / filename).
     b. Render Markdown.
     c. Write to GitHub (only if the path does not already exist).
     d. Mark submission ID as seen (only on successful write or already-exists).
  5. Persist updated deduplication state.

Mode A (same repo): state is stored locally and committed via git in the workflow.
Mode B (separate repo): state is stored remotely in the destination repo via the API.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Union

from .config import Config, ConfigError
from .deduplication import DeduplicationStore, RemoteDeduplicationStore
from .github_client import GitHubAPIError, GitHubClient
from .leetcode_client import AuthError, LeetCodeAPIError, LeetCodeClient
from .markdown_writer import render_submission
from .organizer import submission_path

logger = logging.getLogger(__name__)

AnyStore = Union[DeduplicationStore, RemoteDeduplicationStore]


def run(config: Config, store: AnyStore) -> int:
    """
    Execute one synchronization run.

    Returns the number of new submissions written.
    """
    lc = LeetCodeClient(
        username=config.leetcode_username,
        session_cookie=config.leetcode_session,
        csrf_token=config.leetcode_csrf,
        fetch_limit=config.fetch_limit,
        sync_mode=config.sync_mode,
    )
    gh = GitHubClient(
        token=config.github_token,
        repo=config.github_repo,
        branch=config.github_branch,
    )

    try:
        submissions = lc.fetch_recent_accepted_submissions()
    except AuthError as exc:
        logger.error("Authentication failed: %s", exc)
        logger.error(
            "ACTION REQUIRED: Refresh your LEETCODE_SESSION and "
            "LEETCODE_CSRF_TOKEN secrets in GitHub Actions."
        )
        sys.exit(2)
    except LeetCodeAPIError as exc:
        logger.error("LeetCode API error: %s", exc)
        sys.exit(3)

    new_count = 0
    for record in submissions:
        if store.is_seen(record.submission_id):
            logger.debug(
                "Already synced submission %s (%s), skipping.",
                record.submission_id,
                record.problem_title,
            )
            continue

        path = submission_path(record, solutions_root=config.solutions_root)
        markdown = render_submission(record)
        commit_msg = (
            f"sync: add {record.difficulty.lower()} #{record.problem_id} "
            f"{record.problem_title} [{record.language}] ({record.submission_id})"
        )

        try:
            written = gh.write_file_if_new(
                path=path,
                content=markdown,
                commit_message=commit_msg,
                author_name=config.git_author_name,
                author_email=config.git_author_email,
            )
        except GitHubAPIError as exc:
            logger.error("Failed to write %s: %s", path, exc)
            # Do NOT mark as seen — allow retry on the next run.
            continue

        if written:
            new_count += 1
            logger.info(
                "Synced: %s [%s] → %s",
                record.problem_title,
                record.language,
                path,
            )

        # Mark seen whether new or already-existing — if it existed, a prior run
        # already committed it; no need to write it again.
        store.mark_seen(record.submission_id)

    store.save()
    return new_count


def main() -> None:
    try:
        config = Config.from_env()
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    # Mode B: SUBMISSIONS_TOKEN is a separate env var set before GITHUB_TOKEN
    # is overwritten by the workflow. Detect mode by checking the original env var.
    submissions_token = os.environ.get("SUBMISSIONS_TOKEN", "").strip()
    if submissions_token:
        gh_state = GitHubClient(
            token=submissions_token,
            repo=config.github_repo,
            branch=config.github_branch,
        )
        store: AnyStore = RemoteDeduplicationStore(
            gh=gh_state,
            author_name=config.git_author_name,
            author_email=config.git_author_email,
        )
        logger.info("Mode B: state stored remotely in %s.", config.github_repo)
    else:
        store = DeduplicationStore()
        logger.info("Mode A: state stored locally.")

    new_count = run(config, store)

    if new_count == 0:
        logger.info("No new submissions found. Nothing committed.")
    else:
        logger.info("Sync complete. %d new submission(s) written.", new_count)


if __name__ == "__main__":
    main()
