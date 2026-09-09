"""Doc295 regressions for human-led General suites and canonical audit routing."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.generation_router.providers import (
    ProductionImageGenerationProvider,
)
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import has_product_profile_facts
from alchemy_creative_agent_3_0.app.shared_capabilities import CapabilityInput, SharedCapabilityRegistry
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    ModeAwareRoleDirector,
    VisualCapabilityClusterModule,
)


def _enforced_plan() -> dict:
    active = ["human_realism", "product_identity", "reference_channel_policy", "suite_direction"]
    return {
        "plan_id": "plan_doc295",
        "activation_mode": "enforced",
        "dependency_order": active,
        "active_capabilities": [{"capability_id": item, "selected_profile": "balanced"} for item in active],
    }


def _mixed_profile() -> dict:
    return {
        "subject_entities": [
            {
                "entity_id": "person-1",
                "entity_type": "person",
                "role": "primary_subject",
                "visible_in_target": True,
                "preservation_level": "high",
                "confidence": 0.99,
                "attributes": {"age_direction": "adult"},
            },
            {
                "entity_id": "product-1",
                "entity_type": "product",
                "role": "held_object",
                "visible_in_target": True,
                "preservation_level": "strong",
                "confidence": 0.99,
                "attributes": {"form": "bottle"},
            },
        ]
    }


def _cluster_metadata(*, scenario_id: str, template_id: str) -> dict:
    metadata = {
        "brain_owned_forward_execution": True,
        "capability_activation_plan": _enforced_plan(),
        "visual_task_profile": _mixed_profile(),
        "requested_image_count": 2,
        "effective_variation_mode": "delivery_suite",
        "project_context_snapshot": {
            "project_id": "project_doc295",
            "template_id": template_id,
            "selected_output_assets": [],
            "selected_reference_assets": [],
            "uploaded_reference_assets": [],
        },
        "resolved_scenario_id": scenario_id,
        "resolved_template_id": template_id,
    }
    if scenario_id == "general_creative":
        role_plan = ModeAwareRoleDirector().build(
            project_id="project_doc295",
            job_id="job_doc295",
            user_input="",
            mode="delivery_suite",
            requested_image_count=2,
            subject_type="generic",
            scenario_id=scenario_id,
            template_id=template_id,
        )
        contract = ModeAwareRoleDirector().build_variation_execution_contract(
            role_plan=role_plan,
            scenario_id=scenario_id,
            template_id=template_id,
        )
        assert contract is not None
        metadata.update(
            {
                "variation_execution_contract": contract.model_dump(mode="json"),
                "variation_execution_contract_enforced": True,
                "variation_execution_contract_binding": {
                    "contract_version": contract.contract_version,
                    "contract_digest": contract.contract_digest,
                },
                "variation_execution_mode": "delivery_suite",
                "variation_execution_requested_image_count": 2,
            }
        )
    return metadata


def test_doc295_general_mixed_person_product_scene_is_human_led() -> None:
    result = SharedCapabilityRegistry.with_default_modules().run(
        CapabilityInput(
            job_id="job_doc295_general",
            scenario_id="general_creative",
            user_input="",
            metadata=_cluster_metadata(
                scenario_id="general_creative",
                template_id="general_template",
            ),
        ),
        module_ids=["visual_capability_cluster"],
    )

    cluster = result.results[-1].facts["visual_capability_cluster"]
    role_plan = cluster["role_specific_generation_plan"]

    assert cluster["template_consistency_policy"]["policy_id"] == "portrait_identity"
    assert role_plan["subject_type"] == "character"
    assert [item["role_key"] for item in role_plan["role_recipes"]] == [
        "cover_hero",
        "subject_focus",
    ]
    assert cluster["mode_quality_profile"]["metadata"]["subject_type"] == "character"
    assert cluster["human_photorealism_guidance"]["subject_type"] == "character"
    # Product truth remains active as a capability/fact; it no longer hijacks
    # the frame's primary subject or General suite role family.
    assert cluster["profile"]["metadata"]["commerce_terms_allowed"] is True


def test_doc295_ecommerce_keeps_product_truth_primary() -> None:
    result = SharedCapabilityRegistry.with_default_modules().run(
        CapabilityInput(
            job_id="job_doc295_ecommerce",
            scenario_id="ecommerce",
            user_input="",
            metadata=_cluster_metadata(
                scenario_id="ecommerce",
                template_id="ecommerce_template",
            ),
        ),
        module_ids=["visual_capability_cluster"],
    )

    cluster = result.results[-1].facts["visual_capability_cluster"]
    role_plan = cluster["role_specific_generation_plan"]

    assert cluster["template_consistency_policy"]["policy_id"] == "product_truth"
    assert role_plan["subject_type"] == "product"
    assert [item["role_key"] for item in role_plan["role_recipes"]] == [
        "hero_object",
        "context_scene",
    ]


def test_doc295_legacy_general_mixed_text_keeps_human_primary() -> None:
    policy = VisualCapabilityClusterModule()._template_consistency_policy(  # noqa: SLF001
        template_id="general_template",
        scenario_id="general_creative",
        user_input="A woman crouching and holding a bottle in a supermarket aisle.",
        allow_product_language=True,
    )

    assert policy["policy_id"] == "portrait_identity"


def test_doc295_general_compatibility_profile_is_not_product_evidence() -> None:
    compatibility_request = SimpleNamespace(
        uploaded_assets=[],
        product_profile={
            "brand_or_project_name": "project",
            "project_goal": "a human lifestyle image",
            "project_context": {"template_id": "general_template"},
        },
    )
    typed_product_request = SimpleNamespace(
        uploaded_assets=[],
        product_profile={"product_name": "amber bottle"},
    )

    compatibility_binding = ScenarioRuntime._resolved_general_variation_role_binding(  # noqa: SLF001
        compatibility_request
    )
    typed_product_binding = ScenarioRuntime._resolved_general_variation_role_binding(  # noqa: SLF001
        typed_product_request
    )

    assert compatibility_binding["subject_type"] == "generic"
    assert compatibility_binding["source"] == "runtime_subject_facts_unresolved"
    assert typed_product_binding["subject_type"] == "product"
    assert typed_product_binding["source"] == "runtime_typed_reference_facts"


@pytest.mark.parametrize("entity_type", ["human", "character"])
def test_doc295_brain_human_aliases_keep_general_subject_precedence(entity_type: str) -> None:
    metadata = _cluster_metadata(
        scenario_id="general_creative",
        template_id="general_template",
    )
    profile = _mixed_profile()
    profile["subject_entities"][0]["entity_type"] = entity_type
    metadata["visual_task_profile"] = profile

    module = VisualCapabilityClusterModule()

    assert module._brain_owned_forward_has_visible_subject(  # noqa: SLF001
        SimpleNamespace(metadata=metadata),
        "person",
    ) is True
    policy = module._brain_owned_forward_template_consistency_policy(  # noqa: SLF001
        CapabilityInput(
            job_id="job_doc295_alias",
            scenario_id="general_creative",
            user_input="",
            metadata=metadata,
        ),
        allow_product_language=True,
    )
    assert policy["policy_id"] == "portrait_identity"


def test_doc295_runtime_product_hint_is_reconciled_with_brain_human_profile() -> None:
    metadata = _cluster_metadata(
        scenario_id="general_creative",
        template_id="general_template",
    )
    metadata.update(
        {
            "variation_execution_role_binding": {
                "subject_type": "product",
                "has_identity_anchor": False,
                "source": "runtime_typed_reference_facts",
            },
            "resolved_scenario_id": "general_creative",
            "resolved_template_id": "general_template",
            "variation_execution_contract_enforced": True,
        }
    )

    result = SharedCapabilityRegistry.with_default_modules().run(
        CapabilityInput(
            job_id="job_doc295_runtime_reconcile",
            scenario_id="general_creative",
            user_input="",
            product_profile={"product_name": "amber bottle"},
            metadata=metadata,
        ),
        module_ids=["visual_capability_cluster"],
    )

    cluster = result.results[-1].facts["visual_capability_cluster"]
    assert cluster["role_specific_generation_plan"]["subject_type"] == "character"
    assert [item["role_key"] for item in cluster["role_specific_generation_plan"]["role_recipes"]] == [
        "cover_hero",
        "subject_focus",
    ]


def test_doc295_visual_product_evidence_uses_the_shared_typed_fact_authority() -> None:
    assert has_product_profile_facts({"product_type": "bottle"}) is True
    assert has_product_profile_facts({"platform": "amazon_us"}) is False
    assert has_product_profile_facts(
        {
            "brand_or_project_name": "project",
            "project_goal": "a human lifestyle image",
            "project_context": {"template_id": "general_template"},
        }
    ) is False


def test_doc295_multi_output_provider_audit_reads_the_matching_brain_receipt() -> None:
    records = [
        {
            "output_index": 1,
            "prompt": "First complete canonical direction.",
            "review_status": "approved",
            "user_direction_integrity": {
                "contract_version": "v3_user_direction_integrity_v1",
                "status": "preserved",
                "owner": "remote_v3_llm_brain",
            },
        },
        {
            "output_index": 2,
            "prompt": "Second complete canonical direction.",
            "review_status": "approved",
            "user_direction_integrity": {
                "contract_version": "v3_user_direction_integrity_v1",
                "status": "rewritten",
                "owner": "remote_v3_llm_brain",
            },
        },
    ]
    request = SimpleNamespace(
        metadata={
            "require_real_images": True,
            "llm_brain": {"canonical_provider_prompts": records},
        },
        generation_plan=SimpleNamespace(metadata={"output_index": 1}),
    )
    provider = ProductionImageGenerationProvider(output_store=SimpleNamespace())

    prompt = provider._brain_signed_provider_prompt(request)  # noqa: SLF001
    integrity = provider._brain_user_direction_integrity(request)  # noqa: SLF001
    audit = provider._provider_prompt_audit(  # noqa: SLF001
        prompt,
        "The full user direction.",
        prompt_source="remote_brain_canonical",
        user_direction_integrity=integrity,
    )

    assert prompt == records[1]["prompt"]
    assert integrity["status"] == "rewritten"
    assert audit["user_direction_lossless"] is True
    assert audit["user_direction_semantic_status"] == "rewritten"


@pytest.mark.parametrize("raw_output_index", ["1", 1.0, True, -1])
def test_doc295_provider_selector_rejects_coerced_output_index(raw_output_index) -> None:
    record = {
        "output_index": 1,
        "prompt": "A complete canonical direction with the requested scene.",
        "review_status": "approved",
        "user_direction_integrity": {
            "contract_version": "v3_user_direction_integrity_v1",
            "status": "preserved",
            "owner": "remote_v3_llm_brain",
        },
    }
    request = SimpleNamespace(
        metadata={
            "require_real_images": True,
            "llm_brain": {"canonical_provider_prompts": [record]},
        },
        generation_plan=SimpleNamespace(metadata={"output_index": raw_output_index}),
    )

    provider = ProductionImageGenerationProvider(output_store=SimpleNamespace())

    assert provider._brain_signed_provider_prompt(request) == ""  # noqa: SLF001
    assert provider._brain_user_direction_integrity(request) == {}  # noqa: SLF001


@pytest.mark.parametrize(
    "mutator",
    [
        lambda record: record.pop("user_direction_integrity"),
        lambda record: record["user_direction_integrity"].update({"status": "unknown"}),
        lambda record: record.update({"review_status": "rejected"}),
        lambda record: record.update({"output_index": "1"}),
    ],
)
def test_doc295_provider_selector_fails_closed_for_non_closed_canonical_record(mutator) -> None:
    record = {
        "output_index": 1,
        "prompt": "A complete canonical direction with the requested scene.",
        "review_status": "approved",
        "user_direction_integrity": {
            "contract_version": "v3_user_direction_integrity_v1",
            "status": "preserved",
            "owner": "remote_v3_llm_brain",
        },
    }
    mutator(record)
    request = SimpleNamespace(
        metadata={
            "require_real_images": True,
            "llm_brain": {"canonical_provider_prompts": [record]},
        },
        generation_plan=SimpleNamespace(metadata={"output_index": 0}),
    )

    provider = ProductionImageGenerationProvider(output_store=SimpleNamespace())

    assert provider._brain_signed_provider_prompt(request) == ""  # noqa: SLF001
    assert provider._brain_user_direction_integrity(request) == {}  # noqa: SLF001


def test_doc295_provider_selector_rejects_duplicate_output_receipts() -> None:
    record = {
        "output_index": 1,
        "prompt": "A complete canonical direction with the requested scene.",
        "review_status": "approved",
        "user_direction_integrity": {
            "contract_version": "v3_user_direction_integrity_v1",
            "status": "preserved",
            "owner": "remote_v3_llm_brain",
        },
    }
    duplicate = dict(record)
    duplicate["prompt"] = "A second complete canonical direction for the same lane."
    request = SimpleNamespace(
        metadata={
            "require_real_images": True,
            "llm_brain": {"canonical_provider_prompts": [record, duplicate]},
        },
        generation_plan=SimpleNamespace(metadata={"output_index": 0}),
    )

    provider = ProductionImageGenerationProvider(output_store=SimpleNamespace())

    assert provider._brain_signed_provider_prompt(request) == ""  # noqa: SLF001


@pytest.mark.parametrize("bad_prompt", [123, ["not", "a", "prompt"], None])
def test_doc295_provider_selector_rejects_non_string_canonical_prompt(bad_prompt) -> None:
    record = {
        "output_index": 1,
        "prompt": bad_prompt,
        "review_status": "approved",
        "user_direction_integrity": {
            "contract_version": "v3_user_direction_integrity_v1",
            "status": "preserved",
            "owner": "remote_v3_llm_brain",
        },
    }
    request = SimpleNamespace(
        metadata={
            "require_real_images": True,
            "llm_brain": {"canonical_provider_prompts": [record]},
        },
        generation_plan=SimpleNamespace(metadata={"output_index": 0}),
    )

    provider = ProductionImageGenerationProvider(output_store=SimpleNamespace())

    assert provider._brain_signed_provider_prompt(request) == ""  # noqa: SLF001
    assert provider._brain_user_direction_integrity(request) == {}  # noqa: SLF001


@pytest.mark.parametrize(
    "audit_key",
    ["character_card_slot_delta_recovery_used", "reference_led_slot_delta_decision_required"],
)
def test_doc295_provider_does_not_coerce_string_slot_delta_flags(audit_key: str) -> None:
    record = {
        "output_index": 1,
        "prompt": "A complete canonical direction with the requested scene.",
        "review_status": "approved",
    }
    request = SimpleNamespace(
        metadata={
            "require_real_images": True,
            "llm_brain": {
                "canonical_provider_prompts": [record],
                "audit": {audit_key: "false"},
            },
        },
        generation_plan=SimpleNamespace(metadata={"output_index": 0}),
    )

    provider = ProductionImageGenerationProvider(output_store=SimpleNamespace())

    assert provider._brain_signed_provider_prompt(request) == ""  # noqa: SLF001
    assert provider._brain_user_direction_integrity(request) == {}  # noqa: SLF001
