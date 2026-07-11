from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
    active_review_contract,
)


def _product_result(monkeypatch):
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    return ScenarioRuntime().plan_job({"user_input": "Create a premium product hero for a desk lamp", "scenario_selection": {"scenario_id": "general_creative"}, "uploaded_assets": [{"asset_id": "product", "role": "product_reference"}], "metadata": {"requested_image_count": 1}}).planning_result


def test_product_job_ignores_human_review_issue(monkeypatch) -> None:
    result = _product_result(monkeypatch)
    service = V3ProductApiService()
    codes, patch, _ = service._activation_filtered_retry_signal(result, ["ai_face_render"], {"prompt_additions": ["face"]}, "test")
    assert codes == []
    assert patch == {}
    assert result.metadata["capability_activation_audit"]["ignored_out_of_scope_issue_codes"] == ["ai_face_render"]


def test_product_job_keeps_product_review_issue(monkeypatch) -> None:
    result = _product_result(monkeypatch)
    codes, _, _ = V3ProductApiService()._activation_filtered_retry_signal(result, ["product_identity_drift"], {}, "test")
    assert codes == ["product_identity_drift"]


def test_enforced_vision_prompt_uses_active_review_vocabulary(monkeypatch) -> None:
    result = _product_result(monkeypatch)
    metadata = dict(result.metadata)
    contract = active_review_contract(metadata)
    prompt = _inspection_prompt(metadata)
    assert contract["enforced"] is True
    assert "product_identity_drift" in prompt
    assert "ai_face_render" not in prompt
    assert "identity_consistency" not in prompt


def test_reference_policy_registers_prompt_ownership_review_and_retry_codes(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    result = ScenarioRuntime().plan_job(
        {
            "user_input": "Create a real portrait of the same woman with black hair in a new cool studio scene",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_assets": [{"asset_id": "face", "role": "face_reference"}],
            "metadata": {
                "requested_image_count": 1,
                "project_context_snapshot": {
                    "project_id": "project_reference_review",
                    "template_id": "general_template",
                    "selected_reference_assets": [
                        {
                            "asset_ref_id": "face",
                            "asset_id": "face",
                            "source_type": "uploaded",
                            "role": "face_reference",
                            "use_policy": "identity",
                        }
                    ],
                },
            },
        }
    ).planning_result

    contract = active_review_contract(dict(result.metadata))
    prompt = _inspection_prompt(dict(result.metadata))

    assert contract["enforced"] is True
    assert "reference_channel_policy" in contract["review_capability_sources"]
    assert "source_hair_overinherited" in contract["issue_codes"]
    assert "prompt_owned_channel_ignored" in contract["issue_codes"]
    assert "source_hair_overinherited" in prompt
