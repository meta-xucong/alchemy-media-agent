$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    $VenvPath = Join-Path $ProjectRoot ".venv"
    $PythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    $UvCommand = Get-Command uv -ErrorAction SilentlyContinue

    if ($PythonLauncher) {
        & $PythonLauncher.Source -3 -m venv $VenvPath
    }
    elseif ($PythonCommand) {
        & $PythonCommand.Source -m venv $VenvPath
    }
    elseif ($UvCommand) {
        & $UvCommand.Source venv $VenvPath
    }
    else {
        throw "Python launcher, python, and uv were not found; install Python or uv before setting up V2."
    }
    if ($LASTEXITCODE -ne 0) {
        throw "V2 virtual environment creation failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path $VenvPython)) {
    throw "V2 virtual environment did not create its Python interpreter: $VenvPython."
}

& $VenvPython -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) {
    throw "V2 pip bootstrap failed with exit code $LASTEXITCODE."
}

& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "V2 pip upgrade failed with exit code $LASTEXITCODE."
}
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "V2 dependency installation failed with exit code $LASTEXITCODE."
}
& $VenvPython -m pip install -e (Join-Path (Split-Path -Parent $ProjectRoot) "render_bridge_primary")
if ($LASTEXITCODE -ne 0) {
    throw "V2 RenderBridge shared package installation failed with exit code $LASTEXITCODE."
}
& $VenvPython -m pip check
if ($LASTEXITCODE -ne 0) {
    throw "V2 dependency check failed with exit code $LASTEXITCODE."
}

Write-Host "Custom Media Agent 2.0 venv is ready: $VenvPython"
