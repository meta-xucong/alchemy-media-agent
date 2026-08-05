"""First red test for durable Body-refresh continuation ownership.

Correction model
----------------
The fresh ``VisualAssetLibraryLifecycleService`` entry owns one analysis
context and one attempt.  If candidate one is reviewed and the process stops
before candidate two, the next official resume must load the private,
server-owned attempt state and start at candidate two.  It must not call the
source analyzer again or invoke the fresh path, which would regenerate
candidate one.

This test deliberately uses the real Library -> Host -> Character Card
candidate boundary and only replaces the candidate generator with a
deterministic interruption seam.  No provider or ImageGen call is made.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_body_analysis_profile_lifecycle_freeze import (
    BodySilhouettePublicRequest,
    VisualAssetLibraryLifecycleService,
    _RefreshFanoutGenerator,
    _internal_body_sources,
    _profile_context,
    _library_refresh_fixture,
)

from alchemy_creative_agent_3_0.app.visual_assets.body_refresh_attempt_state import (
    BodyRefreshAttemptStateError,
    BodyRefreshAttemptStateStore,
)
from alchemy_creative_agent_3_0.app.visual_assets.body_cross_view_review import (
    BODY_CROSS_VIEW_DIMENSION_EVIDENCE_CODES,
    BODY_CROSS_VIEW_DIMENSIONS,
    BODY_CROSS_VIEW_PIXEL_EVIDENCE_CODE,
    build_body_cross_view_review_receipt,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    BODY_SLOT_KEYS,
    BodyRefreshAttemptIdentity,
    BodySourceAdmission,
    CharacterCardPreparationService,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    CharacterCardCandidateResult,
    CharacterCardCandidateRequest,
    CharacterCardCandidateLifecycleBoundaryError,
    CharacterCardRuntimeUnavailable,
    CharacterCardStageResult,
)
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import ProductApiAnchorPackPreparationHost
from alchemy_creative_agent_3_0.app.product_api.service import (
    CreateCreativeJobRequest,
    PersistentProductJobStore,
    ProductJobRecord,
    ProductJobStatusValue,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import AnchorCandidateUnavailable
from alchemy_creative_agent_3_0.app.visual_assets.formal_slot_acceptance import (
    FormalSlotReceipt,
    mark_formal_slot_receipt_reload_public_projection_verified,
)
from test_v3_doc245_body_formal_slot_receipt_seam import (
    _BodyGenerator,
    _BodyReviewer,
    _active_body_card,
    _body_attempt,
    _review,
)


class _DirectedOperationJobStore:
    def __init__(self, records: list[object]) -> None:
        self.records = list(records)
        self.direct_calls: list[str] = []
        self.full_scan_calls: list[str] = []

    def get_mcp_operation_records(self, operation_id: str) -> list[object]:
        self.direct_calls.append(operation_id)
        return list(self.records)

    def list_mcp_operation_records(self, operation_id: str) -> list[object]:
        self.full_scan_calls.append(operation_id)
        raise AssertionError("resume operation lookup must not scan the full job catalog")


def test_body_resume_operation_lookup_uses_direct_store_reader_without_full_scan() -> None:
    operation_id = "visual_asset_body_silhouette_body.rear_full_3"
    target = SimpleNamespace(job_id="job_rear3")
    store = _DirectedOperationJobStore([target])
    service = SimpleNamespace(job_store=store, visual_asset_catalog=None)
    host = ProductApiAnchorPackPreparationHost(service)

    records = host._mcp_operation_job_records(operation_id)  # noqa: SLF001

    assert records == [target]
    assert store.direct_calls == [operation_id]
    assert store.full_scan_calls == []


def test_persistent_operation_index_streams_legacy_records_and_rejects_wrong_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation_id = "visual_asset_body_silhouette_body.rear_full_3"
    wrong_operation_id = "visual_asset_body_silhouette_body.front_full_1"
    store = PersistentProductJobStore(tmp_path / "v3-jobs")

    def record(job_id: str, operation: str) -> ProductJobRecord:
        return ProductJobRecord(
            request=CreateCreativeJobRequest(
                user_input="durable Body resume",
                metadata={
                    "generation_channel": "mcp",
                    "mcp_operation_id": operation,
                },
            ),
            status=ProductJobStatusValue.PLANNED,
            job_id_value=job_id,
        )

    # Write pre-index records directly to model an existing V3 job directory;
    # the production lookup must migrate it without _load_all_records().
    store._write_record(record("job_rear3", operation_id))  # noqa: SLF001
    store._write_record(record("job_front1", wrong_operation_id))  # noqa: SLF001
    monkeypatch.setattr(
        store,
        "_load_all_records",
        lambda: pytest.fail("operation lookup must not load the full job catalog"),
    )

    matches = store.get_mcp_operation_records(operation_id)

    assert [item.job_id for item in matches] == ["job_rear3"]
    assert store.get_mcp_operation_records(wrong_operation_id)[0].job_id == "job_front1"


def test_persistent_operation_index_is_maintained_on_save_and_reopen(tmp_path: Path) -> None:
    operation_id = "visual_asset_body_silhouette_body.rear_full_3"
    store = PersistentProductJobStore(tmp_path / "v3-jobs")
    store.save(
        ProductJobRecord(
            request=CreateCreativeJobRequest(
                user_input="durable Body resume",
                metadata={
                    "generation_channel": "mcp",
                    "mcp_operation_id": operation_id,
                },
            ),
            status=ProductJobStatusValue.PLANNED,
            job_id_value="job_rear3",
        )
    )
    index_payload = json.loads(
        (tmp_path / "v3-jobs" / "mcp_operation_index.json").read_text(encoding="utf-8")
    )
    assert operation_id not in json.dumps(index_payload, ensure_ascii=True)
    assert hashlib.sha256(operation_id.encode("utf-8")).hexdigest() in index_payload["operations"]

    reopened = PersistentProductJobStore(tmp_path / "v3-jobs")
    reopened._load_all_records = lambda: pytest.fail(  # type: ignore[method-assign]  # noqa: SLF001
        "reopened operation lookup must use the private index"
    )

    matches = reopened.get_mcp_operation_records(operation_id)

    assert [item.job_id for item in matches] == ["job_rear3"]


def test_body_resume_prefers_one_authoritative_generated_checkpoint_over_stale_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation_id = "visual_asset_body_silhouette_body.front_full_2"
    generated = SimpleNamespace(
        job_id="job_generated",
        planning_result=object(),
        generation_result=object(),
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "body_silhouette",
                "professional_character_card_slot": "body.front_full",
                "professional_character_card_reference_output_ids": ["face_ref"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {"handoff_id": "mcp_handoff_current", "status": "job_checkpointed"},
            }
        ),
    )
    stale_retry = SimpleNamespace(
        job_id="job_stale_retry",
        planning_result=object(),
        generation_result=None,
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "body_silhouette",
                "professional_character_card_slot": "body.front_full",
                "professional_character_card_reference_output_ids": ["face_ref"],
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "mcp_materialization": {"handoff_id": "mcp_handoff_current", "status": "pending"},
            }
        ),
    )

    class _Store:
        def get_mcp_operation_records(self, requested_operation_id: str) -> list[object]:
            assert requested_operation_id == operation_id
            return [stale_retry, generated]

    host = ProductApiAnchorPackPreparationHost(
        SimpleNamespace(
            job_store=_Store(),
            visual_asset_catalog=None,
            mcp_materialization_store=SimpleNamespace(),
        )
    )
    monkeypatch.setattr(
        host,
        "_mcp_materialization_payload",
        lambda _handoff_id: {"handoff_id": "mcp_handoff_current", "status": "job_checkpointed"},
    )
    monkeypatch.setattr(host, "_character_card_mcp_handoff_current", lambda _request, _payload: True)
    monkeypatch.setattr(
        host,
        "_character_card_planning_metadata_current",
        lambda _request, _record, _operation_id, _requested_refs: True,
    )
    monkeypatch.setattr(
        host,
        "_character_card_generated_mcp_checkpoint_current",
        lambda _request, record, _operation_id, _payload: record is generated,
    )
    monkeypatch.setattr(
        host,
        "_character_card_submitted_generated_mcp_checkpoint_current",
        lambda _request, _record, _operation_id, _payload: False,
    )

    request = SimpleNamespace(
        reference_output_ids=["face_ref"],
        mcp_handoff_id="mcp_handoff_current",
        review_only_resume=False,
        module="body_silhouette",
        slot_key="body.front_full",
        body_refresh_source_mode="reference_assisted",
        body_refresh_contract_required=True,
    )

    result = host._mcp_resume_character_card_stage_job_record(request, operation_id)  # noqa: SLF001

    assert result is generated


def test_incomplete_operation_index_merges_legacy_and_new_same_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation_id = "visual_asset_body_silhouette_body.rear_full_3"
    store = PersistentProductJobStore(tmp_path / "v3-jobs")

    def record(job_id: str) -> ProductJobRecord:
        return ProductJobRecord(
            request=CreateCreativeJobRequest(
                user_input="durable Body resume",
                metadata={
                    "generation_channel": "mcp",
                    "mcp_operation_id": operation_id,
                },
            ),
            status=ProductJobStatusValue.PLANNED,
            job_id_value=job_id,
        )

    # Legacy A predates the private operation index. Saving B first creates an
    # incomplete index entry for the same operation and must not hide A.
    store._write_record(record("job_legacy_rear3"))  # noqa: SLF001
    store.save(record("job_new_rear3"))
    monkeypatch.setattr(
        store,
        "_load_all_records",
        lambda: pytest.fail("operation lookup must not load the full job catalog"),
    )

    matches = store.get_mcp_operation_records(operation_id)

    assert {item.job_id for item in matches} == {"job_legacy_rear3", "job_new_rear3"}


class _InterruptAfterReviewedCandidate(_RefreshFanoutGenerator):
    """Allow candidate one to review, then emulate an outer process stop."""

    def __init__(self, runtime) -> None:
        super().__init__(runtime)
        self.interrupt_once = True

    def generate(self, request):
        if self.interrupt_once and self.requests:
            self.interrupt_once = False
            raise KeyboardInterrupt()
        return super().generate(request)


def test_library_resume_after_reviewed_candidate_one_starts_candidate_two(
    tmp_path: Path,
) -> None:
    lifecycle, host, service, body_asset_ids, analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    visual_asset_id = next(iter(lifecycle.catalog._assets.values())).visual_asset_id  # noqa: SLF001
    state_store = BodyRefreshAttemptStateStore(tmp_path / "body-refresh-attempts")
    lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=state_store,
    )

    generator = _InterruptAfterReviewedCandidate(host.runtime)
    host.generator = generator
    host.preparation.generator = generator
    def resume_body_silhouette(**kwargs):
        return host.preparation.refresh_body_silhouette(
            kwargs["card"],
            face_reference_output_ids=[
                str(kwargs["card"].face_slots[key].output_id or "")
                for key in ("face.front", "face.profile", "face.rear_head")
            ],
            source_class="observed",
            project_id=f"visual_asset_{visual_asset_id}",
            people_asset_id=visual_asset_id,
            body_evidence_ids=list(kwargs["body_source_admission"].body_evidence_ids),
            consent_provenance_id="server-consent-reference",
            user_intent="reference-assisted Body refresh",
            generation_channel="mcp",
            body_refresh_analysis_context=kwargs["body_refresh_analysis_context"],
            body_refresh_attempt_identity=kwargs["body_refresh_attempt_identity"],
            resume_slot_key=kwargs["resume_slot_key"],
            resume_candidate_index=kwargs["resume_candidate_index"],
        )

    host.resume_body_silhouette = resume_body_silhouette  # type: ignore[attr-defined]
    request = BodySilhouettePublicRequest(
        source_class="observed",
        target_age_scope="age_6_child_only",
        body_reference_asset_id=body_asset_ids[0],
        body_reference_asset_ids=body_asset_ids,
    )

    with pytest.raises(KeyboardInterrupt):
        lifecycle.refresh_character_card_body_silhouette(
            owner_scope="owner",
            visual_asset_id=visual_asset_id,
            body_request=request,
            generation_channel="mcp",
        )
    assert host.preparation.candidate_checkpoint_callback is None
    assert host._body_refresh_candidate_checkpoint_callback is None  # noqa: SLF001
    assert host._body_refresh_formal_receipt_callback is None  # noqa: SLF001

    frozen = state_store.load_current(visual_asset_id=visual_asset_id)
    assert frozen.next_slot_key == "body.front_full"
    assert frozen.next_candidate_index == 2
    assert frozen.analyzer_call_count == 1
    assert [item.candidate_index for item in generator.requests] == [1]

    resumed = lifecycle.resume_character_card_body_silhouette(
        owner_scope="owner",
        visual_asset_id=visual_asset_id,
        body_request=request,
        generation_channel="mcp",
    )

    assert resumed.character_card.body_silhouette_refresh_status in {"blocked", "reviewing"}
    assert [item.candidate_index for item in generator.requests[:2]] == [1, 2]
    assert len(analyzer.calls) == 1
    assert all(
        item.body_refresh_analysis_context.profile_digest
        == frozen.analysis_context.profile_digest
        for item in generator.requests
    )
    assert host.preparation.candidate_checkpoint_callback is None
    assert host._body_refresh_candidate_checkpoint_callback is None  # noqa: SLF001
    assert host._body_refresh_formal_receipt_callback is None  # noqa: SLF001


def test_library_resume_rejects_changed_face_reference_chain_before_host(
    tmp_path: Path,
) -> None:
    lifecycle, host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    original_face_reference_output_ids = [
        str(asset.character_card.face_slots[key].output_id or "")
        for key in ("face.front", "face.profile", "face.rear_head")
    ]
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=original_face_reference_output_ids,
    )
    store = BodyRefreshAttemptStateStore(tmp_path / "face-chain-state")
    store.begin(
        visual_asset_id=asset.visual_asset_id,
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    )

    changed_face = asset.character_card.face_slots["face.front"].model_copy(
        update={"output_id": "face-front-changed"}
    )
    changed_face_slots = dict(asset.character_card.face_slots)
    changed_face_slots["face.front"] = changed_face
    lifecycle.catalog.save(
        asset.model_copy(
            update={
                "character_card": asset.character_card.model_copy(
                    update={"face_slots": changed_face_slots}
                )
            }
        )
    )

    def unexpected_resume(**_kwargs):  # pragma: no cover - guard assertion
        raise AssertionError("resume host must not run after Face chain drift")

    host.resume_body_silhouette = unexpected_resume  # type: ignore[method-assign]
    resumed_lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=store,
    )

    with pytest.raises(
        BodyRefreshAttemptStateError,
        match="face reference chain mismatch",
    ):
        resumed_lifecycle.resume_character_card_body_silhouette(
            owner_scope="owner",
            visual_asset_id=asset.visual_asset_id,
            body_request=BodySilhouettePublicRequest(
                source_class="observed",
                target_age_scope="age_6_child_only",
                body_reference_asset_id=body_asset_ids[0],
                body_reference_asset_ids=body_asset_ids,
            ),
            generation_channel="mcp",
        )


def test_state_pointer_selects_new_same_revision_and_never_falls_back_on_tamper(
    tmp_path: Path,
) -> None:
    store, first_state, _context = _start_state(tmp_path)
    second_attempt, second_context = _profile_context()
    second_state = store.begin(
        visual_asset_id=first_state.visual_asset_id,
        attempt_identity=second_attempt,
        analysis_context=second_context,
        body_source_admission=first_state.body_source_admission,
    )
    current = store.load_current(visual_asset_id=first_state.visual_asset_id)
    assert current.state_id == second_state.state_id
    assert current.attempt_identity.append_only_revision == first_state.attempt_identity.append_only_revision
    assert current.attempt_identity.attempt_id == second_attempt.attempt_id

    store._path(  # noqa: SLF001
        second_state.visual_asset_id,
        second_state.attempt_identity.attempt_id,
    ).write_text("{", encoding="utf-8")
    with pytest.raises(BodyRefreshAttemptStateError, match="state invalid"):
        store.load_current(visual_asset_id=first_state.visual_asset_id)


def test_state_pointer_cross_asset_mismatch_fails_closed(tmp_path: Path) -> None:
    store, state, _context = _start_state(tmp_path)
    pointer_path = store._pointer_path(state.visual_asset_id)  # noqa: SLF001
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["visual_asset_id"] = "different-visual-asset"
    pointer_path.write_text(
        json.dumps(pointer),
        encoding="utf-8",
    )
    with pytest.raises(BodyRefreshAttemptStateError, match="pointer asset mismatch"):
        store.load_current(visual_asset_id=state.visual_asset_id)


@pytest.mark.parametrize(
    "missing_surface",
    ("method", "candidate_callback", "formal_callback"),
)
def test_durable_resume_missing_method_or_callback_preserves_private_callbacks(
    tmp_path: Path,
    missing_surface: str,
) -> None:
    lifecycle, host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=[
            str(asset.character_card.face_slots[key].output_id or "")
            for key in ("face.front", "face.profile", "face.rear_head")
        ],
    )
    store = BodyRefreshAttemptStateStore(tmp_path / "resume-callback-state")
    store.begin(
        visual_asset_id=asset.visual_asset_id,
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    )
    old_candidate_callback = object()
    old_formal_callback = object()
    host._body_refresh_candidate_checkpoint_callback = old_candidate_callback  # noqa: SLF001
    host._body_refresh_formal_receipt_callback = old_formal_callback  # noqa: SLF001
    if missing_surface == "method":
        host.resume_body_silhouette = None  # type: ignore[method-assign]
    elif missing_surface == "candidate_callback":
        host.set_body_refresh_candidate_checkpoint_callback = None  # type: ignore[method-assign]
    else:
        host.set_body_refresh_formal_receipt_callback = None  # type: ignore[method-assign]

    resumed_lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=store,
    )
    with pytest.raises(
        (BodyRefreshAttemptStateError, CharacterCardRuntimeUnavailable),
        match="(body_refresh_durable_resume_unavailable|body refresh durable callbacks unavailable)",
    ):
        resumed_lifecycle.resume_character_card_body_silhouette(
            owner_scope="owner",
            visual_asset_id=asset.visual_asset_id,
            body_request=BodySilhouettePublicRequest(
                source_class="observed",
                target_age_scope="age_6_child_only",
                body_reference_asset_id=body_asset_ids[0],
                body_reference_asset_ids=body_asset_ids,
            ),
            generation_channel="mcp",
        )
    assert host._body_refresh_candidate_checkpoint_callback is old_candidate_callback  # noqa: SLF001
    assert host._body_refresh_formal_receipt_callback is old_formal_callback  # noqa: SLF001


@pytest.mark.parametrize(
    "missing_surface",
    ("candidate_callback", "formal_callback"),
)
def test_fresh_strict_mcp_missing_callback_fails_before_state_begin(
    tmp_path: Path,
    missing_surface: str,
) -> None:
    lifecycle, host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    store = BodyRefreshAttemptStateStore(tmp_path / "fresh-callback-state")
    host._body_refresh_candidate_checkpoint_callback = object()  # noqa: SLF001
    host._body_refresh_formal_receipt_callback = object()  # noqa: SLF001
    if missing_surface == "candidate_callback":
        host.set_body_refresh_candidate_checkpoint_callback = None  # type: ignore[method-assign]
    else:
        host.set_body_refresh_formal_receipt_callback = None  # type: ignore[method-assign]
    fresh_lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=store,
    )
    with pytest.raises(BodyRefreshAttemptStateError, match="callbacks unavailable"):
        fresh_lifecycle.refresh_character_card_body_silhouette(
            owner_scope="owner",
            visual_asset_id=asset.visual_asset_id,
            body_request=BodySilhouettePublicRequest(
                source_class="observed",
                target_age_scope="age_6_child_only",
                body_reference_asset_id=body_asset_ids[0],
                body_reference_asset_ids=body_asset_ids,
            ),
            generation_channel="mcp",
        )
    assert not store._pointer_path(asset.visual_asset_id).exists()  # noqa: SLF001


def _start_state(tmp_path: Path):
    attempt, context = _profile_context()
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=[asset.asset_id for asset in _internal_body_sources()],
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=["face-front", "face-profile", "face-rear"],
    )
    store = BodyRefreshAttemptStateStore(tmp_path / "state")
    state = store.begin(
        visual_asset_id="visual-card-01",
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    )
    return store, state, context


class _FormalContinuationGenerator:
    def __init__(self) -> None:
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        operation_id = (
            f"{request.people_asset_id}:{request.module}:{request.slot_key}:"
            f"{request.candidate_index}:refresh_attempt_"
            f"{hashlib.sha256(request.body_refresh_attempt_identity.attempt_id.encode()).hexdigest()[:16]}"
        )
        return CharacterCardCandidateResult(
            candidate_id=f"candidate_{request.slot_key}_{request.candidate_index}",
            output_id=f"v3_output_{request.slot_key}_{request.candidate_index}",
            module=request.module,
            slot_key=request.slot_key,
            candidate_index=request.candidate_index,
            operation_id=operation_id,
            source_candidate_ids=[f"source_{request.slot_key}_{request.candidate_index}"],
            source_output_ids=list(request.reference_output_ids),
            canonical_prompt_hash="a" * 64,
            prompt_compilation_id=f"compilation_{request.slot_key}_{request.candidate_index}",
            prompt_reference_parity_verified=True,
        )


def _private_front_checkpoint(
    state_store,
    state,
    *,
    operation_id: str,
    output_id: str,
    review_receipt_digest: str,
):
    return state_store.checkpoint_reviewed_candidate(
        state,
        slot_key="body.front_full",
        candidate_index=1,
        candidate_digest=hashlib.sha256(output_id.encode()).hexdigest(),
        attempt_round=1,
        review_status="pass",
        review_receipt_digest=review_receipt_digest,
        operation_id=operation_id,
        output_id=output_id,
    )


def test_review_checkpoint_reconciliation_updates_receipt_without_advancing_cursor(
    tmp_path: Path,
) -> None:
    state_store = BodyRefreshAttemptStateStore(tmp_path / "state")
    attempt, context = _context_for_body_asset_ids(
        [
            "body_source_1",
            "body_source_2",
            "body_source_3",
            "body_source_4",
            "body_source_5",
        ]
    )
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=[
            "body_source_1",
            "body_source_2",
            "body_source_3",
            "body_source_4",
            "body_source_5",
        ],
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=["face_front", "face_profile", "face_rear"],
    )
    state = state_store.begin(
        visual_asset_id="visual_asset_review_reconciliation",
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    )
    operation_id = "body_operation_front_1"
    output_id = "v3_output_front_1"
    state = _private_front_checkpoint(
        state_store,
        state,
        operation_id=operation_id,
        output_id=output_id,
        review_receipt_digest="a" * 64,
    )

    updated = state_store.reconcile_reviewed_candidate(
        state,
        slot_key="body.front_full",
        candidate_index=1,
        attempt_round=1,
        candidate_digest=hashlib.sha256(output_id.encode()).hexdigest(),
        review_status="fail",
        review_receipt_digest="b" * 64,
        operation_id=operation_id,
        output_id=output_id,
    )

    assert updated.next_slot_key == state.next_slot_key
    assert updated.next_candidate_index == state.next_candidate_index
    assert updated.status == state.status
    assert len(updated.candidate_checkpoints) == 1
    assert updated.candidate_checkpoints[0].review_status == "fail"
    assert updated.candidate_checkpoints[0].review_receipt_digest == "b" * 64
    assert state_store.load_current(
        visual_asset_id="visual_asset_review_reconciliation"
    ).candidate_checkpoints[0].review_receipt_digest == "b" * 64


def test_review_checkpoint_reconciliation_rejects_identity_drift(tmp_path: Path) -> None:
    state_store = BodyRefreshAttemptStateStore(tmp_path / "state")
    attempt, context = _context_for_body_asset_ids(
        [
            "body_source_1",
            "body_source_2",
            "body_source_3",
            "body_source_4",
            "body_source_5",
        ]
    )
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=[
            "body_source_1",
            "body_source_2",
            "body_source_3",
            "body_source_4",
            "body_source_5",
        ],
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=["face_front", "face_profile", "face_rear"],
    )
    state = state_store.begin(
        visual_asset_id="visual_asset_review_reconciliation",
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    )
    state = _private_front_checkpoint(
        state_store,
        state,
        operation_id="body_operation_front_1",
        output_id="v3_output_front_1",
        review_receipt_digest="a" * 64,
    )

    with pytest.raises(BodyRefreshAttemptStateError, match="checkpoint identity mismatch"):
        state_store.reconcile_reviewed_candidate(
            state,
            slot_key="body.front_full",
            candidate_index=1,
            attempt_round=1,
            candidate_digest=hashlib.sha256(b"wrong-output").hexdigest(),
            review_status="pass",
            review_receipt_digest="b" * 64,
            operation_id="body_operation_front_1",
            output_id="v3_output_front_1",
        )


def test_library_reconciles_prior_review_receipt_before_resume(
    tmp_path: Path,
) -> None:
    state_store = BodyRefreshAttemptStateStore(tmp_path / "state")
    attempt, context = _context_for_body_asset_ids(
        [
            "body_source_1",
            "body_source_2",
            "body_source_3",
            "body_source_4",
            "body_source_5",
        ]
    )
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=[
            "body_source_1",
            "body_source_2",
            "body_source_3",
            "body_source_4",
            "body_source_5",
        ],
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=["face_front", "face_profile", "face_rear"],
    )
    visual_asset_id = "visual_asset_review_reconciliation"
    state = state_store.begin(
        visual_asset_id=visual_asset_id,
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    )
    operation_id = "body_operation_front_1"
    output_id = "v3_output_front_1"
    state = _private_front_checkpoint(
        state_store,
        state,
        operation_id=operation_id,
        output_id=output_id,
        review_receipt_digest="a" * 64,
    )
    state = state_store.reconcile_reviewed_candidate(
        state,
        slot_key="body.front_full",
        candidate_index=1,
        attempt_round=1,
        candidate_digest=hashlib.sha256(output_id.encode()).hexdigest(),
        review_status="fail",
        review_receipt_digest="b" * 64,
        operation_id=operation_id,
        output_id=output_id,
    )

    class _Host:
        calls: list[tuple[str, int]] = []

        def reconstitute_body_refresh_generated_candidate_checkpoint(self, **kwargs):
            self.calls.append((kwargs["slot_key"], kwargs["candidate_index"]))
            return {
                "slot_key": kwargs["slot_key"],
                "candidate_index": kwargs["candidate_index"],
                "attempt_round": kwargs["attempt_round"],
                "candidate_digest": hashlib.sha256(output_id.encode()).hexdigest(),
                "review_status": "pass",
                "review_receipt_digest": "c" * 64,
                "operation_id": operation_id,
                "output_id": output_id,
            }

    host = _Host()
    library = object.__new__(VisualAssetLibraryLifecycleService)
    library.body_refresh_attempt_state_store = state_store
    library.character_card_stage_host = host
    asset = SimpleNamespace(character_card=SimpleNamespace())

    updated = library._reconcile_body_refresh_prior_candidate_reviews(  # noqa: SLF001
        visual_asset_id=visual_asset_id,
        asset=asset,
        state=state,
    )

    assert host.calls == [("body.front_full", 1)]
    assert updated.next_slot_key == state.next_slot_key
    assert updated.next_candidate_index == state.next_candidate_index
    assert updated.candidate_checkpoints[0].review_status == "pass"
    assert updated.candidate_checkpoints[0].review_receipt_digest == "c" * 64


def _context_for_body_asset_ids(
    body_asset_ids: list[str],
) -> tuple[object, object]:
    attempt, base_context = _profile_context()
    admitted_assets = [
        source.model_copy(update={"asset_id": asset_id})
        for source, asset_id in zip(_internal_body_sources(), body_asset_ids, strict=True)
    ]
    context = base_context.from_analysis(
        attempt_id=attempt.attempt_id,
        append_only_revision=attempt.append_only_revision,
        admitted_body_assets=admitted_assets,
        profile=base_context.profile,
    )
    return attempt, context


def test_new_host_reconstitutes_front_candidate_and_reaches_formal_receipt(
    tmp_path: Path,
) -> None:
    lifecycle, _old_host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=[
            str(asset.character_card.face_slots[key].output_id or "")
            for key in ("face.front", "face.profile", "face.rear_head")
        ],
    )
    state_store = BodyRefreshAttemptStateStore(tmp_path / "state")
    state = state_store.begin(
        visual_asset_id=asset.visual_asset_id,
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    )
    operation_id = (
        f"{asset.visual_asset_id}:body_silhouette:body.front_full:1:refresh_attempt_"
        f"{hashlib.sha256(attempt.attempt_id.encode()).hexdigest()[:16]}"
    )
    output_id = "v3_output_body_front_1"
    candidate = CharacterCardCandidateResult(
        candidate_id="candidate_body_front_1",
        output_id=output_id,
        module="body_silhouette",
        slot_key="body.front_full",
        candidate_index=1,
        operation_id=operation_id,
        source_candidate_ids=["source_body_front_1"],
        source_output_ids=list(admission.face_reference_output_ids),
        canonical_prompt_hash="b" * 64,
        prompt_compilation_id="compilation_front_1",
        prompt_reference_parity_verified=True,
    )
    review = _BodyReviewer().review(candidate)
    state = _private_front_checkpoint(
        state_store,
        state,
        operation_id=operation_id,
        output_id=output_id,
        review_receipt_digest=(
            CharacterCardPreparationService.body_refresh_review_receipt_digest(
                candidate,
                review,
            )
        ),
    )
    checkpoint = state.candidate_checkpoints[0]
    private_payload = state_store._path(  # noqa: SLF001
        asset.visual_asset_id,
        attempt.attempt_id,
    ).read_text(encoding="utf-8")
    assert operation_id in private_payload
    assert output_id in private_payload
    assert "operation_id" not in state.safe_metadata()
    assert "output_id" not in state.safe_metadata()

    fresh_host = ProductApiAnchorPackPreparationHost(service)
    record = SimpleNamespace(
        job_id="job_body_front_1",
        generation_result=SimpleNamespace(),
        request=SimpleNamespace(
            metadata={
                "professional_body_refresh_analysis_context": context.safe_metadata(),
                "professional_character_card_body_source_admission": admission.model_dump(mode="json"),
                "professional_character_card_candidate_index": 1,
                "professional_character_card_candidate_count": 3,
                "professional_character_card_attempt_round": 1,
                "professional_character_card_body_refresh_source_mode": "reference_assisted",
                "professional_character_card_body_refresh_target_age_scope": "age_6_child_only",
                "professional_character_card_body_model_context": "similar_person_body_reference_assisted_v1",
                "mcp_operation_id": operation_id,
            }
        ),
    )
    fresh_host._mcp_resume_character_card_stage_job_record = (  # noqa: SLF001
        lambda _request, requested_operation_id: record
        if requested_operation_id == operation_id
        else None
    )
    fresh_host._character_card_candidate_and_review = (  # noqa: SLF001
        lambda _job_id, _request, **_kwargs: (candidate, review)
    )
    continuation = _FormalContinuationGenerator()

    def continue_with_formal_receipt(**kwargs):
        prep = CharacterCardPreparationService(
            generator=continuation,
            reviewer=_BodyReviewer(),
        )
        card = kwargs["card"]
        return prep.refresh_body_silhouette(
            card,
            face_reference_output_ids=list(admission.face_reference_output_ids),
            source_class="observed",
            project_id=f"visual_asset_{asset.visual_asset_id}",
            people_asset_id=asset.visual_asset_id,
            body_evidence_ids=list(admission.body_evidence_ids),
            consent_provenance_id="server-consent-reference",
            user_intent="reference-assisted Body refresh",
            generation_channel="mcp",
            body_refresh_analysis_context=context,
            body_refresh_attempt_identity=attempt,
            resume_slot_key=kwargs["resume_slot_key"],
            resume_candidate_index=kwargs["resume_candidate_index"],
            prior_reviewed_candidates=kwargs["prior_reviewed_candidates"],
        )

    fresh_host.refresh_body_silhouette = continue_with_formal_receipt  # type: ignore[method-assign]
    result = fresh_host.resume_body_silhouette(
        asset=asset,
        card=asset.character_card,
        request=BodySilhouettePublicRequest(
            source_class="observed",
            target_age_scope="age_6_child_only",
            body_reference_asset_id=body_asset_ids[0],
            body_reference_asset_ids=body_asset_ids,
        ),
        generation_channel="mcp",
        body_refresh_analysis_context=context,
        body_source_admission=admission,
        body_refresh_attempt_identity=attempt,
        resume_slot_key=state.next_slot_key,
        resume_candidate_index=state.next_candidate_index,
        prior_reviewed_candidate_checkpoints=[checkpoint],
    )

    assert result.status == "review", (
        result.failure_codes,
        getattr(result, "shared_runtime_failure", None),
        list(getattr(result, "formal_slot_receipts", {}) or {}),
    )
    assert "body.front_full" in result.formal_slot_receipts
    assert set(result.formal_slot_receipts) == {
        "body.front_full",
        "body.side_full",
        "body.rear_full",
    }
    assert set(result.card.body_silhouette_refresh_slots) == {
        "body.front_full",
        "body.side_full",
        "body.rear_full",
    }
    assert [request.candidate_index for request in continuation.requests[:2]] == [2, 3]
    assert [request.candidate_index for request in continuation.requests[2:]] == [1, 2, 3, 1, 2, 3]


def test_resume_reconstitution_does_not_allocate_prior_records_and_only_current_cursor_enters_plan_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prior candidate reconstruction must not re-project durable job records.

    The resume cursor is rear/candidate3, while front1-3, side1-3, and
    rear1-2 already have durable reviewed records.  Reconstitution may read
    and re-project those records, but the durable operation/job identity set
    must remain unchanged.  Only the current cursor may cross the host
    refresh/create-plan boundary.
    """

    lifecycle, _old_host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    face_reference_output_ids = [
        str(asset.character_card.face_slots[key].output_id or "")
        for key in ("face.front", "face.profile", "face.rear_head")
    ]
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=face_reference_output_ids,
    )
    host = ProductApiAnchorPackPreparationHost(service)
    records: dict[str, SimpleNamespace] = {}
    outputs_by_job: dict[str, list[SimpleNamespace]] = {}
    checkpoints: list[SimpleNamespace] = []
    positions = [
        (slot_key, candidate_index)
        for slot_key in ("body.front_full", "body.side_full", "body.rear_full")
        for candidate_index in (1, 2, 3)
        if not (slot_key == "body.rear_full" and candidate_index == 3)
    ]

    def request_for(slot_key: str, candidate_index: int) -> Any:
        return CharacterCardCandidateRequest(
            project_id=f"visual_asset_{asset.visual_asset_id}",
            people_asset_id=str(asset.visual_asset_id),
            card_version_id=asset.character_card.card_version_id,
            module="body_silhouette",
            slot_key=slot_key,
            candidate_index=candidate_index,
            attempt_round=1,
            reference_output_ids=face_reference_output_ids,
            user_intent="reference-assisted Body refresh",
            source_class="observed",
            body_source_admission=admission,
            body_refresh_source_mode="reference_assisted",
            body_refresh_target_age_scope="age_6_child_only",
            body_model_context="similar_person_body_reference_assisted_v1",
            body_refresh_contract_required=True,
            consent_provenance_id="server-consent-reference",
            generation_channel="mcp",
            body_refresh_attempt_identity=attempt,
            body_refresh_analysis_context=context,
        )

    def add_record(slot_key: str, candidate_index: int) -> None:
        request = request_for(slot_key, candidate_index)
        operation_id = host._character_card_candidate_mcp_operation_id(request)  # noqa: SLF001
        job_id = f"job_reconstituted_{slot_key.rsplit('.', 1)[-1]}_{candidate_index}"
        output_id = f"output_reconstituted_{slot_key.rsplit('.', 1)[-1]}_{candidate_index}"
        candidate_id = f"candidate_{slot_key}_{candidate_index}"
        asset_id = f"asset_{asset.visual_asset_id}"
        output_path = tmp_path / f"{output_id}.png"
        output_path.write_bytes(b"directed-review-fixture")
        inspection = {
            "job_id": job_id,
            "candidate_id": candidate_id,
            "asset_id": asset_id,
            "output_id": output_id,
            "status": "pass",
            "mode": "vision_model",
            "verification_state": "verified",
            "score_card": {
                "same_person_readability": 0.95,
                "distinctive_feature_readability": 0.95,
                "human_realism": 0.95,
                "pose_compliance": 0.95,
                "visual_quality": 0.95,
                "ai_overperfection_penalty": 0.95,
                "overall": 0.95,
                "body_chain_coherence": 0.95,
                "stage_aware_proportion": 0.95,
                "head_neck_shoulder_continuity": 0.95,
                "torso_limb_joint_plausibility": 0.95,
                "stance_ground_contact": 0.95,
            },
            "issue_codes": [],
        }
        metadata = {
            "professional_character_card_preparation": True,
            "professional_character_card_stage": "body_silhouette",
            "professional_character_card_slot": slot_key,
            "professional_character_card_candidate_index": candidate_index,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_attempt_round": 1,
            "professional_character_card_body_refresh_source_mode": "reference_assisted",
            "professional_character_card_body_refresh_target_age_scope": "age_6_child_only",
            "professional_character_card_body_model_context": (
                "similar_person_body_reference_assisted_v1"
            ),
            "professional_character_card_reference_output_ids": face_reference_output_ids,
            "professional_body_refresh_analysis_context": context.safe_metadata(),
            "professional_character_card_body_source_admission": admission.model_dump(mode="json"),
            "mcp_operation_id": operation_id,
            "provider_prompt_sha256": "a" * 64,
            "prompt_compilation_id": f"compiled_{candidate_index}",
            "provider_reference_image_count": 2,
            "provider_reference_assets": ["face_detail", "face_geometry"],
            "post_generation_review_package": {"inspections": [inspection]},
        }
        record = SimpleNamespace(
            job_id=job_id,
            request=SimpleNamespace(metadata=metadata),
            planning_result=None,
            generation_result=SimpleNamespace(metadata=metadata),
            created_at="created",
            updated_at="updated",
        )
        output = SimpleNamespace(
            output_id=output_id,
            job_id=job_id,
            candidate_id=candidate_id,
            asset_id=asset_id,
            file_path=str(output_path),
            output_format="png",
            mime_type="image/png",
            metadata={
                "provider_prompt_sha256": "a" * 64,
                "prompt_compilation_id": f"compiled_{candidate_index}",
                "provider_reference_image_count": 2,
                "provider_reference_assets": ["face_detail", "face_geometry"],
            },
        )
        records[operation_id] = record
        records[job_id] = record
        outputs_by_job[job_id] = [output]
        service.job_store._records[job_id] = record  # noqa: SLF001

        # Prime the exact review receipt without allowing setup to persist a
        # lifecycle projection.  The real resume below re-enables the writer.
        candidate, review = host._character_card_candidate_and_review(  # noqa: SLF001
            job_id,
            request,
            persist_lifecycle_checkpoints=False,
            expected_output_id=output_id,
        )
        checkpoints.append(
            SimpleNamespace(
                slot_key=slot_key,
                candidate_index=candidate_index,
                attempt_round=1,
                operation_id=operation_id,
                output_id=output_id,
                review_status=str(review.status),
                review_receipt_digest=(
                    CharacterCardPreparationService.body_refresh_review_receipt_digest(
                        candidate,
                        review,
                    )
                ),
            )
        )

    original_recorder = service.record_character_card_candidate_lifecycle_checkpoint
    monkeypatch.setattr(
        service,
        "record_character_card_candidate_lifecycle_checkpoint",
        lambda **_kwargs: None,
    )
    def directed_get_output(output_id: str) -> Any:
        return next(
            (
                output
                for outputs in outputs_by_job.values()
                for output in outputs
                if str(output.output_id) == str(output_id)
            ),
            None,
        )

    monkeypatch.setattr(service.output_store, "get_output", directed_get_output)
    monkeypatch.setattr(
        service.output_store,
        "list_by_job",
        lambda job_id: list(outputs_by_job.get(job_id, [])),
    )
    for slot_key, candidate_index in positions:
        add_record(slot_key, candidate_index)
    monkeypatch.setattr(service, "record_character_card_candidate_lifecycle_checkpoint", original_recorder)
    monkeypatch.setattr(
        service,
        "get_job_record",
        lambda job_id: records.get(job_id),
    )
    monkeypatch.setattr(service.output_store, "get_output", directed_get_output)
    monkeypatch.setattr(
        service.output_store,
        "list_by_job",
        lambda _job_id: pytest.fail(
            "prior reconstitution must use the checkpoint output identity, not list_by_job"
        ),
    )
    monkeypatch.setattr(
        host,
        "_mcp_resume_character_card_stage_job_record",
        lambda _request, operation_id: records.get(operation_id),
    )

    prior_record_snapshots = {
        str(record.job_id): (
            str(record.updated_at),
            json.dumps(record.request.metadata, sort_keys=True, separators=(",", ":")),
        )
        for record in records.values()
    }
    durable_job_ids_before_resume = set(service.job_store._records)  # noqa: SLF001
    save_calls: list[str] = []
    original_save = service.job_store.save

    def tracked_save(record: Any) -> Any:
        save_calls.append(str(record.job_id))
        return original_save(record)

    monkeypatch.setattr(service.job_store, "save", tracked_save)
    current_plan_boundary: list[tuple[str, int | None]] = []

    def current_cursor_only(**kwargs: Any) -> Any:
        current_plan_boundary.append(
            (str(kwargs["resume_slot_key"]), kwargs["resume_candidate_index"])
        )
        return SimpleNamespace(
            card=asset.character_card,
            status="blocked",
            failure_codes=["mcp_materialization_pending"],
            shared_runtime_failure=None,
        )

    monkeypatch.setattr(host, "refresh_body_silhouette", current_cursor_only)
    result = host.resume_body_silhouette(
        asset=asset,
        card=asset.character_card,
        request=BodySilhouettePublicRequest(
            source_class="observed",
            target_age_scope="age_6_child_only",
            body_reference_asset_id=body_asset_ids[0],
            body_reference_asset_ids=body_asset_ids,
        ),
        generation_channel="mcp",
        body_refresh_analysis_context=context,
        body_source_admission=admission,
        body_refresh_attempt_identity=attempt,
        resume_slot_key="body.rear_full",
        resume_candidate_index=3,
        prior_reviewed_candidate_checkpoints=checkpoints,
    )

    assert result.status == "blocked"
    assert current_plan_boundary == [("body.rear_full", 3)]
    durable_job_ids_after_resume = set(service.job_store._records)  # noqa: SLF001
    assert durable_job_ids_after_resume - durable_job_ids_before_resume == set()
    assert durable_job_ids_before_resume - durable_job_ids_after_resume == set()
    assert durable_job_ids_after_resume == durable_job_ids_before_resume
    assert save_calls == []

    for record in records.values():
        assert (
            str(record.updated_at),
            json.dumps(record.request.metadata, sort_keys=True, separators=(",", ":")),
        ) == prior_record_snapshots[str(record.job_id)]

    # The default remains write-enabled for a live/current candidate; only
    # prior checkpoint reconstruction receives the read-only flag.
    save_calls.clear()
    live_checkpoint = next(
        item
        for item in checkpoints
        if item.slot_key == "body.rear_full" and item.candidate_index == 2
    )
    host._character_card_candidate_and_review(  # noqa: SLF001
        records[live_checkpoint.operation_id].job_id,
        request_for("body.rear_full", 2),
        expected_output_id=live_checkpoint.output_id,
    )
    assert save_calls

    valid_output = directed_get_output(live_checkpoint.output_id)
    assert valid_output is not None
    wrong_job_output = SimpleNamespace(
        **{**vars(valid_output), "job_id": "job_wrong_binding"}
    )
    for invalid_output in (None, wrong_job_output):
        monkeypatch.setattr(
            service.output_store,
            "get_output",
            lambda _output_id, invalid_output=invalid_output: invalid_output,
        )
        with pytest.raises(CharacterCardCandidateLifecycleBoundaryError) as exc_info:
            host._character_card_candidate_and_review(  # noqa: SLF001
                records[live_checkpoint.operation_id].job_id,
                request_for("body.rear_full", 2),
                persist_lifecycle_checkpoints=False,
                expected_output_id=live_checkpoint.output_id,
            )
        assert (
            exc_info.value.candidate_lifecycle_failure_code
            == "candidate_review_extraction_unbound"
        )


