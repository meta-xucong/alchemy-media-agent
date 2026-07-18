"""Doc161: reference ownership reaches Brain sign-off without local prompt recipes."""

from __future__ import annotations

import json
import base64
from io import BytesIO

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainReferenceChannelOwnershipDecisionMissing,
)
from alchemy_creative_agent_3_0.app.creative_core.central_brain import CentralCreativeBrain
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
)
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.assets import V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.scenario_runtime import runtime as scenario_runtime_module
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _ownership_contract() -> dict[str, object]:
    return {
        "required": True,
        "contract_version": "v3_reference_channel_ownership_decision_v1",
        "owner": "remote_v3_llm_brain",
        "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
        "reference_owned_channels": ["identity_geometry", "body_identity"],
        "current_request_owned_channels": [
            "hair_direction",
            "wardrobe_structure",
            "lighting_color",
            "scene_background",
            "camera_composition",
            "mood_art_direction",
            "style_finish",
        ],
        "explicit_user_locked_channels": [],
        "blocked_reference_inheritance_channels": ["hair_direction", "wardrobe_structure"],
        "resolution_mode": "rewrite_complete_canonical_prompt",
    }


def _finalizer_request() -> BrainRunRequest:
    return BrainRunRequest(
        user_input="Keep the same person in a new scene and new wardrobe.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={
            "canonical_prompt_context": {
                "reference_channel_ownership_decision": _ownership_contract(),
                "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
            }
        },
    )


def test_doc161_finalizer_schema_requires_remote_reference_ownership_receipt() -> None:
    payload = json.loads(build_remote_payload(_finalizer_request()))
    schema = payload["return_schema"]["canonical_provider_prompts"][0]
    serialized = json.dumps(payload, ensure_ascii=False)

    assert schema["reference_channel_ownership_decision"] == {
        "contract_version": "v3_reference_channel_ownership_decision_v1",
        "status": "approved|rewritten",
        "owner": "remote_v3_llm_brain",
    }
    assert "rewrite the whole prompt" in payload["remote_response_contract"]
    assert "local negative list" in payload["remote_response_contract"]
    assert "provider_prompt_rules" not in serialized
    assert "provider_negative_rules" not in serialized
    assert "prompt_additions" not in serialized


def test_doc161_adapter_fails_closed_when_remote_receipt_is_missing(monkeypatch) -> None:
    class MissingReceiptProvider:
        provider = "missing_receipt_test"
        model = "fixture"

        def available(self, *, force: bool = False) -> bool:
            return True

        def run(self, request) -> dict:  # noqa: ANN001
            return {
                "canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": "A complete remote-authored photographic direction that respects the person.",
                        "review_status": "approved",
                    }
                ]
            }

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    adapter = V3LLMBrainAdapter(provider=MissingReceiptProvider())

    with pytest.raises(BrainReferenceChannelOwnershipDecisionMissing):
        adapter.finalize_canonical_provider_prompts(_finalizer_request())


def test_doc161_runtime_projects_only_typed_reference_ownership() -> None:
    projection = {
        "capability_projection": {
            "resolved_reference_policy_package": {
                "applies": True,
                "effective_channel_owners": {
                    "identity_geometry": "reference:source:hard",
                    "body_identity": "reference:source:medium",
                    "hair_direction": "current_prompt",
                    "wardrobe_structure": "current_prompt",
                    "lighting_color": "current_prompt",
                    "scene_background": "current_prompt",
                    "camera_composition": "current_prompt_or_defaults",
                    "mood_art_direction": "current_prompt_or_defaults",
                    "style_finish": "current_prompt_or_defaults",
                },
                "policies": [
                    {
                        "explicit_user_locks": [],
                        "blocked_inheritance_channels": ["hair_direction", "wardrobe_structure"],
                        "provider_prompt_rules": ["legacy renderer prose must not cross"],
                        "provider_negative_rules": ["legacy negative prose must not cross"],
                    }
                ],
            }
        }
    }

    decision = ScenarioRuntime._reference_channel_ownership_decision(
        projection,
        frozen_binding={"envelope_id": "opaque", "ledger_id": "opaque"},
    )
    serialized = json.dumps(decision, ensure_ascii=False)

    assert decision["reference_owned_channels"] == ["body_identity", "identity_geometry"]
    assert "hair_direction" in decision["current_request_owned_channels"]
    assert decision["blocked_reference_inheritance_channels"] == [
        "hair_direction",
        "wardrobe_structure",
    ]
    assert "legacy renderer prose" not in serialized
    assert "provider_prompt_rules" not in serialized


