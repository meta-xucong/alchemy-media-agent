"""Red tests and correction model for Body/Face reference partitioning.

Correction model
----------------
The fresh reference-assisted Body run admitted five server-owned
``body_proportion_reference`` assets and the Body request also carried the
Face identity chain.  The first loss is at the route/materialization boundary:
the MCP Body request inherits the direct GPT image-edit provider's five-image
cap, while the shared asset-binding planner treats the Face inputs as generic
hard-role competitors.  The result is a pre-MCP capability block even though
the five Body assets and Face identity evidence were admitted independently.

The owning fix is a typed, stage-aware materialization partition.  A strict
Body/MCP request must retain the complete Body partition and the Face identity
partition, including stable fingerprints, without merging either into a
generic Face role.  Direct image-edit routes keep their existing ``>5``
fail-closed contract.  MCP may only admit the partition under its own typed
capability contract; it must never silently trim references.  The partition
must survive the frozen handoff/public view, while ordinary MCP, Expression,
General, and other routes must not inherit Body fields.  Prompt text,
candidate/formal/activation authority, and provider routing are out of scope.

These tests intentionally begin red against the current implementation.  The
production owner is expected to be, in order, the MCP provider's typed
reference admission/materialization projection, the shared asset-binding
planner's Body-stage partition handling, and the MCP handoff-store sanitizer.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router.providers import (
    GenerationRequest,
    McpMaterializationProvider,
    ProductionImageGenerationProvider,
    ReferenceInputAdmissionError,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc245_body_formal_slot_receipt_seam import (
    _mcp_body_generation_request,
)
from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import (
    McpMaterializationHandoffStore,
)
from alchemy_creative_agent_3_0.app.creative_core.mcp_reference_partition import (
    McpBodyReferencePartition,
)
from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
    body_silhouette_mcp_materialization_channel_contract,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    default_body_refresh_presentation_intent,
    default_body_silhouette_backdrop_presentation_contract,
    default_body_silhouette_hair_continuity_contract,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.asset_binding_planner import (
    AssetBindingPlanner,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.contracts import (
    AssetRole,
    CapabilityInput,
    CapabilityStatus,
    UploadedAssetInfo,
)


def _write_reference_assets(tmp_path, *, body_count: int, face_count: int) -> tuple[list[dict], list[dict]]:
    body_assets: list[dict] = []
    face_assets: list[dict] = []
    for group, count, role, target in (
        ("body", body_count, "body_proportion_reference", body_assets),
        ("face", face_count, "face_reference", face_assets),
    ):
        for index in range(count):
            path = tmp_path / f"{group}-{index}.png"
            Image.new("RGB", (32, 32), (220 + index, 220, 220)).save(path, format="PNG")
            target.append(
                {
                    "asset_id": f"{group}-asset-{index}",
                    "role": role,
                    "file_path": str(path),
                    "provider_input_required": True,
                    "source_integrity_id": f"sha256:{group}-{index}",
                    "metadata": {
                        "source_type": "uploaded",
                        "provider_input_required": True,
                        "reference_truth_layer": (
                            "body_proportion_truth" if group == "body" else "identity_continuity"
                        ),
                    },
                }
            )
    return body_assets, face_assets


def _provider_request(*assets: dict, stage: str = "body_silhouette") -> SimpleNamespace:
    body_metadata = {
        "professional_character_card_body_refresh_source_mode": "reference_assisted",
        "professional_character_card_body_refresh_contract_required": True,
    } if stage == "body_silhouette" else {}
    return SimpleNamespace(
        metadata={
            "generation_channel": "mcp",
            "professional_character_card_stage": stage,
            "professional_character_card_slot": "body.front_full"
            if stage == "body_silhouette"
            else "expression_set.front",
            "reference_assets": list(assets),
            **body_metadata,
        },
        generation_plan=SimpleNamespace(metadata={}),
    )


def _body_face_partition(body_assets: list[dict], face_assets: list[dict]) -> dict:
    return {
        "contract_version": "body_mcp_reference_partition_v1",
        "body_proportion_reference": {
            "role": "body_proportion_reference",
            "truth_layer": "body_proportion_truth",
            "asset_count": len(body_assets),
            "asset_hashes": [f"body-hash-{index}" for index, _ in enumerate(body_assets)],
        },
        "face_identity_reference": {
            "role": "face_identity_reference",
            "truth_layer": "identity_continuity",
            "identity_continuity_only": True,
            "asset_count": len(face_assets),
            "asset_hashes": [f"face-hash-{index}" for index, _ in enumerate(face_assets)],
        },
    }


def test_direct_image_edit_route_keeps_over_five_reference_fail_closed(tmp_path) -> None:
    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    request = _provider_request(*body_assets, *face_assets, stage="body_silhouette")

    with pytest.raises(ReferenceInputAdmissionError) as exc_info:
        ProductionImageGenerationProvider()._reference_assets(request)

    assert exc_info.value.detail["reference_input_failure_code"] == (
        "reference_input_capability_mismatch"
    )


def test_mcp_body_route_partitions_and_retains_five_body_plus_two_face_refs(tmp_path) -> None:
    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    request = _provider_request(*body_assets, *face_assets, stage="body_silhouette")

    retained = McpMaterializationProvider()._reference_assets(request)

    assert len(retained) >= 7
    assert sum(item["role"] == "body_proportion_reference" for item in retained) == 5
    assert sum(item["role"] == "face_reference" for item in retained) == 2
    assert request.metadata["body_mcp_reference_partition"]["body_proportion_reference"]["asset_count"] == 5
    assert request.metadata["body_mcp_reference_partition"]["face_identity_reference"]["asset_count"] == 2


def test_mcp_body_handoff_public_view_preserves_typed_body_face_partition(tmp_path) -> None:
    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=3)
    partition = _body_face_partition(body_assets, face_assets)
    contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
        "body_refresh_source_mode": "reference_assisted",
        "body_silhouette_mcp_materialization_channel_contract": (
            body_silhouette_mcp_materialization_channel_contract()
        ),
        "body_refresh_presentation_intent": default_body_refresh_presentation_intent().model_dump(
            mode="json"
        ),
        "body_silhouette_hair_continuity_contract": (
            default_body_silhouette_hair_continuity_contract()
        ),
        "body_silhouette_backdrop_presentation_contract": (
            default_body_silhouette_backdrop_presentation_contract()
        ),
        "body_mcp_reference_partition": partition,
        "raw_prompt": "must never be persisted in the typed partition",
        "provider_payload": {"secret": "must never be persisted"},
    }
    store = McpMaterializationHandoffStore(storage_root=tmp_path / "handoffs")

    handoff = store.ensure_pending(
        operation_id="visual_asset_partition:body_silhouette:body.front_full:1",
        prompt="Body proportion and stance only.",
        prompt_sha256="partition-prompt-hash",
        reference_assets=[],
        rendering_contract=contract,
        require_body_rendering_contract=True,
    )

    public_contract = store.public_view(handoff["handoff_id"])["rendering_contract"]
    assert public_contract["body_mcp_reference_partition"] == partition
    assert "raw_prompt" not in public_contract
    assert "provider_payload" not in public_contract
    assert handoff["rendering_contract_fingerprint"] == store._rendering_contract_fingerprint(contract)
    changed_contract = {
        **contract,
        "body_mcp_reference_partition": _body_face_partition(body_assets[:4], face_assets),
    }
    assert handoff["rendering_contract_fingerprint"] != store._rendering_contract_fingerprint(
        changed_contract
    )


def test_body_stage_asset_binding_does_not_make_face_refs_generic_competitors(tmp_path) -> None:
    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    assets = [
        UploadedAssetInfo(
            asset_id=item["asset_id"],
            role=AssetRole(item["role"]),
            file_path=item["file_path"],
            metadata={
                **item["metadata"],
                "body_mcp_reference_partition": "body_only_partition_v1"
                if item["role"] == "body_proportion_reference"
                else "face_identity_partition_v1",
            },
        )
        for item in [*body_assets, *face_assets]
    ]
    capability_input = CapabilityInput(
        job_id="partition-job",
        scenario_id="professional_character_card",
        user_input="strict body silhouette",
        uploaded_assets=assets,
        metadata={
            "generation_channel": "mcp",
            "professional_character_card_stage": "body_silhouette",
            "professional_character_card_slot": "body.front_full",
            "professional_character_card_body_refresh_source_mode": "reference_assisted",
            "professional_anchor_reference_assets": [*body_assets, *face_assets],
        },
    )

    result = AssetBindingPlanner().execute(capability_input)

    assert not any(warning.code == "asset_binding_role_conflict" for warning in result.warnings)
    assert capability_input.metadata["body_mcp_reference_partition"]["body_proportion_reference"][
        "asset_count"
    ] == 5
    assert capability_input.metadata["body_mcp_reference_partition"]["face_identity_reference"][
        "asset_count"
    ] == 2
    bindings = result.facts["asset_binding_plan"]["bindings"]
    assert sum(binding["role"] == "body_proportion_reference" for binding in bindings) == 5
    assert sum(binding["role"] == "face_reference" for binding in bindings) == 2


def test_mcp_body_build_app_request_carries_partition_into_frozen_context(tmp_path) -> None:
    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    request = _mcp_body_generation_request(
        "Body proportion and stance only.",
        source_mode="reference_assisted",
    )
    request.metadata.update(
        {
            "professional_character_card_body_refresh_contract_required": True,
            "professional_identity_reference_strategy": "serial_anchor_pack_root_reuse_v1",
            "reference_assets": [*body_assets, *face_assets],
        }
    )

    app_request, _, retained = McpMaterializationProvider()._build_app_request(request)

    context = app_request.prompt_plan.variables["mcp_materialization_context"]
    partition = context["rendering_contract"]["body_mcp_reference_partition"]
    assert len(retained) >= 7
    assert partition["body_proportion_reference"]["asset_count"] == 5
    assert partition["face_identity_reference"]["asset_count"] == 2


def test_mcp_inference_first_keeps_face_only_compatibility_without_body_partition(tmp_path) -> None:
    _body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    request = _mcp_body_generation_request(
        "Body proportion and stance only.",
        source_mode="inference_first",
    )
    request.metadata.update(
        {
            "reference_assets": face_assets[:1],
            "professional_character_card_body_refresh_contract_required": True,
        }
    )

    app_request, _, retained = McpMaterializationProvider()._build_app_request(request)

    context = app_request.prompt_plan.variables["mcp_materialization_context"]
    contract = context["rendering_contract"]
    assert context["require_body_rendering_contract"] is True
    assert contract["body_refresh_source_mode"] == "inference_first"
    assert "body_mcp_reference_partition" not in contract
    assert not any(item.get("role") == "body_proportion_reference" for item in retained)
    assert not any(
        (item.get("metadata") or {}).get("reference_truth_layer") == "body_proportion_truth"
        for item in retained
    )


def test_mcp_inference_first_body_partition_is_fail_closed(tmp_path) -> None:
    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    request = _mcp_body_generation_request(
        "Body proportion and stance only.",
        source_mode="inference_first",
    )
    request.metadata.update(
        {
            "reference_assets": face_assets,
            "body_mcp_reference_partition": _body_face_partition(body_assets, face_assets),
            "professional_character_card_body_refresh_contract_required": True,
        }
    )

    with pytest.raises(ReferenceInputAdmissionError) as exc_info:
        McpMaterializationProvider()._reference_assets(request)

    assert exc_info.value.detail["reference_input_failure_code"] == (
        "body_reference_partition_forbidden_for_inference"
    )


def test_ordinary_mcp_and_expression_paths_do_not_inherit_body_partition(tmp_path) -> None:
    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    generic_contract = McpMaterializationHandoffStore._safe_rendering_contract(
        {
            "renderer": "codex_builtin_imagegen",
            "model": "gpt-image-2",
            "body_mcp_reference_partition": _body_face_partition(body_assets, face_assets),
        }
    )

    assert "body_mcp_reference_partition" not in generic_contract
    assert not McpMaterializationProvider._is_character_card_body_mcp_materialization(
        {
            "generation_channel": "mcp",
            "professional_character_card_stage": "expression_set",
            "professional_character_card_slot": "expression.front",
        }
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda partition: partition["body_proportion_reference"].update(asset_count=True),
        lambda partition: partition["body_proportion_reference"].update(asset_count="5"),
        lambda partition: partition["face_identity_reference"].update(asset_hashes="not-a-list"),
        lambda partition: partition["face_identity_reference"].update(asset_count=2),
        lambda partition: partition["body_proportion_reference"].update(raw_key="forbidden"),
    ],
)
def test_body_mcp_reference_partition_rejects_malformed_nested_fields(mutation) -> None:
    partition = _body_face_partition([{}] * 5, [{}] * 3)
    mutation(partition)

    with pytest.raises(ValueError):
        McpBodyReferencePartition.model_validate(partition)


def test_strict_body_handoff_missing_partition_fails_closed() -> None:
    contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
        "body_refresh_source_mode": "reference_assisted",
        "body_silhouette_mcp_materialization_channel_contract": (
            body_silhouette_mcp_materialization_channel_contract()
        ),
    }

    with pytest.raises(Exception) as exc_info:
        McpMaterializationHandoffStore._safe_rendering_contract(
            contract,
            require_body_rendering_contract=True,
        )

    assert exc_info.value.detail["failure_code"] == "body_reference_partition_missing"


def test_strict_body_planner_malformed_partition_fails_closed(tmp_path) -> None:
    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    result = AssetBindingPlanner().execute(
        CapabilityInput(
            job_id="partition-invalid-job",
            scenario_id="professional_character_card",
            user_input="strict body silhouette",
            uploaded_assets=[],
            metadata={
                "generation_channel": "mcp",
                "professional_character_card_stage": "body_silhouette",
                "professional_character_card_slot": "body.front_full",
                "professional_character_card_body_refresh_source_mode": "reference_assisted",
                "body_mcp_reference_partition": {"unknown": "payload"},
                "professional_anchor_reference_assets": [*body_assets, *face_assets],
            },
        )
    )

    assert result.status == CapabilityStatus.ERROR
    assert result.warnings[0].code == "body_mcp_reference_partition_invalid"
