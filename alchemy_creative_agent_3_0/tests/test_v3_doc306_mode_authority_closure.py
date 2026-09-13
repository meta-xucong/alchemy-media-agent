from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import CapabilityActivationError
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import (
    GeneralVariationModeBinding,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.mode_role_director import (
    ModeAwareRoleDirector,
)
from alchemy_creative_agent_3_0.app.variation_modes import build_general_variation_mode_binding


def _bound_general_metadata(mode: str = "creative_exploration", count: int = 2) -> dict:
    director = ModeAwareRoleDirector()
    role_plan = director.build(
        project_id="project_doc306",
        job_id="job_doc306",
        user_input="Create a visual set.",
        mode=mode,
        requested_image_count=count,
        subject_type="generic",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=False,
    )
    contract = director.build_variation_execution_contract(
        role_plan=role_plan,
        scenario_id="general_creative",
        template_id="general_template",
    )
    assert contract is not None
    resolution = {
        "variation_mode": "auto",
        "effective_variation_mode": mode,
        "variation_mode_source": "auto",
    }
    return {
        "variation_execution_contract_enforced": True,
        "variation_execution_contract": contract.model_dump(mode="json"),
        "variation_execution_role_plan": role_plan.model_dump(mode="json"),
        "variation_mode_binding": build_general_variation_mode_binding(
            resolution,
            contract_version=contract.contract_version,
            contract_digest=contract.contract_digest,
        ),
        "variation_execution_mode": mode,
        "variation_execution_requested_image_count": count,
        "variation_execution_suite_direction_authoritative": True,
        "variation_execution_contract_binding": {
            "contract_version": contract.contract_version,
            "contract_digest": contract.contract_digest,
        },
    }


def test_enforced_general_role_plan_requires_every_ordered_recipe() -> None:
    metadata = _bound_general_metadata()
    metadata.pop("variation_execution_role_plan")

    with pytest.raises(CapabilityActivationError, match="general_variation_role_plan_missing"):
        ScenarioRuntime._validated_general_role_recipes(metadata, expected_count=2)  # noqa: SLF001


def test_enforced_general_role_plan_rejects_index_or_count_drift() -> None:
    metadata = _bound_general_metadata()
    metadata["variation_execution_role_plan"]["role_recipes"][1]["index"] = 1

    with pytest.raises(CapabilityActivationError, match="general_variation_role_plan_binding_mismatch"):
        ScenarioRuntime._validated_general_role_recipes(metadata, expected_count=2)  # noqa: SLF001


def test_mode_binding_is_carried_into_the_enforced_ledger_projection() -> None:
    metadata = _bound_general_metadata()
    raw_cluster = {
        "variation_execution_contract": metadata["variation_execution_contract"],
        "variation_mode_binding": metadata["variation_mode_binding"],
    }
    plan = SimpleNamespace(dependency_order=["suite_direction"])

    projection = ScenarioRuntime._ledger_capability_projection(raw_cluster, plan)  # noqa: SLF001

    assert projection["variation_mode_binding"] == metadata["variation_mode_binding"]


def test_ledger_mode_binding_missing_is_not_silently_dropped() -> None:
    metadata = _bound_general_metadata()
    raw_cluster = {"variation_execution_contract": metadata["variation_execution_contract"]}
    plan = SimpleNamespace(dependency_order=["suite_direction"])

    with pytest.raises(CapabilityActivationError, match="general_variation_mode_binding_missing"):
        ScenarioRuntime._ledger_capability_projection(raw_cluster, plan)  # noqa: SLF001


def test_trusted_continuation_preserves_and_validates_mode_binding_and_roles() -> None:
    source = _bound_general_metadata()
    child = {
        "variation_mode": "selection_candidates",
        "variation_mode_binding": {"effective_mode": "selection_candidates"},
    }

    restored = V3ProductApiService._trusted_variation_execution_metadata(child, source)  # noqa: SLF001

    assert restored["variation_mode_binding"] == source["variation_mode_binding"]
    assert restored["variation_execution_role_plan"] == source["variation_execution_role_plan"]
    parsed = GeneralVariationModeBinding.model_validate(restored["variation_mode_binding"])
    assert parsed.effective_mode == "creative_exploration"
