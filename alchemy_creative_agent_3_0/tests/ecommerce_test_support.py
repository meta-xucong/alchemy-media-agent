"""Explicit remote-Brain test double for E-Commerce-only tests.

Production never imports this helper.  It exists because E-Commerce correctly
fails closed without a remote creative Brain, while unit tests need a stable
contract-shaped substitute.
"""

from __future__ import annotations

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_fallback_result
from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime


class EcommerceRemoteBrainTestProvider:
    provider = "ecommerce_remote_brain_test_double"
    model = "contract-fixture-v1"

    def available(self, *, force: bool = False) -> bool:
        return True

    def run(self, request) -> dict:
        payload = build_fallback_result(request).model_dump(mode="json")
        count = request.requested_image_count
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


def ecommerce_test_service(**service_kwargs) -> V3ProductApiService:
    runtime = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())
    )
    return V3ProductApiService(scenario_runtime=runtime, **service_kwargs)
