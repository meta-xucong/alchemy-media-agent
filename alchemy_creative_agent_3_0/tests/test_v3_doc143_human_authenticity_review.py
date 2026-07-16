"""Doc143: shared personhood and photographic-material review closure."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    GeneratedOutputResolution,
    HumanPhotorealismLayer,
    VisionOutputInspector,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
    active_review_contract,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


class _StaticVisionProvider:
    provider_name = "doc143_static_vision"

    def __init__(self, payload: dict) -> None:
        self.payload = dict(payload)

    def available(self, *, force: bool = False) -> bool:  # noqa: ARG002
        return True

    def inspect(self, resolution, *, metadata=None):  # noqa: ANN001, ARG002
        return dict(self.payload)


def _guidance() -> dict:
    return HumanPhotorealismLayer().build(
        project_id="project_doc143",
        job_id="job_doc143",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="Create a real-camera photograph of a visible person in an ordinary setting.",
        subject_type="person",
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

    path = tmp_path / "doc143.png"
    image = Image.new("RGB", (96, 128), color=(138, 156, 172))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    path.write_bytes(buffer.getvalue())
    return GeneratedOutputResolution(
        resolution_id="resolution_doc143",
        project_id="project_doc143",
        job_id="job_doc143",
        candidate_id="candidate_doc143",
        asset_id="asset_doc143",
        output_id="output_doc143",
        file_path=str(path),
        mime_type="image/png",
        width=96,
        height=128,
        status="ready",
    )


def test_doc143_fresh_human_contract_has_only_generic_authenticity_obligations() -> None:
    contract = _guidance()["semantic_contract"]

    assert contract["contract_version"] == "v3_human_realism_semantic_v5"
    assert contract["personhood_requirement"] == "individual_noninterchangeable_presence"
    assert contract["expression_ownership_requirement"] == "situation_owned_unless_explicit_user_direction"
    assert contract["complexion_rendering_requirement"] == (
        "preserve_reference_or_user_owned_complexion_with_scene_balanced_color"
    )
    assert contract["photographic_material_requirement"] == "camera_observed_human_materiality"
    assert "child" not in str(contract).lower()
    assert "prompt_additions" not in str(contract).lower()


def test_doc143_enforced_reviewer_receives_frozen_authenticity_contract_not_legacy_catalogue() -> None:
    metadata = _plan_metadata()
    contract = active_review_contract(metadata)
    prompt = _inspection_prompt(metadata)

    assert contract["human_naturalness_verdict_required"] is True
    assert contract["human_authenticity_contract"] == {
        "contract_version": "v3_human_realism_semantic_v5",
        "personhood_requirement": "individual_noninterchangeable_presence",
        "expression_ownership_requirement": "situation_owned_unless_explicit_user_direction",
        "complexion_rendering_requirement": "preserve_reference_or_user_owned_complexion_with_scene_balanced_color",
        "photographic_material_requirement": "camera_observed_human_materiality",
    }
    assert "human_naturalness_verdict" in prompt
    assert "individual_noninterchangeable_presence" in prompt
    assert "situation_owned_unless_explicit_user_direction" in prompt
    assert "camera_observed_human_materiality" in prompt
    assert "frozen_child_smile" not in prompt
    assert "plastic_skin" not in prompt


def test_doc143_missing_pixel_attestation_withholds_certification(tmp_path: Path) -> None:
    metadata = _plan_metadata()
    metadata["vision_inspection_mode"] = "vision_model"
    report = VisionOutputInspector(
        vision_provider=_StaticVisionProvider(
            {"status": "pass", "confidence": 0.94, "issue_codes": []}
        )
    ).inspect(_resolution(tmp_path), metadata=metadata)

    assert report.status == "manual_review"
    assert report.retryable is False
    assert report.evidence["human_naturalness_attestation"]["status"] == "missing"


def test_doc143_generic_retry_attestation_is_review_evidence_not_renderer_prose(tmp_path: Path) -> None:
    metadata = _plan_metadata()
    metadata["vision_inspection_mode"] = "vision_model"
    report = VisionOutputInspector(
        vision_provider=_StaticVisionProvider(
            {
                "status": "fail_retryable",
                "confidence": 0.94,
                "issue_codes": ["human_rendering_artifact"],
                "human_naturalness_verdict": {
                    "status": "retry_recommended",
                    "issue_codes": ["human_rendering_artifact"],
                },
            }
        )
    ).inspect(_resolution(tmp_path), metadata=metadata)

    assert report.status == "fail_retryable"
    assert [item["code"] for item in report.detected_issues] == ["human_rendering_artifact"]
    assert report.retry_patch == {}
    assert report.evidence["human_naturalness_attestation"]["status"] == "retry_recommended"
