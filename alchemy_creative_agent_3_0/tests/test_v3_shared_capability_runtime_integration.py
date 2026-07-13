import json
from pathlib import Path

from PIL import Image

from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
from alchemy_creative_agent_3_0.app.schemas import ProviderStrategy
from alchemy_creative_agent_3_0.app.shared_capabilities import UploadedAssetInfo


def _image(path: Path) -> Path:
    Image.new("RGB", (320, 320), (200, 40, 40)).save(path)
    return path


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
