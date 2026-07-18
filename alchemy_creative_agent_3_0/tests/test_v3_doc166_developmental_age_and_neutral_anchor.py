"""Doc166: age coherence and neutral Professional anchors stay Brain-owned."""

from __future__ import annotations

import inspect
import json

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainDevelopmentalAgeDecisionMissing,
    BrainProfessionalAnchorViewDecisionMissing,
)
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.human_photorealism import (
    HUMAN_REALISM_REVIEW_DIMENSIONS,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _professional_identity_quality_contract,
)
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _human_guidance(user_input: str):
    return HumanPhotorealismLayer().build(
        project_id="project_doc166",
        job_id="job_doc166",
        scenario_id="general_creative",
        template_id="general_template",
        user_input=user_input,
        subject_type="person",
        variation_mode="single_hero",
        has_identity_reference=True,
        metadata={
            "brain_owned_forward_execution": True,
            "human_realism_execution_required": True,
            "frozen_rendering_intent": {
                "rendering_mode": "photoreal",
                "stylization_scope": "none",
                "decision_owner": "remote_brain",
            },
        },
    )


def _anchor_request(
    *,
    target_view_role: str = "standard_front",
    capture_presentation: str = "neutral_identity_evidence_capture",
    capture_continuity: str | None = None,
) -> BrainRunRequest:
    continuity = capture_continuity or (
        "establish_neutral_capture"
        if target_view_role == "standard_front"
        else "preserve_approved_prior_capture"
    )
    return BrainRunRequest(
        user_input="Prepare one identity anchor from the frozen Professional plan.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={
            "canonical_prompt_context": {
                "professional_anchor_view_decision": {
                    "required": True,
                    "contract_version": "v3_professional_anchor_view_decision_v3",
                    "owner": "remote_v3_llm_brain",
                    "target_view_role": target_view_role,
                    "capture_presentation": capture_presentation,
                    "capture_continuity": continuity,
                    "frozen_binding": {
                        "envelope_id": "opaque-envelope",
                        "ledger_id": "opaque-ledger",
                    },
                },
                "professional_face_identity_quality_contract": (
                    ProfessionalModeRuntimeBridge._face_identity_quality_contract(  # noqa: SLF001
                        neutral_capture=True
                    )
                ),
                "frozen_binding": {
                    "envelope_id": "opaque-envelope",
                    "ledger_id": "opaque-ledger",
                },
            }
        },
    )


def _age_owned_request() -> BrainRunRequest:
    return BrainRunRequest(
        user_input="Keep the same person and represent the current-request-owned developmental stage.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={
            "canonical_prompt_context": {
                "human_developmental_age_decision": {
                    "required": True,
                    "contract_version": "v3_human_developmental_age_decision_v2",
                    "age_fidelity": "follow_explicit_prompt",
                    "source_age_inheritance": "not_automatic_when_current_prompt_assigns_age",
                    "developmental_age_coherence": "whole_person_requested_stage",
                    "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
                    "owner": "remote_v3_llm_brain",
                    "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
                },
                "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
            }
        },
    )


def test_doc166_shared_contract_separates_developmental_age_from_identity() -> None:
    guidance = _human_guidance(
        "Keep the same person but represent them at approximately six years old in the current scene."
    )
    contract = guidance.semantic_contract
    serialized = json.dumps(contract, ensure_ascii=False).lower()

    assert contract["contract_version"] == "v3_human_realism_semantic_v8"
    assert contract["developmental_age_coherence_requirement"] == "whole_person_requested_stage"
    assert "human_developmental_age_coherence" in contract["quality_axes"]
    assert "human_age_or_identity_fidelity" in contract["quality_axes"]
    assert guidance.positive_prompt_fragments == []
    assert guidance.retry_patch_templates == {}
    for forbidden in ("baby fat", "rounder cheeks", "larger eyes", "whiten skin", "child teeth", "kidswear"):
        assert forbidden not in serialized


def test_doc166_age_resolution_transports_whole_person_obligation_without_recipe() -> None:
    resolved = ScenarioRuntime._human_realism_age_resolution(  # noqa: SLF001
        {
            "capability_projection": {
                "human_photorealism_guidance": {
                    "metadata": {
                        "human_realism_plugin": {
                            "universal_rendering_profile": {"age_fidelity": "follow_explicit_prompt"}
                        }
                    }
                }
            }
        }
    )

    assert resolved["age_fidelity"] == "follow_explicit_prompt"
    assert resolved["source_age_inheritance"] == "not_automatic_when_current_prompt_assigns_age"
    assert resolved["developmental_age_coherence"] == "whole_person_requested_stage"
    assert resolved["review_owner"] == "v3_shared_vision"
    assert "cheek" not in json.dumps(resolved, ensure_ascii=False).lower()


def test_doc166_professional_contract_declares_neutral_capture_without_renderer_recipe() -> None:
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(view_role="standard_front")
    contract = planning["professional_face_identity_quality_contract"]
    serialized = json.dumps(planning, ensure_ascii=False).lower()

    assert contract["contract_version"] == "professional_face_identity_quality_v2"
    assert contract["capture_presentation"] == "neutral_identity_evidence_capture"
    assert contract["developmental_age_coherence"] == "whole_person_when_age_owned"
    assert planning["professional_face_identity_quality_contract"] == contract
    for forbidden in ("white background", "business suit", "round cheek", "skin whitening", "baby fat"):
        assert forbidden not in serialized


