"""
LeetCode API client.

IMPORTANT — Authentication reality:
  LeetCode does NOT offer an official public API for retrieving submission
  source code. The GraphQL endpoint used here is the same endpoint that
  LeetCode's own web app calls; it requires a valid LEETCODE_SESSION cookie
  and a matching CSRF token extracted from a logged-in browser session.

  Without these credentials only limited public data (problem metadata,
  recent accepted submission stubs) may be available for some accounts.

  The session cookie expires when you log out or LeetCode invalidates it
  (typically after weeks or months of inactivity, or on a password change).

  Submissions made on any device (phone, laptop, another computer) ARE
  visible through this API as long as the session belongs to the same account,
  because the data lives server-side on LeetCode's infrastructure.

  This client makes HTTPS requests only. No credentials are logged.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from .organizer import SubmissionRecord

logger = logging.getLogger(__name__)

_BASE_URL = "https://leetcode.com"
_GRAPHQL_URL = f"{_BASE_URL}/graphql"

# Minimum seconds between requests to be polite to LeetCode's servers.
_REQUEST_DELAY = 0.5

_SUBMISSION_LIST_QUERY = """
query submissionList($offset: Int!, $limit: Int!, $lastKey: String) {
  submissionList(offset: $offset, limit: $limit, lastKey: $lastKey) {
    lastKey
    hasNext
    submissions {
      id
      title
      titleSlug
      status
      statusDisplay
      lang
      langName
      runtime
      timestamp
      url
      isPending
      memory
    }
  }
}
"""

_SUBMISSION_DETAIL_QUERY = """
query submissionDetails($submissionId: Int!) {
  submissionDetails(submissionId: $submissionId) {
    runtime
    runtimeDisplay
    runtimePercentile
    runtimeDistribution
    memory
    memoryDisplay
    memoryPercentile
    memoryDistribution
    code
    timestamp
    statusCode
    user {
      username
    }
    lang {
      name
      verboseName
    }
    question {
      questionId
      titleSlug
      title
      difficulty
      topicTags {
        name
        slug
      }
    }
    notes
    totalCorrect
    totalTestcases
  }
}
"""

_PROBLEM_DETAIL_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    title
    difficulty
    topicTags {
      name
      slug
    }
    frontendQuestionId
  }
}
"""

_USER_STATUS_QUERY = """
query userStatus {
  userStatus {
    isSignedIn
    username
    userId
  }
}
"""


class AuthError(Exception):
    """Raised when LeetCode credentials are absent or rejected."""


class LeetCodeAPIError(Exception):
    """Raised on unexpected API responses."""


