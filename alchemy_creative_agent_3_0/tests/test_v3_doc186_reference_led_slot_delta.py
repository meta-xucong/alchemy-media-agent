"""Doc186 reference-led Character Card slot-delta prompt contract."""

from __future__ import annotations

import json

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainProfessionalAnchorViewDecisionMissing,
    BrainProviderAdmissionDecisionMissing,
)
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _finalizer_request(*, slot_delta_type: str = "expression") -> BrainRunRequest:
    context = {
        "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
        "professional_face_identity_quality_contract": {
            "contract_version": "professional_face_identity_quality_v2",
            "scope": "character_card_expression_set",
            "owner": "remote_v3_llm_brain",
        },
        "reference_led_slot_delta_decision": {
            "required": True,
            "contract_version": "v3_reference_led_slot_delta_decision_v1",
            "materialization_mode": "reference_led_slot_delta",
            "stable_identity_source": "approved_character_card_reference",
            "prompt_scope": "slot_delta_only",
            "safety_sensitive_repetition_policy": "avoid_repeating_stable_person_biology",
            "slot_delta_type": slot_delta_type,
            "owner": "remote_v3_llm_brain",
            "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
        },
        "provider_admission_decision": {
            "required": True,
            "contract_version": "v3_provider_admission_decision_v1",
            "provider_admission_status": "admitted",
            "prompt_language_mode": "concise_positive_renderer_direction",
            "safety_sensitive_prompt_normalized": "applied",
            "owner": "remote_v3_llm_brain",
            "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
        },
    }
    return BrainRunRequest(
        user_input="Prepare one Character Card expression slot from the approved reference.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={"canonical_prompt_context": context},
    )


def _face_anchor_finalizer_request() -> BrainRunRequest:
    context = {
        "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
        "professional_face_identity_quality_contract": {
            "contract_version": "professional_face_identity_quality_v2",
            "scope": "character_card_face_identity",
            "owner": "remote_v3_llm_brain",
            "capture_presentation": "neutral_identity_evidence_capture",
            "geometry_scope": "face_and_head_only",
        },
        "professional_anchor_view_decision": {
            "required": True,
            "contract_version": "v3_professional_anchor_view_decision_v3",
            "target_view_role": "standard_front",
            "capture_presentation": "neutral_identity_evidence_capture",
            "capture_continuity": "establish_neutral_capture",
            "capture_scope": "character_card_face_identity",
            "framing_standard": "consistent_head_and_upper_shoulders_reference_crop",
            "crop_policy": "head_top_margin_full_face_neck_and_upper_shoulders_visible",
            "torso_scope": "upper_shoulders_only_no_half_body_or_big_head_crop",
            "source_viewpoint_inheritance": "identity_only_do_not_inherit_source_pose_angle",
            "front_pose_normalization": "normalize_to_symmetric_camera_facing_front",
            "face_axis_alignment": "face_midline_vertical_eyes_level_nose_centered",
            "owner": "remote_v3_llm_brain",
            "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
        },
        "provider_admission_decision": {
            "required": True,
            "contract_version": "v3_provider_admission_decision_v1",
            "provider_admission_status": "admitted",
            "prompt_language_mode": "concise_positive_renderer_direction",
            "safety_sensitive_prompt_normalized": "applied",
            "owner": "remote_v3_llm_brain",
            "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
        },
    }
    return BrainRunRequest(
        user_input="Prepare the standard front Face Identity slot.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={"canonical_prompt_context": context},
    )


def test_doc186_bridge_marks_only_later_character_card_slots_as_reference_led() -> None:
    front = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="standard_front",
        capture_scope="character_card_face_identity",
    )
    profile = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="profile",
        capture_scope="character_card_face_identity",
    )
    ordinary = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="profile",
        capture_scope="anchor_pack",
    )
    expression = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="expression_set",
        slot_key="expression.smile",
    )
    body = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="body_silhouette",
        slot_key="body.front_full",
        source_class="brain_inferred",
    )

    assert "reference_led_slot_delta_contract" not in front
    assert "reference_led_slot_delta_contract" not in ordinary
    assert profile["reference_led_slot_delta_contract"]["slot_delta_type"] == "view_angle"
    assert expression["reference_led_slot_delta_contract"]["slot_delta_type"] == "expression"
    assert body["reference_led_slot_delta_contract"]["slot_delta_type"] == "body_pose"


