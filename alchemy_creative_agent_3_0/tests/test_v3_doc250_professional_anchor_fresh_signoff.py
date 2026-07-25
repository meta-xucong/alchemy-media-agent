"""Doc250: fresh Professional standard-front Brain signoff stays authoritative."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import (
    ProfessionalModeRuntimeBridge,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import (
    EcommerceRemoteBrainTestProvider,
)


CAPTURE_SCOPE = "character_card_face_identity"
REQUIRED_STANDARD_FRONT_DECISION = {
    "contract_version": "v3_professional_anchor_view_decision_v3",
    "owner": "remote_v3_llm_brain",
    "target_view_role": "standard_front",
    "capture_presentation": "neutral_identity_evidence_capture",
    "capture_continuity": "establish_neutral_capture",
    "capture_scope": CAPTURE_SCOPE,
    "framing_standard": "consistent_head_and_upper_shoulders_reference_crop",
    "crop_policy": "head_top_margin_full_face_neck_and_upper_shoulders_visible",
    "torso_scope": "upper_shoulders_only_no_half_body_or_big_head_crop",
    "aspect_ratio_standard": "honor_frozen_rendering_size_as_reference_card_aspect_ratio",
    "source_viewpoint_inheritance": "identity_only_do_not_inherit_source_pose_angle",
    "front_pose_normalization": "normalize_to_symmetric_camera_facing_front",
    "face_axis_alignment": "face_midline_vertical_eyes_level_nose_centered",
}


class _Doc250FreshBrainProvider(EcommerceRemoteBrainTestProvider):
    def __init__(self, *, finalizer_fault: str | None = None) -> None:
        super().__init__()
        self.finalizer_fault = finalizer_fault
        self.finalizer_metadata: list[dict[str, object]] = []

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage != "provider_prompt_finalize":
            return payload
        self.finalizer_metadata.append(deepcopy(dict(request.metadata or {})))
        prompts = payload.get("canonical_provider_prompts")
        if not isinstance(prompts, list):
            return payload
        if self.finalizer_fault == "missing_anchor_signature":
            for item in prompts:
                if isinstance(item, dict):
                    item.pop("professional_anchor_view_decision", None)
        elif self.finalizer_fault == "wrong_view":
            for item in prompts:
                if isinstance(item, dict) and isinstance(item.get("professional_anchor_view_decision"), dict):
                    item["professional_anchor_view_decision"]["target_view_role"] = "profile"
        elif self.finalizer_fault == "wrong_owner":
            for item in prompts:
                if isinstance(item, dict) and isinstance(item.get("professional_anchor_view_decision"), dict):
                    item["professional_anchor_view_decision"]["owner"] = "local_fixture"
        elif self.finalizer_fault == "wrong_version":
            for item in prompts:
                if isinstance(item, dict) and isinstance(item.get("professional_anchor_view_decision"), dict):
                    item["professional_anchor_view_decision"]["contract_version"] = (
                        "v3_professional_anchor_view_decision_v2"
                    )
        elif self.finalizer_fault == "duplicate_prompt":
            prompts.append(deepcopy(prompts[0]))
        elif self.finalizer_fault == "generic_provider_failure":
            raise RuntimeError("upstream fixture transport failed")
        return payload


def _source_image(tmp_path: Path) -> Path:
    path = tmp_path / "doc250-source.png"
    Image.new("RGB", (640, 960), (175, 135, 120)).save(path)
    return path


def _standard_front_request(
    tmp_path: Path,
    *,
    planning_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    planning = (
        planning_metadata
        if planning_metadata is not None
        else ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
            view_role="standard_front",
            capture_scope=CAPTURE_SCOPE,
        )
    )
    return {
        "user_input": "Prepare one Character Card Face Identity standard-front capture.",
        "scenario_selection": {"scenario_id": "general_creative"},
        "uploaded_assets": [
            {
                "asset_id": "v3_asset_doc250",
                "role": "face_reference",
                "file_path": str(_source_image(tmp_path)),
                "use_policy": "identity",
                "strength": "hard",
            }
        ],
        "metadata": {
            "project_id": "project_doc250",
            "requested_image_count": 1,
            "requested_image_size": "1024x1536",
            "quality_mode": "strict",
            "require_real_images": True,
            "professional_mode": True,
            "professional_anchor_pack_preparation": True,
            "professional_planning_metadata": planning,
        },
    }


def _runtime(provider: _Doc250FreshBrainProvider) -> ScenarioRuntime:
    return ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))


def _canonical_prompt_context(provider: _Doc250FreshBrainProvider) -> dict[str, object]:
    assert provider.finalizer_metadata
    context = provider.finalizer_metadata[-1].get("canonical_prompt_context")
    assert isinstance(context, dict)
    return context


def test_doc250_fresh_standard_front_finalizer_receives_complete_v3_requirement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    provider = _Doc250FreshBrainProvider()

    result = _runtime(provider).plan_job(_standard_front_request(tmp_path))

    assert result.status.value == "planned"
    context = _canonical_prompt_context(provider)
    requirement = context.get("professional_anchor_view_decision")
    assert isinstance(requirement, dict)
    for key, value in REQUIRED_STANDARD_FRONT_DECISION.items():
        assert requirement.get(key) == value
    assert requirement.get("required") is True
    assert isinstance(requirement.get("frozen_binding"), dict)
    assert context.get("professional_face_identity_quality_contract")
    assert "portrait_identity" in (context.get("active_shared_capability_ids") or [])
    assert "reference_channel_policy" in (context.get("active_shared_capability_ids") or [])
    assert "human_realism" in (context.get("active_shared_capability_ids") or [])


def test_doc250_missing_fresh_standard_front_signature_blocks_with_specific_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    provider = _Doc250FreshBrainProvider(finalizer_fault="missing_anchor_signature")

    result = _runtime(provider).plan_job(_standard_front_request(tmp_path))

    assert result.status.value == "blocked"
    assert result.metadata["capability_activation_error"] == "CapabilityActivationError"
    outcome = result.metadata.get("remote_creative_brain_outcome")
    assert isinstance(outcome, dict)
    assert outcome["reason_code"] == "professional_anchor_view_decision_missing"
    assert outcome["outcome_class"] == "remote_prompt_signoff_unavailable"


def test_doc250_valid_fresh_v3_signature_plans_without_reuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    provider = _Doc250FreshBrainProvider()

    result = _runtime(provider).plan_job(_standard_front_request(tmp_path))

    assert result.status.value == "planned"
    assert provider.finalizer_metadata
    finalizer_metadata = provider.finalizer_metadata[-1]
    assert "trusted_professional_anchor_view_decision_reuse" not in finalizer_metadata


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_view",
        "wrong_owner",
        "wrong_version",
        "duplicate_prompt",
    ],
)
def test_doc250_wrong_or_duplicate_fresh_signature_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    provider = _Doc250FreshBrainProvider(finalizer_fault=fault)

    result = _runtime(provider).plan_job(_standard_front_request(tmp_path))

    assert result.status.value == "blocked"
    outcome = result.metadata.get("remote_creative_brain_outcome")
    assert isinstance(outcome, dict)
    assert outcome["reason_code"] in {
        "professional_anchor_view_decision_missing",
        "remote_creative_brain_prompt_signoff_invalid",
    }


def test_doc250_capability_activation_projection_missing_is_not_reported_as_brain_signature_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    provider = _Doc250FreshBrainProvider()
    incomplete_planning = {
        "professional_reference_stage": "standard_front",
        "professional_anchor_capture_scope": CAPTURE_SCOPE,
    }

    result = _runtime(provider).plan_job(
        _standard_front_request(tmp_path, planning_metadata=incomplete_planning)
    )

    assert result.status.value == "blocked"
    assert "professional_anchor_pack_preparation_contract_invalid" in result.warnings[-1]
    assert not provider.finalizer_metadata
    assert "remote_creative_brain_outcome" not in result.metadata


def test_doc250_non_contract_provider_failure_is_not_misclassified_as_prompt_contract_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    provider = _Doc250FreshBrainProvider(finalizer_fault="generic_provider_failure")

    result = _runtime(provider).plan_job(_standard_front_request(tmp_path))

    assert result.status.value == "blocked"
    outcome = result.metadata.get("remote_creative_brain_outcome")
    assert isinstance(outcome, dict)
    assert outcome["reason_code"] == "remote_creative_brain_prompt_signoff_unavailable"
