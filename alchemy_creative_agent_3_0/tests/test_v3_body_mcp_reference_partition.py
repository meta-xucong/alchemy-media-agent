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
Body/MCP request must retain the complete server-owned Body evidence partition
and the Face identity partition, including stable fingerprints, without
merging either into a generic Face role.  Body evidence informs the
Body-owner/Vision/Brain proportion context; it is not a physical ImageGen
input.  Only Face identity refs reach the renderer, so the direct image-edit
cap is evaluated against the Face physical projection.  Direct image-edit
routes keep their existing ``>5`` fail-closed contract.  The partition must
survive the frozen handoff/public view, while ordinary MCP, Expression,
General, and other routes must not inherit Body fields.  Prompt text,
candidate/formal/activation authority, and provider routing are out of scope.

These tests intentionally begin red against the current implementation.  The
production owner is expected to be, in order, the MCP provider's typed
reference admission/materialization projection, the shared asset-binding
planner's Body-stage partition handling, and the MCP handoff-store sanitizer.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router.providers import (
    GenerationRequest,
    GenerationResponse,
    McpMaterializationProvider,
    ProductionImageGenerationProvider,
    ReferenceInputAdmissionError,
)
from alchemy_creative_agent_3_0.app.generation_router.router import GenerationRouter
from alchemy_creative_agent_3_0.app.creative_core.central_brain import CentralCreativeBrain
from alchemy_creative_agent_3_0.tests.test_v3_doc245_body_formal_slot_receipt_seam import (
    _mcp_body_generation_request,
)
from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import (
    McpMaterializationHandoffStore,
    build_body_renderer_execution_receipt,
)
from alchemy_creative_agent_3_0.app.creative_core.mcp_reference_partition import (
    McpBodyReferencePartition,
)
from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
    body_silhouette_fixed_full_body_framing_contract,
    body_silhouette_integrated_whole_person_synthesis_contract,
    body_silhouette_mcp_materialization_channel_contract,
)
from alchemy_creative_agent_3_0.app.visual_assets.body_proportion_evidence_profile import (
    BodyMorphologyEvidenceProfile,
    BodyRefreshAnalysisContext,
    BodySourceAnalysisAssetEnvelope,
)
from alchemy_creative_agent_3_0.app.schemas import CandidateResult, ProviderStrategy
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    default_body_refresh_presentation_intent,
    default_body_silhouette_backdrop_presentation_contract,
    default_body_silhouette_garment_continuity_contract,
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


def _morphology_profile() -> BodyMorphologyEvidenceProfile:
    return BodyMorphologyEvidenceProfile(
        contract_version="body_morphology_evidence_profile_v2",
        source_mode="reference_assisted",
        source_truth_layer="body_proportion_truth",
        relative_head_to_stature="proportional",
        shoulder_to_head="narrower",
        torso_to_leg="shorter_torso",
        arm_to_leg="proportional",
        build="slender",
        neck_shoulder="narrow_transition",
        developmental_stage_context="middle_stage_context",
        stance_ground="grounded_full_contact",
        cross_view_support="multi_view_supported",
        source_count=5,
        analysis_receipt={
            "owner": "server_owned_body_proportion_analysis",
            "status": "complete",
            "analysis_provider": "configured_body_source_analysis_provider",
        },
    )


def _morphology_contract() -> dict[str, object]:
    profile = _morphology_profile()
    profile_payload = profile.model_dump(mode="json")
    bands = {
        key: value
        for key, value in profile_payload.items()
        if key
        not in {
            "contract_version",
            "source_mode",
            "source_truth_layer",
            "source_count",
            "analysis_receipt",
        }
    }
    canonical = lambda value: hashlib.sha256(  # noqa: E731
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "body_morphology_evidence_profile_v2",
        "profile_digest": canonical(profile_payload),
        "bands_digest": canonical(bands),
        "bands": bands,
        "target_age_scope": "age_6_child_only",
    }


