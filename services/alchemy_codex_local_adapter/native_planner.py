"""Doc130/131 canonical-provider-prompt bridge from local stdio MCP to Codex ImageGen."""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import queue
import sys
import threading
import time
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_SKELETON_ROOT = _REPO_ROOT / "src_skeleton"
_REPO_ROOT_TEXT = str(_REPO_ROOT)
if _REPO_ROOT_TEXT not in sys.path:
    sys.path.insert(0, _REPO_ROOT_TEXT)
_SRC_SKELETON_ROOT_TEXT = str(_SRC_SKELETON_ROOT)
while _SRC_SKELETON_ROOT_TEXT in sys.path:
    sys.path.remove(_SRC_SKELETON_ROOT_TEXT)
sys.path.insert(0, _SRC_SKELETON_ROOT_TEXT)

from alchemy_creative_agent_3_0.app.generation_router import (
    ProductionImageGenerationProvider,
    build_provider_generation_request,
)
from app.providers.base import ProviderRuntimeError
from alchemy_creative_agent_3_0.app.scenario_runtime import (
    ScenarioRuntime,
    ScenarioRuntimeResult,
    ScenarioRuntimeStatus,
)
from alchemy_creative_agent_3_0.app.llm_brain.stage_trace import record_stage_event
from alchemy_creative_agent_3_0.app.creative_core.rules import stable_id
from alchemy_creative_agent_3_0.app.shared_capabilities import AssetRole, UploadedAssetInfo
from alchemy_creative_agent_3_0.app.visual_assets import (
    ProfessionalModeBinding,
    ProfessionalModeRuntimeBridge,
)
from alchemy_creative_agent_3_0.app.photography_profiles import (
    GENERAL_PHOTOGRAPHY_PROFILE_ID,
    default_photographer_profile_catalog,
)

from .contracts import (
    NATIVE_EXECUTION_CHANNEL,
    NativeImageGenPlanRequest,
    NativeReferenceInput,
    NativeProfessionalImageGenPlanRequest,
    NativeSpecializedImageGenPlanRequest,
    reference_mime_type,
    reference_role_for_channel,
)
from .professional_binding import ProfessionalBindingResolution
from .provenance import native_plan_provenance


_GENERAL_TEMPLATE_SCENARIOS = {"general_template": "general_creative"}
_SPECIALIZED_TEMPLATE_SCENARIOS = {
    "ecommerce_template": "ecommerce",
    "photographer_template": "photography",
}
_ECOMMERCE_PRODUCT_TRUTH_SELECTION_ROLES = {
    "lifestyle_primary_product_view",
    "playful_environment_interaction_view",
    "walking_or_lookback_view",
    "back_or_structure_view",
    "product_detail_or_print_view",
}
_ECOMMERCE_PRODUCT_TRUTH_DETAIL_ROLE = "product_detail_or_print_view"

ProfessionalBindingResolver = Callable[..., ProfessionalModeBinding | ProfessionalBindingResolution | None]


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0.0 else default


_LOCAL_MCP_PLANNING_TIMEOUT_SECONDS = _float_env(
    "CODEX_NATIVE_IMAGEGEN_PLANNING_TIMEOUT_SECONDS",
    540.0,
)
_LOCAL_MCP_BRAIN_TRANSPORT_TIMEOUT_SECONDS = _float_env(
    "CODEX_NATIVE_IMAGEGEN_BRAIN_TRANSPORT_TIMEOUT_SECONDS",
    min(210.0, max(1.0, (_LOCAL_MCP_PLANNING_TIMEOUT_SECONDS - 120.0) / 2.0)),
)


class _LocalMcpPlanningTimeout(TimeoutError):
    """Internal deadline for conversation-only Codex MCP planning."""


class _LocalMcpPlanningInProgress(RuntimeError):
    """Raised when another local MCP planning worker owns the slot."""


_PLANNING_PROCESS_LOCK = threading.Lock()


def _safe_remote_brain_transport_failure(value: Any) -> dict[str, Any]:
    """Keep Local MCP transport diagnostics useful but public-safe."""

    if not isinstance(value, dict):
        return {}
    schema_version = value.get("schema_version")
    stage = value.get("stage")
    error_class = value.get("transport_error_class")
    timeout_phase = value.get("timeout_phase")
    timeout_seconds = value.get("timeout_seconds")
    elapsed_ms = value.get("elapsed_ms")
    if schema_version != "v3_brain_transport_failure_v1":
        return {}
    if not isinstance(stage, str) or not stage.strip():
        return {}
    if error_class != "timeout":
        return {}
    if timeout_phase not in {
        "connect_timeout",
        "ttfb_timeout",
        "read_timeout",
        "complete_response_timeout",
        "json_parse_timeout",
        "unknown_transport_timeout",
    }:
        return {}
    if not isinstance(timeout_seconds, (int, float)) or float(timeout_seconds) <= 0.0:
        return {}
    if not isinstance(elapsed_ms, int) or elapsed_ms < 0:
        return {}
    return {
        "schema_version": "v3_brain_transport_failure_v1",
        "stage": stage,
        "transport_error_class": "timeout",
        "timeout_phase": timeout_phase,
        "timeout_seconds": round(float(timeout_seconds), 3),
        "elapsed_ms": elapsed_ms,
        "response_started": bool(value.get("response_started")),
        "first_content_observed": bool(value.get("first_content_observed")),
        "complete_response_observed": bool(value.get("complete_response_observed")),
        "json_parse_started": bool(value.get("json_parse_started")),
        "json_parse_completed": bool(value.get("json_parse_completed")),
    }


class PlanningOnlyGenerationRouter:
    """Sentinel injected into ScenarioRuntime so this facade cannot render."""

    def generate(self, *_: Any, **__: Any) -> Any:
        raise RuntimeError("Doc126 planning-only facade must never call a generation provider")


def _plan_job_process_entrypoint(request: dict[str, Any], result_queue: Any) -> None:
    try:
        record_stage_event("native_planner_child", "process_entrypoint_started")
        runtime = ScenarioRuntime(generation_router=PlanningOnlyGenerationRouter())
        record_stage_event("native_planner_child", "scenario_runtime_constructed")
        record_stage_event("native_planner_child", "scenario_runtime_plan_job_call")
        result = runtime.plan_job(request)
        record_stage_event(
            "native_planner_child",
            "scenario_runtime_plan_job_returned",
            terminal_reason=getattr(result.status, "value", result.status),
        )
        result_queue.put({"kind": "value", "result": result.model_dump(mode="json")})
    except BaseException as exc:  # pragma: no cover - exercised through parent process
        record_stage_event(
            "native_planner_child",
            "process_entrypoint_error",
            terminal_reason=exc.__class__.__name__,
        )
        result_queue.put(
            {
                "kind": "error",
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            }
        )


