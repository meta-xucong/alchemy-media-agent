[CmdletBinding()]
param(
    [string]$Passphrase = $env:POLYMARKET_SSH_PASSPHRASE,
    [int]$RetentionDays = 30,
    [int]$TrashRetentionDays = 7
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Passphrase)) {
    throw "Passphrase is required through -Passphrase or POLYMARKET_SSH_PASSPHRASE."
}

$wrapper = "D:\AI\SSH\VPS_SSH_KEY\hosts\alchemy-media-agent\connect.ps1"
if (-not (Test-Path -LiteralPath $wrapper)) {
    throw "Alchemy VPS SSH wrapper not found: $wrapper"
}
$files = @(
    @{ Local = Join-Path $PSScriptRoot "v3_storage_maintenance.py"; Remote = "v3_storage_maintenance.py"; Mode = "0755" },
    @{ Local = Join-Path $PSScriptRoot "v3-storage-maintenance.sh"; Remote = "v3-storage-maintenance.sh"; Mode = "0755" },
    @{ Local = Join-Path $PSScriptRoot "systemd\alchemy-v3-storage-maintenance.service"; Remote = "alchemy-v3-storage-maintenance.service"; Mode = "0644" },
    @{ Local = Join-Path $PSScriptRoot "systemd\alchemy-v3-storage-maintenance.timer"; Remote = "alchemy-v3-storage-maintenance.timer"; Mode = "0644" }
)

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("set -euo pipefail")
$lines.Add("TARGET=/opt/alchemy-media-agent-ops/vps-storage-maintenance")
$lines.Add("UNIT_DIR=/etc/systemd/system")
$lines.Add("TMP_FILES=()")
$lines.Add('cleanup() { if ((${#TMP_FILES[@]})); then rm -f "${TMP_FILES[@]}"; fi; }')
$lines.Add("trap cleanup EXIT")
$lines.Add("printf 'PRE_HOST='; hostname")
$lines.Add("printf 'PRE_DISK='; df -h /var/lib/alchemy/v1/media_storage | tail -1")
$lines.Add("printf 'PRE_V1='; docker inspect -f '{{.State.Status}}' alchemy-media-agent 2>/dev/null || true")
$lines.Add("printf 'PRE_V2='; systemctl is-active alchemy-v2-api.service 2>/dev/null || true")
$lines.Add("printf 'PRE_SUB2API='; docker ps --format '{{.Names}} {{.Image}} {{.Status}}' | grep -i sub2api || true")
$lines.Add('install -d -m 0755 "$TARGET"')

foreach ($file in $files) {
    if (-not (Test-Path -LiteralPath $file.Local)) {
        throw "Missing local patch file: $($file.Local)"
    }
    $encoded = [Convert]::ToBase64String([IO.File]::ReadAllBytes($file.Local))
    $temporary = "/tmp/v3-maint-$([guid]::NewGuid().ToString('N')).b64"
    $lines.Add("TMP_FILES+=('$temporary')")
    $lines.Add("printf '%s' '$encoded' | base64 -d > '$temporary'")
    if ($file.Remote -like "*.service" -or $file.Remote -like "*.timer") {
        $destination = "/etc/systemd/system/$($file.Remote)"
    }
    else {
        $destination = "/opt/alchemy-media-agent-ops/vps-storage-maintenance/$($file.Remote)"
    }
    $lines.Add("install -m $($file.Mode) '$temporary' '$destination'")
    $lines.Add("rm -f '$temporary'")
}

$lines.Add(('python3 "$TARGET/v3_storage_maintenance.py" --root /var/lib/alchemy/v1/media_storage --retention-days ' + $RetentionDays + ' --failure-retention-days 7 --trash-retention-days ' + $TrashRetentionDays + ' --apply --purge-trash'))
$lines.Add("systemctl daemon-reload")
$lines.Add("systemctl enable --now alchemy-v3-storage-maintenance.timer")
$lines.Add("systemctl start alchemy-v3-storage-maintenance.service")
$lines.Add("printf 'POST_TIMER='; systemctl is-active alchemy-v3-storage-maintenance.timer")
$lines.Add("printf 'POST_SERVICE='; systemctl show -p Result --value alchemy-v3-storage-maintenance.service")
$lines.Add("printf 'POST_DISK='; df -h /var/lib/alchemy/v1/media_storage | tail -1")
$lines.Add("printf 'POST_V1='; docker inspect -f '{{.State.Status}}' alchemy-media-agent 2>/dev/null || true")
$lines.Add("printf 'POST_V2='; systemctl is-active alchemy-v2-api.service 2>/dev/null || true")
$lines.Add("printf 'POST_SUB2API='; docker ps --format '{{.Names}} {{.Image}} {{.Status}}' | grep -i sub2api || true")
$lines.Add('printf ''OPS_PATH=''; readlink -f "$TARGET"')
$lines.Add("# remote-script-eof")

& $wrapper -Passphrase $Passphrase -RemoteScript ($lines -join "`n")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
