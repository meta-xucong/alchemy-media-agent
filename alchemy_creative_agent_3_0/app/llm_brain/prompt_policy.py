"""Single policy authority for V3 canonical renderer prompts.

This module describes the final prompt contract only.  It does not govern the
structured Brain request payload or any Provider-specific byte limit.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Mapping


V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV: Final = "v3_unified_prompt_compression_v1"
V3_UNIFIED_PROMPT_COMPRESSION_THRESHOLD_CHARS: Final = 6000
V3_UNIFIED_PROMPT_COMPRESSION_TARGET_MAX_CHARS: Final = 3500
V3_UNIFIED_PROMPT_TRANSPORT_REQUIRED_HARD_LIMIT_CHARS: Final = 6000
# The existing route setting is a Unicode-character cap.  This is the
# corresponding worst-case UTF-8 envelope (four bytes per Unicode code point),
# used only to verify the serialized transport, never to decide semantics.
V3_UNIFIED_PROMPT_TRANSPORT_REQUIRED_SAFE_UTF8_BYTES: Final = (
    V3_UNIFIED_PROMPT_TRANSPORT_REQUIRED_HARD_LIMIT_CHARS * 4
)
V3_UNIFIED_PROMPT_MAX_LENGTH_POLICY_RECOVERY: Final = 1
V3_BRAIN_SOURCE_PROJECTION_CONTRACT_REV: Final = "v3_brain_source_projection_v1"
V3_BRAIN_SOURCE_PROJECTION_FINALIZER_STAGE: Final = "provider_prompt_finalize"
V3_BRAIN_CAPABILITY_GUIDANCE_CONTRACT_REV: Final = "v3_brain_capability_guidance_v1"
V3_BRAIN_PROTECTED_CONSTRAINTS_CONTRACT_REV: Final = "v3_brain_protected_constraints_v1"

_V3_BRAIN_CAPABILITY_GUIDANCE_STAGES: frozenset[str] = frozenset(
    {
        "creative_strategy",
        "generation_prompt",
        "negative_prompt",
    }
)


def _canonical_value_sha256(value: Any) -> str:
    """Digest JSON-shaped server facts without interpreting their meaning."""

    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def canonical_prompt_sha256(prompt: str) -> str:
    """Return the digest of the exact signed prompt text."""

    return hashlib.sha256(str(prompt).encode("utf-8")).hexdigest()


def brain_source_projection_sha256(source_projection: Mapping[str, Any]) -> str:
    """Digest the server-owned Brain source package, excluding its digest field."""

    payload = {
        key: value
        for key, value in dict(source_projection).items()
        if key != "source_digest"
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def brain_source_projection_binding_sha256(binding: Mapping[str, Any]) -> str:
    """Digest the frozen source-binding fields, excluding their self digest."""

    payload = {
        key: value
        for key, value in dict(binding).items()
        if key != "binding_digest"
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def brain_source_projection_receipt_sha256(receipt: Mapping[str, Any]) -> str:
    """Digest one Brain-owned receipt, excluding its self digest."""

    payload = {
        key: value
        for key, value in dict(receipt).items()
        if key != "receipt_digest"
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalized_text_list(value: Any) -> list[str]:
    """Normalize bounded server-owned text directions without authoring prose."""

    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        values = []
    return list(
        dict.fromkeys(
            str(item).strip()
            for item in values
            if isinstance(item, str) and str(item).strip()
        )
    )


def build_brain_capability_guidance(
    *,
    capability_projection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project active capability directions into the Brain-owned source.

    The capability composer remains the authority for these directions.  This
    helper translates its typed contribution records into a narrow semantic
    package for the Brain finalizer; it does not append renderer text and it
    deliberately excludes provider, review, retry, and metadata payloads.
    """

    projection = dict(capability_projection or {})
    raw_cluster = projection.get("visual_cluster")
    raw_cluster = raw_cluster if isinstance(raw_cluster, Mapping) else {}
    composed = projection.get("composed_visual_contribution")
    composed = composed if isinstance(composed, Mapping) else {}

    active_capability_ids = _normalized_text_list(composed.get("active_capability_ids"))
    raw_contributions = raw_cluster.get("capability_contributions")
    if not isinstance(raw_contributions, list):
        raw_contributions = projection.get("capability_contributions")
    if not isinstance(raw_contributions, list):
        raw_contributions = []
    if not active_capability_ids:
        active_capability_ids = _normalized_text_list(
            [
                item.get("capability_id")
                for item in raw_contributions
                if isinstance(item, Mapping)
            ]
        )
    active_set = set(active_capability_ids)

    obligations: list[dict[str, Any]] = []
    positive_directions: list[str] = []
    negative_directions: list[str] = []
    for raw_contribution in raw_contributions:
        if not isinstance(raw_contribution, Mapping):
            continue
        capability_id = str(raw_contribution.get("capability_id") or "").strip()
        if not capability_id or capability_id not in active_set:
            continue
        stages = _normalized_text_list(raw_contribution.get("stages"))
        applicable_stages = [
            stage for stage in stages if stage in _V3_BRAIN_CAPABILITY_GUIDANCE_STAGES
        ]
        if not applicable_stages:
            continue
        positive = _normalized_text_list(raw_contribution.get("prompt_additions"))
        negative = _normalized_text_list(raw_contribution.get("negative_additions"))
        if not positive and not negative:
            continue
        obligations.append(
            {
                "capability_id": capability_id,
                "applies_to_stages": applicable_stages,
                "positive_directions": positive,
                "negative_directions": negative,
            }
        )
        positive_directions.extend(positive)
        negative_directions.extend(negative)

    # The composed aggregate is the compatibility fallback for an older
    # envelope that does not retain the per-capability rows.  In the current
    # enforced path it is also a completeness check: no composed direction may
    # disappear merely because a row was not materialized in the projection.
    positive_directions.extend(_normalized_text_list(composed.get("prompt_additions")))
    negative_directions.extend(_normalized_text_list(composed.get("negative_additions")))
    return {
        "contract_version": V3_BRAIN_CAPABILITY_GUIDANCE_CONTRACT_REV,
        "semantic_coverage": "complete",
        "active_capability_ids": active_capability_ids,
        "generation_obligations": obligations,
        "positive_directions": _normalized_text_list(positive_directions),
        "negative_directions": _normalized_text_list(negative_directions),
    }


