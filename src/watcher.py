"""
Local background watcher for LeetCode Cloud Sync.

Polls LeetCode periodically (every 60 seconds by default) and syncs new
submissions automatically without requiring GitHub Actions cron delays
or manual intervention.
"""

from __future__ import annotations

import logging
import os
import pathlib
import sys
import time
from logging.handlers import RotatingFileHandler
from typing import Union

from dotenv import load_dotenv

from .config import Config, ConfigError
from .deduplication import DeduplicationStore, RemoteDeduplicationStore
from .github_client import GitHubClient
from .main import run

logger = logging.getLogger(__name__)

AnyStore = Union[DeduplicationStore, RemoteDeduplicationStore]


def watch(interval: int = 60, log_file: pathlib.Path | None = None) -> None:
    """Run continuous polling loop to sync new LeetCode submissions."""
    load_dotenv()

    try:
        config = Config.from_env()
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if log_file is None:
        log_dir = pathlib.Path("logs")
        log_dir.mkdir(exist_ok=True, parents=True)
        log_file = log_dir / "watcher.log"
    else:
        log_file.parent.mkdir(exist_ok=True, parents=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level, logging.INFO))

    # Add RotatingFileHandler if not already present
    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%SZ",
            )
        )
        root_logger.addHandler(file_handler)

    # Add StreamHandler for stderr if not already present
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%SZ",
            )
        )
        root_logger.addHandler(stream_handler)

    submissions_token = os.environ.get("SUBMISSIONS_TOKEN", "").strip()
    store: AnyStore
    if submissions_token:
        gh_state = GitHubClient(
            token=submissions_token,
            repo=config.github_repo,
            branch=config.github_branch,
        )
        store = RemoteDeduplicationStore(
            gh=gh_state,
            author_name=config.git_author_name,
            author_email=config.git_author_email,
        )
        logger.info("Watcher Mode B: state stored remotely in %s.", config.github_repo)
    else:
        store = DeduplicationStore()
        logger.info("Watcher Mode A: state stored locally.")

    logger.info("Starting local LeetCode sync watcher (polling every %ds)...", interval)
    logger.info("Press Ctrl+C to stop.")

    try:
        while True:
            try:
                new_count = run(config, store)
                if new_count > 0:
                    logger.info("Watcher successfully synced %d new submission(s).", new_count)
            except Exception as exc:
                logger.error("Error during sync run: %s", exc)
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Watcher stopped by user.")


def main() -> None:
    interval = int(os.environ.get("WATCH_INTERVAL", "60"))
    watch(interval)


if __name__ == "__main__":
    main()
