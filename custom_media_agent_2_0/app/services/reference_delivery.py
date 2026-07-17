"""V2-native reference-content delivery contracts.

This module deliberately contains no route, repository, or provider calls.  It
turns the existing V2 asset-binding result into a canonical, auditable contract
that downstream prompt, provider, renderer, and reviewer modules can share.
"""

from __future__ import annotations

from hashlib import sha256
import re
from typing import Any


HARD_REFERENCE_ROLES = {"subject_reference", "logo_reference", "face_reference", "background_reference"}
_DENSE_SOURCE_PATTERN = re.compile(
    r"(?:menu|poster|price|schedule|catalog|flyer|菜[单單]|海报|海報|价格|價目|价目|套餐|日期|活动|活動|二维码|二維碼)",
    re.IGNORECASE,
)
_TEXT_KIND_PATTERNS = (
    ("price", re.compile(r"(?:[$¥￥]|\b\d+(?:\.\d{1,2})?\s*(?:元|rmb|usd|cny|%))", re.IGNORECASE)),
    ("date", re.compile(r"(?:\d{1,2}[/-]\d{1,2}|星期[一二三四五六日天]|周[一二三四五六日天]|\bmon\b|\btue\b|\bwed\b|\bthu\b|\bfri\b)", re.IGNORECASE)),
    ("cta", re.compile(r"(?:扫码|掃碼|预约|預約|订购|訂購|联系|聯絡|电话|電話|关注|關注|buy|order|contact)", re.IGNORECASE)),
)


def build_reference_delivery_contract(asset_context: dict[str, Any] | None) -> dict[str, Any]:
    """Build a V2 delivery contract from already-resolved asset bindings.

    The result separates template-owned frame fields from source-owned facts.
    It includes source text only in the private prompt-plan contract; callers
    must use :func:`reference_delivery_audit` for persisted public metadata.
    """

    context = asset_context if isinstance(asset_context, dict) else {}
    relationship = _mapping(context.get("task_relationship_model"))
    binding_plan = _mapping(context.get("asset_binding_plan"))
    bindings = [item for item in binding_plan.get("bindings", []) if isinstance(item, dict)]
    template_locked = bool(context.get("template_lock_contract"))
    contracts = [_reference_intent_contract(binding, template_locked=template_locked) for binding in bindings]
    evidence = _source_evidence(context, contracts)
    composite_source = any(item["usage_mode"] == "composite_content" for item in contracts)
    dense_source = composite_source or _is_information_dense(context, evidence)
    evidence_capture = _evidence_capture(context, evidence)
    source_text_evidence_required = bool(dense_source)
    # A single uploaded asset may deliberately fulfil several V2 roles (for
    # example, product identity and logo).  Keep every role-level contract for
    # auditability, while matching the provider plan's one-input-per-asset
    # semantics here.  Otherwise a correct, de-duplicated provider request
    # would look like contract drift at preflight.
    required_reference_ids = _unique_asset_ids(
        item["asset_id"] for item in contracts if item["provider_input_required"]
    )
    critical_field_ids = [item["field_id"] for item in evidence if item["required"]]
    return {
        "contract_version": 1,
        "contract_id": _stable_id("rdc", context, contracts),
        "template_frame_owner": "selected_template" if template_locked else "creative_run",
        "reference_intents": contracts,
        "source_evidence": evidence,
        "evidence_capture": evidence_capture,
        "required_reference_asset_ids": required_reference_ids,
        "requires_image_reference": bool(required_reference_ids),
        "information_dense": dense_source,
        "text_rendering": {
            "mode": "deterministic_overlay" if dense_source else "generative",
            "required_field_ids": critical_field_ids,
            "overlay_slots_required": bool(dense_source and critical_field_ids),
        },
        "acceptance": {
            "requires_pixel_review": bool(required_reference_ids or dense_source),
            "requires_source_text_evidence": source_text_evidence_required,
            "source_text_evidence_ready": bool(evidence) if source_text_evidence_required else None,
            "block_automatic_delivery": bool(source_text_evidence_required and not evidence),
            "required_field_ids": critical_field_ids,
            "minimum_text_coverage": 1.0 if dense_source and critical_field_ids else None,
            "template_layout_policy": "selected_template" if template_locked else "creative_run",
        },
        "semantic_retry": {
            "max_attempts": 1 if (required_reference_ids or dense_source) else 0,
            "eligible_risks": [
                "reference_adherence_unverified",
                "reference_pixel_review_unavailable",
                "required_source_text_unverified",
                "deterministic_text_overlay_missing",
                "provider_input_images_missing",
            ],
        },
        "task_relationship": {
            "primary_relationship": str(relationship.get("primary_relationship") or ""),
            "content_extraction": bool(relationship.get("content_extraction")),
            "template_slot_replacement": bool(relationship.get("template_slot_replacement")),
        },
    }