def test_doc161_real_reference_runtime_requires_and_records_brain_signoff(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    source = tmp_path / "portrait.png"
    Image.new("RGB", (640, 640), (186, 142, 121)).save(source)
    provider = EcommerceRemoteBrainTestProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))

    result = runtime.plan_job(
        {
            "user_input": "Keep the same woman but use short hair, a white shirt, and a cool studio.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_assets": [
                {
                    "asset_id": "portrait_doc161",
                    "role": "face_reference",
                    "file_path": str(source),
                    "use_policy": "identity",
                    "strength": "hard",
                }
            ],
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    finalizer = next(item for item in provider.requests if item["stage"] == "provider_prompt_finalize")
    ownership = finalizer["metadata"]["canonical_prompt_context"][
        "reference_channel_ownership_decision"
    ]
    assert "identity_geometry" in ownership["reference_owned_channels"]
    assert "hair_direction" in ownership["current_request_owned_channels"]
    assert "wardrobe_structure" in ownership["blocked_reference_inheritance_channels"]
    audit = result.metadata["llm_brain"]["audit"]
    assert audit["reference_channel_ownership_decision_required"] is True
    assert audit["reference_channel_ownership_decision_signed"] is True


def test_doc161_professional_anchor_preparation_has_formal_quality_context() -> None:
    metadata = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(view_role="standard_front")

    assert metadata["professional_mode"] is True
    assert metadata["professional_anchor_pack_preparation"] is True
    assert metadata["professional_reference_stage"] == "standard_front"
    assert metadata["professional_identity_reference_strategy"] == "serial_anchor_pack_root_reuse_v1"
    contract = metadata["professional_face_identity_quality_contract"]
    assert contract["priority_order"][0] == "same_person_likeness"
    assert contract["owner"] == "remote_v3_llm_brain"
    serialized = json.dumps(metadata).lower()
    assert "prompt_additions" not in serialized
    assert "canonical_provider_prompt" not in serialized


def test_doc161_formal_professional_anchor_preparation_reaches_shared_runtime(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    source = tmp_path / "professional-root.png"
    Image.new("RGB", (640, 640), (184, 140, 120)).save(source)
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="standard_front"
    )
    provider = EcommerceRemoteBrainTestProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))

    result = runtime.plan_job(
        {
            "user_input": (
                "Prepare one straight-on Face Identity anchor of the same person, with ordinary neutral styling "
                "and camera-observed human materiality."
            ),
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_assets": [
                {
                    "asset_id": "professional_root_doc161",
                    "role": "face_reference",
                    "file_path": str(source),
                    "use_policy": "identity",
                    "strength": "hard",
                }
            ],
            "metadata": {
                "project_id": "project_doc161_anchor",
                "requested_image_count": 1,
                "require_real_images": True,
                "professional_mode": True,
                "professional_anchor_pack_preparation": True,
                "professional_planning_metadata": planning,
            },
        }
    )

    assert result.status.value == "planned"
    plan = result.metadata["capability_activation_plan"]
    assert {"portrait_identity", "reference_channel_policy", "human_realism"}.issubset(
        set(plan["dependency_order"])
    )
    finalizer = next(item for item in provider.requests if item["stage"] == "provider_prompt_finalize")
    context = finalizer["metadata"]["canonical_prompt_context"]
    assert context["professional_face_identity_quality_contract"] == planning[
        "professional_face_identity_quality_contract"
    ]
    assert context["reference_channel_ownership_decision"]["required"] is True


def test_doc164_generate_loop_receives_frozen_professional_stage_before_provider(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    source = tmp_path / "professional-root.png"
    Image.new("RGB", (640, 640), (184, 140, 120)).save(source)
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="three_quarter"
    )
    provider = EcommerceRemoteBrainTestProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))
    captured: dict[str, object] = {}
    real_generation_loop = scenario_runtime_module.run_generation_loop

    def capture_generation_metadata(**kwargs):  # noqa: ANN003, ANN202
        captured.update(dict(kwargs["runtime_metadata"]))
        return real_generation_loop(**kwargs)

    monkeypatch.setattr(
        scenario_runtime_module,
        "run_generation_loop",
        capture_generation_metadata,
    )

    result = runtime.generate_job(
        {
            "user_input": "Prepare one three-quarter Face Identity anchor of the same person.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_assets": [
                {
                    "asset_id": "professional_root_doc164",
                    "role": "face_reference",
                    "file_path": str(source),
                    "use_policy": "identity",
                    "strength": "hard",
                }
            ],
            "metadata": {
                "project_id": "project_doc164_generation_boundary",
                "requested_image_count": 1,
                "require_real_images": True,
                "professional_mode": True,
                "professional_anchor_pack_preparation": True,
                "professional_planning_metadata": planning,
            },
        }
    )

    assert result.status.value == "generated"
    assert captured["professional_identity_reference_strategy"] == (
        "serial_anchor_pack_root_reuse_v1"
    )
    assert captured["professional_reference_stage"] == "three_quarter"


