from __future__ import annotations

import json
import base64
import hashlib
from io import BytesIO

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import (
    McpMaterializationError,
    McpMaterializationHandoffStore,
    build_body_renderer_execution_receipt,
)
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
    body_silhouette_integrated_whole_person_synthesis_contract,
    body_silhouette_mcp_materialization_channel_contract,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    default_body_refresh_presentation_intent,
    default_body_silhouette_backdrop_presentation_contract,
    default_body_silhouette_garment_continuity_contract,
    default_body_silhouette_hair_continuity_contract,
)


def _partition() -> dict:
    return {
        "contract_version": "body_mcp_reference_partition_v1",
        "body_proportion_reference": {
            "role": "body_proportion_reference",
            "truth_layer": "body_proportion_truth",
            "asset_count": 5,
            "asset_hashes": [f"body-hash-{index}" for index in range(5)],
        },
        "face_identity_reference": {
            "role": "face_identity_reference",
            "truth_layer": "identity_continuity",
            "identity_continuity_only": True,
            "asset_count": 2,
            "asset_hashes": ["face-hash-0", "face-hash-1"],
        },
    }


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 48), (240, 240, 240)).save(buffer, format="PNG")
    return buffer.getvalue()


def _morphology_profile() -> dict:
    bands = {
        "relative_head_to_stature": "larger",
        "shoulder_to_head": "narrower",
        "torso_to_leg": "shorter_torso",
        "arm_to_leg": "proportional",
        "build": "slender",
        "neck_shoulder": "narrow_transition",
        "developmental_stage_context": "middle_stage_context",
        "stance_ground": "grounded_full_contact",
        "cross_view_support": "multi_view_supported",
    }
    canonical = json.dumps(bands, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    bands_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "schema_version": "body_morphology_evidence_profile_v2",
        "profile_digest": "a" * 64,
        "bands_digest": bands_digest,
        "bands": bands,
        "target_age_scope": "age_6_child_only",
    }


def _strict_contract() -> dict:
    return {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
        "size_normalization": "white_matte_contain_to_contract_size",
        "body_refresh_source_mode": "reference_assisted",
        "target_age_scope": "age_6_child_only",
        "body_silhouette_mcp_materialization_channel_contract": body_silhouette_mcp_materialization_channel_contract(),
        "body_silhouette_integrated_whole_person_synthesis_contract": (
            body_silhouette_integrated_whole_person_synthesis_contract()
        ),
        "body_mcp_reference_partition": _partition(),
        "body_morphology_profile": _morphology_profile(),
        "body_refresh_presentation_intent": default_body_refresh_presentation_intent().model_dump(mode="json"),
        "body_silhouette_garment_continuity_contract": default_body_silhouette_garment_continuity_contract(),
        "body_silhouette_hair_continuity_contract": default_body_silhouette_hair_continuity_contract(),
        "body_silhouette_backdrop_presentation_contract": default_body_silhouette_backdrop_presentation_contract(),
    }


def _ensure(
    store: McpMaterializationHandoffStore,
    contract: dict | None = None,
    *,
    require_body_rendering_contract: bool = True,
) -> dict:
    return store.ensure_pending(
        operation_id="visual_asset_renderer_contract:body_silhouette:body.front_full:1",
        prompt="Body proportion and stance only.",
        prompt_sha256="canonical-prompt-hash",
        reference_assets=[],
        rendering_contract=contract or _strict_contract(),
        require_body_rendering_contract=require_body_rendering_contract,
    )


def _renderer_execution_receipt(request: dict) -> dict:
    return build_body_renderer_execution_receipt(
        renderer_prompt_sha256=request["renderer_prompt_sha256"],
        renderer_execution_directive_sha256=request["renderer_execution_directive_sha256"],
        canonical_prompt_sha256=request["canonical_prompt_sha256"],
        rendering_contract_fingerprint=request["rendering_contract_fingerprint"],
        nonce_sha256=request["renderer_execution_directive"]["nonce_sha256"],
        reference_asset_hashes=request["reference_asset_hashes"],
    )


