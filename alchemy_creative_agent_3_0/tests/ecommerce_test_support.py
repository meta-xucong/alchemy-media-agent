"""Explicit remote-Brain test double for E-Commerce-only tests.

Production never imports this helper.  It exists because E-Commerce correctly
fails closed without a remote creative Brain, while unit tests need a stable
contract-shaped substitute.
"""

from __future__ import annotations

from copy import deepcopy

from alchemy_creative_agent_3_0.app.generation_router import GenerationRouter, MockGenerationProvider
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_fallback_result
from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime


class EcommerceRemoteBrainTestProvider:
    provider = "ecommerce_remote_brain_test_double"
    model = "contract-fixture-v1"

    def __init__(self, *, fault: str | None = None) -> None:
        self.fault = fault
        self.requests: list[dict] = []

    def available(self, *, force: bool = False) -> bool:
        return self.fault != "unavailable"

    def run(self, request) -> dict:
        self.requests.append(deepcopy(request.model_dump(mode="json")))
        payload = build_fallback_result(request).model_dump(mode="json")
        count = request.requested_image_count
        if self.fault == "missing_image_set_plan":
            payload.pop("image_set_plan", None)
            return payload
        if self.fault == "empty_image_set_plan":
            payload["image_set_plan"] = {
                "set_goal": "Incomplete remote result",
                "image_count": count,
                "size": request.requested_image_size,
                "shot_plan": [],
            }
            return payload
        if self.fault == "mismatched_image_set_plan":
            payload["image_set_plan"] = {
                "set_goal": "Incomplete remote result",
                "image_count": count,
                "size": request.requested_image_size,
                "shot_plan": ["Only a partial remote direction"],
            }
            return payload
        payload["image_set_plan"] = {
            "set_goal": "Test-only remote Brain product image set",
            "image_count": count,
            "size": request.requested_image_size,
            "shot_plan": [
                f"Remote Brain test output {index}: communicate the supplied product facts and this request's buyer need."
                for index in range(1, count + 1)
            ],
            "evidence_dimensions_by_output": _apparel_evidence_dimensions(request, count),
            "composition_rules": ["Remote Brain decides the complete image treatment for each requested output."],
            "quality_bar": ["Product facts and approved claims remain faithful."],
        }
        payload["prompt_guidance"] = {
            **payload["prompt_guidance"],
            "optimized_direction": "Use the remote Brain's product-specific image intent.",
            "visual_direction_addons": ["Use the remote Brain's product-specific image intent."],
        }
        return payload


def _apparel_evidence_dimensions(request, count: int) -> list[dict]:
    context = request.metadata.get("ecommerce_creative_context") if isinstance(request.metadata, dict) else None
    profile = context.get("apparel_on_model_evidence_profile") if isinstance(context, dict) else None
    if not isinstance(profile, dict) or not profile.get("applies") or count <= 1:
        return []
    dimensions = [str(item) for item in profile.get("allowed_evidence_dimensions", []) if str(item).strip()]
    if not dimensions:
        return []
    entries = []
    for index in range(1, count + 1):
        primary = dimensions[(index - 1) % len(dimensions)]
        evidence = [primary]
        if index > len(dimensions):
            evidence.append(dimensions[index % len(dimensions)])
        entries.append({"output_index": index, "evidence_dimensions": evidence})
    return entries


def ecommerce_test_service(
    *,
    brain_provider: EcommerceRemoteBrainTestProvider | None = None,
    **service_kwargs,
) -> V3ProductApiService:
    # E-Commerce jobs with reference truth deliberately freeze a real-image
    # provider strategy in production.  The test Brain double alone is not
    # enough to make that path hermetic: without an explicit router, the
    # default runtime would materialize ProductionImageGenerationProvider and
    # a unit test could wait on the configured external image gateway.
    #
    # Pin the complete test-only rendering seam to MockGenerationProvider.
    # Passing it as ``provider`` makes the fixture deterministic for every
    # strategy (including reference-conditioned jobs) without relaxing the
    # production strategy contract or modifying application code.
    runtime = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=brain_provider or EcommerceRemoteBrainTestProvider()),
        generation_router=GenerationRouter(provider=MockGenerationProvider()),
    )
    return V3ProductApiService(scenario_runtime=runtime, **service_kwargs)
