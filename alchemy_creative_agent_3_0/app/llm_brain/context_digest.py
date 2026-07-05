"""Context digestion helpers for the V3 LLM Brain."""

from __future__ import annotations

from typing import Any


def as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except Exception:
            return {}
    return dict(value) if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_text(value: Any, limit: int = 260) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        return text[: max(0, limit - 1)].rstrip() + "..."
    return text


def clean_text_list(values: list[Any], limit: int = 8, text_limit: int = 140) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = clean_text(value, text_limit)
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def project_context_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    snapshot = metadata.get("project_context_snapshot")
    return as_dict(snapshot)


def selected_outputs_from_context(project_context: dict[str, Any]) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for item in as_list(project_context.get("selected_output_assets")):
        data = as_dict(item)
        if data:
            outputs.append(data)
    return outputs


def selected_references_from_context(project_context: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for key in ("selected_reference_assets", "uploaded_reference_assets"):
        for item in as_list(project_context.get(key)):
            data = as_dict(item)
            if data:
                refs.append(data)
    return refs


def negative_notes_from_context(project_context: dict[str, Any]) -> list[str]:
    return clean_text_list(
        [
            *as_list(project_context.get("rejected_style_tags")),
            *as_list(project_context.get("negative_direction_notes")),
        ],
        limit=10,
    )
