#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${V1_MEDIA_STORAGE_DIR:-/var/lib/alchemy/v1/media_storage}"
RETENTION_DAYS="${V3_STORAGE_RETENTION_DAYS:-30}"
TRASH_RETENTION_DAYS="${V3_STORAGE_TRASH_RETENTION_DAYS:-7}"
FAILURE_RETENTION_DAYS="${V3_FAILURE_RETENTION_DAYS:-7}"
SCRIPT="${V3_STORAGE_MAINTENANCE_SCRIPT:-/opt/alchemy-media-agent-ops/vps-storage-maintenance/v3_storage_maintenance.py}"

exec python3 "${SCRIPT}" --root "${ROOT}" --retention-days "${RETENTION_DAYS}" \
  --failure-retention-days "${FAILURE_RETENTION_DAYS}" \
  --trash-retention-days "${TRASH_RETENTION_DAYS}" --apply --purge-trash
