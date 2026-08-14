"""Doc276 shared face-integrity delivery certification contracts.

These tests deliberately describe the missing foundation boundary. They use
only local pixels and static review providers; no test creates a project job or
contacts a generation, vision, or provider service.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image
from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.creative_core.rules import stable_id
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    GeneratedOutputResolution,
    VisionOutputInspector,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import (
    ReviewEvidenceChannel,
    ReviewEvidencePlan,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.review_evidence import (
    review_plan_digest,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
    active_review_contract,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc143_human_authenticity_review import (
    _plan_metadata,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc96_high_fidelity_identity import (
    _identity_review_metadata,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)
from alchemy_creative_agent_3_0.tests.test_v3_post_generation_vision_review import (
    _BoundReadyResolver,
    _StaticReadyResolver,
    _create_general_job,
    _internal_generation_metadata,
    _ready_resolution,
    _service,
)


class _StaticVisionProvider:
    provider_name = "doc276_static_vision"

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = dict(payload)
        self.calls = 0
        self.metadata_calls: list[dict[str, Any]] = []

    def available(self, *, force: bool = False) -> bool:  # noqa: ARG002
        return True

    def inspect(self, resolution, *, metadata=None):  # noqa: ANN001, ARG002
        self.calls += 1
        self.metadata_calls.append(dict(metadata or {}))
        return dict(self.payload)


class _UnavailableIdentityMetric:
    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, output_path, reference_paths):  # noqa: ANN001, ARG002
        self.calls += 1
        return {
            "status": "unavailable",
            "reason_codes": ["reference_face_not_detected", "multiple_output_faces"],
            "metadata": {"provider": "doc276_local_identity_metric"},
        }


def _png(path: Path, *, color: tuple[int, int, int]) -> Path:
    image = Image.new("RGB", (96, 128), color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    path.write_bytes(buffer.getvalue())
    return path


def _resolution(tmp_path: Path) -> GeneratedOutputResolution:
    path = _png(tmp_path / "reviewed-output.png", color=(132, 150, 166))
    return GeneratedOutputResolution(
        resolution_id="resolution_doc276",
        project_id="project_doc276",
        job_id="job_doc276",
        candidate_id="candidate_doc276",
        asset_id="asset_doc276",
        output_id="output_doc276",
        file_path=str(path),
        mime_type="image/png",
        width=96,
        height=128,
        status="ready",
    )


def _server_review_evidence_metadata(
    resolution: GeneratedOutputResolution,
    *,
    identity_required: bool,
) -> dict[str, Any]:
    """Model Product API's pre-provider, per-output evidence injection."""

    source_binding_digest = stable_id(
        "review_evidence_binding",
        resolution.job_id,
        resolution.output_id,
        "doc276_server_fixture",
    )
    channels = {
        "product_truth": ReviewEvidenceChannel(
            applicability="not_applicable",
            evidence_state="not_applicable",
        ),
        "person_identity": (
            ReviewEvidenceChannel(
                applicability="required",
                evidence_state="available",
                evidence_ids=["reference_doc276"],
                comparison_allowed=True,
                source_type="uploaded",
            )
            if identity_required
            else ReviewEvidenceChannel(
                applicability="not_applicable",
                evidence_state="not_applicable",
            )
        ),
        "prompt_semantics": ReviewEvidenceChannel(
            applicability="required",
            evidence_state="available",
            evidence_ids=["prompt_contract"],
            source_type="prompt_contract",
        ),
        "selected_output": ReviewEvidenceChannel(
            applicability="required",
            evidence_state="available",
            evidence_ids=[resolution.output_id],
            source_type="generated_output",
        ),
    }
    plan_data = {
        "contract_version": "review_evidence_plan_v1",
        "plan_id": stable_id(
            "review_evidence_plan",
            resolution.job_id,
            resolution.output_id,
            source_binding_digest,
        ),
        "job_id": resolution.job_id,
        "output_id": resolution.output_id,
        "review_mode": "real_pixel",
        "channels": {name: channel.model_dump(mode="json") for name, channel in channels.items()},
        "source_binding_digest": source_binding_digest,
    }
    plan_data["review_plan_digest"] = review_plan_digest(plan_data)
    plan = ReviewEvidencePlan.model_validate(plan_data)
    return {
        "review_evidence_plan": plan.model_dump(mode="json"),
        "review_evidence_plan_digest": plan.review_plan_digest,
        "review_evidence_plan_authority": "exact_review_evidence_resolver",
        "review_reference_evidence_required": identity_required,
        "review_reference_evidence_available": identity_required,
        "doc276_face_integrity_review_required": True,
    }


