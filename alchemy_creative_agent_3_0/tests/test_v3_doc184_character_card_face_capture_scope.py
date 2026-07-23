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
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _enforced_inspection_prompt,
    active_review_contract,
)
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


def _anchor_request(
    *,
    capture_scope: str | None = None,
    view_role: str = "standard_front",
) -> BrainRunRequest:
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role=view_role,  # type: ignore[arg-type]
        **({"capture_scope": CAPTURE_SCOPE} if capture_scope else {}),
    )
    decision = {
        "required": True,
        "contract_version": "v3_professional_anchor_view_decision_v3",
        "owner": "remote_v3_llm_brain",
        "target_view_role": view_role,
        "capture_presentation": "neutral_identity_evidence_capture",
        "capture_continuity": (
            "establish_neutral_capture"
            if view_role == "standard_front"
            else "preserve_approved_prior_capture"
        ),
        "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
    }
    if capture_scope:
        decision.update(
            {
                "capture_scope": capture_scope,
            }
        )
        if view_role == "standard_front":
            decision.update(
                {
                    "framing_standard": "consistent_head_and_upper_shoulders_reference_crop",
                    "crop_policy": "head_top_margin_full_face_neck_and_upper_shoulders_visible",
                    "torso_scope": "upper_shoulders_only_no_half_body_or_big_head_crop",
                    "aspect_ratio_standard": (
                        "honor_frozen_rendering_size_as_reference_card_aspect_ratio"
                    ),
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
    evidence_capture = face["professional_face_identity_quality_contract"][
        "face_card_evidence_capture_contract"
    ]
    assert evidence_capture["contract_version"] == "v3_character_card_face_evidence_capture_v1"
    assert evidence_capture["capture_objective"] == (
        "standardized_identity_evidence_capture_not_portfolio_or_beauty_portrait"
    )
    assert evidence_capture["pose_observability"] == (
        "balanced_ears_cheeks_shoulders_no_head_turn_or_tilt"
    )
    assert evidence_capture["complexion_semantics"] == (
        "cool_white_or_fair_means_neutral_white_balance_luminous_clean_exposure_not_bleaching"
    )
    assert evidence_capture["commercial_refinement_policy"] == (
        "clean_high_key_commercial_retouch_allowed_without_identity_or_materiality_loss"
    )
    assert evidence_capture["front_pose_tolerance"] == "minor_natural_asymmetry_allowed_but_not_nonfront_view"
    assert evidence_capture["face_view_pose_compliance"] == (
        "pose_compliance_means_requested_face_view_angle_for_character_card_not_full_body_pose"
    )
    assert evidence_capture["aspect_ratio_standard"] == (
        "honor_frozen_rendering_size_as_reference_card_aspect_ratio"
    )
    assert (
        face["professional_face_identity_quality_contract"]["body_silhouette_contract"]
        == "not_applicable_until_body_silhouette_stage"
    )
    assert ordinary["professional_anchor_capture_scope"] == "anchor_pack"
    assert ordinary["professional_face_identity_quality_contract"]["scope"] == "face_identity_anchor_pack"
    assert "geometry_scope" not in ordinary["professional_face_identity_quality_contract"]
    assert "face_card_evidence_capture_contract" not in ordinary[
        "professional_face_identity_quality_contract"
    ]


def test_doc184_character_card_later_stages_keep_professional_quality_contract() -> None:
    expression = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="expression_set",
        slot_key="expression.laugh",
    )
    body = ProfessionalModeRuntimeBridge.character_card_stage_metadata(
        stage="body_silhouette",
        slot_key="body.front_full",
        source_class="user_described",
    )

    assert expression["professional_face_identity_quality_contract"]["scope"] == "character_card_expression_set"
    assert (
        expression["professional_face_identity_quality_contract"]["expression_contract"]
        == "preserve_identity_and_front_card_framing_while_varying_expression_only"
    )
    assert expression["professional_face_identity_quality_contract"]["positive_expression_default"] == "laugh"
    assert (
        expression["professional_face_identity_quality_contract"]["expression_framing_contract"]["baseline"]
        == "active_face_front_winner"
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
    assert schema["professional_anchor_view_decision"]["aspect_ratio_standard"] == (
        "honor_frozen_rendering_size_as_reference_card_aspect_ratio"
    )
    assert (
        schema["professional_anchor_view_decision"]["front_pose_normalization"]
        == "normalize_to_symmetric_camera_facing_front"
    )
    assert "face/head angle only" in payload["remote_response_contract"]
    assert "straight-on, symmetric" in payload["remote_response_contract"]
    assert "no dirty cast, no smear" in payload["remote_response_contract"]
    assert "evidence-grade standardized identity capture" in payload["remote_response_contract"]
    assert "rather than a portfolio, fashion" in payload["remote_response_contract"]
    assert "balanced left/right ear and cheek visibility" in payload["remote_response_contract"]
    assert "plain white matte reference field" in payload["remote_response_contract"]
    assert "neutral white balance, clean exposure and natural fair skin" in payload[
        "remote_response_contract"
    ]
    assert "vertical 2:3 card" in payload["remote_response_contract"]
    assert "full-body portrait" in payload["remote_response_contract"]
    assert "provider_admission_decision" in schema
    assert "concise_positive_renderer_direction" in payload["remote_response_contract"]
    assert "prompt suffix" not in payload["remote_response_contract"].lower()

    ordinary_payload = json.loads(build_remote_payload(_anchor_request()))
    ordinary_schema = ordinary_payload["return_schema"]["canonical_provider_prompts"][0]
    assert "capture_scope" not in ordinary_schema["professional_anchor_view_decision"]
    assert "provider_admission_decision" not in ordinary_schema
    assert "evidence-grade standardized identity capture" not in ordinary_payload[
        "remote_response_contract"
    ]


def test_doc188_anchor_view_recovery_names_required_aspect_fields() -> None:
    request = _anchor_request(capture_scope=CAPTURE_SCOPE)
    recovery_request = request.model_copy(
        update={
            "metadata": {
                **request.metadata,
                "professional_anchor_view_contract_recovery": {
                    "contract_version": "v3_professional_anchor_view_contract_recovery_v1",
                    "attempt": 1,
                    "same_frozen_context": True,
                    "target_view_role": "standard_front",
                    "capture_scope": CAPTURE_SCOPE,
                    "required_receipt_fields": [
                        "capture_scope",
                        "framing_standard",
                        "crop_policy",
                        "torso_scope",
                        "aspect_ratio_standard",
                        "source_viewpoint_inheritance",
                        "front_pose_normalization",
                        "face_axis_alignment",
                    ],
                    "required_prompt_materialization": (
                        "vertical_2_3_reference_card_aspect_language"
                    ),
                },
            }
        },
        deep=True,
    )

    payload = json.loads(build_remote_payload(recovery_request))

    assert payload["professional_anchor_view_contract_recovery"][
        "required_prompt_materialization"
    ] == "vertical_2_3_reference_card_aspect_language"
    assert "required_receipt_fields" in payload["remote_response_contract"]
    assert "vertical 2:3 reference-card aspect language" in payload["remote_response_contract"]
    assert "1024x1536 reference-card composition" in payload["remote_response_contract"]


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
    assert context["professional_anchor_view_decision"]["aspect_ratio_standard"] == (
        "honor_frozen_rendering_size_as_reference_card_aspect_ratio"
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


def test_doc184_adapter_accepts_native_chinese_face_identity_scope_terms() -> None:
    class ChineseScopeProvider(_ScopeEchoProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            for item in payload.get("canonical_provider_prompts", []):
                item["prompt"] = (
                    "商业级干净通透的标准人物角色卡 Face Identity 正面视觉资产。"
                    "主体真正直面镜头，脸部中线垂直、双眼水平、鼻梁居中；"
                    "竖版2:3标准参考卡，"
                    "固定为头部、颈部和上肩景别，头顶留有适度边距，完整脸部、颈部和上肩清晰可见。"
                    "明亮洁净白底影棚，真实摄影质感。"
                )
            return payload

    prompts, audit = V3LLMBrainAdapter(provider=ChineseScopeProvider()).finalize_canonical_provider_prompts(
        _anchor_request(capture_scope=CAPTURE_SCOPE)
    )

    assert prompts[0].prompt.startswith("商业级干净通透")
    assert audit["professional_anchor_prompt_scope_checked"] is True


def test_doc189_adapter_accepts_native_chinese_three_quarter_face_slot_terms() -> None:
    class ChineseThreeQuarterProvider(_ScopeEchoProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            for item in payload.get("canonical_provider_prompts", []):
                item["prompt"] = (
                    "竖版2:3标准人物角色卡，左前45度头颈上肩景别。"
                    "同一名六岁女童，沿用已通过正面参考卡的商业精修白底质感，"
                    "以已通过 left_front_25 的 25-degree transition 作为过渡，形成自然左前45度家族视角，"
                    "左耳在画面左侧可见，鼻尖朝画面右侧，"
                    "不能接近正脸，鼻梁偏移，有侧脸深度，脸颊后退，远侧眼更小，视线随鼻尖方向，不直视镜头，只露近侧耳，远近眼不同但双眼仍可见，"
                    "允许自然角度浮动，只拦截明显正脸、纯侧面、背面或方向错位，"
                    "保持与正面卡同一相机距离和同一头部比例，眼线高度、下巴线、领口线高度和画面底部截断一致，"
                    "头部周围发丝轮廓完整、头顶留白、颈部、上肩和衣领线可见，长发可在上肩下方自然裁切，"
                    "不是大头近景，不是半身，不要放大，头发边缘清晰不要柔焦。冷白皮为中性白平衡和干净曝光，"
                    "真实相机质感，无塑料磨皮，无场景和道具。"
                )
                item["professional_anchor_view_decision"] = {
                    **item["professional_anchor_view_decision"],
                    "target_view_role": "three_quarter",
                    "capture_continuity": "preserve_approved_prior_capture",
                }
            return payload

    prompts, audit = V3LLMBrainAdapter(provider=ChineseThreeQuarterProvider()).finalize_canonical_provider_prompts(
        _anchor_request(capture_scope=CAPTURE_SCOPE, view_role="three_quarter")
    )

    assert "左前45度" in prompts[0].prompt
    assert audit["professional_anchor_prompt_scope_checked"] is True


def test_doc190_adapter_rejects_three_quarter_without_fixed_left_side_and_scale() -> None:
    class WeakThreeQuarterProvider(_ScopeEchoProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            for item in payload.get("canonical_provider_prompts", []):
                item["prompt"] = (
                    "Generic three-quarter 45-degree portrait of the same child, head and shoulders, "
                    "plain white background, neutral expression."
                )
                item["professional_anchor_view_decision"] = {
                    **item["professional_anchor_view_decision"],
                    "target_view_role": "three_quarter",
                    "capture_continuity": "preserve_approved_prior_capture",
                }
            return payload

    with pytest.raises(BrainProfessionalAnchorViewDecisionMissing):
        V3LLMBrainAdapter(provider=WeakThreeQuarterProvider()).finalize_canonical_provider_prompts(
            _anchor_request(capture_scope=CAPTURE_SCOPE, view_role="three_quarter")
        )


def test_doc193_adapter_accepts_left_front_prompt_without_ear_nose_recipe() -> None:
    class CompactLeftProvider(_ScopeEchoProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            for item in payload.get("canonical_provider_prompts", []):
                item["prompt"] = (
                    "Vertical 2:3 standard character card, left-front 45-degree head-and-upper-shoulders portrait. "
                    "Same child, same camera distance and head size, same vertical crop boundaries, face-card scale "
                    "and shoulder-line padding, complete head-and-hair silhouette, similar head-top margin, full face, "
                    "neck, upper shoulders and collar line visible, crop ends just below the upper shoulders. "
                    "Not a tight face close-up, not a half-body crop, no zooming in, no faded hair boundary."
                )
                item["professional_anchor_view_decision"] = {
                    **item["professional_anchor_view_decision"],
                    "target_view_role": "three_quarter",
                    "capture_continuity": "preserve_approved_prior_capture",
                }
            return payload

    prompts, audit = V3LLMBrainAdapter(provider=CompactLeftProvider()).finalize_canonical_provider_prompts(
        _anchor_request(capture_scope=CAPTURE_SCOPE, view_role="three_quarter")
    )

    assert "left-front 45-degree" in prompts[0].prompt
    assert audit["professional_anchor_prompt_scope_checked"] is True


def test_doc190_adapter_rejects_ambiguous_reverse_three_quarter_face_slot_prompt() -> None:
    class WeakReverseProvider(_ScopeEchoProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            for item in payload.get("canonical_provider_prompts", []):
                item["prompt"] = (
                    "Reverse three-quarter view portrait of a 6-year-old girl, head and upper shoulders, "
                    "against a clean white studio background, soft even lighting, neutral expression."
                )
                item["professional_anchor_view_decision"] = {
                    **item["professional_anchor_view_decision"],
                    "target_view_role": "reverse_three_quarter",
                    "capture_continuity": "preserve_approved_prior_capture",
                }
            return payload

    with pytest.raises(BrainProfessionalAnchorViewDecisionMissing):
        V3LLMBrainAdapter(provider=WeakReverseProvider()).finalize_canonical_provider_prompts(
            _anchor_request(capture_scope=CAPTURE_SCOPE, view_role="reverse_three_quarter")
        )


def test_doc190_adapter_rejects_reverse_three_quarter_when_it_means_rear_head() -> None:
    class ChineseRearReverseProvider(_ScopeEchoProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            for item in payload.get("canonical_provider_prompts", []):
                item["prompt"] = (
                    "竖版2:3标准人物角色卡，背后三分之四头颈上肩景别。"
                    "后脑为主，脸部大部分背向镜头，只露少量侧脸边缘，不回头看镜头，"
                    "白底明亮影棚，真实相机肤质和自然发丝。"
                )
                item["professional_anchor_view_decision"] = {
                    **item["professional_anchor_view_decision"],
                    "target_view_role": "reverse_three_quarter",
                    "capture_continuity": "preserve_approved_prior_capture",
                }
            return payload

    with pytest.raises(BrainProfessionalAnchorViewDecisionMissing):
        V3LLMBrainAdapter(provider=ChineseRearReverseProvider()).finalize_canonical_provider_prompts(
            _anchor_request(capture_scope=CAPTURE_SCOPE, view_role="reverse_three_quarter")
        )


def test_doc190_adapter_accepts_reverse_three_quarter_as_opposite_front_45_slot() -> None:
    class ChineseOppositeFrontProvider(_ScopeEchoProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            for item in payload.get("canonical_provider_prompts", []):
                item["prompt"] = (
                    "竖版2:3标准人物角色卡，反侧前方右前45度头颈上肩景别。"
                    "Reference role map: input 1 is root identity geometry, input 2 is front identity detail, input 3 is front full-frame card framing, input 4 is the approved 90-degree side profile and is the primary pose-depth guide, input 5 is the approved right_front_25 transition and is only the right-side identity/framing bridge. "
                    "同一名六岁女童，脸部仍然可见，是独立的另一侧前方建模照，"
                    "以已通过 right_front_25 的 25-degree transition 只作为过渡身份桥，形成自然右前45度家族视角，independent opposite-side，不是水平翻转，"
                    "右耳在画面右侧可见，鼻尖朝画面左侧，避免和左前45度同侧重复，"
                    "不能接近正脸，鼻梁偏移，有侧脸深度，脸颊后退，远侧眼更小，视线随鼻尖方向，不直视镜头，只露近侧耳，远近眼不同但双眼仍可见，"
                    "允许自然角度浮动，只拦截明显正脸、纯侧面、背面、镜像或方向错位，"
                    "景别匹配已通过正面卡片家族的头部大小和肩颈范围，眼线高度、下巴线、领口线高度和画面底部截断一致，"
                    "保持与正面卡同一相机距离和同一头部比例，头部周围发丝轮廓完整、头顶留白、颈部、上肩和衣领线可见，长发可在上肩下方自然裁切，"
                    "不是大头近景，不是半身，不要放大，头发边缘清晰不要柔焦。"
                    "白底明亮影棚，真实相机肤质和自然发丝。"
                )
                item["professional_anchor_view_decision"] = {
                    **item["professional_anchor_view_decision"],
                    "target_view_role": "reverse_three_quarter",
                    "capture_continuity": "preserve_approved_prior_capture",
                }
            return payload

    prompts, audit = V3LLMBrainAdapter(
        provider=ChineseOppositeFrontProvider()
    ).finalize_canonical_provider_prompts(
        _anchor_request(capture_scope=CAPTURE_SCOPE, view_role="reverse_three_quarter")
    )

    assert "右前45度" in prompts[0].prompt
    assert "右耳在画面右侧" in prompts[0].prompt
    assert audit["professional_anchor_prompt_scope_checked"] is True


def test_doc189_nonfront_character_card_payload_uses_reference_led_view_delta_language() -> None:
    payload = json.loads(build_remote_payload(
        _anchor_request(capture_scope=CAPTURE_SCOPE, view_role="three_quarter")
    ))

    contract = payload["remote_response_contract"]
    schema = payload["return_schema"]["canonical_provider_prompts"][0][
        "professional_anchor_view_decision"
    ]
    assert "change only the frozen view angle" in contract
    assert "Do not restate straight-on symmetry" in contract
    assert "match the approved front/card-family vertical 2:3" in contract
    assert "For visible turning slots" in contract
    assert "allow natural face-box changes caused by head rotation" in contract
    assert "not by matching another angle's face rectangle" in contract
    assert "Do not turn this into a checklist" in contract
    assert "full card framing" in contract
    assert "avoid close-up" in contract
    assert "For three_quarter, produce the left-front 45-family face card" in contract
    assert "For the standard_front slot" not in contract
    assert "face midline vertical" not in contract
    assert "Always return the exact frozen aspect-ratio standard field" not in contract
    assert "framing_standard" not in schema
    assert "aspect_ratio_standard" not in schema


def test_doc184_adapter_rejects_native_chinese_face_identity_scope_leak() -> None:
    class ChineseHalfBodyProvider(_ScopeEchoProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            for item in payload.get("canonical_provider_prompts", []):
                item["prompt"] = (
                    "标准正面角色卡，真正直面镜头，脸部中线垂直、双眼水平、鼻梁居中，"
                    "但画面是半身照并站在花园户外场景中。"
                )
            return payload

    with pytest.raises(BrainProfessionalAnchorViewDecisionMissing):
        V3LLMBrainAdapter(provider=ChineseHalfBodyProvider()).finalize_canonical_provider_prompts(
            _anchor_request(capture_scope=CAPTURE_SCOPE)
        )


def test_doc190_face_review_requires_view_pose_compliance_score() -> None:
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
    assert face_review.status == "fail"
    assert "professional_anchor_review_score_incomplete" in face_review.issue_codes

    ordinary_request = request.model_copy(update={"capture_scope": "anchor_pack"})
    _, ordinary_review = host._candidate_and_review(job.job_id, ordinary_request)  # noqa: SLF001
    assert ordinary_review.status == "fail"
    assert "professional_anchor_review_score_incomplete" in ordinary_review.issue_codes


def test_doc190_face_review_rejects_view_angle_pose_below_bar() -> None:
    from alchemy_creative_agent_3_0.tests.test_v3_doc162_product_anchor_pack_host import _SharedProductService

    service = _SharedProductService()
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    job = service.create_professional_anchor_preparation_job(
        {"user_input": PREPARATION_INTENT},
        view_role="three_quarter",
        reference_evidence_ids=["root_doc184", "front_doc184", "left25_doc184"],
        capture_scope=CAPTURE_SCOPE,
    )
    service.generate_job(job.job_id, {})
    inspection = service.jobs[job.job_id].generation_result.metadata[
        "post_generation_review_package"
    ]["inspections"][0]
    inspection["score_card"]["pose_compliance"] = 0.72
    request = AnchorGenerationRequest(
        project_id="project_doc184",
        people_asset_id="people_doc184",
        pack_version_id="pack_doc184",
        view_role="three_quarter",
        candidate_index=1,
        preparation_intent=PREPARATION_INTENT,
        root_source_asset_id="root_doc184",
        reference_evidence_ids=["root_doc184", "front_doc184", "left25_doc184"],
        capture_scope=CAPTURE_SCOPE,
    )

    _, face_review = host._candidate_and_review(job.job_id, request)  # noqa: SLF001

    assert face_review.status == "fail"
    assert "professional_face_card_view_angle_below_bar" in face_review.issue_codes


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
    inspection["score_card"]["visual_quality"] = 0.89
    inspection["score_card"]["technical_finish"] = 0.87
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


def test_doc189_face_review_accepts_commercial_refined_identity_card() -> None:
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
    inspection["status"] = "warning"
    inspection["issue_codes"] = ["human_skin_or_retouch"]
    inspection["score_card"].update(
        {
            "same_person_readability": 0.90,
            "distinctive_feature_readability": 0.80,
            "developmental_age_coherence": 0.90,
            "prompt_owned_channel_obedience": 0.82,
            "neutral_capture_compliance": 0.86,
            "visual_quality": 0.90,
            "technical_finish": 0.88,
            "human_realism": 0.83,
            "ai_overperfection_penalty": 0.18,
        }
    )
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
    assert "professional_face_card_commercial_clarity_below_bar" not in face_review.issue_codes
    assert "professional_face_card_identity_evidence_below_bar" not in face_review.issue_codes


def test_doc189_face_review_rejects_polished_but_identity_weak_card() -> None:
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
    inspection["score_card"].update(
        {
            "same_person_readability": 0.86,
            "distinctive_feature_readability": 0.74,
            "visual_quality": 0.98,
            "technical_finish": 0.98,
            "human_realism": 0.94,
        }
    )
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
    assert "professional_face_card_identity_evidence_below_bar" in face_review.issue_codes


def test_doc189_review_contract_calibrates_commercial_refined_realism() -> None:
    metadata = {
        "professional_planning_metadata": ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
            view_role="standard_front",
            capture_scope=CAPTURE_SCOPE,
        ),
        "capability_execution_envelope": {
            "activation_plan": {
                "activation_mode": "enforced",
                "metadata": ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
                    view_role="standard_front",
                    capture_scope=CAPTURE_SCOPE,
                ),
            },
            "resolved_constraint_ledger": {
                "provider_projection": {"composed_visual_contribution": {}},
                "review_contracts": [],
                "hard_semantic_contract": True,
            },
        },
    }
    contract = active_review_contract(metadata)
    prompt = _enforced_inspection_prompt(
        user_goal=PREPARATION_INTENT,
        template_id="professional_character_card",
        reference_policy={},
        reference_count=2,
        feedback_contract={"applies": False},
        review_contract=contract,
        apparel_contract={"applies": False},
        output_evidence={},
        serial_anchor_review={},
    )

    assert contract["professional_identity_quality"]["commercial_refinement_policy"] == (
        "clean_high_key_commercial_retouch_allowed_without_identity_or_materiality_loss"
    )
    assert contract["professional_identity_quality"]["face_view_pose_compliance"] == (
        "pose_compliance_means_requested_face_view_angle_for_character_card_not_full_body_pose"
    )
    assert "commercial-refined realism calibration" in prompt
    assert "Do not fail merely because skin is clean, bright, fair, or commercially refined" in prompt
    assert "pose_compliance means head-view slot geometry" in prompt
    assert "angle labels are visual modeling targets rather than exact protractor measurements" in prompt
    assert "three_quarter should read as a usable left/front-side three-quarter head view around the 45-degree family" in prompt
    assert "profile as a clear approximately 90-degree" in prompt
    assert "same camera distance and head size" in prompt
    assert "tight face/head close-ups" in prompt
    assert "rear_head must instead keep a clear back-of-head hair outline" in prompt


def test_doc184_body_silhouette_keeps_its_own_typed_contract() -> None:
    request = BodyPreparationRequest(
        source_class="brain_inferred",
        face_reference_output_ids=["front", "profile", "rear"],
    )
    assert request.reference_output_ids == ["front", "profile", "rear"]
    assert request.observed_truth is False
    assert not hasattr(request, "capture_scope")
