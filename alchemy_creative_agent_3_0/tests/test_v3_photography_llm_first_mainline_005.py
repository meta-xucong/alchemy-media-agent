"""PX-MAINLINE-005 regressions for LLM-first Photography execution."""

from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_fallback_result
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import photography_capability_policy
from alchemy_creative_agent_3_0.tests.photography_test_support import (
    PhotographyRemoteBrainTestProvider,
    photography_test_runtime,
    photography_test_service,
)


def _binding() -> dict:
    return {
        "binding_mode": "general",
        "profile_id": "general_photography",
        "profile_display_name": "General Photography",
        "profile_version": "v1",
        "selection_source": None,
        "catalog_version": "mainline-catalog-v1",
        "availability_decision": "general_default",
        "technique_package_checksum": "general-photography-v1",
        "pinned_at": "2026-07-14T00:00:00+00:00",
    }


def _request(*, mode_id: str = "professional_set") -> dict:
    return {
        "user_input": "Create an intimate documentary portrait session of a ceramic artist at work.",
        "scenario_selection": {"scenario_id": "photography", "mode_id": mode_id},
        "metadata": {"template_id": "photographer_template", "photographer_profile_binding": _binding()},
    }


class _UnavailableRemoteBrain:
    provider = "unavailable_photography_fixture"
    model = "fixture"

    def available(self, *, force: bool = False) -> bool:
        return False

    def run(self, request):  # pragma: no cover - assertion guard
        raise AssertionError("a disabled remote Brain must not be called")


class _WrongCardinalityRemoteBrain(PhotographyRemoteBrainTestProvider):
    def run(self, request) -> dict:
        payload = build_fallback_result(request).model_dump(mode="json")
        payload["image_set_plan"] = {
            "set_goal": "invalid fixture",
            "image_count": 1,
            "size": request.requested_image_size,
            "shot_plan": ["Only one invalid remote direction."],
            "composition_rules": [],
            "quality_bar": [],
        }
        return payload


def test_photography_policy_requires_remote_brain_and_names_it_as_creative_owner() -> None:
    policy = photography_capability_policy()

    assert policy.requires_remote_creative_brain is True
    assert policy.metadata["creative_direction_owner"] == "remote_v3_llm_brain"
    assert "suite_direction" in policy.forbidden_capabilities


def test_photography_blocks_when_remote_brain_is_unavailable_or_role_count_is_invalid(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    unavailable = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=_UnavailableRemoteBrain())).plan_job(_request())

    assert unavailable.status == ScenarioRuntimeStatus.BLOCKED
    assert "remote_creative_brain_required_for_template" in " ".join(unavailable.warnings)
    assert unavailable.metadata["remote_creative_brain_outcome"] == {
        "schema_version": "v3_remote_creative_brain_outcome_v1",
        "state": "blocked",
        "reason_code": "remote_creative_brain_required_for_template",
        "outcome_class": "remote_provider_unavailable",
        "llm_used": False,
        "fallback_used": True,
        "remote_provider_available": False,
        "remote_contract_rejected_sections": [],
    }

    wrong_count = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=_WrongCardinalityRemoteBrain())
    ).plan_job(_request())

    assert wrong_count.status == ScenarioRuntimeStatus.BLOCKED
    assert "remote_creative_brain_image_set_plan_invalid" in " ".join(wrong_count.warnings)
    invalid = wrong_count.metadata["remote_creative_brain_outcome"]
    assert invalid["outcome_class"] == "remote_contract_invalid"
    assert invalid["remote_contract_rejected_sections"] == [
        "image_set_plan",
        "visual_task_profile.rendering_intent",
        "canonical_provider_prompts",
    ]


def test_photography_brain_receives_only_noncreative_contract_and_owns_each_direction(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    provider = PhotographyRemoteBrainTestProvider()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))

    result = runtime.plan_job(_request())

    assert result.status == ScenarioRuntimeStatus.PLANNED
    assert "suite_direction" not in result.metadata["capability_activation_plan"]["dependency_order"]
    brain_request = provider.requests[0]
    context = brain_request.metadata["photography_creative_context"]
    assert context["role_ids"] == ["session_hero", "environmental_context", "detail_or_moment"]
    assert context["role_count"] == 3
    assert context["pinned_profile_checksum"] == "general-photography-v1"
    assert context["forbidden_cross_template_roles"] == [
        "general_suite_direction",
        "general_cover_hero",
        "ecommerce_deliverable_role",
    ]
    assert all(key not in json.dumps(context) for key in ("camera_distance", "crop_rule", "scene_rule", "prompt_pressure"))

    specialized = result.metadata["specialized_scenario_plan"]
    recipes = specialized["execution_plan"]["role_recipes"]
    assert all(recipe["prompt_pressure"] == "" and recipe["purpose"] == "" for recipe in recipes)
    assert all(recipe["metadata"]["static_recipe_present"] is False for recipe in recipes)
    assert specialized["execution_plan"]["prompt_additions"] == []

    deliverables = result.metadata["template_deliverable_plan"]["deliverables"]
    assert [item["image_intent"] for item in deliverables] == [
        "Remote Photography direction 1: create one complete, original photographic image that answers the user's request and respects the declared reference truth.",
        "Remote Photography direction 2: create one complete, original photographic image that answers the user's request and respects the declared reference truth.",
        "Remote Photography direction 3: create one complete, original photographic image that answers the user's request and respects the declared reference truth.",
    ]
    assert all(item["source"] == "remote_v3_llm_brain" for item in deliverables)