def _server_review_binding(
    resolution: GeneratedOutputResolution,
    *,
    metadata: dict[str, Any],
) -> dict[str, str]:
    """Derive the expected claim tuple solely from injected server metadata.

    Tests never let a provider-proposed value define the expected project, job,
    output, or evidence digest. This mirrors `_attach_post_generation_review`,
    which injects the resolver's exact per-output metadata before inspection.
    """

    raw_plan = metadata.get("review_evidence_plan")
    assert isinstance(raw_plan, dict)
    assert metadata.get("review_evidence_plan_authority") == "exact_review_evidence_resolver"
    plan = ReviewEvidencePlan.model_validate(raw_plan)
    assert metadata.get("review_evidence_plan_digest") == plan.review_plan_digest
    assert plan.job_id == resolution.job_id
    assert plan.output_id == resolution.output_id
    person_channel = plan.channels["person_identity"]
    reference_evidence_digest = stable_id(
        "review_reference_evidence",
        resolution.project_id,
        plan.job_id,
        plan.output_id,
        plan.source_binding_digest,
        ",".join(person_channel.evidence_ids),
    )
    return {
        "reviewed_project_id": resolution.project_id,
        "reviewed_job_id": plan.job_id,
        "reviewed_output_id": plan.output_id,
        "review_evidence_plan_digest": plan.review_plan_digest,
        "source_binding_digest": plan.source_binding_digest,
        "reference_evidence_digest": reference_evidence_digest,
    }


def _human_metadata(tmp_path: Path, *, identity_required: bool) -> dict[str, Any]:
    if identity_required:
        reference = _png(tmp_path / "identity-reference.png", color=(176, 156, 142))
        metadata = _identity_review_metadata(reference)
        metadata["uploaded_assets"][0]["asset_id"] = "reference_doc276"
        metadata["vision_inspection_mode"] = "vision_model"
        return metadata
    metadata = _plan_metadata()
    metadata["vision_inspection_mode"] = "vision_model"
    return metadata


def _inspection_metadata(
    tmp_path: Path,
    resolution: GeneratedOutputResolution,
    *,
    identity_required: bool,
) -> dict[str, Any]:
    """Return human review context plus Product API's private plan injection."""

    metadata = _human_metadata(tmp_path, identity_required=identity_required)
    metadata.update(
        _server_review_evidence_metadata(
            resolution,
            identity_required=identity_required,
        )
    )
    return metadata


def _passing_human_payload() -> dict[str, Any]:
    return {
        "status": "pass",
        "confidence": 0.98,
        "issue_codes": [],
        "scores": {
            "same_person_readability": 0.99,
            "identity_consistency": 0.99,
            "human_realism": 0.98,
        },
        "human_naturalness_verdict": {"status": "pass", "issue_codes": []},
    }


def _face_integrity_attestation(
    status: str,
    *,
    binding: dict[str, str],
    issue_codes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "doc276_face_integrity_attestation_v1",
        "status": status,
        **binding,
        "primary_face_scope": "visible_primary_face",
        "issue_codes": list(issue_codes or []),
    }


def _reference_comparison_certification(*, binding: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "doc276_reference_comparison_certification_v1",
        "status": "pass",
        **binding,
        "primary_face_scope": "visible_primary_face",
    }


def test_doc276_identity_metric_unavailable_cannot_auto_certify_high_provider_scores(tmp_path: Path) -> None:
    """A visible locked identity needs explicit comparison and face evidence."""

    identity_metric = _UnavailableIdentityMetric()
    resolution = _resolution(tmp_path)
    metadata = _inspection_metadata(tmp_path, resolution, identity_required=True)
    report = VisionOutputInspector(
        vision_provider=_StaticVisionProvider(_passing_human_payload()),
        identity_metric_provider=identity_metric,
    ).inspect(resolution, metadata=metadata)

    assert identity_metric.calls == 1
    assert report.evidence["identity_metric"]["status"] == "unavailable"
    assert report.status == "manual_review"
    attestation = report.evidence["face_integrity_attestation"]
    assert attestation["status"] == "not_verifiable"
    assert attestation["primary_face_scope"] == "visible_primary_face"
    assert report.evidence["reference_comparison_certification"]["status"] == "missing"


