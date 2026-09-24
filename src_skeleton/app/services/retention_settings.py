from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.storage import media_store


DEFAULT_RETENTION_DAYS = 30
MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 3650


def retention_settings_path(root: Path | None = None) -> Path:
    return (root or media_store.root) / "retention_settings.json"


def get_retention_settings(root: Path | None = None) -> dict[str, Any]:
    path = retention_settings_path(root)
    payload: dict[str, Any] = {}
    if path.exists():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                payload = parsed
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            payload = {}

    return {
        "delete_protected_data": bool(payload.get("delete_protected_data", False)),
        "retention_days": _normalize_retention_days(payload.get("retention_days", DEFAULT_RETENTION_DAYS)),
        "persisted": path.exists(),
        "updated_at": str(payload.get("updated_at") or "") or None,
    }


def save_retention_settings(
    *,
    delete_protected_data: bool,
    retention_days: int,
    root: Path | None = None,
) -> dict[str, Any]:
    normalized_days = _normalize_retention_days(retention_days)
    path = retention_settings_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "delete_protected_data": bool(delete_protected_data),
        "retention_days": normalized_days,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(path)
    return get_retention_settings(root)


def _normalize_retention_days(value: object) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS
    return max(MIN_RETENTION_DAYS, min(MAX_RETENTION_DAYS, days))
