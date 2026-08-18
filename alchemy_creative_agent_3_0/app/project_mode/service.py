"""Project Mode service wrapping the existing V3 Product API."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from typing import Any
from uuid import uuid4

from ..app_shell.routes import API_NAMESPACE
from ..creative_core.rules import stable_id
from ..product_api import V3ProductApiService
from ..product_api.contracts import (
    ProductJobStatus,
    ProductJobStatusValue,
    SelectionResponse,
    SelectedResult,
    V3AssetUploadStatusValue,
    V3UploadedAssetRecord,
)
from ..scenario_packs.photography import (
    PhotographerProfileBinding,
    PhotographyPackOutput,
    PhotographySetContinuationRequest,
)
from ..scenario_packs.photography.continuation import PhotographySetContinuationDirector
from ..scenario_packs.ecommerce.reference_projection import (
    PhysicalProductReferenceProjection,
    ProductTruthAdmission,
)
from ..scenario_packs.ecommerce.provider_deliverability_closure import (
    safe_closure_operation,
    verified_provider_deliverability_closure_receipt,
)
from ..scenario_packs.ecommerce.opaque_provider_rejection_hold import (
    safe_ambiguous_provider_request_hold_operation,
    verified_ambiguous_provider_request_hold_receipt,
)
from ..scenario_packs.ecommerce.predecessor_authority import (
    DOC279_PRIVATE_NAMESPACE,
    build_transparent_predecessor_receipt,
    verified_transparent_predecessor_receipt,
)
from ..scenario_packs.ecommerce.provider_deliverability_closure import (
    _verified_command_binding,
)
from ..schemas import BrandProfile, ProviderStrategy, ReferenceAsset
from ..shared_capabilities.activation import CapabilityActivationPlan, CapabilityPlanAmendment
from ..shared_capabilities.visual_cluster.reference_channel_policy import ReferenceChannelPolicyModule
from ..visual_assets import ProjectVisualAssetBindingService
from .contracts import (
    ECOMMERCE_TEMPLATE_ID,
    GENERAL_TEMPLATE_ID,
    CreateProjectJobRequest,
    CreateProjectRequest,
    EcommerceSlotAttemptSummary,
    EcommerceSlotContinuationRequest,
    EcommerceSlotContinuationResponse,
    EcommerceSlotCurrentDelivery,
    EcommerceSlotDeliveryResponse,
    EcommerceSlotLineage,
    PhotographyRoleAttemptSummary,
    PhotographyRoleContinuationRequest,
    PhotographyRoleContinuationResponse,
    PhotographyRoleCurrentDelivery,
    PhotographyRoleDeliveryResponse,
    PhotographyRoleLineage,
    OutputRef,
    ProjectBrandMemoryConfirmRequest,
    ProjectBrandMemoryConfirmResponse,
    ProjectBrandMemoryProposal,
    ProjectBrandMemoryProposalMode,
    ProjectBrandMemoryProposalRequest,
    ProjectBrandMemoryProposalResponse,
    ProjectBrandMemoryProposalStatus,
    ProjectCommerceProfile,
    ProjectContextPackage,
    ProjectFeedbackRecord,
    ProjectFeedbackRequest,
    ProjectFeedbackResponse,
    ProjectFeedbackStatus,
    ProjectFeedbackTargetType,
    ProjectFeedbackType,
    ProjectListResponse,
    ProjectMemorySummary,
    ProjectOutputSelectionStateValue,
    ProjectOutputStateRequest,
    ProjectReferenceAsset,
    ProjectReferenceRequest,
    ProjectReferenceResponse,
    ProjectReferenceSourceType,
    ProjectReferenceStatus,
    ProjectReferenceUpdateRequest,
    ProjectReferenceUsePolicy,
    ProjectRecord,
    ProjectResponse,
    ProjectSelectedOutputState,
    ProjectStatus,
    ProjectTimelineItem,
    ProjectTimelineResponse,
    PROJECT_API_SOURCE,
    PHOTOGRAPHER_TEMPLATE_ID,
    TemplateCard,
    TimelineItemType,
)
from .store import InMemoryProjectStore
from .source_library import (
    build_project_source_library,
    canonical_digest as doc270_canonical_digest,
    public_project_source_library,
    resolve_doc270_shadow_reference_requirements,
)
from .source_evidence import (
    CallableGeneralSourceSelectionBrain,
    GeneralSourceSelectionBrain,
    OpenAICompatibleGeneralSourceSelectionBrain,
)
from .ecommerce_view_activation import (
    DisabledEcommerceViewActivationIssuer,
    EcommerceViewActivationIssuer,
    issuer_from_environment,
)
from .templates import ProjectTemplateManifest, ProjectTemplateRegistry


ECOMMERCE_PRODUCT_UPLOAD_ROLES = {"product_reference", "subject_reference"}
PROJECT_PRODUCT_REFERENCE_ROLES = {"product", *ECOMMERCE_PRODUCT_UPLOAD_ROLES}
_ECOMMERCE_IGNORED_CLIENT_METADATA = frozenset(
    {
        "current_reference_binding_digest",
        "doc265_reference_channel_recovery",
        "supersedes_job_id",
        "historical_reference_projection",
        "legacy_reference_projection",
        "legacy_upload_authorization_facts",
        "provider_deliverability_closure_receipt",
        "ambiguous_provider_request_hold_receipt",
        "doc271_terminal_job_receipt",
        "doc271_current_source_binding",
        "doc271_command_binding",
        "doc271_project_goal_snapshot",
        "provider_policy_blocked",
        "provider_failure_retry",
        "doc270_project_source_library",
        "doc270_reference_resolution_receipts",
        "doc270_source_library_binding_receipts",
        "source_evidence_profile",
        "doc270_ecommerce_view_activation",
        "doc270_ecommerce_view_activation_receipts",
        "doc270_ecommerce_command_identity",
        "doc270_ecommerce_command_facts",
        "selected_product_asset_ids",
    }
)

_DOC270_IGNORED_CLIENT_METADATA = frozenset(
    {
        "doc270_project_source_library",
        "doc270_reference_resolution_receipts",
        "doc270_source_library_binding_receipts",
        "source_evidence_profile",
    }
)

_DOC270_PHASE3_IGNORED_CLIENT_METADATA = frozenset(
    {
        "doc270_general_activation",
        "doc270_general_source_activation_receipts",
        "doc270_general_original_source_projection",
        "doc270_general_command_identity",
        "server_command_identity",
        "doc270_reference_resolution_receipts",
        "selected_original_asset_ids",
    }
)
_DOC270_PHASE3_COMMAND_IDENTITY_KEYS = frozenset(
    {
        "schema_version",
        "issuer",
        "capability_id",
        "capability_version",
        "project_id",
        "template_id",
        "command_id",
        "command_plan_binding_digest",
        "coalescing_nonce",
        "identity_digest",
    }
)
_DOC270_PHASE3_PUBLIC_STATES = frozenset({"prompt_only", "receipt_invalid", "activated_resolved"})
_DOC270_PHASE3_PROTOCOL_VERSION = "doc270_phase3_general_activation_v1"
_DOC270_PHASE3_CAPABILITY_VERSION = "doc270_phase3_general_activation_capability_v1"
_DOC270_PHASE3_REGISTRY_VERSION = "doc270_phase3_receipt_registry_v1"
_DOC270_PHASE3_COMMAND_IDENTITY_POLICY = {
    "schema_version": "doc270_general_command_identity_v1",
    "issuer": "v3_project_mode_general_command_registry",
    "capability_id": "doc270_general_source_activation",
    "capability_version": _DOC270_PHASE3_CAPABILITY_VERSION,
}
_DOC270_PHASE3_REGISTRY_POLICY = {
    "issuer": "v3_doc270_phase2_receipt_registry",
    "schema_version": "doc270_phase2_registry_entry_v1",
    "version": _DOC270_PHASE3_REGISTRY_VERSION,
    "capability_id": "doc270_shadow_resolution_registry",
    "capability_version": _DOC270_PHASE3_CAPABILITY_VERSION,
}
_DOC270_PHASE3_ACTIVATION_CAPABILITY_POLICY = {
    "schema_version": "doc270_general_activation_capability_v1",
    "issuer": "v3_doc270_general_activation_registry",
    "capability_id": "doc270_general_source_activation",
    "capability_version": _DOC270_PHASE3_CAPABILITY_VERSION,
}

_DOC270_PHASE4_CAPABILITY_VERSION = "doc270_phase4_ecommerce_view_activation_v1"
_DOC270_PHASE4_COMMAND_IDENTITY_POLICY = {
    "schema_version": "doc270_ecommerce_command_identity_v1",
    "issuer": "v3_project_mode_ecommerce_command_registry",
    "capability_id": "doc270_ecommerce_view_activation",
    "capability_version": _DOC270_PHASE4_CAPABILITY_VERSION,
}
_DOC270_PHASE4_REGISTRY_POLICY = {
    "schema_version": "doc270_ecommerce_phase4_registry_entry_v1",
    "issuer": "v3_doc270_ecommerce_view_registry",
    "capability_id": "doc270_ecommerce_view_activation",
    "capability_version": _DOC270_PHASE4_CAPABILITY_VERSION,
}
_DOC270_PHASE4_CAPABILITY_POLICY = {
    "schema_version": "doc270_ecommerce_view_activation_capability_v1",
    "issuer": "v3_doc270_ecommerce_activation_registry",
    "capability_id": "doc270_ecommerce_view_activation",
    "capability_version": _DOC270_PHASE4_CAPABILITY_VERSION,
}
_DOC270_PHASE4_COMMAND_IDENTITY_KEYS = frozenset(
    {
        "schema_version",
        "issuer",
        "capability_id",
        "capability_version",
        "project_id",
        "template_id",
        "command_id",
        "command_plan_binding_digest",
        "coalescing_nonce",
        "identity_digest",
    }
)
_DOC270_PHASE4_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "issuer",
        "project_id",
        "command_identity",
        "command_plan_binding_digest",
        "output_index",
        "output_identity",
        "requirement_nonce",
        "requirement_digest",
        "source_library_snapshot_digest",
        "state",
        "maximum_sources",
        "matched_references",
        "evidence_profile_digests",
        "requirement_kind",
        "evidence_profile",
        "shadow_only",
        "receipt_digest",
    }
)
_DOC270_PHASE4_CURRENT_OPERATION_KEY = "doc270_ecommerce_view_activation_current_operation"
_DOC270_PHASE4_PRIVATE_POLICY_NAMESPACE = "doc270_phase4_activation_policy"
_DOC270_PHASE4_PRIVATE_COMMAND_NAMESPACE = "doc270_phase4_commands"
_DOC270_PHASE4_PRIVATE_ENTRY_NAMESPACE = "doc270_phase4_registry_entries"
_DOC270_PHASE4_PRIVATE_DECISION_NAMESPACE = "doc270_phase4_resolution_decisions"
_DOC281_TERMINAL_RECEIPT_NAMESPACE = "doc281_source_association_terminal_receipts_v1"
_DOC281_TERMINAL_RECEIPT_SCHEMA = "doc281_source_association_terminal_receipt_v1"
_DOC281_GENERAL_COMMAND_NAMESPACE = "doc281_general_commands_v1"
_DOC281_GENERAL_SELECTION_NAMESPACE = "doc281_general_selection_receipts_v2"
_DOC281_GENERAL_RECEIPT_NAMESPACE = "doc281_general_resolution_receipts_v1"
_DOC281_GENERAL_SOURCE_POLICY_FIELDS = frozenset({
    "enabled",
    "policy_authority",
    "policy_version",
    "maximum_sources",
})
_DOC270_PHASE4_REQUIREMENT_ISSUER = {
    "authority": "v3_server_template_requirement_issuer",
    "schema_version": "doc270_requirement_issuer_v1",
    "version": "doc270_server_requirement_issuer_v1",
}
_DOC270_PHASE4_ANALYZER = {
    "authority": "v3_server_image_evidence",
    "schema_version": "doc270_image_evidence_analyzer_v1",
    "version": "doc270_server_image_evidence_v1",
}
_DOC270_PHASE4_REQUIREMENT_KINDS = frozenset(
    {"object_front_presentation", "object_rear_structure", "object_detail"}
)
_DOC277_PRIVATE_PLANNING_NAMESPACE = "doc277_project_planning_operations"
_DOC277_CURRENT_OPERATION_KEY = "doc277_planning_current_operation"
_DOC277_OPERATION_STATES = frozenset({"planning", "planning_failed"})


class EcommerceSlotContinuationError(ValueError):
    """Structured public failure for the namespaced slot-continuation route."""

    def __init__(self, code: str, message: str, *, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.v3_status_code = status_code


class PhotographyRoleContinuationError(ValueError):
    """Structured public failure for the Photography role-continuation route."""

    def __init__(self, code: str, message: str, *, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.v3_status_code = status_code


class Doc281GeneralSourceRegistry:
    """Brain-owned General original selection with server-only integrity binding.

    General receives no semantic taxonomy. A source-selection Brain sees the
    explicit command and all reverified current originals at once, then emits
    only opaque handles. This registry maps those handles back to the exact
    reference/asset/SHA snapshot, freezes the receipt, and never admits history
    or browser-authored selection facts.
    """

    protocol = "doc281_general_source_registry_v2"
    _CACHE_MISS = "miss"
    _CACHE_SELECTED = "selected"
    _CACHE_PROMPT_ONLY = "prompt_only"
    _CACHE_INVALID = "invalid"

    def __init__(
        self,
        *,
        selection_brain: GeneralSourceSelectionBrain | Any | None = None,
        analysis_entry_loader: Any | None = None,
        selection_policy_version: str = "doc281_general_source_selection_policy_v2",
        maximum_sources: int = 2,
        selection_receipt_lookup: Any | None = None,
        selection_receipt_append: Any | None = None,
    ) -> None:
        self.selection_brain = self._coerce_selection_brain(selection_brain)
        self.analysis_entry_loader = analysis_entry_loader
        self.selection_policy_version = str(selection_policy_version or "").strip()
        self.maximum_sources = maximum_sources
        self.selection_receipt_lookup = selection_receipt_lookup
        self.selection_receipt_append = selection_receipt_append
        self._identities: dict[str, dict[str, Any]] = {}
        self._receipts: dict[str, dict[str, Any]] = {}

    @property
    def enabled(self) -> bool:
        return bool(
            self.selection_brain is not None
            and self.selection_policy_version
            and isinstance(self.maximum_sources, int)
            and not isinstance(self.maximum_sources, bool)
            and 1 <= self.maximum_sources <= 4
        )

    @staticmethod
    def _coerce_selection_brain(value: GeneralSourceSelectionBrain | Any | None) -> GeneralSourceSelectionBrain | None:
        if isinstance(value, GeneralSourceSelectionBrain):
            return value
        if callable(value):
            return CallableGeneralSourceSelectionBrain(value)
        return None

    def issue_command_identity(self, **kwargs: Any) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        project_id = str(kwargs.get("project_id") or "").strip()
        template_id = str(kwargs.get("template_id") or "").strip()
        snapshot = kwargs.get("source_library_snapshot")
        command_direction = str(kwargs.get("command_direction") or "").strip()
        requested_output_count = kwargs.get("requested_output_count")
        if (
            not project_id
            or template_id != GENERAL_TEMPLATE_ID
            or not isinstance(snapshot, dict)
            or not command_direction
            or not isinstance(requested_output_count, int)
            or isinstance(requested_output_count, bool)
            or not 1 <= requested_output_count <= 8
        ):
            return None
        snapshot_digest = str(snapshot.get("snapshot_digest") or "").strip().lower()
        if len(snapshot_digest) != 64:
            return None
        selection_facts = {
            "schema_version": "doc281_general_source_selection_v2",
            "project_id": project_id,
            "template_id": template_id,
            "command_direction": command_direction,
            "source_library_snapshot_digest": snapshot_digest,
            "policy_version": self.selection_policy_version,
            "requested_output_count": requested_output_count,
            "maximum_sources": self.maximum_sources,
        }
        binding_digest = doc270_canonical_digest(selection_facts)
        cache_state, selection = self._cached_selection(
            project_id=project_id,
            selection_facts=selection_facts,
            selection_binding_digest=binding_digest,
        )
        if cache_state == self._CACHE_INVALID:
            return None
        if cache_state == self._CACHE_MISS:
            selection = self._select_current_sources(
                project_id=project_id,
                snapshot=snapshot,
                command_direction=command_direction,
                requested_output_count=requested_output_count,
                selection_binding_digest=binding_digest,
            )
            if selection is None:
                return None
            if callable(self.selection_receipt_append):
                try:
                    self.selection_receipt_append(
                        project_id=project_id,
                        selection_facts=dict(selection_facts),
                        selection_binding_digest=binding_digest,
                        selection=dict(selection),
                    )
                except Exception:
                    return None
        if not isinstance(selection, dict):
            return None
        selection_digest = str(selection.get("selection_digest") or "").strip().lower()
        if len(selection_digest) != 64:
            return None
        output_plan = [
            {
                "output_index": output_index,
                "output_nonce": doc270_canonical_digest({
                    "project_id": project_id,
                    "template_id": template_id,
                    "command_direction": command_direction,
                    "source_library_snapshot_digest": snapshot_digest,
                    "selection_digest": selection_digest,
                    "output_index": output_index,
                }),
            }
            for output_index in range(1, requested_output_count + 1)
        ]
        output_plan_digest = doc270_canonical_digest(output_plan)
        command_facts = {
            "project_id": project_id,
            "template_id": template_id,
            "command_direction": command_direction,
            "source_library_snapshot_digest": snapshot_digest,
            "selection_digest": selection_digest,
            "requested_output_count": requested_output_count,
            "output_plan_digest": output_plan_digest,
        }
        command_facts_digest = doc270_canonical_digest(command_facts)
        identity = {
            "schema_version": "doc281_general_command_identity_v2",
            "issuer": "v3_doc281_general_source_selection_brain",
            "protocol": self.protocol,
            "project_id": project_id,
            "template_id": template_id,
            "command_id": stable_id("doc281_general_command", command_facts_digest),
            "plan_binding_digest": doc270_canonical_digest(command_facts),
            "coalescing_nonce": command_facts_digest,
            "requested_output_count": requested_output_count,
            "output_plan_digest": output_plan_digest,
        }
        identity["identity_digest"] = doc270_canonical_digest(identity)
        self._identities[identity["identity_digest"]] = {
            "identity": dict(identity),
            "selection": dict(selection),
            "snapshot": dict(snapshot),
            "output_plan": output_plan,
        }
        return dict(identity)

    def _select_current_sources(
        self,
        *,
        project_id: str,
        snapshot: dict[str, Any],
        command_direction: str,
        requested_output_count: int,
        selection_binding_digest: str,
    ) -> dict[str, Any] | None:
        original_entries = [
            dict(item)
            for item in snapshot.get("entries", [])
            if isinstance(item, dict)
            and item.get("automatic_use_eligible") is True
            and item.get("availability_state") == "ready_verified"
        ]
        if not original_entries:
            return self._bound_selection(
                {"state": "prompt_only", "output_selections": []},
                candidates={},
                requested_output_count=requested_output_count,
                selection_binding_digest=selection_binding_digest,
            )
        if not callable(self.analysis_entry_loader):
            return None
        try:
            loaded = self.analysis_entry_loader(project_id=project_id, entries=original_entries)
        except Exception:
            return None
        if not isinstance(loaded, list) or len(loaded) != len(original_entries):
            return None
        original_by_reference = {
            str(item.get("reference_id") or ""): item
            for item in original_entries
            if str(item.get("reference_id") or "")
        }
        candidates: dict[str, dict[str, Any]] = {}
        for item in loaded:
            if not isinstance(item, dict):
                return None
            reference_id = str(item.get("reference_id") or "")
            original = original_by_reference.get(reference_id)
            if (
                not isinstance(original, dict)
                or item.get("asset_id") != original.get("asset_id")
                or item.get("content_sha256") != original.get("content_sha256")
            ):
                return None
            handle = doc270_canonical_digest({
                "schema_version": "doc281_general_source_candidate_handle_v1",
                "reference_id": reference_id,
                "asset_id": str(original.get("asset_id") or ""),
                "content_sha256": str(original.get("content_sha256") or ""),
            })
            if handle in candidates:
                return None
            candidates[handle] = {
                "reference_id": reference_id,
                "asset_id": str(original.get("asset_id") or ""),
                "content_sha256": str(original.get("content_sha256") or ""),
                "candidate_handle": handle,
                "analysis_bytes": item.get("analysis_bytes"),
                "mime_type": item.get("mime_type"),
            }
        try:
            issued = self.selection_brain.select(
                command_direction=command_direction,
                entries=[
                    {
                        "candidate_handle": handle,
                        "analysis_bytes": candidate["analysis_bytes"],
                        "mime_type": candidate["mime_type"],
                    }
                    for handle, candidate in sorted(candidates.items())
                ],
                requested_output_count=requested_output_count,
                maximum_sources=self.maximum_sources,
            )
        except Exception:
            return None
        return self._bound_selection(
            issued,
            candidates=candidates,
            requested_output_count=requested_output_count,
            selection_binding_digest=selection_binding_digest,
        )

    def _bound_selection(
        self,
        issued: Any,
        *,
        candidates: dict[str, dict[str, Any]],
        requested_output_count: int,
        selection_binding_digest: str,
    ) -> dict[str, Any] | None:
        if not isinstance(issued, dict) or set(issued) != {"state", "output_selections"}:
            return None
        state = issued.get("state")
        output_selections = issued.get("output_selections")
        if state == "prompt_only":
            if output_selections != []:
                return None
            selection = {
                "schema_version": "doc281_general_source_selection_v2",
                "state": "prompt_only",
                "maximum_sources": self.maximum_sources,
                "policy_version": self.selection_policy_version,
                "selection_binding_digest": selection_binding_digest,
                "output_selections": [],
            }
            selection["selection_digest"] = doc270_canonical_digest(selection)
            return selection
        if state != "selected" or not isinstance(output_selections, list) or len(output_selections) != requested_output_count:
            return None
        indexes: set[int] = set()
        bound_outputs: list[dict[str, Any]] = []
        for output in output_selections:
            if not isinstance(output, dict) or set(output) != {"output_index", "candidate_handles"}:
                return None
            index = output.get("output_index")
            handles = output.get("candidate_handles")
            if (
                not isinstance(index, int)
                or isinstance(index, bool)
                or index < 1
                or index > requested_output_count
                or index in indexes
                or not isinstance(handles, list)
                or not 1 <= len(handles) <= self.maximum_sources
                or len(handles) != len(set(handles))
                or any(not isinstance(handle, str) or handle not in candidates for handle in handles)
            ):
                return None
            indexes.add(index)
            selected_sources = [
                {
                    "reference_id": str(candidates[handle]["reference_id"]),
                    "asset_id": str(candidates[handle]["asset_id"]),
                    "content_sha256": str(candidates[handle]["content_sha256"]),
                }
                for handle in handles
            ]
            bound_outputs.append({
                "output_index": index,
                "selected_sources": sorted(selected_sources, key=doc270_canonical_digest),
            })
        if indexes != set(range(1, requested_output_count + 1)):
            return None
        selection = {
            "schema_version": "doc281_general_source_selection_v2",
            "state": "selected",
            "maximum_sources": self.maximum_sources,
            "policy_version": self.selection_policy_version,
            "selection_binding_digest": selection_binding_digest,
            "output_selections": sorted(bound_outputs, key=lambda item: item["output_index"]),
        }
        selection["selection_digest"] = doc270_canonical_digest(selection)
        return selection

    def _cached_selection(
        self,
        *,
        project_id: str,
        selection_facts: dict[str, Any],
        selection_binding_digest: str,
    ) -> tuple[str, dict[str, Any] | None]:
        if not callable(self.selection_receipt_lookup):
            return self._CACHE_MISS, None
        try:
            record = self.selection_receipt_lookup(
                project_id=project_id,
                selection_binding_digest=selection_binding_digest,
            )
        except Exception:
            return self._CACHE_INVALID, None
        if record is None:
            return self._CACHE_MISS, None
        if not isinstance(record, dict) or set(record) != {
            "schema_version", "identity_digest", "selection_binding_digest",
            "selection_facts", "selection", "receipt_digest",
        }:
            return self._CACHE_INVALID, None
        if (
            record.get("schema_version") != "doc281_general_source_selection_receipt_v2"
            or record.get("identity_digest") != selection_binding_digest
            or record.get("selection_binding_digest") != selection_binding_digest
            or record.get("selection_facts") != selection_facts
            or not self._same_digest_record(record, "receipt_digest")
        ):
            return self._CACHE_INVALID, None
        selection = self._selection_from_record(
            record.get("selection"),
            requested_output_count=int(selection_facts["requested_output_count"]),
            selection_binding_digest=selection_binding_digest,
        )
        if selection is None:
            return self._CACHE_INVALID, None
        return (
            self._CACHE_SELECTED if selection["state"] == "selected" else self._CACHE_PROMPT_ONLY,
            selection,
        )

    def _selection_from_record(
        self,
        value: Any,
        *,
        requested_output_count: int,
        selection_binding_digest: str,
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict) or set(value) != {
            "schema_version", "state", "maximum_sources", "policy_version",
            "selection_binding_digest", "output_selections", "selection_digest",
        }:
            return None
        if (
            value.get("schema_version") != "doc281_general_source_selection_v2"
            or value.get("maximum_sources") != self.maximum_sources
            or value.get("policy_version") != self.selection_policy_version
            or value.get("selection_binding_digest") != selection_binding_digest
            or not self._same_digest_record(value, "selection_digest")
        ):
            return None
        state = value.get("state")
        outputs = value.get("output_selections")
        if state == "prompt_only":
            return dict(value) if outputs == [] else None
        if state != "selected" or not isinstance(outputs, list) or len(outputs) != requested_output_count:
            return None
        indexes: set[int] = set()
        for output in outputs:
            if not isinstance(output, dict) or set(output) != {"output_index", "selected_sources"}:
                return None
            index = output.get("output_index")
            sources = output.get("selected_sources")
            if (
                not isinstance(index, int)
                or isinstance(index, bool)
                or index < 1
                or index > requested_output_count
                or index in indexes
                or not isinstance(sources, list)
                or not 1 <= len(sources) <= self.maximum_sources
            ):
                return None
            identities: set[tuple[str, str]] = set()
            for source in sources:
                if not isinstance(source, dict) or set(source) != {"reference_id", "asset_id", "content_sha256"}:
                    return None
                reference_id = str(source.get("reference_id") or "")
                asset_id = str(source.get("asset_id") or "")
                content_sha256 = str(source.get("content_sha256") or "").lower()
                if (
                    not reference_id
                    or not asset_id
                    or len(content_sha256) != 64
                    or (reference_id, asset_id) in identities
                ):
                    return None
                identities.add((reference_id, asset_id))
            indexes.add(index)
        return dict(value) if indexes == set(range(1, requested_output_count + 1)) else None

    @staticmethod
    def _same_digest_record(value: dict[str, Any], field: str) -> bool:
        digest = str(value.get(field) or "").strip().lower()
        return len(digest) == 64 and digest == doc270_canonical_digest(
            {key: item for key, item in value.items() if key != field}
        )

    def lookup_registered_receipt(self, **kwargs: Any) -> dict[str, Any] | None:
        identity = kwargs.get("command_identity")
        project_id = str(kwargs.get("project_id") or "").strip()
        if not self.enabled or not isinstance(identity, dict) or identity.get("project_id") != project_id:
            return None
        stored = self._identities.get(str(identity.get("identity_digest") or ""))
        if not isinstance(stored, dict) or stored.get("identity") != identity:
            return None
        receipt = self._receipts.get(str(identity["identity_digest"]))
        if receipt is None:
            selection = dict(stored["selection"])
            snapshot = dict(stored["snapshot"])
            selected_by_output = {
                int(item["output_index"]): [dict(source) for source in item["selected_sources"]]
                for item in selection.get("output_selections", [])
                if isinstance(item, dict)
                and isinstance(item.get("output_index"), int)
                and isinstance(item.get("selected_sources"), list)
            }
            output_bindings: list[dict[str, Any]] = []
            for plan_item in stored["output_plan"]:
                output_index = int(plan_item["output_index"])
                binding = {
                    "output_index": output_index,
                    "output_nonce": str(plan_item["output_nonce"]),
                    "matched_references": selected_by_output.get(output_index, []),
                }
                binding["output_binding_digest"] = doc270_canonical_digest({
                    "project_id": project_id,
                    "command_plan_binding_digest": identity["plan_binding_digest"],
                    "selection_digest": selection["selection_digest"],
                    "source_library_snapshot_digest": snapshot["snapshot_digest"],
                    **binding,
                })
                output_bindings.append(binding)
            all_selected: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for binding in output_bindings:
                for source in binding["matched_references"]:
                    key = (str(source["reference_id"]), str(source["asset_id"]))
                    if key not in seen:
                        seen.add(key)
                        all_selected.append(dict(source))
            receipt = {
                "project_id": project_id,
                "command_plan_binding_digest": identity["plan_binding_digest"],
                "selection_digest": selection["selection_digest"],
                "source_library_snapshot_digest": snapshot["snapshot_digest"],
                "state": "resolved" if selection["state"] == "selected" else "prompt_only",
                "matched_references": sorted(all_selected, key=doc270_canonical_digest),
                "output_bindings": output_bindings if selection["state"] == "selected" else [],
            }
            receipt["receipt_digest"] = doc270_canonical_digest(receipt)
            self._receipts[str(identity["identity_digest"])] = receipt
        return {
            "protocol": self.protocol,
            "schema_version": "doc281_general_registered_receipt_v2",
            "command_identity": dict(identity),
            "receipt": dict(receipt),
        }

    def selection_for_identity(self, identity: dict[str, Any]) -> dict[str, Any] | None:
        stored = self._identities.get(str(identity.get("identity_digest") or ""))
        selection = stored.get("selection") if isinstance(stored, dict) else None
        return dict(selection) if isinstance(selection, dict) else None

    def observations_for_identity(self, _identity: dict[str, Any]) -> list[dict[str, Any]]:
        return []


def doc281_general_source_registry_from_environment() -> Doc281GeneralSourceRegistry:
    """Compose the General source-selection Brain from private server config."""

    configured = str(os.getenv("ALCHEMY_DOC281_GENERAL_SOURCE_POLICY_PATH") or "").strip()
    policy_path = Path(configured) if configured else Path(__file__).with_name("policies") / "doc281_general_source_policy_v1.json"
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return Doc281GeneralSourceRegistry()
    if (
        not isinstance(policy, dict)
        or set(policy) != _DOC281_GENERAL_SOURCE_POLICY_FIELDS
        or policy.get("enabled") is not True
        or not isinstance(policy.get("policy_authority"), str)
        or not str(policy["policy_authority"]).strip()
        or not isinstance(policy.get("policy_version"), str)
        or not str(policy["policy_version"]).strip()
    ):
        return Doc281GeneralSourceRegistry()
    maximum_sources = policy.get("maximum_sources")
    if (
        not isinstance(maximum_sources, int)
        or isinstance(maximum_sources, bool)
        or not 1 <= maximum_sources <= 4
    ):
        return Doc281GeneralSourceRegistry()
    try:
        from ..shared_capabilities.visual_cluster.vision_provider import _lab_vision_enabled, _lab_vision_setting
        if not _lab_vision_enabled():
            return Doc281GeneralSourceRegistry()
        api_key, base_url, model = (_lab_vision_setting(field) for field in ("api_key", "base_url", "model"))
        brain = OpenAICompatibleGeneralSourceSelectionBrain(
            api_key=api_key, base_url=base_url, model=model,
            timeout_seconds=float(os.getenv(
                "ALCHEMY_DOC281_GENERAL_SOURCE_SELECTION_TIMEOUT_SECONDS",
                os.getenv("ALCHEMY_DOC281_GENERAL_SOURCE_ANALYSIS_TIMEOUT_SECONDS", "30"),
            )),
        )
    except (ImportError, ValueError, TypeError):
        return Doc281GeneralSourceRegistry()
    if not brain.available():
        return Doc281GeneralSourceRegistry()

    return Doc281GeneralSourceRegistry(
        selection_brain=brain,
        selection_policy_version=str(policy["policy_version"]),
        maximum_sources=maximum_sources,
    )


class V3ProjectModeService:
    """V3-owned project layer that delegates job execution to Product API."""

    def __init__(
        self,
        product_service: V3ProductApiService | None = None,
        project_store: InMemoryProjectStore | None = None,
        template_registry: ProjectTemplateRegistry | None = None,
        reference_channel_policy_module: ReferenceChannelPolicyModule | None = None,
        project_visual_asset_binding_service: ProjectVisualAssetBindingService | None = None,
        ecommerce_view_activation_issuer: EcommerceViewActivationIssuer | None = None,
        doc281_general_source_registry: Doc281GeneralSourceRegistry | None = None,
    ) -> None:
        self.product_service = product_service or V3ProductApiService()
        self.project_store = project_store or InMemoryProjectStore()
        scenario_registry = getattr(getattr(self.product_service, "scenario_runtime", None), "scenario_registry", None)
        self.template_registry = template_registry or ProjectTemplateRegistry(scenario_registry=scenario_registry)
        self.reference_channel_policy_module = reference_channel_policy_module or ReferenceChannelPolicyModule()
        self.project_visual_asset_binding_service = project_visual_asset_binding_service
        self.ecommerce_view_activation_issuer = (
            ecommerce_view_activation_issuer or issuer_from_environment()
        )
        self.doc281_general_source_registry = doc281_general_source_registry or doc281_general_source_registry_from_environment()
        if (
            isinstance(self.doc281_general_source_registry, Doc281GeneralSourceRegistry)
            and self.doc281_general_source_registry.analysis_entry_loader is None
        ):
            self.doc281_general_source_registry.analysis_entry_loader = self._doc281_general_analysis_entries
        if isinstance(self.doc281_general_source_registry, Doc281GeneralSourceRegistry):
            if self.doc281_general_source_registry.selection_receipt_lookup is None:
                self.doc281_general_source_registry.selection_receipt_lookup = (
                    self._doc281_general_selection_receipt_lookup
                )
            if self.doc281_general_source_registry.selection_receipt_append is None:
                self.doc281_general_source_registry.selection_receipt_append = (
                    self._doc281_general_selection_receipt_append
                )
        self._doc277_planning_lock = threading.RLock()
        # Product API uses this narrow readback only while authenticating a
        # terminal Doc271 record. It reads an append-only Project Mode snapshot
        # instead of trusting a copy in Job metadata.
        self.product_service.doc271_project_goal_snapshot_lookup = self._doc271_project_goal_snapshot
        self.product_service.doc271_command_attempt_association_lookup = (
            self._doc271_command_attempt_association
        )
        self.product_service.doc270_source_library_snapshot_lookup = (
            self._doc270_project_source_library_by_id
        )
        # Resolve these at call time so a restarted/extended Project Mode
        # service remains the sole owner of E31 private authority.
        self.product_service.doc270_ecommerce_view_activation_resolver = (
            lambda **kwargs: self._doc270_ecommerce_view_activation_decision(**kwargs)
        )
        self.product_service.doc270_ecommerce_view_activation_identity_issuer = (
            lambda **kwargs: self._doc270_ecommerce_command_identity_lookup(**kwargs)
        )
        self.product_service.doc270_ecommerce_view_activation_existing_lookup = (
            lambda **kwargs: self._doc270_ecommerce_existing_command_by_identity(**kwargs)
        )

    def _doc270_general_activation_capability_lookup(self) -> dict[str, Any] | None:
        """Return a server-owned activation capability when one is registered."""

        return None

    def _doc270_general_command_identity_lookup(self, **_kwargs: Any) -> dict[str, Any] | None:
        """Issue/read a private General command identity. Disabled by default."""

        return None

    def _doc270_general_phase2_receipt_registry_lookup(self, **_kwargs: Any) -> dict[str, Any] | None:
        """Read a server-owned Phase 2 receipt entry. Disabled by default."""

        return None

    def _doc281_general_selection_receipt_lookup(
        self,
        *,
        project_id: str,
        selection_binding_digest: str,
    ) -> dict[str, Any] | None:
        """Read one exact private Brain-selection receipt for replay only."""

        if not isinstance(project_id, str) or not isinstance(selection_binding_digest, str):
            return None
        try:
            records = self.project_store.list_private_records(
                project_id, _DOC281_GENERAL_SELECTION_NAMESPACE,
            )
        except Exception:
            return None
        for record in reversed(records):
            if (
                isinstance(record, dict)
                and record.get("selection_binding_digest") == selection_binding_digest
            ):
                return dict(record)
        return None

    def _doc281_general_selection_receipt_append(
        self,
        *,
        project_id: str,
        selection_facts: dict[str, Any],
        selection_binding_digest: str,
        selection: dict[str, Any],
    ) -> dict[str, object]:
        receipt = {
            "schema_version": "doc281_general_source_selection_receipt_v2",
            "identity_digest": selection_binding_digest,
            "selection_binding_digest": selection_binding_digest,
            "selection_facts": dict(selection_facts),
            "selection": dict(selection),
        }
        receipt["receipt_digest"] = self._doc270_digest(receipt)
        return self.project_store.append_private_record(
            project_id, _DOC281_GENERAL_SELECTION_NAMESPACE, receipt,
        )

    def _doc270_ecommerce_view_activation_capability_lookup(
        self,
        *,
        project_id: str | None = None,
        expected_output_count: int | None = None,
    ) -> dict[str, Any] | None:
        """Return the private E31 capability when its server registry enables it."""

        if not project_id:
            return None
        try:
            capability = self.ecommerce_view_activation_issuer.capability(project_id=project_id)
        except Exception:
            return None
        if (
            expected_output_count is not None
            and (
                not isinstance(expected_output_count, int)
                or isinstance(expected_output_count, bool)
                or not self.ecommerce_view_activation_issuer.supports_output_count(
                    expected_output_count=expected_output_count
                )
            )
        ):
            return None
        return dict(capability) if isinstance(capability, dict) else None

    def _doc270_ecommerce_command_identity_lookup(self, **_kwargs: Any) -> dict[str, Any] | None:
        """Issue/read one E31 identity from private server command facts."""

        project_id = str(_kwargs.get("project_id") or "").strip()
        template_id = str(_kwargs.get("template_id") or "").strip()
        facts = _kwargs.get("command_facts")
        if not project_id or template_id != ECOMMERCE_TEMPLATE_ID or not isinstance(facts, dict):
            return None
        try:
            project = self._require_project(project_id)
            snapshot = self._doc270_project_source_library(project)
        except Exception:
            return None
        normalized = {
            "project_id": project_id,
            "template_id": template_id,
            "command_direction": str(facts.get("command_direction") or "").strip(),
            "requested_output_count": int(facts.get("requested_output_count") or 0),
            "current_reference_binding_digest": self._ecommerce_current_reference_binding_digest(project),
            "source_library_snapshot_digest": str(snapshot.get("snapshot_digest") or "").strip(),
        }
        if not normalized["command_direction"] or normalized["requested_output_count"] < 1:
            return None
        command_facts_digest = self._doc270_digest(normalized)
        for record in self.project_store.list_private_records(
            project_id, _DOC270_PHASE4_PRIVATE_COMMAND_NAMESPACE
        ):
            if record.get("command_facts_digest") == command_facts_digest:
                identity = record.get("identity")
                return dict(identity) if isinstance(identity, dict) else None
        command_id = stable_id(
            "doc270_ecommerce_phase4_command", project_id, command_facts_digest
        )
        identity = {
            **_DOC270_PHASE4_COMMAND_IDENTITY_POLICY,
            "project_id": project_id,
            "template_id": template_id,
            "command_id": command_id,
            "command_plan_binding_digest": self._doc270_digest(
                {
                    "command_id": command_id,
                    "command_facts_digest": command_facts_digest,
                    "source_library_snapshot_digest": normalized["source_library_snapshot_digest"],
                }
            ),
            "coalescing_nonce": command_facts_digest,
        }
        identity["identity_digest"] = self._doc270_digest(identity)
        self.project_store.append_private_record(
            project_id,
            _DOC270_PHASE4_PRIVATE_COMMAND_NAMESPACE,
            {
                "schema_version": "doc270_ecommerce_phase4_command_facts_v1",
                "identity_digest": identity["identity_digest"],
                "command_facts_digest": command_facts_digest,
                "command_facts": normalized,
                "identity": identity,
            },
        )
        return dict(identity)

    def _doc270_ecommerce_analysis_entries(
        self,
        *,
        project_id: str,
        entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]] | None:
        """Re-read bytes immediately before the private analyzer port.

        `analysis_bytes` exists only on the ephemeral adapter input. It is
        removed before policy persistence, Job metadata, and every public
        projection.
        """

        result: list[dict[str, Any]] = []
        for entry in entries:
            asset_id = str(entry.get("asset_id") or "").strip()
            expected_sha = str(entry.get("content_sha256") or "").strip().lower()
            record = self.product_service.get_uploaded_asset(asset_id)
            record_status = str(getattr(getattr(record, "status", None), "value", getattr(record, "status", ""))).strip()
            role = str(getattr(record, "role", "") or "").strip()
            mime_type = str(getattr(record, "mime_type", "") or "").strip().lower()
            if (
                not asset_id
                or len(expected_sha) != 64
                or record is None
                or record_status != "ready"
                or role != "product_reference"
                or mime_type not in {"image/png", "image/jpeg", "image/webp"}
                or entry.get("source_type") != "uploaded"
                or entry.get("use_policy") != "product"
                or entry.get("reference_channel") != "product_truth"
            ):
                return None
            path = Path(str(getattr(record, "file_path", "") or "")) if record is not None else None
            if path is None or not path.is_file():
                return None
            try:
                content = path.read_bytes()
            except OSError:
                return None
            actual_sha = hashlib.sha256(content).hexdigest()
            if actual_sha != expected_sha:
                return None
            result.append({
                **dict(entry),
                "mime_type": mime_type,
                "analysis_bytes": content,
            })
        return result or None

    def _doc270_ecommerce_existing_command_by_identity(
        self,
        *,
        project_id: str,
        identity: dict[str, Any],
    ) -> ProductJobStatus | None:
        try:
            project = self._require_project(project_id)
        except Exception:
            return None
        return self._doc270_ecommerce_existing_command(project, identity)

    def _doc270_ecommerce_phase2_receipt_registry_lookup(self, **_kwargs: Any) -> dict[str, Any] | None:
        """Read or issue private E31 receipts for one new E-Commerce command."""

        project_id = str(_kwargs.get("project_id") or "").strip()
        identity = _kwargs.get("command_identity")
        if not project_id or not isinstance(identity, dict):
            return None
        existing = self._doc270_ecommerce_private_entry(project_id, identity)
        if existing is not None:
            return existing
        if self._doc270_ecommerce_private_decision_exists(project_id, identity):
            return None
        command = self._doc270_ecommerce_private_command(project_id, identity)
        if command is None:
            return None
        policy = self._doc270_ecommerce_private_policy(project_id, identity)
        policy_was_persisted = policy is not None
        issue_outcome = "ready"
        if policy is None:
            policy, issue_outcome = self._doc270_ecommerce_issue_policy_for_command(
                project_id=project_id,
                identity=identity,
                command=command,
            )
        if policy is None:
            if issue_outcome == "source_analysis_unavailable":
                # Operational analysis availability is not a durable product
                # evidence verdict. A later explicit submit may analyze again.
                return {"state": "source_analysis_unavailable"}
            self.project_store.append_private_record(
                project_id,
                _DOC270_PHASE4_PRIVATE_DECISION_NAMESPACE,
                {
                    "schema_version": "doc270_ecommerce_phase4_resolution_decision_v1",
                    "identity_digest": str(identity.get("identity_digest") or ""),
                    "state": "needs_input",
                },
            )
            return None
        try:
            entry = self._issue_doc270_ecommerce_phase4_registry_entry(
                project_id=project_id,
                identity=identity,
                command=command,
                policy=policy,
            )
        except Exception:
            entry = None
        if entry is None:
            if issue_outcome == "source_analysis_incomplete":
                # At least one canonical original could not be observed. It
                # may satisfy the unmatched hard requirement once analysis
                # recovers, so do not persist a negative product verdict.
                return {"state": "source_analysis_unavailable"}
            self.project_store.append_private_record(
                project_id,
                _DOC270_PHASE4_PRIVATE_DECISION_NAMESPACE,
                {
                    "schema_version": "doc270_ecommerce_phase4_resolution_decision_v1",
                    "identity_digest": str(identity.get("identity_digest") or ""),
                    "state": "needs_input",
                },
            )
            return None
        if not policy_was_persisted:
            try:
                self._register_doc270_ecommerce_view_activation_policy(
                    project_id=project_id,
                    identity=identity,
                    requirements=list(policy.get("requirements") or []),
                    evidence_profiles=list(policy.get("evidence_profiles") or []),
                    provenance=policy.get("provenance"),
                )
            except (TypeError, ValueError):
                return {"state": "source_analysis_unavailable"}
        self.project_store.append_private_record(
            project_id,
            _DOC270_PHASE4_PRIVATE_ENTRY_NAMESPACE,
            {
                "schema_version": "doc270_ecommerce_phase4_registry_record_v1",
                "identity_digest": str(identity["identity_digest"]),
                "entry": entry,
            },
        )
        return entry

    def _register_doc270_ecommerce_view_activation_policy(
        self,
        *,
        project_id: str,
        identity: dict[str, Any],
        requirements: list[dict[str, Any]],
        evidence_profiles: list[dict[str, Any]],
        provenance: Any = None,
        enabled: bool = True,
    ) -> None:
        """Append one private E31 policy issued by a trusted server operator.

        This has no public route.  Its strict input validation makes the
        durable record suitable for production configuration and deterministic
        local tests without ever treating browser metadata as policy.
        """

        if not self._doc270_ecommerce_command_identity_valid(identity, project_id=project_id):
            raise ValueError("doc270_ecommerce_activation_policy_invalid")
        if self._doc270_ecommerce_private_command(project_id, identity) is None:
            raise ValueError("doc270_ecommerce_activation_policy_invalid")
        self._require_project(project_id)
        project = self._require_project(project_id)
        snapshot = self._doc270_project_source_library(project)
        entries = {
            str(item.get("reference_id") or ""): item
            for item in snapshot.get("entries", [])
            if isinstance(item, dict) and item.get("ecommerce_product_eligible") is True
        }
        expected_profile_keys = {
            "schema_version", "analyzer", "project_id", "reference_id", "asset_id",
            "content_sha256", "evidence_state", "subject_kind", "view_kind", "affordances", "profile_digest",
        }
        expected_affordances = {
            "front": "object_front_presentation",
            "rear": "object_back_or_structure",
            "detail_or_macro": "object_detail",
        }
        for profile in evidence_profiles:
            reference_id = str(profile.get("reference_id") or "") if isinstance(profile, dict) else ""
            entry = entries.get(reference_id)
            if (
                not isinstance(profile, dict)
                or set(profile) != expected_profile_keys
                or profile.get("schema_version") != "doc270_source_evidence_profile_v2"
                or profile.get("analyzer") != _DOC270_PHASE4_ANALYZER
                or profile.get("project_id") != project_id
                or not isinstance(entry, dict)
                or profile.get("asset_id") != entry.get("asset_id")
                or profile.get("content_sha256") != entry.get("content_sha256")
                or profile.get("evidence_state") != "observed"
                or profile.get("subject_kind") != "object_or_product"
                or profile.get("view_kind") not in expected_affordances
                or profile.get("affordances") != [expected_affordances.get(profile.get("view_kind"))]
                or not self._doc270_same_digest_record(profile, "profile_digest")
            ):
                raise ValueError("doc270_ecommerce_activation_policy_invalid")
        expected_requirement_keys = {"output_index", "kind"}
        indexes = [item.get("output_index") for item in requirements if isinstance(item, dict)]
        if (
            len(indexes) != len(requirements)
            or any(set(item) != expected_requirement_keys for item in requirements if isinstance(item, dict))
            or any(not isinstance(index, int) or isinstance(index, bool) or index < 1 for index in indexes)
            or len(indexes) != len(set(indexes))
            or any(str(item.get("kind") or "") not in _DOC270_PHASE4_REQUIREMENT_KINDS for item in requirements)
        ):
            raise ValueError("doc270_ecommerce_activation_policy_invalid")
        payload = {
            "schema_version": "doc270_ecommerce_phase4_activation_policy_v1",
            "identity_digest": identity["identity_digest"],
            "capability": {
                **_DOC270_PHASE4_CAPABILITY_POLICY,
                "template_id": ECOMMERCE_TEMPLATE_ID,
                "enabled": bool(enabled),
            },
            "requirements": [dict(item) for item in requirements if isinstance(item, dict)],
            "evidence_profiles": [dict(item) for item in evidence_profiles if isinstance(item, dict)],
            "provenance": dict(provenance) if isinstance(provenance, dict) else {},
        }
        if (
            len(payload["requirements"]) != len(requirements)
            or len(payload["evidence_profiles"]) != len(evidence_profiles)
            or set(payload["provenance"]) != {"authority", "version"}
            or not all(isinstance(payload["provenance"].get(key), str) and payload["provenance"][key].strip() for key in ("authority", "version"))
        ):
            raise ValueError("doc270_ecommerce_activation_policy_invalid")
        payload["policy_digest"] = self._doc270_digest(payload)
        existing = self._doc270_ecommerce_private_policy(project_id, identity)
        if existing is not None:
            if existing == payload:
                return
            raise ValueError("doc270_ecommerce_activation_policy_conflict")
        self.project_store.append_private_record(
            project_id,
            _DOC270_PHASE4_PRIVATE_POLICY_NAMESPACE,
            payload,
        )

    def _doc270_ecommerce_private_policy(
        self,
        project_id: str,
        identity: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        records = self.project_store.list_private_records(
            project_id, _DOC270_PHASE4_PRIVATE_POLICY_NAMESPACE
        )
        identity_digest = str(identity.get("identity_digest") or "")
        matches = [record for record in records if record.get("identity_digest") == identity_digest]
        if len(matches) != 1:
            return None
        policy = matches[0]
        if (
            set(policy) != {"schema_version", "identity_digest", "capability", "requirements", "evidence_profiles", "provenance", "policy_digest"}
            or policy.get("schema_version") != "doc270_ecommerce_phase4_activation_policy_v1"
            or policy.get("identity_digest") != identity_digest
            or not self._doc270_same_digest_record(policy, "policy_digest")
            or not self._doc270_ecommerce_view_activation_capability_valid(policy.get("capability"))
            or not isinstance(policy.get("requirements"), list)
            or not isinstance(policy.get("evidence_profiles"), list)
            or not isinstance(policy.get("provenance"), dict)
            or set(policy["provenance"]) != {"authority", "version"}
        ):
            return None
        return dict(policy)

    def _doc270_ecommerce_issue_policy_for_command(
        self,
        *,
        project_id: str,
        identity: dict[str, Any],
        command: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        """Analyze current admitted originals once for this new command identity."""

        try:
            project = self._require_project(project_id)
            snapshot = self._doc270_project_source_library(project)
            facts = dict(command["command_facts"])
            entries = [
                dict(entry)
                for entry in snapshot.get("entries", [])
                if isinstance(entry, dict) and entry.get("ecommerce_product_eligible") is True
            ]
            analysis_entries = self._doc270_ecommerce_analysis_entries(
                project_id=project_id,
                entries=entries,
            )
            if analysis_entries is None:
                # The admitted original no longer matches its durable file,
                # role, channel, or SHA facts. That is a material input issue,
                # not an analyzer outage.
                return None, "source_input_invalid"
            issued = self.ecommerce_view_activation_issuer.issue(
                project_id=project_id,
                expected_output_count=int(facts.get("requested_output_count") or 0),
                entries=analysis_entries,
            )
            if not isinstance(issued, dict):
                return None, "source_analysis_unavailable"
            outcome = str(issued.get("outcome") or "")
            if outcome == "source_analysis_unavailable":
                return None, outcome
            if outcome != "ready":
                return None, "source_analysis_invalid"
            candidate = {
                "requirements": list(issued.get("requirements") or []),
                "evidence_profiles": list(issued.get("evidence_profiles") or []),
                "provenance": issued.get("provenance"),
            }
            return (
                candidate,
                "ready" if issued.get("analysis_complete") is True else "source_analysis_incomplete",
            )
        except (KeyError, OSError, TypeError, ValueError):
            return None, "source_analysis_unavailable"

    def _doc270_ecommerce_private_command(
        self,
        project_id: str,
        identity: dict[str, Any],
    ) -> dict[str, Any] | None:
        identity_digest = str(identity.get("identity_digest") or "")
        records = self.project_store.list_private_records(
            project_id, _DOC270_PHASE4_PRIVATE_COMMAND_NAMESPACE
        )
        matches = [record for record in records if record.get("identity_digest") == identity_digest]
        if len(matches) != 1:
            return None
        command = matches[0]
        if (
            set(command) != {"schema_version", "identity_digest", "command_facts_digest", "command_facts", "identity"}
            or command.get("schema_version") != "doc270_ecommerce_phase4_command_facts_v1"
            or command.get("identity") != identity
            or not isinstance(command.get("command_facts"), dict)
        ):
            return None
        facts = dict(command["command_facts"])
        if command.get("command_facts_digest") != self._doc270_digest(facts):
            return None
        return dict(command)

    def _doc270_ecommerce_private_entry(
        self,
        project_id: str,
        identity: dict[str, Any],
    ) -> dict[str, Any] | None:
        records = self.project_store.list_private_records(
            project_id, _DOC270_PHASE4_PRIVATE_ENTRY_NAMESPACE
        )
        identity_digest = str(identity.get("identity_digest") or "")
        matches = [record for record in records if record.get("identity_digest") == identity_digest]
        if len(matches) != 1:
            return None
        entry = matches[0].get("entry")
        return dict(entry) if isinstance(entry, dict) else None

    def _doc270_ecommerce_private_decision_exists(
        self,
        project_id: str,
        identity: dict[str, Any],
    ) -> bool:
        identity_digest = str(identity.get("identity_digest") or "")
        return any(
            record.get("identity_digest") == identity_digest
            for record in self.project_store.list_private_records(
                project_id, _DOC270_PHASE4_PRIVATE_DECISION_NAMESPACE
            )
        )

    def _issue_doc270_ecommerce_phase4_registry_entry(
        self,
        *,
        project_id: str,
        identity: dict[str, Any],
        command: dict[str, Any],
        policy: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Resolve registered hard requirements against fresh verified bytes."""

        project = self._require_project(project_id)
        snapshot = self._doc270_project_source_library(project)
        facts = dict(command["command_facts"])
        expected_count = int(facts.get("requested_output_count") or 0)
        if expected_count < 1:
            return None
        requirements = list(policy["requirements"])
        if len(requirements) != expected_count:
            return None
        indexes = [item.get("output_index") for item in requirements if isinstance(item, dict)]
        if set(indexes) != set(range(1, expected_count + 1)) or len(indexes) != expected_count:
            return None
        command_handle = {
            "schema_version": "doc270_shadow_command_handle_v1",
            "authority": "v3_server_shadow_command_handle",
            "command_id": f"server-command-{project_id}",
            "plan_id": f"server-plan-{project_id}",
            "plan_version": 1,
        }
        command_handle["command_binding_digest"] = doc270_canonical_digest(command_handle)
        evidence_by_reference = {
            str(item.get("reference_id") or ""): dict(item)
            for item in policy["evidence_profiles"]
            if isinstance(item, dict) and str(item.get("reference_id") or "").strip()
        }
        resolved: list[dict[str, Any]] = []
        for requirement_spec in sorted(requirements, key=lambda item: int(item["output_index"])):
            if not isinstance(requirement_spec, dict):
                return None
            kind = str(requirement_spec.get("kind") or "")
            if kind not in _DOC270_PHASE4_REQUIREMENT_KINDS:
                return None
            requirement = {
                "schema_version": "doc270_reference_requirement_v1",
                "issuer": dict(_DOC270_PHASE4_REQUIREMENT_ISSUER),
                "project_id": project_id,
                "command_plan_binding": command_handle,
                "output_index": int(requirement_spec["output_index"]),
                "output_identity": f"ecommerce-output-{int(requirement_spec['output_index'])}",
                "requirement_nonce": stable_id(
                    "doc270_ecommerce_requirement", identity["identity_digest"], requirement_spec["output_index"], kind
                ),
                "source_library_snapshot_digest": snapshot["snapshot_digest"],
                "template_id": ECOMMERCE_TEMPLATE_ID,
                "original_source_channel": "project_uploaded_original",
                "kind": kind,
                "strength": "hard",
                "maximum_sources": 1,
            }
            requirement["requirement_digest"] = doc270_canonical_digest(requirement)
            plan_binding = {
                "project_id": project_id,
                "command_plan_binding": command_handle,
                "output_index": requirement["output_index"],
                "output_identity": requirement["output_identity"],
                "requirement_nonce": requirement["requirement_nonce"],
                "requirement_digest": requirement["requirement_digest"],
                "source_library_snapshot_digest": snapshot["snapshot_digest"],
                "issuer": dict(_DOC270_PHASE4_REQUIREMENT_ISSUER),
            }
            shadow = resolve_doc270_shadow_reference_requirements(
                project_id=project_id,
                command_plan_binding=command_handle,
                trusted_project_lookup=lambda identifier: self._require_project(identifier),
                upload_lookup=self.product_service.get_uploaded_asset,
                trusted_requirement_lookup=lambda _handle, value=requirement: dict(value),
                trusted_plan_binding_lookup=lambda _handle, value=plan_binding: dict(value),
                evidence_lookup=lambda entry: dict(evidence_by_reference[entry["reference_id"]])
                if entry.get("reference_id") in evidence_by_reference
                else None,
                trusted_capability_lookup=lambda name: {
                    "requirement_issuer": dict(_DOC270_PHASE4_REQUIREMENT_ISSUER),
                    "image_evidence_analyzer": dict(_DOC270_PHASE4_ANALYZER),
                    f"template:{ECOMMERCE_TEMPLATE_ID}": {"shadow_enabled": True},
                }.get(name),
            )
            if shadow.get("state") != "resolved" or len(shadow.get("matched_references") or []) != 1:
                return None
            match = dict(shadow["matched_references"][0])
            profile = evidence_by_reference.get(str(match.get("reference_id") or ""))
            if not isinstance(profile, dict) or profile.get("profile_digest") != match.get("profile_digest"):
                return None
            receipt = {
                "schema_version": "doc270_reference_resolution_receipt_v1",
                "issuer": "v3_doc270_shadow_matcher",
                "project_id": project_id,
                "command_identity": dict(identity),
                "command_plan_binding_digest": identity["command_plan_binding_digest"],
                "output_index": requirement["output_index"],
                "output_identity": requirement["output_identity"],
                "requirement_nonce": requirement["requirement_nonce"],
                "requirement_digest": requirement["requirement_digest"],
                "source_library_snapshot_digest": snapshot["snapshot_digest"],
                "state": "resolved",
                "maximum_sources": 1,
                "matched_references": [match],
                "evidence_profile_digests": [match["profile_digest"]],
                "requirement_kind": kind,
                "evidence_profile": {
                    key: profile[key]
                    for key in ("subject_kind", "view_kind", "affordances")
                },
                "shadow_only": True,
            }
            receipt["receipt_digest"] = self._doc270_digest(receipt)
            resolved.append(receipt)
        entry = {
            **_DOC270_PHASE4_REGISTRY_POLICY,
            "project_id": project_id,
            "template_id": ECOMMERCE_TEMPLATE_ID,
            "command_identity": dict(identity),
            "source_library_snapshot_digest": snapshot["snapshot_digest"],
            "receipts": resolved,
        }
        entry["registry_entry_digest"] = self._doc270_digest(entry)
        return entry

    @staticmethod
    def _doc270_digest(value: Any) -> str:
        return hashlib.sha256(
            json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @classmethod
    def _doc270_same_digest_record(cls, value: dict[str, Any], field: str) -> bool:
        digest = str(value.get(field) or "").strip().lower()
        return len(digest) == 64 and digest == cls._doc270_digest(
            {key: item for key, item in value.items() if key != field}
        )

    def _doc270_general_command_identity_valid(
        self,
        identity: Any,
        *,
        project_id: str,
        template_id: str,
    ) -> bool:
        if not isinstance(identity, dict) or set(identity) != _DOC270_PHASE3_COMMAND_IDENTITY_KEYS:
            return False
        if (
            identity.get("schema_version") != _DOC270_PHASE3_COMMAND_IDENTITY_POLICY["schema_version"]
            or identity.get("issuer") != _DOC270_PHASE3_COMMAND_IDENTITY_POLICY["issuer"]
            or identity.get("capability_id") != _DOC270_PHASE3_COMMAND_IDENTITY_POLICY["capability_id"]
            or identity.get("project_id") != project_id
            or identity.get("template_id") != template_id
        ):
            return False
        if not all(
            isinstance(identity.get(key), str) and str(identity[key]).strip()
            for key in ("capability_version", "command_id", "command_plan_binding_digest", "coalescing_nonce")
        ):
            return False
        return self._doc270_same_digest_record(identity, "identity_digest")

    @staticmethod
    def _doc270_general_activation_capability_valid(
        capability: Any,
        *,
        template_id: str,
    ) -> bool:
        expected = _DOC270_PHASE3_ACTIVATION_CAPABILITY_POLICY
        return (
            isinstance(capability, dict)
            and set(capability) == {
                "schema_version", "issuer", "capability_id", "capability_version", "template_id", "enabled"
            }
            and capability.get("schema_version") == expected["schema_version"]
            and capability.get("issuer") == expected["issuer"]
            and capability.get("capability_id") == expected["capability_id"]
            and capability.get("capability_version") == expected["capability_version"]
            and capability.get("template_id") == template_id
            and capability.get("enabled") is True
        )

    def _doc270_general_existing_command(
        self,
        project: ProjectRecord,
        identity: dict[str, Any],
    ) -> ProductJobStatus | None:
        for job_id in reversed(project.job_ids):
            record = self.product_service.get_job_record(job_id)
            if record is None:
                continue
            metadata = dict(record.request.metadata or {})
            if metadata.get("doc270_general_command_identity") == identity:
                return self.product_service.get_job(job_id)
        return None

    def _doc270_general_activation_decision(
        self,
        project: ProjectRecord,
        *,
        template_id: str,
        identity: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify a private registered Phase 2 receipt for one new General command."""

        try:
            entry = self._doc270_general_phase2_receipt_registry_lookup(
                project_id=project.project_id,
                command_identity=dict(identity),
            )
        except Exception:
            entry = None
        if not isinstance(entry, dict):
            return {"state": "receipt_invalid"}
        entry_keys = {
            "issuer", "schema_version", "version", "capability_id", "capability_version",
            "command_identity", "output_identity", "receipt", "receipt_digest", "registry_entry_digest",
        }
        if (
            identity.get("capability_version") != _DOC270_PHASE3_CAPABILITY_VERSION
            or
            set(entry) != entry_keys
            or entry.get("issuer") != _DOC270_PHASE3_REGISTRY_POLICY["issuer"]
            or entry.get("schema_version") != _DOC270_PHASE3_REGISTRY_POLICY["schema_version"]
            or entry.get("capability_id") != _DOC270_PHASE3_REGISTRY_POLICY["capability_id"]
            or entry.get("version") != _DOC270_PHASE3_REGISTRY_POLICY["version"]
            or entry.get("capability_version") != _DOC270_PHASE3_REGISTRY_POLICY["capability_version"]
            or entry.get("capability_version") != identity.get("capability_version")
            or not isinstance(entry.get("version"), str)
            or not str(entry.get("version") or "").strip()
            or not isinstance(entry.get("capability_version"), str)
            or not str(entry.get("capability_version") or "").strip()
            or entry.get("command_identity") != identity
            or not self._doc270_same_digest_record(entry, "registry_entry_digest")
        ):
            return {"state": "receipt_invalid"}
        receipt = entry.get("receipt")
        if not isinstance(receipt, dict) or entry.get("receipt_digest") != receipt.get("receipt_digest"):
            return {"state": "receipt_invalid"}
        if not entry.get("output_identity") or entry.get("output_identity") != receipt.get("output_identity"):
            return {"state": "receipt_invalid"}
        if not self._doc270_same_digest_record(receipt, "receipt_digest"):
            return {"state": "receipt_invalid"}
        state = str(receipt.get("state") or "").strip()
        if state in {"no_reference", "optional_uncertain", "insufficient_evidence", "invalid", "not_applicable"}:
            return {"state": "prompt_only"}
        if state != "resolved":
            return {"state": "receipt_invalid"}
        receipt_keys = {
            "schema_version", "project_id", "command_plan_binding_digest", "command_identity",
            "output_index", "output_identity", "requirement_nonce", "requirement_digest",
            "source_library_snapshot_digest", "source_resolver", "state", "matched_references",
            "evidence_profile_digests", "shadow_only", "receipt_digest",
        }
        if (
            set(receipt) != receipt_keys
            or receipt.get("schema_version") != "doc270_reference_resolution_receipt_v1"
            or receipt.get("project_id") != project.project_id
            or receipt.get("command_identity") != identity
            or receipt.get("command_plan_binding_digest") != identity.get("command_plan_binding_digest")
            or receipt.get("shadow_only") is not True
            or not isinstance(receipt.get("output_index"), int)
            or int(receipt["output_index"]) < 1
            or not all(isinstance(receipt.get(key), str) and str(receipt[key]).strip() for key in (
                "output_identity", "requirement_nonce", "requirement_digest", "source_library_snapshot_digest"
            ))
            or receipt.get("source_resolver") != {"authority": "v3_doc270_shadow_matcher", "version": "doc270_shadow_matcher_v1"}
        ):
            return {"state": "receipt_invalid"}
        try:
            snapshot = self._doc270_project_source_library(project)
        except Exception:
            return {"state": "receipt_invalid"}
        if receipt.get("source_library_snapshot_digest") != snapshot.get("snapshot_digest"):
            return {"state": "receipt_invalid"}
        references = receipt.get("matched_references")
        profiles = receipt.get("evidence_profile_digests")
        if not isinstance(references, list) or not references or not isinstance(profiles, list) or len(references) != len(profiles):
            return {"state": "receipt_invalid"}
        entries = {
            str(item.get("reference_id") or ""): item
            for item in snapshot.get("entries", [])
            if isinstance(item, dict)
        }
        selected: list[dict[str, str]] = []
        seen_references: set[str] = set()
        seen_assets: set[str] = set()
        for item, profile_digest in zip(references, profiles, strict=True):
            if not isinstance(item, dict) or set(item) != {"reference_id", "asset_id", "content_sha256", "profile_digest"}:
                return {"state": "receipt_invalid"}
            reference_id = str(item.get("reference_id") or "")
            asset_id = str(item.get("asset_id") or "")
            content_sha256 = str(item.get("content_sha256") or "").lower()
            item_profile = str(item.get("profile_digest") or "")
            entry_item = entries.get(reference_id)
            if (
                not reference_id or not asset_id or len(content_sha256) != 64 or not item_profile
                or item_profile != profile_digest or reference_id in seen_references or asset_id in seen_assets
                or not isinstance(entry_item, dict)
                or entry_item.get("asset_id") != asset_id
                or entry_item.get("content_sha256") != content_sha256
                or entry_item.get("availability_state") != "ready_verified"
                or entry_item.get("automatic_use_eligible") is not True
            ):
                return {"state": "receipt_invalid"}
            seen_references.add(reference_id)
            seen_assets.add(asset_id)
            selected.append(
                {
                    "reference_id": reference_id,
                    "asset_id": asset_id,
                    "content_sha256": content_sha256,
                    "source_receipt_digest": str(receipt["receipt_digest"]),
                }
            )
        return {
            "state": "activated_resolved",
            "source_receipt_digest": str(receipt["receipt_digest"]),
            "source_library_snapshot_digest": str(snapshot["snapshot_digest"]),
            "selected_original_reference_ids": [item["reference_id"] for item in selected],
            "selected_original_asset_ids": [item["asset_id"] for item in selected],
            "maximum_sources": len(selected),
            "projection": {
                "schema_version": "doc270_general_original_source_projection_v1",
                "state": "activated_resolved",
                "source_receipt_digest": str(receipt["receipt_digest"]),
                "source_library_snapshot_digest": str(snapshot["snapshot_digest"]),
                "sources": selected,
            },
        }

    def _doc281_general_registered_receipt_decision(
        self,
        project: ProjectRecord,
        *,
        identity: dict[str, Any],
        entry: Any,
    ) -> dict[str, Any]:
        """Consume only the named Doc281 private registry response.

        The registry owns the Brain selection receipt. This boundary only
        re-reads the current project snapshot and freezes the provider
        projection; it never accepts browser selection metadata.
        """

        if not isinstance(entry, dict) or set(entry) != {"protocol", "schema_version", "command_identity", "receipt"}:
            return {"state": "receipt_invalid"}
        if (
            entry.get("protocol") != "doc281_general_source_registry_v2"
            or entry.get("schema_version") != "doc281_general_registered_receipt_v2"
            or entry.get("command_identity") != identity
            or not isinstance(entry.get("receipt"), dict)
        ):
            return {"state": "receipt_invalid"}
        receipt = dict(entry["receipt"])
        if not self._doc270_same_digest_record(receipt, "receipt_digest"):
            return {"state": "receipt_invalid"}
        selection_digest = str(receipt.get("selection_digest") or "").lower()
        # A digest-shaped placeholder is not a Brain-issued source-selection
        # binding. The registry never emits a degenerate digest.
        if len(selection_digest) != 64 or len(set(selection_digest)) == 1:
            return {"state": "receipt_invalid"}
        state = str(receipt.get("state") or "").strip()
        if state == "prompt_only":
            return {"state": "prompt_only"}
        if state != "resolved":
            return {"state": "receipt_invalid"}
        try:
            snapshot = self._doc270_project_source_library(project)
        except Exception:
            return {"state": "receipt_invalid"}
        if (
            receipt.get("project_id") != project.project_id
            or receipt.get("command_plan_binding_digest") != identity.get("plan_binding_digest", identity.get("command_plan_binding_digest"))
            or receipt.get("source_library_snapshot_digest") != snapshot.get("snapshot_digest")
        ):
            return {"state": "receipt_invalid"}
        raw_matches = receipt.get("matched_references")
        if not isinstance(raw_matches, list) or not raw_matches or len(raw_matches) > 4:
            return {"state": "receipt_invalid"}
        entries = {
            str(item.get("reference_id") or ""): item
            for item in snapshot.get("entries", [])
            if isinstance(item, dict)
        }
        selected: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in raw_matches:
            if not isinstance(item, dict):
                return {"state": "receipt_invalid"}
            reference_id = str(item.get("reference_id") or "")
            asset_id = str(item.get("asset_id") or "")
            sha = str(item.get("content_sha256") or "").lower()
            entry_item = entries.get(reference_id)
            if (
                not reference_id or reference_id in seen or not entry_item
                or entry_item.get("asset_id") != asset_id
                or entry_item.get("content_sha256") != sha
                or entry_item.get("automatic_use_eligible") is not True
                or entry_item.get("availability_state") != "ready_verified"
            ):
                return {"state": "receipt_invalid"}
            seen.add(reference_id)
            selected.append({
                "reference_id": reference_id,
                "asset_id": asset_id,
                "content_sha256": sha,
                "source_receipt_digest": str(receipt["receipt_digest"]),
            })
        output_bindings = receipt.get("output_bindings")
        requested_output_count = identity.get("requested_output_count")
        output_plan_digest = str(identity.get("output_plan_digest") or "")
        frozen_output_bindings: list[dict[str, Any]] = []
        output_selected_keys: set[tuple[str, str]] = set()
        if requested_output_count is not None or output_plan_digest:
            if (
                not isinstance(requested_output_count, int) or isinstance(requested_output_count, bool)
                or not 1 <= requested_output_count <= 8 or len(output_plan_digest) != 64
                or not isinstance(output_bindings, list) or len(output_bindings) != requested_output_count
            ):
                return {"state": "receipt_invalid"}
            indexes: set[int] = set()
            for binding in output_bindings:
                if not isinstance(binding, dict) or set(binding) != {
                    "output_index", "output_nonce", "matched_references", "output_binding_digest",
                }:
                    return {"state": "receipt_invalid"}
                output_index = binding.get("output_index")
                output_nonce = str(binding.get("output_nonce") or "")
                binding_matches = binding.get("matched_references")
                if (
                    not isinstance(output_index, int) or output_index < 1 or output_index > requested_output_count
                    or output_index in indexes or len(output_nonce) != 64
                    or not isinstance(binding_matches, list)
                    or not binding_matches
                    or len(binding_matches) > 4
                    or not self._doc270_same_digest_record(
                        {
                            "project_id": project.project_id,
                            "command_plan_binding_digest": identity["plan_binding_digest"],
                            "selection_digest": receipt["selection_digest"],
                            "source_library_snapshot_digest": receipt["source_library_snapshot_digest"],
                            "output_index": output_index,
                            "output_nonce": output_nonce,
                            "matched_references": binding_matches,
                            "output_binding_digest": binding.get("output_binding_digest"),
                        },
                        "output_binding_digest",
                    )
                ):
                    return {"state": "receipt_invalid"}
                binding_keys: set[tuple[str, str]] = set()
                for source in binding_matches:
                    if not isinstance(source, dict):
                        return {"state": "receipt_invalid"}
                    source_reference_id = str(source.get("reference_id") or "")
                    source_asset_id = str(source.get("asset_id") or "")
                    source_sha = str(source.get("content_sha256") or "").lower()
                    source_entry = entries.get(source_reference_id)
                    source_key = (source_reference_id, source_asset_id)
                    if (
                        not source_reference_id
                        or source_key in binding_keys
                        or not isinstance(source_entry, dict)
                        or source_entry.get("asset_id") != source_asset_id
                        or source_entry.get("content_sha256") != source_sha
                        or source_entry.get("automatic_use_eligible") is not True
                        or source_entry.get("availability_state") != "ready_verified"
                    ):
                        return {"state": "receipt_invalid"}
                    binding_keys.add(source_key)
                    output_selected_keys.add(source_key)
                indexes.add(output_index)
                frozen_output_bindings.append({
                    "output_index": output_index,
                    "output_nonce": output_nonce,
                    "output_binding_digest": str(binding["output_binding_digest"]),
                })
            if indexes != set(range(1, requested_output_count + 1)):
                return {"state": "receipt_invalid"}
            if output_selected_keys != {(item["reference_id"], item["asset_id"]) for item in selected}:
                return {"state": "receipt_invalid"}
        return {
            "state": "activated_resolved",
            "source_receipt_digest": str(receipt["receipt_digest"]),
            "source_library_snapshot_digest": str(snapshot["snapshot_digest"]),
            "selected_original_reference_ids": [item["reference_id"] for item in selected],
            "selected_original_asset_ids": [item["asset_id"] for item in selected],
            "maximum_sources": len(selected),
            "output_source_bindings": frozen_output_bindings,
            "projection": {
                "schema_version": "doc270_general_original_source_projection_v1",
                "state": "activated_resolved",
                "source_receipt_digest": str(receipt["receipt_digest"]),
                "source_library_snapshot_digest": str(snapshot["snapshot_digest"]),
                "sources": selected,
            },
        }

    @staticmethod
    def _doc270_ecommerce_view_activation_capability_valid(capability: Any) -> bool:
        expected = _DOC270_PHASE4_CAPABILITY_POLICY
        return (
            isinstance(capability, dict)
            and set(capability) == {
                "schema_version", "issuer", "capability_id", "capability_version", "template_id", "enabled"
            }
            and all(capability.get(key) == value for key, value in expected.items())
            and capability.get("template_id") == ECOMMERCE_TEMPLATE_ID
            and capability.get("enabled") is True
        )

    def _doc270_ecommerce_command_identity_valid(
        self,
        identity: Any,
        *,
        project_id: str,
    ) -> bool:
        policy = _DOC270_PHASE4_COMMAND_IDENTITY_POLICY
        return (
            isinstance(identity, dict)
            and set(identity) == _DOC270_PHASE4_COMMAND_IDENTITY_KEYS
            and all(identity.get(key) == value for key, value in policy.items())
            and identity.get("project_id") == project_id
            and identity.get("template_id") == ECOMMERCE_TEMPLATE_ID
            and all(
                isinstance(identity.get(key), str) and str(identity[key]).strip()
                for key in ("command_id", "command_plan_binding_digest", "coalescing_nonce")
            )
            and self._doc270_same_digest_record(identity, "identity_digest")
        )

    def _doc270_ecommerce_existing_command(
        self,
        project: ProjectRecord,
        identity: dict[str, Any],
    ) -> ProductJobStatus | None:
        for job_id in reversed(project.job_ids):
            record = self.product_service.get_job_record(job_id)
            if record is None:
                continue
            metadata = dict(record.request.metadata or {})
            if metadata.get("doc270_ecommerce_command_identity") == identity:
                return self.product_service.get_job(job_id)
        return None

    def _doc270_ecommerce_view_activation_decision(
        self,
        *,
        project_id: str,
        identity: dict[str, Any],
        expected_output_count: int,
        canonical_product_asset_ids: list[str],
    ) -> dict[str, Any]:
        """Verify E31's private view receipts before any E-Commerce Job exists."""

        try:
            project = self._require_project(project_id)
            entry = self._doc270_ecommerce_phase2_receipt_registry_lookup(
                project_id=project.project_id,
                command_identity=dict(identity),
            )
            snapshot = self._doc270_project_source_library(project)
        except Exception:
            return {"state": "needs_input"}
        if isinstance(entry, dict) and entry.get("state") == "source_analysis_unavailable":
            return {"state": "source_analysis_unavailable"}
        if not isinstance(entry, dict) or not isinstance(snapshot, dict):
            return {"state": "needs_input"}
        if (
            set(entry) != {
                "schema_version", "issuer", "capability_id", "capability_version", "project_id",
                "template_id", "command_identity", "source_library_snapshot_digest", "receipts",
                "registry_entry_digest",
            }
            or any(entry.get(key) != value for key, value in _DOC270_PHASE4_REGISTRY_POLICY.items())
            or entry.get("project_id") != project.project_id
            or entry.get("template_id") != ECOMMERCE_TEMPLATE_ID
            or entry.get("command_identity") != identity
            or entry.get("source_library_snapshot_digest") != snapshot.get("snapshot_digest")
            or not self._doc270_same_digest_record(entry, "registry_entry_digest")
        ):
            return {"state": "needs_input"}
        receipts = entry.get("receipts")
        if not isinstance(receipts, list) or len(receipts) != expected_output_count:
            return {"state": "needs_input"}
        entries = {
            str(item.get("reference_id") or ""): item
            for item in snapshot.get("entries", [])
            if isinstance(item, dict)
        }
        current_admitted_ids = [
            str(item).strip() for item in canonical_product_asset_ids if str(item).strip()
        ]
        current_eligible_ids = [
            str(item.get("asset_id") or "").strip()
            for item in snapshot.get("entries", [])
            if isinstance(item, dict) and item.get("ecommerce_product_eligible") is True
        ]
        if (
            not current_admitted_ids
            or len(current_admitted_ids) != len(set(current_admitted_ids))
            or current_eligible_ids != current_admitted_ids
        ):
            return {"state": "needs_input"}
        resolved: list[dict[str, Any]] = []
        verified_receipts: list[dict[str, Any]] = []
        indexes: set[int] = set()
        for receipt in receipts:
            if not isinstance(receipt, dict) or set(receipt) != _DOC270_PHASE4_RECEIPT_KEYS:
                return {"state": "needs_input"}
            if (
                receipt.get("schema_version") != "doc270_reference_resolution_receipt_v1"
                or receipt.get("issuer") != "v3_doc270_shadow_matcher"
                or receipt.get("project_id") != project.project_id
                or receipt.get("command_identity") != identity
                or receipt.get("command_plan_binding_digest") != identity.get("command_plan_binding_digest")
                or receipt.get("source_library_snapshot_digest") != snapshot.get("snapshot_digest")
                or receipt.get("state") != "resolved"
                or receipt.get("maximum_sources") != 1
                or receipt.get("shadow_only") is not True
                or not self._doc270_same_digest_record(receipt, "receipt_digest")
            ):
                return {"state": "needs_input"}
            output_index = receipt.get("output_index")
            if (
                not isinstance(output_index, int)
                or isinstance(output_index, bool)
                or output_index < 1
                or output_index > expected_output_count
                or output_index in indexes
                or not all(
                    isinstance(receipt.get(key), str) and str(receipt[key]).strip()
                    for key in ("output_identity", "requirement_nonce", "requirement_digest", "requirement_kind")
                )
            ):
                return {"state": "needs_input"}
            evidence = receipt.get("evidence_profile")
            profiles = receipt.get("evidence_profile_digests")
            matches = receipt.get("matched_references")
            if (
                not isinstance(evidence, dict)
                or set(evidence) not in (
                    {"subject_kind", "view_kind", "affordances"},
                    {"subject_kind", "view_kind", "affordances", "semantic_domain"},
                )
                or evidence.get("subject_kind") != "object_or_product"
                or not isinstance(evidence.get("view_kind"), str)
                or not isinstance(evidence.get("affordances"), list)
                or not evidence["affordances"]
                or (
                    "semantic_domain" in evidence
                    and (not isinstance(evidence.get("semantic_domain"), str) or not evidence["semantic_domain"].strip())
                )
                or not isinstance(profiles, list)
                or len(profiles) != 1
                or not isinstance(matches, list)
                or len(matches) != 1
            ):
                return {"state": "needs_input"}
            match = matches[0]
            if not isinstance(match, dict) or set(match) != {
                "reference_id", "asset_id", "content_sha256", "profile_digest"
            }:
                return {"state": "needs_input"}
            reference_id = str(match.get("reference_id") or "")
            asset_id = str(match.get("asset_id") or "")
            digest = str(match.get("content_sha256") or "").lower()
            profile_digest = str(match.get("profile_digest") or "")
            source = entries.get(reference_id)
            if (
                not reference_id
                or not asset_id
                or len(digest) != 64
                or profile_digest != profiles[0]
                or not isinstance(source, dict)
                or source.get("asset_id") != asset_id
                or source.get("content_sha256") != digest
                or source.get("availability_state") != "ready_verified"
                or source.get("ecommerce_product_eligible") is not True
                or source.get("source_type") != "uploaded"
                or source.get("use_policy") != "product"
                or source.get("role") != "product_reference"
                or source.get("reference_channel") != "product_truth"
                or asset_id not in current_admitted_ids
            ):
                return {"state": "needs_input"}
            indexes.add(output_index)
            verified_receipts.append(dict(receipt))
            resolved.append(
                {
                    "output_index": output_index,
                    "selected_product_asset_id": asset_id,
                    "source_receipt_digest": receipt["receipt_digest"],
                    "source_library_snapshot_digest": snapshot["snapshot_digest"],
                }
            )
        if indexes != set(range(1, expected_output_count + 1)):
            return {"state": "needs_input"}
        return {
            "state": "activated_resolved",
            "receipts": sorted(verified_receipts, key=lambda item: item["output_index"]),
            "selection": sorted(resolved, key=lambda item: item["output_index"]),
        }

    @staticmethod
    def _doc270_ecommerce_needs_input_status(project_id: str) -> ProductJobStatus:
        return ProductJobStatus(
            job_id="",
            status=ProductJobStatusValue.BLOCKED,
            api_namespace=API_NAMESPACE,
            ui_entry_route=f"{API_NAMESPACE}/projects/{project_id}",
            metadata={
                "current_operation": {
                    "state": "needs_input",
                    "terminal": True,
                    "pending": False,
                    "next_actions": [{"id": "review_product_inputs"}],
                }
            },
        )

    @staticmethod
    def _doc270_ecommerce_needs_input_operation() -> dict[str, Any]:
        return {
            "state": "needs_input",
            "terminal": True,
            "pending": False,
            "next_actions": [{"id": "review_product_inputs"}],
        }

    @staticmethod
    def _doc270_ecommerce_source_analysis_unavailable_operation() -> dict[str, Any]:
        return {
            "state": "source_analysis_unavailable",
            "terminal": True,
            "pending": False,
            "next_actions": [{"id": "retry_source_analysis"}],
        }

    def _set_doc270_ecommerce_needs_input_operation(self, project: ProjectRecord) -> None:
        metadata = dict(project.metadata or {})
        metadata[_DOC270_PHASE4_CURRENT_OPERATION_KEY] = {
            "operation": self._doc270_ecommerce_needs_input_operation(),
            "project_job_count": len(project.job_ids),
        }
        project.metadata = metadata
        project.updated_at = _utc_now_iso()
        self.project_store.save_project(project)

    def _set_doc270_ecommerce_source_analysis_unavailable_operation(self, project: ProjectRecord) -> None:
        metadata = dict(project.metadata or {})
        metadata[_DOC270_PHASE4_CURRENT_OPERATION_KEY] = {
            "operation": self._doc270_ecommerce_source_analysis_unavailable_operation(),
            "project_job_count": len(project.job_ids),
        }
        project.metadata = metadata
        project.updated_at = _utc_now_iso()
        self.project_store.save_project(project)

    def _clear_doc270_ecommerce_needs_input_operation(self, project: ProjectRecord) -> None:
        metadata = dict(project.metadata or {})
        if _DOC270_PHASE4_CURRENT_OPERATION_KEY not in metadata:
            return
        metadata.pop(_DOC270_PHASE4_CURRENT_OPERATION_KEY, None)
        project.metadata = metadata
        project.updated_at = _utc_now_iso()
        self.project_store.save_project(project)

    def list_projects(self, limit: int = 20, owner_user_id: int | None = None) -> ProjectListResponse:
        projects = [
            project
            for project in self.project_store.list_projects(limit=100)
            if project.status != ProjectStatus.ARCHIVED and self._project_visible_to_owner(project, owner_user_id)
        ][: max(1, min(int(limit or 20), 100))]
        for project in projects:
            self._reconcile_project_outputs(project)
        summaries = [self._memory_summary(project) for project in projects]
        return ProjectListResponse(
            api_namespace=API_NAMESPACE,
            route=f"{API_NAMESPACE}/projects",
            total=len(summaries),
            limit=max(1, min(int(limit or 20), 100)),
            projects=summaries,
            templates=self.template_cards(),
            metadata=self._metadata(),
        )

    def list_project_outputs(
        self,
        limit: int = 60,
        owner_user_id: int | None = None,
        compact: bool = False,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        bounded_limit = max(1, min(int(limit or 60), 200))
        items: list[dict[str, Any]] = []
        if project_id:
            project = self._require_project(project_id)
            review_items: list[dict[str, Any]] = []
            if project.status != ProjectStatus.ARCHIVED and self._project_visible_to_owner(project, owner_user_id):
                self._reconcile_project_outputs(project)
                items = self._project_output_items(
                    project,
                    limit=bounded_limit,
                    owner_user_id=owner_user_id,
                    compact=compact,
                )
                review_items = self._project_review_output_items(
                    project,
                    limit=bounded_limit,
                    owner_user_id=owner_user_id,
                    compact=compact,
                )
            items = sorted(items, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:bounded_limit]
            review_items = sorted(review_items, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:bounded_limit]
            return {
                "api_namespace": API_NAMESPACE,
                "route": f"{API_NAMESPACE}/project-outputs",
                "project_id": project_id,
                "total": len(items),
                "limit": bounded_limit,
                "items": items,
                "review_items": review_items,
                "metadata": {**self._metadata(), "compact": bool(compact), "project_scoped": True},
            }
        project_scan_limit = max(12, min(100, bounded_limit * 2))
        review_items = []
        for project in self.project_store.list_projects(limit=project_scan_limit):
            if project.status == ProjectStatus.ARCHIVED:
                continue
            if not self._project_visible_to_owner(project, owner_user_id):
                continue
            self._reconcile_project_outputs(project)
            items.extend(
                self._project_output_items(
                    project,
                    limit=bounded_limit,
                    owner_user_id=owner_user_id,
                    compact=compact,
                )
            )
            review_items.extend(
                self._project_review_output_items(
                    project,
                    limit=bounded_limit,
                    owner_user_id=owner_user_id,
                    compact=compact,
                )
            )
        items = sorted(items, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:bounded_limit]
        review_items = sorted(review_items, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:bounded_limit]
        return {
            "api_namespace": API_NAMESPACE,
            "route": f"{API_NAMESPACE}/project-outputs",
            "total": len(items),
            "limit": bounded_limit,
            "items": items,
            "review_items": review_items,
            "metadata": {**self._metadata(), "compact": bool(compact)},
        }

    def create_project(self, request: CreateProjectRequest | dict[str, Any]) -> ProjectResponse:
        create_request = self._coerce_create_project_request(request)
        template_manifest = self._ensure_active_template(create_request.primary_template_id)
        now = _utc_now_iso()
        project_id = f"project_{uuid4().hex[:10]}"
        title = create_request.title or self._title_from_goal(create_request.user_goal)
        initial_asset_role = self._initial_uploaded_asset_role(
            template_id=template_manifest.template_id,
            user_goal=create_request.user_goal,
        )
        project = ProjectRecord(
            project_id=project_id,
            title=title,
            status=ProjectStatus.ACTIVE,
            primary_template_id=template_manifest.template_id,
            allowed_template_ids=[template_manifest.template_id],
            linked_brand_id=create_request.linked_brand_id,
            user_goal=create_request.user_goal,
            short_summary=self._short_text(create_request.user_goal, 72),
            uploaded_asset_refs=[
                {"asset_id": asset_id, "source": "project_create", "role": initial_asset_role}
                for asset_id in create_request.uploaded_asset_ids
            ],
            created_at=now,
            updated_at=now,
            metadata={
                **{
                    key: value
                    for key, value in dict(create_request.metadata or {}).items()
                    if not str(key).startswith("doc277_")
                },
                "source": PROJECT_API_SOURCE,
                "project_mode": True,
                "imports_v1_v2_runtime": False,
                "imports_lab_runtime": False,
                "template_manifest_id": template_manifest.template_id,
                "scenario_pack_id": template_manifest.scenario_pack_id,
            },
        )
        self.project_store.save_project(project)
        self._append_timeline(
            project.project_id,
            TimelineItemType.PROJECT_CREATED,
            "创建了项目",
            (
                "项目已准备好，可以上传商品图生成第一组电商套图。"
                if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID
                else "项目已准备好，可以冻结摄影专业套图并生成第一组照片。"
                if template_manifest.template_id == "photographer_template"
                else "项目已准备好，可以使用通用模板生成第一组创意图。"
            ),
            metadata={"template_id": template_manifest.template_id, "scenario_pack_id": template_manifest.scenario_pack_id},
        )
        project.latest_context = self._build_context(project)
        project.memory_summary = self._memory_summary(project)
        self.project_store.save_project(project)
        return self._project_response(project)

    def get_project(self, project_id: str) -> ProjectResponse:
        project = self._require_project(project_id)
        self._reconcile_project_outputs(project)
        self._ensure_project_product_reference_integrity(project)
        project.latest_context = self._build_context(project)
        project.memory_summary = self._memory_summary(project)
        self.project_store.save_project(project)
        return self._project_response(project)

    def begin_project_planning_operation(
        self,
        project_id: str,
        request: CreateProjectJobRequest | dict[str, Any],
    ) -> dict[str, Any]:
        """Persist one pre-Job planning operation before remote Brain work."""

        with self._doc277_planning_lock:
            project = self._require_project(project_id)
            existing = self._doc277_current_planning_operation(project)
            if existing is not None and existing["state"] == "planning":
                return existing

            job_request = self._coerce_create_project_job_request(request)
            template_manifest = self._ensure_active_template(job_request.template_id)
            metadata = {
                key: value
                for key, value in dict(job_request.metadata or {}).items()
                if not str(key).startswith("doc277_")
            }
            normalized_request = job_request.model_copy(update={"metadata": metadata})
            serialized_request = normalized_request.model_dump(mode="json", exclude_none=True)
            operation_id = stable_id(
                "doc277_project_planning",
                project.project_id,
                uuid4().hex,
            )
            request_digest = self._doc277_digest(
                {
                    "project_id": project.project_id,
                    "template_id": template_manifest.template_id,
                    "request": serialized_request,
                }
            )
            now = _utc_now_iso()
            public_operation = {
                "operation_id": operation_id,
                "state": "planning",
                "terminal": False,
                "pending": True,
                "next_actions": [],
            }
            self.project_store.append_private_record(
                project.project_id,
                _DOC277_PRIVATE_PLANNING_NAMESPACE,
                {
                    "schema_version": "doc277_project_planning_operation_v1",
                    "record_kind": "opened",
                    "identity_digest": self._doc277_digest(
                        {
                            "project_id": project.project_id,
                            "operation_id": operation_id,
                            "record_kind": "opened",
                        }
                    ),
                    "project_id": project.project_id,
                    "operation_id": operation_id,
                    "template_id": template_manifest.template_id,
                    "request_digest": request_digest,
                    "request": serialized_request,
                    "created_at": now,
                },
            )
            project.metadata = {
                **dict(project.metadata or {}),
                _DOC277_CURRENT_OPERATION_KEY: {
                    **public_operation,
                    "created_at": now,
                },
            }
            project.updated_at = now
            self.project_store.save_project(project)
            return public_operation

    def complete_project_planning_operation(
        self,
        project_id: str,
        operation_id: str,
        *,
        job_id: str,
    ) -> dict[str, Any]:
        """Close planning only after one actual Product Job has been persisted."""

        clean_operation_id = str(operation_id or "").strip()
        clean_job_id = str(job_id or "").strip()
        if not clean_job_id:
            raise ValueError("doc277_planning_completion_job_missing")
        with self._doc277_planning_lock:
            project = self._require_project(project_id)
            current = self._doc277_current_planning_operation(project)
            if current is None or current["state"] != "planning" or current["operation_id"] != clean_operation_id:
                raise ValueError("doc277_planning_operation_not_pending")
            now = _utc_now_iso()
            self.project_store.append_private_record(
                project.project_id,
                _DOC277_PRIVATE_PLANNING_NAMESPACE,
                {
                    "schema_version": "doc277_project_planning_operation_v1",
                    "record_kind": "completed",
                    "identity_digest": self._doc277_digest(
                        {
                            "project_id": project.project_id,
                            "operation_id": clean_operation_id,
                            "record_kind": "completed",
                            "job_id": clean_job_id,
                        }
                    ),
                    "project_id": project.project_id,
                    "operation_id": clean_operation_id,
                    "job_id": clean_job_id,
                    "created_at": now,
                },
            )
            metadata = dict(project.metadata or {})
            metadata.pop(_DOC277_CURRENT_OPERATION_KEY, None)
            project.metadata = metadata
            project.updated_at = now
            self.project_store.save_project(project)
            return {"operation_id": clean_operation_id, "job_id": clean_job_id}

    def fail_project_planning_operation(
        self,
        project_id: str,
        operation_id: str,
        *,
        failure_code: str,
        job_id: str | None = None,
        ecommerce_opaque_hold_response: bool = False,
    ) -> dict[str, Any]:
        """Persist a terminal planning closure without exposing internals."""

        clean_operation_id = str(operation_id or "").strip()
        if not clean_operation_id:
            raise ValueError("doc277_planning_operation_missing")
        with self._doc277_planning_lock:
            project = self._require_project(project_id)
            current = self._doc277_current_planning_operation(project)
            if current is None or current["state"] != "planning" or current["operation_id"] != clean_operation_id:
                raise ValueError("doc277_planning_operation_not_pending")
            if str(job_id or "").strip():
                self._issue_doc279_transparent_predecessor_receipt(
                    project_id,
                    str(job_id).strip(),
                )
            no_job_e32_projection: dict[str, str] | None = None
            if (
                bool(ecommerce_opaque_hold_response)
                and not str(job_id or "").strip()
                and str(failure_code or "").strip() == "planning_preflight_blocked"
            ):
                try:
                    opaque_hold, transparent_successor = (
                        self._doc279_current_opaque_provider_hold(project)
                    )
                except (KeyError, OSError, ValueError):
                    opaque_hold, transparent_successor = None, False
                hold_receipt_id = str(
                    (opaque_hold or {}).get("hold_receipt_id") or ""
                ).strip()
                if opaque_hold is not None and not transparent_successor and hold_receipt_id:
                    no_job_e32_projection = {
                        "schema_version": "doc279_e32_no_job_operation_projection_v1",
                        "authority": "v3_project_mode",
                        "project_id": project.project_id,
                        "operation_id": clean_operation_id,
                        "state": "ambiguous_provider_request_hold",
                        "opaque_hold_receipt_id": hold_receipt_id,
                    }
                    no_job_e32_projection["projection_digest"] = self._doc277_digest(
                        no_job_e32_projection
                    )
            public_operation = {
                "operation_id": clean_operation_id,
                "state": "planning_failed",
                "terminal": True,
                "pending": False,
                "next_actions": [{"id": "review_project_request"}],
            }
            now = _utc_now_iso()
            self.project_store.append_private_record(
                project.project_id,
                _DOC277_PRIVATE_PLANNING_NAMESPACE,
                {
                    "schema_version": "doc277_project_planning_operation_v1",
                    "record_kind": "failed",
                    "identity_digest": self._doc277_digest(
                        {
                            "project_id": project.project_id,
                            "operation_id": clean_operation_id,
                            "record_kind": "failed",
                            "failure_code": str(failure_code or "").strip() or "planning_unavailable",
                        }
                    ),
                    "project_id": project.project_id,
                    "operation_id": clean_operation_id,
                    "failure_code": str(failure_code or "").strip() or "planning_unavailable",
                    "created_at": now,
                    **(
                        {
                            "doc279_e32_no_job_operation_projection": (
                                no_job_e32_projection
                            )
                        }
                        if no_job_e32_projection is not None
                        else {}
                    ),
                },
            )
            project.metadata = {
                **dict(project.metadata or {}),
                _DOC277_CURRENT_OPERATION_KEY: {
                    **public_operation,
                    "created_at": now,
                },
            }
            project.updated_at = now
            self.project_store.save_project(project)
            return public_operation

    def close_interrupted_project_planning_operations(self) -> int:
        """Fail closed after a process restart; planning is never replayed."""

        closed = 0
        for project in self.project_store.list_all_projects():
            operation = self._doc277_current_planning_operation(project)
            if operation is None or operation["state"] != "planning":
                continue
            try:
                self.fail_project_planning_operation(
                    project.project_id,
                    operation["operation_id"],
                    failure_code="planning_process_restarted",
                )
            except (KeyError, ValueError):
                continue
            closed += 1
        return closed

    def list_timeline(self, project_id: str) -> ProjectTimelineResponse:
        project = self._require_project(project_id)
        self._reconcile_project_outputs(project)
        items = self.project_store.list_timeline(project.project_id)
        return ProjectTimelineResponse(
            api_namespace=API_NAMESPACE,
            route=f"{API_NAMESPACE}/projects/{project.project_id}/timeline",
            project_id=project.project_id,
            total=len(items),
            items=items,
            metadata={
                **self._metadata(),
                "project_outputs": self._project_output_items(project, limit=60),
            },
        )

    def get_project_context(self, project_id: str) -> ProjectContextPackage:
        project = self._require_project(project_id)
        self._ensure_project_product_reference_integrity(project)
        return self._refresh_project_context(project)

    def archive_project(self, project_id: str) -> ProjectResponse:
        project = self._require_project(project_id)
        now = _utc_now_iso()
        project.status = ProjectStatus.ARCHIVED
        project.updated_at = now
        project.metadata = {
            **project.metadata,
            "archived_at": now,
            "hidden_from_recent_projects": True,
            "archive_mode": "soft_archive",
        }
        project.memory_summary = self._memory_summary(project)
        self.project_store.save_project(project)
        self._append_timeline(
            project.project_id,
            TimelineItemType.PROJECT_ARCHIVED,
            "归档了项目",
            "这个项目已从最近项目里移除，历史内容仍保留。",
            metadata={"archive_mode": "soft_archive"},
        )
        project = self._require_project(project.project_id)
        return self._project_response(project)

    def delete_project(self, project_id: str) -> dict[str, Any]:
        project = self._require_project(project_id)
        self._reconcile_project_outputs(project)
        output_ids = self._project_generated_output_ids(project)
        upload_ids = self._project_uploaded_reference_ids(project)
        shared_output_ids = self._shared_project_output_ids(project, output_ids)
        shared_upload_ids = self._shared_project_upload_ids(project, upload_ids)
        output_ids_to_delete = [output_id for output_id in output_ids if output_id not in shared_output_ids]
        upload_ids_to_delete = [asset_id for asset_id in upload_ids if asset_id not in shared_upload_ids]

        deleted_outputs = 0
        failed_outputs: list[str] = []
        output_store = getattr(self.product_service, "output_store", None)
        if output_store is not None and hasattr(output_store, "delete_output"):
            for output_id in output_ids_to_delete:
                try:
                    if output_store.delete_output(output_id):
                        deleted_outputs += 1
                except Exception:
                    failed_outputs.append(output_id)

        deleted_uploads = 0
        failed_uploads: list[str] = []
        asset_store = getattr(self.product_service, "asset_store", None)
        if asset_store is not None and hasattr(asset_store, "delete_upload"):
            for asset_id in upload_ids_to_delete:
                try:
                    if asset_store.delete_upload(asset_id):
                        deleted_uploads += 1
                except Exception:
                    failed_uploads.append(asset_id)

        deleted_jobs = 0
        job_store = getattr(self.product_service, "job_store", None)
        if job_store is not None and hasattr(job_store, "delete_many"):
            deleted_jobs = int(job_store.delete_many(list(project.job_ids)))

        delete_store_project = getattr(self.project_store, "delete_project", None)
        project_deleted = bool(delete_store_project(project.project_id)) if callable(delete_store_project) else False
        return {
            "api_namespace": API_NAMESPACE,
            "route": f"{API_NAMESPACE}/projects/{project.project_id}",
            "project_id": project.project_id,
            "deleted": project_deleted,
            "deleted_outputs": deleted_outputs,
            "deleted_uploaded_assets": deleted_uploads,
            "deleted_jobs": deleted_jobs,
            "skipped_shared_outputs": len(shared_output_ids),
            "skipped_shared_uploaded_assets": len(shared_upload_ids),
            "failed_outputs": failed_outputs,
            "failed_uploaded_assets": failed_uploads,
            "metadata": {
                **self._metadata(),
                "delete_mode": "hard_delete_project_scope",
                "project_deleted_at": _utc_now_iso(),
            },
        }

    def add_project_reference(
        self,
        project_id: str,
        request: ProjectReferenceRequest | dict[str, Any],
    ) -> ProjectReferenceResponse:
        project = self._require_project(project_id)
        reference_request = self._coerce_reference_request(request)
        now = _utc_now_iso()
        preview_url: str | None = None
        if (
            project.primary_template_id == ECOMMERCE_TEMPLATE_ID
            and reference_request.source_type == ProjectReferenceSourceType.GENERATED_SELECTED
        ):
            try:
                output_record = self._require_ecommerce_selected_output_reference(project, reference_request)
            except ValueError:
                self._record_ecommerce_reference_channel_issue(
                    project,
                    issue_code="invalid_selected_continuation_output",
                    now=now,
                )
                raise
            preview_url = output_record.thumbnail_url or output_record.preview_url
            reference_request = reference_request.model_copy(
                update={
                    "asset_ref_id": output_record.output_id,
                    "created_from_job_id": output_record.job_id,
                    "created_from_output_id": output_record.output_id,
                    "metadata": {
                        **dict(reference_request.metadata or {}),
                        "canonical_output_binding": True,
                        "output_id": output_record.output_id,
                        "asset_id": output_record.asset_id,
                        "candidate_id": output_record.candidate_id,
                        "source_integrity_id": self._doc265_output_source_integrity_id(output_record),
                        "doc265_channel": "selected_continuation_directions",
                    },
                }
            )
            self._clear_ecommerce_reference_channel_issue(project)
        elif project.primary_template_id == ECOMMERCE_TEMPLATE_ID:
            self._clear_ecommerce_reference_channel_issue(project)
        reference = self._upsert_project_reference(
            project,
            source_type=reference_request.source_type,
            asset_ref_id=reference_request.asset_ref_id,
            now=now,
            label=reference_request.label,
            user_note=reference_request.user_note,
            use_policy=reference_request.use_policy,
            created_from_job_id=reference_request.created_from_job_id,
            created_from_output_id=reference_request.created_from_output_id,
            preview_url=preview_url,
            metadata=reference_request.metadata,
        )
        context = self._refresh_project_context(project)
        self._append_timeline(
            project.project_id,
            TimelineItemType.REFERENCE_UPLOADED,
            "添加了项目参考图",
            "这张参考图会在后续生成时继续帮助保持项目方向。",
            asset_ids=[reference.asset_ref_id],
            metadata={"reference_id": reference.reference_id, "use_policy": reference.use_policy.value},
        )
        return ProjectReferenceResponse(
            api_namespace=API_NAMESPACE,
            route=f"{API_NAMESPACE}/projects/{project.project_id}/references",
            project_id=project.project_id,
            reference=reference,
            project=project,
            context=context,
            metadata=self._metadata(),
        )

    def update_project_reference(
        self,
        project_id: str,
        reference_id: str,
        request: ProjectReferenceUpdateRequest | dict[str, Any],
    ) -> ProjectReferenceResponse:
        project = self._require_project(project_id)
        update_request = self._coerce_reference_update_request(request)
        reference = self._find_reference(project, reference_id)
        if update_request.label is not None:
            reference.label = update_request.label
        if update_request.user_note is not None:
            reference.user_note = update_request.user_note
        if update_request.status is not None:
            reference.status = update_request.status
        if update_request.use_policy is not None:
            reference.use_policy = update_request.use_policy
        reference.metadata.update(update_request.metadata)
        context = self._refresh_project_context(project)
        self._append_timeline(
            project.project_id,
            TimelineItemType.REFERENCE_UPDATED,
            "更新了项目参考",
            "后续生成会按新的参考设置继续。",
            asset_ids=[reference.asset_ref_id],
            metadata={"reference_id": reference.reference_id, "status": reference.status.value},
        )
        return ProjectReferenceResponse(
            api_namespace=API_NAMESPACE,
            route=f"{API_NAMESPACE}/projects/{project.project_id}/references/{reference.reference_id}",
            project_id=project.project_id,
            reference=reference,
            project=project,
            context=context,
            metadata=self._metadata(),
        )

    def remove_project_reference(
        self,
        project_id: str,
        reference_id: str,
        request: ProjectOutputStateRequest | dict[str, Any] | None = None,
    ) -> ProjectReferenceResponse:
        project = self._require_project(project_id)
        state_request = self._coerce_output_state_request(request or {})
        reference = self._find_reference(project, reference_id)
        now = _utc_now_iso()
        removed_output_ref: OutputRef | None = None
        if reference.source_type == ProjectReferenceSourceType.GENERATED_SELECTED:
            output_id = reference.created_from_output_id or reference.asset_ref_id
            try:
                removed_output_ref = self._find_output_ref(project, output_id)
                self._set_output_state(
                    project,
                    removed_output_ref,
                    ProjectOutputSelectionStateValue.UNSELECTED,
                    now,
                    note=state_request.plain_text or "用户移除了项目参考",
                )
                project.selected_output_refs = [
                    existing
                    for existing in project.selected_output_refs
                    if self._output_identity(existing) != self._output_identity(removed_output_ref)
                ]
            except KeyError:
                removed_output_ref = None
        reference.status = ProjectReferenceStatus.INACTIVE
        feedback = self._append_feedback(
            project,
            target_type=ProjectFeedbackTargetType.REFERENCE,
            target_id=reference.reference_id,
            feedback_type=ProjectFeedbackType.REMOVE_REFERENCE,
            plain_text=state_request.plain_text or "用户移除了项目参考",
            reason_tags=state_request.reason_tags,
            metadata={"reference_id": reference.reference_id, **state_request.metadata},
        )
        context = self._refresh_project_context(project)
        self._append_timeline(
            project.project_id,
            TimelineItemType.REFERENCE_REMOVED,
            "移除了项目参考",
            "这张参考不会继续影响后续生成，项目历史仍保留。",
            asset_ids=[reference.asset_ref_id],
            selected_output_refs=[removed_output_ref] if removed_output_ref else [],
            metadata={"reference_id": reference.reference_id, "feedback_id": feedback.feedback_id},
        )
        return ProjectReferenceResponse(
            api_namespace=API_NAMESPACE,
            route=f"{API_NAMESPACE}/projects/{project.project_id}/references/{reference.reference_id}/remove",
            project_id=project.project_id,
            reference=reference,
            project=project,
            context=context,
            metadata=self._metadata(),
        )

    def add_project_feedback(
        self,
        project_id: str,
        request: ProjectFeedbackRequest | dict[str, Any],
    ) -> ProjectFeedbackResponse:
        project = self._require_project(project_id)
        feedback_request = self._coerce_feedback_request(request)
        feedback = self._append_feedback(
            project,
            target_type=feedback_request.target_type,
            target_id=feedback_request.target_id,
            feedback_type=feedback_request.feedback_type,
            plain_text=feedback_request.plain_text,
            reason_tags=feedback_request.reason_tags,
            status=feedback_request.status,
            metadata=feedback_request.metadata,
        )
        if feedback.feedback_type == ProjectFeedbackType.REMOVE_REFERENCE and feedback.target_id:
            self._find_reference(project, feedback.target_id).status = ProjectReferenceStatus.INACTIVE
        context = self._refresh_project_context(project)
        self._append_timeline(
            project.project_id,
            TimelineItemType.NOTE_ADDED,
            "记录了项目反馈",
            self._short_text(feedback.plain_text, 80),
            metadata={"feedback_id": feedback.feedback_id, "feedback_type": feedback.feedback_type.value},
        )
        return ProjectFeedbackResponse(
            api_namespace=API_NAMESPACE,
            route=f"{API_NAMESPACE}/projects/{project.project_id}/feedback",
            project_id=project.project_id,
            feedback=feedback,
            project=project,
            context=context,
            metadata=self._metadata(),
        )

    def create_brand_memory_proposal(
        self,
        project_id: str,
        request: ProjectBrandMemoryProposalRequest | dict[str, Any],
    ) -> ProjectBrandMemoryProposalResponse:
        project = self._require_project(project_id)
        proposal_request = self._coerce_brand_memory_proposal_request(request)
        context = self._refresh_project_context(project)
        self._ensure_brand_memory_proposal_available(context)
        if proposal_request.mode == ProjectBrandMemoryProposalMode.APPEND:
            target_brand_id = proposal_request.target_brand_id or project.linked_brand_id
            if not target_brand_id:
                raise ValueError("target_brand_id is required when appending to Brand Memory")
            if self.product_service.brand_profile_service.load_profile(target_brand_id) is None:
                raise KeyError("target brand memory was not found")

        now = _utc_now_iso()
        proposal = self._build_brand_memory_proposal(project, context, proposal_request, now)
        project.brand_memory_proposals = [
            existing
            for existing in project.brand_memory_proposals
            if existing.proposal_id != proposal.proposal_id
        ]
        project.brand_memory_proposals.append(proposal)
        project.updated_at = now
        project.memory_summary = self._memory_summary(project)
        self.project_store.save_project(project)
        return ProjectBrandMemoryProposalResponse(
            api_namespace=API_NAMESPACE,
            route=f"{API_NAMESPACE}/projects/{project.project_id}/brand-memory/proposal",
            project_id=project.project_id,
            proposal=proposal,
            project=project,
            context=context,
            metadata={**self._metadata(), "brand_memory_written": False},
        )

    def confirm_brand_memory_proposal(
        self,
        project_id: str,
        request: ProjectBrandMemoryConfirmRequest | dict[str, Any],
    ) -> ProjectBrandMemoryConfirmResponse:
        project = self._require_project(project_id)
        confirm_request = self._coerce_brand_memory_confirm_request(request)
        proposal = self._find_brand_memory_proposal(project, confirm_request.proposal_id)
        if proposal.status == ProjectBrandMemoryProposalStatus.CONFIRMED:
            raise ValueError("this Brand Memory proposal has already been saved")
        brand = self._apply_brand_memory_confirmation(project, proposal, confirm_request)
        now = _utc_now_iso()
        proposal.status = ProjectBrandMemoryProposalStatus.CONFIRMED
        proposal.confirmed_at = now
        proposal.target_brand_id = brand.brand_id
        proposal.brand_name_suggestion = confirm_request.edited_brand_name or proposal.brand_name_suggestion
        proposal.style_summary = confirm_request.edited_style_summary
        proposal.keep_notes = self._dedupe_text(confirm_request.edited_keep_notes or proposal.keep_notes)
        proposal.avoid_notes = self._dedupe_text(confirm_request.edited_avoid_notes or proposal.avoid_notes)
        proposal.usage_scenes = self._dedupe_text(confirm_request.edited_usage_scenes or proposal.usage_scenes)
        proposal.metadata = {
            **proposal.metadata,
            **confirm_request.metadata,
            "confirmed_by_user": True,
            "brand_memory_written": True,
        }
        project.linked_brand_id = brand.brand_id
        project.updated_at = now
        project.memory_summary = self._memory_summary(project)
        self.project_store.save_project(project)
        plain_summary = "以后可以在新项目中继续沿用这组已确认的视觉方向。"
        self._append_timeline(
            project.project_id,
            TimelineItemType.BRAND_MEMORY_CONFIRMED,
            "已保存为品牌风格",
            plain_summary,
            asset_ids=proposal.reference_asset_ids,
            metadata={"brand_id": brand.brand_id, "proposal_id": proposal.proposal_id},
        )
        project = self._require_project(project.project_id)
        return ProjectBrandMemoryConfirmResponse(
            api_namespace=API_NAMESPACE,
            route=f"{API_NAMESPACE}/projects/{project.project_id}/brand-memory/confirm",
            project_id=project.project_id,
            brand_id=brand.brand_id,
            memory_update_applied=True,
            updated_at=now,
            plain_summary=plain_summary,
            proposal=proposal,
            project=project,
            metadata={**self._metadata(), "brand_memory_written": True},
        )

    def unselect_project_output(
        self,
        project_id: str,
        output_id: str,
        request: ProjectOutputStateRequest | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        project = self._require_project(project_id)
        state_request = self._coerce_output_state_request(request or {})
        now = _utc_now_iso()
        ref = self._find_output_ref(project, output_id)
        self._set_output_state(
            project,
            ref,
            ProjectOutputSelectionStateValue.UNSELECTED,
            now,
            note=state_request.plain_text,
        )
        project.selected_output_refs = [
            existing
            for existing in project.selected_output_refs
            if self._output_identity(existing) != self._output_identity(ref)
        ]
        for reference in self._references_for_output(project, ref):
            reference.status = ProjectReferenceStatus.INACTIVE
        context = self._refresh_project_context(project)
        self._append_timeline(
            project.project_id,
            TimelineItemType.CANDIDATE_UNSELECTED,
            "取消了后续参考",
            "这张图会保留在历史里，但不会继续影响后面的生成。",
            job_id=ref.job_id,
            asset_ids=[ref.asset_id] if ref.asset_id else [],
            candidate_ids=[ref.candidate_id] if ref.candidate_id else [],
            selected_output_refs=[ref],
            metadata={"output_id": self._output_identity(ref)},
        )
        return self._state_change_response(project, context)

    def reject_project_output(
        self,
        project_id: str,
        output_id: str,
        request: ProjectOutputStateRequest | dict[str, Any],
    ) -> dict[str, Any]:
        project = self._require_project(project_id)
        state_request = self._coerce_output_state_request(request)
        if not state_request.plain_text:
            raise ValueError("plain_text is required")
        now = _utc_now_iso()
        ref = self._find_output_ref(project, output_id)
        self._set_output_state(
            project,
            ref,
            ProjectOutputSelectionStateValue.REJECTED,
            now,
            note=state_request.plain_text,
        )
        project.selected_output_refs = [
            existing
            for existing in project.selected_output_refs
            if self._output_identity(existing) != self._output_identity(ref)
        ]
        for reference in self._references_for_output(project, ref):
            reference.status = ProjectReferenceStatus.INACTIVE
        feedback = self._append_feedback(
            project,
            target_type=ProjectFeedbackTargetType.OUTPUT,
            target_id=self._output_identity(ref),
            feedback_type=ProjectFeedbackType.AVOID_DIRECTION,
            plain_text=state_request.plain_text,
            reason_tags=state_request.reason_tags,
            metadata=state_request.metadata,
        )
        context = self._refresh_project_context(project)
        self._append_timeline(
            project.project_id,
            TimelineItemType.DIRECTION_REJECTED,
            "标记了不想要的方向",
            self._short_text(state_request.plain_text, 80),
            job_id=ref.job_id,
            asset_ids=[ref.asset_id] if ref.asset_id else [],
            candidate_ids=[ref.candidate_id] if ref.candidate_id else [],
            selected_output_refs=[ref],
            metadata={"output_id": self._output_identity(ref), "feedback_id": feedback.feedback_id},
        )
        return self._state_change_response(project, context, feedback=feedback)

    def _doc281_ecommerce_drift_terminal_status(
        self,
        project: ProjectRecord,
        request: CreateProjectJobRequest,
    ) -> ProductJobStatus | None:
        """Close a drifted active product association before any write or plan."""

        snapshot = self._doc270_project_source_library(project)
        drifted = [
            item for item in snapshot.get("entries", [])
            if isinstance(item, dict)
            and item.get("use_policy") == "product"
            and item.get("availability_state") in {
                "upload_missing", "upload_not_ready", "role_or_channel_invalid", "file_missing", "file_unreadable", "content_drift",
            }
        ]
        if not drifted:
            return None
        command_facts = {
            "project_id": project.project_id,
            "template_id": ECOMMERCE_TEMPLATE_ID,
            "explicit_command_key": str(dict(request.metadata or {}).get("idempotency_key") or request.user_input or project.user_goal).strip(),
            "association_snapshot_digest": str(snapshot.get("snapshot_digest") or ""),
        }
        command_identity = {
            "schema_version": "doc281_source_association_command_identity_v1",
            "project_id": project.project_id,
            "template_id": ECOMMERCE_TEMPLATE_ID,
            "command_id": stable_id("doc281_source_association_command", self._doc270_digest(command_facts)),
            "command_facts_digest": self._doc270_digest(command_facts),
        }
        command_identity["identity_digest"] = self._doc270_digest(command_identity)
        operation = {
            "state": "needs_input",
            "terminal": True,
            "pending": False,
            "next_actions": [{"id": "review_product_inputs"}],
        }
        receipt = {
            "schema_version": _DOC281_TERMINAL_RECEIPT_SCHEMA,
            "identity_digest": command_identity["identity_digest"],
            "command_identity": command_identity,
            "association_snapshot_digest": command_facts["association_snapshot_digest"],
            "public_operation": operation,
        }
        receipt["receipt_digest"] = self._doc270_digest(receipt)
        existing = self.project_store.append_private_record(
            project.project_id,
            _DOC281_TERMINAL_RECEIPT_NAMESPACE,
            receipt,
        )
        projected = existing.get("public_operation") if isinstance(existing, dict) else operation
        return ProductJobStatus(
            job_id="",
            status=ProductJobStatusValue.BLOCKED,
            api_namespace=API_NAMESPACE,
            ui_entry_route=f"{API_NAMESPACE}/projects/{project.project_id}",
            metadata={"current_operation": dict(projected) if isinstance(projected, dict) else operation},
        )

    def _doc281_current_terminal_operation(self, project: ProjectRecord) -> dict[str, Any] | None:
        """Rehydrate the newest still-current sanitized Doc281 closure."""

        try:
            snapshot_digest = str(self._doc270_project_source_library(project).get("snapshot_digest") or "")
        except Exception:
            return None
        for receipt in reversed(self.project_store.list_private_records(
            project.project_id, _DOC281_TERMINAL_RECEIPT_NAMESPACE,
        )):
            if not isinstance(receipt, dict) or not self._doc270_same_digest_record(receipt, "receipt_digest"):
                continue
            identity = receipt.get("command_identity")
            operation = receipt.get("public_operation")
            if (
                receipt.get("schema_version") != _DOC281_TERMINAL_RECEIPT_SCHEMA
                or not isinstance(identity, dict)
                or identity.get("project_id") != project.project_id
                or identity.get("template_id") != ECOMMERCE_TEMPLATE_ID
                or receipt.get("association_snapshot_digest") != snapshot_digest
                or not isinstance(operation, dict)
                or operation.get("state") != "needs_input"
                or operation.get("terminal") is not True
                or operation.get("pending") is not False
                or operation.get("next_actions") != [{"id": "review_product_inputs"}]
            ):
                continue
            return dict(operation)
        return None

    def _doc281_general_analysis_entries(self, *, project_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """Give the shared analyzer only reverified current bytes, ephemerally."""

        result: list[dict[str, Any]] = []
        for entry in entries:
            asset_id = str(entry.get("asset_id") or "").strip()
            expected_sha = str(entry.get("content_sha256") or "").strip().lower()
            record = self.product_service.get_uploaded_asset(asset_id)
            path = Path(str(getattr(record, "file_path", "") or "")) if record is not None else None
            mime_type = str(getattr(record, "mime_type", "") or "").strip().lower()
            if (
                not asset_id or len(expected_sha) != 64 or entry.get("automatic_use_eligible") is not True
                or record is None or str(getattr(getattr(record, "status", None), "value", "")) != "ready"
                or path is None or not path.is_file() or mime_type not in {"image/png", "image/jpeg", "image/webp"}
            ):
                return None
            try:
                content = path.read_bytes()
            except OSError:
                return None
            if hashlib.sha256(content).hexdigest() != expected_sha:
                return None
            result.append({**entry, "analysis_bytes": content, "mime_type": mime_type})
        return result or None

    def create_project_job(
        self,
        project_id: str,
        request: CreateProjectJobRequest | dict[str, Any],
        *,
        _trusted_photography_continuation: bool = False,
        _trusted_capability_continuation: bool = False,
    ) -> ProductJobStatus:
        project = self._require_project(project_id)
        job_request = self._coerce_create_project_job_request(request)
        # Doc270 Phase 1 fields are server-owned compatibility evidence.  A
        # browser may not author them for any template, including General or
        # Photography; trusted E-Commerce code adds its own internal snapshot
        # and receipt after canonical admission.
        job_request = job_request.model_copy(
            update={
                "metadata": {
                    key: value
                    for key, value in dict(job_request.metadata or {}).items()
                    if key not in _DOC270_IGNORED_CLIENT_METADATA
                }
            }
        )
        template_manifest = self._ensure_active_template(job_request.template_id)
        doc270_general_identity: dict[str, Any] | None = None
        doc270_general_activation: dict[str, Any] | None = None
        if template_manifest.template_id == GENERAL_TEMPLATE_ID:
            job_request = job_request.model_copy(
                update={
                    "metadata": {
                        key: value
                        for key, value in dict(job_request.metadata or {}).items()
                        if key not in _DOC270_PHASE3_IGNORED_CLIENT_METADATA
                    }
                }
            )
            doc281_registry = self.doc281_general_source_registry
            if doc281_registry.enabled:
                try:
                    identity = doc281_registry.issue_command_identity(
                        project_id=project.project_id,
                        template_id=template_manifest.template_id,
                        command_direction=str(job_request.user_input or project.user_goal or "").strip(),
                        source_library_snapshot=self._doc270_project_source_library(project),
                        requested_output_count=_bounded_requested_image_count(
                            job_request.metadata.get("requested_image_count")
                        ) or 1,
                    )
                    if isinstance(identity, dict):
                        self.project_store.append_private_record(project.project_id, _DOC281_GENERAL_COMMAND_NAMESPACE, {
                            "schema_version": "doc281_general_command_v2", "identity": dict(identity),
                            "identity_digest": str(identity.get("identity_digest") or ""),
                        })
                    existing_general = (
                        self._doc270_general_existing_command(project, identity)
                        if isinstance(identity, dict)
                        else None
                    )
                    if existing_general is not None:
                        return existing_general
                    persisted = next((record.get("entry") for record in reversed(self.project_store.list_private_records(
                        project.project_id, _DOC281_GENERAL_RECEIPT_NAMESPACE,
                    )) if record.get("identity_digest") == identity.get("identity_digest")), None) if isinstance(identity, dict) else None
                    entry = dict(persisted) if isinstance(persisted, dict) else doc281_registry.lookup_registered_receipt(
                        project_id=project.project_id,
                        command_identity=dict(identity) if isinstance(identity, dict) else None,
                    )
                    if isinstance(identity, dict) and isinstance(entry, dict):
                        self.project_store.append_private_record(project.project_id, _DOC281_GENERAL_RECEIPT_NAMESPACE, {
                            "schema_version": "doc281_general_resolution_receipt_v2", "identity_digest": str(identity.get("identity_digest") or ""),
                            "entry": dict(entry),
                        })
                except Exception:
                    identity, entry = None, None
                if isinstance(identity, dict):
                    doc270_general_identity = dict(identity)
                    doc270_general_activation = self._doc281_general_registered_receipt_decision(
                        project,
                        identity=doc270_general_identity,
                        entry=entry,
                    )
                else:
                    # An unavailable, optional, or invalid Doc281 decision is
                    # ordinary prompt-only General.  Do not fall through to
                    # the legacy project-asset expansion below.
                    doc270_general_activation = {"state": "prompt_only"}
            else:
                capability = self._doc270_general_activation_capability_lookup()
                if self._doc270_general_activation_capability_valid(
                    capability,
                    template_id=template_manifest.template_id,
                ):
                    try:
                        identity = self._doc270_general_command_identity_lookup(
                            project_id=project.project_id,
                            template_id=template_manifest.template_id,
                        )
                    except Exception:
                        identity = None
                    if identity is not None:
                        if self._doc270_general_command_identity_valid(
                            identity,
                            project_id=project.project_id,
                            template_id=template_manifest.template_id,
                        ) and identity.get("capability_version") == capability.get("capability_version"):
                            existing_general = self._doc270_general_existing_command(project, identity)
                            if existing_general is not None:
                                return existing_general
                            doc270_general_identity = dict(identity)
                            doc270_general_activation = self._doc270_general_activation_decision(
                                project,
                                template_id=template_manifest.template_id,
                                identity=doc270_general_identity,
                            )
                        else:
                            doc270_general_activation = {"state": "receipt_invalid"}
        if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID and (
            job_request.suite_slot_request
            or (
                job_request.commerce_profile_patch is not None
                and job_request.commerce_profile_patch.suite_slots_requested
            )
        ):
            raise ValueError(
                "ecommerce_static_slot_request_retired: the Central Brain decides the requested image set from facts and user intent."
            )
        ecommerce_text_to_image_fallback = False
        if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID:
            job_request = job_request.model_copy(
                update={
                    "metadata": {
                        key: value
                        for key, value in dict(job_request.metadata or {}).items()
                        if key not in _ECOMMERCE_IGNORED_CLIENT_METADATA
                    }
                }
            )
            drift_terminal = self._doc281_ecommerce_drift_terminal_status(project, job_request)
            if drift_terminal is not None:
                return drift_terminal
            requested_reference_ids = [
                str(item).strip()
                for item in job_request.uploaded_asset_ids
                if str(item).strip()
            ]
            requested_product_ids: list[str] = []
            legacy_output_ids: list[str] = []
            if requested_reference_ids:
                requested_product_ids, legacy_output_ids, invalid_reference_ids, invalid_product_ids = (
                    self._classify_ecommerce_legacy_reference_ids(project, requested_reference_ids)
                )
                if invalid_reference_ids:
                    self._record_ecommerce_reference_channel_issue(
                        project,
                        issue_code="invalid_legacy_reference_channel",
                        now=_utc_now_iso(),
                    )
                    raise ValueError("reference channel input invalid")
                if invalid_product_ids:
                    self._ecommerce_product_reference_asset_ids(project, invalid_product_ids)
            if requested_product_ids:
                # A browser upload selector is admitted only by resolving the
                # V3 upload record, then persisted as a project-owned
                # reference before the canonical pool is read.
                self._ecommerce_product_reference_asset_ids(project, requested_product_ids)
                self._persist_job_uploaded_references(
                    project,
                    requested_product_ids,
                    template_id=template_manifest.template_id,
                    user_input=job_request.user_input or project.user_goal,
                )
            if legacy_output_ids:
                job_request = job_request.model_copy(
                    update={
                        "metadata": {
                            **dict(job_request.metadata or {}),
                            "doc265_reference_channel_recovery": {
                                "schema_version": "doc265_reference_channel_recovery_v1",
                                "authority": "v3_project_mode",
                                "legacy_uploaded_output_ids": legacy_output_ids,
                                "recovered_product_asset_ids": requested_product_ids,
                            },
                        }
                    }
                )
            self._ensure_ecommerce_selected_output_integrity(project)
            doc269_selected_continuation_admissions = (
                self._doc269_selected_continuation_admissions(project)
            )
            # Explicit selectors have now been admitted into Project Mode.
            # A project created with ready product uploads starts with an
            # append-only legacy mirror.  Materialize the current canonical
            # pool into authoritative project associations before either the
            # Doc270 source library or command identity reads it.  Otherwise
            # Product API admission can accept a product whose source-library
            # snapshot is empty, which is a false cross-authority mismatch.
            # Empty pools remain the established text-to-image path.
            initial_canonical_product_ids = self._ecommerce_product_reference_asset_ids(project, [])
            if initial_canonical_product_ids:
                self._persist_job_uploaded_references(
                    project,
                    initial_canonical_product_ids,
                    template_id=template_manifest.template_id,
                    user_input=job_request.user_input or project.user_goal,
                )
            # Reconcile canonical refs after association materialization so a
            # first submission and its immediate replay observe the same
            # server-owned product pool.
            self._ensure_project_product_reference_integrity(project)
            uploaded_asset_ids = self._ecommerce_product_reference_asset_ids(project, [])
            current_reference_binding_digest = self._ecommerce_current_reference_binding_digest(project)
            doc270_ecommerce_view_activation_enabled = False
            doc270_requested_output_count = (
                _bounded_requested_image_count(job_request.metadata.get("requested_image_count"))
                or 1
            )
            try:
                capability = self._doc270_ecommerce_view_activation_capability_lookup(
                    project_id=project.project_id,
                    expected_output_count=doc270_requested_output_count,
                )
            except TypeError:
                # Existing deterministic test doubles predate the project-
                # scoped capability argument; production never takes this
                # compatibility branch.
                capability = self._doc270_ecommerce_view_activation_capability_lookup()
            if uploaded_asset_ids and self._doc270_ecommerce_view_activation_capability_valid(capability):
                # E31's identity and frozen source snapshot are issued only
                # after Product API has completed Doc263/Doc264 admission.
                # This is a server-only enable signal, never a caller-owned
                # snapshot, selected-id list, or receipt.
                doc270_ecommerce_view_activation_enabled = True
            doc271_command_direction = str(job_request.user_input or project.user_goal or "").strip()
            try:
                doc271_current_source_binding = self._doc271_current_source_binding(
                    project,
                    selected_continuation_admissions=doc269_selected_continuation_admissions,
                )
            except (OSError, ValueError, KeyError):
                # A legacy or unselected generated-history reference remains
                # owned by the existing Doc265 path. It is simply ineligible
                # for Doc271 closure matching, never a new create-time block.
                doc271_current_source_binding = None
            closure = self._doc271_matching_provider_deliverability_closure(
                project,
                user_input=str(project.user_goal or "").strip(),
                command_direction=doc271_command_direction,
                requested_output_count=_bounded_requested_image_count(
                    job_request.metadata.get("requested_image_count")
                )
                or 1,
                selected_continuation_admissions=doc269_selected_continuation_admissions,
                current_source_binding=doc271_current_source_binding,
            )
            if closure is not None:
                return ProductJobStatus(
                    job_id="",
                    status=ProductJobStatusValue.BLOCKED,
                    api_namespace=API_NAMESPACE,
                    ui_entry_route=f"{API_NAMESPACE}/projects/{project.project_id}",
                    metadata={"current_operation": safe_closure_operation(closure)},
                )
            opaque_hold = self._doc278_matching_opaque_provider_hold(
                project,
                user_input=str(project.user_goal or "").strip(),
                command_direction=doc271_command_direction,
                requested_output_count=_bounded_requested_image_count(
                    job_request.metadata.get("requested_image_count")
                )
                or 1,
                selected_continuation_admissions=doc269_selected_continuation_admissions,
                current_source_binding=doc271_current_source_binding,
                current_reference_binding_digest=current_reference_binding_digest,
            )
            if opaque_hold is not None:
                return ProductJobStatus(
                    job_id="",
                    status=ProductJobStatusValue.BLOCKED,
                    api_namespace=API_NAMESPACE,
                    ui_entry_route=f"{API_NAMESPACE}/projects/{project.project_id}",
                    metadata={
                        "current_operation": safe_ambiguous_provider_request_hold_operation(
                            opaque_hold
                        )
                    },
                )
            idempotency_key = str(job_request.metadata.get("idempotency_key") or "").strip()
            existing = self._existing_ecommerce_command(
                project,
                idempotency_key=idempotency_key,
                current_reference_binding_digest=current_reference_binding_digest,
            )
            if existing is not None:
                return existing
            supersedes_job_id = self._ecommerce_superseded_job_id(project)
            doc271_goal_snapshot = self._issue_doc271_project_goal_snapshot(
                project,
                template_id=template_manifest.template_id,
            )
            doc271_command_binding = {
                "schema_version": "doc271_command_binding_v1",
                "authority": "v3_project_mode",
                "project_id": project.project_id,
                "template_id": template_manifest.template_id,
                "command_attempt_id": doc271_goal_snapshot["command_attempt_id"],
                "goal_snapshot_id": doc271_goal_snapshot["snapshot_id"],
                "goal_snapshot_digest": doc271_goal_snapshot["snapshot_digest"],
                "command_direction": doc271_command_direction,
            }
            doc271_command_binding["command_binding_digest"] = self._doc271_digest(
                {
                    "template_id": template_manifest.template_id,
                    "project_id": project.project_id,
                    "command_attempt_id": doc271_goal_snapshot["command_attempt_id"],
                    "goal_snapshot_id": doc271_goal_snapshot["snapshot_id"],
                    "goal_snapshot_digest": doc271_goal_snapshot["snapshot_digest"],
                    "command_direction": doc271_command_direction,
                }
            )
            job_request = job_request.model_copy(
                update={
                    "metadata": {
                        **dict(job_request.metadata or {}),
                        # This value is always rebuilt from active canonical
                        # project references, never trusted from the browser.
                        "current_reference_binding_digest": current_reference_binding_digest,
                        **(
                            {"doc271_current_source_binding": doc271_current_source_binding}
                            if isinstance(doc271_current_source_binding, dict)
                            else {}
                        ),
                        "doc271_command_binding": doc271_command_binding,
                        **(
                            {
                                "doc270_ecommerce_view_activation_enabled": True,
                                "doc270_ecommerce_command_facts": {
                                    "template_id": template_manifest.template_id,
                                    "command_direction": str(job_request.user_input or project.user_goal or "").strip(),
                                    "requested_output_count": _bounded_requested_image_count(
                                        job_request.metadata.get("requested_image_count")
                                    ) or 1,
                                    "current_reference_binding_digest": current_reference_binding_digest,
                                },
                            }
                            if doc270_ecommerce_view_activation_enabled
                            else {}
                        ),
                    }
                }
            )
            ecommerce_text_to_image_fallback = not uploaded_asset_ids
            commerce_profile = self._merge_commerce_profile(project, job_request)
        else:
            uploaded_asset_ids = list(
                dict.fromkeys([*self._project_asset_ids(project), *job_request.uploaded_asset_ids])
            )
            if doc270_general_activation is not None:
                if doc270_general_activation["state"] == "activated_resolved":
                    uploaded_asset_ids = list(doc270_general_activation["selected_original_asset_ids"])
                else:
                    uploaded_asset_ids = []
                job_request = job_request.model_copy(
                    update={
                        "metadata": {
                            **dict(job_request.metadata or {}),
                            "doc270_general_command_identity": doc270_general_identity,
                            "doc270_general_source_activation_receipts": [
                                {
                                    key: value
                                    for key, value in doc270_general_activation.items()
                                    if key != "projection"
                                }
                            ],
                            **(
                                {
                                    "doc270_general_original_source_projection": doc270_general_activation["projection"],
                                    **(
                                        {
                                            "doc281_general_output_source_bindings_v1": doc270_general_activation[
                                                "output_source_bindings"
                                            ],
                                        }
                                        if isinstance(doc270_general_activation.get("output_source_bindings"), list)
                                        else {}
                                    ),
                                }
                                if doc270_general_activation["state"] == "activated_resolved"
                                else {}
                            ),
                        }
                    }
                )
            current_reference_binding_digest = ""
            idempotency_key = ""
            supersedes_job_id = None
            commerce_profile = None
        if template_manifest.template_id not in project.allowed_template_ids:
            project.allowed_template_ids.append(template_manifest.template_id)
        project.primary_template_id = template_manifest.template_id
        user_input = job_request.user_input or project.user_goal
        if template_manifest.template_id != ECOMMERCE_TEMPLATE_ID:
            self._persist_job_uploaded_references(
                project,
                uploaded_asset_ids,
                template_id=template_manifest.template_id,
                user_input=user_input,
            )
        advanced_reference_controls = self._advanced_reference_controls_for_template(
            project=project,
            request=job_request,
            template_id=template_manifest.template_id,
        )
        project.metadata["advanced_reference_controls"] = dict(advanced_reference_controls)
        project.metadata["doc90_advanced_reference_controls"] = bool(advanced_reference_controls)
        context = self._build_context(
            project,
            continuation_instruction=job_request.user_input,
            template_id=template_manifest.template_id,
            commerce_profile=commerce_profile,
        )
        context_snapshot = context.model_dump(mode="json")
        scenario_selection = self._scenario_selection_for_template(
            template_manifest,
            job_request,
            context,
            commerce_profile=commerce_profile,
            has_product_reference=bool(uploaded_asset_ids),
            advanced_reference_controls=advanced_reference_controls,
        )
        product_profile = self._product_profile_for_template(
            project,
            context_snapshot,
            job_request,
            template_manifest,
            commerce_profile=commerce_profile,
            advanced_reference_controls=advanced_reference_controls,
        )
        scenario_parameters = dict(scenario_selection.get("parameters") or {})
        general_variation_contract = (
            self._general_variation_contract(job_request.metadata)
            if template_manifest.template_id == GENERAL_TEMPLATE_ID
            else {}
        )
        if general_variation_contract:
            scenario_parameters = {**scenario_parameters, **general_variation_contract}
        project_job_sequence = len(project.job_ids) + 1
        create_payload = {
            "user_input": user_input,
            "brand_id": project.linked_brand_id,
            "scenario_selection": scenario_selection,
            "photographer_profile_id": job_request.photographer_profile_id,
            "photographer_profile_selection_source": job_request.photographer_profile_selection_source,
            "uploaded_asset_ids": uploaded_asset_ids,
            "product_profile": product_profile,
            "metadata": {
                **job_request.metadata,
                "project_id": project.project_id,
                "template_id": template_manifest.template_id,
                "template_manifest_id": template_manifest.template_id,
                "project_job_sequence": project_job_sequence,
                "scenario_pack_id": template_manifest.scenario_pack_id,
                "scenario_parameters": scenario_parameters,
                # Desktop and H5 consume this canonical General contract at
                # the Job metadata root. Keep that stable projection in sync
                # with the Scenario Pack diagnostic snapshot.
                **general_variation_contract,
                # Central Brain consumes these normalized values from the job
                # metadata, not from the nested Scenario Pack diagnostic
                # snapshot.  Preserve the explicit General canvas/count there
                # so a default social asset cannot silently overwrite a user
                # request such as 3:2 / 1536x1024 at materialization time.
                **(
                    {"requested_image_count": scenario_parameters["requested_image_count"]}
                    if "requested_image_count" in scenario_parameters
                    else {}
                ),
                **(
                    {"requested_image_size": scenario_parameters["requested_image_size"]}
                    if "requested_image_size" in scenario_parameters
                    else {}
                ),
                "selected_mode_id": scenario_selection.get("mode_id"),
                "selected_preset_id": scenario_selection.get("preset_id"),
                "project_context_version": context.context_version,
                "project_context_snapshot": context_snapshot,
                "project_mode": True,
                "advanced_reference_controls": advanced_reference_controls,
                "doc90_advanced_reference_controls": bool(advanced_reference_controls),
                "apply_brand_memory_update_default": False,
                "commerce_profile_present": commerce_profile is not None,
                "ecommerce_text_to_image_fallback": ecommerce_text_to_image_fallback,
                "has_product_reference": bool(uploaded_asset_ids) if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID else None,
                "ecommerce_slot_lineage_seed": template_manifest.template_id == ECOMMERCE_TEMPLATE_ID,
                **(
                    {
                        "current_reference_binding_digest": current_reference_binding_digest,
                        "idempotency_key": idempotency_key,
                    }
                    if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID
                    else {}
                ),
                **({"supersedes_job_id": supersedes_job_id} if supersedes_job_id else {}),
            },
        }
        status = (
            self.product_service.create_project_ecommerce_job(
                create_payload,
                canonical_product_asset_ids=uploaded_asset_ids,
                binding_service=self.project_visual_asset_binding_service,
                doc269_selected_continuation_admissions=doc269_selected_continuation_admissions,
                doc270_source_library_enabled=True,
                trusted_doc270_ecommerce_view_activation=doc270_ecommerce_view_activation_enabled,
            )
            if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID
            and not _trusted_capability_continuation
            else self.product_service.create_trusted_photography_continuation_job(create_payload)
            if _trusted_photography_continuation
            else self.product_service.create_trusted_capability_continuation_job(create_payload)
            if _trusted_capability_continuation
            else self.product_service.create_project_visual_asset_bound_job(
                create_payload,
                binding_service=self.project_visual_asset_binding_service,
            )
            if self.project_visual_asset_binding_service is not None
            else self.product_service.create_job(create_payload)
        )
        if (
            template_manifest.template_id == ECOMMERCE_TEMPLATE_ID
            and not str(status.job_id or "").strip()
            and isinstance(status.metadata.get("current_operation"), dict)
            and status.metadata["current_operation"].get("state") == "needs_input"
        ):
            self._set_doc270_ecommerce_needs_input_operation(project)
            return status
        if (
            template_manifest.template_id == ECOMMERCE_TEMPLATE_ID
            and not str(status.job_id or "").strip()
            and isinstance(status.metadata.get("current_operation"), dict)
            and status.metadata["current_operation"].get("state") == "source_analysis_unavailable"
        ):
            self._set_doc270_ecommerce_source_analysis_unavailable_operation(project)
            return status
        if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID:
            self._clear_doc270_ecommerce_needs_input_operation(project)
        if (
            template_manifest.template_id == ECOMMERCE_TEMPLATE_ID
            and isinstance(status.metadata.get("current_operation"), dict)
            and status.metadata["current_operation"].get("state") == "needs_input"
        ):
            supersedes_job_id = None
        bound_context_snapshot = status.metadata.get("project_context_snapshot")
        if not isinstance(bound_context_snapshot, dict):
            bound_context_snapshot = context_snapshot
        photographer_profile_binding = self.product_service.photographer_profile_binding_for_job(status.job_id)
        if photographer_profile_binding is not None:
            project.photographer_profile_bindings[status.job_id] = photographer_profile_binding.model_dump(mode="json")
        status.metadata.update(
            {
                "project_id": project.project_id,
                "template_id": template_manifest.template_id,
                "template_manifest_id": template_manifest.template_id,
                "project_job_sequence": project_job_sequence,
                "scenario_pack_id": template_manifest.scenario_pack_id,
                "scenario_parameters": scenario_selection.get("parameters") or {},
                "selected_mode_id": scenario_selection.get("mode_id"),
                "selected_preset_id": scenario_selection.get("preset_id"),
                "project_context_version": context.context_version,
                "project_context_snapshot": bound_context_snapshot,
                "project_mode": True,
                "advanced_reference_controls": advanced_reference_controls,
                "doc90_advanced_reference_controls": bool(advanced_reference_controls),
                "commerce_profile_present": commerce_profile is not None,
                "ecommerce_text_to_image_fallback": ecommerce_text_to_image_fallback,
                "has_product_reference": bool(uploaded_asset_ids) if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID else None,
                "ecommerce_slot_lineage": status.metadata.get("ecommerce_slot_lineage"),
                **(
                    {
                        "current_reference_binding_digest": current_reference_binding_digest,
                        "idempotency_key": idempotency_key,
                    }
                    if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID
                    else {}
                ),
                **({"supersedes_job_id": supersedes_job_id} if supersedes_job_id else {}),
                "photographer_profile_binding": (
                    photographer_profile_binding.model_dump(mode="json") if photographer_profile_binding is not None else None
                ),
            }
        )
        self._link_job(
            project,
            status.job_id,
            context,
            doc271_command_binding=doc271_command_binding if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID else None,
        )
        if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID:
            self._persist_ecommerce_slot_anchor(project, status)
        elif template_manifest.template_id == "photographer_template":
            self._persist_photography_role_anchor(project, status)
        self._append_timeline(
            project.project_id,
            TimelineItemType.JOB_CREATED,
            self._job_created_title(template_manifest),
            self._job_created_summary(template_manifest),
            job_id=status.job_id,
            metadata={
                "template_id": template_manifest.template_id,
                "scenario_pack_id": template_manifest.scenario_pack_id,
                "project_context_version": context.context_version,
                "advanced_reference_controls": advanced_reference_controls,
                "doc90_advanced_reference_controls": bool(advanced_reference_controls),
                "commerce_profile_present": commerce_profile is not None,
                "ecommerce_text_to_image_fallback": ecommerce_text_to_image_fallback,
                "has_product_reference": bool(uploaded_asset_ids) if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID else None,
                "ecommerce_slot_lineage": status.metadata.get("ecommerce_slot_lineage"),
            },
        )
        return status

    def create_ecommerce_slot_continuation(
        self,
        project_id: str,
        parent_job_id: str,
        slot_id: str,
        request: EcommerceSlotContinuationRequest | dict[str, Any],
    ) -> EcommerceSlotContinuationResponse:
        """Create one append-only E-Commerce slot child; generation stays separate."""

        project = self._require_project(project_id)
        self._ensure_project_job(project, parent_job_id)
        continuation_request = self._coerce_ecommerce_slot_continuation_request(request)
        clean_slot_id = str(slot_id or "").strip()
        anchor = self._require_ecommerce_slot_anchor(project, parent_job_id)
        parent_lineage = EcommerceSlotLineage.model_validate(anchor["lineage"])
        if parent_lineage.parent_slot_id and parent_lineage.parent_slot_id != clean_slot_id:
            raise EcommerceSlotContinuationError(
                "slot_continuation_not_supported",
                "A child continuation can only continue its own E-Commerce slot.",
            )
        root_anchor = self._require_ecommerce_slot_anchor(project, parent_lineage.root_job_id)
        declared_slots = [str(item).strip() for item in root_anchor.get("declared_slot_ids") or [] if str(item).strip()]
        if not clean_slot_id or clean_slot_id not in declared_slots:
            raise EcommerceSlotContinuationError(
                "slot_continuation_not_supported",
                "This E-Commerce slot is not declared by the parent job's frozen suite.",
            )
        evidence_ids = list(continuation_request.new_evidence_asset_ids)
        self._validate_continuation_evidence(project, evidence_ids)
        self._validate_new_continuation_evidence(anchor, evidence_ids)
        parent_plan = CapabilityActivationPlan.model_validate(anchor["frozen_capability_activation_plan"])
        frozen_plan, amendment, amendment_metadata = self._resolve_ecommerce_slot_plan(
            project=project,
            root_job_id=parent_lineage.root_job_id,
            slot_id=clean_slot_id,
            parent_anchor=anchor,
            parent_plan=parent_plan,
            evidence_ids=evidence_ids,
        )
        lineage_payload = EcommerceSlotLineage(
            root_job_id=parent_lineage.root_job_id,
            parent_job_id=parent_job_id,
            parent_slot_id=clean_slot_id,
            continuation_kind="ecommerce_slot",
            continuation_correction_note=continuation_request.correction_note,
            new_evidence_asset_ids=evidence_ids,
            capability_activation_plan_id=frozen_plan.plan_id,
            plan_amendment_id=amendment.amendment_id if amendment else None,
            created_at=_utc_now_iso(),
        )
        source = self._continuation_source(continuation_request.metadata)
        child_metadata = {
            "source": source,
            "ecommerce_slot_lineage": lineage_payload.model_dump(mode="json"),
            # A continuation is one revised provider image for the selected
            # opaque output ID.  This is quantity/lineage transport, not a
            # local creative slot recipe.
            "requested_image_count": 1,
            "capability_activation_plan": frozen_plan.model_dump(mode="json"),
            "capability_activation_plan_id": frozen_plan.plan_id,
            "capability_plan_reuse_source_job_id": parent_job_id,
            "capability_plan_reuse_source_snapshot": self._capability_plan_source_snapshot(
                parent_job_id,
                anchor,
            ),
            "continuation_evidence_asset_ids": evidence_ids,
            **amendment_metadata,
        }
        owner_user_id = self._positive_owner_id(dict(continuation_request.metadata or {}).get("veyra_user_id"))
        if owner_user_id is not None:
            child_metadata["veyra_user_id"] = owner_user_id
        if amendment is not None:
            child_metadata["capability_plan_amendment"] = amendment.model_dump(mode="json")
        child = self.create_project_job(
            project_id,
            {
                "template_id": ECOMMERCE_TEMPLATE_ID,
                "user_input": self._slot_continuation_instruction(
                    str(anchor["planning_request"].get("user_input") or project.user_goal),
                    clean_slot_id,
                    continuation_request.correction_note,
                ),
                "uploaded_asset_ids": self._continuation_product_evidence_ids(project, evidence_ids),
                "metadata": child_metadata,
            },
            _trusted_capability_continuation=True,
        )
        child_anchor = self._require_ecommerce_slot_anchor(project, child.job_id)
        child_lineage = EcommerceSlotLineage.model_validate(child_anchor["lineage"])
        delivery = self.resolve_ecommerce_slot_delivery(project_id, parent_lineage.root_job_id, clean_slot_id)
        route = self._ecommerce_slot_continuation_route(project_id, parent_job_id, clean_slot_id)
        return EcommerceSlotContinuationResponse(
            api_namespace=API_NAMESPACE,
            route=route,
            project_id=project_id,
            parent_job_id=parent_job_id,
            slot_id=clean_slot_id,
            child_job_id=child.job_id,
            child_status=str(child.status),
            lineage=child_lineage,
            delivery=delivery,
            metadata={
                "source": PROJECT_API_SOURCE,
                "generation_route": f"{API_NAMESPACE}/projects/{project_id}/jobs/{child.job_id}/generate",
                "append_only": True,
                "uses_shared_generation_review_retry": True,
                "plan_amendment_applied": amendment is not None,
                "plan_amendment_enabled": self._capability_plan_amendment_enabled(),
            },
        )

    def get_ecommerce_slot_delivery(
        self,
        project_id: str,
        root_job_id: str,
        slot_id: str,
    ) -> EcommerceSlotDeliveryResponse:
        return self.resolve_ecommerce_slot_delivery(project_id, root_job_id, slot_id)

    def resolve_ecommerce_slot_delivery(
        self,
        project_id: str,
        root_job_id: str,
        slot_id: str,
    ) -> EcommerceSlotDeliveryResponse:
        project = self._require_project(project_id)
        self._ensure_project_job(project, root_job_id)
        root_anchor = self._require_ecommerce_slot_anchor(project, root_job_id)
        root_lineage = EcommerceSlotLineage.model_validate(root_anchor["lineage"])
        clean_slot_id = str(slot_id or "").strip()
        declared_slots = [str(item).strip() for item in root_anchor.get("declared_slot_ids") or [] if str(item).strip()]
        if root_lineage.root_job_id != root_job_id or not clean_slot_id or clean_slot_id not in declared_slots:
            raise EcommerceSlotContinuationError(
                "slot_continuation_not_supported",
                "This job and slot do not expose an E-Commerce continuation delivery lineage.",
            )
        attempts: list[EcommerceSlotAttemptSummary] = []
        current_delivery: EcommerceSlotCurrentDelivery | None = None
        for job_id in project.job_ids:
            anchor = self._ecommerce_slot_anchor(project, job_id)
            if anchor is None:
                continue
            lineage = EcommerceSlotLineage.model_validate(anchor["lineage"])
            is_root_attempt = job_id == root_job_id
            if not is_root_attempt and (
                lineage.root_job_id != root_job_id or lineage.parent_slot_id != clean_slot_id
            ):
                continue
            status = self.product_service.get_job(job_id)
            candidates = self._slot_candidates(status, clean_slot_id, is_root_attempt=is_root_attempt)
            candidate_ids = [str(item.get("candidate_id") or "") for item in candidates if item.get("candidate_id")]
            output_ids = [str(item.get("output_id") or "") for item in candidates if item.get("output_id")]
            attempt = EcommerceSlotAttemptSummary(
                job_id=job_id,
                parent_job_id=lineage.parent_job_id,
                status=str(status.status),
                candidate_ids=candidate_ids,
                output_ids=output_ids,
                created_at=str(anchor.get("created_at") or "") or None,
                metadata={
                    "continuation_kind": lineage.continuation_kind,
                    "plan_amendment_id": lineage.plan_amendment_id,
                },
            )
            attempts.append(attempt)
            if status.status == ProductJobStatusValue.GENERATED and candidates:
                candidate = candidates[0]
                current_delivery = EcommerceSlotCurrentDelivery(
                    root_job_id=root_job_id,
                    slot_id=clean_slot_id,
                    job_id=job_id,
                    candidate_id=str(candidate["candidate_id"]),
                    asset_id=str(candidate.get("asset_id") or "") or None,
                    output_id=str(candidate.get("output_id") or "") or None,
                    preview_url=str(candidate.get("preview_url") or candidate.get("preview_uri") or "") or None,
                    download_url=str(candidate.get("download_url") or "") or None,
                    resolved_at=_utc_now_iso(),
                )
        if current_delivery is not None:
            for attempt in attempts:
                attempt.is_current_delivery = attempt.job_id == current_delivery.job_id
        route = self._ecommerce_slot_delivery_route(project_id, root_job_id, clean_slot_id)
        return EcommerceSlotDeliveryResponse(
            api_namespace=API_NAMESPACE,
            route=route,
            project_id=project_id,
            root_job_id=root_job_id,
            slot_id=clean_slot_id,
            current_delivery=current_delivery,
            attempts=attempts,
            metadata={
                "source": PROJECT_API_SOURCE,
                "append_only_history": True,
                "failed_or_blocked_children_preserve_previous_delivery": True,
            },
        )

    def create_photography_role_continuation(
        self,
        project_id: str,
        parent_job_id: str,
        role_id: str,
        request: PhotographyRoleContinuationRequest | dict[str, Any],
    ) -> PhotographyRoleContinuationResponse:
        """Append one user-directed continuation for a frozen Photography role."""

        project = self._require_project(project_id)
        self._ensure_project_job(project, parent_job_id)
        continuation_request = self._coerce_photography_role_continuation_request(request)
        clean_role_id = str(role_id or "").strip()
        anchor = self._require_photography_role_anchor(project, parent_job_id)
        parent_lineage = PhotographyRoleLineage.model_validate(anchor["lineage"])
        if parent_lineage.parent_role_id and parent_lineage.parent_role_id != clean_role_id:
            raise PhotographyRoleContinuationError(
                "photography_role_continuation_not_supported",
                "A Photography child continuation can only continue its own frozen role.",
            )
        root_anchor = self._require_photography_role_anchor(project, parent_lineage.root_job_id)
        declared_roles = self._declared_photography_roles(root_anchor)
        if not clean_role_id or clean_role_id not in declared_roles:
            raise PhotographyRoleContinuationError(
                "photography_role_continuation_not_supported",
                "This role is not declared by the parent professional-set contract.",
            )
        evidence_ids = list(continuation_request.new_reference_asset_ids)
        self._validate_photography_continuation_evidence(project, anchor, evidence_ids)
        module_continuation = self._plan_photography_module_continuation(
            anchor=anchor,
            role_id=clean_role_id,
            request=continuation_request,
            job_key=f"{parent_job_id}:{clean_role_id}:continuation",
        )
        parent_plan = CapabilityActivationPlan.model_validate(anchor["frozen_capability_activation_plan"])
        frozen_plan, amendment, amendment_metadata = self._resolve_photography_role_plan(
            project=project,
            root_job_id=parent_lineage.root_job_id,
            role_id=clean_role_id,
            parent_anchor=anchor,
            parent_plan=parent_plan,
            evidence_ids=evidence_ids,
        )
        child_specialized = self._photography_child_specialized_plan(
            anchor=anchor,
            role_id=clean_role_id,
            correction_note=continuation_request.correction_note,
            module_continuation=module_continuation.model_dump(mode="json"),
        )
        lineage_payload = PhotographyRoleLineage(
            root_job_id=parent_lineage.root_job_id,
            parent_job_id=parent_job_id,
            parent_role_id=clean_role_id,
            root_set_id=parent_lineage.root_set_id,
            continuation_kind="photography_role",
            continuation_correction_note=continuation_request.correction_note,
            new_reference_asset_ids=evidence_ids,
            capability_activation_plan_id=frozen_plan.plan_id,
            plan_amendment_id=amendment.amendment_id if amendment else None,
            created_at=_utc_now_iso(),
        )
        parent_request = dict(anchor["planning_request"])
        parent_metadata = dict(parent_request.get("metadata") or {})
        child_metadata = {
            "source": self._photography_continuation_source(continuation_request.metadata),
            "photographer_profile_binding": dict(parent_metadata["photographer_profile_binding"]),
            "specialized_scenario_plan": child_specialized,
            "photography_role_lineage": lineage_payload.model_dump(mode="json"),
            "capability_activation_plan": frozen_plan.model_dump(mode="json"),
            "capability_activation_plan_id": frozen_plan.plan_id,
            "capability_plan_reuse_source_job_id": parent_job_id,
            "capability_plan_reuse_source_snapshot": self._capability_plan_source_snapshot(
                parent_job_id,
                anchor,
            ),
            "continuation_reference_asset_ids": evidence_ids,
            **amendment_metadata,
        }
        if amendment is not None:
            child_metadata["capability_plan_amendment"] = amendment.model_dump(mode="json")
        owner_user_id = self._positive_owner_id(dict(continuation_request.metadata or {}).get("veyra_user_id"))
        if owner_user_id is not None:
            child_metadata["veyra_user_id"] = owner_user_id
        child = self.create_project_job(
            project_id,
            {
                "template_id": "photographer_template",
                "user_input": self._photography_role_continuation_instruction(
                    str(parent_request.get("user_input") or project.user_goal),
                    clean_role_id,
                    continuation_request.correction_note,
                ),
                "uploaded_asset_ids": evidence_ids,
                "metadata": child_metadata,
            },
            _trusted_photography_continuation=True,
        )
        child_anchor = self._require_photography_role_anchor(project, child.job_id)
        child_lineage = PhotographyRoleLineage.model_validate(child_anchor["lineage"])
        delivery = self.resolve_photography_role_delivery(
            project_id,
            parent_lineage.root_job_id,
            clean_role_id,
        )
        return PhotographyRoleContinuationResponse(
            api_namespace=API_NAMESPACE,
            route=self._photography_role_continuation_route(project_id, parent_job_id, clean_role_id),
            project_id=project_id,
            parent_job_id=parent_job_id,
            role_id=clean_role_id,
            child_job_id=child.job_id,
            child_status=str(child.status),
            lineage=child_lineage,
            delivery=delivery,
            metadata={
                "source": PROJECT_API_SOURCE,
                "generation_route": f"{API_NAMESPACE}/projects/{project_id}/jobs/{child.job_id}/generate",
                "append_only": True,
                "uses_shared_generation_review_retry": True,
                "plan_amendment_applied": amendment is not None,
                "plan_amendment_enabled": self._capability_plan_amendment_enabled(),
                "named_profile_reconfirmation_validated": True,
            },
        )

    def get_photography_role_delivery(
        self,
        project_id: str,
        root_job_id: str,
        role_id: str,
    ) -> PhotographyRoleDeliveryResponse:
        return self.resolve_photography_role_delivery(project_id, root_job_id, role_id)

    def resolve_photography_role_delivery(
        self,
        project_id: str,
        root_job_id: str,
        role_id: str,
    ) -> PhotographyRoleDeliveryResponse:
        project = self._require_project(project_id)
        self._ensure_project_job(project, root_job_id)
        root_anchor = self._require_photography_role_anchor(project, root_job_id)
        root_lineage = PhotographyRoleLineage.model_validate(root_anchor["lineage"])
        clean_role_id = str(role_id or "").strip()
        declared_roles = self._declared_photography_roles(root_anchor)
        if root_lineage.root_job_id != root_job_id or not clean_role_id or clean_role_id not in declared_roles:
            raise PhotographyRoleContinuationError(
                "photography_role_continuation_not_supported",
                "This job and role do not expose a Photography professional-set delivery lineage.",
            )
        attempts: list[PhotographyRoleAttemptSummary] = []
        current_delivery: PhotographyRoleCurrentDelivery | None = None
        for job_id in project.job_ids:
            anchor = self._photography_role_anchor(project, job_id)
            if anchor is None:
                continue
            lineage = PhotographyRoleLineage.model_validate(anchor["lineage"])
            is_root_attempt = job_id == root_job_id
            if not is_root_attempt and (
                lineage.root_job_id != root_job_id or lineage.parent_role_id != clean_role_id
            ):
                continue
            status = self.product_service.get_job(job_id)
            candidates = self._photography_role_candidates(status, clean_role_id, is_root_attempt=is_root_attempt)
            candidate_ids = [str(item.get("candidate_id") or "") for item in candidates if item.get("candidate_id")]
            output_ids = [str(item.get("output_id") or "") for item in candidates if item.get("output_id")]
            attempts.append(
                PhotographyRoleAttemptSummary(
                    job_id=job_id,
                    parent_job_id=lineage.parent_job_id,
                    status=str(status.status),
                    candidate_ids=candidate_ids,
                    output_ids=output_ids,
                    created_at=str(anchor.get("created_at") or "") or None,
                    metadata={
                        "continuation_kind": lineage.continuation_kind,
                        "plan_amendment_id": lineage.plan_amendment_id,
                    },
                )
            )
            if status.status == ProductJobStatusValue.GENERATED and candidates:
                candidate = candidates[0]
                current_delivery = PhotographyRoleCurrentDelivery(
                    root_job_id=root_job_id,
                    root_set_id=root_lineage.root_set_id,
                    role_id=clean_role_id,
                    job_id=job_id,
                    candidate_id=str(candidate["candidate_id"]),
                    asset_id=str(candidate.get("asset_id") or "") or None,
                    output_id=str(candidate.get("output_id") or "") or None,
                    preview_url=str(candidate.get("preview_url") or candidate.get("preview_uri") or "") or None,
                    download_url=str(candidate.get("download_url") or "") or None,
                    resolved_at=_utc_now_iso(),
                )
        if current_delivery is not None:
            for attempt in attempts:
                attempt.is_current_delivery = attempt.job_id == current_delivery.job_id
        return PhotographyRoleDeliveryResponse(
            api_namespace=API_NAMESPACE,
            route=self._photography_role_delivery_route(project_id, root_job_id, clean_role_id),
            project_id=project_id,
            root_job_id=root_job_id,
            root_set_id=root_lineage.root_set_id,
            role_id=clean_role_id,
            current_delivery=current_delivery,
            attempts=attempts,
            metadata={
                "source": PROJECT_API_SOURCE,
                "append_only_history": True,
                "failed_or_blocked_children_preserve_previous_delivery": True,
                "final_role_winner_only": True,
            },
        )

    def generate_project_job(self, project_id: str, job_id: str, request: dict[str, Any] | None = None) -> ProductJobStatus:
        project = self._require_project(project_id)
        self._ensure_project_job(project, job_id)
        template_id = self._template_id_for_project_job(project, job_id)
        payload = dict(request or {})
        metadata = dict(payload.get("metadata") or {})
        metadata.update({"project_id": project.project_id, "template_id": template_id, "project_mode": True})
        payload["metadata"] = metadata
        status = self.product_service.generate_job(job_id, payload)
        status.metadata.update({"project_id": project.project_id, "template_id": template_id, "project_mode": True})
        if status.status == ProductJobStatusValue.GENERATED:
            final_delivery = status.metadata.get("final_delivery") if isinstance(status.metadata, dict) else None
            final_delivery_withheld = (
                isinstance(final_delivery, dict)
                and bool(final_delivery.get("delivery_gate_applies"))
                and not bool(final_delivery.get("automatic_delivery_available"))
            )
            manual_confirmation_required = bool(
                isinstance(final_delivery, dict) and final_delivery.get("manual_confirmation_required")
            )
            self._append_timeline(
                project.project_id,
                TimelineItemType.JOB_GENERATED,
                (
                    "生成结果需要人工确认"
                    if manual_confirmation_required
                    else "生成结果未通过自动验收"
                    if final_delivery_withheld
                    else "生成了一组电商套图"
                    if template_id == ECOMMERCE_TEMPLATE_ID
                    else "生成了一组创意图"
                ),
                (
                    "真实像素已生成并完成审查，但需要人工确认；暂不作为最终交付。"
                    if manual_confirmation_required
                    else "真实像素已生成，但没有可自动交付的最终结果。"
                    if final_delivery_withheld
                    else "套图已生成，请先检查商品细节和卖点是否准确。"
                    if template_id == ECOMMERCE_TEMPLATE_ID
                    else "图片已生成，可以选中喜欢的结果作为后续风格参考。"
                ),
                job_id=job_id,
                asset_ids=[asset.asset_id for asset in status.asset_series],
                candidate_ids=[candidate.candidate_id for candidate in status.candidates],
                metadata={
                    "template_id": template_id,
                    "scenario_pack_id": status.scenario.scenario_id if status.scenario else None,
                    "final_delivery": dict(final_delivery) if isinstance(final_delivery, dict) else {},
                },
            )
            review_package = status.metadata.get("post_generation_review") if isinstance(status.metadata, dict) else None
            review_certification = status.metadata.get("review_certification") if isinstance(status.metadata, dict) else None
            if isinstance(review_package, dict):
                review_summary = self._post_generation_review_summary(review_package)
                self._append_timeline(
                    project.project_id,
                    TimelineItemType.VISUAL_REVIEW,
                    "V3 检查了生成结果",
                    review_summary,
                    job_id=job_id,
                    asset_ids=[asset.asset_id for asset in status.asset_series],
                    candidate_ids=[candidate.candidate_id for candidate in status.candidates],
                    metadata={
                        "template_id": template_id,
                        "inspection_count": review_package.get("metadata", {}).get("inspection_count"),
                        "recommended_output_ids": list(review_package.get("recommended_output_ids") or []),
                        "hidden_output_ids": list(review_package.get("hidden_output_ids") or []),
                        "review_certification": review_certification if isinstance(review_certification, dict) else {},
                        "final_delivery": dict(final_delivery) if isinstance(final_delivery, dict) else {},
                    },
                )
            retry_summary = status.metadata.get("visual_auto_retry") if isinstance(status.metadata, dict) else None
            if isinstance(retry_summary, dict) and int(retry_summary.get("executed_count") or 0) > 0:
                self._append_timeline(
                    project.project_id,
                    TimelineItemType.VISUAL_RETRY,
                    "V3 自动补做了一次",
                    "发现可修复问题后，V3 已保留原图，并追加了一组更干净的结果。",
                    job_id=job_id,
                    asset_ids=[asset.asset_id for asset in status.asset_series],
                    candidate_ids=[candidate.candidate_id for candidate in status.candidates],
                    metadata={
                        "template_id": template_id,
                        "executed_count": retry_summary.get("executed_count"),
                        "max_attempts": retry_summary.get("max_attempts"),
                    },
                )
        elif status.status in {ProductJobStatusValue.BLOCKED, ProductJobStatusValue.FAILED}:
            provider_retry = status.metadata.get("provider_failure_retry") if isinstance(status.metadata, dict) else None
            provider_execution = status.metadata.get("provider_execution") if isinstance(status.metadata, dict) else None
            specialized_execution = (
                status.metadata.get("specialized_execution_summary")
                if isinstance(status.metadata, dict)
                else None
            )
            review_certification = (
                status.metadata.get("review_certification")
                if isinstance(status.metadata, dict)
                else None
            )
            incomplete_specialized_set = (
                isinstance(specialized_execution, dict)
                and str(specialized_execution.get("status") or "").lower() == "incomplete"
            )
            final_delivery_withheld = bool(
                isinstance(specialized_execution, dict) and specialized_execution.get("final_delivery_withheld")
            )
            if isinstance(provider_retry, dict) and int(provider_retry.get("executed_count") or 0) > 0:
                self._append_timeline(
                    project.project_id,
                    TimelineItemType.PROVIDER_RETRY,
                    "V3 已自动换线重试",
                    "第一次生图没有成功，V3 已重新发起一次生成请求。",
                    job_id=job_id,
                    metadata={
                        "template_id": template_id,
                        "executed_count": provider_retry.get("executed_count"),
                        "max_attempts": provider_retry.get("max_attempts"),
                        "fresh_upstream_requests": provider_retry.get("fresh_upstream_requests"),
                        "final_status": provider_retry.get("final_status"),
                    },
                )
            self._append_timeline(
                project.project_id,
                TimelineItemType.JOB_BLOCKED,
                (
                    "摄影专业套图未完整生成"
                    if incomplete_specialized_set
                    else "摄影结果需要人工确认"
                    if isinstance(review_certification, dict)
                    and review_certification.get("state") == "manual_confirmation_required"
                    else "摄影结果未通过自动认证"
                    if final_delivery_withheld
                    else "本次没有生成图片"
                ),
                (
                    self._incomplete_specialized_set_summary(specialized_execution)
                    if incomplete_specialized_set
                    else self._review_certification_summary(review_certification)
                    if isinstance(review_certification, dict)
                    else self._blocked_generation_summary(status)
                ),
                job_id=job_id,
                metadata={
                    "template_id": template_id,
                    "status": str(status.status),
                    "warnings": list(status.warnings or [])[:3],
                    "provider_failure_retry": provider_retry if isinstance(provider_retry, dict) else {},
                    "provider_execution": provider_execution if isinstance(provider_execution, dict) else {},
                    "specialized_execution_summary": specialized_execution if final_delivery_withheld else {},
                    "review_certification": review_certification if isinstance(review_certification, dict) else {},
                    "normal_project_delivery_withheld": final_delivery_withheld,
                },
            )
        return status

    def mark_project_job_generating(
        self,
        project_id: str,
        job_id: str,
        *,
        background_attempt_id: str | None = None,
        background_timeout_seconds: float | None = None,
        background_timeout_owner: str | None = None,
        background_runtime_id: str | None = None,
    ) -> ProductJobStatus:
        """Mark a queued project job before the web layer releases its worker."""

        project = self._require_project(project_id)
        self._ensure_project_job(project, job_id)
        return self.product_service.mark_job_generating(
            job_id,
            background_attempt_id=background_attempt_id,
            background_timeout_seconds=background_timeout_seconds,
            background_timeout_owner=background_timeout_owner,
            background_runtime_id=background_runtime_id,
        )

    def mark_project_job_generation_timed_out(
        self,
        project_id: str,
        job_id: str,
        *,
        background_attempt_id: str,
        timeout_seconds: float,
    ) -> ProductJobStatus:
        """Persist one terminal timeout without permitting a late worker delivery."""

        project = self._require_project(project_id)
        self._ensure_project_job(project, job_id)
        status = self.product_service.mark_job_generation_timed_out(
            job_id,
            background_attempt_id=background_attempt_id,
            timeout_seconds=timeout_seconds,
        )
        timeout_metadata = status.metadata.get("generation_lifecycle_timeout") if isinstance(status.metadata, dict) else None
        if isinstance(timeout_metadata, dict) and timeout_metadata.get("background_attempt_id") == background_attempt_id:
            self._append_timeline(
                project.project_id,
                TimelineItemType.JOB_BLOCKED,
                "本次没有生成图片",
                "上游生图在总等待时间内没有返回终态，本次已安全结束，不会自动重复提交。",
                job_id=job_id,
                metadata={
                    "template_id": self._template_id_for_project_job(project, job_id),
                    "timeout_seconds": timeout_metadata.get("timeout_seconds"),
                    "timeout_owner": timeout_metadata.get("owner"),
                    "background_attempt_id": background_attempt_id,
                },
            )
        return status

    def mark_project_job_generation_worker_failed(
        self,
        project_id: str,
        job_id: str,
        *,
        background_attempt_id: str,
        failure_code: str,
    ) -> ProductJobStatus:
        """Project-facing terminal closure for a local background worker error."""

        project = self._require_project(project_id)
        self._ensure_project_job(project, job_id)
        previous = self.product_service.get_job(job_id)
        previous_failure = (
            previous.metadata.get("generation_lifecycle_failure")
            if isinstance(previous.metadata, dict)
            else None
        )
        status = self.product_service.mark_job_generation_worker_failed(
            job_id,
            background_attempt_id=background_attempt_id,
            failure_code=failure_code,
        )
        failure_metadata = status.metadata.get("generation_lifecycle_failure") if isinstance(status.metadata, dict) else None
        if (
            not isinstance(previous_failure, dict)
            and isinstance(failure_metadata, dict)
            and failure_metadata.get("background_attempt_id") == background_attempt_id
        ):
            self._append_timeline(
                project.project_id,
                TimelineItemType.JOB_BLOCKED,
                "Generation request ended before image delivery",
                "V3 closed this background attempt safely and did not replay an image request automatically.",
                job_id=job_id,
                metadata={
                    "template_id": self._template_id_for_project_job(project, job_id),
                    "failure_code": failure_metadata.get("failure_code"),
                    "failure_owner": failure_metadata.get("owner"),
                    "background_attempt_id": background_attempt_id,
                },
            )
        return status

    def _blocked_generation_summary(self, status: ProductJobStatus) -> str:
        warnings = [str(item).strip() for item in (status.warnings or []) if str(item).strip()]
        joined = " ".join(warnings).lower()
        if any(token in joined for token in ("timeout", "timed out", "gateway", "502", "503", "504", "could not be downloaded")):
            return "上游生图暂时超时，本次没有生成图片。项目已保留，可以稍后重新生成。"
        if any(token in joined for token in ("api key", "not configured", "insufficient", "policy", "safety")):
            return "生成配置或策略暂时不满足要求，本次没有生成图片。项目已保留。"
        return "本次生成没有拿到可用图片。项目已保留，可以稍后重新生成。"

    @staticmethod
    def _incomplete_specialized_set_summary(execution: dict[str, Any]) -> str:
        missing = [str(item).strip() for item in execution.get("missing_role_keys", []) if str(item).strip()]
        if missing:
            return f"已保留已完成角色的追加历史，但不会把不完整套图当作单张交付。未完成角色：{', '.join(missing)}。"
        return "已保留执行诊断，但不会把不完整的专业套图当作单张交付。"

    def select_project_job(
        self,
        project_id: str,
        job_id: str,
        request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        project = self._require_project(project_id)
        self._ensure_project_job(project, job_id)
        template_id = self._template_id_for_project_job(project, job_id)
        payload = dict(request or {})
        payload["apply_memory_update"] = False
        metadata = dict(payload.get("metadata") or {})
        metadata.update({"project_id": project.project_id, "template_id": template_id, "project_mode": True})
        payload["metadata"] = metadata
        current_status = self.product_service.get_job(job_id)
        if current_status.status in {ProductJobStatusValue.GENERATING, ProductJobStatusValue.FINALIZING}:
            return self._selection_hold_response(
                project,
                template_id=template_id,
                status=current_status,
                reason="finalization_pending",
                message="图片仍在完成审查和交付收尾，暂时不能选作后续参考。",
            )
        preflight_refs, unresolved_refs = self._resolved_output_refs_for_status(
            project,
            current_status,
            selected_candidate_id=str(payload.get("selected_candidate_id") or "").strip() or None,
            selected_asset_id=str(payload.get("selected_asset_id") or "").strip() or None,
        )
        if not preflight_refs:
            return self._selection_hold_response(
                project,
                template_id=template_id,
                status=current_status,
                reason="output_unavailable",
                message="这张图的真实输出还不能安全读取，因此不会用其它图片替代它继续生成。",
                unresolved_refs=unresolved_refs,
            )
        if current_status.status == ProductJobStatusValue.GENERATED and (
            current_status.metadata.get("restored_from_output_store")
            or current_status.metadata.get("partial_generation_recovery")
        ):
            # A partial recovery is a durable real output, even though the
            # append-only job record remains blocked for the later failed role.
            # Select exactly that output; never fabricate a candidate from the
            # unfinished role.
            selected = self._selection_from_restored_status(current_status, payload)
        else:
            selected = self.product_service.select_result(job_id, payload)
            if selected.status == ProductJobStatusValue.NOT_FOUND:
                restored_status = self.product_service.get_job(job_id)
                if restored_status.status == ProductJobStatusValue.GENERATED:
                    selected = self._selection_from_restored_status(restored_status, payload)
        refs, unresolved_refs = self._output_refs_from_selection(project, selected)
        if not refs:
            return self._selection_hold_response(
                project,
                template_id=template_id,
                status=selected.job_status,
                reason="output_unavailable",
                message="这张图的真实输出还不能安全读取，因此不会用其它图片替代它继续生成。",
                unresolved_refs=unresolved_refs,
            )
        existing_ref_ids = {ref.output_ref_id for ref in project.selected_output_refs}
        project.selected_output_refs.extend([ref for ref in refs if ref.output_ref_id not in existing_ref_ids])
        now = _utc_now_iso()
        for ref in refs:
            self._set_output_state(project, ref, ProjectOutputSelectionStateValue.SELECTED, now)
            self._upsert_generated_reference(project, ref, now)
        self._refresh_project_context(project)
        self._append_timeline(
            project.project_id,
            TimelineItemType.CANDIDATE_SELECTED,
            "选中了后续参考",
            "已选结果会作为本项目后续风格参考，不会自动写入品牌记忆。",
            job_id=job_id,
            asset_ids=selected.selected_result.selected_asset_ids,
            candidate_ids=selected.selected_result.selected_candidate_ids,
            selected_output_refs=refs,
            metadata={"brand_memory_auto_applied": False},
        )
        return {
            **selected.model_dump(mode="json"),
            "project": project.model_dump(mode="json"),
            "context": project.latest_context.model_dump(mode="json") if project.latest_context else None,
            "metadata": {
                **selected.metadata,
                "project_id": project.project_id,
                "template_id": template_id,
                "project_mode": True,
                "brand_memory_auto_applied": False,
                "continuation_available": True,
                "project_outputs": self._project_output_items(project, limit=60),
            },
        }

    def _selection_from_restored_status(
        self,
        status: ProductJobStatus,
        request_payload: dict[str, Any],
    ) -> SelectionResponse:
        selected_candidate_id = str(request_payload.get("selected_candidate_id") or "").strip()
        selected_asset_id = str(request_payload.get("selected_asset_id") or "").strip()
        candidates = list(status.candidates)
        assets = list(status.asset_series)
        if selected_candidate_id:
            candidates = [candidate for candidate in candidates if candidate.candidate_id == selected_candidate_id]
            candidate_asset_ids = {candidate.asset_id for candidate in candidates}
            assets = [asset for asset in assets if asset.asset_id in candidate_asset_ids]
        elif selected_asset_id:
            assets = [asset for asset in assets if asset.asset_id == selected_asset_id]
            asset_candidate_ids = {asset.selected_candidate_id for asset in assets if asset.selected_candidate_id}
            candidates = [
                candidate
                for candidate in candidates
                if candidate.asset_id == selected_asset_id
                or (asset_candidate_ids and candidate.candidate_id in asset_candidate_ids)
            ]
        selected_result = SelectedResult(
            selected_candidate_ids=[candidate.candidate_id for candidate in candidates if candidate.candidate_id],
            selected_asset_ids=[asset.asset_id for asset in assets if asset.asset_id],
            asset_pack_id=status.asset_pack_id,
            memory_update_applied=False,
            metadata={
                "selection_status": "selected_from_restored_outputs",
                "source": PROJECT_API_SOURCE,
                "restored_from_output_store": True,
                "apply_memory_update_requested": False,
            },
        )
        restored_status = status.model_copy(
            update={
                "status": ProductJobStatusValue.SELECTED,
                "selected_result": selected_result,
                "metadata": {
                    **dict(status.metadata or {}),
                    "selected_from_restored_outputs": True,
                },
            },
            deep=True,
        )
        return SelectionResponse(
            job_id=status.job_id,
            status=ProductJobStatusValue.SELECTED,
            selected_result=selected_result,
            job_status=restored_status,
            warnings=list(status.warnings),
            metadata={
                "source": PROJECT_API_SOURCE,
                "project_mode": True,
                "restored_from_output_store": True,
            },
        )

    def template_cards(self) -> list[TemplateCard]:
        return self.template_registry.list_cards()

    def _coerce_ecommerce_slot_continuation_request(
        self,
        request: EcommerceSlotContinuationRequest | dict[str, Any],
    ) -> EcommerceSlotContinuationRequest:
        if isinstance(request, EcommerceSlotContinuationRequest):
            return request
        return EcommerceSlotContinuationRequest.model_validate(request)

    def _persist_ecommerce_slot_anchor(self, project: ProjectRecord, status: ProductJobStatus) -> None:
        record = self.product_service.get_job_record(status.job_id)
        if record is None:
            return
        request_metadata = dict(record.request.metadata or {})
        lineage = request_metadata.get("ecommerce_slot_lineage")
        plan = request_metadata.get("capability_activation_plan")
        if not isinstance(lineage, dict) or not isinstance(plan, dict):
            return
        parsed_lineage = EcommerceSlotLineage.model_validate(lineage)
        CapabilityActivationPlan.model_validate(plan)
        anchors = self._ecommerce_slot_anchors(project)
        declared_slots = self._declared_ecommerce_slots(status)
        if parsed_lineage.root_job_id != status.job_id:
            root_anchor = anchors.get(parsed_lineage.root_job_id) or {}
            declared_slots = [
                str(item).strip()
                for item in root_anchor.get("declared_slot_ids") or []
                if str(item).strip()
            ]
        anchors[status.job_id] = {
            "lineage": parsed_lineage.model_dump(mode="json"),
            "frozen_capability_activation_plan": plan,
            "planning_request": record.request.model_dump(mode="json"),
            "declared_slot_ids": declared_slots,
            "created_at": record.created_at,
        }
        project.metadata = {
            **dict(project.metadata or {}),
            "ecommerce_slot_lineage_records": anchors,
        }
        project.updated_at = _utc_now_iso()
        self.project_store.save_project(project)

    def _coerce_photography_role_continuation_request(
        self,
        request: PhotographyRoleContinuationRequest | dict[str, Any],
    ) -> PhotographyRoleContinuationRequest:
        if isinstance(request, PhotographyRoleContinuationRequest):
            return request
        return PhotographyRoleContinuationRequest.model_validate(request)

    def _persist_photography_role_anchor(self, project: ProjectRecord, status: ProductJobStatus) -> None:
        """Persist the immutable set plan needed for role-level lineage reads."""

        record = self.product_service.get_job_record(status.job_id)
        if record is None:
            return
        request_metadata = dict(record.request.metadata or {})
        lineage = request_metadata.get("photography_role_lineage")
        plan = request_metadata.get("capability_activation_plan")
        specialized = request_metadata.get("specialized_scenario_plan")
        if not isinstance(lineage, dict) or not isinstance(plan, dict) or not isinstance(specialized, dict):
            return
        parsed_lineage = PhotographyRoleLineage.model_validate(lineage)
        CapabilityActivationPlan.model_validate(plan)
        execution = specialized.get("execution_plan")
        if not isinstance(execution, dict):
            return
        anchors = self._photography_role_anchors(project)
        declared_roles = self._declared_photography_roles_from_execution(execution)
        if parsed_lineage.root_job_id != status.job_id:
            root_anchor = anchors.get(parsed_lineage.root_job_id) or {}
            declared_roles = [
                str(item).strip()
                for item in root_anchor.get("declared_role_ids") or []
                if str(item).strip()
            ]
        anchors[status.job_id] = {
            "lineage": parsed_lineage.model_dump(mode="json"),
            "frozen_capability_activation_plan": plan,
            "specialized_scenario_plan": specialized,
            "planning_request": record.request.model_dump(mode="json"),
            "declared_role_ids": declared_roles,
            "created_at": record.created_at,
        }
        project.metadata = {
            **dict(project.metadata or {}),
            "photography_role_lineage_records": anchors,
        }
        project.updated_at = _utc_now_iso()
        self.project_store.save_project(project)

    def _photography_role_anchors(self, project: ProjectRecord) -> dict[str, dict[str, Any]]:
        raw = dict(project.metadata or {}).get("photography_role_lineage_records")
        if not isinstance(raw, dict):
            return {}
        return {
            str(job_id): dict(payload)
            for job_id, payload in raw.items()
            if isinstance(payload, dict)
        }

    def _photography_role_anchor(self, project: ProjectRecord, job_id: str) -> dict[str, Any] | None:
        return self._photography_role_anchors(project).get(job_id)

    def _require_photography_role_anchor(self, project: ProjectRecord, job_id: str) -> dict[str, Any]:
        anchor = self._photography_role_anchor(project, job_id)
        if anchor is None:
            raise PhotographyRoleContinuationError(
                "photography_role_continuation_not_supported",
                "This historical or non-Photography job has no readable professional-set continuation lineage.",
            )
        required = ("lineage", "frozen_capability_activation_plan", "specialized_scenario_plan", "planning_request")
        if any(not isinstance(anchor.get(key), dict) for key in required):
            raise PhotographyRoleContinuationError(
                "photography_role_continuation_not_supported",
                "This Photography job has incomplete professional-set continuation lineage.",
            )
        return anchor

    def _declared_photography_roles(self, root_anchor: dict[str, Any]) -> list[str]:
        return [
            str(item).strip()
            for item in root_anchor.get("declared_role_ids") or []
            if str(item).strip()
        ]

    def _declared_photography_roles_from_execution(self, execution: dict[str, Any]) -> list[str]:
        recipes = execution.get("role_recipes")
        if not isinstance(recipes, list):
            return []
        return list(
            dict.fromkeys(
                str(item.get("role_key") or "").strip()
                for item in recipes
                if isinstance(item, dict) and str(item.get("role_key") or "").strip()
            )
        )

    def _validate_photography_continuation_evidence(
        self,
        project: ProjectRecord,
        parent_anchor: dict[str, Any],
        evidence_ids: list[str],
    ) -> None:
        if not evidence_ids:
            return
        authorized = set(self._project_asset_ids(project)) | set(self._project_output_reference_ids(project))
        unknown = [item for item in evidence_ids if item not in authorized]
        if unknown:
            raise PhotographyRoleContinuationError(
                "invalid_photography_continuation_evidence",
                "New reference evidence must already be an authorized project asset or selected output.",
                status_code=400,
            )
        planning_request = dict(parent_anchor.get("planning_request") or {})
        parent_metadata = dict(planning_request.get("metadata") or {})
        parent_evidence = {
            str(item).strip()
            for item in [
                *list(planning_request.get("uploaded_asset_ids") or []),
                *list(parent_metadata.get("continuation_reference_asset_ids") or []),
            ]
            if str(item).strip()
        }
        if any(item in parent_evidence for item in evidence_ids):
            raise PhotographyRoleContinuationError(
                "invalid_photography_continuation_evidence",
                "A new-evidence continuation must add reference evidence not already present in its parent lineage.",
                status_code=400,
            )

    def _plan_photography_module_continuation(
        self,
        *,
        anchor: dict[str, Any],
        role_id: str,
        request: PhotographyRoleContinuationRequest,
        job_key: str,
    ):
        specialized = dict(anchor["specialized_scenario_plan"])
        metadata = dict(specialized.get("metadata") or {})
        raw_output = metadata.get("photography_pack_output")
        if not isinstance(raw_output, dict):
            raise PhotographyRoleContinuationError(
                "photography_role_continuation_not_supported",
                "The frozen Photography planning output is unavailable for continuation validation.",
            )
        try:
            parent_output = PhotographyPackOutput.model_validate(raw_output)
            execution = dict(specialized.get("execution_plan") or {})
            recipe = next(
                (
                    item
                    for item in execution.get("role_recipes", [])
                    if isinstance(item, dict) and str(item.get("role_key") or "") == role_id
                ),
                None,
            )
            if not isinstance(recipe, dict):
                raise ValueError("photography_set_continuation_parent_role_mismatch")
            module_request = PhotographySetContinuationRequest(
                parent_shot_id=str(recipe.get("role_id") or ""),
                target_role=role_id,
                correction_note=request.correction_note,
                new_reference_asset_ids=list(request.new_reference_asset_ids),
                reconfirmed_profile_id=request.reconfirmed_profile_id,
                reconfirmed_profile_version=request.reconfirmed_profile_version,
                reconfirmed_technique_package_checksum=request.reconfirmed_technique_package_checksum,
                profile_selection_source=request.profile_selection_source,
            )
            return PhotographySetContinuationDirector().plan(
                parent_output=parent_output,
                profile_binding=PhotographerProfileBinding.model_validate(parent_output.profile_binding),
                request=module_request,
                job_key=job_key,
            )
        except ValueError as exc:
            raise PhotographyRoleContinuationError(
                "photography_role_profile_reconfirmation_failed",
                str(exc),
            ) from exc

    def _resolve_photography_role_plan(
        self,
        *,
        project: ProjectRecord,
        root_job_id: str,
        role_id: str,
        parent_anchor: dict[str, Any],
        parent_plan: CapabilityActivationPlan,
        evidence_ids: list[str],
    ) -> tuple[CapabilityActivationPlan, CapabilityPlanAmendment | None, dict[str, Any]]:
        if not evidence_ids:
            return parent_plan, None, {}
        preview_payload = dict(parent_anchor["planning_request"])
        preview_metadata = dict(preview_payload.get("metadata") or {})
        for key in (
            "capability_activation_plan",
            "capability_activation_plan_id",
            "capability_catalog_version",
            "capability_activation_mode",
            "capability_plan_amendment",
            "photographer_profile_binding",
            "specialized_scenario_plan",
            "specialized_scenario_plan_summary",
            "specialized_role_execution_plan",
            "photography_role_lineage",
            "continuation_reference_asset_ids",
        ):
            preview_metadata.pop(key, None)
        preview_metadata["continuation_new_reference_asset_ids"] = list(evidence_ids)
        preview_payload["metadata"] = preview_metadata
        binding = dict(parent_anchor["planning_request"].get("metadata") or {}).get("photographer_profile_binding")
        if isinstance(binding, dict):
            profile_id = str(binding.get("profile_id") or "").strip()
            if profile_id and profile_id != "general_photography":
                preview_payload["photographer_profile_id"] = profile_id
                preview_payload["photographer_profile_selection_source"] = "user_explicit_ui"
        preview_payload["scenario_selection"] = {
            "scenario_id": "photography",
            "mode_id": "professional_set",
            "parameters": {"delivery_mode": "professional_set"},
        }
        preview_payload["uploaded_asset_ids"] = list(
            dict.fromkeys([*list(preview_payload.get("uploaded_asset_ids") or []), *evidence_ids])
        )
        try:
            preview = self.product_service.preview_capability_activation(preview_payload)
            candidate_plan = CapabilityActivationPlan.model_validate(preview["capability_activation_plan"])
        except Exception as exc:
            raise PhotographyRoleContinuationError(
                "photography_role_plan_amendment_unavailable",
                "The new reference could not be negotiated through the shared high-fidelity capability path: "
                f"{str(exc)[:160]}",
            ) from exc
        if candidate_plan.template_id != parent_plan.template_id or candidate_plan.scenario_id != parent_plan.scenario_id:
            raise PhotographyRoleContinuationError(
                "photography_role_plan_amendment_invalid",
                "The proposed shared capability plan does not match the parent Photography job.",
            )
        if candidate_plan.dependency_order == parent_plan.dependency_order:
            return parent_plan, None, {}
        if not self._capability_plan_amendment_enabled():
            raise PhotographyRoleContinuationError(
                "photography_role_plan_amendment_disabled",
                "New evidence changes the shared capability plan, but controlled plan amendments are disabled.",
            )
        if self._photography_role_has_plan_amendment(project, root_job_id, role_id):
            raise PhotographyRoleContinuationError(
                "photography_role_plan_amendment_exhausted",
                "This professional-set role already used its one allowed capability-plan amendment.",
            )
        amendment = CapabilityPlanAmendment(
            amendment_id=stable_id(
                "photography_role_plan_amendment",
                root_job_id,
                role_id,
                parent_plan.plan_id,
                candidate_plan.plan_id,
                evidence_ids,
            ),
            original_plan_id=parent_plan.plan_id,
            amended_plan_id=candidate_plan.plan_id,
            evidence_ids=evidence_ids,
            reason_code="new_authorized_reference_changed_capability_plan",
        )
        return candidate_plan, amendment, {
            key: preview[key]
            for key in (
                "visual_task_profile",
                "capability_activation_intent",
                "capability_catalog_version",
                "capability_activation_mode",
            )
            if key in preview
        }

    def _photography_role_has_plan_amendment(self, project: ProjectRecord, root_job_id: str, role_id: str) -> bool:
        for anchor in self._photography_role_anchors(project).values():
            lineage = anchor.get("lineage")
            if not isinstance(lineage, dict):
                continue
            if (
                lineage.get("root_job_id") == root_job_id
                and lineage.get("parent_role_id") == role_id
                and lineage.get("plan_amendment_id")
            ):
                return True
        return False

    def _photography_child_specialized_plan(
        self,
        *,
        anchor: dict[str, Any],
        role_id: str,
        correction_note: str | None,
        module_continuation: dict[str, Any],
    ) -> dict[str, Any]:
        specialized = dict(anchor["specialized_scenario_plan"])
        execution = dict(specialized.get("execution_plan") or {})
        recipe = next(
            (
                dict(item)
                for item in execution.get("role_recipes", [])
                if isinstance(item, dict) and str(item.get("role_key") or "") == role_id
            ),
            None,
        )
        if recipe is None:
            raise PhotographyRoleContinuationError(
                "photography_role_continuation_not_supported",
                "The frozen professional-set role recipe is unavailable.",
            )
        # The role remains a structural lineage binding.  The child job's
        # explicit correction stays in user_input for a fresh remote-Brain
        # direction; never turn it into a local Photography prompt recipe.
        recipe["purpose"] = ""
        recipe["prompt_pressure"] = ""
        execution_metadata = dict(execution.get("metadata") or {})
        execution_metadata.update(
            {
                "role_continuation": True,
                "continuation_target_role": role_id,
                "module_continuation": module_continuation,
                "requested_delivery_count": 1,
            }
        )
        execution.update(
            {
                "plan_id": stable_id("photography_role_execution_child", execution.get("plan_id"), role_id, correction_note),
                "requested_image_count": 1,
                "role_recipes": [recipe],
                "prompt_additions": [],
                "negative_additions": [],
                "metadata": execution_metadata,
            }
        )
        safe_summary = dict(specialized.get("safe_summary") or {})
        safe_summary.update({"delivery_roles": [role_id], "role_continuation": True})
        specialized["requested_image_count"] = 1
        specialized["execution_plan"] = execution
        specialized["safe_summary"] = safe_summary
        return specialized

    def _photography_role_candidates(
        self,
        status: ProductJobStatus,
        role_id: str,
        *,
        is_root_attempt: bool,
    ) -> list[dict[str, Any]]:
        asset_metadata_by_candidate = {
            asset.selected_candidate_id: dict(asset.metadata or {})
            for asset in status.asset_series
            if asset.selected_candidate_id
        }
        candidates = [candidate.model_dump(mode="json") for candidate in status.candidates]
        matched = [
            candidate
            for candidate in candidates
            if str(
                dict(candidate.get("metadata") or {}).get("mode_role_key")
                or asset_metadata_by_candidate.get(candidate.get("candidate_id"), {}).get("asset_metadata", {}).get("mode_role_key")
                or asset_metadata_by_candidate.get(candidate.get("candidate_id"), {}).get("mode_role_key")
                or ""
            ).strip()
            == role_id
        ]
        if matched or is_root_attempt:
            return matched
        return candidates

    def _photography_continuation_source(self, metadata: dict[str, Any]) -> str:
        source = str(dict(metadata or {}).get("source") or "photography_workspace").strip()
        return source[:120] or "photography_workspace"

    def _photography_role_continuation_instruction(
        self,
        parent_instruction: str,
        role_id: str,
        correction_note: str | None,
    ) -> str:
        correction = f" User correction: {correction_note}" if correction_note else ""
        return (
            f"{parent_instruction}\n\n"
            f"Photography professional-set continuation: regenerate only the frozen '{role_id}' role."
            f" Preserve the parent profile binding, color/finish anchor, reference truth, and capability plan.{correction}"
        )

    def _photography_role_continuation_route(self, project_id: str, parent_job_id: str, role_id: str) -> str:
        return f"{API_NAMESPACE}/projects/{project_id}/jobs/{parent_job_id}/photography-roles/{role_id}/continuations"

    def _photography_role_delivery_route(self, project_id: str, root_job_id: str, role_id: str) -> str:
        return f"{API_NAMESPACE}/projects/{project_id}/jobs/{root_job_id}/photography-roles/{role_id}/delivery"

    def _selection_hold_response(
        self,
        project: ProjectRecord,
        *,
        template_id: str,
        status: ProductJobStatus,
        reason: str,
        message: str,
        unresolved_refs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Return an explicit hold rather than silently substituting a reference."""

        context = self._refresh_project_context(project)
        return {
            "job_id": status.job_id,
            "status": status.status.value if hasattr(status.status, "value") else str(status.status),
            "selected_result": {
                "selected_candidate_ids": [],
                "selected_asset_ids": [],
                "metadata": {"selection_status": "selection_held", "hold_reason": reason},
            },
            "job_status": status.model_dump(mode="json"),
            "warnings": [message],
            "project": project.model_dump(mode="json"),
            "context": context.model_dump(mode="json"),
            "metadata": {
                "source": PROJECT_API_SOURCE,
                "project_id": project.project_id,
                "template_id": template_id,
                "project_mode": True,
                "selection_held": True,
                "continuation_available": False,
                "hold_reason": reason,
                "unresolved_selected_outputs": list(unresolved_refs or []),
                "project_outputs": self._project_output_items(project, limit=60),
            },
        }
    def _ecommerce_slot_anchors(self, project: ProjectRecord) -> dict[str, dict[str, Any]]:
        raw = dict(project.metadata or {}).get("ecommerce_slot_lineage_records")
        if not isinstance(raw, dict):
            return {}
        anchors: dict[str, dict[str, Any]] = {}
        for job_id, payload in raw.items():
            if isinstance(payload, dict):
                anchors[str(job_id)] = dict(payload)
        return anchors

    def _ecommerce_slot_anchor(self, project: ProjectRecord, job_id: str) -> dict[str, Any] | None:
        return self._ecommerce_slot_anchors(project).get(job_id)

    def _require_ecommerce_slot_anchor(self, project: ProjectRecord, job_id: str) -> dict[str, Any]:
        anchor = self._ecommerce_slot_anchor(project, job_id)
        if anchor is None:
            raise EcommerceSlotContinuationError(
                "slot_continuation_not_supported",
                "This historical or non-E-Commerce job has no readable slot-continuation lineage.",
            )
        if not isinstance(anchor.get("lineage"), dict) or not isinstance(anchor.get("frozen_capability_activation_plan"), dict):
            raise EcommerceSlotContinuationError(
                "slot_continuation_not_supported",
                "This E-Commerce job has incomplete slot-continuation lineage.",
            )
        if not isinstance(anchor.get("planning_request"), dict):
            raise EcommerceSlotContinuationError(
                "slot_continuation_not_supported",
                "This E-Commerce job cannot safely reconstruct its continuation request.",
            )
        return anchor

    def _declared_ecommerce_slots(self, status: ProductJobStatus) -> list[str]:
        ecommerce = status.ecommerce
        if ecommerce is None:
            return []
        # New E-Commerce jobs have opaque, Brain-selected output IDs.  Keep
        # the historical recipe read only as a migration fallback so Doc105
        # continuation works without any fixed marketplace slot vocabulary.
        output_intents = ecommerce.remote_brain_output_intents or []
        declared = [
            str(intent.get("output_id") or intent.get("slot_id") or "").strip()
            for intent in output_intents
            if isinstance(intent, dict) and str(intent.get("output_id") or intent.get("slot_id") or "").strip()
        ]
        if declared:
            return list(dict.fromkeys(declared))
        recipes = ecommerce.image_recipes
        return list(
            dict.fromkeys(
                str(recipe.get("slot") or "").strip()
                for recipe in recipes
                if isinstance(recipe, dict) and str(recipe.get("slot") or "").strip()
            )
        )

    def _validate_continuation_evidence(self, project: ProjectRecord, evidence_ids: list[str]) -> None:
        authorized = set(self._project_asset_ids(project)) | set(self._project_output_reference_ids(project))
        unknown = [item for item in evidence_ids if item not in authorized]
        if unknown:
            raise EcommerceSlotContinuationError(
                "invalid_slot_continuation_evidence",
                "New evidence must already be an authorized project asset or selected output.",
                status_code=400,
            )

    def _validate_new_continuation_evidence(self, parent_anchor: dict[str, Any], evidence_ids: list[str]) -> None:
        if not evidence_ids:
            return
        planning_request = dict(parent_anchor.get("planning_request") or {})
        metadata = dict(planning_request.get("metadata") or {})
        parent_evidence = {
            str(item).strip()
            for item in [
                *list(planning_request.get("uploaded_asset_ids") or []),
                *list(metadata.get("continuation_evidence_asset_ids") or []),
            ]
            if str(item).strip()
        }
        if any(item in parent_evidence for item in evidence_ids):
            raise EcommerceSlotContinuationError(
                "invalid_slot_continuation_evidence",
                "A plan amendment requires evidence that was not already present in the parent continuation anchor.",
                status_code=400,
            )

    def _continuation_product_evidence_ids(self, project: ProjectRecord, evidence_ids: list[str]) -> list[str]:
        return [asset_id for asset_id in evidence_ids if self._is_ready_product_upload(asset_id)]

    @staticmethod
    def _capability_plan_source_snapshot(parent_job_id: str, anchor: dict[str, Any]) -> dict[str, Any]:
        """Carry the durable parent binding across a Project Mode restart.

        Product API's in-memory job store is deliberately replaceable.  The
        append-only Project anchor is the persisted continuation authority, so
        it transports the minimal source-plan proof for the internal Product
        API hand-off after a process restart.
        """

        planning_request = dict(anchor.get("planning_request") or {})
        metadata = dict(planning_request.get("metadata") or {})
        return {
            "job_id": parent_job_id,
            "capability_activation_plan": dict(anchor.get("frozen_capability_activation_plan") or {}),
            "capability_plan_provenance": dict(metadata.get("capability_plan_provenance") or {}),
        }

    def _capability_plan_amendment_enabled(self) -> bool:
        return os.getenv("V3_CAPABILITY_PLAN_AMENDMENT_ENABLED", "false").strip().lower() == "true"

    def _resolve_ecommerce_slot_plan(
        self,
        *,
        project: ProjectRecord,
        root_job_id: str,
        slot_id: str,
        parent_anchor: dict[str, Any],
        parent_plan: CapabilityActivationPlan,
        evidence_ids: list[str],
    ) -> tuple[CapabilityActivationPlan, CapabilityPlanAmendment | None, dict[str, Any]]:
        if not evidence_ids or not self._capability_plan_amendment_enabled():
            return parent_plan, None, {}
        if self._slot_has_plan_amendment(project, root_job_id, slot_id):
            raise EcommerceSlotContinuationError(
                "slot_plan_amendment_exhausted",
                "This root-job and slot lineage already contains its one allowed capability-plan amendment.",
            )
        preview_payload = dict(parent_anchor["planning_request"])
        preview_metadata = dict(preview_payload.get("metadata") or {})
        for key in (
            "capability_activation_plan",
            "capability_activation_plan_id",
            "capability_catalog_version",
            "capability_activation_mode",
            "capability_plan_amendment",
            "ecommerce_slot_lineage",
        ):
            preview_metadata.pop(key, None)
        preview_metadata["continuation_new_evidence_asset_ids"] = list(evidence_ids)
        preview_payload["metadata"] = preview_metadata
        preview_payload["uploaded_asset_ids"] = list(
            dict.fromkeys(
                [
                    *list(preview_payload.get("uploaded_asset_ids") or []),
                    *self._continuation_product_evidence_ids(project, evidence_ids),
                ]
            )
        )
        try:
            preview = self.product_service.preview_capability_activation(preview_payload)
            candidate_plan = CapabilityActivationPlan.model_validate(preview["capability_activation_plan"])
        except Exception as exc:
            raise EcommerceSlotContinuationError(
                "slot_plan_amendment_unavailable",
                f"The new evidence could not be safely evaluated for a capability-plan amendment: {str(exc)[:160]}",
            ) from exc
        if candidate_plan.template_id != parent_plan.template_id or candidate_plan.scenario_id != parent_plan.scenario_id:
            raise EcommerceSlotContinuationError(
                "slot_plan_amendment_invalid",
                "The proposed capability plan does not match the parent template and scenario.",
            )
        if candidate_plan.dependency_order == parent_plan.dependency_order:
            return parent_plan, None, {}
        amendment = CapabilityPlanAmendment(
            amendment_id=stable_id(
                "ecommerce_slot_plan_amendment",
                root_job_id,
                slot_id,
                parent_plan.plan_id,
                candidate_plan.plan_id,
                evidence_ids,
            ),
            original_plan_id=parent_plan.plan_id,
            amended_plan_id=candidate_plan.plan_id,
            evidence_ids=evidence_ids,
            reason_code="new_authorized_evidence_changed_capability_plan",
        )
        return candidate_plan, amendment, {
            key: preview[key]
            for key in (
                "visual_task_profile",
                "capability_activation_intent",
                "capability_catalog_version",
                "capability_activation_mode",
            )
            if key in preview
        }

    def _slot_has_plan_amendment(self, project: ProjectRecord, root_job_id: str, slot_id: str) -> bool:
        for anchor in self._ecommerce_slot_anchors(project).values():
            lineage = anchor.get("lineage")
            if not isinstance(lineage, dict):
                continue
            if (
                lineage.get("root_job_id") == root_job_id
                and lineage.get("parent_slot_id") == slot_id
                and lineage.get("plan_amendment_id")
            ):
                return True
        return False

    def _continuation_source(self, metadata: dict[str, Any]) -> str:
        source = str(dict(metadata or {}).get("source") or "ecommerce_workspace").strip()
        return source[:120] or "ecommerce_workspace"

    def _slot_continuation_instruction(self, parent_instruction: str, slot_id: str, correction_note: str | None) -> str:
        correction = f" User correction: {correction_note}" if correction_note else ""
        return (
            f"{parent_instruction}\n\n"
            f"E-Commerce slot continuation: regenerate only the declared '{slot_id}' role."
            f" Preserve the parent product facts, frozen capability plan, and suite identity.{correction}"
        )

    def _slot_candidates(
        self,
        status: ProductJobStatus,
        slot_id: str,
        *,
        is_root_attempt: bool,
    ) -> list[dict[str, Any]]:
        asset_metadata_by_candidate = {
            asset.selected_candidate_id: dict(asset.metadata or {})
            for asset in status.asset_series
            if asset.selected_candidate_id
        }
        candidates = [candidate.model_dump(mode="json") for candidate in status.candidates]
        matched = [
            candidate
            for candidate in candidates
            if str(
                dict(candidate.get("metadata") or {}).get("ecommerce_slot")
                or asset_metadata_by_candidate.get(candidate.get("candidate_id"), {}).get("ecommerce_slot")
                or ""
            ).strip()
            == slot_id
        ]
        if matched or is_root_attempt:
            return matched
        return candidates

    def _ecommerce_slot_continuation_route(self, project_id: str, parent_job_id: str, slot_id: str) -> str:
        return f"{API_NAMESPACE}/projects/{project_id}/jobs/{parent_job_id}/ecommerce-slots/{slot_id}/continuations"

    def _ecommerce_slot_delivery_route(self, project_id: str, root_job_id: str, slot_id: str) -> str:
        return f"{API_NAMESPACE}/projects/{project_id}/jobs/{root_job_id}/ecommerce-slots/{slot_id}/delivery"

    def _coerce_create_project_request(self, request: CreateProjectRequest | dict[str, Any]) -> CreateProjectRequest:
        if isinstance(request, CreateProjectRequest):
            return request
        return CreateProjectRequest.model_validate(request)

    def _coerce_create_project_job_request(
        self,
        request: CreateProjectJobRequest | dict[str, Any],
    ) -> CreateProjectJobRequest:
        if isinstance(request, CreateProjectJobRequest):
            return request
        return CreateProjectJobRequest.model_validate(request)

    def _coerce_reference_request(self, request: ProjectReferenceRequest | dict[str, Any]) -> ProjectReferenceRequest:
        if isinstance(request, ProjectReferenceRequest):
            return request
        return ProjectReferenceRequest.model_validate(request)

    def _coerce_reference_update_request(
        self,
        request: ProjectReferenceUpdateRequest | dict[str, Any],
    ) -> ProjectReferenceUpdateRequest:
        if isinstance(request, ProjectReferenceUpdateRequest):
            return request
        return ProjectReferenceUpdateRequest.model_validate(request)

    def _coerce_feedback_request(self, request: ProjectFeedbackRequest | dict[str, Any]) -> ProjectFeedbackRequest:
        if isinstance(request, ProjectFeedbackRequest):
            return request
        return ProjectFeedbackRequest.model_validate(request)

    def _coerce_output_state_request(
        self,
        request: ProjectOutputStateRequest | dict[str, Any],
    ) -> ProjectOutputStateRequest:
        if isinstance(request, ProjectOutputStateRequest):
            return request
        return ProjectOutputStateRequest.model_validate(request)

    def _coerce_brand_memory_proposal_request(
        self,
        request: ProjectBrandMemoryProposalRequest | dict[str, Any],
    ) -> ProjectBrandMemoryProposalRequest:
        if isinstance(request, ProjectBrandMemoryProposalRequest):
            return request
        return ProjectBrandMemoryProposalRequest.model_validate(request)

    def _coerce_brand_memory_confirm_request(
        self,
        request: ProjectBrandMemoryConfirmRequest | dict[str, Any],
    ) -> ProjectBrandMemoryConfirmRequest:
        if isinstance(request, ProjectBrandMemoryConfirmRequest):
            return request
        return ProjectBrandMemoryConfirmRequest.model_validate(request)

    def _ensure_active_template(self, template_id: str | None) -> ProjectTemplateManifest:
        return self.template_registry.ensure_can_create_project_job(template_id or GENERAL_TEMPLATE_ID)

    def _optional_ecommerce_product_reference(self, project: ProjectRecord, request: CreateProjectJobRequest) -> list[str]:
        return self._ecommerce_product_reference_asset_ids(project, request.uploaded_asset_ids)

    def _project_has_product_reference(self, project: ProjectRecord) -> bool:
        try:
            return bool(self._ecommerce_product_reference_asset_ids(project, []))
        except ValueError:
            return False

    def _classify_ecommerce_legacy_reference_ids(
        self,
        project: ProjectRecord,
        reference_ids: list[str],
    ) -> tuple[list[str], list[str], list[str], list[str]]:
        product_asset_ids: list[str] = []
        historical_output_ids: list[str] = []
        invalid_reference_ids: list[str] = []
        invalid_product_ids: list[str] = []
        for raw_id in reference_ids:
            clean_id = str(raw_id or "").strip()
            if not clean_id:
                continue
            if self._is_ready_product_upload(clean_id):
                product_asset_ids.append(clean_id)
                continue
            output_matches = self._ecommerce_generated_output_record_matches_for_identifier(clean_id)
            if len(output_matches) == 1:
                output_record = output_matches[0]
                if str(getattr(output_record, "job_id", "") or "").strip() in set(project.job_ids):
                    historical_output_ids.append(output_record.output_id)
                else:
                    invalid_reference_ids.append(clean_id)
                continue
            if len(output_matches) > 1 or clean_id.startswith("v3_output_"):
                invalid_reference_ids.append(clean_id)
                continue
            if self.product_service.get_uploaded_asset(clean_id) is not None:
                invalid_product_ids.append(clean_id)
                continue
            invalid_product_ids.append(clean_id)
        return (
            list(dict.fromkeys(product_asset_ids)),
            list(dict.fromkeys(historical_output_ids)),
            list(dict.fromkeys(invalid_reference_ids)),
            list(dict.fromkeys(invalid_product_ids)),
        )

    def _ecommerce_generated_output_record_matches_for_identifier(self, identifier: str) -> list[Any]:
        selector = str(identifier or "").strip()
        if not selector:
            return []
        output_store = getattr(self.product_service, "output_store", None)
        if output_store is None:
            return []
        record = output_store.get_output(selector)
        if record is not None:
            return [record]
        if selector.startswith("v3_output_"):
            return []
        try:
            records = output_store.list_outputs(limit=10000)
        except Exception:
            return []
        matches: list[Any] = []
        seen_output_ids: set[str] = set()
        for candidate in records:
            if selector not in {
                str(getattr(candidate, "asset_id", "") or ""),
                str(getattr(candidate, "candidate_id", "") or ""),
            }:
                continue
            output_id = str(getattr(candidate, "output_id", "") or "")
            if output_id in seen_output_ids:
                continue
            seen_output_ids.add(output_id)
            matches.append(candidate)
        return matches

    def _ecommerce_generated_output_record_for_identifier(self, identifier: str) -> Any | None:
        matches = self._ecommerce_generated_output_record_matches_for_identifier(identifier)
        if len(matches) != 1:
            return None
        return matches[0]

    def _require_ecommerce_selected_output_reference(
        self,
        project: ProjectRecord,
        request: ProjectReferenceRequest,
    ) -> Any:
        asset_selector = str(request.asset_ref_id or "").strip()
        output_selector = str(request.created_from_output_id or asset_selector or "").strip()
        job_selector = str(request.created_from_job_id or "").strip()
        if not output_selector:
            raise ValueError("continuation output reference invalid")
        record = self._ecommerce_generated_output_record_for_identifier(output_selector)
        if record is None and asset_selector and asset_selector != output_selector:
            record = self._ecommerce_generated_output_record_for_identifier(asset_selector)
        if record is None:
            raise ValueError("continuation output reference unavailable")
        record_output_id = str(getattr(record, "output_id", "") or "").strip()
        record_job_id = str(getattr(record, "job_id", "") or "").strip()
        if str(request.created_from_output_id or "").strip() and request.created_from_output_id != record_output_id:
            raise ValueError("continuation output reference mismatch")
        if asset_selector and asset_selector not in {
            record_output_id,
            str(getattr(record, "asset_id", "") or "").strip(),
            str(getattr(record, "candidate_id", "") or "").strip(),
        }:
            raise ValueError("continuation output reference mismatch")
        if not record_job_id or record_job_id not in set(project.job_ids):
            raise ValueError("continuation output reference project mismatch")
        if job_selector and job_selector != record_job_id:
            raise ValueError("continuation output reference project mismatch")
        file_path = Path(str(getattr(record, "file_path", "") or ""))
        if not file_path.is_file() or not self._doc265_output_source_integrity_id(record):
            raise ValueError("continuation output reference unavailable")
        return record

    def _ensure_ecommerce_selected_output_integrity(self, project: ProjectRecord) -> None:
        """Revalidate persisted Doc265 selections before a new command exists."""

        for reference in self._active_project_references(project):
            if reference.source_type != ProjectReferenceSourceType.GENERATED_SELECTED:
                continue
            try:
                self._validate_ecommerce_selected_output_reference(project, reference)
            except ValueError as exc:
                self._record_ecommerce_reference_channel_issue(
                    project,
                    issue_code="selected_continuation_output_integrity_invalid",
                    now=_utc_now_iso(),
                )
                raise ValueError("continuation output reference unavailable") from exc

    def _doc269_selected_continuation_admissions(
        self,
        project: ProjectRecord,
    ) -> list[dict[str, str]]:
        """Freeze only Doc265-validated selections for Doc269's renderer plan."""

        admissions: list[dict[str, str]] = []
        for reference in self._active_project_references(project):
            if reference.source_type != ProjectReferenceSourceType.GENERATED_SELECTED:
                continue
            if reference.use_policy != ProjectReferenceUsePolicy.STYLE:
                # Generated records on other existing Doc265 channels remain
                # history/review evidence. Only the explicit style selection
                # may enter Doc269's fifth physical renderer slot.
                continue
            record = self._validate_ecommerce_selected_output_reference(project, reference)
            digest = self._doc265_output_source_integrity_id(record)
            if not digest.startswith("sha256:"):
                raise ValueError("continuation output reference unavailable")
            admissions.append(
                {
                    "selection_authority": "doc265_project_mode",
                    "project_id": project.project_id,
                    "reference_id": reference.reference_id,
                    "output_id": str(record.output_id),
                    "source_job_id": str(record.job_id),
                    "candidate_id": str(record.candidate_id),
                    "project_job_ids": list(project.job_ids),
                    "content_sha256": digest.removeprefix("sha256:"),
                    "source_type": "generated_selected",
                    "use_policy": "style",
                    "role": "selected_continuation_reference",
                    "channel": "generated_selected",
                    "file_path": str(Path(str(record.file_path)).resolve()),
                }
            )
        if len(admissions) > 1:
            raise ValueError("continuation output reference unavailable")
        return admissions

    def _validate_ecommerce_selected_output_reference(
        self,
        project: ProjectRecord,
        reference: ProjectReferenceAsset,
    ) -> Any:
        output_store = getattr(self.product_service, "output_store", None)
        output_id = str(reference.created_from_output_id or "").strip()
        if output_store is None or not output_id:
            raise ValueError("selected output binding missing")
        record = output_store.get_output(output_id)
        if record is None:
            raise ValueError("selected output record missing")

        record_output_id = str(getattr(record, "output_id", "") or "").strip()
        record_job_id = str(getattr(record, "job_id", "") or "").strip()
        record_asset_id = str(getattr(record, "asset_id", "") or "").strip()
        record_candidate_id = str(getattr(record, "candidate_id", "") or "").strip()
        if (
            not record_output_id
            or output_id != record_output_id
            or str(reference.asset_ref_id or "").strip() != record_output_id
            or str(reference.created_from_job_id or "").strip() != record_job_id
            or not record_job_id
            or record_job_id not in set(project.job_ids)
        ):
            raise ValueError("selected output project binding mismatch")

        metadata = dict(reference.metadata or {})
        if metadata.get("canonical_output_binding") is not True:
            raise ValueError("selected output is not canonical")
        if any(
            str(metadata.get(key) or "").strip() != expected
            for key, expected in {
                "output_id": record_output_id,
                "asset_id": record_asset_id,
                "candidate_id": record_candidate_id,
            }.items()
        ):
            raise ValueError("selected output binding mismatch")

        source_integrity_id = str(metadata.get("source_integrity_id") or "").strip()
        actual_integrity_id = self._doc265_output_source_integrity_id(record)
        if not actual_integrity_id or source_integrity_id != actual_integrity_id:
            raise ValueError("selected output source integrity mismatch")
        return record

    def _record_ecommerce_reference_channel_issue(
        self,
        project: ProjectRecord,
        *,
        issue_code: str,
        now: str | None = None,
    ) -> None:
        metadata = dict(project.metadata or {})
        metadata["doc265_reference_channel_needs_attention"] = {
            "schema_version": "doc265_reference_channel_needs_attention_v1",
            "authority": "v3_project_mode",
            "issue_code": issue_code,
        }
        project.metadata = metadata
        project.updated_at = now or _utc_now_iso()
        self.project_store.save_project(project)

    def _clear_ecommerce_reference_channel_issue(self, project: ProjectRecord) -> None:
        metadata = dict(project.metadata or {})
        if "doc265_reference_channel_needs_attention" not in metadata:
            return
        metadata.pop("doc265_reference_channel_needs_attention", None)
        project.metadata = metadata
        project.updated_at = _utc_now_iso()
        self.project_store.save_project(project)

    def _ecommerce_product_reference_asset_ids(
        self,
        project: ProjectRecord,
        request_asset_ids: list[str],
    ) -> list[str]:
        product_asset_ids: list[str] = []
        invalid_request_ids: list[str] = []

        request_product_ids: list[str] = []
        for asset_id in request_asset_ids:
            clean_id = str(asset_id or "").strip()
            if not clean_id:
                continue
            if self._is_ready_product_upload(clean_id):
                request_product_ids.append(clean_id)
            else:
                invalid_request_ids.append(clean_id)

        # An active server-owned product association is evidence that the
        # project has product originals, even when its upload record is now
        # missing or has role/readiness drift. Preserve the ID so Product API
        # can close the exact admission before planning instead of silently
        # routing the project into text-to-image.
        product_asset_ids.extend(self._project_product_reference_candidates(project))
        product_asset_ids.extend(request_product_ids)

        if invalid_request_ids:
            raise ValueError("商品图还没有上传完成或不是有效的商品参考图，请重新上传商品图。")
        return self._dedupe_uploaded_asset_ids_by_content(product_asset_ids)

    def _project_product_reference_candidates(self, project: ProjectRecord) -> list[str]:
        active_product_references = [
            reference
            for reference in project.reference_assets
            if reference.status == ProjectReferenceStatus.ACTIVE
            and reference.source_type == ProjectReferenceSourceType.UPLOADED
            and reference.use_policy == ProjectReferenceUsePolicy.PRODUCT
        ]
        candidate_ids = [reference.asset_ref_id for reference in active_product_references]
        active_product_reference_ids = {
            reference.reference_id for reference in active_product_references
        }
        active_uploaded_reference_ids = {
            reference.reference_id
            for reference in project.reference_assets
            if reference.status == ProjectReferenceStatus.ACTIVE
            and reference.source_type == ProjectReferenceSourceType.UPLOADED
        }
        legacy_ids: list[str] = []
        for item in project.uploaded_asset_refs:
            asset_id = str(item.get("asset_id") or "").strip()
            if (
                not asset_id
                or str(item.get("role") or "").strip() not in PROJECT_PRODUCT_REFERENCE_ROLES
                or str(item.get("status") or "").strip().lower() == ProjectReferenceStatus.INACTIVE.value
            ):
                continue
            reference_id = str(item.get("reference_id") or "").strip()
            source = str(item.get("source") or "").strip().lower()
            if reference_id in active_product_reference_ids:
                legacy_ids.append(asset_id)
                continue
            # A legacy mirror may preserve a product association only while
            # the canonical active Project reference remains product truth.
            # It must never promote an active association whose current
            # server-owned policy has moved to another channel.
            if reference_id in active_uploaded_reference_ids:
                continue
            # Project-create selectors are only historical evidence when
            # their durable upload still exists. A fake selector must retain
            # the established no-product fallback; legacy mirrors without
            # that source remain server-owned associations and are preserved
            # for admission to close if their upload is gone.
            if source == "project_create" and self.product_service.get_uploaded_asset(asset_id) is None:
                continue
            legacy_ids.append(asset_id)
        return self._dedupe_uploaded_asset_ids_by_content(
            [asset_id for asset_id in dict.fromkeys([*candidate_ids, *legacy_ids]) if asset_id]
        )

    def _ensure_project_product_reference_integrity(self, project: ProjectRecord) -> None:
        changed = self._soft_suppress_duplicate_product_references(
            project,
            now=_utc_now_iso(),
            reason="content_sha256_duplicate_product_reference",
        )
        if changed:
            project.updated_at = _utc_now_iso()
            self.project_store.save_project(project)

    def _ecommerce_current_reference_binding_digest(self, project: ProjectRecord) -> str:
        """Hash current canonical project inputs without trusting request metadata."""

        sources: list[dict[str, str]] = []
        for reference in self._active_project_references(project):
            asset_id = str(reference.asset_ref_id or "").strip()
            if not asset_id:
                continue
            upload = self.product_service.get_uploaded_asset(asset_id)
            if reference.source_type == ProjectReferenceSourceType.UPLOADED:
                sources.append(
                    {
                        "asset_id": asset_id,
                        "source_type": reference.source_type.value,
                        "use_policy": reference.use_policy.value,
                        "content_sha256": self._uploaded_asset_content_sha256(upload) or "",
                    }
                )
            elif reference.source_type == ProjectReferenceSourceType.GENERATED_SELECTED:
                sources.append(
                    {
                        "asset_id": asset_id,
                        "source_type": reference.source_type.value,
                        "use_policy": reference.use_policy.value,
                        "content_sha256": str(
                            reference.metadata.get("source_integrity_id") or ""
                        ).strip(),
                    }
                )
        payload = {
            "schema_version": "doc263_current_reference_binding_v1",
            "project_id": project.project_id,
            "sources": sources,
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _doc271_current_source_binding(
        self,
        project: ProjectRecord,
        *,
        selected_continuation_admissions: list[dict[str, str]],
    ) -> dict[str, Any] | None:
        """Freeze every active source's actual authority facts for Doc271.

        This intentionally supplements, rather than changes, Doc263's compact
        product-reference digest.  It tracks the complete active pool and the
        persisted upload role that Doc263 normalizes into product truth.
        """

        selected_by_output = {
            str(item.get("output_id") or "").strip(): item
            for item in selected_continuation_admissions
            if isinstance(item, dict) and str(item.get("output_id") or "").strip()
        }
        sources: list[dict[str, Any]] = []
        ordered_references = sorted(
            self._active_project_references(project),
            key=lambda item: (
                item.source_type.value,
                str(item.asset_ref_id or ""),
                str(item.reference_id or ""),
            ),
        )
        for reference in ordered_references:
            asset_id = str(reference.asset_ref_id or "").strip()
            if not asset_id:
                raise ValueError("current project reference binding unavailable")
            if reference.source_type == ProjectReferenceSourceType.UPLOADED:
                upload = self.product_service.get_uploaded_asset(asset_id)
                path = Path(str(getattr(upload, "file_path", "") or "")) if upload else None
                actual_sha = self._file_content_fingerprint(path) if path is not None else ""
                if (
                    upload is None
                    or not actual_sha
                    or self._uploaded_asset_content_sha256(upload) != actual_sha
                ):
                    raise ValueError("current project reference binding unavailable")
                persisted_role = str(getattr(upload, "role", "") or "").strip()
                if not persisted_role:
                    raise ValueError("current project reference binding unavailable")
                reference_channel = (
                    "product_truth"
                    if reference.use_policy == ProjectReferenceUsePolicy.PRODUCT
                    else "uploaded_reference"
                )
                continuation_role = "not_applicable"
                continuation_channel = "not_applicable"
            elif reference.source_type == ProjectReferenceSourceType.GENERATED_SELECTED:
                admission = selected_by_output.get(asset_id)
                if not isinstance(admission, dict):
                    raise ValueError("current project reference binding unavailable")
                path = Path(str(admission.get("file_path") or ""))
                actual_sha = self._file_content_fingerprint(path)
                if not actual_sha or actual_sha != str(admission.get("content_sha256") or "").lower():
                    raise ValueError("current project reference binding unavailable")
                persisted_role = "generated_output"
                reference_channel = str(admission.get("channel") or "").strip()
                continuation_role = str(admission.get("role") or "").strip()
                continuation_channel = str(admission.get("channel") or "").strip()
                if reference_channel != "generated_selected" or continuation_role != "selected_continuation_reference":
                    raise ValueError("current project reference binding unavailable")
            else:
                raise ValueError("current project reference binding unavailable")
            sources.append(
                {
                    "ordinal": len(sources) + 1,
                    "asset_id": asset_id,
                    "content_sha256": actual_sha,
                    "source_type": reference.source_type.value,
                    "use_policy": reference.use_policy.value,
                    "persisted_role": persisted_role,
                    "reference_channel": reference_channel,
                    "continuation_role": continuation_role,
                    "continuation_channel": continuation_channel,
                }
            )
        # Existing no-product/text-only and history-only E-Commerce flows do
        # not form a Doc271 closure. They retain their established paths.
        if not sources:
            return None
        payload = {
            "schema_version": "doc271_current_project_source_binding_v1",
            "project_id": project.project_id,
            "sources": sources,
        }
        return {
            "schema_version": payload["schema_version"],
            "authority": "v3_project_mode",
            "project_id": project.project_id,
            "sources": sources,
            "source_binding_digest": self._doc271_digest(payload),
        }

    @staticmethod
    def _active_project_references(project: ProjectRecord) -> list[ProjectReferenceAsset]:
        return [
            reference
            for reference in project.reference_assets
            if reference.status == ProjectReferenceStatus.ACTIVE
        ]

    def _existing_ecommerce_command(
        self,
        project: ProjectRecord,
        *,
        idempotency_key: str,
        current_reference_binding_digest: str,
    ) -> ProductJobStatus | None:
        if not idempotency_key:
            return None
        for job_id in reversed(project.job_ids):
            record = self.product_service.get_job_record(job_id)
            if record is None:
                continue
            metadata = dict(record.request.metadata or {})
            if (
                str(metadata.get("idempotency_key") or "").strip() == idempotency_key
                and str(metadata.get("current_reference_binding_digest") or "").strip()
                == current_reference_binding_digest
            ):
                return self.product_service.get_job(job_id)
        return None

    @staticmethod
    def _doc271_digest(value: Any) -> str:
        return hashlib.sha256(
            json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _issue_doc271_project_goal_snapshot(
        self,
        project: ProjectRecord,
        *,
        template_id: str,
    ) -> dict[str, Any]:
        """Persist one append-only Project Mode goal fact before Job creation."""

        project_goal = str(project.user_goal or "").strip()
        if not project_goal:
            raise ValueError("doc271_project_goal_snapshot_invalid")
        command_attempt_id = f"attempt_{uuid4().hex}"
        snapshot_id = stable_id(
            "doc271_project_goal_snapshot",
            project.project_id,
            template_id,
            command_attempt_id,
        )
        payload = {
            "schema_version": "doc271_project_goal_snapshot_v1",
            "authority": "v3_project_mode",
            "snapshot_id": snapshot_id,
            "project_id": project.project_id,
            "template_id": template_id,
            "command_attempt_id": command_attempt_id,
            "project_goal": project_goal,
        }
        snapshot = {**payload, "snapshot_digest": self._doc271_digest(payload)}
        metadata = dict(project.metadata or {})
        snapshots = dict(metadata.get("doc271_project_goal_snapshots") or {})
        snapshots[snapshot_id] = snapshot
        project.metadata = {**metadata, "doc271_project_goal_snapshots": snapshots}
        project.updated_at = _utc_now_iso()
        self.project_store.save_project(project)
        return dict(snapshot)

    def _doc271_project_goal_snapshot(
        self,
        project_id: str,
        snapshot_id: str,
    ) -> dict[str, Any] | None:
        """Read a complete immutable snapshot without deriving current state."""

        project = self.project_store.get_project(str(project_id or "").strip())
        if project is None:
            return None
        snapshots = dict(project.metadata or {}).get("doc271_project_goal_snapshots")
        snapshot = snapshots.get(str(snapshot_id or "").strip()) if isinstance(snapshots, dict) else None
        if not isinstance(snapshot, dict):
            return None
        expected_keys = {
            "schema_version",
            "authority",
            "snapshot_id",
            "project_id",
            "template_id",
            "command_attempt_id",
            "project_goal",
            "snapshot_digest",
        }
        if set(snapshot) != expected_keys:
            return None
        payload = {key: snapshot[key] for key in expected_keys - {"snapshot_digest"}}
        if (
            snapshot.get("schema_version") != "doc271_project_goal_snapshot_v1"
            or snapshot.get("authority") != "v3_project_mode"
            or snapshot.get("project_id") != project.project_id
            or snapshot.get("snapshot_id") != snapshot_id
            or not str(snapshot.get("command_attempt_id") or "").strip()
            or not str(snapshot.get("project_goal") or "").strip()
            or snapshot.get("snapshot_digest") != self._doc271_digest(payload)
        ):
            return None
        return dict(snapshot)

    def _doc271_command_attempt_association(
        self,
        project_id: str,
        command_attempt_id: str,
    ) -> dict[str, Any] | None:
        project = self.project_store.get_project(str(project_id or "").strip())
        if project is None:
            return None
        raw = dict(project.metadata or {}).get("doc271_command_attempt_job_associations")
        association = raw.get(str(command_attempt_id or "").strip()) if isinstance(raw, dict) else None
        expected = {"authority", "project_id", "template_id", "command_attempt_id", "snapshot_id", "job_id"}
        if not isinstance(association, dict) or set(association) != expected:
            return None
        if (
            association.get("authority") != "v3_project_mode"
            or association.get("project_id") != project.project_id
            or association.get("command_attempt_id") != command_attempt_id
            or not str(association.get("job_id") or "").strip()
            or association["job_id"] not in project.job_ids
        ):
            return None
        return dict(association)

    def _doc271_matching_provider_deliverability_closure(
        self,
        project: ProjectRecord,
        *,
        user_input: str,
        command_direction: str,
        requested_output_count: int,
        selected_continuation_admissions: list[dict[str, str]],
        current_source_binding: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Read only complete same-project policy evidence before a new command."""

        if project.primary_template_id != ECOMMERCE_TEMPLATE_ID:
            return None
        if not isinstance(current_source_binding, dict):
            return None
        for job_id in reversed(project.job_ids):
            record = self.product_service.get_job_record(job_id)
            if record is None:
                continue
            try:
                status = self.product_service.get_job(job_id)
            except Exception:
                continue
            value = getattr(status, "status", None)
            normalized = str(getattr(value, "value", value) or "").strip().lower()
            if not normalized or normalized == ProductJobStatusValue.NOT_FOUND.value:
                continue
            # The newest readable Job is the only command authority. A newer
            # planned, generating, or settled Job prevents an old terminal
            # receipt from being reused as this command's result.
            receipt = verified_provider_deliverability_closure_receipt(
                record,
                uploaded_asset_lookup=self.product_service.get_uploaded_asset,
                generated_output_lookup=self.product_service.output_store.get_output,
                source_job_lookup=self.product_service.get_job_record,
                project_goal_snapshot_lookup=self._doc271_project_goal_snapshot,
                command_attempt_association_lookup=self._doc271_command_attempt_association,
            )
            if (
                receipt is not None
                and receipt.get("project_id") == project.project_id
                and self._doc271_current_binding_matches(
                project,
                receipt=receipt,
                user_input=user_input,
                command_direction=command_direction,
                requested_output_count=requested_output_count,
                selected_continuation_admissions=selected_continuation_admissions,
                current_source_binding=current_source_binding,
                )
            ):
                return receipt
            return None
        return None

    def _doc271_current_binding_matches(
        self,
        project: ProjectRecord,
        *,
        receipt: dict[str, Any],
        user_input: str,
        command_direction: str | None = None,
        requested_output_count: int | None = None,
        selected_continuation_admissions: list[dict[str, str]],
        current_source_binding: dict[str, Any] | None,
    ) -> bool:
        """Compare only current server-owned E-Commerce authority to a receipt."""

        current_goal = str(user_input or "").strip()
        if not current_goal or self._doc271_digest(
            {"template_id": ECOMMERCE_TEMPLATE_ID, "project_goal": current_goal}
        ) != receipt.get("canonical_project_goal_digest"):
            return False
        if command_direction is not None and self._doc271_digest(
            {
                "template_id": ECOMMERCE_TEMPLATE_ID,
                "project_goal": current_goal,
                "command_direction": str(command_direction or "").strip(),
            }
        ) != receipt.get("canonical_goal_prompt_digest"):
            return False
        if (
            not isinstance(current_source_binding, dict)
            or receipt.get("current_project_source_binding_digest")
            != current_source_binding.get("source_binding_digest")
        ):
            return False
        bindings = receipt.get("per_output_reference_bindings")
        if not isinstance(bindings, list) or not bindings:
            return False
        try:
            output_indexes = [int(item.get("output_index")) for item in bindings if isinstance(item, dict)]
        except (TypeError, ValueError):
            return False
        if output_indexes != list(range(1, len(bindings) + 1)):
            return False
        if requested_output_count is not None and len(bindings) != requested_output_count:
            return False
        if receipt.get("per_output_reference_bindings_digest") != self._doc271_digest(bindings):
            return False
        if receipt.get("physical_plan_digests") != [
            item.get("plan_digest") for item in bindings if isinstance(item, dict)
        ]:
            return False
        active_product_ids = {
            str(reference.asset_ref_id or "").strip()
            for reference in self._active_project_references(project)
            if reference.source_type == ProjectReferenceSourceType.UPLOADED
            and reference.use_policy == ProjectReferenceUsePolicy.PRODUCT
        }
        reference_sets: list[tuple[list[Any], list[Any], int]] = []
        for item in bindings:
            binding = item.get("reference_binding") if isinstance(item, dict) else None
            if not isinstance(binding, dict) or item.get("reference_binding_digest") != self._doc271_digest(binding):
                return False
            ids = binding.get("ordered_reference_ids")
            digests = binding.get("ordered_reference_sha256")
            channels = binding.get("ordered_reference_channels")
            roles = binding.get("ordered_reference_roles")
            source_types = binding.get("ordered_reference_source_types")
            locked_face_ids = binding.get("locked_face_output_ids")
            if (
                not isinstance(ids, list)
                or not isinstance(digests, list)
                or not isinstance(channels, list)
                or not isinstance(roles, list)
                or not isinstance(source_types, list)
                or not isinstance(locked_face_ids, list)
                or len(ids) != len(digests)
                or len(ids) != len(roles)
                or len(ids) != len(source_types)
                or any(not str(face_id or "").strip() for face_id in locked_face_ids)
            ):
                return False
            face_count = len(locked_face_ids)
            if face_count not in {0, 3}:
                return False
            expected_count = 1 + face_count
            has_continuation = len(ids) == expected_count + 1
            if len(ids) not in {expected_count, expected_count + 1}:
                return False
            expected_channels = ["product_truth"] + ["people_identity"] * face_count
            expected_roles = ["product_reference"] + ["face_reference"] * face_count
            expected_source_types = ["uploaded"] + ["visual_asset_library"] * face_count
            if has_continuation:
                expected_channels.append("generated_selected")
                expected_roles.append("selected_continuation_reference")
                expected_source_types.append("generated_selected")
            if (
                channels != expected_channels
                or roles != expected_roles
                or source_types != expected_source_types
                or [str(value) for value in ids[1 : 1 + face_count]]
                != [str(value) for value in locked_face_ids]
            ):
                return False
            product = self.product_service.get_uploaded_asset(str(ids[0]))
            product_path = Path(str(getattr(product, "file_path", "") or "")) if product else None
            if (
                str(ids[0]) not in active_product_ids
                or product_path is None
                or not product_path.is_file()
                or self._uploaded_asset_content_sha256(product) != str(digests[0]).lower()
            ):
                return False
            reference_sets.append((ids, digests, face_count))
        face_counts = {face_count for _ids, _digests, face_count in reference_sets}
        if len(face_counts) != 1:
            return False
        locked_face_count = face_counts.pop()
        if locked_face_count:
            if self.project_visual_asset_binding_service is None:
                return False
            current_binding = self.project_visual_asset_binding_service.current(project_id=project.project_id)
            if current_binding.state != "valid" or self._doc271_digest({"bindings": current_binding.model_dump(mode="json").get("bindings", [])}) != receipt.get("locked_visual_asset_binding_digest"):
                return False
            try:
                current_faces = self.product_service._library_visual_asset_reference_assets(  # noqa: SLF001
                    current_binding,
                    binding_service=self.project_visual_asset_binding_service,
                )
            except (OSError, ValueError, KeyError):
                return False
            face_by_id = {
                str(item.get("output_id") or item.get("asset_id") or "").strip(): item
                for item in current_faces
                if isinstance(item, dict)
            }
            if len(face_by_id) != locked_face_count:
                return False
            for ids, digests, _face_count in reference_sets:
                for source_id, digest in zip(ids[1 : 1 + locked_face_count], digests[1 : 1 + locked_face_count], strict=True):
                    face = face_by_id.get(str(source_id))
                    path = Path(str(face.get("file_path") or "")) if isinstance(face, dict) else None
                    if path is None or not path.is_file():
                        return False
                    try:
                        if hashlib.sha256(path.read_bytes()).hexdigest() != str(digest).lower():
                            return False
                    except OSError:
                        return False
        continuation = selected_continuation_admissions[0] if selected_continuation_admissions else None
        continuation_index = 1 + locked_face_count
        continuation_ids = {
            str(ids[continuation_index])
            for ids, _digests, _face_count in reference_sets
            if len(ids) == continuation_index + 1
        }
        continuation_digests = {
            str(digests[continuation_index]).lower()
            for ids, digests, _face_count in reference_sets
            if len(ids) == continuation_index + 1
        }
        if continuation_ids:
            path = Path(str(continuation.get("file_path") or "")) if isinstance(continuation, dict) else None
            if len(continuation_ids) != 1 or len(continuation_digests) != 1 or not isinstance(continuation, dict) or str(continuation.get("output_id") or "") not in continuation_ids or str(continuation.get("content_sha256") or "").lower() not in continuation_digests or path is None or not path.is_file():
                return False
            try:
                if hashlib.sha256(path.read_bytes()).hexdigest() not in continuation_digests:
                    return False
            except OSError:
                return False
        elif continuation is not None:
            return False
        router = getattr(getattr(self.product_service, "scenario_runtime", None), "generation_router", None)
        selected_provider = getattr(router, "provider", None)
        if selected_provider is None and router is not None:
            selected_provider = getattr(router, "providers", {}).get(
                ProviderStrategy.DEFAULT_IMAGE_PROVIDER
            )
        identity_builder = getattr(selected_provider, "execution_identity", None)
        if not callable(identity_builder):
            return False
        try:
            identity = identity_builder(operation="image_edit")
        except (TypeError, ValueError):
            return False
        route = {
            "provider_capability_id": identity.get("provider_capability_id"),
            "provider_name": identity.get("provider_name"),
            "provider_model": identity.get("model"),
            "provider_operation": identity.get("operation"),
            "provider_route_identity": identity.get("route_identity"),
        }
        return all(receipt.get(key) == value for key, value in route.items())

    @staticmethod
    def _ecommerce_configured_route_identity() -> str:
        """Bind a pre-execution record to the configured, not yet invoked route."""

        try:
            from app.config import settings as app_settings
        except Exception:
            return ""
        provider = str(getattr(app_settings, "default_image_provider", "") or "").strip()
        model = str(getattr(app_settings, "default_image_model", "") or "").strip()
        profile = str(
            getattr(app_settings, "openai_image_transport_profile", "") or ""
        ).strip()
        if not provider or not model or not profile:
            return ""
        return f"configured:{provider}:{model}:{profile}"

    def _doc279_private_receipt_for_job(
        self,
        project: ProjectRecord,
        record,
        *,
        require_current_facts: bool,
        user_input: str | None = None,
        command_direction: str | None = None,
        requested_output_count: int | None = None,
        selected_continuation_admissions: list[dict[str, str]] | None = None,
        current_source_binding: dict[str, Any] | None = None,
        current_reference_binding_digest: str | None = None,
    ) -> dict[str, Any] | None:
        """Authenticate one server-private E33 receipt against durable facts."""

        metadata = dict(getattr(getattr(record, "request", None), "metadata", {}) or {})
        route_identity = self._ecommerce_configured_route_identity()
        if (
            not route_identity
            or str(metadata.get("project_id") or "").strip() != project.project_id
            or str(metadata.get("template_id") or "").strip() != ECOMMERCE_TEMPLATE_ID
        ):
            return None
        try:
            private_records = self.project_store.list_private_records(
                project.project_id,
                DOC279_PRIVATE_NAMESPACE,
            )
        except ValueError:
            return None
        matches = [
            item
            for item in private_records
            if isinstance(item, dict) and item.get("terminal_job_id") == record.job_id
        ]
        if len(matches) != 1:
            return None
        receipt = verified_transparent_predecessor_receipt(
            record,
            matches[0],
            output_records_lookup=self.product_service.output_store.list_by_job,
            provider_route_identity=route_identity,
        )
        if receipt is None:
            return None
        command = _verified_command_binding(
            record,
            project_id=project.project_id,
            template_id=ECOMMERCE_TEMPLATE_ID,
            project_goal_snapshot_lookup=self._doc271_project_goal_snapshot,
            command_attempt_association_lookup=self._doc271_command_attempt_association,
        )
        if command is None:
            return None
        project_goal, stored_direction, _goal_prompt_digest = command
        raw_command = metadata.get("doc271_command_binding")
        raw_source = metadata.get("doc271_current_source_binding")
        raw_locked = metadata.get("frozen_visual_asset_binding_set")
        raw_continuations = metadata.get("doc269_selected_continuation_admissions", [])
        try:
            admission = ProductTruthAdmission.from_mapping(
                metadata.get("professional_ecommerce_product_truth_admission")
            )
        except ValueError:
            return None
        current_product_ids = self._ecommerce_product_reference_asset_ids(project, [])
        if (
            admission.project_id != project.project_id
            or admission.job_id != record.job_id
            or list(admission.canonical_asset_ids) != list(current_product_ids)
            or not isinstance(raw_command, dict)
            or receipt.get("command_binding_digest") != raw_command.get("command_binding_digest")
            or not isinstance(raw_source, dict)
            or receipt.get("current_source_binding_digest")
            != raw_source.get("source_binding_digest")
            or not isinstance(raw_locked, dict)
            or not isinstance(raw_continuations, list)
            or receipt.get("selected_continuation_admissions_digest")
            != self._doc271_digest(raw_continuations)
            or receipt.get("current_reference_binding_digest")
            != metadata.get("current_reference_binding_digest")
        ):
            return None
        if not require_current_facts:
            return receipt
        admissions = selected_continuation_admissions
        if admissions is None:
            try:
                admissions = self._doc269_selected_continuation_admissions(project)
            except (OSError, ValueError, KeyError):
                return None
        source_binding = current_source_binding
        if source_binding is None:
            try:
                source_binding = self._doc271_current_source_binding(
                    project,
                    selected_continuation_admissions=admissions,
                )
            except (OSError, ValueError, KeyError):
                return None
        reference_binding_digest = (
            current_reference_binding_digest
            if current_reference_binding_digest is not None
            else self._ecommerce_current_reference_binding_digest(project)
        )
        if (
            not isinstance(source_binding, dict)
            or raw_source != source_binding
            or receipt.get("current_source_binding_digest")
            != source_binding.get("source_binding_digest")
            or str(reference_binding_digest or "").strip() == ""
            or receipt.get("current_reference_binding_digest") != reference_binding_digest
            or raw_continuations != admissions
            or receipt.get("selected_continuation_admissions_digest")
            != self._doc271_digest(admissions)
            or receipt.get("provider_route_identity") != route_identity
        ):
            return None
        if self.project_visual_asset_binding_service is None:
            return None
        current_locked = self.project_visual_asset_binding_service.current(
            project_id=project.project_id
        ).model_dump(mode="json")
        if (
            receipt.get("locked_visual_asset_binding") != raw_locked
            or self._doc271_digest({"bindings": raw_locked.get("bindings", [])})
            != self._doc271_digest({"bindings": current_locked.get("bindings", [])})
        ):
            return None
        try:
            receipt_count = int(receipt.get("requested_output_count"))
        except (TypeError, ValueError):
            return None
        if (
            requested_output_count is not None and receipt_count != requested_output_count
        ) or receipt_count < 1:
            return None
        current_goal = str(user_input if user_input is not None else project.user_goal or "").strip()
        if current_goal != project_goal:
            return None
        if command_direction is not None and str(command_direction or "").strip() != stored_direction:
            return None
        return receipt

    def _issue_doc279_transparent_predecessor_receipt(
        self,
        project_id: str,
        job_id: str,
    ) -> dict[str, Any] | None:
        """Append one E33 receipt only after re-reading a blocked, no-execution Job."""

        project = self._require_project(project_id)
        record = self.product_service.get_job_record(str(job_id or "").strip())
        if record is None or record.job_id not in project.job_ids:
            return None
        route_identity = self._ecommerce_configured_route_identity()
        if not route_identity:
            return None
        try:
            admissions = self._doc269_selected_continuation_admissions(project)
            source_binding = self._doc271_current_source_binding(
                project,
                selected_continuation_admissions=admissions,
            )
            reference_binding_digest = self._ecommerce_current_reference_binding_digest(project)
        except (OSError, ValueError, KeyError):
            return None
        candidate = build_transparent_predecessor_receipt(
            record,
            output_records_lookup=self.product_service.output_store.list_by_job,
            provider_route_identity=route_identity,
        )
        if candidate is None:
            return None
        # The candidate is rebuilt from the durable Job.  The same routine
        # then requires its immutable command/source/People facts to equal the
        # current Project Mode authority before it can be appended.
        raw_matches = self._doc279_private_receipt_for_job(
            project,
            record,
            require_current_facts=True,
            user_input=str(project.user_goal or "").strip(),
            command_direction=str(getattr(record.request, "user_input", "") or "").strip(),
            requested_output_count=int(candidate["requested_output_count"]),
            selected_continuation_admissions=admissions,
            current_source_binding=source_binding,
            current_reference_binding_digest=reference_binding_digest,
        )
        if raw_matches is not None:
            return raw_matches
        # There is intentionally no stored E33 receipt yet. Validate the
        # candidate against the same durable/current authority before append.
        metadata = dict(record.request.metadata or {})
        if (
            metadata.get("doc271_current_source_binding") != source_binding
            or metadata.get("current_reference_binding_digest")
            != reference_binding_digest
            or metadata.get("doc269_selected_continuation_admissions") != admissions
        ):
            return None
        if self.project_visual_asset_binding_service is None:
            return None
        raw_locked = metadata.get("frozen_visual_asset_binding_set")
        current_locked = self.project_visual_asset_binding_service.current(
            project_id=project.project_id
        ).model_dump(mode="json")
        if (
            not isinstance(raw_locked, dict)
            or self._doc271_digest({"bindings": raw_locked.get("bindings", [])})
            != self._doc271_digest({"bindings": current_locked.get("bindings", [])})
        ):
            return None
        command = _verified_command_binding(
            record,
            project_id=project.project_id,
            template_id=ECOMMERCE_TEMPLATE_ID,
            project_goal_snapshot_lookup=self._doc271_project_goal_snapshot,
            command_attempt_association_lookup=self._doc271_command_attempt_association,
        )
        if command is None or command[0] != str(project.user_goal or "").strip():
            return None
        try:
            return self.project_store.append_private_record(
                project.project_id,
                DOC279_PRIVATE_NAMESPACE,
                candidate,
            )
        except ValueError:
            return None

    def _doc279_matching_opaque_provider_hold(
        self,
        project: ProjectRecord,
        *,
        user_input: str,
        command_direction: str | None,
        requested_output_count: int | None,
        selected_continuation_admissions: list[dict[str, str]],
        current_source_binding: dict[str, Any] | None,
        current_reference_binding_digest: str,
    ) -> tuple[dict[str, Any] | None, bool]:
        """Find E32 only after skipping a verified same-fact E33 successor."""

        if (
            project.primary_template_id != ECOMMERCE_TEMPLATE_ID
            or not isinstance(current_source_binding, dict)
            or not str(current_reference_binding_digest or "").strip()
        ):
            return None, False
        transparent_successor_seen = False
        for job_id in reversed(project.job_ids):
            record = self.product_service.get_job_record(job_id)
            if record is None:
                continue
            try:
                status = self.product_service.get_job(job_id)
            except Exception:
                continue
            value = getattr(status, "status", None)
            normalized = str(getattr(value, "value", value) or "").strip().lower()
            if not normalized or normalized == ProductJobStatusValue.NOT_FOUND.value:
                continue
            opaque_hold = verified_ambiguous_provider_request_hold_receipt(
                record,
                uploaded_asset_lookup=self.product_service.get_uploaded_asset,
                generated_output_lookup=self.product_service.output_store.get_output,
                source_job_lookup=self.product_service.get_job_record,
                project_goal_snapshot_lookup=self._doc271_project_goal_snapshot,
                command_attempt_association_lookup=self._doc271_command_attempt_association,
                output_records_lookup=self.product_service.output_store.list_by_job,
            )
            if (
                normalized in {
                    ProductJobStatusValue.BLOCKED.value,
                    ProductJobStatusValue.FAILED.value,
                }
                and opaque_hold is not None
                and opaque_hold.get("project_id") == project.project_id
                and self._doc278_current_binding_matches(
                    project,
                    receipt=opaque_hold,
                    user_input=user_input,
                    command_direction=command_direction,
                    requested_output_count=requested_output_count,
                    selected_continuation_admissions=selected_continuation_admissions,
                    current_source_binding=current_source_binding,
                    current_reference_binding_digest=current_reference_binding_digest,
                )
            ):
                return opaque_hold, transparent_successor_seen
            transparent = self._doc279_private_receipt_for_job(
                project,
                record,
                require_current_facts=True,
                user_input=user_input,
                command_direction=command_direction,
                requested_output_count=requested_output_count,
                selected_continuation_admissions=selected_continuation_admissions,
                current_source_binding=current_source_binding,
                current_reference_binding_digest=current_reference_binding_digest,
            )
            if transparent is not None:
                transparent_successor_seen = True
                continue
            # Any readable current/executed/delivered/changed/malformed Job is
            # authoritative; it prevents looking back to an older E32 receipt.
            return None, False
        return None, False

    def _doc278_matching_opaque_provider_hold(
        self,
        project: ProjectRecord,
        *,
        user_input: str,
        command_direction: str | None,
        requested_output_count: int | None,
        selected_continuation_admissions: list[dict[str, str]],
        current_source_binding: dict[str, Any] | None,
        current_reference_binding_digest: str,
    ) -> dict[str, Any] | None:
        """Return the newest valid E32 receipt after E33 predecessor handling."""

        receipt, _transparent = self._doc279_matching_opaque_provider_hold(
            project,
            user_input=user_input,
            command_direction=command_direction,
            requested_output_count=requested_output_count,
            selected_continuation_admissions=selected_continuation_admissions,
            current_source_binding=current_source_binding,
            current_reference_binding_digest=current_reference_binding_digest,
        )
        return receipt

    def _doc279_current_opaque_provider_hold(
        self,
        project: ProjectRecord,
    ) -> tuple[dict[str, Any] | None, bool]:
        """Read the current E32 operation and whether E33 made it reachable."""

        try:
            admissions = self._doc269_selected_continuation_admissions(project)
            source_binding = self._doc271_current_source_binding(
                project,
                selected_continuation_admissions=admissions,
            )
            reference_binding_digest = self._ecommerce_current_reference_binding_digest(project)
        except (OSError, ValueError, KeyError):
            return None, False
        return self._doc279_matching_opaque_provider_hold(
            project,
            user_input=str(project.user_goal or "").strip(),
            command_direction=None,
            requested_output_count=None,
            selected_continuation_admissions=admissions,
            current_source_binding=source_binding,
            current_reference_binding_digest=reference_binding_digest,
        )

    def _doc278_current_binding_matches(
        self,
        project: ProjectRecord,
        *,
        receipt: dict[str, Any],
        user_input: str,
        command_direction: str | None,
        requested_output_count: int | None,
        selected_continuation_admissions: list[dict[str, str]],
        current_source_binding: dict[str, Any] | None,
        current_reference_binding_digest: str,
    ) -> bool:
        """Compare only re-derived current create facts to an E32 receipt."""

        try:
            receipt_count = int(receipt.get("requested_output_count"))
        except (TypeError, ValueError):
            return False
        if (
            receipt.get("schema_version")
            != "doc278_ambiguous_provider_request_hold_receipt_v1"
            or receipt.get("authority") != "v3_ecommerce_opaque_provider_hold"
            or receipt_count < 1
            or (
                requested_output_count is not None
                and receipt_count != requested_output_count
            )
            or receipt.get("current_reference_binding_digest")
            != current_reference_binding_digest
            or receipt.get("selected_continuation_admissions_digest")
            != self._doc271_digest(selected_continuation_admissions)
        ):
            return False
        return self._doc271_current_binding_matches(
            project,
            receipt=receipt,
            user_input=user_input,
            command_direction=command_direction,
            requested_output_count=receipt_count,
            selected_continuation_admissions=selected_continuation_admissions,
            current_source_binding=current_source_binding,
        )

    def _reference_projection_drift_superseded_job_id(self, project: ProjectRecord) -> str | None:
        for job_id in reversed(project.job_ids):
            record = self.product_service.get_job_record(job_id)
            if record is None or record.status not in {
                ProductJobStatusValue.BLOCKED,
                ProductJobStatusValue.FAILED,
            }:
                continue
            metadata = dict(record.request.metadata or {})
            receipt = metadata.get("doc263_reference_projection_drift_receipt")
            if (
                isinstance(receipt, dict)
                and set(receipt) == {
                    "schema_version",
                    "authority",
                    "job_id",
                    "project_id",
                    "failure_code",
                    "source",
                }
                and receipt.get("schema_version")
                == "doc263_reference_projection_drift_receipt_v1"
                and receipt.get("authority") == "v3_product_api"
                and receipt.get("job_id") == record.job_id
                and str(receipt.get("project_id") or "").strip()
                == str(project.project_id).strip()
                and receipt.get("failure_code") == "reference_projection_drift"
                and receipt.get("source") == "provider_pre_dispatch_contract"
            ):
                return record.job_id
        return None

    def _ecommerce_superseded_job_id(self, project: ProjectRecord) -> str | None:
        drift_job_id = self._reference_projection_drift_superseded_job_id(project)
        if drift_job_id:
            return drift_job_id
        contract_drift_job_id = self._ecommerce_final_contract_drift_superseded_job_id(project)
        if contract_drift_job_id:
            return contract_drift_job_id
        current_product_asset_ids = set(self._project_product_reference_candidates(project))
        for job_id in reversed(project.job_ids):
            record = self.product_service.get_job_record(job_id)
            if record is None or record.status not in {
                ProductJobStatusValue.BLOCKED,
                ProductJobStatusValue.FAILED,
            }:
                continue
            metadata = dict(record.request.metadata or {})
            frozen_product_asset_ids = [
                str(asset_id).strip()
                for asset_id in record.request.uploaded_asset_ids
                if str(asset_id).strip()
            ]
            if (
                str(metadata.get("project_id") or "").strip() != project.project_id
                or str(metadata.get("template_id") or "").strip() != ECOMMERCE_TEMPLATE_ID
                or "doc263_project_canonical_product_asset_ids" in metadata
                or "professional_ecommerce_product_truth_admission" in metadata
                or not frozen_product_asset_ids
                or not set(frozen_product_asset_ids).issubset(current_product_asset_ids)
            ):
                continue
            if any(
                str(warning or "").strip().lower().startswith("product_truth_admission_invalid:")
                for warning in record.warnings
            ):
                return record.job_id
        return None

    def _ecommerce_final_contract_drift_superseded_job_id(
        self,
        project: ProjectRecord,
    ) -> str | None:
        """Recognize only the durable final-ID drift shape from old E-Commerce jobs."""

        current_product_asset_ids = set(self._project_product_reference_candidates(project))
        for job_id in reversed(project.job_ids):
            record = self.product_service.get_job_record(job_id)
            if record is None or record.status not in {
                ProductJobStatusValue.BLOCKED,
                ProductJobStatusValue.FAILED,
            }:
                continue
            metadata = dict(record.request.metadata or {})
            if (
                str(metadata.get("project_id") or "").strip() != project.project_id
                or str(metadata.get("template_id") or "").strip() != ECOMMERCE_TEMPLATE_ID
                or metadata.get("professional_ecommerce_contract_authority")
                != "v3_product_api"
                or record.planning_result is None
                or record.planning_result.creative_job.job_id != record.job_id
            ):
                continue
            try:
                request_admission = ProductTruthAdmission.from_mapping(
                    metadata.get("professional_ecommerce_product_truth_admission")
                )
                request_projections = metadata.get(
                    "professional_ecommerce_physical_product_projections"
                )
                if (
                    request_admission.project_id != project.project_id
                    or request_admission.job_id == record.job_id
                    or not request_projections
                    or not isinstance(request_projections, dict)
                    or list(record.request.uploaded_asset_ids)
                    != list(request_admission.canonical_asset_ids)
                    or not set(request_admission.canonical_asset_ids).issubset(
                        current_product_asset_ids
                    )
                ):
                    continue
                request_projection_records = {
                    key: PhysicalProductReferenceProjection.from_mapping(value)
                    for key, value in request_projections.items()
                    if isinstance(key, str) and isinstance(value, dict)
                }
                if (
                    len(request_projection_records) != len(request_projections)
                    or not request_projection_records
                    or any(
                        key != str(item.output_index) or item.job_id != record.job_id
                        for key, item in request_projection_records.items()
                    )
                ):
                    continue
                plan_metadata = dict(record.planning_result.metadata or {})
                plan_admission = ProductTruthAdmission.from_mapping(
                    plan_metadata.get("professional_ecommerce_product_truth_admission")
                )
                plan_projections = plan_metadata.get(
                    "professional_ecommerce_physical_product_projections"
                )
                if (
                    plan_admission.project_id != project.project_id
                    or plan_admission.job_id != record.job_id
                    or plan_projections != request_projections
                    or plan_admission.canonical_asset_ids
                    != request_admission.canonical_asset_ids
                    or plan_admission.sources != request_admission.sources
                    or plan_admission.product_truth_plan_digest
                    != request_admission.product_truth_plan_digest
                    or plan_admission.model_dump()
                    == request_admission.model_dump()
                ):
                    continue
                for raw_projection in plan_projections.values():
                    projection = PhysicalProductReferenceProjection.from_mapping(raw_projection)
                    projection.validate_against(plan_admission)
                    if projection.job_id != record.job_id:
                        raise ValueError("plan projection job mismatch")
                if not record.planning_result.generation_plans or any(
                    dict(plan.metadata or {}).get(
                        "professional_ecommerce_product_truth_admission"
                    )
                    != plan_admission.model_dump()
                    or dict(plan.metadata or {}).get(
                        "professional_ecommerce_physical_product_projections"
                    )
                    != plan_projections
                    for plan in record.planning_result.generation_plans
                ):
                    continue
            except (TypeError, ValueError, KeyError, AttributeError):
                continue
            return record.job_id
        return None

    def _soft_suppress_duplicate_product_references(
        self,
        project: ProjectRecord,
        *,
        now: str,
        reason: str,
    ) -> bool:
        changed = False
        canonical_by_key: dict[str, tuple[str, str]] = {}
        for reference in project.reference_assets:
            if not self._is_active_uploaded_product_reference(reference):
                continue
            key = self._uploaded_asset_content_key(reference.asset_ref_id)
            if not key:
                continue
            canonical = canonical_by_key.get(key)
            if canonical is None:
                canonical_by_key[key] = (reference.reference_id, reference.asset_ref_id)
                continue
            reference.status = ProjectReferenceStatus.INACTIVE
            reference.metadata.update(
                {
                    "duplicate_product_reference_suppressed": True,
                    "duplicate_product_reference_reason": reason,
                    "canonical_reference_id": canonical[0],
                    "canonical_asset_ref_id": canonical[1],
                    "suppressed_at": now,
                }
            )
            changed = True

        for item in project.uploaded_asset_refs:
            asset_id = str(item.get("asset_id") or "").strip()
            if not asset_id or str(item.get("status") or "").strip().lower() == ProjectReferenceStatus.INACTIVE.value:
                continue
            role = str(item.get("role") or "").strip()
            if role not in PROJECT_PRODUCT_REFERENCE_ROLES:
                continue
            key = self._uploaded_asset_content_key(asset_id)
            if not key:
                continue
            canonical = canonical_by_key.get(key)
            if canonical is None:
                canonical_by_key[key] = (str(item.get("reference_id") or ""), asset_id)
                continue
            if asset_id == canonical[1]:
                continue
            item.update(
                {
                    "status": ProjectReferenceStatus.INACTIVE.value,
                    "duplicate_product_reference_suppressed": True,
                    "duplicate_product_reference_reason": reason,
                    "canonical_reference_id": canonical[0],
                    "canonical_asset_ref_id": canonical[1],
                    "suppressed_at": now,
                }
            )
            changed = True
        return changed

    def _is_active_uploaded_product_reference(self, reference: ProjectReferenceAsset) -> bool:
        return (
            reference.status == ProjectReferenceStatus.ACTIVE
            and reference.source_type == ProjectReferenceSourceType.UPLOADED
            and reference.use_policy == ProjectReferenceUsePolicy.PRODUCT
        )

    def _dedupe_uploaded_asset_ids_by_content(self, asset_ids: list[str]) -> list[str]:
        canonical: list[str] = []
        seen: set[str] = set()
        for asset_id in asset_ids:
            clean_id = str(asset_id or "").strip()
            if not clean_id:
                continue
            key = self._uploaded_asset_content_key(clean_id) or f"asset_id:{clean_id}"
            if key in seen:
                continue
            seen.add(key)
            canonical.append(clean_id)
        return canonical

    def _uploaded_asset_content_key(self, asset_id: str) -> str:
        upload_record = self.product_service.get_uploaded_asset(str(asset_id or "").strip())
        digest = self._uploaded_asset_content_sha256(upload_record)
        return f"sha256:{digest}" if digest else ""

    def _uploaded_asset_content_sha256(self, upload_record: V3UploadedAssetRecord | None) -> str:
        if upload_record is None:
            return ""
        digest = str(
            upload_record.content_sha256
            or (upload_record.metadata or {}).get("content_sha256")
            or ""
        ).strip().lower()
        if digest:
            return digest
        if upload_record.file_path:
            return self._file_content_fingerprint(Path(upload_record.file_path)).strip().lower()
        return ""

    def _merge_commerce_profile(
        self,
        project: ProjectRecord,
        request: CreateProjectJobRequest,
    ) -> ProjectCommerceProfile:
        current = project.commerce_profile or ProjectCommerceProfile(project_id=project.project_id)
        data = current.model_dump(mode="python")
        patch = request.commerce_profile_patch
        patch_data = patch.model_dump(mode="python", exclude_none=True) if patch is not None else {}
        scalar_fields = [
            "product_name",
            "product_category",
            "target_platform",
            "target_market",
            "price_positioning",
            "target_audience",
        ]
        list_fields = [
            "core_selling_points",
            "must_keep_facts",
            "avoid_claims",
            "keyword_roots",
            "keywords",
            "competitor_notes",
        ]
        for field in scalar_fields:
            value = patch_data.get(field)
            if value is not None:
                data[field] = value
        for field in list_fields:
            values = patch_data.get(field)
            if values:
                data[field] = self._dedupe_text(values)
        # Construction evidence is one product-truth record.  Replace it as
        # an atomic, explicitly supplied fact set rather than merging stale
        # garment details from a previous job into a new product request.
        if "apparel_construction" in patch_data:
            data["apparel_construction"] = dict(patch_data.get("apparel_construction") or {})
        metadata = dict(data.get("metadata") or {})
        metadata.update(dict(patch_data.get("metadata") or {}))
        metadata.update(
            {
                "source": PROJECT_API_SOURCE,
                "template_id": ECOMMERCE_TEMPLATE_ID,
                "updated_from_project_job": True,
            }
        )
        data["project_id"] = project.project_id
        data["updated_at"] = _utc_now_iso()
        data["metadata"] = metadata
        profile = ProjectCommerceProfile.model_validate(data)
        project.commerce_profile = profile
        project.schema_version = "project_mode_v3_ecommerce_profile"
        project.updated_at = profile.updated_at or project.updated_at
        return profile

    def _scenario_selection_for_template(
        self,
        manifest: ProjectTemplateManifest,
        request: CreateProjectJobRequest,
        context: ProjectContextPackage,
        *,
        commerce_profile: ProjectCommerceProfile | None = None,
        has_product_reference: bool = False,
        advanced_reference_controls: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if manifest.template_id == ECOMMERCE_TEMPLATE_ID:
            profile = commerce_profile or request.commerce_profile_patch
            platform = profile.target_platform if profile else None
            market = profile.target_market if profile else None
            commerce_metadata = dict(profile.metadata or {}) if profile else {}
            parameters: dict[str, Any] = {
                "project_context_version": context.context_version,
                "use_project_context": request.use_project_context,
                "project_mode": True,
                "has_product_reference": bool(has_product_reference),
                "text_to_image_fallback": not bool(has_product_reference),
            }
            requested_count = _bounded_requested_image_count(request.metadata.get("requested_image_count"))
            if requested_count is not None:
                parameters["requested_image_count"] = requested_count
            requested_size = str(request.metadata.get("requested_image_size") or "").strip()
            if requested_size:
                parameters["requested_image_size"] = requested_size
            if market:
                parameters["market"] = market
            if profile and profile.product_category:
                parameters["product_category"] = profile.product_category
            copy_locale = str(commerce_metadata.get("copy_locale") or "").strip()
            if copy_locale:
                parameters["copy_locale"] = copy_locale
            approved_literal_copy = str(commerce_metadata.get("approved_literal_copy") or "").strip()
            if approved_literal_copy:
                parameters["approved_literal_copy"] = approved_literal_copy
            return {
                "scenario_id": manifest.scenario_pack_id,
                # New E-Commerce jobs are directed only by user facts plus
                # the remote Brain.  Historical mode/preset identifiers are
                # accepted by record readers but never re-emitted here.
                "mode_id": None,
                "preset_id": None,
                "platform_profile": platform or "generic",
                "parameters": parameters,
            }
        if manifest.template_id == "photographer_template":
            raw_mode = str(
                request.metadata.get("selected_mode_id")
                or request.metadata.get("mode_id")
                or "single_hero"
            ).strip()
            allowed_modes = {"single_hero", "reference_reshoot", "professional_set"}
            if raw_mode not in allowed_modes:
                raise PhotographyRoleContinuationError(
                    "photography_mode_not_supported",
                    "Photography accepts only single hero, reference reshoot, or the frozen professional set.",
                    status_code=400,
                )
            raw_preservation = request.metadata.get("preservation_controls")
            preservation = dict(raw_preservation) if isinstance(raw_preservation, dict) else {}
            parameters = {
                "project_context_version": context.context_version,
                "use_project_context": request.use_project_context,
                "project_mode": True,
                "delivery_mode": raw_mode,
                "input_mode": (
                    "reference_to_professional_reshoot"
                    if raw_mode == "reference_reshoot"
                    else str(request.metadata.get("input_mode") or "text_to_photo")
                ),
                "scene_domain": request.metadata.get("scene_domain"),
                "reshoot_strength": request.metadata.get("reshoot_strength"),
                "preservation_controls": preservation,
                "preserve_nonhuman_identity": bool(request.metadata.get("preserve_nonhuman_identity")),
                "requested_image_count": 3 if raw_mode == "professional_set" else 1,
            }
            requested_size = str(request.metadata.get("requested_image_size") or "").strip()
            if requested_size:
                parameters["requested_image_size"] = requested_size
            return {
                "scenario_id": manifest.scenario_pack_id,
                "mode_id": raw_mode,
                "preset_id": None,
                "parameters": {key: value for key, value in parameters.items() if value is not None},
            }
        variation_contract = self._general_variation_contract(request.metadata)
        parameters = {
            "project_context_version": context.context_version,
            "use_project_context": request.use_project_context,
        }
        parameters.update(variation_contract)
        if advanced_reference_controls:
            parameters["advanced_reference_controls"] = dict(advanced_reference_controls)
        requested_count = _bounded_requested_image_count(request.metadata.get("requested_image_count"))
        if requested_count is not None:
            parameters["requested_image_count"] = requested_count
        requested_size = _explicit_requested_image_size(request.metadata.get("requested_image_size"))
        if requested_size is None:
            requested_size = _infer_general_requested_image_size(request.user_input)
        if requested_size:
            parameters["requested_image_size"] = requested_size
        # General starts in the scenario pack's neutral freeform state.  A
        # Project Mode request may explicitly choose one of General's simple
        # presentation modes, but it must never silently turn every new
        # project into a campaign-poster job.  That old default caused
        # ordinary single-image work to inherit an unrelated promotional
        # framing at the very first project boundary.
        general_modes = {
            "freeform",
            "campaign_poster",
            "social_cover",
            "brand_visual",
            "product_style_hero",
        }
        general_presets = {
            "blank",
            "campaign_poster",
            "social_cover",
            "brand_key_visual",
            "product_style_hero",
        }
        mode_id = str(
            request.metadata.get("selected_mode_id")
            or request.metadata.get("mode_id")
            or "freeform"
        ).strip()
        if mode_id not in general_modes:
            mode_id = "freeform"
        default_presets = {
            "freeform": "blank",
            "campaign_poster": "campaign_poster",
            "social_cover": "social_cover",
            "brand_visual": "brand_key_visual",
            "product_style_hero": "product_style_hero",
        }
        preset_id = str(
            request.metadata.get("selected_preset_id")
            or request.metadata.get("preset_id")
            or default_presets[mode_id]
        ).strip()
        if preset_id not in general_presets:
            preset_id = default_presets[mode_id]
        return {
            "scenario_id": manifest.scenario_pack_id,
            "mode_id": mode_id,
            "preset_id": preset_id,
            "parameters": parameters,
        }

    def _product_profile_for_template(
        self,
        project: ProjectRecord,
        context_snapshot: dict[str, Any],
        request: CreateProjectJobRequest,
        manifest: ProjectTemplateManifest,
        *,
        commerce_profile: ProjectCommerceProfile | None,
        advanced_reference_controls: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base = {
            "brand_or_project_name": project.title,
            "project_goal": project.user_goal,
            "project_context": context_snapshot,
        }
        if manifest.template_id == GENERAL_TEMPLATE_ID:
            base.update(self._general_variation_contract(request.metadata))
        if advanced_reference_controls:
            base["advanced_reference_controls"] = dict(advanced_reference_controls)
        if manifest.template_id != ECOMMERCE_TEMPLATE_ID:
            return base
        profile = commerce_profile or project.commerce_profile or ProjectCommerceProfile(project_id=project.project_id)
        payload: dict[str, Any] = {
            **base,
            "product_name": profile.product_name,
            "product_category": profile.product_category,
            "platform": profile.target_platform,
            "market": profile.target_market,
            "price_positioning": profile.price_positioning,
            "target_audience": profile.target_audience,
            "selling_points": list(profile.core_selling_points),
            "core_selling_points": list(profile.core_selling_points),
            "facts": list(profile.must_keep_facts),
            "product_specs": list(profile.must_keep_facts),
            "claims": list(profile.avoid_claims),
            "keyword_roots": list(profile.keyword_roots),
            "keywords": list(profile.keywords),
            "competitor_notes": list(profile.competitor_notes),
            "apparel_construction": dict(profile.apparel_construction),
            "has_product_reference": bool(request.uploaded_asset_ids or self._project_product_reference_candidates(project)),
            "text_to_image_fallback": not bool(request.uploaded_asset_ids or self._project_product_reference_candidates(project)),
        }
        return {key: value for key, value in payload.items() if value not in (None, [], {})}

    def _general_variation_contract(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        metadata = dict(metadata or {})
        allowed = {
            "auto",
            "selection_candidates",
            "delivery_suite",
            "creative_exploration",
            "format_layout_adaptation",
        }
        requested = str(
            metadata.get("variation_mode_override")
            or metadata.get("variation_mode")
            or metadata.get("continuation_mode")
            or metadata.get("effective_variation_mode")
            or "auto"
        ).strip()
        if requested not in allowed:
            requested = "auto"
        inferred = str(metadata.get("inferred_variation_mode") or "").strip()
        if inferred not in allowed:
            inferred = ""
        effective = str(metadata.get("effective_variation_mode") or "").strip()
        if effective not in allowed:
            effective = requested
        if effective == "auto":
            effective = inferred or "delivery_suite"
        source = str(metadata.get("variation_mode_source") or ("auto" if requested == "auto" else "manual")).strip()
        return {
            "variation_mode": requested,
            "effective_variation_mode": effective,
            "continuation_mode": effective,
            "inferred_variation_mode": inferred or None,
            "variation_mode_source": source,
        }

    def _advanced_reference_controls_for_template(
        self,
        *,
        project: ProjectRecord,
        request: CreateProjectJobRequest,
        template_id: str,
    ) -> dict[str, Any]:
        if template_id not in {GENERAL_TEMPLATE_ID, ECOMMERCE_TEMPLATE_ID}:
            return {}
        raw_controls = {
            **self._clean_advanced_reference_controls(request.metadata.get("advanced_reference_controls")),
            **self._clean_advanced_reference_controls(request.advanced_reference_controls),
        }
        has_identity_reference = self._project_has_active_identity_reference(project)
        has_reference = self._project_has_active_reference(project)
        defaults = {
            "preserve_person_identity": bool(has_identity_reference),
            "preserve_product_appearance": bool(template_id == ECOMMERCE_TEMPLATE_ID and has_reference),
            "preserve_scene_consistency": False,
        }
        controls = {
            key: bool(raw_controls[key]) if key in raw_controls else default
            for key, default in defaults.items()
        }
        return {
            **controls,
            "template_scope": template_id,
            "doc": "90",
            "has_active_reference": has_reference,
            "has_identity_reference": has_identity_reference,
            "source": "manual" if raw_controls else f"{template_id}_defaults",
        }

    def _clean_advanced_reference_controls(self, value: Any) -> dict[str, bool]:
        if not isinstance(value, dict):
            return {}
        allowed = {
            "preserve_person_identity",
            "preserve_product_appearance",
            "preserve_scene_consistency",
        }
        return {key: bool(value[key]) for key in allowed if key in value}

    def _project_has_active_reference(self, project: ProjectRecord) -> bool:
        return any(reference.status == ProjectReferenceStatus.ACTIVE for reference in project.reference_assets)

    def _project_has_active_identity_reference(self, project: ProjectRecord) -> bool:
        identity_policies = {
            ProjectReferenceUsePolicy.IDENTITY,
            ProjectReferenceUsePolicy.PRODUCT_IDENTITY,
        }
        if any(
            reference.status == ProjectReferenceStatus.ACTIVE and reference.use_policy in identity_policies
            for reference in project.reference_assets
        ):
            return True
        return bool(self._project_has_active_reference(project) and self._looks_like_character_project(project))

    def _job_created_title(self, manifest: ProjectTemplateManifest) -> str:
        if manifest.template_id == ECOMMERCE_TEMPLATE_ID:
            return "电商套图任务已创建"
        if manifest.template_id == "photographer_template":
            return "摄影专业套图任务已创建"
        return "生成任务已创建"

    def _job_created_summary(self, manifest: ProjectTemplateManifest) -> str:
        if manifest.template_id == ECOMMERCE_TEMPLATE_ID:
            return "电商模板已开始整理商品信息、卖点和套图位置。"
        if manifest.template_id == "photographer_template":
            return "摄影模板已冻结角色、档案和参考真值，并将交给共享生成与审查流程。"
        return "通用模板已开始理解项目需求。"

    def _template_id_for_project_job(self, project: ProjectRecord, job_id: str) -> str:
        for item in reversed(self.project_store.list_timeline(project.project_id)):
            if item.job_id == job_id and item.metadata.get("template_id"):
                return str(item.metadata["template_id"])
        if project.primary_template_id:
            return project.primary_template_id
        status = self.product_service.get_job(job_id)
        template_id = status.metadata.get("template_id") if status and status.metadata else None
        if template_id:
            return str(template_id)
        return GENERAL_TEMPLATE_ID

    def _ensure_brand_memory_proposal_available(self, context: ProjectContextPackage) -> None:
        if context.selected_output_assets or context.selected_reference_assets or context.uploaded_reference_assets:
            return
        raise ValueError("Project needs a selected image or active reference before saving Brand Memory")

    def _build_brand_memory_proposal(
        self,
        project: ProjectRecord,
        context: ProjectContextPackage,
        request: ProjectBrandMemoryProposalRequest,
        now: str,
    ) -> ProjectBrandMemoryProposal:
        target_brand_id = request.target_brand_id or project.linked_brand_id
        loaded_brand = self.product_service.brand_profile_service.load_profile(target_brand_id) if target_brand_id else None
        reference_output_ids = self._dedupe_text(
            [
                self._output_identity(ref)
                for ref in context.selected_output_assets
            ]
        )
        reference_asset_ids = self._dedupe_text(
            [
                str(item.get("asset_ref_id") or item.get("asset_id") or "")
                for item in [*context.selected_reference_assets, *context.uploaded_reference_assets]
            ]
        )
        keep_notes = self._dedupe_text(
            [
                *(context.confirmed_visual_tone or []),
                "保持已选图片的整体视觉方向" if context.selected_output_assets else "",
                "沿用项目中的有效参考图" if context.uploaded_reference_assets or context.selected_reference_assets else "",
            ]
        )
        usage_scenes = self._dedupe_text([project.short_summary, context.goal_summary, project.title])
        style_summary = project.confirmed_style_summary or context.goal_summary or project.user_goal
        proposal_id = stable_id(
            "project_brand_memory_proposal",
            project.project_id,
            target_brand_id,
            request.mode.value,
            context.context_version,
            ",".join(reference_output_ids),
            ",".join(reference_asset_ids),
        )
        return ProjectBrandMemoryProposal(
            proposal_id=proposal_id,
            project_id=project.project_id,
            target_brand_id=target_brand_id,
            mode=request.mode,
            status=ProjectBrandMemoryProposalStatus.DRAFT,
            brand_name_suggestion=(loaded_brand.brand_name if loaded_brand else None) or project.title,
            style_summary=style_summary,
            keep_notes=keep_notes,
            avoid_notes=self._dedupe_text(context.negative_direction_notes),
            usage_scenes=usage_scenes,
            reference_output_ids=reference_output_ids,
            reference_asset_ids=reference_asset_ids,
            created_at=now,
            metadata={
                **request.metadata,
                "source": PROJECT_API_SOURCE,
                "brand_memory_written": False,
                "project_context_version": context.context_version,
            },
        )

    def _find_brand_memory_proposal(
        self,
        project: ProjectRecord,
        proposal_id: str,
    ) -> ProjectBrandMemoryProposal:
        for proposal in project.brand_memory_proposals:
            if proposal.proposal_id == proposal_id:
                return proposal
        raise KeyError("Brand Memory proposal was not found in this project")

    def _apply_brand_memory_confirmation(
        self,
        project: ProjectRecord,
        proposal: ProjectBrandMemoryProposal,
        request: ProjectBrandMemoryConfirmRequest,
    ) -> BrandProfile:
        brand_id = proposal.target_brand_id
        if proposal.mode == ProjectBrandMemoryProposalMode.APPEND:
            if not brand_id:
                raise ValueError("target_brand_id is required when appending to Brand Memory")
            profile = self.product_service.brand_profile_service.load_profile(brand_id)
            if profile is None:
                raise KeyError("target brand memory was not found")
        else:
            brand_id = brand_id or stable_id("brand", project.project_id, request.edited_brand_name or project.title)
            profile = BrandProfile(
                brand_id=brand_id,
                brand_name=request.edited_brand_name or proposal.brand_name_suggestion or project.title,
                is_temporary=False,
                visual_tone=[],
                color_palette=[],
                layout_preference=None,
                typography_preference=None,
                copywriting_tone=None,
                reference_assets=[],
                successful_asset_ids=[],
                rejected_style_tags=[],
                metadata={
                    "source": PROJECT_API_SOURCE,
                    "created_from_project_id": project.project_id,
                    "created_from_proposal_id": proposal.proposal_id,
                },
            )
        profile.brand_name = request.edited_brand_name or profile.brand_name or proposal.brand_name_suggestion
        for note in self._dedupe_text([request.edited_style_summary, *request.edited_keep_notes]):
            if note not in profile.visual_tone:
                profile.visual_tone.append(note)
        for note in self._dedupe_text(request.edited_avoid_notes or proposal.avoid_notes):
            if note not in profile.rejected_style_tags:
                profile.rejected_style_tags.append(note)
        for asset_id in self._dedupe_text([*proposal.reference_output_ids, *proposal.reference_asset_ids]):
            if asset_id not in profile.successful_asset_ids:
                profile.successful_asset_ids.append(asset_id)
        existing_reference_ids = {reference.asset_id for reference in profile.reference_assets}
        for reference in self._brand_reference_assets(project, proposal):
            if reference.asset_id not in existing_reference_ids:
                profile.reference_assets.append(reference)
                existing_reference_ids.add(reference.asset_id)
        confirmation = {
            "project_id": project.project_id,
            "proposal_id": proposal.proposal_id,
            "style_summary": request.edited_style_summary,
            "keep_notes": self._dedupe_text(request.edited_keep_notes or proposal.keep_notes),
            "avoid_notes": self._dedupe_text(request.edited_avoid_notes or proposal.avoid_notes),
            "usage_scenes": self._dedupe_text(request.edited_usage_scenes or proposal.usage_scenes),
        }
        existing_confirmations = list(profile.metadata.get("project_memory_confirmations") or [])
        existing_confirmations.append(confirmation)
        profile.metadata = {
            **profile.metadata,
            "last_project_memory_confirmation": confirmation,
            "project_memory_confirmations": existing_confirmations,
            "last_memory_update_source": PROJECT_API_SOURCE,
        }
        return self.product_service.brand_profile_service.save_profile(profile)

    def _brand_reference_assets(
        self,
        project: ProjectRecord,
        proposal: ProjectBrandMemoryProposal,
    ) -> list[ReferenceAsset]:
        references: list[ReferenceAsset] = []
        selected_lookup = {self._output_identity(ref): ref for ref in project.selected_output_refs}
        for output_id in proposal.reference_output_ids:
            ref = selected_lookup.get(output_id)
            references.append(
                ReferenceAsset(
                    asset_id=output_id,
                    asset_type="project_selected_output",
                    source="project_mode_brand_memory_confirmation",
                    purpose="confirmed project style reference",
                    uri=(ref.download_url or ref.preview_url if ref else None),
                    metadata={"project_id": project.project_id, "proposal_id": proposal.proposal_id},
                )
            )
        project_references = {reference.asset_ref_id: reference for reference in project.reference_assets}
        for asset_id in proposal.reference_asset_ids:
            project_reference = project_references.get(asset_id)
            references.append(
                ReferenceAsset(
                    asset_id=asset_id,
                    asset_type="project_reference_asset",
                    source="project_mode_brand_memory_confirmation",
                    purpose=(project_reference.use_policy.value if project_reference else "project reference"),
                    uri=(project_reference.preview_url if project_reference else None),
                    metadata={"project_id": project.project_id, "proposal_id": proposal.proposal_id},
                )
            )
        return references

    def _dedupe_text(self, values: list[str | None]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    def _require_project(self, project_id: str) -> ProjectRecord:
        project = self.project_store.get_project(project_id)
        if project is None:
            raise KeyError("这个项目没有找到")
        return project

    def _ensure_project_job(self, project: ProjectRecord, job_id: str) -> None:
        if job_id not in project.job_ids:
            raise KeyError("这个生成任务不属于当前项目")

    def _link_job(
        self,
        project: ProjectRecord,
        job_id: str,
        context: ProjectContextPackage,
        *,
        doc271_command_binding: dict[str, Any] | None = None,
    ) -> None:
        if job_id not in project.job_ids:
            project.job_ids.append(job_id)
        if isinstance(doc271_command_binding, dict):
            attempt_id = str(doc271_command_binding.get("command_attempt_id") or "").strip()
            snapshot_id = str(doc271_command_binding.get("goal_snapshot_id") or "").strip()
            if not attempt_id or not snapshot_id:
                raise ValueError("doc271_command_attempt_binding_invalid")
            metadata = dict(project.metadata or {})
            associations = dict(metadata.get("doc271_command_attempt_job_associations") or {})
            association = {
                "authority": "v3_project_mode",
                "project_id": project.project_id,
                "template_id": ECOMMERCE_TEMPLATE_ID,
                "command_attempt_id": attempt_id,
                "snapshot_id": snapshot_id,
                "job_id": job_id,
            }
            existing = associations.get(attempt_id)
            if existing is not None and existing != association:
                raise ValueError("doc271_command_attempt_binding_immutable")
            associations[attempt_id] = association
            project.metadata = {**metadata, "doc271_command_attempt_job_associations": associations}
        project.latest_context = context
        project.last_context_built_at = context.created_at
        project.schema_version = "project_mode_v3_ecommerce_profile" if project.commerce_profile else "project_mode_v2_context_assets_feedback"
        project.updated_at = _utc_now_iso()
        project.memory_summary = self._memory_summary(project)
        self.project_store.save_project(project)

    def _refresh_project_context(
        self,
        project: ProjectRecord,
        continuation_instruction: str | None = None,
    ) -> ProjectContextPackage:
        context = self._build_context(project, continuation_instruction=continuation_instruction)
        project.latest_context = context
        project.last_context_built_at = context.created_at
        project.schema_version = "project_mode_v3_ecommerce_profile" if project.commerce_profile else "project_mode_v2_context_assets_feedback"
        project.updated_at = _utc_now_iso()
        project.memory_summary = self._memory_summary(project)
        self.project_store.save_project(project)
        return context

    def _append_timeline(
        self,
        project_id: str,
        item_type: TimelineItemType,
        title: str,
        summary: str,
        *,
        job_id: str | None = None,
        asset_ids: list[str] | None = None,
        candidate_ids: list[str] | None = None,
        selected_output_refs: list[OutputRef] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProjectTimelineItem:
        idempotent_job_items = {
            TimelineItemType.JOB_GENERATED,
            TimelineItemType.PROVIDER_RETRY,
            TimelineItemType.JOB_BLOCKED,
            TimelineItemType.VISUAL_REVIEW,
            TimelineItemType.VISUAL_RETRY,
        }
        if job_id and item_type in idempotent_job_items:
            for existing in self.project_store.list_timeline(project_id):
                if existing.item_type == item_type and (existing.job_id == job_id or existing.related_job_id == job_id):
                    return existing
        created_at = _utc_now_iso()
        item = ProjectTimelineItem(
            timeline_item_id=stable_id("timeline", project_id, item_type, job_id, created_at),
            project_id=project_id,
            item_type=item_type,
            title=title,
            summary=summary,
            job_id=job_id,
            asset_ids=asset_ids or [],
            candidate_ids=candidate_ids or [],
            selected_output_refs=selected_output_refs or [],
            created_at=created_at,
            related_job_id=job_id,
            related_output_ids=[
                ref.output_id
                for ref in selected_output_refs or []
                if ref.output_id
            ],
            metadata=metadata or {},
        )
        return self.project_store.append_timeline(item)

    def _reconcile_project_outputs(self, project: ProjectRecord) -> bool:
        output_store = getattr(self.product_service, "output_store", None)
        if output_store is None or not project.job_ids:
            return False
        timeline = self.project_store.list_timeline(project.project_id)
        generated_jobs = {
            item.job_id or item.related_job_id
            for item in timeline
            if item.item_type == TimelineItemType.JOB_GENERATED and (item.job_id or item.related_job_id)
        }
        reviewed_jobs = {
            item.job_id or item.related_job_id
            for item in timeline
            if item.item_type == TimelineItemType.VISUAL_REVIEW and (item.job_id or item.related_job_id)
        }
        changed = False
        for job_id in list(dict.fromkeys(project.job_ids)):
            job_status = self.product_service.get_job(job_id)
            if job_status.status in {ProductJobStatusValue.GENERATING, ProductJobStatusValue.FINALIZING}:
                # An output file can appear before shared review/retry settles
                # delivery.  Never create a completed timeline entry from it.
                continue
            try:
                records = list(output_store.list_by_job(job_id))
            except Exception:
                continue
            if not records:
                continue
            records = sorted(records, key=lambda item: item.created_at or "")
            incomplete_execution = self._incomplete_specialized_set_execution(job_status, records)
            if incomplete_execution is not None:
                review_certification = incomplete_execution.get("review_certification")
                is_noncertifying = (
                    str(incomplete_execution.get("status") or "").lower() != "incomplete"
                    and isinstance(review_certification, dict)
                    and review_certification.get("state") != "certified"
                )
                diagnostic = "specialized_review_noncertifying" if is_noncertifying else "specialized_role_coverage_incomplete"
                if not any(
                    item.item_type == TimelineItemType.NOTE_ADDED
                    and (item.job_id == job_id or item.related_job_id == job_id)
                    and isinstance(item.metadata, dict)
                    and item.metadata.get("execution_diagnostic") == diagnostic
                    for item in timeline
                ):
                    self._append_timeline(
                        project.project_id,
                        TimelineItemType.NOTE_ADDED,
                        "摄影结果尚未自动认证" if is_noncertifying else "专业套图存在未完成角色",
                        (
                            self._review_certification_summary(review_certification)
                            if is_noncertifying
                            else self._incomplete_specialized_set_summary(incomplete_execution)
                        ),
                        job_id=job_id,
                        metadata={
                            "execution_diagnostic": diagnostic,
                            "specialized_execution_summary": incomplete_execution,
                            "review_certification": review_certification if isinstance(review_certification, dict) else {},
                            "append_only_history_preserved": True,
                            "normal_project_delivery_withheld": True,
                        },
                    )
                    timeline = self.project_store.list_timeline(project.project_id)
                    changed = True
                # Provider pixels remain append-only evidence, but they are
                # not a deliverable until every frozen role has its winner.
                continue
            asset_ids = [record.asset_id for record in records if getattr(record, "asset_id", None)]
            candidate_ids = [record.candidate_id for record in records if getattr(record, "candidate_id", None)]
            output_ids = [record.output_id for record in records if getattr(record, "output_id", None)]
            if job_id not in generated_jobs:
                self._append_timeline(
                    project.project_id,
                    TimelineItemType.JOB_GENERATED,
                    "生成了一组图片",
                    "图片已保存到项目里，可以继续查看、选择或再生成。",
                    job_id=job_id,
                    asset_ids=asset_ids,
                    candidate_ids=candidate_ids,
                    metadata={
                        "template_id": self._template_id_for_project_job(project, job_id),
                        "restored_from_output_store": True,
                        "output_ids": output_ids,
                    },
                )
                generated_jobs.add(job_id)
                changed = True
            if job_id not in reviewed_jobs:
                self._append_timeline(
                    project.project_id,
                    TimelineItemType.VISUAL_REVIEW,
                    "V3 已同步生成结果",
                    "V3 找到了已经生成的图片，并把它们补回到这个项目。",
                    job_id=job_id,
                    asset_ids=asset_ids,
                    candidate_ids=candidate_ids,
                    metadata={
                        "template_id": self._template_id_for_project_job(project, job_id),
                        "restored_from_output_store": True,
                        "inspection_count": len(records),
                        "recommended_output_ids": output_ids,
                        "hidden_output_ids": [],
                    },
                )
                reviewed_jobs.add(job_id)
                changed = True
        if changed:
            project.memory_summary = self._memory_summary(project)
            self.project_store.save_project(project)
        return changed

    @staticmethod
    def _incomplete_specialized_set_execution(job_status: ProductJobStatus, records: list[Any]) -> dict[str, Any] | None:
        metadata = dict(job_status.metadata or {})
        execution = metadata.get("specialized_execution_summary")
        review_certification = metadata.get("review_certification")
        def with_certification(value: dict[str, Any]) -> dict[str, Any]:
            projected = dict(value)
            if isinstance(review_certification, dict):
                projected["review_certification"] = dict(review_certification)
            return projected
        if isinstance(execution, dict) and bool(execution.get("final_delivery_withheld")):
            return with_certification(execution)
        if isinstance(execution, dict) and str(execution.get("status") or "").lower() == "incomplete":
            return with_certification(execution)
        if not isinstance(execution, dict):
            return None
        expected = [str(item).strip() for item in execution.get("role_keys", []) if str(item).strip()]
        if len(expected) < 2:
            return None
        delivered: set[str] = set()
        for record in records:
            record_metadata = dict(getattr(record, "metadata", {}) or {})
            role_key = str(record_metadata.get("mode_role_key") or "").strip()
            if not role_key:
                recipe = record_metadata.get("mode_role_recipe")
                role_key = str(recipe.get("role_key") or "").strip() if isinstance(recipe, dict) else ""
            if role_key:
                delivered.add(role_key)
        missing = [role_key for role_key in expected if role_key not in delivered]
        if not missing:
            return None
        return {
            **with_certification(execution),
            "status": "incomplete",
            "missing_role_keys": missing,
            "final_delivery_withheld": True,
            "append_only_history_preserved": True,
        }

    @staticmethod
    def _review_certification_summary(certification: dict[str, Any]) -> str:
        """Give the Project timeline a safe, actionable certification result."""

        state = str(certification.get("state") or "blocked")
        role_modes = [
            str(item.get("review_mode") or "unknown")
            for item in certification.get("roles", [])
            if isinstance(item, dict)
        ]
        modes = "、".join(list(dict.fromkeys(role_modes))) or "unknown"
        if state == "manual_confirmation_required":
            return f"真实像素审查方式：{modes}。本次需要人工确认，不计入自动验收通过，也不会作为最终交付。"
        return f"真实像素审查未自动认证（审查方式：{modes}）。结果保留在追加历史中，未作为最终交付。"

    def _post_generation_review_summary(self, review_package: dict[str, Any]) -> str:
        lines = [str(item).strip() for item in review_package.get("user_visible_summary", []) if str(item).strip()]
        if lines:
            return "；".join(lines[:3])
        inspections = review_package.get("inspections")
        if isinstance(inspections, list) and any(
            isinstance(item, dict) and item.get("status") == "manual_review"
            for item in inspections
        ):
            return "图片已检查，部分结果需要人工确认。"
        if isinstance(inspections, list) and any(
            isinstance(item, dict) and item.get("status") == "fail_retryable"
            for item in inspections
        ):
            return "图片已检查，发现可修复问题。"
        return "图片已检查，没有发现明显问题。"

    def _upsert_project_reference(
        self,
        project: ProjectRecord,
        *,
        source_type: ProjectReferenceSourceType,
        asset_ref_id: str,
        now: str,
        label: str | None = None,
        user_note: str | None = None,
        use_policy: ProjectReferenceUsePolicy = ProjectReferenceUsePolicy.GENERAL,
        created_from_job_id: str | None = None,
        created_from_output_id: str | None = None,
        preview_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProjectReferenceAsset:
        reference_id = stable_id(
            "project_reference",
            project.project_id,
            source_type.value,
            asset_ref_id,
            created_from_job_id,
            created_from_output_id,
        )
        upload_record = (
            self._require_ready_uploaded_reference(asset_ref_id, use_policy)
            if source_type == ProjectReferenceSourceType.UPLOADED
            else None
        )
        reference_metadata = dict(metadata or {})
        if source_type == ProjectReferenceSourceType.UPLOADED:
            reference_metadata.setdefault("v3_upload_lookup", "ready")
            use_policy = self._effective_uploaded_reference_use_policy(
                project,
                upload_record,
                requested_policy=use_policy,
                metadata=reference_metadata,
            )
            reference_metadata.setdefault("effective_use_policy", use_policy.value)
            digest = self._uploaded_asset_content_sha256(upload_record)
            if digest:
                reference_metadata.setdefault("content_sha256", digest)
            if use_policy == ProjectReferenceUsePolicy.PRODUCT:
                content_key = self._uploaded_asset_content_key(asset_ref_id)
                canonical = self._active_product_reference_for_content(
                    project,
                    asset_ref_id=asset_ref_id,
                    content_key=content_key,
                )
                if canonical is not None:
                    canonical.metadata.setdefault("duplicate_product_reference_reused", True)
                    return canonical
                canonical_asset_id = self._legacy_product_asset_id_for_content(
                    project,
                    asset_ref_id=asset_ref_id,
                    content_key=content_key,
                )
                if canonical_asset_id and canonical_asset_id != asset_ref_id:
                    return self._upsert_project_reference(
                        project,
                        source_type=source_type,
                        asset_ref_id=canonical_asset_id,
                        now=now,
                        label=label,
                        user_note=user_note,
                        use_policy=use_policy,
                        created_from_job_id=created_from_job_id,
                        created_from_output_id=created_from_output_id,
                        preview_url=preview_url,
                        metadata={
                            **reference_metadata,
                            "duplicate_product_reference_reused_asset_ref_id": asset_ref_id,
                        },
                    )
        existing = next((item for item in project.reference_assets if item.reference_id == reference_id), None)
        if existing is None:
            existing = ProjectReferenceAsset(
                reference_id=reference_id,
                project_id=project.project_id,
                source_type=source_type,
                asset_ref_id=asset_ref_id,
                preview_url=preview_url or (upload_record.content_url if upload_record else None),
                created_at=now,
                created_from_job_id=created_from_job_id,
                created_from_output_id=created_from_output_id,
                label=label,
                user_note=user_note,
                status=ProjectReferenceStatus.ACTIVE,
                use_policy=use_policy,
                metadata=reference_metadata,
            )
            project.reference_assets.append(existing)
        else:
            existing.status = ProjectReferenceStatus.ACTIVE
            existing.label = label if label is not None else existing.label
            existing.user_note = user_note if user_note is not None else existing.user_note
            existing.use_policy = use_policy
            existing.preview_url = preview_url or existing.preview_url or (upload_record.content_url if upload_record else None)
            existing.metadata.update(reference_metadata)
        if source_type == ProjectReferenceSourceType.UPLOADED:
            self._ensure_legacy_uploaded_ref(project, existing)
        return existing

    def _active_product_reference_for_content(
        self,
        project: ProjectRecord,
        *,
        asset_ref_id: str,
        content_key: str,
    ) -> ProjectReferenceAsset | None:
        if not content_key:
            return None
        for reference in project.reference_assets:
            if not self._is_active_uploaded_product_reference(reference):
                continue
            if reference.asset_ref_id == asset_ref_id:
                continue
            if self._uploaded_asset_content_key(reference.asset_ref_id) == content_key:
                return reference
        return None

    def _legacy_product_asset_id_for_content(
        self,
        project: ProjectRecord,
        *,
        asset_ref_id: str,
        content_key: str,
    ) -> str | None:
        if not content_key:
            return None
        for item in project.uploaded_asset_refs:
            candidate_id = str(item.get("asset_id") or "").strip()
            if not candidate_id or candidate_id == asset_ref_id:
                continue
            if str(item.get("status") or "").strip().lower() == ProjectReferenceStatus.INACTIVE.value:
                continue
            if str(item.get("role") or "").strip() not in PROJECT_PRODUCT_REFERENCE_ROLES:
                continue
            if self._uploaded_asset_content_key(candidate_id) == content_key:
                return candidate_id
        return None

    def _persist_job_uploaded_references(
        self,
        project: ProjectRecord,
        uploaded_asset_ids: list[str],
        *,
        template_id: str,
        user_input: str,
    ) -> None:
        now = _utc_now_iso()
        seen: set[str] = set()
        for asset_id in uploaded_asset_ids:
            clean_id = str(asset_id or "").strip()
            if not clean_id or clean_id in seen:
                continue
            seen.add(clean_id)
            requested_policy = (
                ProjectReferenceUsePolicy.PRODUCT
                if template_id == ECOMMERCE_TEMPLATE_ID
                else ProjectReferenceUsePolicy.GENERAL
            )
            try:
                self._upsert_project_reference(
                    project,
                    source_type=ProjectReferenceSourceType.UPLOADED,
                    asset_ref_id=clean_id,
                    now=now,
                    label="Job uploaded reference",
                    user_note="Uploaded for this project job and kept as project context.",
                    use_policy=requested_policy,
                    metadata={
                        "persisted_from_project_job": True,
                        "template_id": template_id,
                        "user_input_preview": self._short_text(user_input, 120),
                    },
                )
            except ValueError:
                if template_id != ECOMMERCE_TEMPLATE_ID:
                    continue
                raise

    def _effective_uploaded_reference_use_policy(
        self,
        project: ProjectRecord,
        upload_record: V3UploadedAssetRecord | None,
        *,
        requested_policy: ProjectReferenceUsePolicy,
        metadata: dict[str, Any] | None = None,
    ) -> ProjectReferenceUsePolicy:
        if upload_record is None:
            return requested_policy
        role = str(upload_record.role or "").strip().lower()
        requested = requested_policy
        if requested in {
            ProjectReferenceUsePolicy.PRODUCT,
            ProjectReferenceUsePolicy.PRODUCT_IDENTITY,
            ProjectReferenceUsePolicy.IDENTITY,
            ProjectReferenceUsePolicy.BRAND_ASSET,
        }:
            return requested
        if role in ECOMMERCE_PRODUCT_UPLOAD_ROLES:
            return ProjectReferenceUsePolicy.PRODUCT
        character_roles = {"face_reference", "portrait_identity", "identity_reference"}
        possible_subject_roles = {"unknown_reference", "subject_reference", "general", ""}
        if role in character_roles:
            return ProjectReferenceUsePolicy.IDENTITY
        if self._looks_like_character_project(project) and role in possible_subject_roles:
            if metadata is not None:
                metadata.setdefault("identity_policy_inferred_from", "character_project_uploaded_reference")
            return ProjectReferenceUsePolicy.IDENTITY
        return requested if requested != ProjectReferenceUsePolicy.GENERAL else ProjectReferenceUsePolicy.GENERAL

    def _upsert_generated_reference(self, project: ProjectRecord, ref: OutputRef, now: str) -> ProjectReferenceAsset:
        return self._upsert_project_reference(
            project,
            source_type=ProjectReferenceSourceType.GENERATED_SELECTED,
            asset_ref_id=self._output_identity(ref),
            now=now,
            label="已选图片",
            user_note=ref.selection_reason,
            use_policy=self._generated_output_use_policy(project),
            created_from_job_id=ref.job_id,
            created_from_output_id=ref.output_id or self._output_identity(ref),
            preview_url=ref.thumbnail_url or ref.preview_url,
            metadata={
                "output_ref_id": ref.output_ref_id,
                "output_id": ref.output_id,
                "candidate_id": ref.candidate_id,
                "asset_id": ref.asset_id,
                "canonical_output_binding": bool(ref.metadata.get("canonical_output_binding")),
                "source_integrity_id": ref.metadata.get("source_integrity_id"),
            },
        )

    def _ensure_legacy_uploaded_ref(self, project: ProjectRecord, reference: ProjectReferenceAsset) -> None:
        digest = self._uploaded_asset_content_sha256(self.product_service.get_uploaded_asset(reference.asset_ref_id))
        for item in project.uploaded_asset_refs:
            if str(item.get("asset_id") or "") != reference.asset_ref_id:
                continue
            item.update(
                {
                    "source": "project_reference",
                    "role": reference.use_policy.value,
                    "reference_id": reference.reference_id,
                    "status": ProjectReferenceStatus.ACTIVE.value,
                }
            )
            if digest:
                item["content_sha256"] = digest
            return
        payload = {
            "asset_id": reference.asset_ref_id,
            "source": "project_reference",
            "role": reference.use_policy.value,
            "reference_id": reference.reference_id,
            "status": ProjectReferenceStatus.ACTIVE.value,
        }
        if digest:
            payload["content_sha256"] = digest
        project.uploaded_asset_refs.append(payload)

    def _require_ready_uploaded_reference(
        self,
        asset_id: str,
        use_policy: ProjectReferenceUsePolicy,
    ) -> V3UploadedAssetRecord:
        clean_id = str(asset_id or "").strip()
        upload_record = self.product_service.get_uploaded_asset(clean_id)
        if upload_record is None:
            raise ValueError("这张参考图没有在 V3 上传记录里找到，请重新上传后再保存。")
        if upload_record.status != V3AssetUploadStatusValue.READY:
            raise ValueError("这张参考图还没有上传完成，请等上传完成后再保存。")
        if use_policy == ProjectReferenceUsePolicy.PRODUCT and not self._is_product_reference_upload(upload_record):
            raise ValueError("电商商品参考必须使用商品图上传，请重新上传商品图。")
        return upload_record

    def _is_ready_product_upload(self, asset_id: str) -> bool:
        upload_record = self.product_service.get_uploaded_asset(asset_id)
        if upload_record is None or upload_record.status != V3AssetUploadStatusValue.READY:
            return False
        return self._is_product_reference_upload(upload_record)

    def _is_product_reference_upload(self, upload_record: V3UploadedAssetRecord) -> bool:
        return str(upload_record.role or "").strip() in ECOMMERCE_PRODUCT_UPLOAD_ROLES

    def _append_feedback(
        self,
        project: ProjectRecord,
        *,
        target_type: ProjectFeedbackTargetType,
        target_id: str | None,
        feedback_type: ProjectFeedbackType,
        plain_text: str,
        reason_tags: list[str] | None = None,
        status: ProjectFeedbackStatus = ProjectFeedbackStatus.ACTIVE,
        metadata: dict[str, Any] | None = None,
    ) -> ProjectFeedbackRecord:
        now = _utc_now_iso()
        feedback = ProjectFeedbackRecord(
            feedback_id=stable_id(
                "project_feedback",
                project.project_id,
                target_type.value,
                target_id,
                feedback_type.value,
                plain_text,
                now,
            ),
            project_id=project.project_id,
            target_type=target_type,
            target_id=target_id,
            feedback_type=feedback_type,
            plain_text=plain_text,
            reason_tags=list(reason_tags or []),
            created_at=now,
            status=status,
            metadata=metadata or {},
        )
        project.feedback_records.append(feedback)
        if feedback.feedback_type == ProjectFeedbackType.AVOID_DIRECTION and feedback.status == ProjectFeedbackStatus.ACTIVE:
            if feedback.plain_text not in project.rejected_direction_notes:
                project.rejected_direction_notes.append(feedback.plain_text)
        return feedback

    def _set_output_state(
        self,
        project: ProjectRecord,
        ref: OutputRef,
        state: ProjectOutputSelectionStateValue,
        now: str,
        note: str | None = None,
    ) -> ProjectSelectedOutputState:
        output_id = self._output_identity(ref)
        existing = next((item for item in project.selected_output_states if item.output_id == output_id), None)
        if existing is None:
            existing = ProjectSelectedOutputState(
                project_id=project.project_id,
                job_id=ref.job_id or "",
                output_id=output_id,
                selection_state=state,
            )
            project.selected_output_states.append(existing)
        existing.selection_state = state
        if state == ProjectOutputSelectionStateValue.SELECTED:
            existing.selected_at = now
            existing.selection_note = note or ref.selection_reason
            existing.unselected_at = None
            existing.rejected_at = None
            existing.rejection_note = None
        elif state == ProjectOutputSelectionStateValue.UNSELECTED:
            existing.unselected_at = now
            existing.selection_note = note or existing.selection_note
        elif state == ProjectOutputSelectionStateValue.REJECTED:
            existing.rejected_at = now
            existing.rejection_note = note
        return existing

    def _find_reference(self, project: ProjectRecord, reference_id: str) -> ProjectReferenceAsset:
        for reference in project.reference_assets:
            if reference.reference_id == reference_id:
                return reference
        raise KeyError("没有找到这张项目参考图")

    def _find_output_ref(self, project: ProjectRecord, output_id: str) -> OutputRef:
        for ref in project.selected_output_refs:
            if output_id in {ref.output_id, ref.asset_id, ref.candidate_id, ref.output_ref_id}:
                return ref
        for reference in project.reference_assets:
            if output_id in {reference.asset_ref_id, reference.created_from_output_id, reference.reference_id}:
                return OutputRef(
                    output_ref_id=reference.metadata.get("output_ref_id") or reference.reference_id,
                    source_type="selected_candidate",
                    project_id=project.project_id,
                    job_id=reference.created_from_job_id,
                    asset_id=reference.metadata.get("asset_id"),
                    candidate_id=reference.metadata.get("candidate_id"),
                    output_id=reference.created_from_output_id or reference.asset_ref_id,
                    preview_url=reference.preview_url,
                    thumbnail_url=reference.preview_url,
                    selection_reason=reference.user_note,
                    selected_at=reference.created_at,
                    metadata={"restored_from_reference_id": reference.reference_id},
                )
        output_store = getattr(self.product_service, "output_store", None)
        if output_store is not None:
            for job_id in project.job_ids:
                try:
                    records = output_store.list_by_job(job_id)
                except Exception:
                    continue
                for record in records:
                    if output_id in {record.output_id, record.asset_id, record.candidate_id}:
                        return self._output_ref_from_record(project, record)
        raise KeyError("这张图没有在当前项目里找到")

    def _references_for_output(self, project: ProjectRecord, ref: OutputRef) -> list[ProjectReferenceAsset]:
        identity = self._output_identity(ref)
        return [
            reference
            for reference in project.reference_assets
            if identity
            in {
                reference.asset_ref_id,
                reference.created_from_output_id,
                reference.metadata.get("output_ref_id"),
            }
        ]

    def _output_identity(self, ref: OutputRef) -> str:
        return ref.output_id or ref.asset_id or ref.candidate_id or ref.output_ref_id

    def _enrich_selected_output_ref(self, ref: OutputRef) -> OutputRef:
        if ref.metadata.get("file_path"):
            return ref
        output_store = getattr(self.product_service, "output_store", None)
        if output_store is None:
            return ref
        output_id = ref.output_id or ref.asset_id
        if not output_id:
            return ref
        record = output_store.get_output(output_id)
        if record is None:
            return ref
        metadata = {
            **dict(ref.metadata),
            "file_path": record.file_path,
            "mime_type": record.mime_type,
            "provider": record.provider,
            "model": record.model,
            "v3_owned_output": True,
        }
        return ref.model_copy(
            update={
                "asset_id": ref.asset_id or record.asset_id,
                "candidate_id": ref.candidate_id or record.candidate_id,
                "output_id": ref.output_id or record.output_id,
                "preview_url": ref.preview_url or record.preview_url,
                "thumbnail_url": ref.thumbnail_url or record.thumbnail_url,
                "download_url": ref.download_url or record.download_url,
                "metadata": metadata,
            }
        )

    def _generated_output_use_policy(
        self,
        project: ProjectRecord,
        template_id: str | None = None,
    ) -> ProjectReferenceUsePolicy:
        effective_template_id = template_id or project.primary_template_id
        if effective_template_id == ECOMMERCE_TEMPLATE_ID or project.commerce_profile is not None:
            return ProjectReferenceUsePolicy.PRODUCT_IDENTITY
        if self._looks_like_character_project(project):
            return ProjectReferenceUsePolicy.IDENTITY
        return ProjectReferenceUsePolicy.STYLE

    def _looks_like_character_project(self, project: ProjectRecord) -> bool:
        text = " ".join(
            str(item or "")
            for item in [
                project.user_goal,
                project.short_summary,
                project.confirmed_style_summary,
                *getattr(project, "confirmed_style_tags", []),
            ]
        ).lower()
        return self._looks_like_character_text(text)

    def _looks_like_character_text(self, text: str) -> bool:
        normalized = str(text or "").lower()
        character_tokens = (
            "portrait",
            "person",
            "people",
            "woman",
            "girl",
            "model",
            "beauty",
            "face",
            "fashion",
            "\u5199\u771f",
            "\u7f8e\u5973",
            "\u4eba\u50cf",
            "\u4eba\u7269",
            "\u6a21\u7279",
            "\u5973\u751f",
            "\u5973\u6027",
        )
        return any(token in normalized for token in character_tokens)

    def _initial_uploaded_asset_role(self, *, template_id: str, user_goal: str) -> str:
        if template_id == ECOMMERCE_TEMPLATE_ID:
            return "product_reference"
        if self._looks_like_character_text(user_goal):
            return "face_reference"
        return "unknown_reference"

    def _reference_role_for_policy(self, policy: ProjectReferenceUsePolicy) -> str:
        return {
            ProjectReferenceUsePolicy.IDENTITY: "identity_reference",
            ProjectReferenceUsePolicy.PRODUCT_IDENTITY: "product_identity_reference",
            ProjectReferenceUsePolicy.BRAND_ASSET: "brand_asset_reference",
            ProjectReferenceUsePolicy.COMPOSITION: "composition_reference",
            ProjectReferenceUsePolicy.LIGHTING: "lighting_reference",
            ProjectReferenceUsePolicy.MOOD: "mood_reference",
            ProjectReferenceUsePolicy.PRODUCT: "product_reference",
        }.get(policy, "style_reference")

    def _lock_targets_for_policy(self, policy: ProjectReferenceUsePolicy) -> list[str]:
        if policy == ProjectReferenceUsePolicy.PRODUCT_IDENTITY or policy == ProjectReferenceUsePolicy.PRODUCT:
            return ["shape", "material", "color", "logo_or_label_position", "proportions"]
        if policy == ProjectReferenceUsePolicy.IDENTITY:
            return ["face_identity", "body_identity_direction", "natural_complexion_direction"]
        if policy == ProjectReferenceUsePolicy.BRAND_ASSET:
            return ["logo_shape", "brand_color", "brand_symbol", "layout_position"]
        if policy == ProjectReferenceUsePolicy.LIGHTING:
            return ["lighting", "shadow", "contrast", "mood"]
        if policy == ProjectReferenceUsePolicy.COMPOSITION:
            return ["framing", "camera_angle", "subject_scale", "negative_space"]
        return ["style", "composition", "palette", "lighting"]

    def _selected_output_state_map(self, project: ProjectRecord) -> dict[str, ProjectOutputSelectionStateValue]:
        return {state.output_id: state.selection_state for state in project.selected_output_states}

    def _active_references(self, project: ProjectRecord) -> list[ProjectReferenceAsset]:
        return [ref for ref in project.reference_assets if ref.status == ProjectReferenceStatus.ACTIVE]

    def _reference_context_dict(self, reference: ProjectReferenceAsset) -> dict[str, Any]:
        data = {
            "reference_id": reference.reference_id,
            "source_type": reference.source_type.value,
            "asset_ref_id": reference.asset_ref_id,
            "preview_url": reference.preview_url,
            "label": reference.label,
            "user_note": reference.user_note,
            "use_policy": reference.use_policy.value,
            "created_from_job_id": reference.created_from_job_id,
            "created_from_output_id": reference.created_from_output_id,
            "metadata": dict(reference.metadata),
        }
        data.update(self._reference_file_payload(reference))
        return data

    def _reference_file_payload(self, reference: ProjectReferenceAsset) -> dict[str, Any]:
        if reference.source_type == ProjectReferenceSourceType.UPLOADED:
            upload_record = self.product_service.get_uploaded_asset(reference.asset_ref_id)
            if upload_record is None:
                return {}
            return {
                "asset_id": upload_record.asset_id,
                "role": reference.use_policy.value,
                "file_path": upload_record.file_path,
                "uri": upload_record.content_url,
                "filename": upload_record.filename,
                "mime_type": upload_record.mime_type,
                "content_sha256": self._uploaded_asset_content_sha256(upload_record),
            }
        output_store = getattr(self.product_service, "output_store", None)
        output_id = reference.created_from_output_id or reference.asset_ref_id
        if output_store is None or not output_id:
            return {}
        record = output_store.get_output(output_id)
        if record is None:
            return {}
        return {
            "asset_id": record.output_id,
            "role": reference.use_policy.value,
            "file_path": record.file_path,
            "uri": record.download_url,
            "filename": f"{record.output_id}.{record.output_format}",
            "mime_type": record.mime_type,
            "output_id": record.output_id,
            "candidate_id": record.candidate_id,
            "source_integrity_id": self._output_source_integrity_id(record),
        }

    def _state_change_response(
        self,
        project: ProjectRecord,
        context: ProjectContextPackage,
        *,
        feedback: ProjectFeedbackRecord | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "api_namespace": API_NAMESPACE,
            "route": f"{API_NAMESPACE}/projects/{project.project_id}",
            "project": project.model_dump(mode="json"),
            "context": context.model_dump(mode="json"),
            "metadata": {
                **self._metadata(),
                "project_outputs": self._project_output_items(project, limit=60),
            },
        }
        if feedback is not None:
            payload["feedback"] = feedback.model_dump(mode="json")
        return payload

    def _build_context(
        self,
        project: ProjectRecord,
        continuation_instruction: str | None = None,
        template_id: str | None = None,
        commerce_profile: ProjectCommerceProfile | None = None,
    ) -> ProjectContextPackage:
        now = _utc_now_iso()
        effective_template_id = template_id or project.primary_template_id or GENERAL_TEMPLATE_ID
        effective_commerce_profile = commerce_profile or project.commerce_profile
        timeline_ids = list(project.timeline_refs)
        state_map = self._selected_output_state_map(project)
        selected_ref_candidates = [
            ref
            for ref in project.selected_output_refs
            if state_map.get(self._output_identity(ref), ProjectOutputSelectionStateValue.SELECTED)
            == ProjectOutputSelectionStateValue.SELECTED
        ]
        selected_refs: list[OutputRef] = []
        unresolved_selected_outputs: list[dict[str, Any]] = []
        for ref in selected_ref_candidates:
            canonical = self._canonical_selected_output_ref(project, ref)
            if canonical is None:
                unresolved_selected_outputs.append(
                    {
                        "job_id": ref.job_id,
                        "candidate_id": ref.candidate_id,
                        "asset_id": ref.asset_id,
                        "output_id": ref.output_id,
                        "reason": "legacy_or_unavailable_materialized_output",
                    }
                )
                continue
            selected_refs.append(canonical)
        active_references = self._active_references(project)
        active_uploaded_references = [
            self._reference_context_dict(reference)
            for reference in active_references
            if reference.source_type == ProjectReferenceSourceType.UPLOADED
        ]
        inactive_reference_ids = {
            reference.reference_id
            for reference in project.reference_assets
            if reference.status == ProjectReferenceStatus.INACTIVE
        }
        inactive_asset_ids = {
            reference.asset_ref_id
            for reference in project.reference_assets
            if reference.status == ProjectReferenceStatus.INACTIVE
        }
        legacy_uploaded_references = [
            item
            for item in project.uploaded_asset_refs
            if str(item.get("asset_id") or "").strip() not in inactive_asset_ids
            and str(item.get("reference_id") or "").strip() not in inactive_reference_ids
            and str(item.get("status") or "").strip().lower() != ProjectReferenceStatus.INACTIVE.value
        ]
        active_generated_references: list[dict[str, Any]] = []
        unresolved_generated_references: list[dict[str, Any]] = []
        for reference in active_references:
            if reference.source_type != ProjectReferenceSourceType.GENERATED_SELECTED:
                continue
            payload = self._reference_context_dict(reference)
            if payload.get("file_path") and payload.get("output_id"):
                active_generated_references.append(payload)
            else:
                unresolved_generated_references.append(
                    {
                        "reference_id": reference.reference_id,
                        "asset_ref_id": reference.asset_ref_id,
                        "created_from_output_id": reference.created_from_output_id,
                        "reason": "legacy_or_unavailable_materialized_output",
                    }
                )
        active_avoid_notes = [
            feedback.plain_text
            for feedback in project.feedback_records
            if feedback.status == ProjectFeedbackStatus.ACTIVE
            and feedback.feedback_type == ProjectFeedbackType.AVOID_DIRECTION
        ]
        negative_notes = list(dict.fromkeys([*project.rejected_direction_notes, *active_avoid_notes]))
        tone = self._style_chips(project)
        version = stable_id(
            "project_context",
            project.project_id,
            len(selected_refs),
            len(active_references),
            len(negative_notes),
            continuation_instruction,
            effective_template_id,
            effective_commerce_profile.updated_at if effective_commerce_profile else None,
        )
        metadata: dict[str, Any] = {
            "source": PROJECT_API_SOURCE,
            "positive_context_from_selected_outputs_only": True,
            "unselected_candidates_excluded": True,
            "active_reference_count": len(active_references),
            "active_uploaded_reference_count": len(active_uploaded_references),
            "active_generated_reference_count": len(active_generated_references),
            "suppressed_generated_reference_count": len(unresolved_generated_references),
            "active_negative_feedback_count": len(active_avoid_notes),
            "template_id": effective_template_id,
            "reference_resolution_audit": {
                "retained_selected_output_ids": [ref.output_id for ref in selected_refs if ref.output_id],
                "suppressed_selected_outputs": unresolved_selected_outputs,
                "retained_generated_reference_ids": [
                    str(item.get("reference_id") or item.get("output_id") or "")
                    for item in active_generated_references
                ],
                "suppressed_generated_references": unresolved_generated_references,
                "no_substitution": True,
            },
        }
        selected_visual_references = self._selected_visual_references(
            project,
            effective_template_id,
            selected_refs,
            active_generated_references,
            active_uploaded_references,
        )
        visual_snapshot = self._project_visual_grammar_snapshot(
            project=project,
            context_version=version,
            selected_refs=selected_refs,
            active_generated_references=active_generated_references,
            active_uploaded_references=active_uploaded_references,
            negative_notes=negative_notes,
            tone=tone,
        )
        template_policy = self._project_template_consistency_policy(project, effective_template_id)
        strong_reference_bindings = self._project_strong_reference_bindings(
            project=project,
            template_id=effective_template_id,
            selected_visual_references=selected_visual_references,
        )
        reference_policy_package = self.reference_channel_policy_module.resolve(
            project_id=project.project_id,
            job_id=None,
            user_input=continuation_instruction or project.user_goal,
            subject_type=str(template_policy.get("identity_lock_default") or "generic"),
            template_id=effective_template_id,
            strong_bindings=strong_reference_bindings,
            selected_outputs=[item.model_dump(mode="json") for item in selected_refs],
            advanced_reference_controls=self._clean_advanced_reference_controls(
                project.metadata.get("advanced_reference_controls")
            ),
            metadata=project.metadata,
        )
        identity_lock_profiles = self._project_identity_lock_profiles(
            project=project,
            template_policy=template_policy,
            strong_reference_bindings=strong_reference_bindings,
            visual_snapshot=visual_snapshot,
            reference_policy_package=reference_policy_package.model_dump(mode="json"),
        )
        project_identity_anchors = self._project_identity_anchors(
            project=project,
            template_policy=template_policy,
            selected_refs=selected_refs,
            strong_reference_bindings=strong_reference_bindings,
            identity_lock_profiles=identity_lock_profiles,
            reference_policy_package=reference_policy_package.model_dump(mode="json"),
        )
        strong_reference_continuation_plan = self._project_strong_reference_continuation_plan(
            project=project,
            anchors=project_identity_anchors,
            strong_reference_bindings=strong_reference_bindings,
            reference_policy_package=reference_policy_package.model_dump(mode="json"),
        )
        general_suite_role_plan = self._project_general_suite_role_plan(
            project=project,
            template_id=effective_template_id,
            continuation_instruction=continuation_instruction,
            metadata={**project.metadata, "requested_image_count": project.metadata.get("requested_image_count")},
        )
        batch_identity_diversity_review = self._project_batch_identity_diversity_review(
            project=project,
            anchors=project_identity_anchors,
            general_suite_role_plan=general_suite_role_plan,
        )
        negative_visual_memory = self._project_negative_visual_memory(negative_notes)
        metadata["visual_continuity_strength"] = visual_snapshot["continuity_strength"]
        metadata["visual_snapshot_id"] = visual_snapshot["snapshot_id"]
        metadata["strong_reference_binding_count"] = len(strong_reference_bindings)
        metadata["identity_lock_count"] = len(identity_lock_profiles)
        metadata["project_identity_anchor_count"] = len(project_identity_anchors)
        metadata["strong_reference_continuation_plan_id"] = strong_reference_continuation_plan.get("plan_id")
        metadata["reference_policy_package_id"] = reference_policy_package.package_id
        metadata["doc93_reference_channel_policy"] = bool(reference_policy_package.applies)
        metadata["general_suite_role_plan_id"] = general_suite_role_plan.get("plan_id")
        metadata["batch_identity_diversity_review_id"] = batch_identity_diversity_review.get("review_id")
        metadata["template_consistency_policy"] = template_policy
        if effective_template_id == ECOMMERCE_TEMPLATE_ID and effective_commerce_profile is not None:
            metadata["commerce_profile"] = effective_commerce_profile.model_dump(mode="json")
            metadata["product_reference_required"] = True
        return ProjectContextPackage(
            project_id=project.project_id,
            context_version=version,
            goal_summary=project.short_summary or project.user_goal,
            template_id=effective_template_id,
            linked_brand_id=project.linked_brand_id,
            confirmed_visual_tone=tone,
            selected_reference_assets=active_generated_references,
            selected_output_assets=selected_refs,
            uploaded_reference_assets=active_uploaded_references or legacy_uploaded_references,
            selected_visual_references=selected_visual_references,
            visual_grammar_snapshot=visual_snapshot,
            strong_reference_bindings=strong_reference_bindings,
            identity_lock_profiles=identity_lock_profiles,
            project_identity_anchors=project_identity_anchors,
            strong_reference_continuation_plan=strong_reference_continuation_plan,
            resolved_reference_policy_package=reference_policy_package.model_dump(mode="json"),
            general_suite_role_plan=general_suite_role_plan,
            batch_identity_diversity_review=batch_identity_diversity_review,
            negative_visual_memory=negative_visual_memory,
            template_consistency_policy=template_policy,
            confirmed_visual_profile_summary=self._visual_profile_summary(project, tone, selected_refs),
            visual_continuity_strength=visual_snapshot["continuity_strength"],
            rejected_style_tags=negative_notes,
            negative_direction_notes=negative_notes,
            negative_visual_directions=negative_notes,
            continuation_instruction=continuation_instruction,
            source_timeline_item_ids=timeline_ids,
            created_at=now,
            metadata=metadata,
        )

    def _selected_visual_references(
        self,
        project: ProjectRecord,
        template_id: str,
        selected_refs: list[OutputRef],
        active_generated_references: list[dict[str, Any]],
        active_uploaded_references: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        references: list[dict[str, Any]] = []
        strong_uploaded_references: list[dict[str, Any]] = []
        soft_uploaded_references: list[dict[str, Any]] = []
        for item in active_uploaded_references:
            try:
                policy = ProjectReferenceUsePolicy(str(item.get("use_policy") or "general"))
            except ValueError:
                policy = ProjectReferenceUsePolicy.GENERAL
            if policy == ProjectReferenceUsePolicy.PRODUCT and template_id == ECOMMERCE_TEMPLATE_ID:
                policy = ProjectReferenceUsePolicy.PRODUCT_IDENTITY
            payload = dict(item)
            payload.setdefault("source_type", ProjectReferenceSourceType.UPLOADED.value)
            payload["use_policy"] = policy.value
            payload.setdefault("role", self._reference_role_for_policy(policy))
            payload.setdefault(
                "strength",
                "hard"
                if policy
                in {
                    ProjectReferenceUsePolicy.IDENTITY,
                    ProjectReferenceUsePolicy.PRODUCT_IDENTITY,
                    ProjectReferenceUsePolicy.PRODUCT,
                    ProjectReferenceUsePolicy.BRAND_ASSET,
                }
                else "medium",
            )
            payload.setdefault("lock_targets", self._lock_targets_for_policy(policy))
            if policy in {
                ProjectReferenceUsePolicy.IDENTITY,
                ProjectReferenceUsePolicy.PRODUCT_IDENTITY,
                ProjectReferenceUsePolicy.PRODUCT,
                ProjectReferenceUsePolicy.BRAND_ASSET,
            }:
                strong_uploaded_references.append(payload)
            else:
                soft_uploaded_references.append(payload)
        references.extend(strong_uploaded_references)
        generated_by_id = {
            str(
                item.get("output_id")
                or item.get("created_from_output_id")
                or item.get("asset_ref_id")
                or item.get("asset_id")
                or ""
            ): item
            for item in active_generated_references
        }
        selected_policy = self._generated_output_use_policy(project, template_id)
        for ref in selected_refs:
            identity = self._output_identity(ref)
            generated_payload = generated_by_id.get(str(ref.output_id or "")) or generated_by_id.get(identity) or {}
            payload = {
                "source_type": "selected_output",
                "output_id": ref.output_id,
                "asset_id": ref.asset_id,
                "candidate_id": ref.candidate_id,
                "file_path": ref.metadata.get("file_path"),
                "source_integrity_id": ref.metadata.get("source_integrity_id"),
                "preview_url": ref.preview_url,
                "thumbnail_url": ref.thumbnail_url,
                "download_url": ref.download_url,
                "selection_reason": ref.selection_reason,
                "use_policy": selected_policy.value,
                "role": self._reference_role_for_policy(selected_policy),
                "strength": "medium",
                "lock_targets": self._lock_targets_for_policy(selected_policy),
                "metadata": dict(ref.metadata),
            }
            payload.update({key: value for key, value in generated_payload.items() if value not in (None, "", [], {})})
            payload["source_type"] = "selected_output"
            payload["use_policy"] = selected_policy.value
            payload["role"] = self._reference_role_for_policy(selected_policy)
            references.append(payload)
        for item in [*active_generated_references, *soft_uploaded_references]:
            references.append(dict(item))
        return self._dedupe_visual_reference_payloads(references)

    def _project_template_consistency_policy(self, project: ProjectRecord, template_id: str) -> dict[str, Any]:
        selected_policy = self._generated_output_use_policy(project, template_id)
        if selected_policy == ProjectReferenceUsePolicy.PRODUCT_IDENTITY:
            return {
                "policy_id": "product_truth",
                "primary_priority": "product_identity",
                "strong_reference_default": "hard",
                "identity_lock_default": "product",
                "review_focus": ["product_identity_drift", "unrelated_product_or_object", "visible_text_artifact"],
            }
        if selected_policy == ProjectReferenceUsePolicy.IDENTITY:
            return {
                "policy_id": "portrait_identity",
                "primary_priority": "character_identity",
                "strong_reference_default": "hard",
                "identity_lock_default": "character",
                "review_focus": ["identity_drift", "hair_or_outfit_drift", "camera_lighting_drift"],
            }
        return {
            "policy_id": "general_visual_grammar",
            "primary_priority": "style_and_visual_grammar",
            "strong_reference_default": "medium",
            "identity_lock_default": "generic",
            "review_focus": ["style_drift", "composition_mismatch", "visible_text_artifact"],
        }

    def _project_strong_reference_bindings(
        self,
        *,
        project: ProjectRecord,
        template_id: str,
        selected_visual_references: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        bindings: list[dict[str, Any]] = []
        for item in selected_visual_references:
            source_id = str(
                item.get("output_id")
                or item.get("asset_id")
                or item.get("asset_ref_id")
                or item.get("reference_id")
                or ""
            ).strip()
            if not source_id:
                continue
            try:
                use_policy = ProjectReferenceUsePolicy(str(item.get("use_policy") or "style"))
            except ValueError:
                use_policy = self._generated_output_use_policy(project, template_id)
            strength = str(item.get("strength") or "")
            if not strength:
                strength = "hard" if use_policy in {
                    ProjectReferenceUsePolicy.IDENTITY,
                    ProjectReferenceUsePolicy.PRODUCT_IDENTITY,
                    ProjectReferenceUsePolicy.BRAND_ASSET,
                } else "medium"
            file_path = str(item.get("file_path") or "").strip()
            bindings.append(
                {
                    "binding_id": stable_id("project_strong_reference_binding", project.project_id, source_id, use_policy.value),
                    "source_type": item.get("source_type") or "project_reference",
                    "source_id": source_id,
                    "asset_id": item.get("asset_id") or item.get("asset_ref_id") or source_id,
                    "output_id": item.get("output_id") or item.get("created_from_output_id"),
                    "source_integrity_id": item.get("source_integrity_id")
                    or (item.get("metadata") or {}).get("source_integrity_id"),
                    "file_path": file_path or None,
                    "preview_url": item.get("preview_url") or item.get("thumbnail_url") or item.get("uri"),
                    "role": item.get("role") or self._reference_role_for_policy(use_policy),
                    "strength": strength,
                    "use_policy": use_policy.value,
                    "lock_targets": item.get("lock_targets") or self._lock_targets_for_policy(use_policy),
                    "provider_input_required": bool(
                        file_path and (strength == "hard" or item.get("source_type") == "selected_output")
                    ),
                    "prompt_only_fallback": not bool(file_path),
                    "user_visible_label": self._reference_user_label(use_policy),
                    "metadata": {
                        "selected_project_anchor": item.get("source_type") == "selected_output",
                        "canonical_output_binding": bool(
                            (item.get("metadata") or {}).get("canonical_output_binding")
                        ),
                        "source_integrity_id": item.get("source_integrity_id")
                        or (item.get("metadata") or {}).get("source_integrity_id"),
                        "template_id": template_id,
                    },
                }
            )
        return self._dedupe_visual_reference_payloads(bindings)

    def _project_identity_lock_profiles(
        self,
        *,
        project: ProjectRecord,
        template_policy: dict[str, Any],
        strong_reference_bindings: list[dict[str, Any]],
        visual_snapshot: dict[str, Any],
        reference_policy_package: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not strong_reference_bindings:
            return []
        subject_type = str(template_policy.get("identity_lock_default") or "generic")
        reference_policy_package = dict(reference_policy_package or {})
        effective_owners = (
            reference_policy_package.get("effective_channel_owners")
            if isinstance(reference_policy_package.get("effective_channel_owners"), dict)
            else {}
        )
        hair_locked = self._reference_channel_owner_is_locked(effective_owners, "hair_direction")
        wardrobe_locked = self._reference_channel_owner_is_locked(effective_owners, "wardrobe_structure")
        camera_locked = self._reference_channel_owner_is_locked(effective_owners, "camera_composition")
        lighting_locked = self._reference_channel_owner_is_locked(effective_owners, "lighting_color")
        style_locked = self._reference_channel_owner_is_locked(effective_owners, "style_finish")
        structured_appearance = wardrobe_locked
        if subject_type == "character":
            keep_rules = [
                "keep the same person's recognizable face geometry, facial-feature relationships, age direction, and body identity direction",
                "follow the current prompt for hair, makeup, wardrobe, lighting, scene, camera, mood, and style unless a channel is explicitly locked",
            ]
            avoid_rules = ["face drift", "same beauty type but different person"]
            if hair_locked:
                keep_rules.append("keep the explicitly assigned hair direction")
                avoid_rules.append("locked hair direction drift")
            if wardrobe_locked:
                keep_rules.append("keep the explicitly assigned wardrobe direction")
                avoid_rules.append("locked wardrobe direction drift")
            if structured_appearance:
                keep_rules.append(
                    "keep the same appearance asset structure: silhouette, layer order, neckline or collar direction, sleeve or cuff shape, closure or sash logic, material behavior, pattern family, trim placement, and accessory placement coherent"
                )
                avoid_rules.extend(
                    [
                        "appearance asset replacement",
                        "garment structure drift",
                        "pattern family drift",
                        "trim or accessory placement drift",
                    ]
                )
        elif subject_type == "product":
            keep_rules = [
                "keep product shape, material, color, and proportions",
                "do not invent extra products, labels, or unsupported details",
            ]
            avoid_rules = ["product identity drift", "unrelated object", "distorted label or logo"]
        else:
            keep_rules = [
                "keep selected style, composition, palette, and lighting",
                "allow new content only when it follows the project direction",
            ]
            avoid_rules = ["style drift", "unrelated prop", "cluttered composition"]
        return [
            {
                "lock_id": stable_id("project_identity_lock", project.project_id, subject_type, len(strong_reference_bindings)),
                "project_id": project.project_id,
                "subject_type": subject_type,
                "lock_strength": "strong" if any(item.get("strength") == "hard" for item in strong_reference_bindings) else "normal",
                "source_binding_ids": [str(item.get("binding_id")) for item in strong_reference_bindings if item.get("binding_id")],
                "keep_rules": keep_rules,
                "allowed_changes": ["new scene details requested by the user", "compatible image-suite variation"],
                "forbidden_drift": avoid_rules,
                "prompt_constraints": [
                    *keep_rules,
                    *(
                        [str(item) for item in visual_snapshot.get("style_rules", [])[:4]]
                        if subject_type != "character" or style_locked
                        else []
                    ),
                ],
                "negative_constraints": [
                    *avoid_rules,
                    *[str(item) for item in visual_snapshot.get("negative_directions", [])[:4]],
                ],
                "user_visible_summary": self._identity_lock_user_summary(subject_type),
                "metadata": {
                    "template_policy": template_policy,
                    "structured_appearance_lock": structured_appearance,
                    "doc93_reference_channel_policy": bool(reference_policy_package.get("applies")),
                    "reference_policy_package_id": reference_policy_package.get("package_id"),
                    "camera_locked": camera_locked,
                    "lighting_locked": lighting_locked,
                },
            }
        ]

    def _project_identity_anchors(
        self,
        *,
        project: ProjectRecord,
        template_policy: dict[str, Any],
        selected_refs: list[OutputRef],
        strong_reference_bindings: list[dict[str, Any]],
        identity_lock_profiles: list[dict[str, Any]],
        reference_policy_package: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not selected_refs and not strong_reference_bindings:
            return []
        subject_type = str(template_policy.get("identity_lock_default") or "generic")
        output_ids = self._dedupe_text([self._output_identity(ref) for ref in selected_refs])
        asset_ids = self._dedupe_text([str(ref.asset_id or ref.output_id or "") for ref in selected_refs])
        candidate_ids = self._dedupe_text([str(ref.candidate_id or "") for ref in selected_refs])
        binding_ids = self._dedupe_text([str(item.get("binding_id") or "") for item in strong_reference_bindings])
        provider_required = any(bool(item.get("provider_input_required")) for item in strong_reference_bindings)
        lock_rules = self._dedupe_text(
            rule
            for profile in identity_lock_profiles
            for rule in [*profile.get("keep_rules", []), *profile.get("prompt_constraints", [])]
        )
        reference_policy_package = dict(reference_policy_package or {})
        effective_owners = (
            reference_policy_package.get("effective_channel_owners")
            if isinstance(reference_policy_package.get("effective_channel_owners"), dict)
            else {}
        )
        style_reference_active = self._reference_channel_owner_is_locked(effective_owners, "style_finish")
        return [
            {
                "anchor_id": stable_id("project_identity_anchor", project.project_id, subject_type, ",".join(output_ids), ",".join(binding_ids)),
                "project_id": project.project_id,
                "subject_type": "character" if subject_type == "character" else "product" if subject_type == "product" else "generic",
                "source_output_ids": output_ids,
                "source_asset_ids": asset_ids,
                "source_candidate_ids": candidate_ids,
                "source_binding_ids": binding_ids,
                "active": True,
                "anchor_strength": "strong" if provider_required or subject_type in {"character", "product"} else "medium",
                "identity_keep_rules": lock_rules[:8],
                "style_keep_rules": list(self._style_chips(project))[:6] if style_reference_active else [],
                "allowed_variations": self._anchor_allowed_variations(subject_type),
                "forbidden_drift": self._anchor_forbidden_drift(subject_type),
                "provider_reference_required": provider_required,
                "prompt_only_fallback": not provider_required,
                "user_visible_summary": [
                    "Selected image will guide the next generation.",
                    "V3 keeps the important identity/style details while allowing useful variation.",
                ],
                "metadata": {
                    "doc": "58",
                    "extends": ["93"],
                    "template_policy": template_policy.get("policy_id"),
                    "reference_policy_package_id": reference_policy_package.get("package_id"),
                },
            }
        ]

    def _project_strong_reference_continuation_plan(
        self,
        *,
        project: ProjectRecord,
        anchors: list[dict[str, Any]],
        strong_reference_bindings: list[dict[str, Any]],
        reference_policy_package: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not anchors and not strong_reference_bindings:
            return {}
        provider_ids = self._dedupe_text(
            str(item.get("asset_id") or item.get("output_id") or item.get("source_id") or "")
            for item in strong_reference_bindings
            if item.get("provider_input_required")
        )
        prompt_only_ids = self._dedupe_text(
            str(item.get("asset_id") or item.get("output_id") or item.get("source_id") or "")
            for item in strong_reference_bindings
            if item.get("prompt_only_fallback") and not item.get("provider_input_required")
        )
        lock_targets = self._dedupe_text(
            str(target)
            for item in strong_reference_bindings
            for target in item.get("lock_targets", [])
        )
        reference_policy_package = dict(reference_policy_package or {})
        effective_owners = (
            reference_policy_package.get("effective_channel_owners")
            if isinstance(reference_policy_package.get("effective_channel_owners"), dict)
            else {}
        )
        structured_appearance = self._reference_channel_owner_is_locked(effective_owners, "wardrobe_structure")
        provider_rules = self._dedupe_text(reference_policy_package.get("provider_prompt_rules") or [])
        provider_negative_rules = self._dedupe_text(reference_policy_package.get("provider_negative_rules") or [])
        prompt_additions = self._dedupe_text(
            [
                "use active project reference images as the strongest positive references",
                "preserve uploaded prototype identity/product details before extending selected generated style",
                *provider_rules,
                *(
                    [
                        "when styling defines the project, preserve the same appearance asset structure: silhouette, layer order, collar or neckline direction, sleeve or cuff shape, closure or sash logic, material behavior, pattern family, trim placement, and accessory placement"
                    ]
                    if structured_appearance
                    else []
                ),
                *[rule for anchor in anchors for rule in anchor.get("identity_keep_rules", [])],
                *[rule for anchor in anchors for rule in anchor.get("style_keep_rules", [])],
            ]
        )[:12]
        negative_additions = self._dedupe_text(
            [
                "do not use unselected candidates as positive references",
                *provider_negative_rules,
                *(
                    [
                        "do not redesign the appearance asset",
                        "do not change garment structure or layer logic",
                        "do not replace pattern family, trim placement, or accessory placement without a user request",
                    ]
                    if structured_appearance
                    else []
                ),
                *[rule for anchor in anchors for rule in anchor.get("forbidden_drift", [])],
            ]
        )[:12]
        return {
            "plan_id": stable_id("strong_reference_continuation_plan", project.project_id, ",".join(item.get("anchor_id", "") for item in anchors)),
            "project_id": project.project_id,
            "active_anchor_ids": [item.get("anchor_id") for item in anchors if item.get("anchor_id")],
            "provider_required_reference_ids": provider_ids,
            "prompt_only_reference_ids": prompt_only_ids,
            "lock_targets": lock_targets,
            "prompt_additions": prompt_additions,
            "negative_additions": negative_additions,
            "reference_mode": "provider_image_reference" if provider_ids else "prompt_only_reference" if prompt_only_ids else "context_reference",
            "user_visible_summary": ["Selected result is saved as the next reference."],
            "metadata": {
                "doc": "58",
                "extends": ["93"],
                "strong_binding_count": len(strong_reference_bindings),
                "reference_policy_package_id": reference_policy_package.get("package_id"),
                "doc93_reference_channel_policy": bool(reference_policy_package.get("applies")),
            },
        }

    def _project_general_suite_role_plan(
        self,
        *,
        project: ProjectRecord,
        template_id: str,
        continuation_instruction: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if template_id != GENERAL_TEMPLATE_ID:
            return {}
        requested_count = _bounded_requested_image_count(metadata.get("requested_image_count")) or 2
        requested_count = max(1, requested_count)
        mode = str(metadata.get("effective_variation_mode") or metadata.get("variation_mode") or "delivery_suite")
        if mode not in {"selection_candidates", "delivery_suite", "creative_exploration", "format_layout_adaptation"}:
            mode = "delivery_suite"
        roles = self._suite_roles_for_mode(mode, requested_count, has_anchor=bool(project.selected_output_refs))
        return {
            "plan_id": stable_id("general_suite_role_plan", project.project_id, mode, requested_count, continuation_instruction or project.user_goal),
            "project_id": project.project_id,
            "variation_mode": mode,
            "requested_image_count": requested_count,
            "roles": roles,
            "prompt_additions": [
                f"Image {index}: {role['label']} - {role['shot_instruction']}"
                for index, role in enumerate(roles, 1)
            ],
            "batch_review_rules": [
                "each output should have a clear role in the set",
                "avoid repeating the same pose/crop when roles differ",
                "keep the same project direction across all roles",
            ],
            "user_visible_summary": ["V3 planned distinct uses for this set."],
            "metadata": {"doc": "58", "role_count": len(roles)},
        }

    def _project_batch_identity_diversity_review(
        self,
        *,
        project: ProjectRecord,
        anchors: list[dict[str, Any]],
        general_suite_role_plan: dict[str, Any],
    ) -> dict[str, Any]:
        applies = bool(anchors or general_suite_role_plan.get("roles"))
        return {
            "review_id": stable_id("batch_identity_diversity_review", project.project_id, len(anchors), general_suite_role_plan.get("plan_id")),
            "project_id": project.project_id,
            "applies": applies,
            "status": "planned" if applies else "not_applicable",
            "identity_keep_checks": self._dedupe_text(rule for anchor in anchors for rule in anchor.get("identity_keep_rules", [])[:4]),
            "diversity_checks": [
                "keep identity/style consistent without cloning the same still",
                "vary pose, expression, camera angle, crop, scene, or layout according to mode",
            ] if applies else [],
            "suite_role_checks": [
                f"{index}. {role.get('label')}: {role.get('purpose')}"
                for index, role in enumerate(general_suite_role_plan.get("roles", []), 1)
            ],
            "retry_patch": {
                "prompt_additions": ["preserve anchor while varying pose, expression, angle, crop, or role"],
                "negative_additions": ["same exact expression, head angle, pose, and crop in every image"],
            } if applies else {},
            "user_visible_summary": ["V3 will keep the direction consistent and avoid cloned frames."] if applies else [],
            "metadata": {"doc": "58"},
        }

    def _anchor_allowed_variations(self, subject_type: str) -> list[str]:
        if subject_type == "character":
            return ["expression", "gaze", "pose", "head angle", "camera distance", "small hair movement", "compatible scene"]
        if subject_type == "product":
            return ["camera angle", "lighting", "surface", "lifestyle scene", "crop"]
        return ["framing", "crop", "scene detail", "camera distance"]

    def _anchor_forbidden_drift(self, subject_type: str) -> list[str]:
        if subject_type == "character":
            return ["identity drift", "face swap", "major body type drift", "major hair color drift", "cloned stills"]
        if subject_type == "product":
            return ["product identity drift", "wrong label", "extra unrelated product", "distorted material"]
        return ["style drift", "unrelated object drift", "cluttered composition"]

    def _suite_roles_for_mode(self, mode: str, requested_count: int, *, has_anchor: bool) -> list[dict[str, Any]]:
        keep = "same recognizable subject/person" if has_anchor else "same subject direction"
        role_sets = {
            "selection_candidates": [
                ("best_frame_candidate", "Best pick", "close matching frame with subtle expression or pose change"),
                ("angle_candidate", "Angle comparison", "same style with a small angle or camera-distance change"),
                ("crop_candidate", "Crop comparison", "same treatment with a different crop"),
                ("mood_candidate", "Mood comparison", "same direction with a subtle gaze or light change"),
            ],
            "creative_exploration": [
                ("hero_direction", "Main route", "strong subject-focused hero image"),
                ("scene_direction", "Scene route", "same subject in a compatible different scene"),
                ("styling_direction", "Styling route", "controlled styling or atmosphere variation"),
                ("layout_direction", "Layout route", "clean layout-friendly option"),
            ],
            "format_layout_adaptation": [
                ("square_cover", "Square cover", "square-safe composition"),
                ("vertical_cover", "Vertical cover", "vertical cover crop with clean negative space"),
                ("horizontal_layout", "Horizontal layout", "horizontal composition with side space"),
                ("close_crop", "Close crop", "tight usable crop"),
            ],
            "delivery_suite": [
                ("cover_hero", "Cover image", "hero image with strongest first impression"),
                ("portrait_or_subject_focus", "Subject focus", "closer subject-led frame"),
                ("side_or_three_quarter_angle", "Angle variation", "side or three-quarter angle from the same shoot"),
                ("wide_scene_or_context", "Scene context", "wider scene or atmosphere frame"),
            ],
        }
        roles = role_sets.get(mode, role_sets["delivery_suite"])[:requested_count]
        return [
            {
                "role_id": stable_id("general_suite_role", mode, index, label),
                "label": label,
                "purpose": purpose,
                "shot_instruction": shot,
                "variation_axes": ["pose", "angle", "crop", "scene"] if mode != "selection_candidates" else ["expression", "pose", "crop"],
                "keep_rules": [keep, "coherent lighting and palette"],
                "avoid_rules": ["collage", "visible text", "exact duplicate still"],
            }
            for index, (label, purpose, shot) in enumerate(roles, 1)
        ]

    def _project_negative_visual_memory(self, negative_notes: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "source": "project_feedback",
                "code": "negative_direction",
                "message": note,
                "severity": "medium",
            }
            for note in self._dedupe_text(negative_notes)[:12]
        ]

    def _reference_user_label(self, policy: ProjectReferenceUsePolicy) -> str:
        if policy == ProjectReferenceUsePolicy.IDENTITY:
            return "Use selected image to keep the person consistent"
        if policy in {ProjectReferenceUsePolicy.PRODUCT, ProjectReferenceUsePolicy.PRODUCT_IDENTITY}:
            return "Use selected image to keep the product consistent"
        if policy == ProjectReferenceUsePolicy.BRAND_ASSET:
            return "Use selected image to keep brand assets consistent"
        return "Use selected image to keep the visual direction consistent"

    def _identity_lock_user_summary(self, subject_type: str) -> list[str]:
        if subject_type == "character":
            return ["Keeps the same person's recognizable face; styling and scene follow the current request"]
        if subject_type == "product":
            return ["Keeps product shape, material, color, proportions, and label position"]
        return ["Keeps the selected style, composition, palette, and lighting"]

    def _reference_channel_owner_is_locked(self, owners: dict[str, Any], channel: str) -> bool:
        owner = str(owners.get(channel) or "")
        return owner.startswith("reference:") and owner.rsplit(":", 1)[-1] in {"hard", "medium"}

    def _project_visual_grammar_snapshot(
        self,
        *,
        project: ProjectRecord,
        context_version: str,
        selected_refs: list[OutputRef],
        active_generated_references: list[dict[str, Any]],
        active_uploaded_references: list[dict[str, Any]],
        negative_notes: list[str],
        tone: list[str],
    ) -> dict[str, Any]:
        selected_output_ids = self._dedupe_text([self._output_identity(ref) for ref in selected_refs])
        generated_reference_ids = self._dedupe_text(
            [
                str(item.get("asset_ref_id") or item.get("asset_id") or item.get("output_id") or "")
                for item in active_generated_references
            ]
        )
        uploaded_reference_ids = self._dedupe_text(
            [
                str(item.get("asset_ref_id") or item.get("asset_id") or item.get("reference_id") or "")
                for item in active_uploaded_references
            ]
        )
        continuity_strength = "strong" if selected_output_ids else "medium" if generated_reference_ids or uploaded_reference_ids else "weak"
        snapshot_id = stable_id(
            "project_visual_grammar_snapshot",
            project.project_id,
            context_version,
            ",".join(selected_output_ids),
            ",".join(generated_reference_ids),
            ",".join(uploaded_reference_ids),
            ",".join(negative_notes),
        )
        return {
            "snapshot_id": snapshot_id,
            "project_id": project.project_id,
            "context_version": context_version,
            "positive_anchor_output_ids": selected_output_ids,
            "active_reference_ids": generated_reference_ids,
            "uploaded_reference_ids": uploaded_reference_ids,
            "style_rules": tone,
            "negative_directions": negative_notes,
            "continuity_strength": continuity_strength,
            "positive_context_from_selected_outputs_only": True,
            "unselected_candidates_excluded": True,
        }

    def _visual_profile_summary(self, project: ProjectRecord, tone: list[str], selected_refs: list[OutputRef]) -> str:
        parts = [project.short_summary or project.user_goal]
        if tone:
            parts.append(" / ".join(tone[:3]))
        if selected_refs:
            parts.append("uses selected project images only for their assigned continuation channels")
        return self._short_text(" | ".join(part for part in parts if part), 160)

    def _dedupe_visual_reference_payloads(self, references: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in references:
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            identity = str(
                item.get("source_integrity_id")
                or metadata.get("source_integrity_id")
                or item.get("output_id")
                or item.get("asset_id")
                or item.get("asset_ref_id")
                or item.get("reference_id")
                or ""
            )
            if not identity or identity in seen:
                continue
            seen.add(identity)
            unique.append({key: value for key, value in item.items() if value not in (None, "", [], {})})
        return unique

    def _memory_summary(self, project: ProjectRecord) -> ProjectMemorySummary:
        timeline = self.project_store.list_timeline(project.project_id)
        state_map = self._selected_output_state_map(project)
        selected_refs = [
            ref
            for ref in project.selected_output_refs
            if state_map.get(self._output_identity(ref), ProjectOutputSelectionStateValue.SELECTED)
            == ProjectOutputSelectionStateValue.SELECTED
        ]
        latest_thumbnails: list[str] = []
        if project.primary_template_id != ECOMMERCE_TEMPLATE_ID:
            latest_thumbnails = [
                ref.thumbnail_url or ref.preview_url
                for ref in selected_refs
                if ref.thumbnail_url or ref.preview_url
            ][:3]
        if not latest_thumbnails:
            latest_thumbnails = self._latest_generated_thumbnail_urls(project)
        last_action = timeline[-1].title if timeline else "项目已创建"
        return ProjectMemorySummary(
            project_id=project.project_id,
            title=project.title,
            goal=project.short_summary,
            primary_template_id=project.primary_template_id,
            scenario_id=self._scenario_id_for_template(project.primary_template_id),
            active_template_label=self._template_label(project.primary_template_id),
            latest_thumbnail_urls=latest_thumbnails,
            confirmed_style_chips=self._style_chips(project),
            selected_asset_count=len(selected_refs),
            job_count=len(project.job_ids),
            latest_job_status=self._latest_project_job_status(project),
            last_action_label=last_action,
            updated_at=project.updated_at,
            next_suggested_actions=self._next_actions(project),
        )

    def _latest_project_job_status(self, project: ProjectRecord) -> str | None:
        """Return one safe lifecycle value for recent-project rendering.

        Project cards must not imply that a terminally blocked/failed job is
        still generating merely because it has no output thumbnail.  This is a
        derived read model: the Product API record remains the source of truth,
        and no provider/review payload is copied into the project summary.
        """

        for job_id in reversed(project.job_ids):
            try:
                status = self.product_service.get_job(job_id)
            except Exception:
                continue
            value = getattr(status, "status", None)
            if value is None:
                continue
            normalized = getattr(value, "value", value)
            normalized = str(normalized or "").strip().lower()
            if normalized and normalized != ProductJobStatusValue.NOT_FOUND.value:
                return normalized
        return None

    def _latest_generated_thumbnail_urls(self, project: ProjectRecord, limit: int = 3) -> list[str]:
        if project.primary_template_id == ECOMMERCE_TEMPLATE_ID:
            urls: list[str] = []
            for item in self._project_output_items(
                project,
                limit=max(12, int(limit or 3) * 4),
                compact=True,
            ):
                url = item.get("thumbnail_url") or item.get("preview_url") or item.get("download_url")
                if url and not str(url).startswith("mock://"):
                    urls.append(str(url))
                if len(dict.fromkeys(urls)) >= limit:
                    break
            return list(dict.fromkeys(urls))[:limit]
        output_store = getattr(self.product_service, "output_store", None)
        if output_store is None:
            return []
        urls: list[str] = []
        for job_id in reversed(project.job_ids):
            if not self._project_job_delivery_is_settled(job_id):
                continue
            try:
                records = output_store.list_by_job(job_id)
            except Exception:
                continue
            delivery = self._delivery_annotations_for_records(records)
            for record in sorted(records, key=lambda item: item.created_at or "", reverse=True):
                delivery_state = delivery.get(self._output_record_identity(record), {}).get("delivery_state")
                if delivery_state != "final_delivery":
                    continue
                url = record.thumbnail_url or record.preview_url or record.download_url
                if url and not str(url).startswith("mock://"):
                    urls.append(str(url))
                    if len(dict.fromkeys(urls)) >= limit:
                        return list(dict.fromkeys(urls))[:limit]
        return list(dict.fromkeys(urls))[:limit]

    def _delivery_annotations_for_records(self, records: list[Any]) -> dict[str, dict[str, Any]]:
        usable_records = [record for record in records if self._output_record_has_usable_image(record)]
        if not usable_records:
            return {}
        requested_count = self._delivery_requested_image_count(usable_records)
        attempt_groups: dict[int, list[Any]] = {}
        for record in usable_records:
            attempt_groups.setdefault(self._output_record_retry_attempt(record), []).append(record)
        if not attempt_groups:
            return {}
        for group in attempt_groups.values():
            group.sort(key=lambda item: item.created_at or "")
        sorted_attempts = sorted(attempt_groups)
        preferred_records = [
            record
            for record in usable_records
            if bool((getattr(record, "metadata", None) or {}).get("delivery_preferred_output"))
        ]
        preference_active = bool(preferred_records)
        if preference_active:
            preferred_records.sort(key=lambda item: item.created_at or "")
            final_records = preferred_records[:requested_count]
            final_attempt = self._output_record_retry_attempt(final_records[0])
        else:
            complete_attempts = [
                attempt
                for attempt in sorted_attempts
                if len(attempt_groups.get(attempt, [])) >= requested_count
            ]
            final_attempt = complete_attempts[-1] if complete_attempts else max(
                sorted_attempts,
                key=lambda attempt: (len(attempt_groups.get(attempt, [])), attempt),
            )
            final_records = attempt_groups.get(final_attempt, [])[:requested_count]
        final_records = [
            record
            for record in final_records
            if not self._output_record_is_review_rejected(record)
        ]
        final_attempts = sorted({self._output_record_retry_attempt(record) for record in final_records})
        final_ids = {self._output_record_identity(record) for record in final_records}
        annotations: dict[str, dict[str, Any]] = {}
        for attempt, group in attempt_groups.items():
            retry_codes = self._delivery_retry_reason_codes(group)
            for record in group:
                identity = self._output_record_identity(record)
                if not identity:
                    continue
                delivery_state = "final_delivery" if identity in final_ids else "process_only"
                if preference_active and identity not in final_ids:
                    delivery_state = "superseded"
                elif attempt < final_attempt and final_ids:
                    delivery_state = "superseded"
                annotations[identity] = {
                    "delivery_state": delivery_state,
                    "delivery_attempt_index": attempt,
                    "delivery_final_attempt_index": final_attempt,
                    "delivery_final_attempt_indexes": final_attempts,
                    "delivery_requested_image_count": requested_count,
                    "delivery_group_output_count": len(group),
                    "retry_superseded": delivery_state == "superseded",
                    "reviewed_best_attempt": preference_active,
                    "retry_reason_codes": retry_codes,
                }
        return annotations

    def _project_review_output_items(
        self,
        project: ProjectRecord,
        *,
        limit: int = 60,
        owner_user_id: int | None = None,
        compact: bool = False,
    ) -> list[dict[str, Any]]:
        """Return generated pixels kept for project review, never delivery.

        The ordinary ``items`` collection is the only formal delivery surface.
        This parallel read model deliberately exposes only safe media pointers
        and review state so users can inspect rejected or superseded images
        without letting them leak into home previews or continuation references.
        """

        all_items = self._project_output_items(
            project,
            limit=max(1, int(limit or 60)),
            include_hidden=True,
            owner_user_id=owner_user_id,
            compact=compact,
        )
        final_items = self._project_output_items(
            project,
            limit=max(1, int(limit or 60)),
            include_hidden=False,
            owner_user_id=owner_user_id,
            compact=compact,
        )
        final_ids = {
            self._public_project_output_identity(item)
            for item in final_items
            if self._public_project_output_identity(item)
        }
        review_items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in all_items:
            identity = self._public_project_output_identity(item)
            if not identity or identity in final_ids or identity in seen:
                continue
            if not self._public_project_output_has_image(item):
                continue
            seen.add(identity)
            reason = self._public_project_review_reason(item)
            metadata = dict(item.get("metadata") or {})
            review_items.append(
                {
                    **item,
                    "review_only": True,
                    "review_reason": reason,
                    "metadata": {
                        **metadata,
                        "review_only": True,
                        "review_reason": reason,
                    },
                }
            )
            if len(review_items) >= max(1, int(limit or 60)):
                break
        return review_items

    def _ecommerce_project_view(self, project: ProjectRecord) -> dict[str, Any]:
        """Build the Doc263 public read model from Project Mode-owned records."""

        if project.primary_template_id != ECOMMERCE_TEMPLATE_ID:
            return {}

        original_inputs: list[dict[str, Any]] = []
        seen_original_asset_ids: set[str] = set()
        selected_directions: list[dict[str, Any]] = []
        seen_direction_ids: set[str] = set()
        for reference in self._active_references(project):
            if (
                reference.source_type == ProjectReferenceSourceType.UPLOADED
                and reference.use_policy == ProjectReferenceUsePolicy.PRODUCT
                and reference.asset_ref_id not in seen_original_asset_ids
            ):
                seen_original_asset_ids.add(reference.asset_ref_id)
                original_inputs.append(
                    {
                        "reference_id": reference.reference_id,
                        "asset_ref_id": reference.asset_ref_id,
                        "label": reference.label,
                        "preview_url": reference.preview_url,
                        "created_at": reference.created_at,
                    }
                )
            if reference.source_type == ProjectReferenceSourceType.GENERATED_SELECTED:
                output_id = str(reference.created_from_output_id or reference.asset_ref_id or "").strip()
                if output_id and output_id not in seen_direction_ids:
                    seen_direction_ids.add(output_id)
                    selected_directions.append(
                        {
                            "reference_id": reference.reference_id,
                            "output_id": output_id,
                            "job_id": reference.created_from_job_id,
                            "preview_url": reference.preview_url,
                            "created_at": reference.created_at,
                        }
                    )

        state_map = self._selected_output_state_map(project)
        for reference in project.selected_output_refs:
            output_id = self._output_identity(reference)
            if (
                output_id
                and output_id not in seen_direction_ids
                and state_map.get(output_id) == ProjectOutputSelectionStateValue.SELECTED
            ):
                seen_direction_ids.add(output_id)
                selected_directions.append(
                    {
                        "reference_id": reference.output_ref_id,
                        "output_id": output_id,
                        "job_id": reference.job_id,
                        "preview_url": reference.preview_url,
                        "created_at": reference.selected_at,
                    }
                )

        locked_person_identity: list[dict[str, Any]] = []
        if self.project_visual_asset_binding_service is not None:
            binding_set = self.project_visual_asset_binding_service.current(project_id=project.project_id)
            # A stale catalog read must not erase the user's append-only
            # project binding from the public projection. It is still blocked
            # for new renderer admission; this branch only supplies the safe
            # generic label for the history/view surface.
            if str(getattr(binding_set, "state", "")) in {"valid", "blocked"}:
                for binding in getattr(binding_set, "bindings", []):
                    if str(getattr(binding, "status", "")) != "active":
                        continue
                    locked_person_identity.append(
                        {
                            "binding_id": str(getattr(binding, "binding_id", "") or ""),
                            "visual_asset_id": str(getattr(binding, "visual_asset_id", "") or ""),
                            "selected_version_id": str(getattr(binding, "selected_version_id", "") or ""),
                            "asset_type": str(getattr(binding, "asset_type", "") or ""),
                            "display_name": self._ecommerce_locked_identity_display_name(binding),
                        }
                    )

        delivered_outputs = [
            self._ecommerce_public_history_output(item)
            for item in self._project_output_items(project, limit=60, compact=True)
        ]
        review_withheld_outputs = [
            self._ecommerce_public_history_output(item)
            for item in self._project_review_output_items(project, limit=60, compact=True)
        ]
        failed_attempts = self._ecommerce_failed_attempts(project)
        return {
            "schema_version": "doc263_ecommerce_project_view_v1",
            "groups": {
                "original_product_inputs": {"items": original_inputs},
                "locked_person_identity": {"items": locked_person_identity},
                "selected_continuation_directions": {"items": selected_directions},
                "generated_and_review_history": {
                    "delivered_outputs": delivered_outputs,
                    "review_withheld_outputs": review_withheld_outputs,
                    "failed_attempts": failed_attempts,
                },
            },
        }

    def _ecommerce_locked_identity_display_name(self, binding: Any) -> str:
        binding_service = self.project_visual_asset_binding_service
        catalog = getattr(binding_service, "catalog", None)
        if catalog is not None:
            asset = catalog.get(
                owner_scope=str(getattr(binding, "owner_scope", "") or ""),
                visual_asset_id=str(getattr(binding, "visual_asset_id", "") or ""),
            )
            display_name = str(getattr(asset, "display_name", "") or "").strip()
            if display_name:
                return display_name
        return "已绑定人物资产"

    @staticmethod
    def _ecommerce_public_history_output(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "output_id": item.get("output_id"),
            "job_id": item.get("job_id"),
            "preview_url": item.get("preview_url"),
            "thumbnail_url": item.get("thumbnail_url"),
            "download_url": item.get("download_url"),
            "created_at": item.get("created_at"),
            "delivery_state": item.get("delivery_state"),
            "certification_state": item.get("certification_state"),
            "review_only": bool(item.get("review_only")),
            "review_reason": item.get("review_reason"),
        }

    def _ecommerce_failed_attempts(self, project: ProjectRecord) -> list[dict[str, Any]]:
        attempts: list[dict[str, Any]] = []
        for job_id in reversed(project.job_ids):
            try:
                status = self.product_service.get_job(job_id)
            except Exception:
                continue
            value = getattr(status, "status", None)
            normalized = str(getattr(value, "value", value) or "").strip().lower()
            if normalized not in {
                ProductJobStatusValue.BLOCKED.value,
                ProductJobStatusValue.FAILED.value,
            }:
                continue
            attempts.append(
                {
                    "job_id": job_id,
                    "state": "failed_no_delivery",
                    "terminal": True,
                    "next_actions": [{"id": "continue"}],
                }
            )
        return attempts

    def _ecommerce_current_operation(self, project: ProjectRecord) -> dict[str, Any] | None:
        """Expose one sanitized operation fact without forwarding Job warnings."""

        if project.primary_template_id != ECOMMERCE_TEMPLATE_ID:
            return None
        phase4_operation = dict(project.metadata or {}).get(_DOC270_PHASE4_CURRENT_OPERATION_KEY)
        if isinstance(phase4_operation, dict):
            operation = phase4_operation.get("operation")
            expected_job_count = phase4_operation.get("project_job_count")
            if (
                isinstance(operation, dict)
                and expected_job_count == len(project.job_ids)
                and json.dumps(operation, sort_keys=True) in {
                    json.dumps(self._doc270_ecommerce_needs_input_operation(), sort_keys=True),
                    json.dumps(self._doc270_ecommerce_source_analysis_unavailable_operation(), sort_keys=True),
                }
            ):
                return dict(operation)
        if isinstance(
            dict(project.metadata or {}).get("doc265_reference_channel_needs_attention"),
            dict,
        ):
            return {
                "state": "continuation_reference_unavailable",
                "terminal": True,
                "pending": False,
                "channel": "selected_continuation_directions",
                "next_actions": [{"id": "review_selected_references"}],
            }
        opaque_hold, _transparent_successor = self._doc279_current_opaque_provider_hold(project)
        if opaque_hold is not None:
            return safe_ambiguous_provider_request_hold_operation(opaque_hold)
        for job_id in reversed(project.job_ids):
            record = self.product_service.get_job_record(job_id)
            if record is None:
                continue
            try:
                status = self.product_service.get_job(job_id)
            except Exception:
                continue
            value = getattr(status, "status", None)
            normalized = str(getattr(value, "value", value) or "").strip().lower()
            if not normalized or normalized == ProductJobStatusValue.NOT_FOUND.value:
                continue
            closure = verified_provider_deliverability_closure_receipt(
                record,
                uploaded_asset_lookup=self.product_service.get_uploaded_asset,
                generated_output_lookup=self.product_service.output_store.get_output,
                source_job_lookup=self.product_service.get_job_record,
                project_goal_snapshot_lookup=self._doc271_project_goal_snapshot,
                command_attempt_association_lookup=self._doc271_command_attempt_association,
            )
            if closure is not None and closure.get("project_id") == project.project_id:
                try:
                    current_admissions = self._doc269_selected_continuation_admissions(project)
                    current_source_binding = self._doc271_current_source_binding(
                        project,
                        selected_continuation_admissions=current_admissions,
                    )
                except (OSError, ValueError, KeyError):
                    current_source_binding = None
                    current_admissions = []
                # Project view has no new command receipt. Its exact current
                # direction is the durable project goal, never a historical
                # Job prompt. A later readable Job returns below before older
                # history is considered.
                if (
                    normalized in {
                        ProductJobStatusValue.BLOCKED.value,
                        ProductJobStatusValue.FAILED.value,
                    }
                    and isinstance(current_source_binding, dict)
                    and self._doc271_current_binding_matches(
                        project,
                        receipt=closure,
                        user_input=str(project.user_goal or "").strip(),
                        selected_continuation_admissions=current_admissions,
                        current_source_binding=current_source_binding,
                    )
                ):
                    return safe_closure_operation(closure)
            opaque_hold = verified_ambiguous_provider_request_hold_receipt(
                record,
                uploaded_asset_lookup=self.product_service.get_uploaded_asset,
                generated_output_lookup=self.product_service.output_store.get_output,
                source_job_lookup=self.product_service.get_job_record,
                project_goal_snapshot_lookup=self._doc271_project_goal_snapshot,
                command_attempt_association_lookup=self._doc271_command_attempt_association,
                output_records_lookup=self.product_service.output_store.list_by_job,
            )
            if opaque_hold is not None and opaque_hold.get("project_id") == project.project_id:
                try:
                    current_admissions = self._doc269_selected_continuation_admissions(project)
                    current_source_binding = self._doc271_current_source_binding(
                        project,
                        selected_continuation_admissions=current_admissions,
                    )
                    current_reference_binding_digest = self._ecommerce_current_reference_binding_digest(
                        project
                    )
                except (OSError, ValueError, KeyError):
                    current_admissions = []
                    current_source_binding = None
                    current_reference_binding_digest = ""
                if (
                    normalized
                    in {
                        ProductJobStatusValue.BLOCKED.value,
                        ProductJobStatusValue.FAILED.value,
                    }
                    and self._doc278_current_binding_matches(
                        project,
                        receipt=opaque_hold,
                        user_input=str(project.user_goal or "").strip(),
                        command_direction=None,
                        requested_output_count=None,
                        selected_continuation_admissions=current_admissions,
                        current_source_binding=current_source_binding,
                        current_reference_binding_digest=current_reference_binding_digest,
                    )
                ):
                    return safe_ambiguous_provider_request_hold_operation(opaque_hold)
            if record is not None and self._doc267_review_withheld_closure_is_valid(
                dict(record.request.metadata or {}),
                job_id=record.job_id,
            ):
                return {
                    "job_id": record.job_id,
                    "state": "review_withheld_finalization_failed",
                    "terminal": True,
                    "pending": False,
                    "next_actions": [{"id": "review_generation_history"}],
                }
            if (
                record is not None
                and dict(record.request.metadata or {}).get("doc264_ecommerce_product_input_needs_attention")
                is True
            ):
                return {
                    "state": "needs_input",
                    "terminal": True,
                    "pending": False,
                    "next_actions": [{"id": "review_product_inputs"}],
                }
            if normalized in {
                ProductJobStatusValue.BLOCKED.value,
                ProductJobStatusValue.FAILED.value,
            }:
                return {
                    "job_id": job_id,
                    "state": "failed_no_delivery",
                    "terminal": True,
                    "pending": False,
                    "next_actions": [{"id": "continue"}],
                }
            if normalized in {
                ProductJobStatusValue.GENERATING.value,
                ProductJobStatusValue.FINALIZING.value,
            }:
                return {
                    "job_id": job_id,
                    "state": "queued_or_generating",
                    "terminal": False,
                    "pending": True,
                    "next_actions": [],
                }
            if normalized == ProductJobStatusValue.PLANNED.value:
                return {
                    "job_id": job_id,
                    "state": "planning",
                    "terminal": False,
                    "pending": True,
                    "next_actions": [],
                }
            # The newest readable settled operation is authoritative. Older
            # blocked/failed attempts remain append-only history only.
            return None
        return None

    def _doc276_face_integrity_current_operation(self, project: ProjectRecord) -> dict[str, Any] | None:
        """Project a shared withheld review state without exposing Job evidence.

        This is intentionally evaluated from the newest readable Job only.
        Old append-only reviews stay in history and cannot overwrite a newer
        planned or delivered command.
        """

        for job_id in reversed(project.job_ids):
            record = self.product_service.get_job_record(job_id)
            if record is None:
                continue
            result = record.generation_result or record.planning_result
            if result is None:
                return None
            package = dict(result.metadata or {}).get("post_generation_review_package")
            inspections = package.get("inspections") if isinstance(package, dict) else []
            required_output_ids = {
                str(output_id).strip()
                for output_id in (
                    package.get("doc276_face_integrity_required_output_ids", [])
                    if isinstance(package, dict)
                    else []
                )
                if str(output_id).strip()
            }
            if not required_output_ids:
                return None
            inspections_by_output = {
                str(inspection.get("output_id") or "").strip(): inspection
                for inspection in (inspections if isinstance(inspections, list) else [])
                if isinstance(inspection, dict) and str(inspection.get("output_id") or "").strip()
            }
            face_integrity_withheld = any(
                not self.product_service._doc276_face_integrity_delivery_certified(  # noqa: SLF001
                    inspections_by_output.get(output_id, {}),
                    required=True,
                )
                for output_id in required_output_ids
            )
            if not face_integrity_withheld:
                return None
            final_delivery, _output_ids, _asset_ids = self.product_service._public_final_delivery_projection(result)
            if final_delivery.get("final_delivery_status") != "withheld_manual_confirmation":
                return None
            return {
                "state": "review_withheld_face_integrity",
                "terminal": True,
                "pending": False,
                "next_actions": [{"id": "review_generation_history"}],
            }
        return None

    def _doc280_ecommerce_review_current_operation(self, project: ProjectRecord) -> dict[str, Any] | None:
        """Expose one E34 retained-review operation for the newest Job only."""

        if project.primary_template_id != ECOMMERCE_TEMPLATE_ID:
            return None
        for job_id in reversed(project.job_ids):
            record = self.product_service.get_job_record(job_id)
            if record is None:
                continue
            try:
                status = self.product_service.get_job(job_id)
            except Exception:
                return None
            disposition = dict(getattr(status, "metadata", {}) or {}).get("review_disposition")
            if not isinstance(disposition, dict):
                return None
            if (
                disposition.get("schema_version") != "doc280_ecommerce_review_disposition_v1"
                or disposition.get("terminal") is not True
                or disposition.get("pending") is not False
            ):
                return None
            state = str(disposition.get("state") or "").strip()
            if state not in {
                "review_withheld_manual_confirmation",
                "review_withheld_review_failure",
            }:
                return None
            if disposition.get("next_actions") != [{"id": "review_generation_history"}]:
                return None
            return {
                "state": state,
                "terminal": True,
                "pending": False,
                "next_actions": [{"id": "review_generation_history"}],
            }
        return None

    @staticmethod
    def _public_project_output_identity(item: dict[str, Any]) -> str:
        return str(
            item.get("output_id")
            or item.get("asset_id")
            or item.get("candidate_id")
            or item.get("output_ref_id")
            or ""
        ).strip()

    @staticmethod
    def _public_project_output_has_image(item: dict[str, Any]) -> bool:
        for key in ("thumbnail_url", "preview_url", "download_url"):
            value = str(item.get(key) or "").strip()
            if value and not value.startswith("mock://"):
                return True
        return False

    @staticmethod
    def _public_project_review_reason(item: dict[str, Any]) -> str:
        metadata = dict(item.get("metadata") or {})
        codes = [
            str(code).strip().lower()
            for code in metadata.get("retry_reason_codes", [])
            if str(code).strip()
        ]
        if any("exhausted_refine_budget" in code for code in codes):
            return "自动精修次数已用完，保留这张图供复核。"
        if any("reject" in code or "review" in code for code in codes):
            return "自动审查未建议正式交付，保留这张图供复核。"
        if str(item.get("delivery_state") or "").lower() in {"superseded", "process_only"}:
            return "这张图属于过程记录，未进入正式交付。"
        if str(item.get("selection_state") or "").lower() in {"unselected", "rejected"}:
            return "这张图已从正式项目结果中移出。"
        if str(item.get("certification_state") or "").lower() in {
            "blocked",
            "manual_confirmation_required",
        }:
            return "这张图尚未通过正式交付审查。"
        return "这张图未进入正式交付，保留供复核。"

    def _delivery_requested_image_count(self, records: list[Any]) -> int:
        values: list[int] = []
        for record in records:
            metadata = dict(getattr(record, "metadata", None) or {})
            raw = metadata.get("requested_image_count")
            try:
                parsed = int(raw)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                values.append(parsed)
        return max(1, min(8, max(values) if values else len(records) or 1))

    def _output_record_retry_attempt(self, record: Any) -> int:
        metadata = dict(getattr(record, "metadata", None) or {})
        raw = metadata.get("visual_auto_retry_attempt", metadata.get("retry_attempt", 0))
        try:
            return max(0, int(raw or 0))
        except (TypeError, ValueError):
            return 0

    def _output_record_is_review_rejected(self, record: Any) -> bool:
        """Recognize explicit review/retry rejection without guessing from pixels."""

        metadata = dict(getattr(record, "metadata", None) or {})
        sources = [metadata]
        for key in ("candidate_metadata", "asset_metadata", "review"):
            nested = metadata.get(key)
            if isinstance(nested, dict):
                sources.append(nested)
        rejected_values = {
            "blocked",
            "fail",
            "failed",
            "failed_after_retry",
            "manual_review",
            "reject",
            "rejected",
            "retry",
            "retry_recommended",
        }
        for source in sources:
            for key in ("recommendation", "review_recommendation", "retry_recommendation", "review_status"):
                value = str(source.get(key) or "").strip().lower()
                if value in rejected_values:
                    return True
            if any(
                bool(source.get(key))
                for key in ("candidate_rejected", "review_rejected", "reject_recommendation", "refine_budget_exhausted")
            ):
                return True
            for key in ("visual_retry_reason_codes", "retry_reason_codes", "issue_codes"):
                values = source.get(key)
                if not isinstance(values, list):
                    continue
                for value in values:
                    normalized = str(value or "").strip().lower()
                    if (
                        "exhausted_refine_budget" in normalized
                        or "reject_recommendation" in normalized
                        or normalized in {"review_rejected", "output_rejected", "failed_after_retry"}
                    ):
                        return True
        return False

    def _output_record_has_usable_image(self, record: Any) -> bool:
        return any(
            str(getattr(record, field, "") or "").strip()
            and not str(getattr(record, field, "") or "").startswith("mock://")
            for field in ("download_url", "preview_url", "thumbnail_url")
        )

    def _delivery_retry_reason_codes(self, records: list[Any]) -> list[str]:
        codes: list[str] = []
        for record in records:
            metadata = dict(getattr(record, "metadata", None) or {})
            for key in ("visual_retry_reason_codes", "retry_reason_codes", "issue_codes"):
                value = metadata.get(key)
                if isinstance(value, list):
                    codes.extend(str(item).strip() for item in value if str(item).strip())
        return list(dict.fromkeys(codes))

    def _project_output_items(
        self,
        project: ProjectRecord,
        *,
        limit: int = 60,
        include_hidden: bool = False,
        owner_user_id: int | None = None,
        compact: bool = False,
    ) -> list[dict[str, Any]]:
        output_store = getattr(self.product_service, "output_store", None)
        if output_store is None:
            return []
        state_map = self._selected_output_state_map(project)
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for job_id in reversed(project.job_ids):
            try:
                job_status = self.product_service.get_job(job_id)
            except Exception:
                continue
            job_record = self.product_service.get_job_record(job_id)
            has_doc267_review_closure = (
                job_record is not None
                and self._doc267_review_withheld_closure_is_valid(
                    dict(job_record.request.metadata or {}),
                    job_id=job_id,
                )
            )
            if not self._job_delivery_is_settled(job_status):
                # A terminal job may have generated pixels while a shared
                # final-delivery gate is withholding them. Those pixels are
                # review-only evidence, but must never appear on the normal
                # delivery surface. In-flight jobs remain hidden everywhere.
                if has_doc267_review_closure:
                    if not include_hidden:
                        continue
                elif not include_hidden or not self._job_has_terminal_review_state(job_status):
                    continue
            try:
                records = output_store.list_by_job(job_id)
            except Exception:
                continue
            delivery = self._delivery_annotations_for_records(records)
            for record in sorted(records, key=lambda item: item.created_at or "", reverse=True):
                if not self._output_record_visible_to_owner(record, owner_user_id):
                    continue
                identity = self._output_record_identity(record)
                if not identity or identity in seen:
                    continue
                seen.add(identity)
                state = self._output_state_for_record(state_map, record)
                delivery_entry = delivery.get(identity, {})
                review_projection = self._public_output_review_projection(job_status, record)
                if not include_hidden and str(delivery_entry.get("delivery_state") or "final_delivery") != "final_delivery":
                    continue
                # Modern shared review applies a canonical final-delivery gate
                # on the Job. A materialized PNG is not an ordinary Project
                # delivery when that gate withholds it for review. Legacy
                # output-only jobs remain readable.
                if not include_hidden and not self._review_projection_allows_project_delivery(review_projection):
                    continue
                if (
                    not include_hidden
                    and state
                    in {
                        ProjectOutputSelectionStateValue.UNSELECTED,
                        ProjectOutputSelectionStateValue.REJECTED,
                    }
                ):
                    continue
                items.append(
                    self._output_item_from_record(
                        project,
                        record,
                        state,
                        compact=compact,
                        delivery=delivery_entry,
                        review_projection=review_projection,
                    )
                )
                if len(items) >= max(1, int(limit or 60)):
                    return items
        return items[: max(1, int(limit or 60))]

    def _project_job_delivery_is_settled(self, job_id: str) -> bool:
        """Known in-flight jobs must not leak process outputs onto project boards."""

        job_status = self.product_service.get_job(job_id)
        return self._job_delivery_is_settled(job_status)

    @staticmethod
    def _job_delivery_is_settled(job_status: ProductJobStatus) -> bool:
        """Keep one terminal-state rule for normal and recovered Project outputs."""

        if job_status.status in {ProductJobStatusValue.GENERATING, ProductJobStatusValue.FINALIZING}:
            return False
        execution = dict(job_status.metadata or {}).get("specialized_execution_summary")
        # A multi-role template can preserve generated pixels in append-only
        # history while still withholding them from the ordinary project
        # result panel until every frozen role has a final winner.
        return not (isinstance(execution, dict) and bool(execution.get("final_delivery_withheld")))

    @staticmethod
    def _doc267_review_withheld_closure_is_valid(
        metadata: dict[str, Any],
        *,
        job_id: str,
    ) -> bool:
        """Recognize only the closed Product API receipt, never a browser flag."""

        closure = metadata.get("post_generation_review_closure")
        if not isinstance(closure, dict):
            return False
        output_ids = closure.get("output_ids")
        pixel_bindings = closure.get("pixel_bindings")
        if (
            closure.get("schema_version") != "doc267_post_generation_review_closure_v1"
            or closure.get("authority") != "v3_product_api"
            or closure.get("state") != "review_withheld_finalization_failed"
            or str(closure.get("job_id") or "").strip() != job_id
            or closure.get("history_only") is not True
            or closure.get("real_pixel_review") is not False
            or closure.get("automatic_delivery_available") is not False
            or closure.get("manual_confirmation_required") is not True
            or closure.get("automatic_replay") is not False
            or not isinstance(output_ids, list)
            or not output_ids
            or any(not isinstance(value, str) or not value.strip() for value in output_ids)
            or len(output_ids) != len(set(output_ids))
            or not isinstance(pixel_bindings, list)
            or len(pixel_bindings) != len(output_ids)
        ):
            return False
        binding_output_ids: list[str] = []
        for binding in pixel_bindings:
            if not isinstance(binding, dict):
                return False
            output_id = str(binding.get("output_id") or "").strip()
            if (
                not output_id
                or not str(binding.get("asset_id") or "").strip()
                or not str(binding.get("candidate_id") or "").strip()
                or len(str(binding.get("content_sha256") or "").strip()) != 64
            ):
                return False
            binding_output_ids.append(output_id)
        return binding_output_ids == output_ids and len(binding_output_ids) == len(set(binding_output_ids))

    @staticmethod
    def _job_has_terminal_review_state(job_status: ProductJobStatus) -> bool:
        """Allow ended withheld jobs into the review-only projection only."""

        if V3ProjectModeService._doc267_review_withheld_closure_is_valid(
            dict(job_status.metadata or {}),
            job_id=job_status.job_id,
        ):
            return True
        return job_status.status not in {
            ProductJobStatusValue.GENERATING,
            ProductJobStatusValue.FINALIZING,
        }

    @staticmethod
    def _public_output_review_projection(job_status: ProductJobStatus, record: Any) -> dict[str, Any]:
        """Project safe, per-output projection of the canonical shared review.

        Output records deliberately keep renderer provenance and media pointers,
        while the Product Job owns review and final-delivery truth.  Project
        recovery therefore reads the already-public Job projection and matches
        it to the materialized output.  This is not a second reviewer and never
        exposes provider errors, prompts, paths, or internal evidence.
        """

        metadata = dict(job_status.metadata or {})
        review = metadata.get("post_generation_review")
        review = dict(review) if isinstance(review, dict) else {}
        output_id = str(getattr(record, "output_id", "") or "").strip()
        inspection: dict[str, Any] = {}
        for item in review.get("inspections", []):
            if not isinstance(item, dict):
                continue
            if output_id and str(item.get("output_id") or "").strip() == output_id:
                inspection = dict(item)
                break

        review_mode = str(inspection.get("mode") or "").strip().lower() or None
        review_status = str(inspection.get("status") or "").strip().lower() or None
        verification_state = str(inspection.get("verification_state") or "").strip().lower() or None
        final_delivery = metadata.get("final_delivery")
        final_delivery = dict(final_delivery) if isinstance(final_delivery, dict) else {}
        public_delivery_state = str(final_delivery.get("final_delivery_status") or "not_evaluated").strip().lower()
        certified = (
            review_mode in {"vision_model", "hybrid"}
            and verification_state == "verified"
            and review_status in {"pass", "warning"}
            and public_delivery_state == "ready"
        )
        if certified:
            certification_state = "certified"
        elif review_status == "manual_review" or public_delivery_state == "withheld_manual_confirmation":
            certification_state = "manual_confirmation_required"
        elif review_mode or public_delivery_state not in {"", "not_evaluated"}:
            certification_state = "blocked"
        else:
            certification_state = "not_evaluated"
        return {
            "review_mode": review_mode,
            "review_status": review_status,
            "verification_state": verification_state,
            "certification_state": certification_state,
            "public_delivery_state": public_delivery_state,
            # Internal control used only while aggregating the ordinary
            # Project board. `_output_item_from_record` strips it so the
            # public result remains limited to the safe review projection.
            # A baseline ``not_evaluated`` placeholder is not an applied gate.
            "_final_delivery_recorded": bool(final_delivery.get("delivery_gate_applies")),
        }

    @staticmethod
    def _review_projection_allows_project_delivery(review_projection: dict[str, Any]) -> bool:
        """Keep withheld modern outputs out of ordinary Project delivery.

        Older jobs can have append-only output records without an applied
        final-delivery gate, so they stay readable for compatibility. Once a
        canonical gate applies, only its explicit ``ready`` state may appear
        on the normal Project result surface.
        """

        if not bool(review_projection.get("_final_delivery_recorded")):
            return True
        return str(review_projection.get("public_delivery_state") or "").strip().lower() == "ready"

    def _output_ref_from_record(self, project: ProjectRecord, record: Any) -> OutputRef:
        return OutputRef(
            output_ref_id=stable_id("output_ref", project.project_id, record.job_id, record.output_id),
            source_type="generated_output",
            project_id=project.project_id,
            job_id=record.job_id,
            asset_id=record.asset_id,
            candidate_id=record.candidate_id,
            output_id=record.output_id,
            preview_url=record.preview_url,
            thumbnail_url=record.thumbnail_url,
            download_url=record.download_url,
            selection_reason="project generated image",
            selected_at=record.created_at,
            metadata={
                "restored_from_output_store": True,
                "canonical_output_binding": True,
                "file_path": record.file_path,
                "source_integrity_id": self._output_source_integrity_id(record),
                "provider": record.provider,
                "model": record.model,
            },
        )

    def _output_item_from_record(
        self,
        project: ProjectRecord,
        record: Any,
        state: ProjectOutputSelectionStateValue | None,
        *,
        compact: bool = False,
        delivery: dict[str, Any] | None = None,
        review_projection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record_metadata = dict(record.metadata or {})
        state_value = (state.value if hasattr(state, "value") else str(state)) if state else "available"
        delivery_metadata = dict(delivery or {})
        public_review = {
            key: value
            for key, value in dict(review_projection or {}).items()
            if not str(key).startswith("_")
        }
        delivery_state = str(delivery_metadata.get("delivery_state") or "final_delivery")
        item = {
            "output_ref_id": stable_id("project_output", project.project_id, record.job_id, record.output_id),
            "source_type": "generated_output",
            "project_id": project.project_id,
            "project_title": project.title,
            "project_goal": project.short_summary or project.user_goal,
            "template_id": project.primary_template_id,
            "job_id": record.job_id,
            "asset_id": record.asset_id,
            "candidate_id": record.candidate_id,
            "output_id": record.output_id,
            "download_url": record.download_url,
            "preview_url": record.preview_url,
            "thumbnail_url": record.thumbnail_url,
            "created_at": record.created_at,
            "selection_state": state_value,
            "selected": state == ProjectOutputSelectionStateValue.SELECTED,
            "delivery_state": delivery_state,
            **public_review,
            "metadata": {
                "width": record.width,
                "height": record.height,
                "format": record.output_format,
                "provider": record.provider,
                "model": record.model,
                "requested_image_count": record_metadata.get("requested_image_count"),
                "requested_image_size": record_metadata.get("requested_image_size"),
                "final_provider_prompt": record_metadata.get("final_provider_prompt"),
                "compiled_visual_direction": record_metadata.get("compiled_visual_direction"),
                "style_notes": record_metadata.get("style_notes") or [],
                "layout_notes": record_metadata.get("layout_notes") or [],
                **delivery_metadata,
                **public_review,
            },
        }
        if compact:
            item["metadata"] = {
                "width": record.width,
                "height": record.height,
                "format": record.output_format,
                "provider": record.provider,
                "model": record.model,
                "requested_image_count": record_metadata.get("requested_image_count"),
                "requested_image_size": record_metadata.get("requested_image_size"),
                "compact": True,
                **delivery_metadata,
                **public_review,
            }
        return item

    def _output_record_identity(self, record: Any) -> str:
        return str(getattr(record, "output_id", None) or getattr(record, "asset_id", None) or getattr(record, "candidate_id", None) or "")

    def _output_state_for_record(
        self,
        state_map: dict[str, ProjectOutputSelectionStateValue],
        record: Any,
    ) -> ProjectOutputSelectionStateValue | None:
        for key in (record.output_id, record.asset_id, record.candidate_id):
            if key and key in state_map:
                return state_map[key]
        return None

    def _project_visible_to_owner(self, project: ProjectRecord, owner_user_id: int | None) -> bool:
        if owner_user_id is None:
            return True
        project_owner_id = self._positive_owner_id(project.metadata.get("veyra_user_id"))
        return project_owner_id is None or project_owner_id == owner_user_id

    def _output_record_visible_to_owner(self, record: Any, owner_user_id: int | None) -> bool:
        if owner_user_id is None:
            return True
        metadata = dict(getattr(record, "metadata", None) or {})
        record_owner_id = self._positive_owner_id(metadata.get("veyra_user_id"))
        return record_owner_id is None or record_owner_id == owner_user_id

    def _positive_owner_id(self, value: Any) -> int | None:
        try:
            parsed = int(value or 0)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _style_chips(self, project: ProjectRecord) -> list[str]:
        chips: list[str] = []
        text = f"{project.user_goal} {project.confirmed_style_summary or ''}".lower()
        for keyword, label in [
            ("清爽", "清爽"),
            ("高级", "高级"),
            ("留白", "留白"),
            ("小红书", "小红书"),
            ("海报", "海报"),
            ("品牌", "品牌视觉"),
            ("product", "产品感"),
            ("产品", "产品感"),
        ]:
            if keyword in text and label not in chips:
                chips.append(label)
        if project.selected_output_refs and "已选风格" not in chips:
            chips.append("已选风格")
        # A project with no user-confirmed visual style still needs an honest
        # template-level label.  In particular, an E-Commerce project must not
        # inherit the General Template fallback in the project workspace or
        # recent-project cards.
        return chips[:5] or [self._template_label(project.primary_template_id)]

    def _template_label(self, template_id: str | None) -> str:
        if template_id == ECOMMERCE_TEMPLATE_ID:
            return "电商模板"
        if template_id == PHOTOGRAPHER_TEMPLATE_ID:
            return "摄影师模板"
        return "通用模板"

    def _scenario_id_for_template(self, template_id: str | None) -> str:
        manifest = self.template_registry.get_manifest(template_id)
        return manifest.scenario_pack_id if manifest is not None else GENERAL_SCENARIO_ID

    def _next_actions(self, project: ProjectRecord) -> list[str]:
        has_active_selected_outputs = bool(self._build_context(project).selected_output_assets) if project.project_id else False
        if project.primary_template_id == ECOMMERCE_TEMPLATE_ID:
            if has_active_selected_outputs:
                return ["继续补一张同风格电商图", "检查商品细节是否准确", "导出已选套图"]
            if project.job_ids:
                return ["选中可用的套图", "标记不想要的方向", "补充商品卖点"]
            return ["上传商品图", "生成第一组电商套图", "补充商品卖点"]
        if has_active_selected_outputs:
            return ["继续同风格生成", "上传新参考图继续", "下载已选图片"]
        if project.job_ids:
            return ["选中喜欢的图片", "继续生成新图", "补充参考图"]
        return ["生成第一组创意图", "上传参考图", "补充项目感觉"]

    def _output_refs_from_selection(
        self,
        project: ProjectRecord,
        selected: SelectionResponse,
    ) -> tuple[list[OutputRef], list[dict[str, Any]]]:
        return self._resolved_output_refs_for_status(
            project,
            selected.job_status,
            selected_candidate_ids=set(selected.selected_result.selected_candidate_ids),
            selected_asset_ids=set(selected.selected_result.selected_asset_ids),
        )

    def _resolved_output_refs_for_status(
        self,
        project: ProjectRecord,
        status: ProductJobStatus,
        *,
        selected_candidate_id: str | None = None,
        selected_asset_id: str | None = None,
        selected_candidate_ids: set[str] | None = None,
        selected_asset_ids: set[str] | None = None,
    ) -> tuple[list[OutputRef], list[dict[str, Any]]]:
        """Resolve a selection to exact V3 output records before it is persisted.

        Candidate and asset identifiers are planning identifiers, not provider
        inputs.  The project layer is deliberately strict here: a continuation
        may use an exact materialized output, or it is held.  It must never
        fall back to another candidate from the same job.
        """

        selected_candidate_ids = set(selected_candidate_ids or [])
        selected_asset_ids = set(selected_asset_ids or [])
        if selected_candidate_id:
            selected_candidate_ids.add(selected_candidate_id)
        if selected_asset_id:
            selected_asset_ids.add(selected_asset_id)
        refs: list[OutputRef] = []
        now = _utc_now_iso()
        for candidate in status.candidates:
            if selected_candidate_ids and candidate.candidate_id not in selected_candidate_ids:
                continue
            if selected_asset_ids and candidate.asset_id not in selected_asset_ids:
                continue
            refs.append(
                OutputRef(
                    output_ref_id=stable_id("output_ref", project.project_id, status.job_id, candidate.candidate_id),
                    source_type="selected_candidate",
                    project_id=project.project_id,
                    job_id=status.job_id,
                    asset_id=candidate.asset_id,
                    candidate_id=candidate.candidate_id,
                    output_id=candidate.output_id,
                    preview_url=candidate.preview_url or candidate.preview_uri,
                    thumbnail_url=candidate.thumbnail_url,
                    download_url=candidate.download_url,
                    selection_reason="user selected for project continuation",
                    selected_at=now,
                    metadata={"recommendation": candidate.recommendation},
                )
            )
        if not refs:
            for asset in status.asset_series:
                if selected_asset_ids and asset.asset_id not in selected_asset_ids:
                    continue
                refs.append(
                    OutputRef(
                        output_ref_id=stable_id("output_ref", project.project_id, status.job_id, asset.asset_id),
                        source_type="selected_asset",
                        project_id=project.project_id,
                        job_id=status.job_id,
                        asset_id=asset.asset_id,
                        output_id=asset.output_id,
                        preview_url=asset.preview_url or asset.preview_uri,
                        thumbnail_url=asset.thumbnail_url,
                        download_url=asset.download_url,
                        selection_reason="user selected for project continuation",
                        selected_at=now,
                    )
                )
        resolved: list[OutputRef] = []
        unresolved: list[dict[str, Any]] = []
        for ref in refs:
            canonical = self._canonical_selected_output_ref(project, ref)
            if canonical is None:
                unresolved.append(
                    {
                        "job_id": ref.job_id,
                        "candidate_id": ref.candidate_id,
                        "asset_id": ref.asset_id,
                        "output_id": ref.output_id,
                        "reason": "materialized_output_unavailable",
                    }
                )
                continue
            resolved.append(canonical)
        return resolved, unresolved

    def _canonical_selected_output_ref(self, project: ProjectRecord, ref: OutputRef) -> OutputRef | None:
        """Hydrate one selected output from its immutable local output record."""

        output_store = getattr(self.product_service, "output_store", None)
        if output_store is None or not ref.job_id:
            return None
        records: list[Any] = []
        if ref.output_id:
            record = output_store.get_output(ref.output_id)
            if record is not None:
                records = [record]
        if not records:
            try:
                records = list(output_store.list_by_job(ref.job_id))
            except Exception:
                return None
            if ref.candidate_id:
                records = [item for item in records if item.candidate_id == ref.candidate_id]
            elif ref.asset_id:
                records = [item for item in records if item.asset_id == ref.asset_id]
            else:
                return None
        records = [
            item
            for item in records
            if item.job_id == ref.job_id
            and (not ref.candidate_id or item.candidate_id == ref.candidate_id)
            and (not ref.asset_id or item.asset_id == ref.asset_id)
        ]
        if len(records) != 1:
            return None
        record = records[0]
        if not self._output_record_is_renderable(record):
            return None
        source_integrity_id = self._output_source_integrity_id(record)
        return OutputRef(
            output_ref_id=stable_id("output_ref", project.project_id, record.job_id, record.output_id),
            source_type="generated_output",
            project_id=project.project_id,
            job_id=record.job_id,
            asset_id=record.asset_id,
            candidate_id=record.candidate_id,
            output_id=record.output_id,
            preview_url=record.preview_url,
            thumbnail_url=record.thumbnail_url,
            download_url=record.download_url,
            selection_reason=ref.selection_reason,
            selected_at=ref.selected_at,
            metadata={
                **dict(ref.metadata),
                "canonical_output_binding": True,
                "file_path": record.file_path,
                "mime_type": record.mime_type,
                "provider": record.provider,
                "model": record.model,
                "source_integrity_id": source_integrity_id,
                "v3_owned_output": True,
            },
        )

    def _output_record_is_renderable(self, record: Any) -> bool:
        file_path = str(getattr(record, "file_path", "") or "").strip()
        return bool(
            file_path
            and Path(file_path).is_file()
            and str(getattr(record, "preview_url", "") or "").strip()
            and str(getattr(record, "thumbnail_url", "") or "").strip()
            and str(getattr(record, "download_url", "") or "").strip()
        )

    def _output_source_integrity_id(self, record: Any) -> str:
        strict_integrity_id = self._doc265_output_source_integrity_id(record)
        return strict_integrity_id or f"output:{record.output_id}"

    def _doc265_output_source_integrity_id(self, record: Any) -> str:
        file_path = Path(str(getattr(record, "file_path", "") or ""))
        digest = self._file_content_fingerprint(file_path)
        return f"sha256:{digest}" if digest else ""

    def _file_content_fingerprint(self, file_path: Path) -> str:
        try:
            digest = hashlib.sha256()
            with file_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except OSError:
            return ""

    def _project_asset_ids(self, project: ProjectRecord) -> list[str]:
        inactive_ids = {
            reference.asset_ref_id
            for reference in project.reference_assets
            if reference.status == ProjectReferenceStatus.INACTIVE
        }
        active_reference_ids = [
            reference.asset_ref_id
            for reference in project.reference_assets
            if reference.status == ProjectReferenceStatus.ACTIVE
            and reference.source_type == ProjectReferenceSourceType.UPLOADED
        ]
        legacy_ids = [
            str(item["asset_id"])
            for item in project.uploaded_asset_refs
            if item.get("asset_id") and str(item["asset_id"]) not in inactive_ids
            and str(item.get("status") or "").strip().lower() != ProjectReferenceStatus.INACTIVE.value
        ]
        return list(dict.fromkeys([*active_reference_ids, *legacy_ids]))

    def _project_generated_output_ids(self, project: ProjectRecord) -> list[str]:
        output_ids = self._project_output_reference_ids(project)
        output_store = getattr(self.product_service, "output_store", None)
        if output_store is not None:
            for job_id in list(dict.fromkeys(project.job_ids)):
                try:
                    records = output_store.list_by_job(job_id)
                except Exception:
                    continue
                output_ids.extend(str(getattr(record, "output_id", "") or "") for record in records)
        return list(dict.fromkeys(output_id for output_id in output_ids if output_id))

    def _project_output_reference_ids(self, project: ProjectRecord) -> list[str]:
        output_ids: list[str] = []
        for ref in project.selected_output_refs:
            if ref.output_id:
                output_ids.append(ref.output_id)
        for state in project.selected_output_states:
            if state.output_id:
                output_ids.append(state.output_id)
        for reference in project.reference_assets:
            if reference.source_type == ProjectReferenceSourceType.GENERATED_SELECTED:
                if reference.created_from_output_id:
                    output_ids.append(reference.created_from_output_id)
                if str(reference.asset_ref_id or "").startswith("v3_output_"):
                    output_ids.append(reference.asset_ref_id)
        for timeline_item in self.project_store.list_timeline(project.project_id):
            output_ids.extend(str(item or "") for item in timeline_item.related_output_ids)
            for ref in timeline_item.selected_output_refs:
                if ref.output_id:
                    output_ids.append(ref.output_id)
        context = project.latest_context
        if context is not None:
            for ref in context.selected_output_assets:
                if ref.output_id:
                    output_ids.append(ref.output_id)
            for item in context.selected_reference_assets:
                output_id = str(item.get("output_id") or item.get("created_from_output_id") or "").strip()
                if output_id:
                    output_ids.append(output_id)
        return list(dict.fromkeys(output_id for output_id in output_ids if output_id))

    def _project_uploaded_reference_ids(self, project: ProjectRecord) -> list[str]:
        asset_ids = self._project_asset_ids(project)
        for reference in project.reference_assets:
            if reference.source_type == ProjectReferenceSourceType.UPLOADED:
                asset_ids.append(reference.asset_ref_id)
        context = project.latest_context
        if context is not None:
            for item in context.uploaded_reference_assets:
                asset_id = str(item.get("asset_id") or item.get("asset_ref_id") or "").strip()
                if asset_id:
                    asset_ids.append(asset_id)
        return list(dict.fromkeys(asset_id for asset_id in asset_ids if asset_id))

    def _shared_project_output_ids(self, project: ProjectRecord, candidate_output_ids: list[str]) -> set[str]:
        candidates = {str(item or "").strip() for item in candidate_output_ids if str(item or "").strip()}
        if not candidates:
            return set()
        shared: set[str] = set()
        for other in self.project_store.list_projects(limit=100):
            if other.project_id == project.project_id:
                continue
            for output_id in self._project_output_reference_ids(other):
                if output_id in candidates:
                    shared.add(output_id)
        return shared

    def _shared_project_upload_ids(self, project: ProjectRecord, candidate_asset_ids: list[str]) -> set[str]:
        candidates = {str(item or "").strip() for item in candidate_asset_ids if str(item or "").strip()}
        if not candidates:
            return set()
        shared: set[str] = set()
        for other in self.project_store.list_projects(limit=100):
            if other.project_id == project.project_id:
                continue
            for asset_id in self._project_uploaded_reference_ids(other):
                if asset_id in candidates:
                    shared.add(asset_id)
        return shared

    def _doc277_current_planning_operation(self, project: ProjectRecord) -> dict[str, Any] | None:
        """Read only a server-issued pending or terminal planning projection."""

        pointer = dict(project.metadata or {}).get(_DOC277_CURRENT_OPERATION_KEY)
        if not isinstance(pointer, dict):
            return None
        operation_id = str(pointer.get("operation_id") or "").strip()
        state = str(pointer.get("state") or "").strip()
        if not operation_id or state not in _DOC277_OPERATION_STATES:
            return None
        try:
            records = self.project_store.list_private_records(
                project.project_id,
                _DOC277_PRIVATE_PLANNING_NAMESPACE,
            )
        except ValueError:
            return None
        opened = any(
            record.get("record_kind") == "opened"
            and record.get("project_id") == project.project_id
            and record.get("operation_id") == operation_id
            for record in records
        )
        if not opened:
            return None
        terminal_kinds = {
            str(record.get("record_kind") or "")
            for record in records
            if record.get("project_id") == project.project_id
            and record.get("operation_id") == operation_id
        }
        if state == "planning":
            if terminal_kinds.intersection({"completed", "failed"}):
                return None
            return {
                "operation_id": operation_id,
                "state": "planning",
                "terminal": False,
                "pending": True,
                "next_actions": [],
            }
        if "failed" not in terminal_kinds:
            return None
        return {
            "operation_id": operation_id,
            "state": "planning_failed",
            "terminal": True,
            "pending": False,
            "next_actions": [{"id": "review_project_request"}],
        }

    @staticmethod
    def _doc277_digest(value: dict[str, Any]) -> str:
        serialized = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _doc279_no_job_e32_projection_matches(
        self,
        project: ProjectRecord,
        operation: dict[str, Any] | None,
        opaque_hold: dict[str, Any] | None,
        *,
        transparent_successor: bool,
    ) -> bool:
        """Read a server-issued no-Job E32 projection without changing history."""

        if (
            transparent_successor
            or not isinstance(operation, dict)
            or operation.get("state") != "planning_failed"
            or opaque_hold is None
        ):
            return False
        operation_id = str(operation.get("operation_id") or "").strip()
        hold_receipt_id = str(opaque_hold.get("hold_receipt_id") or "").strip()
        if not operation_id or not hold_receipt_id:
            return False
        try:
            records = self.project_store.list_private_records(
                project.project_id,
                _DOC277_PRIVATE_PLANNING_NAMESPACE,
            )
        except ValueError:
            return False
        for record in reversed(records):
            if (
                record.get("record_kind") != "failed"
                or record.get("project_id") != project.project_id
                or record.get("operation_id") != operation_id
            ):
                continue
            projection = record.get("doc279_e32_no_job_operation_projection")
            if not isinstance(projection, dict):
                return False
            expected_keys = {
                "schema_version",
                "authority",
                "project_id",
                "operation_id",
                "state",
                "opaque_hold_receipt_id",
                "projection_digest",
            }
            if set(projection) != expected_keys:
                return False
            unsigned = {
                key: value
                for key, value in projection.items()
                if key != "projection_digest"
            }
            if (
                str(projection.get("projection_digest") or "").strip()
                != self._doc277_digest(unsigned)
            ):
                return False
            return (
                projection.get("schema_version")
                == "doc279_e32_no_job_operation_projection_v1"
                and projection.get("authority") == "v3_project_mode"
                and projection.get("project_id") == project.project_id
                and projection.get("operation_id") == operation_id
                and projection.get("state") == "ambiguous_provider_request_hold"
                and projection.get("opaque_hold_receipt_id") == hold_receipt_id
            )
        return False

    def _project_response(self, project: ProjectRecord) -> ProjectResponse:
        public_project = self._public_project_record(project)
        disclosures = self._doc281_used_source_disclosures(project)
        if disclosures:
            public_project.metadata["doc281_used_source_disclosures"] = disclosures
        metadata = {
            **self._metadata(),
            "project_outputs": self._project_output_items(project, limit=60),
        }
        metadata["project_source_library"] = public_project_source_library(
            self._doc270_project_source_library(project)
        )
        # A current association-drift closure is bound to the active source
        # snapshot and must take precedence over stale planned-job progress.
        # It is rehydrated privately rather than trusted from project metadata.
        operation = self._doc281_current_terminal_operation(project)
        if operation is None:
            operation = self._doc277_current_planning_operation(project)
        ecommerce_operation: dict[str, Any] | None = None
        ecommerce_transparent_successor = False
        ecommerce_no_job_e32_projection = False
        if project.primary_template_id == ECOMMERCE_TEMPLATE_ID:
            opaque_hold, ecommerce_transparent_successor = self._doc279_current_opaque_provider_hold(
                project
            )
            if opaque_hold is not None:
                ecommerce_operation = safe_ambiguous_provider_request_hold_operation(opaque_hold)
                ecommerce_no_job_e32_projection = self._doc279_no_job_e32_projection_matches(
                    project,
                    operation,
                    opaque_hold,
                    transparent_successor=ecommerce_transparent_successor,
                )
        if operation is None:
            operation = self._doc276_face_integrity_current_operation(project)
        if (
            operation is not None
            and operation.get("state") == "planning_failed"
            and ecommerce_operation is not None
            and (
                ecommerce_transparent_successor
                or ecommerce_no_job_e32_projection
            )
        ):
            operation = ecommerce_operation
        if operation is not None:
            metadata["current_operation"] = operation
        if project.primary_template_id == ECOMMERCE_TEMPLATE_ID:
            metadata["ecommerce_project_view"] = self._ecommerce_project_view(project)
            if operation is None:
                operation = (
                    ecommerce_operation
                    or self._ecommerce_current_operation(project)
                    or self._doc280_ecommerce_review_current_operation(project)
                )
                if operation is not None:
                    metadata["current_operation"] = operation
        return ProjectResponse(
            api_namespace=API_NAMESPACE,
            route=f"{API_NAMESPACE}/projects/{project.project_id}",
            project=public_project,
            templates=self.template_cards(),
            context=project.latest_context,
            metadata=metadata,
        )

    def _doc281_used_source_disclosures(self, project: ProjectRecord) -> list[dict[str, Any]]:
        """Project safe source labels for exact eligible Job/output bindings only."""

        delivered = self._project_output_items(project, limit=60)
        output_by_id = {
            self._public_project_output_identity(item): item
            for item in delivered
            if self._public_project_output_identity(item)
        }
        # Review history is a separate visible surface. Only its established
        # withheld-review projection may receive a source label; a failed or
        # merely materialized output is never promoted by this disclosure.
        for item in self._project_output_items(project, limit=60, include_hidden=True):
            output_id = self._public_project_output_identity(item)
            if (
                output_id
                and output_id not in output_by_id
                and self._public_project_output_has_image(item)
                and str(item.get("certification_state") or "") in {
                    "manual_confirmation_required", "blocked",
                }
            ):
                output_by_id[output_id] = item
        visible_positions = {
            self._public_project_output_identity(item): position
            for position, item in enumerate(output_by_id.values(), start=1)
            if self._public_project_output_identity(item)
        }
        disclosures: list[dict[str, Any]] = []
        for output_id, item in output_by_id.items():
            job_id = str(item.get("job_id") or "").strip()
            record = self.product_service.get_job_record(job_id)
            metadata = dict(getattr(getattr(record, "request", None), "metadata", {}) or {})
            bindings = metadata.get("doc281_general_output_source_bindings_v1")
            projection = metadata.get("doc270_general_original_source_projection")
            if (
                isinstance(bindings, list)
                and bindings
                and isinstance(projection, dict)
                and isinstance(projection.get("sources"), list)
                and projection["sources"]
            ):
                output_index = self._doc281_persisted_output_binding(
                    job_id=job_id, output_id=output_id, job_record=record,
                )
                if (
                    isinstance(output_index, int)
                    and any(
                        isinstance(binding, dict) and binding.get("output_index") == output_index
                        for binding in bindings
                    )
                ):
                    disclosures.append({
                        "output_label": f"Output {visible_positions[output_id]}",
                        "sources": [{"category": "project_original", "label": "Selected original"}],
                    })
                continue
            receipts = metadata.get("doc270_ecommerce_view_activation_receipts")
            if not isinstance(receipts, list) or not receipts:
                continue
            output_index = self._doc281_persisted_output_binding(
                job_id=job_id, output_id=output_id, job_record=record,
            )
            if (
                isinstance(output_index, int)
                and any(
                    isinstance(receipt, dict)
                    and receipt.get("output_index") == output_index
                    and isinstance(receipt.get("matched_references"), list)
                    and receipt["matched_references"]
                    for receipt in receipts
                )
            ):
                disclosures.append({
                    "output_label": f"Output {visible_positions[output_id]}",
                    "sources": [{"category": "project_original", "label": "Selected original"}],
                })
        return disclosures

    def _doc281_persisted_output_binding(
        self,
        *,
        job_id: str,
        output_id: str,
        job_record: Any,
    ) -> int | None:
        """Read and verify the immutable output-plan envelope on one output."""

        try:
            output_record = self.product_service.output_store.get_output(output_id)
        except Exception:
            return None
        if output_record is None or str(getattr(output_record, "job_id", "") or "") != job_id:
            return None
        envelope = dict(getattr(output_record, "metadata", {}) or {}).get("doc281_output_plan_binding")
        if not isinstance(envelope, dict) or set(envelope) != {
            "schema_version", "job_id", "command_identity_digest", "output_index",
            "output_nonce", "output_binding_digest", "source_receipt_digest", "output_id",
            "record_binding_digest",
        } or envelope.get("schema_version") != "doc281_output_plan_binding_v1" \
            or envelope.get("job_id") != job_id or envelope.get("output_id") != output_id \
            or not self._doc270_same_digest_record(envelope, "record_binding_digest"):
            return None
        metadata = dict(getattr(getattr(job_record, "request", None), "metadata", {}) or {})
        identity = metadata.get("doc270_general_command_identity")
        bindings = metadata.get("doc281_general_output_source_bindings_v1")
        projection = metadata.get("doc270_general_original_source_projection")
        if isinstance(identity, dict) and isinstance(bindings, list) and isinstance(projection, dict):
            if envelope.get("command_identity_digest") != identity.get("identity_digest") \
                or envelope.get("source_receipt_digest") != projection.get("source_receipt_digest"):
                return None
            binding = next(
                (
                    item for item in bindings
                    if isinstance(item, dict) and item.get("output_index") == envelope.get("output_index")
                ),
                None,
            )
            if not isinstance(binding, dict) or any(
                envelope.get(key) != binding.get(key)
                for key in ("output_index", "output_nonce", "output_binding_digest")
            ):
                return None
            return envelope["output_index"] if isinstance(envelope.get("output_index"), int) else None
        ecommerce_identity = metadata.get("doc270_ecommerce_command_identity")
        receipts = metadata.get("doc270_ecommerce_view_activation_receipts")
        receipt = next(
            (
                item for item in receipts
                if isinstance(item, dict) and item.get("output_index") == envelope.get("output_index")
            ),
            None,
        ) if isinstance(receipts, list) else None
        if (
            not isinstance(ecommerce_identity, dict)
            or not isinstance(receipt, dict)
            or envelope.get("command_identity_digest") != ecommerce_identity.get("identity_digest")
            or envelope.get("output_nonce") != receipt.get("requirement_nonce")
            or envelope.get("output_binding_digest") != receipt.get("receipt_digest")
            or envelope.get("source_receipt_digest") != receipt.get("receipt_digest")
        ):
            return None
        return envelope["output_index"] if isinstance(envelope.get("output_index"), int) else None

    @staticmethod
    def _public_project_record(project: ProjectRecord) -> ProjectRecord:
        """Keep durable continuation plans out of browser project reads."""

        public_metadata_keys = {
            "source",
            "project_mode",
            "v3_workspace",
            "frontend_surface",
            "selected_template_id",
            "template_manifest_id",
            "selected_scenario_id",
            "scenario_pack_id",
            "template_first_create",
            "selected_brand_memory_id",
            "selected_brand_memory_name",
            "imports_v1_v2_runtime",
            "imports_lab_runtime",
            "doc90_advanced_reference_controls",
            "advanced_reference_controls",
            "doc281_used_source_disclosures",
        }
        public_metadata = {
            key: value
            for key, value in dict(project.metadata or {}).items()
            if key in public_metadata_keys
        }
        return project.model_copy(update={"metadata": public_metadata}, deep=True)

    def _metadata(self) -> dict[str, Any]:
        ecommerce_manifest = self.template_registry.get_manifest(ECOMMERCE_TEMPLATE_ID)
        ecommerce_locked = not bool(ecommerce_manifest and ecommerce_manifest.project_can_create_jobs)
        return {
            "source": PROJECT_API_SOURCE,
            "project_mode": True,
            "v3_owned": True,
            "imports_v1_v2_runtime": False,
            "imports_lab_runtime": False,
            "ecommerce_template_locked": ecommerce_locked,
        }

    def _doc270_project_source_library(self, project: ProjectRecord) -> dict[str, Any]:
        """Build the current read-only original-source snapshot for Doc270."""

        return build_project_source_library(
            project_id=project.project_id,
            references=list(project.reference_assets),
            upload_lookup=self.product_service.get_uploaded_asset,
        )

    def _doc270_project_source_library_by_id(self, project_id: str) -> dict[str, Any]:
        return self._doc270_project_source_library(self._require_project(project_id))

    def _title_from_goal(self, goal: str) -> str:
        clean = goal.strip().replace("\n", " ")
        return self._short_text(clean, 18) or "V3 项目"

    def _short_text(self, value: str, limit: int) -> str:
        text = str(value or "").strip()
        return text if len(text) <= limit else f"{text[: max(1, limit - 1)]}..."


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded_requested_image_count(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return None


_REQUESTED_IMAGE_SIZE_ALIASES = {
    "1024x1024": "1024x1024",
    "1024×1024": "1024x1024",
    "1024 by 1024": "1024x1024",
    "1024x1536": "1024x1536",
    "1024×1536": "1024x1536",
    "1024 by 1536": "1024x1536",
    "1536x1024": "1536x1024",
    "1536×1024": "1536x1024",
    "1536 by 1024": "1536x1024",
}


def _explicit_requested_image_size(value: object) -> str | None:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    return _REQUESTED_IMAGE_SIZE_ALIASES.get(normalized)


def _infer_general_requested_image_size(user_input: str | None) -> str | None:
    """Honor an explicit General canvas instruction before the 4:5 default.

    General's default social canvas is an implementation fallback, not an
    instruction that may override a user's stated output format.  Only clear
    dimension or aspect-ratio language is inferred here; vague words such as
    "cinematic" or "banner-like" intentionally retain the default.
    """

    text = re.sub(r"\s+", " ", str(user_input or "").lower())
    compact = text.replace(" ", "")
    for alias, size in _REQUESTED_IMAGE_SIZE_ALIASES.items():
        if alias.replace(" ", "") in compact:
            return size
    ratio_patterns = (
        ("1536x1024", r"(?<!\d)3\s*[:：]\s*2(?!\d)"),
        ("1024x1536", r"(?<!\d)2\s*[:：]\s*3(?!\d)"),
        ("1024x1024", r"(?<!\d)1\s*[:：]\s*1(?!\d)"),
    )
    for size, pattern in ratio_patterns:
        if re.search(pattern, text):
            return size
    return None
