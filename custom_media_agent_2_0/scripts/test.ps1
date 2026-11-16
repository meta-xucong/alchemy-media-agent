$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    & (Join-Path $PSScriptRoot "setup_venv.ps1")
    $SetupSucceeded = $?
    $SetupExitCode = $LASTEXITCODE
    if (-not $SetupSucceeded -or $SetupExitCode -ne 0) {
        throw "V2 virtual environment setup failed with exit code $SetupExitCode."
    }
}

Push-Location $ProjectRoot
try {
    & $VenvPython -m pip --version *> $null
    if ($LASTEXITCODE -ne 0) {
        & $VenvPython -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) {
            throw "V2 pip bootstrap failed with exit code $LASTEXITCODE."
        }
    }

    $BridgePrimaryPath = Join-Path (Split-Path -Parent $ProjectRoot) "render_bridge_primary"
    & $VenvPython -m pip install --no-deps --editable $BridgePrimaryPath
    if ($LASTEXITCODE -ne 0) {
        throw "V2 RenderBridge shared package install failed with exit code $LASTEXITCODE."
    }

    & $VenvPython -m pytest -q
    if ($LASTEXITCODE -ne 0) {
        throw "V2 pytest failed with exit code $LASTEXITCODE."
    }

    & $VenvPython -m compileall app
    if ($LASTEXITCODE -ne 0) {
        throw "V2 compileall failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
