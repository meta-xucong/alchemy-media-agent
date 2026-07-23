"""Product API-backed Professional Face Identity anchor preparation host.

The host adapts the existing bounded AnchorPack orchestration to the ordinary
ScenarioRuntime -> Remote Brain -> shared Provider -> shared Vision path.  It
does not author provider prompts, perform a private review, or persist a
second candidate/delivery lifecycle.
"""

from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Any

from PIL import Image

from ..shared_capabilities.visual_cluster.expression_review import project_laugh_expression_review_receipt
from ..shared_capabilities.visual_cluster.identity_metric import create_default_identity_metric_provider
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

    _ANCHOR_PACK_PROVIDER_REFERENCE_COUNTS = {
        "standard_front": 2,
        "three_quarter": 3,
        "profile": 5,
    }
    _CHARACTER_CARD_PROVIDER_REFERENCE_COUNTS = {
        "standard_front": 2,
        "left_front_25": 3,
        "three_quarter": 5,
        "profile": 5,
        "right_front_25": 5,
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
    _CHARACTER_CARD_FACE_CLARITY_FLOORS = {
        "visual_quality": 0.90,
        "technical_finish": 0.88,
        "human_realism": 0.82,
    }
    _CHARACTER_CARD_FACE_IDENTITY_FLOORS = {
        "same_person_readability": 0.88,
        "distinctive_feature_readability": 0.78,
        "developmental_age_coherence": 0.86,
        "prompt_owned_channel_obedience": 0.78,
        # For Character Card Face Identity this score means face-view slot
        # compliance (front/left45/profile/right45/rear), not full-body pose.
        "pose_compliance": 0.80,
        "neutral_capture_compliance": 0.82,
    }
    _CHARACTER_CARD_PROFILE_CONTINUITY_FLOORS = {
        # A strict side-profile card exposes a different subset of the face
        # than a front or 45-degree card.  Keep commercial clarity and
        # child/pose compliance strict, but let same-person readability use a
        # cross-angle continuity floor instead of the front-facing geometry
        # target that can otherwise reject a valid 90-degree profile.
        "same_person_readability": 0.80,
        "distinctive_feature_readability": 0.76,
        "developmental_age_coherence": 0.86,
        "prompt_owned_channel_obedience": 0.78,
        "pose_compliance": 0.86,
        "neutral_capture_compliance": 0.82,
    }
    _CHARACTER_CARD_REAR_HEAD_CONTINUITY_FLOORS = {
        # Rear-head cards intentionally hide the face, so shared Vision may
        # score face-specific readability lower while still verifying the
        # non-face continuity evidence (hair mass, crown, neck, shoulders).
        # Keep visible face slots on the stricter FACE_IDENTITY floors.
        "same_person_readability": 0.70,
        "distinctive_feature_readability": 0.65,
        "developmental_age_coherence": 0.86,
        "prompt_owned_channel_obedience": 0.78,
        "pose_compliance": 0.86,
        "neutral_capture_compliance": 0.82,
    }
    _CHARACTER_CARD_FACE_FRAMING_PARITY_MAX_RELATIVE_DELTA = 0.05
    _CHARACTER_CARD_FOREGROUND_HEIGHT_MAX_RELATIVE_DELTA = 0.10
    _CHARACTER_CARD_FOREGROUND_WIDTH_MAX_RELATIVE_DELTA = 0.28
    _CHARACTER_CARD_HEAD_TOP_MARGIN_MAX_ABSOLUTE_DELTA = 0.045
    _CHARACTER_CARD_SHOULDER_PADDING_MAX_ABSOLUTE_DELTA = 0.055
    _CHARACTER_CARD_FRONT_25_MIN_VIEW_MAGNITUDE = 0.060
    _CHARACTER_CARD_FRONT_25_MAX_VIEW_MAGNITUDE = 0.24
    _CHARACTER_CARD_FRONT_45_HARD_MIN_VIEW_MAGNITUDE = 0.10
    _CHARACTER_CARD_FRONT_45_MIN_VIEW_MAGNITUDE = 0.15
    _CHARACTER_CARD_FRONT_45_MAX_VIEW_MAGNITUDE = 0.38
    _CHARACTER_CARD_FRONT_25_FACE_FRAMING_PARITY_MAX_RELATIVE_DELTA = 0.08
    _CHARACTER_CARD_FRONT_45_FACE_FRAMING_PARITY_MAX_RELATIVE_DELTA = 0.10
    _CHARACTER_CARD_SCORE_FLOOR_EPSILON = 0.005

    def __init__(self, service: V3ProductApiService) -> None:
        self.product_service = service
        self._review_by_candidate_id: dict[str, AnchorReviewDecision] = {}
        self._stage_plan_source_job_ids: dict[tuple[str, str], str] = {}
        self._stage_visual_retry_consumed: set[tuple[str, str]] = set()
        self._character_card_reviews: dict[str, AnchorReviewDecision] = {}
        self._character_card_retry_counts: dict[tuple[str, str], int] = {}
        self._identity_metric_provider: Any | None = None
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
        pending_mcp_handoff_ids: list[str] | None = None,
    ) -> AnchorPackPreparationResult:
        """Reuse the same host for the two additive Doc178 Face slots."""

        safe_resume_from_pack = self._sanitize_character_card_resume_pack(
            resume_from_pack
        )
        return self._orchestrator.prepare(
            AnchorPackPreparationRequest(
                project_id=project_id,
                asset=people_asset,
                root_source_provenance=root_source_provenance,
                preparation_intent=people_asset.preparation_intent,
                face_view_scope="character_card",
                generation_channel=generation_channel if generation_channel in {"provider", "mcp"} else "provider",
                pending_mcp_handoff_ids=list(pending_mcp_handoff_ids or []),
            ),
            resume_from_pack=safe_resume_from_pack,
        )

    def _sanitize_character_card_resume_pack(
        self,
        resume_from_pack: IdentityAnchorPackVersion | None,
    ) -> IdentityAnchorPackVersion | None:
        """Drop stale accepted checkpoints that fail the current card contract.

        Character Card Face Identity evolved from a loose three-view anchor pack
        into a fixed card matrix.  Older failed packs can therefore contain
        "accepted" continuation views that were produced before the current
        left/right 45° and fixed-framing gates existed.  Resuming from such a
        checkpoint would let a non-canonical left 45° contaminate the independent opposite
        right 45°, profile, rear, Expression Set and Body Silhouette stages.

        Keep only the longest valid prefix.  Later views and their old failure
        receipts are discarded so the shared bounded candidate budget restarts
        from the first invalid slot instead of silently continuing from stale
        evidence.
        """

        if resume_from_pack is None:
            return None
        if resume_from_pack.status != "failed":
            return resume_from_pack
        ordered_roles = (
            "standard_front",
            *AnchorPackPreparationService.CHARACTER_CARD_SUPPLEMENTARY_ROLES,
        )
        active_views = [view for view in resume_from_pack.anchor_views if view.active]
        valid_prefix = []
        for index, view in enumerate(active_views):
            expected_role = ordered_roles[index] if index < len(ordered_roles) else None
            if view.view_role != expected_role:
                break
            if not self._character_card_resume_view_checkpoint_verified(
                view,
                prior_views=valid_prefix,
            ):
                break
            valid_prefix.append(view)
        if len(valid_prefix) == len(active_views):
            return resume_from_pack
        valid_roles = {view.view_role for view in valid_prefix}
        retained_failures = [
            failure
            for failure in resume_from_pack.candidate_failures
            if failure.view_role in valid_roles
        ]
        return resume_from_pack.model_copy(
            update={
                "anchor_views": valid_prefix,
                "candidate_failures": retained_failures,
            }
        )

    def _character_card_resume_view_checkpoint_verified(
        self,
        view,
        *,
        prior_views: list,
    ) -> bool:
        output = self.product_service.output_store.get_output(view.output_id)
        if output is None or not str(getattr(output, "file_path", "") or "").strip():
            return False
        file_path = Path(str(output.file_path))
        provider = self._character_card_identity_metric_provider()
        profile = provider.profile_reference(file_path)
        if profile.get("status") != "ready":
            return False
        hint = str(profile.get("view_hint") or "").strip().lower()
        if view.view_role == "standard_front":
            return hint == "front"
        if view.view_role == "left_front_25":
            return (
                not self._character_card_front_25_view_depth_issues(
                    profile,
                    expected_side="right",
                )
                and self._character_card_resume_view_framing_verified(
                    view,
                    prior_views=prior_views,
                )
            )
        if view.view_role == "three_quarter":
            return (
                hint == "right_three_quarter"
                and not self._character_card_front_45_view_depth_issues(
                    profile
                )
                and self._character_card_resume_view_framing_verified(
                    view,
                    prior_views=prior_views,
                )
            )
        if view.view_role == "profile":
            return (
                hint in {"right_profile", "left_profile"}
                and self._character_card_resume_view_framing_verified(
                    view,
                    prior_views=prior_views,
                )
            )
        if view.view_role == "right_front_25":
            return (
                not self._character_card_front_25_view_depth_issues(
                    profile,
                    expected_side="left",
                )
                and self._character_card_resume_view_framing_verified(
                    view,
                    prior_views=prior_views,
                )
            )
        if view.view_role == "reverse_three_quarter":
            if hint != "left_three_quarter":
                return False
            if self._character_card_front_45_view_depth_issues(profile):
                return False
            baseline = next(
                (item for item in prior_views if item.view_role == "three_quarter"),
                None,
            )
            if baseline is None:
                return False
            baseline_output = self.product_service.output_store.get_output(
                baseline.output_id
            )
            if baseline_output is None or not str(getattr(baseline_output, "file_path", "") or "").strip():
                return False
            baseline_profile = provider.profile_reference(Path(str(baseline_output.file_path)))
            return (
                baseline_profile.get("status") == "ready"
                and str(baseline_profile.get("view_hint") or "").strip().lower()
                == "right_three_quarter"
                and not self._character_card_front_45_view_depth_issues(
                    baseline_profile
                )
                and self._character_card_resume_view_framing_verified(
                    view,
                    prior_views=prior_views,
                )
            )
        if view.view_role == "rear_head":
            return self._character_card_resume_view_framing_verified(
                view,
                prior_views=prior_views,
            )
        return False

    def _character_card_resume_view_framing_verified(
        self,
        view,
        *,
        prior_views: list,
    ) -> bool:
        selected_output = self.product_service.output_store.get_output(view.output_id)
        if selected_output is None or not str(getattr(selected_output, "file_path", "") or "").strip():
            return False
        selected_path = Path(str(selected_output.file_path))
        baseline_role = (
            "left_front_25"
            if view.view_role == "three_quarter"
            else "right_front_25"
            if view.view_role == "reverse_three_quarter"
            else "standard_front"
        )
        baseline_view = next((item for item in prior_views if item.view_role == baseline_role), None)
        if baseline_view is None:
            return False
        baseline_output = self.product_service.output_store.get_output(baseline_view.output_id)
        if baseline_output is None or not str(getattr(baseline_output, "file_path", "") or "").strip():
            return False
        baseline_path = Path(str(baseline_output.file_path))
        selected_box = _foreground_card_box(selected_path)
        baseline_box = _foreground_card_box(baseline_path)
        if not selected_box or not baseline_box:
            return False
        return not self._character_card_foreground_framing_issues(
            view.view_role,
            selected_box,
            baseline_box,
        )

    def activate(
        self,
        pack: IdentityAnchorPackVersion,
        *,
        confirmed: bool,
    ) -> IdentityAnchorPackVersion:
        return self._orchestrator.activate(pack, confirmed=confirmed)

    @classmethod
    def _expected_provider_reference_count(cls, request: AnchorGenerationRequest) -> int:
        if request.capture_scope == "character_card_face_identity":
            return cls._CHARACTER_CARD_PROVIDER_REFERENCE_COUNTS[request.view_role]
        return cls._ANCHOR_PACK_PROVIDER_REFERENCE_COUNTS[request.view_role]

    def generate(
        self,
        request: AnchorGenerationRequest | CharacterCardCandidateRequest,
    ) -> AnchorCandidateResult | CharacterCardCandidateResult:
        """Materialize one bounded candidate through the ordinary Product API."""

        if isinstance(request, CharacterCardCandidateRequest):
            return self._generate_character_card_candidate(request)

        if (
            request.generation_channel == "mcp"
            and str(request.mcp_handoff_id or "").strip()
            and not self._mcp_anchor_handoff_matches_current_contract(request)
        ):
            request = request.model_copy(update={"mcp_handoff_id": None})

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
            if request.mcp_handoff_id:
                job_request["metadata"]["mcp_materialization"] = {
                    "handoff_id": request.mcp_handoff_id,
                    "status": "pending",
                    "generation_channel": "mcp",
                    "resume_required": True,
                }
            job_kwargs.update(
                generation_channel="mcp",
                mcp_operation_id=request.mcp_operation_id,
            )
        resume_record = self._mcp_resume_planned_job_record(request) if request.generation_channel == "mcp" else None
        if resume_record is None:
            status = self.product_service.create_professional_anchor_preparation_job(job_request, **job_kwargs)
            status_job_id = status.job_id
            status_value = status.status
        else:
            status = None
            status_job_id = resume_record.job_id
            if getattr(resume_record, "generation_result", None) is not None:
                try:
                    candidate, review = self._candidate_and_review(status_job_id, request)
                except RuntimeError as exc:
                    if str(exc) != "professional_anchor_real_pixel_review_missing":
                        raise
                    # A local MCP/process interruption may leave a job after
                    # artifact materialization but before the shared
                    # post-generation review package is persisted. Treat that
                    # as an unfinished finalization checkpoint and re-enter
                    # the ordinary generate_job path for the same frozen job.
                    status_value = ProductJobStatusValue.PLANNED
                else:
                    self._review_by_candidate_id[candidate.candidate_id] = review
                    self._record_stage_visual_retry_usage(stage_key, status_job_id)
                    return candidate
            else:
                status_value = ProductJobStatusValue.PLANNED
        if status_value != ProductJobStatusValue.PLANNED:
            record = self.product_service.get_job_record(status.job_id)
            request_metadata = dict(record.request.metadata) if record is not None else {}
            remote_outcome = request_metadata.get("remote_creative_brain_outcome")
            if isinstance(remote_outcome, dict):
                reason_code = str(remote_outcome.get("reason_code") or "").strip()
                if reason_code in {"remote_brain_unavailable", "remote_brain_unauthorized"}:
                    raise AnchorCandidateUnavailable(reason_code)
            raise AnchorCandidateUnavailable("professional_anchor_candidate_planning_blocked")
        self._stage_plan_source_job_ids.setdefault(stage_key, status_job_id)
        # The stage owns one shared bounded repair. A Provider failure with no
        # reviewed pixels must not consume it merely because it happened on
        # candidate one; the first candidate that actually executes the
        # shared visual retry consumes the budget for all later candidates.
        retry_available = stage_key not in self._stage_visual_retry_consumed
        generation = self.product_service.generate_job(
            status_job_id,
            {
                "quality_mode": "strict",
                "metadata": (
                    {
                        "max_visual_retry_attempts": 1,
                        **(
                            {"_v3_resume_finalizing_review": True}
                            if resume_record is not None and request.generation_channel == "mcp"
                            else {}
                        ),
                    }
                    if retry_available
                    else {
                        "disable_visual_auto_retry": True,
                        "max_visual_retry_attempts": 0,
                        **(
                            {"_v3_resume_finalizing_review": True}
                            if resume_record is not None and request.generation_channel == "mcp"
                            else {}
                        ),
                    }
                ),
            },
        )
        self._record_stage_visual_retry_usage(stage_key, status_job_id)
        if generation.status not in {ProductJobStatusValue.GENERATED, ProductJobStatusValue.SELECTED}:
            mcp_materialization = self._mcp_materialization_from_generation_failure(generation, status_job_id)
            handoff_id = (
                str(mcp_materialization.get("handoff_id") or "").strip()
                if isinstance(mcp_materialization, dict)
                else ""
            )
            if request.generation_channel == "mcp" and handoff_id:
                materialization_payload = self._mcp_materialization_payload(handoff_id)
                if not self._mcp_anchor_materialization_matches_current_contract(
                    request,
                    materialization_payload
                    if isinstance(materialization_payload, dict)
                    else mcp_materialization,
                ):
                    raise AnchorCandidateUnavailable(
                        "professional_anchor_mcp_prompt_contract_stale"
                    )
                raise AnchorCandidateUnavailable(
                    "mcp_materialization_pending"
                    if str(mcp_materialization.get("status") or "").lower() == "pending"
                    else "mcp_materialization_failed",
                    mcp_handoff_id=handoff_id,
                )
            raise AnchorCandidateUnavailable("professional_anchor_candidate_generation_failed")
        candidate, review = self._candidate_and_review(status_job_id, request)
        self._review_by_candidate_id[candidate.candidate_id] = review
        return candidate

    def _mcp_resume_planned_job_record(self, request: AnchorGenerationRequest) -> Any | None:
        """Return a prior frozen MCP handoff job instead of re-planning.

        A pending MCP materialization is a durable user-visible checkpoint:
        Brain already produced the canonical prompt and the handoff store keeps
        that prompt immutable. Once the user submits an image artifact, resume
        must consume the same planned job and continue into shared review. It
        must not ask Brain for a second prompt first, because a transient Brain
        timeout would strand an otherwise valid submitted image.
        """

        handoff_id = str(request.mcp_handoff_id or "").strip()
        operation_id = str(request.mcp_operation_id or "").strip()
        if not handoff_id or not operation_id:
            return None
        job_store = getattr(self.product_service, "job_store", None)
        list_recent = getattr(job_store, "list_recent", None)
        if not callable(list_recent):
            return None
        try:
            candidates = list_recent(100)
        except Exception:
            return None
        for record in candidates:
            if getattr(record, "planning_result", None) is None:
                continue
            generated_record = getattr(record, "generation_result", None) is not None
            metadata = dict(getattr(getattr(record, "request", None), "metadata", {}) or {})
            materialization = metadata.get("mcp_materialization")
            if isinstance(materialization, dict):
                if str(materialization.get("handoff_id") or "").strip() != handoff_id:
                    continue
                contract_payload = materialization
            elif generated_record:
                # A submitted MCP artifact is consumed during Provider-equivalent
                # materialization.  Older generated job records may no longer
                # carry the handoff id in request metadata, but they are still
                # the durable result for the same frozen operation.  Match them
                # only when the original handoff is now consumed and every
                # project/stage/reference field above has already matched.
                contract_payload = self._mcp_materialization_payload(handoff_id)
                if not isinstance(contract_payload, dict):
                    continue
                if str(contract_payload.get("status") or "").strip().lower() != "consumed":
                    continue
            else:
                continue
            if str(metadata.get("generation_channel") or "").strip().lower() != "mcp":
                continue
            if str(metadata.get("mcp_operation_id") or "").strip() != operation_id:
                continue
            if metadata.get("professional_anchor_pack_preparation") is not True:
                continue
            if str(metadata.get("professional_reference_stage") or "").strip() != request.view_role:
                continue
            if str(metadata.get("professional_anchor_capture_scope") or "anchor_pack") != request.capture_scope:
                continue
            if not generated_record and not self._mcp_anchor_materialization_matches_current_contract(
                request,
                contract_payload,
            ):
                continue
            return record
        return None

    def _mcp_anchor_handoff_matches_current_contract(
        self,
        request: AnchorGenerationRequest,
    ) -> bool:
        """Return whether a requested frozen MCP handoff can resume safely.

        MCP handoffs are intentionally immutable.  A prompt-contract upgrade
        must therefore not silently resume an older frozen prompt for a
        Character Card Face Identity slot: the old artifact may have the right
        operation id while missing the current left/right 45-degree card
        framing contract.  Ordinary Anchor Pack handoffs keep the historical
        behavior.
        """

        if request.capture_scope != "character_card_face_identity":
            return True
        handoff_id = str(request.mcp_handoff_id or "").strip()
        if not handoff_id:
            return True
        materialization = self._mcp_materialization_payload(handoff_id)
        if materialization is None:
            return True
        if str(materialization.get("status") or "").strip().lower() == "consumed":
            return True
        return self._mcp_anchor_materialization_matches_current_contract(
            request,
            materialization,
        )

    def _mcp_anchor_materialization_matches_current_contract(
        self,
        request: AnchorGenerationRequest,
        materialization: Any,
    ) -> bool:
        if request.capture_scope != "character_card_face_identity":
            return True
        if not isinstance(materialization, dict):
            return True
        prompt = str(materialization.get("canonical_prompt") or "").strip()
        if not prompt:
            return True
        return _character_card_face_identity_mcp_prompt_current(
            request.view_role,
            prompt,
        )

    def _mcp_materialization_payload(self, handoff_id: str) -> dict[str, Any] | None:
        store = getattr(self.product_service, "mcp_materialization_store", None)
        get = getattr(store, "get", None)
        if not callable(get):
            return None
        try:
            payload = get(handoff_id)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

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
            user_intents=self._character_card_expression_slot_intents(base_intent),
            generation_channel=generation_channel if generation_channel in {"provider", "mcp"} else "provider",
        )
        return self._attach_character_card_receipt(result, asset=asset, stage="expression_set")

    def prepare_expression_slot(
        self,
        *,
        asset: Any,
        card: CharacterCardState,
        expression: str,
        generation_channel: str = "provider",
    ) -> CharacterCardStageResult:
        front_output_id = str(card.face_slots["face.front"].output_id or "").strip()
        if not front_output_id:
            raise ValueError("character_card_expression_front_winner_missing")
        if expression != "smile":
            raise ValueError("character_card_expression_slot_not_explicitly_supported")
        preparation = CharacterCardPreparationService(generator=self, reviewer=self)
        base_intent = str(getattr(asset, "preparation_intent", "") or "").strip()
        if not base_intent:
            raise ValueError("character_card_expression_intent_missing")
        result = preparation.prepare_expression_slot(
            card,
            expression="smile",
            front_output_id=front_output_id,
            project_id=f"visual_asset_{asset.visual_asset_id}",
            people_asset_id=asset.visual_asset_id,
            user_intent=self._character_card_single_expression_intent(base_intent, "smile"),
            generation_channel=generation_channel if generation_channel in {"provider", "mcp"} else "provider",
        )
        return self._attach_character_card_receipt(result, asset=asset, stage="expression_set")

    @staticmethod
    def _character_card_expression_slot_intents(base_intent: str) -> dict[str, str]:
        """Attach the minimal slot-owned expression target to the asset intent.

        Identity, age, complexion and material finish still come from the
        approved Face Identity reference.  This helper only prevents all
        Expression Set slots from inheriting one neutral preparation sentence.
        """

        base = base_intent.strip()
        return {
            "laugh": (
                f"{base}\nExpression slot target: expression.laugh. "
                "Render the same person in a clearly readable joyful laugh keyframe rather than a polite open-mouth smile, "
                "with bright engaged gaze, visible lower-lid/periocular participation, upper-cheek lift, relaxed jaw opening, "
                "natural age-appropriate teeth visibility, slight spontaneous asymmetry, and only a small amount of natural "
                "head-shoulder energy while preserving the approved front-card framing."
            ),
            "anger": (
                f"{base}\nExpression slot target: expression.anger. "
                "Render the same person with a mild, age-appropriate annoyed or serious expression; "
                "avoid adult aggression, shouting, or theatrical anger."
            ),
            "sad": (
                f"{base}\nExpression slot target: expression.sad. "
                "Render the same person with a quiet, age-appropriate sad or pensive expression; "
                "avoid tears, drama, or a distressed scene."
            ),
        }

    @staticmethod
    def _character_card_single_expression_intent(base_intent: str, expression: str) -> str:
        base = base_intent.strip()
        if expression == "smile":
            return (
                f"{base}\nExpression slot target: expression.smile. "
                "Render the same person in an explicitly requested low-intensity natural smile, "
                "preserving the approved front-card framing, identity, lighting, white background, and crop. "
                "This is an optional extension expression and must not replace the default expression.laugh slot."
            )
        raise ValueError("character_card_expression_slot_not_explicitly_supported")

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
                    shared_review_receipts=self._character_card_stage_review_receipts(result),
                )
            }
        )

    @staticmethod
    def _character_card_stage_review_receipts(result: CharacterCardStageResult) -> list[dict[str, Any]]:
        receipts: list[dict[str, Any]] = []
        seen: set[str] = set()
        for attempt in result.attempts:
            review = getattr(attempt, "review", None)
            for receipt in getattr(review, "shared_review_receipts", []) or []:
                if not isinstance(receipt, dict):
                    continue
                identity = "|".join(
                    str(receipt.get(key) or "")
                    for key in ("owner", "contract_version", "expression", "status")
                )
                if identity in seen:
                    continue
                seen.add(identity)
                receipts.append(dict(receipt))
        return receipts

    def _generate_character_card_candidate(
        self,
        request: CharacterCardCandidateRequest,
    ) -> CharacterCardCandidateResult:
        stage_key = (request.people_asset_id, request.module, request.slot_key)
        operation_id = f"{request.people_asset_id}:{request.module}:{request.slot_key}:{request.candidate_index}"
        resume_record = (
            self._mcp_resume_character_card_stage_job_record(request, operation_id)
            if request.generation_channel == "mcp"
            else None
        )
        if resume_record is None:
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
                mcp_operation_id=operation_id,
            )
            status_job_id = status.job_id
            status_value = status.status
        else:
            status_job_id = resume_record.job_id
            if getattr(resume_record, "generation_result", None) is not None:
                try:
                    candidate, review = self._character_card_candidate_and_review(status_job_id, request)
                except RuntimeError as exc:
                    if str(exc) != "character_card_real_pixel_review_missing":
                        raise
                    status_value = ProductJobStatusValue.PLANNED
                else:
                    self._character_card_reviews[candidate.candidate_id] = review
                    self._record_character_card_retry_usage(stage_key, status_job_id)
                    return candidate
            else:
                status_value = ProductJobStatusValue.PLANNED
        if request.generation_channel == "mcp" and request.mcp_handoff_id:
            status_record = self.product_service.get_job_record(status_job_id)
            if status_record is not None:
                status_record.request.metadata = {
                    **dict(status_record.request.metadata),
                    "mcp_materialization": {
                        "handoff_id": request.mcp_handoff_id,
                        "status": "pending",
                        "generation_channel": "mcp",
                        "resume_required": True,
                    },
                }
                self.product_service.job_store.save(status_record)
        if status_value != ProductJobStatusValue.PLANNED:
            record = self.product_service.get_job_record(status_job_id)
            request_metadata = dict(record.request.metadata) if record is not None else {}
            remote_outcome = request_metadata.get("remote_creative_brain_outcome")
            if isinstance(remote_outcome, dict):
                reason_code = str(remote_outcome.get("reason_code") or "").strip()
                if reason_code in {"remote_brain_unavailable", "remote_brain_unauthorized"}:
                    raise AnchorCandidateUnavailable(reason_code)
            raise AnchorCandidateUnavailable("character_card_candidate_planning_blocked")
        generation = self.product_service.generate_job(
            status_job_id,
            {
                "quality_mode": "strict",
                "metadata": {
                    "max_visual_retry_attempts": 1,
                    **(
                        {"_v3_resume_finalizing_review": True}
                        if resume_record is not None and request.generation_channel == "mcp"
                        else {}
                    ),
                },
            },
        )
        self._record_character_card_retry_usage(stage_key, status_job_id)
        if generation.status not in {ProductJobStatusValue.GENERATED, ProductJobStatusValue.SELECTED}:
            mcp_materialization = self._mcp_materialization_from_generation_failure(generation, status_job_id)
            handoff_id = (
                str(mcp_materialization.get("handoff_id") or "").strip()
                if isinstance(mcp_materialization, dict)
                else ""
            )
            if request.generation_channel == "mcp" and handoff_id:
                materialization_payload = self._mcp_materialization_payload(handoff_id)
                if not _character_card_stage_mcp_prompt_current(
                    request.slot_key,
                    str(
                        (
                            materialization_payload
                            if isinstance(materialization_payload, dict)
                            else mcp_materialization
                        ).get("canonical_prompt")
                        or ""
                    ),
                ):
                    raise AnchorCandidateUnavailable(
                        "character_card_stage_prompt_contract_invalid"
                    )
                raise AnchorCandidateUnavailable(
                    "mcp_materialization_pending"
                    if str(mcp_materialization.get("status") or "").lower() == "pending"
                    else "mcp_materialization_failed",
                    mcp_handoff_id=handoff_id,
                )
            raise AnchorCandidateUnavailable("character_card_candidate_generation_failed")
        candidate, review = self._character_card_candidate_and_review(status_job_id, request)
        self._character_card_reviews[candidate.candidate_id] = review
        return candidate

    def _mcp_resume_character_card_stage_job_record(
        self,
        request: CharacterCardCandidateRequest,
        operation_id: str,
    ) -> Any | None:
        """Resume a frozen Character Card MCP candidate instead of re-planning.

        Face Identity already treats a pending MCP materialization as a durable
        checkpoint.  Expression Set and Body Silhouette must follow the same
        rule: once Brain has authored the canonical prompt and the MCP handoff
        exists, a later submit/resume consumes that same job and then returns to
        shared review.  It must not ask Brain for a new prompt first.
        """

        job_store = getattr(self.product_service, "job_store", None)
        list_recent = getattr(job_store, "list_recent", None)
        if not callable(list_recent):
            return None
        try:
            candidates = list_recent(200)
        except Exception:
            return None
        requested_refs = [str(item).strip() for item in request.reference_output_ids]
        requested_handoff = str(request.mcp_handoff_id or "").strip()
        for record in candidates:
            if getattr(record, "planning_result", None) is None:
                continue
            metadata = dict(getattr(getattr(record, "request", None), "metadata", {}) or {})
            if metadata.get("professional_character_card_preparation") is not True:
                continue
            if str(metadata.get("generation_channel") or "").strip().lower() != "mcp":
                continue
            if str(metadata.get("mcp_operation_id") or "").strip() != operation_id:
                continue
            if str(metadata.get("professional_character_card_stage") or "").strip() != request.module:
                continue
            if str(metadata.get("professional_character_card_slot") or "").strip() != request.slot_key:
                continue
            record_refs = [
                str(item).strip()
                for item in (metadata.get("professional_character_card_reference_output_ids") or [])
                if str(item).strip()
            ]
            if record_refs != requested_refs:
                continue
            materialization = metadata.get("mcp_materialization")
            if requested_handoff:
                if isinstance(materialization, dict):
                    if str(materialization.get("handoff_id") or "").strip() != requested_handoff:
                        continue
                elif getattr(record, "generation_result", None) is not None:
                    handoff_payload = self._mcp_materialization_payload(requested_handoff)
                    if not isinstance(handoff_payload, dict):
                        continue
                    if str(handoff_payload.get("status") or "").strip().lower() != "consumed":
                        continue
                else:
                    continue
            if getattr(record, "generation_result", None) is None and not isinstance(materialization, dict):
                continue
            return record
        return None

    def _mcp_materialization_from_generation_failure(self, generation: Any, job_id: str) -> dict[str, Any] | None:
        """Recover an opaque MCP handoff from public status or the durable job record."""

        metadata_candidates: list[dict[str, Any]] = []
        generation_metadata = getattr(generation, "metadata", {})
        if isinstance(generation_metadata, dict):
            metadata_candidates.append(generation_metadata)
        record = self.product_service.get_job_record(job_id)
        if record is not None:
            request_metadata = getattr(getattr(record, "request", None), "metadata", None)
            if isinstance(request_metadata, dict):
                metadata_candidates.append(request_metadata)
            result_metadata = getattr(getattr(record, "generation_result", None), "metadata", None)
            if isinstance(result_metadata, dict):
                metadata_candidates.append(result_metadata)
        for metadata in metadata_candidates:
            materialization = metadata.get("mcp_materialization")
            if isinstance(materialization, dict) and str(materialization.get("handoff_id") or "").strip():
                return materialization
        return None

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
        raw_status = _inspection_status(inspection)
        raw_issues = inspection.get("issue_codes") or inspection.get("detected_issues") or []
        issue_codes = [
            str(item.get("code") if isinstance(item, dict) else item).strip()
            for item in raw_issues
            if str(item.get("code") if isinstance(item, dict) else item).strip()
        ]
        score_card = _normalized_anchor_score_card(
            inspection.get("score_card"),
            raw_status=raw_status,
            issue_codes=issue_codes,
        )
        verified = (
            str(inspection.get("mode") or "").strip().lower() in {"vision_model", "hybrid"}
            and str(inspection.get("verification_state") or "").strip().lower() == "verified"
        )
        output_metadata = dict(selected.metadata or {})
        parity = self._character_card_prompt_reference_parity_verified(
            output_metadata,
            fallback_expected_reference_count=(
                2 if request.module == "expression_set" else 3
            ),
        )
        if not parity:
            raise AnchorCandidateUnavailable(
                "professional_character_card_prompt_reference_parity_unverified",
                output_id=selected.output_id,
                candidate_id=selected.candidate_id,
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
        if self._mcp_review_pending(request, inspection, issue_codes, verified):
            raise AnchorCandidateUnavailable(
                "mcp_review_pending",
                mcp_handoff_id=request.mcp_handoff_id,
                output_id=selected.output_id,
                candidate_id=selected.candidate_id,
            )
        evidence_codes = ["shared_real_pixel_review_verified" if verified else "shared_real_pixel_review_unverified"]
        expression_gate_issues: list[str] = []
        shared_review_receipts: list[dict[str, Any]] = []
        if request.module == "expression_set" and request.slot_key == "expression.laugh":
            expression_receipt = project_laugh_expression_review_receipt(
                score_card=score_card,
                issue_codes=issue_codes,
            )
            evidence_codes.extend(expression_receipt.evidence_codes)
            expression_gate_issues.extend(expression_receipt.issue_codes)
            issue_codes.extend(expression_receipt.issue_codes)
            shared_review_receipts.append(expression_receipt.to_public_dict())
        review = AnchorReviewDecision(
            status=(
                "pass"
                if verified
                and raw_status in {"pass", "warning"}
                and parity
                and not expression_gate_issues
                else "fail"
            ),
            identity_scores=IdentityScoreSummary(
                same_face_score=score_card.get("same_person_readability", score_card.get("identity", 0.0)),
                visual_quality_score=score_card.get("visual_quality", score_card.get("overall", 0.0)),
                distinctive_feature_score=score_card.get("distinctive_feature_readability", 0.0),
                human_realism_score=score_card.get("human_realism", 0.0),
                pose_compliance_score=score_card.get("pose_compliance", 0.0),
                ai_overperfection_penalty=score_card.get("ai_overperfection_penalty", 1.0),
                evidence_codes=list(dict.fromkeys(evidence_codes)),
            ),
            issue_codes=list(dict.fromkeys(issue_codes)),
            shared_review_receipts=shared_review_receipts,
        )
        return candidate, review

    @staticmethod
    def _character_card_prompt_reference_parity_verified(
        output_metadata: dict[str, Any],
        *,
        fallback_expected_reference_count: int,
    ) -> bool:
        """Verify the renderer-facing prompt/reference package is self-consistent.

        Character Card stages can pass one logical slot reference that expands
        into multiple renderer images, for example a face.front winner yielding
        feature-detail, geometry and full-frame card evidence.  Host acceptance
        must therefore consume the shared materialization receipt instead of
        guessing a fixed count by module.
        """

        if not str(output_metadata.get("provider_prompt_sha256") or "").strip():
            return False
        if not str(output_metadata.get("prompt_compilation_id") or "").strip():
            return False

        def _positive_int(value: Any) -> int | None:
            try:
                count = int(value)
            except (TypeError, ValueError):
                return None
            return count if count > 0 else None

        provider_count = _positive_int(output_metadata.get("provider_reference_image_count"))
        if provider_count is None:
            return False

        declared_counts: list[int] = []
        reference_asset_count = output_metadata.get("reference_asset_count")
        if reference_asset_count is not None:
            count = _positive_int(reference_asset_count)
            if count is None:
                return False
            declared_counts.append(count)

        provider_reference_assets = output_metadata.get("provider_reference_assets")
        if isinstance(provider_reference_assets, list):
            declared_counts.append(len(provider_reference_assets))

        reference_asset_ids = output_metadata.get("reference_asset_ids")
        if isinstance(reference_asset_ids, list):
            declared_counts.append(len(reference_asset_ids))

        reference_input_execution = output_metadata.get("reference_input_execution")
        if isinstance(reference_input_execution, dict) and reference_input_execution.get("reference_count") is not None:
            count = _positive_int(reference_input_execution.get("reference_count"))
            if count is None:
                return False
            declared_counts.append(count)

        if declared_counts:
            return all(count == provider_count for count in declared_counts)
        return provider_count == fallback_expected_reference_count

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
        raw_status = _inspection_status(inspection)
        raw_issues = inspection.get("issue_codes")
        if not isinstance(raw_issues, list):
            raw_issues = inspection.get("detected_issues")
        issue_codes = []
        for item in raw_issues if isinstance(raw_issues, list) else []:
            code = item.get("code") if isinstance(item, dict) else item
            if str(code or "").strip():
                issue_codes.append(str(code).strip())
        score_card = _normalized_anchor_score_card(
            inspection.get("score_card"),
            raw_status=raw_status,
            issue_codes=issue_codes,
        )
        required_dimensions = set(self._REQUIRED_SCORE_DIMENSIONS)
        missing_dimensions = sorted(required_dimensions - set(score_card))
        verified = (
            str(inspection.get("mode") or "").strip().lower() in {"vision_model", "hybrid"}
            and str(inspection.get("verification_state") or "").strip().lower() == "verified"
        )
        output_metadata = dict(selected.metadata or {})
        expected_reference_count = self._expected_provider_reference_count(request)
        prompt_hash = str(output_metadata.get("provider_prompt_sha256") or "").strip()
        provider_reference_assets_all = [
            dict(item)
            for item in output_metadata.get("provider_reference_assets", [])
            if isinstance(item, dict) and item.get("provider_reference_derivative")
        ]
        card_framing_reference_assets = [
            dict(item)
            for item in output_metadata.get("provider_reference_assets", [])
            if isinstance(item, dict)
            and (
                item.get("derivative_kind") == "character_card_full_frame_framing_reference"
                or item.get("identity_evidence_scope") == "card_framing"
            )
        ]
        provider_reference_assets = [
            item
            for item in provider_reference_assets_all
            if item.get("identity_evidence_scope") != "card_framing"
        ]
        scoped_face_localization_assets = [
            item
            for item in provider_reference_assets
            if item.get("identity_evidence_scope") in {"feature_detail", "head_geometry"}
        ]
        face_localization_reference_assets = (
            scoped_face_localization_assets
            if any(item.get("identity_evidence_scope") for item in provider_reference_assets)
            else provider_reference_assets
        )
        face_localization_verified = bool(
            face_localization_reference_assets
            and all(
                item.get("identity_face_localization_applied") is True
                and item.get("identity_face_localization_status") == "detected"
                and item.get("identity_nonidentity_pixel_suppression_profile")
                == "face_localized_nonidentity_suppression_v1"
                for item in face_localization_reference_assets
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
        if self._mcp_review_pending(request, inspection, issue_codes, verified):
            raise AnchorCandidateUnavailable(
                "mcp_review_pending",
                mcp_handoff_id=request.mcp_handoff_id,
                output_id=selected.output_id,
                candidate_id=selected.candidate_id,
            )
        cross_angle_identity_metric_contextualized = (
            self._character_card_cross_angle_identity_metric_contextualized(
                request,
                raw_status,
                issue_codes,
            )
        )
        raw_status_passes = raw_status in {"pass", "warning"} or cross_angle_identity_metric_contextualized
        if cross_angle_identity_metric_contextualized:
            issue_codes.append("professional_cross_angle_identity_metric_contextualized")
        if not raw_status:
            issue_codes.append("shared_visual_review_status_missing")
        elif not raw_status_passes:
            issue_codes.append("shared_visual_review_status_not_passed")
        passes = (
            verified
            and raw_status_passes
            and not missing_dimensions
            and face_localization_verified
        )
        if missing_dimensions:
            issue_codes.append("professional_anchor_review_score_incomplete")
        if not face_localization_verified:
            issue_codes.append("professional_anchor_face_localization_unverified")
        clarity_failures: list[str] = []
        identity_failures: list[str] = []
        if request.capture_scope == "character_card_face_identity":
            for dimension, floor in self._CHARACTER_CARD_FACE_CLARITY_FLOORS.items():
                if self._character_card_score_below_floor(score_card, dimension, floor):
                    clarity_failures.append(dimension)
            if clarity_failures:
                issue_codes.append("professional_face_card_commercial_clarity_below_bar")
            identity_floors = self._character_card_face_identity_floors(request.view_role)
            for dimension, floor in identity_floors.items():
                if self._character_card_score_below_floor(score_card, dimension, floor):
                    identity_failures.append(dimension)
            if identity_failures:
                issue_codes.append(
                    "professional_rear_head_nonface_continuity_below_bar"
                    if request.view_role == "rear_head"
                    else "professional_face_card_identity_evidence_below_bar"
                )
            if "pose_compliance" in identity_failures:
                issue_codes.append("professional_face_card_view_angle_below_bar")
            shared_slot_pose_verified = bool(
                verified
                and raw_status_passes
                and not self._character_card_score_below_floor(
                    score_card,
                    "pose_compliance",
                    identity_floors.get("pose_compliance", 0.0),
                )
            )
            if shared_slot_pose_verified:
                # The shared Vision contract owns Character Card slot pose:
                # for this module pose_compliance means front/25/45/profile/
                # rear head-view compliance.  The local detector is a fallback
                # diagnostic only; it must not override a verified shared pass
                # with a brittle numeric yaw estimate.
                view_direction_verified, view_direction_issues = True, []
            else:
                view_direction_verified, view_direction_issues = (
                    self._character_card_face_view_direction_parity(request, selected)
                )
            issue_codes.extend(view_direction_issues)
            framing_parity_verified, framing_parity_issues = self._character_card_face_framing_parity(
                request, selected
            )
            issue_codes.extend(framing_parity_issues)
            card_framing_verified, card_framing_issues = self._character_card_card_framing_parity(
                request, selected
            )
            issue_codes.extend(card_framing_issues)
        else:
            view_direction_verified = True
            framing_parity_verified = True
            card_framing_verified = True
        passes = passes and not clarity_failures
        passes = passes and not identity_failures
        passes = passes and view_direction_verified
        passes = passes and framing_parity_verified
        passes = passes and card_framing_verified
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
                    *(
                        ["face_view_direction_parity_verified"]
                        if view_direction_verified
                        else ["face_view_direction_parity_unverified"]
                    ),
                    *(
                        ["face_view_framing_parity_verified"]
                        if framing_parity_verified
                        else ["face_view_framing_parity_unverified"]
                    ),
                ] if parity_verified else ["shared_real_pixel_review_verified" if verified else "shared_real_pixel_review_unverified"],
            ),
            issue_codes=list(dict.fromkeys(issue_codes)),
        )
        return candidate, decision

    def _character_card_score_below_floor(self, score_card: dict[str, float], dimension: str, floor: float) -> bool:
        value = score_card.get(dimension, -1.0)
        return value + self._CHARACTER_CARD_SCORE_FLOOR_EPSILON < floor

    def _character_card_face_identity_floors(self, view_role: str) -> dict[str, float]:
        if view_role == "profile":
            return dict(self._CHARACTER_CARD_PROFILE_CONTINUITY_FLOORS)
        if view_role == "rear_head":
            return dict(self._CHARACTER_CARD_REAR_HEAD_CONTINUITY_FLOORS)
        return dict(self._CHARACTER_CARD_FACE_IDENTITY_FLOORS)

    @staticmethod
    def _character_card_cross_angle_identity_metric_contextualized(
        request: AnchorGenerationRequest,
        raw_status: str,
        issue_codes: list[str],
    ) -> bool:
        """Treat a profile-only objective metric warning as contextual.

        The shared Vision package may mark a clean, verified 90-degree profile
        as retryable solely because the local objective identity metric was
        calibrated for front/three-quarter geometry.  For Character Card
        profile only, this issue is allowed to be adjudicated by the slot
        floors, view-direction parity, framing parity and prompt/reference
        parity that follow.  Other issues, other slots and ordinary projects
        remain fail-closed.
        """

        if request.capture_scope != "character_card_face_identity":
            return False
        if request.view_role != "profile":
            return False
        if raw_status != "fail_retryable":
            return False
        normalized = {str(item).strip() for item in issue_codes if str(item).strip()}
        return normalized == {"identity_metric_below_commercial_target"}

    @staticmethod
    def _mcp_review_pending(
        request: Any,
        inspection: dict[str, Any],
        issue_codes: list[str],
        verified: bool,
    ) -> bool:
        """Treat MCP pixel + Vision timeout as a resumable review checkpoint.

        MCP materialization has already produced a real output.  If the shared
        Vision provider times out and returns manual_review/provider_timeout,
        the next resume should re-enter review for the same frozen job instead
        of consuming a new image candidate.
        """

        if str(getattr(request, "generation_channel", "") or "").strip().lower() != "mcp":
            return False
        if not str(getattr(request, "mcp_handoff_id", "") or "").strip():
            return False
        if verified:
            return False
        status = _inspection_status(inspection)
        verification_state = str(inspection.get("verification_state") or "").strip().lower()
        return (
            status == "manual_review"
            and verification_state != "verified"
            and "provider_timeout" in set(issue_codes)
        )

    def _character_card_face_view_direction_parity(
        self,
        request: AnchorGenerationRequest,
        selected,
    ) -> tuple[bool, list[str]]:
        if request.view_role not in {
            "left_front_25",
            "three_quarter",
            "right_front_25",
            "reverse_three_quarter",
        }:
            return True, []
        provider = self._character_card_identity_metric_provider()
        selected_profile = provider.profile_reference(Path(selected.file_path))
        if selected_profile.get("status") != "ready":
            return False, ["professional_face_card_view_direction_metric_unavailable"]
        if request.view_role == "left_front_25":
            issues = self._character_card_front_25_view_depth_issues(
                selected_profile,
                expected_side="right",
            )
            return not issues, issues
        if request.view_role == "right_front_25":
            issues = self._character_card_front_25_view_depth_issues(
                selected_profile,
                expected_side="left",
            )
            return not issues, issues
        # Do not require the coarse detector label to be exactly
        # ``*_three_quarter``.  A commercially valid 45° head card can be
        # labeled as a shallow profile by the local detector even though it is
        # visually a usable front-side modeling reference.  The hard gate
        # should prevent side swaps and near-front/rear/profile slot leaks, not
        # demand mathematically exact yaw.
        expected_side = "right" if request.view_role == "three_quarter" else "left"
        depth_issues = self._character_card_front_45_view_depth_issues(
            selected_profile,
            expected_side=expected_side,
        )
        if depth_issues:
            return False, depth_issues
        if request.view_role != "reverse_three_quarter":
            return True, []
        baseline_output_id = self._character_card_face_framing_baseline_output_id(request)
        if not baseline_output_id:
            return False, ["professional_face_card_opposite_45_reference_missing"]
        baseline = self.product_service.output_store.get_output(baseline_output_id)
        if baseline is None or not str(getattr(baseline, "file_path", "") or "").strip():
            return False, ["professional_face_card_opposite_45_reference_missing"]
        baseline_profile = provider.profile_reference(Path(baseline.file_path))
        if baseline_profile.get("status") != "ready":
            return False, ["professional_face_card_opposite_45_metric_unavailable"]
        baseline_depth_issues = self._character_card_front_25_view_depth_issues(
            baseline_profile,
            expected_side="left",
        )
        if baseline_depth_issues:
            return False, baseline_depth_issues
        return True, []

    def _character_card_front_25_view_depth_issues(
        self,
        profile: dict[str, Any],
        *,
        expected_side: str,
    ) -> list[str]:
        magnitude = _face_view_magnitude(profile)
        offset = _face_view_offset(profile)
        if magnitude is None or offset is None:
            return ["professional_face_card_view_angle_metric_unavailable"]
        if expected_side == "right" and offset <= 0:
            return ["professional_face_card_25_direction_failed"]
        if expected_side == "left" and offset >= 0:
            return ["professional_face_card_25_direction_failed"]
        if magnitude < self._CHARACTER_CARD_FRONT_25_MIN_VIEW_MAGNITUDE:
            return ["professional_face_card_25_angle_too_shallow"]
        if magnitude > self._CHARACTER_CARD_FRONT_25_MAX_VIEW_MAGNITUDE:
            return ["professional_face_card_25_angle_too_deep"]
        return []

    def _character_card_front_45_view_depth_issues(
        self,
        profile: dict[str, Any],
        *,
        expected_side: str | None = None,
        baseline: bool = False,
    ) -> list[str]:
        magnitude = _face_view_magnitude(profile)
        offset = _face_view_offset(profile)
        if magnitude is None:
            return ["professional_face_card_view_angle_metric_unavailable"]
        if expected_side == "right" and (offset is None or offset <= 0):
            return ["professional_face_card_view_direction_parity_failed"]
        if expected_side == "left" and (offset is None or offset >= 0):
            return ["professional_face_card_view_direction_parity_failed"]
        if magnitude < self._CHARACTER_CARD_FRONT_45_MIN_VIEW_MAGNITUDE:
            view_hint = str(profile.get("view_hint") or "").strip().lower()
            # The local yaw magnitude is only a soft slot-separation guard.
            # When the detector already classifies the image as a three-quarter
            # view and the requested left/right sign is correct, prefer the
            # shared Vision pose/quality verdict over a brittle numeric cutoff.
            if (
                "three_quarter" in view_hint
                and magnitude >= self._CHARACTER_CARD_FRONT_45_HARD_MIN_VIEW_MAGNITUDE
            ):
                return []
            return [
                "professional_face_card_baseline_45_angle_too_shallow"
                if baseline
                else "professional_face_card_view_angle_too_shallow"
            ]
        if magnitude > self._CHARACTER_CARD_FRONT_45_MAX_VIEW_MAGNITUDE:
            return [
                "professional_face_card_baseline_45_angle_too_deep"
                if baseline
                else "professional_face_card_view_angle_too_deep"
            ]
        return []

    def _character_card_face_framing_parity(
        self,
        request: AnchorGenerationRequest,
        selected,
    ) -> tuple[bool, list[str]]:
        if request.capture_scope == "character_card_face_identity":
            # Do not use detected face-box area as a hard acceptance gate for
            # non-front Character Card slots. A real 25/45/90-degree head turn
            # naturally changes the face detector rectangle even when the
            # modeling-card crop is perfectly consistent. Slot acceptance should
            # be governed by shared Vision identity/pose readability plus the
            # full-card foreground framing gate below (head top, subject scale,
            # shoulder/bottom cutoff), not by projecting one angle's face box
            # onto another angle.
            return True, []
        if request.view_role not in {
            "left_front_25",
            "three_quarter",
            "right_front_25",
            "reverse_three_quarter",
        }:
            return True, []
        baseline_output_id = self._character_card_face_framing_baseline_output_id(request)
        if not baseline_output_id:
            return False, ["professional_face_card_framing_reference_missing"]
        baseline = self.product_service.output_store.get_output(baseline_output_id)
        if baseline is None or not str(getattr(baseline, "file_path", "") or "").strip():
            return False, ["professional_face_card_framing_reference_missing"]
        provider = self._character_card_identity_metric_provider()
        selected_profile = provider.profile_reference(Path(selected.file_path))
        baseline_profile = provider.profile_reference(Path(baseline.file_path))
        issues = self._character_card_face_area_parity_issues(
            selected_profile,
            baseline_profile,
            view_role=request.view_role,
        )
        return not issues, issues

    def _character_card_face_area_parity_issues(
        self,
        selected_profile: dict[str, Any],
        baseline_profile: dict[str, Any],
        *,
        view_role: str | None = None,
    ) -> list[str]:
        selected_ratio = _face_box_area_ratio(selected_profile.get("face_box"))
        baseline_ratio = _face_box_area_ratio(baseline_profile.get("face_box"))
        if (
            selected_profile.get("status") != "ready"
            or baseline_profile.get("status") != "ready"
            or selected_ratio is None
            or baseline_ratio is None
            or baseline_ratio <= 0
        ):
            return ["professional_face_card_framing_metric_unavailable"]
        relative_delta = abs(selected_ratio - baseline_ratio) / baseline_ratio
        max_relative_delta = self._CHARACTER_CARD_FACE_FRAMING_PARITY_MAX_RELATIVE_DELTA
        if view_role in {"left_front_25", "right_front_25"}:
            max_relative_delta = self._CHARACTER_CARD_FRONT_25_FACE_FRAMING_PARITY_MAX_RELATIVE_DELTA
        if view_role in {"three_quarter", "reverse_three_quarter"}:
            max_relative_delta = self._CHARACTER_CARD_FRONT_45_FACE_FRAMING_PARITY_MAX_RELATIVE_DELTA
        if relative_delta > max_relative_delta:
            return ["professional_face_card_framing_parity_failed"]
        return []

    def _character_card_card_framing_parity(
        self,
        request: AnchorGenerationRequest,
        selected,
    ) -> tuple[bool, list[str]]:
        if request.view_role not in {
            "left_front_25",
            "three_quarter",
            "profile",
            "right_front_25",
            "reverse_three_quarter",
            "rear_head",
        }:
            return True, []
        baseline_output_id = self._character_card_card_framing_baseline_output_id(request)
        if not baseline_output_id:
            return False, ["professional_face_card_card_framing_reference_missing"]
        baseline = self.product_service.output_store.get_output(baseline_output_id)
        if baseline is None or not str(getattr(baseline, "file_path", "") or "").strip():
            return False, ["professional_face_card_card_framing_reference_missing"]
        selected_box = _foreground_card_box(Path(selected.file_path))
        baseline_box = _foreground_card_box(Path(baseline.file_path))
        if not selected_box or not baseline_box:
            return False, ["professional_face_card_foreground_framing_metric_unavailable"]
        issue_codes = self._character_card_foreground_framing_issues(
            request.view_role,
            selected_box,
            baseline_box,
        )
        return not issue_codes, issue_codes

    def _character_card_foreground_framing_issues(
        self,
        view_role: str,
        selected_box: dict[str, float],
        baseline_box: dict[str, float],
    ) -> list[str]:
        issue_codes: list[str] = []
        baseline_height = float(baseline_box["height_ratio"])
        selected_height = float(selected_box["height_ratio"])
        if baseline_height <= 0 or selected_height <= 0:
            return ["professional_face_card_foreground_framing_metric_unavailable"]
        height_delta = abs(selected_height - baseline_height) / baseline_height
        baseline_width = float(baseline_box.get("width_ratio") or 0.0)
        selected_width = float(selected_box.get("width_ratio") or 0.0)
        if baseline_width <= 0 or selected_width <= 0:
            return ["professional_face_card_foreground_framing_metric_unavailable"]
        width_delta = abs(selected_width - baseline_width) / baseline_width
        top_delta = abs(float(selected_box["top_ratio"]) - float(baseline_box["top_ratio"]))
        selected_bottom = float(selected_box["top_ratio"]) + selected_height
        baseline_bottom = float(baseline_box["top_ratio"]) + baseline_height
        bottom_delta = abs(selected_bottom - baseline_bottom)
        if height_delta > self._CHARACTER_CARD_FOREGROUND_HEIGHT_MAX_RELATIVE_DELTA:
            issue_codes.append("professional_face_card_subject_scale_parity_failed")
        if (
            view_role in {"left_front_25", "three_quarter", "right_front_25", "reverse_three_quarter"}
            and width_delta > self._CHARACTER_CARD_FOREGROUND_WIDTH_MAX_RELATIVE_DELTA
        ):
            issue_codes.append("professional_face_card_subject_width_parity_failed")
        if top_delta > self._CHARACTER_CARD_HEAD_TOP_MARGIN_MAX_ABSOLUTE_DELTA:
            issue_codes.append("professional_face_card_head_top_margin_parity_failed")
        if bottom_delta > self._CHARACTER_CARD_SHOULDER_PADDING_MAX_ABSOLUTE_DELTA:
            issue_codes.append("professional_face_card_shoulder_padding_parity_failed")
        return issue_codes

    def _character_card_identity_metric_provider(self):
        if self._identity_metric_provider is None:
            self._identity_metric_provider = create_default_identity_metric_provider()
        return self._identity_metric_provider

    @staticmethod
    def _character_card_face_framing_baseline_output_id(request: AnchorGenerationRequest) -> str | None:
        output_ids = []
        for value in request.reference_evidence_ids:
            source_id = str(value or "").split("::", 1)[0].strip()
            if source_id.startswith("v3_output_") and source_id not in output_ids:
                output_ids.append(source_id)
        if request.view_role in {"left_front_25", "right_front_25"}:
            return output_ids[0] if output_ids else None
        if request.view_role == "three_quarter":
            return output_ids[-1] if output_ids else None
        if request.view_role == "reverse_three_quarter":
            return output_ids[-1] if output_ids else None
        return None

    @staticmethod
    def _character_card_card_framing_baseline_output_id(request: AnchorGenerationRequest) -> str | None:
        output_ids = []
        for value in request.reference_evidence_ids:
            source_id = str(value or "").split("::", 1)[0].strip()
            if source_id.startswith("v3_output_") and source_id not in output_ids:
                output_ids.append(source_id)
        if request.view_role == "reverse_three_quarter":
            return output_ids[0] if output_ids else None
        if request.view_role in {"left_front_25", "three_quarter", "profile", "right_front_25", "rear_head"}:
            return output_ids[0] if output_ids else None
        return None

    @staticmethod
    def _review_rank(inspection: dict[str, Any]) -> tuple[int, float, float]:
        verified = str(inspection.get("verification_state") or "").strip().lower() == "verified"
        passed = _inspection_status(inspection) in {"pass", "warning"}
        scores = _normalized_anchor_score_card(
            inspection.get("score_card"),
            raw_status=_inspection_status(inspection),
            issue_codes=[],
        )
        return (
            int(verified and passed),
            float(scores.get("same_person_readability") or 0.0),
            float(scores.get("overall") or 0.0),
        )


