"""Doc248 absolute portrait realism hot-plug Enhanced module contracts."""

from __future__ import annotations

import inspect
import ast
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.absolute_portrait_realism import (
    ABSOLUTE_PORTRAIT_REALISM_PROFILE_ID,
    REQUIRED_REALISM_DIMENSIONS,
    AbsolutePortraitRealismProof,
    evaluate_absolute_portrait_realism,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import (
    AnchorCandidateUnavailable,
    AnchorCandidateResult,
    AnchorGenerationRequest,
    AnchorPackPreparationResult,
    AnchorPackPreparationService,
    AnchorReviewDecision,
    _absolute_portrait_realism_enhanced_proof_summary,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import IdentityScoreSummary
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import ProductApiAnchorPackPreparationHost
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.visual_assets.contracts import (
    FaceIdentityModule,
    IdentityAnchorPackVersion,
    PeopleAsset,
    RootSourceProvenance,
)
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    LibraryRootSourceProvenance,
    VisualAsset,
    VisualAssetLibraryLifecycleService,
)
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    active_review_contract,
)


def _passing_dimensions() -> dict[str, float]:
    return {
        "eye_gaze_alignment": 0.91,
        "facial_micro_asymmetry": 0.84,
        "skin_micro_texture": 0.88,
        "hair_strand_randomness": 0.86,
        "ear_anatomy_clarity": 0.8,
        "natural_light_transition": 0.9,
        "camera_texture_response": 0.83,
        "commercial_beauty_preserved": 0.92,
    }


def _proof(**overrides: object) -> AbsolutePortraitRealismProof:
    payload = {
        "candidate_id": "candidate_front_1",
        "output_id": "v3_output_front_1",
        "dimensions": _passing_dimensions(),
        "evidence_codes": [
            "real_photo_eye_hair_skin_ear_light_verified",
            "commercial_beauty_preserved",
        ],
    }
    payload.update(overrides)
    return evaluate_absolute_portrait_realism(**payload)  # type: ignore[arg-type]


def test_doc248_passing_realism_proof_projects_to_formal_enhanced_proof() -> None:
    proof = _proof()
    enhanced = _absolute_portrait_realism_enhanced_proof_summary(proof)

    assert proof.eligible is True
    assert proof.status == "pass"
    assert enhanced.profile_id == ABSOLUTE_PORTRAIT_REALISM_PROFILE_ID
    assert enhanced.requirement_id == "absolute_portrait_realism_visible_evidence_v1"
    assert enhanced.candidate_id == "candidate_front_1"
    assert enhanced.output_id == "v3_output_front_1"
    assert enhanced.eligible is True
    assert set(REQUIRED_REALISM_DIMENSIONS) <= set(enhanced.dimensions)


@pytest.mark.parametrize(
    "missing_dimension",
    [
        "eye_gaze_alignment",
        "skin_micro_texture",
        "hair_strand_randomness",
        "ear_anatomy_clarity",
        "commercial_beauty_preserved",
    ],
)
def test_doc248_missing_visible_realism_dimension_fails_closed(missing_dimension: str) -> None:
    dimensions = _passing_dimensions()
    dimensions.pop(missing_dimension)

    proof = _proof(dimensions=dimensions)

    assert proof.eligible is False
    assert proof.status == "fail"
    assert "absolute_portrait_realism_evidence_missing" in proof.issue_codes
    enhanced = _absolute_portrait_realism_enhanced_proof_summary(proof)
    assert enhanced.eligible is False


@pytest.mark.parametrize(
    ("dimension", "issue"),
    [
        ("eye_gaze_alignment", "eye_gaze_or_perspective_inconsistent"),
        ("skin_micro_texture", "poreless_plastic_skin"),
        ("hair_strand_randomness", "pasted_or_over_regular_hair"),
        ("ear_anatomy_clarity", "simplified_ear_anatomy"),
    ],
)
def test_doc248_ai_face_artifact_dimensions_fail_without_lowering_gate(dimension: str, issue: str) -> None:
    dimensions = _passing_dimensions()
    dimensions[dimension] = 0.34

    proof = _proof(dimensions=dimensions, issue_codes=[issue])

    assert proof.eligible is False
    assert "absolute_portrait_realism_dimension_below_target" in proof.issue_codes
    assert issue in proof.issue_codes


