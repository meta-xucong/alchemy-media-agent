"""Doc148: shared complexion balance is Brain-owned and pixel-attested."""

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
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.plugins.base import VisualPluginContext
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.plugins.human_realism import HumanRealismPlugin
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
    active_review_contract,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


class _StaticVisionProvider:
    provider_name = "doc148_static_vision"

    def available(self, *, force: bool = False) -> bool:  # noqa: ARG002
        return True

    def inspect(self, resolution, *, metadata=None):  # noqa: ANN001, ARG002
        return {
            "status": "fail_retryable",
            "confidence": 0.93,
            "issue_codes": ["human_skin_or_retouch"],
            "human_naturalness_verdict": {
                "status": "retry_recommended",
                "issue_codes": ["human_skin_or_retouch"],
            },
        }


class _SceneBalancedResigner(EcommerceRemoteBrainTestProvider):
    """The remote test double proves a whole-direction rewrite remains remote-owned."""

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage == "provider_prompt_finalize":
            payload["canonical_provider_prompts"][0]["prompt"] = (
                "A real-camera photograph of a person in their ordinary sunlit room, "
                "with their natural complexion reading clearly within the scene's balanced daylight "
                "and the requested calm domestic mood."
            )
            payload["canonical_provider_prompts"][0]["human_naturalness_decision"] = {
                "contract_version": "v3_human_naturalness_decision_v1",
                "status": "rewritten",
                "owner": "remote_v3_llm_brain",
            }
        return payload


def _guidance(user_input: str, *, subject_type: str = "person") -> dict:
    return HumanPhotorealismLayer().build(
        project_id="project_doc148",
        job_id="job_doc148",
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
            "user_input": "Create a natural real-camera photograph of a visible adult person in an ordinary room.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )
    assert result.status.value == "planned"
    return dict(result.metadata)


def _resolution(tmp_path: Path) -> GeneratedOutputResolution:
    from PIL import Image

    path = tmp_path / "doc148.png"
    image = Image.new("RGB", (96, 128), color=(138, 156, 172))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    path.write_bytes(buffer.getvalue())
    return GeneratedOutputResolution(
        resolution_id="resolution_doc148",
        project_id="project_doc148",
        job_id="job_doc148",
        candidate_id="candidate_doc148",
        asset_id="asset_doc148",
        output_id="output_doc148",
        file_path=str(path),
        mime_type="image/png",
        width=96,
        height=128,
        status="ready",
    )


def test_doc148_freezes_one_generic_complexion_requirement_across_contexts() -> None:
    contexts = (
        "A real-camera portrait of an adult ceramic artist at work.",
        "A real-camera photograph of a young person walking through an ordinary garden.",
        "A real-camera photograph of a person carefully holding a handmade object.",
        "A low-key real-camera portrait of a person in a quiet evening room.",
    )

    for context in contexts:
        contract = _guidance(context)["semantic_contract"]
        serialized = json.dumps(contract, ensure_ascii=False).lower()
        assert contract["contract_version"] == "v3_human_realism_semantic_v7"
        assert contract["complexion_rendering_requirement"] == (
            "preserve_reference_or_user_owned_complexion_with_scene_balanced_color"
        )
        assert "child" not in serialized
        assert "palette" not in serialized
        assert "prompt_additions" not in serialized


def test_doc148_detail_scope_keeps_complexion_without_personhood_or_expression() -> None:
    contract = HumanPhotorealismLayer._semantic_contract(  # noqa: SLF001
        activation={},
        human_subject_kind="hand_or_skin_detail",
        review_targets=["human_anatomy_or_proportion", "human_skin_or_retouch"],
    )
    contribution = HumanRealismPlugin().contribute(
        VisualPluginContext(
            plan=SimpleNamespace(plan_id="plan_doc148_detail"),
            active=SimpleNamespace(capability_id="human_realism", version="v1", selected_profile="balanced"),
            cluster={
                "human_photorealism_guidance": {
                    "applies": True,
                    "semantic_contract": contract,
                    "metadata": {"human_realism_plugin": {"human_subject_kind": "hand_or_skin_detail"}},
                }
            },
        )
    )

    assert contract["personhood_requirement"] == "not_applicable"
    assert contract["expression_ownership_requirement"] == "not_applicable"
    assert contract["complexion_rendering_requirement"] == (
        "preserve_reference_or_user_owned_complexion_with_scene_balanced_color"
    )
    assert "human_skin_or_retouch" in contribution.review_contract["issue_codes"]
    assert contribution.review_contract["human_naturalness_verdict_required"] is False


def test_doc148_enforced_reviewer_receives_the_frozen_complexion_contract() -> None:
    metadata = _plan_metadata()
    contract = active_review_contract(metadata)
    prompt = _inspection_prompt(metadata)

    assert contract["human_authenticity_contract"] == {
        "contract_version": "v3_human_realism_semantic_v7",
        "developmental_age_coherence_requirement": "whole_person_requested_stage",
        "personhood_requirement": "individual_noninterchangeable_presence",
        "expression_ownership_requirement": "situation_owned_unless_explicit_user_direction",
        "expression_resolution_requirement": "individual_situation_not_stock_geometry",
        "complexion_rendering_requirement": "preserve_reference_or_user_owned_complexion_with_scene_balanced_color",
        "photographic_material_requirement": "camera_observed_human_materiality",
    }
    assert "human_skin_or_retouch" in contract["issue_codes"]
    assert "complexion and scene-balanced color" in prompt
    assert "plastic_skin" not in prompt


def test_doc148_complexion_review_is_generic_evidence_not_renderer_prose(tmp_path: Path) -> None:
    metadata = _plan_metadata()
    metadata["vision_inspection_mode"] = "vision_model"
    report = VisionOutputInspector(vision_provider=_StaticVisionProvider()).inspect(
        _resolution(tmp_path), metadata=metadata
    )

    assert report.status == "fail_retryable"
    assert [item["code"] for item in report.detected_issues] == ["human_skin_or_retouch"]
    assert report.retry_patch == {}
    assert report.evidence["human_naturalness_attestation"] == {
        "required": True,
        "status": "retry_recommended",
        "issue_codes": ["human_skin_or_retouch"],
    }


def test_doc148_remote_brain_rewrites_the_whole_direction_for_scene_balance() -> None:
    provider = _SceneBalancedResigner()
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        {
            "user_input": "Create a candid real-camera photograph of a visible adult person in an ordinary sunlit room.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    finalizer = next(item for item in provider.requests if item["stage"] == "provider_prompt_finalize")
    payload = json.loads(build_remote_payload(BrainRunRequest.model_validate(finalizer)))
    frozen_contract = payload["frozen_render_context"]["active_semantic_capability_contracts"][0]
    assert frozen_contract["complexion_rendering_requirement"] == (
        "preserve_reference_or_user_owned_complexion_with_scene_balanced_color"
    )
    assert "complexion_rendering_requirement" in SYSTEM_PROMPT
    assert "prompt_additions" not in json.dumps(payload, ensure_ascii=False)
    assert "candidate_canonical_provider_prompts" not in payload
    assert result.metadata["llm_brain"]["canonical_provider_prompts"][0]["prompt"].startswith(
        "A real-camera photograph of a person in their ordinary sunlit room"
    )