def _inspection_status(inspection: dict[str, Any]) -> str:
    """Return the shared Vision status across persisted receipt projections."""

    for key in ("status", "review_status", "final_review_status"):
        value = str(inspection.get(key) or "").strip().lower()
        if not value:
            continue
        return {
            "passed": "pass",
            "ready": "pass",
            "needs_retry": "fail_retryable",
            "retryable": "fail_retryable",
            "failed": "fail_final",
        }.get(value, value)
    verdict = inspection.get("feedback_verdict")
    if isinstance(verdict, dict):
        value = str(verdict.get("status") or "").strip().lower()
        if value in {"pass", "passes", "resolved", "compliant"}:
            return "pass"
    return ""


def _normalized_anchor_score_card(
    raw_score_card: Any,
    *,
    raw_status: str,
    issue_codes: list[str],
) -> dict[str, float]:
    """Normalize equivalent shared Vision score names without changing gates.

    The shared Vision receipt is the source of truth.  This function only maps
    public or historical aliases onto the internal Character Card dimensions so
    that a verified pass is not overwritten by a stale projection name.  It does
    not invent a passing result for a failing receipt.
    """

    if not isinstance(raw_score_card, dict):
        return {}
    score_card = {
        str(key).strip(): float(value)
        for key, value in raw_score_card.items()
        if str(key).strip() and isinstance(value, (int, float)) and not isinstance(value, bool)
    }

    def copy_first(target: str, aliases: tuple[str, ...]) -> None:
        if target in score_card:
            return
        for alias in aliases:
            if alias in score_card:
                score_card[target] = score_card[alias]
                return

    copy_first(
        "same_person_readability",
        ("same_person", "same-person", "same_face", "identity_consistency", "identity"),
    )
    copy_first(
        "distinctive_feature_readability",
        ("distinctive_features", "distinctive_feature_score", "identity_fidelity"),
    )
    copy_first("visual_quality", ("quality", "commercial_finish", "overall"))
    copy_first("technical_finish", ("commercial_finish", "visual_quality", "overall"))
    copy_first("human_realism", ("realism", "human_naturalness", "camera_observed_human_materiality"))
    copy_first("pose_compliance", ("view_pose_compliance", "face_view_pose_compliance", "pose"))
    copy_first("developmental_age_coherence", ("age_identity_direction", "age_coherence"))
    copy_first("prompt_owned_channel_obedience", ("prompt_obedience", "feedback_compliance"))
    copy_first("neutral_capture_compliance", ("neutral_capture", "capture_compliance"))

    normalized_issues = {str(item or "").strip() for item in issue_codes if str(item or "").strip()}
    if (
        "ai_overperfection_penalty" not in score_card
        and raw_status in {"pass", "warning"}
        and "professional_ai_overperfection" not in normalized_issues
        and "human_skin_or_retouch" not in normalized_issues
        and "generic_stock_photo_finish" not in normalized_issues
    ):
        score_card["ai_overperfection_penalty"] = 0.0
    return score_card