def test_doc186_brain_schema_requires_reference_led_delta_receipt() -> None:
    payload = json.loads(build_remote_payload(_finalizer_request()))
    schema = payload["return_schema"]["canonical_provider_prompts"][0]

    assert schema["reference_led_slot_delta_decision"] == {
        "contract_version": "v3_reference_led_slot_delta_decision_v1",
        "materialization_mode": "reference_led_slot_delta",
        "stable_identity_source": "approved_character_card_reference",
        "prompt_scope": "slot_delta_only",
        "safety_sensitive_repetition_policy": "avoid_repeating_stable_person_biology",
        "slot_delta_type": "expression",
        "status": "approved|rewritten",
        "owner": "remote_v3_llm_brain",
    }
    assert "reference-led slot delta" in payload["remote_response_contract"]
    assert "Do not restate stable person biology" in payload["remote_response_contract"]


def test_doc186_adapter_rejects_missing_reference_led_delta_receipt() -> None:
    class MissingSlotDeltaProvider(EcommerceRemoteBrainTestProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            for item in payload.get("canonical_provider_prompts", []):
                item.pop("reference_led_slot_delta_decision", None)
            return payload

    with pytest.raises(BrainProviderAdmissionDecisionMissing):
        V3LLMBrainAdapter(provider=MissingSlotDeltaProvider()).finalize_canonical_provider_prompts(
            _finalizer_request()
        )


def test_doc186_adapter_rejects_face_identity_prompt_that_leaves_slot_scope() -> None:
    class WrongFaceScopeProvider(EcommerceRemoteBrainTestProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            for item in payload.get("canonical_provider_prompts", []):
                item["prompt"] = (
                    "A full-body photograph of a young person standing in a sunlit park with "
                    "golden backlight, cinematic focus, and a summer dress."
                )
            return payload

    with pytest.raises(BrainProfessionalAnchorViewDecisionMissing):
        V3LLMBrainAdapter(provider=WrongFaceScopeProvider()).finalize_canonical_provider_prompts(
            _face_anchor_finalizer_request()
        )


def test_doc186_scenario_runtime_projects_delta_contract_for_character_card_stage(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    source = tmp_path / "front-winner.png"
    Image.new("RGB", (640, 640), (180, 160, 150)).save(source)
    brain = EcommerceRemoteBrainTestProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain))
    planning = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="expression_set",
        slot_key="expression.smile",
    )
    result = runtime.plan_job(
        {
            "user_input": "Prepare one Character Card expression slot.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_assets": [
                {
                    "asset_id": "front_winner",
                    "role": "face_reference",
                    "file_path": str(source),
                    "use_policy": "identity",
                    "strength": "hard",
                }
            ],
            "metadata": {
                "project_id": "project_doc186",
                "requested_image_count": 1,
                "require_real_images": True,
                "professional_mode": True,
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "expression_set",
                "professional_character_card_slot": "expression.smile",
                "professional_anchor_reference_assets": [
                    {"asset_id": "front_winner", "role": "portrait_identity"}
                ],
                "professional_planning_metadata": planning,
                "generation_channel": "mcp",
                "mcp_operation_id": "asset_doc186:expression_set:expression.smile:1",
            },
        }
    )

    assert result.status.value == "planned"
    finalizer = [item for item in brain.requests if item["stage"] == "provider_prompt_finalize"][-1]
    context = finalizer["metadata"]["canonical_prompt_context"]

    assert context["reference_led_slot_delta_decision"]["slot_delta_type"] == "expression"
    assert context["provider_admission_decision"]["prompt_language_mode"] == (
        "concise_positive_renderer_direction"
    )
    assert result.metadata["llm_brain"]["audit"]["reference_led_slot_delta_decision_signed"] is True


def test_doc186_general_mode_does_not_receive_character_card_delta_contract() -> None:
    payload = json.loads(
        build_remote_payload(
            BrainRunRequest(
                user_input="A simple product photo.",
                stage="provider_prompt_finalize",
                scenario_id="general_creative",
                template_id="general_template",
                requested_image_count=1,
                metadata={"canonical_prompt_context": {}},
            )
        )
    )
    schema = payload["return_schema"]["canonical_provider_prompts"][0]

    assert "reference_led_slot_delta_decision" not in schema