def test_doc164_central_brain_keeps_frozen_professional_stage_on_each_output_plan() -> None:
    result = CentralCreativeBrain().run_generation_loop(
        user_input="Prepare one three-quarter identity anchor.",
        runtime_metadata={
            "requested_image_count": 1,
            "professional_identity_reference_strategy": "serial_anchor_pack_root_reuse_v1",
            "professional_reference_stage": "three_quarter",
        },
    )

    metadata = result.generation_plans[0].metadata
    assert metadata["professional_identity_reference_strategy"] == (
        "serial_anchor_pack_root_reuse_v1"
    )
    assert metadata["professional_reference_stage"] == "three_quarter"


def test_doc164_serial_anchor_vision_distinguishes_root_from_reviewed_winner(
    tmp_path,
) -> None:
    root = tmp_path / "root.png"
    winner = tmp_path / "front-winner.png"
    Image.new("RGB", (64, 64), (160, 130, 115)).save(root)
    Image.new("RGB", (64, 64), (150, 135, 125)).save(winner)
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="three_quarter"
    )
    prompt = _inspection_prompt(
        {
            "user_input": "Prepare one three-quarter identity anchor.",
            "professional_identity_reference_strategy": "serial_anchor_pack_root_reuse_v1",
            "professional_reference_stage": "three_quarter",
            "reference_assets": [
                {"asset_id": "root", "role": "face_reference", "file_path": str(root)},
                {
                    "asset_id": "front",
                    "role": "face_reference",
                    "source_type": "selected_output",
                    "file_path": str(winner),
                },
            ],
            "capability_execution_envelope": {
                "activation_plan": {
                    "plan_id": "plan_doc164",
                    "activation_mode": "enforced",
                    "dependency_order": [],
                    "metadata": planning,
                },
                "resolved_constraint_ledger": {
                    "hard_semantic_contract": True,
                    "provider_projection": {
                        "composed_visual_contribution": {"active_capability_ids": []}
                    },
                    "review_contracts": [],
                },
            },
        }
    )

    assert "Image 2 is the immutable root portrait" in prompt
    assert "previously reviewed anchor winners" in prompt
    assert "same_person_identity_plus_neutral_anchor_capture_continuity" in prompt
    assert '"reviewed_prior_anchor_image_indexes": [3]' in prompt


def test_doc164_ordinary_identity_review_does_not_gain_anchor_continuity(tmp_path) -> None:
    root = tmp_path / "root.png"
    Image.new("RGB", (64, 64), (160, 130, 115)).save(root)
    prompt = _inspection_prompt(
        {
            "user_input": "Keep the same person in a new setting.",
            "reference_assets": [
                {"asset_id": "root", "role": "face_reference", "file_path": str(root)}
            ],
        }
    )

    assert "Professional serial-anchor reference authority" not in prompt
    assert "previously reviewed anchor winners" not in prompt


def test_doc161_professional_anchor_preparation_rejects_missing_root_before_brain(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    provider = EcommerceRemoteBrainTestProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="standard_front"
    )

    result = runtime.plan_job(
        {
            "user_input": "Prepare one Face Identity anchor.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {
                "professional_mode": True,
                "professional_anchor_pack_preparation": True,
                "professional_planning_metadata": planning,
                "require_real_images": True,
            },
        }
    )

    assert result.status.value == "blocked"
    assert "professional_anchor_pack_root_evidence_missing" in " ".join(result.warnings)
    assert provider.requests == []


