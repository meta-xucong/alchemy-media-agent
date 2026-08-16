"""Scenario-neutral server source-image observation foundation.

Only verified image bytes exist at this boundary.  The adapter emits a closed
semantic observation; callers bind project/reference/asset/SHA separately.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Protocol, runtime_checkable


SOURCE_EVIDENCE_OUTPUT_TOKEN_BUDGET = 640
SEMANTIC_PROFILE_KEYS = frozenset({"evidence_state", "subject_kind", "view_kind", "affordances"})
SEMANTIC_SUBJECT_KINDS = ("object_or_product", "person", "brand_or_graphic")
SEMANTIC_VIEW_KINDS = ("front", "rear", "detail_or_macro", "environment_wide", "packaging")
SEMANTIC_AFFORDANCES = (
    "object_front_presentation", "object_back_or_structure", "object_detail", "environment", "logo_or_mark",
)


@runtime_checkable
class SourceEvidenceAnalyzer(Protocol):
    """One-source semantic observation transport.

    The caller supplies exactly one temporary, already reverified image entry.
    The transport can return only one closed semantic observation. It never
    returns reference, asset, SHA, project, or selection facts.
    """

    def analyze(self, *, project_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]] | None: ...


class CallableSourceEvidenceAnalyzer:
    """Explicit adapter for deterministic server test/composition callables."""

    def __init__(self, callback: Any) -> None:
        self._callback = callback

    def analyze(self, *, project_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        return self._callback(project_id=project_id, entries=entries)


class OpenAICompatibleSourceEvidenceAnalyzer:
    """Private OpenAI-compatible transport for one temporary verified image."""

    def __init__(self, *, api_key: str | None, base_url: str | None, model: str | None,
                 timeout_seconds: float = 30.0, preferred_protocol: str = "responses") -> None:
        self.api_key, self.base_url, self.model = (str(value or "").strip() for value in (api_key, base_url, model))
        self.timeout_seconds = max(0.5, min(float(timeout_seconds), 90.0))
        self.preferred_protocol = str(preferred_protocol or "").strip().lower()
        if self.preferred_protocol not in {"responses", "chat"}:
            raise ValueError("source_evidence_protocol_invalid")

    def available(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def analyze(self, *, project_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        del project_id
        if not self.available() or len(entries) != 1:
            return None
        entry = entries[0]
        content = entry.get("analysis_bytes") if isinstance(entry, dict) else None
        mime = str(entry.get("mime_type") or "").strip().lower() if isinstance(entry, dict) else ""
        if not isinstance(content, bytes) or not content or mime not in {"image/png", "image/jpeg", "image/webp"}:
            return None
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url, max_retries=0)
            data_url = f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"
            result = self._call(client, data_url)
        except Exception:
            return None
        return [result] if isinstance(result, dict) else None

    def _call(self, client: Any, data_url: str) -> dict[str, Any]:
        instruction = semantic_analysis_instruction()
        if self.preferred_protocol == "responses":
            response = client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": [{"type": "input_text", "text": instruction}, {"type": "input_image", "image_url": data_url}]}],
                text={"format": {"type": "json_schema", "name": "source_evidence", "strict": True, "schema": semantic_response_schema()}},
                timeout=self.timeout_seconds,
                max_output_tokens=SOURCE_EVIDENCE_OUTPUT_TOKEN_BUDGET,
            )
            return validated_semantic_response(json.loads(str(getattr(response, "output_text", "") or "")))
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": [{"type": "text", "text": instruction}, {"type": "image_url", "image_url": {"url": data_url}}]}],
            response_format={"type": "json_object"}, timeout=self.timeout_seconds,
            max_tokens=SOURCE_EVIDENCE_OUTPUT_TOKEN_BUDGET,
        )
        return validated_semantic_response(json.loads(str(response.choices[0].message.content or "")))


def semantic_response_schema() -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "required": list(SEMANTIC_PROFILE_KEYS), "properties": {
        "evidence_state": {"type": "string", "enum": ["observed"]},
        "subject_kind": {"type": "string", "enum": list(SEMANTIC_SUBJECT_KINDS)},
        "view_kind": {"type": "string", "enum": list(SEMANTIC_VIEW_KINDS)},
        "affordances": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "enum": list(SEMANTIC_AFFORDANCES)}},
    }}


def semantic_analysis_instruction() -> str:
    return (
        "Inspect only the supplied image. Return exactly one JSON object with exactly these fields: "
        "evidence_state, subject_kind, view_kind, affordances. Do not infer identity, filename, project, user intent, or prompt."
    )


def semantic_response_is_valid(payload: Any) -> bool:
    values = payload.get("affordances") if isinstance(payload, dict) else None
    return bool(
        isinstance(payload, dict) and set(payload) == SEMANTIC_PROFILE_KEYS and payload.get("evidence_state") == "observed"
        and payload.get("subject_kind") in SEMANTIC_SUBJECT_KINDS and payload.get("view_kind") in SEMANTIC_VIEW_KINDS
        and isinstance(values, list) and values and len(values) == len(set(values))
        and all(isinstance(value, str) and value in SEMANTIC_AFFORDANCES for value in values)
    )


def validated_semantic_response(payload: Any) -> dict[str, Any]:
    if not semantic_response_is_valid(payload):
        raise ValueError("source_evidence_response_invalid")
    return dict(payload)