def _face_box_area_ratio(face_box: Any) -> float | None:
    if not isinstance(face_box, list) or len(face_box) != 4:
        return None
    try:
        width = float(face_box[2])
        height = float(face_box[3])
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return width * height


def _face_view_magnitude(profile: dict[str, Any]) -> float | None:
    if not isinstance(profile, dict):
        return None
    raw = profile.get("face_view_magnitude")
    if raw is None:
        raw = profile.get("face_view_offset_ratio")
    try:
        value = abs(float(raw))
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


def _face_view_offset(profile: dict[str, Any]) -> float | None:
    if not isinstance(profile, dict):
        return None
    raw = profile.get("face_view_offset_ratio")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _character_card_face_identity_mcp_prompt_current(view_role: str, prompt: str) -> bool:
    """Keep MCP resume aligned with the requested Face Identity slot.

    The operation id, references and signed Brain receipts are the authoritative
    contract.  This helper only catches clearly stale/wrong-slot handoffs; it is
    deliberately not a second renderer recipe.
    """

    role = str(view_role or "").strip()
    normalized = " ".join(str(prompt or "").lower().split())
    if not normalized:
        return False
    if role not in {
        "left_front_25",
        "three_quarter",
        "profile",
        "right_front_25",
        "reverse_three_quarter",
        "rear_head",
    }:
        return True
    role_terms = {
        "left_front_25": (
            "left-front 25",
            "left front 25",
            "left-front transition",
            "left front transition",
            "shallow left-front",
            "25-degree transition",
            "25 degree transition",
        ),
        "three_quarter": (
            "left-front",
            "left front",
            "front-left",
            "front left",
            "left three-quarter",
            "left-side 45",
            "left 45",
        ),
        "profile": ("profile", "side profile", "side view", "90-degree", "90 degree"),
        "right_front_25": (
            "right-front 25",
            "right front 25",
            "right-front transition",
            "right front transition",
            "shallow right-front",
            "opposite 25",
            "25-degree transition",
            "25 degree transition",
        ),
        "reverse_three_quarter": (
            "right-front",
            "right front",
            "front-right",
            "front right",
            "right three-quarter",
            "opposite front",
            "opposite-side 45",
            "right-side 45",
            "right 45",
        ),
        "rear_head": ("rear head", "back of head", "rear view", "back view"),
    }
    if not any(term in normalized for term in role_terms.get(role, ())):
        return False
    if role == "reverse_three_quarter" and any(
        term in normalized
        for term in (
            "rear three-quarter",
            "rear 3/4",
            "back three-quarter",
            "back 3/4",
            "back of head dominant",
            "rear of head dominant",
            "mirror the approved left-front",
            "mirrors the approved left-front",
            "mirror the approved left front",
            "mirrored opposite side",
            "mirror opposite side",
        )
    ):
        return False
    if role == "rear_head" and any(
        term in normalized
        for term in (
            "front-facing",
            "front facing",
            "looking at the camera",
            "direct eye contact",
        )
    ):
        return False
    return True