def test_doc161_product_api_internal_anchor_job_injects_server_owned_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    provider = EcommerceRemoteBrainTestProvider()
    service = V3ProductApiService(
        scenario_runtime=ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))
    )
    service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "uploads")
    image = Image.new("RGB", (640, 640), (184, 140, 120))
    content = BytesIO()
    image.save(content, format="PNG")
    raw = content.getvalue()
    upload = service.create_uploaded_asset(
        {
            "filename": "authorized-root.png",
            "mime_type": "image/png",
            "size_bytes": len(raw),
            "role": "face_reference",
        }
    )
    service.store_uploaded_asset_content(
        upload.asset_id,
        {"content_base64": base64.b64encode(raw).decode("ascii"), "mime_type": "image/png"},
    )
    service.complete_uploaded_asset(upload.asset_id)

    status = service.create_professional_anchor_preparation_job(
        {
            "user_input": "Prepare one straight-on Face Identity anchor of this same person.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_asset_ids": [upload.asset_id],
            "metadata": {
                "project_id": "project_doc161_internal_host",
                "requested_image_count": 1,
                "require_real_images": True,
            },
        },
        view_role="standard_front",
    )

    assert status.status == ProductJobStatusValue.PLANNED
    record = service.get_job_record(status.job_id)
    assert record is not None
    assert record.request.metadata["professional_anchor_pack_preparation"] is True
    assert record.request.metadata["professional_identity_reference_strategy"] == "serial_anchor_pack_root_reuse_v1"
    assert record.request.metadata["professional_reference_stage"] == "standard_front"
    assert record.request.metadata["professional_planning_metadata"][
        "professional_reference_stage"
    ] == "standard_front"
    assert record.request.metadata["capability_activation_plan"]["metadata"][
        "professional_face_identity_quality_contract"
    ]["owner"] == "remote_v3_llm_brain"

    remote_call_count = len(provider.requests)
    second = service.create_professional_anchor_preparation_job(
        {
            "user_input": "Prepare one straight-on Face Identity anchor of this same person.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_asset_ids": [upload.asset_id],
            "metadata": {
                "project_id": "project_doc161_internal_host",
                "requested_image_count": 1,
                "require_real_images": True,
            },
        },
        view_role="standard_front",
        reference_evidence_ids=[upload.asset_id],
        stage_plan_source_job_id=status.job_id,
    )
    assert second.status == ProductJobStatusValue.PLANNED
    assert len(provider.requests) == remote_call_count
    second_record = service.get_job_record(second.job_id)
    assert second_record is not None
    assert second_record.request.metadata["capability_plan_provenance"]["source_job_id"] == status.job_id


def test_doc161_public_job_cannot_impersonate_anchor_preparation() -> None:
    service = V3ProductApiService()
    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        service.create_job(
            {
                "user_input": "Impersonate an internal preparation job.",
                "scenario_selection": {"scenario_id": "general_creative"},
                "metadata": {"professional_anchor_pack_preparation": True},
            }
        )


def test_doc162_internal_profile_anchor_resolves_root_and_two_reviewed_winners(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    provider = EcommerceRemoteBrainTestProvider()
    service = V3ProductApiService(
        scenario_runtime=ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))
    )
    service.asset_store = V3UploadedAssetStore(storage_root=tmp_path / "uploads")
    service.output_store = V3GeneratedOutputStore(storage_root=tmp_path / "outputs")
    image = Image.new("RGB", (128, 128), (184, 140, 120))
    content = BytesIO()
    image.save(content, format="PNG")
    raw = content.getvalue()
    encoded = base64.b64encode(raw).decode("ascii")
    upload = service.create_uploaded_asset(
        {
            "filename": "authorized-root.png",
            "mime_type": "image/png",
            "size_bytes": len(raw),
            "role": "face_reference",
        }
    )
    service.store_uploaded_asset_content(
        upload.asset_id,
        {"content_base64": encoded, "mime_type": "image/png"},
    )
    service.complete_uploaded_asset(upload.asset_id)
    winners = [
        service.output_store.save_base64_output(
            job_id=f"source_job_{index}",
            candidate_id=f"source_candidate_{index}",
            asset_id=f"source_asset_{index}",
            provider="test",
            model="test",
            encoded_image=encoded,
            mime_type="image/png",
            metadata={"review_status": "pass"},
        )
        for index in range(2)
    ]

    status = service.create_professional_anchor_preparation_job(
        {
            "user_input": "Prepare one profile Face Identity anchor of this same person.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_asset_ids": [upload.asset_id],
            "metadata": {
                "project_id": "project_doc162_profile_host",
                "requested_image_count": 1,
                "require_real_images": True,
            },
        },
        view_role="profile",
        reference_evidence_ids=[upload.asset_id, *(item.output_id for item in winners)],
    )

    assert status.status == ProductJobStatusValue.PLANNED
    record = service.get_job_record(status.job_id)
    assert record is not None
    selected = record.request.metadata["professional_anchor_reference_assets"]
    assert [item["asset_id"] for item in selected] == [item.output_id for item in winners]
    runtime_payload = service._runtime_request_payload(record.request)  # noqa: SLF001
    assert [item.asset_id if hasattr(item, "asset_id") else item["asset_id"] for item in runtime_payload["uploaded_assets"]] == [
        upload.asset_id,
        winners[0].output_id,
        winners[1].output_id,
    ]
    generation_metadata = record.planning_result.generation_plans[0].metadata
    assert generation_metadata["professional_identity_reference_strategy"] == (
        "serial_anchor_pack_root_reuse_v1"
    )
    assert generation_metadata["professional_reference_stage"] == "profile"
    frozen_references = generation_metadata["reference_assets"]
    assert [item.get("output_id") for item in frozen_references[1:]] == [
        winners[0].output_id,
        winners[1].output_id,
    ]
    assert all(item.get("source_type") == "selected_output" for item in frozen_references[1:])