@pytest.mark.parametrize(
    "issue",
    [
        "compression_noise_used_as_realism",
        "random_grain_used_as_realism",
        "blur_used_as_realism",
        "dirty_skin_used_as_realism",
        "beauty_degraded_for_realism",
        "identity_geometry_redesigned",
    ],
)
def test_doc248_fake_realism_degradation_strategy_is_rejected(issue: str) -> None:
    proof = _proof(issue_codes=[issue])

    assert proof.eligible is False
    assert "realism_degradation_strategy_rejected" in proof.issue_codes


def test_doc248_beauty_preservation_is_hard_requirement() -> None:
    dimensions = _passing_dimensions()
    dimensions["commercial_beauty_preserved"] = 0.62

    proof = _proof(dimensions=dimensions)

    assert proof.eligible is False
    assert "commercial_beauty_not_preserved" in proof.issue_codes


def test_doc248_public_summary_is_safe_and_stable() -> None:
    proof = _proof()
    summary = proof.public_summary()
    reloaded = AbsolutePortraitRealismProof.model_validate(proof.model_dump(mode="json"))

    assert reloaded == proof
    assert summary["eligible"] is True
    serialized = str(summary).lower()
    for forbidden in ("prompt", "provider", "mcp", "handoff", "artifact", "path", "raw", "api_key"):
        assert forbidden not in serialized


def test_doc248_private_or_malformed_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AbsolutePortraitRealismProof(
            candidate_id="candidate_1",
            output_id="output_1",
            status="pass",
            eligible=True,
            evidence_codes=["realism_verified"],
            dimensions={**_passing_dimensions(), "provider_raw_score": 0.9},
        )
    with pytest.raises(ValidationError):
        AbsolutePortraitRealismProof(
            candidate_id="candidate_1",
            output_id="output_1",
            status="pass",
            eligible=False,
            evidence_codes=["realism_verified"],
            dimensions=_passing_dimensions(),
        )


def test_doc248_empty_evidence_is_not_backfilled_as_reviewed() -> None:
    with pytest.raises(ValidationError):
        evaluate_absolute_portrait_realism(
            candidate_id="candidate_1",
            output_id="output_1",
            dimensions=_passing_dimensions(),
            evidence_codes=[],
        )


def test_doc248_required_dimensions_cannot_be_narrowed() -> None:
    narrowed = [dimension for dimension in REQUIRED_REALISM_DIMENSIONS if dimension != "ear_anatomy_clarity"]
    with pytest.raises(ValidationError):
        evaluate_absolute_portrait_realism(
            candidate_id="candidate_1",
            output_id="output_1",
            dimensions=_passing_dimensions(),
            evidence_codes=["absolute_portrait_realism_reviewed"],
            required_dimensions=narrowed,
        )


def test_doc248_policy_thresholds_and_finite_scores_are_fail_closed() -> None:
    with pytest.raises(ValidationError):
        evaluate_absolute_portrait_realism(
            candidate_id="candidate_1",
            output_id="output_1",
            dimensions=_passing_dimensions(),
            evidence_codes=["absolute_portrait_realism_reviewed"],
            minimum_dimension_score=0.1,
        )
    dimensions = _passing_dimensions()
    dimensions["skin_micro_texture"] = float("nan")
    with pytest.raises(ValueError):
        evaluate_absolute_portrait_realism(
            candidate_id="candidate_1",
            output_id="output_1",
            dimensions=dimensions,
            evidence_codes=["absolute_portrait_realism_reviewed"],
        )


