import json
from types import SimpleNamespace
from pathlib import Path

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
from alchemy_creative_agent_3_0.app.schemas import ProviderStrategy
from alchemy_creative_agent_3_0.app.shared_capabilities import UploadedAssetInfo
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import CapabilityActivationError
from alchemy_creative_agent_3_0.app.shared_capabilities.base import SharedCapabilityModule
from alchemy_creative_agent_3_0.app.shared_capabilities.contracts import CapabilityInput


def _image(path: Path) -> Path:
    Image.new("RGB", (320, 320), (200, 40, 40)).save(path)
    return path


def test_shared_capability_exception_keeps_only_a_sanitized_failure_frame() -> None:
    class RaisingVisualCluster(SharedCapabilityModule):
        module_id = "visual_capability_cluster"

        def execute(self, capability_input: CapabilityInput):
            raise TypeError("private prompt text must not enter the diagnostic receipt")

    result = RaisingVisualCluster().run(
        CapabilityInput(job_id="job_test", scenario_id="general_creative", user_input="private prompt")
    )

    assert result.status.value == "error"
    assert result.metadata["exception_type"] == "TypeError"
    assert result.metadata["exception_frame"]["source"] == Path(__file__).name
    assert result.metadata["exception_frame"]["function"] == "execute"
    assert result.metadata["exception_frame"]["line"] > 0
    assert "private prompt" not in json.dumps(result.metadata)


def test_scenario_runtime_runs_optional_asset_capabilities_for_general_creative(tmp_path) -> None:
    runtime = ScenarioRuntime()
    product_image = _image(tmp_path / "product.png")

    result = runtime.plan_job(
        {
            "user_input": "Create a clean product-style campaign image.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_assets": [
                {
                    "asset_id": "asset_product",
                    "file_path": str(product_image),
                    "filename": "product.png",
                }
            ],
        }
    )

    assert result.status == ScenarioRuntimeStatus.PLANNED
    assert result.capability_run is not None
    assert result.capability_run.status.value == "complete"
    module_ids = [item.module_id for item in result.capability_run.results]
    assert {
        "asset_role_analyzer",
        "asset_binding_planner",
        "prompt_constraint_compiler",
        "visual_capability_cluster",
    }.issubset(module_ids)
    assert module_ids.index("asset_role_analyzer") < module_ids.index("asset_binding_planner")
    assert module_ids.index("asset_binding_planner") < module_ids.index("prompt_constraint_compiler")
    assert not any("ecommerce" in module_id or "kidswear" in module_id for module_id in module_ids)
    assert result.planning_result is not None
    shared = result.planning_result.metadata["shared_capabilities"]
    assert shared["enabled"] is True
    assert "asset_role_analyzer" in shared["module_ids"]
    assert result.planning_result.creative_job.uploaded_asset_ids == ["asset_product"]


def test_product_api_runs_information_integrity_for_product_profile(tmp_path) -> None:
    service = V3ProductApiService()

    created = service.create_job(
        {
            "user_input": "Create a clean campaign image.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "product_profile": {
                "required_text": ["Summer Launch"],
                "claims": ["100% guaranteed result"],
            },
        }
    )

    assert created.status == ProductJobStatusValue.PLANNED
    shared = created.metadata["shared_capabilities"]
    assert shared["enabled"] is True
    module_ids = shared["module_ids"]
    assert {"information_integrity_lock", "prompt_constraint_compiler", "visual_capability_cluster"}.issubset(module_ids)
    assert module_ids.index("information_integrity_lock") < module_ids.index("prompt_constraint_compiler")
    assert not any("ecommerce" in module_id or "kidswear" in module_id for module_id in module_ids)
    assert shared["result_statuses"]["information_integrity_lock"] == "warning"
    assert shared["visual_cluster"]["cluster_id"]
    assert created.warnings


def test_general_visual_cluster_sanitizes_commercial_case_terms() -> None:
    runtime = ScenarioRuntime()

    result = runtime.plan_job(
        {
            "user_input": "Create a fresh summer portrait cover with clean bright light.",
            "scenario_selection": {"scenario_id": "general_creative", "parameters": {"use_case_library": True}},
            "metadata": {"template_id": "general_template"},
        }
    )

    assert result.status == ScenarioRuntimeStatus.PLANNED
    assert result.planning_result is not None
    shared = result.planning_result.metadata["shared_capabilities"]
    cluster_text = json.dumps(shared["visual_cluster"], ensure_ascii=False).lower()
    assert shared["visual_cluster"]["cluster_id"]
    assert "commercial" not in cluster_text
    assert "product" not in cluster_text
    assert "clean optional blank space" in cluster_text or "cover-safe clean space" in cluster_text


