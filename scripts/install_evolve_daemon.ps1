<#
  install_evolve_daemon.ps1 — turn SINGULARITY's self-evolution into a real 24/7
  background daemon via a Windows Scheduled Task.

  The task runs `python -m singularity evolve` (the self-learning loop: pursue
  standing objectives, self-reflect via the LLM into lessons, re-discover
  capabilities, improve routing) at every logon, restarting on failure, so the
  organism keeps learning around the clock — no manual start needed.

  Usage (from the repo root):
      powershell -ExecutionPolicy Bypass -File scripts\install_evolve_daemon.ps1
      # custom goals / cadence:
      ... -File scripts\install_evolve_daemon.ps1 -IntervalSeconds 1800 -Goals "scan the market","audit my skills"

  Remove it:  Unregister-ScheduledTask -TaskName "SINGULARITY-Evolve" -Confirm:$false
  Start now:  Start-ScheduledTask -TaskName "SINGULARITY-Evolve"
#>
param(
  [int]$IntervalSeconds = 1800,
  [string[]]$Goals = @("scan the market", "audit my skills for gaps", "check system health"),
  [string]$TaskName = "SINGULARITY-Evolve"
)

$ErrorActionPreference = "Stop"
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue).Source }
if (-not $py) { throw "python not found on PATH" }

# Run from the repo root (this script lives in <repo>/scripts).
$repo = Split-Path -Parent $PSScriptRoot
$goalArgs = ($Goals | ForEach-Object { '"' + $_ + '"' }) -join ' '
$argline = "-m singularity evolve $goalArgs --interval $IntervalSeconds"

Write-Host "python : $py"
Write-Host "repo   : $repo"
Write-Host "command: python $argline"

$action   = New-ScheduledTaskAction   -Execute $py -Argument $argline -WorkingDirectory $repo
$trigger  = New-ScheduledTaskTrigger   -AtLogOn
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
              -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 5) `
              -ExecutionTimeLimit ([TimeSpan]::Zero)   # run indefinitely

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Description "JARVIS / SINGULARITY 24/7 self-learning loop" -Force | Out-Null

Write-Host ""
Write-Host "Registered scheduled task '$TaskName' — JARVIS self-evolves at every logon."
Write-Host "Start it now:  Start-ScheduledTask -TaskName $TaskName"
Write-Host "Watch it:      Get-ScheduledTaskInfo -TaskName $TaskName"
Write-Host "Stop/remove:   Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