def test_doc248_module_does_not_import_provider_mcp_route_or_formal_core() -> None:
    import alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.absolute_portrait_realism as module

    tree = ast.parse(inspect.getsource(module))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name.lower() for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(str(node.module or "").lower())

    for forbidden in ("formal_slot_acceptancecore", "product_api", "provider", "mcp", "route_handlers"):
        assert all(forbidden not in module_name for module_name in imported)

    source = inspect.getsource(module).lower()
    for forbidden_objective in ("undetectable", "detector evasion", "bypass detector"):
        assert forbidden_objective not in source


def test_doc248_module_is_slot_agnostic_and_hot_pluggable() -> None:
    proof = evaluate_absolute_portrait_realism(
        candidate_id="candidate_any_module",
        output_id="output_any_module",
        dimensions=_passing_dimensions(),
        evidence_codes=["real_photo_detail_review_verified"],
    )
    enhanced = _absolute_portrait_realism_enhanced_proof_summary(proof)

    assert enhanced.profile_id == "absolute_portrait_realism_v1"
    assert enhanced.owner == "v3_professional_enhanced_profile_contract"
    dumped = enhanced.model_dump(mode="json")
    assert "module" not in dumped
    assert "slot_key" not in dumped


def _shared_receipt() -> dict[str, object]:
    return {
        "owner": "v3_shared_visual_cluster",
        "contract_version": "v3_character_card_generic_slot_review_receipt_v1",
        "status": "pass",
        "evidence_codes": ["shared_visual_review_verified"],
        "issue_codes": [],
        "score_dimensions": ["generic_visual_quality"],
        "framing_delta_dimensions": ["front_card_framing"],
    }


def _anchor_candidate(index: int) -> AnchorCandidateResult:
    return AnchorCandidateResult(
        candidate_id=f"candidate_front_{index}",
        view_id=f"view_front_{index}",
        output_id=f"v3_output_front_{index}",
        view_role="standard_front",
        candidate_index=index,
        source_candidate_ids=[f"candidate_front_{index}"],
        source_asset_ids=["source_original"],
        brain_plan_id=f"brain_plan_{index}",
        canonical_prompt_hash=f"prompt_hash_{index}",
        prompt_compilation_id=f"prompt_compilation_{index}",
        prompt_reference_parity_verified=True,
    )


def _anchor_review(
    index: int,
    *,
    complete_absolute_evidence: bool,
    same_face_score: float,
) -> AnchorReviewDecision:
    evidence_codes = ["face_identity_shared_identity_review_verified"]
    if complete_absolute_evidence:
        evidence_codes.extend(
            [
                "absolute_eye_gaze_alignment_verified",
                "absolute_facial_micro_asymmetry_verified",
                "absolute_skin_micro_texture_verified",
                "absolute_hair_strand_randomness_verified",
                "absolute_ear_anatomy_clarity_verified",
                "absolute_natural_light_transition_verified",
                "absolute_camera_texture_response_verified",
                "absolute_commercial_beauty_preserved",
            ]
        )
    return AnchorReviewDecision(
        status="pass",
        identity_scores=IdentityScoreSummary(
            same_face_score=same_face_score,
            distinctive_feature_score=same_face_score,
            human_realism_score=0.92 if complete_absolute_evidence else 0.99,
            visual_quality_score=0.93,
            pose_compliance_score=0.91,
            evidence_codes=evidence_codes,
        ),
        shared_review_receipts=[_shared_receipt()],
    )


def test_doc248_face_front_opt_in_filters_winner_by_absolute_realism_proof() -> None:
    service = AnchorPackPreparationService(generator=object(), reviewer=object())
    attempts = [
        (_anchor_candidate(1), _anchor_review(1, complete_absolute_evidence=True, same_face_score=0.83)),
        # Highest identity score, but missing absolute-realism proof; it must not win.
        (_anchor_candidate(2), _anchor_review(2, complete_absolute_evidence=False, same_face_score=0.99)),
        (_anchor_candidate(3), _anchor_review(3, complete_absolute_evidence=True, same_face_score=0.88)),
    ]

    receipt = service._formal_receipt_for_attempts(  # noqa: SLF001
        view_role="standard_front",
        attempts=attempts,
        acceptance_mode="standard_three_candidate",
        absolute_portrait_realism_required=True,
    )

    assert receipt.candidate_eligibility_required is True
    assert receipt.winner_candidate_id == "candidate_front_3"
    assert receipt.candidates[1].enhanced_proof is not None
    assert receipt.candidates[1].enhanced_proof.eligible is False
    assert receipt.candidates[2].enhanced_proof is not None
    assert receipt.candidates[2].enhanced_proof.profile_id == "absolute_portrait_realism_v1"