def test_runtime_generation_passes_visual_cluster_to_generation_metadata() -> None:
    runtime = ScenarioRuntime()

    result = runtime.generate_job(
        {
            "user_input": "Create a fresh summer portrait cover with clean bright light.",
            "scenario_selection": {"scenario_id": "general_creative", "parameters": {"use_case_library": True}},
            "metadata": {"template_id": "general_template"},
        },
        provider_strategy=ProviderStrategy.MOCK_GENERATION,
    )

    assert result.status == ScenarioRuntimeStatus.GENERATED
    assert result.generation_result is not None
    shared = result.generation_result.metadata["shared_capabilities"]
    plan_metadata = result.generation_result.generation_plans[0].metadata
    assert shared["visual_cluster"]["cluster_id"]
    assert plan_metadata["shared_capabilities"]["visual_cluster"]["cluster_id"] == shared["visual_cluster"]["cluster_id"]
    assert plan_metadata["visual_cluster"]["cluster_id"] == shared["visual_cluster"]["cluster_id"]


def test_placeholder_scenario_does_not_run_shared_capabilities(tmp_path) -> None:
    runtime = ScenarioRuntime()
    product_image = _image(tmp_path / "product.png")

    result = runtime.plan_job(
        {
            "user_input": "Create a future new-media material set.",
            "scenario_selection": {
                "scenario_id": "new_media",
                "parameters": {"capabilities": ["asset_role_analyzer"]},
            },
            "uploaded_assets": [UploadedAssetInfo(asset_id="asset_product", file_path=str(product_image))],
        }
    )

    assert result.status == ScenarioRuntimeStatus.BLOCKED
    assert result.capability_run is None
    assert result.scenario_resolution.can_create_jobs is False


def test_required_shared_capability_failure_blocks_runtime() -> None:
    runtime = ScenarioRuntime()

    result = runtime.plan_job(
        {
            "user_input": "Create a campaign image.",
            "scenario_selection": {
                "scenario_id": "general_creative",
                "parameters": {
                    "capabilities": ["missing_capability"],
                    "required_capabilities": ["missing_capability"],
                },
            },
        }
    )

    assert result.status == ScenarioRuntimeStatus.BLOCKED
    assert result.capability_run is not None
    assert result.capability_run.status.value == "failed"
    assert result.capability_run.required_failures == ["missing_capability"]
    assert result.planning_result is None


