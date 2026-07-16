"""Doc130/131 canonical-provider-prompt bridge from local stdio MCP to Codex ImageGen."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from alchemy_creative_agent_3_0.app.generation_router import (
    ProductionImageGenerationProvider,
    build_provider_generation_request,
)
from app.providers.base import ProviderRuntimeError
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
from alchemy_creative_agent_3_0.app.shared_capabilities import AssetRole, UploadedAssetInfo
from alchemy_creative_agent_3_0.app.photography_profiles import (
    GENERAL_PHOTOGRAPHY_PROFILE_ID,
    default_photographer_profile_catalog,
)

from .contracts import (
    NATIVE_EXECUTION_CHANNEL,
    NativeImageGenPlanRequest,
    NativeSpecializedImageGenPlanRequest,
    reference_mime_type,
    reference_role_for_channel,
)
from .provenance import native_plan_provenance


_GENERAL_TEMPLATE_SCENARIOS = {"general_template": "general_creative"}
_SPECIALIZED_TEMPLATE_SCENARIOS = {
    "ecommerce_template": "ecommerce",
    "photographer_template": "photography",
}
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
        """Prepare the stable General-only Local Mode contract.

        Specialist templates deliberately have their own public entry point;
        accepting them here would make a caller unable to see or validate the
        specialist factual/profile contract that is part of the frozen plan.
        """

        if request.template_id in _SPECIALIZED_TEMPLATE_SCENARIOS:
            return self._blocked(
                "codex_native_imagegen_template_not_enabled",
                "This specialized template requires the explicit frozen specialized-plan Local Mode tool.",
            )
        scenario_id = _GENERAL_TEMPLATE_SCENARIOS.get(request.template_id)
        if scenario_id is None:
            return self._blocked("codex_native_imagegen_template_invalid", "The selected template is unavailable for Codex Native ImageGen Mode.")
        return self._prepare_frozen_plan(
            request,
            scenario_id=scenario_id,
            scenario_selection={
                "scenario_id": scenario_id,
                # Canvas is a frozen user contract just like output count.
                # Put it through the normal Scenario Selection boundary as
                # well as the normalized metadata record below; otherwise an
                # old General default can silently reassert 1:1 while the
                # Local MCP caller asked for a portrait or landscape canvas.
                "parameters": {
                    "requested_image_count": request.requested_image_count,
                    **({"requested_image_size": request.requested_image_size} if request.requested_image_size else {}),
                },
            },
            metadata={},
        )

    def prepare_frozen_specialized_native_imagegen_plan(
        self,
        request: NativeSpecializedImageGenPlanRequest,
    ) -> dict[str, Any]:
        """Relay a specialist's *existing* runtime plan to Codex ImageGen.

        The adapter contributes no creative direction.  It only constructs
        the same product-level scenario request that the shared runtime needs
        to freeze the template-owned contract, then projects the same
        materialized Web Provider prompt/reference inputs for conversation
        use.  No Project, Provider, review, retry, candidate, or delivery is
        created.
        """

        scenario_id = _SPECIALIZED_TEMPLATE_SCENARIOS.get(request.template_id)
        if scenario_id is None:
            return self._blocked("codex_native_imagegen_template_invalid", "The selected specialized template is unavailable for Codex Native ImageGen Mode.")

        if request.template_id == "ecommerce_template":
            return self._prepare_frozen_plan(
                request,
                scenario_id=scenario_id,
                scenario_selection={
                    "scenario_id": scenario_id,
                    "platform_profile": request.platform_profile,
                    "parameters": {
                        "requested_image_count": request.requested_image_count,
                        **({"requested_image_size": request.requested_image_size} if request.requested_image_size else {}),
                    },
                },
                metadata={"local_mcp_specialized_relay": True},
            )

        # Named profiles are rejected by the request contract because Local
        # Mode has no Project/API immutable-selection transaction.  General
        # Photography is the existing public default and is resolved by the
        # shared catalog, then frozen into the same runtime metadata shape.
        binding = default_photographer_profile_catalog().resolve_binding(
            scenario_id="photography",
            profile_id=GENERAL_PHOTOGRAPHY_PROFILE_ID,
            selection_source=None,
        )
        return self._prepare_frozen_plan(
            request,
            scenario_id=scenario_id,
            scenario_selection={
                "scenario_id": scenario_id,
                "mode_id": request.photography_mode,
                "parameters": {
                    "requested_image_count": request.requested_image_count,
                    **({"requested_image_size": request.requested_image_size} if request.requested_image_size else {}),
                },
            },
            metadata={
                "local_mcp_specialized_relay": True,
                "photographer_profile_binding": binding.model_dump(mode="json"),
            },
        )

    def _prepare_frozen_plan(
        self,
        request: NativeImageGenPlanRequest | NativeSpecializedImageGenPlanRequest,
        *,
        scenario_id: str,
        scenario_selection: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        runtime = self._runtime_factory()
        uploaded_assets = self._uploaded_assets(request)
        result = runtime.plan_job(
            {
                "user_input": request.user_input,
                "scenario_selection": scenario_selection,
                "metadata": {
                    "template_id": request.template_id,
                    "requested_image_count": request.requested_image_count,
                    "requested_image_size": request.requested_image_size,
                    # Local Mode has no image transport, but it must plan as a
                    # real-image job so the shared Runtime requires the same
                    # remote Central Brain contract as the Web Provider path.
                    "require_real_images": True,
                    "real_image_generation": True,
                    **metadata,
                },
                # The source files are passed through the same V3 upload
                # contract as Web Mode.  The remote Brain compact payload
                # receives only safe asset evidence, never the local paths.
                "uploaded_assets": uploaded_assets,
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

        deliverable_plan = result.metadata.get("template_deliverable_plan")
        if not isinstance(deliverable_plan, dict):
            return self._blocked("codex_native_imagegen_template_deliverable_plan_missing", "V3 planning did not freeze a complete template deliverable plan.")
        deliverables = deliverable_plan.get("deliverables")
        if not isinstance(deliverables, list) or len(deliverables) != request.requested_image_count:
            return self._blocked("codex_native_imagegen_count_mismatch", "V3 did not freeze one template deliverable for every requested output.")

        outputs: list[dict[str, Any]] = []
        envelope_id = str(envelope.get("envelope_id") or "").strip()
        if not envelope_id:
            return self._blocked("codex_native_imagegen_envelope_missing_id", "V3 planning did not provide an admission envelope identity.")
        try:
            materializations = self._canonical_materializations(result.planning_result)
        except (ProviderRuntimeError, ValueError):
            return self._blocked(
                "codex_native_imagegen_canonical_prompt_unavailable",
                "V3 could not materialize one canonical Provider prompt for every requested output.",
            )
        if len(materializations) != request.requested_image_count:
            return self._blocked("codex_native_imagegen_count_mismatch", "V3 did not materialize the requested number of canonical Provider prompts.")
        for index, materialization in enumerate(materializations, start=1):
            reference_paths = [str(item["file_path"]) for item in materialization.reference_assets if item.get("file_path")]
            try:
                output = {
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
                    # These are the same admitted source files that the Web
                    # Provider receives before its shared transport preflight.
                    # Codex must pass them without substitution alongside the
                    # exact prompt above; an empty list means text-to-image.
                    "reference_image_paths": reference_paths,
                    "reference_input_contract": {
                        "operation": "image_edit" if reference_paths else "image_generate",
                        "declared_reference_count": len(request.reference_inputs),
                        "admitted_reference_count": len(reference_paths),
                        "source_sha256": [item.source_sha256 for item in request.reference_inputs],
                    },
                }
                output.update(self._specialized_lineage_projection(request.template_id, deliverables[index - 1]))
            except ValueError:
                return self._blocked(
                    "codex_native_imagegen_specialized_lineage_invalid",
                    "The frozen specialized plan did not provide a valid structural lineage contract.",
                )
            outputs.append(output)

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
    def _specialized_lineage_projection(template_id: str, deliverable: Any) -> dict[str, Any]:
        """Expose only existing structural Photography lineage.

        E-Commerce emits no semantic slot/recipe/role surface at all.  The
        Photography role is a pre-existing frozen lineage key; it is never
        creative content and cannot become a local shot/camera/crop recipe.
        """

        if template_id != "photographer_template":
            return {}
        metadata = deliverable.get("metadata") if isinstance(deliverable, dict) else None
        role = metadata.get("specialized_role_key") if isinstance(metadata, dict) else None
        if not isinstance(role, str) or not role.strip():
            raise ValueError("photography frozen deliverable lacks its structural lineage role")
        return {"photography_lineage_role": role}

    @staticmethod
    def _uploaded_assets(request: NativeImageGenPlanRequest | NativeSpecializedImageGenPlanRequest) -> list[UploadedAssetInfo]:
        """Translate explicit local files into the ordinary V3 upload shape.

        No copy, upload store, or alternate reference resolver is created
        here.  V3's normal admission/materialization path owns every
        subsequent decision, including a fail-closed rejection.
        """

        return [
            UploadedAssetInfo(
                asset_id=item.asset_id,
                role=AssetRole(reference_role_for_channel(item.channel)),
                file_path=item.file_path,
                filename=item.file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1],
                mime_type=reference_mime_type(item.file_path),
                metadata={
                    "provider_input_required": True,
                    "source_integrity_id": item.source_sha256,
                    "codex_native_reference_channel": item.channel,
                    "v3_owned_upload": True,
                },
            )
            for item in request.reference_inputs
        ]

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