def test_doc248_face_front_without_opt_in_preserves_existing_formal_selection() -> None:
    service = AnchorPackPreparationService(generator=object(), reviewer=object())
    attempts = [
        (_anchor_candidate(1), _anchor_review(1, complete_absolute_evidence=True, same_face_score=0.83)),
        (_anchor_candidate(2), _anchor_review(2, complete_absolute_evidence=False, same_face_score=0.99)),
        (_anchor_candidate(3), _anchor_review(3, complete_absolute_evidence=True, same_face_score=0.88)),
    ]

    receipt = service._formal_receipt_for_attempts(  # noqa: SLF001
        view_role="standard_front",
        attempts=attempts,
        acceptance_mode="standard_three_candidate",
    )

    assert receipt.candidate_eligibility_required is False
    assert receipt.winner_candidate_id == "candidate_front_2"
    assert all(candidate.enhanced_proof is None for candidate in receipt.candidates)


def test_doc248_absolute_realism_opt_in_does_not_apply_to_auxiliary_bridge() -> None:
    service = AnchorPackPreparationService(generator=object(), reviewer=object())
    attempts = [(_anchor_candidate(1), _anchor_review(1, complete_absolute_evidence=False, same_face_score=0.99))]

    receipt = service._formal_receipt_for_attempts(  # noqa: SLF001
        view_role="left_front_25",
        attempts=attempts,
        acceptance_mode="auxiliary_first_pass_reference",
        absolute_portrait_realism_required=True,
    )

    assert receipt.acceptance_mode == "auxiliary_first_pass_reference"
    assert receipt.candidate_eligibility_required is False
    assert receipt.candidates[0].enhanced_proof is None


def test_doc248_product_host_threads_absolute_realism_flag_into_face_request() -> None:
    host = ProductApiAnchorPackPreparationHost(V3ProductApiService())

    class _FakeOrchestrator:
        def __init__(self) -> None:
            self.request = None

        def prepare(self, request, *, resume_from_pack=None):  # noqa: ANN001, ANN201
            self.request = request
            return SimpleNamespace(status="blocked")

    fake = _FakeOrchestrator()
    host._orchestrator = fake  # noqa: SLF001
    people_asset = PeopleAsset(
        people_asset_id="asset_absolute_realism",
        project_id="project_absolute_realism",
        subject_kind="human_person",
        face_identity_module=FaceIdentityModule(
            module_id="face_asset_absolute_realism",
            people_asset_id="asset_absolute_realism",
            status="draft",
        ),
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id="source_original",
            project_id="project_absolute_realism",
        ),
        preparation_intent="character_card",
        status="draft",
    )

    host.prepare_character_card(
        project_id="project_absolute_realism",
        people_asset=people_asset,
        root_source_provenance=people_asset.root_source_provenance,
        absolute_portrait_realism_required=True,
    )

    assert fake.request is not None
    assert fake.request.face_view_scope == "character_card"
    assert fake.request.absolute_portrait_realism_required is True


def _library_asset_for_absolute_realism() -> VisualAsset:
    return VisualAsset(
        visual_asset_id="asset_absolute_realism",
        asset_type="people",
        display_name="Absolute Realism Test",
        owner_scope="local_default",
        root_source_provenance=LibraryRootSourceProvenance(
            source_asset_id="source_original",
            consent_reference="user-confirmed-source",
            supplementary_source_asset_ids=["source_supplemental"],
        ),
        preparation_intent="character card front identity",
        created_at="2026-07-25T00:00:00Z",
        updated_at="2026-07-25T00:00:00Z",
    )