def test_generated_resume_record_uses_result_output_identity_before_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A generated resume record must use its output identity, not list_by_job."""

    lifecycle, _old_host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    face_reference_output_ids = [
        str(asset.character_card.face_slots[key].output_id or "")
        for key in ("face.front", "face.profile", "face.rear_head")
    ]
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=face_reference_output_ids,
    )
    host = ProductApiAnchorPackPreparationHost(service)
    request = CharacterCardCandidateRequest(
        project_id=f"visual_asset_{asset.visual_asset_id}",
        people_asset_id=asset.visual_asset_id,
        card_version_id=asset.character_card.card_version_id,
        module="body_silhouette",
        slot_key="body.rear_full",
        candidate_index=3,
        attempt_round=1,
        reference_output_ids=face_reference_output_ids,
        user_intent="reference-assisted Body refresh",
        source_class="observed",
        consent_provenance_id="server-consent-reference",
        body_source_admission=admission,
        body_refresh_source_mode="reference_assisted",
        body_refresh_target_age_scope="age_6_child_only",
        body_model_context="similar_person_body_reference_assisted_v1",
        body_refresh_contract_required=True,
        generation_channel="mcp",
        body_refresh_attempt_identity=attempt,
        body_refresh_analysis_context=context,
        mcp_handoff_id="mcp_handoff_rear3_directed",
        review_only_resume=True,
    )
    operation_id = host._character_card_candidate_mcp_operation_id(request)  # noqa: SLF001
    output_id = "v3_output_rear3_directed"
    candidate_id = "candidate_rear3_directed"
    asset_id = f"asset_{asset.visual_asset_id}"
    output_path = tmp_path / "rear3-directed.png"
    output_path.write_bytes(b"directed-resume-output")
    inspection = {
        "job_id": "job_rear3_directed",
        "candidate_id": candidate_id,
        "asset_id": asset_id,
        "output_id": output_id,
        "status": "pass",
        "mode": "vision_model",
        "verification_state": "verified",
        "score_card": {
            "same_person_readability": 0.95,
            "distinctive_feature_readability": 0.95,
            "human_realism": 0.95,
            "pose_compliance": 0.95,
            "visual_quality": 0.95,
            "ai_overperfection_penalty": 0.95,
            "overall": 0.95,
            "body_chain_coherence": 0.95,
            "stage_aware_proportion": 0.95,
            "head_neck_shoulder_continuity": 0.95,
            "torso_limb_joint_plausibility": 0.95,
            "stance_ground_contact": 0.95,
        },
        "issue_codes": [],
    }
    output_metadata = {
        "provider_prompt_sha256": "a" * 64,
        "prompt_compilation_id": "compiled_rear3_directed",
        "provider_reference_image_count": 3,
        "provider_reference_assets": ["face_front", "face_profile", "face_rear"],
    }
    output = SimpleNamespace(
        output_id=output_id,
        job_id="job_rear3_directed",
        candidate_id=candidate_id,
        asset_id=asset_id,
        file_path=str(output_path),
        metadata=output_metadata,
    )
    generation_result = SimpleNamespace(
        metadata={"post_generation_review_package": {"inspections": [inspection]}},
        asset_pack=SimpleNamespace(
            assets=[
                SimpleNamespace(
                    metadata={
                        "candidate_metadata": {
                            "output_id": output_id,
                            "candidate_id": candidate_id,
                            "mcp_materialization": {
                                "handoff_id": "mcp_handoff_rear3_directed",
                            },
                        }
                    }
                )
            ]
        ),
    )
    record = SimpleNamespace(
        job_id="job_rear3_directed",
        request=SimpleNamespace(
            metadata={
                "professional_body_refresh_analysis_context": context.safe_metadata(),
                "professional_character_card_body_source_admission": admission.model_dump(mode="json"),
                "professional_character_card_slot": "body.rear_full",
                "professional_character_card_candidate_index": 3,
                "professional_character_card_candidate_count": 3,
                "professional_character_card_attempt_round": 1,
                "professional_character_card_body_refresh_source_mode": "reference_assisted",
                "professional_character_card_body_refresh_target_age_scope": "age_6_child_only",
                "professional_character_card_body_model_context": "similar_person_body_reference_assisted_v1",
                "mcp_operation_id": operation_id,
            }
        ),
        generation_result=generation_result,
    )
    monkeypatch.setattr(
        host,
        "_mcp_resume_character_card_stage_job_record",
        lambda _request, requested_operation_id: (
            record if requested_operation_id == operation_id else None
        ),
    )
    monkeypatch.setattr(service, "get_job_record", lambda _job_id: record)
    get_output_calls: list[str] = []

    def directed_get_output(requested_output_id: str):
        get_output_calls.append(str(requested_output_id))
        return output if requested_output_id == output_id else None

    list_by_job_calls: list[str] = []
    monkeypatch.setattr(service.output_store, "get_output", directed_get_output)
    monkeypatch.setattr(
        service.output_store,
        "file_for_variant",
        lambda _output_id, _variant: (str(output_path),),
    )
    monkeypatch.setattr(
        service.output_store,
        "list_by_job",
        lambda job_id: pytest.fail(
            list_by_job_calls.append(str(job_id))
            or "generated resume must use the result output identity"
        ),
    )
    monkeypatch.setattr(
        host,
        "_record_character_card_candidate_lifecycle_checkpoint",
        lambda **_kwargs: None,
    )

    candidate = host._generate_character_card_candidate(request)  # noqa: SLF001

    assert candidate.output_id == output_id
    assert get_output_calls == [output_id]
    assert list_by_job_calls == []


def test_submitted_generated_body_mcp_checkpoint_enters_direct_review_without_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A submitted frozen artifact with a generated result enters direct review.

    The handoff is deliberately still ``submitted``: it has not received the
    later job-checkpoint projection.  Normal resume is nevertheless safe to
    review when the generated result, file-backed output, review package, and
    every strict Body/MCP identity binding agree.  Explicit review-only resume
    still requires the existing ``job_checkpointed`` authority.  Pending/
    no-output records and tampered handoff/output identities remain closed.
    """

    lifecycle, _old_host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    face_reference_output_ids = [
        str(asset.character_card.face_slots[key].output_id or "")
        for key in ("face.front", "face.profile", "face.rear_head")
    ]
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=face_reference_output_ids,
    )
    host = ProductApiAnchorPackPreparationHost(service)
    handoff_id = "mcp_handoff_rear3_submitted_generated"
    output_id = "v3_output_rear3_submitted_generated"
    candidate_id = "candidate_rear3_submitted_generated"
    output_asset_id = f"asset_{asset.visual_asset_id}"
    operation_id = (
        f"{asset.visual_asset_id}:body_silhouette:body.rear_full:3:refresh_attempt_"
        f"{hashlib.sha256(attempt.attempt_id.encode()).hexdigest()[:16]}"
    )
    request = CharacterCardCandidateRequest(
        project_id=f"visual_asset_{asset.visual_asset_id}",
        people_asset_id=asset.visual_asset_id,
        card_version_id=asset.character_card.card_version_id,
        module="body_silhouette",
        slot_key="body.rear_full",
        candidate_index=3,
        attempt_round=1,
        reference_output_ids=face_reference_output_ids,
        user_intent="reference-assisted Body refresh",
        source_class="observed",
        consent_provenance_id="server-consent-reference",
        body_source_admission=admission,
        body_refresh_source_mode="reference_assisted",
        body_refresh_target_age_scope="age_6_child_only",
        body_model_context="similar_person_body_reference_assisted_v1",
        body_refresh_contract_required=True,
        generation_channel="mcp",
        body_refresh_attempt_identity=attempt,
        body_refresh_analysis_context=context,
        mcp_handoff_id=handoff_id,
        review_only_resume=False,
    )
    output_path = tmp_path / "rear3-submitted-generated.png"
    output_path.write_bytes(b"submitted-generated-review-fixture")
    artifact_sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
    inspection = {
        "job_id": "job_rear3_submitted_generated",
        "candidate_id": candidate_id,
        "asset_id": output_asset_id,
        "output_id": output_id,
        "status": "pass",
        "mode": "vision_model",
        "verification_state": "verified",
        "score_card": {
            "same_person_readability": 0.95,
            "distinctive_feature_readability": 0.95,
            "human_realism": 0.95,
            "pose_compliance": 0.95,
            "visual_quality": 0.95,
            "ai_overperfection_penalty": 0.95,
            "overall": 0.95,
            "body_chain_coherence": 0.95,
            "stage_aware_proportion": 0.95,
            "head_neck_shoulder_continuity": 0.95,
            "torso_limb_joint_plausibility": 0.95,
            "stance_ground_contact": 0.95,
        },
        "issue_codes": [],
    }
    output = SimpleNamespace(
        output_id=output_id,
        job_id="job_rear3_submitted_generated",
        candidate_id=candidate_id,
        asset_id=output_asset_id,
        file_path=str(output_path),
        metadata={"artifact_sha256": artifact_sha256},
    )
    generation_result = SimpleNamespace(
        metadata={"post_generation_review_package": {"inspections": [inspection]}},
        asset_pack=SimpleNamespace(
            assets=[
                SimpleNamespace(
                    metadata={
                        "candidate_metadata": {
                            "output_id": output_id,
                            "candidate_id": candidate_id,
                        }
                    }
                )
            ]
        ),
    )
    record_metadata = {
        "professional_character_card_preparation": True,
        "generation_channel": "mcp",
        "mcp_operation_id": operation_id,
        "professional_character_card_stage": "body_silhouette",
        "professional_character_card_slot": "body.rear_full",
        "professional_character_card_candidate_index": 3,
        "professional_character_card_candidate_count": 3,
        "professional_character_card_attempt_round": 1,
        "professional_character_card_source_class": "observed",
        "professional_character_card_body_refresh_source_mode": "reference_assisted",
        "professional_character_card_body_refresh_target_age_scope": "age_6_child_only",
        "professional_character_card_body_model_context": "similar_person_body_reference_assisted_v1",
        "professional_character_card_reference_output_ids": list(face_reference_output_ids),
        "professional_body_refresh_analysis_context": context.safe_metadata(),
        "professional_character_card_body_source_admission": admission.model_dump(mode="json"),
        "mcp_materialization": {
            "handoff_id": handoff_id,
            "status": "submitted",
            "generation_channel": "mcp",
            "resume_required": True,
        },
    }
    record = SimpleNamespace(
        job_id="job_rear3_submitted_generated",
        request=SimpleNamespace(metadata=record_metadata),
        planning_result=SimpleNamespace(
            generation_plans=[],
            asset_pack=SimpleNamespace(
                assets=[
                    SimpleNamespace(
                        asset_id=output_asset_id,
                        prompt_compilation_id="compiled_rear3_submitted_generated",
                    )
                ]
            ),
        ),
        generation_result=generation_result,
    )
    canonical_prompt = "frozen body renderer prompt"
    face_hash_1 = hashlib.sha256(b"face-physical-1").hexdigest()
    face_hash_2 = hashlib.sha256(b"face-physical-2").hexdigest()
    body_hashes = [hashlib.sha256(f"body-hash-{index}".encode("utf-8")).hexdigest() for index in range(5)]
    face_partition_hash = hashlib.sha256(b"face-semantic-hash").hexdigest()
    renderer_prompt_sha256 = hashlib.sha256(
        (canonical_prompt + "\n\nrenderer directive").encode("utf-8")
    ).hexdigest()
    rendering_contract = {
        "body_refresh_source_mode": "reference_assisted",
        "target_age_scope": "age_6_child_only",
        "slot_key": "body.rear_full",
        "candidate_index": 3,
        "candidate_count": 3,
        "professional_body_refresh_analysis_context": context.safe_metadata(),
        "body_morphology_profile": {
            "schema_version": "body_morphology_evidence_profile_v2",
            "profile_digest": context.profile_digest,
            "target_age_scope": "age_6_child_only",
        },
        "body_mcp_reference_partition": {
            "body_proportion_reference": {
                "asset_count": 5,
                "asset_hashes": body_hashes,
                "role": "body_proportion_reference",
                "truth_layer": "body_proportion_truth",
            },
            "face_identity_reference": {
                "asset_count": 1,
                "asset_hashes": [face_partition_hash],
                "identity_continuity_only": True,
                "role": "face_identity_reference",
                "truth_layer": "identity_continuity",
            },
        },
    }
    rendering_contract_fingerprint = service.mcp_materialization_store._rendering_contract_fingerprint(
        rendering_contract
    )
    renderer_directive = {
        "directive_sha256": "d" * 64,
        "canonical_prompt_sha256": hashlib.sha256(canonical_prompt.encode("utf-8")).hexdigest(),
        "rendering_contract_fingerprint": rendering_contract_fingerprint,
        "materialization_prompt": "renderer directive",
    }
    handoff_payload = {
        "handoff_id": handoff_id,
        "status": "submitted",
        "operation_id": operation_id,
        "artifact_sha256": artifact_sha256,
        "prompt_sha256": hashlib.sha256(canonical_prompt.encode("utf-8")).hexdigest(),
        "canonical_prompt": canonical_prompt,
        "renderer_prompt_sha256": renderer_prompt_sha256,
        "renderer_execution_directive_sha256": "d" * 64,
        "renderer_execution_directive": renderer_directive,
        "reference_asset_hashes": [face_hash_1, face_hash_2],
        "reference_assets": [
            {
                "asset_id": "face-physical-1",
                "sha256": face_hash_1,
                "role": "portrait_identity",
                "reference_truth_layer": "portrait_identity_truth",
                "identity_evidence_scope": "feature_detail",
            },
            {
                "asset_id": "face-physical-2",
                "sha256": face_hash_2,
                "role": "portrait_identity",
                "reference_truth_layer": "portrait_identity_truth",
                "identity_evidence_scope": "pose_geometry",
            },
        ],
        "reference_semantic_fingerprint": "face-semantic-fingerprint",
        "rendering_contract_fingerprint": rendering_contract_fingerprint,
        "rendering_contract": rendering_contract,
    }
    candidate = CharacterCardCandidateResult(
        candidate_id=candidate_id,
        output_id=output_id,
        module="body_silhouette",
        slot_key="body.rear_full",
        candidate_index=3,
        operation_id=operation_id,
        source_candidate_ids=[candidate_id],
        source_output_ids=list(face_reference_output_ids),
        canonical_prompt_hash="a" * 64,
        prompt_compilation_id="compiled_rear3_submitted_generated",
        prompt_reference_parity_verified=True,
    )
    review = _BodyReviewer().review(candidate)
    review_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(host, "_mcp_operation_job_records", lambda _operation_id: [record])
    monkeypatch.setattr(host, "_mcp_materialization_payload", lambda _handoff_id: handoff_payload)
    monkeypatch.setattr(service, "get_job_record", lambda _job_id: record)
    monkeypatch.setattr(service.output_store, "get_output", lambda _output_id: output)
    monkeypatch.setattr(
        service.output_store,
        "file_for_variant",
        lambda _output_id, _variant: (str(output_path),),
    )
    monkeypatch.setattr(
        service.output_store,
        "list_by_job",
        lambda _job_id: pytest.fail("submitted generated direct review must not scan by job"),
    )

    def direct_review(_job_id, _request, **kwargs):
        review_calls.append((str(kwargs.get("expected_output_id") or ""), str(_request.mcp_handoff_id or "")))
        return real_review(_job_id, _request, **kwargs)

    real_review = host._character_card_candidate_and_review
    monkeypatch.setattr(host, "_character_card_candidate_and_review", direct_review)
    monkeypatch.setattr(
        service,
        "generate_professional_character_card_candidate",
        lambda *_args, **_kwargs: pytest.fail("submitted generated target must not call provider"),
    )
    monkeypatch.setattr(
        service,
        "generate_job",
        lambda *_args, **_kwargs: pytest.fail("submitted generated target must not call provider"),
    )
    monkeypatch.setattr(
        service,
        "create_professional_character_card_stage_job",
        lambda *_args, **_kwargs: pytest.fail("submitted generated target must not create a job"),
    )

    original_output_metadata = dict(output.metadata)
    resolved = host._generate_character_card_candidate(request)  # noqa: SLF001

    assert resolved.output_id == output_id
    assert review_calls == [(output_id, handoff_id)]
    assert output.metadata == original_output_metadata
    assert "rendering_contract_fingerprint" not in output.metadata
    assert "provider_reference_assets" not in output.metadata
    assert "prompt_compilation_id" not in output.metadata

    generation_asset_metadata = generation_result.asset_pack.assets[0].metadata
    generation_asset_metadata["candidate_metadata"]["mcp_materialization"] = {
        "handoff_id": "mcp_handoff_wrong"
    }
    with pytest.raises(AnchorCandidateUnavailable) as generation_handoff_conflict_exc:
        host._generate_character_card_candidate(request)  # noqa: SLF001
    assert generation_handoff_conflict_exc.value.failure_code == "mcp_materialization_checkpoint_mismatch"
    generation_asset_metadata["candidate_metadata"].pop("mcp_materialization")

    legacy_handoff = dict(handoff_payload)
    legacy_contract = dict(handoff_payload["rendering_contract"])
    for legacy_key in (
        "slot_key",
        "candidate_index",
        "candidate_count",
        "professional_body_refresh_analysis_context",
    ):
        legacy_contract.pop(legacy_key, None)
    legacy_handoff["rendering_contract"] = legacy_contract
    monkeypatch.setattr(
        host,
        "_mcp_materialization_payload",
        lambda _handoff_id, payload=legacy_handoff: payload,
    )
    review_calls.clear()

    legacy_resolved = host._generate_character_card_candidate(request)  # noqa: SLF001

    assert legacy_resolved.output_id == output_id
    assert review_calls == [(output_id, handoff_id)]

    conflicting_handoff = dict(legacy_handoff)
    conflicting_contract = dict(legacy_contract)
    conflicting_contract["slot_key"] = "body.front_full"
    conflicting_handoff["rendering_contract"] = conflicting_contract
    monkeypatch.setattr(
        host,
        "_mcp_materialization_payload",
        lambda _handoff_id, payload=conflicting_handoff: payload,
    )
    with pytest.raises(AnchorCandidateUnavailable) as conflict_exc:
        host._generate_character_card_candidate(request)  # noqa: SLF001
    assert conflict_exc.value.failure_code == "mcp_materialization_checkpoint_mismatch"

    bad_prompt_handoff = dict(legacy_handoff)
    bad_prompt_handoff["prompt_sha256"] = "0" * 64
    monkeypatch.setattr(
        host,
        "_mcp_materialization_payload",
        lambda _handoff_id, payload=bad_prompt_handoff: payload,
    )
    with pytest.raises(AnchorCandidateUnavailable) as bad_prompt_exc:
        host._generate_character_card_candidate(request)  # noqa: SLF001
    assert bad_prompt_exc.value.failure_code == "mcp_materialization_checkpoint_mismatch"

    missing_planning_asset_record = SimpleNamespace(
        job_id=record.job_id,
        request=record.request,
        planning_result=SimpleNamespace(
            generation_plans=[],
            asset_pack=SimpleNamespace(
                assets=[
                    SimpleNamespace(
                        asset_id="asset_for_another_output",
                        prompt_compilation_id="compiled_rear3_submitted_generated",
                    )
                ]
            ),
            ),
        generation_result=record.generation_result,
    )
    monkeypatch.setattr(host, "_mcp_operation_job_records", lambda _operation_id: [missing_planning_asset_record])
    monkeypatch.setattr(service, "get_job_record", lambda _job_id: missing_planning_asset_record)
    monkeypatch.setattr(
        host,
        "_mcp_materialization_payload",
        lambda _handoff_id, payload=legacy_handoff: payload,
    )
    with pytest.raises(AnchorCandidateUnavailable) as missing_planning_asset_exc:
        host._generate_character_card_candidate(request)  # noqa: SLF001
    assert missing_planning_asset_exc.value.failure_code == (
        "professional_character_card_prompt_reference_parity_unverified"
    )
    monkeypatch.setattr(service, "get_job_record", lambda _job_id: record)

    body_mixed_handoff = dict(legacy_handoff)
    body_mixed_handoff["reference_asset_hashes"] = [body_hashes[0], face_hash_2]
    monkeypatch.setattr(
        host,
        "_mcp_materialization_payload",
        lambda _handoff_id, payload=body_mixed_handoff: payload,
    )
    monkeypatch.setattr(host, "_mcp_operation_job_records", lambda _operation_id: [record])
    with pytest.raises(AnchorCandidateUnavailable) as body_mixed_exc:
        host._generate_character_card_candidate(request)  # noqa: SLF001
    assert body_mixed_exc.value.failure_code == "mcp_materialization_checkpoint_mismatch"

    missing_metadata = dict(record_metadata)
    missing_metadata.pop("professional_body_refresh_analysis_context")
    missing_metadata_record = SimpleNamespace(
        job_id=record.job_id,
        request=SimpleNamespace(metadata=missing_metadata),
        planning_result=record.planning_result,
        generation_result=record.generation_result,
    )
    monkeypatch.setattr(host, "_mcp_operation_job_records", lambda _operation_id: [missing_metadata_record])
    monkeypatch.setattr(
        host,
        "_mcp_materialization_payload",
        lambda _handoff_id, payload=legacy_handoff: payload,
    )
    with pytest.raises(AnchorCandidateUnavailable) as missing_metadata_exc:
        host._generate_character_card_candidate(request)  # noqa: SLF001
    assert missing_metadata_exc.value.failure_code == "mcp_materialization_checkpoint_mismatch"

    monkeypatch.setattr(host, "_mcp_operation_job_records", lambda _operation_id: [record])

    explicit_review_only_request = request.model_copy(update={"review_only_resume": True})
    with pytest.raises(AnchorCandidateUnavailable) as review_only_exc:
        host._mcp_resume_character_card_stage_job_record(  # noqa: SLF001
            explicit_review_only_request,
            operation_id,
        )
    assert review_only_exc.value.failure_code == "mcp_review_target_not_found"

    pending_record = SimpleNamespace(
        job_id=record.job_id,
        request=record.request,
        planning_result=record.planning_result,
        generation_result=None,
    )
    monkeypatch.setattr(host, "_mcp_operation_job_records", lambda _operation_id: [pending_record])
    assert host._mcp_resume_character_card_stage_job_record(request, operation_id) is None  # noqa: SLF001

    monkeypatch.setattr(host, "_mcp_operation_job_records", lambda _operation_id: [record])
    wrong_handoff_request = request.model_copy(update={"mcp_handoff_id": "mcp_handoff_wrong"})
    with pytest.raises(AnchorCandidateUnavailable) as wrong_handoff_exc:
        host._mcp_resume_character_card_stage_job_record(  # noqa: SLF001
            wrong_handoff_request,
            operation_id,
        )
    assert wrong_handoff_exc.value.failure_code == "mcp_materialization_checkpoint_mismatch"

    wrong_output_generation_result = SimpleNamespace(
        metadata=generation_result.metadata,
        asset_pack=SimpleNamespace(
            assets=[
                SimpleNamespace(
                    metadata={
                        "candidate_metadata": {
                            "output_id": "v3_output_wrong",
                            "candidate_id": candidate_id,
                            "mcp_materialization": {"handoff_id": handoff_id},
                        }
                    }
                )
            ]
        ),
    )
    wrong_output_record = SimpleNamespace(
        job_id=record.job_id,
        request=record.request,
        planning_result=record.planning_result,
        generation_result=wrong_output_generation_result,
    )
    monkeypatch.setattr(host, "_mcp_operation_job_records", lambda _operation_id: [wrong_output_record])
    with pytest.raises(AnchorCandidateUnavailable) as wrong_output_exc:
        host._mcp_resume_character_card_stage_job_record(request, operation_id)  # noqa: SLF001
    assert wrong_output_exc.value.failure_code == "mcp_materialization_checkpoint_mismatch"

    monkeypatch.setattr(host, "_mcp_operation_job_records", lambda _operation_id: [record])
    for missing_contract_key in (
        "slot_key",
        "candidate_index",
        "candidate_count",
        "professional_body_refresh_analysis_context",
    ):
        incomplete_handoff = dict(handoff_payload)
        incomplete_contract = dict(handoff_payload["rendering_contract"])
        incomplete_contract.pop(missing_contract_key, None)
        incomplete_handoff["rendering_contract"] = incomplete_contract
        monkeypatch.setattr(host, "_mcp_materialization_payload", lambda _handoff_id, payload=incomplete_handoff: payload)
        review_calls.clear()
        resolved_incomplete = host._generate_character_card_candidate(request)  # noqa: SLF001
        assert resolved_incomplete.output_id == output_id
        assert review_calls == [(output_id, handoff_id)]


