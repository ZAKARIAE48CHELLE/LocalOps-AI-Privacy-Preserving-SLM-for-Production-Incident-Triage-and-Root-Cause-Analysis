<#
.SYNOPSIS
    LocalOps AI — 1-Click PowerShell System Launcher
.DESCRIPTION
    Launches the full LocalOps AI stack:
    - Verifies CUDA GPU environment and model checkpoint
    - Compiles frontend dashboard if needed
    - Starts the unified FastAPI backend
    - Automatically opens the Operator Dashboard in your browser
#>

param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8000,
    [switch]$NoBrowser,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# Determine Python path
$PythonExe = "python"
if (Test-Path ".venv\Scripts\python.exe") {
    $PythonExe = ".venv\Scripts\python.exe"
} elseif (Test-Path "venv\Scripts\python.exe") {
    $PythonExe = "venv\Scripts\python.exe"
}

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "          LocalOps AI — PowerShell Launcher                     " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "Interpreter: $PythonExe" -ForegroundColor DarkGray

$argsList = @("scripts/run_all.py", "--host", $HostAddress, "--port", $Port)
if ($NoBrowser) { $argsList += "--no-browser" }
if ($Reload) { $argsList += "--reload" }

& $PythonExe $argsList