def build_brain_protected_constraint_projection(
    *,
    prompt_guidance: Mapping[str, Any],
    image_set_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Project non-negotiable rendering constraints into a salient Brain channel.

    These facts already belong to the user/frozen planning contract.  The
    explicit projection prevents a natural-language finalizer from replacing
    numeric framing, crop, body-completeness, landmark, or negative rules with
    a broad quality summary while still allowing the final prompt to remain
    one coherent renderer direction rather than a checklist.
    """

    guidance = dict(prompt_guidance)
    plan = dict(image_set_plan)
    return {
        "contract_version": V3_BRAIN_PROTECTED_CONSTRAINTS_CONTRACT_REV,
        "semantic_coverage": "complete",
        "hard_constraints": _normalized_text_list(guidance.get("hard_constraints")),
        "composition_rules": _normalized_text_list(plan.get("composition_rules")),
        "quality_bar": _normalized_text_list(plan.get("quality_bar")),
        "layout_notes": _normalized_text_list(guidance.get("layout_notes")),
        "style_notes": _normalized_text_list(guidance.get("style_notes")),
        "negative_constraints": _normalized_text_list(guidance.get("negative_prompt_addons")),
    }


def with_brain_source_projection_digest(source_projection: Mapping[str, Any]) -> dict[str, Any]:
    """Return a source package with its stable server-owned digest attached."""

    payload = dict(source_projection)
    payload["source_digest"] = brain_source_projection_sha256(payload)
    return payload


def build_brain_source_projection(
    *,
    prompt_guidance: Mapping[str, Any],
    image_set_plan: Mapping[str, Any],
    requested_image_count: int,
    capability_guidance: Mapping[str, Any] | None = None,
    binding_facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the complete, scenario-neutral source package for finalization."""

    plan = dict(image_set_plan)
    guidance = dict(prompt_guidance)
    capability_guidance = dict(capability_guidance or {})
    protected_constraint_projection = build_brain_protected_constraint_projection(
        prompt_guidance=guidance,
        image_set_plan=plan,
    )
    binding_facts = dict(binding_facts or {})
    projected_guidance_and_plan = {
        "prompt_guidance": guidance,
        "image_set_plan": plan,
    }
    source_binding = {
        "contract_version": V3_BRAIN_SOURCE_PROJECTION_CONTRACT_REV,
        "user_intent_digest": _canonical_value_sha256(binding_facts.get("user_intent")),
        "planning_result_digest": _canonical_value_sha256(binding_facts.get("planning_result")),
        "prompt_guidance_image_set_digest": _canonical_value_sha256(projected_guidance_and_plan),
        "capability_guidance_digest": _canonical_value_sha256(capability_guidance),
        "protected_constraint_projection_digest": _canonical_value_sha256(
            protected_constraint_projection
        ),
        "active_capability_contract_digest": _canonical_value_sha256(
            binding_facts.get("active_capability_contracts", [])
        ),
        "reference_channel_ownership_digest": _canonical_value_sha256(
            binding_facts.get("reference_channel_ownership", {})
        ),
        "frozen_runtime_binding_digest": _canonical_value_sha256(
            binding_facts.get("frozen_runtime_binding", {})
        ),
        "policy_revision": str(
            binding_facts.get("policy_revision") or V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV
        ),
        "finalizer_stage": str(
            binding_facts.get("finalizer_stage") or V3_BRAIN_SOURCE_PROJECTION_FINALIZER_STAGE
        ),
    }
    source_binding["binding_digest"] = brain_source_projection_binding_sha256(source_binding)
    directions = [
        {"output_index": index, "direction": str(direction).strip()}
        for index, direction in enumerate(plan.get("shot_plan") or [], start=1)
        if str(direction).strip()
    ]
    return with_brain_source_projection_digest(
        {
            "contract_version": V3_BRAIN_SOURCE_PROJECTION_CONTRACT_REV,
            "requested_image_count": int(requested_image_count),
            "prompt_guidance": guidance,
            "image_set_plan": plan,
            "capability_guidance": capability_guidance,
            "protected_constraint_projection": protected_constraint_projection,
            "source_binding": source_binding,
            "per_output_directions": directions,
        }
    )


def build_brain_source_projection_receipt(
    projection: Mapping[str, Any],
    *,
    output_index: int,
    requested_image_count: int,
) -> dict[str, Any]:
    """Build the exact typed receipt expected from the Brain finalizer."""

    receipt = {
        "contract_version": V3_BRAIN_SOURCE_PROJECTION_CONTRACT_REV,
        "source_digest": str(projection.get("source_digest") or "").lower(),
        "output_index": int(output_index),
        "requested_image_count": int(requested_image_count),
        "semantic_coverage": "complete",
        "owner": "remote_v3_llm_brain",
    }
    receipt["receipt_digest"] = brain_source_projection_receipt_sha256(receipt)
    return receipt


def validate_brain_source_projection_receipt(
    record: Mapping[str, Any],
    *,
    required: bool,
    expected_digest: str | None = None,
    expected_output_index: int | None = None,
    expected_requested_image_count: int | None = None,
) -> tuple[bool, str]:
    """Validate a Brain source binding without reconstructing creative semantics locally."""

    if not required:
        return True, "legacy_source_projection_not_required"
    receipt = record.get("source_projection_receipt")
    if not isinstance(receipt, Mapping):
        return False, "source_projection_receipt_missing"
    expected_keys = {
        "contract_version",
        "source_digest",
        "output_index",
        "requested_image_count",
        "semantic_coverage",
        "owner",
        "receipt_digest",
    }
    if set(receipt) != expected_keys:
        return False, "source_projection_receipt_schema_invalid"
    source_digest = receipt.get("source_digest")
    receipt_digest = receipt.get("receipt_digest")
    output_index = receipt.get("output_index")
    requested_image_count = receipt.get("requested_image_count")
    if (
        receipt.get("contract_version") != V3_BRAIN_SOURCE_PROJECTION_CONTRACT_REV
        or receipt.get("semantic_coverage") != "complete"
        or receipt.get("owner") != "remote_v3_llm_brain"
        or not isinstance(source_digest, str)
        or len(source_digest) != 64
        or any(char not in "0123456789abcdef" for char in source_digest.lower())
        or source_digest.lower() != str(expected_digest or "").lower()
        or not isinstance(receipt_digest, str)
        or len(receipt_digest) != 64
        or any(char not in "0123456789abcdef" for char in receipt_digest.lower())
        or receipt_digest.lower() != brain_source_projection_receipt_sha256(receipt)
        or not isinstance(output_index, int)
        or isinstance(output_index, bool)
        or output_index != expected_output_index
        or not isinstance(requested_image_count, int)
        or isinstance(requested_image_count, bool)
        or requested_image_count != expected_requested_image_count
        or output_index < 1
        or requested_image_count < 1
        or output_index > requested_image_count
    ):
        return False, "source_projection_receipt_binding_invalid"
    return True, "source_projection_receipt_valid"


def validate_unified_prompt_record(
    record: Mapping[str, Any],
    *,
    required: bool,
) -> tuple[bool, str, str]:
    """Validate structured compression evidence without inferring semantics locally.

    The Brain owns semantic completeness.  Runtime code only checks the signed
    fields, policy values, final length, and final-text digest.
    """

    if not required:
        return True, "legacy_policy_not_required", "legacy"
    # The receipt binds the exact renderer text.  Whitespace is part of the
    # signed prompt and must not be normalized before digest or length checks.
    prompt = str(record.get("prompt") or "")
    if record.get("prompt_status") != "complete":
        return False, "prompt_status_incomplete", "blocked"
    if record.get("semantic_coverage") != "complete":
        return False, "semantic_coverage_incomplete", "blocked"
    decision = record.get("compression_decision")
    receipt = record.get("compression_receipt")
    if decision == "none":
        if len(prompt) > V3_UNIFIED_PROMPT_COMPRESSION_THRESHOLD_CHARS:
            return False, "over_threshold_without_compression", "blocked"
        if receipt is not None:
            return False, "unexpected_compression_receipt", "blocked"
        return True, "none", "none"
    if decision != "brain_semantic_once":
        return False, "compression_decision_missing", "blocked"
    if len(prompt) > V3_UNIFIED_PROMPT_COMPRESSION_TARGET_MAX_CHARS:
        return False, "compressed_prompt_exceeds_target", "blocked"
    if not isinstance(receipt, Mapping):
        return False, "compression_receipt_missing", "blocked"
    expected_keys = {
        "contract_version",
        "policy_revision",
        "decision",
        "source_chars",
        "final_chars",
        "final_prompt_sha256",
        "semantic_status",
        "owner",
    }
    if set(receipt) != expected_keys:
        return False, "compression_receipt_schema_invalid", "blocked"
    source_chars = receipt.get("source_chars")
    final_chars = receipt.get("final_chars")
    if (
        not isinstance(source_chars, int)
        or isinstance(source_chars, bool)
        or source_chars <= V3_UNIFIED_PROMPT_COMPRESSION_THRESHOLD_CHARS
        or not isinstance(final_chars, int)
        or isinstance(final_chars, bool)
        or final_chars != len(prompt)
        or final_chars > V3_UNIFIED_PROMPT_COMPRESSION_TARGET_MAX_CHARS
        or receipt.get("contract_version") != "v3_prompt_compression_receipt_v1"
        or receipt.get("policy_revision") != V3_UNIFIED_PROMPT_COMPRESSION_POLICY_REV
        or receipt.get("decision") != "brain_semantic_once"
        or receipt.get("semantic_status") != "complete"
        or receipt.get("owner") != "remote_v3_llm_brain"
        or receipt.get("final_prompt_sha256")
        != _safe_canonical_prompt_sha256(prompt)
    ):
        return False, "compression_receipt_binding_invalid", "blocked"
    return True, "brain_semantic_once", "brain_semantic_once"


def _safe_canonical_prompt_sha256(prompt: str) -> str | None:
    """Return a digest for valid UTF-8 text, or ``None`` for fail-closed input."""

    try:
        return canonical_prompt_sha256(prompt)
    except UnicodeEncodeError:
        return None
