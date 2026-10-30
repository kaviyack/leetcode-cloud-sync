<#
.SYNOPSIS
    Uninstalls the LeetCode Cloud Sync Windows Scheduled Task.
.DESCRIPTION
    Removes the 'LeetCodeCloudSyncWatcher' scheduled task created by setup-task.ps1.
    Does not delete project files or logs.
#>

[CmdletBinding()]
param(
    [string]$TaskName = "LeetCodeCloudSyncWatcher"
)

$ErrorActionPreference = "Stop"

Write-Host "Removing Windows Scheduled Task '$TaskName'..." -ForegroundColor Cyan

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
    # Stop task if running
    $State = (Get-ScheduledTask -TaskName $TaskName).State
    if ($State -eq "Running") {
        Write-Host "Stopping running task..."
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Successfully removed scheduled task '$TaskName'." -ForegroundColor Green
} else {
    Write-Host "Task '$TaskName' was not found (already uninstalled or never registered)." -ForegroundColor Yellow
}
