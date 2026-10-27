"""Tests for the organizer module: difficulty classification, slug generation, paths."""

from __future__ import annotations

from src.organizer import (
    difficulty_dir,
    problem_dir_name,
    problem_slug_from_title,
    submission_filename,
    submission_path,
)
from tests.conftest import make_record

# ---------------------------------------------------------------------------
# 1. Difficulty classification
# ---------------------------------------------------------------------------

class TestDifficultyDir:
    def test_easy(self):
        assert difficulty_dir("Easy") == "easy"

    def test_easy_lowercase(self):
        assert difficulty_dir("easy") == "easy"

    def test_medium(self):
        assert difficulty_dir("Medium") == "medium"

    def test_hard(self):
        assert difficulty_dir("Hard") == "hard"

    # 2. Unknown difficulty handling
    def test_unknown(self):
        assert difficulty_dir("Unknown") == "unknown"

    def test_empty_string_unknown(self):
        assert difficulty_dir("") == "unknown"

    def test_garbage_unknown(self):
        assert difficulty_dir("EXTREME") == "unknown"


class TestSubmissionRecordDifficulty:
    """SubmissionRecord normalises difficulty in __post_init__."""

    def test_easy_normalised(self):
        r = make_record(difficulty="easy")
        assert r.difficulty == "Easy"

    def test_medium_normalised(self):
        r = make_record(difficulty="MEDIUM")
        assert r.difficulty == "Medium"

    def test_hard_normalised(self):
        r = make_record(difficulty="Hard")
        assert r.difficulty == "Hard"

    def test_unknown_normalised(self):
        r = make_record(difficulty="???")
        assert r.difficulty == "Unknown"


# ---------------------------------------------------------------------------
# 3. Problem slug generation
# ---------------------------------------------------------------------------

class TestProblemSlugFromTitle:
    def test_simple(self):
        assert problem_slug_from_title("Two Sum") == "two-sum"

    def test_punctuation_stripped(self):
        assert problem_slug_from_title("Zigzag Conversion") == "zigzag-conversion"

    def test_numbers_preserved(self):
        assert problem_slug_from_title("4Sum II") == "4sum-ii"

    def test_special_chars(self):
        slug = problem_slug_from_title("N-Queens II")
        assert slug == "n-queens-ii"

    def test_no_leading_trailing_dash(self):
        slug = problem_slug_from_title("  LRU Cache  ")
        assert not slug.startswith("-")
        assert not slug.endswith("-")


class TestProblemDirName:
    def test_padding(self):
        assert problem_dir_name(6, "zigzag-conversion") == "0006-zigzag-conversion"

    def test_four_digit(self):
        assert problem_dir_name(1234, "my-problem") == "1234-my-problem"

    def test_single_digit(self):
        assert problem_dir_name(1, "two-sum") == "0001-two-sum"


# ---------------------------------------------------------------------------
# 4. Submission filename generation
# ---------------------------------------------------------------------------

class TestSubmissionFilename:
    def test_format(self):
        record = make_record(
            submission_id="987654321",
            language="python3",
            timestamp=1761523200,  # 2025-10-26 20:00 UTC
        )
        name = submission_filename(record)
        # Must include the submission ID
        assert "987654321" in name
        # Must end with .md
        assert name.endswith(".md")
        # Language must appear in filename (sanitised)
        assert "python3" in name

    def test_different_ids_different_filenames(self):
        r1 = make_record(submission_id="111", timestamp=1761523200)
        r2 = make_record(submission_id="222", timestamp=1761523200)
        assert submission_filename(r1) != submission_filename(r2)

    def test_same_id_same_filename(self):
        r1 = make_record(submission_id="111", timestamp=1761523200)
        r2 = make_record(submission_id="111", timestamp=1761523200)
        assert submission_filename(r1) == submission_filename(r2)

    def test_language_sanitised(self):
        record = make_record(language="C++", submission_id="1")
        name = submission_filename(record)
        assert "#" not in name
        assert "+" not in name
        assert name.endswith(".md")


# ---------------------------------------------------------------------------
# Full submission_path
# ---------------------------------------------------------------------------

class TestSubmissionPath:
    def test_easy_path(self):
        r = make_record(difficulty="Easy", problem_id=1, problem_slug="two-sum")
        path = submission_path(r, solutions_root="solutions")
        assert path.startswith("solutions/easy/0001-two-sum/")
        assert path.endswith(".md")

    def test_medium_path(self):
        r = make_record(difficulty="Medium", problem_id=6, problem_slug="zigzag-conversion")
        path = submission_path(r, solutions_root="solutions")
        assert "solutions/medium/0006-zigzag-conversion/" in path

    def test_hard_path(self):
        r = make_record(difficulty="Hard", problem_id=4, problem_slug="median-of-two-sorted-arrays")
        path = submission_path(r, solutions_root="solutions")
        assert "solutions/hard/" in path

    def test_unknown_difficulty_path(self):
        r = make_record(difficulty="Unknown", problem_id=999, problem_slug="mystery")
        path = submission_path(r, solutions_root="solutions")
        assert "solutions/unknown/" in path

    def test_custom_solutions_root(self):
        r = make_record()
        path = submission_path(r, solutions_root="my_solutions")
        assert path.startswith("my_solutions/")

    # 6. Different submission IDs for same problem preserve both
    def test_two_submissions_same_problem_different_ids(self):
        r1 = make_record(submission_id="AAA", problem_id=1, problem_slug="two-sum", timestamp=1761523200)
        r2 = make_record(submission_id="BBB", problem_id=1, problem_slug="two-sum", timestamp=1761523200)
        p1 = submission_path(r1)
        p2 = submission_path(r2)
        assert p1 != p2, "Different submission IDs must produce different paths"

    # 9. Multiple languages for same problem
    def test_different_languages_different_paths(self):
        r_py = make_record(submission_id="PY1", language="python3", problem_slug="two-sum")
        r_java = make_record(submission_id="JV1", language="java", problem_slug="two-sum")
        p_py = submission_path(r_py)
        p_java = submission_path(r_java)
        assert p_py != p_java, "Different languages must produce different paths"
        assert "python3" in p_py
        assert "java" in p_java
