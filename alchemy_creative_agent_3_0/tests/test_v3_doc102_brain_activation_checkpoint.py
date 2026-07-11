from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import ecommerce_capability_policy


def test_fallback_brain_always_emits_task_profile_and_intent(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    adapter = V3LLMBrainAdapter()
    request = adapter.build_request(
        user_input="Create a real woman portrait from the supplied face reference",
        stage="generate",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={"requested_image_count": 1},
        uploaded_assets=[{"asset_id": "face", "role": "face_reference"}],
    )
    result = adapter.run(request)
    assert result.visual_task_profile is not None
    assert result.capability_activation_intent is not None
    assert any(item.capability_id == "portrait_identity" for item in result.capability_activation_intent.requested_capabilities)
    assert any(item.checkpoint_id == "task_profile_and_capability_activation" for item in result.checkpoints)


def test_ecommerce_brain_runs_only_with_trusted_policy(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    adapter = V3LLMBrainAdapter()
    request = adapter.build_request(
        user_input="Create a product listing hero",
        stage="plan",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        metadata={},
        template_capability_policy=ecommerce_capability_policy(),
    )
    result = adapter.run(request)
    assert result.capability_activation_intent is not None
    assert any(item.capability_id == "product_identity" for item in result.capability_activation_intent.requested_capabilities)


def test_generic_photography_word_does_not_prove_visible_human(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    adapter = V3LLMBrainAdapter()
    request = adapter.build_request(
        user_input="Atmospheric landscape photography",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={"requested_image_count": 1},
    )
    result = adapter.run(request)
    ids = {item.capability_id for item in result.capability_activation_intent.requested_capabilities}
    assert "human_realism" not in ids
    assert "portrait_identity" not in ids
