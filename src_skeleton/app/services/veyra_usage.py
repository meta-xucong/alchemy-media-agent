from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from app.config import settings


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


def record_veyra_usage(record: VeyraUsageRecord) -> None:
    payload = asdict(record)
    if not payload.get("created_at"):
        payload["created_at"] = datetime.now(timezone.utc).isoformat()
    settings.veyra_usage_path.parent.mkdir(parents=True, exist_ok=True)
    with settings.veyra_usage_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")
