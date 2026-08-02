"""Red test for refresh-level Body source-analysis profile freezing.

Correction model
----------------
The Character Card formal path owns one fresh refresh containing three Body
views and three candidates per view.  Source analysis is evidence preparation,
not candidate generation, so the same five-source binding must produce one
typed frozen profile/receipt before candidate requests fan out.  The current
runtime calls ``_body_proportion_profile_for_brain`` from each Brain request;
this test intentionally exposes that per-candidate analysis until a refresh
owner freezes the typed result.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import ProductApiAnchorPackPreparationHost
from alchemy_creative_agent_3_0.app.visual_assets.body_proportion_evidence_profile import (
    BodyRefreshAnalysisContext,
    BodyProportionEvidenceProfile,
    BodySourceAnalysisAssetEnvelope,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    BodySourceAdmission,
    BodyRefreshAttemptIdentity,
    CharacterCardCandidateRequest,
    CharacterCardCandidateResult,
    CharacterCardPreparationService,
)
from test_v3_doc245_body_formal_slot_receipt_seam import _BodyReviewer, _active_body_card


_BODY_SLOTS = ("body.front_full", "body.side_full", "body.rear_full")
_BODY_BANDS = {
    "head_body_scale": "balanced_child_scale",
    "neck_shoulder": "balanced_child_transition",
    "torso_limb": "balanced_child_torso_limb",
    "arm_leg": "balanced_child_arm_leg",
    "developmental_stage": "early_childhood_coherent",
    "stance_ground": "grounded_full_contact",
    "cross_view_support": "front_back_supported",
}


def _internal_body_sources() -> list[BodySourceAnalysisAssetEnvelope]:
    return [
        BodySourceAnalysisAssetEnvelope(
            asset_id=f"body-source-{index}",
            role="body_proportion_reference",
            reference_truth_layer="body_proportion_truth",
            file_path=f"C:/private/body-source-{index}.png",
            mime_type="image/png",
            source_sha256=(f"{index + 1:02x}" * 32),
            source_provenance="server_admitted_body_reference",
            consent_reference="server_consent_reference",
            rights_reference="server_rights_reference",
        )
        for index in range(5)
    ]


class _CountingBodyAnalyzer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def analyze(self, assets: tuple[dict[str, Any], ...]) -> dict[str, Any]:
        binding = tuple(str(asset["metadata"]["source_sha256"]) for asset in assets)
        self.calls.append(binding)
        return {
            "contract_version": "body_proportion_evidence_profile_v1",
            "source_mode": "reference_assisted",
            "source_truth_layer": "body_proportion_truth",
            "allowed_bands": dict(_BODY_BANDS),
            "source_count": 5,
            "analysis_receipt": {
                "owner": "server_owned_body_proportion_analysis",
                "status": "complete",
                "analysis_provider": "configured_body_source_analysis_provider",
            },
        }


def _candidate_request(candidate: CharacterCardCandidateRequest) -> SimpleNamespace:
    return SimpleNamespace(
        metadata={
            "professional_mode": True,
            "professional_character_card_stage": "body_silhouette",
            "professional_character_card_slot": candidate.slot_key,
            "professional_character_card_body_refresh_source_mode": "reference_assisted",
            "professional_character_card_body_model_context": (
                "similar_person_body_reference_assisted_v1"
            ),
            "professional_character_card_candidate_index": candidate.candidate_index,
            "professional_body_refresh_analysis_context": (
                candidate.body_refresh_analysis_context.safe_metadata()
                if candidate.body_refresh_analysis_context is not None
                else None
            ),
        },
        body_source_analysis_assets=_internal_body_sources(),
        body_refresh_analysis_context=candidate.body_refresh_analysis_context,
    )


class _RefreshFanoutGenerator:
    def __init__(self, runtime: ScenarioRuntime) -> None:
        self.runtime = runtime
        self.requests: list[CharacterCardCandidateRequest] = []
        self.request_profiles: list[Any] = []

    def generate(self, request: CharacterCardCandidateRequest) -> CharacterCardCandidateResult:
        self.requests.append(request)
        # This is the production request boundary: the host has to receive the
        # already-frozen typed profile; it must not analyze inside each call.
        profile = self.runtime._body_proportion_profile_for_brain(  # noqa: SLF001
            _candidate_request(request),
            stage="plan",
        )
        self.request_profiles.append(profile)
        return CharacterCardCandidateResult(
            candidate_id=f"candidate_{request.slot_key}_{request.candidate_index}",
            output_id=f"output_{request.slot_key}_{request.candidate_index}",
            module=request.module,
            slot_key=request.slot_key,
            candidate_index=request.candidate_index,
            source_candidate_ids=[f"source_{request.slot_key}_{request.candidate_index}"],
            source_output_ids=list(request.reference_output_ids),
            canonical_prompt_hash=f"prompt_{request.slot_key}_{request.candidate_index}",
            prompt_compilation_id=f"compilation_{request.slot_key}_{request.candidate_index}",
            prompt_reference_parity_verified=True,
        )


def test_fresh_body_refresh_freezes_one_profile_before_three_view_candidate_fanout() -> None:
    analyzer = _CountingBodyAnalyzer()
    runtime = ScenarioRuntime(body_proportion_source_analyzer=analyzer)
    generator = _RefreshFanoutGenerator(runtime)
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())
    attempt_identity = BodyRefreshAttemptIdentity.create(append_only_revision=2)
    profile = runtime.body_proportion_source_analysis_adapter.analyze(
        [asset.to_analyzer_record() for asset in _internal_body_sources()],
        source_mode="reference_assisted",
        analyzer=analyzer,
    )
    context = BodyRefreshAnalysisContext.from_analysis(
        attempt_id=attempt_identity.attempt_id,
        append_only_revision=attempt_identity.append_only_revision,
        admitted_body_assets=_internal_body_sources(),
        profile=profile,
    )
    result = service.refresh_body_silhouette(
        _active_body_card(),
        face_reference_output_ids=["face.front", "face.profile", "face.rear"],
        source_class="observed",
        body_evidence_ids=[f"body-source-{index}" for index in range(5)],
        consent_provenance_id="server-consent-reference",
        user_intent="reference-assisted body silhouette refresh",
        generation_channel="mcp",
        body_refresh_analysis_context=context,
        body_refresh_attempt_identity=attempt_identity,
    )

    assert result.status == "review"
    assert len(generator.requests) == 9
    assert [request.slot_key for request in generator.requests] == [
        slot_key for slot_key in _BODY_SLOTS for _ in (1, 2, 3)
    ]
    assert all(isinstance(profile, BodyProportionEvidenceProfile) for profile in generator.request_profiles)
    assert len({profile.model_dump_json() for profile in generator.request_profiles}) == 1
    assert len(analyzer.calls) == 1
    assert len({request.body_refresh_attempt_identity.attempt_id for request in generator.requests}) == 1
    assert all(
        request.body_refresh_source_mode == "reference_assisted"
        for request in generator.requests
    )
    assert all(binding == analyzer.calls[0] for binding in analyzer.calls)


def _profile_context() -> tuple[BodyRefreshAttemptIdentity, BodyRefreshAnalysisContext]:
    runtime = ScenarioRuntime(body_proportion_source_analyzer=_CountingBodyAnalyzer())
    profile = BodyProportionEvidenceProfile(
        contract_version="body_proportion_evidence_profile_v1",
        source_mode="reference_assisted",
        source_truth_layer="body_proportion_truth",
        allowed_bands=_BODY_BANDS,
        source_count=5,
        analysis_receipt={
            "owner": "server_owned_body_proportion_analysis",
            "status": "complete",
            "analysis_provider": "configured_body_source_analysis_provider",
        },
    )
    attempt = BodyRefreshAttemptIdentity.create(append_only_revision=3)
    return attempt, BodyRefreshAnalysisContext.from_analysis(
        attempt_id=attempt.attempt_id,
        append_only_revision=attempt.append_only_revision,
        admitted_body_assets=_internal_body_sources(),
        profile=profile,
    )


def _candidate_contract_kwargs(
    *,
    attempt: BodyRefreshAttemptIdentity,
    context: Any = None,
    source_class: str = "observed",
    source_mode: str = "reference_assisted",
) -> dict[str, Any]:
    return {
        "project_id": "project",
        "people_asset_id": "people_asset",
        "card_version_id": "card_version",
        "module": "body_silhouette",
        "slot_key": "body.front_full",
        "candidate_index": 1,
        "reference_output_ids": ["face.front", "face.profile", "face.rear"],
        "user_intent": "reference-assisted Body refresh",
        "source_class": source_class,
        "consent_provenance_id": "server-consent-reference",
        "body_source_admission": BodySourceAdmission(
            source_class="observed",
            body_evidence_ids=[f"body-source-{index}" for index in range(5)],
            body_reference_role="body_proportion_reference",
            body_reference_truth_layer="body_proportion_truth",
            face_reference_output_ids=["face.front", "face.profile", "face.rear"],
        )
        if source_class == "observed"
        else None,
        "body_refresh_source_mode": source_mode,
        "body_model_context": (
            "similar_person_body_reference_assisted_v1"
            if source_mode == "reference_assisted"
            else "system_inferred_body_model_scene_neutral_v1"
        ),
        "body_refresh_contract_required": True,
        "generation_channel": "mcp",
        "body_refresh_attempt_identity": attempt,
        "body_refresh_analysis_context": context,
    }


def test_reference_assisted_body_candidate_requires_frozen_context() -> None:
    attempt, _context = _profile_context()
    with pytest.raises(ValueError, match="body_proportion_analysis_context_missing"):
        CharacterCardCandidateRequest(**_candidate_contract_kwargs(attempt=attempt))


def test_public_dict_context_and_wrong_attempt_are_rejected() -> None:
    attempt, context = _profile_context()
    with pytest.raises(ValueError, match="body_refresh_analysis_context_untrusted"):
        CharacterCardCandidateRequest(
            **_candidate_contract_kwargs(
                attempt=attempt,
                context=context.model_dump(mode="python"),
            )
        )
    other_attempt = BodyRefreshAttemptIdentity.create(append_only_revision=3)
    with pytest.raises(ValueError, match="body_proportion_analysis_context_attempt_mismatch"):
        CharacterCardCandidateRequest(
            **_candidate_contract_kwargs(attempt=other_attempt, context=context)
        )


def test_inference_first_rejects_observed_analysis_context() -> None:
    attempt, context = _profile_context()
    with pytest.raises(ValueError, match="body_proportion_analysis_context_source_mode_invalid"):
        CharacterCardCandidateRequest(
            **_candidate_contract_kwargs(
                attempt=attempt,
                context=context,
                source_class="brain_inferred",
                source_mode="inference_first",
            )
        )


def test_runtime_rejects_profile_or_source_binding_digest_drift() -> None:
    attempt, context = _profile_context()
    request_metadata = {
        "professional_mode": True,
        "professional_character_card_preparation": True,
        "professional_character_card_stage": "body_silhouette",
        "professional_character_card_slot": "body.front_full",
        "professional_character_card_body_refresh_source_mode": "reference_assisted",
        "professional_body_refresh_analysis_context": context.safe_metadata(),
    }
    drifted_profile = context.model_copy(update={"profile_digest": "0" * 64})
    runtime = ScenarioRuntime()
    with pytest.raises(Exception, match="body_proportion_analysis_context_mismatch"):
        runtime._body_proportion_profile_for_brain(  # noqa: SLF001
            SimpleNamespace(
                metadata=request_metadata,
                body_refresh_analysis_context=drifted_profile,
            ),
            stage="plan",
        )
    drifted_binding = context.model_copy(update={"source_binding_digest": "1" * 64})
    with pytest.raises(Exception, match="body_proportion_analysis_context_mismatch"):
        runtime._body_proportion_profile_for_brain(  # noqa: SLF001
            SimpleNamespace(
                metadata=request_metadata,
                body_refresh_analysis_context=drifted_binding,
            ),
            stage="plan",
        )


def test_safe_refresh_context_has_no_raw_source_or_provider_fields() -> None:
    _attempt, context = _profile_context()
    safe = context.safe_metadata()
    assert set(safe) == {
        "contract_version",
        "schema_version",
        "source_mode",
        "attempt_id",
        "append_only_revision",
        "source_binding_digest",
        "profile_digest",
    }
    assert all(
        not any(marker in str(value).lower() for marker in ("path", "url", "base64", "provider_id"))
        for value in safe.values()
    )


def test_product_api_anchor_host_fails_closed_before_fanout_without_context() -> None:
    host = ProductApiAnchorPackPreparationHost.__new__(ProductApiAnchorPackPreparationHost)
    with pytest.raises(ValueError, match="body_proportion_analysis_context_missing"):
        host.refresh_body_silhouette(
            asset=SimpleNamespace(
                visual_asset_id="visual_asset_body",
                preparation_intent="reference-assisted Body refresh",
                root_source_provenance=SimpleNamespace(consent_reference="consent"),
            ),
            card=_active_body_card(),
            request=SimpleNamespace(
                source_class="observed",
                body_reference_asset_id="body-source-0",
            ),
            generation_channel="mcp",
        )