def test_doc276_explicit_provider_face_and_reference_certifications_can_cover_unavailable_metric(
    tmp_path: Path,
) -> None:
    resolution = _resolution(tmp_path)
    metadata = _inspection_metadata(tmp_path, resolution, identity_required=True)
    binding = _server_review_binding(resolution, metadata=metadata)
    payload = _passing_human_payload()
    payload["face_integrity_attestation"] = _face_integrity_attestation("pass", binding=binding)
    payload["reference_comparison_certification"] = _reference_comparison_certification(binding=binding)
    identity_metric = _UnavailableIdentityMetric()
    provider = _StaticVisionProvider(payload)

    report = VisionOutputInspector(
        vision_provider=provider,
        identity_metric_provider=identity_metric,
    ).inspect(resolution, metadata=metadata)

    assert identity_metric.calls == 1
    assert provider.metadata_calls == [metadata]
    assert provider.metadata_calls[0]["review_evidence_plan_digest"] == binding["review_evidence_plan_digest"]
    assert provider.metadata_calls[0]["review_evidence_plan_authority"] == "exact_review_evidence_resolver"
    assert report.status == "pass"
    assert report.evidence["face_integrity_attestation"] == _face_integrity_attestation("pass", binding=binding)
    assert report.evidence["reference_comparison_certification"] == _reference_comparison_certification(binding=binding)


def test_doc276_vision_prompt_requires_the_server_injected_opaque_binding(tmp_path: Path) -> None:
    resolution = _resolution(tmp_path)
    metadata = _inspection_metadata(tmp_path, resolution, identity_required=True)
    binding = _server_review_binding(resolution, metadata=metadata)
    metadata["doc276_expected_face_binding"] = binding

    prompt = _inspection_prompt(metadata)

    assert "face_integrity_attestation" in prompt
    assert "reference_comparison_certification" in prompt
    for value in binding.values():
        assert value in prompt


def test_doc276_provider_cannot_self_exempt_an_expected_primary_face(tmp_path: Path) -> None:
    resolution = _resolution(tmp_path)
    metadata = _inspection_metadata(tmp_path, resolution, identity_required=True)
    binding = _server_review_binding(resolution, metadata=metadata)
    payload = _passing_human_payload()
    face = _face_integrity_attestation("pass", binding=binding)
    face["primary_face_scope"] = "no_visible_primary_face"
    payload["face_integrity_attestation"] = face
    payload["reference_comparison_certification"] = _reference_comparison_certification(binding=binding)

    report = VisionOutputInspector(
        vision_provider=_StaticVisionProvider(payload),
        identity_metric_provider=_UnavailableIdentityMetric(),
    ).inspect(resolution, metadata=metadata)

    assert report.status == "manual_review"
    assert report.evidence["face_integrity_attestation"]["status"] == "not_verifiable"


def test_doc276_browser_metadata_cannot_enable_the_server_rollout_gate(tmp_path: Path) -> None:
    provider = _StaticVisionProvider(_passing_human_payload())
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(_ready_resolution(tmp_path)),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = _create_general_job(service)

    service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {
                "vision_inspection_mode": "vision_model",
                "doc276_face_integrity_review_required": True,
            },
        },
    )

    package = _internal_generation_metadata(service, created.job_id)["post_generation_review_package"]
    assert package.get("doc276_face_integrity_review_required") is not True


