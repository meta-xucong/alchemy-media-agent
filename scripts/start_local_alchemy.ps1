$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$composeFiles = @(
    (Join-Path $repoRoot 'docker-compose.yml'),
    (Join-Path $repoRoot '.runtime\render-bridge-local\docker-compose.loopback.yml'),
    (Join-Path $repoRoot 'docker-compose.local-source-build.yml')
)

foreach ($composeFile in $composeFiles) {
    if (-not (Test-Path -LiteralPath $composeFile -PathType Leaf)) {
        throw "Required local Compose file is missing: $composeFile"
    }
}

$revisionOutput = & git -C $repoRoot rev-parse --verify HEAD 2>$null
$gitExitCode = $LASTEXITCODE
$revision = ($revisionOutput -join '').Trim()
if ($gitExitCode -ne 0 -or $revision -notmatch '^[0-9a-fA-F]{40}$') {
    throw 'Could not read the current Alchemy Git revision.'
}

$buildInputPaths = @(
    'src_skeleton/Dockerfile',
    'src_skeleton/requirements.txt',
    'src_skeleton/app',
    'scripts/fetch_v3_identity_models.py',
    'render_bridge_primary',
    'alchemy_creative_agent_3_0/__init__.py',
    'alchemy_creative_agent_3_0/app'
)
$gitStatusArgs = @('status', '--porcelain', '--untracked-files=all', '--') + $buildInputPaths
$buildInputStatus = @(& git -C $repoRoot @gitStatusArgs)
if ($LASTEXITCODE -ne 0) {
    throw 'Could not verify that the Docker build inputs match the Git revision.'
}
if ($buildInputStatus.Count -gt 0) {
    throw "Docker build inputs contain uncommitted changes; refusing to label the image as Git revision $revision.`n$($buildInputStatus -join "`n")"
}

$env:ALCHEMY_REVISION = $revision

$docker = Get-Command docker -CommandType Application -ErrorAction Stop
$composeArgs = @('compose', '--project-directory', $repoRoot)
foreach ($composeFile in $composeFiles) {
    $composeArgs += @('-f', $composeFile)
}

Write-Host "Validating local Alchemy Compose configuration for revision $revision..." -ForegroundColor Cyan
$previousPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    & $docker.Source @composeArgs config --quiet
    $composeExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousPreference
}
if ($composeExitCode -ne 0) {
    throw "Local Alchemy Compose configuration failed with exit code $composeExitCode. The running service was not changed."
}

Write-Host 'Building Alchemy from the current checkout...' -ForegroundColor Cyan
try {
    $ErrorActionPreference = 'Continue'
    & $docker.Source @composeArgs build alchemy-media-agent
    $composeExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousPreference
}
if ($composeExitCode -ne 0) {
    throw "Local Alchemy build failed with exit code $composeExitCode. The running service was not changed."
}

$imageRevisionOutput = & $docker.Source image inspect alchemy-media-agent:bridge-local --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' 2>$null
$imageInspectExitCode = $LASTEXITCODE
$imageRevision = ($imageRevisionOutput -join '').Trim()
if ($imageInspectExitCode -ne 0 -or $imageRevision -ne $revision) {
    throw 'The newly built Alchemy image does not report the current Git revision. The running service was not changed.'
}

Write-Host 'Starting only the Alchemy service...' -ForegroundColor Cyan
try {
    $ErrorActionPreference = 'Continue'
    & $docker.Source @composeArgs up -d --no-build --no-deps alchemy-media-agent
    $composeExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousPreference
}
if ($composeExitCode -ne 0) {
    throw "Local Alchemy start failed with exit code $composeExitCode."
}

Write-Host "Alchemy started from Git revision $imageRevision." -ForegroundColor Green
