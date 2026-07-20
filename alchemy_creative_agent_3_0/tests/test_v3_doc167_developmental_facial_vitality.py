"""Doc167: developmental facial vitality stays shared, semantic and Brain-owned."""

from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router import ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import SYSTEM_PROMPT, build_remote_payload
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainDevelopmentalAgeDecisionMissing,
    BrainDevelopmentalPresenceDecisionMissing,
)
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    HUMAN_DEVELOPMENTAL_PRESENCE_REVIEW_INSTRUCTIONS,
    _professional_identity_quality_contract,
)
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider
from services.alchemy_codex_local_adapter.contracts import NativeImageGenPlanRequest
from services.alchemy_codex_local_adapter.native_planner import CodexNativeImageGenPlanner


_PRESENCE_REQUIREMENT = "integrated_stage_coherent_face_attention_and_affect"


def _guidance(*, human_subject_kind: str = "person"):
    return HumanPhotorealismLayer._semantic_contract(  # noqa: SLF001
        activation={},
        human_subject_kind=human_subject_kind,
        review_targets=[
            "human_age_or_identity_fidelity",
            "human_developmental_age_coherence",
            "human_expression_context",
        ],
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
                    "developmental_presence": _PRESENCE_REQUIREMENT,
                    "owner": "remote_v3_llm_brain",
                    "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
                },
                "human_developmental_presence_decision": {
                    "required": True,
                    "contract_version": "v3_human_developmental_presence_decision_v2",
                    "developmental_presence": _PRESENCE_REQUIREMENT,
                    "resolution_mode": (
                        "holistic_person_and_situation_resolution"
                    ),
                    "owner": "remote_v3_llm_brain",
                    "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
                },
                "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
            }
        },
    )


def test_doc167_shared_contract_adds_one_indivisible_age_general_presence_obligation() -> None:
    contract = _guidance()
    serialized = json.dumps(contract, ensure_ascii=False).lower()

    assert contract["contract_version"] == "v3_human_realism_semantic_v8"
    assert contract["developmental_presence_requirement"] == _PRESENCE_REQUIREMENT
    assert contract["developmental_age_coherence_requirement"] == "whole_person_requested_stage"
    for forbidden in (
        "baby fat",
        "round face",
        "larger eyes",
        "visible teeth",
        "child smile",
        "kidswear",
    ):
        assert forbidden not in serialized


def test_doc167_non_age_bearing_detail_is_not_given_a_facial_presence_contract() -> None:
    contract = _guidance(human_subject_kind="hand_or_skin_detail")
    assert contract["developmental_presence_requirement"] == "not_applicable"


def test_doc167_brain_receipt_requires_integrated_developmental_presence() -> None:
    payload = json.loads(build_remote_payload(_age_owned_request()))
    schema = payload["return_schema"]["canonical_provider_prompts"][0]

    assert schema["human_developmental_age_decision"] == {
        "contract_version": "v3_human_developmental_age_decision_v2",
        "age_fidelity": "follow_explicit_prompt",
        "source_age_inheritance": "not_automatic_when_current_prompt_assigns_age",
        "developmental_age_coherence": "whole_person_requested_stage",
        "developmental_presence": _PRESENCE_REQUIREMENT,
        "status": "approved|rewritten",
        "owner": "remote_v3_llm_brain",
    }
    assert schema["human_developmental_presence_decision"] == {
        "contract_version": "v3_human_developmental_presence_decision_v2",
        "developmental_presence": _PRESENCE_REQUIREMENT,
        "resolution_mode": (
            "holistic_person_and_situation_resolution"
        ),
        "status": "approved|rewritten",
        "owner": "remote_v3_llm_brain",
    }
    contract = payload["remote_response_contract"]
    assert "do not explain or manufacture the stage through inferred facial morphology" in contract
    assert "A stated stage remains valid renderer language" in contract
    assert "complete person and situation" in contract
    assert "facial measurement" in contract
    assert "developmental_presence_requirement" in SYSTEM_PROMPT


