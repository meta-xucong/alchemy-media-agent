$ErrorActionPreference = "Stop"

param(
    [string]$WorkerId = "v2-standalone-worker"
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    & (Join-Path $PSScriptRoot "setup_venv.ps1")
}

Push-Location $ProjectRoot
try {
    & $VenvPython -m app.workers.task_queue_worker --worker-id $WorkerId
}
finally {
    Pop-Location
}