def _current_body_context(body_assets: list[dict]) -> BodyRefreshAnalysisContext:
    profile = _morphology_profile()
    envelopes = [
        BodySourceAnalysisAssetEnvelope(
            asset_id=str(item["asset_id"]),
            role="body_proportion_reference",
            reference_truth_layer="body_proportion_truth",
            file_path=str(item["file_path"]),
            mime_type="image/png",
            source_sha256=hashlib.sha256(Path(item["file_path"]).read_bytes()).hexdigest(),
            source_provenance="user_provided_body_reference",
            consent_reference="consent_body_reference",
            rights_reference="rights_body_reference",
        )
        for item in body_assets
    ]
    return BodyRefreshAnalysisContext.from_analysis(
        attempt_id="body_refresh_attempt_0123456789abcdef0123456789abcdef",
        append_only_revision=1,
        admitted_body_assets=envelopes,
        profile=profile,
        target_age_scope="age_6_child_only",
    )


def _attach_current_body_context(
    request: GenerationRequest,
    body_assets: list[dict],
    face_assets: list[dict],
) -> GenerationRequest:
    context = _current_body_context(body_assets)
    request.metadata.update(
        {
            "professional_identity_reference_strategy": "character_card_shared_identity_v1",
            "professional_body_refresh_analysis_context": context.safe_metadata(),
            "professional_character_card_face_view_binding": {
                "front_full": {
                    "face_slot": "face.front",
                    "source_asset_id": face_assets[0]["asset_id"],
                }
            },
        }
    )
    return request.model_copy(update={"body_refresh_analysis_context": context})


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
    request.metadata["professional_anchor_reference_assets"] = [*body_assets, *face_assets]

    retained = McpMaterializationProvider()._reference_assets(request)

    assert len(retained) == 2
    assert all(item["role"] == "face_reference" for item in retained)
    assert all(
        item.get("file_path") not in {body["file_path"] for body in body_assets}
        for item in retained
    )
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
        "target_age_scope": "age_6_child_only",
        "body_silhouette_mcp_materialization_channel_contract": (
            body_silhouette_mcp_materialization_channel_contract()
        ),
        "body_silhouette_integrated_whole_person_synthesis_contract": (
            body_silhouette_integrated_whole_person_synthesis_contract()
        ),
        "body_silhouette_fixed_full_body_framing_contract": (
            body_silhouette_fixed_full_body_framing_contract()
        ),
        "body_refresh_presentation_intent": default_body_refresh_presentation_intent().model_dump(
            mode="json"
        ),
        "body_silhouette_garment_continuity_contract": (
            default_body_silhouette_garment_continuity_contract()
        ),
        "body_silhouette_hair_continuity_contract": (
            default_body_silhouette_hair_continuity_contract()
        ),
        "body_silhouette_backdrop_presentation_contract": (
            default_body_silhouette_backdrop_presentation_contract()
        ),
        "body_mcp_reference_partition": partition,
        "body_morphology_profile": _morphology_contract(),
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
    renderer_request = store.public_renderer_request(handoff["handoff_id"])
    assert public_contract["body_mcp_reference_partition"] == partition
    renderer_prompt = renderer_request["renderer_prompt"].lower()
    assert "natural child-scale head-to-stature relationship" in renderer_prompt
    assert "shoulders naturally narrower relative to the head" in renderer_prompt
    assert "natural compact torso relative to leg length" in renderer_prompt
    assert "slender, age-appropriate child build" in renderer_prompt
    assert "one coherent whole person" in renderer_prompt
    assert "body proportion evidence has already been analyzed server-side and is not a physical input" in renderer_prompt
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
            "professional_anchor_reference_assets": [*body_assets, *face_assets],
            "reference_assets": [*body_assets, *face_assets],
        }
    )
    request = _attach_current_body_context(request, body_assets, face_assets)

    app_request, _, retained = McpMaterializationProvider()._build_app_request(request)

    context = app_request.prompt_plan.variables["mcp_materialization_context"]
    partition = context["rendering_contract"]["body_mcp_reference_partition"]
    assert request.body_refresh_analysis_context is not None
    assert "professional_body_proportion_analysis_receipt" not in request.metadata
    assert len(retained) <= 5
    assert all(item.get("role") == "portrait_identity" for item in retained)
    assert partition["body_proportion_reference"]["asset_count"] == 5
    assert partition["face_identity_reference"]["asset_count"] == 2


