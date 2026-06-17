from __future__ import annotations

import re
from typing import Any


SENSITIVE_MARKERS = (
    "case_id",
    "asset_id",
    "provider_id",
    "source_url",
    "api",
    "repository",
    "storage",
)
SENSITIVE_PATTERNS = (
    (r"\bcase_github_[a-z0-9_.-]+\b", "selected visual reference"),
    (r"\bgithub_evolinkai_[a-z0-9_.-]+\b", "curated visual reference"),
    (r"\basset_[a-z0-9_.-]+\b", "uploaded visual reference"),
    (r"\bapi[_ -]?key\b", "credential"),
    (r"\bapi\b", "service"),
    (r"\bEvoLinkAI\b", "curated reference"),
)


def build_prompt_transform_metadata(
    *,
    base_prompt: str,
    final_prompt: str,
    mode_info: dict[str, str],
    constraints: list[str],
    applied: bool,
    fallback_used: bool = False,
    error: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "enabled": True,
        "source_mode": mode_info.get("source", ""),
        "v2_mode": mode_info.get("v2_mode", ""),
        "transform_mode": mode_info.get("transform_mode", ""),
        "fidelity_mode": mode_info.get("fidelity_mode", ""),
        "applied": bool(applied),
        "fallback_used": bool(fallback_used),
        "constraint_count": len(constraints),
        "constraints": [_sanitize_metadata_text(item) for item in constraints[:12]],
        "base_prompt_chars": len(base_prompt or ""),
        "final_prompt_chars": len(final_prompt or ""),
    }
    if error:
        metadata["error"] = _sanitize_metadata_text(error)[:240]
    return metadata


def _sanitize_metadata_text(value: Any) -> str:
    text = " ".join(str(value or "").split())
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    for marker in SENSITIVE_MARKERS:
        text = text.replace(marker, "internal_reference")
    return text
