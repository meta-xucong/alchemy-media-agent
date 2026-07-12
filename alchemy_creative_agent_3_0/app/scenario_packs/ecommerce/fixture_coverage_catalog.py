"""Descriptor-only coverage plan for future owner-approved E-Commerce fixtures."""

from __future__ import annotations

from typing import Any, Literal

from ...schemas.models import V3BaseModel
from .acceptance_fixtures import EcommerceAcceptanceFixture


FIXTURE_COVERAGE_CATALOG_VERSION = "v3_ecommerce_fixture_coverage_2026_07_12"
FIRST_WAVE_CATEGORY_IDS = frozenset({"apparel", "beauty", "electronics", "home_kitchen", "food_beverage"})
REQUIRED_TEXT_LOCALES = frozenset({"en-US", "zh-CN", "ru-RU"})


class EcommerceFixtureCoverageCase(V3BaseModel):
    """A future acceptance-run requirement, never a product fixture or image asset."""

    case_id: str
    category_id: str
    platform_profile: str
    market: str
    delivery_scope: str = "listing_only"
    role_map: dict[str, str]
    text_policy: Literal["forbidden", "required", "not_applicable"] = "not_applicable"
    copy_locale: str | None = None
    required_evidence: list[str] = []
    requires_provider_failure_probe: bool = False
    metadata: dict[str, Any] = {}


def baseline_ecommerce_fixture_coverage() -> tuple[EcommerceFixtureCoverageCase, ...]:
    """Return a non-consented test-plan matrix for the first production gate."""

    return (
        EcommerceFixtureCoverageCase(
            case_id="amazon_us_apparel_primary_truth",
            category_id="apparel",
            platform_profile="amazon_us",
            market="US",
            role_map={
                "main_image": "actual product primary view and text-forbidden primary-image check",
                "detail_image": "construction and material detail backed by supplied facts",
            },
            text_policy="forbidden",
            required_evidence=["product_reference", "text_forbidden_primary", "delivery_lineage"],
        ),
        EcommerceFixtureCoverageCase(
            case_id="amazon_us_electronics_feature_en",
            category_id="electronics",
            platform_profile="amazon_us",
            market="US",
            role_map={
                "main_image": "actual product primary view",
                "feature_image_1": "one supplied feature with an approved English copy plan",
            },
            text_policy="required",
            copy_locale="en-US",
            required_evidence=["product_reference", "text_bearing_locale", "delivery_lineage"],
        ),
        EcommerceFixtureCoverageCase(
            case_id="ozon_home_kitchen_benefit_ru",
            category_id="home_kitchen",
            platform_profile="ozon",
            market="RU",
            role_map={
                "main_image": "actual product primary view",
                "benefit_image": "one supplied use or function with an approved Russian copy plan",
            },
            text_policy="required",
            copy_locale="ru-RU",
            required_evidence=["product_reference", "text_bearing_locale", "delivery_lineage"],
        ),
        EcommerceFixtureCoverageCase(
            case_id="taobao_beauty_detail_zh",
            category_id="beauty",
            platform_profile="taobao",
            market="CN",
            role_map={
                "main_image": "actual product primary view",
                "detail_image": "packaging or texture detail with an approved Chinese copy plan",
            },
            text_policy="required",
            copy_locale="zh-CN",
            required_evidence=["product_reference", "text_bearing_locale", "delivery_lineage"],
        ),
        EcommerceFixtureCoverageCase(
            case_id="shopify_food_beverage_provider_failure",
            category_id="food_beverage",
            platform_profile="shopify",
            market="global",
            role_map={
                "hero_image": "actual product primary view",
                "scenario_image": "truthful serving or use context",
            },
            required_evidence=["product_reference", "provider_failure", "delivery_lineage"],
            requires_provider_failure_probe=True,
        ),
    )


def validate_fixture_coverage(cases: tuple[EcommerceFixtureCoverageCase, ...] | list[EcommerceFixtureCoverageCase]) -> list[str]:
    """Validate a coverage plan without registering, accepting, or bundling any fixture."""

    issues: list[str] = []
    case_ids = [case.case_id for case in cases]
    if len(set(case_ids)) != len(case_ids):
        issues.append("fixture coverage case IDs must be unique")
    category_ids = {case.category_id for case in cases}
    missing_categories = sorted(FIRST_WAVE_CATEGORY_IDS - category_ids)
    if missing_categories:
        issues.append(f"fixture coverage is missing first-wave categories: {', '.join(missing_categories)}")
    text_locales = {case.copy_locale for case in cases if case.text_policy == "required" and case.copy_locale}
    missing_locales = sorted(REQUIRED_TEXT_LOCALES - text_locales)
    if missing_locales:
        issues.append(f"fixture coverage is missing required text locales: {', '.join(missing_locales)}")
    if not any("text_forbidden_primary" in case.required_evidence for case in cases):
        issues.append("fixture coverage requires a text-forbidden primary-image case")
    if not any(case.requires_provider_failure_probe for case in cases):
        issues.append("fixture coverage requires a provider-failure probe")
    for case in cases:
        if not case.role_map:
            issues.append(f"{case.case_id} requires a role map")
        if case.text_policy == "required" and not case.copy_locale:
            issues.append(f"{case.case_id} requires a copy locale")
        if case.text_policy != "required" and case.copy_locale:
            issues.append(f"{case.case_id} cannot declare a copy locale without required text")
    return issues


def owner_fixture_from_coverage(
    case: EcommerceFixtureCoverageCase,
    *,
    fixture_id: str,
    owner_consent: bool,
    source_facts: list[str],
    allowed_claims: list[str] | None = None,
) -> EcommerceAcceptanceFixture:
    """Instantiate a registry-ready fixture only after an owner supplies consent and facts."""

    return EcommerceAcceptanceFixture(
        fixture_id=fixture_id,
        owner_consent=owner_consent,
        source_facts=list(source_facts),
        role_map=dict(case.role_map),
        platform=case.platform_profile,
        market=case.market,
        placement_context=case.delivery_scope,
        allowed_claims=list(allowed_claims or []),
        metadata={
            "fixture_coverage_catalog_version": FIXTURE_COVERAGE_CATALOG_VERSION,
            "coverage_case_id": case.case_id,
            "category_id": case.category_id,
            "copy_locale": case.copy_locale,
            "text_review_required": case.text_policy == "required",
            "required_acceptance_evidence": list(case.required_evidence),
            "requires_provider_failure_probe": case.requires_provider_failure_probe,
        },
    )
