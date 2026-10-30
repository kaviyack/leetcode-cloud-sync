# Windows Task Scheduler Support for LeetCode Cloud Sync

LeetCode Cloud Sync supports running the background watcher (`src.watcher`) continuously as a Windows background task via **Windows Task Scheduler**. This allows your submissions to sync automatically whenever you log into Windows, without needing a browser extension or keeping a GitHub Actions cron runner active.

---

## Table of contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Secure configuration of environment variables](#secure-configuration-of-environment-variables)
4. [Installing the scheduled task](#installing-the-scheduled-task)
5. [Checking task status and running immediately](#checking-task-status-and-running-immediately)
6. [Viewing logs and log rotation](#viewing-logs-and-log-rotation)
7. [Stopping the watcher](#stopping-the-watcher)
8. [Uninstalling the task](#uninstalling-the-task)
9. [Troubleshooting](#troubleshooting)

---

## Overview

When configured:
- Windows Task Scheduler triggers `python -m src.watcher` at your user logon (`AtLogOn`).
- The task runs in the background using your project's virtual environment Python interpreter and repository root working directory.
- Concurrency control ensures only one instance runs at a time (`IgnoreNew`).
- Automatic failure recovery restarts the task if it encounters an unexpected interruption.
- Logs are rotated automatically in a project-local `logs/watcher.log` file.

---

## Prerequisites

- Windows 10 or Windows 11.
- Python 3.11+ installed with the project virtual environment set up (`.venv`).
- Required dependencies installed (`pip install -r requirements.txt`).

---

## Secure configuration of environment variables

**Important (Security Requirement 6):** Secrets such as `LEETCODE_SESSION`, `LEETCODE_CSRF_TOKEN`, and `GITHUB_TOKEN` / `SUBMISSIONS_TOKEN` must **never** be hardcoded into scripts, task arguments, command lines, or logs.

Environment variables can be supplied securely using either of two methods:

### Method 1: Local `.env` file (Recommended for development)
1. Copy `.env.example` to `.env` in the repository root:
   ```powershell
   copy .env.example .env
   ```
2. Open `.env` and fill in your LeetCode and GitHub credentials.
3. The watcher automatically loads `.env` via `python-dotenv` upon startup.
4. Ensure `.env` is listed in your `.gitignore` so it is never committed or pushed to GitHub.

### Method 2: Windows User Environment Variables
1. Press `Win + R`, type `sysdm.cpl`, and press Enter.
2. Go to the **Advanced** tab and click **Environment Variables...**.
3. Under **User variables for your username**, click **New...** and add required variables:
   - `LEETCODE_USERNAME`
   - `LEETCODE_SESSION`
   - `LEETCODE_CSRF_TOKEN`
   - `GITHUB_REPO`
   - `GITHUB_TOKEN` (or `SUBMISSIONS_TOKEN`)
4. Click OK and restart any open PowerShell windows. Task Scheduler inherits user environment variables automatically.

---

## Installing the scheduled task

To register the scheduled task:

1. Open PowerShell **normally** (Administrator elevation is **not** required because the task runs under your user account at logon).
2. Navigate to the repository directory:
   ```powershell
   cd C:\path\to\leetcode-cloud-sync
   ```
3. Run the setup script:
   ```powershell
   .\scripts\setup-task.ps1
   ```

The script automatically:
- Detects the project virtual environment python (`.venv\Scripts\python.exe`) or falls back to system Python.
- Sets the correct absolute working directory.
- Registers a task named `LeetCodeCloudSyncWatcher` triggered at logon.
- Configures multi-instance prevention and automatic failure restart.

---

## Checking task status and running immediately

### Check status
```powershell
Get-ScheduledTask -TaskName "LeetCodeCloudSyncWatcher"
Get-ScheduledTaskInfo -TaskName "LeetCodeCloudSyncWatcher"
```

### Start immediately (without waiting for login)
```powershell
Start-ScheduledTask -TaskName "LeetCodeCloudSyncWatcher"
```

---

## Viewing logs and log rotation

Logs are written to project-local:
`logs/watcher.log`

### View recent log output
```powershell
Get-Content logs\watcher.log -Tail 50
```

### Log rotation
- The watcher uses Python's `RotatingFileHandler`.
- Max file size: **5 MB**.
- Backup count: **3** (`watcher.log`, `watcher.log.1`, `watcher.log.2`, `watcher.log.3`).
- This prevents log files from growing indefinitely.

---

## Stopping the watcher

To stop a running instance of the watcher task:
```powershell
Stop-ScheduledTask -TaskName "LeetCodeCloudSyncWatcher"
```

---

## Uninstalling the task

To completely remove the Windows Scheduled Task (leaving your project code and logs intact):

1. Open PowerShell in the project directory.
2. Run the uninstall script:
   ```powershell
   .\scripts\uninstall-task.ps1
   ```

---

## Troubleshooting

### Task does not start at logon
- Ensure your user account remains logged in (Task Scheduler `AtLogOn` triggers when the user logs into the session).
- Check `Get-ScheduledTaskInfo` for `LastTaskResult`. A result of `0` indicates success; non-zero indicates an error code.

### Python or module not found error in logs
- Verify that `.venv\Scripts\python.exe` exists and dependencies are installed (`pip install -r requirements.txt`).
- Re-run `.\scripts\setup-task.ps1` to re-bind the correct Python executable path.

### Authentication errors (403 / AuthError)
- Your `LEETCODE_SESSION` cookie has expired. Refresh your cookies from leetcode.com and update them in your `.env` file or Windows Environment Variables.
