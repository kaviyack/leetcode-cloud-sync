# LeetCode Cloud Sync

> Automatically save your LeetCode submissions to GitHub — from any device, without keeping a computer on.

[![CI](https://github.com/kaviyack/leetcode-cloud-sync/actions/workflows/ci.yml/badge.svg)](https://github.com/kaviyack/leetcode-cloud-sync/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

---

**LeetCode Cloud Sync is not affiliated with or endorsed by LeetCode.**

---

## Table of contents

1. [What it does](#what-it-does)
2. [Architecture and synchronization flow](#architecture-and-synchronization-flow)
3. [Repository architecture: one repo vs. two repos](#repository-architecture-one-repo-vs-two-repos)
4. [Supported configuration options](#supported-configuration-options)
5. [Prerequisites](#prerequisites)
6. [Fork or clone the project](#fork-or-clone-the-project)
7. [Configure your LeetCode account](#configure-your-leetcode-account)
8. [Configure the destination repository](#configure-the-destination-repository)
9. [Add GitHub Actions secrets and variables](#add-github-actions-secrets-and-variables)
10. [Enable the workflow and run a manual sync](#enable-the-workflow-and-run-a-manual-sync)
11. [Inspect workflow logs safely](#inspect-workflow-logs-safely)
12. [Difficulty folders and timestamped files](#difficulty-folders-and-timestamped-files)
13. [How duplicate submissions are handled](#how-duplicate-submissions-are-handled)
14. [Run tests locally](#run-tests-locally)
15. [Troubleshooting](#troubleshooting)
16. [Security and privacy](#security-and-privacy)
17. [Contributing and reporting vulnerabilities](#contributing-and-reporting-vulnerabilities)
18. [Disable scheduled synchronization](#disable-scheduled-synchronization)
19. [Running locally with Windows Task Scheduler](#running-locally-with-windows-task-scheduler)

---

## What it does

LeetCode Cloud Sync is a Python tool that runs inside GitHub Actions on a schedule. Every time it runs, it:

- Fetches your recent submissions from LeetCode's GraphQL API (accepted only, or all statuses depending on configuration).
- Organises them by difficulty (Easy / Medium / Hard / Unknown).
- Commits each new submission as a Markdown file to a GitHub repository of your choice.

Because it runs on GitHub's servers, synchronisation works regardless of which device you submitted from — phone, laptop, library computer, or anything else. No browser extension. No local machine required to stay online.

| | Browser Extension | LeetCode Cloud Sync |
|---|---|---|
| Requires your device to be on | Yes | No |
| Works from any device | No | Yes |
| Runs unattended | No | Yes |
| Stores submissions in GitHub | Depends | Yes |
| Open source and auditable | Varies | Yes |

---

## Architecture and synchronization flow

```
Your LeetCode account (any device)
         │
         ▼  (GitHub Actions cron, ~5 min — best-effort, not guaranteed)
  GitHub Actions Runner
         │  LeetCode GraphQL API (HTTPS, authenticated)
         ▼
  Python sync agent
     ├─ Fetches submissions (up to FETCH_LIMIT, filtered by SYNC_MODE)
     ├─ Deduplicates against .leetcode_sync_state.json
     ├─ Renders each new submission as a Markdown file
     └─ Commits to the configured destination repository
```

**Source files** (`src/`):

| File | Purpose |
|---|---|
| `config.py` | Loads and validates all environment variables |
| `leetcode_client.py` | Fetches submissions via LeetCode's GraphQL API |
| `github_client.py` | Writes files to GitHub via the Contents REST API |
| `organizer.py` | Determines difficulty directory and file path |
| `markdown_writer.py` | Renders submissions as Markdown |
| `deduplication.py` | Tracks which submission IDs have already been synced |
| `main.py` | Orchestrates the full sync run |
| `diagnose.py` | Validates credentials and connectivity without committing |

---

## Repository architecture: one repo vs. two repos

You can choose either setup:

### Option A — Single repository (simplest)

Everything lives in one repository: the application source code and your solutions.

- No extra token required — `GITHUB_TOKEN` is automatically available in Actions.
- Solutions are committed alongside the application code.

### Option B — Separate submissions repository (recommended for a clean separation)

| Repository | Contents |
|---|---|
| `YOUR_USERNAME/leetcode-cloud-sync` | Python source, tests, CI, documentation |
| `YOUR_USERNAME/leetcode-submissions` | Your generated solution Markdown files only |

Benefits:
- Clean separation between tool source code and personal solutions.
- Contributors to the tool do not see your solutions.
- You can make the submissions repo public or private independently.

**Important:** The built-in `GITHUB_TOKEN` only has write access to the repository it runs in. To write to `YOUR_USERNAME/leetcode-submissions` from a workflow in `YOUR_USERNAME/leetcode-cloud-sync`, you must create a fine-grained personal access token (PAT). See [Configure the destination repository](#configure-the-destination-repository).

> **Public repository warning:** Any solution committed to a public GitHub repository is visible to everyone, including future employers and other LeetCode users. If you want privacy, make your submissions repository private.

---

## Supported configuration options

### Configuration reference

| Variable | Type | Required | Purpose |
|---|---|---|---|
| `LEETCODE_USERNAME` | Variable | Yes | Your LeetCode username |
| `LEETCODE_SESSION` | Secret | Yes | Browser session cookie for API access |
| `LEETCODE_CSRF_TOKEN` | Secret | Yes | CSRF token paired with session cookie |
| `GITHUB_TOKEN` | Auto / Secret | Yes | Token with Contents write on the destination repo |
| `SUBMISSIONS_TOKEN` | Secret | Mode B only | Fine-grained PAT for cross-repo writes (takes precedence over `GITHUB_TOKEN`) |
| `DESTINATION_REPO` | Variable | Yes | Destination repo in `owner/repo` format (e.g., `YOUR_USERNAME/leetcode-submissions`) |
| `GITHUB_BRANCH` | Variable | No | Branch to commit to (default: `main`) |
| `SOLUTIONS_ROOT` | Variable | No | Solutions directory in the destination repo (default: `solutions`) |
| `SYNC_MODE` | Variable | No | `accepted` (only accepted submissions) or `all` (all statuses including WA, TLE, etc.) (default: `accepted`) |
| `FETCH_LIMIT` | Variable | No | Max submissions per run (default: `20`) |
| `LOG_LEVEL` | Variable | No | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` (default: `INFO`) |

### Where each variable belongs

| Variable | GitHub Actions secrets | GitHub Actions variables | Local `.env` |
|---|---|---|---|
| `LEETCODE_SESSION` | Yes | No | Yes (never commit) |
| `LEETCODE_CSRF_TOKEN` | Yes | No | Yes (never commit) |
| `SUBMISSIONS_TOKEN` | Yes | No | Yes (never commit) |
| `GITHUB_TOKEN` | Auto-provided | No | Yes (fine-grained PAT) |
| `LEETCODE_USERNAME` | No | Yes | Yes |
| `DESTINATION_REPO` | No | Yes | Yes |
| `GITHUB_BRANCH` | No | Yes | Yes |
| `SOLUTIONS_ROOT` | No | Yes | Yes |
| `SYNC_MODE` | No | Yes | Yes |
| `FETCH_LIMIT` | No | Yes | Yes |
| `LOG_LEVEL` | No | Yes | Yes |

---

## Prerequisites

- A [GitHub account](https://github.com).
- A [LeetCode account](https://leetcode.com) with at least one accepted submission.
- Python 3.11+ (for local use or development only — cloud runs do not require local Python).

---

## Fork or clone the project

### To use the tool in your own GitHub account (recommended for beginners)

1. Click **Fork** on the [GitHub page](https://github.com/kaviyack/leetcode-cloud-sync).
2. Keep the fork in your own account. The workflow will run in your fork automatically.

### To contribute or develop locally

```bash
git clone https://github.com/kaviyack/leetcode-cloud-sync.git
cd leetcode-cloud-sync
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
# Edit .env — do NOT commit it
```

---

## Configure your LeetCode account

The tool accesses LeetCode's GraphQL API using your browser session cookies. These are required to retrieve submission source code.

### How to get your session cookies

1. Log in to [leetcode.com](https://leetcode.com) in your browser.
2. Open **DevTools**:
   - Chrome/Edge: `F12` → **Application** tab → **Storage** → **Cookies** → `leetcode.com`
   - Firefox: `F12` → **Storage** tab → **Cookies** → `https://leetcode.com`
3. Find the cookie named `LEETCODE_SESSION` and copy its value.
4. Find the cookie named `csrftoken` and copy its value.

> **These cookies are equivalent to your LeetCode password.** Anyone with these values can access your account. Treat them as secrets. Do not paste them into source files, README files, issue comments, or any public place.

Session cookies typically last weeks but expire when you log out, change your password, or LeetCode invalidates them.

---

## Configure the destination repository

### Option A — Same repository

No extra steps needed. The built-in `GITHUB_TOKEN` has write access to the current repository automatically.

Set `DESTINATION_REPO` to your repository name (e.g., `YOUR_USERNAME/leetcode-cloud-sync`) or leave it unset — the workflow defaults to the current repository.

### Option B — Separate submissions repository

#### Step 1: Create the submissions repository

1. Go to [github.com/new](https://github.com/new).
2. Create a repository named `leetcode-submissions` (or any name you prefer).
3. Set visibility: **Public** (visible to everyone) or **Private** (only you).
4. Initialize it with a README so the `main` branch exists.
5. Do **not** clone or push anything else yet.

#### Step 2: Create a fine-grained personal access token (PAT)

The built-in `GITHUB_TOKEN` cannot write to a different repository. You need a PAT.

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens**.
2. Click **Generate new token**.
3. Set:
   - **Token name**: `leetcode-submissions-write` (or any name)
   - **Expiration**: choose an expiry that fits your workflow (e.g., 1 year)
   - **Resource owner**: your account (`YOUR_USERNAME`)
   - **Repository access**: **Only select repositories** → select `leetcode-submissions`
4. Under **Permissions → Repository permissions**:
   - **Contents**: **Read and write**
   - All other permissions: leave as **No access**
5. Click **Generate token** and copy the value immediately. You cannot see it again.

#### Step 3: Add the PAT as a secret in leetcode-cloud-sync

In `YOUR_USERNAME/leetcode-cloud-sync`:
**Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `SUBMISSIONS_TOKEN` | The fine-grained PAT from step 2 |

When `SUBMISSIONS_TOKEN` is set, the workflow uses it instead of `GITHUB_TOKEN` for all API calls to the destination repository.

---

## Add GitHub Actions secrets and variables

In `YOUR_USERNAME/leetcode-cloud-sync`:

### Secrets

**Settings → Secrets and variables → Actions → Secrets → New repository secret**

| Secret name | Value |
|---|---|
| `LEETCODE_SESSION` | Your `LEETCODE_SESSION` cookie value |
| `LEETCODE_CSRF_TOKEN` | Your `csrftoken` cookie value |
| `SUBMISSIONS_TOKEN` | Your fine-grained PAT (Mode B only) |

### Variables

**Settings → Secrets and variables → Actions → Variables → New repository variable**

| Variable name | Value | Notes |
|---|---|---|
| `LEETCODE_USERNAME` | Your LeetCode username (e.g., `user123`) | Not a secret |
| `DESTINATION_REPO` | Destination repo in `owner/repo` format | Mode A: same repo. Mode B: `YOUR_USERNAME/leetcode-submissions` |
| `SYNC_MODE` | `accepted` or `all` | `accepted`: only accepted submissions. `all`: all statuses (WA, TLE, RE, etc.) |
| `GITHUB_BRANCH` | `main` | Optional, defaults to `main` |
| `SOLUTIONS_ROOT` | `solutions` | Optional, defaults to `solutions` |
| `FETCH_LIMIT` | `20` | Optional, max ~40 before rate limits |
| `LOG_LEVEL` | `INFO` | Optional |

### Workflow permissions (Mode A only)

If writing to the same repository:
**Settings → Actions → General → Workflow permissions → Read and write permissions** → Save.

For Mode B, the workflow permission can remain at the default read-only setting because all writes use the `SUBMISSIONS_TOKEN` PAT.

---

## Enable the workflow and run a manual sync

1. Go to the **Actions** tab of `YOUR_USERNAME/leetcode-cloud-sync`.
2. If prompted, click **I understand my workflows, go ahead and enable them**.
3. Select **LeetCode Cloud Sync** from the left sidebar.
4. Click **Run workflow** → **Run workflow** to trigger a one-time manual sync.
5. Watch the run complete. If successful, new files appear in the destination repository under `solutions/`.

The workflow also runs automatically on a 5-minute cron schedule.

> **Schedule caveat:** GitHub Actions cron schedules are best-effort. A 5-minute schedule may be delayed by minutes or hours during high platform load. This tool cannot guarantee that a new submission appears in your repository within exactly 5 minutes.

---

## Inspect workflow logs safely

1. Go to the **Actions** tab.
2. Click the most recent **LeetCode Cloud Sync** run.
3. Click the **Sync LeetCode Submissions** job.
4. Expand **Run synchronization** to see detailed log output.

The application never logs session cookies, CSRF tokens, or `GITHUB_TOKEN` values. If you ever see a credential value in a log line, please report it as a security issue.

---

## Difficulty folders and timestamped files

Solutions are stored under the `solutions/` directory (or the value of `SOLUTIONS_ROOT`) in the destination repository:

```
solutions/
├── easy/
│   └── 0001-two-sum/
│       └── 20261026_2015_python3_1234567890.md
├── medium/
│   └── 0006-zigzag-conversion/
│       └── 20261026_2030_java_9876543210.md
├── hard/
└── unknown/      ← used when difficulty cannot be determined
```

**Filename format:** `<YYYYMMDD>_<HHMM>_<language>_<submission_id>.md`

The submission ID in the filename guarantees uniqueness — two attempts at the same problem on the same day produce two separate files.

Each file contains:

- Problem number, title, and link to leetcode.com
- Difficulty, topic tags, language
- Submission ID and UTC timestamp
- Status, runtime, and memory usage
- Full submitted source code
- A complexity section (fill in manually)

**Problem statements are not reproduced** — only a link is provided, to respect LeetCode's content restrictions.

---

## How duplicate submissions are handled

The deduplication store (`.leetcode_sync_state.json`) tracks every submission ID that has been written.

| Scenario | Result |
|---|---|
| Same problem submitted again | New file created (different submission ID) |
| Same problem in a different language | Both files preserved |
| Identical code resubmitted (new ID) | New file created |
| Same submission seen on multiple polling runs | Written only once (deduplicated) |
| Existing submission file | Never overwritten |

The state file is committed to the destination repository so all workflow runs share the same deduplication state.

---

## Run tests locally

```bash
# Install dependencies (if not already done)
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run type checking
mypy src/ --ignore-missing-imports --no-strict-optional

# Run linter
ruff check src/ tests/
```

Tests do not require LeetCode credentials or network access. All external API calls are mocked.

---

## Troubleshooting

### Authentication failed / 403 Forbidden

**Cause:** The `LEETCODE_SESSION` cookie has expired or been invalidated.

**Fix:**
1. Log in to leetcode.com in your browser.
2. Copy the new `LEETCODE_SESSION` and `csrftoken` values.
3. Update both secrets in **Settings → Secrets and variables → Actions**.
4. Re-run the workflow.

### 403 Forbidden when writing to the destination repository

**Cause:** `GITHUB_TOKEN` does not have write access to the destination repository.

**Fix (Mode B):** Ensure `SUBMISSIONS_TOKEN` is set as a secret and contains a valid fine-grained PAT with Contents write permission on the destination repository.

### No new files appear after the workflow runs successfully

**Possible causes:**
- All recent submissions were already synced (check `.leetcode_sync_state.json`).
- The `FETCH_LIMIT` is lower than the number of new submissions since the last run.

**Fix:** Trigger a manual run and set `fetch_limit` to a higher value (e.g. `100`) to catch up on older submissions.

### submissionList returned null

**Cause:** The session cookie is expired or the CSRF token does not match.

**Fix:** Refresh both `LEETCODE_SESSION` and `LEETCODE_CSRF_TOKEN` and update the secrets.

### Rate limited (HTTP 429)

**Cause:** Too many requests to LeetCode in a short time.

**Fix:** Reduce `FETCH_LIMIT` or increase the cron interval.

---

## Security and privacy

- **Public repository = public solutions.** Any solution committed to a public GitHub repository is visible to everyone. Use a private repository if you want privacy.
- Credentials are stored only as GitHub Actions secrets (encrypted at rest, never printed in logs).
- The source code never logs session cookies or tokens.
- HTTPS is used for all API calls.
- The `SUBMISSIONS_TOKEN` PAT is scoped to the destination repository with Contents write only — no other repositories or permissions.
- **No official LeetCode API.** This tool uses LeetCode's internal GraphQL endpoint, which LeetCode may change or restrict without notice. If the API changes, the tool may stop working until updated.
- **Session cookies expire.** You will need to refresh them manually when they expire.
- **Schedule is best-effort.** GitHub Actions does not guarantee 5-minute delivery.
- **Fetch limit.** Each run fetches only the most recent N accepted submissions. Very old submissions may require a higher `FETCH_LIMIT` on a manual run.

---

## Contributing and reporting vulnerabilities

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and contribution guidelines.

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards.

To report a security vulnerability, do **not** open a public issue. See [SECURITY.md](SECURITY.md) for responsible disclosure instructions.

---

## Disable scheduled synchronization

To pause syncing without deleting anything:

- Go to **Actions → LeetCode Cloud Sync** → click the `...` menu → **Disable workflow**.

To stop permanently:

- Delete `.github/workflows/leetcode-sync.yml` from the repository.

---

## Running locally with Windows Task Scheduler

If you prefer running the background watcher locally on Windows instead of (or in addition to) GitHub Actions, you can set up a Windows Scheduled Task:

1. Configure your credentials securely in a local `.env` file (see [Fork or clone the project](#fork-or-clone-the-project)).
2. Register the scheduled task at logon by running:
   ```powershell
   .\scripts\setup-task.ps1
   ```
3. View logs at `logs/watcher.log` (rotation enabled).
4. To uninstall the task:
   ```powershell
   .\scripts\uninstall-task.ps1
   ```

See the full guide in [docs/windows-task-scheduler.md](docs/windows-task-scheduler.md) for detailed configuration, checking task status, log rotation, and troubleshooting.

---

## License

[MIT](LICENSE)
