"""Tests for the Markdown writer."""

from __future__ import annotations

from src.markdown_writer import render_submission
from tests.conftest import make_record


class TestRenderSubmission:
    def test_contains_problem_title(self):
        r = make_record(problem_title="Two Sum", problem_id=1)
        md = render_submission(r)
        assert "Two Sum" in md

    def test_contains_submission_id(self):
        r = make_record(submission_id="99887766")
        md = render_submission(r)
        assert "99887766" in md

    def test_contains_difficulty(self):
        r = make_record(difficulty="Medium")
        md = render_submission(r)
        assert "Medium" in md

    def test_contains_language(self):
        r = make_record(language="java")
        md = render_submission(r)
        assert "java" in md

    def test_contains_status(self):
        r = make_record(status="Accepted")
        md = render_submission(r)
        assert "Accepted" in md

    def test_contains_solution_code(self):
        r = make_record(code="def solve():\n    return 42")
        md = render_submission(r)
        assert "def solve():" in md
        assert "return 42" in md

    def test_code_in_fence(self):
        r = make_record(language="python3", code="x = 1")
        md = render_submission(r)
        assert "```python" in md

    def test_java_fence(self):
        r = make_record(language="java", code="int x = 0;")
        md = render_submission(r)
        assert "```java" in md

    def test_runtime_present(self):
        r = make_record(runtime="48 ms")
        md = render_submission(r)
        assert "48 ms" in md

    def test_memory_present(self):
        r = make_record(memory="16.2 MB")
        md = render_submission(r)
        assert "16.2 MB" in md

    def test_topic_tags_present(self):
        r = make_record(topic_tags=["Dynamic Programming", "Array"])
        md = render_submission(r)
        assert "Dynamic Programming" in md
        assert "Array" in md

    def test_problem_url_present(self):
        r = make_record(url="https://leetcode.com/problems/two-sum/")
        md = render_submission(r)
        assert "https://leetcode.com/problems/two-sum/" in md

    # 8. Missing optional metadata
    def test_missing_runtime(self):
        r = make_record(runtime=None)
        md = render_submission(r)
        assert "_Not available_" in md

    def test_missing_memory(self):
        r = make_record(memory=None)
        md = render_submission(r)
        assert "_Not available_" in md

    def test_missing_topic_tags(self):
        r = make_record(topic_tags=[])
        md = render_submission(r)
        assert "_Not available_" in md

    def test_missing_code(self):
        r = make_record(code=None)
        md = render_submission(r)
        assert "LEETCODE_SESSION" in md  # Explains how to enable code retrieval

    def test_no_full_problem_statement(self):
        r = make_record()
        md = render_submission(r)
        # Must not claim to include the full problem statement
        assert "not redistributed" in md or "Visit the link" in md

    def test_timestamp_formatted(self):
        r = make_record(timestamp=1761523200)
        md = render_submission(r)
        # Should render a human-readable date, not just a raw epoch
        assert "UTC" in md

    def test_complexity_section_present(self):
        r = make_record()
        md = render_submission(r)
        assert "Complexity" in md

    def test_complexity_marked_as_estimate(self):
        r = make_record()
        md = render_submission(r)
        assert "not automatically determined" in md
