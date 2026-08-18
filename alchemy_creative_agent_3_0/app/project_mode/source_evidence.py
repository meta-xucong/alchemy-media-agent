"""Server-owned source-image transports.

Only verified image bytes exist at this boundary. E-Commerce may consume the
typed single-image observation transport for its specialized product policy.
General uses the separate source-selection Brain below: it receives the
current command and complete verified candidates, then returns only opaque
candidate handles. Project Mode binds project/reference/SHA facts itself.
"""

from __future__ import annotations

import base64
import json
from json import JSONDecodeError
from typing import Any, Protocol, runtime_checkable


SOURCE_EVIDENCE_OUTPUT_TOKEN_BUDGET = 640
GENERAL_SOURCE_SELECTION_OUTPUT_TOKEN_BUDGET = 360
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


@runtime_checkable
class GeneralSourceSelectionBrain(Protocol):
    """Brain-owned General original selection for one explicit command.

    The caller supplies all current, verified candidates at once. The Brain
    can make a visual decision but may return only opaque candidate handles.
    It never receives project, reference, asset, SHA, browser, history, or
    persistence identifiers.
    """

    def select(
        self,
        *,
        command_direction: str,
        entries: list[dict[str, Any]],
        requested_output_count: int,
        maximum_sources: int,
    ) -> dict[str, Any] | None: ...


class CallableGeneralSourceSelectionBrain:
    """Explicit adapter for deterministic Brain test/composition doubles."""

    def __init__(self, callback: Any) -> None:
        self._callback = callback

    def select(
        self,
        *,
        command_direction: str,
        entries: list[dict[str, Any]],
        requested_output_count: int,
        maximum_sources: int,
    ) -> dict[str, Any] | None:
        return self._callback(
            command_direction=command_direction,
            entries=entries,
            requested_output_count=requested_output_count,
            maximum_sources=maximum_sources,
        )


class OpenAICompatibleGeneralSourceSelectionBrain:
    """Visual General-source decision through the configured V3 Brain route.

    This path has no source taxonomy, filename heuristic, or local semantic
    matcher. The model sees the command and complete current original set in
    one request. The server validates opaque handles before using a source.
    """

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        model: str | None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key, self.base_url, self.model = (
            str(value or "").strip() for value in (api_key, base_url, model)
        )
        self.timeout_seconds = max(0.5, min(float(timeout_seconds), 90.0))

    def available(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def select(
        self,
        *,
        command_direction: str,
        entries: list[dict[str, Any]],
        requested_output_count: int,
        maximum_sources: int,
    ) -> dict[str, Any] | None:
        if (
            not self.available()
            or not isinstance(command_direction, str)
            or not command_direction.strip()
            or not isinstance(requested_output_count, int)
            or isinstance(requested_output_count, bool)
            or not 1 <= requested_output_count <= 8
            or not isinstance(maximum_sources, int)
            or isinstance(maximum_sources, bool)
            or not 1 <= maximum_sources <= 4
        ):
            return None
        normalized = _selection_entries(entries)
        if not normalized:
            return {"state": "prompt_only", "output_selections": []}
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key, base_url=self.base_url, max_retries=0)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": _general_source_selection_content(
                        command_direction=command_direction,
                        entries=normalized,
                        requested_output_count=requested_output_count,
                        maximum_sources=maximum_sources,
                    ),
                }],
                response_format={"type": "json_object"},
                temperature=0,
                timeout=self.timeout_seconds,
                max_tokens=GENERAL_SOURCE_SELECTION_OUTPUT_TOKEN_BUDGET,
            )
            raw = str(response.choices[0].message.content or "")
        except Exception:
            return None
        return general_source_selection_response_from_text(
            raw,
            candidate_handles={str(item["candidate_handle"]) for item in normalized},
            requested_output_count=requested_output_count,
            maximum_sources=maximum_sources,
        )


def _selection_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        handle = str(entry.get("candidate_handle") or "").strip()
        content = entry.get("analysis_bytes") if isinstance(entry, dict) else None
        mime_type = str(entry.get("mime_type") or "").strip().lower() if isinstance(entry, dict) else ""
        if (
            len(handle) != 64
            or handle in seen
            or not isinstance(content, bytes)
            or not content
            or mime_type not in {"image/png", "image/jpeg", "image/webp"}
        ):
            return []
        seen.add(handle)
        normalized.append({
            "candidate_handle": handle,
            "analysis_bytes": content,
            "mime_type": mime_type,
        })
    return sorted(normalized, key=lambda item: str(item["candidate_handle"]))


def _general_source_selection_content(
    *,
    command_direction: str,
    entries: list[dict[str, Any]],
    requested_output_count: int,
    maximum_sources: int,
) -> list[dict[str, Any]]:
    instruction = (
        "You are the V3 creative Brain deciding whether current uploaded originals should be used for this command. "
        "Inspect the command and every candidate image together. Make the decision from their actual visual content. "
        "Return plain JSON only, with exactly keys state and output_selections. "
        "For prompt_only, output_selections must be []. For selected, output_selections must contain exactly one object "
        "for every output index from 1 through " + str(requested_output_count) + ". Each object must have exactly "
        "output_index and candidate_handles. Each candidate_handles list must contain one through " + str(maximum_sources) +
        " opaque handles from the supplied candidates, with no duplicates. Use prompt_only when no original is materially "
        "needed. Do not return explanations, semantic labels, filenames, IDs, hashes, or any text beyond that JSON schema. "
        "Opaque handles are address tokens only and have no visual meaning.\n"
        "Requested output count: " + str(requested_output_count) + "\nCommand: " + command_direction
    )
    content: list[dict[str, Any]] = [
        {"type": "text", "text": instruction},
        {"type": "text", "text": "Requested output count: " + str(requested_output_count)},
    ]
    for entry in entries:
        data_url = (
            "data:" + str(entry["mime_type"]) + ";base64," +
            base64.b64encode(entry["analysis_bytes"]).decode("ascii")
        )
        content.extend([
            {"type": "text", "text": "Candidate handle: " + str(entry["candidate_handle"])},
            {"type": "image_url", "image_url": {"url": data_url}},
        ])
    return content


def general_source_selection_response_from_text(
    raw: Any,
    *,
    candidate_handles: set[str],
    requested_output_count: int,
    maximum_sources: int,
) -> dict[str, Any] | None:
    try:
        payload = json.loads(str(raw or ""))
    except (TypeError, ValueError, JSONDecodeError):
        return None
    if not isinstance(payload, dict) or set(payload) != {"state", "output_selections"}:
        return None
    state = payload.get("state")
    selections = payload.get("output_selections")
    if state == "prompt_only":
        return {"state": state, "output_selections": []} if selections == [] else None
    if state != "selected" or not isinstance(selections, list) or len(selections) != requested_output_count:
        return None
    normalized: list[dict[str, Any]] = []
    indexes: set[int] = set()
    for item in selections:
        if not isinstance(item, dict) or set(item) != {"output_index", "candidate_handles"}:
            return None
        index = item.get("output_index")
        handles = item.get("candidate_handles")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 1
            or index > requested_output_count
            or index in indexes
            or not isinstance(handles, list)
            or not 1 <= len(handles) <= maximum_sources
            or len(handles) != len(set(handles))
            or any(not isinstance(handle, str) or handle not in candidate_handles for handle in handles)
        ):
            return None
        indexes.add(index)
        normalized.append({"output_index": index, "candidate_handles": list(handles)})
    if indexes != set(range(1, requested_output_count + 1)):
        return None
    return {"state": "selected", "output_selections": sorted(normalized, key=lambda item: item["output_index"])}


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