class CodexNativeImageGenPlanner:
    """Freeze and expose V3's canonical final provider prompts, never pixels."""

    def __init__(
        self,
        runtime_factory: Callable[[], ScenarioRuntime] | None = None,
        professional_binding_resolver: ProfessionalBindingResolver | None = None,
        planning_timeout_seconds: float | None = None,
        brain_transport_timeout_seconds: float | None = None,
        planning_process_entrypoint: Callable[[dict[str, Any], Any], None] | None = None,
    ) -> None:
        self._uses_default_runtime_factory = runtime_factory is None
        self._runtime_factory = runtime_factory or self._default_runtime
        self._professional_binding_resolver = professional_binding_resolver
        self._planning_process_entrypoint = (
            planning_process_entrypoint or _plan_job_process_entrypoint
        )
        self._planning_timeout_seconds = (
            _LOCAL_MCP_PLANNING_TIMEOUT_SECONDS
            if planning_timeout_seconds is None
            else max(0.1, float(planning_timeout_seconds))
        )
        self._brain_transport_timeout_seconds = (
            _LOCAL_MCP_BRAIN_TRANSPORT_TIMEOUT_SECONDS
            if brain_transport_timeout_seconds is None
            else max(0.1, min(210.0, float(brain_transport_timeout_seconds)))
        )

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

    def prepare_frozen_professional_native_imagegen_plan(
        self,
        request: NativeProfessionalImageGenPlanRequest,
    ) -> dict[str, Any]:
        """Project one server-bound Professional plan without owning pixels.

        The resolver is intentionally injected by the embedding host.  It is
        the only place allowed to look up the active People Asset/Face pack;
        the MCP payload contains selectors, never a binding or pack record.
        Without a resolver this conversation-only adapter fails closed.
        """

        scenario_id = {
            "general_template": "general_creative",
            **_SPECIALIZED_TEMPLATE_SCENARIOS,
        }.get(request.template_id)
        if scenario_id is None:
            return self._blocked(
                "codex_native_imagegen_template_invalid",
                "The selected template is unavailable for Professional Native ImageGen planning.",
            )
        if self._professional_binding_resolver is None:
            return self._blocked(
                "codex_native_imagegen_professional_binding_unavailable",
                "Professional Native ImageGen requires a server-owned People Asset binding resolver.",
            )

        job_id = self._professional_job_id(request)
        try:
            binding_resolution = self._professional_binding_resolver(
                project_id=request.project_id,
                people_asset_id=request.people_asset_id,
                job_id=job_id,
                reference_view_ids=list(request.professional_identity_view_ids),
            )
        except Exception:
            return self._blocked(
                "codex_native_imagegen_professional_binding_invalid",
                "The server-owned Professional binding could not be resolved.",
            )
        if isinstance(binding_resolution, ProfessionalBindingResolution):
            binding = binding_resolution.binding
            server_owned_identity_references = tuple(binding_resolution.identity_references)
            binding_snapshot = binding_resolution.binding_snapshot
        else:
            binding = binding_resolution
            server_owned_identity_references = ()
            binding_snapshot = None
        if not isinstance(binding, ProfessionalModeBinding):
            return self._blocked(
                "codex_native_imagegen_professional_binding_unavailable",
                "The server-owned Professional binding resolver returned no valid binding.",
            )
        if (
            binding.job_id != job_id
            or binding.project_id != request.project_id
            or binding.people_asset_id != request.people_asset_id
            or binding.identity_view_ids != list(request.professional_identity_view_ids)
        ):
            return self._blocked(
                "codex_native_imagegen_professional_binding_invalid",
                "The server-owned Professional binding does not match the requested job selectors.",
            )
        professional_product_model = (
            request.template_id == "ecommerce_template"
            and request.professional_reference_stage is None
        )
        if professional_product_model and not server_owned_identity_references:
            return self._blocked(
                "codex_native_imagegen_professional_identity_references_missing",
                "Professional E-Commerce planning requires server-owned identity references from the selected Character Card asset.",
            )
        if professional_product_model:
            if server_owned_identity_references[0].channel != "portrait_identity" or not any(
                item.channel == "selected_identity_reference"
                for item in server_owned_identity_references[1:]
            ):
                return self._blocked(
                    "codex_native_imagegen_professional_identity_references_missing",
                    "Professional E-Commerce planning requires the immutable root portrait and at least one reviewed Character Card identity view.",
                )

        scenario_selection: dict[str, Any] = {
            "scenario_id": scenario_id,
            "parameters": {
                "requested_image_count": request.requested_image_count,
                **({"requested_image_size": request.requested_image_size} if request.requested_image_size else {}),
            },
        }
        metadata: dict[str, Any] = {}
        if request.template_id == "ecommerce_template":
            scenario_selection["platform_profile"] = request.platform_profile
        elif request.template_id == "photographer_template":
            scenario_selection.update(
                {
                    "mode_id": request.photography_mode,
                }
            )
            profile_binding = default_photographer_profile_catalog().resolve_binding(
                scenario_id="photography",
                profile_id=GENERAL_PHOTOGRAPHY_PROFILE_ID,
                selection_source=None,
            )
            metadata = {
                "photographer_profile_binding": profile_binding.model_dump(mode="json"),
            }
        if professional_product_model:
            provider_budget = self._professional_product_model_provider_budget(server_owned_identity_references)
            professional_metadata = {
                "professional_identity_reference_strategy": "visual_asset_library_product_model_v1",
                "professional_product_model_planning": True,
                "professional_product_truth_required": True,
            }
            ecommerce_context = dict(metadata.get("ecommerce_creative_context") or {})
            ecommerce_context["provider_reference_budget"] = self._brain_safe_provider_reference_budget(
                provider_budget
            )
            metadata["ecommerce_creative_context"] = ecommerce_context
        else:
            anchor_preparation_metadata = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
                view_role=request.professional_reference_stage or "standard_front"
            )
            professional_metadata = {
                # The serial relay is a conversation-only projection of the
                # formal anchor-preparation path, not an ordinary Professional
                # delivery.  Reuse the typed server contract so the Remote
                # Brain owns neutral capture and exact view resolution; never
                # repair a missing capture decision with local prompt prose.
                "professional_anchor_pack_preparation": True,
                "professional_planning_metadata": anchor_preparation_metadata,
                "professional_identity_reference_strategy": "serial_anchor_pack_root_reuse_v1",
                **(
                    {"professional_reference_stage": request.professional_reference_stage}
                    if request.professional_reference_stage
                    else {}
                ),
            }
        metadata.update(
            {
                "professional_mode": "professional",
                "project_id": request.project_id,
                "professional_mode_binding_record": binding.model_dump(mode="json"),
                **(
                    {"professional_visual_asset_binding_snapshot": binding_snapshot.to_brain_evidence()}
                    if binding_snapshot is not None
                    else {}
                ),
                "local_mcp_professional_relay": True,
                **professional_metadata,
            }
        )
        result = self._prepare_frozen_plan(
            request,
            scenario_id=scenario_id,
            scenario_selection=scenario_selection,
            metadata=metadata,
            server_owned_references=server_owned_identity_references,
        )
        if result.get("status") == "planned_for_codex_native_imagegen":
            identity_strategy = (
                "visual_asset_library_product_model_v1"
                if professional_product_model
                else "serial_anchor_pack_root_reuse_v1"
            )
            result["provenance"].update(
                {
                    "professional_mode": True,
                    "professional_binding": binding.to_brain_evidence(),
                    "professional_identity_view_ids": list(binding.identity_view_ids),
                    "professional_reference_stage": request.professional_reference_stage,
                    "professional_identity_reference_strategy": identity_strategy,
                    **(
                        {"professional_visual_asset_binding_snapshot": binding_snapshot.to_brain_evidence()}
                        if binding_snapshot is not None
                        else {}
                    ),
                    "professional_serial_intent_sha256": hashlib.sha256(
                        request.user_input.encode("utf-8")
                    ).hexdigest(),
                    "professional_binding_evidence_sha256": self._binding_evidence_sha256(binding),
                }
            )
        return result

    @staticmethod
    def _professional_job_id(request: NativeProfessionalImageGenPlanRequest) -> str:
        job_scope = f"{request.project_id}::{request.template_id}"
        return stable_id("job", request.user_input, None, job_scope, None)

    @staticmethod
    def _binding_evidence_sha256(binding: ProfessionalModeBinding) -> str:
        payload = json.dumps(binding.to_brain_evidence(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _professional_product_model_provider_budget(
        server_owned_references: tuple[NativeReferenceInput, ...],
    ) -> dict[str, Any]:
        # The shared Provider materializer expands each Professional identity
        # source into feature-detail and head-geometry provider derivatives.
        # E-Commerce product selection must budget against that final renderer
        # admission shape, not just raw source IDs.  Product truth inputs are
        # suppressed to focused product crops, so they currently consume one
        # provider input each.
        identity_derivative_count = len(server_owned_references) * 2
        max_refs = ProductionImageGenerationProvider.max_provider_reference_images
        return {
            "contract_version": "professional_ecommerce_provider_reference_budget_v1",
            "max_provider_reference_images": max_refs,
            "identity_source_asset_ids": [item.asset_id for item in server_owned_references],
            "identity_derivative_reference_count": identity_derivative_count,
            "product_truth_derivative_reference_count_per_source": 1,
            "max_product_truth_source_refs_per_output": max(0, max_refs - identity_derivative_count),
            "owner": "codex_native_professional_planner",
            "basis": "provider_materialized_reference_derivative_count",
        }

    @staticmethod
    def _brain_safe_provider_reference_budget(provider_budget: dict[str, Any]) -> dict[str, Any]:
        return {
            key: provider_budget[key]
            for key in (
                "contract_version",
                "max_provider_reference_images",
                "identity_derivative_reference_count",
                "product_truth_derivative_reference_count_per_source",
                "max_product_truth_source_refs_per_output",
                "owner",
                "basis",
            )
            if key in provider_budget
        }

    def _professional_product_truth_selection_by_asset(
        self,
        *,
        request: NativeProfessionalImageGenPlanRequest,
        planning_result: Any,
        deliverables: list[Any],
        server_owned_references: tuple[NativeReferenceInput, ...],
        uploaded_assets: list[UploadedAssetInfo],
    ) -> dict[str, dict[str, Any]]:
        product_truth_pool = [item for item in request.reference_inputs if item.channel == "product_truth"]
        product_truth_ids = [item.asset_id for item in product_truth_pool]
        if not product_truth_ids:
            return {
                "blocked": True,
                "code": "codex_native_imagegen_professional_product_binding_incomplete",
                "message": "Professional E-Commerce planning requires product truth references.",
            }
        uploaded_by_asset_id = {item.asset_id: item for item in uploaded_assets}
        identity_asset_ids = [item.asset_id for item in server_owned_references]
        product_truth_hashes = {item.asset_id: item.source_sha256 for item in product_truth_pool}
        generation_plans = {item.asset_id: item for item in planning_result.generation_plans}
        provider_budget = self._professional_product_model_provider_budget(server_owned_references)
        max_product_truth_refs = int(provider_budget["max_product_truth_source_refs_per_output"])
        selection_by_asset_id: dict[str, dict[str, Any]] = {}
        for index, asset in enumerate(planning_result.series_plan.assets, start=1):
            deliverable = deliverables[index - 1] if index <= len(deliverables) else {}
            generation_plan = generation_plans.get(asset.asset_id)
            generation_metadata = (
                dict(generation_plan.metadata)
                if generation_plan is not None and isinstance(generation_plan.metadata, dict)
                else {}
            )
            deliverable_metadata = deliverable.get("metadata") if isinstance(deliverable, dict) else None
            deliverable_metadata = dict(deliverable_metadata) if isinstance(deliverable_metadata, dict) else {}
            selection_source = "generation_plan.metadata"
            raw_selected = generation_metadata.get("selected_product_truth_asset_ids")
            if raw_selected is None:
                raw_selected = generation_metadata.get("admitted_product_truth_asset_ids")
            if raw_selected is None:
                raw_selected = deliverable_metadata.get("selected_product_truth_asset_ids")
                selection_source = "template_deliverable.metadata"
            if raw_selected is None:
                raw_selected = deliverable_metadata.get("admitted_product_truth_asset_ids")
                selection_source = "template_deliverable.metadata"
            if not isinstance(raw_selected, list):
                return {
                    "blocked": True,
                    "code": "codex_native_imagegen_product_truth_selection_missing",
                    "message": "Professional E-Commerce planning requires structured per-output product truth selection metadata.",
                }
            selected = [str(item).strip() for item in raw_selected if str(item).strip()]
            if not selected:
                return {
                    "blocked": True,
                    "code": "codex_native_imagegen_product_truth_selection_missing",
                    "message": "Professional E-Commerce planning selected no product truth reference for an output.",
                }
            if len(selected) != len(set(selected)):
                return {
                    "blocked": True,
                    "code": "codex_native_imagegen_product_truth_selection_invalid",
                    "message": "Professional E-Commerce planning selected duplicate product truth references.",
                }
            if not set(selected).issubset(set(product_truth_ids)):
                return {
                    "blocked": True,
                    "code": "codex_native_imagegen_product_truth_selection_invalid",
                    "message": "Professional E-Commerce planning selected a product truth reference outside the frozen product pool.",
                }
            role = str(
                generation_metadata.get("product_truth_selection_role")
                or deliverable_metadata.get("product_truth_selection_role")
                or ""
            ).strip()
            if role not in _ECOMMERCE_PRODUCT_TRUTH_SELECTION_ROLES:
                return {
                    "blocked": True,
                    "code": "codex_native_imagegen_product_truth_selection_invalid",
                    "message": "Professional E-Commerce planning requires a structured product truth selection role for every output.",
                }
            if len(selected) > 2:
                return {
                    "blocked": True,
                    "code": "codex_native_imagegen_product_truth_selection_invalid",
                    "message": "Professional E-Commerce planning selected too many product truth references for one output.",
                }
            if len(selected) == 2 and role != _ECOMMERCE_PRODUCT_TRUTH_DETAIL_ROLE:
                return {
                    "blocked": True,
                    "code": "codex_native_imagegen_product_truth_selection_invalid",
                    "message": "Professional E-Commerce planning may select two product truth references only for a detail or print output role.",
                }
            if len(selected) > max_product_truth_refs:
                return {
                    "blocked": True,
                    "code": "codex_native_imagegen_reference_input_capacity_exceeded",
                    "message": "V3 cannot admit the selected Professional identity and product truth references within the configured renderer input capacity.",
                }
            omitted = [
                {
                    "asset_id": asset_id,
                    "reason": "not_selected_for_this_frozen_deliverable",
                    "source_sha256": product_truth_hashes.get(asset_id),
                }
                for asset_id in product_truth_ids
                if asset_id not in selected
            ]
            selected_ids = set(selected)
            provider_asset_ids = [*identity_asset_ids, *selected]
            reference_assets = []
            for asset_id in provider_asset_ids:
                uploaded = uploaded_by_asset_id.get(asset_id)
                if uploaded is None:
                    continue
                data = uploaded.model_dump(mode="json")
                metadata = dict(data.get("metadata") or {})
                if asset_id in selected_ids:
                    metadata["reference_sanitization"] = {
                        "suppress_full_frame_provider_reference": True,
                        "reason_codes": ["professional_product_model_uses_selected_product_truth_crop"],
                    }
                data["metadata"] = metadata
                reference_assets.append(data)
            final_hashes = [
                str((item.get("metadata") or {}).get("source_integrity_id") or "")
                for item in reference_assets
                if isinstance(item, dict)
            ]
            selection_audit = {
                "selection_source": selection_source,
                "product_truth_pool_asset_ids": list(product_truth_ids),
                "product_truth_pool_source_sha256": dict(product_truth_hashes),
                "product_truth_selection_role": role,
                "selected_product_truth_asset_ids": list(selected),
                "omitted_product_truth": omitted,
                "identity_source_asset_ids": list(identity_asset_ids),
                "provider_reference_budget": dict(provider_budget),
                "final_reference_source_sha256": final_hashes,
                "selection_policy": "remote_brain_structured_frozen_metadata_only",
            }
            selection_by_asset_id[asset.asset_id] = {
                **selection_audit,
                "metadata_overrides": {
                    "reference_assets": reference_assets,
                    "uploaded_assets": reference_assets,
                    "product_truth_selection": selection_audit,
                    "product_truth_selection_role": role,
                    "selected_product_truth_asset_ids": list(selected),
                    "admitted_product_truth_asset_ids": list(selected),
                    "product_truth_pool_asset_ids": list(product_truth_ids),
                    "provider_reference_budget": dict(provider_budget),
                    "omitted_product_truth": omitted,
                },
            }
        return selection_by_asset_id

    def _prepare_frozen_plan(
        self,
        request: NativeImageGenPlanRequest | NativeSpecializedImageGenPlanRequest | NativeProfessionalImageGenPlanRequest,
        *,
        scenario_id: str,
        scenario_selection: dict[str, Any],
        metadata: dict[str, Any],
        server_owned_references: tuple[NativeReferenceInput, ...] = (),
    ) -> dict[str, Any]:
        runtime = None if self._uses_default_runtime_factory else self._runtime_factory()
        uploaded_assets = self._uploaded_assets(request, server_owned_references=server_owned_references)
        runtime_metadata = {
            "template_id": request.template_id,
            "requested_image_count": request.requested_image_count,
            "requested_image_size": request.requested_image_size,
            # Local Mode has no image transport, but it must plan as a
            # real-image job so the shared Runtime requires the same remote
            # Central Brain contract as the Web Provider path.
            "require_real_images": True,
            "real_image_generation": True,
            **metadata,
        }
        runtime_metadata.setdefault(
            "_brain_transport_timeout_seconds",
            self._brain_transport_timeout_seconds,
        )
        runtime_request = {
            "user_input": request.user_input,
            "scenario_selection": scenario_selection,
            "metadata": runtime_metadata,
            # The source files are passed through the same V3 upload contract
            # as Web Mode.  The remote Brain compact payload receives only
            # safe asset evidence, never the local paths.
            "uploaded_assets": uploaded_assets,
        }
        try:
            result = self._plan_job_with_deadline(runtime, runtime_request)
        except _LocalMcpPlanningTimeout:
            return self._blocked(
                "codex_native_imagegen_planning_timeout",
                "Codex Native ImageGen planning exceeded the local MCP interaction deadline before any image was created.",
            )
        except _LocalMcpPlanningInProgress:
            return self._blocked(
                "codex_native_imagegen_planning_in_progress",
                "Codex Native ImageGen planning is already running; no new image planning request was started.",
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
            materialization_metadata: dict[str, Any] = {}
            materialization_metadata_by_asset_id: dict[str, dict[str, Any]] = {}
            professional_product_truth_by_asset_id: dict[str, dict[str, Any]] = {}
            if isinstance(request, NativeProfessionalImageGenPlanRequest):
                # Product-model plans freeze their
                # visual_asset_library_product_model_v1 strategy and complete
                # identity + product truth references in the planning result
                # metadata.  Keep that source of truth intact.  Only legacy
                # Professional serial stages may receive the serial strategy
                # compatibility projection here.
                professional_product_model = (
                    request.template_id == "ecommerce_template"
                    and request.professional_reference_stage is None
                )
                if professional_product_model:
                    product_selection = self._professional_product_truth_selection_by_asset(
                        request=request,
                        planning_result=result.planning_result,
                        deliverables=deliverables,
                        server_owned_references=server_owned_references,
                        uploaded_assets=uploaded_assets,
                    )
                    if isinstance(product_selection, dict) and product_selection.get("blocked"):
                        return self._blocked(str(product_selection["code"]), str(product_selection["message"]))
                    product_truth_ids = {
                        item.asset_id for item in request.reference_inputs if item.channel == "product_truth"
                    }
                    for output_asset in result.planning_result.series_plan.assets:
                        output_asset_id = str(output_asset.asset_id)
                        selection_contract = (
                            product_selection.get(output_asset_id)
                            if isinstance(product_selection, dict)
                            else None
                        )
                        if not isinstance(selection_contract, dict):
                            return self._blocked(
                                "codex_native_imagegen_product_truth_selection_missing",
                                "Professional E-Commerce planning requires structured per-output product truth selection metadata.",
                            )
                        raw_selected_product_truth = selection_contract.get(
                            "selected_product_truth_asset_ids"
                        )
                        if not isinstance(raw_selected_product_truth, list):
                            return self._blocked(
                                "codex_native_imagegen_product_truth_selection_missing",
                                "Professional E-Commerce planning requires structured per-output product truth selection metadata.",
                            )
                        selected_product_truth_ids = [
                            str(item).strip()
                            for item in raw_selected_product_truth
                            if str(item).strip()
                        ]
                        if not selected_product_truth_ids:
                            return self._blocked(
                                "codex_native_imagegen_product_truth_selection_missing",
                                "Professional E-Commerce planning selected no product truth reference for an output.",
                            )
                        if len(selected_product_truth_ids) != len(set(selected_product_truth_ids)):
                            return self._blocked(
                                "codex_native_imagegen_product_truth_selection_invalid",
                                "Professional E-Commerce planning selected duplicate product truth references.",
                            )
                        if not set(selected_product_truth_ids).issubset(product_truth_ids):
                            return self._blocked(
                                "codex_native_imagegen_product_truth_selection_invalid",
                                "Professional E-Commerce planning selected a product truth reference outside the frozen product pool.",
                            )
                        selection_role = str(
                            selection_contract.get("product_truth_selection_role") or ""
                        ).strip()
                        if selection_role not in _ECOMMERCE_PRODUCT_TRUTH_SELECTION_ROLES:
                            return self._blocked(
                                "codex_native_imagegen_product_truth_selection_invalid",
                                "Professional E-Commerce planning requires a structured product truth selection role for every output.",
                            )
                        if len(selected_product_truth_ids) > 2:
                            return self._blocked(
                                "codex_native_imagegen_product_truth_selection_invalid",
                                "Professional E-Commerce planning selected too many product truth references for one output.",
                            )
                        if (
                            len(selected_product_truth_ids) == 2
                            and selection_role != _ECOMMERCE_PRODUCT_TRUTH_DETAIL_ROLE
                        ):
                            return self._blocked(
                                "codex_native_imagegen_product_truth_selection_invalid",
                                "Professional E-Commerce planning may select two product truth references only for a detail or print output role.",
                            )
                    professional_product_truth_by_asset_id = product_selection
                    materialization_metadata_by_asset_id = {
                        asset_id: dict(selection.get("metadata_overrides") or {})
                        for asset_id, selection in professional_product_truth_by_asset_id.items()
                    }
                elif request.professional_reference_stage:
                    materialization_metadata = {
                        "professional_identity_reference_strategy": "serial_anchor_pack_root_reuse_v1",
                        "professional_reference_stage": request.professional_reference_stage,
                    }
            materializations = self._canonical_materializations(
                result.planning_result,
                metadata_overrides=materialization_metadata,
                metadata_overrides_by_asset_id=materialization_metadata_by_asset_id,
            )
        except ProviderRuntimeError as exc:
            detail = dict(getattr(exc, "detail", {}) or {})
            failure_code = str(detail.get("reference_input_failure_code") or "").strip()
            if isinstance(request, NativeProfessionalImageGenPlanRequest) and failure_code == "reference_input_capability_mismatch":
                return self._blocked(
                    "codex_native_imagegen_reference_input_capacity_exceeded",
                    "V3 cannot admit every required Professional identity and product truth reference within the configured image-input capacity.",
                )
            if isinstance(request, NativeProfessionalImageGenPlanRequest) and failure_code == "reference_input_unsupported":
                return self._blocked(
                    "codex_native_imagegen_required_reference_unavailable",
                    "V3 could not admit every required Professional reference image; no substitute provider input is allowed.",
                )
            return self._blocked(
                "codex_native_imagegen_canonical_prompt_unavailable",
                "V3 could not materialize one canonical Provider prompt for every requested output.",
            )
        except ValueError:
            return self._blocked(
                "codex_native_imagegen_canonical_prompt_unavailable",
                "V3 could not materialize one canonical Provider prompt for every requested output.",
            )
        if len(materializations) != request.requested_image_count:
            return self._blocked("codex_native_imagegen_count_mismatch", "V3 did not materialize the requested number of canonical Provider prompts.")
        materialization_asset_ids = [
            str(asset.asset_id)
            for asset in result.planning_result.series_plan.assets
        ]
        if len(materialization_asset_ids) != len(materializations):
            return self._blocked("codex_native_imagegen_count_mismatch", "V3 did not preserve one stable output asset binding for every materialized Provider prompt.")
        if isinstance(request, NativeProfessionalImageGenPlanRequest):
            professional_product_model = (
                request.template_id == "ecommerce_template"
                and request.professional_reference_stage is None
            )
            for asset_id, materialization in zip(materialization_asset_ids, materializations):
                admitted_source_ids = {
                    str(item.get("source_asset_id") or item.get("asset_id") or "").strip()
                    for item in materialization.reference_assets
                    if isinstance(item, dict)
                }
                selection_contract = professional_product_truth_by_asset_id.get(asset_id)
                identity_source_ids = {item.asset_id for item in server_owned_references}
                product_truth_source_ids = {
                    item.asset_id for item in request.reference_inputs if item.channel == "product_truth"
                }
                selected_product_truth_source_ids: set[str] = set()
                if professional_product_model:
                    if not isinstance(selection_contract, dict):
                        return self._blocked(
                            "codex_native_imagegen_product_truth_selection_missing",
                            "Professional E-Commerce planning requires structured per-output product truth selection metadata.",
                        )
                    raw_selected_product_truth = selection_contract.get("selected_product_truth_asset_ids")
                    if not isinstance(raw_selected_product_truth, list):
                        return self._blocked(
                            "codex_native_imagegen_product_truth_selection_missing",
                            "Professional E-Commerce planning requires structured per-output product truth selection metadata.",
                        )
                    selected_product_truth_list = [
                        str(item).strip() for item in raw_selected_product_truth if str(item).strip()
                    ]
                    if not selected_product_truth_list:
                        return self._blocked(
                            "codex_native_imagegen_product_truth_selection_missing",
                            "Professional E-Commerce planning selected no product truth reference for an output.",
                        )
                    if len(selected_product_truth_list) != len(set(selected_product_truth_list)):
                        return self._blocked(
                            "codex_native_imagegen_product_truth_selection_invalid",
                            "Professional E-Commerce planning selected duplicate product truth references.",
                        )
                    selected_product_truth_source_ids = set(selected_product_truth_list)
                    if not selected_product_truth_source_ids.issubset(product_truth_source_ids):
                        return self._blocked(
                            "codex_native_imagegen_product_truth_selection_invalid",
                            "Professional E-Commerce planning selected a product truth reference outside the frozen product pool.",
                        )
                    selection_role = str(selection_contract.get("product_truth_selection_role") or "").strip()
                    if selection_role not in _ECOMMERCE_PRODUCT_TRUTH_SELECTION_ROLES:
                        return self._blocked(
                            "codex_native_imagegen_product_truth_selection_invalid",
                            "Professional E-Commerce planning requires a structured product truth selection role for every output.",
                        )
                    if len(selected_product_truth_list) > 2:
                        return self._blocked(
                            "codex_native_imagegen_product_truth_selection_invalid",
                            "Professional E-Commerce planning selected too many product truth references for one output.",
                        )
                    if len(selected_product_truth_list) == 2 and selection_role != _ECOMMERCE_PRODUCT_TRUTH_DETAIL_ROLE:
                        return self._blocked(
                            "codex_native_imagegen_product_truth_selection_invalid",
                            "Professional E-Commerce planning may select two product truth references only for a detail or print output role.",
                        )
                    if len(materialization.reference_assets) > ProductionImageGenerationProvider.max_provider_reference_images:
                        return self._blocked(
                            "codex_native_imagegen_reference_input_capacity_exceeded",
                            "V3 cannot admit every required Professional identity and selected product truth reference within the configured image-input capacity.",
                        )
                    if not identity_source_ids or not product_truth_source_ids:
                        return self._blocked(
                            "codex_native_imagegen_professional_product_binding_incomplete",
                            "Professional E-Commerce planning requires both selected identity references and product truth references.",
                        )
                    if not identity_source_ids.issubset(admitted_source_ids):
                        return self._blocked(
                            "codex_native_imagegen_professional_identity_reference_missing",
                            "The shared Provider materializer did not admit the selected Professional identity references; no image was created.",
                        )
                    if not selected_product_truth_source_ids.issubset(admitted_source_ids):
                        return self._blocked(
                            "codex_native_imagegen_product_truth_reference_missing",
                            "The shared Provider materializer did not admit every selected product truth reference; no image was created.",
                        )
                    unselected_product_truth_source_ids = product_truth_source_ids - selected_product_truth_source_ids
                    if unselected_product_truth_source_ids.intersection(admitted_source_ids):
                        return self._blocked(
                            "codex_native_imagegen_product_truth_selection_leaked",
                            "The shared Provider materializer admitted product truth references that were not selected for this frozen output.",
                        )
                elif [
                    item.asset_id for item in request.reference_inputs if item.asset_id not in admitted_source_ids
                ]:
                    return self._blocked(
                        "codex_native_imagegen_professional_reference_parity_mismatch",
                        "The shared Provider materializer did not admit every Professional serial-chain reference; no image was created.",
                    )
        canonical_prompt_signing = self._canonical_prompt_signing_provenance(
            llm_brain,
            active_capability_ids=envelope.get("active_capability_ids"),
        )
        if canonical_prompt_signing is None:
            return self._blocked(
                "codex_native_imagegen_human_resigning_missing",
                "V3 did not produce the required shared Human Realism Brain re-signing receipt.",
            )
        for index, (asset_id, materialization) in enumerate(zip(materialization_asset_ids, materializations), start=1):
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
                        "declared_reference_count": len(request.reference_inputs) + len(server_owned_references),
                        "admitted_reference_count": len(reference_paths),
                        "source_sha256": [
                            item.source_sha256 for item in (*server_owned_references, *request.reference_inputs)
                        ],
                    },
                }
                # Keep the legacy NativeImageGenPlanRequest contract stable;
                # Professional relay callers additionally receive the exact
                # admitted source lineage needed for serial-chain parity.
                if isinstance(request, NativeProfessionalImageGenPlanRequest):
                    output["reference_input_contract"]["admitted_reference_source_asset_ids"] = [
                        source_id for source_id in dict.fromkeys(
                            str(item.get("source_asset_id") or item.get("asset_id") or "")
                            for item in materialization.reference_assets
                            if isinstance(item, dict)
                        ) if source_id
                    ]
                    output["reference_input_contract"]["admitted_reference_derivative_asset_ids"] = [
                        str(item.get("asset_id") or "")
                        for item in materialization.reference_assets
                        if isinstance(item, dict)
                        and item.get("provider_reference_derivative") is True
                        and str(item.get("asset_id") or "")
                    ]
                    if server_owned_references:
                        output["reference_input_contract"]["professional_identity_source_asset_ids"] = [
                            item.asset_id for item in server_owned_references
                        ]
                    product_truth_ids = [
                        item.asset_id for item in request.reference_inputs if item.channel == "product_truth"
                    ]
                    if product_truth_ids:
                        professional_product_model = (
                            request.template_id == "ecommerce_template"
                            and request.professional_reference_stage is None
                        )
                        selection_contract = professional_product_truth_by_asset_id.get(asset_id)
                        if professional_product_model:
                            if not isinstance(selection_contract, dict):
                                return self._blocked(
                                    "codex_native_imagegen_product_truth_selection_missing",
                                    "Professional E-Commerce planning requires structured per-output product truth selection metadata.",
                                )
                            raw_selected_product_truth = selection_contract.get(
                                "selected_product_truth_asset_ids"
                            )
                            if not isinstance(raw_selected_product_truth, list):
                                return self._blocked(
                                    "codex_native_imagegen_product_truth_selection_missing",
                                    "Professional E-Commerce planning requires structured per-output product truth selection metadata.",
                                )
                            selected_product_truth_ids = [
                                str(item).strip()
                                for item in raw_selected_product_truth
                                if str(item).strip()
                            ]
                            if not selected_product_truth_ids:
                                return self._blocked(
                                    "codex_native_imagegen_product_truth_selection_missing",
                                    "Professional E-Commerce planning selected no product truth reference for an output.",
                                )
                            if len(selected_product_truth_ids) != len(set(selected_product_truth_ids)):
                                return self._blocked(
                                    "codex_native_imagegen_product_truth_selection_invalid",
                                    "Professional E-Commerce planning selected duplicate product truth references.",
                                )
                            if not set(selected_product_truth_ids).issubset(set(product_truth_ids)):
                                return self._blocked(
                                    "codex_native_imagegen_product_truth_selection_invalid",
                                    "Professional E-Commerce planning selected a product truth reference outside the frozen product pool.",
                                )
                            selection_role = str(
                                selection_contract.get("product_truth_selection_role") or ""
                            ).strip()
                            if selection_role not in _ECOMMERCE_PRODUCT_TRUTH_SELECTION_ROLES:
                                return self._blocked(
                                    "codex_native_imagegen_product_truth_selection_invalid",
                                    "Professional E-Commerce planning requires a structured product truth selection role for every output.",
                                )
                            if len(selected_product_truth_ids) > 2:
                                return self._blocked(
                                    "codex_native_imagegen_product_truth_selection_invalid",
                                    "Professional E-Commerce planning selected too many product truth references for one output.",
                                )
                            if (
                                len(selected_product_truth_ids) == 2
                                and selection_role != _ECOMMERCE_PRODUCT_TRUTH_DETAIL_ROLE
                            ):
                                return self._blocked(
                                    "codex_native_imagegen_product_truth_selection_invalid",
                                    "Professional E-Commerce planning may select two product truth references only for a detail or print output role.",
                                )
                        else:
                            selection_contract = (
                                selection_contract if isinstance(selection_contract, dict) else {}
                            )
                            selected_product_truth_ids = list(product_truth_ids)
                        omitted_product_truth = list(selection_contract.get("omitted_product_truth") or [])
                        product_truth_pool_hashes = dict(
                            selection_contract.get("product_truth_pool_source_sha256") or {}
                        )
                        selected_product_truth_hashes = [
                            product_truth_pool_hashes.get(asset_id)
                            for asset_id in selected_product_truth_ids
                            if product_truth_pool_hashes.get(asset_id)
                        ]
                        output["reference_input_contract"]["source_sha256"] = [
                            item.source_sha256 for item in server_owned_references
                        ] + selected_product_truth_hashes
                        output["reference_input_contract"]["product_truth_pool_asset_ids"] = product_truth_ids
                        output["reference_input_contract"]["product_truth_pool_source_sha256"] = product_truth_pool_hashes
                        if professional_product_model:
                            output["reference_input_contract"]["product_truth_selection_role"] = selection_role
                        output["reference_input_contract"]["selected_product_truth_asset_ids"] = selected_product_truth_ids
                        output["reference_input_contract"]["admitted_product_truth_asset_ids"] = [
                            source_id for source_id in dict.fromkeys(
                                source_id
                                for source_id in output["reference_input_contract"]["admitted_reference_source_asset_ids"]
                                if source_id in set(selected_product_truth_ids)
                            )
                        ]
                        output["reference_input_contract"]["omitted_product_truth"] = omitted_product_truth
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
            "planning_receipt": self._planning_receipt(llm_brain),
            "provenance": native_plan_provenance(
                template_id=request.template_id,
                scenario_id=scenario_id,
                output_count=request.requested_image_count,
                activation_plan_id=str(envelope.get("envelope_id") or ""),
                constraint_ledger_id=str(ledger.get("ledger_id") or ""),
                admission_fallback_observed=False,
                canonical_prompt_signing=canonical_prompt_signing,
            ),
        }

    @staticmethod
    def _planning_receipt(llm_brain: dict[str, Any]) -> dict[str, Any]:
        """Project a small, non-creative Brain execution receipt for Codex.

        This makes a slow or exhausted remote plan diagnosable without exposing
        prompts, references, endpoints, model credentials, or hidden Brain
        reasoning.  It is a projection of normal V3 audit facts, not a Local
        Mode lifecycle or a retry authority.
        """

        audit = llm_brain.get("audit") if isinstance(llm_brain.get("audit"), dict) else {}
        transports = audit.get("remote_brain_transports")
        transports = [item for item in transports if isinstance(item, dict)] if isinstance(transports, list) else []
        stages = [
            str(item.get("stage"))
            for item in transports
            if str(item.get("stage") or "").strip()
        ]
        elapsed_ms = sum(
            max(0, int(item.get("elapsed_ms") or 0))
            for item in transports
            if isinstance(item.get("elapsed_ms"), (int, float))
        )
        receipt: dict[str, Any] = {
            "state": "planned",
            "remote_brain_call_count": max(0, int(audit.get("remote_brain_call_count") or len(transports))),
            "stages": stages,
            "total_elapsed_ms": elapsed_ms,
        }
        execution_budget = audit.get("remote_brain_execution_budget")
        if isinstance(execution_budget, dict):
            safe_budget = {
                key: execution_budget.get(key)
                for key in ("logical_budget_seconds", "remaining_ms", "state")
                if key in execution_budget
            }
            if safe_budget:
                receipt["execution_budget"] = safe_budget
        return receipt

    @staticmethod
    def planning_only_acceptance_summary(
        report: dict[str, Any],
        *,
        expected_image_count: int | None = None,
        required_identity_source_asset_ids: list[str] | tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Evaluate a native planning-only report without creating artifacts.

        Controlled validation reports wrap the native planner result under
        ``planner_result``.  The authoritative Brain receipt lives inside that
        nested planner result, not at the report top level.  This helper keeps
        the acceptance contract in one safe, value-light place so evidence
        runners do not accidentally mark a successful two-stage plan/finalizer
        path as failed.
        """

        if not isinstance(report, dict):
            report = {}
        planner_result = report.get("planner_result")
        planner_result = planner_result if isinstance(planner_result, dict) else report
        receipt = planner_result.get("planning_receipt")
        receipt = receipt if isinstance(receipt, dict) else {}
        raw_stages = receipt.get("stages")
        stages = [
            str(item)
            for item in raw_stages
            if str(item or "").strip()
        ] if isinstance(raw_stages, list) else []
        remote_brain_call_count = max(0, int(receipt.get("remote_brain_call_count") or 0))
        outputs = planner_result.get("outputs")
        outputs = outputs if isinstance(outputs, list) else []
        expected_count = expected_image_count
        if expected_count is None:
            raw_expected = (
                planner_result.get("requested_output_count")
                or (report.get("request") or {}).get("requested_image_count")
            )
            try:
                expected_count = int(raw_expected)
            except (TypeError, ValueError):
                expected_count = 0
        mutation_delta = report.get("mutation_delta")
        mutation_delta = mutation_delta if isinstance(mutation_delta, dict) else {}
        required_identity = {
            str(item).strip()
            for item in required_identity_source_asset_ids
            if str(item).strip()
        }
        selected_ok = True
        refs_ok = True
        no_leak_ok = True
        identity_ok = True if not required_identity else bool(outputs)
        pool_hash_parity_ok = True
        first_pool_ids: list[str] | None = None
        first_pool_hashes: dict[str, Any] | None = None
        for output in outputs:
            if not isinstance(output, dict):
                selected_ok = False
                refs_ok = False
                continue
            contract = output.get("reference_input_contract")
            contract = contract if isinstance(contract, dict) else {}
            selected = [
                str(item).strip()
                for item in (contract.get("selected_product_truth_asset_ids") or [])
                if str(item).strip()
            ]
            pool = [
                str(item).strip()
                for item in (contract.get("product_truth_pool_asset_ids") or [])
                if str(item).strip()
            ]
            admitted_product = {
                str(item).strip()
                for item in (contract.get("admitted_product_truth_asset_ids") or [])
                if str(item).strip()
            }
            admitted_sources = {
                str(item).strip()
                for item in (contract.get("admitted_reference_source_asset_ids") or [])
                if str(item).strip()
            }
            identity_sources = {
                str(item).strip()
                for item in (contract.get("professional_identity_source_asset_ids") or [])
                if str(item).strip()
            }
            if not selected or len(selected) != len(set(selected)) or not set(selected).issubset(set(pool)):
                selected_ok = False
            if not set(selected).issubset(admitted_product):
                refs_ok = False
            try:
                admitted_reference_count = int(contract.get("admitted_reference_count") or 0)
            except (TypeError, ValueError):
                admitted_reference_count = 0
            reference_path_count = len(output.get("reference_image_paths") or [])
            if (
                admitted_reference_count > ProductionImageGenerationProvider.max_provider_reference_images
                or reference_path_count > ProductionImageGenerationProvider.max_provider_reference_images
            ):
                refs_ok = False
            if (set(pool) - set(selected)).intersection(admitted_sources):
                no_leak_ok = False
            if required_identity and not required_identity.issubset(identity_sources):
                identity_ok = False
            pool_hashes = contract.get("product_truth_pool_source_sha256")
            pool_hashes = pool_hashes if isinstance(pool_hashes, dict) else {}
            if first_pool_ids is None:
                first_pool_ids = list(pool)
                first_pool_hashes = dict(pool_hashes)
            elif list(pool) != first_pool_ids or dict(pool_hashes) != (first_pool_hashes or {}):
                pool_hash_parity_ok = False
        return {
            "remote_brain_two_stage": (
                remote_brain_call_count >= 2
                and "plan" in stages
                and "provider_prompt_finalize" in stages
            ),
            "exact_n": (
                planner_result.get("status") == "planned_for_codex_native_imagegen"
                and expected_count > 0
                and int(planner_result.get("requested_output_count") or 0) == expected_count
                and len(outputs) == expected_count
            ),
            "selected_product_truth_from_pool_each_output": bool(outputs) and selected_ok,
            "final_refs_lte_provider_cap_each_output": bool(outputs) and refs_ok,
            "required_identity_source_present_each_output": identity_ok,
            "no_unselected_product_truth_leak": bool(outputs) and no_leak_ok,
            "pool_hash_parity_stable": bool(outputs) and pool_hash_parity_ok,
            "mutation_delta_zero": not any(
                int(value or 0) != 0
                for value in mutation_delta.values()
                if isinstance(value, (int, float))
            ) if mutation_delta else False,
        }

    @staticmethod
    def _canonical_prompt_signing_provenance(
        llm_brain: dict[str, Any],
        *,
        active_capability_ids: Any,
    ) -> dict[str, Any] | None:
        """Project only public-safe evidence for the exact prompt relay.

        Local Mode does not create a candidate, inspect a pixel, or certify a
        delivery. It can still show whether the normal V3 runtime completed
        the shared finalizer path that produced the canonical string being
        handed back to Codex.
        """

        audit = llm_brain.get("audit") if isinstance(llm_brain.get("audit"), dict) else {}
        allowed_stages = {
            "provider_prompt_finalize",
            "provider_prompt_human_naturalness_resign",
            "provider_prompt_developmental_presence_verify",
            "provider_prompt_professional_capture_resign",
        }
        raw_stages = audit.get("canonical_provider_prompt_stages")
        stages = [str(item) for item in raw_stages if str(item) in allowed_stages] if isinstance(raw_stages, list) else []
        if not stages:
            stage = str(audit.get("canonical_provider_prompt_stage") or "")
            stages = [stage] if stage in allowed_stages else []
        human_active = isinstance(active_capability_ids, list) and "human_realism" in active_capability_ids
        human_resigned = bool(audit.get("human_realism_natural_presence_resigned"))
        human_decision_signed = bool(audit.get("human_realism_natural_presence_decision_signed"))
        raw_decisions = audit.get("human_realism_natural_presence_decisions")
        decision_statuses = [
            str(item.get("status"))
            for item in raw_decisions
            if isinstance(item, dict) and str(item.get("status") or "") in {"approved", "rewritten"}
        ] if isinstance(raw_decisions, list) else []
        historical_two_pass = ["provider_prompt_finalize", "provider_prompt_human_naturalness_resign"]
        developmental_two_pass = [
            "provider_prompt_finalize",
            "provider_prompt_developmental_presence_verify",
        ]
        professional_two_pass = ["provider_prompt_finalize", "provider_prompt_professional_capture_resign"]
        professional_three_pass = [
            "provider_prompt_finalize",
            "provider_prompt_developmental_presence_verify",
            "provider_prompt_professional_capture_resign",
        ]
        combined_finalizer = ["provider_prompt_finalize"]
        if human_active and (
            tuple(stages)
            not in {
                tuple(combined_finalizer),
                tuple(historical_two_pass),
                tuple(developmental_two_pass),
                tuple(professional_two_pass),
                tuple(professional_three_pass),
            }
            or not human_resigned
            or not human_decision_signed
            or not decision_statuses
        ):
            return None
        if not stages:
            return None
        return {
            "stages": stages,
            "human_realism_natural_presence_resigned": human_resigned,
            "human_realism_natural_presence_decision_statuses": decision_statuses,
        }

    def _plan_job_with_deadline(self, runtime: ScenarioRuntime | None, request: dict[str, Any]) -> Any:
        """Run the synchronous runtime planner behind a local MCP deadline.

        The remote Brain has its own transport timeout, but this stdio MCP
        tool must also fail closed before a desktop caller sees an apparently
        hung tool call.  The default runtime is isolated in a child process and
        killed on timeout, so a timed-out planner cannot keep running in the
        MCP host process and later create job, handoff, output, receipt, retry,
        or delivery state.  A single-process lock rejects overlapping native
        planning attempts instead of stacking orphaned workers.
        """

        if self._uses_default_runtime_factory:
            return self._plan_job_in_process(request)
        if runtime is None:
            runtime = self._runtime_factory()
        return self._plan_job_in_thread(runtime, request)

    def _plan_job_in_process(self, request: dict[str, Any]) -> ScenarioRuntimeResult:
        if not _PLANNING_PROCESS_LOCK.acquire(blocking=False):
            record_stage_event("native_planner_parent", "planning_overlap_rejected")
            raise _LocalMcpPlanningInProgress()
        result_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=1)
        process = multiprocessing.Process(
            target=self._planning_process_entrypoint,
            args=(request, result_queue),
            name="codex-native-imagegen-planner",
        )
        try:
            record_stage_event("native_planner_parent", "process_starting")
            process.start()
            record_stage_event("native_planner_parent", "process_started")
            deadline = time.monotonic() + self._planning_timeout_seconds
            payload: Any | None = None
            while time.monotonic() < deadline:
                try:
                    payload = result_queue.get(timeout=0.1)
                    record_stage_event("native_planner_parent", "process_queue_payload_received")
                    break
                except queue.Empty:
                    if not process.is_alive():
                        break
            if payload is None and process.is_alive():
                record_stage_event(
                    "native_planner_parent",
                    "process_timeout",
                    terminal_reason="local_mcp_planning_timeout",
                    extra={"timeout_seconds": self._planning_timeout_seconds},
                )
                process.terminate()
                process.join(timeout=1.0)
                if process.is_alive():  # pragma: no cover - platform fallback
                    process.kill()
                    process.join(timeout=1.0)
                raise _LocalMcpPlanningTimeout()
            if payload is None:
                process.join(timeout=1.0)
                record_stage_event(
                    "native_planner_parent",
                    "process_exited",
                    terminal_reason=str(process.exitcode),
                    extra={"exitcode": process.exitcode},
                )
                try:
                    payload = result_queue.get_nowait()
                except queue.Empty as exc:
                    record_stage_event("native_planner_parent", "process_queue_empty", terminal_reason=str(process.exitcode))
                    raise RuntimeError(
                        f"Codex Native ImageGen planning process exited without a result (exitcode={process.exitcode})."
                    ) from exc
            process.join(timeout=1.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1.0)
                if process.is_alive():  # pragma: no cover - platform fallback
                    process.kill()
                    process.join(timeout=1.0)
            record_stage_event(
                "native_planner_parent",
                "process_exited",
                terminal_reason=str(process.exitcode),
                extra={"exitcode": process.exitcode},
            )
            if payload is None:
                raise RuntimeError(
                    f"Codex Native ImageGen planning process exited without a result (exitcode={process.exitcode})."
                )
            if not isinstance(payload, dict):
                raise RuntimeError("Codex Native ImageGen planning process returned an invalid payload.")
            if payload.get("kind") == "error":
                error_type = str(payload.get("error_type") or "RuntimeError")
                message = str(payload.get("message") or "planning process failed")
                record_stage_event("native_planner_parent", "process_returned_error", terminal_reason=error_type)
                raise RuntimeError(f"{error_type}: {message}")
            if payload.get("kind") != "value" or not isinstance(payload.get("result"), dict):
                record_stage_event("native_planner_parent", "process_returned_invalid_payload")
                raise RuntimeError("Codex Native ImageGen planning process returned an invalid result.")
            record_stage_event("native_planner_parent", "process_returned_value")
            return ScenarioRuntimeResult.model_validate(payload["result"])
        finally:
            result_queue.close()
            result_queue.join_thread()
            _PLANNING_PROCESS_LOCK.release()

    def _plan_job_in_thread(self, runtime: ScenarioRuntime, request: dict[str, Any]) -> ScenarioRuntimeResult:
        """Deadline wrapper for injected runtimes used by focused tests.

        Only the default runtime is used by the MCP production facade, and that
        path is process-isolated and killable.  A custom runtime object cannot
        be safely serialized or force-cancelled, so it keeps the historical
        thread shape but no longer bypasses the deadline: overlapping calls are
        rejected, timeout returns fail-closed, and the slot remains locked until
        the injected runtime naturally drains.
        """

        if not _PLANNING_PROCESS_LOCK.acquire(blocking=False):
            record_stage_event("native_planner_thread", "planning_overlap_rejected")
            raise _LocalMcpPlanningInProgress()
        result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

        def runner() -> None:
            try:
                record_stage_event("native_planner_thread", "scenario_runtime_plan_job_call")
                result = runtime.plan_job(request)
                record_stage_event("native_planner_thread", "scenario_runtime_plan_job_returned")
                result_queue.put(("value", result))
            except BaseException as exc:  # pragma: no cover - re-raised below
                record_stage_event("native_planner_thread", "scenario_runtime_plan_job_error", terminal_reason=exc.__class__.__name__)
                result_queue.put(("error", exc))
            finally:
                _PLANNING_PROCESS_LOCK.release()

        thread = threading.Thread(
            target=runner,
            name="codex-native-imagegen-planner",
            daemon=True,
        )
        thread.start()
        try:
            kind, value = result_queue.get(timeout=self._planning_timeout_seconds)
        except queue.Empty as exc:
            record_stage_event(
                "native_planner_thread",
                "thread_timeout",
                terminal_reason="local_mcp_planning_timeout",
                extra={"timeout_seconds": self._planning_timeout_seconds},
            )
            raise _LocalMcpPlanningTimeout() from exc
        if kind == "error":
            raise value
        return value

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
    def _uploaded_assets(
        request: NativeImageGenPlanRequest | NativeSpecializedImageGenPlanRequest | NativeProfessionalImageGenPlanRequest,
        *,
        server_owned_references: tuple[NativeReferenceInput, ...] = (),
    ) -> list[UploadedAssetInfo]:
        """Translate explicit local files into the ordinary V3 upload shape.

        No copy, upload store, or alternate reference resolver is created
        here.  V3's normal admission/materialization path owns every
        subsequent decision, including a fail-closed rejection.
        """

        references = (*server_owned_references, *request.reference_inputs)
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
                    "codex_native_server_owned_reference": item.server_owned,
                    # Keep the shared Brain's existing public channel vocabulary
                    # stable; the adapter-only source label remains separate.
                    "codex_native_reference_channel": (
                        "portrait_identity" if item.channel == "selected_identity_reference" else item.channel
                    ),
                    "codex_native_selected_identity_reference": item.channel == "selected_identity_reference",
                    "selected_generated_output": item.channel == "selected_identity_reference",
                    "professional_anchor_lineage_role": (
                        "prior_view_winner"
                        if item.channel == "selected_identity_reference"
                        else "identity_root"
                    ),
                    "source_type": (
                        "selected_generated_output" if item.channel == "selected_identity_reference" else "uploaded"
                    ),
                    "output_id": item.asset_id if item.channel == "selected_identity_reference" else None,
                    "v3_owned_upload": True,
                },
            )
            for item in references
        ]

    @staticmethod
    def _canonical_materializations(
        planning_result: Any,
        *,
        metadata_overrides: dict[str, Any] | None = None,
        metadata_overrides_by_asset_id: dict[str, dict[str, Any]] | None = None,
    ) -> list[Any]:
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
            generation_plan = generation_plans[asset.asset_id]
            asset_metadata_overrides = (
                dict(metadata_overrides_by_asset_id.get(asset.asset_id) or {})
                if isinstance(metadata_overrides_by_asset_id, dict)
                else {}
            )
            combined_metadata_overrides = {
                **(metadata_overrides or {}),
                **asset_metadata_overrides,
            }
            if combined_metadata_overrides:
                generation_plan = generation_plan.model_copy(
                    update={
                        "metadata": {
                            **(
                                generation_plan.metadata
                                if isinstance(generation_plan.metadata, dict)
                                else {}
                            ),
                            **combined_metadata_overrides,
                        }
                    }
                )
            request = build_provider_generation_request(
                asset_spec=asset,
                layout_plan=layouts[asset.asset_id],
                prompt_compilation=prompts[asset.asset_id],
                condition_plan=conditions[asset.asset_id],
                generation_plan=generation_plan,
                job_id=planning_result.creative_job.job_id,
            )
            if combined_metadata_overrides:
                request = request.model_copy(
                    update={
                        "metadata": {
                            **request.metadata,
                            **{
                                key: value
                                for key, value in combined_metadata_overrides.items()
                                if key in {"reference_assets", "uploaded_assets"}
                            },
                        }
                    }
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
            result = self._blocked(f"codex_native_imagegen_{str(remote['reason_code'])}", message)
            # Keep Local MCP diagnosis actionable without exposing the raw
            # provider exception, endpoint, prompt or credential.  This is
            # the same public-safe outcome shape persisted by V3 jobs; it is
            # not a second runtime state machine and cannot authorize a
            # fallback, retry, provider request or delivery.
            safe_fields = {
                "schema_version",
                "state",
                "reason_code",
                "outcome_class",
                "llm_used",
                "fallback_used",
                "remote_provider_available",
                "remote_error_class",
                "remote_brain_stage",
                "remote_http_status_code",
                "execution_budget",
                "remote_brain_transport_failure",
                "remote_contract_rejected_sections",
                "expected_image_count",
                "actual_image_count",
                "actual_direction_count",
            }
            result["planning_failure"] = {}
            for key, value in remote.items():
                if key not in safe_fields:
                    continue
                if key == "remote_brain_transport_failure":
                    value = _safe_remote_brain_transport_failure(value)
                    if not value:
                        continue
                result["planning_failure"][key] = value
            return result
        return self._blocked("codex_native_imagegen_planning_blocked", message)
