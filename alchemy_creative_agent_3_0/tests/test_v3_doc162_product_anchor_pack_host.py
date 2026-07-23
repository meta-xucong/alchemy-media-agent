"""Doc162: formal Product API host closes the shared AnchorPack seam."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from PIL import Image, ImageDraw

from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import AnchorGenerationRequest
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import (
    ProductApiAnchorPackPreparationHost,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest
from alchemy_creative_agent_3_0.app.product_api.assets import V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import ProductJobRecord, V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.visual_assets.catalog import InMemoryVisualAssetCatalog
from alchemy_creative_agent_3_0.app.visual_assets.contracts import (
    AnchorCandidateFailureReceipt,
    AnchorView,
    FaceIdentityModule,
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    PeopleAsset,
    RootSourceProvenance,
)


PREPARATION_INTENT = (
    "Prepare a coherent professional identity anchor pack for the same person while "
    "letting the current request own developmental stage, presentation, and capture treatment."
)


class _OutputStore:
    def __init__(self) -> None:
        self.by_job: dict[str, list[SimpleNamespace]] = {}
        self.by_output: dict[str, SimpleNamespace] = {}

    def list_by_job(self, job_id: str):  # noqa: ANN201
        return list(self.by_job.get(job_id, []))

    def get_output(self, output_id: str):  # noqa: ANN201
        return self.by_output.get(output_id)


class _SharedProductService:
    """Test double for the already-tested Product API/Provider/Vision path."""

    def __init__(self) -> None:
        self.visual_asset_catalog = InMemoryVisualAssetCatalog()
        self.output_store = _OutputStore()
        self.jobs: dict[str, SimpleNamespace] = {}
        self.requests: list[dict] = []
        self._tmp = TemporaryDirectory()
        self.image_root = Path(self._tmp.name)

    def create_professional_anchor_preparation_job(
        self,
        payload,
        *,
        view_role,
        reference_evidence_ids,
        stage_plan_source_job_id=None,
        capture_scope="anchor_pack",
        generation_channel="provider",
        mcp_operation_id=None,
    ):  # noqa: ANN001, ANN201
        job_id = f"job_{len(self.requests) + 1}"
        self.requests.append(
            {
                "job_id": job_id,
                "payload": payload,
                "view_role": view_role,
                "reference_evidence_ids": list(reference_evidence_ids),
                "stage_plan_source_job_id": stage_plan_source_job_id,
                "capture_scope": capture_scope,
                "generation_channel": generation_channel,
                "mcp_operation_id": mcp_operation_id,
            }
        )
        return SimpleNamespace(status=ProductJobStatusValue.PLANNED, job_id=job_id)

    def generate_job(self, job_id, request):  # noqa: ANN001, ANN201
        frozen = next(item for item in self.requests if item["job_id"] == job_id)
        frozen["generation_request"] = dict(request)
        role = frozen["view_role"]
        expected_references = (
            {
                "standard_front": 2,
                "left_front_25": 3,
                "three_quarter": 5,
                "profile": 5,
                "right_front_25": 5,
                "reverse_three_quarter": 5,
                "rear_head": 5,
            }
            if frozen.get("capture_scope") == "character_card_face_identity"
            else {"standard_front": 2, "three_quarter": 3, "profile": 5}
        )[role]
        output_id = f"output_{job_id}"
        candidate_id = f"candidate_{job_id}"
        image_path = self.image_root / f"{output_id}.png"
        _write_framing_card(image_path, top=0.14, height=0.72)
        output = SimpleNamespace(
            output_id=output_id,
            candidate_id=candidate_id,
            file_path=str(image_path),
            metadata={
                "provider_prompt_sha256": f"sha256:{job_id}",
                "prompt_compilation_id": f"prompt_{job_id}",
                "provider_reference_image_count": expected_references,
                "provider_reference_assets": [
                    {
                        "provider_reference_derivative": True,
                        "identity_face_localization_applied": True,
                        "identity_face_localization_status": "detected",
                        "identity_nonidentity_pixel_suppression_profile": (
                            "face_localized_nonidentity_suppression_v1"
                        ),
                    }
                    for _ in range(expected_references)
                ],
            },
        )
        self.output_store.by_job[job_id] = [output]
        self.output_store.by_output[output_id] = output
        score_card = {
            "same_person_readability": 0.90 + len(self.requests) / 1000,
            "distinctive_feature_readability": 0.91,
            "human_realism": 0.94,
            "pose_compliance": 0.92,
            "visual_quality": 0.97,
            "technical_finish": 0.97,
            "developmental_age_coherence": 0.92,
            "prompt_owned_channel_obedience": 0.92,
            "neutral_capture_compliance": 0.92,
            "ai_overperfection_penalty": 0.04,
            "overall": 0.94,
        }
        self.jobs[job_id] = SimpleNamespace(
            generation_result=SimpleNamespace(
                planning_result_id=f"planning_{job_id}",
                metadata={
                    "visual_auto_retry": {"executed_count": 0},
                    "post_generation_review_package": {
                        "inspections": [
                            {
                                "output_id": output_id,
                                "mode": "hybrid",
                                "verification_state": "verified",
                                "status": "pass",
                                "score_card": score_card,
                                "issue_codes": [],
                            }
                        ]
                    }
                },
            )
        )
        return SimpleNamespace(status=ProductJobStatusValue.GENERATED)

    def get_job_record(self, job_id):  # noqa: ANN001, ANN201
        return self.jobs.get(job_id)


class _FramingProfiler:
    def __init__(
        self,
        ratios: dict[str, float],
        view_hints: dict[str, str] | None = None,
        view_magnitudes: dict[str, float] | None = None,
    ) -> None:
        self.ratios = ratios
        self.view_hints = dict(view_hints or {})
        self.view_magnitudes = dict(view_magnitudes or {})

    def profile_reference(self, path):  # noqa: ANN001, ANN201
        ratio = self.ratios.get(str(path), 0.0)
        if ratio <= 0:
            return {"status": "face_not_detected", "view_hint": "unknown", "framing_hint": "unknown"}
        view_hint = self.view_hints.get(str(path), "front")
        magnitude = self.view_magnitudes.get(
            str(path),
            0.0
            if view_hint == "front"
            else 0.45
            if "profile" in view_hint
            else 0.24,
        )
        offset = -abs(magnitude) if str(view_hint).startswith("left") else abs(magnitude)
        return {
            "status": "ready",
            "view_hint": view_hint,
            "face_view_magnitude": magnitude,
            "face_view_offset_ratio": offset,
            "framing_hint": "head_shoulders",
            "face_box": [0.2, 0.2, ratio, 1.0],
            "embedding_persisted": False,
        }


def _write_framing_card(
    path: Path,
    *,
    top: float,
    height: float,
    left: float = 0.275,
    width: float = 0.45,
) -> None:
    image = Image.new("RGB", (200, 300), "white")
    x1 = int(200 * left)
    x2 = int(200 * min(0.98, left + width))
    y1 = int(300 * top)
    y2 = int(300 * min(0.98, top + height))
    draw = ImageDraw.Draw(image)
    draw.rectangle((x1, y1, x2, y2), fill=(48, 48, 48))
    image.save(path)


def _asset() -> PeopleAsset:
    return PeopleAsset(
        people_asset_id="person_doc162",
        project_id="project_doc162",
        subject_kind="human_person",
        face_identity_module=FaceIdentityModule(
            module_id="face_doc162",
            people_asset_id="person_doc162",
        ),
        preparation_intent=PREPARATION_INTENT,
    )


def _root() -> RootSourceProvenance:
    return RootSourceProvenance(
        source_type="uploaded_portrait",
        source_asset_id="v3_asset_root",
        project_id="project_doc162",
        consent_reference="authorized-test-source",
    )


def _anchor_view(role: str, output_id: str) -> AnchorView:
    return AnchorView(
        view_id=f"view_{output_id}",
        view_role=role,  # type: ignore[arg-type]
        output_id=output_id,
        source_candidate_ids=[f"candidate_{output_id}"],
        identity_scores=IdentityScoreSummary(
            same_face_score=0.91,
            visual_quality_score=0.94,
            distinctive_feature_score=0.90,
            human_realism_score=0.93,
            pose_compliance_score=0.92,
            ai_overperfection_penalty=0.05,
            evidence_codes=["shared_real_pixel_review_verified"],
        ),
    )


def _reverse_45_generation_request() -> AnchorGenerationRequest:
    return AnchorGenerationRequest(
        project_id="project_doc162",
        people_asset_id="person_doc162",
        pack_version_id="pack_doc162",
        view_role="reverse_three_quarter",
        candidate_index=1,
        preparation_intent=PREPARATION_INTENT,
        root_source_asset_id="v3_asset_root",
        reference_evidence_ids=[
            "v3_asset_root",
            "v3_output_front",
            "v3_output_profile",
            "v3_output_right25",
        ],
        capture_scope="character_card_face_identity",
    )


def _three_45_generation_request() -> AnchorGenerationRequest:
    return AnchorGenerationRequest(
        project_id="project_doc162",
        people_asset_id="person_doc162",
        pack_version_id="pack_doc162",
        view_role="three_quarter",
        candidate_index=1,
        preparation_intent=PREPARATION_INTENT,
        root_source_asset_id="v3_asset_root",
        reference_evidence_ids=[
            "v3_asset_root",
            "v3_output_front",
            "v3_output_left25",
        ],
        capture_scope="character_card_face_identity",
    )


def _rear_head_generation_request() -> AnchorGenerationRequest:
    return AnchorGenerationRequest(
        project_id="project_doc162",
        people_asset_id="person_doc162",
        pack_version_id="pack_doc162",
        view_role="rear_head",
        candidate_index=1,
        preparation_intent=PREPARATION_INTENT,
        root_source_asset_id="v3_asset_root",
        reference_evidence_ids=[
            "v3_asset_root",
            "v3_output_front",
            "v3_output_profile",
            "v3_output_right45",
        ],
        capture_scope="character_card_face_identity",
    )


def test_doc162_product_host_runs_three_by_three_by_three_through_shared_service() -> None:
    service = _SharedProductService()
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]

    result = host.prepare(
        project_id="project_doc162",
        people_asset=_asset(),
        root_source_provenance=_root(),
    )

    assert result.status == "review"
    assert len(service.requests) == 9
    assert [item["view_role"] for item in service.requests] == [
        "standard_front", "standard_front", "standard_front",
        "three_quarter", "three_quarter", "three_quarter",
        "profile", "profile", "profile",
    ]
    front_winner = result.pack.anchor_views[0].output_id
    three_quarter_winner = result.pack.anchor_views[1].output_id
    assert all(
        item["reference_evidence_ids"] == ["v3_asset_root", front_winner]
        for item in service.requests[3:6]
    )
    assert all(
        item["reference_evidence_ids"] == [
            "v3_asset_root",
            front_winner,
            three_quarter_winner,
        ]
        for item in service.requests[6:]
    )
    assert all(attempt.candidate.prompt_reference_parity_verified for attempt in result.attempts)
    assert all(attempt.candidate.brain_plan_id.startswith("planning_job_") for attempt in result.attempts)
    assert service.requests[0]["stage_plan_source_job_id"] is None
    assert service.requests[1]["stage_plan_source_job_id"] == service.requests[0]["job_id"]
    assert service.requests[2]["stage_plan_source_job_id"] == service.requests[0]["job_id"]
    assert service.requests[3]["stage_plan_source_job_id"] is None
    assert service.requests[6]["stage_plan_source_job_id"] is None
    assert all(
        item["payload"]["user_input"] == PREPARATION_INTENT
        for item in service.requests
    )
    assert all(
        attempt.request.preparation_intent == PREPARATION_INTENT
        for attempt in result.attempts
    )
    assert "prompt" not in service.requests[0]["payload"]["metadata"]


def test_doc192_reverse_45_framing_parity_uses_approved_right25_as_baseline() -> None:
    service = _SharedProductService()
    service.output_store.by_output["v3_output_right25"] = SimpleNamespace(file_path="right25.png")
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {"right25.png": 0.14, "right45.png": 0.145},
        {"right25.png": "left_three_quarter", "right45.png": "left_three_quarter"},
        {"right25.png": 0.12, "right45.png": 0.24},
    )
    request = _reverse_45_generation_request()

    assert host._character_card_face_framing_baseline_output_id(request) == "v3_output_right25"  # noqa: SLF001
    passed, issues = host._character_card_face_framing_parity(  # noqa: SLF001
        request,
        SimpleNamespace(file_path="right45.png"),
    )

    assert passed is True
    assert issues == []


def test_doc193_character_card_angle_slots_do_not_hard_fail_on_face_box_projection_drift() -> None:
    service = _SharedProductService()
    service.output_store.by_output["v3_output_right25"] = SimpleNamespace(file_path="right25.png")
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {"right25.png": 0.14, "right45.png": 0.18},
        {"right25.png": "left_three_quarter", "right45.png": "left_three_quarter"},
        {"right25.png": 0.12, "right45.png": 0.24},
    )

    passed, issues = host._character_card_face_framing_parity(  # noqa: SLF001
        _reverse_45_generation_request(),
        SimpleNamespace(file_path="right45.png"),
    )

    assert passed is True
    assert issues == []


def test_doc193_character_card_angle_slots_keep_face_box_diagnostic_non_blocking() -> None:
    service = _SharedProductService()
    service.output_store.by_output["v3_output_right25"] = SimpleNamespace(file_path="right25.png")
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {"right25.png": 0.140, "right45.png": 0.162},
        {"right25.png": "left_three_quarter", "right45.png": "left_three_quarter"},
        {"right25.png": 0.12, "right45.png": 0.24},
    )

    passed, issues = host._character_card_face_framing_parity(  # noqa: SLF001
        _reverse_45_generation_request(),
        SimpleNamespace(file_path="right45.png"),
    )

    assert passed is True
    assert issues == []


def test_doc192_reverse_45_face_area_parity_allows_minor_yaw_projection_drift() -> None:
    service = _SharedProductService()
    service.output_store.by_output["v3_output_right25"] = SimpleNamespace(file_path="right25.png")
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    # The raw helper remains available for diagnostics, but Character Card
    # angle-slot acceptance now uses the full-card foreground framing gate
    # instead of this face-box area comparison.
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {"right25.png": 0.157, "right45.png": 0.166},
        {"right25.png": "left_three_quarter", "right45.png": "left_three_quarter"},
        {"right25.png": 0.12, "right45.png": 0.24},
    )

    passed, issues = host._character_card_face_framing_parity(  # noqa: SLF001
        _reverse_45_generation_request(),
        SimpleNamespace(file_path="right45.png"),
    )

    assert passed is True
    assert issues == []


def test_doc192_visible_face_area_parity_allows_yaw_wobble_but_rejects_large_drift() -> None:
    host = ProductApiAnchorPackPreparationHost(_SharedProductService())  # type: ignore[arg-type]
    baseline = {"status": "ready", "face_box": [0.0, 0.0, 0.157, 1.0]}

    assert (
        host._character_card_face_area_parity_issues(  # noqa: SLF001
            {"status": "ready", "face_box": [0.0, 0.0, 0.166, 1.0]},
            baseline,
            view_role="reverse_three_quarter",
        )
        == []
    )
    assert (
        host._character_card_face_area_parity_issues(  # noqa: SLF001
            {"status": "ready", "face_box": [0.0, 0.0, 0.169, 1.0]},
            baseline,
            view_role="right_front_25",
        )
        == []
    )
    assert host._character_card_face_area_parity_issues(  # noqa: SLF001
        {"status": "ready", "face_box": [0.0, 0.0, 0.172, 1.0]},
        baseline,
        view_role="right_front_25",
    ) == ["professional_face_card_framing_parity_failed"]
    assert host._character_card_face_area_parity_issues(  # noqa: SLF001
        {"status": "ready", "face_box": [0.0, 0.0, 0.174, 1.0]},
        baseline,
        view_role="reverse_three_quarter",
    ) == ["professional_face_card_framing_parity_failed"]


def test_doc190_three_quarter_rejects_random_opposite_side_direction() -> None:
    service = _SharedProductService()
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {"left45.png": 0.14},
        {"left45.png": "left_three_quarter"},
    )

    passed, issues = host._character_card_face_view_direction_parity(  # noqa: SLF001
        _three_45_generation_request(),
        SimpleNamespace(file_path="left45.png"),
    )

    assert passed is False
    assert issues == ["professional_face_card_view_direction_parity_failed"]


def test_doc190_reverse_45_requires_independent_opposite_side_direction() -> None:
    service = _SharedProductService()
    service.output_store.by_output["v3_output_right25"] = SimpleNamespace(file_path="right25.png")
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {"right25.png": 0.14, "right45.png": 0.15},
        {"right25.png": "left_three_quarter", "right45.png": "left_three_quarter"},
        {"right25.png": 0.12, "right45.png": 0.24},
    )

    passed, issues = host._character_card_face_view_direction_parity(  # noqa: SLF001
        _reverse_45_generation_request(),
        SimpleNamespace(file_path="right45.png"),
    )

    assert passed is True
    assert issues == []


def test_doc192_reverse_45_accepts_relaxed_detector_profile_label_when_side_and_depth_fit() -> None:
    service = _SharedProductService()
    service.output_store.by_output["v3_output_right25"] = SimpleNamespace(file_path="right25.png")
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {"right25.png": 0.14, "right45.png": 0.15},
        {"right25.png": "left_three_quarter", "right45.png": "left_profile"},
        {"right25.png": 0.12, "right45.png": 0.35},
    )

    passed, issues = host._character_card_face_view_direction_parity(  # noqa: SLF001
        _reverse_45_generation_request(),
        SimpleNamespace(file_path="right45.png"),
    )

    assert passed is True
    assert issues == []


def test_doc193_three_quarter_soft_gate_prefers_detector_slot_over_brittle_yaw_number() -> None:
    host = ProductApiAnchorPackPreparationHost(_SharedProductService())  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {"left45.png": 0.1212},
        {"left45.png": "right_three_quarter"},
        {"left45.png": 0.1212},
    )

    passed, issues = host._character_card_face_view_direction_parity(  # noqa: SLF001
        _three_45_generation_request(),
        SimpleNamespace(file_path="left45.png"),
    )

    assert passed is True
    assert issues == []


def test_doc190_reverse_45_rejects_same_side_duplicate() -> None:
    service = _SharedProductService()
    service.output_store.by_output["v3_output_right25"] = SimpleNamespace(file_path="right25.png")
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {"right25.png": 0.14, "right45.png": 0.15},
        {"right25.png": "left_three_quarter", "right45.png": "right_three_quarter"},
        {"right25.png": 0.12, "right45.png": 0.24},
    )

    passed, issues = host._character_card_face_view_direction_parity(  # noqa: SLF001
        _reverse_45_generation_request(),
        SimpleNamespace(file_path="right45.png"),
    )

    assert passed is False
    assert issues == ["professional_face_card_view_direction_parity_failed"]


def test_doc190_reverse_45_rejects_shallow_frontish_angle() -> None:
    service = _SharedProductService()
    service.output_store.by_output["v3_output_right25"] = SimpleNamespace(file_path="right25.png")
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {"right25.png": 0.14, "right45.png": 0.08},
        {"right25.png": "left_three_quarter", "right45.png": "left_three_quarter"},
        {"right25.png": 0.12, "right45.png": 0.08},
    )

    passed, issues = host._character_card_face_view_direction_parity(  # noqa: SLF001
        _reverse_45_generation_request(),
        SimpleNamespace(file_path="right45.png"),
    )

    assert passed is False
    assert issues == ["professional_face_card_view_angle_too_shallow"]


def test_doc190_character_card_resume_drops_stale_non45_checkpoint() -> None:
    service = _SharedProductService()
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path="front.png")
    service.output_store.by_output["v3_output_left45"] = SimpleNamespace(file_path="left45.png")
    service.output_store.by_output["v3_output_profile"] = SimpleNamespace(file_path="profile.png")
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {
            "front.png": 0.16,
            "left45.png": 0.14,
            "profile.png": 0.09,
        },
        {
            "front.png": "front",
            # Historical accepted output: visually usable but not canonical
            # enough for the current left/right 45-degree card contract.
            "left45.png": "front",
            "profile.png": "right_profile",
        },
    )
    failed_pack = IdentityAnchorPackVersion(
        pack_version_id="pack_stale_left45",
        people_asset_id="person_doc162",
        status="failed",
        anchor_views=[
            _anchor_view("standard_front", "v3_output_front"),
            _anchor_view("three_quarter", "v3_output_left45"),
            _anchor_view("profile", "v3_output_profile"),
        ],
        candidate_failures=[
            AnchorCandidateFailureReceipt(
                stage="supplementary",
                view_role="reverse_three_quarter",
                candidate_index=1,
                failure_code="shared_visual_review_failed",
            )
        ],
        root_source_provenance=_root(),
    )

    sanitized = host._sanitize_character_card_resume_pack(failed_pack)  # noqa: SLF001

    assert sanitized is not None
    assert [view.view_role for view in sanitized.anchor_views] == ["standard_front"]
    assert sanitized.candidate_failures == []


def test_doc190_reverse_45_card_framing_parity_rejects_head_top_margin_drift(tmp_path) -> None:
    service = _SharedProductService()
    front = tmp_path / "front.png"
    right45 = tmp_path / "right45.png"
    _write_framing_card(front, top=0.16, height=0.68)
    _write_framing_card(right45, top=0.08, height=0.91)
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path=str(front))
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]

    passed, issues = host._character_card_card_framing_parity(  # noqa: SLF001
        _reverse_45_generation_request(),
        SimpleNamespace(file_path=str(right45)),
    )

    assert passed is False
    assert "professional_face_card_head_top_margin_parity_failed" in issues
    assert "professional_face_card_subject_scale_parity_failed" in issues


def test_doc190_reverse_45_card_framing_parity_rejects_subtle_subject_scale_drift(tmp_path) -> None:
    service = _SharedProductService()
    front = tmp_path / "front.png"
    right45 = tmp_path / "right45.png"
    _write_framing_card(front, top=0.14, height=0.70, left=0.28, width=0.44)
    _write_framing_card(right45, top=0.14, height=0.78, left=0.28, width=0.44)
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path=str(front))
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]

    passed, issues = host._character_card_card_framing_parity(  # noqa: SLF001
        _reverse_45_generation_request(),
        SimpleNamespace(file_path=str(right45)),
    )

    assert passed is False
    assert "professional_face_card_subject_scale_parity_failed" in issues


def test_doc190_reverse_45_card_framing_parity_rejects_looser_matching_face_area(tmp_path) -> None:
    service = _SharedProductService()
    front = tmp_path / "front.png"
    right45 = tmp_path / "right45.png"
    _write_framing_card(front, top=0.14, height=0.70, left=0.28, width=0.44)
    _write_framing_card(right45, top=0.14, height=0.86, left=0.18, width=0.64)
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path=str(front))
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {str(front): 0.14, str(right45): 0.145},
        {str(front): "front", str(right45): "left_three_quarter"},
        {str(front): 0.0, str(right45): 0.24},
    )

    passed, issues = host._character_card_face_framing_parity(  # noqa: SLF001
        _reverse_45_generation_request(),
        SimpleNamespace(file_path=str(right45)),
    )
    foreground_passed, foreground_issues = host._character_card_card_framing_parity(  # noqa: SLF001
        _reverse_45_generation_request(),
        SimpleNamespace(file_path=str(right45)),
    )

    assert passed is True
    assert issues == []
    assert foreground_passed is False
    assert "professional_face_card_subject_scale_parity_failed" in foreground_issues
    assert "professional_face_card_subject_width_parity_failed" in foreground_issues
    assert "professional_face_card_shoulder_padding_parity_failed" in foreground_issues


def test_doc190_character_card_resume_drops_stale_loose_45_checkpoint(tmp_path) -> None:
    service = _SharedProductService()
    front = tmp_path / "front.png"
    left45 = tmp_path / "loose-left45.png"
    _write_framing_card(front, top=0.14, height=0.70, left=0.28, width=0.44)
    _write_framing_card(left45, top=0.13, height=0.86, left=0.18, width=0.64)
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path=str(front))
    service.output_store.by_output["v3_output_left45"] = SimpleNamespace(file_path=str(left45))
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {str(front): 0.16, str(left45): 0.155},
        {str(front): "front", str(left45): "right_three_quarter"},
    )
    failed_pack = IdentityAnchorPackVersion(
        pack_version_id="pack_loose_left45",
        people_asset_id="person_doc162",
        status="failed",
        anchor_views=[
            _anchor_view("standard_front", "v3_output_front"),
            _anchor_view("three_quarter", "v3_output_left45"),
        ],
        candidate_failures=[],
        root_source_provenance=_root(),
    )

    sanitized = host._sanitize_character_card_resume_pack(failed_pack)  # noqa: SLF001

    assert sanitized is not None
    assert [view.view_role for view in sanitized.anchor_views] == ["standard_front"]


def test_doc193_character_card_resume_keeps_angle_slot_with_face_projection_drift(tmp_path) -> None:
    service = _SharedProductService()
    front = tmp_path / "front.png"
    left25 = tmp_path / "left25.png"
    left45 = tmp_path / "left45.png"
    _write_framing_card(front, top=0.14, height=0.70, left=0.28, width=0.44)
    _write_framing_card(left25, top=0.142, height=0.705, left=0.275, width=0.445)
    _write_framing_card(left45, top=0.145, height=0.71, left=0.27, width=0.45)
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path=str(front))
    service.output_store.by_output["v3_output_left25"] = SimpleNamespace(file_path=str(left25))
    service.output_store.by_output["v3_output_left45"] = SimpleNamespace(file_path=str(left45))
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {str(front): 0.160, str(left25): 0.152, str(left45): 0.132},
        {str(front): "front", str(left25): "right_three_quarter", str(left45): "right_three_quarter"},
        {str(front): 0.0, str(left25): 0.10, str(left45): 0.18},
    )
    failed_pack = IdentityAnchorPackVersion(
        pack_version_id="pack_valid_left45_projection_drift",
        people_asset_id="person_doc193",
        status="failed",
        anchor_views=[
            _anchor_view("standard_front", "v3_output_front"),
            _anchor_view("left_front_25", "v3_output_left25"),
            _anchor_view("three_quarter", "v3_output_left45"),
        ],
        candidate_failures=[],
        root_source_provenance=_root(),
    )

    sanitized = host._sanitize_character_card_resume_pack(failed_pack)  # noqa: SLF001

    assert sanitized is not None
    assert [view.view_role for view in sanitized.anchor_views] == [
        "standard_front",
        "left_front_25",
        "three_quarter",
    ]


def test_doc193_mcp_review_timeout_keeps_same_output_as_review_pending(tmp_path) -> None:
    service = _SharedProductService()
    front = tmp_path / "front.png"
    left25 = tmp_path / "left25.png"
    _write_framing_card(front, top=0.14, height=0.70, left=0.28, width=0.44)
    _write_framing_card(left25, top=0.142, height=0.705, left=0.275, width=0.445)
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path=str(front))
    service.output_store.by_output["v3_output_left25"] = SimpleNamespace(file_path=str(left25))
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {str(front): 0.160, str(left25): 0.152},
        {str(front): "front", str(left25): "right_three_quarter"},
        {str(front): 0.0, str(left25): 0.10},
    )
    original_generate = service.generate_job

    def timeout_review(job_id, request):  # noqa: ANN001, ANN202
        status = original_generate(job_id, request)
        inspection = service.jobs[job_id].generation_result.metadata[
            "post_generation_review_package"
        ]["inspections"][0]
        inspection["verification_state"] = "unverified"
        inspection["status"] = "manual_review"
        inspection["score_card"] = {
            "overall": 0.5,
            "same_person_readability": 0.93,
        }
        inspection["issue_codes"] = ["provider_timeout"]
        return status

    service.generate_job = timeout_review  # type: ignore[method-assign]
    failed_pack = IdentityAnchorPackVersion(
        pack_version_id="pack_review_timeout",
        people_asset_id="person_doc162",
        status="failed",
        anchor_views=[
            _anchor_view("standard_front", "v3_output_front"),
            _anchor_view("left_front_25", "v3_output_left25"),
        ],
        candidate_failures=[
            AnchorCandidateFailureReceipt(
                stage="supplementary",
                view_role="three_quarter",
                candidate_index=1,
                failure_code="mcp_materialization_pending",
                mcp_handoff_id="mcp_handoff_review_timeout",
            )
        ],
        root_source_provenance=_root(),
    )

    result = host.prepare_character_card(
        project_id="project_doc162",
        people_asset=_asset(),
        root_source_provenance=_root(),
        resume_from_pack=failed_pack,
        generation_channel="mcp",
    )

    assert result.status == "blocked"
    assert result.failure_codes == ["mcp_review_pending"]
    assert len(service.requests) == 1
    failure = result.generation_failures[-1]
    assert failure.failure_code == "mcp_review_pending"
    assert failure.mcp_handoff_id == "mcp_handoff_review_timeout"
    assert failure.output_id == "output_job_1"
    assert failure.candidate_id == "candidate_job_1"


def test_doc190_character_card_resume_drops_stale_shallow_45_checkpoint(tmp_path) -> None:
    service = _SharedProductService()
    front = tmp_path / "front.png"
    left45 = tmp_path / "shallow-left45.png"
    _write_framing_card(front, top=0.14, height=0.70, left=0.28, width=0.44)
    _write_framing_card(left45, top=0.14, height=0.70, left=0.28, width=0.44)
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path=str(front))
    service.output_store.by_output["v3_output_left45"] = SimpleNamespace(file_path=str(left45))
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {str(front): 0.16, str(left45): 0.155},
        {str(front): "front", str(left45): "right_three_quarter"},
        {str(front): 0.0, str(left45): 0.13},
    )
    failed_pack = IdentityAnchorPackVersion(
        pack_version_id="pack_shallow_left45",
        people_asset_id="person_doc162",
        status="failed",
        anchor_views=[
            _anchor_view("standard_front", "v3_output_front"),
            _anchor_view("three_quarter", "v3_output_left45"),
        ],
        candidate_failures=[],
        root_source_provenance=_root(),
    )

    sanitized = host._sanitize_character_card_resume_pack(failed_pack)  # noqa: SLF001

    assert sanitized is not None
    assert [view.view_role for view in sanitized.anchor_views] == ["standard_front"]


def test_doc190_rear_head_uses_nonface_continuity_floor_after_shared_vision_pass(tmp_path) -> None:
    service = _SharedProductService()
    front = tmp_path / "front.png"
    rear = tmp_path / "rear.png"
    _write_framing_card(front, top=0.14, height=0.86)
    _write_framing_card(rear, top=0.12, height=0.88)
    job_id = "job_rear"
    output_id = "output_rear"
    candidate_id = "candidate_rear"
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path=str(front))
    service.output_store.by_job[job_id] = [
        SimpleNamespace(
            output_id=output_id,
            candidate_id=candidate_id,
            file_path=str(rear),
            metadata={
                "provider_prompt_sha256": "sha256:rear",
                "prompt_compilation_id": "prompt_rear",
                "provider_reference_image_count": 5,
                "provider_reference_assets": [
                    {
                        "provider_reference_derivative": True,
                        "identity_face_localization_applied": True,
                        "identity_face_localization_status": "detected",
                        "identity_nonidentity_pixel_suppression_profile": (
                            "face_localized_nonidentity_suppression_v1"
                        ),
                    }
                    for _ in range(5)
                ],
            },
        )
    ]
    service.jobs[job_id] = SimpleNamespace(
        generation_result=SimpleNamespace(
            planning_result_id="planning_rear",
            metadata={
                "post_generation_review_package": {
                    "inspections": [
                        {
                            "output_id": output_id,
                            "mode": "hybrid",
                            "verification_state": "verified",
                            "status": "pass",
                            "score_card": {
                                "same_person_readability": 0.72,
                                "distinctive_feature_readability": 0.70,
                                "human_realism": 0.93,
                                "pose_compliance": 0.98,
                                "visual_quality": 0.94,
                                "technical_finish": 0.94,
                                "developmental_age_coherence": 0.91,
                                "prompt_owned_channel_obedience": 0.95,
                                "neutral_capture_compliance": 0.95,
                                "ai_overperfection_penalty": 0.08,
                                "overall": 0.92,
                            },
                            "issue_codes": [],
                        }
                    ]
                }
            },
        )
    )
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]

    _candidate, decision = host._candidate_and_review(  # noqa: SLF001
        job_id,
        _rear_head_generation_request(),
    )

    assert decision.status == "pass"
    assert "professional_face_card_identity_evidence_below_bar" not in decision.issue_codes
    assert "professional_rear_head_nonface_continuity_below_bar" not in decision.issue_codes


def test_doc193_profile_contextualizes_cross_angle_identity_metric_when_other_evidence_passes(tmp_path) -> None:
    service = _SharedProductService()
    front = tmp_path / "front.png"
    _write_framing_card(front, top=0.14, height=0.72)
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path=str(front))
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    job = service.create_professional_anchor_preparation_job(
        {"user_input": PREPARATION_INTENT},
        view_role="profile",
        reference_evidence_ids=["root_doc193", "v3_output_front", "v3_output_left45"],
        capture_scope="character_card_face_identity",
    )
    service.generate_job(job.job_id, {})
    inspection = service.jobs[job.job_id].generation_result.metadata[
        "post_generation_review_package"
    ]["inspections"][0]
    inspection["status"] = "fail_retryable"
    inspection["issue_codes"] = ["identity_metric_below_commercial_target"]
    inspection["score_card"].update(
        {
            "same_person_readability": 0.8132,
            "distinctive_feature_readability": 0.84,
            "identity_fidelity": 0.84,
            "human_realism": 0.90,
            "pose_compliance": 0.96,
            "visual_quality": 0.93,
            "technical_finish": 0.93,
            "developmental_age_coherence": 0.93,
            "prompt_owned_channel_obedience": 0.91,
            "neutral_capture_compliance": 0.93,
        }
    )
    request = AnchorGenerationRequest(
        project_id="project_doc193",
        people_asset_id="people_doc193",
        pack_version_id="pack_doc193",
        view_role="profile",
        candidate_index=1,
        preparation_intent=PREPARATION_INTENT,
        root_source_asset_id="root_doc193",
        reference_evidence_ids=["root_doc193", "v3_output_front", "v3_output_left45"],
        capture_scope="character_card_face_identity",
    )

    _candidate, decision = host._candidate_and_review(job.job_id, request)  # noqa: SLF001

    assert decision.status == "pass"
    assert "professional_cross_angle_identity_metric_contextualized" in decision.issue_codes
    assert "professional_face_card_identity_evidence_below_bar" not in decision.issue_codes


def test_doc194_character_card_left45_uses_shared_pass_receipt_projection(tmp_path) -> None:
    service = _SharedProductService()
    front = tmp_path / "front.png"
    _write_framing_card(front, top=0.14, height=0.72)
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path=str(front))
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    job = service.create_professional_anchor_preparation_job(
        {"user_input": PREPARATION_INTENT},
        view_role="three_quarter",
        reference_evidence_ids=["root_doc194", "v3_output_front", "v3_output_left25"],
        capture_scope="character_card_face_identity",
    )
    service.generate_job(job.job_id, {})
    selected = service.output_store.by_job[job.job_id][0]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {str(selected.file_path): 0.16},
        {str(selected.file_path): "right_three_quarter"},
        {str(selected.file_path): 0.42},
    )
    inspection = service.jobs[job.job_id].generation_result.metadata[
        "post_generation_review_package"
    ]["inspections"][0]
    inspection.pop("status", None)
    inspection["review_status"] = "pass"
    inspection["score_card"] = {
        "overall": 0.91,
        "same-person": 0.9333,
        "distinctive_feature_readability": 0.91,
        "human_realism": 0.90,
        "pose_compliance": 0.90,
        "visual_quality": 0.94,
        "technical_finish": 0.94,
        "developmental_age_coherence": 0.90,
        "prompt_owned_channel_obedience": 0.91,
        "neutral_capture_compliance": 0.90,
    }
    request = AnchorGenerationRequest(
        project_id="project_doc194",
        people_asset_id="people_doc194",
        pack_version_id="pack_doc194",
        view_role="three_quarter",
        candidate_index=1,
        preparation_intent=PREPARATION_INTENT,
        root_source_asset_id="root_doc194",
        reference_evidence_ids=["root_doc194", "v3_output_front", "v3_output_left25"],
        capture_scope="character_card_face_identity",
    )

    _candidate, decision = host._candidate_and_review(job.job_id, request)  # noqa: SLF001

    assert decision.status == "pass"
    assert decision.identity_scores.same_face_score == 0.9333
    assert "shared_visual_review_failed" not in decision.issue_codes
    assert "shared_visual_review_status_missing" not in decision.issue_codes


def test_doc193_character_card_identity_floor_uses_small_numeric_tolerance(tmp_path) -> None:
    service = _SharedProductService()
    front = tmp_path / "front.png"
    _write_framing_card(front, top=0.14, height=0.72)
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path=str(front))
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    job = service.create_professional_anchor_preparation_job(
        {"user_input": PREPARATION_INTENT},
        view_role="right_front_25",
        reference_evidence_ids=["root_doc193", "v3_output_front", "v3_output_profile"],
        capture_scope="character_card_face_identity",
    )
    service.generate_job(job.job_id, {})
    selected = service.output_store.by_job[job.job_id][0]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {str(front): 0.160, str(selected.file_path): 0.158},
        {str(front): "front", str(selected.file_path): "left_three_quarter"},
        {str(front): 0.0, str(selected.file_path): 0.10},
    )
    inspection = service.jobs[job.job_id].generation_result.metadata[
        "post_generation_review_package"
    ]["inspections"][0]
    inspection["status"] = "pass"
    inspection["issue_codes"] = []
    inspection["score_card"].update(
        {
            "same_person_readability": 0.8776,
            "distinctive_feature_readability": 0.84,
            "identity_fidelity": 0.84,
            "human_realism": 0.88,
            "pose_compliance": 0.88,
            "visual_quality": 0.94,
            "technical_finish": 0.93,
            "developmental_age_coherence": 0.90,
            "prompt_owned_channel_obedience": 0.91,
            "neutral_capture_compliance": 0.93,
        }
    )
    request = AnchorGenerationRequest(
        project_id="project_doc193",
        people_asset_id="people_doc193",
        pack_version_id="pack_doc193",
        view_role="right_front_25",
        candidate_index=1,
        preparation_intent=PREPARATION_INTENT,
        root_source_asset_id="root_doc193",
        reference_evidence_ids=["root_doc193", "v3_output_front", "v3_output_profile"],
        capture_scope="character_card_face_identity",
    )

    _candidate, decision = host._candidate_and_review(job.job_id, request)  # noqa: SLF001

    assert decision.status == "pass"
    assert "professional_face_card_identity_evidence_below_bar" not in decision.issue_codes


def test_doc176_two_source_front_uses_bounded_calibration_then_serial_winners() -> None:
    service = _SharedProductService()
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    root = _root().model_copy(update={"supplementary_source_asset_ids": ["v3_asset_supplement"]})

    result = host.prepare(
        project_id="project_doc162",
        people_asset=_asset(),
        root_source_provenance=root,
    )

    assert result.status == "review"
    assert all(
        item["reference_evidence_ids"] == ["v3_asset_root", "v3_asset_supplement"]
        and item["payload"]["uploaded_asset_ids"] == ["v3_asset_root", "v3_asset_supplement"]
        for item in service.requests[:3]
    )
    front_winner = result.pack.anchor_views[0].output_id
    assert all(
        item["reference_evidence_ids"] == ["v3_asset_root", front_winner]
        and item["payload"]["uploaded_asset_ids"] == ["v3_asset_root"]
        for item in service.requests[3:6]
    )
    assert "v3_asset_supplement" not in str(service.requests[3:])


def test_doc178_extension_views_keep_lineage_but_bound_provider_evidence_to_five() -> None:
    root = "v3_asset_root"
    front = "v3_output_front"
    right25 = "v3_output_right25"
    profile = "v3_output_profile"
    reverse = "v3_output_reverse"

    assert V3ProductApiService._professional_anchor_provider_evidence_ids(
        view_role="reverse_three_quarter",
        evidence_ids=[root, front, right25, profile],
    ) == [root, front, right25, profile]
    assert V3ProductApiService._professional_anchor_provider_evidence_ids(
        view_role="rear_head",
        evidence_ids=[root, front, profile, reverse],
    ) == [root, profile, reverse]


def test_doc165_provider_failure_without_pixels_does_not_consume_stage_repair() -> None:
    service = _SharedProductService()
    original_generate = service.generate_job
    call_count = 0

    def fail_first_before_pixels(job_id, request):  # noqa: ANN001, ANN202
        nonlocal call_count
        call_count += 1
        status = original_generate(job_id, request)
        if call_count == 1:
            service.output_store.by_job[job_id] = []
            service.jobs[job_id].generation_result.metadata.pop(
                "post_generation_review_package",
                None,
            )
            return SimpleNamespace(status=ProductJobStatusValue.BLOCKED)
        return status

    service.generate_job = fail_first_before_pixels  # type: ignore[method-assign]
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]

    result = host.prepare(
        project_id="project_doc162",
        people_asset=_asset(),
        root_source_provenance=_root(),
    )

    assert result.status == "review"
    assert service.requests[0]["generation_request"]["metadata"] == {
        "max_visual_retry_attempts": 1
    }
    assert service.requests[1]["generation_request"]["metadata"] == {
        "max_visual_retry_attempts": 1
    }


def test_doc165_executed_shared_repair_disables_later_stage_repairs() -> None:
    service = _SharedProductService()
    original_generate = service.generate_job

    def consume_first_stage_repair(job_id, request):  # noqa: ANN001, ANN202
        status = original_generate(job_id, request)
        if len(service.requests) == 1:
            service.jobs[job_id].generation_result.metadata["visual_auto_retry"] = {
                "executed_count": 1
            }
        return status

    service.generate_job = consume_first_stage_repair  # type: ignore[method-assign]
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]

    result = host.prepare(
        project_id="project_doc162",
        people_asset=_asset(),
        root_source_provenance=_root(),
    )

    assert result.status == "review"
    assert service.requests[0]["generation_request"]["metadata"] == {
        "max_visual_retry_attempts": 1
    }
    assert service.requests[1]["generation_request"]["metadata"] == {
        "disable_visual_auto_retry": True,
        "max_visual_retry_attempts": 0,
    }
    assert service.requests[2]["generation_request"]["metadata"] == {
        "disable_visual_auto_retry": True,
        "max_visual_retry_attempts": 0,
    }


def test_doc162_product_host_fails_review_when_typed_score_is_incomplete() -> None:
    service = _SharedProductService()
    original_generate = service.generate_job

    def incomplete(job_id, request):  # noqa: ANN001, ANN202
        status = original_generate(job_id, request)
        inspection = service.jobs[job_id].generation_result.metadata[
            "post_generation_review_package"
        ]["inspections"][0]
        inspection["score_card"].pop("same_person_readability")
        return status

    service.generate_job = incomplete  # type: ignore[method-assign]
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]

    result = host.prepare(
        project_id="project_doc162",
        people_asset=_asset(),
        root_source_provenance=_root(),
    )

    assert result.status == "blocked"
    assert result.failure_codes == ["no_passing_front_candidate"]
    assert len(service.requests) == 3
    assert all(
        "professional_anchor_review_score_incomplete" in attempt.review.issue_codes
        for attempt in result.attempts
    )


def test_doc163_product_host_withholds_anchor_when_face_localization_falls_back() -> None:
    service = _SharedProductService()
    original_generate = service.generate_job

    def unlocalized(job_id, request):  # noqa: ANN001, ANN202
        status = original_generate(job_id, request)
        output = service.output_store.by_job[job_id][0]
        output.metadata["provider_reference_assets"][0]["identity_face_localization_applied"] = False
        output.metadata["provider_reference_assets"][0]["identity_face_localization_status"] = (
            "heuristic_fallback"
        )
        return status

    service.generate_job = unlocalized  # type: ignore[method-assign]
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]

    result = host.prepare(
        project_id="project_doc162",
        people_asset=_asset(),
        root_source_provenance=_root(),
    )

    assert result.status == "blocked"
    assert result.failure_codes == ["no_passing_front_candidate"]
    assert len(service.requests) == 3
    assert all(
        "professional_anchor_face_localization_unverified" in attempt.review.issue_codes
        for attempt in result.attempts
    )


def test_doc193_character_card_face_gate_ignores_pose_geometry_localization_scope(tmp_path) -> None:
    service = _SharedProductService()
    front = tmp_path / "front.png"
    right25 = tmp_path / "right25.png"
    selected_path = None
    _write_framing_card(front, top=0.14, height=0.70, left=0.28, width=0.44)
    _write_framing_card(right25, top=0.142, height=0.705, left=0.275, width=0.445)
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path=str(front))
    service.output_store.by_output["v3_output_right25"] = SimpleNamespace(file_path=str(right25))
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    job = service.create_professional_anchor_preparation_job(
        {"user_input": PREPARATION_INTENT},
        view_role="reverse_three_quarter",
        reference_evidence_ids=[
            "v3_asset_root",
            "v3_output_front",
            "v3_output_profile",
            "v3_output_right25",
        ],
        capture_scope="character_card_face_identity",
    )
    service.generate_job(job.job_id, {})
    selected = service.output_store.by_job[job.job_id][0]
    selected_path = str(selected.file_path)
    selected.metadata["provider_reference_assets"] = [
        {
            "provider_reference_derivative": True,
            "identity_evidence_scope": "pose_geometry",
            "identity_face_localization_applied": True,
            "identity_face_localization_status": "detected",
            "identity_nonidentity_pixel_suppression_profile": (
                "face_localized_nonidentity_suppression_v1"
            ),
        },
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
            "identity_evidence_scope": "card_framing",
            "derivative_kind": "character_card_full_frame_framing_reference",
            "identity_face_localization_applied": False,
            "identity_face_localization_status": "not_applicable",
        },
        {
            "provider_reference_derivative": True,
            "identity_evidence_scope": "pose_geometry",
            "identity_face_localization_applied": False,
            "identity_face_localization_status": "not_applicable",
        },
        {
            "provider_reference_derivative": True,
            "identity_evidence_scope": "feature_detail",
            "identity_face_localization_applied": True,
            "identity_face_localization_status": "detected",
            "identity_nonidentity_pixel_suppression_profile": (
                "face_localized_nonidentity_suppression_v1"
            ),
        },
    ]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {str(front): 0.160, str(right25): 0.154, selected_path: 0.132},
        {str(front): "front", str(right25): "left_three_quarter", selected_path: "left_three_quarter"},
        {str(front): 0.0, str(right25): 0.10, selected_path: 0.22},
    )
    request = AnchorGenerationRequest(
        project_id="project_doc193",
        people_asset_id="people_doc193",
        pack_version_id="pack_doc193",
        view_role="reverse_three_quarter",
        candidate_index=1,
        preparation_intent=PREPARATION_INTENT,
        root_source_asset_id="v3_asset_root",
        reference_evidence_ids=[
            "v3_asset_root",
            "v3_output_front",
            "v3_output_profile",
            "v3_output_right25",
        ],
        capture_scope="character_card_face_identity",
    )

    _candidate, decision = host._candidate_and_review(job.job_id, request)  # noqa: SLF001

    assert decision.status == "pass"
    assert "face_localized_identity_evidence_verified" in decision.identity_scores.evidence_codes
    assert "professional_anchor_face_localization_unverified" not in decision.issue_codes


def test_doc193_character_card_face_gate_still_requires_feature_detail_localization(tmp_path) -> None:
    service = _SharedProductService()
    front = tmp_path / "front.png"
    right25 = tmp_path / "right25.png"
    _write_framing_card(front, top=0.14, height=0.70, left=0.28, width=0.44)
    _write_framing_card(right25, top=0.142, height=0.705, left=0.275, width=0.445)
    service.output_store.by_output["v3_output_front"] = SimpleNamespace(file_path=str(front))
    service.output_store.by_output["v3_output_right25"] = SimpleNamespace(file_path=str(right25))
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]
    job = service.create_professional_anchor_preparation_job(
        {"user_input": PREPARATION_INTENT},
        view_role="reverse_three_quarter",
        reference_evidence_ids=[
            "v3_asset_root",
            "v3_output_front",
            "v3_output_profile",
            "v3_output_right25",
        ],
        capture_scope="character_card_face_identity",
    )
    service.generate_job(job.job_id, {})
    selected = service.output_store.by_job[job.job_id][0]
    selected.metadata["provider_reference_assets"] = [
        {
            "provider_reference_derivative": True,
            "identity_evidence_scope": "feature_detail",
            "identity_face_localization_applied": False,
            "identity_face_localization_status": "heuristic_fallback",
            "identity_nonidentity_pixel_suppression_profile": (
                "face_localized_nonidentity_suppression_v1"
            ),
        },
        {
            "provider_reference_derivative": True,
            "identity_evidence_scope": "card_framing",
            "derivative_kind": "character_card_full_frame_framing_reference",
            "identity_face_localization_applied": False,
            "identity_face_localization_status": "not_applicable",
        },
        {
            "provider_reference_derivative": True,
            "identity_evidence_scope": "pose_geometry",
            "identity_face_localization_applied": False,
            "identity_face_localization_status": "not_applicable",
        },
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
            "identity_evidence_scope": "pose_geometry",
            "identity_face_localization_applied": True,
            "identity_face_localization_status": "detected",
            "identity_nonidentity_pixel_suppression_profile": (
                "face_localized_nonidentity_suppression_v1"
            ),
        },
    ]
    host._identity_metric_provider = _FramingProfiler(  # noqa: SLF001
        {str(front): 0.160, str(right25): 0.154, str(selected.file_path): 0.132},
        {str(front): "front", str(right25): "left_three_quarter", str(selected.file_path): "left_three_quarter"},
        {str(front): 0.0, str(right25): 0.10, str(selected.file_path): 0.22},
    )
    request = AnchorGenerationRequest(
        project_id="project_doc193",
        people_asset_id="people_doc193",
        pack_version_id="pack_doc193",
        view_role="reverse_three_quarter",
        candidate_index=1,
        preparation_intent=PREPARATION_INTENT,
        root_source_asset_id="v3_asset_root",
        reference_evidence_ids=[
            "v3_asset_root",
            "v3_output_front",
            "v3_output_profile",
            "v3_output_right25",
        ],
        capture_scope="character_card_face_identity",
    )

    _candidate, decision = host._candidate_and_review(job.job_id, request)  # noqa: SLF001

    assert decision.status == "fail"
    assert "face_localized_identity_evidence_unverified" in decision.identity_scores.evidence_codes
    assert "professional_anchor_face_localization_unverified" in decision.issue_codes


def test_doc164_product_host_records_reference_parity_failure_without_crashing() -> None:
    service = _SharedProductService()
    original_generate = service.generate_job

    def wrong_reference_budget(job_id, request):  # noqa: ANN001, ANN202
        status = original_generate(job_id, request)
        output = service.output_store.by_job[job_id][0]
        output.metadata["provider_reference_image_count"] = 99
        return status

    service.generate_job = wrong_reference_budget  # type: ignore[method-assign]
    host = ProductApiAnchorPackPreparationHost(service)  # type: ignore[arg-type]

    result = host.prepare(
        project_id="project_doc162",
        people_asset=_asset(),
        root_source_provenance=_root(),
    )

    assert result.status == "blocked"
    assert result.failure_codes == ["no_passing_front_candidate"]
    assert len(result.generation_failures) == 3
    assert {
        item.failure_code for item in result.generation_failures
    } == {"professional_anchor_prompt_reference_parity_unverified"}


def test_doc163_selected_anchor_winner_has_canonical_provider_binding(tmp_path) -> None:
    upload_store = V3UploadedAssetStore(tmp_path / "uploads")
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    service = V3ProductApiService(asset_store=upload_store, output_store=output_store)
    image = Image.new("RGB", (64, 64), (130, 110, 100))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    upload = service.create_uploaded_asset(
        {
            "filename": "root.png",
            "mime_type": "image/png",
            "size_bytes": len(buffer.getvalue()),
            "role": "face_reference",
        }
    )
    service.store_uploaded_asset_content(
        upload.asset_id,
        {"content_base64": encoded, "mime_type": "image/png"},
    )
    service.complete_uploaded_asset(upload.asset_id)
    winner = output_store.save_base64_output(
        job_id="source_job",
        candidate_id="source_candidate",
        asset_id="source_asset",
        provider="test",
        model="test",
        encoded_image=encoded,
        mime_type="image/png",
    )
    request = CreateCreativeJobRequest(
        user_input="Prepare a supplementary anchor.",
        uploaded_asset_ids=[upload.asset_id],
    )

    references = service._professional_anchor_reference_assets(  # noqa: SLF001
        request,
        view_role="three_quarter",
        reference_evidence_ids=[upload.asset_id, winner.output_id],
    )

    assert len(references) == 1
    assert references[0]["asset_id"] == winner.output_id
    assert references[0]["output_id"] == winner.output_id
    assert references[0]["source_type"] == "selected_output"
    assert references[0]["role"] == "face_reference"
    assert references[0]["use_policy"] == "identity"
    assert references[0]["strength"] == "hard"
    assert references[0]["provider_input_required"] is True
    assert references[0]["metadata"]["canonical_output_binding"] is True
    assert references[0]["metadata"]["professional_anchor_lineage_evidence"] is True
    assert references[0]["metadata"]["professional_anchor_lineage_role"] == "prior_view_winner"


def test_doc164_runtime_freezes_selected_anchor_winner_as_output_reference(tmp_path) -> None:
    upload_store = V3UploadedAssetStore(tmp_path / "uploads")
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    service = V3ProductApiService(asset_store=upload_store, output_store=output_store)
    image = Image.new("RGB", (64, 64), (130, 110, 100))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    upload = service.create_uploaded_asset(
        {
            "filename": "root.png",
            "mime_type": "image/png",
            "size_bytes": len(buffer.getvalue()),
            "role": "face_reference",
        }
    )
    service.store_uploaded_asset_content(
        upload.asset_id,
        {"content_base64": encoded, "mime_type": "image/png"},
    )
    service.complete_uploaded_asset(upload.asset_id)
    winner = output_store.save_base64_output(
        job_id="source_job",
        candidate_id="source_candidate",
        asset_id="source_asset",
        provider="test",
        model="test",
        encoded_image=encoded,
        mime_type="image/png",
    )
    request = CreateCreativeJobRequest(
        user_input="Prepare a supplementary anchor.",
        uploaded_asset_ids=[upload.asset_id],
        metadata={
            "professional_anchor_reference_assets": service._professional_anchor_reference_assets(  # noqa: SLF001
                CreateCreativeJobRequest(
                    user_input="Prepare a supplementary anchor.",
                    uploaded_asset_ids=[upload.asset_id],
                ),
                view_role="three_quarter",
                reference_evidence_ids=[upload.asset_id, winner.output_id],
            )
        },
    )

    payload = service._runtime_request_payload(request)  # noqa: SLF001
    runtime_request = ScenarioRuntimeRequest.model_validate(payload)
    references = service.scenario_runtime._reference_assets_from_request_metadata(  # noqa: SLF001
        runtime_request
    )
    selected = next(item for item in references if item.get("asset_id") == winner.output_id)

    assert selected["output_id"] == winner.output_id
    assert selected["source_type"] == "selected_output"
    assert selected["use_policy"] == "identity"
    assert selected["strength"] == "hard"
    assert selected["provider_input_required"] is True
    assert selected["metadata"]["professional_anchor_lineage_role"] == "prior_view_winner"


def test_doc162_shared_review_receives_frozen_selected_winner_sources(tmp_path) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    image = Image.new("RGB", (32, 32), (120, 100, 90))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    winner = output_store.save_base64_output(
        job_id="source_job",
        candidate_id="source_candidate",
        asset_id="source_asset",
        provider="test",
        model="test",
        encoded_image=encoded,
        mime_type="image/png",
    )
    service = V3ProductApiService(output_store=output_store)
    request = CreateCreativeJobRequest(
        user_input="Prepare a supplementary anchor.",
        uploaded_asset_ids=[],
        metadata={
            "professional_anchor_reference_assets": [
                {"asset_id": winner.output_id, "metadata": {"source_type": "selected_output"}}
            ]
        },
    )
    record = ProductJobRecord(
        request=request,
        status=ProductJobStatusValue.GENERATED,
        job_id_value="job_review_projection",
    )
    resolution = SimpleNamespace(
        metadata={
            "candidate_metadata": {
                "reference_input_execution": {
                    "admission_outcome": "admitted",
                    "operation_outcome": "pixels_received",
                    "reference_count": 1,
                },
                "reference_truth_source_ids": [winner.output_id],
            }
        }
    )

    metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001

    assert metadata["review_reference_evidence_available"] is True
    assert metadata["reference_assets"] == [
        {
            "asset_id": winner.output_id,
            "output_id": winner.output_id,
            "role": "face_reference",
            "source_type": "selected_output",
            "use_policy": "admitted_generation_reference",
            "file_path": winner.file_path,
            "mime_type": "image/png",
        }
    ]