def reference_delivery_prompt_section(contract: dict[str, Any] | None) -> str:
    """Render only the necessary provider instruction from a delivery contract."""

    contract = _mapping(contract)
    if not contract:
        return ""
    intents = [item for item in contract.get("reference_intents", []) if isinstance(item, dict)]
    evidence = [item for item in contract.get("source_evidence", []) if isinstance(item, dict) and item.get("required")]
    parts: list[str] = []
    for intent in intents:
        if not intent.get("provider_input_required"):
            continue
        label = str(intent.get("usage_mode") or "reference").replace("_", " ")
        source_fields = ", ".join(str(item) for item in intent.get("source_owned_fields", [])[:5])
        parts.append(
            f"Reference {intent.get('reference_index') or '?'} is a {label} contract with {intent.get('authority')} authority. "
            f"Preserve its source-owned fields: {source_fields or 'declared visual evidence'}."
        )
    if evidence:
        values = "; ".join(
            f"{item.get('kind', 'copy')}: {item.get('value')}" for item in evidence if str(item.get("value") or "").strip()
        )
        if values:
            parts.append(
                "SOURCE FACTS: retain these source facts exactly where the active template provides compatible text slots: " + values
            )
    if contract.get("information_dense"):
        parts.append(
            "For information-dense source material, do not invent, reorder, or garble dates, prices, offer rules, CTA, or source-to-item relationships. "
            "The selected template remains the layout owner unless the user explicitly unlocks source layout."
        )
    return " ".join(parts).strip()


def reference_delivery_audit(contract: dict[str, Any] | None) -> dict[str, Any]:
    """Return a persistable audit summary without raw source copy or image bytes."""

    contract = _mapping(contract)
    intents = [item for item in contract.get("reference_intents", []) if isinstance(item, dict)]
    evidence = [item for item in contract.get("source_evidence", []) if isinstance(item, dict)]
    return {
        "contract_id": contract.get("contract_id"),
        "contract_version": contract.get("contract_version"),
        "template_frame_owner": contract.get("template_frame_owner"),
        "information_dense": bool(contract.get("information_dense")),
        "requires_image_reference": bool(contract.get("requires_image_reference")),
        "required_reference_asset_ids": list(contract.get("required_reference_asset_ids") or []),
        "reference_intents": [
            {
                "asset_id": item.get("asset_id"),
                "reference_index": item.get("reference_index"),
                "usage_mode": item.get("usage_mode"),
                "authority": item.get("authority"),
                "provider_input_required": bool(item.get("provider_input_required")),
                "source_owned_fields": list(item.get("source_owned_fields") or []),
            }
            for item in intents
        ],
        "source_evidence": [
            {
                "field_id": item.get("field_id"),
                "asset_id": item.get("asset_id"),
                "kind": item.get("kind"),
                "required": bool(item.get("required")),
                "value_hash": item.get("value_hash"),
                "value_length": item.get("value_length"),
                "confidence": item.get("confidence"),
            }
            for item in evidence
        ],
        "evidence_capture": _mapping(contract.get("evidence_capture")),
        "text_rendering": _mapping(contract.get("text_rendering")),
        "acceptance": _mapping(contract.get("acceptance")),
        "semantic_retry": _mapping(contract.get("semantic_retry")),
    }


def _reference_intent_contract(binding: dict[str, Any], *, template_locked: bool) -> dict[str, Any]:
    role = str(binding.get("role") or "subject_reference")
    fusion_mode = str(binding.get("fusion_mode") or "reference")
    usage_mode = _usage_mode(role=role, fusion_mode=fusion_mode)
    authority = "required" if bool(binding.get("provider_input_required")) or str(binding.get("constraint_strength")) == "required" else "strong"
    source_owned, template_owned = _field_authority(usage_mode=usage_mode, template_locked=template_locked)
    placement = _mapping(binding.get("placement_intent"))
    return {
        "asset_id": str(binding.get("asset_id") or ""),
        "reference_index": binding.get("reference_index"),
        "role": role,
        "requested_role": binding.get("requested_role"),
        "fusion_mode": fusion_mode,
        "usage_mode": usage_mode,
        "authority": authority,
        "provider_input_required": bool(binding.get("provider_input_required")),
        "source_layout_policy": "only_if_unlocked" if template_locked else "creative_run",
        "source_owned_fields": source_owned,
        "template_owned_fields": template_owned,
        "target_surface": binding.get("target_surface") or placement.get("target_surface"),
    }


