"""Project Mode service wrapping the existing V3 Product API."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
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
from ..schemas import BrandProfile, ReferenceAsset
from ..shared_capabilities.activation import CapabilityActivationPlan, CapabilityPlanAmendment
from ..shared_capabilities.visual_cluster.reference_channel_policy import ReferenceChannelPolicyModule
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
from .templates import ProjectTemplateManifest, ProjectTemplateRegistry


ECOMMERCE_PRODUCT_UPLOAD_ROLES = {"product_reference", "subject_reference"}
PROJECT_PRODUCT_REFERENCE_ROLES = {"product", *ECOMMERCE_PRODUCT_UPLOAD_ROLES}


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


class V3ProjectModeService:
    """V3-owned project layer that delegates job execution to Product API."""

    def __init__(
        self,
        product_service: V3ProductApiService | None = None,
        project_store: InMemoryProjectStore | None = None,
        template_registry: ProjectTemplateRegistry | None = None,
        reference_channel_policy_module: ReferenceChannelPolicyModule | None = None,
    ) -> None:
        self.product_service = product_service or V3ProductApiService()
        self.project_store = project_store or InMemoryProjectStore()
        scenario_registry = getattr(getattr(self.product_service, "scenario_runtime", None), "scenario_registry", None)
        self.template_registry = template_registry or ProjectTemplateRegistry(scenario_registry=scenario_registry)
        self.reference_channel_policy_module = reference_channel_policy_module or ReferenceChannelPolicyModule()

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
            if project.status != ProjectStatus.ARCHIVED and self._project_visible_to_owner(project, owner_user_id):
                self._reconcile_project_outputs(project)
                items = self._project_output_items(
                    project,
                    limit=bounded_limit,
                    owner_user_id=owner_user_id,
                    compact=compact,
                )
            items = sorted(items, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:bounded_limit]
            return {
                "api_namespace": API_NAMESPACE,
                "route": f"{API_NAMESPACE}/project-outputs",
                "project_id": project_id,
                "total": len(items),
                "limit": bounded_limit,
                "items": items,
                "metadata": {**self._metadata(), "compact": bool(compact), "project_scoped": True},
            }
        project_scan_limit = max(12, min(100, bounded_limit * 2))
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
        items = sorted(items, key=lambda item: str(item.get("created_at") or ""), reverse=True)[:bounded_limit]
        return {
            "api_namespace": API_NAMESPACE,
            "route": f"{API_NAMESPACE}/project-outputs",
            "total": len(items),
            "limit": bounded_limit,
            "items": items,
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
                **create_request.metadata,
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
        project.latest_context = self._build_context(project)
        project.memory_summary = self._memory_summary(project)
        self.project_store.save_project(project)
        return self._project_response(project)

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
        template_manifest = self._ensure_active_template(job_request.template_id)
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
        uploaded_asset_ids = list(dict.fromkeys([*self._project_asset_ids(project), *job_request.uploaded_asset_ids]))
        ecommerce_text_to_image_fallback = False
        if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID:
            uploaded_asset_ids = self._ecommerce_product_reference_asset_ids(project, job_request.uploaded_asset_ids)
            ecommerce_text_to_image_fallback = not uploaded_asset_ids
            commerce_profile = self._merge_commerce_profile(project, job_request)
        else:
            commerce_profile = None
        if template_manifest.template_id not in project.allowed_template_ids:
            project.allowed_template_ids.append(template_manifest.template_id)
        project.primary_template_id = template_manifest.template_id
        user_input = job_request.user_input or project.user_goal
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
            },
        }
        status = (
            self.product_service.create_trusted_photography_continuation_job(create_payload)
            if _trusted_photography_continuation
            else self.product_service.create_trusted_capability_continuation_job(create_payload)
            if _trusted_capability_continuation
            else self.product_service.create_job(create_payload)
        )
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
                "photographer_profile_binding": (
                    photographer_profile_binding.model_dump(mode="json") if photographer_profile_binding is not None else None
                ),
            }
        )
        self._link_job(project, status.job_id, context)
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
            self._append_timeline(
                project.project_id,
                TimelineItemType.JOB_GENERATED,
                "生成了一组电商套图" if template_id == ECOMMERCE_TEMPLATE_ID else "生成了一组创意图",
                "套图已生成，请先检查商品细节和卖点是否准确。" if template_id == ECOMMERCE_TEMPLATE_ID else "图片已生成，可以选中喜欢的结果作为后续风格参考。",
                job_id=job_id,
                asset_ids=[asset.asset_id for asset in status.asset_series],
                candidate_ids=[candidate.candidate_id for candidate in status.candidates],
                metadata={"template_id": template_id, "scenario_pack_id": status.scenario.scenario_id if status.scenario else None},
            )
            review_package = status.metadata.get("post_generation_review") if isinstance(status.metadata, dict) else None
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
            specialized_execution = (
                status.metadata.get("specialized_execution_summary")
                if isinstance(status.metadata, dict)
                else None
            )
            incomplete_specialized_set = (
                isinstance(specialized_execution, dict)
                and str(specialized_execution.get("status") or "").lower() == "incomplete"
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
                "摄影专业套图未完整生成" if incomplete_specialized_set else "本次没有生成图片",
                (
                    self._incomplete_specialized_set_summary(specialized_execution)
                    if incomplete_specialized_set
                    else self._blocked_generation_summary(status)
                ),
                job_id=job_id,
                metadata={
                    "template_id": template_id,
                    "status": str(status.status),
                    "warnings": list(status.warnings or [])[:3],
                    "provider_failure_retry": provider_retry if isinstance(provider_retry, dict) else {},
                    "specialized_execution_summary": specialized_execution if incomplete_specialized_set else {},
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
    ) -> ProductJobStatus:
        """Mark a queued project job before the web layer releases its worker."""

        project = self._require_project(project_id)
        self._ensure_project_job(project, job_id)
        return self.product_service.mark_job_generating(
            job_id,
            background_attempt_id=background_attempt_id,
            background_timeout_seconds=background_timeout_seconds,
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
        if correction_note:
            recipe["prompt_pressure"] = (
                f"{str(recipe.get('prompt_pressure') or '').strip()} User correction: {correction_note}"
            ).strip()
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
                "prompt_additions": [f"Photography role {role_id}: {recipe.get('prompt_pressure') or ''}".strip()],
                "negative_additions": list(recipe.get("negative_pressure") or []),
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
            str(intent.get("slot_id") or "").strip()
            for intent in output_intents
            if isinstance(intent, dict) and str(intent.get("slot_id") or "").strip()
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

    def _ecommerce_product_reference_asset_ids(
        self,
        project: ProjectRecord,
        request_asset_ids: list[str],
    ) -> list[str]:
        product_asset_ids: list[str] = []
        invalid_request_ids: list[str] = []

        for asset_id in request_asset_ids:
            clean_id = str(asset_id or "").strip()
            if not clean_id:
                continue
            if self._is_ready_product_upload(clean_id):
                product_asset_ids.append(clean_id)
            else:
                invalid_request_ids.append(clean_id)

        for asset_id in self._project_product_reference_candidates(project):
            if self._is_ready_product_upload(asset_id):
                product_asset_ids.append(asset_id)

        if invalid_request_ids:
            raise ValueError("商品图还没有上传完成或不是有效的商品参考图，请重新上传商品图。")
        return list(dict.fromkeys(product_asset_ids))

    def _project_product_reference_candidates(self, project: ProjectRecord) -> list[str]:
        candidate_ids = [
            reference.asset_ref_id
            for reference in project.reference_assets
            if reference.status == ProjectReferenceStatus.ACTIVE
            and reference.source_type == ProjectReferenceSourceType.UPLOADED
            and reference.use_policy == ProjectReferenceUsePolicy.PRODUCT
        ]
        legacy_ids = [
            str(item.get("asset_id") or "").strip()
            for item in project.uploaded_asset_refs
            if str(item.get("role") or "").strip() in PROJECT_PRODUCT_REFERENCE_ROLES
        ]
        return [asset_id for asset_id in dict.fromkeys([*candidate_ids, *legacy_ids]) if asset_id]

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
            preset_id = str(
                request.metadata.get("selected_preset_id")
                or request.metadata.get("preset_id")
                or "one_click_product_set"
            )
            mode_id = str(request.metadata.get("selected_mode_id") or request.metadata.get("mode_id") or preset_id)
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
                "mode_id": mode_id,
                "preset_id": preset_id,
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
        return {
            "scenario_id": manifest.scenario_pack_id,
            "mode_id": "campaign_poster",
            "preset_id": "campaign_poster",
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
        status = self.product_service.get_job(job_id)
        template_id = status.metadata.get("template_id") if status and status.metadata else None
        if template_id:
            return str(template_id)
        for item in reversed(self.project_store.list_timeline(project.project_id)):
            if item.job_id == job_id and item.metadata.get("template_id"):
                return str(item.metadata["template_id"])
        return project.primary_template_id or GENERAL_TEMPLATE_ID

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

    def _link_job(self, project: ProjectRecord, job_id: str, context: ProjectContextPackage) -> None:
        if job_id not in project.job_ids:
            project.job_ids.append(job_id)
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
                if not any(
                    item.item_type == TimelineItemType.NOTE_ADDED
                    and (item.job_id == job_id or item.related_job_id == job_id)
                    and isinstance(item.metadata, dict)
                    and item.metadata.get("execution_diagnostic") == "specialized_role_coverage_incomplete"
                    for item in timeline
                ):
                    self._append_timeline(
                        project.project_id,
                        TimelineItemType.NOTE_ADDED,
                        "专业套图存在未完成角色",
                        self._incomplete_specialized_set_summary(incomplete_execution),
                        job_id=job_id,
                        metadata={
                            "execution_diagnostic": "specialized_role_coverage_incomplete",
                            "specialized_execution_summary": incomplete_execution,
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
        if isinstance(execution, dict) and str(execution.get("status") or "").lower() == "incomplete":
            return dict(execution)
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
            **dict(execution),
            "status": "incomplete",
            "missing_role_keys": missing,
            "final_delivery_withheld": True,
            "append_only_history_preserved": True,
        }

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
                "candidate_id": ref.candidate_id,
                "asset_id": ref.asset_id,
                "canonical_output_binding": bool(ref.metadata.get("canonical_output_binding")),
                "source_integrity_id": ref.metadata.get("source_integrity_id"),
            },
        )

    def _ensure_legacy_uploaded_ref(self, project: ProjectRecord, reference: ProjectReferenceAsset) -> None:
        existing_ids = {str(item.get("asset_id")) for item in project.uploaded_asset_refs if item.get("asset_id")}
        if reference.asset_ref_id not in existing_ids:
            project.uploaded_asset_refs.append(
                {
                    "asset_id": reference.asset_ref_id,
                    "source": "project_reference",
                    "role": reference.use_policy.value,
                    "reference_id": reference.reference_id,
                }
            )

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
            active_template_label=self._template_label(project.primary_template_id),
            latest_thumbnail_urls=latest_thumbnails,
            confirmed_style_chips=self._style_chips(project),
            selected_asset_count=len(selected_refs),
            job_count=len(project.job_ids),
            last_action_label=last_action,
            updated_at=project.updated_at,
            next_suggested_actions=self._next_actions(project),
        )

    def _latest_generated_thumbnail_urls(self, project: ProjectRecord, limit: int = 3) -> list[str]:
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
            has_final_delivery = any(
                item.get("delivery_state") == "final_delivery"
                for item in delivery.values()
            )
            for record in sorted(records, key=lambda item: item.created_at or "", reverse=True):
                delivery_state = delivery.get(self._output_record_identity(record), {}).get("delivery_state")
                if delivery_state == "superseded" or (has_final_delivery and delivery_state != "final_delivery"):
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
            if not self._project_job_delivery_is_settled(job_id):
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
                if not include_hidden and str(delivery_entry.get("delivery_state") or "final_delivery") != "final_delivery":
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
                    )
                )
                if len(items) >= max(1, int(limit or 60)):
                    return items
        return items[: max(1, int(limit or 60))]

    def _project_job_delivery_is_settled(self, job_id: str) -> bool:
        """Known in-flight jobs must not leak process outputs onto project boards."""

        job_status = self.product_service.get_job(job_id)
        if job_status.status in {ProductJobStatusValue.GENERATING, ProductJobStatusValue.FINALIZING}:
            return False
        execution = dict(job_status.metadata or {}).get("specialized_execution_summary")
        # A multi-role template can preserve generated pixels in append-only
        # history while still withholding them from the ordinary project
        # result panel until every frozen role has a final winner.
        return not (
            isinstance(execution, dict)
            and str(execution.get("status") or "").lower() == "incomplete"
            and bool(execution.get("final_delivery_withheld"))
        )

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
    ) -> dict[str, Any]:
        record_metadata = dict(record.metadata or {})
        state_value = (state.value if hasattr(state, "value") else str(state)) if state else "available"
        delivery_metadata = dict(delivery or {})
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
        file_path = Path(str(getattr(record, "file_path", "") or ""))
        digest = self._file_content_fingerprint(file_path)
        return f"sha256:{digest}" if digest else f"output:{record.output_id}"

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

    def _project_response(self, project: ProjectRecord) -> ProjectResponse:
        return ProjectResponse(
            api_namespace=API_NAMESPACE,
            route=f"{API_NAMESPACE}/projects/{project.project_id}",
            project=project,
            templates=self.template_cards(),
            context=project.latest_context,
            metadata={
                **self._metadata(),
                "project_outputs": self._project_output_items(project, limit=60),
            },
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
