from __future__ import annotations

from copy import deepcopy

from alchemy_creative_agent_3_0.app.generation_router import GenerationRouter
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce import (
    ecommerce_product_truth_selection_contract_issues,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import ecommerce_capability_policy
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


class _SequencedProductTruthProvider(EcommerceRemoteBrainTestProvider):
    def __init__(self, *, fault: str, recover: bool) -> None:
        super().__init__()
        self.fault = fault
        self.recover = recover

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage not in {"plan", "generate"}:
            return payload
        if len(self.requests) == 1 or not self.recover:
            entry = payload["image_set_plan"]["evidence_dimensions_by_output"][0]
            if self.fault == "role":
                entry["product_truth_selection_role"] = "not_a_product_truth_role"
            elif self.fault == "unknown_asset":
                entry["selected_product_truth_asset_ids"] = ["not_in_the_frozen_pool"]
            elif self.fault == "capacity":
                entry["product_truth_selection_role"] = "lifestyle_primary_product_view"
                entry["selected_product_truth_asset_ids"] = ["product_a", "product_b"]
        return payload


def _request(adapter: V3LLMBrainAdapter):
    return adapter.build_request(
        user_input="Create one factual product-on-model image from the supplied product truth.",
        stage="plan",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        uploaded_assets=[
            {
                "asset_id": "product_a",
                "role": "product_reference",
                "metadata": {"codex_native_reference_channel": "product_truth"},
            },
            {
                "asset_id": "product_b",
                "role": "product_reference",
                "metadata": {"codex_native_reference_channel": "product_truth"},
            },
        ],
        metadata={
            "requested_image_count": 1,
            "require_real_images": True,
            "professional_product_truth_required": True,
            "ecommerce_creative_context": {
                "product_truth_reference_pool": [
                    {"asset_id": "product_a", "reference_channel": "product_truth", "source_type": "uploaded"},
                    {"asset_id": "product_b", "reference_channel": "product_truth", "source_type": "uploaded"},
                ],
                "provider_reference_budget": {"max_product_truth_source_refs_per_output": 1},
            },
        },
        template_capability_policy=ecommerce_capability_policy(),
    )


def test_doc281_semantic_product_truth_failure_retries_the_same_request_with_safe_diagnostics() -> None:
    provider = _SequencedProductTruthProvider(fault="role", recover=True)
    adapter = V3LLMBrainAdapter(provider=provider)

    result = adapter.run(_request(adapter))

    assert result.audit["remote_semantic_contract_recovery_attempted"] is True
    assert result.audit["remote_semantic_contract_recovery_succeeded"] is True
    assert len(provider.requests) == 2
    first, second = provider.requests
    assert first["user_input"] == second["user_input"]
    assert first["requested_image_count"] == second["requested_image_count"] == 1
    diagnostics = second["metadata"]["remote_semantic_contract_recovery"]["validation_diagnostics"]
    assert diagnostics["sections"]["image_set_plan"]["validation_error_types"] == ["selection_invalid"]
    assert "not_a_product_truth_role" not in str(diagnostics)
    assert "product_a" not in str(diagnostics)


def test_doc281_unknown_asset_and_capacity_are_rejected_before_runtime() -> None:
    for fault, expected_type in (("unknown_asset", "selection_unknown_asset"), ("capacity", "selection_capacity_exceeded")):
        provider = _SequencedProductTruthProvider(fault=fault, recover=False)
        adapter = V3LLMBrainAdapter(provider=provider)

        result = adapter.run(_request(adapter))

        assert len(provider.requests) == 2
        assert result.audit["remote_contract_rejected_sections"] == ["image_set_plan"]
        diagnostics = result.audit["remote_image_set_validation_audit"]
        assert expected_type in diagnostics["validation_error_types"]
        assert result.audit["remote_semantic_contract_recovery_succeeded"] is False


def test_doc281_shared_contract_matches_the_runtime_semantics() -> None:
    entries = [
        {
            "output_index": 1,
            "evidence_dimensions": [],
            "product_truth_selection_role": "lifestyle_primary_product_view",
            "selected_product_truth_asset_ids": ["product_a", "product_b"],
        }
    ]

    assert ecommerce_product_truth_selection_contract_issues(
        deepcopy(entries),
        expected_count=1,
        allowed_asset_ids={"product_a", "product_b"},
        max_source_refs=1,
    ) == ["selection_invalid", "selection_capacity_exceeded"]


def test_doc281_runtime_blocks_after_bounded_invalid_recovery_before_image_provider() -> None:
    class _NeverImageProvider:
        def __init__(self) -> None:
            self.calls = 0

        def generate(self, request):  # noqa: ANN001
            self.calls += 1
            raise AssertionError("invalid Brain contract must stop before image-provider dispatch")

    provider = _SequencedProductTruthProvider(fault="role", recover=False)
    image_provider = _NeverImageProvider()
    runtime = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=provider),
        generation_router=GenerationRouter(provider=image_provider),
    )

    result = runtime.generate_job(
        {
            "user_input": "Create one factual product-on-model image from the supplied product truth.",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "parameters": {"requested_image_count": 1},
            },
            "uploaded_assets": [
                {
                    "asset_id": "product_a",
                    "role": "product_reference",
                    "metadata": {"codex_native_reference_channel": "product_truth"},
                },
                {
                    "asset_id": "product_b",
                    "role": "product_reference",
                    "metadata": {"codex_native_reference_channel": "product_truth"},
                },
            ],
            "metadata": {
                "requested_image_count": 1,
                "require_real_images": True,
                "professional_product_truth_required": True,
                "ecommerce_creative_context": {
                    "product_truth_reference_pool": [
                        {"asset_id": "product_a", "reference_channel": "product_truth", "source_type": "uploaded"},
                        {"asset_id": "product_b", "reference_channel": "product_truth", "source_type": "uploaded"},
                    ],
                    "provider_reference_budget": {"max_product_truth_source_refs_per_output": 1},
                },
            },
        }
    )

    assert result.status == ScenarioRuntimeStatus.BLOCKED
    assert result.generation_result is None
    assert len(provider.requests) == 2
    assert image_provider.calls == 0


def test_doc281_context_snapshot_drift_and_missing_budget_are_rejected_before_runtime() -> None:
    drift_request = _request(V3LLMBrainAdapter())
    drift_metadata = deepcopy(drift_request.metadata)
    drift_metadata["ecommerce_creative_context"]["product_truth_reference_pool"] = [
        {"asset_id": "product_a", "reference_channel": "product_truth", "source_type": "uploaded"}
    ]
    drift_request = drift_request.model_copy(update={"metadata": drift_metadata}, deep=True)
    drift_provider = _SequencedProductTruthProvider(fault="role", recover=False)
    drift_result = V3LLMBrainAdapter(provider=drift_provider).run(drift_request)

    assert "selection_contract_context_invalid" in drift_result.audit["remote_image_set_validation_audit"][
        "validation_error_types"
    ]

    budget_request = _request(V3LLMBrainAdapter())
    budget_metadata = deepcopy(budget_request.metadata)
    budget_metadata["ecommerce_creative_context"].pop("provider_reference_budget")
    budget_request = budget_request.model_copy(update={"metadata": budget_metadata}, deep=True)
    budget_provider = _SequencedProductTruthProvider(fault="role", recover=False)
    budget_result = V3LLMBrainAdapter(provider=budget_provider).run(budget_request)

    assert "selection_capacity_contract_missing" in budget_result.audit["remote_image_set_validation_audit"][
        "validation_error_types"
    ]