def test_doc166_finalizer_requires_exact_neutral_capture_receipt() -> None:
    payload = json.loads(build_remote_payload(_anchor_request()))
    schema = payload["return_schema"]["canonical_provider_prompts"][0]

    assert schema["professional_anchor_view_decision"] == {
        "contract_version": "v3_professional_anchor_view_decision_v3",
        "target_view_role": "standard_front",
        "capture_presentation": "neutral_identity_evidence_capture",
        "capture_continuity": "establish_neutral_capture",
        "status": "approved|rewritten",
        "owner": "remote_v3_llm_brain",
    }
    assert "whole-person developmental stage" in payload["remote_response_contract"]
    assert "neutral identity-evidence capture" in payload["remote_response_contract"]
    assert "prior-view winner as evidence of the approved capture presentation" in payload["remote_response_contract"]
    assert "one unambiguous frozen viewpoint" in payload["remote_response_contract"]
    assert "append a correction" in payload["remote_response_contract"]


def test_doc166_serial_anchor_requires_prior_capture_continuity_receipt() -> None:
    payload = json.loads(build_remote_payload(_anchor_request(target_view_role="three_quarter")))
    schema = payload["return_schema"]["canonical_provider_prompts"][0]

    assert schema["professional_anchor_view_decision"]["capture_continuity"] == (
        "preserve_approved_prior_capture"
    )
    assert "selected prior-view winner to own the in-pack capture presentation" in (
        payload["remote_response_contract"]
    )
    assert "re-inheriting presentation from the identity root" in payload["remote_response_contract"]

    resign_request = _anchor_request(target_view_role="three_quarter").model_copy(
        update={
            "stage": "provider_prompt_professional_capture_resign",
            "metadata": {
                **_anchor_request(target_view_role="three_quarter").metadata,
                "candidate_canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": "A complete Brain-authored candidate that still needs serial capture verification.",
                        "review_status": "approved",
                    }
                ],
            },
        },
        deep=True,
    )
    resign_payload = json.loads(build_remote_payload(resign_request))
    assert resign_payload["stage"] == "provider_prompt_professional_capture_resign"
    assert "generic neutral" in resign_payload["remote_response_contract"].lower()
    assert resign_payload["candidate_canonical_provider_prompts"][0]["prompt"].startswith(
        "A complete Brain-authored candidate"
    )


def test_doc166_finalizer_requires_current_request_owned_age_receipt() -> None:
    payload = json.loads(build_remote_payload(_age_owned_request()))
    schema = payload["return_schema"]["canonical_provider_prompts"][0]

    assert schema["human_developmental_age_decision"] == {
        "contract_version": "v3_human_developmental_age_decision_v2",
        "age_fidelity": "follow_explicit_prompt",
        "source_age_inheritance": "not_automatic_when_current_prompt_assigns_age",
        "developmental_age_coherence": "whole_person_requested_stage",
        "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
        "status": "approved|rewritten",
        "owner": "remote_v3_llm_brain",
    }
    assert "source portrait remains identity evidence" in payload["remote_response_contract"]
    assert "merely repeats an age number or age label" in payload["remote_response_contract"]
    assert "independent observer who cannot read the prompt" in payload["remote_response_contract"]
    assert "do not append feature instructions" in payload["remote_response_contract"]


