"""Doc184: Character Card Face Identity has a face-only capture contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainProfessionalAnchorViewDecisionMissing,
    BrainProviderAdmissionDecisionMissing,
)
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import ProductApiAnchorPackPreparationHost
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import (
    AnchorGenerationRequest,
    AnchorPackPreparationRequest,
    AnchorPackPreparationService,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import BodyPreparationRequest
from alchemy_creative_agent_3_0.app.visual_assets.contracts import (
    FaceIdentityModule,
    PeopleAsset,
    RootSourceProvenance,
)
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


CAPTURE_SCOPE = "character_card_face_identity"
PREPARATION_INTENT = "Prepare neutral identity evidence for the same person."


def _asset() -> PeopleAsset:
    return PeopleAsset(
        people_asset_id="people_doc184",
        project_id="project_doc184",
        subject_kind="human_person",
        face_identity_module=FaceIdentityModule(
            module_id="face_doc184",
            people_asset_id="people_doc184",
        ),
        preparation_intent=PREPARATION_INTENT,
    )


def _root() -> RootSourceProvenance:
    return RootSourceProvenance(
        source_type="uploaded_portrait",
        source_asset_id="root_doc184",
        project_id="project_doc184",
    )


def _anchor_request(*, capture_scope: str | None = None) -> BrainRunRequest:
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="standard_front",
        **({"capture_scope": CAPTURE_SCOPE} if capture_scope else {}),
    )
    decision = {
        "required": True,
        "contract_version": "v3_professional_anchor_view_decision_v3",
        "owner": "remote_v3_llm_brain",
        "target_view_role": "standard_front",
        "capture_presentation": "neutral_identity_evidence_capture",
        "capture_continuity": "establish_neutral_capture",
        "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
    }
    if capture_scope:
        decision.update(
            {
                "capture_scope": capture_scope,
                "framing_standard": "consistent_head_and_upper_shoulders_reference_crop",
                "crop_policy": "head_top_margin_full_face_neck_and_upper_shoulders_visible",
                "torso_scope": "upper_shoulders_only_no_half_body_or_big_head_crop",
                "source_viewpoint_inheritance": "identity_only_do_not_inherit_source_pose_angle",
                "front_pose_normalization": "normalize_to_symmetric_camera_facing_front",
                "face_axis_alignment": "face_midline_vertical_eyes_level_nose_centered",
            }
        )
    provider_admission = {
        "required": True,
        "contract_version": "v3_provider_admission_decision_v1",
        "provider_admission_status": "admitted",
        "prompt_language_mode": "concise_positive_renderer_direction",
        "safety_sensitive_prompt_normalized": "applied",
        "owner": "remote_v3_llm_brain",
        "frozen_binding": decision["frozen_binding"],
    } if capture_scope else None
    return BrainRunRequest(
        user_input="Prepare the frozen Professional identity evidence view.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={
            "canonical_prompt_context": {
                "professional_anchor_view_decision": decision,
                "professional_face_identity_quality_contract": planning[
                    "professional_face_identity_quality_contract"
                ],
                "frozen_binding": decision["frozen_binding"],
                **(
                    {"provider_admission_decision": provider_admission}
                    if provider_admission is not None
                    else {}
                ),
            }
        },
    )


def test_doc184_character_card_scope_is_typed_and_ordinary_anchor_scope_is_unchanged() -> None:
    face = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="standard_front",
        capture_scope=CAPTURE_SCOPE,
    )
    ordinary = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="standard_front"
    )

    assert face["professional_anchor_capture_scope"] == CAPTURE_SCOPE
    assert face["professional_face_identity_quality_contract"]["scope"] == CAPTURE_SCOPE
    assert face["professional_face_identity_quality_contract"]["geometry_scope"] == "face_and_head_only"
    assert (
        face["professional_face_identity_quality_contract"]["face_identity_framing_contract"][
            "framing_standard"
        ]
        == "consistent_head_and_upper_shoulders_reference_crop"
    )
    assert (
        face["professional_face_identity_quality_contract"]["front_pose_normalization_contract"][
            "front_pose_normalization"
        ]
        == "normalize_to_symmetric_camera_facing_front"
    )
    assert (
        face["professional_face_identity_quality_contract"]["face_card_image_clarity_contract"][
            "clarity_standard"
        ]
        == "commercial_clean_translucent_no_smear_no_dirty_noise"
    )
    assert (
        face["professional_face_identity_quality_contract"]["body_silhouette_contract"]
        == "not_applicable_until_body_silhouette_stage"
    )
    assert ordinary["professional_anchor_capture_scope"] == "anchor_pack"
    assert ordinary["professional_face_identity_quality_contract"]["scope"] == "face_identity_anchor_pack"
    assert "geometry_scope" not in ordinary["professional_face_identity_quality_contract"]


def test_doc184_character_card_later_stages_keep_professional_quality_contract() -> None:
    expression = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="expression_set",
        slot_key="expression.smile",
    )
    body = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="body_silhouette",
        slot_key="body.front_full",
        source_class="user_described",
    )

    assert expression["professional_face_identity_quality_contract"]["scope"] == "character_card_expression_set"
    assert (
        expression["professional_face_identity_quality_contract"]["expression_contract"]
        == "preserve_identity_while_varying_expression_only"
    )
    assert body["professional_face_identity_quality_contract"]["scope"] == "character_card_body_silhouette"
    assert (
        body["professional_face_identity_quality_contract"]["body_silhouette_contract"]
        == "preserve_identity_scale_and_age_appropriate_body_proportion"
    )
    assert expression["professional_face_identity_quality_contract"]["contract_version"] == (
        body["professional_face_identity_quality_contract"]["contract_version"]
    )


def test_doc184_generation_request_derives_scope_only_from_character_card_view_scope() -> None:
    service = AnchorPackPreparationService(generator=object(), reviewer=object())
    common = {
        "request": AnchorPackPreparationRequest(
            project_id="project_doc184",
            asset=_asset(),
            root_source_provenance=_root(),
            preparation_intent=PREPARATION_INTENT,
        ),
        "pack_version_id": "pack_doc184",
        "view_role": "standard_front",
        "candidate_index": 1,
        "reference_evidence_ids": ["root_doc184"],
    }
    ordinary = service._generation_request(**common)  # noqa: SLF001
    character_card = service._generation_request(  # noqa: SLF001
        **{
            **common,
            "request": common["request"].model_copy(update={"face_view_scope": "character_card"}),
        }
    )

    assert ordinary.capture_scope == "anchor_pack"
    assert character_card.capture_scope == CAPTURE_SCOPE


def test_doc184_brain_schema_and_receipt_carry_face_scope_without_prompt_patching() -> None:
    payload = json.loads(build_remote_payload(_anchor_request(capture_scope=CAPTURE_SCOPE)))
    schema = payload["return_schema"]["canonical_provider_prompts"][0]

    assert schema["professional_anchor_view_decision"]["capture_scope"] == CAPTURE_SCOPE
    assert (
        schema["professional_anchor_view_decision"]["framing_standard"]
        == "consistent_head_and_upper_shoulders_reference_crop"
    )
    assert (
        schema["professional_anchor_view_decision"]["front_pose_normalization"]
        == "normalize_to_symmetric_camera_facing_front"
    )
    assert "face/head angle only" in payload["remote_response_contract"]
    assert "straight-on, symmetric" in payload["remote_response_contract"]
    assert "no dirty cast, no smear" in payload["remote_response_contract"]
    assert "full-body portrait" in payload["remote_response_contract"]
    assert "provider_admission_decision" in schema
    assert "concise_positive_renderer_direction" in payload["remote_response_contract"]
    assert "prompt suffix" not in payload["remote_response_contract"].lower()

    ordinary_payload = json.loads(build_remote_payload(_anchor_request()))
    ordinary_schema = ordinary_payload["return_schema"]["canonical_provider_prompts"][0]
    assert "capture_scope" not in ordinary_schema["professional_anchor_view_decision"]
    assert "provider_admission_decision" not in ordinary_schema


class _ScopeEchoProvider(EcommerceRemoteBrainTestProvider):
    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage == "provider_prompt_finalize":
            for item in payload.get("canonical_provider_prompts", []):
                decision = item.get("professional_anchor_view_decision")
                if isinstance(decision, dict):
                    decision["capture_scope"] = CAPTURE_SCOPE
        return payload


def test_doc184_runtime_and_adapter_preserve_brain_scope_receipt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    source = tmp_path / "identity-root.png"
    Image.new("RGB", (640, 640), (170, 135, 120)).save(source)
    brain = _ScopeEchoProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain))
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="standard_front",
        capture_scope=CAPTURE_SCOPE,
    )

    result = runtime.plan_job(
        {
            "user_input": "Prepare one Character Card Face Identity capture.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_assets": [
                {
                    "asset_id": "root_doc184",
                    "role": "face_reference",
                    "file_path": str(source),
                    "use_policy": "identity",
                    "strength": "hard",
                }
            ],
            "metadata": {
                "project_id": "project_doc184",
                "requested_image_count": 1,
                "require_real_images": True,
                "professional_mode": True,
                "professional_anchor_pack_preparation": True,
                "professional_planning_metadata": planning,
            },
        }
    )

    assert result.status.value == "planned"
    finalizer = [item for item in brain.requests if item["stage"] == "provider_prompt_finalize"][-1]
    context = finalizer["metadata"]["canonical_prompt_context"]
    assert context["professional_anchor_view_decision"]["capture_scope"] == CAPTURE_SCOPE
    assert (
        context["professional_anchor_view_decision"]["framing_standard"]
        == "consistent_head_and_upper_shoulders_reference_crop"
    )
    assert (
        context["professional_anchor_view_decision"]["face_axis_alignment"]
        == "face_midline_vertical_eyes_level_nose_centered"
    )
    assert context["provider_admission_decision"]["prompt_language_mode"] == (
        "concise_positive_renderer_direction"
    )
    assert result.metadata["llm_brain"]["audit"]["professional_anchor_view_decisions"][0]["capture_scope"] == CAPTURE_SCOPE
    assert result.metadata["llm_brain"]["audit"]["provider_admission_decision_signed"] is True


def test_doc184_adapter_fail_closes_when_provider_admission_receipt_is_missing() -> None:
    class MissingAdmissionProvider(_ScopeEchoProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            for item in payload.get("canonical_provider_prompts", []):
                item.pop("provider_admission_decision", None)
            return payload

    with pytest.raises(BrainProviderAdmissionDecisionMissing):
        V3LLMBrainAdapter(provider=MissingAdmissionProvider()).finalize_canonical_provider_prompts(
            _anchor_request(capture_scope=CAPTURE_SCOPE)
        )


def test_doc184_adapter_rejects_front_prompt_without_pose_normalization() -> None:
    class MissingFrontNormalizationProvider(_ScopeEchoProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            for item in payload.get("canonical_provider_prompts", []):
                item["prompt"] = (
                    "Clean front-facing head-and-upper-shoulders identity reference portrait on a plain white "
                    "studio background, same person, natural camera-observed human materiality."
                )
            return payload

    with pytest.raises(BrainProfessionalAnchorViewDecisionMissing):
        V3LLMBrainAdapter(provider=MissingFrontNormalizationProvider()).finalize_canonical_provider_prompts(
            _anchor_request(capture_scope=CAPTURE_SCOPE)
        )


def test_doc184_adapter_rejects_nonstandard_face_identity_framing() -> None:
    class HalfBodyProvider(_ScopeEchoProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            for item in payload.get("canonical_provider_prompts", []):
                item["prompt"] = (
                    "Clean straight-on front-facing symmetric centered half-body identity reference portrait on a "
                    "plain white studio background, eyes level and nose centered, same person."
                )
            return payload

    with pytest.raises(BrainProfessionalAnchorViewDecisionMissing):
        V3LLMBrainAdapter(provider=HalfBodyProvider()).finalize_canonical_provider_prompts(
            _anchor_request(capture_scope=CAPTURE_SCOPE)
        )


def test_doc184_face_review_does_not_require_pose_but_ordinary_anchor_still_does() -> None:
    from alchemy_creative_agent_3_0.tests.test_v3_doc162_product_anchor_pack_host import _SharedProductService

    service = _SharedProductService()
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    job = service.create_professional_anchor_preparation_job(
        {"user_input": PREPARATION_INTENT},
        view_role="standard_front",
        reference_evidence_ids=["root_doc184"],
    )
    service.generate_job(job.job_id, {})
    service.jobs[job.job_id].generation_result.metadata["post_generation_review_package"]["inspections"][0][
        "score_card"
    ].pop("pose_compliance")
    request = AnchorGenerationRequest(
        project_id="project_doc184",
        people_asset_id="people_doc184",
        pack_version_id="pack_doc184",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent=PREPARATION_INTENT,
        root_source_asset_id="root_doc184",
        reference_evidence_ids=["root_doc184"],
        capture_scope=CAPTURE_SCOPE,
    )
    _, face_review = host._candidate_and_review(job.job_id, request)  # noqa: SLF001
    assert face_review.status == "pass"
    assert "professional_anchor_review_score_incomplete" not in face_review.issue_codes

    ordinary_request = request.model_copy(update={"capture_scope": "anchor_pack"})
    _, ordinary_review = host._candidate_and_review(job.job_id, ordinary_request)  # noqa: SLF001
    assert ordinary_review.status == "fail"
    assert "professional_anchor_review_score_incomplete" in ordinary_review.issue_codes


def test_doc184_face_review_rejects_commercial_clarity_below_bar() -> None:
    from alchemy_creative_agent_3_0.tests.test_v3_doc162_product_anchor_pack_host import _SharedProductService

    service = _SharedProductService()
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    job = service.create_professional_anchor_preparation_job(
        {"user_input": PREPARATION_INTENT},
        view_role="standard_front",
        reference_evidence_ids=["root_doc184"],
    )
    service.generate_job(job.job_id, {})
    inspection = service.jobs[job.job_id].generation_result.metadata[
        "post_generation_review_package"
    ]["inspections"][0]
    inspection["score_card"]["visual_quality"] = 0.95
    inspection["score_card"]["technical_finish"] = 0.95
    request = AnchorGenerationRequest(
        project_id="project_doc184",
        people_asset_id="people_doc184",
        pack_version_id="pack_doc184",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent=PREPARATION_INTENT,
        root_source_asset_id="root_doc184",
        reference_evidence_ids=["root_doc184"],
        capture_scope=CAPTURE_SCOPE,
    )

    _, face_review = host._candidate_and_review(job.job_id, request)  # noqa: SLF001

    assert face_review.status == "fail"
    assert "professional_face_card_commercial_clarity_below_bar" in face_review.issue_codes


def test_doc184_body_silhouette_keeps_its_own_typed_contract() -> None:
    request = BodyPreparationRequest(
        source_class="brain_inferred",
        face_reference_output_ids=["front", "profile", "rear"],
    )
    assert request.reference_output_ids == ["front", "profile", "rear"]
    assert request.observed_truth is False
    assert not hasattr(request, "capture_scope")
