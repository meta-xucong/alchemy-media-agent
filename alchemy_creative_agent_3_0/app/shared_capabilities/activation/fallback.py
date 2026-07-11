"""Deterministic task profiling and activation intent fallback."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import (
    ActivationEvidence,
    CapabilityActivationIntent,
    PreservationTarget,
    RequestedCapability,
    TemplateCapabilityPolicy,
    VisualSubjectEntity,
    VisualTaskProfile,
)


PERSON_SIGNALS = (
    "person",
    "portrait",
    "woman",
    "man",
    "girl",
    "boy",
    "model",
    "人物",
    "人像",
    "女性",
    "男性",
    "女孩",
    "男孩",
    "美女",
    "模特",
    "女模",
    "男模",
    "儿童",
    "孩子",
    "小孩",
    "宝宝",
    "真人",
)
STYLIZED_PERSON_SIGNALS = ("anime", "cartoon", "illustration", "3d character", "动漫", "漫画", "插画", "卡通", "三维角色")
PRODUCT_SIGNALS = ("product", "packshot", "listing", "商品", "产品", "包装", "主图", "电商")
SCENE_SIGNALS = ("landscape", "interior", "architecture", "cityscape", "风景", "室内", "建筑", "场景", "空间")
LAYOUT_SIGNALS = ("poster", "banner", "carousel", "layout", "headline", "海报", "横幅", "轮播", "排版", "标题", "文字")


def build_task_profile_and_intent(
    *,
    user_input: str,
    job_id: str,
    project_id: str | None,
    template_id: str,
    scenario_id: str,
    uploaded_assets: list[dict[str, Any]],
    reference_assets: list[dict[str, Any]],
    product_profile: dict[str, Any],
    metadata: dict[str, Any],
    template_policy: TemplateCapabilityPolicy,
) -> tuple[VisualTaskProfile, CapabilityActivationIntent]:
    text = user_input.casefold()
    all_assets = [*uploaded_assets, *reference_assets]
    evidence: list[ActivationEvidence] = []
    entities: list[VisualSubjectEntity] = []
    preservation: list[PreservationTarget] = []
    requested: list[RequestedCapability] = []

    def add_evidence(kind: str, source: str, value: Any, confidence: float) -> str:
        evidence_id = stable_id("activation_evidence", job_id, kind, source, len(evidence))
        evidence.append(ActivationEvidence(evidence_id=evidence_id, evidence_type=kind, source=source, value=value, confidence=confidence))
        return evidence_id

    def add_entity(entity_type: str, confidence: float, asset_ids: list[str] | None = None, preservation_level: str = "none") -> str:
        entity_id = stable_id("visual_entity", job_id, entity_type, len(entities))
        entities.append(
            VisualSubjectEntity(
                entity_id=entity_id,
                entity_type=entity_type,
                source_asset_ids=list(asset_ids or []),
                preservation_level=preservation_level,
                confidence=confidence,
            )
        )
        return entity_id

    asset_roles: dict[str, list[str]] = {}
    for asset in all_assets:
        role = str(asset.get("role") or asset.get("asset_role") or asset.get("reference_role") or "").casefold()
        asset_id = str(asset.get("asset_id") or asset.get("output_id") or asset.get("reference_id") or "")
        asset_roles.setdefault(role, []).append(asset_id)

    person_text = any(signal in text for signal in PERSON_SIGNALS)
    stylized_person = any(signal in text for signal in STYLIZED_PERSON_SIGNALS)
    portrait_assets = [asset_id for role, ids in asset_roles.items() if any(key in role for key in ("face", "portrait", "identity", "person")) for asset_id in ids if asset_id]
    product_assets = [asset_id for role, ids in asset_roles.items() if "product" in role or "商品" in role for asset_id in ids if asset_id]
    scene_assets = [asset_id for role, ids in asset_roles.items() if any(key in role for key in ("scene", "background", "composition")) for asset_id in ids if asset_id]
    product_text = scenario_id == "ecommerce" or bool(product_profile) or any(signal in text for signal in PRODUCT_SIGNALS)
    scene_text = any(signal in text for signal in SCENE_SIGNALS)
    layout_text = any(signal in text for signal in LAYOUT_SIGNALS)

    if person_text or portrait_assets:
        evidence_id = add_evidence("visible_person", "user_input" if person_text else "declared_asset_role", True, 0.85)
        entity_id = add_entity("person", 0.85, portrait_assets, "strong" if portrait_assets else "none")
        if not stylized_person:
            requested.append(RequestedCapability(capability_id="human_realism", reason_codes=["visible_real_person"], evidence_ids=[evidence_id], confidence=0.85))
        if portrait_assets:
            portrait_evidence = add_evidence("portrait_reference", "declared_asset_role", portrait_assets, 0.95)
            preservation.append(PreservationTarget(target_id=stable_id("preserve", entity_id), target_type="person_identity", source_entity_id=entity_id, source_asset_ids=portrait_assets, level="strong", allowed_changes=["pose", "expression", "camera", "lighting", "styling"], evidence_ids=[portrait_evidence]))
            requested.append(RequestedCapability(capability_id="portrait_identity", reason_codes=["portrait_reference_present"], evidence_ids=[portrait_evidence], requested_profile="strong", confidence=0.95))

    if product_text or product_assets:
        source = "product_reference" if product_assets else "product_intent"
        product_evidence = add_evidence(source, "declared_asset_role" if product_assets else "user_or_template", product_assets or True, 0.95 if product_assets else 0.75)
        entity_id = add_entity("product", 0.95 if product_assets else 0.75, product_assets, "strong" if product_assets else "concept")
        if product_assets:
            preservation.append(PreservationTarget(target_id=stable_id("preserve", entity_id), target_type="product_identity", source_entity_id=entity_id, source_asset_ids=product_assets, level="strong", allowed_changes=["background", "camera", "lighting", "context"], evidence_ids=[product_evidence]))
        requested.append(RequestedCapability(capability_id="product_identity", reason_codes=[source], evidence_ids=[product_evidence], requested_profile="reference_truth" if product_assets else "described_concept", confidence=0.95 if product_assets else 0.75))

    if scene_text or scene_assets:
        scene_evidence = add_evidence("scene_reference" if scene_assets else "scene_intent", "declared_asset_role" if scene_assets else "user_input", scene_assets or True, 0.9 if scene_assets else 0.65)
        add_entity("scene", 0.9 if scene_assets else 0.65, scene_assets, "balanced" if scene_assets else "none")
        if scene_assets or bool(metadata.get("preserve_scene")):
            requested.append(RequestedCapability(capability_id="scene_continuity", reason_codes=["scene_preservation"], evidence_ids=[scene_evidence], confidence=0.9))

    if layout_text or metadata.get("required_text"):
        layout_evidence = add_evidence("layout_intent", "user_input", True, 0.8)
        add_entity("text_layout", 0.8)
        requested.append(RequestedCapability(capability_id="typography_layout", reason_codes=["layout_or_text_requested"], evidence_ids=[layout_evidence], confidence=0.8))

    requested_count = _int_value(metadata.get("requested_image_count"), 1)
    variation_mode = str(metadata.get("variation_mode") or metadata.get("effective_variation_mode") or "")
    if requested_count > 1 or variation_mode:
        suite_evidence = add_evidence("multiple_outputs", "explicit_control", requested_count, 1.0)
        requested.append(RequestedCapability(capability_id="suite_direction", reason_codes=["multiple_outputs"], evidence_ids=[suite_evidence], confidence=1.0))

    if all_assets:
        ref_evidence = add_evidence("reference_assets_present", "request", len(all_assets), 1.0)
        requested.append(RequestedCapability(capability_id="reference_channel_policy", reason_codes=["reference_assets_present"], evidence_ids=[ref_evidence], confidence=1.0))

    for capability_id in metadata.get("capability_hints", []) if isinstance(metadata.get("capability_hints"), list) else []:
        cleaned = str(capability_id or "").strip()
        if not cleaned:
            continue
        hint_evidence = add_evidence("explicit_capability_hint", "scenario_parameter", cleaned, 0.8)
        requested.append(
            RequestedCapability(
                capability_id=cleaned,
                activation_mode="recommended",
                reason_codes=["explicit_capability_hint"],
                evidence_ids=[hint_evidence],
                confidence=0.8,
            )
        )

    requested = _dedupe_requested(requested)
    profile_id = stable_id("visual_task_profile", job_id, template_id, scenario_id, user_input)
    profile = VisualTaskProfile(
        profile_id=profile_id,
        project_id=project_id,
        job_id=job_id,
        template_id=template_id,
        scenario_id=scenario_id,
        subject_entities=entities,
        preservation_targets=preservation,
        allowed_changes=["composition", "camera", "lighting", "background"] if preservation else [],
        visual_intent_tags=[tag for tag, active in (("portrait", person_text), ("product", product_text), ("scene", scene_text), ("layout", layout_text)) if active],
        requested_deliverable_roles=list(metadata.get("requested_deliverable_roles") or []),
        explicit_user_controls={key: metadata[key] for key in ("requested_image_count", "variation_mode", "preserve_scene") if key in metadata},
        unknown_requirements=[] if entities else ["subject_type_not_explicit"],
        confidence=max([entity.confidence for entity in entities], default=0.5),
        evidence=evidence,
    )
    intent = CapabilityActivationIntent(
        intent_id=stable_id("capability_intent", profile_id, *[item.capability_id for item in requested]),
        task_profile_id=profile_id,
        requested_capabilities=requested,
        unresolved_signals=list(profile.unknown_requirements),
        confidence=profile.confidence,
    )
    return profile, intent


def _dedupe_requested(items: list[RequestedCapability]) -> list[RequestedCapability]:
    merged: dict[str, RequestedCapability] = {}
    for item in items:
        current = merged.get(item.capability_id)
        if current is None or item.confidence > current.confidence:
            merged[item.capability_id] = item
    return list(merged.values())


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