def test_doc166_runtime_carries_age_capture_and_view_to_one_brain_signoff(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    source = tmp_path / "identity-root.png"
    Image.new("RGB", (640, 640), (172, 138, 121)).save(source)
    brain = EcommerceRemoteBrainTestProvider(
        developmental_age_intent="current_request_assigns_stage"
    )
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain))

    result = runtime.plan_job(
        {
            "user_input": (
                "Keep this same person's recognizable identity, represent them at approximately six years old, "
                "and prepare the frozen neutral identity evidence view."
            ),
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_assets": [
                {
                    "asset_id": "root_doc166",
                    "role": "face_reference",
                    "file_path": str(source),
                    "use_policy": "identity",
                    "strength": "hard",
                }
            ],
            "metadata": {
                "project_id": "project_doc166_runtime",
                "requested_image_count": 1,
                "require_real_images": True,
                "professional_mode": True,
                "professional_anchor_pack_preparation": True,
                "professional_planning_metadata": (
                    ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
                        view_role="standard_front"
                    )
                ),
            },
        }
    )

    assert result.status.value == "planned"
    finalizer = [request for request in brain.requests if request["stage"] == "provider_prompt_finalize"][-1]
    context = finalizer["metadata"]["canonical_prompt_context"]
    assert context["reference_bindings"][0]["professional_anchor_lineage_role"] == "identity_root"
    assert context["human_realism_age_resolution"]["developmental_age_coherence"] == (
        "whole_person_requested_stage"
    )
    assert context["human_developmental_age_decision"]["source_age_inheritance"] == (
        "not_automatic_when_current_prompt_assigns_age"
    )
    assert context["professional_face_identity_quality_contract"]["capture_presentation"] == (
        "neutral_identity_evidence_capture"
    )
    assert context["professional_anchor_view_decision"] == {
        "required": True,
        "contract_version": "v3_professional_anchor_view_decision_v3",
        "owner": "remote_v3_llm_brain",
        "target_view_role": "standard_front",
        "capture_presentation": "neutral_identity_evidence_capture",
        "capture_continuity": "establish_neutral_capture",
        "frozen_binding": context["frozen_binding"],
    }
    audit = result.metadata["llm_brain"]["audit"]
    assert audit["professional_anchor_view_decisions"] == [
        {
            "contract_version": "v3_professional_anchor_view_decision_v3",
            "target_view_role": "standard_front",
            "capture_presentation": "neutral_identity_evidence_capture",
            "capture_continuity": "establish_neutral_capture",
            "status": "approved",
            "owner": "remote_v3_llm_brain",
        }
    ]
    assert audit["human_developmental_age_decision_signed"] is True
    assert audit["human_developmental_age_decisions"][0]["developmental_age_coherence"] == (
        "whole_person_requested_stage"
    )
    assert audit["human_developmental_age_resign_completed"] is True
    assert audit["canonical_provider_prompt_stages"] == [
        "provider_prompt_finalize",
        "provider_prompt_developmental_presence_verify",
    ]
    assert [request["stage"] for request in brain.requests] == [
        "plan",
        "provider_prompt_finalize",
        "provider_prompt_developmental_presence_verify",
    ]


def test_doc166_adapter_rejects_missing_developmental_age_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingAgeReceiptProvider:
        provider = "missing_age_receipt_fixture"
        model = "fixture"

        def available(self, *, force: bool = False) -> bool:
            return True

        def run(self, request) -> dict:  # noqa: ANN001
            return {
                "canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": "A complete remote-authored same-person developmental-stage direction.",
                        "review_status": "approved",
                    }
                ]
            }

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    adapter = V3LLMBrainAdapter(provider=MissingAgeReceiptProvider())
    with pytest.raises(BrainDevelopmentalAgeDecisionMissing):
        adapter.finalize_canonical_provider_prompts(_age_owned_request())


@pytest.mark.parametrize("receipt_capture", [None, "studio_beauty_portrait"])
def test_doc166_adapter_rejects_missing_or_mismatched_capture_receipt(
    monkeypatch: pytest.MonkeyPatch,
    receipt_capture: str | None,
) -> None:
    class InvalidCaptureProvider:
        provider = "invalid_capture_fixture"
        model = "fixture"

        def available(self, *, force: bool = False) -> bool:
            return True

        def run(self, request) -> dict:  # noqa: ANN001
            receipt = {
                "contract_version": "v3_professional_anchor_view_decision_v3",
                "target_view_role": "standard_front",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            }
            if receipt_capture is not None:
                receipt["capture_presentation"] = receipt_capture
            return {
                "canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": "A complete remote-authored Professional identity evidence direction.",
                        "review_status": "approved",
                        "professional_anchor_view_decision": receipt,
                    }
                ]
            }

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    adapter = V3LLMBrainAdapter(provider=InvalidCaptureProvider())
    with pytest.raises(BrainProfessionalAnchorViewDecisionMissing):
        adapter.finalize_canonical_provider_prompts(_anchor_request())


def test_doc166_shared_review_exposes_age_and_neutral_capture_separately() -> None:
    assert "human_developmental_age_coherence" in HUMAN_REALISM_REVIEW_DIMENSIONS
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(view_role="profile")
    contract = _professional_identity_quality_contract(
        {
            "professional_planning_metadata": planning,
            "capability_execution_envelope": {
                "envelope_id": "opaque",
                "activation_plan": {"metadata": {}},
            },
        },
        {"metadata": {}},
    )
    assert contract["applies"] is True
    assert "developmental_age_coherence" in contract["score_dimensions"]
    assert "developmental_facial_presence" in contract["score_dimensions"]
    assert "neutral_capture_compliance" in contract["score_dimensions"]
    assert "professional_developmental_age_drift" in contract["issue_codes"]
    assert "professional_developmental_presence_drift" in contract["issue_codes"]
    assert "professional_neutral_capture_mismatch" in contract["issue_codes"]


def test_doc166_runtime_and_professional_bridge_do_not_author_local_age_recipes() -> None:
    source = "\n".join(
        (
            inspect.getsource(ScenarioRuntime._human_realism_age_resolution),  # noqa: SLF001
            inspect.getsource(ProfessionalModeRuntimeBridge._face_identity_quality_contract),  # noqa: SLF001
            inspect.getsource(HumanPhotorealismLayer._activation),  # noqa: SLF001
        )
    ).lower()
    for forbidden in (
        "baby fat",
        "rounder cheeks",
        "larger eyes",
        "child teeth",
        "whiten skin",
        "prompt_suffix",
        "re.compile",
        "_has_explicit_age_direction",
        "year(?:s)?",
    ):
        assert forbidden not in source
