from pathlib import Path

from PIL import Image

from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
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
    assert [item.module_id for item in result.capability_run.results] == [
        "asset_role_analyzer",
        "asset_binding_planner",
        "prompt_constraint_compiler",
    ]
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
    assert shared["module_ids"] == ["information_integrity_lock", "prompt_constraint_compiler"]
    assert shared["result_statuses"]["information_integrity_lock"] == "warning"
    assert created.warnings


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
