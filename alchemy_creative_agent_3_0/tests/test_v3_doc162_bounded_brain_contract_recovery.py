"""Doc162: strict semantic recovery stays remote-only and bounded."""

from __future__ import annotations

import json

from PIL import Image

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.llm_brain.providers import BrainProviderError
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    active_review_contract,
    inspection_reference_paths,
)
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _complete_profile() -> dict:
    return {
        "rendering_intent": {
            "rendering_mode": "photoreal",
            "stylization_scope": "none",
            "decision_owner": "remote_brain",
        },
        "subject_entities": [],
        "visual_intent_tags": ["photographic_observation"],
        "unknown_requirements": [],
        "confidence": 0.95,
        "evidence": [],
    }


def _complete_activation() -> dict:
    return {
        "requested_capabilities": [],
        "rejected_capabilities": [],
        "unresolved_signals": [],
        "confidence": 0.95,
    }


class _SequencedSemanticProvider(EcommerceRemoteBrainTestProvider):
    def __init__(self, *, recover: bool) -> None:
        super().__init__()
        self.recover = recover

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage != "plan":
            return payload
        if len(self.requests) == 1 or not self.recover:
            payload["visual_task_profile"] = {
                "rendering_intent": _complete_profile()["rendering_intent"],
            }
        else:
            payload["visual_task_profile"] = _complete_profile()
        payload["capability_activation_intent"] = _complete_activation()
        return payload


def _strict_request(adapter: V3LLMBrainAdapter):  # noqa: ANN201
    return adapter.build_request(
        user_input="Create one factual studio photograph of a ceramic vessel with no person visible.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={"requested_image_count": 1, "require_real_images": True},
    )


def test_doc162_one_remote_schema_reanswer_recovers_same_frozen_request(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _SequencedSemanticProvider(recover=True)
    adapter = V3LLMBrainAdapter(provider=provider)

    result = adapter.run(_strict_request(adapter))

    assert result.audit["remote_semantic_contract_recovery_attempted"] is True
    assert result.audit["remote_semantic_contract_recovery_succeeded"] is True
    assert result.audit["remote_semantic_contract_recovery_initial_rejected_sections"] == [
        "visual_task_profile"
    ]
    assert result.audit["remote_semantic_contract_recovery_final_rejected_sections"] == []
    assert len(provider.requests) == 2
    first, second = provider.requests
    assert first["user_input"] == second["user_input"]
    assert first["requested_image_count"] == second["requested_image_count"] == 1
    assert "remote_semantic_contract_recovery" not in first["metadata"]
    assert second["metadata"]["remote_semantic_contract_recovery"] == {
        "contract_version": "v3_remote_semantic_contract_recovery_v1",
        "attempt": 1,
        "rejected_sections": ["visual_task_profile"],
        "same_frozen_request": True,
    }


def test_doc162_two_invalid_semantic_answers_fail_closed_after_exactly_two_calls(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _SequencedSemanticProvider(recover=False)
    adapter = V3LLMBrainAdapter(provider=provider)

    result = adapter.run(_strict_request(adapter))

    assert len(provider.requests) == 2
    assert result.audit["remote_contract_partial_fallback"] is True
    assert result.audit["remote_contract_rejected_sections"] == ["visual_task_profile"]
    assert result.audit["remote_semantic_contract_recovery_attempted"] is True
    assert result.audit["remote_semantic_contract_recovery_succeeded"] is False
    assert result.audit["remote_semantic_contract_recovery_final_rejected_sections"] == [
        "visual_task_profile"
    ]


def test_doc162_recovery_payload_requests_complete_reanswer_not_patch(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    adapter = V3LLMBrainAdapter(provider=_SequencedSemanticProvider(recover=True))
    request = _strict_request(adapter)
    recovery_request = request.model_copy(
        update={
            "metadata": {
                **request.metadata,
                "remote_semantic_contract_recovery": {
                    "contract_version": "v3_remote_semantic_contract_recovery_v1",
                    "attempt": 1,
                    "rejected_sections": ["visual_task_profile"],
                    "same_frozen_request": True,
                },
            }
        },
        deep=True,
    )

    payload = json.loads(build_remote_payload(recovery_request))

    assert payload["semantic_contract_recovery"]["same_frozen_request"] is True
    assert payload["semantic_contract_recovery"]["rejected_sections"] == ["visual_task_profile"]
    assert "Re-author the complete compact contract" in payload["remote_response_contract"]
    assert "do not return a patch" in payload["remote_response_contract"]


def test_doc162_transport_failure_does_not_trigger_semantic_recovery(monkeypatch) -> None:
    class _FailingProvider:
        provider = "remote_test"
        model = "remote_test_v1"

        def __init__(self) -> None:
            self.calls = 0

        def available(self, *, force: bool = False) -> bool:
            return True

        def run(self, request):  # noqa: ANN001
            self.calls += 1
            raise BrainProviderError("remote brain provider failed: request timed out")

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _FailingProvider()
    adapter = V3LLMBrainAdapter(provider=provider)

    result = adapter.run(_strict_request(adapter))

    assert provider.calls == 1
    assert result.llm_used is False
    assert result.audit["remote_semantic_contract_recovery_attempted"] is False


def _professional_review_metadata() -> dict:
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="profile"
    )
    return {
        "capability_execution_envelope": {
            "activation_plan": {
                "activation_mode": "enforced",
                "metadata": {
                    "professional_face_identity_quality_contract": planning[
                        "professional_face_identity_quality_contract"
                    ]
                },
            },
            "resolved_constraint_ledger": {
                "hard_semantic_contract": True,
                "review_contracts": [],
                "provider_projection": {},
            },
        },
        "professional_planning_metadata": planning,
        "professional_identity_reference_strategy": "serial_anchor_pack_root_reuse_v1",
        "professional_reference_stage": "profile",
    }


def test_doc162_professional_quality_contract_projects_typed_shared_vision_dimensions() -> None:
    contract = active_review_contract(_professional_review_metadata())

    assert contract["professional_identity_quality"]["applies"] is True
    assert "same_person_readability" in contract["score_dimensions"]
    assert "distinctive_feature_readability" in contract["score_dimensions"]
    assert "prompt_owned_channel_obedience" in contract["score_dimensions"]
    assert "professional_ai_overperfection" in contract["issue_codes"]


def test_doc162_professional_profile_review_keeps_three_original_sources(tmp_path) -> None:
    metadata = _professional_review_metadata()
    references = []
    for index, source_type in enumerate(("uploaded", "selected_output", "selected_output"), start=1):
        path = tmp_path / f"reference-{index}.png"
        Image.new("RGB", (32, 32), (index * 20, 40, 60)).save(path)
        references.append(
            {
                "asset_id": f"source_{index}",
                "file_path": str(path),
                "source_type": source_type,
                "role": "face_reference",
                "use_policy": "identity",
            }
        )
    metadata["reference_assets"] = references

    assert inspection_reference_paths(metadata) == [
        tmp_path / "reference-1.png",
        tmp_path / "reference-2.png",
        tmp_path / "reference-3.png",
    ]


def test_doc162_ordinary_review_still_caps_reference_sources_at_two(tmp_path) -> None:
    metadata = _professional_review_metadata()
    metadata.pop("professional_identity_reference_strategy")
    references = []
    for index in range(1, 4):
        path = tmp_path / f"ordinary-{index}.png"
        Image.new("RGB", (32, 32), (index * 20, 40, 60)).save(path)
        references.append({"asset_id": f"ordinary_{index}", "file_path": str(path)})
    metadata["reference_assets"] = references

    assert len(inspection_reference_paths(metadata)) == 2