def test_photography_compact_remote_payload_is_valid_without_a_capability_catalog() -> None:
    """The fail-closed remote call must not crash before it reaches the Brain."""

    request = V3LLMBrainAdapter().build_request(
        user_input="Create three quiet landscape photographs; no people or visible text.",
        stage="plan",
        scenario_id="photography",
        template_id="photographer_template",
        metadata={
            "requested_image_count": 3,
            "photographer_profile_binding": _binding(),
            "specialized_scenario_plan": {"execution_plan": {"role_recipes": [{"role_key": "session_hero"}, {"role_key": "environmental_context"}, {"role_key": "detail_or_moment"}]}},
        },
        template_capability_policy=photography_capability_policy(),
    )

    payload = json.loads(build_remote_payload(request))

    assert payload["return_schema"]["image_set_plan"]
    assert "visual_task_profile" in payload["return_schema"]
    assert "canonical_provider_prompts" not in payload["return_schema"]
    assert payload["photography_creative_context"]["role_count"] == 3


def test_general_and_ecommerce_brain_requests_never_receive_photography_contract() -> None:
    adapter = V3LLMBrainAdapter()
    metadata = {
        "photographer_profile_binding": _binding(),
        "specialized_scenario_plan": {
            "execution_plan": {"role_recipes": [{"role_key": "session_hero"}]},
        },
    }
    for scenario_id, template_id in (("general_creative", "general_template"), ("ecommerce", "ecommerce_template")):
        request = adapter.build_request(
            user_input="Create a quiet image.",
            stage="plan",
            scenario_id=scenario_id,
            template_id=template_id,
            metadata=metadata,
        )
        payload = json.loads(build_remote_payload(request))
        assert "photography_creative_context" not in request.metadata
        assert "photography_creative_context" not in payload
        assert "photography_context_instructions" not in payload


def test_metadata_only_photography_review_withholds_terminal_delivery(monkeypatch) -> None:
    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    service = photography_test_service()
    create_request = _request(mode_id="single_hero")
    create_request["metadata"] = {"template_id": "photographer_template"}
    created = service.create_job(create_request)
    assert created.status.value == "planned"

    generated = service.generate_job(created.job_id, {"metadata": {"vision_inspection_mode": "metadata_only"}})

    assert generated.status.value == "blocked"
    summary = generated.metadata["specialized_execution_summary"]
    assert summary["status"] == "non_certifying"
    assert summary["noncertifying_role_keys"] == ["hero_photograph"]
    assert summary["final_delivery_withheld"] is True
    assert "real-pixel review" in " ".join(generated.warnings).lower()

    certification = generated.metadata["review_certification"]
    assert certification == {
        "schema_version": "v3_review_certification_v1",
        "scenario_id": "photography",
        "state": "blocked",
        "automatic_delivery_certified": False,
        "manual_confirmation_required": False,
        "final_delivery_withheld": True,
        "roles": [
            {
                "role_key": "hero_photograph",
                "state": "blocked",
                "review_mode": "metadata_only",
                "review_status": "manual_review",
                "verification_state": "unverified",
            }
        ],
    }
    assert "candidate_id" not in json.dumps(certification)


def test_legacy_photography_summary_can_only_be_projected_to_withhold_not_recertified(monkeypatch) -> None:
    """Pre-Doc116 records retain review truth without gaining certification."""

    monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    service = photography_test_service()
    create_request = _request(mode_id="single_hero")
    create_request["metadata"] = {"template_id": "photographer_template"}
    created = service.create_job(create_request)
    service.generate_job(created.job_id, {"metadata": {"vision_inspection_mode": "metadata_only"}})

    record = service.get_job_record(created.job_id)
    assert record is not None
    legacy_summary = dict(record.request.metadata["specialized_execution_summary"])
    legacy_summary.pop("review_certification", None)
    record.request.metadata["specialized_execution_summary"] = legacy_summary
    record.request.metadata.pop("review_certification", None)
    service.job_store.save(record)

    restored = service.get_job(created.job_id)
    certification = restored.metadata["review_certification"]
    assert certification["state"] == "blocked"
    assert certification["automatic_delivery_certified"] is False
    assert certification["final_delivery_withheld"] is True
    assert "candidate_id" not in json.dumps(certification)