def test_doc167_brain_owns_explicit_stage_assignment_without_source_age_estimation() -> None:
    assert "an explicit instruction not to inherit the source's apparent stage" in SYSTEM_PROMPT
    assert "even when the source stage is unknown or happens to look similar" in SYSTEM_PROMPT
    assert "keyword matching" in SYSTEM_PROMPT


def test_doc167_historical_age_transition_verifier_payload_remains_readable() -> None:
    request = _age_owned_request().model_copy(
        update={
            "stage": "provider_prompt_developmental_presence_verify",
            "metadata": {
                **_age_owned_request().metadata,
                "canonical_prompt_context": {
                    **_age_owned_request().metadata["canonical_prompt_context"],
                    "final_prompt_semantic_preflight": {
                        "required": True,
                        "scope": "whole_image_human_photographic_plausibility",
                        "owner": "remote_v3_llm_brain",
                        "revision_mode": "rewrite_complete_canonical_prompt",
                    },
                    "human_naturalness_decision": {
                        "required": True,
                        "contract_version": "v3_human_naturalness_decision_v1",
                        "owner": "remote_v3_llm_brain",
                        "frozen_binding": {"envelope_id": "opaque-envelope", "ledger_id": "opaque-ledger"},
                    },
                },
                "candidate_canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": "A complete but non-authoritative candidate portrait direction for the requested person.",
                    }
                ],
            },
        },
        deep=True,
    )
    payload = json.loads(build_remote_payload(request))

    assert payload["stage"] == "provider_prompt_developmental_presence_verify"
    assert payload["candidate_canonical_provider_prompts"][0]["prompt"].startswith(
        "A complete but non-authoritative"
    )
    contract = payload["remote_response_contract"]
    assert "candidate wording is not authoritative" in contract
    assert "integrated perceptual outcome" in contract
    assert "never a local patch" in contract
    source = inspect.getsource(ScenarioRuntime._finalize_canonical_provider_prompts).lower()  # noqa: SLF001
    assert "re.compile" not in source
    assert "prompt suffix" not in source


def test_doc167_adapter_rejects_legacy_receipt_for_fresh_v2_requirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class LegacyReceiptProvider:
        provider = "legacy_age_receipt_fixture"
        model = "fixture"

        def available(self, *, force: bool = False) -> bool:  # noqa: ARG002
            return True

        def run(self, request):  # noqa: ANN001, ARG002
            return {
                "canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": "A complete remote-authored developmental-stage portrait direction.",
                        "review_status": "approved",
                        "human_developmental_age_decision": {
                            "contract_version": "v3_human_developmental_age_decision_v1",
                            "age_fidelity": "follow_explicit_prompt",
                            "source_age_inheritance": "not_automatic_when_current_prompt_assigns_age",
                            "developmental_age_coherence": "whole_person_requested_stage",
                            "status": "approved",
                            "owner": "remote_v3_llm_brain",
                        },
                    }
                ]
            }

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    adapter = V3LLMBrainAdapter(provider=LegacyReceiptProvider())
    with pytest.raises(BrainDevelopmentalAgeDecisionMissing):
        adapter.finalize_canonical_provider_prompts(_age_owned_request())


