Warning: truncated output (original token count: 172849)
Total output lines: 14611

"""Project Mode service wrapping the existing V3 Product API."""

from __future__ import annotations

import base64
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
from ..creative_core.doc281_output_plan_binding import (
    DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY,
    validate_doc73_binding,
)
from ..creative_core.rules import stable_id
from ..product_api import V3ProductApiService
from ..product_api.contracts import (
    GenerateContinuation,
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
from ..variation_modes import (
    GENERAL_VARIATION_MODE_ALIASES,
    GENERAL_VARIATION_MODES,
    infer_general_variation_mode,
    resolve_general_variation_mode,
)
from ..visual_assets import ProjectVisualAssetBindingService
from .contracts import (
    ECOMMERCE_TEMPLATE_ID,
    GENERAL_TEMPLATE_ID,
    CreateProjectJobRequest,
    CreateProjectRequest,
    GeneralGenerationPreferences,
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
    ProjectGenerationPreferences,
    PhotographyGenerationPreferences,
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
_PROJECT_LIST_CURSOR_SCHEMA = "v3_project_list_cursor_v1"
_GENERAL_VARIATION_MODES = GENERAL_VARIATION_MODES
_GENERAL_VARIATION_MODE_ALIASES = GENERAL_VARIATION_MODE_ALIASES
# Home cards are a bounded read surface.  A project with more indexed Jobs
# than this can still receive a newest-candidate cover, but its exact formal
# and review counts stay unknown instead of making a long-tail read block the
# whole page or silently undercounting it.
_HOME_PREVIEW_MAX_JOB_STATES = 64
_HOME_PREVIEW_MAX_INDEX_RECORDS = 4096
_HOME_PREVIEW_MAX_OUTPUTS_PER_JOB = 128


def _project_listing_key(project: ProjectRecord) -> tuple[str, str, str]:
    return (
        str(project.updated_at or ""),
        str(project.created_at or ""),
        str(project.project_id or ""),
    )


def _encode_project_list_cursor(project: ProjectRecord) -> str:
    payload = {
        "created_at": str(project.created_at or ""),
        "project_id": str(project.project_id or ""),
        "schema_version": _PROJECT_LIST_CURSOR_SCHEMA,
        "updated_at": str(project.updated_at or ""),
    }
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_project_list_cursor(value: str | None) -> tuple[str, str, str] | None:
    if value is None or not str(value).strip():
        return None
    token = str(value).strip()
    try:
        padded = token + ("=" * (-len(token) % 4))
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError, base64.binascii.Error) as exc:
        raise ValueError("v3_project_cursor_invalid") from exc
    if not isinstance(payload, dict) or set(payload) != {"created_at", "project_id", "schema_version", "updated_at"}:
        raise ValueError("v3_project_cursor_invalid")
    if payload.get("schema_version") != _PROJECT_LIST_CURSOR_SCHEMA:
        raise ValueError("v3_project_cursor_invalid")
    if not all(isinstance(payload.get(key), str) and payload[key] for key in ("created_at", "project_id", "updated_at")):
        raise ValueError("v3_project_cursor_invalid")
    return (payload["updated_at"], payload["created_at"], payload["project_id"])
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
_DOC73_AUTO_IDENTITY_ANCHOR_CONTROL_NAMESPACE = "doc73_auto_identity_anchor_controls_v1"
_DOC73_AUTO_IDENTITY_ANCHOR_CONTROL_SCHEMA = "doc73_auto_identity_anchor_control_v1"
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
                if self._doc270_general_existing_job_replayable(project, record):
                    return self.product_service.get_job(job_id)
                if self._doc270_general_existing_job_retryable(record) or self._doc270_general_existing_job_needs_delivery_retry(project, record):
                    continue
                status = str(getattr(getattr(record, "status", None), "value", getattr(record, "status", "")) or "").strip().lower()
                if status in {"generated", "selected", "ready"} and not self._doc270_general_existing_job_has_usable_output(project, record):
                    # A legacy record can say generated after Brain/Provider
                    # work while lacking a persisted V3 output. Never replay
                    # that metadata-only success to the browser.
                    continue
                return self.product_service.get_job(job_id)
        return None

    def _doc270_general_existing_job_has_usable_output(self, project: ProjectRecord, record: Any) -> bool:
        job_id = str(getattr(record, "job_id", "") or "").strip()
        if not job_id:
            return False
        try:
            visible_items = self._project_output_items(project, limit=160, include_hidden=False)
        except Exception:
            return False
        if any(str(item.get("job_id") or "").strip() == job_id for item in visible_items):
            return True
        output_store = getattr(self.product_service, "output_store", None)
        if output_store is None:
            return False
        try:
            records = output_store.list_by_job(str(getattr(record, "job_id", "") or ""))
        except Exception:
            return False
        return any(
            self._output_record_has_usable_image(item)
            and bool(str(getattr(item, "file_path", "") or "").strip())
            and Path(str(getattr(item, "file_path", "") or "")).is_file()
            for item in records
        )

    def _doc270_general_existing_job_needs_delivery_retry(self, project: ProjectRecord, record: Any) -> bool:
        raw_status = getattr(record, "status", "")
        status = str(getattr(raw_status, "value", raw_status) or "").strip().lower()
        return status in {"generated", "selected", "ready"} and not self._doc270_general_existing_job_has_usable_output(project, record)

    def _doc270_general_retry_requested(
        self,
        project: ProjectRecord,
        identity: dict[str, Any],
        requested_job_id: Any,
    ) -> bool:
        """Authorize an explicit UI retry for the current terminal Job only."""

        job_id = str(requested_job_id or "").strip()
        if not job_id or job_id not in project.job_ids:
            return False
        record = self.product_service.get_job_record(job_id)
        if record is None:
            return False
        if dict(record.request.metadata or {}).get("doc270_general_command_identity") != identity:
            return False
        raw_status = getattr(record, "status", "")
        status = str(getattr(raw_status, "value", raw_status) or "").strip().lower()
        return status in {"generated", "selected", "ready", "blocked", "failed"}

    def _doc270_general_existing_job_replayable(self, project: ProjectRecord, record: Any) -> bool:
        """Keep durable replay strict while allowing transient Brain recovery.

        A command identity is still immutable evidence.  A blocked record is
        only re-plannable when the remote Brain stopped before any image
        request and its typed lifecycle evidence identifies a transport or
        availability failure.  Product-policy closures and provider failures
        remain immutable replays.
        """

        raw_status = getattr(record, "status", "")
        status = str(getattr(raw_status, "value", raw_status) or "").strip().lower()
        if status in {"generated", "selected", "ready"}:
            return self._doc270_general_existing_job_has_usable_output(project, record)
        if status not in {"blocked", "failed"}:
            return True
        return not self._doc270_general_existing_job_retryable(record)

    @staticmethod
    def _doc270_general_existing_job_retryable(record: Any) -> bool:
        """Recognize only a transient pre-provider remote-Brain failure."""

        raw_status = getattr(record, "status", "")
        status = str(getattr(raw_status, "value", raw_status) or "").strip().lower()
        if status not in {"blocked", "failed"}:
            return False
        metadata = dict(getattr(getattr(record, "request", None), "metadata", {}) or {})
        failure = metadata.get("generation_lifecycle_failure")
        if not isinstance(failure, dict) or failure.get("schema_version") != "v3_generation_lifecycle_failure_v1":
            return False
        if failure.get("failure_family") != "remote_creative_brain" or failure.get("provider_request_started") is not False:
            return False
        outcome = failure.get("remote_creative_brain_outcome")
        if not isinstance(outcome, dict) or outcome.get("state") != "blocked":
            return False
        transport = outcome.get("remote_brain_transport_failure")
        return bool(
            outcome.get("remote_provider_available") is False
            or outcome.get("remote_error_class") in {"timeout", "unavailable"}
            or (isinstance(transport, dict) and transport.get("transport_error_class") in {"timeout", "connect_error", "read_error"})
        )

    def _doc270_general_retryable_command_exists(
        self,
        project: ProjectRecord,
        identity: dict[str, Any],
    ) -> bool:
        for job_id in project.job_ids:
            record = self.product_service.get_job_record(job_id)
            if record is None:
                continue
            metadata = dict(record.request.metadata or {})
            if metadata.get("doc270_general_command_identity") == identity and (
                self._doc270_general_existing_job_retryable(record)
                or self._doc270_general_existing_job_needs_delivery_retry(project, record)
            ):
                return True
        return False

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
                for key in ("command_id", "command_plan_binding_digest", "coalesc…122849 tokens truncated…                   actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
                except (OSError, ValueError, TypeError):
                    continue
                expected_digest = str(binding.get("source_content_sha256") or "").strip().lower()
                if expected_digest.startswith("sha256:"):
                    expected_digest = expected_digest.split(":", 1)[1].strip()
                if (
                    len(expected_digest) != 64
                    or any(character not in "0123456789abcdef" for character in expected_digest)
                    or actual_digest != expected_digest
                ):
                    continue
                control_state = self._doc73_auto_identity_anchor_control_state(
                    project.project_id,
                    clean_job_id,
                    record_output_id,
                )
                if control_state == "invalid":
                    return {
                        "record": record,
                        "binding": dict(binding),
                        "state": "invalid",
                    }
                return {
                    "record": record,
                    "binding": dict(binding),
                    "state": "unbound" if control_state == "unbound" else "bound",
                }
        return None

    def _doc73_auto_identity_anchor_transport(
        self,
        project: ProjectRecord,
    ) -> dict[str, Any] | None:
        """Project Mode's private handoff for the already-bound auto anchor."""

        anchor = self._doc73_auto_identity_anchor_record(project)
        if not isinstance(anchor, dict) or anchor.get("state") != "bound":
            return None
        record = anchor.get("record")
        binding = anchor.get("binding")
        file_path = str(getattr(record, "file_path", "") or "").strip()
        output_id = str(getattr(record, "output_id", "") or "").strip()
        candidate_id = str(getattr(record, "candidate_id", "") or "").strip()
        if not file_path or not output_id or not candidate_id or not isinstance(binding, dict):
            return None
        reference = {
            "asset_id": output_id,
            "source_id": output_id,
            "output_id": output_id,
            "candidate_id": candidate_id,
            "source_type": "auto_batch_continuity",
            "origin": "auto_batch_continuity",
            "role": "continuity_reference",
            "use_policy": "continuity",
            "strength": "hard",
            "provider_input_required": True,
            "file_path": file_path,
            "filename": Path(file_path).name,
            "mime_type": str(getattr(record, "mime_type", "") or "image/png"),
            "lock_targets": [
                "broad face shape",
                "eye shape and spacing",
                "nose-mouth relationship",
                "jawline direction",
                "age impression",
                "body type and proportions",
            ],
            "metadata": {
                "doc": "73",
                "auto_batch_identity_anchor": True,
                "origin": "auto_batch_continuity",
                DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY: dict(binding),
                "source_asset_id": binding.get("source_asset_id"),
                "project_id": project.project_id,
                "user_reference_priority": True,
                "doc93_reference_channel_safe": True,
            },
            DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY: dict(binding),
        }
        return {
            "doc73_auto_identity_anchor_receipt": dict(binding),
            "doc73_auto_identity_anchor_reference": reference,
        }

    def _doc73_auto_identity_anchor_control_state(
        self,
        project_id: str,
        job_id: str,
        output_id: str,
    ) -> str:
        list_private_records = getattr(self.project_store, "list_private_records", None)
        if not callable(list_private_records):
            return "bound"
        try:
            records = list_private_records(project_id, _DOC73_AUTO_IDENTITY_ANCHOR_CONTROL_NAMESPACE)
        except Exception:
            return "invalid"
        control_keys = {
            "schema_version", "project_id", "job_id", "output_id", "state", "changed_at",
        }
        for record in reversed(records):
            if not isinstance(record, dict):
                continue
            if (
                record.get("project_id") != project_id
                or record.get("job_id") != job_id
                or record.get("output_id") != output_id
            ):
                continue
            if (
                set(record) != control_keys
                or record.get("schema_version") != _DOC73_AUTO_IDENTITY_ANCHOR_CONTROL_SCHEMA
            ):
                return "invalid"
            state = record.get("state")
            if state in {"bound", "unbound"}:
                return state
            return "invalid"
        return "bound"

    def _record_doc73_auto_identity_anchor_control(
        self,
        *,
        project_id: str,
        job_id: str,
        output_id: str,
        state: str,
        changed_at: str,
    ) -> bool:
        append_private_record = getattr(self.project_store, "append_private_record", None)
        if not callable(append_private_record) or state not in {"bound", "unbound"}:
            return False
        try:
            append_private_record(
                project_id,
                _DOC73_AUTO_IDENTITY_ANCHOR_CONTROL_NAMESPACE,
                {
                    "schema_version": _DOC73_AUTO_IDENTITY_ANCHOR_CONTROL_SCHEMA,
                    "project_id": project_id,
                    "job_id": job_id,
                    "output_id": output_id,
                    "state": state,
                    "changed_at": changed_at,
                },
            )
        except Exception:
            return False
        return True

    def _doc73_auto_identity_anchor_public_projection(
        self,
        project: ProjectRecord,
        *,
        owner_user_id: int | None = None,
    ) -> dict[str, Any] | None:
        anchor = self._doc73_auto_identity_anchor_record(
            project,
            owner_user_id=owner_user_id,
        )
        if anchor is None:
            return None
        record = anchor["record"]
        state = str(anchor.get("state") or "").strip().lower()
        if state not in {"bound", "unbound"}:
            return None
        bound = state == "bound"
        return {
            "schema_version": "doc73_auto_identity_anchor_public_v1",
            "state": state,
            "binding_mode": "automatic_continuity",
            "review_surface": "identity_anchor",
            "project_id": project.project_id,
            "job_id": str(getattr(record, "job_id", "") or "").strip(),
            "output_id": str(getattr(record, "output_id", "") or "").strip(),
            "asset_id": str(getattr(record, "asset_id", "") or "").strip(),
            "preview_url": getattr(record, "preview_url", None),
            "thumbnail_url": getattr(record, "thumbnail_url", None),
            "download_url": getattr(record, "download_url", None),
            "created_at": getattr(record, "created_at", None),
            "label": "人物身份锚点",
            "can_unbind": bound,
            "can_bind": not bound,
        }

    def _project_visible_output_count(
        self,
        project: ProjectRecord,
        *,
        owner_user_id: int | None = None,
        project_records: list[Any] | None = None,
        output_records_by_job: dict[str, list[Any]] | None = None,
        job_status_by_id: dict[str, ProductJobStatus | None] | None = None,
        job_record_by_id: dict[str, Any] | None = None,
        job_read_failures: set[str] | None = None,
    ) -> int | None:
        """Count formal delivery outputs without inventing a second gate.

        Home cards need a number, but the one-cover preview cannot provide it.
        Reuse the same Project Mode delivery projection that owns visibility,
        review, retry, selection, and owner predicates; this helper only
        changes the result shape from output items to a count.
        """

        product_service = getattr(self, "product_service", None)
        output_store = getattr(product_service, "output_store", None)
        list_by_project = getattr(output_store, "list_by_project", None)
        if output_store is None or not callable(list_by_project):
            return None
        if project_records is None:
            try:
                project_records = list(list_by_project(project.project_id, limit=4096))
            except Exception:
                return None
        records = list(project_records)
        if not records:
            return 0
        records_by_job = output_records_by_job if output_records_by_job is not None else {}
        for record in records:
            job_id = str(getattr(record, "job_id", "") or "").strip()
            if not job_id:
                continue
            bucket = records_by_job.setdefault(job_id, [])
            output_id = str(getattr(record, "output_id", "") or "").strip()
            if output_id and any(
                str(getattr(existing, "output_id", "") or "").strip() == output_id
                for existing in bucket
            ):
                continue
            bucket.append(record)
        indexed_job_ids = {
            str(getattr(record, "job_id", "") or "").strip()
            for record in records
            if str(getattr(record, "job_id", "") or "").strip()
        }
        declared_job_ids = [
            str(job_id or "").strip()
            for job_id in (project.job_ids or [])
            if str(job_id or "").strip()
        ]
        candidate_job_ids = (
            [job_id for job_id in declared_job_ids if job_id in indexed_job_ids]
            if declared_job_ids
            else self._project_indexed_job_ids(project, records)
        )
        if not candidate_job_ids:
            return 0
        count_project = project
        model_copy = getattr(project, "model_copy", None)
        if callable(model_copy):
            count_project = model_copy(update={"job_ids": candidate_job_ids}, deep=False)
        visible_items = self._project_output_items(
            count_project,
            limit=max(1, len(records)),
            owner_user_id=owner_user_id,
            compact=True,
            output_records_by_job=records_by_job,
            job_status_by_id=job_status_by_id,
            job_record_by_id=job_record_by_id,
            job_read_failures=job_read_failures,
        )
        return len(visible_items)

    def _project_delivery_preview_items(
        self,
        project: ProjectRecord,
        *,
        limit: int = 1,
        owner_user_id: int | None = None,
        compact: bool = True,
        project_records: list[Any] | None = None,
        output_records_by_job: dict[str, list[Any]] | None = None,
        job_status_by_id: dict[str, ProductJobStatus | None] | None = None,
        job_record_by_id: dict[str, Any] | None = None,
        job_read_failures: set[str] | None = None,
        candidate_job_limit: int | None = None,
        home_candidate_job_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Find one newest project output without scanning every project Job.

        The output store index is only a candidate locator. The existing
        ``_project_output_items`` predicates still decide whether the Job and
        output are a formal delivery, so preview loading cannot widen public
        delivery or continuation authority.
        """

        output_store = getattr(self.product_service, "output_store", None)
        list_by_project = getattr(output_store, "list_by_project", None)
        if project_records is None and not callable(list_by_project):
            return []
        if project_records is None:
            try:
                records = list_by_project(project.project_id, limit=256)
            except Exception:
                return []
        else:
            records = list(project_records)
        if home_candidate_job_ids is not None:
            candidate_job_ids = list(dict.fromkeys(
                str(job_id or "").strip()
                for job_id in home_candidate_job_ids
                if str(job_id or "").strip()
            ))
        else:
            allowed_job_ids = set(self._project_indexed_job_ids(project, records))
            newest_by_job: dict[str, str] = {}
            for record in records:
                job_id = str(getattr(record, "job_id", "") or "").strip()
                if not job_id or job_id not in allowed_job_ids:
                    continue
                created_at = str(getattr(record, "created_at", "") or "")
                if created_at > newest_by_job.get(job_id, ""):
                    newest_by_job[job_id] = created_at
            if not newest_by_job:
                return []
            candidate_job_ids = [
                job_id
                for job_id, _created_at in sorted(
                    newest_by_job.items(),
                    key=lambda entry: (entry[1], entry[0]),
                    reverse=True,
                )
            ]
            if candidate_job_limit is not None:
                bounded_candidate_limit = max(1, int(candidate_job_limit or 1))
                candidate_job_ids = candidate_job_ids[:bounded_candidate_limit]
        if not candidate_job_ids:
            return []
        # ``_project_output_items`` preserves the Project record's historical
        # oldest-to-newest order by iterating ``project.job_ids`` in reverse.
        # Keep that invariant here so a stale legacy job cannot run before the
        # newest indexed candidate and block the home cover.
        preview_project = project.model_copy(
            update={"job_ids": list(reversed(candidate_job_ids))},
            deep=False,
        )
        snapshot_kwargs = {}
        if output_records_by_job is not None:
            snapshot_kwargs["output_records_by_job"] = output_records_by_job
        if job_status_by_id is not None:
            snapshot_kwargs["job_status_by_id"] = job_status_by_id
        if job_record_by_id is not None:
            snapshot_kwargs["job_record_by_id"] = job_record_by_id
        if job_read_failures is not None:
            snapshot_kwargs["job_read_failures"] = job_read_failures
        return self._project_output_items(
            preview_project,
            limit=min(max(1, int(limit or 1)), 1),
            owner_user_id=owner_user_id,
            compact=compact,
            **snapshot_kwargs,
        )

    def _project_job_delivery_is_settled(self, job_id: str) -> bool:
        """Known in-flight jobs must not leak process outputs onto project boards."""

        job_status = self.product_service.get_job(job_id)
        return self._job_delivery_is_settled(job_status)

    @staticmethod
    def _output_store_restore_state(job_status: ProductJobStatus) -> str:
        return str(dict(job_status.metadata or {}).get("output_store_restore_state") or "").strip().lower()

    @staticmethod
    def _output_store_recovery_required(job_status: ProductJobStatus) -> bool:
        return V3ProjectModeService._output_store_restore_state(job_status) in {
            "needs_recovery",
            "delivery_withheld",
        }

    @staticmethod
    def _job_delivery_is_settled(job_status: ProductJobStatus) -> bool:
        """Keep one terminal-state rule for normal and recovered Project outputs."""

        if V3ProjectModeService._output_store_recovery_required(job_status):
            return False
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
    def _canonical_final_delivery_output_ids(job_status: ProductJobStatus) -> set[str] | None:
        """Return the Job-owned final output set when a modern review gate applies."""

        metadata = dict(job_status.metadata or {})
        final_delivery = metadata.get("final_delivery")
        if not isinstance(final_delivery, dict) or not bool(final_delivery.get("delivery_gate_applies")):
            return None
        if final_delivery.get("automatic_delivery_available") is not True:
            return set()
        review = metadata.get("post_generation_review")
        if not isinstance(review, dict):
            return set()
        if "recommended_output_ids" in review:
            values = review.get("recommended_output_ids")
            if not isinstance(values, list):
                return set()
            return {str(value).strip() for value in values if str(value).strip()}
        review_items = review.get("review_items", review.get("inspections", []))
        if not isinstance(review_items, list):
            return set()
        return {
            str(item.get("output_id") or "").strip()
            for item in review_items
            if isinstance(item, dict)
            and str(item.get("output_id") or "").strip()
            and str(item.get("mode") or "").strip().lower() in {"vision_model", "hybrid"}
            and str(item.get("verification_state") or "").strip().lower() == "verified"
            and str(item.get("status") or "").strip().lower() in {"pass", "warning"}
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
        review_items = review.get("review_items", review.get("inspections", []))
        for item in review_items:
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
        canonical_final_output_ids = V3ProjectModeService._canonical_final_delivery_output_ids(job_status)
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
        projection = {
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
            "_final_delivery_output_eligible": (
                canonical_final_output_ids is None
                or output_id in canonical_final_output_ids
            ),
        }
        restore_state = V3ProjectModeService._output_store_restore_state(job_status)
        if restore_state in {"needs_recovery", "delivery_withheld"}:
            projection.update(
                {
                    "output_store_restore_state": restore_state,
                    "review_only": True,
                    "recovery_required": True,
                }
            )
        return projection

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
        return (
            str(review_projection.get("public_delivery_state") or "").strip().lower() == "ready"
            and bool(review_projection.get("_final_delivery_output_eligible"))
        )

    def _output_ref_from_record(self, project: ProjectRecord, record: Any) -> OutputRef:
        preview_url, thumbnail_url, download_url = self._canonical_output_urls(record)
        return OutputRef(
            output_ref_id=stable_id("output_ref", project.project_id, record.job_id, record.output_id),
            source_type="generated_output",
            project_id=project.project_id,
            job_id=record.job_id,
            asset_id=record.asset_id,
            candidate_id=record.candidate_id,
            output_id=record.output_id,
            preview_url=preview_url,
            thumbnail_url=thumbnail_url,
            download_url=download_url,
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
        restore_state = str(public_review.get("output_store_restore_state") or "").strip().lower()
        if restore_state in {"needs_recovery", "delivery_withheld"}:
            delivery_metadata = {
                **delivery_metadata,
                "delivery_state": "review_only",
                "output_store_restore_state": restore_state,
                "review_only": True,
                "recovery_required": True,
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
        return project_owner_id == owner_user_id

    def _project_workspace(self, project: ProjectRecord) -> str:
        """Return the persisted V3 workspace without inferring from a template."""

        workspace = str((project.metadata or {}).get("v3_workspace") or "").strip().lower()
        return "professional" if workspace == "professional" else "standard"

    def _output_record_visible_to_owner(self, record: Any, owner_user_id: int | None) -> bool:
        if owner_user_id is None:
            return True
        metadata = dict(getattr(record, "metadata", None) or {})
        record_owner_id = self._positive_owner_id(metadata.get("veyra_user_id"))
        return record_owner_id == owner_user_id

    def _project_output_record_visible_to_owner(
        self,
        project: ProjectRecord,
        record: Any,
        owner_user_id: int | None,
    ) -> bool:
        """Apply project-scoped legacy ownership without widening references.

        New records keep the strict output-owner predicate.  Only an output
        with an absent/empty owner can inherit the owner of the exact project
        named in its metadata; malformed owner values, missing project links,
        and ownerless projects remain fail-closed.  This helper is used only
        while a project is already in a caller-visible scope.
        """

        if owner_user_id is None:
            return True
        metadata = dict(getattr(record, "metadata", None) or {})
        raw_output_owner = metadata.get("veyra_user_id")
        record_owner_id = self._positive_owner_id(raw_output_owner)
        if record_owner_id is not None:
            return record_owner_id == owner_user_id
        if raw_output_owner is not None and str(raw_output_owner).strip():
            return False
        record_project_id = str(metadata.get("project_id") or "").strip()
        if not record_project_id or record_project_id != str(project.project_id or "").strip():
            return False
        project_owner_id = self._positive_owner_id(project.metadata.get("veyra_user_id"))
        return project_owner_id == owner_user_id

    def _job_record_visible_to_owner(self, record: Any, owner_user_id: int | None) -> bool:
        if owner_user_id is None or record is None:
            return True
        metadata = dict(getattr(getattr(record, "request", None), "metadata", None) or {})
        record_owner_id = self._positive_owner_id(metadata.get("veyra_user_id"))
        return record_owner_id == owner_user_id

    def _project_job_record_visible_to_owner(
        self,
        project: ProjectRecord,
        record: Any,
        owner_user_id: int | None,
    ) -> bool:
        """Apply the same narrow project fallback to legacy Job metadata.

        Some old project Jobs carry the project link but predate the
        output/job-level Veyra owner field.  Only a project-scoped output read
        may use that link, and only after the project itself has a matching
        owner.  Generic Job reads keep the strict owner predicate above.
        """

        if owner_user_id is None or record is None:
            return True
        metadata = dict(getattr(getattr(record, "request", None), "metadata", None) or {})
        raw_job_owner = metadata.get("veyra_user_id")
        record_owner_id = self._positive_owner_id(raw_job_owner)
        if record_owner_id is not None:
            return record_owner_id == owner_user_id
        if raw_job_owner is not None and str(raw_job_owner).strip():
            return False
        record_project_id = str(metadata.get("project_id") or "").strip()
        if not record_project_id or record_project_id != str(project.project_id or "").strip():
            return False
        project_owner_id = self._positive_owner_id(project.metadata.get("veyra_user_id"))
        return project_owner_id == owner_user_id

    def _project_job_owner_gap_can_use_project_output_scope(
        self,
        project: ProjectRecord,
        record: Any,
        output_records: list[Any],
        owner_user_id: int | None,
    ) -> bool:
        """Recover a legacy Job owner gap only for linked project outputs.

        A legacy Job may have neither an owner nor a project field even though
        it is persisted in the visible project's ``job_ids`` and its output
        record carries the exact project link.  The project membership plus
        output link is sufficient for this already project-scoped read, but
        never becomes a generic Job authorization fallback.
        """

        if owner_user_id is None or record is None:
            return True
        metadata = dict(getattr(getattr(record, "request", None), "metadata", None) or {})
        raw_job_owner = metadata.get("veyra_user_id")
        if raw_job_owner is not None and str(raw_job_owner).strip():
            return False
        project_owner_id = self._positive_owner_id(project.metadata.get("veyra_user_id"))
        if project_owner_id != owner_user_id:
            return False
        project_id = str(project.project_id or "").strip()
        for output_record in output_records:
            output_metadata = dict(getattr(output_record, "metadata", None) or {})
            raw_output_owner = output_metadata.get("veyra_user_id")
            if raw_output_owner is not None and str(raw_output_owner).strip():
                continue
            if str(output_metadata.get("project_id") or "").strip() == project_id:
                return True
        return False

    def _uploaded_reference_visible_to_owner(
        self,
        reference: dict[str, Any],
        owner_user_id: int | None,
    ) -> bool:
        if owner_user_id is None:
            return True
        asset_id = str(
            reference.get("asset_ref_id")
            or reference.get("asset_id")
            or ""
        ).strip()
        if not asset_id:
            return False
        try:
            record = self.product_service.get_uploaded_asset(asset_id)
        except Exception:
            return False
        return record is not None and self._positive_owner_id(
            getattr(record, "veyra_user_id", None)
        ) == owner_user_id

    def _output_ref_visible_to_owner(
        self,
        reference: OutputRef,
        owner_user_id: int | None,
    ) -> bool:
        if owner_user_id is None:
            return True
        output_store = getattr(self.product_service, "output_store", None)
        get_output = getattr(output_store, "get_output", None)
        if not callable(get_output):
            return False
        identifiers = {
            str(getattr(reference, field, None) or "").strip()
            for field in ("output_id", "asset_id", "candidate_id", "output_ref_id")
        }
        identifiers.discard("")
        for identifier in identifiers:
            try:
                record = get_output(identifier)
            except Exception:
                continue
            if record is not None and self._output_record_visible_to_owner(record, owner_user_id):
                return True
        return False

    def _reference_visible_to_owner(
        self,
        reference: ProjectReferenceAsset,
        owner_user_id: int | None,
    ) -> bool:
        if owner_user_id is None:
            return True
        if reference.source_type == ProjectReferenceSourceType.UPLOADED:
            return self._uploaded_reference_visible_to_owner(
                {"asset_ref_id": reference.asset_ref_id},
                owner_user_id,
            )
        if reference.source_type == ProjectReferenceSourceType.GENERATED_SELECTED:
            output_store = getattr(self.product_service, "output_store", None)
            get_output = getattr(output_store, "get_output", None)
            if not callable(get_output):
                return False
            output_id = str(
                reference.created_from_output_id or reference.asset_ref_id or ""
            ).strip()
            try:
                record = get_output(output_id) if output_id else None
            except Exception:
                record = None
            return record is not None and self._output_record_visible_to_owner(
                record,
                owner_user_id,
            )
        return False

    def _timeline_items_for_owner(
        self,
        items: list[ProjectTimelineItem],
        owner_user_id: int | None,
    ) -> list[ProjectTimelineItem]:
        if owner_user_id is None:
            return items
        visible_items: list[ProjectTimelineItem] = []
        for item in items:
            related_job_ids = {
                str(value or "").strip()
                for value in (item.job_id, item.related_job_id)
                if str(value or "").strip()
            }
            if any(
                not self._job_record_visible_to_owner(
                    self.product_service.get_job_record(job_id),
                    owner_user_id,
                )
                for job_id in related_job_ids
            ):
                continue
            visible_refs = [
                reference
                for reference in item.selected_output_refs
                if self._output_ref_visible_to_owner(reference, owner_user_id)
            ]
            visible_items.append(
                item.model_copy(update={"selected_output_refs": visible_refs})
            )
        return visible_items

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

    def _selection_from_persisted_output_refs(
        self,
        status: ProductJobStatus,
        refs: list[OutputRef],
    ) -> SelectionResponse:
        """Build a selection receipt from exact output-store bindings.

        A restarted worker may have persisted pixels while the append-only Job
        record still has no planning candidate/asset projection. Project Mode
        may select those pixels only after its job-scoped output resolver has
        proved the binding; it must never invent a candidate or choose a
        sibling output.
        """

        candidate_ids = list(dict.fromkeys(ref.candidate_id for ref in refs if ref.candidate_id))
        asset_ids = list(dict.fromkeys(ref.asset_id for ref in refs if ref.asset_id))
        selected_result = SelectedResult(
            selected_candidate_ids=candidate_ids,
            selected_asset_ids=asset_ids,
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

    def _resolved_output_refs_for_status(
        self,
        project: ProjectRecord,
        status: ProductJobStatus,
        *,
        selected_candidate_id: str | None = None,
        selected_asset_id: str | None = None,
        selected_candidate_ids: set[str] | None = None,
        selected_asset_ids: set[str] | None = None,
        selected_output_id: str | None = None,
        selected_output_ids: set[str] | None = None,
    ) -> tuple[list[OutputRef], list[dict[str, Any]]]:
        """Resolve a selection to exact V3 output records before it is persisted.

        Candidate and asset identifiers are planning identifiers, not provider
        inputs.  The project layer is deliberately strict here: a continuation
        may use an exact materialized output, or it is held.  It must never
        fall back to another candidate from the same job.
        """

        selected_candidate_ids = set(selected_candidate_ids or [])
        selected_asset_ids = set(selected_asset_ids or [])
        selected_output_ids = set(selected_output_ids or [])
        if selected_candidate_id:
            selected_candidate_ids.add(selected_candidate_id)
        if selected_asset_id:
            selected_asset_ids.add(selected_asset_id)
        if selected_output_id:
            selected_output_ids.add(selected_output_id)
        refs: list[OutputRef] = []
        now = _utc_now_iso()
        has_selection_filter = bool(selected_candidate_ids or selected_asset_ids or selected_output_ids)
        selected_candidates: list[Any] = []
        for candidate in status.candidates:
            if has_selection_filter and not (
                candidate.candidate_id in selected_candidate_ids
                or candidate.asset_id in selected_asset_ids
                or candidate.output_id in selected_output_ids
            ):
                continue
            selected_candidates.append(candidate)
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
        selected_candidate_asset_ids = {
            candidate.asset_id for candidate in selected_candidates if candidate.asset_id
        }
        for asset in status.asset_series:
            if has_selection_filter and not (
                asset.asset_id in selected_asset_ids
                or asset.output_id in selected_output_ids
                or asset.asset_id in selected_candidate_asset_ids
                or asset.selected_candidate_id in selected_candidate_ids
            ):
                continue
            # A candidate ref is authoritative when the same output was
            # selected through a candidate id. Add an asset ref only for an
            # asset-only branch (including legacy records with no candidate).
            if asset.asset_id in selected_candidate_asset_ids:
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
        persisted_refs, persisted_unresolved = self._persisted_output_refs_for_selection(
            project,
            status,
            selected_candidate_ids=selected_candidate_ids,
            selected_asset_ids=selected_asset_ids,
            selected_output_ids=selected_output_ids,
            existing_refs=refs,
            selected_at=now,
        )
        refs.extend(persisted_refs)
        resolved: list[OutputRef] = []
        unresolved: list[dict[str, Any]] = list(persisted_unresolved)
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

    def _persisted_output_refs_for_selection(
        self,
        project: ProjectRecord,
        status: ProductJobStatus,
        *,
        selected_candidate_ids: set[str],
        selected_asset_ids: set[str],
        selected_output_ids: set[str],
        existing_refs: list[OutputRef],
        selected_at: str,
    ) -> tuple[list[OutputRef], list[dict[str, Any]]]:
        """Resolve explicit selectors against the job-scoped output store.

        This is intentionally a recovery adapter, not a replacement for the
        Product Job candidate projection. It is used only for explicit
        selection IDs and accepts a record only when exactly one renderable
        output matches that ID inside the current project-owned job.
        """

        selectors = {
            *(('candidate', selector) for selector in selected_candidate_ids),
            *(('asset', selector) for selector in selected_asset_ids),
            *(('output', selector) for selector in selected_output_ids),
        }
        if not selectors:
            return [], []
        existing_selector_bindings = {
            (selector_type, str(value or "").strip())
            for ref in existing_refs
            for selector_type, value in (
                ("output", ref.output_id),
                ("candidate", ref.candidate_id),
                ("asset", ref.asset_id),
            )
            if str(value or "").strip()
        }
        # The status projection is already authoritative for selectors it
        # contains.  The output-store adapter is only needed for an explicit
        # selector that is absent from that projection (for example a durable
        # output written just before a worker restart).  Do not manufacture a
        # store-unavailable diagnostic when every selector will still pass
        # through the canonical materialization gate below.
        selectors_to_resolve = selectors - existing_selector_bindings
        if not selectors_to_resolve:
            return [], []
        output_store = getattr(getattr(self, "product_service", None), "output_store", None)
        list_by_job = getattr(output_store, "list_by_job", None)
        if not callable(list_by_job):
            return [], [
                {
                    "job_id": status.job_id,
                    "reason": "materialized_output_store_unavailable",
                }
            ]
        try:
            records = list(list_by_job(status.job_id))
        except Exception:
            return [], [
                {
                    "job_id": status.job_id,
                    "reason": "materialized_output_store_unavailable",
                }
            ]
        matches_by_selector: dict[tuple[str, str], list[Any]] = {
            selector: [] for selector in selectors_to_resolve
        }
        for record in records:
            if str(getattr(record, "job_id", "") or "").strip() != status.job_id:
                continue
            record_ids = {
                "candidate": str(getattr(record, "candidate_id", "") or "").strip(),
                "asset": str(getattr(record, "asset_id", "") or "").strip(),
                "output": str(getattr(record, "output_id", "") or "").strip(),
            }
            for selector in selectors_to_resolve:
                if record_ids.get(selector[0]) == selector[1]:
                    matches_by_selector[selector].append(record)
        selected_records: dict[str, Any] = {}
        unresolved: list[dict[str, Any]] = []
        for selector_type, selector in sorted(selectors_to_resolve):
            selector_key = (selector_type, selector)
            matches = matches_by_selector.get(selector_key, [])
            if len(matches) != 1:
                unresolved.append(
                    {
                        "job_id": status.job_id,
                        "selector": selector,
                        "selector_type": selector_type,
                        "reason": (
                            "materialized_output_selector_not_found"
                            if not matches
                            else "materialized_output_selector_ambiguous"
                        ),
                    }
                )
                continue
            record = matches[0]
            output_id = str(getattr(record, "output_id", "") or "").strip()
            if not output_id or not self._output_record_is_renderable(record):
                unresolved.append(
                    {
                        "job_id": status.job_id,
                        "selector": selector,
                        "reason": "materialized_output_unavailable",
                    }
                )
                continue
            record_bindings = {
                (field, str(getattr(record, f"{field}_id", "") or "").strip())
                for field in ("output", "candidate", "asset")
                if str(getattr(record, f"{field}_id", "") or "").strip()
            }
            if record_bindings.intersection(existing_selector_bindings):
                continue
            selected_records[output_id] = record
        refs: list[OutputRef] = []
        for output_id, record in selected_records.items():
            base = self._output_ref_from_record(project, record)
            refs.append(
                base.model_copy(
                    update={
                        "selection_reason": "user selected persisted project output",
                        "selected_at": selected_at,
                        "metadata": {
                            **dict(base.metadata or {}),
                            "restored_from_output_store": True,
                        },
                    }
                )
            )
        return refs, unresolved

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
        preview_url, thumbnail_url, download_url = self._canonical_output_urls(record)
        source_integrity_id = self._output_source_integrity_id(record)
        return OutputRef(
            output_ref_id=stable_id("output_ref", project.project_id, record.job_id, record.output_id),
            source_type="generated_output",
            project_id=project.project_id,
            job_id=record.job_id,
            asset_id=record.asset_id,
            candidate_id=record.candidate_id,
            output_id=record.output_id,
            preview_url=preview_url,
            thumbnail_url=thumbnail_url,
            download_url=download_url,
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
        renderable = bool(
            file_path
            and Path(file_path).is_file()
            and str(getattr(record, "preview_url", "") or "").strip()
            and str(getattr(record, "thumbnail_url", "") or "").strip()
            and str(getattr(record, "download_url", "") or "").strip()
        )

        if not renderable:
            return False
        # The output store owns canonical paths and immutable content
        # integrity. A persisted record's historical file_path/URLs are not
        # sufficient evidence for Project Mode recovery; when the store
        # exposes its resolver, require all three serving variants to pass it;
        # a store without the resolver is rejected below.
        output_store = getattr(getattr(self, "product_service", None), "output_store", None)
        file_for_variant = getattr(output_store, "file_for_variant", None)
        if not callable(file_for_variant):
            # A path and three URLs are only legacy metadata. Without the
            # output-store resolver there is no proof that the served variants
            # are canonical, current, and integrity-checked; recovery must
            # fail closed instead of trusting an adapter-shaped record.
            return False
        for variant in ("download", "preview", "thumbnail"):
            try:
                binding = file_for_variant(record.output_id, variant)
            except Exception:
                return False
            if (
                not isinstance(binding, tuple)
                or not binding
                or not Path(str(binding[0] or "")).is_file()
            ):
                return False
        return True

    @staticmethod
    def _canonical_output_urls(record: Any) -> tuple[str, str, str]:
        """Derive serving routes from the immutable output id, never metadata URLs."""

        output_id = str(getattr(record, "output_id", "") or "").strip()
        if not output_id:
            return "", "", ""
        from ..product_api.outputs import download_route, preview_route, thumbnail_route

        return preview_route(output_id), thumbnail_route(output_id), download_route(output_id)

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
        operation = {
            "operation_id": operation_id,
            "state": "planning_failed",
            "terminal": True,
            "pending": False,
            "next_actions": [{"id": "review_project_request"}],
        }
        failed_record = next(
            (
                record
                for record in reversed(records)
                if record.get("record_kind") == "failed"
                and record.get("project_id") == project.project_id
                and record.get("operation_id") == operation_id
            ),
            None,
        )
        if not isinstance(failed_record, dict):
            return operation
        record_job_id = str(failed_record.get("job_id") or "").strip()
        if not record_job_id or record_job_id not in project.job_ids:
            return operation
        record_failure_code = str(failed_record.get("failure_code") or "").strip()
        expected_identity = {
            "project_id": project.project_id,
            "operation_id": operation_id,
            "record_kind": "failed",
            "failure_code": record_failure_code or "planning_unavailable",
            "job_id": record_job_id,
        }
        if failed_record.get("identity_digest") != self._doc277_digest(expected_identity):
            return operation
        operation["job_id"] = record_job_id
        if record_failure_code:
            operation["failure_code"] = record_failure_code
        return operation

    def _doc277_planning_has_terminal_job_after(self, project: ProjectRecord) -> bool:
        """Detect a terminal Job created after a still-open planning operation."""

        pointer = dict(project.metadata or {}).get(_DOC277_CURRENT_OPERATION_KEY)
        if not isinstance(pointer, dict) or pointer.get("state") != "planning":
            return False
        operation_created_at = str(pointer.get("created_at") or "").strip()
        if not operation_created_at:
            return False
        try:
            operation_time = datetime.fromisoformat(operation_created_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        for job_id in reversed(project.job_ids):
            record = self.product_service.get_job_record(str(job_id or "").strip())
            if record is None:
                continue
            record_created_at = str(getattr(record, "created_at", "") or "").strip()
            try:
                record_time = datetime.fromisoformat(record_created_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if record_time < operation_time:
                continue
            try:
                status = self.product_service.get_job(record.job_id)
            except Exception:
                continue
            raw_status = getattr(status, "status", None)
            normalized = str(
                getattr(raw_status, "value", raw_status) or ""
            ).strip().lower()
            return normalized in {
                ProductJobStatusValue.BLOCKED.value,
                ProductJobStatusValue.FAILED.value,
            }
        return False

    def _doc277_terminal_job_operation(self, project: ProjectRecord) -> dict[str, Any] | None:
        """Project a generic no-delivery terminal state for a failed Job."""

        if not self._doc277_planning_has_terminal_job_after(project):
            return None
        for job_id in reversed(project.job_ids):
            status = self.product_service.get_job(str(job_id or "").strip())
            status_metadata = getattr(status, "metadata", None) if status is not None else None
            raw_operation = (
                status_metadata.get("current_operation")
                if isinstance(status_metadata, dict)
                else None
            )
            if isinstance(raw_operation, dict) and raw_operation.get("terminal") is True:
                return dict(raw_operation)
            return {
                "state": "failed_no_delivery",
                "terminal": True,
                "pending": False,
                "next_actions": [{"id": "continue"}],
            }
        return None

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

    def _project_response(
        self,
        project: ProjectRecord,
        *,
        owner_user_id: int | None = None,
        context_override: ProjectContextPackage | None = None,
    ) -> ProjectResponse:
        project_output_items = self._project_output_items(
            project,
            limit=60,
            owner_user_id=owner_user_id,
        )
        public_project = self._public_project_record(
            project,
            owner_user_id=owner_user_id,
            visible_output_items=project_output_items,
        )
        disclosures = self._doc281_used_source_disclosures(
            project,
            owner_user_id=owner_user_id,
        )
        if disclosures:
            public_project.metadata["doc281_used_source_disclosures"] = disclosures
        metadata = {
            **self._metadata(),
            "project_outputs": project_output_items,
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
        if operation is not None and operation.get("state") == "planning":
            if project.primary_template_id == ECOMMERCE_TEMPLATE_ID:
                terminal_job_operation = (
                    self._ecommerce_current_operation(project)
                    or self._doc277_terminal_job_operation(project)
                )
            else:
                terminal_job_operation = self._doc277_terminal_job_operation(project)
            if (
                terminal_job_operation is not None
                and terminal_job_operation.get("terminal") is True
                and self._doc277_planning_has_terminal_job_after(project)
            ):
                operation = terminal_job_operation
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
            context=self._public_project_context(context_override if context_override is not None else project.latest_context),
            metadata=metadata,
        )

    def _doc281_used_source_disclosures(
        self,
        project: ProjectRecord,
        *,
        owner_user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Project safe source labels for exact eligible Job/output bindings only."""

        delivered = self._project_output_items(
            project,
            limit=60,
            owner_user_id=owner_user_id,
        )
        output_by_id = {
            self._public_project_output_identity(item): item
            for item in delivered
            if self._public_project_output_identity(item)
        }
        # Review history is a separate visible surface. Only its established
        # withheld-review projection may receive a source label; a failed or
        # merely materialized output is never promoted by this disclosure.
        for item in self._project_output_items(
            project,
            limit=60,
            include_hidden=True,
            owner_user_id=owner_user_id,
        ):
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

    def _public_project_record(
        self,
        project: ProjectRecord,
        *,
        owner_user_id: int | None = None,
        visible_output_items: list[dict[str, Any]] | None = None,
    ) -> ProjectRecord:
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
        public_metadata = self._public_metadata_projection(project.metadata, public_metadata_keys)
        auto_anchor = self._doc73_auto_identity_anchor_public_projection(
            project,
            owner_user_id=owner_user_id,
        )
        if auto_anchor is not None:
            public_metadata["doc73_auto_identity_anchor"] = auto_anchor
        visible_aliases = self._visible_output_aliases(visible_output_items or [])
        public_selected_refs = [
            self._public_output_ref(ref)
            for ref in project.selected_output_refs
            if owner_user_id is None or self._output_ref_aliases(ref).intersection(visible_aliases)
        ]
        public_payload = project.model_dump(mode="json")
        public_payload.update(
            {
                "metadata": public_metadata,
                "selected_output_refs": [ref.model_dump(mode="json") for ref in public_selected_refs],
                "latest_context": self._public_project_context(project.latest_context).model_dump(mode="json") if project.latest_context else None,
            }
        )
        return ProjectRecord.model_validate(self._public_safe_projection(public_payload))

    @classmethod
    def _public_job_status(cls, status: ProductJobStatus) -> ProductJobStatus:
        """Project a Product status before embedding it in Project responses."""

        payload = cls._public_safe_projection(status.model_dump(mode="json"))
        return ProductJobStatus.model_validate(payload)

    @classmethod
    def public_job_status(cls, status: ProductJobStatus) -> ProductJobStatus:
        """Expose the safe Job projection to the HTTP route adapter."""

        return cls._public_job_status(status)

    @classmethod
    def _public_reference_asset(cls, reference: ProjectReferenceAsset) -> ProjectReferenceAsset:
        """Project a reference response without execution-only metadata."""

        payload = cls._public_safe_projection(reference.model_dump(mode="json"))
        return ProjectReferenceAsset.model_validate(payload)

    @classmethod
    def _public_feedback_record(cls, feedback: ProjectFeedbackRecord) -> ProjectFeedbackRecord:
        """Project a feedback response without execution-only metadata."""

        payload = cls._public_safe_projection(feedback.model_dump(mode="json"))
        return ProjectFeedbackRecord.model_validate(payload)

    @classmethod
    def _public_brand_memory_proposal(
        cls,
        proposal: ProjectBrandMemoryProposal,
    ) -> ProjectBrandMemoryProposal:
        """Project a Brand Memory response without execution-only metadata."""

        payload = cls._public_safe_projection(proposal.model_dump(mode="json"))
        return ProjectBrandMemoryProposal.model_validate(payload)

    def _public_project_for_nested_response(self, project: ProjectRecord) -> ProjectRecord:
        """Use the same safe project projection for every mutation response."""

        return self._public_project_record(
            project,
            visible_output_items=self._project_output_items(project, limit=60),
        )

    @staticmethod
    def _output_ref_aliases(ref: OutputRef) -> set[str]:
        return {
            str(getattr(ref, field, None) or "").strip()
            for field in ("output_id", "asset_id", "candidate_id", "output_ref_id")
            if str(getattr(ref, field, None) or "").strip()
        }

    @classmethod
    def _visible_output_aliases(cls, items: list[dict[str, Any]]) -> set[str]:
        aliases: set[str] = set()
        for item in items:
            for field in ("output_id", "asset_id", "candidate_id", "output_ref_id"):
                value = str(item.get(field) or "").strip()
                if value:
                    aliases.add(value)
        return aliases

    @staticmethod
    def _public_safe_projection(value: Any) -> Any:
        """Remove execution-only data from nested public dictionaries."""
        private_keys = {
            "final_provider_prompt", "compiled_visual_direction", "optimized_direction",
            "provider_prompt", "provider_negative_prompt", "provider_prompt_rules",
            "provider_negative_rules", "llm_brain", "file_path", "source_integrity_id",
            "canonical_output_binding", "v3_owned_output", "retry_patch", "retry_patches",
            "prompt_additions", "negative_additions", "reasoning", "provider_payload", "provider_request",
        }
        if isinstance(value, dict):
            return {
                key: V3ProjectModeService._public_safe_projection(item)
                for key, item in value.items()
                if str(key).strip().lower() not in private_keys
            }
        if isinstance(value, (list, tuple)):
            return [V3ProjectModeService._public_safe_projection(item) for item in value]
        return value

    @classmethod
    def _public_metadata_projection(
        cls, metadata: dict[str, Any] | None, allowed_keys: set[str]
    ) -> dict[str, Any]:
        return cls._public_safe_projection(
            {key: value for key, value in dict(metadata or {}).items() if key in allowed_keys}
        )

    @classmethod
    def _public_project_context(cls, context: ProjectContextPackage | None) -> ProjectContextPackage | None:
        if context is None:
            return None
        public_metadata_keys = {
            "source", "positive_context_from_selected_outputs_only", "unselected_candidates_excluded",
            "active_reference_count", "active_uploaded_reference_count", "active_generated_reference_count",
            "suppressed_generated_reference_count", "active_negative_feedback_count", "template_id",
            "reference_resolution_audit", "general_forced_reference_count", "variation_mode",
            "effective_variation_mode", "inferred_variation_mode", "variation_mode_source",
            "requested_image_count", "requested_image_size", "visual_continuity_strength",
            "visual_snapshot_id", "strong_reference_binding_count", "identity_lock_count",
            "project_identity_anchor_count", "strong_reference_continuation_plan_id",
            "reference_policy_package_id", "doc93_reference_channel_policy", "general_suite_role_plan_id",
            "batch_identity_diversity_review_id", "template_consistency_policy",
            "doc73_auto_identity_anchor_state", "commerce_profile", "product_reference_required",
        }
        payload = context.model_dump(mode="json")
        payload["metadata"] = cls._public_metadata_projection(context.metadata, public_metadata_keys)
        payload["selected_output_assets"] = [
            cls._public_output_ref(ref).model_dump(mode="json")
            for ref in context.selected_output_assets
        ]
        return ProjectContextPackage.model_validate(cls._public_safe_projection(payload))

    @classmethod
    def _public_output_ref(cls, ref: OutputRef) -> OutputRef:
        return ref.model_copy(
            update={
                "metadata": cls._public_metadata_projection(
                    ref.metadata,
                    {
                        "recommendation", "restored_from_reference_id", "restored_from_output_store",
                        "delivery_state", "output_store_restore_state", "review_only", "recovery_required",
                    },
                )
            },
            deep=True,
        )

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


def _infer_general_variation_mode(
    user_input: str | None,
    *,
    requested_count: object | None = None,
    has_reference: bool = False,
    selected_size: object | None = None,
) -> str:
    """Keep legacy Project Mode callers on the shared inference authority."""

    return infer_general_variation_mode(
        user_input,
        requested_count=requested_count,
        has_reference=has_reference,
        selected_size=selected_size,
    )


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
