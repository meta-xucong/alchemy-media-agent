from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter


def test_disabled_remote_reasoning_still_produces_activation_governance(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    adapter = V3LLMBrainAdapter()
    request = adapter.build_request(
        user_input="Create a product hero",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={"scenario_parameters": {"capabilities": ["product_identity"]}},
    )
    result = adapter.run(request)
    assert result.skipped is True
    assert result.capability_activation_intent is not None
    assert any(
        item.capability_id == "product_identity"
        for item in result.capability_activation_intent.requested_capabilities
    )


def test_unknown_explicit_hint_stays_an_intent_not_an_executor(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    adapter = V3LLMBrainAdapter()
    request = adapter.build_request(
        user_input="Create a clean image",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={"scenario_parameters": {"capabilities": ["not_registered"]}},
    )
    result = adapter.run(request)
    assert any(
        item.capability_id == "not_registered"
        for item in result.capability_activation_intent.requested_capabilities
    )
