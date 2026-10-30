<#
.SYNOPSIS
    Registers the LeetCode Cloud Sync Watcher as a Windows Scheduled Task at user logon.
.DESCRIPTION
    This script creates a Windows Scheduled Task named 'LeetCodeCloudSyncWatcher' that runs
    the Python background watcher (`python -m src.watcher`) whenever the current user logs on.
    It uses the virtual environment Python interpreter (if present) and the repository root
    as the working directory. It prevents concurrent instances and configures failure restarts.
#>

[CmdletBinding()]
param(
    [string]$TaskName = "LeetCodeCloudSyncWatcher",
    [string]$PythonPath,
    [string]$WorkDir
)

$ErrorActionPreference = "Stop"

# Determine repository root (assumes script is in <repo>/scripts/)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $WorkDir) {
    $WorkDir = (Resolve-Path "$ScriptDir\..").Path
}

# Determine Python executable
if (-not $PythonPath) {
    $VenvPython = Join-Path $WorkDir ".venv\Scripts\python.exe"
    if (Test-Path $VenvPython) {
        $PythonPath = (Resolve-Path $VenvPython).Path
    } else {
        $SysPython = Get-Command python -ErrorAction SilentlyContinue
        if ($SysPython) {
            $PythonPath = $SysPython.Source
        } else {
            throw "Python executable not found. Please specify -PythonPath or create a virtual environment at .venv."
        }
    }
}

Write-Host "Configuring Windows Scheduled Task..." -ForegroundColor Cyan
Write-Host "  Task Name        : $TaskName"
Write-Host "  Working Directory: $WorkDir"
Write-Host "  Python Path      : $PythonPath"
Write-Host "  Action           : -m src.watcher"

$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "-m src.watcher" -WorkingDirectory $WorkDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn

# Settings: prevent multiple instances, run on demand, restart on failure
$Settings = New-ScheduledTaskSettingsSet `
    -MultipleInstance IgnoreNew `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Days 365)

# Register task for current user
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Background watcher for LeetCode Cloud Sync — automatically syncs submissions on startup." `
    -Force

Write-Host "`nSuccessfully registered scheduled task '$TaskName'!" -ForegroundColor Green
Write-Host "The watcher will start automatically at your next Windows login."
Write-Host "To start the task immediately now without waiting for login, run:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Yellow
Write-Host "To check task status, run:"
Write-Host "  Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Yellow
Write-Host "To view logs, check: $WorkDir\logs\watcher.log" -ForegroundColor Yellow
