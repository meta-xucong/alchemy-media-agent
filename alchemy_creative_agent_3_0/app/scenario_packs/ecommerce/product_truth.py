"""Product truth locking for E-Commerce image generation."""

from __future__ import annotations

from typing import Any

from .contracts import ProductFactRecord, ProductTruthLock
from .utils import as_list, clean_text, first_non_empty, unique_preserve_order


CATEGORY_HINTS = {
    "desk_lamp": ("lamp", "lighting", "light", "desk lamp", "table lamp"),
    "headphones": ("headphone", "earbud", "earphone", "bluetooth"),
    "skincare": ("skincare", "serum", "cream", "bottle", "cosmetic"),
    "perfume": ("perfume", "fragrance", "scent"),
    "drink": ("drink", "beverage", "tea", "coffee", "juice"),
    "home_storage": ("organizer", "storage", "rack", "shelf", "box"),
    "pet_product": ("pet", "dog", "cat"),
    "apparel": ("shirt", "shoe", "bag", "clothing", "apparel"),
}

CLAIM_RISK_TOKENS = ("certified", "fda", "medical", "cure", "patent", "100%", "guarantee", "guaranteed")
FACT_LEDGER_VERSION = "v1"
FACT_SOURCE_TYPES = {"reference_visible", "supplier_spec", "user_confirmed", "derived_blocked"}
FACT_VERIFICATIONS = {"verified", "requires_confirmation", "blocked"}


def claim_review_required(text: str, unsupported_claims: list[str] | None = None) -> bool:
    lower = text.lower()
    if any(token in lower for token in CLAIM_RISK_TOKENS):
        return True
    return any(claim.lower() in lower for claim in unsupported_claims or [] if claim)


