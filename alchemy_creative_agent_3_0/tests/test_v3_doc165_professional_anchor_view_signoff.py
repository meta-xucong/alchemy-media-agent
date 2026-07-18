"""Doc165: Professional anchor view stays Brain-owned and fail-closed."""

from __future__ import annotations

import json

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainProfessionalAnchorViewDecisionMissing,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _view_contract(target: str = "profile") -> dict[str, object]:
    return {
        "required": True,
        "contract_version": "v3_professional_anchor_view_decision_v1",
        "owner": "remote_v3_llm_brain",
        "target_view_role": target,
        "frozen_binding": {
            "envelope_id": "opaque-envelope",
            "ledger_id": "opaque-ledger",
        },
    }


def _finalizer_request(target: str = "profile") -> BrainRunRequest:
    return BrainRunRequest(
        user_input="Prepare one identity anchor from the frozen Professional plan.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={
            "canonical_prompt_context": {
                "professional_anchor_view_decision": _view_contract(target),
                "professional_face_identity_quality_contract": {
                    "contract_version": "v3_professional_face_identity_quality_contract_v1",
                    "owner": "remote_v3_llm_brain",
                },
                "frozen_binding": {
                    "envelope_id": "opaque-envelope",
                    "ledger_id": "opaque-ledger",
                },
            }
        },
    )


def test_doc165_finalizer_schema_carries_exact_frozen_view_without_prompt_parsing() -> None:
    payload = json.loads(build_remote_payload(_finalizer_request("profile")))
    schema = payload["return_schema"]["canonical_provider_prompts"][0]
    serialized = json.dumps(payload, ensure_ascii=False)

    assert schema["professional_anchor_view_decision"] == {
        "contract_version": "v3_professional_anchor_view_decision_v1",
        "target_view_role": "profile",
        "status": "approved|rewritten",
        "owner": "remote_v3_llm_brain",
    }
    assert "rewrite the entire prompt" in payload["remote_response_contract"]
    assert "do not append a correction" in payload["remote_response_contract"]
    assert "keyword list" in payload["remote_response_contract"]
    assert "prompt_regex" not in serialized
    assert "provider_prompt_suffix" not in serialized


@pytest.mark.parametrize("receipt_target", [None, "standard_front", "three_quarter"])
def test_doc165_adapter_rejects_missing_or_mismatched_view_receipt(
    monkeypatch,
    receipt_target: str | None,
) -> None:
    class InvalidViewProvider:
        provider = "invalid_view_fixture"
        model = "fixture"

        def available(self, *, force: bool = False) -> bool:
            return True

        def run(self, request) -> dict:  # noqa: ANN001
            receipt = (
                {
                    "professional_anchor_view_decision": {
                        "contract_version": "v3_professional_anchor_view_decision_v1",
                        "target_view_role": receipt_target,
                        "status": "approved",
                        "owner": "remote_v3_llm_brain",
                    }
                }
                if receipt_target
                else {}
            )
            return {
                "canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": "A complete remote-authored Professional identity anchor direction.",
                        "review_status": "approved",
                        **receipt,
                    }
                ]
            }

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    adapter = V3LLMBrainAdapter(provider=InvalidViewProvider())

    with pytest.raises(BrainProfessionalAnchorViewDecisionMissing):
        adapter.finalize_canonical_provider_prompts(_finalizer_request("profile"))


def test_doc165_runtime_reanswers_missing_view_receipt_once_with_same_frozen_role(
    tmp_path,
    monkeypatch,
) -> None:
    class MissingOnceProvider(EcommerceRemoteBrainTestProvider):
        def __init__(self) -> None:
            super().__init__()
            self.finalizer_calls = 0

        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            if request.stage == "provider_prompt_finalize":
                self.finalizer_calls += 1
                if self.finalizer_calls == 1:
                    payload["canonical_provider_prompts"][0].pop(
                        "professional_anchor_view_decision",
                        None,
                    )
            return payload

    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    source = tmp_path / "root.png"
    Image.new("RGB", (640, 640), (170, 135, 120)).save(source)
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="profile"
    )
    provider = MissingOnceProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))

    result = runtime.plan_job(
        {
            "user_input": "Prepare one identity anchor from the frozen Professional plan.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_assets": [
                {
                    "asset_id": "root_doc165",
                    "role": "face_reference",
                    "file_path": str(source),
                    "use_policy": "identity",
                    "strength": "hard",
                }
            ],
            "metadata": {
                "project_id": "project_doc165",
                "requested_image_count": 1,
                "require_real_images": True,
                "professional_mode": True,
                "professional_anchor_pack_preparation": True,
                "professional_planning_metadata": planning,
            },
        }
    )

    assert result.status.value == "planned"
    assert provider.finalizer_calls == 2
    finalizers = [item for item in provider.requests if item["stage"] == "provider_prompt_finalize"]
    assert len(finalizers) == 2
    first_contract = finalizers[0]["metadata"]["canonical_prompt_context"][
        "professional_anchor_view_decision"
    ]
    second_contract = finalizers[1]["metadata"]["canonical_prompt_context"][
        "professional_anchor_view_decision"
    ]
    assert first_contract == second_contract
    assert first_contract["target_view_role"] == "profile"
    assert finalizers[1]["metadata"]["professional_anchor_view_contract_recovery"] == {
        "contract_version": "v3_professional_anchor_view_contract_recovery_v1",
        "attempt": 1,
        "same_frozen_context": True,
        "target_view_role": "profile",
    }
    audit = result.metadata["llm_brain"]["audit"]
    assert audit["professional_anchor_view_contract_recovery_attempted"] is True
    assert audit["professional_anchor_view_contract_recovery_succeeded"] is True
    assert audit["professional_anchor_view_decision_signed"] is True

