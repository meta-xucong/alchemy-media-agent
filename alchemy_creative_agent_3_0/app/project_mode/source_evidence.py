"""Scenario-neutral server source-image observation foundation.

Only verified image bytes exist at this boundary.  The adapter emits a closed
semantic observation; callers bind project/reference/asset/SHA separately.
"""

from __future__ import annotations

import base64
import json
from json import JSONDecodeError
from typing import Any, Protocol, runtime_checkable


SOURCE_EVIDENCE_OUTPUT_TOKEN_BUDGET = 640
REQUIREMENT_ISSUER_OUTPUT_TOKEN_BUDGET = 120
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


class OpenAICompatibleTextRequirementIssuer:
    """Strict text-only Doc281 requirement classifier.

    It deliberately has no source-library argument: candidate evidence remains
    exclusively with the server matcher after this bounded intent decision.
    """

    def __init__(self, *, api_key: str | None, base_url: str | None, model: str | None,
                 allowed_kinds: tuple[str, ...], maximum_sources: int, timeout_seconds: float = 30.0) -> None:
        self.api_key, self.base_url, self.model = (str(value or "").strip() for value in (api_key, base_url, model))
        self.allowed_kinds = tuple(item for item in allowed_kinds if isinstance(item, str) and item)
        self.maximum_sources = maximum_sources
        self.timeout_seconds = max(0.5, min(float(timeout_seconds), 90.0))

    def available(self) -> bool:
        return bool(
            self.api_key
            and self.base_url
            and self.model
            and self.allowed_kinds
            and len(self.allowed_kinds) == len(set(self.allowed_kinds))
            and isinstance(self.maximum_sources, int)
            and not isinstance(self.maximum_sources, bool)
            and 1 <= self.maximum_sources <= 4
        )

    def __call__(self, *, command_direction: str) -> dict[str, Any] | None:
        if not self.available() or not isinstance(command_direction, str) or not command_direction.strip():
            return None
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url, max_retries=0)
            response = client.chat.completions.create(model=self.model, messages=[{"role":"user","content":(
                requirement_classification_instruction(self.allowed_kinds) + "\nCommand: " + command_direction)}],
                response_format={"type":"json_object"}, timeout=self.timeout_seconds,
                max_tokens=REQUIREMENT_ISSUER_OUTPUT_TOKEN_BUDGET)
            value = json.loads(str(response.choices[0].message.content or ""))
        except Exception:
            return None
        if not isinstance(value, dict) or set(value) != {"state", "kind"}:
            return None
        state, kind = value.get("state"), value.get("kind")
        if state == "optional_uncertain" and kind == "none":
            return {"state": state}
        if state != "required" or kind not in self.allowed_kinds:
            return None
        return {"state": "required", "kind": kind, "maximum_sources": self.maximum_sources}


def requirement_classification_instruction(allowed_kinds: tuple[str, ...]) -> str:
    """Return the complete policy-owned, text-only classifier contract.

    The vocabulary is deliberately rendered by the server from the validated
    packaged policy.  The command is appended by the caller only after this
    invariant contract, so no candidate-library value can become a selector.
    """

    vocabulary = json.dumps(list(allowed_kinds), ensure_ascii=True, separators=(",", ":"))
    return (
        "Classify only the command text into this closed requirement vocabulary: " + vocabulary + ". "
        "Return exactly one JSON object with exactly the keys state and kind. "
        "For state required, kind must be exactly one vocabulary value. "
        "For state optional_uncertain, kind must be exactly none. "
        "Do not add keys, explanations, selections, or assumptions about uploaded material."
    )


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
            return semantic_response_from_text(str(getattr(response, "output_text", "") or ""))
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": [{"type": "text", "text": instruction}, {"type": "image_url", "image_url": {"url": data_url}}]}],
            response_format={"type": "json_object"}, temperature=0, timeout=self.timeout_seconds,
            max_tokens=SOURCE_EVIDENCE_OUTPUT_TOKEN_BUDGET,
        )
        return semantic_response_from_text(str(response.choices[0].message.content or ""))


def semantic_response_schema() -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "required": list(SEMANTIC_PROFILE_KEYS), "properties": {
        "evidence_state": {"type": "string", "enum": ["observed"]},
        "subject_kind": {"type": "string", "enum": list(SEMANTIC_SUBJECT_KINDS)},
        "view_kind": {"type": "string", "enum": list(SEMANTIC_VIEW_KINDS)},
        "affordances": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string", "enum": list(SEMANTIC_AFFORDANCES)}},
    }}


def semantic_analysis_instruction() -> str:
    subject_values = ", ".join(SEMANTIC_SUBJECT_KINDS)
    view_values = ", ".join(SEMANTIC_VIEW_KINDS)
    affordance_values = ", ".join(SEMANTIC_AFFORDANCES)
    return (
        "Inspect only the supplied image. Return plain JSON only, with no Markdown and no explanation. "
        "Return exactly this schema: {\"evidence_state\":\"observed\",\"subject_kind\":\"one_enum\","
        "\"view_kind\":\"one_enum\",\"affordances\":[\"one_primary_enum\"]}. "
        "Allowed evidence_state: observed. "
        f"Allowed subject_kind values: {subject_values}. "
        f"Allowed view_kind values: {view_values}. "
        f"Allowed affordances values: {affordance_values}. "
        "Use only exact allowed enum strings. Do not create synonyms or longer labels. "
        "Choose exactly one primary affordance for the dominant visual evidence; do not include secondary marks or decorative details. "
        "Do not infer identity, filename, project, user intent, prompt, or private identifiers."
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


def semantic_response_from_text(raw: Any) -> dict[str, Any]:
    text = str(raw or "").strip()
    for candidate in _semantic_json_candidates(text):
        try:
            payload = json.loads(candidate)
        except JSONDecodeError:
            continue
        return validated_semantic_response(payload)
    raise ValueError("source_evidence_response_invalid")


def _semantic_json_candidates(text: str) -> tuple[str, ...]:
    if not text:
        return ()
    candidates: list[str] = [text]
    fenced = _strip_markdown_json_fence(text)
    if fenced and fenced not in candidates:
        candidates.append(fenced)
    balanced = _first_balanced_json_object(fenced or text)
    if balanced and balanced not in candidates:
        candidates.append(balanced)
    return tuple(candidates)


def _strip_markdown_json_fence(text: str) -> str:
    lines = text.strip().splitlines()
    if len(lines) >= 3 and lines[0].strip().startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _first_balanced_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index, character in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return ""
