"""HTTP and production-host fail-closed contracts for Doc178."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.expression_review import (
    EXPRESSION_FRAMING_DELTA_MAX,
    LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES,
    project_laugh_expression_review_receipt,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    BodySilhouettePublicRequest,
    CharacterCardCandidateAttempt,
    CharacterCardCandidateRequest,
    CharacterCardCandidateResult,
    CharacterCardPreparationService,
    CharacterCardRuntimeUnavailable,
    CharacterCardSharedRuntimeReceipt,
    CharacterCardStageResult,
    CharacterCardState,
    CharacterCardSlot,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import AnchorPackPreparationResult, AnchorReviewDecision
from alchemy_creative_agent_3_0.app.visual_assets.contracts import IdentityAnchorPackVersion, IdentityScoreSummary, RootSourceProvenance
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    LibraryRootSourceProvenance,
    LibraryVisualAssetCreateRequest,
    PersistentVisualAssetLibraryCatalog,
    VisualAssetLibraryCatalog,
    VisualAssetLibraryLifecycleService,
)


def _catalog_asset(catalog: VisualAssetLibraryCatalog):
    return catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Character Card test asset",
            root_source_asset_id="root_upload",
            consent_reference="root-consent",
            preparation_intent="user-authored character intent",
        ),
    )


def test_doc178_http_routes_are_registered_as_real_fastapi_routes() -> None:
    from app import main as app_main

    paths = {route.path for route in app_main.app.routes if hasattr(route, "path")}
    assert "/api/v3/creative-agent/visual-assets/{visual_asset_id}/character-card/prepare" in paths
    assert "/api/v3/creative-agent/visual-assets/{visual_asset_id}/character-card/activate" in paths


def test_doc178_http_prepare_without_shared_host_returns_safe_unavailable(monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from app import main as app_main

    monkeypatch.setattr(app_main.settings, "veyra_auth_enabled", False)
    catalog = VisualAssetLibraryCatalog()
    asset = _catalog_asset(catalog)
    monkeypatch.setattr(
        app_main,
        "v3_route_handlers",
        V3ProductRouteHandlers(
            service=V3ProductApiService(),
            visual_asset_library_catalog=catalog,
        ),
    )
    response = TestClient(app_main.app).post(
        f"/api/v3/creative-agent/visual-assets/{asset.visual_asset_id}/character-card/prepare",
        json={"stage": "face_identity"},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "character_card_shared_runtime_unavailable"
    assert "provider" not in response.text.lower()


def test_doc178_offline_generator_reviewer_cannot_be_a_production_stage_host() -> None:
    catalog = VisualAssetLibraryCatalog()
    _catalog_asset(catalog)
    lifecycle = VisualAssetLibraryLifecycleService(
        catalog,
        character_card_stage_host=CharacterCardPreparationService(generator=None, reviewer=None),
    )

    with pytest.raises(CharacterCardRuntimeUnavailable, match="shared_runtime_required"):
        lifecycle.prepare_character_card_stage(
            owner_scope="local_default",
            visual_asset_id="visual_asset_missing_host_marker",
            stage="expression_set",
        )


def test_doc178_body_public_contract_distinguishes_observed_description_and_brain() -> None:
    observed = BodySilhouettePublicRequest(
        source_class="observed", body_reference_asset_id="upload_full_body"
    )
    described = BodySilhouettePublicRequest(
        source_class="user_described", body_facts="约一米二，普通儿童体态"
    )
    inferred = BodySilhouettePublicRequest(source_class="brain_inferred")
    assert observed.body_reference_asset_id == "upload_full_body"
    assert described.body_facts and inferred.body_facts is None
    with pytest.raises(ValueError):
        BodySilhouettePublicRequest(source_class="observed", body_reference_asset_id="C:\\secret.png")
    with pytest.raises(ValueError):
        BodySilhouettePublicRequest(source_class="user_described", body_facts="", body_reference_asset_id=None)
    with pytest.raises(ValueError):
        BodySilhouettePublicRequest(source_class="brain_inferred", body_facts="a body recipe")


class _SharedStageHost:
    production_shared_runtime = True

    def __init__(self) -> None:
        self.body_request = None

    @staticmethod
    def _laugh_review_receipt() -> dict[str, object]:
        score_card = {
            "mouth_eye_coherence": 0.9,
            "gaze_engagement": 0.88,
            "periocular_affect": 0.86,
            "cheek_jaw_coupling": 0.87,
            "jaw_relaxation": 0.82,
            "arousal_intensity_coherence": 0.86,
            "spontaneity_asymmetry": 0.76,
            "expression_age_coherence": 0.86,
            "expression_identity_preservation": 0.88,
            "expression_framing_parity": 0.91,
        }
        for dimension in EXPRESSION_FRAMING_DELTA_MAX:
            score_card[dimension] = 0.01
        return project_laugh_expression_review_receipt(
            score_card=score_card,
            issue_codes=[],
        ).to_public_dict()

    @classmethod
    def _shared_review_receipt(cls, *, slot_key: str = "") -> dict[str, object]:
        if slot_key == "expression.laugh":
            return cls._laugh_review_receipt()
        return {
            "owner": "v3_shared_visual_cluster",
            "contract_version": "v3_character_card_generic_slot_review_receipt_v1",
            "status": "pass",
            "evidence_codes": ["shared_visual_review_verified"],
            "issue_codes": [],
            "score_dimensions": ["identity_fidelity", "visual_quality"],
            "framing_delta_dimensions": [],
        }

    @classmethod
    def _receipt(cls, *, slot_key: str = "") -> CharacterCardSharedRuntimeReceipt:
        return CharacterCardSharedRuntimeReceipt(
            final_winner_selection_verified=True,
            prompt_reference_parity_verified=True,
            shared_review_receipts=[cls._shared_review_receipt(slot_key=slot_key)],
        )

    @classmethod
    def _attempt(cls, *, slot_key: str, output_id: str, module: str = "body_silhouette") -> CharacterCardCandidateAttempt:
        request = CharacterCardCandidateRequest(
            project_id="project_doc178",
            people_asset_id="people_doc178",
            card_version_id="card_ready",
            module=module,  # type: ignore[arg-type]
            slot_key=slot_key,  # type: ignore[arg-type]
            candidate_index=1,
            reference_output_ids=["front", "profile", "rear"]
            if module == "body_silhouette"
            else ["front_winner"],
            user_intent="shared-runtime-owned test intent",
            source_class="observed" if module == "body_silhouette" else None,
            consent_provenance_id="body-consent" if module == "body_silhouette" else None,
        )
        candidate = CharacterCardCandidateResult(
            candidate_id=f"candidate_{slot_key}",
            output_id=output_id,
            module=module,  # type: ignore[arg-type]
            slot_key=slot_key,
            candidate_index=1,
            source_candidate_ids=[f"candidate_{slot_key}"],
            source_output_ids=list(request.reference_output_ids),
            canonical_prompt_hash=f"sha256:{slot_key}",
            prompt_compilation_id=f"compile_{slot_key}",
            prompt_reference_parity_verified=True,
        )
        review = AnchorReviewDecision(
            status="pass",
            identity_scores=IdentityScoreSummary(
                same_face_score=0.9,
                distinctive_feature_score=0.9,
                human_realism_score=0.9,
                visual_quality_score=0.9,
                evidence_codes=sorted(LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES)
                if slot_key == "expression.laugh"
                else ["shared_visual_review_verified"],
            ),
            shared_review_receipts=[cls._shared_review_receipt(slot_key=slot_key)],
        )
        return CharacterCardCandidateAttempt(request=request, candidate=candidate, review=review)

    def prepare_expression_set(self, *, asset, card):
        output_id = "expression_laugh_doc178"
        laugh_slot = CharacterCardSlot(
            slot_key="expression.laugh",
            module="expression_set",
            state="winner_selected",
            output_id=output_id,
            source_candidate_ids=["candidate_expression_laugh"],
            lineage_id="lineage_expression_laugh",
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
        )
        return CharacterCardStageResult(
            status="review",
            card=card.model_copy(
                update={
                    "expression_set_status": "partial",
                    "expression_slots": {**card.expression_slots, "expression.laugh": laugh_slot},
                }
            ),
            attempts=[
                self._attempt(
                    slot_key="expression.laugh",
                    output_id=output_id,
                    module="expression_set",
                )
            ],
            winner_output_ids={"expression.laugh": output_id},
            shared_runtime_receipt=self._receipt(slot_key="expression.laugh"),
        )

    def prepare_body_silhouette(self, *, asset, card, request=None):
        self.body_request = request
        output_id = "body_front_doc178"
        body_slot = CharacterCardSlot(
            slot_key="body.front_full",
            module="body_silhouette",
            state="winner_selected",
            output_id=output_id,
            source_candidate_ids=["candidate_body_front"],
            source_class="observed",
            consent_provenance_id="body-consent",
            lineage_id="lineage_body_front",
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
        )
        return CharacterCardStageResult(
            status="review",
            card=card.model_copy(
                update={
                    "body_silhouette_status": "reviewing",
                    "body_slots": {**card.body_slots, "body.front_full": body_slot},
                }
            ),
            attempts=[self._attempt(slot_key="body.front_full", output_id=output_id)],
            winner_output_ids={"body.front_full": output_id},
            shared_runtime_receipt=self._receipt(),
        )


def test_doc178_shared_host_receipt_is_required_and_body_source_is_resolved_server_side() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = _catalog_asset(catalog)
    source = SimpleNamespace(
        status="ready",
        role="full_body_reference",
        metadata={"consent_reference": "body-consent"},
    )
    host = _SharedStageHost()
    lifecycle = VisualAssetLibraryLifecycleService(
        catalog,
        root_source_resolver=lambda asset_id: source if asset_id == "body_upload" else None,
        character_card_stage_host=host,
    )
    ready = asset.model_copy(
        update={
            "character_card": CharacterCardState.initial(card_version_id="card_ready").model_copy(
                update={"face_identity_status": "active", "expression_set_status": "active"}
            )
        }
    )
    catalog.save(ready)
    result = lifecycle.prepare_character_card_stage(
        owner_scope="local_default",
        visual_asset_id=asset.visual_asset_id,
        stage="body_silhouette",
        body_request=BodySilhouettePublicRequest(
            source_class="observed", body_reference_asset_id="body_upload"
        ),
    )
    assert result.character_card.body_silhouette_status == "reviewing"
    assert host.body_request.source_class == "observed"
    assert host.body_request.body_reference_asset_id == "body_upload"


def test_doc178_character_card_state_survives_catalog_reopen(tmp_path) -> None:
    catalog = PersistentVisualAssetLibraryCatalog(tmp_path)
    asset = _catalog_asset(catalog)
    persisted = asset.model_copy(
        update={
            "character_card": asset.character_card.model_copy(
                update={"face_identity_status": "reviewing", "append_only_revision": 2}
            )
        }
    )
    catalog.save(persisted)

    reopened = PersistentVisualAssetLibraryCatalog(tmp_path)
    restored = reopened.get(owner_scope="local_default", visual_asset_id=asset.visual_asset_id)
    assert restored is not None
    assert restored.character_card.face_identity_status == "reviewing"
    assert restored.character_card.append_only_revision == 2


def test_doc178_route_handler_rejects_expression_payload_and_no_host_is_safe() -> None:
    handlers = V3ProductRouteHandlers(service=V3ProductApiService())
    with pytest.raises(ValueError, match="stage_payload"):
        handlers.post_visual_asset_character_card_prepare(
            "asset_1", {"stage": "expression_set", "expression_intent": "smile"}
        )
    with pytest.raises(CharacterCardRuntimeUnavailable, match="unavailable"):
        handlers.post_visual_asset_character_card_prepare("asset_1", {"stage": "face_identity"})


def test_doc230_route_handler_accepts_explicit_laugh_single_slot_payload() -> None:
    captured = {}

    class _Lifecycle:
        def prepare_character_card_stage(self, **kwargs):
            captured.update(kwargs)
            return _catalog_asset(VisualAssetLibraryCatalog())

    handlers = V3ProductRouteHandlers(service=V3ProductApiService())
    handlers.visual_asset_library_service = _Lifecycle()

    handlers.post_visual_asset_character_card_prepare(
        "asset_laugh",
        {"stage": "expression_set", "generation_channel": "mcp", "expression": "laugh"},
    )

    assert captured["visual_asset_id"] == "asset_laugh"
    assert captured["stage"] == "expression_set"
    assert captured["expression"] == "laugh"
    assert captured["generation_channel"] == "mcp"


def test_doc202_route_accepts_only_confirmed_failed_slot_retry_without_prompt_injection() -> None:
    captured = {}

    class _Lifecycle:
        def prepare_character_card_stage(self, **kwargs):
            captured.update(kwargs)
            return _catalog_asset(VisualAssetLibraryCatalog())

    handlers = V3ProductRouteHandlers(service=V3ProductApiService())
    handlers.visual_asset_library_service = _Lifecycle()

    with pytest.raises(ValueError, match="failed_slot_retry_flag"):
        handlers.post_visual_asset_character_card_prepare(
            "asset_retry",
            {"stage": "expression_set", "generation_channel": "mcp", "confirm_retry": True},
        )
    with pytest.raises(ValueError, match="stage_payload"):
        handlers.post_visual_asset_character_card_prepare(
            "asset_retry",
            {
                "stage": "expression_set",
                "generation_channel": "mcp",
                "retry_failed_slot": True,
                "confirm_retry": True,
                "expression_prompt": "force this candidate through",
            },
        )
    with pytest.raises(ValueError, match="uses_persisted_slot"):
        handlers.post_visual_asset_character_card_prepare(
            "asset_retry",
            {
                "stage": "expression_set",
                "generation_channel": "mcp",
                "expression": "smile",
                "retry_failed_slot": True,
                "confirm_retry": True,
            },
        )

    payload = handlers.post_visual_asset_character_card_prepare(
        "asset_retry",
        {
            "stage": "expression_set",
            "generation_channel": "mcp",
            "retry_failed_slot": True,
            "confirm_retry": True,
        },
    )

    assert captured["visual_asset_id"] == "asset_retry"
    assert captured["stage"] == "expression_set"
    assert captured["generation_channel"] == "mcp"
    assert captured["retry_failed_slot"] is True
    assert captured["confirm_retry"] is True
    assert "expression" not in captured or captured["expression"] is None
    assert payload["visual_asset"]["visual_asset_id"]


def test_doc180_character_card_activate_route_accepts_face_identity_module() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = _catalog_asset(catalog)
    captured = {}

    class _Lifecycle:
        def activate_character_card_face(self, **kwargs):
            captured.update(kwargs)
            return asset

    handlers = V3ProductRouteHandlers(service=V3ProductApiService(), visual_asset_library_catalog=catalog)
    handlers.visual_asset_library_service = _Lifecycle()
    payload = handlers.post_visual_asset_character_card_activate(
        asset.visual_asset_id,
        {"module": "face_identity", "confirm_activation": True},
    )

    assert captured == {
        "owner_scope": "local_default",
        "visual_asset_id": asset.visual_asset_id,
        "confirm_activation": True,
    }
    assert payload["visual_asset"]["visual_asset_id"] == asset.visual_asset_id


def test_doc180_public_character_card_projection_exposes_only_server_owned_media_urls() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = _catalog_asset(catalog)
    card = asset.character_card
    face_slots = dict(card.face_slots)
    face_slots["face.front"] = CharacterCardSlot(
        slot_key="face.front",
        module="face_identity",
        state="winner_selected",
        output_id="output_front_1",
        review_verified=True,
        prompt_reference_parity_verified=True,
    )
    updated = asset.model_copy(
        update={
            "character_card": card.model_copy(
                update={"face_slots": face_slots, "face_identity_status": "reviewing"}
            )
        }
    )
    public = V3ProductRouteHandlers._visual_asset_public_record(updated)
    slot = public["character_card"]["slots"]["face.front"]
    assert slot["available"] is True
    assert slot["preview_url"].endswith("/outputs/output_front_1/preview")
    assert slot["download_url"].endswith("/outputs/output_front_1/download")
    assert "output_id" not in slot
    assert "prompt" not in slot
    assert "provider" not in slot


def test_doc180_face_prepare_persists_safe_failure_for_the_browser_card() -> None:
    class _UnavailableFaceHost:
        def prepare_character_card(self, *, project_id, people_asset, root_source_provenance):
            pack = IdentityAnchorPackVersion(
                pack_version_id="pack_failed",
                people_asset_id=people_asset.people_asset_id,
                status="failed",
                root_source_provenance=RootSourceProvenance(
                    source_type="uploaded_portrait",
                    source_asset_id=root_source_provenance.source_asset_id,
                    project_id=project_id,
                    consent_reference=root_source_provenance.consent_reference,
                ),
            )
            return AnchorPackPreparationResult(
                status="blocked",
                pack=pack,
                failure_codes=["remote_brain_unavailable"],
            )

    catalog = VisualAssetLibraryCatalog()
    asset = _catalog_asset(catalog)
    lifecycle = VisualAssetLibraryLifecycleService(catalog, anchor_pack_host=_UnavailableFaceHost())
    updated = lifecycle.prepare_character_card_face(owner_scope="local_default", visual_asset_id=asset.visual_asset_id)
    assert updated.lifecycle_status == "blocked"
    assert updated.versions[-1].failure_code == "remote_brain_unavailable"
    public = V3ProductRouteHandlers._visual_asset_public_record(updated)
    assert public["latest_preparation"]["failure_code"] == "remote_brain_unavailable"
