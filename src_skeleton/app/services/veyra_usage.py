from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from app.config import settings


_write_lock = Lock()


@dataclass(frozen=True)
class VeyraUsageRecord:
    user_id: int
    amount: float
    balance_after: float
    idempotency_key: str
    reference_id: str
    source: str
    replayed: bool = False
    created_at: str = ""


def record_veyra_usage(record: VeyraUsageRecord, *, deduplicate: bool = False) -> None:
    payload = asdict(record)
    if not payload.get("created_at"):
        payload["created_at"] = datetime.now(timezone.utc).isoformat()
    settings.veyra_usage_path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock, settings.veyra_usage_path.open("a+", encoding="utf-8") as handle:
        if deduplicate:
            handle.seek(0)
            for line in handle:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (isinstance(item, dict) and item.get("user_id") == record.user_id
                        and item.get("idempotency_key") == record.idempotency_key):
                    return
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def list_veyra_usage(user_id: int, *, limit: int = 50) -> dict[str, Any]:
    if not settings.veyra_usage_path.exists():
        return {"items": [], "total": 0}
    items: list[dict[str, Any]] = []
    for line in settings.veyra_usage_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            if int(item.get("user_id") or 0) != int(user_id):
                continue
        except (TypeError, ValueError):
            continue
        items.append(item)
    items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {"items": items[:limit], "total": len(items)}