def test_doc167_adapter_rejects_missing_presence_receipt_for_fresh_full_person(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingPresenceProvider:
        provider = "missing_presence_receipt_fixture"
        model = "fixture"

        def available(self, *, force: bool = False) -> bool:  # noqa: ARG002
            return True

        def run(self, request):  # noqa: ANN001, ARG002
            return {
                "canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": "A complete remote-authored developmental-stage portrait direction.",
                        "review_status": "approved",
                        "human_developmental_age_decision": {
                            "contract_version": "v3_human_developmental_age_decision_v2",
                            "age_fidelity": "follow_explicit_prompt",
                            "source_age_inheritance": "not_automatic_when_current_prompt_assigns_age",
                            "developmental_age_coherence": "whole_person_requested_stage",
                            "developmental_presence": _PRESENCE_REQUIREMENT,
                            "status": "approved",
                            "owner": "remote_v3_llm_brain",
                        },
                    }
                ]
            }

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    adapter = V3LLMBrainAdapter(provider=MissingPresenceProvider())
    with pytest.raises(BrainDevelopmentalPresenceDecisionMissing):
        adapter.finalize_canonical_provider_prompts(_age_owned_request())


def test_doc167_professional_review_exposes_presence_without_a_child_reviewer() -> None:
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(view_role="standard_front")
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

    assert "developmental_facial_presence" in contract["score_dimensions"]
    assert "professional_developmental_presence_drift" in contract["issue_codes"]
    assert "stage-coherent facial presence" in HUMAN_DEVELOPMENTAL_PRESENCE_REVIEW_INSTRUCTIONS
    assert "round face" in HUMAN_DEVELOPMENTAL_PRESENCE_REVIEW_INSTRUCTIONS
    assert "must not require" in HUMAN_DEVELOPMENTAL_PRESENCE_REVIEW_INSTRUCTIONS


def test_doc167_runtime_contract_path_contains_no_local_child_face_recipe() -> None:
    source = "\n".join(
        (
            inspect.getsource(HumanPhotorealismLayer._semantic_contract),  # noqa: SLF001
            inspect.getsource(ScenarioRuntime._human_realism_age_resolution),  # noqa: SLF001
        )
    ).lower()
    for forbidden in (
        "baby fat",
        "round face",
        "big eyes",
        "child teeth",
        "innocent gaze",
        "prompt suffix",
        "re.compile",
    ):
        assert forbidden not in source


def test_doc167_same_stage_person_uses_one_combined_finalizer_without_extra_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class PresenceResigner(EcommerceRemoteBrainTestProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            if request.stage == "provider_prompt_finalize":
                payload["canonical_provider_prompts"][0]["prompt"] = (
                    "A real-camera portrait in which this particular six-year-old quietly notices the photographer, "
                    "her resting facial fullness, attentive gaze and small unperformed mouth response reading together "
                    "as one ordinary person at the requested stage in soft window light."
                )
                payload["canonical_provider_prompts"][0][
                    "human_developmental_presence_decision"
                ]["status"] = "rewritten"
            return payload

    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = PresenceResigner(developmental_age_intent="preserve_reference_stage")
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        {
            "user_input": (
                "Create a real-camera portrait of the same approximately six-year-old person, "
                "quietly attentive in an ordinary bright studio."
            ),
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    assert [item["stage"] for item in provider.requests] == [
        "plan",
        "provider_prompt_finalize",
    ]
    audit = result.metadata["llm_brain"]["audit"]
    assert audit.get("human_developmental_age_resign_required") is not True
    assert audit["human_developmental_presence_decision_required"] is True
    assert audit["human_developmental_presence_decision_signed"] is True
    assert audit["human_developmental_presence_decisions"] == [
        {
            "contract_version": "v3_human_developmental_presence_decision_v2",
            "developmental_presence": _PRESENCE_REQUIREMENT,
            "resolution_mode": (
                "holistic_person_and_situation_resolution"
            ),
            "status": "rewritten",
            "owner": "remote_v3_llm_brain",
        }
    ]
    final_prompt = result.metadata["llm_brain"]["canonical_provider_prompts"][0]["prompt"]
    assert "one ordinary person at the requested stage" in final_prompt
    assert "child-appropriate features and proportions" not in final_prompt


def _native_identity_plan(
    *,
    source,
    developmental_age_intent: str,
    user_input: str,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict, EcommerceRemoteBrainTestProvider]:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    brain = EcommerceRemoteBrainTestProvider(
        developmental_age_intent=developmental_age_intent,
    )
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: ScenarioRuntime(
            llm_brain_adapter=V3LLMBrainAdapter(provider=brain),
        )
    )
    result = planner.prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(
            {
                "user_input": user_input,
                "template_id": "general_template",
                "requested_image_count": 1,
                "requested_image_size": "1024x1536",
                "reference_inputs": [
                    {"channel": "portrait_identity", "file_path": str(source)}
                ],
            }
        )
    )
    return result, brain


