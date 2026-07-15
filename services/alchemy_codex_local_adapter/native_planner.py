"""Doc129 constraint-admission bridge from local stdio MCP to Codex ImageGen."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus

from .contracts import (
    NATIVE_EXECUTION_CHANNEL,
    NativeImageGenPlanRequest,
    public_reference_instructions,
)
from .provenance import native_plan_provenance


_TEMPLATE_SCENARIOS = {"general_template": "general_creative"}
_DEFERRED_TEMPLATE_IDS = frozenset({"ecommerce_template", "photographer_template"})
_FORBIDDEN_LOCAL_CREATIVE_CAPABILITIES = frozenset({"suite_direction"})


class PlanningOnlyGenerationRouter:
    """Sentinel injected into ScenarioRuntime so this facade cannot render."""

    def generate(self, *_: Any, **__: Any) -> Any:
        raise RuntimeError("Doc126 planning-only facade must never call a generation provider")


class NativePlanningNoRemoteBrainProvider:
    """Keep Local Mode independent from Web Mode's configured remote Brain.

    The resulting deterministic runtime answer is allowed to help V3 freeze
    admission contracts, but it is never surfaced as a creative direction.
    The current Codex conversation owns the natural-language direction.
    """

    provider = "codex_native_no_remote_brain"
    model = "not-applicable"

    def available(self, *, force: bool = False) -> bool:  # noqa: ARG002
        return False

    def run(self, *_: Any, **__: Any) -> Any:
        raise RuntimeError("Doc126 Local Mode must never call a remote Central Brain")


class CodexNativeImageGenPlanner:
    """Freeze non-creative V3 guardrails without creating images or outputs."""

    def __init__(self, runtime_factory: Callable[[], ScenarioRuntime] | None = None) -> None:
        self._runtime_factory = runtime_factory or self._default_runtime

    @staticmethod
    def _default_runtime() -> ScenarioRuntime:
        # ScenarioRuntime otherwise supplies GenerationRouter(), whose default
        # constructor includes the production renderer.  Planning never needs
        # it, so provide a fail-closed sentinel instead.
        return ScenarioRuntime(
            generation_router=PlanningOnlyGenerationRouter(),
            llm_brain_adapter=V3LLMBrainAdapter(provider=NativePlanningNoRemoteBrainProvider()),
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

        instructions = public_reference_instructions(request.reference_declarations)
        guardrails = self._public_guardrails(normalized, envelope)
        capability_ids = self._public_capability_ids(envelope)
        outputs: list[dict[str, Any]] = []
        envelope_id = str(envelope.get("envelope_id") or "").strip()
        if not envelope_id:
            return self._blocked("codex_native_imagegen_envelope_missing_id", "V3 planning did not provide an admission envelope identity.")
        for index in range(1, request.requested_image_count + 1):
            outputs.append(
                {
                    "output_index": index,
                    "output_binding_id": f"codex_native_output_{envelope_id.rsplit('_', 1)[-1]}_{index}",
                    "creative_direction_brief": {
                        "protected_user_intent": str(normalized.get("protected_user_intent") or request.user_input),
                        "requested_image_size": normalized.get("effective_image_size"),
                        "text_policy": str(normalized.get("text_policy") or "provider_native_no_forced_text"),
                        "constraints_to_preserve": guardrails,
                        "active_quality_capabilities": capability_ids,
                        "direction_authoring_instruction": (
                            "Author one self-contained natural-language whole-image direction for this output. "
                            "Use the protected user intent as the creative source and preserve the listed guardrails. "
                            "Do not turn the brief into a keyword stack or add an unrequested predefined image recipe."
                        ),
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
                admission_fallback_observed=bool((result.metadata.get("llm_brain") or {}).get("fallback_used")),
            ),
        }

    @staticmethod
    def _public_capability_ids(envelope: dict[str, Any]) -> list[str]:
        plan = envelope.get("activation_plan") if isinstance(envelope.get("activation_plan"), dict) else {}
        raw = plan.get("active_capabilities") if isinstance(plan.get("active_capabilities"), list) else []
        return [
            capability_id
            for capability_id in (
                str(item.get("capability_id") or "").strip()
                for item in raw
                if isinstance(item, dict)
            )
            if capability_id and capability_id not in _FORBIDDEN_LOCAL_CREATIVE_CAPABILITIES
        ]

    @staticmethod
    def _public_guardrails(normalized: dict[str, Any], envelope: dict[str, Any]) -> list[str]:
        """Return bounded, non-creative invariants for the Codex conversation.

        This deliberately does not read PromptCompiler output, template
        deliverable directions, capability prompt fragments, retry patches, or
        legacy General suite metadata.  Those fields can contain historical
        role/camera recipes and must never influence Codex-native creation.
        """

        guardrails = ["Preserve the user's explicitly stated subject, facts, and intended use."]
        text_policy = str(normalized.get("text_policy") or "")
        if text_policy == "provider_native_text_forbidden":
            guardrails.append("Do not include visible text, labels, logos, watermarks, or decorative copy.")
        elif text_policy == "provider_native_no_forced_text":
            guardrails.append("Do not invent prominent visible copy, labels, logos, or watermarks unless the user explicitly asks for them.")
        else:
            guardrails.append("Any visible text must be explicitly requested by the user; this conversation-only mode cannot certify text fidelity.")
        capability_ids = set(CodexNativeImageGenPlanner._public_capability_ids(envelope))
        if "human_realism" in capability_ids:
            guardrails.append(
                "For any visibly real person, keep appearance, anatomy, expression, and age presentation natural and consistent with the user's requested styling; do not introduce beauty-filter or anatomy-focused details."
            )
        if capability_ids & {"portrait_identity", "product_identity", "nonhuman_subject_identity", "reference_channel_policy"}:
            guardrails.append("Treat each declared reference channel as truth only for that channel; do not substitute or broaden its meaning.")
        return guardrails

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
