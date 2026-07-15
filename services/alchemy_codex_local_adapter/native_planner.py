"""Doc130 canonical-provider-prompt bridge from local stdio MCP to Codex ImageGen."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from alchemy_creative_agent_3_0.app.generation_router import (
    ProductionImageGenerationProvider,
    build_provider_generation_request,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus

from .contracts import (
    NATIVE_EXECUTION_CHANNEL,
    NativeImageGenPlanRequest,
    public_reference_instructions,
)
from .provenance import native_plan_provenance


_TEMPLATE_SCENARIOS = {"general_template": "general_creative"}
_DEFERRED_TEMPLATE_IDS = frozenset({"ecommerce_template", "photographer_template"})
class PlanningOnlyGenerationRouter:
    """Sentinel injected into ScenarioRuntime so this facade cannot render."""

    def generate(self, *_: Any, **__: Any) -> Any:
        raise RuntimeError("Doc126 planning-only facade must never call a generation provider")


class CodexNativeImageGenPlanner:
    """Freeze and expose V3's canonical final provider prompts, never pixels."""

    def __init__(self, runtime_factory: Callable[[], ScenarioRuntime] | None = None) -> None:
        self._runtime_factory = runtime_factory or self._default_runtime

    @staticmethod
    def _default_runtime() -> ScenarioRuntime:
        # ScenarioRuntime otherwise supplies GenerationRouter(), whose default
        # constructor includes the production renderer.  Planning never needs
        # it, so provide a fail-closed sentinel instead.
        return ScenarioRuntime(
            generation_router=PlanningOnlyGenerationRouter(),
        )

    def prepare_native_imagegen_plan(self, request: NativeImageGenPlanRequest) -> dict[str, Any]:
        if request.template_id in _DEFERRED_TEMPLATE_IDS:
            return self._blocked(
                "codex_native_imagegen_template_not_enabled",
                "This specialized template is not enabled for Codex Native ImageGen Mode.",
            )
        scenario_id = _TEMPLATE_SCENARIOS.get(request.template_id)
        if scenario_id is None:
            return self._blocked("codex_native_imagegen_template_invalid", "The selected template is unavailable for Codex Native ImageGen Mode.")
        missing = [item.channel for item in request.reference_declarations if item.required and not item.attached_in_current_codex_conversation]
        if missing:
            return self._blocked(
                "codex_native_imagegen_required_reference_missing",
                "A required reference is not attached in the current Codex conversation.",
            )
        if request.reference_declarations:
            return self._blocked(
                "codex_native_imagegen_reference_prompt_parity_unavailable",
                "Codex Native ImageGen prompt parity currently supports text-only requests; it cannot prove the same provider-normalized reference input without a supported attachment handoff.",
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
                    # Local Mode has no image transport, but it must plan as a
                    # real-image job so the shared Runtime requires the same
                    # remote Central Brain contract as the Web Provider path.
                    "require_real_images": True,
                    "real_image_generation": True,
                    "codex_native_reference_declarations": [
                        {
                            "channel": item.channel,
                            "attached_in_current_codex_conversation": item.attached_in_current_codex_conversation,
                        }
                        for item in request.reference_declarations
                    ],
                },
            }
        )
        if result.status != ScenarioRuntimeStatus.PLANNED or result.planning_result is None:
            return self._blocked_from_runtime(result.metadata, "Codex Native ImageGen planning was blocked before any image was created.")

        ledger = result.metadata.get("resolved_constraint_ledger")
        envelope = result.metadata.get("capability_execution_envelope")
        normalized = result.metadata.get("normalized_v3_job_intent")
        if not all(isinstance(item, dict) for item in (ledger, envelope, normalized)):
            return self._blocked("codex_native_imagegen_frozen_plan_missing", "V3 planning did not produce a complete frozen planning contract.")
        if int(normalized.get("effective_image_count") or 0) != request.requested_image_count:
            return self._blocked("codex_native_imagegen_count_mismatch", "V3 planning did not preserve the requested image count.")
        if str(envelope.get("activation_mode") or "") != "enforced":
            return self._blocked("codex_native_imagegen_envelope_not_enforced", "Codex Native ImageGen requires an enforced V3 admission envelope.")
        llm_brain = result.metadata.get("llm_brain") if isinstance(result.metadata.get("llm_brain"), dict) else {}
        if not bool(llm_brain.get("llm_used")) or bool(llm_brain.get("fallback_used")):
            return self._blocked(
                "codex_native_imagegen_remote_brain_required",
                "Codex Native ImageGen requires a valid non-fallback remote Central Brain result.",
            )

        instructions = public_reference_instructions(request.reference_declarations)
        outputs: list[dict[str, Any]] = []
        envelope_id = str(envelope.get("envelope_id") or "").strip()
        if not envelope_id:
            return self._blocked("codex_native_imagegen_envelope_missing_id", "V3 planning did not provide an admission envelope identity.")
        try:
            materializations = self._canonical_materializations(result.planning_result)
        except ValueError:
            return self._blocked(
                "codex_native_imagegen_canonical_prompt_unavailable",
                "V3 could not materialize one canonical Provider prompt for every requested output.",
            )
        if len(materializations) != request.requested_image_count:
            return self._blocked("codex_native_imagegen_count_mismatch", "V3 did not materialize the requested number of canonical Provider prompts.")
        for index, materialization in enumerate(materializations, start=1):
            outputs.append(
                {
                    "output_index": index,
                    "output_binding_id": f"codex_native_output_{envelope_id.rsplit('_', 1)[-1]}_{index}",
                    # Codex must give this exact Unicode string to ImageGen;
                    # the hash is a safe parity receipt, not a second prompt.
                    "imagegen_prompt": materialization.generation_prompt,
                    "provider_prompt_sha256": materialization.prompt_sha256,
                    "rendering_contract": {
                        "model": "gpt-image-2",
                        "size": materialization.size,
                        "quality": materialization.quality,
                        "output_format": materialization.output_format,
                    },
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
                admission_fallback_observed=False,
            ),
        }

    @staticmethod
    def _canonical_materializations(planning_result: Any) -> list[Any]:
        """Materialize every output through the exact Web Provider boundary.

        This creates no Web client, does not select an upstream account, and
        does not send a request.  The shared provider class is used solely as
        the canonical final-prompt materializer.
        """

        assets = {item.asset_id: item for item in planning_result.series_plan.assets}
        layouts = {item.asset_id: item for item in planning_result.layout_plans}
        prompts = {item.asset_id: item for item in planning_result.prompt_compilations}
        conditions = {item.asset_id: item for item in planning_result.condition_plans}
        generation_plans = {item.asset_id: item for item in planning_result.generation_plans}
        if not assets or set(assets) != set(layouts) or set(assets) != set(prompts) or set(assets) != set(conditions) or set(assets) != set(generation_plans):
            raise ValueError("planning result does not have one complete provider contract per asset")
        materializer = ProductionImageGenerationProvider(output_store=object())
        materializations: list[Any] = []
        for asset in planning_result.series_plan.assets:
            request = build_provider_generation_request(
                asset_spec=asset,
                layout_plan=layouts[asset.asset_id],
                prompt_compilation=prompts[asset.asset_id],
                condition_plan=conditions[asset.asset_id],
                generation_plan=generation_plans[asset.asset_id],
                job_id=planning_result.creative_job.job_id,
            )
            materializations.append(materializer.materialize_final_prompt(request))
        return materializations

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
