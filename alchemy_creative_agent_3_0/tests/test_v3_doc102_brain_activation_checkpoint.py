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


def test_remote_brain_keeps_safe_activation_contract_when_structured_sections_are_malformed(monkeypatch) -> None:
    class MalformedStructuredProvider:
        provider = "openai"
        model = "remote-structured-test"

        def available(self, *, force: bool = False) -> bool:
            return True

        def run(self, request):  # noqa: ANN001
            return {
                "prompt_guidance": {
                    "optimized_direction": "remote refined ancient portrait direction",
                },
                "visual_task_profile": {
                    "preservation_targets": ["same-person facial geometry"],
                    "evidence": ["E_USER_PROMPT", "E_UPLOADED_REFERENCE"],
                },
                "capability_activation_intent": {
                    "rejected_capabilities": [
                        {
                            "capability_id": "product_identity",
                            "evidence_ids": ["E_USER_PROMPT"],
                        }
                    ]
                },
            }

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    adapter = V3LLMBrainAdapter(provider=MalformedStructuredProvider())
    request = adapter.build_request(
        user_input="Create a realistic woman portrait from the supplied face reference",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={"requested_image_count": 1, "require_real_images": True},
        uploaded_assets=[{"asset_id": "face", "role": "face_reference"}],
    )

    result = adapter.run(request)

    assert result.llm_used is True
    assert result.prompt_guidance.optimized_direction == "remote refined ancient portrait direction"
    assert result.visual_task_profile.preservation_targets
    assert all(target.target_id for target in result.visual_task_profile.preservation_targets)
    requested = {item.capability_id for item in result.capability_activation_intent.requested_capabilities}
    assert {"human_realism", "portrait_identity"} <= requested
    assert result.audit["remote_contract_partial_fallback"] is True
    assert result.audit["remote_contract_rejected_sections"] == [
        "visual_task_profile",
        "capability_activation_intent",
    ]


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
