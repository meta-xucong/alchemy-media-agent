"""Doc118 planning-only bridge from local stdio MCP to frozen V3 planning."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus

from .contracts import (
    NATIVE_EXECUTION_CHANNEL,
    NativeImageGenPlanRequest,
    public_reference_instructions,
)
from .provenance import native_plan_provenance


_TEMPLATE_SCENARIOS = {
    "general_template": "general_creative",
    "ecommerce_template": "ecommerce",
    "photographer_template": "photography",
}


class PlanningOnlyGenerationRouter:
    """Sentinel injected into ScenarioRuntime so this facade cannot render."""

    def generate(self, *_: Any, **__: Any) -> Any:
        raise RuntimeError("Doc118 planning-only facade must never call a generation provider")


class CodexNativeImageGenPlanner:
    """Build public-safe image-tool prompts without creating images or outputs."""

    def __init__(self, runtime_factory: Callable[[], ScenarioRuntime] | None = None) -> None:
        self._runtime_factory = runtime_factory or self._default_runtime

    @staticmethod
    def _default_runtime() -> ScenarioRuntime:
        # ScenarioRuntime otherwise supplies GenerationRouter(), whose default
        # constructor includes the production renderer.  Planning never needs
        # it, so provide a fail-closed sentinel instead.
        return ScenarioRuntime(generation_router=PlanningOnlyGenerationRouter())

    def prepare_native_imagegen_plan(self, request: NativeImageGenPlanRequest) -> dict[str, Any]:
        scenario_id = _TEMPLATE_SCENARIOS.get(request.template_id)
        if scenario_id is None:
            return self._blocked("codex_native_imagegen_template_invalid", "The selected template is unavailable for Codex Native ImageGen Mode.")
        missing = [item.channel for item in request.reference_declarations if item.required and not item.attached_in_current_codex_conversation]
        if missing:
            return self._blocked(
                "codex_native_imagegen_required_reference_missing",
                "A required reference is not attached in the current Codex conversation.",
            )

        runtime = self._runtime_factory()
        result = runtime.plan_job(
            {
                "user_input": request.user_input,
                "scenario_selection": {
                    "scenario_id": scenario_id,
                    "parameters": {"requested_image_count": request.requested_image_count},
                },
                "metadata": {
                    "template_id": request.template_id,
                    "requested_image_count": request.requested_image_count,
                    "requested_image_size": request.requested_image_size,
                    "codex_native_reference_declarations": [
                        {
                            "channel": item.channel,
                            "attached_in_current_codex_conversation": item.attached_in_current_codex_conversation,
                            "required": item.required,
                        }
                        for item in request.reference_declarations
                    ],
                },
            }
        )
        if result.status != ScenarioRuntimeStatus.PLANNED or result.planning_result is None:
            return self._blocked_from_runtime(result.metadata, "Codex Native ImageGen planning was blocked before any image was created.")

        frozen_plan = result.metadata.get("template_deliverable_plan")
        ledger = result.metadata.get("resolved_constraint_ledger")
        envelope = result.metadata.get("capability_execution_envelope")
        normalized = result.metadata.get("normalized_v3_job_intent")
        if not all(isinstance(item, dict) for item in (frozen_plan, ledger, envelope, normalized)):
            return self._blocked("codex_native_imagegen_frozen_plan_missing", "V3 planning did not produce a complete frozen planning contract.")
        deliverables = frozen_plan.get("deliverables")
        prompts = result.planning_result.prompt_compilations
        if not isinstance(deliverables, list) or len(deliverables) != request.requested_image_count or len(prompts) != request.requested_image_count:
            return self._blocked("codex_native_imagegen_role_count_mismatch", "V3 planning returned a count that does not match the requested outputs.")
        if int(normalized.get("effective_image_count") or 0) != request.requested_image_count:
            return self._blocked("codex_native_imagegen_count_mismatch", "V3 planning did not preserve the requested image count.")

        instructions = public_reference_instructions(request.reference_declarations)
        outputs: list[dict[str, Any]] = []
        for index, (deliverable, prompt) in enumerate(zip(deliverables, prompts, strict=True), 1):
            if not isinstance(deliverable, dict) or deliverable.get("output_index") != index:
                return self._blocked("codex_native_imagegen_role_lineage_invalid", "V3 planning returned an invalid frozen output lineage.")
            role_lineage = str(deliverable.get("deliverable_id") or "").strip()
            if not role_lineage:
                return self._blocked("codex_native_imagegen_role_lineage_invalid", "V3 planning did not provide a frozen output lineage.")
            image_prompt = str(prompt.visual_prompt or "").strip()
            if not image_prompt:
                return self._blocked("codex_native_imagegen_prompt_missing", "V3 planning did not produce an ImageGen-ready prompt.")
            outputs.append(
                {
                    "output_index": index,
                    "role_lineage": role_lineage,
                    "imagegen_prompt": image_prompt,
                    "hard_constraints": [str(item) for item in prompt.hard_constraints if str(item).strip()],
                    "text_policy": str(prompt.text_policy or normalized.get("text_policy") or "provider_native_no_forced_text"),
                    "reference_instructions": list(instructions),
                }
            )

        return {
            "status": "planned_for_codex_native_imagegen",
            "execution_channel": NATIVE_EXECUTION_CHANNEL,
            "requested_output_count": request.requested_image_count,
            "outputs": outputs,
            "provenance": native_plan_provenance(
                template_id=request.template_id,
                scenario_id=scenario_id,
                output_count=request.requested_image_count,
                activation_plan_id=str(envelope.get("envelope_id") or ""),
                constraint_ledger_id=str(ledger.get("ledger_id") or ""),
                fallback_used=bool((result.metadata.get("llm_brain") or {}).get("fallback_used")),
            ),
        }

    @staticmethod
    def _blocked(code: str, message: str) -> dict[str, Any]:
        return {
            "status": "blocked",
            "code": code,
            "message": message,
            "execution_channel": NATIVE_EXECUTION_CHANNEL,
            "delivery_state": "no_image_created",
        }

    def _blocked_from_runtime(self, metadata: dict[str, Any], message: str) -> dict[str, Any]:
        remote = metadata.get("remote_creative_brain_outcome") if isinstance(metadata, dict) else None
        if isinstance(remote, dict) and str(remote.get("reason_code") or "").strip():
            return self._blocked(f"codex_native_imagegen_{str(remote['reason_code'])}", message)
        return self._blocked("codex_native_imagegen_planning_blocked", message)