def test_activation_block_receipt_preserves_safe_private_diagnostics() -> None:
    runtime = ScenarioRuntime()
    request = runtime._coerce_request(
        {
            "user_input": "private user prompt that must not be persisted in diagnostics",
            "scenario_selection": {"scenario_id": "general_creative"},
        }
    )
    resolution = runtime.scenario_registry.resolve(request.scenario_selection)
    profile = SimpleNamespace(
        profile_id="profile_123",
        template_id="general_template",
        scenario_id="general_creative",
        output_medium="image",
        rendering_intent=SimpleNamespace(
            rendering_mode="photoreal",
            stylization_scope="none",
            decision_owner="remote_brain",
        ),
        developmental_age_intent="not_applicable",
        subject_entities=[
            SimpleNamespace(entity_type="person"),
            SimpleNamespace(entity_type="person"),
            SimpleNamespace(entity_type="leak_this_prompt"),
        ],
        unknown_requirements=["do not persist this private user wording"],
    )
    plan = SimpleNamespace(
        plan_id="plan_123",
        fingerprint="a1b2c3",
        activation_mode="enforced",
        dependency_order=["human_realism", "universal_visual_quality"],
        base_capabilities=[SimpleNamespace(capability_id="human_realism", activation_mode="required", reason_codes=["visible_person"])],
        active_capabilities=[SimpleNamespace(capability_id="human_realism", activation_mode="required", reason_codes=["visible_person"])],
        inactive_capabilities=[SimpleNamespace(capability_id="portrait_identity", reason_code="not_applicable_no_visible_human")],
    )
    warning = SimpleNamespace(
        code="capability_execution_failed",
        severity="error",
        message="unsafe raw provider or user detail must be omitted",
        metadata={"exception_type": "ValueError"},
    )
    unknown_warning = SimpleNamespace(
        code="leak_this_prompt_without_spaces",
        severity="warning",
        message="untrusted executor detail",
        metadata={},
    )
    cluster_result = SimpleNamespace(
        module_id="visual_capability_cluster",
        status=SimpleNamespace(value="warning"),
        metadata={
            "exception_type": "TypeError",
            "exception_frame": {
                "source": r"C:\private\visual_cluster.py",
                "line": 321,
                "function": "execute",
            },
        },
        warnings=[warning, unknown_warning],
        facts={
            "visual_capability_cluster": {
                "human_photorealism_guidance": {
                    "applies": False,
                    "metadata": {
                        "disabled_reason": "frozen_rendering_intent_conflict",
                        "human_realism_plugin": {
                            "primary_reason": "frozen_rendering_intent_conflict",
                            "disabled_reason": "frozen_rendering_intent_conflict",
                        },
                    },
                }
            }
        },
    )
    active_run = SimpleNamespace(
        status=SimpleNamespace(value="failed"),
        results=[cluster_result],
        warnings=[warning, unknown_warning],
        required_failures=["human_realism"],
    )

    diagnostics = runtime._activation_failure_diagnostics(
        plan,
        active_run,
        SimpleNamespace(visual_task_profile=profile),
        failure_code="human_realism_execution_mismatch",
    )
    exc = CapabilityActivationError("human_realism_execution_mismatch")
    exc.activation_failure_diagnostics = diagnostics
    blocked = runtime._activation_blocked_result(request, resolution, exc)

    persisted = blocked.capability_run.metadata["activation_failure_diagnostics"]
    serialized = json.dumps(persisted)
    assert persisted["profile_summary"]["rendering_intent"]["rendering_mode"] == "photoreal"
    assert persisted["profile_summary"]["subject_entity_counts"] == {"person": 2, "other": 1}
    assert persisted["planned_capabilities"]["dependency_order"] == ["human_realism", "universal_visual_quality"]
    assert persisted["human_realism_execution"] == {
        "status": "not_applied",
        "applies": False,
        "primary_reason": "frozen_rendering_intent_conflict",
        "disabled_reason": "frozen_rendering_intent_conflict",
    }
    assert persisted["executor"]["warnings"][0]["code"] == "capability_execution_failed"
    assert persisted["executor"]["warnings"][1]["code"] == "other"
    visual_result = next(item for item in persisted["executor"]["results"] if item["module_id"] == "visual_capability_cluster")
    assert visual_result["exception_type"] == "TypeError"
    assert visual_result["exception_frame"] == {
        "source": "visual_cluster.py",
        "line": 321,
        "function": "execute",
    }
    assert "C:\\private\\visual_cluster.py" not in serialized
    assert "leak_this_prompt" not in serialized
    assert "unsafe raw provider" not in serialized
    assert "private user prompt" not in serialized
    assert "do not persist this private" not in serialized
    assert "activation_failure_diagnostics" not in blocked.metadata
    persisted_record = json.dumps(blocked.capability_run.model_dump(mode="json"))
    assert "activation_failure_diagnostics" in persisted_record
    public_summary = V3ProductApiService()._capability_run_summary(blocked.capability_run)
    assert "activation_failure_diagnostics" not in public_summary
    public_lifecycle = V3ProductApiService._generation_lifecycle_failure_from_runtime_result(blocked)
    assert public_lifecycle["failure_code"] == "capability_activation_blocked"
    assert "activation_failure_diagnostics" not in public_lifecycle

    # Missing executor reason is explicit in the receipt rather than silently
    # producing an unexplained `not_applied` state.
    cluster_result.facts["visual_capability_cluster"]["human_photorealism_guidance"]["metadata"] = {}
    fallback = runtime._activation_failure_diagnostics(
        plan,
        active_run,
        SimpleNamespace(visual_task_profile=profile),
        failure_code="human_realism_execution_mismatch",
    )
    assert fallback["human_realism_execution"]["disabled_reason"] == "reason_unavailable"


def test_frozen_capability_guard_ignores_inactive_and_blocks_missing_active_hr() -> None:
    runtime = ScenarioRuntime()
    runtime._validate_frozen_capability_execution(  # noqa: SLF001
        SimpleNamespace(dependency_order=[]),
        SimpleNamespace(results=[]),
    )

    blocked_run = SimpleNamespace(
        results=[
            SimpleNamespace(
                module_id="visual_capability_cluster",
                facts={
                    "visual_capability_cluster": {
                        "human_photorealism_guidance": {"applies": False}
                    }
                },
            )
        ]
    )
    with pytest.raises(CapabilityActivationError, match="human_realism_execution_mismatch"):
        runtime._validate_frozen_capability_execution(  # noqa: SLF001
            SimpleNamespace(dependency_order=["human_realism"]),
            blocked_run,
        )
