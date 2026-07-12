import pytest

from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.acceptance_fixtures import (
    EcommerceAcceptanceFixture,
    EcommerceFixtureAcceptanceRecord,
    EcommerceFixtureRegistry,
)


def _fixture() -> EcommerceAcceptanceFixture:
    return EcommerceAcceptanceFixture(
        fixture_id="owner_shirt_fixture",
        owner_consent=True,
        source_facts=["blue striped shirt", "cotton poplin"],
        role_map={"main_image": "primary silhouette", "detail_image": "material detail"},
        platform="amazon",
        market="US",
    )


def test_fixture_registry_refuses_unconsented_or_underspecified_fixtures() -> None:
    registry = EcommerceFixtureRegistry()
    with pytest.raises(ValueError, match="owner consent"):
        registry.register(_fixture().model_copy(update={"owner_consent": False}))
    with pytest.raises(ValueError, match="source facts"):
        registry.register(_fixture().model_copy(update={"source_facts": []}))


def test_metadata_or_similarity_cannot_mark_a_fixture_as_real_output_passed() -> None:
    registry = EcommerceFixtureRegistry()
    registry.register(_fixture())
    issues = registry.validate_acceptance(EcommerceFixtureAcceptanceRecord(fixture_id="owner_shirt_fixture", passed=True))

    assert "planner metadata alone cannot pass real-output acceptance" in issues
    assert "real Provider/Review Gate C evidence is required" in issues
    assert "record cannot be marked passed while acceptance evidence is incomplete" in issues


def test_real_output_acceptance_contract_requires_all_evidence_dimensions() -> None:
    registry = EcommerceFixtureRegistry()
    registry.register(_fixture())
    record = EcommerceFixtureAcceptanceRecord(
        fixture_id="owner_shirt_fixture",
        provider_run_id="provider_run_123",
        gate_c_status="passed",
        terminal_seconds=120,
        planner_metadata_only=False,
        human_scores={"product_fidelity": 4.5, "role_differentiation": 4.0, "realism": 4.0, "delivery_closure": 4.5},
        retry_superseded_closed=True,
        text_review_required=True,
        text_review_passed=True,
        passed=True,
    )

    assert registry.validate_acceptance(record) == []
