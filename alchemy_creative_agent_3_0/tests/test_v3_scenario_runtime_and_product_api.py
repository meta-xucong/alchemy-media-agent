import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.product_api import CreateCreativeJobRequest, ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_packs import ScenarioSelection
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeRequest, ScenarioRuntimeStatus
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _brand_service(tmp_path) -> BrandProfileService:
    return BrandProfileService(BrandProfileStore(tmp_path / "brand_memory"))


def test_scenario_runtime_runs_general_creative_and_enriches_metadata(tmp_path) -> None:
    runtime = ScenarioRuntime(brand_profile_service=_brand_service(tmp_path))

    result = runtime.plan_job(
        {
            "user_input": "Create a fresh summer campaign poster for a tea shop.",
            "scenario_selection": {"scenario_id": "general_creative", "mode_id": "campaign_poster"},
            "uploaded_asset_ids": ["upload_product_1"],
            "product_profile": {"category": "beverage"},
        }
    )

    assert result.status == ScenarioRuntimeStatus.PLANNED
    assert result.planning_result is not None
    assert result.scenario_resolution.manifest.scenario_id == "general_creative"
    assert result.planning_result.metadata["scenario_id"] == "general_creative"
    assert result.planning_result.metadata["selected_mode_id"] == "campaign_poster"
    assert result.planning_result.creative_job.uploaded_asset_ids == ["upload_product_1"]
    assert result.planning_result.creative_job.metadata["product_profile"] == {"category": "beverage"}


def test_scenario_runtime_runs_ecommerce_and_enriches_metadata(tmp_path) -> None:
    runtime = ScenarioRuntime(
        brand_profile_service=_brand_service(tmp_path),
        llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider()),
    )

    result = runtime.plan_job(
        {
            "user_input": "Create an ecommerce listing set for a desk lamp.",
            "scenario_selection": {"scenario_id": "ecommerce", "platform_profile": "amazon_us"},
            "uploaded_asset_ids": ["product_lamp"],
            "product_profile": {"product_category": "desk lamp", "selling_points": ["Adjustable angle"]},
        }
    )

    assert result.status == ScenarioRuntimeStatus.PLANNED
    assert result.planning_result is not None
    assert result.scenario_resolution.manifest.scenario_id == "ecommerce"
    assert result.scenario_resolution.can_create_jobs is True
    assert result.planning_result.metadata["scenario_id"] == "ecommerce"
    assert "output_review" in result.planning_result.metadata["shared_capabilities"]["module_ids"]


def test_product_api_accepts_general_scenario_selection_and_keeps_simple_response(tmp_path) -> None:
    service = V3ProductApiService(brand_profile_service=_brand_service(tmp_path))

    created = service.create_job(
        {
            "user_input": "Create a clean social campaign cover for a tea shop.",
            "scenario_selection": {
                "scenario_id": "general_creative",
                "mode_id": "social_cover",
                "preset_id": "social_cover",
            },
            "uploaded_asset_ids": ["upload_style_1"],
            "product_profile": {"category": "beverage"},
        }
    )

    assert created.status == ProductJobStatusValue.PLANNED
    assert created.scenario is not None
    assert created.scenario.scenario_id == "general_creative"
    assert created.scenario.can_create_jobs is True
    assert created.scenario.selected_mode_id == "social_cover"
    assert created.asset_series
    assert created.metadata["scenario_id"] == "general_creative"


def test_product_api_runs_ecommerce_scenario_and_keeps_job_retrievable(tmp_path) -> None:
    service = V3ProductApiService(
        brand_profile_service=_brand_service(tmp_path),
        scenario_runtime=ScenarioRuntime(
            brand_profile_service=_brand_service(tmp_path),
            llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider()),
        ),
    )

    created = service.create_job(
        {
            "user_input": "Create a marketplace-ready product listing image set.",
            "scenario_selection": {"scenario_id": "ecommerce", "platform_profile": "amazon_us"},
            "uploaded_asset_ids": ["product_reference"],
            "product_profile": {"product_category": "desk lamp", "selling_points": ["Metal body"]},
        }
    )
    fetched = service.get_job(created.job_id)
    generated = service.generate_job(created.job_id)
    selected = service.select_result(created.job_id)

    assert created.status == ProductJobStatusValue.PLANNED
    assert fetched.status == ProductJobStatusValue.PLANNED
    assert generated.status == ProductJobStatusValue.GENERATED
    assert selected.status == ProductJobStatusValue.SELECTED
    assert created.scenario is not None
    assert created.scenario.scenario_id == "ecommerce"
    assert created.scenario.can_create_jobs is True
    assert created.asset_series
    assert created.ecommerce is not None
    assert created.ecommerce.platform == "amazon"
    assert generated.ecommerce is not None
    assert selected.job_status.ecommerce is not None


def test_scenario_selection_does_not_expose_low_level_generation_controls() -> None:
    with pytest.raises(ValidationError):
        CreateCreativeJobRequest.model_validate(
            {
                "user_input": "Create a campaign image.",
                "scenario_selection": {
                    "scenario_id": "general_creative",
                    "parameters": {"seed": 123},
                },
            }
        )
    with pytest.raises(ValidationError):
        CreateCreativeJobRequest.model_validate(
            {
                "user_input": "Create a campaign image.",
                "product_profile": {"controlnet": "hidden"},
            }
        )
    with pytest.raises(ValidationError):
        CreateCreativeJobRequest.model_validate(
            {
                "user_input": "Create a campaign image.",
                "uploaded_asset_ids": ["valid_asset", ""],
            }
        )
    with pytest.raises(ValidationError):
        CreateCreativeJobRequest(
            user_input="Create a campaign image.",
            scenario_selection=ScenarioSelection(
                scenario_id="general_creative",
                parameters={"node_graph": {"hidden": True}},
            ),
        )
    with pytest.raises(ValidationError):
        ScenarioSelection.model_validate({"scenario_id": "general_creative", "parameters": {"seed": 123}})
    with pytest.raises(ValidationError):
        ScenarioRuntimeRequest.model_validate(
            {
                "user_input": "Create a campaign image.",
                "product_profile": {"ip_adapter_scale": 0.7},
            }
        )
