"""Doc157: shared age-transition semantics stay Brain-owned and channel-safe."""

from __future__ import annotations

import inspect
import json

from alchemy_creative_agent_3_0.app.llm_brain.prompts import SYSTEM_PROMPT
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer


def _guidance(
    user_input: str,
    *,
    has_identity_reference: bool = True,
    developmental_age_intent: str = "preserve_reference_stage",
):
    return HumanPhotorealismLayer().build(
        project_id="project_doc157",
        job_id="job_doc157",
        scenario_id="general_creative",
        template_id="general_template",
        user_input=user_input,
        subject_type="person",
        variation_mode="single_hero",
        has_identity_reference=has_identity_reference,
        metadata={
            "brain_owned_forward_execution": True,
            "human_realism_execution_required": True,
            "frozen_rendering_intent": {
                "rendering_mode": "photoreal",
                "stylization_scope": "none",
                "decision_owner": "remote_brain",
            },
            "frozen_developmental_age_intent": developmental_age_intent,
        },
    )


def test_doc157_enforced_path_preserves_typed_age_direction_without_local_transition_recipe() -> None:
    guidance = _guidance(
        "Keep this same approximately 10-year-old person's face, but render a 6-year-old version "
        "in the current garden scene and current dress.",
        developmental_age_intent="current_request_assigns_stage",
    )
    plugin = guidance.metadata["human_realism_plugin"]
    profile = plugin["universal_rendering_profile"]
    evidence = plugin["evidence"]

    assert profile["age_fidelity"] == "follow_explicit_prompt"
    assert evidence["frozen_developmental_age_intent"] == "current_request_assigns_stage"
    assert guidance.semantic_contract["identity_age_fidelity"] == "explicit_or_reference_backed"
    assert guidance.positive_prompt_fragments == []
    assert guidance.retry_patch_templates == {}
    assert "rounder cheeks" not in json.dumps(guidance.metadata, ensure_ascii=False).lower()
    assert "larger eyes" not in json.dumps(guidance.metadata, ensure_ascii=False).lower()


def test_doc157_same_person_without_age_direction_keeps_reference_continuity_mode() -> None:
    guidance = _guidance("Continue the same person in the current garden scene and current dress.")
    plugin = guidance.metadata["human_realism_plugin"]

    assert plugin["universal_rendering_profile"]["age_fidelity"] == "preserve_reference"
    assert plugin["evidence"]["frozen_developmental_age_intent"] == "preserve_reference_stage"
    assert guidance.semantic_contract["identity_age_fidelity"] == "explicit_or_reference_backed"


def test_doc157_new_person_explicit_age_uses_same_shared_contract() -> None:
    guidance = _guidance(
        "Create a new real-camera person approximately 6 years old in an ordinary garden scene.",
        has_identity_reference=False,
        developmental_age_intent="current_request_assigns_stage",
    )
    serialized = json.dumps(guidance.semantic_contract, ensure_ascii=False).lower()

    assert guidance.metadata["human_realism_plugin"]["universal_rendering_profile"]["age_fidelity"] == (
        "follow_explicit_prompt"
    )
    assert guidance.semantic_contract["contract_version"] == "v3_human_realism_semantic_v8"
    assert "child" not in serialized
    assert "kidswear" not in serialized


def test_doc157_brain_context_carries_age_boundary_without_authoring_prompt_language() -> None:
    projection = {
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
    resolved = ScenarioRuntime._human_realism_age_resolution(projection)  # noqa: SLF001

    assert resolved == {
        "age_fidelity": "follow_explicit_prompt",
        "identity_continuity": "identity_critical_feature_relationships",
        "source_age_inheritance": "not_automatic_when_current_prompt_assigns_age",
        "developmental_age_coherence": "whole_person_requested_stage",
        "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
        "review_owner": "v3_shared_vision",
        "decision_owner": "remote_v3_llm_brain",
        "creative_prompt_owner": "remote_v3_llm_brain",
    }


def test_doc157_brain_owns_age_transition_and_provider_has_no_local_age_append() -> None:
    assert "source person's apparent age" in SYSTEM_PROMPT
    assert "Only the Brain makes this semantic decision" in SYSTEM_PROMPT
    provider_source = inspect.getsource(
        __import__(
            "alchemy_creative_agent_3_0.app.generation_router.providers",
            fromlist=["ProductionImageGenerationProvider"],
        ).ProductionImageGenerationProvider._generation_prompt
    )
    assert "make younger" not in provider_source.lower()
    assert "rounder cheeks" not in provider_source.lower()
    assert "larger eyes" not in provider_source.lower()