def test_strict_body_public_view_exposes_closed_renderer_directive_without_changing_brain_prompt_or_hash(tmp_path) -> None:
    store = McpMaterializationHandoffStore(storage_root=tmp_path / "handoffs")
    handoff = _ensure(store)

    public = store.public_view(handoff["handoff_id"])
    directive = public["renderer_execution_directive"]

    assert public["canonical_prompt"] == "Body proportion and stance only."
    assert public["prompt_sha256"] == "canonical-prompt-hash"
    assert directive["canonical_prompt_sha256"] == public["prompt_sha256"]
    assert directive["rendering_contract_fingerprint"] == public["rendering_contract_fingerprint"]
    assert directive["presentation"] == {
        "top": "short_sleeve_top",
        "bottom": "shorts",
        "footwear": "plain_white_ankle_socks",
    }
    assert directive["backdrop"] == "solid_white"
    assert directive["garment_continuity"]["exact_same_garments_across_views"] is True
    assert directive["garment_continuity"]["canonical_identity"] == {
        "top": {
            "colorway": "plain_soft_white",
            "material": "matte_cotton_jersey",
            "cut": "simple_crew_neck_short_sleeve",
        },
        "bottom": {
            "colorway": "mid_blue",
            "material": "matte_cotton_denim",
            "cut": "relaxed_knee_length_shorts",
        },
        "footwear": {
            "colorway": "plain_white",
            "material": "ribbed_cotton",
            "cut": "ankle_length",
        },
        "surface_policy": "graphic_free_logo_free",
    }
    assert directive["hair_continuity"]["source"] == "current_project_confirmed_face_identity_references"
    assert directive["physical_reference_policy"] == "face_identity_only"
    assert directive["materialization_prompt"]
    assert directive["directive_sha256"]


def test_fake_imagegen_host_receives_typed_renderer_directive_not_body_evidence_or_raw_fields(tmp_path) -> None:
    store = McpMaterializationHandoffStore(storage_root=tmp_path / "handoffs")
    handoff = _ensure(store)

    host_request = store.public_renderer_request(handoff["handoff_id"])
    captured: dict[str, object] = {}

    def fake_imagegen(request: dict[str, object]) -> None:
        captured.update(request)

    fake_imagegen(host_request)
    directive = captured["renderer_execution_directive"]
    assert captured["canonical_prompt"] == "Body proportion and stance only."
    assert captured["canonical_prompt_sha256"] == "canonical-prompt-hash"
    assert captured["renderer_prompt"].startswith(
        "Body proportion and stance only.\n\nExecute the closed server-owned"
    )
    assert captured["renderer_prompt_sha256"]
    assert captured["renderer_execution_directive_sha256"] == directive["directive_sha256"]

    assert directive["presentation"]["top"] == "short_sleeve_top"
    assert directive["presentation"]["bottom"] == "shorts"
    assert directive["presentation"]["footwear"] == "plain_white_ankle_socks"
    assert directive["backdrop"] == "solid_white"
    assert directive["garment_continuity"]["top_presentation"] == "short_sleeve_top"
    assert directive["garment_continuity"]["bottom_presentation"] == "shorts"
    assert directive["garment_continuity"]["footwear_presentation"] == "plain_white_ankle_socks"
    assert directive["garment_continuity"]["canonical_identity"]["bottom"]["colorway"] == "mid_blue"
    assert directive["hair_continuity"]["scope"] == "body_silhouette_only"
    assert directive["physical_reference_policy"] == "face_identity_only"
    assert "plain short-sleeve top" in captured["renderer_prompt"]
    assert "shorts with legs visible" in captured["renderer_prompt"]
    assert "plain white ankle socks with visible ankle and ground contact" in captured["renderer_prompt"]
    assert "exact same-garment series" in captured["renderer_prompt"]
    assert "plain soft-white matte cotton-jersey crew-neck short-sleeve top" in captured[
        "renderer_prompt"
    ]
    assert "mid-blue matte cotton-denim relaxed knee-length shorts" in captured["renderer_prompt"]
    assert "plain white ribbed-cotton ankle socks" in captured["renderer_prompt"]
    assert "graphic-free and logo-free" in captured["renderer_prompt"]
    assert "do not change garment colorway, material, cut, graphics, logos, or added layers" in captured[
        "renderer_prompt"
    ].lower()
    assert "barefoot" not in captured["renderer_prompt"].lower()
    assert "no shoes or socks" not in captured["renderer_prompt"].lower()
    assert "perfectly uniform pure solid white backdrop, no gray, no gradient, no floor, no shadow" in captured["renderer_prompt"]
    assert "same hairstyle category" in captured["renderer_prompt"]
    assert "same hair length tier" in captured["renderer_prompt"]
    assert "same bangs-or-parting pattern" in captured["renderer_prompt"]
    assert "same overall hair outline" in captured["renderer_prompt"]
    assert "body-hash-0" not in json.dumps(directive, sort_keys=True)
    assert "raw_prompt" not in directive
    assert "provider_payload" not in directive
    assert "base64" not in json.dumps(directive, sort_keys=True).lower()


