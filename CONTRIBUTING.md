# Contributing to LeetCode Cloud Sync

Thank you for your interest in contributing!

## How to contribute

1. **Fork** the repository and create a branch from `main`.
2. **Make your changes** with clear, focused commits.
3. **Write or update tests** for any changed behaviour.
4. **Run the test suite** locally: `pytest tests/ -v`
5. **Open a pull request** against `main` with a clear description.

## Development setup

```bash
git clone https://github.com/kaviyack/leetcode-cloud-sync.git
cd leetcode-cloud-sync
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copy the example env file for local testing (never commit .env)
cp .env.example .env

# Run the full test suite (no credentials required)
pytest tests/ -v
```

## What makes a good contribution

- Bug fixes with a test that would have caught the bug.
- Documentation improvements (setup steps, troubleshooting).
- Support for additional LeetCode languages.
- Improved error messages and recovery.

## What to avoid

- Adding runtime dependencies that are not strictly necessary.
- Hardcoding credentials, usernames, or repository names.
- Removing the deduplication guard (submission IDs must remain the dedup key).
- Changes that require storing credentials in source files or the repository.
- Hardcoding `kaviyack/leetcode-submissions` or any specific repository — users must be able to configure their own destination.

## Code style

- Python 3.11+, type hints throughout.
- `ruff` for linting: `ruff check src/ tests/`
- `mypy` for type checking: `mypy src/ --ignore-missing-imports`
- No credentials, real usernames, or real session values in test fixtures.

## Reporting issues

Use the GitHub issue templates for bug reports and feature requests.
