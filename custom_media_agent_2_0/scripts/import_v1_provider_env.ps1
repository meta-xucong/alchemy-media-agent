param(
    [string]$V1EnvPath = "",
    [string]$V2EnvPath = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Read-EnvFile {
    param([string]$Path)
    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        return $values
    }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        if ($trimmed.StartsWith("export ")) {
            $trimmed = $trimmed.Substring(7).Trim()
        }
        $key, $value = $trimmed.Split("=", 2)
        $values[$key.Trim()] = $value.Trim().Trim('"').Trim("'")
    }
    return $values
}

function Write-EnvFile {
    param(
        [string]$Path,
        [hashtable]$Values
    )
    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $lines = @()
    foreach ($key in ($Values.Keys | Sort-Object)) {
        $value = [string]$Values[$key]
        $value = $value.Replace("`r", "").Replace("`n", "").Trim()
        $lines += "$key=$value"
    }
    Set-Content -LiteralPath $Path -Value $lines -Encoding UTF8
}

function Read-CodexAuthValue {
    param([string]$Name)
    $authPath = if ($env:CODEX_AUTH_FILE) { $env:CODEX_AUTH_FILE } else { Join-Path $env:USERPROFILE ".codex\auth.json" }
    if (-not (Test-Path -LiteralPath $authPath)) {
        return ""
    }
    try {
        $payload = Get-Content -LiteralPath $authPath -Raw | ConvertFrom-Json
        $value = $payload.$Name
        if ($value) { return [string]$value }
    }
    catch {
        return ""
    }
    return ""
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $ProjectRoot
if (-not $V1EnvPath) {
    $V1EnvPath = Join-Path $RepoRoot "custom_media_agent_docs\src_skeleton\.env"
}
if (-not $V2EnvPath) {
    $V2EnvPath = Join-Path $ProjectRoot ".env"
}

$v1 = Read-EnvFile -Path $V1EnvPath
$v2 = Read-EnvFile -Path $V2EnvPath

function Set-MappedValue {
    param(
        [string]$Target,
        [string[]]$Sources
    )
    if (-not $Force -and $v2.ContainsKey($Target) -and $v2[$Target]) {
        return
    }
    foreach ($source in $Sources) {
        if ($v1.ContainsKey($source) -and $v1[$source]) {
            $v2[$Target] = $v1[$source]
            return
        }
    }
}

Set-MappedValue -Target "V2_OPENAI_API_KEY" -Sources @("OPENAI_API_KEY")
if ((-not $v2.ContainsKey("V2_OPENAI_API_KEY") -or -not $v2["V2_OPENAI_API_KEY"] -or $Force)) {
    $codexOpenAIKey = Read-CodexAuthValue -Name "OPENAI_API_KEY"
    if ($codexOpenAIKey) {
        $v2["V2_OPENAI_API_KEY"] = $codexOpenAIKey
    }
}
Set-MappedValue -Target "V2_OPENAI_BASE_URL" -Sources @("OPENAI_BASE_URL", "OPENAI_API_BASE")
Set-MappedValue -Target "V2_OPENAI_IMAGE_MODEL" -Sources @("OPENAI_IMAGE_MODEL", "DEFAULT_IMAGE_MODEL")
Set-MappedValue -Target "V2_GEMINI_API_KEY" -Sources @("GEMINI_IMAGE_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")
Set-MappedValue -Target "V2_GEMINI_BASE_URL" -Sources @("GEMINI_IMAGE_BASE_URL", "GOOGLE_GEMINI_BASE_URL")
Set-MappedValue -Target "V2_GEMINI_IMAGE_MODEL" -Sources @("GEMINI_IMAGE_MODEL", "GEMINI_MODEL")

if (-not $v2.ContainsKey("V2_IMAGE_GENERATION_PROVIDER") -or -not $v2["V2_IMAGE_GENERATION_PROVIDER"] -or $Force) {
    if ($v2.ContainsKey("V2_OPENAI_API_KEY") -and $v2["V2_OPENAI_API_KEY"]) {
        $v2["V2_IMAGE_GENERATION_PROVIDER"] = "openai_gpt_image"
    }
    elseif ($v2.ContainsKey("V2_GEMINI_API_KEY") -and $v2["V2_GEMINI_API_KEY"]) {
        $v2["V2_IMAGE_GENERATION_PROVIDER"] = "gemini_image"
    }
    else {
        $v2["V2_IMAGE_GENERATION_PROVIDER"] = "auto"
    }
}

if (-not $v2.ContainsKey("V2_ALLOW_MOCK_FALLBACK")) {
    $v2["V2_ALLOW_MOCK_FALLBACK"] = "true"
}
if (-not $v2.ContainsKey("V2_CLAUDE_ORCHESTRATOR_ENABLED")) {
    $v2["V2_CLAUDE_ORCHESTRATOR_ENABLED"] = "true"
}

Write-EnvFile -Path $V2EnvPath -Values $v2

$configured = @()
if ($v2.ContainsKey("V2_OPENAI_API_KEY") -and $v2["V2_OPENAI_API_KEY"]) { $configured += "openai_gpt_image" }
if ($v2.ContainsKey("V2_GEMINI_API_KEY") -and $v2["V2_GEMINI_API_KEY"]) { $configured += "gemini_image" }
if (-not $configured.Count) { $configured += "none" }
Write-Host "V2 provider env written: $V2EnvPath"
Write-Host "Configured live providers: $($configured -join ', ')"
