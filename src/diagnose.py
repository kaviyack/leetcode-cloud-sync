"""
Diagnostic mode for LeetCode Cloud Sync.

Safe to run at any time — it NEVER commits or writes any files to GitHub.
Use it to validate your configuration and credentials before enabling the
scheduled sync.

Run:
    python -m src.diagnose

Or from GitHub Actions (workflow_dispatch on the diagnose workflow).
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)

_OK = "[OK]"
_WARN = "[WARN]"
_FAIL = "[FAIL]"


def _check(label: str, ok: bool, detail: str = "") -> bool:
    tag = _OK if ok else _FAIL
    msg = f"  {tag}  {label}"
    if detail:
        msg += f"\n        {detail}"
    print(msg)
    return ok


def _warn(label: str, detail: str = "") -> None:
    msg = f"  {_WARN}  {label}"
    if detail:
        msg += f"\n        {detail}"
    print(msg)


def run_diagnose() -> int:
    """
    Execute diagnostic checks. Returns 0 if all critical checks pass, 1 otherwise.

    Checks performed (in order):
      1. Config — required env vars present and correctly formatted.
      2. LeetCode auth — credentials present; small batch fetch attempted.
      3. Source code — verify at least one submission has code retrievable.
      4. GitHub access — destination repo and branch are reachable.

    Nothing is committed. No secrets are printed.
    """
    from .config import Config, ConfigError
    from .github_client import GitHubAPIError, GitHubClient
    from .leetcode_client import AuthError, LeetCodeAPIError, LeetCodeClient

    print()
    print("=" * 60)
    print("  LeetCode Cloud Sync — Diagnostic Mode")
    print("  (Read-only. Nothing will be committed.)")
    print("=" * 60)
    print()

    # ------------------------------------------------------------------ #
    # 1. Configuration
    # ------------------------------------------------------------------ #
    print("1. Configuration")
    config: Optional[Config] = None
    try:
        config = Config.from_env()
        _check("LEETCODE_USERNAME", True, f"username: {config.leetcode_username}")
        _check("GITHUB_TOKEN", True, "token loaded (value not shown)")
        _check(
            "GITHUB_REPO",
            True,
            f"target: {config.github_repo} (branch: {config.github_branch})",
        )
        has_session = config.has_auth()
        if has_session:
            _check("LEETCODE_SESSION", True, "session cookie loaded (value not shown)")
        else:
            _warn(
                "LEETCODE_SESSION not set",
                "Source code will NOT be retrievable. "
                "Only public submission stubs available.",
            )
        if config.leetcode_csrf:
            _check("LEETCODE_CSRF_TOKEN", True, "CSRF token loaded (value not shown)")
        else:
            _warn(
                "LEETCODE_CSRF_TOKEN not set",
                "Requests may be rejected by LeetCode's CSRF protection.",
            )
    except ConfigError as exc:
        _check("Configuration", False, str(exc))
        print()
        print("Diagnosis aborted — fix configuration errors above first.")
        return 1

    all_ok = True

    # ------------------------------------------------------------------ #
    # 2. LeetCode API — authentication and small batch fetch
    # ------------------------------------------------------------------ #
    print()
    print("2. LeetCode API")

    if not config.has_auth():
        _warn(
            "Skipping LeetCode API test",
            "LEETCODE_SESSION is required for submission data.",
        )
    else:
        lc = LeetCodeClient(
            username=config.leetcode_username,
            session_cookie=config.leetcode_session,
            csrf_token=config.leetcode_csrf,
            fetch_limit=3,  # small batch — diagnostic only
            sync_mode="accepted",  # diagnose with accepted only
        )
        records = None
        try:
            auth_status = lc.verify_auth()
            api_user = auth_status.get("username", "unknown")
            _check(
                "LeetCode authentication (userStatus)",
                True,
                f"Session is valid and signed in as '{api_user}'.",
            )
        except AuthError as exc:
            _check(
                "LeetCode authentication",
                False,
                f"Session is expired or invalid. Detail: {exc}",
            )
            all_ok = False
            records = []

        if all_ok:
            try:
                records = lc.fetch_recent_accepted_submissions()
                if not records:
                    _check(
                        "LeetCode submission list",
                        True,
                        "Authenticated successfully, but returned 0 accepted submissions (genuinely zero submissions).",
                    )
                else:
                    _check(
                        "LeetCode API reachable",
                        True,
                        f"fetched {len(records)} accepted submission(s) (limit: 3)",
                    )
            except AuthError as exc:
                _check(
                    "LeetCode authentication",
                    False,
                    f"Auth failed during fetch — refresh your LEETCODE_SESSION cookie. Detail: {exc}",
                )
                all_ok = False
            except LeetCodeAPIError as exc:
                _check(
                    "LeetCode API",
                    False,
                    f"API error (transient?): {exc}",
                )
                all_ok = False

        # ---------------------------------------------------------------- #
        # 3. Source code retrievability
        # ---------------------------------------------------------------- #
        print()
        print("3. Source code retrievability")

        if records is None:
            _warn("Skipped — LeetCode API check did not succeed.")
        elif not records:
            _warn(
                "No accepted submissions returned",
                "Account may have no accepted submissions, or fetch_limit may be 0.",
            )
        else:
            with_code = [r for r in records if r.code]
            without_code = [r for r in records if not r.code]
            if with_code:
                sample = with_code[0]
                _check(
                    "Source code available",
                    True,
                    f"#{sample.problem_id} {sample.problem_title} "
                    f"[{sample.language}] — code length: {len(sample.code)} chars",
                )
            if without_code:
                _warn(
                    f"{len(without_code)} submission(s) have no code",
                    "These may be older submissions or detail-fetch failures.",
                )

    # ------------------------------------------------------------------ #
    # 4. GitHub destination repo access
    # ------------------------------------------------------------------ #
    print()
    print("4. GitHub repository access")

    gh = GitHubClient(
        token=config.github_token,
        repo=config.github_repo,
        branch=config.github_branch,
    )

    _probe_path = ".leetcode_sync_state.json"
    try:
        # We're just probing — file_exists reads; we don't write anything.
        exists = gh.file_exists(_probe_path)
        _check(
            "GitHub API reachable",
            True,
            f"repo: {config.github_repo}, branch: {config.github_branch}",
        )
        if exists:
            _check(
                "State file found",
                True,
                f"{_probe_path} exists — previous sync state present.",
            )
        else:
            _check(
                "State file not found",
                True,
                f"{_probe_path} does not exist yet — first run will create it.",
            )
    except GitHubAPIError as exc:
        err = str(exc)
        if "401" in err or "404" in err:
            _check(
                "GitHub API access",
                False,
                "Check that GITHUB_TOKEN is valid and GITHUB_REPO is correct. "
                f"Detail: {exc}",
            )
        else:
            _check(
                "GitHub API",
                False,
                f"Unexpected error: {exc}",
            )
        all_ok = False

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    print()
    print("=" * 60)
    if all_ok:
        print("  Diagnosis complete — all critical checks passed.")
        print("  You can enable the scheduled sync workflow.")
    else:
        print("  Diagnosis complete — one or more checks FAILED.")
        print("  Fix the failures above, then re-run this diagnostic.")
    print("=" * 60)
    print()

    return 0 if all_ok else 1


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,  # suppress verbose library logs during diagnosis
        format="%(levelname)s: %(message)s",
    )
    sys.exit(run_diagnose())


if __name__ == "__main__":
    main()
