#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${V1_MEDIA_STORAGE_DIR:-/var/lib/alchemy/v1/media_storage}"
TRASH_RETENTION_DAYS="${V3_STORAGE_TRASH_RETENTION_DAYS:-7}"
FAILURE_RETENTION_DAYS="${V3_FAILURE_RETENTION_DAYS:-7}"
SETTINGS_FILE="${V3_RETENTION_SETTINGS_FILE:-${ROOT}/retention_settings.json}"
SCRIPT="${V3_STORAGE_MAINTENANCE_SCRIPT:-/opt/alchemy-media-agent-ops/vps-storage-maintenance/v3_storage_maintenance.py}"

exec python3 "${SCRIPT}" --root "${ROOT}" --settings-file "${SETTINGS_FILE}" \
  --failure-retention-days "${FAILURE_RETENTION_DAYS}" \
  --trash-retention-days "${TRASH_RETENTION_DAYS}" --apply --purge-trash
