"""Focused tests for the V3 General variation compatibility bridge."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.contracts import VariationExecutionReceipt
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_fallback_result
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.llm_brain.providers import BrainPromptContractInvalid
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    ecommerce_capability_policy,
    photography_capability_policy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    ModeAwareRoleDirector,
    VisualCapabilityClusterModule,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.general_suite_director import (
    GeneralSuiteDirector,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import (
    ProjectVisualGrammarSnapshot,
    VariationExecutionContract,
    VariationExecutionOutput,
    VisualCapabilityClusterResult,
    VisualConsistencyGuardResult,
    VisualGrammarProfile,
    VisualQualityReviewResult,
    VisualReferenceBindingProfile,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.contracts import UploadedAssetInfo


def _general_contract(
    count: int = 4,
    mode: str = "delivery_suite",
) -> VariationExecutionContract:
    director = ModeAwareRoleDirector()
    role_plan = director.build(
        project_id="project_variation_contract",
        job_id="job_variation_contract",
        user_input="same person image set",
        mode=mode,
        requested_image_count=count,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=True,
    )
    contract = director.build_variation_execution_contract(
        role_plan=role_plan,
        scenario_id="general_creative",
        template_id="general_template",
    )
    assert contract is not None
    return contract


def test_general_variation_contract_projects_neutral_semantics_only() -> None:
    contract = _general_contract()
    payload = contract.model_dump(mode="json")

    assert set(payload) == {
        "contract_version",
        "contract_digest",
        "mode",
        "requested_image_count",
        "preserve_subject",
        "preserve_style",
        "outputs",
    }
    assert len(contract.contract_digest) == 64
    assert contract.contract_digest == contract.computed_digest()
    assert [item["output_index"] for item in payload["outputs"]] == [1, 2, 3, 4]
    assert payload["outputs"][0]["variation_axes"] == ["framing", "scale", "layout"]
    assert payload["outputs"][2]["variation_axes"] == ["viewpoint", "pose", "attention"]
    assert len({item["output_purpose"] for item in payload["outputs"]}) == 4
    assert len({tuple(item["variation_axes"]) for item in payload["outputs"]}) == 4

    serialized = json.dumps(payload)
    for forbidden in (
        "role_key",
        "role_id",
        "shot_family",
        "camera_distance",
        "angle_rule",
        "crop_rule",
        "scene_rule",
        "prompt_pressure",
        "prompt_additions",
        "negative_additions",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("mode", "count"),
    [
        (mode, count)
        for mode in (
            "selection_candidates",
            "delivery_suite",
            "creative_exploration",
            "format_layout_adaptation",
        )
        for count in (2, 3, 4)
    ],
)
def test_general_variation_contract_semantic_signatures_are_unique(
    mode: str,
    count: int,
) -> None:
    contract = _general_contract(count=count, mode=mode)
    signatures = [
        (item.output_purpose, tuple(item.variation_axes))
        for item in contract.outputs
    ]

    assert all(axes for _, axes in signatures)
    assert len(signatures) == len(set(signatures))


@pytest.mark.parametrize("count", [5, 16])
def test_general_variation_contract_preserves_native_multi_image_range(count: int) -> None:
    contract = _general_contract(count=count)

    assert contract.requested_image_count == count
    assert len(contract.outputs) == count
    assert [item.output_index for item in contract.outputs] == list(range(1, count + 1))
    assert len({(item.output_purpose, tuple(item.variation_axes)) for item in contract.outputs}) == count


@pytest.mark.parametrize(
    ("mode", "count"),
    [
        (mode, count)
        for mode in (
            "selection_candidates",
            "delivery_suite",
            "creative_exploration",
            "format_layout_adaptation",
        )
        for count in (5, 16)
    ],
)
def test_general_suite_director_preserves_native_multi_image_range(mode: str, count: int) -> None:
    plan = GeneralSuiteDirector().build(
        project_id="project_variation_contract",
        job_id="job_variation_contract",
        user_input="same person image set",
        variation_mode=mode,
        requested_image_count=count,
        has_identity_anchor=True,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
    )

    assert plan.requested_image_count == count
    assert len(plan.roles) == count
    assert [role.metadata["index"] for role in plan.roles] == list(range(1, count + 1))


@pytest.mark.parametrize(
    ("mode", "count"),
    [
        (mode, count)
        for mode in (
            "selection_candidates",
            "delivery_suite",
            "creative_exploration",
            "format_layout_adaptation",
        )
        for count in (5, 16)
    ],
)
def test_general_fallback_preserves_native_multi_image_range(mode: str, count: int) -> None:
    result = build_fallback_result(
        BrainRunRequest(
            user_input="Create a varied image set for the same subject.",
            stage="plan",
            scenario_id="general_creative",
            template_id="general_template",
            requested_image_count=count,
            metadata={"variation_mode": mode},
        )
    )

    assert result.image_set_plan.image_count == count
    assert len(result.image_set_plan.shot_plan) == count


@pytest.mark.parametrize("model", [VariationExecutionOutput, VariationExecutionReceipt])
def test_variation_execution_output_indices_reject_bool(model) -> None:  # noqa: ANN001
    fields = {
        "output_index": True,
    }
    if model is VariationExecutionOutput:
        fields.update({
            "output_purpose": "primary_presentation",
            "variation_axes": ["presentation"],
        })
    else:
        fields.update({
            "contract_version": "v3_general_variation_execution_v1",
            "contract_digest": "0" * 64,
            "status": "approved",
            "owner": "remote_v3_llm_brain",
        })

    with pytest.raises(ValidationError):
        model(**fields)


def test_public_product_api_rejects_fresh_variation_contract_metadata() -> None:
    variation_keys = {
        "variation_execution_contract",
        "variation_execution_contract_binding",
        "variation_execution_contract_enforced",
        "variation_execution_mode",
        "variation_execution_requested_image_count",
        "variation_execution_suite_direction_authoritative",
        "variation_execution_role_binding",
    }
    request = CreateCreativeJobRequest(
        user_input="Create a varied General image set.",
        metadata={key: {"forged": True} for key in variation_keys},
    )

    with pytest.raises(ValueError, match="runtime_metadata_server_owned") as exc_info:
        V3ProductApiService().create_job(request)

    assert variation_keys <= set(str(exc_info.value).split(": ", 1)[1].split(", "))


def _trusted_variation_snapshot(contract: VariationExecutionContract) -> dict[str, object]:
    return {
        "job_id": "job_parent_variation",
        "capability_activation_plan": {
            "plan_id": "plan_parent_variation",
            "fingerprint": "f" * 64,
        },
        "capability_plan_provenance": {},
        "variation_execution_contract": contract.model_dump(mode="json"),
        "variation_execution_contract_binding": {
            "contract_version": contract.contract_version,
            "contract_digest": contract.contract_digest,
        },
        "variation_execution_contract_enforced": True,
        "variation_execution_mode": contract.mode,
        "variation_execution_requested_image_count": contract.requested_image_count,
        "variation_execution_suite_direction_authoritative": True,
    }


def test_missing_parent_job_restores_verified_variation_snapshot_over_child_metadata() -> None:
    parent_contract = _general_contract(count=3, mode="creative_exploration")
    snapshot = _trusted_variation_snapshot(parent_contract)
    child_contract = _general_contract(count=2, mode="selection_candidates")
    request = CreateCreativeJobRequest(
        user_input="Continue the approved image set.",
        metadata={
            "capability_activation_plan": dict(snapshot["capability_activation_plan"]),
            "capability_plan_reuse_source_job_id": "job_parent_variation",
            "capability_plan_reuse_source_snapshot": snapshot,
            "variation_execution_contract": child_contract.model_dump(mode="json"),
            "variation_execution_contract_binding": {
                "contract_version": child_contract.contract_version,
                "contract_digest": child_contract.contract_digest,
            },
            "variation_execution_contract_enforced": True,
            "variation_execution_mode": child_contract.mode,
            "variation_execution_requested_image_count": child_contract.requested_image_count,
            "variation_execution_suite_direction_authoritative": True,
        },
    )

    V3ProductApiService()._validate_and_bind_trusted_capability_plan_reuse(request)  # noqa: SLF001

    assert request.metadata["variation_execution_mode"] == parent_contract.mode
    assert request.metadata["variation_execution_requested_image_count"] == parent_contract.requested_image_count
    assert request.metadata["variation_execution_contract"] == parent_contract.model_dump(mode="json")
    assert request.metadata["variation_execution_contract_binding"] == {
        "contract_version": parent_contract.contract_version,
        "contract_digest": parent_contract.contract_digest,
    }


def test_missing_parent_job_rejects_tampered_variation_snapshot() -> None:
    parent_contract = _general_contract(count=3)
    snapshot = _trusted_variation_snapshot(parent_contract)
    tampered = dict(snapshot["variation_execution_contract"])
    tampered["mode"] = "selection_candidates"
    snapshot["variation_execution_contract"] = tampered
    request = CreateCreativeJobRequest(
        user_input="Continue the approved image set.",
        metadata={
            "capability_activation_plan": dict(snapshot["capability_activation_plan"]),
            "capability_plan_reuse_source_job_id": "job_parent_variation",
            "capability_plan_reuse_source_snapshot": snapshot,
        },
    )

    with pytest.raises(ValueError, match="trusted_variation_execution_contract_invalid"):
        V3ProductApiService()._validate_and_bind_trusted_capability_plan_reuse(request)  # noqa: SLF001


def test_compact_real_brain_payload_gates_contract_to_general_multi_image() -> None:
    contract = _general_contract(count=3).model_dump(mode="json")
    binding = {
        "contract_version": contract["contract_version"],
        "contract_digest": contract["contract_digest"],
    }
    shared = {
        "visual_cluster": {
            "variation_execution_contract": contract,
            "role_specific_generation_plan": {
                "role_key": "cover_hero",
                "prompt_additions": ["historical local renderer wording"],
            },
        }
    }
    general_request = BrainRunRequest(
        user_input="Create a real photographic set with one person.",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=3,
        metadata={
            "require_real_images": True,
            "variation_execution_contract_enforced": True,
            "variation_execution_contract_binding": binding,
        },
        shared_capabilities=shared,
    )

    general_payload = json.loads(build_remote_payload(general_request))
    serialized_general = json.dumps(general_payload)
    assert general_payload["variation_execution_contract"] == contract
    assert "role_specific_generation_plan" not in serialized_general
    assert "prompt_additions" not in serialized_general
    assert "prompt_pressure" not in serialized_general
    assert "camera_distance" not in serialized_general

    single_payload = json.loads(
        build_remote_payload(general_request.model_copy(update={"requested_image_count": 1}))
    )
    assert "variation_execution_contract" not in single_payload

    specialized_payload = json.loads(
        build_remote_payload(
            general_request.model_copy(
                update={
                    "scenario_id": "ecommerce",
                    "template_id": "ecommerce_template",
                    "template_capability_policy": ecommerce_capability_policy(),
                }
            )
        )
    )
    assert "variation_execution_contract" not in specialized_payload

    photography_payload = json.loads(
        build_remote_payload(
            general_request.model_copy(
                update={
                    "scenario_id": "photography",
                    "template_id": "photography_template",
                    "template_capability_policy": photography_capability_policy(),
                }
            )
        )
    )
    assert "variation_execution_contract" not in photography_payload


def test_finalizer_context_keeps_frozen_contract_and_old_cluster_records_stay_readable() -> None:
    contract = _general_contract(count=3)
    projection = {
        "scenario_id": "general_creative",
        "template_id": "general_template",
        "effective_image_count": 3,
        "capability_projection": {
            "variation_execution_contract": contract.model_dump(mode="json"),
            "variation_execution_contract_binding": {
                "contract_version": contract.contract_version,
                "contract_digest": contract.contract_digest,
            },
        },
    }
    context = ScenarioRuntime._canonical_prompt_context(
        SimpleNamespace(metadata={}, uploaded_assets=[]),
        SimpleNamespace(dependency_order=[]),
        SimpleNamespace(envelope_id="envelope", execution_fingerprint="fingerprint"),
        SimpleNamespace(ledger_id="ledger", provider_projection=projection),
        SimpleNamespace(image_set_plan=SimpleNamespace(shot_plan=[]), visual_task_profile=None),
    )

    assert context["variation_execution_contract"] == contract.model_dump(mode="json")
    assert context["frozen_binding"]["variation_execution_contract"] == {
        "contract_version": contract.contract_version,
        "contract_digest": contract.contract_digest,
    }
    finalizer_payload = json.loads(
        build_remote_payload(
            BrainRunRequest(
                user_input="Create the approved real image set.",
                stage="provider_prompt_finalize",
                scenario_id="general_creative",
                template_id="general_template",
                requested_image_count=3,
                metadata={"canonical_prompt_context": context},
            )
        )
    )
    assert (
        finalizer_payload["frozen_render_context"]["variation_execution_contract"]
        == contract.model_dump(mode="json")
    )

    old_cluster = VisualCapabilityClusterResult(
        cluster_id="old_cluster",
        version="old",
        scenario_id="general_creative",
        profile=VisualGrammarProfile(profile_id="profile", scenario_id="general_creative"),
        project_snapshot=ProjectVisualGrammarSnapshot(snapshot_id="snapshot"),
        reference_binding_profile=VisualReferenceBindingProfile(binding_id="binding"),
        consistency_guard=VisualConsistencyGuardResult(),
        quality_review=VisualQualityReviewResult(),
    )
    assert old_cluster.variation_execution_contract is None


def _finalizer_request(contract: VariationExecutionContract | None) -> BrainRunRequest:
    context: dict[str, object] = {"variation_execution_contract_required": contract is not None}
    if contract is not None:
        context["variation_execution_contract"] = contract.model_dump(mode="json")
        context["frozen_binding"] = {
            "variation_execution_contract": {
                "contract_version": contract.contract_version,
                "contract_digest": contract.contract_digest,
            }
        }
    return BrainRunRequest(
        user_input="Create the approved real image set.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=contract.requested_image_count if contract is not None else 3,
        metadata={"canonical_prompt_context": context},
    )


def test_active_visual_cluster_reuses_the_runtime_bound_contract() -> None:
    contract = _general_contract(count=3)
    capability_input = SimpleNamespace(
        scenario_id="general_creative",
        metadata={
            "resolved_scenario_id": "general_creative",
            "resolved_template_id": "general_template",
            "variation_execution_contract_enforced": True,
            "variation_execution_mode": contract.mode,
            "variation_execution_requested_image_count": contract.requested_image_count,
            "variation_execution_contract": contract.model_dump(mode="json"),
            "variation_execution_contract_binding": {
                "contract_version": contract.contract_version,
                "contract_digest": contract.contract_digest,
            },
        },
    )
    module = VisualCapabilityClusterModule()

    assert module._variation_execution_contract_from_runtime(capability_input, 3) == contract  # noqa: SLF001

    tampered = contract.model_dump(mode="json")
    tampered["outputs"][0]["output_purpose"] = "detail_focus"
    capability_input.metadata["variation_execution_contract"] = tampered
    with pytest.raises(ValueError):
        module._variation_execution_contract_from_runtime(capability_input, 3)  # noqa: SLF001


@pytest.mark.parametrize("activation_mode", ["legacy", "shadow"])
def test_legacy_and_shadow_initial_paths_do_not_inject_a_new_contract(activation_mode: str) -> None:
    runtime = ScenarioRuntime()
    request = BrainRunRequest(
        user_input="Create a real photographic set.",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=3,
        metadata={
            "capability_activation_plan": {"activation_mode": activation_mode},
            "requested_image_count": 3,
        },
    )
    resolution = SimpleNamespace(
        manifest=SimpleNamespace(scenario_id="general_creative"),
        selected_mode_id=None,
        selected_preset_id=None,
    )
    normalized_intent = SimpleNamespace(effective_image_count=3)

    bound = runtime._bind_initial_general_variation_contract(  # noqa: SLF001
        request,
        resolution,
        normalized_intent,
    )

    assert bound.metadata == request.metadata
    assert "variation_execution_contract_enforced" not in bound.metadata


def test_runtime_and_active_use_the_same_typed_contract_and_role_binding() -> None:
    runtime = ScenarioRuntime()
    request = ScenarioRuntimeRequest(
        user_input="Create a real photographic set with one person.",
        uploaded_assets=[UploadedAssetInfo(asset_id="face-1", role="face_reference")],
        metadata={"requested_image_count": 3},
    )
    resolution = SimpleNamespace(
        manifest=SimpleNamespace(scenario_id="general_creative"),
        selected_mode_id=None,
        selected_preset_id=None,
    )
    normalized_intent = SimpleNamespace(effective_image_count=3)

    bound = runtime._bind_initial_general_variation_contract(  # noqa: SLF001
        request,
        resolution,
        normalized_intent,
    )
    contract = VariationExecutionContract.model_validate(
        bound.metadata["variation_execution_contract"]
    )
    assert bound.metadata["variation_execution_role_binding"] == {
        "subject_type": "character",
        "has_identity_anchor": True,
        "source": "runtime_typed_reference_facts",
    }

    module = runtime.shared_capability_registry.get("visual_capability_cluster")
    assert isinstance(module, VisualCapabilityClusterModule)
    active_input = SimpleNamespace(
        scenario_id="general_creative",
        metadata={
            **bound.metadata,
            "brain_owned_forward_execution": True,
            "capability_activation_plan": {
                "activation_mode": "enforced",
                "dependency_order": ["suite_direction"],
            },
        },
    )
    active_contract = module._variation_execution_contract_from_runtime(active_input, 3)  # noqa: SLF001

    assert active_contract is not None
    assert active_contract.contract_version == contract.contract_version
    assert active_contract.contract_digest == contract.contract_digest
    assert active_contract.model_dump(mode="json") == contract.model_dump(mode="json")


@pytest.mark.parametrize(
    ("mode", "count"),
    [("creative_exploration", 3), ("creative_exploration", 5), ("format_layout_adaptation", 4)],
)
def test_runtime_bound_mode_and_count_override_ambiguous_active_context(
    mode: str,
    count: int,
) -> None:
    runtime = ScenarioRuntime()
    request = ScenarioRuntimeRequest(
        user_input="Create a varied General image set.",
        scenario_selection={
            "scenario_id": "general_creative",
            "parameters": {
                "variation_mode": "delivery_suite",
                "requested_image_count": 2,
            },
        },
        metadata={
            "requested_image_count": count,
            "variation_mode": mode,
        },
    )
    resolution = SimpleNamespace(
        manifest=SimpleNamespace(scenario_id="general_creative"),
        selected_mode_id=None,
        selected_preset_id=None,
    )
    bound = runtime._bind_initial_general_variation_contract(  # noqa: SLF001
        request,
        resolution,
        SimpleNamespace(effective_image_count=count),
    )
    contract = VariationExecutionContract.model_validate(
        bound.metadata["variation_execution_contract"]
    )
    assert bound.metadata["variation_execution_mode"] == mode
    assert contract.mode == mode
    assert bound.metadata["variation_execution_requested_image_count"] == count

    active_input = SimpleNamespace(
        scenario_id="general_creative",
        metadata={
            **bound.metadata,
            "brain_owned_forward_execution": True,
            "scenario_parameters": {
                "variation_mode": "delivery_suite",
                "requested_image_count": 2,
            },
            "capability_activation_plan": {
                "activation_mode": "enforced",
                "dependency_order": ["suite_direction"],
            },
        },
    )
    project_context = {
        "metadata": {
            "variation_mode": "delivery_suite",
            "requested_image_count": 2,
        }
    }
    module = VisualCapabilityClusterModule()

    assert module._effective_variation_mode(active_input, project_context) == contract.mode  # noqa: SLF001
    assert module._requested_image_count(active_input, project_context) == count  # noqa: SLF001


class _CapturingRuntimeBrainAdapter:
    def __init__(self) -> None:
        self.last_request: BrainRunRequest | None = None

    def build_request(self, **kwargs) -> BrainRunRequest:  # noqa: ANN003
        self.last_request = BrainRunRequest(
            user_input=kwargs["user_input"],
            job_id=kwargs.get("job_id"),
            stage=kwargs["stage"],
            scenario_id=kwargs["scenario_id"],
            template_id=kwargs["template_id"],
            metadata=dict(kwargs["metadata"]),
            shared_capabilities=dict(kwargs.get("shared_capabilities") or {}),
            uploaded_assets=list(kwargs.get("uploaded_assets") or []),
            product_profile=dict(kwargs.get("product_profile") or {}),
        )
        return self.last_request

    def run(self, _request: BrainRunRequest) -> SimpleNamespace:
        return SimpleNamespace()


@pytest.mark.parametrize("activation_mode", ["legacy", "shadow"])
def test_run_llm_brain_drops_a_residual_enforced_marker_from_compatibility_paths(
    monkeypatch,
    activation_mode: str,
) -> None:
    contract = _general_contract(count=3)
    adapter = _CapturingRuntimeBrainAdapter()
    runtime = ScenarioRuntime(llm_brain_adapter=adapter)
    request = ScenarioRuntimeRequest(
        user_input="Create a real photographic set.",
        metadata={
            "requested_image_count": 3,
            "capability_activation_plan": {
                "activation_mode": activation_mode,
                "dependency_order": [],
            },
            "variation_execution_contract_enforced": True,
            "variation_execution_contract": contract.model_dump(mode="json"),
            "variation_execution_contract_binding": {
                "contract_version": contract.contract_version,
                "contract_digest": contract.contract_digest,
            },
        },
    )
    resolution = SimpleNamespace(manifest=SimpleNamespace(scenario_id="general_creative"))
    monkeypatch.setattr(
        runtime,
        "_frozen_remote_creative_brain_for_execution",
        lambda _request, _resolution, **_kwargs: None,
    )
    monkeypatch.setattr(
        runtime,
        "_brain_runtime_metadata",
        lambda _request, _resolution, **_kwargs: dict(_request.metadata),
    )
    monkeypatch.setattr(runtime, "_runtime_job_id", lambda *_args: "job-residual-marker")
    monkeypatch.setattr(runtime, "_template_id", lambda *_args: "general_template")

    runtime._run_llm_brain(  # noqa: SLF001
        request,
        resolution,
        None,
        stage="plan",
    )

    assert adapter.last_request is not None
    assert "variation_execution_contract_enforced" not in adapter.last_request.metadata
    assert "variation_execution_contract" not in json.dumps(
        adapter.last_request.shared_capabilities
    )


def test_bound_variation_contract_rejects_nested_mutation_and_keeps_digest_stable() -> None:
    contract = _general_contract(count=3)
    digest = contract.contract_digest

    with pytest.raises(AttributeError):
        contract.outputs[0].variation_axes.append("framing")  # type: ignore[attr-defined]
    with pytest.raises(ValidationError):
        contract.outputs[0].output_purpose = "detail_focus"  # type: ignore[misc]

    assert contract.contract_digest == digest
    assert contract.contract_digest == contract.computed_digest()


def test_brain_count_probe_keeps_legacy_lightweight_request_compatibility() -> None:
    runtime = ScenarioRuntime(llm_brain_adapter=_CapturingRuntimeBrainAdapter())
    request = SimpleNamespace(metadata={"requested_image_count": 3})

    assert runtime._requested_image_count_for_brain(request) == 3  # noqa: SLF001


@pytest.mark.parametrize(
    "metadata, shared_capabilities",
    [
        (
            {
                "variation_execution_contract_enforced": True,
                "variation_execution_contract_binding": {
                    "contract_version": "v3_general_variation_execution_v1",
                    "contract_digest": "0" * 64,
                },
            },
            {},
        ),
        (
            {
                "variation_execution_contract_enforced": True,
                "variation_execution_contract_binding": {
                    "contract_version": "v3_general_variation_execution_v1",
                    "contract_digest": "0" * 64,
                },
            },
            {"visual_cluster": {"variation_execution_contract": {"bad": "contract"}}},
        ),
    ],
)
def test_compact_general_helper_fails_closed_for_missing_or_invalid_bound_contract(
    metadata: dict,
    shared_capabilities: dict,
) -> None:
    request = BrainRunRequest(
        user_input="Create a real photographic set.",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=3,
        metadata={"require_real_images": True, **metadata},
        shared_capabilities=shared_capabilities,
    )

    with pytest.raises(BrainPromptContractInvalid, match="General variation execution contract"):
        build_remote_payload(request)


def _canonical_prompts_for(contract: VariationExecutionContract, *, include_receipts: bool = True) -> list[dict]:
    prompts = []
    for output_index in range(1, contract.requested_image_count + 1):
        item = {
            "output_index": output_index,
            "prompt": f"A complete Brain-authored photographic direction for output {output_index}.",
            "review_status": "approved",
        }
        if include_receipts:
            item["variation_execution_receipt"] = {
                "contract_version": contract.contract_version,
                "contract_digest": contract.contract_digest,
                "output_index": output_index,
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            }
        prompts.append(item)
    return prompts


class _CanonicalPromptProvider:
    provider = "variation_contract_test_provider"
    model = "fixture-v1"

    def __init__(self, response: dict) -> None:
        self.response = response

    def available(self, *, force: bool = False) -> bool:
        return True

    def run(self, request) -> dict:  # noqa: ANN001
        return self.response


def test_finalizer_schema_requires_the_same_general_contract_receipt() -> None:
    contract = _general_contract(count=3)
    payload = json.loads(build_remote_payload(_finalizer_request(contract)))
    schema = payload["return_schema"]["canonical_provider_prompts"][0]

    assert schema["variation_execution_receipt"] == {
        "contract_version": contract.contract_version,
        "contract_digest": contract.contract_digest,
        "output_index": "same integer as this canonical_provider_prompts item",
        "status": "approved|rewritten",
        "owner": "remote_v3_llm_brain",
    }
    assert payload["frozen_render_context"]["variation_execution_contract"] == contract.model_dump(mode="json")

    single = _finalizer_request(contract).model_copy(
        update={
            "requested_image_count": 1,
            "metadata": {
                "canonical_prompt_context": {
                    "variation_execution_contract": contract.model_dump(mode="json"),
                }
            },
        }
    )
    single_payload = json.loads(build_remote_payload(single))
    assert "variation_execution_receipt" not in single_payload["return_schema"]["canonical_provider_prompts"][0]
    assert "variation_execution_contract" not in single_payload["frozen_render_context"]

    specialized = _finalizer_request(contract).model_copy(
        update={
            "scenario_id": "photography",
            "template_id": "photography_template",
            "template_capability_policy": photography_capability_policy(),
        }
    )
    specialized_payload = json.loads(build_remote_payload(specialized))
    assert "variation_execution_receipt" not in specialized_payload["return_schema"]["canonical_provider_prompts"][0]
    assert "variation_execution_contract" not in specialized_payload["frozen_render_context"]


def test_finalizer_accepts_receipts_bound_to_the_frozen_contract(monkeypatch) -> None:
    contract = _general_contract(count=3)
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    adapter = V3LLMBrainAdapter(
        provider=_CanonicalPromptProvider(
            {"canonical_provider_prompts": _canonical_prompts_for(contract)}
        )
    )

    prompts, audit = adapter.finalize_canonical_provider_prompts(_finalizer_request(contract))

    assert prompts[0].variation_execution_receipt is not None
    assert prompts[0].variation_execution_receipt.contract_digest == contract.contract_digest
    assert audit["variation_execution_contract_required"] is True
    assert audit["variation_execution_receipts_signed"] is True


@pytest.mark.parametrize("receipt_case", ["missing", "wrong_digest"])
def test_finalizer_fails_closed_for_missing_or_illegal_receipt(monkeypatch, receipt_case: str) -> None:
    contract = _general_contract(count=3)
    response = {"canonical_provider_prompts": _canonical_prompts_for(contract)}
    if receipt_case == "missing":
        response["canonical_provider_prompts"] = _canonical_prompts_for(contract, include_receipts=False)
    else:
        response["canonical_provider_prompts"][1]["variation_execution_receipt"]["contract_digest"] = "0" * 64
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    adapter = V3LLMBrainAdapter(provider=_CanonicalPromptProvider(response))

    with pytest.raises(BrainPromptContractInvalid):
        adapter.finalize_canonical_provider_prompts(_finalizer_request(contract))


def test_finalizer_rejects_a_drifted_contract_digest(monkeypatch) -> None:
    contract = _general_contract(count=3)
    context = contract.model_dump(mode="json")
    context["outputs"][0]["output_purpose"] = "changed after planning"
    request = _finalizer_request(contract).model_copy(
        update={
            "metadata": {
                "canonical_prompt_context": {
                    "variation_execution_contract_required": True,
                    "variation_execution_contract": context,
                }
            }
        }
    )
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    adapter = V3LLMBrainAdapter(
        provider=_CanonicalPromptProvider({"canonical_provider_prompts": []})
    )

    with pytest.raises(BrainPromptContractInvalid):
        adapter.finalize_canonical_provider_prompts(request)


@pytest.mark.parametrize("binding_field", ["contract_version", "contract_digest"])
def test_finalizer_rejects_a_tampered_frozen_contract_binding(monkeypatch, binding_field: str) -> None:
    contract = _general_contract(count=3)
    request = _finalizer_request(contract)
    context = request.metadata["canonical_prompt_context"]
    frozen_binding = context["frozen_binding"]["variation_execution_contract"]
    frozen_binding[binding_field] = (
        "wrong-version"
        if binding_field == "contract_version"
        else "0" * 64
    )
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    adapter = V3LLMBrainAdapter(
        provider=_CanonicalPromptProvider({"canonical_provider_prompts": _canonical_prompts_for(contract)})
    )

    with pytest.raises(BrainPromptContractInvalid):
        adapter.finalize_canonical_provider_prompts(request)
