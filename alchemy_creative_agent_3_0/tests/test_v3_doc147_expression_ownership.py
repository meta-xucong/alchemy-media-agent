"""Doc147: shared expression ownership is Brain-owned and pixel-attested."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import SYSTEM_PROMPT, build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    GeneratedOutputResolution,
    HumanPhotorealismLayer,
    VisionOutputInspector,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.human_photorealism import (
    HUMAN_REALISM_REVIEW_DIMENSIONS,
    normalize_human_realism_issue_code,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.plugins.base import VisualPluginContext
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.plugins.human_realism import HumanRealismPlugin
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
    active_review_contract,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


class _StaticVisionProvider:
    provider_name = "doc147_static_vision"

    def available(self, *, force: bool = False) -> bool:  # noqa: ARG002
        return True

    def inspect(self, resolution, *, metadata=None):  # noqa: ANN001, ARG002
        return {
            "status": "fail_retryable",
            "confidence": 0.93,
            "issue_codes": ["human_expression_context"],
            "human_naturalness_verdict": {
                "status": "retry_recommended",
                "issue_codes": ["human_expression_context"],
            },
        }


class _SituationOwnedResigner(EcommerceRemoteBrainTestProvider):
    """The test double supplies complete rewrites as the remote Brain."""

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage == "provider_prompt_finalize":
            payload["canonical_provider_prompts"][0]["prompt"] = (
                "A real-camera photograph of a person pausing to listen beside an open window at home, "
                "their expression belonging to the quiet moment and requested daylight."
            )
            payload["canonical_provider_prompts"][0]["human_naturalness_decision"] = {
                "contract_version": "v3_human_naturalness_decision_v1",
                "status": "rewritten",
                "owner": "remote_v3_llm_brain",
            }
        elif request.stage == "provider_prompt_human_naturalness_resign":
            payload["canonical_provider_prompts"][0]["prompt"] = (
                "A real-camera photograph of a person pausing to listen beside an open window at home, "
                "their expression belonging to the quiet moment and requested daylight."
            )
            payload["canonical_provider_prompts"][0]["human_naturalness_decision"] = {
                "contract_version": "v3_human_naturalness_decision_v1",
                "status": "rewritten",
                "owner": "remote_v3_llm_brain",
            }
        else:
            payload["canonical_provider_prompts"][0]["prompt"] = (
                "A real-camera photograph of a person pausing to listen beside an open window at home, "
                "their expression belonging to the quiet moment and requested daylight."
            )
            payload["canonical_provider_prompts"][0]["human_naturalness_decision"] = {
                "contract_version": "v3_human_naturalness_decision_v1",
                "status": "rewritten",
                "owner": "remote_v3_llm_brain",
            }
        return payload


def _guidance(user_input: str, *, subject_type: str = "person") -> dict:
    return HumanPhotorealismLayer().build(
        project_id="project_doc147",
        job_id="job_doc147",
        scenario_id="general_creative",
        template_id="general_template",
        user_input=user_input,
        subject_type=subject_type,
        variation_mode="single_hero",
        has_identity_reference=False,
        metadata={
            "brain_owned_forward_execution": True,
            "human_realism_execution_required": True,
            "frozen_rendering_intent": {
                "rendering_mode": "photoreal",
                "stylization_scope": "none",
                "decision_owner": "remote_brain",
            },
        },
    ).model_dump(mode="json")


def _plan_metadata() -> dict:
    result = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())
    ).plan_job(
        {
            "user_input": "Create a real-camera photograph of a visible adult person reading beside a window at home.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )
    assert result.status.value == "planned"
    return dict(result.metadata)


def _resolution(tmp_path: Path) -> GeneratedOutputResolution:
    from PIL import Image

    path = tmp_path / "doc147.png"
    image = Image.new("RGB", (96, 128), color=(138, 156, 172))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    path.write_bytes(buffer.getvalue())
    return GeneratedOutputResolution(
        resolution_id="resolution_doc147",
        project_id="project_doc147",
        job_id="job_doc147",
        candidate_id="candidate_doc147",
        asset_id="asset_doc147",
        output_id="output_doc147",
        file_path=str(path),
        mime_type="image/png",
        width=96,
        height=128,
        status="ready",
    )


def test_doc147_freezes_one_shared_expression_requirement_across_person_contexts() -> None:
    contexts = (
        "A real-camera portrait of an adult ceramic artist at work.",
        "A real-camera photograph of a young person walking through an ordinary garden.",
        "A real-camera photograph of a person carefully holding a handmade object.",
        "A low-key real-camera portrait of a person in a quiet evening room.",
    )

    for context in contexts:
        contract = _guidance(context)["semantic_contract"]
        assert contract["contract_version"] == "v3_human_realism_semantic_v6"
        assert contract["expression_ownership_requirement"] == "situation_owned_unless_explicit_user_direction"
        assert "human_expression_context" in contract["quality_axes"]
        assert "smile" not in json.dumps(contract, ensure_ascii=False).lower()
        assert "child" not in json.dumps(contract, ensure_ascii=False).lower()


def test_doc147_detail_scope_does_not_pretend_an_absent_face_has_expression() -> None:
    contract = HumanPhotorealismLayer._semantic_contract(  # noqa: SLF001
        activation={},
        human_subject_kind="hand_or_skin_detail",
        review_targets=["human_anatomy_or_proportion", "human_skin_or_retouch"],
    )

    assert contract["expression_ownership_requirement"] == "not_applicable"
    assert "human_expression_context" not in contract["quality_axes"]

    contribution = HumanRealismPlugin().contribute(
        VisualPluginContext(
            plan=SimpleNamespace(plan_id="plan_doc147_detail"),
            active=SimpleNamespace(
                capability_id="human_realism",
                version="v1",
                selected_profile="balanced",
            ),
            cluster={
                "human_photorealism_guidance": {
                    "applies": True,
                    "semantic_contract": contract,
                    "metadata": {"human_realism_plugin": {"human_subject_kind": "hand_or_skin_detail"}},
                }
            },
        )
    )
    assert "human_expression_context" not in contribution.review_contract["issue_codes"]
    assert contribution.review_contract["human_naturalness_verdict_required"] is False


def test_doc147_enforced_review_receives_the_frozen_generic_expression_contract() -> None:
    metadata = _plan_metadata()
    contract = active_review_contract(metadata)
    prompt = _inspection_prompt(metadata)

    assert contract["human_authenticity_contract"] == {
        "contract_version": "v3_human_realism_semantic_v6",
        "personhood_requirement": "individual_noninterchangeable_presence",
        "expression_ownership_requirement": "situation_owned_unless_explicit_user_direction",
        "expression_resolution_requirement": "individual_situation_not_stock_geometry",
        "complexion_rendering_requirement": "preserve_reference_or_user_owned_complexion_with_scene_balanced_color",
        "photographic_material_requirement": "camera_observed_human_materiality",
    }
    assert "human_expression_context" in contract["issue_codes"]
    assert "situation-owned expression" in prompt
    for legacy in ("template_smile", "perfect_smile_repetition", "frozen_child_smile"):
        assert legacy not in prompt


def test_doc147_expression_review_is_normalized_evidence_not_renderer_prose(tmp_path: Path) -> None:
    metadata = _plan_metadata()
    metadata["vision_inspection_mode"] = "vision_model"
    report = VisionOutputInspector(vision_provider=_StaticVisionProvider()).inspect(
        _resolution(tmp_path), metadata=metadata
    )

    assert report.status == "fail_retryable"
    assert [item["code"] for item in report.detected_issues] == ["human_expression_context"]
    assert report.retry_patch == {}
    assert report.evidence["human_naturalness_attestation"] == {
        "required": True,
        "status": "retry_recommended",
        "issue_codes": ["human_expression_context"],
    }


def test_doc147_remote_brain_rewrites_the_whole_prompt_without_a_local_expression_recipe() -> None:
    provider = _SituationOwnedResigner()
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        {
            "user_input": "Create a candid real-camera photograph of a visible adult person reading beside a window at home.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    finalizer = next(item for item in provider.requests if item["stage"] == "provider_prompt_finalize")
    payload = json.loads(build_remote_payload(BrainRunRequest.model_validate(finalizer)))
    assert payload["frozen_render_context"]["active_semantic_capability_contracts"][0][
        "expression_ownership_requirement"
    ] == "situation_owned_unless_explicit_user_direction"
    assert "expression_ownership_requirement" in SYSTEM_PROMPT
    assert "fixed alternate-expression catalogue" in SYSTEM_PROMPT
    assert "absent expression as intentional creative latitude" in SYSTEM_PROMPT
    assert "setting pleasantness or commercial polish alone" in SYSTEM_PROMPT
    assert "plus a static pose is not an expression decision" in SYSTEM_PROMPT
    assert "static pose does not resolve the person's attention or ordinary response" in SYSTEM_PROMPT
    assert "static pose does not by itself resolve the person's attention or ordinary response" in payload[
        "remote_response_contract"
    ]
    assert "prompt_additions" not in json.dumps(payload, ensure_ascii=False)
    assert result.metadata["llm_brain"]["canonical_provider_prompts"][0]["prompt"].startswith(
        "A real-camera photograph of a person pausing to listen"
    )


def test_doc147_legacy_smile_labels_collapse_to_the_shared_dimension_only() -> None:
    assert "human_expression_context" in HUMAN_REALISM_REVIEW_DIMENSIONS
    for legacy in ("template_smile", "perfect_smile_repetition", "frozen_child_smile"):
        assert normalize_human_realism_issue_code(legacy) == "human_expression_context"
