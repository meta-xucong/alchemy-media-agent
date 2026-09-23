"""Only the current accepted Brain decision authorizes optional QR editing."""
import inspect
import pytest
from app.schemas import CreativeOrchestratorDecision
from app.repositories.memory import utc_now
from app.services import claude_orchestrator as brain, generation
from app.services.prompting import compose_prompt_plan


def decision(**overrides):
    data = dict(decision_id="decision_test", provider="claude-code", mode="smart_enhance",
        case_retrieval_plan={"query_text": "product"}, final_prompt="A clean product photograph.", created_at=utc_now())
    data.update(overrides)
    return CreativeOrchestratorDecision.model_validate(data)


@pytest.mark.parametrize("value", [None, "false", "true", 0, 1, [], {}, False, True])
def test_optional_decision_boolean_is_strict_and_roundtrips(value):
    result = decision(qr_preservation_enabled=value)
    assert result.qr_preservation_enabled is (value is True)
    assert CreativeOrchestratorDecision.model_validate_json(result.model_dump_json()).qr_preservation_enabled is (value is True)


def test_missing_optional_field_is_false():
    assert decision().qr_preservation_enabled is False


@pytest.mark.parametrize("value", [True, False, "true", 1, None])
def test_final_checkpoint_never_inherits_an_earlier_true(value):
    raw = {"mode": "smart_enhance", "final_prompt": "A clean product photograph.", "qr_preservation_enabled": value}
    compressed = brain._compress_checkpoint_decision(raw, intent={"qr_preservation_enabled": True},
        visual_strategy={"qr_preservation_enabled": True}, fallback=decision())
    assert compressed["qr_preservation_enabled"] is (value is True)
    normalized = brain._normalize_decision(compressed, fallback=decision(),
        fallback_retrieval_plan=decision().case_retrieval_plan, candidate_cases=[])
    assert normalized.qr_preservation_enabled is (value is True)


@pytest.mark.parametrize("valid,expected", [(True, True), (False, False)])
def test_only_accepted_brain_decision_reaches_prompt_plan(valid, expected):
    model = decision(qr_preservation_enabled=True, fallback_reason=None if valid else "unavailable")
    plan = compose_prompt_plan(mode="smart_enhance", user_prompt="Keep the existing QR at bottom right.",
        cases=[], output={}, orchestrator_decision=model)
    assert plan.user_variables["qr_preservation_enabled"] is expected


def test_semantic_cache_does_not_inherit_permission_or_mutate_saved_entry(monkeypatch):
    from app.config import settings
    raw = {"mode": "smart_enhance", "final_prompt": "A clean product photograph.", "qr_preservation_enabled": True}
    entry = {"decision": raw, "metadata": {"prompt": "prior request"}}
    monkeypatch.setattr(brain, "_read_cache_store", lambda: {"prior": entry})
    monkeypatch.setattr(brain, "_semantic_cache_score", lambda *args: 1.0)
    old = (settings.claude_orchestrator_cache_enabled, settings.claude_orchestrator_semantic_cache_enabled)
    object.__setattr__(settings, "claude_orchestrator_cache_enabled", True)
    object.__setattr__(settings, "claude_orchestrator_semantic_cache_enabled", True)
    try:
        assert brain._read_semantic_cached_decision({})[1]["qr_preservation_enabled"] is False
        assert raw["qr_preservation_enabled"] is True
    finally:
        for name, value in zip(("claude_orchestrator_cache_enabled", "claude_orchestrator_semantic_cache_enabled"), old):
            object.__setattr__(settings, name, value)

def test_qr_schema_is_optional_and_public_image_request_has_no_switch():
    from app.schemas import CreateImageJobRequest
    for schema in (brain.CLAUDE_DECISION_SCHEMA, brain.CLAUDE_INLINE_DECISION_SCHEMA):
        assert schema["properties"]["qr_preservation_enabled"]["type"] == "boolean"
        assert "qr_preservation_enabled" not in schema["required"]
    assert "qr_preservation_enabled" not in CreateImageJobRequest.model_fields
    parameter = inspect.signature(generation.create_image_job).parameters["_qr_preservation_enabled"]
    assert parameter.default is False
    assert parameter.kind == inspect.Parameter.KEYWORD_ONLY


def test_final_checkpoint_skeleton_carries_false_default():
    assert brain._checkpoint_json_skeleton("generation_decision")["qr_preservation_enabled"] is False


def test_qr_slot_binding_survives_compaction():
    slot = {"slot": "qr_code", "rule": "bottom_right", "target_surface": "poster", "source_asset_id": "asset_current"}
    assert brain._compact_asset_slot_plan([slot], limit=8)[0] == slot

@pytest.mark.parametrize("has_reference", [False, True])
def test_inline_policy_uses_source_presence_without_a_keyword_classifier(tmp_path, has_reference):
    import json
    user_prompt = "Keep the existing QR; do not invent another."
    (tmp_path / "context.json").write_text(json.dumps({"request": {"user_prompt": user_prompt}}), encoding="utf-8")
    (tmp_path / "uploaded_assets.json").write_text(json.dumps(
        [{"asset_id": "source", "role": "subject_reference"}] if has_reference else []), encoding="utf-8")
    payload = json.loads(brain._build_inline_json_prompt(tmp_path).split("\n", 1)[1])
    assert payload["user_request"] == user_prompt
    policy = payload["qr_preservation_policy"]
    if has_reference:
        assert policy == brain.QR_PRESERVATION_INSTRUCTION
        assert "task_intent.slot_plan" in policy
        assert "explicitly requests reuse" in policy
    else:
        assert policy == "No reference assets: qr_preservation_enabled=false."
        assert len(policy) < 80