def test_strict_submit_requires_host_request_hashes_and_accepts_matching_hashes(tmp_path) -> None:
    store = McpMaterializationHandoffStore(storage_root=tmp_path / "handoffs")
    handoff = _ensure(store)
    host_request = store.public_renderer_request(handoff["handoff_id"])

    with pytest.raises(McpMaterializationError) as missing:
        store.submit(
            handoff["handoff_id"],
            nonce=handoff["nonce"],
            prompt_sha256=handoff["prompt_sha256"],
            reference_asset_hashes=handoff["reference_asset_hashes"],
            artifact_bytes=_png_bytes(),
        )
    assert missing.value.code == "mcp_materialization_renderer_prompt_hash_required"

    with pytest.raises(McpMaterializationError) as mismatch:
        store.submit(
            handoff["handoff_id"],
            nonce=handoff["nonce"],
            prompt_sha256=handoff["prompt_sha256"],
            reference_asset_hashes=handoff["reference_asset_hashes"],
            artifact_bytes=_png_bytes(),
            renderer_prompt_sha256="0" * 64,
            renderer_execution_directive_sha256=host_request["renderer_execution_directive_sha256"],
        )
    assert mismatch.value.code == "mcp_materialization_renderer_prompt_hash_mismatch"

    with pytest.raises(McpMaterializationError) as missing_directive_hash:
        store.submit(
            handoff["handoff_id"],
            nonce=handoff["nonce"],
            prompt_sha256=handoff["prompt_sha256"],
            reference_asset_hashes=handoff["reference_asset_hashes"],
            artifact_bytes=_png_bytes(),
            renderer_prompt_sha256=host_request["renderer_prompt_sha256"],
        )
    assert missing_directive_hash.value.code == (
        "mcp_materialization_renderer_execution_directive_hash_required"
    )

    with pytest.raises(McpMaterializationError) as bad_directive_hash:
        store.submit(
            handoff["handoff_id"],
            nonce=handoff["nonce"],
            prompt_sha256=handoff["prompt_sha256"],
            reference_asset_hashes=handoff["reference_asset_hashes"],
            artifact_bytes=_png_bytes(),
            renderer_prompt_sha256=host_request["renderer_prompt_sha256"],
            renderer_execution_directive_sha256="0" * 64,
        )
    assert bad_directive_hash.value.code == (
        "mcp_materialization_renderer_execution_directive_hash_mismatch"
    )

    with pytest.raises(McpMaterializationError) as missing_execution_receipt:
        store.submit(
            handoff["handoff_id"],
            nonce=handoff["nonce"],
            prompt_sha256=handoff["prompt_sha256"],
            reference_asset_hashes=handoff["reference_asset_hashes"],
            artifact_bytes=_png_bytes(),
            renderer_prompt_sha256=host_request["renderer_prompt_sha256"],
            renderer_execution_directive_sha256=host_request[
                "renderer_execution_directive_sha256"
            ],
        )
    assert missing_execution_receipt.value.code == (
        "mcp_materialization_renderer_execution_receipt_required"
    )

    submitted = store.submit(
        handoff["handoff_id"],
        nonce=handoff["nonce"],
        prompt_sha256=handoff["prompt_sha256"],
        reference_asset_hashes=handoff["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
        renderer_prompt_sha256=host_request["renderer_prompt_sha256"],
        renderer_execution_directive_sha256=host_request[
            "renderer_execution_directive_sha256"
        ],
        renderer_execution_receipt=_renderer_execution_receipt(host_request),
    )
    assert submitted["status"] == "submitted"


def test_ordinary_submit_remains_compatible_without_renderer_hashes(tmp_path) -> None:
    store = McpMaterializationHandoffStore(storage_root=tmp_path / "handoffs")
    handoff = _ensure(
        store,
        {
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "output_format": "png",
            "count": 1,
        },
        require_body_rendering_contract=False,
    )
    submitted = store.submit(
        handoff["handoff_id"],
        nonce=handoff["nonce"],
        prompt_sha256=handoff["prompt_sha256"],
        reference_asset_hashes=handoff["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
    )
    assert submitted["status"] == "submitted"


def test_route_handler_forwards_renderer_hashes_to_store(tmp_path) -> None:
    captured: dict[str, object] = {}

    class _Store:
        def submit(self, handoff_id: str, **kwargs):  # noqa: ANN001
            captured["handoff_id"] = handoff_id
            captured.update(kwargs)
            return {"status": "submitted"}

    class _Service:
        mcp_materialization_store = _Store()

    handlers = object.__new__(V3ProductRouteHandlers)
    handlers.service = _Service()
    result = handlers.post_mcp_materialization_submit(
        "mcp_handoff_route_test",
        {
            "nonce": "nonce",
            "prompt_sha256": "prompt-hash",
            "reference_asset_hashes": ["face-hash"],
            "renderer_prompt_sha256": "renderer-prompt-hash",
            "renderer_execution_directive_sha256": "directive-hash",
            "renderer_execution_receipt": {"schema_version": "test_receipt"},
            "artifact_base64": base64.b64encode(b"typed-artifact").decode("ascii"),
        },
    )

    assert result == {"status": "submitted"}
    assert captured["renderer_prompt_sha256"] == "renderer-prompt-hash"
    assert captured["renderer_execution_directive_sha256"] == "directive-hash"
    assert captured["renderer_execution_receipt"] == {"schema_version": "test_receipt"}


def test_strict_consume_requires_persisted_renderer_receipt_and_fingerprint(tmp_path) -> None:
    store = McpMaterializationHandoffStore(storage_root=tmp_path / "handoffs")
    handoff = _ensure(store)
    host_request = store.public_renderer_request(handoff["handoff_id"])
    store.submit(
        handoff["handoff_id"],
        nonce=handoff["nonce"],
        prompt_sha256=handoff["prompt_sha256"],
        reference_asset_hashes=handoff["reference_asset_hashes"],
        artifact_bytes=_png_bytes(),
        renderer_prompt_sha256=host_request["renderer_prompt_sha256"],
        renderer_execution_directive_sha256=host_request[
            "renderer_execution_directive_sha256"
        ],
        renderer_execution_receipt=_renderer_execution_receipt(host_request),
    )
    public = store.public_view(handoff["handoff_id"])
    assert public["renderer_prompt_sha256"] == host_request["renderer_prompt_sha256"]

    path = tmp_path / "handoffs" / f"{handoff['handoff_id']}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("renderer_execution_receipt", None)
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(McpMaterializationError) as missing_receipt:
        store.consume(handoff["handoff_id"])
    assert missing_receipt.value.code == "mcp_materialization_renderer_execution_receipt_required"

    payload["renderer_execution_receipt"] = _renderer_execution_receipt(host_request)
    payload["rendering_contract_fingerprint"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(McpMaterializationError) as bad_fingerprint:
        store.public_view(handoff["handoff_id"])
    assert bad_fingerprint.value.code == "mcp_materialization_renderer_execution_directive_mismatch"


def test_old_strict_handoff_without_renderer_directive_fails_closed(tmp_path) -> None:
    store = McpMaterializationHandoffStore(storage_root=tmp_path / "handoffs")
    handoff = _ensure(store)
    path = tmp_path / "handoffs" / f"{handoff['handoff_id']}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("renderer_execution_directive", None)
    payload.pop("renderer_execution_directive_sha256", None)
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(McpMaterializationError) as exc_info:
        store.public_view(handoff["handoff_id"])

    assert exc_info.value.code == "mcp_materialization_renderer_execution_directive_missing"


def test_ordinary_handoff_does_not_inherit_body_renderer_directive(tmp_path) -> None:
    store = McpMaterializationHandoffStore(storage_root=tmp_path / "handoffs")
    handoff = _ensure(
        store,
        {
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "size": "1024x1024",
            "quality": "high",
            "output_format": "png",
            "count": 1,
            "api_operation": "image_edit",
        },
        require_body_rendering_contract=False,
    )

    public = store.public_view(handoff["handoff_id"])

    assert "renderer_execution_directive" not in public
