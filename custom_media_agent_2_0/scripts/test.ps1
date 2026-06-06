$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    & (Join-Path $PSScriptRoot "setup_venv.ps1")
}

Push-Location $ProjectRoot
try {
    & $VenvPython -m pytest -q
    & $VenvPython -m compileall app
}
finally {
    Pop-Location
}
