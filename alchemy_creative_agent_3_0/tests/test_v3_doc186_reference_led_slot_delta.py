"""Doc186 reference-led Character Card slot-delta prompt contract."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_remote_required_result
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainProfessionalAnchorViewDecisionMissing,
    BrainProviderAdmissionDecisionMissing,
)
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    CapabilityActivationPlan,
    TemplateCapabilityPolicy,
)
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


def _slot_delta_runtime_request(
    view_role: str,
    *,
    uploaded_asset_ids: list[str] | None = None,
    reference_assets: list[dict[str, str]] | None = None,
) -> ScenarioRuntimeRequest:
    return ScenarioRuntimeRequest(
        user_input="继续生成标准人物角色卡后续角度位。",
        uploaded_asset_ids=list(uploaded_asset_ids or ["root_source"]),
        metadata={
            "project_id": "project_doc186_recovery",
            "requested_image_count": 1,
            "require_real_images": True,
            "professional_mode": True,
            "professional_anchor_pack_preparation": True,
            "professional_anchor_reference_assets": list(
                reference_assets
                if reference_assets is not None
                else [
                    {"asset_id": "root_source", "role": "root"},
                    {"asset_id": "front_winner", "role": "face_front_winner"},
                ]
            ),
            "professional_planning_metadata": {
                "professional_anchor_capture_scope": "character_card_face_identity",
                "professional_reference_stage": view_role,
            },
            "generation_channel": "mcp",
            "mcp_operation_id": f"asset_doc186:{view_role}:1",
        },
    )


def _remote_required_brain_result(view_role: str):
    return build_remote_required_result(
        BrainRunRequest(
            user_input=f"Prepare one Character Card {view_role} slot.",
            stage="scenario_runtime",
            scenario_id="general_creative",
            template_id="general_template",
            requested_image_count=1,
            requested_image_size="1024x1536",
            metadata=_slot_delta_runtime_request(view_role).metadata,
        ),
        "Remote Brain timed out in a reference-led Character Card slot.",
    )


def test_doc186_nonfront_character_card_brain_timeout_uses_bounded_slot_delta_recovery() -> None:
    runtime = ScenarioRuntime()
    request = _slot_delta_runtime_request("profile")
    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        request,
        _remote_required_brain_result("profile"),
    )

    assert recovered.canonical_provider_prompts
    canonical = recovered.canonical_provider_prompts[0]
    assert "Strict 90-degree side profile" in canonical.prompt
    assert canonical.reference_led_slot_delta_decision.prompt_scope == "slot_delta_only"
    assert canonical.provider_admission_decision.provider_admission_status == "admitted"
    assert recovered.audit["character_card_slot_delta_recovery_prompts_received"] is True
    assert recovered.visual_task_profile is not None
    assert recovered.capability_activation_intent is not None
    assert recovered.visual_task_profile.rendering_intent.decision_owner == "remote_brain"
    assert (
        recovered.visual_task_profile.reference_channel_ownership_intent is not None
        and recovered.visual_task_profile.reference_channel_ownership_intent.decision_owner == "remote_brain"
    )
    assert {
        item.capability_id for item in recovered.capability_activation_intent.requested_capabilities
    } >= {"portrait_identity", "reference_channel_policy", "human_realism"}

    runtime._require_remote_creative_brain(  # noqa: SLF001
        request,
        TemplateCapabilityPolicy(requires_remote_creative_brain=True),
        recovered,
    )
    runtime._require_brain_signed_provider_prompts(  # noqa: SLF001
        request,
        TemplateCapabilityPolicy(requires_remote_creative_brain=True),
        recovered,
        CapabilityActivationPlan(
            plan_id="plan_doc186_recovery",
            fingerprint="fp_doc186_recovery",
            job_id="job_doc186_recovery",
            task_profile_id="profile_doc186_recovery",
            template_id="general_template",
            scenario_id="general_creative",
        ),
    )


def test_doc190_first_45_recovery_counts_root_plus_front_winner_chain() -> None:
    runtime = ScenarioRuntime()
    request = _slot_delta_runtime_request(
        "three_quarter",
        uploaded_asset_ids=["root_source"],
        reference_assets=[
            {"asset_id": "front_winner", "role": "face_front_winner"},
        ],
    )

    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        request,
        _remote_required_brain_result("three_quarter"),
    )

    assert recovered.canonical_provider_prompts
    assert recovered.audit["character_card_slot_delta_recovery_prompts_received"] is True
    assert recovered.audit["character_card_slot_delta_recovery_view_role"] == "three_quarter"
    source_ids = recovered.visual_task_profile.subject_entities[0].source_asset_ids
    assert source_ids == ["root_source", "front_winner"]
    prompt = recovered.canonical_provider_prompts[0].prompt
    assert "Reference role map" in prompt
    assert "approved left_front_25 only as the same-side identity bridge" in prompt
    assert "profile card as the stronger pose-depth reference" not in prompt


def test_doc192_left_25_timeout_recovery_preserves_card_scale_family_without_hard_angle() -> None:
    runtime = ScenarioRuntime()
    request = _slot_delta_runtime_request("left_front_25")
    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        request,
        _remote_required_brain_result("left_front_25"),
    )

    prompt = recovered.canonical_provider_prompts[0].prompt
    assert "Left-front shallow three-quarter transition" in prompt
    assert "natural left-front transition target around 25 to 30 degrees" in prompt
    assert "allow natural renderer variation" in prompt
    assert "approved front card framing" in prompt
    assert "same camera distance" in prompt
    assert "head-top margin" in prompt
    assert "head-neck-upper-shoulders" in prompt
    assert "tight face close-up" in prompt


def test_doc190_recovered_character_card_slot_keeps_shared_human_realism_execution_active() -> None:
    runtime = ScenarioRuntime()
    request = _slot_delta_runtime_request("reverse_three_quarter")
    resolution = runtime.scenario_registry.resolve(request.scenario_selection)
    policy = runtime._resolve_template_capability_policy(request, resolution)  # noqa: SLF001
    catalog = runtime.visual_capability_registry.catalog_snapshot(
        runtime._template_id(request, resolution),  # noqa: SLF001
        resolution.manifest.scenario_id,
    )
    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        request,
        _remote_required_brain_result("reverse_three_quarter"),
    )
    plan = runtime._reuse_or_build_activation_plan(  # noqa: SLF001
        request,
        resolution,
        recovered,
        policy,
        catalog.catalog_version,
        runtime._capability_activation_mode(request),  # noqa: SLF001
    )
    active_run = runtime._run_active_capabilities(  # noqa: SLF001
        request,
        resolution,
        plan,
        None,
        brain_result=recovered,
    )

    cluster = next(
        result
        for result in active_run.results
        if result.module_id == "visual_capability_cluster"
    ).facts["visual_capability_cluster"]

    assert cluster["human_photorealism_guidance"]["applies"] is True
    runtime._validate_frozen_capability_execution(plan, active_run)  # noqa: SLF001


def test_doc190_reverse_three_quarter_timeout_recovery_is_opposite_front_45_not_rear() -> None:
    runtime = ScenarioRuntime()
    request = _slot_delta_runtime_request("reverse_three_quarter")
    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        request,
        _remote_required_brain_result("reverse_three_quarter"),
    )

    prompt = recovered.canonical_provider_prompts[0].prompt
    assert "Right-front three-quarter" in prompt
    assert "opposite front-side 45-degree" in prompt
    assert "independent right-front" in prompt
    assert "Do not mirror or copy the left-front card" in prompt
    assert "Reference role map" in prompt
    assert "input 4 is the approved 90-degree side profile and is the primary pose-depth guide" in prompt
    assert "input 5 is the approved right-front 25-degree transition" in prompt
    assert "right-side identity/framing bridge" in prompt
    assert "right ear on image-right" in prompt
    assert "nose and gaze angled toward image-left" in prompt
    assert "upper-shoulders cutoff" in prompt
    assert "white padding" in prompt
    assert "torso portrait" in prompt
    assert "back of head dominant" not in prompt
    assert "mostly away" not in prompt
    assert "mirrored opposite side" not in prompt
    assert "Mirror the approved" not in prompt


def test_doc190_profile_timeout_recovery_preserves_card_scale_without_face_area_parity() -> None:
    runtime = ScenarioRuntime()
    request = _slot_delta_runtime_request("profile")
    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        request,
        _remote_required_brain_result("profile"),
    )

    prompt = recovered.canonical_provider_prompts[0].prompt
    assert "Strict 90-degree side profile" in prompt
    assert "same camera distance" in prompt
    assert "head size" in prompt
    assert "upper-shoulders cutoff" in prompt
    assert "collar line" in prompt
    assert "same face area proportion" not in prompt
    assert "full face" not in prompt


def test_doc190_rear_head_timeout_recovery_preserves_rear_card_scale_without_face_terms() -> None:
    runtime = ScenarioRuntime()
    request = _slot_delta_runtime_request("rear_head")
    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        request,
        _remote_required_brain_result("rear_head"),
    )

    prompt = recovered.canonical_provider_prompts[0].prompt
    assert "Back-of-head reference" in prompt
    assert "no visible face and no eyes visible" in prompt
    assert "full back-of-head hair boundary" in prompt
    assert "back collar line" in prompt
    assert "upper-shoulders cutoff" in prompt
    assert "same face area proportion" not in prompt
    assert "full face" not in prompt


def test_doc190_slot_delta_transport_timeout_is_not_brain_payload() -> None:
    adapter = V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())
    request = adapter.build_request(
        user_input="Prepare one Character Card side slot.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={"_brain_transport_timeout_seconds": 11, "requested_image_count": 1},
    )

    payload = json.loads(build_remote_payload(request))

    assert request.transport_timeout_seconds == 11
    assert "_brain_transport_timeout_seconds" not in json.dumps(payload, ensure_ascii=False)
    assert "transport_timeout_seconds" not in json.dumps(payload, ensure_ascii=False)


def test_doc190_runtime_shortens_only_character_card_nonfront_slot_delta_brain_wait() -> None:
    runtime = ScenarioRuntime()

    assert runtime._character_card_slot_delta_transport_timeout_seconds(  # noqa: SLF001
        _slot_delta_runtime_request("reverse_three_quarter")
    ) == 28.0
    assert runtime._character_card_slot_delta_transport_timeout_seconds(  # noqa: SLF001
        _slot_delta_runtime_request("standard_front")
    ) is None
    assert runtime._character_card_slot_delta_transport_timeout_seconds(  # noqa: SLF001
        ScenarioRuntimeRequest(
            user_input="普通图片",
            scenario_selection={"scenario_id": "general_creative"},
            metadata={"requested_image_count": 1},
        )
    ) is None


def test_doc186_front_face_slot_never_uses_timeout_recovery() -> None:
    runtime = ScenarioRuntime()
    request = _slot_delta_runtime_request("standard_front")
    recovered = runtime._recover_character_card_slot_delta_brain_result(  # noqa: SLF001
        request,
        _remote_required_brain_result("standard_front"),
    )

    assert not recovered.canonical_provider_prompts
    assert "character_card_slot_delta_recovery_prompts_received" not in recovered.audit


def test_doc186_product_api_accepts_recovered_slot_delta_prompt_as_shared_materialization_contract() -> None:
    result = SimpleNamespace(
        metadata={
            "llm_brain": {
                "canonical_provider_prompts": [{"output_index": 1, "prompt": "slot delta"}],
                "audit": {
                    "character_card_slot_delta_recovery_prompts_received": True,
                    "remote_canonical_provider_prompts_received": False,
                },
            }
        },
        creative_job=None,
    )

    assert V3ProductApiService._uses_brain_signed_provider_prompts(result) is True  # noqa: SLF001