def _character_card_stage_mcp_prompt_current(slot_key: str, prompt: str) -> bool:
    """Keep stage handoffs aligned with the requested Character Card slot."""

    normalized = " ".join(str(prompt or "").lower().split())
    slot = str(slot_key or "").strip()
    if not normalized:
        return False
    expression_terms = {
        "expression.laugh": ("laugh", "laughing", "amused", "delighted", "joyful"),
        "expression.smile": ("smile", "smiling", "happy", "joyful", "cheerful"),
        "expression.anger": ("angry", "anger", "annoyed", "serious", "stern", "upset", "frown"),
        "expression.sad": ("sad", "sadness", "pensive", "downcast", "melancholy", "somber", "unhappy"),
    }.get(slot)
    if expression_terms is not None:
        return any(term in normalized for term in expression_terms)
    return True


def _foreground_card_box(path: Path) -> dict[str, float] | None:
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail((256, 384), Image.Resampling.LANCZOS)
            width, height = image.size
            if width <= 0 or height <= 0:
                return None
            corner = max(8, min(width, height) // 12)
            patches = [
                image.crop((0, 0, corner, corner)),
                image.crop((width - corner, 0, width, corner)),
                image.crop((0, height - corner, corner, height)),
                image.crop((width - corner, height - corner, width, height)),
            ]
            pixels = [
                pixel
                for patch in patches
                for pixel in (
                    patch.get_flattened_data()
                    if hasattr(patch, "get_flattened_data")
                    else patch.getdata()
                )
            ]
            background = tuple(float(median(channel)) for channel in zip(*pixels))
            xs: list[int] = []
            ys: list[int] = []
            for y in range(height):
                for x in range(width):
                    red, green, blue = image.getpixel((x, y))
                    diff = abs(red - background[0]) + abs(green - background[1]) + abs(blue - background[2])
                    if diff > 38 and (red + green + blue) / 3.0 < 248:
                        xs.append(x)
                        ys.append(y)
            if not xs or not ys:
                return None
            x1, x2 = min(xs), max(xs) + 1
            y1, y2 = min(ys), max(ys) + 1
            return {
                "left_ratio": x1 / width,
                "top_ratio": y1 / height,
                "width_ratio": (x2 - x1) / width,
                "height_ratio": (y2 - y1) / height,
                "area_ratio": ((x2 - x1) * (y2 - y1)) / (width * height),
            }
    except Exception:
        return None


__all__ = ["ProductApiAnchorPackPreparationHost"]