@pytest.mark.parametrize(
    "corruption",
    [
        "face_wrong_output",
        "face_wrong_job",
        "face_wrong_project",
        "face_wrong_plan_digest",
        "face_missing_source_digest",
        "comparison_wrong_reference_digest",
        "comparison_cross_output",
        "comparison_unknown_field",
    ],
)
def test_doc276_provider_face_and_comparison_claims_require_exact_server_review_bindings(
    tmp_path: Path,
    corruption: str,
) -> None:
    resolution = _resolution(tmp_path)
    metadata = _inspection_metadata(tmp_path, resolution, identity_required=True)
    binding = _server_review_binding(resolution, metadata=metadata)
    face = _face_integrity_attestation("pass", binding=binding)
    comparison = _reference_comparison_certification(binding=binding)
    if corruption == "face_wrong_output":
        face["reviewed_output_id"] = "output_other"
    elif corruption == "face_wrong_job":
        face["reviewed_job_id"] = "job_other"
    elif corruption == "face_wrong_project":
        face["reviewed_project_id"] = "project_other"
    elif corruption == "face_wrong_plan_digest":
        face["review_evidence_plan_digest"] = stable_id("review_plan", "other")
    elif corruption == "face_missing_source_digest":
        face.pop("source_binding_digest")
    elif corruption == "comparison_wrong_reference_digest":
        comparison["reference_evidence_digest"] = stable_id("review_reference_evidence", "other")
    elif corruption == "comparison_cross_output":
        comparison["reviewed_output_id"] = "output_other"
    else:
        comparison["untrusted_provider_note"] = "must_not_extend_schema"
    payload = _passing_human_payload()
    payload["face_integrity_attestation"] = face
    payload["reference_comparison_certification"] = comparison
    provider = _StaticVisionProvider(payload)

    report = VisionOutputInspector(
        vision_provider=provider,
        identity_metric_provider=_UnavailableIdentityMetric(),
    ).inspect(resolution, metadata=metadata)

    assert provider.metadata_calls == [metadata]
    assert provider.metadata_calls[0]["review_evidence_plan_digest"] == binding["review_evidence_plan_digest"]
    assert report.status == "manual_review"
    assert report.evidence["face_integrity_attestation"]["status"] == "not_verifiable"
    assert report.evidence["reference_comparison_certification"]["status"] == "not_verifiable"


@pytest.mark.parametrize("issue_code", ["human_anatomy_or_proportion", "human_expression_context"])
def test_doc276_face_integrity_retry_issue_is_shared_retry_evidence_not_final_delivery(
    tmp_path: Path,
    issue_code: str,
) -> None:
    resolution = _resolution(tmp_path)
    metadata = _inspection_metadata(tmp_path, resolution, identity_required=False)
    binding = _server_review_binding(resolution, metadata=metadata)
    payload = _passing_human_payload()
    payload.update(
        {
            "status": "fail_retryable",
            "issue_codes": [issue_code],
            "human_naturalness_verdict": {
                "status": "retry_recommended",
                "issue_codes": [issue_code],
            },
            "face_integrity_attestation": _face_integrity_attestation(
                "retry_recommended",
                binding=binding,
                issue_codes=[issue_code],
            ),
        }
    )
    report = VisionOutputInspector(
        vision_provider=_StaticVisionProvider(payload)
    ).inspect(resolution, metadata=metadata)

    assert report.status == "fail_retryable"
    assert report.retryable is True
    attestation = report.evidence["face_integrity_attestation"]
    assert attestation["status"] == "retry_recommended"
    assert attestation["retry_authority"] == "shared_brain_authored_bounded_quality_retry"
    assert attestation["max_retry_attempts"] == 1


def test_doc276_nonhuman_and_no_reference_general_flows_remain_open(tmp_path: Path) -> None:
    metadata = {"vision_inspection_mode": "vision_model"}
    report = VisionOutputInspector(
        vision_provider=_StaticVisionProvider({"status": "pass", "confidence": 0.95, "issue_codes": []})
    ).inspect(_resolution(tmp_path), metadata=metadata)

    assert active_review_contract(metadata).get("human_naturalness_verdict_required") is not True
    assert report.status == "pass"
    assert report.retryable is False
    assert not report.detected_issues


