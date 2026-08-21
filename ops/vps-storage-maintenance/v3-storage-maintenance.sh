#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${V1_MEDIA_STORAGE_DIR:-/var/lib/alchemy/v1/media_storage}"
RETENTION_DAYS="${V3_STORAGE_RETENTION_DAYS:-30}"
SCRIPT="${V3_STORAGE_MAINTENANCE_SCRIPT:-/opt/alchemy-media-agent-ops/vps-storage-maintenance/v3_storage_maintenance.py}"

exec python3 "${SCRIPT}" --root "${ROOT}" --retention-days "${RETENTION_DAYS}" --apply