def test_generated_resume_record_without_output_identity_fails_closed_before_output_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A generated resume result without a server-owned output ID is closed."""

    lifecycle, _old_host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    face_reference_output_ids = [
        str(asset.character_card.face_slots[key].output_id or "")
        for key in ("face.front", "face.profile", "face.rear_head")
    ]
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=face_reference_output_ids,
    )
    host = ProductApiAnchorPackPreparationHost(service)
    request = CharacterCardCandidateRequest(
        project_id=f"visual_asset_{asset.visual_asset_id}",
        people_asset_id=asset.visual_asset_id,
        card_version_id=asset.character_card.card_version_id,
        module="body_silhouette",
        slot_key="body.rear_full",
        candidate_index=3,
        reference_output_ids=face_reference_output_ids,
        user_intent="reference-assisted Body refresh",
        source_class="observed",
        consent_provenance_id="server-consent-reference",
        body_source_admission=admission,
        body_refresh_source_mode="reference_assisted",
        body_refresh_target_age_scope="age_6_child_only",
        body_model_context="similar_person_body_reference_assisted_v1",
        body_refresh_contract_required=True,
        generation_channel="mcp",
        body_refresh_attempt_identity=attempt,
        body_refresh_analysis_context=context,
        mcp_handoff_id="mcp_handoff_rear3_missing_output",
        review_only_resume=True,
    )
    operation_id = host._character_card_candidate_mcp_operation_id(request)  # noqa: SLF001
    record = SimpleNamespace(
        job_id="job_rear3_missing_output",
        request=SimpleNamespace(
            metadata={
                "professional_body_refresh_analysis_context": context.safe_metadata(),
            }
        ),
        generation_result=SimpleNamespace(
            metadata={},
            asset_pack=SimpleNamespace(
                assets=[
                    SimpleNamespace(
                        metadata={
                            "candidate_metadata": {
                                "candidate_id": "candidate_rear3_missing_output",
                                "mcp_materialization": {
                                    "handoff_id": "mcp_handoff_rear3_missing_output",
                                },
                            }
                        }
                    )
                ]
            ),
        ),
    )
    monkeypatch.setattr(
        host,
        "_mcp_resume_character_card_stage_job_record",
        lambda _request, requested_operation_id: (
            record if requested_operation_id == operation_id else None
        ),
    )
    monkeypatch.setattr(service, "get_job_record", lambda _job_id: record)
    monkeypatch.setattr(
        service.output_store,
        "list_by_job",
        lambda _job_id: pytest.fail("missing output identity must fail before list_by_job"),
    )

    with pytest.raises(AnchorCandidateUnavailable) as exc_info:
        host._generate_character_card_candidate(request)  # noqa: SLF001

    assert exc_info.value.failure_code == "mcp_review_output_identity_missing"


def test_library_resume_passes_pointer_cursor_to_one_host_boundary_without_fanout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public resume entry must admit only the pointer's current cursor."""

    lifecycle, host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    face_reference_output_ids = [
        str(asset.character_card.face_slots[key].output_id or "")
        for key in ("face.front", "face.profile", "face.rear_head")
    ]
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=face_reference_output_ids,
    )
    state_store = BodyRefreshAttemptStateStore(tmp_path / "body-refresh-attempts")
    state = state_store.begin(
        visual_asset_id=asset.visual_asset_id,
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    ).model_copy(
        update={
            "status": "interrupted",
            "next_slot_key": "body.rear_full",
            "next_candidate_index": 3,
        }
    )
    state_store._write(state)  # noqa: SLF001
    lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=state_store,
    )
    captured: list[dict[str, object]] = []

    def resume_boundary(**kwargs):  # noqa: ANN001
        captured.append(
            {
                "resume_slot_key": kwargs["resume_slot_key"],
                "resume_candidate_index": kwargs["resume_candidate_index"],
                "attempt_id": kwargs["body_refresh_attempt_identity"].attempt_id,
                "source_digest": kwargs["body_source_admission"].source_evidence_id_digest(),
            }
        )
        return SimpleNamespace(card=kwargs["card"], status="blocked")

    monkeypatch.setattr(host, "resume_body_silhouette", resume_boundary)
    monkeypatch.setattr(
        service,
        "create_professional_character_card_stage_job",
        lambda *_args, **_kwargs: pytest.fail("resume must not enter a new create/plan boundary"),
    )
    request = BodySilhouettePublicRequest(
        source_class="observed",
        target_age_scope="age_6_child_only",
        body_reference_asset_id=body_asset_ids[0],
        body_reference_asset_ids=body_asset_ids,
    )

    lifecycle.resume_character_card_body_silhouette(
        owner_scope="owner",
        visual_asset_id=asset.visual_asset_id,
        body_request=request,
        generation_channel="mcp",
    )

    assert captured == [
        {
            "resume_slot_key": "body.rear_full",
            "resume_candidate_index": 3,
            "attempt_id": attempt.attempt_id,
            "source_digest": admission.source_evidence_id_digest(),
        }
    ]


