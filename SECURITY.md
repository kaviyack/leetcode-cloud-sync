# Security Policy

## Supported versions

Only the latest version on the `main` branch receives security fixes.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues using GitHub's private vulnerability reporting feature:
**Security → Report a vulnerability** (in the repository's Security tab).

Include:
- A description of the vulnerability and its potential impact.
- Steps to reproduce, if applicable.
- Any suggested mitigation.

You will receive a response within 7 days.

## Credential security

This project requires LeetCode session cookies as GitHub Actions secrets.

- **Never** paste session cookies into source files, issues, pull requests, or public discussions.
- Session cookies grant full access to your LeetCode account. Treat them as passwords.
- If you believe your session has been compromised, log out of LeetCode immediately (this invalidates the cookie) and update your GitHub Actions secrets with a fresh cookie.
- The project source code intentionally does not log session values. If you find a code path that does, please report it.

## GitHub token scope

**Mode A (same repository):** The `GITHUB_TOKEN` used in Actions is scoped to the current repository with Contents write permission only. No elevated permissions are requested or used.

**Mode B (separate submissions repository):** The `SUBMISSIONS_TOKEN` should be a fine-grained personal access token scoped to only the destination repository with Contents: Read and write. No other repositories or permissions should be granted.

Do not use a classic personal access token with broad repository access. Fine-grained tokens with the minimum necessary scope are strongly preferred.