def _failed_pack_for_asset(people_asset: PeopleAsset) -> IdentityAnchorPackVersion:
    return IdentityAnchorPackVersion(
        pack_version_id="pack_absolute_realism_failed",
        people_asset_id=people_asset.people_asset_id,
        status="failed",
        root_source_provenance=people_asset.root_source_provenance,
    )


def test_doc248_absolute_realism_inherits_generation_channel_without_special_mcp_default() -> None:
    captured: list[dict[str, object]] = []
    asset = _library_asset_for_absolute_realism()

    class _Catalog:
        def get(self, *, owner_scope: str, visual_asset_id: str):  # noqa: ANN001, ANN201
            assert owner_scope == "local_default"
            assert visual_asset_id == asset.visual_asset_id
            return asset

        def save(self, asset_to_save):  # noqa: ANN001, ANN201
            return asset_to_save

    class _Host:
        def prepare_character_card(self, **kwargs):  # noqa: ANN001, ANN201
            captured.append(dict(kwargs))
            return AnchorPackPreparationResult(
                status="blocked",
                pack=_failed_pack_for_asset(kwargs["people_asset"]),
                failure_codes=["synthetic_block"],
            )

    lifecycle = VisualAssetLibraryLifecycleService(_Catalog(), anchor_pack_host=_Host())  # type: ignore[arg-type]

    lifecycle.prepare_character_card_face(
        owner_scope="local_default",
        visual_asset_id=asset.visual_asset_id,
        absolute_portrait_realism_required=True,
        generation_channel="provider",
    )
    lifecycle.prepare_character_card_face(
        owner_scope="local_default",
        visual_asset_id=asset.visual_asset_id,
        absolute_portrait_realism_required=True,
        generation_channel="mcp",
    )

    assert captured[0]["absolute_portrait_realism_required"] is True
    assert "generation_channel" not in captured[0]
    assert captured[1]["absolute_portrait_realism_required"] is True
    assert captured[1]["generation_channel"] == "mcp"


def test_doc248_public_route_rejects_user_supplied_absolute_realism_flag() -> None:
    handlers = V3ProductRouteHandlers(service=V3ProductApiService())

    with pytest.raises(ValueError, match="character_card_stage_payload_invalid"):
        handlers.post_visual_asset_character_card_prepare(
            "asset_absolute_realism",
            {"stage": "face_identity", "absolute_portrait_realism_required": True},
        )


def test_doc248_ordinary_job_metadata_cannot_forge_absolute_realism_flag() -> None:
    service = V3ProductApiService()

    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        service.create_job(
            {
                "user_input": "Create a realistic portrait.",
                "scenario_selection": {"scenario_id": "general_creative"},
                "metadata": {
                    "requested_image_count": 1,
                    "professional_absolute_portrait_realism_required": True,
                    "professional_absolute_portrait_realism_provenance": "server_feature_flag_v1",
                },
            }
        )


def test_doc248_host_writes_absolute_realism_trusted_provenance_only_for_standard_front() -> None:
    captured: list[dict[str, object]] = []

    class _FakeService:
        visual_asset_catalog = None

        def create_professional_anchor_preparation_job(self, request, **kwargs):  # noqa: ANN001, ANN201
            captured.append(dict(request["metadata"]))
            return SimpleNamespace(job_id="job_blocked", status=ProductJobStatusValue.BLOCKED)

        def get_job_record(self, job_id: str):  # noqa: ANN001, ANN201
            return SimpleNamespace(request=SimpleNamespace(metadata={}))

    host = ProductApiAnchorPackPreparationHost(_FakeService())  # type: ignore[arg-type]

    front_request = AnchorGenerationRequest(
        project_id="project_absolute_realism",
        people_asset_id="asset_absolute_realism",
        pack_version_id="pack_absolute_realism",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent="character card front identity",
        root_source_asset_id="source_original",
        reference_evidence_ids=["source_original", "source_supplemental"],
        initial_supplementary_source_asset_ids=["source_supplemental"],
        absolute_portrait_realism_required=True,
        capture_scope="character_card_face_identity",
    )
    bridge_request = AnchorGenerationRequest(
        project_id="project_absolute_realism",
        people_asset_id="asset_absolute_realism",
        pack_version_id="pack_absolute_realism",
        view_role="left_front_25",
        candidate_index=1,
        preparation_intent="character card bridge",
        root_source_asset_id="source_original",
        reference_evidence_ids=["source_original", "front_output"],
        initial_supplementary_source_asset_ids=[],
        absolute_portrait_realism_required=True,
        capture_scope="character_card_face_identity",
    )

    with pytest.raises(AnchorCandidateUnavailable):
        host.generate(front_request)
    with pytest.raises(AnchorCandidateUnavailable):
        host.generate(bridge_request)

    assert captured[0]["professional_absolute_portrait_realism_required"] is True
    assert captured[0]["professional_absolute_portrait_realism_provenance"] == "server_feature_flag_v1"
    assert "professional_absolute_portrait_realism_required" not in captured[1]
    assert "professional_absolute_portrait_realism_provenance" not in captured[1]