def test_central_generation_loop_preserves_ephemeral_profile_and_face_view_binding(tmp_path) -> None:
    body_assets, _face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=0)
    body_context = _current_body_context(body_assets)
    face_view_binding = {
        "front_full": {"face_slot": "face.front", "source_asset_id": "face-front"},
        "side_full": {"face_slot": "face.profile", "source_asset_id": "face-profile"},
        "rear_full": {"face_slot": "face.rear_head", "source_asset_id": "face-rear"},
    }

    class _CapturingProvider(McpMaterializationProvider):
        def __init__(self) -> None:
            super().__init__()
            self.requests: list[GenerationRequest] = []

        def generate(self, request: GenerationRequest) -> GenerationResponse:
            self.requests.append(request)
            return GenerationResponse(
                candidates=[
                    CandidateResult(
                        candidate_id="candidate_ephemeral_body_context",
                        asset_id=request.generation_plan.asset_id,
                        provider="capture_only",
                        prompt_compilation_id=request.prompt_compilation.prompt_compilation_id,
                        condition_plan_id=request.condition_plan.condition_plan_id,
                        is_mock=True,
                    )
                ],
                provider_metadata={"provider_name": "capture_only"},
                warnings=[],
            )

    provider = _CapturingProvider()
    CentralCreativeBrain(generation_router=GenerationRouter(provider=provider)).run_generation_loop(
        "strict reference-assisted Body candidate",
        provider_strategy=ProviderStrategy.MCP_MATERIALIZATION,
        body_refresh_analysis_context=body_context,
        runtime_metadata={
            "requested_image_count": 1,
            "generation_channel": "mcp",
            "professional_identity_reference_strategy": "character_card_shared_identity_v1",
            "professional_reference_stage": "character_card_body_silhouette",
            "professional_character_card_preparation": True,
            "professional_character_card_stage": "body_silhouette",
            "professional_character_card_slot": "body.front_full",
            "professional_character_card_candidate_index": 1,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_source_mode": "reference_assisted",
            "professional_character_card_body_refresh_contract_required": True,
            "professional_character_card_face_view_binding": face_view_binding,
            "professional_body_refresh_analysis_context": body_context.safe_metadata(),
        },
    )

    assert provider.requests
    provider_request = provider.requests[0]
    assert provider_request.body_refresh_analysis_context is body_context
    assert "body_refresh_analysis_context" not in provider_request.model_dump(mode="json")
    assert provider_request.metadata["professional_character_card_face_view_binding"] == face_view_binding
    assert provider_request.generation_plan.metadata[
        "professional_character_card_face_view_binding"
    ] == face_view_binding
    assert "professional_body_proportion_analysis_receipt" not in provider_request.metadata
    assert "profile" not in provider_request.metadata["professional_body_refresh_analysis_context"]


def test_runtime_frozen_body_metadata_keeps_safe_context_and_face_binding() -> None:
    safe_context = {
        "contract_version": "body_refresh_analysis_context_v2",
        "schema_version": "body_morphology_evidence_profile_v2",
        "source_mode": "reference_assisted",
        "attempt_id": "body_refresh_attempt_0123456789abcdef0123456789abcdef",
        "append_only_revision": 1,
        "source_binding_digest": "1" * 64,
        "source_evidence_id_digest": "2" * 64,
        "profile_digest": "3" * 64,
    }
    face_view_binding = {
        "front_full": {"face_slot": "face.front", "source_asset_id": "face-front"}
    }
    frozen = ScenarioRuntime._frozen_professional_provider_metadata(  # noqa: SLF001
        SimpleNamespace(
            activation_plan=SimpleNamespace(
                metadata={
                    "professional_character_card_preparation": True,
                    "professional_identity_reference_strategy": "character_card_shared_identity_v1",
                    "professional_reference_stage": "character_card_body_silhouette",
                    "professional_character_card_stage": "body_silhouette",
                    "professional_character_card_slot": "body.front_full",
                    "professional_character_card_body_refresh_source_mode": "reference_assisted",
                    "professional_character_card_face_view_binding": face_view_binding,
                    "professional_body_refresh_analysis_context": safe_context,
                }
            )
        )
    )

    assert frozen["professional_character_card_face_view_binding"] == face_view_binding
    assert frozen["professional_body_refresh_analysis_context"] == safe_context
    assert "profile" not in frozen["professional_body_refresh_analysis_context"]