class LeetCodeClient:
    """
    Client for the LeetCode GraphQL API.

    Requires LEETCODE_SESSION and LEETCODE_CSRF_TOKEN for full access.
    Only accepted submissions are synced by default.
    """

    def __init__(
        self,
        username: str,
        session_cookie: Optional[str] = None,
        csrf_token: Optional[str] = None,
        fetch_limit: int = 20,
        sync_mode: str = "accepted",
    ) -> None:
        self.username = username
        self._session_cookie = session_cookie
        self._csrf_token = csrf_token
        self.fetch_limit = fetch_limit
        self.sync_mode = sync_mode
        self._http = requests.Session()
        self._configure_session()

    def _configure_session(self) -> None:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 LeetCodeCloudSync/1.0 "
                "(https://github.com/kaviyack/leetcode-cloud-sync)"
            ),
            "Referer": "https://leetcode.com/",
            "Origin": "https://leetcode.com",
            "Content-Type": "application/json",
        }
        if self._csrf_token:
            headers["x-csrftoken"] = self._csrf_token
        self._http.headers.update(headers)

        if self._session_cookie:
            self._http.cookies.set(
                "LEETCODE_SESSION", self._session_cookie, domain="leetcode.com"
            )
        if self._csrf_token:
            self._http.cookies.set(
                "csrftoken", self._csrf_token, domain="leetcode.com"
            )

    def _graphql(self, query: str, variables: dict) -> dict:
        time.sleep(_REQUEST_DELAY)
        try:
            resp = self._http.post(
                _GRAPHQL_URL,
                json={"query": query, "variables": variables},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise LeetCodeAPIError(f"Network error: {exc}") from exc

        if resp.status_code == 403:
            raise AuthError(
                "LeetCode returned 403 Forbidden. "
                "Your LEETCODE_SESSION cookie may be expired or invalid. "
                "Please refresh it by logging in to leetcode.com in a browser "
                "and copying the new session cookie."
            )
        if resp.status_code == 429:
            raise LeetCodeAPIError(
                "Rate limited by LeetCode (HTTP 429). "
                "Reduce FETCH_LIMIT or increase the sync interval."
            )
        if not resp.ok:
            # Try to extract detailed error message from response body
            error_detail = ""
            try:
                error_body = resp.json()
                if "errors" in error_body:
                    error_msgs = [e.get("message", "") for e in error_body["errors"]]
                    error_detail = f": {'; '.join(error_msgs)}"
            except Exception:
                pass
            raise LeetCodeAPIError(
                f"LeetCode API error: HTTP {resp.status_code}{error_detail}"
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise LeetCodeAPIError(f"Invalid JSON from LeetCode: {exc}") from exc

        if "errors" in data:
            # Surface auth errors specifically
            for err in data["errors"]:
                msg = err.get("message", "")
                if "login" in msg.lower() or "auth" in msg.lower():
                    raise AuthError(f"LeetCode auth error: {msg}")
            raise LeetCodeAPIError(f"GraphQL errors: {data['errors']}")

        return data.get("data", {})

    def verify_auth(self) -> dict:
        """
        Verify that the session cookie and CSRF token provide a valid, signed-in
        LeetCode session via userStatus query. Raises AuthError if not signed in.
        """
        data = self._graphql(_USER_STATUS_QUERY, {})
        status = data.get("userStatus")
        if not status or not status.get("isSignedIn"):
            raise AuthError(
                "LeetCode session is expired or invalid. "
                "User is not signed in according to LeetCode API."
            )
        return status

    def fetch_recent_accepted_submissions(self) -> list[SubmissionRecord]:
        """
        Fetch recent submissions for the configured user.

        Returns a list of SubmissionRecord objects, newest first.
        Source code is fetched individually for each submission.

        Behavior depends on sync_mode:
        - 'accepted': only accepted submissions (filtered client-side)
        - 'all': all submission attempts regardless of status

        If LEETCODE_SESSION is not set, raises AuthError immediately rather
        than returning fake or empty data.
        """
        if not self._session_cookie:
            raise AuthError(
                "LEETCODE_SESSION is required to fetch submissions. "
                "Set this environment variable to your LeetCode session cookie."
            )

        mode_desc = "all submissions" if self.sync_mode == "all" else "accepted submissions"
        logger.info("Fetching recent %s for %s…", mode_desc, self.username)
        raw_submissions = self._fetch_submission_list()

        if self.sync_mode == "accepted":
            logger.info("Found %d accepted submissions in listing.", len(raw_submissions))
        else:
            logger.info("Found %d total submissions in listing.", len(raw_submissions))

        records: list[SubmissionRecord] = []
        for raw in raw_submissions:
            try:
                record = self._enrich_submission(raw)
                if record:
                    records.append(record)
            except (AuthError, LeetCodeAPIError) as exc:
                logger.warning(
                    "Skipping submission %s due to error: %s",
                    raw.get("id"),
                    exc,
                )
                # Re-raise AuthError so the caller can abort early.
                if isinstance(exc, AuthError):
                    raise

        return records

    def _fetch_submission_list(self) -> list[dict]:
        """
        Return raw submission dicts from the submission list API.

        Behavior depends on sync_mode:
        - 'accepted': returns only accepted submissions (filtered client-side)
        - 'all': returns all submissions regardless of status

        Note: LeetCode's GraphQL API returns submissions of all statuses.
        The current query does not include a server-side status filter.
        """
        data = self._graphql(
            _SUBMISSION_LIST_QUERY,
            {
                "offset": 0,
                "limit": self.fetch_limit,
                "lastKey": None,
            },
        )
        submissions_data = data.get("submissionList", {})
        if submissions_data is None:
            raise AuthError(
                "submissionList returned null. "
                "This usually means the session cookie is expired or missing."
            )
        all_subs = submissions_data.get("submissions", []) or []

        if self.sync_mode == "accepted":
            # Filter client-side: LeetCode's status filter may not be honored reliably.
            # statusDisplay == "Accepted" is the canonical accepted state.
            accepted = [
                s for s in all_subs
                if s.get("statusDisplay") == "Accepted" or s.get("status") == "AC"
            ]
            if len(accepted) < len(all_subs):
                logger.debug(
                    "Filtered %d non-accepted submissions client-side.",
                    len(all_subs) - len(accepted),
                )
            return accepted
        else:
            # Return all submissions regardless of status
            return all_subs

    def _enrich_submission(self, raw: dict) -> Optional[SubmissionRecord]:
        """Fetch detail for a single submission and build a SubmissionRecord."""
        sub_id = str(raw.get("id", ""))
        if not sub_id:
            logger.warning("Submission missing ID, skipping: %s", raw)
            return None

        title_slug = raw.get("titleSlug") or raw.get("title_slug", "")
        title = raw.get("title", "Unknown")
        lang = raw.get("lang") or raw.get("langName", "unknown")
        timestamp = int(raw.get("timestamp", 0))
        status = raw.get("statusDisplay") or raw.get("status", "Unknown")

        # Fetch detailed info (includes code and difficulty)
        detail = self._fetch_submission_detail(int(sub_id))

        code: Optional[str] = None
        difficulty = "Unknown"
        topic_tags: list[str] = []
        runtime: Optional[str] = None
        memory: Optional[str] = None
        problem_id = 0

        if detail:
            code = detail.get("code")
            runtime = detail.get("runtimeDisplay") or detail.get("runtime")
            memory = detail.get("memoryDisplay") or detail.get("memory")
            q = detail.get("question") or {}
            difficulty = q.get("difficulty", "Unknown")
            topic_tags = [t["name"] for t in (q.get("topicTags") or [])]
            try:
                problem_id = int(q.get("frontendQuestionId") or q.get("questionId") or 0)
            except (ValueError, TypeError):
                problem_id = 0
            if not title_slug:
                title_slug = q.get("titleSlug", "")
            if not title or title == "Unknown":
                title = q.get("title", "Unknown")

        if not title_slug:
            from .organizer import problem_slug_from_title
            title_slug = problem_slug_from_title(title)

        return SubmissionRecord(
            submission_id=sub_id,
            problem_id=problem_id,
            problem_title=title,
            problem_slug=title_slug,
            difficulty=difficulty,
            language=lang,
            status=status,
            timestamp=timestamp,
            code=code,
            runtime=runtime,
            memory=memory,
            topic_tags=topic_tags,
            url=f"https://leetcode.com/problems/{title_slug}/",
        )

    def _fetch_submission_detail(self, submission_id: int) -> Optional[dict]:
        """Fetch detailed data for a single submission ID."""
        try:
            data = self._graphql(
                _SUBMISSION_DETAIL_QUERY,
                {"submissionId": submission_id},
            )
            return data.get("submissionDetails")
        except LeetCodeAPIError as exc:
            logger.warning(
                "Could not fetch detail for submission %d: %s", submission_id, exc
            )
            return None

    def fetch_problem_metadata(self, title_slug: str) -> dict:
        """Fetch problem metadata (difficulty, tags) by slug."""
        data = self._graphql(_PROBLEM_DETAIL_QUERY, {"titleSlug": title_slug})
        return data.get("question") or {}
