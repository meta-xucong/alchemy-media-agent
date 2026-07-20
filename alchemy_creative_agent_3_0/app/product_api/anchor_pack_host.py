"""Product API-backed Professional Face Identity anchor preparation host.

The host adapts the existing bounded AnchorPack orchestration to the ordinary
ScenarioRuntime -> Remote Brain -> shared Provider -> shared Vision path.  It
does not author provider prompts, perform a private review, or persist a
second candidate/delivery lifecycle.
"""

from __future__ import annotations

from typing import Any

from ..visual_assets.anchor_pack import (
    AnchorCandidateResult,
    AnchorCandidateUnavailable,
    AnchorGenerationRequest,
    AnchorPackPreparationRequest,
    AnchorPackPreparationResult,
    AnchorPackPreparationService,
    AnchorReviewDecision,
)
from ..visual_assets.contracts import (
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    PeopleAsset,
    RootSourceProvenance,
)
from .contracts import ProductJobStatusValue
from .service import V3ProductApiService


class ProductApiAnchorPackPreparationHost:
    """Concrete host that keeps all creative and pixel work in shared V3."""

    _EXPECTED_PROVIDER_REFERENCE_COUNTS = {
        "standard_front": 2,
        "three_quarter": 3,
        "profile": 5,
    }
    _REQUIRED_SCORE_DIMENSIONS = {
        "same_person_readability",
        "distinctive_feature_readability",
        "human_realism",
        "pose_compliance",
        "visual_quality",
        "ai_overperfection_penalty",
    }

    def __init__(self, service: V3ProductApiService) -> None:
        self.product_service = service
        self._review_by_candidate_id: dict[str, AnchorReviewDecision] = {}
        self._stage_plan_source_job_ids: dict[tuple[str, str], str] = {}
        self._stage_visual_retry_consumed: set[tuple[str, str]] = set()
        self._orchestrator = AnchorPackPreparationService(
            generator=self,
            reviewer=self,
            catalog=service.visual_asset_catalog,
        )

    def prepare(
        self,
        *,
        project_id: str,
        people_asset: PeopleAsset,
        root_source_provenance: RootSourceProvenance,
    ) -> AnchorPackPreparationResult:
        return self._orchestrator.prepare(
            AnchorPackPreparationRequest(
                project_id=project_id,
                asset=people_asset,
                root_source_provenance=root_source_provenance,
                preparation_intent=people_asset.preparation_intent,
            )
        )

    def activate(
        self,
        pack: IdentityAnchorPackVersion,
        *,
        confirmed: bool,
    ) -> IdentityAnchorPackVersion:
        return self._orchestrator.activate(pack, confirmed=confirmed)

    def generate(self, request: AnchorGenerationRequest) -> AnchorCandidateResult:
        """Materialize one bounded candidate through the ordinary Product API."""

        stage_key = (request.pack_version_id, request.view_role)
        # At the first stage both admitted source uploads are direct evidence.
        # Once a reviewed winner exists, the serial chain deliberately returns
        # to the primary root plus selected outputs; the supplementary image
        # is not silently carried into later views.
        uploaded_asset_ids = (
            list(request.reference_evidence_ids)
            if request.view_role == "standard_front"
            else [request.root_source_asset_id]
        )
        status = self.product_service.create_professional_anchor_preparation_job(
            {
                "user_input": request.preparation_intent,
                "scenario_selection": {"scenario_id": "general_creative"},
                "uploaded_asset_ids": uploaded_asset_ids,
                "metadata": {
                    "project_id": request.project_id,
                    "requested_image_count": 1,
                    "require_real_images": True,
                    "professional_people_asset_id": request.people_asset_id,
                    "professional_anchor_pack_version_id": request.pack_version_id,
                    "professional_anchor_candidate_index": request.candidate_index,
                },
            },
            view_role=request.view_role,
            reference_evidence_ids=list(request.reference_evidence_ids),
            stage_plan_source_job_id=self._stage_plan_source_job_ids.get(stage_key),
        )
        if status.status != ProductJobStatusValue.PLANNED:
            raise AnchorCandidateUnavailable("professional_anchor_candidate_planning_blocked")
        self._stage_plan_source_job_ids.setdefault(stage_key, status.job_id)
        # The stage owns one shared bounded repair. A Provider failure with no
        # reviewed pixels must not consume it merely because it happened on
        # candidate one; the first candidate that actually executes the
        # shared visual retry consumes the budget for all later candidates.
        retry_available = stage_key not in self._stage_visual_retry_consumed
        generation = self.product_service.generate_job(
            status.job_id,
            {
                "quality_mode": "strict",
                "metadata": (
                    {"max_visual_retry_attempts": 1}
                    if retry_available
                    else {"disable_visual_auto_retry": True, "max_visual_retry_attempts": 0}
                ),
            },
        )
        self._record_stage_visual_retry_usage(stage_key, status.job_id)
        if generation.status not in {ProductJobStatusValue.GENERATED, ProductJobStatusValue.SELECTED}:
            raise AnchorCandidateUnavailable("professional_anchor_candidate_generation_failed")
        candidate, review = self._candidate_and_review(status.job_id, request)
        self._review_by_candidate_id[candidate.candidate_id] = review
        return candidate

    def _record_stage_visual_retry_usage(
        self,
        stage_key: tuple[str, str],
        job_id: str,
    ) -> None:
        """Consume the one stage repair only after shared runtime executed it."""

        record = self.product_service.get_job_record(job_id)
        result = record.generation_result if record is not None else None
        metadata = result.metadata if result is not None and isinstance(result.metadata, dict) else {}
        summary = metadata.get("visual_auto_retry")
        summary = summary if isinstance(summary, dict) else {}
        try:
            executed_count = int(summary.get("executed_count") or 0)
        except (TypeError, ValueError):
            executed_count = 0
        if executed_count > 0:
            self._stage_visual_retry_consumed.add(stage_key)

    def review(self, candidate: AnchorCandidateResult) -> AnchorReviewDecision:
        decision = self._review_by_candidate_id.get(candidate.candidate_id)
        if decision is None:
            raise RuntimeError("professional_anchor_shared_review_missing")
        return decision

    def _candidate_and_review(
        self,
        job_id: str,
        request: AnchorGenerationRequest,
    ) -> tuple[AnchorCandidateResult, AnchorReviewDecision]:
        record = self.product_service.get_job_record(job_id)
        result = record.generation_result if record is not None else None
        if result is None:
            raise RuntimeError("professional_anchor_generation_result_missing")
        package = result.metadata.get("post_generation_review_package")
        inspections = [
            dict(item)
            for item in (package.get("inspections", []) if isinstance(package, dict) else [])
            if isinstance(item, dict)
        ]
        outputs = self.product_service.output_store.list_by_job(job_id)
        if not outputs or not inspections:
            raise RuntimeError("professional_anchor_real_pixel_review_missing")
        inspection_by_output = {
            str(item.get("output_id") or ""): item
            for item in inspections
            if str(item.get("output_id") or "").strip()
        }
        reviewed = [item for item in outputs if item.output_id in inspection_by_output]
        if not reviewed:
            raise RuntimeError("professional_anchor_review_output_binding_missing")
        selected = max(reviewed, key=lambda item: self._review_rank(inspection_by_output[item.output_id]))
        inspection = inspection_by_output[selected.output_id]
        score_card = {
            str(key): float(value)
            for key, value in dict(inspection.get("score_card") or {}).items()
            if isinstance(value, (int, float))
        }
        missing_dimensions = sorted(self._REQUIRED_SCORE_DIMENSIONS - set(score_card))
        verified = (
            str(inspection.get("mode") or "").strip().lower() in {"vision_model", "hybrid"}
            and str(inspection.get("verification_state") or "").strip().lower() == "verified"
        )
        output_metadata = dict(selected.metadata or {})
        expected_reference_count = self._EXPECTED_PROVIDER_REFERENCE_COUNTS[request.view_role]
        prompt_hash = str(output_metadata.get("provider_prompt_sha256") or "").strip()
        provider_reference_assets = [
            dict(item)
            for item in output_metadata.get("provider_reference_assets", [])
            if isinstance(item, dict) and item.get("provider_reference_derivative")
        ]
        face_localization_verified = bool(
            len(provider_reference_assets) == expected_reference_count
            and all(
                item.get("identity_face_localization_applied") is True
                and item.get("identity_face_localization_status") == "detected"
                and item.get("identity_nonidentity_pixel_suppression_profile")
                == "face_localized_nonidentity_suppression_v1"
                for item in provider_reference_assets
            )
        )
        parity_verified = bool(
            prompt_hash
            and str(output_metadata.get("prompt_compilation_id") or "").strip()
            and int(output_metadata.get("provider_reference_image_count") or 0) == expected_reference_count
        )
        if not parity_verified:
            raise AnchorCandidateUnavailable(
                "professional_anchor_prompt_reference_parity_unverified"
            )
        candidate = AnchorCandidateResult(
            candidate_id=selected.candidate_id,
            view_id=f"view_{selected.output_id}",
            output_id=selected.output_id,
            view_role=request.view_role,
            candidate_index=request.candidate_index,
            source_candidate_ids=[item.candidate_id for item in outputs],
            source_asset_ids=list(request.reference_evidence_ids),
            brain_plan_id=result.planning_result_id,
            canonical_prompt_hash=prompt_hash,
            prompt_compilation_id=str(output_metadata.get("prompt_compilation_id") or ""),
            prompt_reference_parity_verified=parity_verified,
        )
        raw_status = str(inspection.get("status") or "").strip().lower()
        passes = (
            verified
            and raw_status in {"pass", "warning"}
            and not missing_dimensions
            and face_localization_verified
        )
        raw_issues = inspection.get("issue_codes")
        if not isinstance(raw_issues, list):
            raw_issues = inspection.get("detected_issues")
        issue_codes = []
        for item in raw_issues if isinstance(raw_issues, list) else []:
            code = item.get("code") if isinstance(item, dict) else item
            if str(code or "").strip():
                issue_codes.append(str(code).strip())
        if missing_dimensions:
            issue_codes.append("professional_anchor_review_score_incomplete")
        if not face_localization_verified:
            issue_codes.append("professional_anchor_face_localization_unverified")
        decision = AnchorReviewDecision(
            status="pass" if passes else "fail",
            identity_scores=IdentityScoreSummary(
                same_face_score=score_card.get("same_person_readability", 0.0),
                visual_quality_score=score_card.get("visual_quality", score_card.get("overall", 0.0)),
                distinctive_feature_score=score_card.get("distinctive_feature_readability", 0.0),
                human_realism_score=score_card.get("human_realism", 0.0),
                pose_compliance_score=score_card.get("pose_compliance", 0.0),
                ai_overperfection_penalty=score_card.get("ai_overperfection_penalty", 1.0),
                evidence_codes=[
                    "shared_real_pixel_review_verified" if verified else "shared_real_pixel_review_unverified",
                    "canonical_prompt_reference_parity_verified",
                    *(
                        ["face_localized_identity_evidence_verified"]
                        if face_localization_verified
                        else ["face_localized_identity_evidence_unverified"]
                    ),
                ] if parity_verified else ["shared_real_pixel_review_verified" if verified else "shared_real_pixel_review_unverified"],
            ),
            issue_codes=list(dict.fromkeys(issue_codes)),
        )
        return candidate, decision

    @staticmethod
    def _review_rank(inspection: dict[str, Any]) -> tuple[int, float, float]:
        verified = str(inspection.get("verification_state") or "").strip().lower() == "verified"
        passed = str(inspection.get("status") or "").strip().lower() in {"pass", "warning"}
        scores = inspection.get("score_card") if isinstance(inspection.get("score_card"), dict) else {}
        return (
            int(verified and passed),
            float(scores.get("same_person_readability") or 0.0),
            float(scores.get("overall") or 0.0),
        )

__all__ = ["ProductApiAnchorPackPreparationHost"]
