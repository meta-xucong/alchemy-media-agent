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
from ..visual_assets.character_card import (
    BodyPreparationRequest,
    CharacterCardCandidateRequest,
    CharacterCardCandidateResult,
    CharacterCardPreparationService,
    CharacterCardSharedRuntimeReceipt,
    CharacterCardSharedRuntimeFailureReceipt,
    CharacterCardStageResult,
    CharacterCardState,
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
        "reverse_three_quarter": 5,
        "rear_head": 5,
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
        self._character_card_reviews: dict[str, AnchorReviewDecision] = {}
        self._character_card_retry_counts: dict[tuple[str, str], int] = {}
        self._orchestrator = AnchorPackPreparationService(
            generator=self,
            reviewer=self,
            catalog=service.visual_asset_catalog,
        )

    production_shared_runtime = True

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

    def prepare_character_card(
        self,
        *,
        project_id: str,
        people_asset: PeopleAsset,
        root_source_provenance: RootSourceProvenance,
        resume_from_pack: IdentityAnchorPackVersion | None = None,
        generation_channel: str = "provider",
    ) -> AnchorPackPreparationResult:
        """Reuse the same host for the two additive Doc178 Face slots."""

        return self._orchestrator.prepare(
            AnchorPackPreparationRequest(
                project_id=project_id,
                asset=people_asset,
                root_source_provenance=root_source_provenance,
                preparation_intent=people_asset.preparation_intent,
                face_view_scope="character_card",
                generation_channel=generation_channel if generation_channel in {"provider", "mcp"} else "provider",
            ),
            resume_from_pack=resume_from_pack,
        )

    def activate(
        self,
        pack: IdentityAnchorPackVersion,
        *,
        confirmed: bool,
    ) -> IdentityAnchorPackVersion:
        return self._orchestrator.activate(pack, confirmed=confirmed)

    def generate(
        self,
        request: AnchorGenerationRequest | CharacterCardCandidateRequest,
    ) -> AnchorCandidateResult | CharacterCardCandidateResult:
        """Materialize one bounded candidate through the ordinary Product API."""

        if isinstance(request, CharacterCardCandidateRequest):
            return self._generate_character_card_candidate(request)

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
        job_request = {
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
        }
        job_kwargs = {
            "view_role": request.view_role,
            "reference_evidence_ids": list(request.reference_evidence_ids),
            "stage_plan_source_job_id": self._stage_plan_source_job_ids.get(stage_key),
        }
        if request.capture_scope != "anchor_pack":
            job_kwargs["capture_scope"] = request.capture_scope
        # Existing Provider host seams keep their original call contract. The
        # extra fields are needed only when the explicitly selected MCP
        # renderer must recover an opaque handoff after a pending run.
        if request.generation_channel == "mcp":
            job_request["metadata"].update(
                generation_channel="mcp",
                mcp_operation_id=request.mcp_operation_id,
            )
            job_kwargs.update(
                generation_channel="mcp",
                mcp_operation_id=request.mcp_operation_id,
            )
        status = self.product_service.create_professional_anchor_preparation_job(job_request, **job_kwargs)
        if status.status != ProductJobStatusValue.PLANNED:
            record = self.product_service.get_job_record(status.job_id)
            request_metadata = dict(record.request.metadata) if record is not None else {}
            remote_outcome = request_metadata.get("remote_creative_brain_outcome")
            if isinstance(remote_outcome, dict):
                reason_code = str(remote_outcome.get("reason_code") or "").strip()
                if reason_code in {"remote_brain_unavailable", "remote_brain_unauthorized"}:
                    raise AnchorCandidateUnavailable(reason_code)
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

    def review(
        self,
        candidate: AnchorCandidateResult | CharacterCardCandidateResult,
    ) -> AnchorReviewDecision:
        if isinstance(candidate, CharacterCardCandidateResult):
            decision = self._character_card_reviews.get(candidate.candidate_id)
            if decision is None:
                raise RuntimeError("character_card_shared_review_missing")
            return decision
        decision = self._review_by_candidate_id.get(candidate.candidate_id)
        if decision is None:
            raise RuntimeError("professional_anchor_shared_review_missing")
        return decision

    def prepare_expression_set(
        self, *, asset: Any, card: CharacterCardState, generation_channel: str = "provider"
    ) -> CharacterCardStageResult:
        front_output_id = str(card.face_slots["face.front"].output_id or "").strip()
        if not front_output_id:
            raise ValueError("character_card_expression_front_winner_missing")
        preparation = CharacterCardPreparationService(generator=self, reviewer=self)
        base_intent = str(getattr(asset, "preparation_intent", "") or "").strip()
        if not base_intent:
            raise ValueError("character_card_expression_intent_missing")
        result = preparation.prepare_expression_set(
            card,
            front_output_id=front_output_id,
            project_id=f"visual_asset_{asset.visual_asset_id}",
            people_asset_id=asset.visual_asset_id,
            user_intents={key: base_intent for key in ("smile", "anger", "sad")},
            generation_channel=generation_channel if generation_channel in {"provider", "mcp"} else "provider",
        )
        return self._attach_character_card_receipt(result, asset=asset, stage="expression_set")

    def prepare_body_silhouette(
        self,
        *,
        asset: Any,
        card: CharacterCardState,
        request: Any = None,
        generation_channel: str = "provider",
    ) -> CharacterCardStageResult:
        if request is None:
            raise ValueError("character_card_body_source_required")
        face_reference_output_ids = [
            str(card.face_slots[key].output_id or "").strip()
            for key in ("face.front", "face.profile", "face.rear_head")
        ]
        if any(not item for item in face_reference_output_ids):
            raise ValueError("character_card_body_face_winners_missing")
        body_evidence_ids = (
            [str(request.body_reference_asset_id)]
            if request.source_class == "observed" and request.body_reference_asset_id
            else []
        )
        user_intent = str(request.body_facts or getattr(asset, "preparation_intent", "") or "").strip()
        if not user_intent:
            raise ValueError("character_card_body_intent_missing")
        preparation = CharacterCardPreparationService(generator=self, reviewer=self)
        result = preparation.prepare_body_silhouette(
            card,
            face_reference_output_ids=face_reference_output_ids,
            source_class=request.source_class,
            project_id=f"visual_asset_{asset.visual_asset_id}",
            people_asset_id=asset.visual_asset_id,
            body_evidence_ids=body_evidence_ids,
            consent_provenance_id=getattr(asset.root_source_provenance, "consent_reference", None),
            user_intent=user_intent,
            generation_channel=generation_channel if generation_channel in {"provider", "mcp"} else "provider",
        )
        return self._attach_character_card_receipt(result, asset=asset, stage="body_silhouette")

    def _attach_character_card_receipt(
        self,
        result: CharacterCardStageResult,
        *,
        asset: Any,
        stage: str,
    ) -> CharacterCardStageResult:
        stage_key = (asset.visual_asset_id, stage)
        retry_count = self._character_card_retry_counts.get(stage_key, 0)
        if result.status != "review":
            return result.model_copy(
                update={
                    "shared_runtime_failure": CharacterCardSharedRuntimeFailureReceipt(
                        failure_count=max(
                            1,
                            min(
                                3,
                                len(result.failures)
                                or int(getattr(result.card, "last_failure_attempt_count", 0) or 0)
                                or len(result.failure_codes)
                                or 3,
                            ),
                        ),
                    )
                }
            )
        return result.model_copy(
            update={
                "shared_runtime_receipt": CharacterCardSharedRuntimeReceipt(
                    retry_count=retry_count,
                    final_winner_selection_verified=bool(result.winner_output_ids),
                    prompt_reference_parity_verified=all(
                        attempt.candidate.prompt_reference_parity_verified
                        for attempt in result.attempts
                    ),
                )
            }
        )

    def _generate_character_card_candidate(
        self,
        request: CharacterCardCandidateRequest,
    ) -> CharacterCardCandidateResult:
        stage_key = (request.people_asset_id, request.module, request.slot_key)
        status = self.product_service.create_professional_character_card_stage_job(
            {
                "user_input": request.user_intent,
                "scenario_selection": {"scenario_id": "general_creative"},
                "metadata": {
                    "project_id": request.project_id,
                    "requested_image_count": 1,
                    "require_real_images": True,
                },
            },
            stage=request.module,
            slot_key=request.slot_key,
            reference_output_ids=request.reference_output_ids,
            source_class=request.source_class,
            generation_channel=request.generation_channel,
            mcp_operation_id=f"{request.people_asset_id}:{request.module}:{request.slot_key}:{request.candidate_index}",
        )
        if status.status != ProductJobStatusValue.PLANNED:
            raise AnchorCandidateUnavailable("character_card_candidate_planning_blocked")
        generation = self.product_service.generate_job(
            status.job_id,
            {"quality_mode": "strict", "metadata": {"max_visual_retry_attempts": 1}},
        )
        self._record_character_card_retry_usage(stage_key, status.job_id)
        if generation.status not in {ProductJobStatusValue.GENERATED, ProductJobStatusValue.SELECTED}:
            generation_metadata = getattr(generation, "metadata", {})
            mcp_materialization = (
                generation_metadata.get("mcp_materialization")
                if isinstance(generation_metadata, dict)
                else None
            )
            handoff_id = (
                str(mcp_materialization.get("handoff_id") or "").strip()
                if isinstance(mcp_materialization, dict)
                else ""
            )
            if request.generation_channel == "mcp" and handoff_id:
                raise AnchorCandidateUnavailable(
                    "mcp_materialization_pending"
                    if str(mcp_materialization.get("status") or "").lower() == "pending"
                    else "mcp_materialization_failed",
                    mcp_handoff_id=handoff_id,
                )
            raise AnchorCandidateUnavailable("character_card_candidate_generation_failed")
        candidate, review = self._character_card_candidate_and_review(status.job_id, request)
        self._character_card_reviews[candidate.candidate_id] = review
        return candidate

    def _record_character_card_retry_usage(self, stage_key: tuple[str, str, str], job_id: str) -> None:
        record = self.product_service.get_job_record(job_id)
        result = record.generation_result if record is not None else None
        metadata = result.metadata if result is not None and isinstance(result.metadata, dict) else {}
        retry = metadata.get("visual_auto_retry")
        if isinstance(retry, dict) and int(retry.get("executed_count") or 0) > 0:
            self._character_card_retry_counts[(stage_key[0], stage_key[1])] = (
                self._character_card_retry_counts.get((stage_key[0], stage_key[1]), 0) + 1
            )

    def _character_card_candidate_and_review(
        self,
        job_id: str,
        request: CharacterCardCandidateRequest,
    ) -> tuple[CharacterCardCandidateResult, AnchorReviewDecision]:
        record = self.product_service.get_job_record(job_id)
        result = record.generation_result if record is not None else None
        if result is None:
            raise RuntimeError("character_card_generation_result_missing")
        package = result.metadata.get("post_generation_review_package")
        inspections = [
            dict(item)
            for item in (package.get("inspections", []) if isinstance(package, dict) else [])
            if isinstance(item, dict)
        ]
        outputs = self.product_service.output_store.list_by_job(job_id)
        if not outputs or not inspections:
            raise RuntimeError("character_card_real_pixel_review_missing")
        by_output = {
            str(item.get("output_id") or ""): item
            for item in inspections
            if str(item.get("output_id") or "").strip()
        }
        reviewed = [item for item in outputs if item.output_id in by_output]
        if not reviewed:
            raise RuntimeError("character_card_review_output_binding_missing")
        selected = max(reviewed, key=lambda item: self._review_rank(by_output[item.output_id]))
        inspection = by_output[selected.output_id]
        score_card = {
            str(key): float(value)
            for key, value in dict(inspection.get("score_card") or {}).items()
            if isinstance(value, (int, float))
        }
        verified = (
            str(inspection.get("mode") or "").strip().lower() in {"vision_model", "hybrid"}
            and str(inspection.get("verification_state") or "").strip().lower() == "verified"
        )
        output_metadata = dict(selected.metadata or {})
        expected_refs = 2 if request.module == "expression_set" else 3
        parity = bool(
            str(output_metadata.get("provider_prompt_sha256") or "").strip()
            and str(output_metadata.get("prompt_compilation_id") or "").strip()
            and int(output_metadata.get("provider_reference_image_count") or 0) == expected_refs
        )
        candidate = CharacterCardCandidateResult(
            candidate_id=selected.candidate_id,
            output_id=selected.output_id,
            module=request.module,
            slot_key=request.slot_key,
            candidate_index=request.candidate_index,
            source_candidate_ids=[item.candidate_id for item in outputs],
            source_output_ids=list(request.reference_output_ids),
            canonical_prompt_hash=str(output_metadata.get("provider_prompt_sha256") or ""),
            prompt_compilation_id=str(output_metadata.get("prompt_compilation_id") or ""),
            prompt_reference_parity_verified=parity,
        )
        raw_issues = inspection.get("issue_codes") or inspection.get("detected_issues") or []
        issue_codes = [
            str(item.get("code") if isinstance(item, dict) else item).strip()
            for item in raw_issues
            if str(item.get("code") if isinstance(item, dict) else item).strip()
        ]
        review = AnchorReviewDecision(
            status="pass" if verified and str(inspection.get("status") or "").lower() in {"pass", "warning"} and parity else "fail",
            identity_scores=IdentityScoreSummary(
                same_face_score=score_card.get("same_person_readability", score_card.get("identity", 0.0)),
                visual_quality_score=score_card.get("visual_quality", score_card.get("overall", 0.0)),
                distinctive_feature_score=score_card.get("distinctive_feature_readability", 0.0),
                human_realism_score=score_card.get("human_realism", 0.0),
                pose_compliance_score=score_card.get("pose_compliance", 0.0),
                ai_overperfection_penalty=score_card.get("ai_overperfection_penalty", 1.0),
                evidence_codes=["shared_real_pixel_review_verified" if verified else "shared_real_pixel_review_unverified"],
            ),
            issue_codes=list(dict.fromkeys(issue_codes)),
        )
        return candidate, review

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
        required_dimensions = set(self._REQUIRED_SCORE_DIMENSIONS)
        if request.capture_scope == "character_card_face_identity":
            # Face Identity establishes facial evidence. Body proportion and
            # full-body pose belong to the later Body Silhouette module.
            required_dimensions.discard("pose_compliance")
        missing_dimensions = sorted(required_dimensions - set(score_card))
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
                pose_compliance_score=score_card.get(
                    "pose_compliance",
                    1.0 if request.capture_scope == "character_card_face_identity" else 0.0,
                ),
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
