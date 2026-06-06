param(
    [string]$OutputPath,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $OutputPath) {
    $OutputPath = Join-Path $repoRoot "src_skeleton\.env"
}

if ((Test-Path -LiteralPath $OutputPath) -and -not $Force) {
    throw "Refusing to overwrite $OutputPath. Re-run with -Force if this is intended."
}

function Get-EnvOrDefault {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$Default = ""
    )
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value
}

function Get-CodexOpenAIKey {
    $authPath = Join-Path $env:USERPROFILE ".codex\auth.json"
    if (-not (Test-Path -LiteralPath $authPath)) {
        return ""
    }
    try {
        $auth = Get-Content -LiteralPath $authPath -Raw | ConvertFrom-Json
        return [string]$auth.OPENAI_API_KEY
    } catch {
        return ""
    }
}

function Get-ClaudeToken {
    $settingsPath = Join-Path $env:USERPROFILE ".claude\settings.json"
    if (-not (Test-Path -LiteralPath $settingsPath)) {
        return ""
    }
    try {
        $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
        return [string]$settings.env.ANTHROPIC_AUTH_TOKEN
    } catch {
        return ""
    }
}

$openaiKey = Get-EnvOrDefault "OPENAI_API_KEY" (Get-CodexOpenAIKey)
$anthropicToken = Get-EnvOrDefault "ANTHROPIC_AUTH_TOKEN" (Get-ClaudeToken)

$lines = @(
    "MEDIA_AGENT_MODE=live",
    "MOCK_IMAGE_PROVIDER_ENABLED=false",
    "ORCHESTRATION_MODE=runtime_first",
    "",
    "DEFAULT_IMAGE_PROVIDER=openai_gpt_image",
    "DEFAULT_IMAGE_MODEL=gpt-image-2",
    "OPENAI_IMAGE_MODEL=gpt-image-2",
    "GEMINI_IMAGE_MODEL=gemini-3-pro-image-preview",
    "GEMINI_IMAGE_BASE_URL=",
    "",
    "DEFAULT_LLM_PROVIDER=anthropic",
    "DEFAULT_LLM_MODEL=kimi-for-coding",
    "BACKUP_LLM_PROVIDER=openai",
    "BACKUP_LLM_MODEL=gpt-5.5",
    "OPENAI_LLM_MODEL=gpt-5.5",
    "KIMI_LLM_MODEL=kimi-for-coding",
    "LLM_PROMPT_PLANNING_ENABLED=true",
    "IMAGE_WORK_INTENSITY=atelier",
    "",
    "DEFAULT_VIDEO_PROVIDER=seedance",
    "",
    "OPENAI_API_KEY=$openaiKey",
    "OPENAI_BASE_URL=https://aiself.vip/v1",
    "ANTHROPIC_API_KEY=",
    "ANTHROPIC_AUTH_TOKEN=$anthropicToken",
    "ANTHROPIC_BASE_URL=https://aiself.vip",
    "GEMINI_IMAGE_API_KEY=",
    "BYTEPLUS_API_KEY=",
    "",
    "MEDIA_STORAGE_ROOT=.media_storage"
)

$parent = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $parent | Out-Null
Set-Content -LiteralPath $OutputPath -Value $lines -Encoding UTF8

Write-Host "Wrote $OutputPath"
if (-not $openaiKey) {
    Write-Host "OPENAI_API_KEY was not found in environment or %USERPROFILE%\.codex\auth.json"
}
if (-not $anthropicToken) {
    Write-Host "ANTHROPIC_AUTH_TOKEN was not found in environment or %USERPROFILE%\.claude\settings.json"
}