def test_doc167_explicit_cross_stage_identity_uses_stage_flexible_feature_evidence(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "uploaded-identity.png"
    Image.new("RGB", (720, 960), (184, 151, 132)).save(source)

    result, brain = _native_identity_plan(
        source=source,
        developmental_age_intent="current_request_assigns_stage",
        user_input=(
            "Keep the same person's recognizable identity, represent the person at the explicitly requested "
            "developmental stage, do not inherit the source's apparent stage, and create one clean real-camera portrait."
        ),
        monkeypatch=monkeypatch,
    )

    assert result["status"] == "planned_for_codex_native_imagegen"
    output = result["outputs"][0]
    assert len(output["reference_image_paths"]) == 1
    assert "portrait_identity_stage_flexible_feature_crop" in output["reference_image_paths"][0]
    assert "portrait_identity_geometry_crop" not in output["reference_image_paths"][0]
    assert output["reference_input_contract"]["admitted_reference_count"] == 1
    assert result["provenance"]["canonical_prompt_signing"]["stages"] == ["provider_prompt_finalize"]
    assert [item["stage"] for item in brain.requests] == [
        "plan",
        "provider_prompt_finalize",
    ]


def test_doc167_same_stage_identity_keeps_doc95_complementary_evidence(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "same-stage-identity.png"
    Image.new("RGB", (720, 960), (184, 151, 132)).save(source)

    result, _ = _native_identity_plan(
        source=source,
        developmental_age_intent="preserve_reference_stage",
        user_input=(
            "Keep this same person's identity and current developmental stage in one clean real-camera portrait."
        ),
        monkeypatch=monkeypatch,
    )

    assert result["status"] == "planned_for_codex_native_imagegen"
    paths = result["outputs"][0]["reference_image_paths"]
    assert len(paths) == 2
    assert any("portrait_identity_crop" in path for path in paths)
    assert any("portrait_identity_geometry_crop" in path for path in paths)


def test_doc167_professional_anchor_contract_is_not_reduced_by_cross_stage_profile() -> None:
    materializer = ProductionImageGenerationProvider(output_store=object())
    uploaded_root = {
        "asset_id": "v3_asset_professional_root",
        "source_type": "uploaded",
        "output_id": None,
    }

    initial = SimpleNamespace(
        metadata={"professional_anchor_pack_preparation": True},
    )
    assert materializer._portrait_identity_derivative_kinds(initial, uploaded_root) is None  # noqa: SLF001

    supplementary = SimpleNamespace(
        metadata={
            "professional_anchor_pack_preparation": True,
            "professional_identity_reference_strategy": "serial_anchor_pack_root_reuse_v1",
            "professional_reference_stage": "three_quarter",
        },
    )
    assert materializer._portrait_identity_derivative_kinds(  # noqa: SLF001
        supplementary,
        uploaded_root,
    ) == ("portrait_identity_pose_geometry_crop",)


def test_doc167_cross_stage_evidence_policy_contains_no_face_recipe_or_prompt_authoring() -> None:
    source = inspect.getsource(
        ProductionImageGenerationProvider._portrait_identity_derivative_kinds  # noqa: SLF001
    ).lower()
    for forbidden in (
        "kidswear",
        "baby fat",
        "big eyes",
        "teeth",
        "smile",
        "re.compile",
        "prompt suffix",
    ):
        assert forbidden not in source