def test_library_resume_reconciles_generated_current_candidate_before_host_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A submitted/resumed MCP candidate must advance the private cursor once.

    External materialization can make the authoritative ProductApi job
    generated before the CharacterCard fan-out callback runs.  The official
    library resume must checkpoint that already-reviewed candidate before it
    asks Host to continue, otherwise it restarts candidate one.
    """

    lifecycle, host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    face_reference_output_ids = [
        str(asset.character_card.face_slots[key].output_id or "")
        for key in ("face.front", "face.profile", "face.rear_head")
    ]
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=face_reference_output_ids,
    )
    state_store = BodyRefreshAttemptStateStore(tmp_path / "generated-current-state")
    initial_state = state_store.begin(
        visual_asset_id=asset.visual_asset_id,
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    )
    assert initial_state.next_slot_key == "body.front_full"
    assert initial_state.next_candidate_index == 1
    lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=state_store,
    )
    candidate_request = CharacterCardCandidateRequest(
        project_id=f"visual_asset_{asset.visual_asset_id}",
        people_asset_id=asset.visual_asset_id,
        card_version_id=asset.character_card.card_version_id,
        module="body_silhouette",
        slot_key="body.front_full",
        candidate_index=1,
        attempt_round=1,
        reference_output_ids=face_reference_output_ids,
        user_intent="reference-assisted Body refresh",
        source_class="observed",
        consent_provenance_id="server-consent-reference",
        body_source_admission=admission,
        body_refresh_source_mode="reference_assisted",
        body_refresh_target_age_scope="age_6_child_only",
        body_model_context="similar_person_body_reference_assisted_v1",
        body_refresh_contract_required=True,
        generation_channel="mcp",
        body_refresh_attempt_identity=attempt,
        body_refresh_analysis_context=context,
    )
    operation_id = host._character_card_candidate_mcp_operation_id(candidate_request)  # noqa: SLF001
    output_id = "v3_output_body_front_generated_current"
    candidate = CharacterCardCandidateResult(
        candidate_id="candidate_body_front_generated_current",
        output_id=output_id,
        module="body_silhouette",
        slot_key="body.front_full",
        candidate_index=1,
        operation_id=operation_id,
        source_candidate_ids=["source_body_front_generated_current"],
        source_output_ids=face_reference_output_ids,
        canonical_prompt_hash="c" * 64,
        prompt_compilation_id="compilation_front_generated_current",
        prompt_reference_parity_verified=True,
    )
    review = _BodyReviewer().review(candidate)
    record = SimpleNamespace(
        job_id="job_body_front_generated_current",
        generation_result=SimpleNamespace(
            metadata={},
            asset_pack=SimpleNamespace(
                assets=[
                    SimpleNamespace(
                        metadata={
                            "candidate_metadata": {
                                "output_id": output_id,
                                "candidate_id": candidate.candidate_id,
                            }
                        }
                    )
                ]
            ),
        ),
        request=SimpleNamespace(
            metadata={
                "professional_body_refresh_analysis_context": context.safe_metadata(),
                "professional_character_card_body_source_admission": admission.model_dump(mode="json"),
                "professional_character_card_candidate_index": 1,
                "professional_character_card_candidate_count": 3,
                "professional_character_card_attempt_round": 1,
                "professional_character_card_body_refresh_source_mode": "reference_assisted",
                "professional_character_card_body_refresh_target_age_scope": "age_6_child_only",
                "professional_character_card_body_model_context": "similar_person_body_reference_assisted_v1",
                "mcp_operation_id": operation_id,
            }
        ),
    )
    monkeypatch.setattr(
        host,
        "_mcp_resume_character_card_stage_job_record",
        lambda _request, requested_operation_id: (
            record if requested_operation_id == operation_id else None
        ),
    )
    review_calls: list[dict[str, object]] = []

    def reconstitute_generated_candidate(_job_id, _request, **kwargs):
        review_calls.append(
            {
                "job_id": _job_id,
                "operation_id": _request.operation_id if hasattr(_request, "operation_id") else operation_id,
                "expected_output_id": kwargs.get("expected_output_id"),
                "persist": kwargs.get("persist_lifecycle_checkpoints", True),
            }
        )
        return candidate, review

    monkeypatch.setattr(host, "_character_card_candidate_and_review", reconstitute_generated_candidate)
    captured: list[dict[str, object]] = []

    def resume_boundary(**kwargs):
        captured.append(
            {
                "resume_slot_key": kwargs["resume_slot_key"],
                "resume_candidate_index": kwargs["resume_candidate_index"],
                "checkpoint_count": len(kwargs["prior_reviewed_candidate_checkpoints"]),
            }
        )
        return CharacterCardStageResult(
            status="blocked",
            card=kwargs["card"],
            attempts=[],
            winner_output_ids={},
            failure_codes=["mcp_materialization_pending"],
        )

    monkeypatch.setattr(host, "resume_body_silhouette", resume_boundary)

    lifecycle.resume_character_card_body_silhouette(
        owner_scope="owner",
        visual_asset_id=asset.visual_asset_id,
        body_request=BodySilhouettePublicRequest(
            source_class="observed",
            target_age_scope="age_6_child_only",
            body_reference_asset_id=body_asset_ids[0],
            body_reference_asset_ids=body_asset_ids,
        ),
        generation_channel="mcp",
    )

    assert captured == [
        {
            "resume_slot_key": "body.front_full",
            "resume_candidate_index": 2,
            "checkpoint_count": 1,
        }
    ]
    assert review_calls == [
        {
            "job_id": "job_body_front_generated_current",
            "operation_id": operation_id,
            "expected_output_id": output_id,
            "persist": False,
        }
    ]
    reconciled_state = state_store.load_current(visual_asset_id=asset.visual_asset_id)
    assert reconciled_state.next_slot_key == "body.front_full"
    assert reconciled_state.next_candidate_index == 2
    assert reconciled_state.candidate_checkpoints[0].operation_id == operation_id
    assert reconciled_state.candidate_checkpoints[0].output_id == output_id


def test_fresh_observed_mcp_refresh_rejects_existing_current_attempt_before_overwrite(
    tmp_path: Path,
) -> None:
    lifecycle, host, service, body_asset_ids, analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=[
            str(asset.character_card.face_slots[key].output_id or "")
            for key in ("face.front", "face.profile", "face.rear_head")
        ],
    )
    state_store = BodyRefreshAttemptStateStore(tmp_path / "fresh-overwrite-state")
    state_store.begin(
        visual_asset_id=asset.visual_asset_id,
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    )
    lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=state_store,
    )

    with pytest.raises(BodyRefreshAttemptStateError, match="already in progress"):
        lifecycle.refresh_character_card_body_silhouette(
            owner_scope="owner",
            visual_asset_id=asset.visual_asset_id,
            body_request=BodySilhouettePublicRequest(
                source_class="observed",
                target_age_scope="age_6_child_only",
                body_reference_asset_id=body_asset_ids[0],
                body_reference_asset_ids=body_asset_ids,
            ),
            generation_channel="mcp",
        )

    assert analyzer.asset_ids == []
    assert (
        state_store.load_current(visual_asset_id=asset.visual_asset_id).attempt_identity.attempt_id
        == attempt.attempt_id
    )


def _card_with_formal_front_refresh_slot(
    asset,
    attempt,
    front_attempts,
    *,
    reload_public_projection_verified: bool = True,
):
    formal_receipt = CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
        slot_key="body.front_full",
        attempts=front_attempts,
    )
    if reload_public_projection_verified:
        formal_receipt = mark_formal_slot_receipt_reload_public_projection_verified(formal_receipt)
    winner_attempt = next(
        item for item in front_attempts
        if item.candidate.output_id == formal_receipt.winner_output_id
    )
    front_slot = CharacterCardPreparationService._winner_slot(  # noqa: SLF001
        module="body_silhouette",
        slot_key="body.front_full",
        winner=winner_attempt.candidate,
        source_class="observed",
        consent_provenance_id="server-consent-reference",
        formal_slot_receipt=formal_receipt,
    )
    return asset.character_card.model_copy(
        update={
            "body_silhouette_refresh_status": "blocked",
            "body_silhouette_refresh_version_id": attempt.attempt_id,
            "body_silhouette_refresh_slots": {"body.front_full": front_slot},
        }
    )


def _state_after_formal_front(
    *,
    store: BodyRefreshAttemptStateStore,
    asset,
    attempt,
    context,
    admission: BodySourceAdmission,
    front_attempts,
):
    state = store.begin(
        visual_asset_id=asset.visual_asset_id,
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    )
    for index, candidate_attempt in enumerate(front_attempts, start=1):
        output_id = candidate_attempt.candidate.output_id
        state = store.checkpoint_reviewed_candidate(
            state,
            slot_key="body.front_full",
            candidate_index=index,
            attempt_round=1,
            candidate_digest=hashlib.sha256(output_id.encode()).hexdigest(),
            review_status="pass",
            review_receipt_digest=(
                CharacterCardPreparationService.body_refresh_review_receipt_digest(
                    candidate_attempt.candidate,
                    candidate_attempt.review,
                )
            ),
            operation_id=(
                f"{asset.visual_asset_id}:body_silhouette:body.front_full:{index}:refresh_attempt_"
                f"{hashlib.sha256(attempt.attempt_id.encode()).hexdigest()[:16]}"
            ),
            output_id=output_id,
        )
    formal_receipt = CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
        slot_key="body.front_full",
        attempts=front_attempts,
    )
    return store.record_formal_receipt(state, formal_receipt=formal_receipt)


def test_library_resume_reconciles_persisted_formal_receipt_before_host(
    tmp_path: Path,
) -> None:
    lifecycle, host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=[
            str(asset.character_card.face_slots[key].output_id or "")
            for key in ("face.front", "face.profile", "face.rear_head")
        ],
    )
    front_attempts = [_body_attempt(index, slot_key="body.front_full") for index in (1, 2, 3)]
    unmarked_card = _card_with_formal_front_refresh_slot(
        asset,
        attempt,
        front_attempts,
        reload_public_projection_verified=False,
    )
    assert not unmarked_card.body_silhouette_refresh_slots[
        "body.front_full"
    ].formal_slot_receipt.reload_public_projection_verified
    lifecycle.catalog.save(asset.model_copy(update={"character_card": unmarked_card}))
    store = BodyRefreshAttemptStateStore(tmp_path / "pre-host-reconcile-state")
    _state_after_formal_front(
        store=store,
        asset=asset,
        attempt=attempt,
        context=context,
        admission=admission,
        front_attempts=front_attempts,
    )
    lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=store,
    )
    observed = {"verified": False}

    def resume_body_silhouette(**kwargs):
        receipt = kwargs["card"].body_silhouette_refresh_slots[
            "body.front_full"
        ].formal_slot_receipt
        observed["verified"] = bool(receipt.reload_public_projection_verified)
        return CharacterCardStageResult(
            status="blocked",
            card=kwargs["card"],
            attempts=[],
            winner_output_ids={},
            failure_codes=["mcp_materialization_pending"],
        )

    host.resume_body_silhouette = resume_body_silhouette  # type: ignore[method-assign]
    lifecycle.resume_character_card_body_silhouette(
        owner_scope="owner",
        visual_asset_id=asset.visual_asset_id,
        body_request=BodySilhouettePublicRequest(
            source_class="observed",
            target_age_scope="age_6_child_only",
            body_reference_asset_id=body_asset_ids[0],
            body_reference_asset_ids=body_asset_ids,
        ),
        generation_channel="mcp",
    )

    assert observed["verified"] is True
    persisted = lifecycle.get(owner_scope="owner", visual_asset_id=asset.visual_asset_id)
    assert persisted.character_card.body_silhouette_refresh_slots[
        "body.front_full"
    ].formal_slot_receipt.reload_public_projection_verified


def test_library_marks_formal_receipt_when_later_slot_returns_blocked(
    tmp_path: Path,
) -> None:
    lifecycle, host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=[
            str(asset.character_card.face_slots[key].output_id or "")
            for key in ("face.front", "face.profile", "face.rear_head")
        ],
    )
    front_attempts = [_body_attempt(index, slot_key="body.front_full") for index in (1, 2, 3)]
    unmarked_card = _card_with_formal_front_refresh_slot(
        asset,
        attempt,
        front_attempts,
        reload_public_projection_verified=False,
    )
    store = BodyRefreshAttemptStateStore(tmp_path / "post-save-reconcile-state")
    _state_after_formal_front(
        store=store,
        asset=asset,
        attempt=attempt,
        context=context,
        admission=admission,
        front_attempts=front_attempts,
    )
    lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=store,
    )

    def resume_body_silhouette(**kwargs):
        return CharacterCardStageResult(
            status="blocked",
            card=unmarked_card,
            attempts=[],
            winner_output_ids={"body.front_full": unmarked_card.body_silhouette_refresh_slots["body.front_full"].output_id},
            failure_codes=["mcp_materialization_pending"],
        )

    host.resume_body_silhouette = resume_body_silhouette  # type: ignore[method-assign]
    lifecycle.resume_character_card_body_silhouette(
        owner_scope="owner",
        visual_asset_id=asset.visual_asset_id,
        body_request=BodySilhouettePublicRequest(
            source_class="observed",
            target_age_scope="age_6_child_only",
            body_reference_asset_id=body_asset_ids[0],
            body_reference_asset_ids=body_asset_ids,
        ),
        generation_channel="mcp",
    )

    persisted = lifecycle.get(owner_scope="owner", visual_asset_id=asset.visual_asset_id)
    assert persisted.character_card.body_silhouette_refresh_slots[
        "body.front_full"
    ].formal_slot_receipt.reload_public_projection_verified


def test_resume_side_preserves_same_attempt_formal_front_slot(tmp_path: Path) -> None:
    lifecycle, _host, _service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=[
            str(asset.character_card.face_slots[key].output_id or "")
            for key in ("face.front", "face.profile", "face.rear_head")
        ],
    )
    front_attempts = [_body_attempt(index, slot_key="body.front_full") for index in (1, 2, 3)]
    resumed_card = _card_with_formal_front_refresh_slot(asset, attempt, front_attempts)
    continuation = _FormalContinuationGenerator()
    preparation = CharacterCardPreparationService(
        generator=continuation,
        reviewer=_BodyReviewer(),
    )

    result = preparation.refresh_body_silhouette(
        resumed_card,
        face_reference_output_ids=list(admission.face_reference_output_ids),
        source_class="observed",
        project_id=f"visual_asset_{asset.visual_asset_id}",
        people_asset_id=asset.visual_asset_id,
        body_evidence_ids=list(admission.body_evidence_ids),
        consent_provenance_id="server-consent-reference",
        user_intent="reference-assisted Body refresh",
        generation_channel="mcp",
        body_refresh_analysis_context=context,
        body_refresh_attempt_identity=attempt,
        resume_slot_key="body.side_full",
        resume_candidate_index=2,
        prior_reviewed_candidates={
            ("body.side_full", 1): _body_attempt(1, slot_key="body.side_full"),
        },
    )

    assert result.status == "review"
    assert set(result.card.body_silhouette_refresh_slots) == {
        "body.front_full",
        "body.side_full",
        "body.rear_full",
    }
    assert result.card.body_silhouette_refresh_slots["body.front_full"].formal_slot_receipt is not None
    assert [request.slot_key for request in continuation.requests] == [
        "body.side_full",
        "body.side_full",
        "body.rear_full",
        "body.rear_full",
        "body.rear_full",
    ]
    assert [request.candidate_index for request in continuation.requests] == [2, 3, 1, 2, 3]


def test_formal_only_resume_reconstitutes_slot_without_generating(tmp_path: Path) -> None:
    lifecycle, _host, _service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    front_attempts = [_body_attempt(index, slot_key="body.front_full") for index in (1, 2, 3)]
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=[
            str(asset.character_card.face_slots[key].output_id or "")
            for key in ("face.front", "face.profile", "face.rear_head")
        ],
    )
    resumed_card = asset.character_card.model_copy(
        update={
            "body_silhouette_refresh_status": "blocked",
            "body_silhouette_refresh_version_id": attempt.attempt_id,
            "body_silhouette_refresh_slots": {},
        }
    )
    store = BodyRefreshAttemptStateStore(tmp_path / "formal-only-state")
    state = store.begin(
        visual_asset_id=asset.visual_asset_id,
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    )
    for index, candidate_attempt in enumerate(front_attempts, start=1):
        output_id = candidate_attempt.candidate.output_id
        state = store.checkpoint_reviewed_candidate(
            state,
            slot_key="body.front_full",
            candidate_index=index,
            attempt_round=1,
            candidate_digest=hashlib.sha256(output_id.encode()).hexdigest(),
            review_status="pass",
            review_receipt_digest=(
                CharacterCardPreparationService.body_refresh_review_receipt_digest(
                    candidate_attempt.candidate,
                    candidate_attempt.review,
                )
            ),
            operation_id=(
                f"{asset.visual_asset_id}:body_silhouette:body.front_full:{index}:refresh_attempt_"
                f"{hashlib.sha256(attempt.attempt_id.encode()).hexdigest()[:16]}"
            ),
            output_id=output_id,
        )
    assert state.status == "awaiting_slot_acceptance"
    assert state.next_candidate_index is None

    class _MustNotGenerate:
        def generate(self, request):  # pragma: no cover - failure is the assertion
            raise AssertionError(f"formal-only resume generated candidate {request.candidate_index}")

    preparation = CharacterCardPreparationService(
        generator=_MustNotGenerate(),
        reviewer=_BodyReviewer(),
    )
    result = preparation.resume_body_silhouette_formal_only(
        resumed_card,
        slot_key="body.front_full",
        body_refresh_attempt_identity=attempt,
        prior_reviewed_candidates={
            ("body.front_full", index): attempt_value
            for index, attempt_value in enumerate(front_attempts, start=1)
        },
        consent_provenance_id="server-consent-reference",
    )

    assert result.status == "blocked"
    assert set(result.formal_slot_receipts) == {"body.front_full"}
    assert result.card.body_silhouette_refresh_slots["body.front_full"].formal_slot_receipt is not None
    state = store.record_formal_receipt(
        state,
        formal_receipt=result.formal_slot_receipts["body.front_full"],
    )
    assert state.next_slot_key == "body.side_full"
    assert state.next_candidate_index == 1


def test_library_formal_only_resume_reconstitutes_front_and_advances_cursor(
    tmp_path: Path,
) -> None:
    lifecycle, host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=[
            str(asset.character_card.face_slots[key].output_id or "")
            for key in ("face.front", "face.profile", "face.rear_head")
        ],
    )
    store = BodyRefreshAttemptStateStore(tmp_path / "library-formal-only-state")
    state = store.begin(
        visual_asset_id=asset.visual_asset_id,
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    )
    records_by_operation: dict[str, object] = {}
    candidates_by_job: dict[str, tuple[object, object]] = {}
    for index in (1, 2, 3):
        operation_id = (
            f"{asset.visual_asset_id}:body_silhouette:body.front_full:{index}:refresh_attempt_"
            f"{hashlib.sha256(attempt.attempt_id.encode()).hexdigest()[:16]}"
        )
        output_id = f"v3_output_library_front_{index}"
        candidate = CharacterCardCandidateResult(
            candidate_id=f"candidate_library_front_{index}",
            output_id=output_id,
            module="body_silhouette",
            slot_key="body.front_full",
            candidate_index=index,
            operation_id=operation_id,
            source_candidate_ids=[f"source_library_front_{index}"],
            source_output_ids=list(admission.face_reference_output_ids),
            canonical_prompt_hash="c" * 64,
            prompt_compilation_id=f"compilation_library_front_{index}",
            prompt_reference_parity_verified=True,
        )
        review = _BodyReviewer().review(candidate)
        job_id = f"job_library_front_{index}"
        records_by_operation[operation_id] = SimpleNamespace(
            job_id=job_id,
            generation_result=SimpleNamespace(),
            request=SimpleNamespace(
                metadata={
                    "professional_body_refresh_analysis_context": context.safe_metadata(),
                    "professional_character_card_body_source_admission": admission.model_dump(mode="json"),
                    "professional_character_card_candidate_index": index,
                    "professional_character_card_candidate_count": 3,
                    "professional_character_card_attempt_round": 1,
                    "professional_character_card_body_refresh_source_mode": "reference_assisted",
                    "professional_character_card_body_refresh_target_age_scope": "age_6_child_only",
                    "professional_character_card_body_model_context": "similar_person_body_reference_assisted_v1",
                    "mcp_operation_id": operation_id,
                }
            ),
        )
        candidates_by_job[job_id] = (candidate, review)
        state = store.checkpoint_reviewed_candidate(
            state,
            slot_key="body.front_full",
            candidate_index=index,
            attempt_round=1,
            candidate_digest=hashlib.sha256(output_id.encode()).hexdigest(),
            review_status="pass",
            review_receipt_digest=(
                CharacterCardPreparationService.body_refresh_review_receipt_digest(
                    candidate,
                    review,
                )
            ),
            operation_id=operation_id,
            output_id=output_id,
        )
    assert state.status == "awaiting_slot_acceptance"

    card = asset.character_card.model_copy(
        update={
            "body_silhouette_refresh_status": "blocked",
            "body_silhouette_refresh_version_id": attempt.attempt_id,
            "body_silhouette_refresh_slots": {},
        }
    )
    lifecycle.catalog.save(asset.model_copy(update={"character_card": card}))
    host._mcp_resume_character_card_stage_job_record = (  # noqa: SLF001
        lambda _request, operation_id: records_by_operation.get(operation_id)
    )
    host._character_card_candidate_and_review = (  # noqa: SLF001
        lambda job_id, _request, **_kwargs: candidates_by_job[job_id]
    )
    resumed_lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=store,
    )
    resumed = resumed_lifecycle.resume_character_card_body_silhouette(
        owner_scope="owner",
        visual_asset_id=asset.visual_asset_id,
        body_request=BodySilhouettePublicRequest(
            source_class="observed",
            target_age_scope="age_6_child_only",
            body_reference_asset_id=body_asset_ids[0],
            body_reference_asset_ids=body_asset_ids,
        ),
        generation_channel="mcp",
    )

    assert resumed.character_card.body_silhouette_refresh_slots["body.front_full"].formal_slot_receipt is not None
    updated_state = store.load_current(visual_asset_id=asset.visual_asset_id)
    assert updated_state.next_slot_key == "body.side_full"
    assert updated_state.next_candidate_index == 1


def test_library_full_review_projects_cross_view_parity_to_pending_refresh(
    tmp_path: Path,
) -> None:
    lifecycle, host, service, body_asset_ids, analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    store = BodyRefreshAttemptStateStore(tmp_path / "full-review-state")
    lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=store,
    )
    result = lifecycle.refresh_character_card_body_silhouette(
        owner_scope="owner",
        visual_asset_id=asset.visual_asset_id,
        body_request=BodySilhouettePublicRequest(
            source_class="observed",
            target_age_scope="age_6_child_only",
            body_reference_asset_id=body_asset_ids[0],
            body_reference_asset_ids=body_asset_ids,
        ),
        generation_channel="mcp",
    )

    assert result.character_card.body_silhouette_refresh_status == "reviewing"
    state = store.load_current(visual_asset_id=asset.visual_asset_id)
    assert state.status == "pending_refresh"
    assert state.cross_view_parity_digest is not None
    assert state.analyzer_call_count == 1
    assert len(analyzer.calls) == 1
    assert len(host.generator.requests) == 9
    assert len({(request.slot_key, request.candidate_index) for request in host.generator.requests}) == 9
    assert host._body_refresh_candidate_checkpoint_callback is None  # noqa: SLF001
    assert host._body_refresh_formal_receipt_callback is None  # noqa: SLF001


def test_library_activate_pending_body_refresh_promotes_formal_winners_without_generation(
    tmp_path: Path,
) -> None:
    lifecycle, host, service, body_asset_ids, analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    store = BodyRefreshAttemptStateStore(tmp_path / "activate-refresh-state")
    lifecycle.catalog.save(
        asset.model_copy(
            update={
                "character_card": asset.character_card.model_copy(
                    update={"body_activation_confirmed": False}
                )
            }
        )
    )
    lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=store,
    )
    request = BodySilhouettePublicRequest(
        source_class="observed",
        target_age_scope="age_6_child_only",
        body_reference_asset_id=body_asset_ids[0],
        body_reference_asset_ids=body_asset_ids,
    )
    refreshed = lifecycle.refresh_character_card_body_silhouette(
        owner_scope="owner",
        visual_asset_id=asset.visual_asset_id,
        body_request=request,
        generation_channel="mcp",
    )
    pending_state = store.load_current(visual_asset_id=asset.visual_asset_id)
    pending_version = refreshed.character_card.body_silhouette_refresh_version_id
    pending_winners = {
        slot_key: slot.output_id
        for slot_key, slot in refreshed.character_card.body_silhouette_refresh_slots.items()
    }
    generated_request_count = len(host.generator.requests)

    activated = lifecycle.activate_character_card_module(
        owner_scope="owner",
        visual_asset_id=asset.visual_asset_id,
        module="body_silhouette",
        confirm_activation=True,
    )

    assert pending_state.status == "pending_refresh"
    assert activated.character_card.body_silhouette_status == "active"
    assert activated.character_card.body_activation_confirmed is True
    assert activated.character_card.body_silhouette_version_id == pending_version
    assert activated.character_card.active_version_id == pending_version
    assert activated.character_card.body_silhouette_refresh_status == "empty"
    assert activated.character_card.body_silhouette_refresh_version_id is None
    assert activated.character_card.body_silhouette_refresh_slots == {}
    assert {
        slot_key: slot.output_id
        for slot_key, slot in activated.character_card.body_slots.items()
    } == pending_winners
    assert all(slot.state == "active" for slot in activated.character_card.body_slots.values())
    assert all(
        slot.formal_slot_receipt is not None and slot.formal_slot_receipt.activation_eligible
        for slot in activated.character_card.body_slots.values()
    )
    activated_state = store.load_current(visual_asset_id=asset.visual_asset_id)
    assert activated_state.status == "activated"
    assert activated_state.activation_digest is not None
    assert activated_state.cross_view_parity_digest == pending_state.cross_view_parity_digest
    assert len(host.generator.requests) == generated_request_count
    assert len(analyzer.calls) == 1


def test_library_activation_rejects_refresh_slot_drift_after_cross_view_receipt(
    tmp_path: Path,
) -> None:
    lifecycle, host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    store = BodyRefreshAttemptStateStore(tmp_path / "drift-refresh-state")
    lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=store,
    )
    refreshed = lifecycle.refresh_character_card_body_silhouette(
        owner_scope="owner",
        visual_asset_id=asset.visual_asset_id,
        body_request=BodySilhouettePublicRequest(
            source_class="observed",
            target_age_scope="age_6_child_only",
            body_reference_asset_id=body_asset_ids[0],
            body_reference_asset_ids=body_asset_ids,
        ),
        generation_channel="mcp",
    )
    state = store.load_current(visual_asset_id=asset.visual_asset_id)
    assert state.status == "pending_refresh"

    slots = dict(refreshed.character_card.body_silhouette_refresh_slots)
    front_slot = slots["body.front_full"]
    front_receipt = FormalSlotReceipt.model_validate(front_slot.formal_slot_receipt)
    alternate = next(
        candidate for candidate in front_receipt.candidates if candidate.candidate_index == 2
    )
    drifted_candidates = [
        candidate.model_copy(
            update={"selected_as_winner": candidate.candidate_id == alternate.candidate_id}
        )
        for candidate in front_receipt.candidates
    ]
    drifted_receipt = FormalSlotReceipt.model_validate(
        front_receipt.model_copy(
            update={
                "candidates": drifted_candidates,
                "winner_candidate_id": alternate.candidate_id,
                "winner_output_id": alternate.output_id,
                "winner_shared_review": alternate.shared_review,
            }
        ).model_dump(mode="python")
    )
    slots["body.front_full"] = front_slot.model_copy(
        update={
            "output_id": alternate.output_id,
            "formal_slot_receipt": drifted_receipt,
        }
    )
    lifecycle.catalog.save(
        refreshed.model_copy(
            update={
                "character_card": refreshed.character_card.model_copy(
                    update={"body_silhouette_refresh_slots": slots}
                )
            }
        )
    )

    with pytest.raises(BodyRefreshAttemptStateError, match="cross-view receipt output mismatch"):
        lifecycle.activate_character_card_module(
            owner_scope="owner",
            visual_asset_id=asset.visual_asset_id,
            module="body_silhouette",
            confirm_activation=True,
        )


def test_library_cross_view_failure_does_not_project_pending_refresh(tmp_path: Path) -> None:
    lifecycle, host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    store = BodyRefreshAttemptStateStore(tmp_path / "cross-view-failure-state")
    lifecycle = VisualAssetLibraryLifecycleService(
        lifecycle.catalog,
        root_source_resolver=service.get_uploaded_asset,
        character_card_stage_host=host,
        body_refresh_attempt_state_store=store,
    )

    host.preparation.reviewer = _BodyReviewer(cross_view_mismatch_slots={"body.side_full"})

    result = lifecycle.refresh_character_card_body_silhouette(
        owner_scope="owner",
        visual_asset_id=asset.visual_asset_id,
        body_request=BodySilhouettePublicRequest(
            source_class="observed",
            target_age_scope="age_6_child_only",
            body_reference_asset_id=body_asset_ids[0],
            body_reference_asset_ids=body_asset_ids,
        ),
        generation_channel="mcp",
    )

    assert result.character_card.body_silhouette_refresh_status == "blocked"
    state = store.load_current(visual_asset_id=asset.visual_asset_id)
    assert state.status == "awaiting_cross_view"
    assert state.cross_view_parity_digest is None


def test_reference_assisted_refresh_uses_stage_cross_view_parity_after_three_formal_slots() -> None:
    class _SingleViewBodyReviewer:
        def review(self, candidate: CharacterCardCandidateResult):
            return _review(
                candidate.candidate_index,
                include_cross_view_parity_evidence=False,
            )

    body_asset_ids = [f"body-source-{index}" for index in range(5)]
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    service = CharacterCardPreparationService(
        generator=_BodyGenerator(),
        reviewer=_SingleViewBodyReviewer(),
    )

    result = service.refresh_body_silhouette(
        _active_body_card(),
        face_reference_output_ids=[
            "face_front_output",
            "face_profile_output",
            "face_rear_output",
        ],
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        consent_provenance_id="server-consent-reference",
        user_intent="reference-assisted body refresh with frozen morphology profile",
        generation_channel="mcp",
        body_refresh_analysis_context=context,
        body_refresh_attempt_identity=attempt,
    )

    assert result.status == "review"
    assert set(result.formal_slot_receipts) == set(BODY_SLOT_KEYS)
    assert result.failure_codes == []
    assert result.card.body_silhouette_refresh_status == "reviewing"


def test_formal_authority_rejects_status_only_reconstituted_review() -> None:
    status_only_attempt = _body_attempt(1, review=SimpleNamespace(status="pass"))
    proof = CharacterCardPreparationService._formal_body_enhanced_proof(  # noqa: SLF001
        slot_key="body.front_full",
        attempt=status_only_attempt,
    )
    assert proof.status == "fail"
    assert "body_shared_review_receipt_missing" in proof.issue_codes


def test_nine_candidate_cursor_reaches_three_formal_receipts_and_pending_refresh(
    tmp_path: Path,
) -> None:
    store, state, _context = _start_state(tmp_path)
    operation_ids: list[str] = []
    output_ids: list[str] = []
    for slot_key in ("body.front_full", "body.side_full", "body.rear_full"):
        for index in (1, 2, 3):
            operation_id = f"visual-card-01:body_silhouette:{slot_key}:{index}:refresh_attempt_0000000000000000"
            output_id = f"v3_output_{slot_key.replace('.', '_')}_{index}"
            operation_ids.append(operation_id)
            output_ids.append(output_id)
            state = store.checkpoint_reviewed_candidate(
                state,
                slot_key=slot_key,
                candidate_index=index,
                attempt_round=1,
                candidate_digest=hashlib.sha256(output_id.encode()).hexdigest(),
                review_status="pass",
                review_receipt_digest=hashlib.sha256(f"{output_id}\0pass".encode()).hexdigest(),
                operation_id=operation_id,
                output_id=output_id,
            )
        formal_receipt = CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
            slot_key=slot_key,
            attempts=[
                _body_attempt(index, slot_key=slot_key)
                for index in (1, 2, 3)
            ],
        )
        state = store.record_formal_receipt(state, formal_receipt=formal_receipt)
    assert state.status == "awaiting_cross_view"
    assert state.next_slot_key is None
    assert state.next_candidate_index is None
    assert len(state.formal_receipt_digests) == 3
    assert state.analyzer_call_count == 1
    assert len(state.candidate_checkpoints) == 9
    assert len(set(operation_ids)) == 9
    assert len(set(output_ids)) == 9

    state = store.record_cross_view_review(
        state,
        receipt=build_body_cross_view_review_receipt(
            attempt_id=state.attempt_identity.attempt_id,
            source_evidence_id_digest=state.body_source_admission.source_evidence_id_digest(),
            view_output_ids={
                "body.front_full": "v3_output_body_front_full_3",
                "body.side_full": "v3_output_body_side_full_3",
                "body.rear_full": "v3_output_body_rear_full_3",
            },
            status="pass",
            dimensions={dimension: "pass" for dimension in BODY_CROSS_VIEW_DIMENSIONS},
            evidence_codes=[
                BODY_CROSS_VIEW_PIXEL_EVIDENCE_CODE,
                *BODY_CROSS_VIEW_DIMENSION_EVIDENCE_CODES.values(),
            ],
            issue_codes=[],
            real_pixel_review_verified=True,
        ),
    )
    assert state.status == "pending_refresh"
    assert state.cross_view_parity_digest is not None


@pytest.mark.parametrize(
    ("tamper", "expected"),
    [
        ("missing", "body_refresh_prior_candidate_record_missing"),
        ("output", "body_refresh_prior_candidate_output_mismatch"),
        ("review", "body_refresh_prior_candidate_review_missing"),
        ("receipt", "body_refresh_prior_candidate_review_receipt_mismatch"),
    ],
)
def test_new_host_reconstitution_missing_or_tampered_job_output_fails_closed(
    tmp_path: Path,
    tamper: str,
    expected: str,
) -> None:
    lifecycle, _old_host, service, body_asset_ids, _analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))  # noqa: SLF001
    attempt, context = _context_for_body_asset_ids(body_asset_ids)
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=body_asset_ids,
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=[
            str(asset.character_card.face_slots[key].output_id or "")
            for key in ("face.front", "face.profile", "face.rear_head")
        ],
    )
    state_store = BodyRefreshAttemptStateStore(tmp_path / "state")
    state = state_store.begin(
        visual_asset_id=asset.visual_asset_id,
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=admission,
    )
    operation_id = (
        f"{asset.visual_asset_id}:body_silhouette:body.front_full:1:refresh_attempt_"
        f"{hashlib.sha256(attempt.attempt_id.encode()).hexdigest()[:16]}"
    )
    output_id = "v3_output_body_front_1"
    state = _private_front_checkpoint(
        state_store,
        state,
        operation_id=operation_id,
        output_id=output_id,
        review_receipt_digest=hashlib.sha256(f"{output_id}\0pass".encode()).hexdigest(),
    )
    checkpoint = state.candidate_checkpoints[0]
    fresh_host = ProductApiAnchorPackPreparationHost(service)
    if tamper == "missing":
        fresh_host._mcp_resume_character_card_stage_job_record = lambda *_args: None  # noqa: SLF001
    else:
        record = SimpleNamespace(
            job_id="job_body_front_1",
            generation_result=SimpleNamespace(),
            request=SimpleNamespace(
                    metadata={
                        "professional_body_refresh_analysis_context": context.safe_metadata(),
                        "professional_character_card_body_source_admission": admission.model_dump(mode="json"),
                        "professional_character_card_candidate_index": 1,
                        "professional_character_card_candidate_count": 3,
                        "professional_character_card_attempt_round": 1,
                        "professional_character_card_body_refresh_source_mode": "reference_assisted",
                        "professional_character_card_body_refresh_target_age_scope": "age_6_child_only",
                        "professional_character_card_body_model_context": "similar_person_body_reference_assisted_v1",
                        "mcp_operation_id": operation_id,
                    }
            ),
        )
        wrong_candidate = CharacterCardCandidateResult(
            candidate_id="candidate_body_front_1",
            output_id=output_id if tamper == "receipt" else "v3_output_tampered",
            module="body_silhouette",
            slot_key="body.front_full",
            candidate_index=1,
            operation_id=operation_id,
            source_candidate_ids=["source_body_front_1"],
            source_output_ids=list(admission.face_reference_output_ids),
            canonical_prompt_hash="b" * 64,
            prompt_compilation_id="compilation_front_1",
            prompt_reference_parity_verified=True,
        )
        fresh_host._mcp_resume_character_card_stage_job_record = lambda *_args: record  # noqa: SLF001
        if tamper == "review":
            def missing_review(*_args, **_kwargs):
                raise CharacterCardRuntimeUnavailable("body_refresh_prior_candidate_review_missing")

            fresh_host._character_card_candidate_and_review = missing_review  # noqa: SLF001
        elif tamper == "receipt":
            fresh_host._character_card_candidate_and_review = lambda *_args, **_kwargs: (
                wrong_candidate,
                _BodyReviewer().review(wrong_candidate),
            )
        else:
            fresh_host._character_card_candidate_and_review = lambda *_args, **_kwargs: (
                wrong_candidate,
                SimpleNamespace(status="pass"),
            )  # noqa: SLF001
    with pytest.raises(CharacterCardRuntimeUnavailable, match=expected):
        fresh_host.resume_body_silhouette(
            asset=asset,
            card=asset.character_card,
            request=BodySilhouettePublicRequest(
                source_class="observed",
                target_age_scope="age_6_child_only",
                body_reference_asset_id=body_asset_ids[0],
                body_reference_asset_ids=body_asset_ids,
            ),
            generation_channel="mcp",
            body_refresh_analysis_context=context,
            body_source_admission=admission,
            body_refresh_attempt_identity=attempt,
            resume_slot_key=state.next_slot_key,
            resume_candidate_index=state.next_candidate_index,
            prior_reviewed_candidate_checkpoints=[checkpoint],
        )


def test_failed_review_is_checkpointed_and_resume_starts_candidate_two(tmp_path: Path) -> None:
    store, state, context = _start_state(tmp_path)
    updated = store.checkpoint_reviewed_candidate(
        state,
        slot_key="body.front_full",
        candidate_index=1,
        candidate_digest="a" * 64,
        attempt_round=1,
        review_status="fail",
        review_receipt_digest="b" * 64,
        operation_id="visual-card-01:body_silhouette:body.front_full:1:refresh_attempt_0000000000000000",
        output_id="v3_output_front_1",
    )
    assert updated.next_slot_key == "body.front_full"
    assert updated.next_candidate_index == 2
    assert updated.status == "interrupted"
    assert updated.candidate_checkpoints[0].review_status == "fail"
    assert updated.analysis_context.profile_digest == context.profile_digest


def test_candidate_three_waits_for_typed_formal_receipt_before_next_slot(tmp_path: Path) -> None:
    store, state, _context_value = _start_state(tmp_path)
    for index in (1, 2, 3):
        state = store.checkpoint_reviewed_candidate(
            state,
            slot_key="body.front_full",
            candidate_index=index,
            candidate_digest=f"{index}" * 64,
            attempt_round=1,
            review_status="pass",
            review_receipt_digest=f"{index + 3}" * 64,
            operation_id=f"visual-card-01:body_silhouette:body.front_full:{index}:refresh_attempt_0000000000000000",
            output_id=f"v3_output_front_{index}",
        )
    assert state.status == "awaiting_slot_acceptance"
    assert state.next_slot_key == "body.front_full"
    assert state.next_candidate_index is None

    formal_receipt = CharacterCardPreparationService._formal_body_slot_receipt(  # noqa: SLF001
        slot_key="body.front_full",
        attempts=[_body_attempt(index) for index in (1, 2, 3)],
    )
    state = store.record_formal_receipt(state, formal_receipt=formal_receipt)
    assert state.status == "interrupted"
    assert state.next_slot_key == "body.side_full"
    assert state.next_candidate_index == 1
    restarted_store = BodyRefreshAttemptStateStore(tmp_path / "state")
    assert restarted_store.load(
        visual_asset_id="visual-card-01",
        attempt_id=state.attempt_identity.attempt_id,
    ).next_slot_key == "body.side_full"
