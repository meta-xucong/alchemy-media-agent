from __future__ import annotations

from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_inspector import (
    _issue_message,
    _vision_provider_timeout_seconds,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
    active_review_contract,
)


def test_enforced_review_prompt_is_compact_without_dropping_frozen_contract(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    result = ScenarioRuntime().plan_job(
        {
            "user_input": "Create a premium product hero for a desk lamp with a new tabletop angle.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_assets": [{"asset_id": "product", "role": "product_reference"}],
            "metadata": {
                "requested_image_count": 1,
                "project_context_snapshot": {
                    "project_id": "project_vision_prompt_budget",
                    "template_id": "general_template",
                    "uploaded_reference_assets": [
                        {
                            "asset_ref_id": "product",
                            "asset_id": "product",
                            "source_type": "uploaded",
                            "role": "product_reference",
                            "use_policy": "product",
                        }
                    ],
                },
            },
        }
    ).planning_result

    metadata = dict(result.metadata)
    contract = active_review_contract(metadata)
    prompt = _inspection_prompt(metadata)

    assert contract["enforced"] is True
    assert len(prompt) < 6000
    assert "product_identity_drift" in prompt
    assert "source_camera_overinherited" in prompt
    assert "human_authenticity_contract" in prompt
    assert "Return keys:" in prompt


def test_vision_review_default_deadline_is_longer_than_legacy_provider_cap(monkeypatch) -> None:
    monkeypatch.delenv("V3_VISION_INSPECTION_TIMEOUT_SECONDS", raising=False)

    assert _vision_provider_timeout_seconds({}) == 120.0


def test_review_transport_failure_is_not_worded_as_a_quality_failure() -> None:
    assert "quality was not judged" in _issue_message("provider_timeout")
    assert "quality was not judged" in _issue_message("provider_error")
