from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings


def favorites_path() -> Path:
    return settings.data_dir / "image_favorites.json"


def list_favorite_ids(*, veyra_user_id: int | None = None, include_legacy_public: bool = True, include_all: bool = False) -> set[str]:
    payload = _read_payload()
    result: set[str] = set()
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        output_id = str(item.get("output_id") or "").strip()
        if not output_id:
            continue
        owner_id = _positive_int_or_none(item.get("veyra_user_id"))
        if not include_all and veyra_user_id is not None and owner_id != veyra_user_id and not (include_legacy_public and owner_id is None):
            continue
        if not include_all and veyra_user_id is None and settings.veyra_auth_enabled:
            continue
        result.add(output_id)
    return result


def set_favorite(output_id: str, favorite: bool, *, veyra_user_id: int | None = None) -> dict[str, Any]:
    clean_id = str(output_id or "").strip()
    if not clean_id:
        raise ValueError("output_id is required")
    payload = _read_payload()
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    now = datetime.now(timezone.utc).isoformat()
    kept: list[dict[str, Any]] = []
    changed = False
    for item in items:
        same_output = item.get("output_id") == clean_id
        same_owner = _positive_int_or_none(item.get("veyra_user_id")) == veyra_user_id
        if same_output and same_owner:
            changed = True
            continue
        kept.append(item)
    if favorite:
        kept.append(
            {
                "output_id": clean_id,
                "veyra_user_id": veyra_user_id,
                "created_at": now,
                "updated_at": now,
            }
        )
    payload = {"items": sorted(kept, key=lambda item: (str(item.get("output_id") or ""), str(item.get("veyra_user_id") or "")))}
    _write_payload(payload)
    return {"output_id": clean_id, "favorite": bool(favorite), "changed": changed or favorite}


def delete_favorite(output_id: str) -> int:
    clean_id = str(output_id or "").strip()
    if not clean_id:
        return 0
    payload = _read_payload()
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    kept = [item for item in items if item.get("output_id") != clean_id]
    removed = len(items) - len(kept)
    if removed:
        _write_payload({"items": kept})
    return removed


def _read_payload() -> dict[str, Any]:
    path = favorites_path()
    if not path.exists():
        return {"items": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"items": []}
    return payload if isinstance(payload, dict) else {"items": []}


def _write_payload(payload: dict[str, Any]) -> None:
    path = favorites_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def _positive_int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
