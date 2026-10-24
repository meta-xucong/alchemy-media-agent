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

$openaiKey = Get-EnvOrDefault "OPENAI_API_KEY" (Get-CodexOpenAIKey)
$llmGatewayKey = Get-EnvOrDefault "LLM_GATEWAY_API_KEY"

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
    "DEFAULT_LLM_MODEL=claude-sonnet-5-5",
    "BACKUP_LLM_PROVIDER=openai",
    "BACKUP_LLM_MODEL=kimi-k3",
    "OPENAI_LLM_MODEL=gpt-6.1-sol",
    "V3_LLM_BRAIN_ENABLED=true",
    "V3_LLM_BRAIN_REMOTE_ENABLED=true",
    "V3_LLM_BRAIN_PROVIDER=anthropic",
    "V3_LLM_BRAIN_MODEL=claude-sonnet-5-5",
    "V3_LLM_BRAIN_BACKUP_MODEL=kimi-k3",
    "V3_LLM_BRAIN_TRANSPORT=chat_nonstream",
    "V3_LLM_BRAIN_TIMEOUT_SECONDS=300",
    "V3_LLM_BRAIN_EXECUTION_BUDGET_SECONDS=2200",
    "V3_LLM_BRAIN_MAX_TOKENS=20000",
    "V3_VISION_INSPECTION_ENABLED=true",
    "KIMI_LLM_MODEL=kimi-for-coding",
    "DEEPSEEK_LLM_MODEL=deepseek-v4-pro-260425",
    "DEEPSEEK_LLM_BASE_URL=https://aiself.vip",
    "LAB_LLM_PROVIDER=anthropic",
    "LAB_LLM_MODEL=claude-sonnet-5-5",
    "LAB_VISION_PROVIDER=openai",
    "V3_VISION_INSPECTION_PROTOCOL=chat_completions",
    "LLM_PROMPT_PLANNING_ENABLED=true",
    "IMAGE_WORK_INTENSITY=atelier",
    "",
    "",
    "OPENAI_API_KEY=$openaiKey",
    "OPENAI_BASE_URL=https://aiself.vip/v1",
    "LLM_GATEWAY_API_KEY=$llmGatewayKey",
    "LLM_GATEWAY_BASE_URL=https://aiself.vip/v1",
    "LAB_DOUBAO_VISION_API_KEY=",
    "LAB_DOUBAO_VISION_BASE_URL=https://aiself.vip/v1",
    "LAB_DOUBAO_VISION_MODEL=doubao-seed-2-0-lite-260428",
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
if (-not $llmGatewayKey) {
    Write-Host "Set LLM_GATEWAY_API_KEY explicitly; image-provider and personal model credentials are not substituted for the gateway key."
}
