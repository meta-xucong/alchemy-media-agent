$ErrorActionPreference = "Stop"

param(
    [string]$Mode = "auto",
    [int]$IntervalMinutes = 360
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    & (Join-Path $PSScriptRoot "setup_venv.ps1")
}

Push-Location $ProjectRoot
try {
    & $VenvPython -m app.workers.resource_sync_worker --mode $Mode --interval-minutes $IntervalMinutes
}
finally {
    Pop-Location
}
