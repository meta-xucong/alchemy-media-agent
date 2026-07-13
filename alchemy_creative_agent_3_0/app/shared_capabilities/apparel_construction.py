"""Typed garment-construction evidence shared by V3 runtime paths.

This module deliberately has no audience, age, template, provider, or scene
vocabulary.  It only makes supplied apparel facts explicit enough for the
constraint ledger, provider projection, and pixel review to preserve them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ..schemas.models import V3BaseModel


APPAREL_CONSTRUCTION_CHANNELS = (
    "product_silhouette",
    "product_pattern_registration",
    "product_layer_topology",
    "product_construction_detail",
    "product_material_response",
    "product_drape_behavior",
)

# These are generic product-truth review outcomes, not a child, fashion, or
# template route.  They are emitted only when an explicit typed construction
# fact is present in the frozen ledger.
APPAREL_CONSTRUCTION_REVIEW_ISSUES: dict[str, str] = {
    "product_silhouette": "product_silhouette_drift",
    "product_pattern_registration": "product_pattern_registration_drift",
    "product_layer_topology": "product_layer_topology_drift",
    "product_construction_detail": "product_construction_detail_drift",
    "product_material_response": "product_material_response_drift",
    "product_drape_behavior": "product_drape_behavior_drift",
}

_APPAREL_CATEGORY_TOKENS = (
    "apparel",
    "clothing",
    "garment",
    "dress",
    "skirt",
    "shirt",
    "jacket",
    "coat",
    "blouse",
    "trouser",
    "pants",
    "jeans",
    "sweater",
    "cardigan",
    "uniform",
    "outfit",
    "fashion",
)

_FACT_ALIASES: dict[str, tuple[str, ...]] = {
    "product_silhouette": (
        "silhouette_and_proportion",
        "silhouette",
        "garment_shape",
        "cut",
        "fit",
        "proportion",
        "length",
        "volume",
    ),
    "product_pattern_registration": (
        "print_or_pattern_registration",
        "pattern_registration",
        "print_placement",
        "pattern_placement",
        "pattern_scale",
        "print_scale",
        "pattern",
        "print",
    ),
    "product_layer_topology": (
        "layer_order",
        "layering",
        "layers",
        "transparency_or_mesh_topology",
        "mesh_topology",
        "transparency",
        "mesh",
        "sheer_layer",
    ),
    "product_construction_detail": (
        "seam_hem_edge_trim_fastening",
        "construction_detail",
        "construction_details",
        "seams",
        "seam",
        "hem",
        "edge_trim",
        "trim",
        "fastening",
        "closure",
        "accessory_placement",
    ),
    "product_material_response": (
        "material_weight_and_surface_response",
        "material_response",
        "fabric_weight",
        "surface_response",
        "fabric_finish",
        "fabric",
        "material",
        "materials",
    ),
    "product_drape_behavior": (
        "fold_tension_gravity_and_drape",
        "drape_behavior",
        "drape",
        "folds",
        "fold_topology",
        "tension",
        "gravity",
    ),
}


class ApparelConstructionFact(V3BaseModel):
    """One supplied garment fact, with its evidentiary strength preserved."""

    channel: str
    values: list[str] = Field(default_factory=list)
    strength: Literal["hard", "strong", "soft"] = "soft"
    source: str = "product_profile"
    source_fields: list[str] = Field(default_factory=list)
    evidence_mode: Literal["reference_backed", "declared_structured", "declared_signal"] = "declared_signal"
    allowed_variation: str = "prompt_owned_when_not_explicitly_evidenced"


class ApparelConstructionFacts(V3BaseModel):
    """A source-proportionate garment truth package.

    ``applies`` is false unless the request identifies apparel or supplies an
    explicit construction map.  The package never attempts to infer garment
    facts from a photograph or from a subject's age.
    """

    applies: bool = False
    facts: list[ApparelConstructionFact] = Field(default_factory=list)
    source_summary: str = "no_apparel_construction_evidence"

    def provider_projection(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def apparel_construction_review_contract(projection: dict[str, Any] | None) -> dict[str, Any]:
    """Derive pixel-review obligations from the already-frozen apparel facts.

    The caller may pass provider-projection JSON rather than a model.  Only
    hard/strong facts are review obligations: soft declared signals remain
    prompt guidance and must not be overclaimed as pixel-verifiable truth.
    """

    payload = dict(projection or {})
    if not bool(payload.get("applies")):
        return {
            "applies": False,
            "facts": [],
            "issue_codes": [],
            "score_dimensions": [],
            "source_summary": "no_apparel_construction_evidence",
        }

    facts: list[dict[str, Any]] = []
    issue_codes: list[str] = []
    for raw_fact in payload.get("facts", []):
        if not isinstance(raw_fact, dict):
            continue
        channel = str(raw_fact.get("channel") or "").strip()
        strength = str(raw_fact.get("strength") or "soft").strip()
        values = _as_strings(raw_fact.get("values"))
        if channel not in APPAREL_CONSTRUCTION_REVIEW_ISSUES or strength not in {"hard", "strong"} or not values:
            continue
        issue_codes.append(APPAREL_CONSTRUCTION_REVIEW_ISSUES[channel])
        facts.append(
            {
                "channel": channel,
                "values": values,
                "strength": strength,
                "evidence_mode": str(raw_fact.get("evidence_mode") or "declared_signal"),
                "allowed_variation": str(raw_fact.get("allowed_variation") or ""),
            }
        )
    return {
        "applies": bool(facts),
        "facts": facts,
        "issue_codes": _unique(issue_codes),
        "score_dimensions": ["product_fidelity", "apparel_construction_fidelity"] if facts else [],
        "source_summary": str(payload.get("source_summary") or "apparel_construction_evidence"),
    }


def extract_apparel_construction_facts(
    product_profile: dict[str, Any] | None,
    *,
    has_reference_evidence: bool = False,
) -> ApparelConstructionFacts:
    """Extract only explicit apparel construction evidence from a profile.

    A nested ``apparel_construction`` map is an explicit, hard structured
    specification.  Equivalent top-level profile fields are retained as soft
    declared signals.  A reference image upgrades either kind of fact to
    reference-backed hard evidence; no visual inference happens here.
    """

    profile = dict(product_profile or {})
    nested = profile.get("apparel_construction")
    nested_map = dict(nested) if isinstance(nested, dict) else {}
    applies = bool(nested_map) or _looks_like_apparel(profile)
    if not applies:
        return ApparelConstructionFacts()

    facts: list[ApparelConstructionFact] = []
    for channel, aliases in _FACT_ALIASES.items():
        values, source_fields, explicit_nested = _fact_values(profile, nested_map, aliases)
        if not values:
            continue
        if has_reference_evidence:
            evidence_mode: Literal["reference_backed", "declared_structured", "declared_signal"] = "reference_backed"
            strength: Literal["hard", "strong", "soft"] = _strength_for_channel(channel, default="hard")
        elif explicit_nested:
            evidence_mode = "declared_structured"
            strength = _strength_for_channel(channel, default="hard")
        else:
            evidence_mode = "declared_signal"
            strength = "soft"
        facts.append(
            ApparelConstructionFact(
                channel=channel,
                values=values,
                strength=strength,
                source="product_profile.apparel_construction" if explicit_nested else "product_profile",
                source_fields=source_fields,
                evidence_mode=evidence_mode,
                allowed_variation=_allowed_variation(channel, strength),
            )
        )

    if not facts:
        return ApparelConstructionFacts(
            applies=True,
            source_summary="apparel_identified_without_explicit_construction_evidence",
        )
    modes = {fact.evidence_mode for fact in facts}
    source_summary = (
        "reference_backed_apparel_construction"
        if "reference_backed" in modes
        else "declared_structured_apparel_construction"
        if "declared_structured" in modes
        else "declared_apparel_construction_signals"
    )
    return ApparelConstructionFacts(applies=True, facts=facts, source_summary=source_summary)


def _looks_like_apparel(profile: dict[str, Any]) -> bool:
    values = [
        profile.get("product_category"),
        profile.get("category"),
        profile.get("product_name"),
        profile.get("name"),
    ]
    text = " ".join(str(value or "") for value in values).lower()
    return any(token in text for token in _APPAREL_CATEGORY_TOKENS)


def _fact_values(
    profile: dict[str, Any],
    nested: dict[str, Any],
    aliases: tuple[str, ...],
) -> tuple[list[str], list[str], bool]:
    values: list[str] = []
    source_fields: list[str] = []
    explicit_nested = False
    for field in aliases:
        if field in nested:
            explicit_nested = True
            source_fields.append(f"apparel_construction.{field}")
            values.extend(_as_strings(nested[field]))
        elif field in profile:
            source_fields.append(field)
            values.extend(_as_strings(profile[field]))
    return _unique(values), _unique(source_fields), explicit_nested


def _strength_for_channel(channel: str, *, default: Literal["hard", "strong", "soft"]) -> Literal["hard", "strong", "soft"]:
    if channel in {"product_material_response", "product_drape_behavior"}:
        return "strong"
    return default


def _allowed_variation(channel: str, strength: Literal["hard", "strong", "soft"]) -> str:
    if channel == "product_drape_behavior":
        return "pose_and_motion_may_change_fold_configuration_without_changing_weight_tension_or_gravity_response"
    if channel == "product_material_response":
        return "lighting_and_pose_may_change_highlights_and_folds_without_changing_material_weight_or_surface_response"
    if strength == "soft":
        return "may_vary_when_not_confirmed_by_reference_or_explicit_structured_specification"
    return "no_change_to_supplied_visible_structure_or_placement"


def _as_strings(value: Any) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, (list, tuple, set)):
        flattened: list[str] = []
        for item in value:
            flattened.extend(_as_strings(item))
        return flattened
    if isinstance(value, dict):
        flattened = []
        for key, item in value.items():
            item_values = _as_strings(item)
            if item_values:
                flattened.extend(f"{key}: {item_value}" for item_value in item_values)
        return flattened
    return []


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
