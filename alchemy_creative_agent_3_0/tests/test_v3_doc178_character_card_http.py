"""HTTP and production-host fail-closed contracts for Doc178."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    BodySilhouettePublicRequest,
    CharacterCardPreparationService,
    CharacterCardRuntimeUnavailable,
    CharacterCardSharedRuntimeReceipt,
    CharacterCardStageResult,
    CharacterCardState,
    CharacterCardSlot,
)
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
    def _receipt() -> CharacterCardSharedRuntimeReceipt:
        return CharacterCardSharedRuntimeReceipt(
            final_winner_selection_verified=True,
            prompt_reference_parity_verified=True,
        )

    def prepare_expression_set(self, *, asset, card):
        return CharacterCardStageResult(
            status="review",
            card=card.model_copy(update={"expression_set_status": "reviewing"}),
            shared_runtime_receipt=self._receipt(),
        )

    def prepare_body_silhouette(self, *, asset, card, request=None):
        self.body_request = request
        return CharacterCardStageResult(
            status="review",
            card=card.model_copy(update={"body_silhouette_status": "reviewing"}),
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
