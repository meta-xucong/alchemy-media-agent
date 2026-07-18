"""Doc161: reference ownership reaches Brain sign-off without local prompt recipes."""

from __future__ import annotations

import json

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainReferenceChannelOwnershipDecisionMissing,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
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
    metadata = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(view_role="front")

    assert metadata["professional_mode"] is True
    assert metadata["professional_anchor_pack_preparation"] is True
    assert metadata["professional_reference_stage"] == "front"
    contract = metadata["professional_face_identity_quality_contract"]
    assert contract["priority_order"][0] == "same_person_likeness"
    assert contract["owner"] == "remote_v3_llm_brain"
    serialized = json.dumps(metadata).lower()
    assert "prompt_additions" not in serialized
    assert "canonical_provider_prompt" not in serialized