class ProductTruthLockBuilder:
    """Build a deterministic first-pass product truth lock from supplied evidence."""

    def build(
        self,
        *,
        user_input: str,
        product_profile: dict[str, Any],
        uploaded_asset_ids: list[str],
        parameters: dict[str, Any],
    ) -> ProductTruthLock:
        category = self._category(user_input, product_profile, parameters)
        unverified_visual_facts = as_list(product_profile.get("unverified_visual_facts"))
        legacy_visible_attributes = self._visible_attributes(product_profile, uploaded_asset_ids)
        fact_ledger = self._fact_ledger(
            product_profile=product_profile,
            visible_attributes=legacy_visible_attributes,
            unverified_visual_facts=unverified_visual_facts,
        )
        fact_ledger, confirmed_fact_ids, removed_fact_ids = self._apply_fact_confirmation_states(
            fact_ledger,
            self._fact_confirmation_states(product_profile),
        )
        blocked_facts = [fact for fact in fact_ledger if fact.verification == "blocked"]
        confirmation_facts = [fact for fact in fact_ledger if fact.verification == "requires_confirmation"]
        visible_attributes = unique_preserve_order(
            [
                *legacy_visible_attributes,
                *[
                    fact.value
                    for fact in fact_ledger
                    if fact.source_type == "reference_visible" and fact.verification != "blocked"
                ],
            ]
        )[:16]
        immutable_attributes = unique_preserve_order(
            [
                *[fact.value for fact in fact_ledger if fact.verification != "blocked"],
                "product shape and proportions",
                "visible logo or label text",
                "material and finish",
                "included components and quantity",
            ]
        )
        evidence_sources = self._evidence_sources(product_profile, uploaded_asset_ids)
        claims = as_list(product_profile.get("claims"))
        unsupported_claims = [
            claim
            for claim in claims
            if self._claim_requires_evidence(claim) and not as_list(product_profile.get("evidence") or product_profile.get("evidence_sources"))
        ]
        warnings = [f"Claim needs evidence before visual use: {claim}" for claim in unsupported_claims]
        warnings.extend(
            f"Visual fact needs final-image confirmation before delivery: {fact.value}"
            for fact in confirmation_facts
        )
        warnings.extend(
            f"Product fact is blocked from prompts, copy, and export: {fact.value}"
            for fact in blocked_facts
        )
        if not uploaded_asset_ids:
            warnings.append("No product image was supplied; product truth must be reviewed manually.")

        return ProductTruthLock(
            product_category=category,
            visible_attributes=visible_attributes,
            immutable_attributes=immutable_attributes,
            fact_ledger=fact_ledger,
            allowed_scene_changes=[
                "background replacement",
                "lighting polish",
                "lifestyle environment",
                "props that do not block the product",
                "platform-safe overlay labels",
            ],
            forbidden_transformations=[
                "changing product shape",
                "changing material or color without user evidence",
                "inventing certifications, test results, patents, or awards",
                "removing or distorting visible logos and labels",
                "changing package count, included accessories, or functional claims",
            ],
            evidence_sources=evidence_sources,
            confidence={
                "uploaded_image": 0.86 if uploaded_asset_ids else 0.0,
                "user_text": 0.68 if clean_text(user_input) else 0.0,
                "product_specs": 0.78 if product_profile else 0.0,
            },
            review_obligations=[
                "Product silhouette remains recognizable in every slot.",
                "Logo, label, material, color, quantity, and visible components match supplied evidence.",
                "Unsupported claims are removed or softened before export.",
                "Overlay text does not cover key product details.",
                *(
                    ["Product-owner confirmation is required for visual facts not verified by the supplied reference image."]
                    if confirmation_facts
                    else []
                ),
            ],
            warnings=warnings,
            metadata={
                "source": "ProductTruthLockBuilder",
                "unsupported_claims": unsupported_claims,
                "unverified_visual_facts": [fact.value for fact in confirmation_facts],
                "fact_ledger_version": FACT_LEDGER_VERSION,
                "confirmation_fact_ids": [fact.fact_id for fact in confirmation_facts],
                "confirmed_fact_ids": confirmed_fact_ids,
                "removed_fact_ids": removed_fact_ids,
                "blocked_fact_ids": [fact.fact_id for fact in blocked_facts],
                "blocked_fact_values": [fact.value for fact in blocked_facts],
                "uploaded_asset_count": len(uploaded_asset_ids),
            },
        )

    def _fact_ledger(
        self,
        *,
        product_profile: dict[str, Any],
        visible_attributes: list[str],
        unverified_visual_facts: list[str],
    ) -> list[ProductFactRecord]:
        records: list[ProductFactRecord] = []
        seen_values: set[str] = set()
        used_ids: set[str] = set()
        for index, raw in enumerate(self._structured_fact_inputs(product_profile), start=1):
            record = self._fact_record(raw, index=index, used_ids=used_ids)
            if record is None:
                continue
            value_key = record.value.lower()
            if value_key in seen_values:
                continue
            records.append(record)
            seen_values.add(value_key)
        legacy_values = [
            *as_list(product_profile.get("immutable_attributes")),
            *[
                value
                for value in visible_attributes
                if "uploaded product/reference image" not in value.lower()
            ],
        ]
        for value in legacy_values:
            record = self._legacy_fact_record(
                value=value,
                source_type="user_confirmed",
                verification="verified",
                used_ids=used_ids,
            )
            if record and record.value.lower() not in seen_values:
                records.append(record)
                seen_values.add(record.value.lower())
        for value in unverified_visual_facts:
            record = self._legacy_fact_record(
                value=value,
                source_type="supplier_spec",
                verification="requires_confirmation",
                used_ids=used_ids,
                review_requirement="product_owner_confirmation",
            )
            if record and record.value.lower() not in seen_values:
                records.append(record)
                seen_values.add(record.value.lower())
        return records

    def _fact_confirmation_states(self, profile: dict[str, Any]) -> dict[str, str]:
        raw = profile.get("product_fact_confirmations") or {}
        states: dict[str, str] = {}
        if isinstance(raw, dict):
            values = raw.items()
        elif isinstance(raw, list):
            values = [
                (item.get("fact_id") or item.get("value"), item.get("status") or item.get("state"))
                for item in raw
                if isinstance(item, dict)
            ]
        else:
            values = []
        for key, value in values:
            normalized_key = clean_text(key).lower()
            normalized_state = clean_text(value).lower()
            if normalized_key and normalized_state in {"confirmed", "removed"}:
                states[normalized_key] = normalized_state
        return states

    def _apply_fact_confirmation_states(
        self,
        records: list[ProductFactRecord],
        states: dict[str, str],
    ) -> tuple[list[ProductFactRecord], list[str], list[str]]:
        active: list[ProductFactRecord] = []
        confirmed_ids: list[str] = []
        removed_ids: list[str] = []
        for fact in records:
            state = states.get(fact.fact_id.lower()) or states.get(fact.value.lower())
            if state == "removed":
                removed_ids.append(fact.fact_id)
                continue
            if state == "confirmed" and fact.verification == "requires_confirmation":
                fact = fact.model_copy(
                    update={
                        "source_type": "user_confirmed",
                        "verification": "verified",
                        "review_requirement": "none",
                    }
                )
                confirmed_ids.append(fact.fact_id)
            active.append(fact)
        return active, confirmed_ids, removed_ids

    def _structured_fact_inputs(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        raw = profile.get("fact_ledger") or profile.get("product_fact_ledger") or []
        if isinstance(raw, dict):
            raw = [raw] if any(key in raw for key in {"value", "label", "fact_id"}) else list(raw.values())
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    def _fact_record(
        self,
        raw: dict[str, Any],
        *,
        index: int,
        used_ids: set[str],
    ) -> ProductFactRecord | None:
        value = clean_text(raw.get("value") or raw.get("fact") or raw.get("label"))
        if not value:
            return None
        source_type = clean_text(raw.get("source_type")).lower() or "user_confirmed"
        if source_type not in FACT_SOURCE_TYPES:
            source_type = "user_confirmed"
        verification = clean_text(raw.get("verification")).lower() or "verified"
        if verification not in FACT_VERIFICATIONS:
            verification = "verified"
        if source_type == "derived_blocked":
            verification = "blocked"
        fact_id = self._unique_fact_id(clean_text(raw.get("fact_id")) or f"fact_{index}", used_ids)
        channels = unique_preserve_order(as_list(raw.get("visual_channels"))) or ["product"]
        allowed_slots = unique_preserve_order(as_list(raw.get("allowed_slot_ids")))
        review_requirement = clean_text(raw.get("review_requirement"))
        if not review_requirement:
            review_requirement = "block" if verification == "blocked" else (
                "product_owner_confirmation" if verification == "requires_confirmation" else "none"
            )
        return ProductFactRecord(
            fact_id=fact_id,
            label=clean_text(raw.get("label")) or value,
            value=value,
            source_type=source_type,
            verification=verification,
            visual_channels=channels,
            allowed_slot_ids=allowed_slots,
            claim_eligible=(
                bool(raw.get("claim_eligible"))
                and verification == "verified"
                and source_type in {"reference_visible", "user_confirmed"}
            ),
            review_requirement=review_requirement,
        )

    def _legacy_fact_record(
        self,
        *,
        value: str,
        source_type: str,
        verification: str,
        used_ids: set[str],
        review_requirement: str = "none",
    ) -> ProductFactRecord | None:
        normalized = clean_text(value)
        if not normalized:
            return None
        return ProductFactRecord(
            fact_id=self._unique_fact_id("legacy_fact", used_ids),
            label=normalized,
            value=normalized,
            source_type=source_type,
            verification=verification,
            visual_channels=["product"],
            review_requirement=review_requirement,
        )

    def _unique_fact_id(self, requested: str, used_ids: set[str]) -> str:
        base = "_".join(part for part in clean_text(requested).lower().replace("-", "_").split() if part) or "fact"
        candidate = base
        suffix = 2
        while candidate in used_ids:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used_ids.add(candidate)
        return candidate

    def _category(self, user_input: str, product_profile: dict[str, Any], parameters: dict[str, Any]) -> str:
        explicit = first_non_empty(
            product_profile.get("product_category"),
            product_profile.get("category"),
            parameters.get("product_category"),
            parameters.get("category"),
        )
        if explicit:
            return explicit.lower().replace(" ", "_")
        lower = f"{user_input} {product_profile}".lower()
        for category, tokens in CATEGORY_HINTS.items():
            if any(token in lower for token in tokens):
                return category
        return "generic_product"

    def _visible_attributes(self, profile: dict[str, Any], uploaded_asset_ids: list[str]) -> list[str]:
        fields = [
            "visible_attributes",
            "facts",
            "product_specs",
            "specs",
            "materials",
            "material",
            "color",
            "colors",
            "dimensions",
            "size",
            "components",
            "package",
            "quantity",
            "logo",
            "brand_or_project_name",
            "brand_name",
        ]
        values: list[str] = []
        for field in fields:
            values.extend(as_list(profile.get(field)))
        if uploaded_asset_ids:
            values.append(f"{len(uploaded_asset_ids)} uploaded product/reference image(s)")
        return unique_preserve_order(values)[:16]

    def _evidence_sources(self, profile: dict[str, Any], uploaded_asset_ids: list[str]) -> list[str]:
        sources = [f"uploaded_asset:{asset_id}" for asset_id in uploaded_asset_ids]
        if clean_text(profile.get("description")):
            sources.append("product description")
        if as_list(profile.get("product_specs") or profile.get("specs")):
            sources.append("product specs")
        if as_list(profile.get("claims")):
            sources.append("supplied claims")
        if as_list(profile.get("evidence") or profile.get("evidence_sources")):
            sources.append("claim evidence")
        return sources or ["user prompt"]

    def _claim_requires_evidence(self, claim: str) -> bool:
        return claim_review_required(claim)