def test_doc276_default_output_contract_gates_non_enforced_human_reviews(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_DOC276_FACE_INTEGRITY_DELIVERY_ENABLED", "true")
    result = SimpleNamespace(
        series_plan=SimpleNamespace(
            assets=[
                SimpleNamespace(
                    asset_id="asset_visible",
                    priority=1,
                    metadata={},
                )
            ]
        )
    )

    contracts = V3ProductApiService._frozen_output_review_contracts_by_asset_id(  # noqa: SLF001
        result,
        {},
    )

    assert contracts == {
        "asset_visible": {
            "source": "product_api_default_output_review_contract",
            "deliverable_id": "output_1",
            "primary_face_visibility_expected": True,
        }
    }
    metadata = _non_enforced_server_human_review_metadata()
    assert active_review_contract(metadata)["enforced"] is False
    assert active_review_contract(metadata)["human_naturalness_verdict_required"] is True
    assert V3ProductApiService()._doc276_face_integrity_review_required(  # noqa: SLF001
        metadata,
        contracts["asset_visible"],
    ) is True


def test_doc276_server_human_contract_requires_live_pixel_review_without_reference() -> None:
    """A frozen human contract must not be downgraded by an empty reference set."""

    service = V3ProductApiService()
    metadata = {
        **_plan_metadata(),
        "require_real_images": True,
        # These are public request-shaped escape hatches for the legacy
        # reference path. They must not defeat the server-issued contract.
        "disable_real_vision_inspection": True,
        "vision_inspection_mode": "metadata_only",
    }

    assert active_review_contract(metadata)["requires_pixel_review"] is True
    assert service._reference_conditioned_real_review_required(  # noqa: SLF001
        metadata,
        quality_mode="standard",
    ) is False
    assert service._server_required_real_pixel_review(  # noqa: SLF001
        metadata,
        quality_mode="standard",
    ) is True
    assert service._server_required_real_pixel_review(  # noqa: SLF001
        metadata,
        quality_mode="explore",
    ) is False


def test_doc276_non_enforced_human_generation_persists_the_required_face_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_DOC276_FACE_INTEGRITY_DELIVERY_ENABLED", "true")
    provider = _StaticVisionProvider(_passing_human_payload())
    service = _service(
        tmp_path,
        output_resolver=_Doc276BoundReadyResolver(_ready_resolution(tmp_path)),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = _create_general_job(service)
    _install_server_owned_human_review_contract(service, created.job_id)

    service.generate_job(
        created.job_id,
        {
            "quality_mode": "explore",
            "metadata": {"vision_inspection_mode": "vision_model"},
        },
    )

    package = _internal_generation_metadata(service, created.job_id)["post_generation_review_package"]
    required_output_ids = package["doc276_face_integrity_required_output_ids"]
    assert required_output_ids == [package["inspections"][0]["output_id"]]
    assert package["inspections"][0]["evidence"]["face_integrity_attestation"]["status"] == "not_verifiable"
    delivery, eligible_outputs, eligible_assets = service._public_final_delivery_projection(  # noqa: SLF001
        service.get_job_record(created.job_id).generation_result
    )
    assert delivery["final_delivery_status"] == "withheld_manual_confirmation"
    assert eligible_outputs == set()
    assert eligible_assets == set()
    assert provider.calls == 1


def _install_server_owned_human_review_contract(
    service: V3ProductApiService,
    job_id: str,
) -> None:
    """Seed only an existing server-planned Human Realism contract for review.

    The fixture uses the same frozen planner metadata exercised by Doc143. It
    deliberately does not place a review contract in browser request metadata.
    """

    record = service.get_job_record(job_id)
    assert record is not None and record.planning_result is not None
    record.planning_result = record.planning_result.model_copy(
        update={
            "metadata": {
                **dict(record.planning_result.metadata or {}),
                **_plan_metadata(),
            }
        }
    )


def _non_enforced_server_human_review_metadata() -> dict[str, Any]:
    """Return an existing Human Realism contract without an execution ledger."""

    human_contract = active_review_contract(_plan_metadata())["human_authenticity_contract"]
    return {
        "visual_cluster": {
            "composed_visual_contribution": {
                "active_capability_ids": ["human_realism"],
                "review_contracts": [
                    {
                        "capability_id": "human_realism",
                        "human_naturalness_verdict_required": True,
                        "human_authenticity_contract": human_contract,
                    }
                ],
            }
        }
    }


class _Doc276BoundReadyResolver(_BoundReadyResolver):
    """Bind the local review pixel to the generated asset and a durable test ID."""

    def resolve_result(self, result, project_id: str | None = None):  # noqa: ANN001
        resolution = super().resolve_result(result, project_id=project_id)[0]
        output_id = str(resolution.output_id or resolution.asset_id or "").strip()
        assert output_id
        return [resolution.model_copy(update={"output_id": output_id})]


def test_doc276_explicit_frozen_no_face_output_does_not_need_face_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_DOC276_FACE_INTEGRITY_DELIVERY_ENABLED", "true")
    result = SimpleNamespace(
        series_plan=SimpleNamespace(
            assets=[
                SimpleNamespace(asset_id="asset_visible", priority=1, metadata={}),
                SimpleNamespace(asset_id="asset_rear", priority=2, metadata={}),
            ]
        )
    )
    review_metadata = {
        "capability_execution_envelope": {
            "resolved_constraint_ledger": {
                "provider_projection": {
                    "deliverables": [
                        {"output_index": 1, "deliverable_id": "front", "metadata": {}},
                        {
                            "output_index": 2,
                            "deliverable_id": "rear",
                            "metadata": {"primary_face_visibility_expected": False},
                        },
                    ]
                }
            }
        }
    }
    contracts = V3ProductApiService._frozen_output_review_contracts_by_asset_id(  # noqa: SLF001
        result,
        review_metadata,
    )
    assert contracts["asset_visible"]["primary_face_visibility_expected"] is True
    assert contracts["asset_rear"]["primary_face_visibility_expected"] is False
    metadata = _non_enforced_server_human_review_metadata()
    service = V3ProductApiService()
    assert service._doc276_face_integrity_review_required(metadata, contracts["asset_visible"]) is True  # noqa: SLF001
    assert service._doc276_face_integrity_review_required(metadata, contracts["asset_rear"]) is False  # noqa: SLF001

    delivery, eligible_outputs, eligible_assets = V3ProductApiService()._public_final_delivery_projection(  # noqa: SLF001
        SimpleNamespace(
            metadata={
                "post_generation_review_package": {
                    "review_evidence_receipt_status": "complete",
                    "doc276_face_integrity_required_output_ids": ["output_visible"],
                    "inspections": [
                        {
                            "output_id": "output_visible",
                            "asset_id": "asset_visible",
                            "mode": "hybrid",
                            "verification_state": "verified",
                            "status": "pass",
                            "evidence": {
                                "face_integrity_attestation": {"status": "pass"},
                                "reference_comparison_certification": {"status": "not_required"},
                            },
                        },
                        {
                            "output_id": "output_rear",
                            "asset_id": "asset_rear",
                            "mode": "hybrid",
                            "verification_state": "verified",
                            "status": "pass",
                            "evidence": {},
                        },
                    ],
                }
            }
        )
    )

    assert delivery["final_delivery_status"] == "ready"
    assert eligible_outputs == {"output_visible", "output_rear"}
    assert eligible_assets == {"asset_visible", "asset_rear"}


def test_doc276_legitimate_frozen_no_visible_primary_face_remains_deliverable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A trusted rear/obscured contract is not a provider-created exemption."""

    monkeypatch.setenv("V3_DOC276_FACE_INTEGRITY_DELIVERY_ENABLED", "true")
    metadata = _non_enforced_server_human_review_metadata()
    metadata["vision_inspection_mode"] = "vision_model"
    report = VisionOutputInspector(
        vision_provider=_StaticVisionProvider(_passing_human_payload())
    ).inspect(_resolution(tmp_path), metadata=metadata)

    assert V3ProductApiService()._doc276_face_integrity_review_required(  # noqa: SLF001
        metadata,
        {
            "source": "resolved_constraint_ledger",
            "deliverable_id": "rear_obscured",
            "primary_face_visibility_expected": False,
        },
    ) is False
    assert report.status == "pass"
    assert "face_integrity_attestation" not in report.evidence


def test_doc276_uncertified_human_review_cannot_enter_final_delivery_and_legacy_stays_history() -> None:
    result = SimpleNamespace(
        metadata={
            "post_generation_review_package": {
                "review_evidence_receipt_status": "complete",
                "inspections": [
                    {
                        "output_id": "output_doc276",
                        "asset_id": "asset_doc276",
                        "mode": "hybrid",
                        "verification_state": "verified",
                        "status": "pass",
                        "evidence": {
                            "face_integrity_attestation": {"status": "missing"},
                            "identity_metric": {"status": "unavailable"},
                        },
                    }
                ],
            }
        }
    )

    delivery, eligible_outputs, eligible_assets = V3ProductApiService()._public_final_delivery_projection(result)  # noqa: SLF001

    assert delivery["automatic_delivery_available"] is False
    assert delivery["final_delivery_status"] == "withheld_manual_confirmation"
    assert eligible_outputs == set()
    assert eligible_assets == set()


def test_doc276_missing_required_review_row_cannot_be_covered_by_another_passing_output() -> None:
    result = SimpleNamespace(
        metadata={
            "post_generation_review_package": {
                "review_evidence_receipt_status": "complete",
                "doc276_face_integrity_required_output_ids": ["output_requires_face_receipt"],
                "inspections": [
                    {
                        "output_id": "output_other",
                        "asset_id": "asset_other",
                        "mode": "hybrid",
                        "verification_state": "verified",
                        "status": "pass",
                        "evidence": {
                            "face_integrity_attestation": {"status": "pass"},
                            "reference_comparison_certification": {"status": "not_required"},
                        },
                    }
                ],
            }
        }
    )

    delivery, eligible_outputs, eligible_assets = V3ProductApiService()._public_final_delivery_projection(result)  # noqa: SLF001

    assert delivery["final_delivery_status"] == "withheld_manual_confirmation"
    assert delivery["automatic_delivery_available"] is False
    assert eligible_outputs == set()
    assert eligible_assets == set()


def test_doc276_project_operation_does_not_mislabel_another_manual_hold_as_face_integrity() -> None:
    result = SimpleNamespace(
        metadata={
            "post_generation_review_package": {
                "doc276_face_integrity_required_output_ids": ["output_face_checked"],
                "inspections": [
                    {
                        "output_id": "output_face_checked",
                        "evidence": {
                            "face_integrity_attestation": {"status": "pass"},
                            "reference_comparison_certification": {"status": "not_required"},
                        },
                    }
                ],
            }
        }
    )
    record = SimpleNamespace(generation_result=result, planning_result=None)

    class ProductServiceStub:
        @staticmethod
        def get_job_record(job_id: str):  # noqa: ANN001
            return record if job_id == "job_doc276" else None

        @staticmethod
        def _doc276_face_integrity_delivery_certified(inspection, *, required):  # noqa: ANN001
            return required and inspection.get("evidence", {}).get("face_integrity_attestation", {}).get("status") == "pass"

        @staticmethod
        def _public_final_delivery_projection(value):  # noqa: ANN001
            assert value is result
            return ({"final_delivery_status": "withheld_manual_confirmation"}, set(), set())

    project_service = object.__new__(V3ProjectModeService)
    project_service.product_service = ProductServiceStub()

    assert project_service._doc276_face_integrity_current_operation(SimpleNamespace(job_ids=["job_doc276"])) is None  # noqa: SLF001


def test_doc276_face_retry_uses_existing_bounded_append_only_authority_without_history_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_DOC276_FACE_INTEGRITY_DELIVERY_ENABLED", "true")
    retry_payload = {
        "status": "fail_retryable",
        "confidence": 0.94,
        "issue_codes": ["visible_text_artifact", "human_rendering_artifact"],
        "human_naturalness_verdict": {
            "status": "retry_recommended",
            "issue_codes": ["human_rendering_artifact"],
        },
    }
    class BoundRetryVisionProvider:
        provider_name = "doc276_bound_retry_vision"

        def __init__(self) -> None:
            self.calls: list[GeneratedOutputResolution] = []

        def available(self, *, force: bool = False) -> bool:  # noqa: ARG002
            return True

        def inspect(self, resolution, *, metadata=None):  # noqa: ANN001
            self.calls.append(resolution)
            assert isinstance(metadata, dict)
            assert metadata.get("doc276_face_integrity_review_required") is True
            binding = _server_review_binding(
                resolution,
                metadata=metadata,
            )
            return {
                **retry_payload,
                "face_integrity_attestation": _face_integrity_attestation(
                    "retry_recommended",
                    binding=binding,
                    issue_codes=["human_rendering_artifact"],
                ),
                "reference_comparison_certification": _reference_comparison_certification(
                    binding=binding,
                ),
            }

    provider = BoundRetryVisionProvider()
    service = _service(
        tmp_path,
        output_resolver=_Doc276BoundReadyResolver(_ready_resolution(tmp_path)),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = _create_general_job(service)
    _install_server_owned_human_review_contract(service, created.job_id)
    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {"vision_inspection_mode": "vision_model", "max_visual_retry_attempts": 1},
        },
    )

    internal_review = _internal_generation_metadata(service, created.job_id)["post_generation_review_package"]
    assert internal_review["review_evidence_receipt_status"] == "complete", internal_review.get("review_evidence_receipt_errors")
    assert "face_integrity_attestation" in internal_review["inspections"][0]["evidence"], internal_review["inspections"][0]["evidence"]
    assert internal_review["inspections"][0]["evidence"]["face_integrity_attestation"]["status"] == "retry_recommended"
    assert internal_review["inspections"][0]["status"] == "fail_retryable"
    assert len(provider.calls) == 2
    assert generated.metadata["visual_auto_retry"]["max_attempts"] == 1
    assert generated.metadata["visual_auto_retry"]["executed_count"] == 1
    assert [attempt["stage"] for attempt in internal_review["review_attempts"]] == ["initial", "final_retry"]
    record = service.get_job_record(created.job_id)
    assert record is not None and record.generation_result is not None
    assert len(record.generation_result.asset_pack.assets) >= 2
    calls_before_read = len(provider.calls)
    assert service.get_job(created.job_id).job_id == created.job_id
    assert len(provider.calls) == calls_before_read
    assert internal_review["face_integrity_retry_receipt"] == {
        "maximum_attempts": 1,
        "historical_job_replay": False,
        "append_only": True,
    }


def _face_withheld_project(template_id: str) -> dict[str, Any]:
    return {
        "project_id": "doc276-project",
        "primary_template_id": template_id,
        "job_ids": ["doc276-history-job"],
        "metadata": {
            "current_operation": {
                "state": "review_withheld_face_integrity",
                "terminal": True,
                "pending": False,
                "next_actions": [{"id": "review_generation_history"}],
            }
        },
    }


@pytest.mark.parametrize("template_id", ["general_template", "ecommerce_template", "photography_template"])
def test_doc276_desktop_and_h5_face_withheld_terminal_state_has_one_local_review_action(
    template_id: str,
) -> None:
    project = _face_withheld_project(template_id)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for html_path, script_path, state, action_selector, action_attr, progress_selector in (
                (
                    DESKTOP_HTML,
                    DESKTOP_JS,
                    "v3State",
                    "[data-v3-project-action='review_generation_history']",
                    "data-v3-project-action",
                    "#v3ProgressDetail",
                ),
                (
                    MOBILE_HTML,
                    MOBILE_JS,
                    "mobileV3State",
                    "[data-mobile-v3-project-action='review_generation_history']",
                    "data-mobile-v3-project-action",
                    "#mobileV3ProgressDetail",
                ),
            ):
                page = _browser_page(browser, html_path=html_path, script_path=script_path)
                if state == "v3State":
                    page.evaluate(
                        """
                        (project) => {
                          window.__doc263ServerProject = project;
                          v3State.currentProject = project;
                          v3State.currentJob = { job_id: "doc276-history-job", status: "blocked", warnings: ["raw internal face digest"] };
                          v3State.selectedScenario = project.primary_template_id === "ecommerce_template"
                            ? "ecommerce"
                            : project.primary_template_id === "photography_template"
                              ? "photography"
                              : "general_creative";
                          v3State.loading = true;
                          v3State.progressStageKey = "planning";
                          v3State.progressTimer = window.setTimeout(() => {}, 10000);
                          renderV3ProjectDetail();
                        }
                        """,
                        project,
                    )
                else:
                    page.evaluate(
                        """
                        (project) => {
                          ensureMobileLayers();
                          setupMobileV3Adapter();
                          window.__doc263ServerProject = project;
                          mobileV3State.currentProject = project;
                          mobileV3State.projects = [project];
                          mobileV3State.currentJob = { job_id: "doc276-history-job", status: "blocked", warnings: ["raw internal face digest"] };
                          mobileV3State.selectedTemplate = project.primary_template_id;
                          mobileV3State.loading = true;
                          mobileV3State.progressStageKey = "planning";
                          mobileV3State.progressTimer = window.setTimeout(() => {}, 10000);
                          renderMobileV3ProjectCurrentOperation(project);
                        }
                        """,
                        project,
                    )

                assert page.locator(action_selector).count() == 1
                assert page.locator(f"[{action_attr}]").count() == 1
                assert page.evaluate(f"{state}.loading") is False
                assert page.evaluate(f"{state}.progressStageKey") in {None, "failed"}
                assert page.evaluate(f"{state}.progressTimer") is None
                public_text = page.locator("body").inner_text()
                assert "raw internal face digest" not in public_text
                assert "preparing" not in public_text.lower()
                assert "generating" not in public_text.lower()
                progress = page.locator(progress_selector)
                progress_text = progress.inner_text() if progress.count() else ""
                assert "preparing" not in progress_text.lower()
                page.locator(action_selector).click()
                assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
        finally:
            browser.close()