def test_doc248_face_host_projects_canonical_generic_shared_receipt_for_formal_core() -> None:
    class _FakeOutputStore:
        def list_by_job(self, job_id: str):  # noqa: ANN001, ANN201
            assert job_id == "job_front_absolute"
            return [
                SimpleNamespace(
                    output_id="v3_output_front_absolute",
                    candidate_id="candidate_front_absolute",
                    metadata={
                        "provider_prompt_sha256": "prompt_hash_front_absolute",
                        "prompt_compilation_id": "prompt_compilation_front_absolute",
                        "provider_reference_image_count": 2,
                        "provider_reference_assets": [
                            {
                                "provider_reference_derivative": True,
                                "identity_evidence_scope": "feature_detail",
                                "identity_face_localization_applied": True,
                                "identity_face_localization_status": "detected",
                                "identity_nonidentity_pixel_suppression_profile": (
                                    "face_localized_nonidentity_suppression_v1"
                                ),
                            },
                            {
                                "provider_reference_derivative": True,
                                "identity_evidence_scope": "head_geometry",
                                "identity_face_localization_applied": True,
                                "identity_face_localization_status": "detected",
                                "identity_nonidentity_pixel_suppression_profile": (
                                    "face_localized_nonidentity_suppression_v1"
                                ),
                            },
                        ],
                    },
                    file_path="unused_front.png",
                )
            ]

    class _FakeService:
        visual_asset_catalog = None
        output_store = _FakeOutputStore()

        def get_job_record(self, job_id: str):  # noqa: ANN001, ANN201
            assert job_id == "job_front_absolute"
            score_card = {
                "same_person_readability": 0.94,
                "distinctive_feature_readability": 0.91,
                "human_realism": 0.9,
                "pose_compliance": 0.92,
                "visual_quality": 0.94,
                "ai_overperfection_penalty": 0.04,
                "technical_finish": 0.93,
                "developmental_age_coherence": 0.9,
                "prompt_owned_channel_obedience": 0.89,
                "neutral_capture_compliance": 0.9,
                **_passing_dimensions(),
            }
            return SimpleNamespace(
                generation_result=SimpleNamespace(
                    planning_result_id="planning_result_front_absolute",
                    metadata={
                        "post_generation_review_package": {
                            "inspections": [
                                {
                                    "output_id": "v3_output_front_absolute",
                                    "status": "pass",
                                    "mode": "vision_model",
                                    "verification_state": "verified",
                                    "issue_codes": [],
                                    "score_card": score_card,
                                }
                            ]
                        }
                    },
                )
            )

    host = ProductApiAnchorPackPreparationHost(_FakeService())  # type: ignore[arg-type]
    request = AnchorGenerationRequest(
        project_id="project_absolute_realism",
        people_asset_id="asset_absolute_realism",
        pack_version_id="pack_absolute_realism",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent="character card front identity",
        root_source_asset_id="source_original",
        reference_evidence_ids=["source_original", "source_supplemental"],
        initial_supplementary_source_asset_ids=["source_supplemental"],
        absolute_portrait_realism_required=True,
        capture_scope="character_card_face_identity",
    )

    candidate, review = host._candidate_and_review("job_front_absolute", request)  # noqa: SLF001

    assert candidate.output_id == "v3_output_front_absolute"
    assert review.status == "pass"
    assert review.shared_review_receipts
    receipt = review.shared_review_receipts[0]
    assert receipt["owner"] == "v3_shared_visual_cluster"
    assert receipt["contract_version"] == "v3_character_card_generic_slot_review_receipt_v1"
    assert receipt["status"] == "pass"
    assert "human_realism" in receipt["score_dimensions"]
    assert "shared_visual_review_status_pass" in receipt["evidence_codes"]