def _usage_mode(*, role: str, fusion_mode: str) -> str:
    if fusion_mode == "composite_content_source":
        return "composite_content"
    if fusion_mode == "template_slot_replacement":
        return "product_identity"
    if role == "logo_reference":
        return "logo_exact"
    if role == "face_reference":
        return "subject_identity"
    if role == "background_reference":
        return "background"
    if role == "style_reference":
        return "style"
    if role == "composition_reference":
        return "composition"
    if role == "color_reference":
        return "color"
    return "subject_identity"


def _field_authority(*, usage_mode: str, template_locked: bool) -> tuple[list[str], list[str]]:
    template_fields = ["composition", "spatial_hierarchy", "lighting", "background_density", "layout_structure"] if template_locked else []
    if usage_mode == "composite_content":
        return ["source_copy", "dates", "prices", "offer_terms", "cta", "food_product_correspondence"], template_fields
    if usage_mode in {"subject_identity", "product_identity"}:
        return ["visible_identity", "shape", "proportions", "product_appearance"], template_fields
    if usage_mode == "logo_exact":
        return ["logo_shape", "logo_proportions", "brand_text"], template_fields
    if usage_mode == "background":
        return ["background_environment"], template_fields
    if usage_mode == "composition":
        return ["camera_relationship"], template_fields
    if usage_mode == "color":
        return ["palette", "accent_colors"], template_fields
    return ["style_cues"], template_fields


def _source_evidence(context: dict[str, Any], contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contracts_by_asset: dict[str, list[dict[str, Any]]] = {}
    for contract in contracts:
        asset_id = str(contract.get("asset_id") or "")
        if asset_id:
            contracts_by_asset.setdefault(asset_id, []).append(contract)
    fields: list[dict[str, Any]] = []
    for asset in context.get("uploaded_assets", []):
        if not isinstance(asset, dict):
            continue
        asset_id = str(asset.get("asset_id") or "")
        asset_contracts = contracts_by_asset.get(asset_id) or []
        if not asset_contracts:
            continue
        brief = _mapping(asset.get("brief"))
        detected = brief.get("detected_text") if isinstance(brief.get("detected_text"), list) else []
        for index, item in enumerate(detected):
            value, confidence = _detected_text_value(item)
            if not value:
                continue
            fields.append(
                {
                    "field_id": f"evidence_{asset_id}_{index + 1}",
                    "asset_id": asset_id,
                    "kind": _text_kind(value),
                    "value": value,
                    "value_hash": _hash(value),
                    "value_length": len(value),
                    "confidence": confidence,
                    "required": any(
                        contract.get("usage_mode") == "composite_content" for contract in asset_contracts
                    )
                    and confidence >= 0.7,
                }
            )
    return fields


def _evidence_capture(context: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    if evidence:
        return {"status": "available", "field_count": len(evidence)}
    receipts: list[dict[str, Any]] = []
    for asset in context.get("uploaded_assets", []):
        if not isinstance(asset, dict):
            continue
        brief = _mapping(asset.get("brief"))
        image = _mapping(brief.get("image"))
        receipt = _mapping(image.get("text_evidence"))
        if receipt:
            receipts.append(receipt)
    statuses = {str(item.get("status") or "") for item in receipts}
    if "unavailable" in statuses:
        status = "unavailable"
    elif "failed" in statuses:
        status = "failed"
    elif "no_text_detected" in statuses:
        status = "no_text_detected"
    else:
        status = "not_captured"
    return {"status": status, "asset_count": len(receipts)}


def _detected_text_value(item: Any) -> tuple[str, float]:
    if isinstance(item, str):
        return _clean(item), 1.0
    if not isinstance(item, dict):
        return "", 0.0
    value = _clean(item.get("text") or item.get("value") or item.get("content"))
    try:
        confidence = float(item.get("confidence", 1.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return value, max(0.0, min(1.0, confidence))


def _is_information_dense(context: dict[str, Any], evidence: list[dict[str, Any]]) -> bool:
    if evidence:
        return True
    return bool(_DENSE_SOURCE_PATTERN.search(str(context.get("user_prompt") or "")))


def _unique_asset_ids(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        asset_id = str(value or "").strip()
        if asset_id and asset_id not in result:
            result.append(asset_id)
    return result


def _text_kind(value: str) -> str:
    for kind, pattern in _TEXT_KIND_PATTERNS:
        if pattern.search(value):
            return kind
    return "copy"


def _stable_id(prefix: str, context: dict[str, Any], contracts: list[dict[str, Any]]) -> str:
    seed = {
        "prompt": _hash(str(context.get("user_prompt") or "")),
        "assets": [
            (item.get("asset_id"), item.get("usage_mode"), item.get("authority"), item.get("reference_index")) for item in contracts
        ],
        "relationship": _mapping(context.get("task_relationship_model")).get("primary_relationship"),
    }
    return f"{prefix}_{_hash(repr(seed))[:12]}"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _hash(value: Any) -> str:
    return sha256(str(value or "").encode("utf-8")).hexdigest()
