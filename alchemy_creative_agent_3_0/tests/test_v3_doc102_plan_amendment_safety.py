import os

from alchemy_creative_agent_3_0.app.shared_capabilities.activation import CapabilityPlanAmendment


def test_plan_amendment_feature_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("V3_CAPABILITY_PLAN_AMENDMENT_ENABLED", raising=False)
    assert os.getenv("V3_CAPABILITY_PLAN_AMENDMENT_ENABLED", "false").lower() == "false"


def test_one_audited_amendment_contract_is_valid() -> None:
    amendment = CapabilityPlanAmendment(
        amendment_id="amendment",
        original_plan_id="plan_1",
        amended_plan_id="plan_2",
        evidence_ids=["new_visible_entity"],
        reason_code="post_generation_new_entity",
    )
    assert amendment.amendment_index == 1
