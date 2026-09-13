"""Canonical resolution for V3 General multi-image variation modes.

This module is deliberately dependency-light.  Project Mode, ScenarioRuntime,
the Brain adapter, fallback planning, and the shared visual cluster all need
to read the same mode authority, but importing one of those higher-level
components from another would create a second precedence implementation (or
an import cycle).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
from typing import Any


GENERAL_VARIATION_MODES = frozenset(
    {
        "auto",
        "selection_candidates",
        "delivery_suite",
        "creative_exploration",
        "format_layout_adaptation",
    }
)

GENERAL_VARIATION_MODE_ALIASES = {
    "similar_options": "selection_candidates",
    "suite_expansion": "delivery_suite",
    "creative_explore": "creative_exploration",
    "layout_adaptation": "format_layout_adaptation",
    "format_adaptation": "format_layout_adaptation",
}

GENERAL_VARIATION_MODE_BINDING_VERSION = "v3_general_variation_mode_binding_v1"


def canonical_general_variation_mode(value: object, *, allow_auto: bool = True) -> str:
    """Return one canonical General mode, or ``""`` for unknown input."""

    normalized = str(value or "").strip().lower()
    normalized = GENERAL_VARIATION_MODE_ALIASES.get(normalized, normalized)
    if normalized == "auto" and not allow_auto:
        return ""
    return normalized if normalized in GENERAL_VARIATION_MODES else ""


def infer_general_variation_mode(
    user_input: str | None,
    *,
    requested_count: object | None = None,
    has_reference: bool = False,
    selected_size: object | None = None,
) -> str:
    """Infer a neutral mode for callers that omit an explicit selection.

    This is only the compatibility inference used for old/direct callers.  A
    non-auto user selection always wins over this function.
    """

    text = re.sub(r"\s+", " ", str(user_input or "").strip().lower())
    if re.search(
        r"尺寸|画幅|比例|版式|横版|竖版|方图|封面|海报|留白|裁切|裁剪|layout|format|ratio|size|crop|adapt",
        text,
    ):
        return "format_layout_adaptation"
    if re.search(
        r"探索|不同方向|不同概念|尝试新风格|不同风格|多种风格|explore|different directions|different concepts|try new styles|different styles|new concepts",
        text,
    ):
        return "creative_exploration"
    if re.search(
        r"沿.{0,12}方向.{0,12}(一组|系列|套图)|套图|一组|系列|组图|延展|扩展|\b(series|suite|set|extend|campaign)\b",
        text,
    ):
        return "delivery_suite"
    if re.search(
        r"相似|备选|多给|挑选|同一|同款|不同姿势|不同角度|similar|alternative|same person|same product|different pose|different angle",
        text,
    ):
        return "selection_candidates"
    try:
        count = int(requested_count) if requested_count not in {None, ""} else 0
    except (TypeError, ValueError):
        count = 0
    if count > 1:
        return "selection_candidates"
    if has_reference:
        return "selection_candidates"
    if str(selected_size or "").strip():
        return "format_layout_adaptation"
    return "delivery_suite"


def _safe_mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _first_mode(
    candidates: Iterable[tuple[str, Mapping[str, Any]]],
    key: str,
    *,
    include_auto: bool = False,
) -> tuple[str, str] | None:
    for source, candidate in candidates:
        mode = canonical_general_variation_mode(candidate.get(key), allow_auto=True)
        if mode and (include_auto or mode != "auto"):
            return mode, source
    return None


def _nested_mode_candidates(
    metadata: Mapping[str, Any],
) -> tuple[list[tuple[str, Mapping[str, Any]]], list[tuple[str, Mapping[str, Any]]]]:
    """Split current request fields from persisted/context compatibility data."""

    current: list[tuple[str, Mapping[str, Any]]] = [("metadata", metadata)]
    parameters = _safe_mapping(metadata.get("scenario_parameters"))
    if parameters is not None:
        current.append(("scenario_parameters", parameters))

    fallback: list[tuple[str, Mapping[str, Any]]] = []
    for key, label in (
        ("project_context_snapshot", "project_context_snapshot.metadata"),
        ("project_context", "project_context.metadata"),
    ):
        container = _safe_mapping(metadata.get(key))
        nested = _safe_mapping(container.get("metadata")) if container is not None else None
        if nested is not None:
            fallback.append((label, nested))
    return current, fallback


def resolve_general_variation_mode(
    metadata: Mapping[str, Any] | None,
    *,
    user_input: str | None = None,
    requested_count: object | None = None,
    has_reference: bool = False,
    selected_size: object | None = None,
    fallback_metadata: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, str | None]:
    """Resolve one server-owned General mode binding.

    ``effective_variation_mode`` is intentionally consulted only after the
    current request's explicit/inferred/frozen facts.  This prevents a value
    persisted by an earlier job from overriding a new manual mode choice.
    """

    primary = _safe_mapping(metadata) or {}
    current, nested_fallback = _nested_mode_candidates(primary)
    fallback = [*nested_fallback]
    for index, candidate in enumerate(fallback_metadata or (), start=1):
        safe = _safe_mapping(candidate)
        if safe is not None:
            fallback.append((f"fallback_{index}", safe))

    requested_mode = "auto"
    source = "auto"
    explicit = _first_mode(current, "variation_mode_override")
    if explicit is not None:
        requested_mode, _ = explicit
        source = "manual"
    else:
        explicit = _first_mode(current, "variation_mode")
        if explicit is None:
            explicit = _first_mode(current, "continuation_mode")
        if explicit is not None:
            requested_mode, _ = explicit
            source = "manual"

    inferred = _first_mode(current, "inferred_variation_mode")
    inferred_mode = inferred[0] if inferred is not None else ""
    if requested_mode != "auto":
        effective_mode = requested_mode
    else:
        # An already frozen contract is reusable evidence, but only after a
        # new explicit/inferred choice had its opportunity to win.
        frozen = _first_mode(current, "variation_execution_mode")
        has_frozen_contract = bool(
            primary.get("variation_execution_contract_enforced") is True
            or isinstance(primary.get("variation_execution_contract"), Mapping)
        )
        if frozen is not None and has_frozen_contract:
            effective_mode = frozen[0]
            source = "frozen_contract"
        elif inferred_mode:
            effective_mode = inferred_mode
            source = "auto"
        else:
            current_effective = _first_mode(current, "effective_variation_mode")
            if current_effective is not None:
                # Frontend/direct API callers may send only the already
                # resolved current value. Preserve it before using the
                # generic count/reference compatibility inference.
                effective_mode = current_effective[0]
                source = "current_derived"
            else:
                inferred_mode = infer_general_variation_mode(
                    user_input,
                    requested_count=(
                        requested_count
                        if requested_count is not None
                        else primary.get("requested_image_count")
                    ),
                    has_reference=bool(
                        has_reference
                        or primary.get("has_reference")
                        or primary.get("has_product_reference")
                    ),
                    selected_size=(
                        selected_size
                        if selected_size is not None
                        else primary.get("requested_image_size")
                    ),
                )
                if inferred_mode:
                    effective_mode = inferred_mode
                    source = "auto"
                else:
                    persisted = _first_mode(fallback, "effective_variation_mode")
                    if persisted is None:
                        persisted = _first_mode(fallback, "variation_mode")
                    if persisted is not None:
                        effective_mode = persisted[0]
                        source = "persisted"
                    else:
                        effective_mode = "delivery_suite"
                        source = "default"

    return {
        "variation_mode": requested_mode,
        "effective_variation_mode": effective_mode,
        "continuation_mode": effective_mode,
        "inferred_variation_mode": inferred_mode or None,
        "variation_mode_source": source,
    }


def build_general_variation_mode_binding(
    resolution: Mapping[str, Any],
    *,
    contract_version: str | None = None,
    contract_digest: str | None = None,
) -> dict[str, str | None]:
    """Build the safe mode provenance record bound to a frozen job/output."""

    binding: dict[str, str | None] = {
        "schema_version": GENERAL_VARIATION_MODE_BINDING_VERSION,
        "requested_mode": str(resolution.get("variation_mode") or "auto"),
        "effective_mode": str(resolution.get("effective_variation_mode") or "delivery_suite"),
        "source": str(resolution.get("variation_mode_source") or "auto"),
    }
    if contract_version:
        binding["contract_version"] = contract_version
    if contract_digest:
        binding["contract_digest"] = contract_digest
    return binding