def test_submitted_reference_assisted_handoff_reuses_frozen_morphology_without_profile_rebuild(
    tmp_path,
) -> None:
    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    store = McpMaterializationHandoffStore(tmp_path / "handoffs")
    provider = McpMaterializationProvider(handoff_store=store)
    request = _mcp_body_generation_request(
        "Body proportion and stance only.",
        source_mode="reference_assisted",
    )
    request.metadata.update(
        {
            "professional_character_card_body_refresh_contract_required": True,
            "professional_character_card_stage": "body_silhouette",
            "professional_character_card_slot": "body.front_full",
            "professional_character_card_candidate_index": 1,
            "professional_character_card_candidate_count": 3,
            "professional_character_card_body_refresh_presentation_intent": (
                default_body_refresh_presentation_intent().model_dump(mode="json")
            ),
            "professional_anchor_reference_assets": [*body_assets, *face_assets],
            "reference_assets": [*body_assets, *face_assets],
        }
    )
    request = _attach_current_body_context(request, body_assets, face_assets)
    app_request, _, retained = provider._build_app_request(request)  # noqa: SLF001
    handoff_context = app_request.prompt_plan.variables["mcp_materialization_context"]
    pending = store.ensure_pending(
        operation_id=handoff_context["operation_id"],
        prompt=handoff_context["canonical_prompt"],
        prompt_sha256=handoff_context["prompt_sha256"],
        reference_assets=retained,
        rendering_contract=handoff_context["rendering_contract"],
        require_body_rendering_contract=True,
    )
    renderer_request = store.public_renderer_request(pending["handoff_id"])
    image = Image.new("RGB", (1024, 1536), (255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    store.submit(
        pending["handoff_id"],
        nonce=pending["nonce"],
        prompt_sha256=pending["prompt_sha256"],
        reference_asset_hashes=pending["reference_asset_hashes"],
        artifact_bytes=buffer.getvalue(),
        renderer_prompt_sha256=renderer_request["renderer_prompt_sha256"],
        renderer_execution_directive_sha256=renderer_request[
            "renderer_execution_directive_sha256"
        ],
        renderer_execution_receipt=build_body_renderer_execution_receipt(
            renderer_prompt_sha256=renderer_request["renderer_prompt_sha256"],
            renderer_execution_directive_sha256=renderer_request[
                "renderer_execution_directive_sha256"
            ],
            canonical_prompt_sha256=renderer_request["canonical_prompt_sha256"],
            rendering_contract_fingerprint=renderer_request["rendering_contract_fingerprint"],
            nonce_sha256=renderer_request["renderer_execution_directive"]["nonce_sha256"],
            reference_asset_hashes=renderer_request["reference_asset_hashes"],
        ),
    )
    stale_face_assets = []
    for index, item in enumerate(face_assets):
        stale_path = tmp_path / f"stale-face-{index}.png"
        Image.new("RGB", (32, 32), (180 + index, 180, 180)).save(stale_path, format="PNG")
        stale_face_assets.append(
            {
                **item,
                "file_path": str(stale_path),
            }
        )
    resumed_metadata = {
        **request.metadata,
        # Same asset ids, different resolved files: a submitted handoff must
        # keep its frozen paths and hashes instead of accepting this newer
        # provider-side derivative.
        "reference_assets": [*body_assets, *stale_face_assets],
        "mcp_materialization": {
            "handoff_id": pending["handoff_id"],
            "status": "submitted",
            "generation_channel": "mcp",
            "resume_required": True,
        },
    }
    resumed = request.model_copy(
        update={
            "metadata": resumed_metadata,
            "body_refresh_analysis_context": None,
        }
    )

    resumed_app_request, _, _ = provider._build_app_request(resumed)  # noqa: SLF001

    resumed_context = resumed_app_request.prompt_plan.variables["mcp_materialization_context"]
    assert resumed_context["resume_from_handoff"] is True
    assert resumed_context["reference_assets"] == pending["reference_assets"]
    assert resumed_context["rendering_contract"]["body_morphology_profile"] == (
        pending["rendering_contract"]["body_morphology_profile"]
    )


def test_reference_assisted_body_partition_stays_typed_but_provider_inputs_are_face_only(
    tmp_path,
) -> None:
    """Body truth remains server-owned context and never becomes an image input."""

    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    request = _mcp_body_generation_request(
        "Body proportion and stance only.",
        source_mode="reference_assisted",
    )
    request.metadata.update(
        {
            "professional_character_card_body_refresh_contract_required": True,
            "professional_anchor_reference_assets": [*body_assets, *face_assets],
            "reference_assets": [*body_assets, *face_assets],
        }
    )
    request = _attach_current_body_context(request, body_assets, face_assets)

    app_request, _, provider_inputs = McpMaterializationProvider()._build_app_request(request)

    context = app_request.prompt_plan.variables["mcp_materialization_context"]
    partition = context["rendering_contract"]["body_mcp_reference_partition"]
    assert partition["body_proportion_reference"]["asset_count"] == 5
    assert partition["face_identity_reference"]["asset_count"] == 2
    assert len(provider_inputs) <= 5
    assert all(item.get("role") == "portrait_identity" for item in provider_inputs)
    assert all(
        item.get("reference_truth_layer") == "portrait_identity_truth"
        for item in provider_inputs
    )
    assert not any(item.get("role") == "body_proportion_reference" for item in provider_inputs)
    assert not any(
        (item.get("metadata") or {}).get("reference_truth_layer") == "body_proportion_truth"
        for item in provider_inputs
    )
    assert not any(
        item.get("file_path") in {body["file_path"] for body in body_assets}
        for item in provider_inputs
    )
    assert context["reference_assets"] == provider_inputs


def test_reference_assisted_client_body_refs_cannot_promote_to_body_truth(tmp_path) -> None:
    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    request = _mcp_body_generation_request(
        "Body proportion and stance only.",
        source_mode="reference_assisted",
    )
    request.metadata.update(
        {
            "professional_character_card_body_refresh_contract_required": True,
            "reference_assets": [*body_assets, *face_assets],
        }
    )

    with pytest.raises(ReferenceInputAdmissionError) as exc_info:
        McpMaterializationProvider()._reference_assets(request)

    assert exc_info.value.detail["reference_input_failure_code"] == (
        "body_mcp_reference_partition_channel_missing"
    )


def test_reference_assisted_view_owned_derivatives_are_face_only_before_handoff_cap(tmp_path) -> None:
    """One view-owned Face source expands to the complementary Doc95 pair."""

    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    request = _mcp_body_generation_request(
        "Body proportion and stance only.",
        source_mode="reference_assisted",
    )
    request.metadata.update(
        {
            "professional_anchor_reference_assets": [*body_assets, *face_assets],
            "reference_assets": [*body_assets, *face_assets],
            "professional_character_card_body_refresh_contract_required": True,
        }
    )
    request = _attach_current_body_context(request, body_assets, face_assets)

    app_request, _, provider_inputs = McpMaterializationProvider()._build_app_request(request)
    variables = app_request.prompt_plan.variables
    asset_plan = variables["asset_plan"]
    context = variables["mcp_materialization_context"]
    partition = context["rendering_contract"]["body_mcp_reference_partition"]

    assert partition["body_proportion_reference"]["asset_count"] == 5
    assert partition["face_identity_reference"]["asset_count"] == 2
    assert len(provider_inputs) == 2
    assert len(asset_plan["assets"]) == 2
    assert {item.get("source_asset_id") for item in provider_inputs} == {face_assets[0]["asset_id"]}
    assert {item.get("identity_evidence_scope") for item in provider_inputs} == {
        "feature_detail",
        "pose_geometry",
    }
    assert all(item.get("role") == "portrait_identity" for item in provider_inputs)
    assert all(item.get("role") == "portrait_identity" for item in asset_plan["assets"])
    assert all(item.get("reference_truth_layer") == "portrait_identity_truth" for item in provider_inputs)
    assert all(item.get("reference_truth_layer") == "portrait_identity_truth" for item in asset_plan["assets"])
    assert not any(
        item.get("file_path") in {body["file_path"] for body in body_assets}
        for item in provider_inputs
    )
    assert not any(
        item.get("storage_path") in {body["file_path"] for body in body_assets}
        for item in asset_plan["assets"]
    )


def test_reference_assisted_partition_is_built_before_base_provider_capacity_check(tmp_path) -> None:
    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    request = _mcp_body_generation_request(
        "Body proportion and stance only.",
        source_mode="reference_assisted",
    )
    request.metadata.update(
        {
            "professional_anchor_reference_assets": [*body_assets, *face_assets],
            "reference_assets": [*body_assets, *face_assets],
            "professional_character_card_body_refresh_contract_required": True,
        }
    )

    retained = McpMaterializationProvider()._reference_assets(request)

    assert len(retained) == 2
    assert request.metadata["body_mcp_reference_partition"]["body_proportion_reference"]["asset_count"] == 5
    assert request.metadata["body_mcp_reference_partition"]["face_identity_reference"]["asset_count"] == 2


def test_reference_assisted_face_physical_projection_still_enforces_cap(tmp_path) -> None:
    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=6)
    request = _mcp_body_generation_request(
        "Body proportion and stance only.",
        source_mode="reference_assisted",
    )
    request.metadata.update(
        {
            "professional_anchor_reference_assets": [*body_assets, *face_assets],
            "reference_assets": [*body_assets, *face_assets],
            "professional_character_card_body_refresh_contract_required": True,
        }
    )

    with pytest.raises(ReferenceInputAdmissionError) as exc_info:
        McpMaterializationProvider()._reference_assets(request)

    assert exc_info.value.detail["reference_input_failure_code"] == (
        "reference_input_capability_mismatch"
    )
    assert request.metadata["body_mcp_reference_partition"]["body_proportion_reference"][
        "asset_count"
    ] == 5


def test_reference_assisted_body_partition_does_not_change_inference_first_face_only_isolation(
    tmp_path,
) -> None:
    """The Body-only provider projection is scoped to reference-assisted mode."""

    body_assets, face_assets = _write_reference_assets(tmp_path, body_count=5, face_count=2)
    request = _mcp_body_generation_request(
        "Body proportion and stance only.",
        source_mode="inference_first",
    )
    request.metadata.update(
        {
            "professional_character_card_body_refresh_contract_required": True,
            "reference_assets": face_assets,
        }
    )

    _app_request, _, provider_inputs = McpMaterializationProvider()._build_app_request(request)

    assert all(item.get("role") != "body_proportion_reference" for item in provider_inputs)
    assert not any(
        (item.get("metadata") or {}).get("reference_truth_layer") == "body_proportion_truth"
        for item in provider_inputs
    )
    assert body_assets


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
        "target_age_scope": "age_6_child_only",
        "body_silhouette_mcp_materialization_channel_contract": (
            body_silhouette_mcp_materialization_channel_contract()
        ),
        "body_silhouette_integrated_whole_person_synthesis_contract": (
            body_silhouette_integrated_whole_person_synthesis_contract()
        ),
        "body_silhouette_fixed_full_body_framing_contract": (
            body_silhouette_fixed_full_body_framing_contract()
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
