$ErrorActionPreference = "Stop"

param(
    [int]$Port = 8020
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    & (Join-Path $PSScriptRoot "setup_venv.ps1")
}

Push-Location $ProjectRoot
try {
    & $VenvPython -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
}
finally {
    Pop-Location
}