def test_doc248_vision_contract_requests_absolute_realism_dimensions_only_when_enabled() -> None:
    planning_metadata = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="standard_front",
        capture_scope="character_card_face_identity",
    )
    envelope = {
        "activation_plan": {
            "metadata": {
                "professional_face_identity_quality_contract": planning_metadata[
                    "professional_face_identity_quality_contract"
                ]
            }
        },
        "resolved_constraint_ledger": {},
    }

    disabled = active_review_contract({"capability_execution_envelope": envelope})
    forged = active_review_contract(
        {
            "capability_execution_envelope": envelope,
            "professional_absolute_portrait_realism_required": True,
        }
    )
    wrong_scope = active_review_contract(
        {
            "capability_execution_envelope": envelope,
            "professional_anchor_capture_scope": "anchor_pack",
            "professional_absolute_portrait_realism_required": True,
            "professional_absolute_portrait_realism_provenance": "server_feature_flag_v1",
        }
    )
    enabled = active_review_contract(
        {
            "capability_execution_envelope": envelope,
            "professional_anchor_capture_scope": "character_card_face_identity",
            "professional_absolute_portrait_realism_required": True,
            "professional_absolute_portrait_realism_provenance": "server_feature_flag_v1",
        }
    )

    for dimension in REQUIRED_REALISM_DIMENSIONS:
        assert dimension not in disabled["score_dimensions"]
        assert dimension not in forged["score_dimensions"]
        assert dimension not in wrong_scope["score_dimensions"]
        assert dimension in enabled["score_dimensions"]
    assert forged["professional_identity_quality"]["absolute_portrait_realism"]["applies"] is False
    assert wrong_scope["professional_identity_quality"]["absolute_portrait_realism"]["applies"] is False
    assert enabled["professional_identity_quality"]["absolute_portrait_realism"]["applies"] is True
    assert enabled["professional_identity_quality"]["absolute_portrait_realism"]["detector_evasion_objective"] is False
    assert enabled["professional_identity_quality"]["absolute_portrait_realism"]["provenance"] == "server_feature_flag_v1"


def test_doc248_host_projects_absolute_realism_evidence_only_from_passing_scores() -> None:
    request = AnchorGenerationRequest(
        project_id="project_absolute_realism",
        people_asset_id="asset_absolute_realism",
        pack_version_id="pack_absolute_realism",
        view_role="standard_front",
        candidate_index=1,
        preparation_intent="character_card",
        root_source_asset_id="source_original",
        reference_evidence_ids=["source_original"],
        brain_plan_id="brain_plan_1",
        canonical_prompt_hash="prompt_hash_1",
        capture_scope="character_card_face_identity",
        absolute_portrait_realism_required=True,
    )
    passing = ProductApiAnchorPackPreparationHost._absolute_portrait_realism_evidence_codes(  # noqa: SLF001
        request,
        _passing_dimensions(),
    )
    weak = dict(_passing_dimensions())
    weak["skin_micro_texture"] = 0.2
    failing = ProductApiAnchorPackPreparationHost._absolute_portrait_realism_evidence_codes(  # noqa: SLF001
        request,
        weak,
    )

    assert "absolute_skin_micro_texture_verified" in passing
    assert "absolute_skin_micro_texture_verified" not in failing
