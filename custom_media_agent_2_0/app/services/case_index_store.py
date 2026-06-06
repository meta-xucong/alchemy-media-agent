from __future__ import annotations

import json
from pathlib import Path

from app.config import settings
from app.schemas import PromptCase


def save_case_index(cases: list[PromptCase], path: Path | None = None) -> Path:
    target = path or settings.case_index_path
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "index_version": cases[0].index_version if cases else None,
        "case_count": len(cases),
        "cases": [case.model_dump(mode="json") for case in cases],
    }
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)
    return target


def load_case_index(path: Path | None = None) -> list[PromptCase]:
    target = path or settings.case_index_path
    if not target.exists():
        return []
    payload = json.loads(target.read_text(encoding="utf-8"))
    return [PromptCase.model_validate(item) for item in payload.get("cases", [])]
