"""Shared sanitizer for bounded public model-routing attempt receipts."""

from __future__ import annotations

import re
from typing import Any


SAFE_MODEL_FAILURE_CLASSES = frozenset({
    "candidate_budget_exhausted",
    "invalid_structured_response",
    "policy_refusal",
    "provider_api_error",
    "provider_error",
    "retryable_upstream",
    "timeout",
})


def safe_model_identifier(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"[^a-zA-Z0-9_.:/-]+", "_", value)[:120]
    return normalized or None


def sanitize_model_attempts(value: Any, *, strict: bool = False) -> list[dict[str, Any]] | None:
    """Normalize candidate attempts; strict mode rejects malformed public receipts."""

    if not isinstance(value, list) or (strict and len(value) > 4):
        return None if strict else []
    safe: list[dict[str, Any]] = []
    for item in value[:4]:
        if not isinstance(item, dict):
            if strict:
                return None
            continue
        model = safe_model_identifier(item.get("model"))
        outcome = item.get("outcome")
        elapsed_ms = item.get("elapsed_ms")
        valid = (
            model is not None
            and outcome in {"failed", "accepted"}
            and isinstance(elapsed_ms, int)
            and not isinstance(elapsed_ms, bool)
        )
        failure_class = item.get("failure_class")
        if failure_class is not None and (
            not isinstance(failure_class, str)
            or failure_class not in SAFE_MODEL_FAILURE_CLASSES
        ):
            valid = False
        if not valid:
            if strict:
                return None
            continue
        safe_item: dict[str, Any] = {
            "model": model,
            "outcome": outcome,
            "elapsed_ms": max(0, min(3_600_000, elapsed_ms)),
        }
        if outcome == "failed" and failure_class in SAFE_MODEL_FAILURE_CLASSES:
            safe_item["failure_class"] = failure_class
        safe.append(safe_item)
    return safe
