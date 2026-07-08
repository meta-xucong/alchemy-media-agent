"""Project Mode service wrapping the existing V3 Product API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..app_shell.routes import API_NAMESPACE
from ..creative_core.prompt_language import looks_like_human_structured_appearance_context
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
from ..schemas import BrandProfile, ReferenceAsset
from .contracts import (
    ECOMMERCE_TEMPLATE_ID,
    GENERAL_TEMPLATE_ID,
    CreateProjectJobRequest,
    CreateProjectRequest,
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
    TemplateCard,
    TimelineItemType,
)
from .store import InMemoryProjectStore
from .templates import ProjectTemplateManifest, ProjectTemplateRegistry


ECOMMERCE_PRODUCT_UPLOAD_ROLES = {"product_reference", "subject_reference"}
PROJECT_PRODUCT_REFERENCE_ROLES = {"product", *ECOMMERCE_PRODUCT_UPLOAD_ROLES}


class V3ProjectModeService:
    """V3-owned project layer that delegates job execution to Product API."""

    def __init__(
        self,
        product_service: V3ProductApiService | None = None,
        project_store: InMemoryProjectStore | None = None,
        template_registry: ProjectTemplateRegistry | None = None,
    ) -> None:
        self.product_service = product_service or V3ProductApiService()
        self.project_store = project_store or InMemoryProjectStore()
        scenario_registry = getattr(getattr(self.product_service, "scenario_runtime", None), "scenario_registry", None)
        self.template_registry = template_registry or ProjectTemplateRegistry(scenario_registry=scenario_registry)

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
            "项目已准备好，可以上传商品图生成第一组电商套图。" if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID else "项目已准备好，可以使用通用模板生成第一组创意图。",
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

    def create_project_job(self, project_id: str, request: CreateProjectJobRequest | dict[str, Any]) -> ProductJobStatus:
        project = self._require_project(project_id)
        job_request = self._coerce_create_project_job_request(request)
        template_manifest = self._ensure_active_template(job_request.template_id)
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
        )
        product_profile = self._product_profile_for_template(
            project,
            context_snapshot,
            job_request,
            template_manifest,
            commerce_profile=commerce_profile,
        )
        project_job_sequence = len(project.job_ids) + 1
        create_payload = {
            "user_input": user_input,
            "brand_id": project.linked_brand_id,
            "scenario_selection": scenario_selection,
            "uploaded_asset_ids": uploaded_asset_ids,
            "product_profile": product_profile,
            "metadata": {
                **job_request.metadata,
                "project_id": project.project_id,
                "template_id": template_manifest.template_id,
                "template_manifest_id": template_manifest.template_id,
                "project_job_sequence": project_job_sequence,
                "scenario_pack_id": template_manifest.scenario_pack_id,
                "scenario_parameters": scenario_selection.get("parameters") or {},
                "selected_mode_id": scenario_selection.get("mode_id"),
                "selected_preset_id": scenario_selection.get("preset_id"),
                "project_context_version": context.context_version,
                "project_context_snapshot": context_snapshot,
                "project_mode": True,
                "apply_brand_memory_update_default": False,
                "commerce_profile_present": commerce_profile is not None,
                "ecommerce_text_to_image_fallback": ecommerce_text_to_image_fallback,
                "has_product_reference": bool(uploaded_asset_ids) if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID else None,
            },
        }
        status = self.product_service.create_job(create_payload)
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
                "project_context_snapshot": context_snapshot,
                "project_mode": True,
                "commerce_profile_present": commerce_profile is not None,
                "ecommerce_text_to_image_fallback": ecommerce_text_to_image_fallback,
                "has_product_reference": bool(uploaded_asset_ids) if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID else None,
            }
        )
        self._link_job(project, status.job_id, context)
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
                "commerce_profile_present": commerce_profile is not None,
                "ecommerce_text_to_image_fallback": ecommerce_text_to_image_fallback,
                "has_product_reference": bool(uploaded_asset_ids) if template_manifest.template_id == ECOMMERCE_TEMPLATE_ID else None,
            },
        )
        return status

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
                "本次没有生成图片",
                self._blocked_generation_summary(status),
                job_id=job_id,
                metadata={
                    "template_id": template_id,
                    "status": str(status.status),
                    "warnings": list(status.warnings or [])[:3],
                    "provider_failure_retry": provider_retry if isinstance(provider_retry, dict) else {},
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
        selected = self.product_service.select_result(job_id, payload)
        if selected.status == ProductJobStatusValue.NOT_FOUND:
            restored_status = self.product_service.get_job(job_id)
            if restored_status.status == ProductJobStatusValue.GENERATED:
                selected = self._selection_from_restored_status(restored_status, payload)
        refs = self._output_refs_from_selection(project, selected)
        if not refs:
            raise ValueError("No generated project image was available to select")
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
            "suite_slots_requested",
        ]
        for field in scalar_fields:
            value = patch_data.get(field)
            if value is not None:
                data[field] = value
        for field in list_fields:
            values = patch_data.get(field)
            if values:
                data[field] = self._dedupe_text(values)
        if request.suite_slot_request:
            data["suite_slots_requested"] = self._dedupe_text(request.suite_slot_request)
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
            parameters: dict[str, Any] = {
                "project_context_version": context.context_version,
                "use_project_context": request.use_project_context,
                "project_mode": True,
                "suite_slot_request": list(request.suite_slot_request),
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
            return {
                "scenario_id": manifest.scenario_pack_id,
                "mode_id": mode_id,
                "preset_id": preset_id,
                "platform_profile": platform or "generic",
                "parameters": parameters,
            }
        variation_contract = self._general_variation_contract(request.metadata)
        parameters = {
            "project_context_version": context.context_version,
            "use_project_context": request.use_project_context,
        }
        parameters.update(variation_contract)
        requested_count = _bounded_requested_image_count(request.metadata.get("requested_image_count"))
        if requested_count is not None:
            parameters["requested_image_count"] = requested_count
        requested_size = str(request.metadata.get("requested_image_size") or "").strip()
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
    ) -> dict[str, Any]:
        base = {
            "brand_or_project_name": project.title,
            "project_goal": project.user_goal,
            "project_context": context_snapshot,
        }
        if manifest.template_id == GENERAL_TEMPLATE_ID:
            base.update(self._general_variation_contract(request.metadata))
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
            "suite_slots_requested": list(profile.suite_slots_requested or request.suite_slot_request),
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

    def _job_created_title(self, manifest: ProjectTemplateManifest) -> str:
        if manifest.template_id == ECOMMERCE_TEMPLATE_ID:
            return "电商套图任务已创建"
        return "生成任务已创建"

    def _job_created_summary(self, manifest: ProjectTemplateManifest) -> str:
        if manifest.template_id == ECOMMERCE_TEMPLATE_ID:
            return "电商模板已开始整理商品信息、卖点和套图位置。"
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
            try:
                records = list(output_store.list_by_job(job_id))
            except Exception:
                continue
            if not records:
                continue
            records = sorted(records, key=lambda item: item.created_at or "")
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

    def _looks_like_structured_appearance_project(self, project: ProjectRecord) -> bool:
        text = " ".join(
            str(item or "")
            for item in [
                project.user_goal,
                project.short_summary,
                project.confirmed_style_summary,
                *getattr(project, "confirmed_style_tags", []),
            ]
        )
        return looks_like_human_structured_appearance_context(text)

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
            return ["face_identity", "hair", "wardrobe", "camera_distance", "lighting_language"]
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
        selected_refs = [
            ref
            for ref in project.selected_output_refs
            if state_map.get(self._output_identity(ref), ProjectOutputSelectionStateValue.SELECTED)
            == ProjectOutputSelectionStateValue.SELECTED
        ]
        selected_refs = [self._enrich_selected_output_ref(ref) for ref in selected_refs]
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
        active_generated_references = [
            self._reference_context_dict(reference)
            for reference in active_references
            if reference.source_type == ProjectReferenceSourceType.GENERATED_SELECTED
        ]
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
            "active_negative_feedback_count": len(active_avoid_notes),
            "template_id": effective_template_id,
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
        identity_lock_profiles = self._project_identity_lock_profiles(
            project=project,
            template_policy=template_policy,
            strong_reference_bindings=strong_reference_bindings,
            visual_snapshot=visual_snapshot,
        )
        project_identity_anchors = self._project_identity_anchors(
            project=project,
            template_policy=template_policy,
            selected_refs=selected_refs,
            strong_reference_bindings=strong_reference_bindings,
            identity_lock_profiles=identity_lock_profiles,
        )
        strong_reference_continuation_plan = self._project_strong_reference_continuation_plan(
            project=project,
            anchors=project_identity_anchors,
            strong_reference_bindings=strong_reference_bindings,
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
                "preview_url": ref.preview_url,
                "thumbnail_url": ref.thumbnail_url,
                "download_url": ref.download_url,
                "selection_reason": ref.selection_reason,
                "use_policy": selected_policy.value,
                "role": self._reference_role_for_policy(selected_policy),
                "strength": "hard" if selected_policy in {
                    ProjectReferenceUsePolicy.IDENTITY,
                    ProjectReferenceUsePolicy.PRODUCT_IDENTITY,
                    ProjectReferenceUsePolicy.BRAND_ASSET,
                } else "medium",
                "lock_targets": self._lock_targets_for_policy(selected_policy),
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
                "policy_id": "ecommerce_product_truth",
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
                    "file_path": file_path or None,
                    "preview_url": item.get("preview_url") or item.get("thumbnail_url") or item.get("uri"),
                    "role": item.get("role") or self._reference_role_for_policy(use_policy),
                    "strength": strength,
                    "use_policy": use_policy.value,
                    "lock_targets": item.get("lock_targets") or self._lock_targets_for_policy(use_policy),
                    "provider_input_required": bool(file_path and strength == "hard"),
                    "prompt_only_fallback": not bool(file_path),
                    "user_visible_label": self._reference_user_label(use_policy),
                    "metadata": {
                        "selected_project_anchor": item.get("source_type") == "selected_output",
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
    ) -> list[dict[str, Any]]:
        if not strong_reference_bindings:
            return []
        subject_type = str(template_policy.get("identity_lock_default") or "generic")
        structured_appearance = self._looks_like_structured_appearance_project(project)
        if subject_type == "character":
            keep_rules = [
                "keep the selected person's recognizable vibe",
                "keep hair, outfit direction, camera distance, and lighting coherent",
            ]
            avoid_rules = ["face drift", "random hairstyle change", "outfit direction drift"]
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
                    *[str(item) for item in visual_snapshot.get("style_rules", [])[:4]],
                ],
                "negative_constraints": [
                    *avoid_rules,
                    *[str(item) for item in visual_snapshot.get("negative_directions", [])[:4]],
                ],
                "user_visible_summary": self._identity_lock_user_summary(subject_type),
                "metadata": {"template_policy": template_policy, "structured_appearance_lock": structured_appearance},
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
                "style_keep_rules": list(self._style_chips(project))[:6],
                "allowed_variations": self._anchor_allowed_variations(subject_type),
                "forbidden_drift": self._anchor_forbidden_drift(subject_type),
                "provider_reference_required": provider_required,
                "prompt_only_fallback": not provider_required,
                "user_visible_summary": [
                    "Selected image will guide the next generation.",
                    "V3 keeps the important identity/style details while allowing useful variation.",
                ],
                "metadata": {"doc": "58", "template_policy": template_policy.get("policy_id")},
            }
        ]

    def _project_strong_reference_continuation_plan(
        self,
        *,
        project: ProjectRecord,
        anchors: list[dict[str, Any]],
        strong_reference_bindings: list[dict[str, Any]],
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
        prompt_additions = self._dedupe_text(
            [
                "use active project reference images as the strongest positive references",
                "preserve uploaded prototype identity/product details before extending selected generated style",
                *(
                    [
                        "when styling defines the project, preserve the same appearance asset structure: silhouette, layer order, collar or neckline direction, sleeve or cuff shape, closure or sash logic, material behavior, pattern family, trim placement, and accessory placement"
                    ]
                    if self._looks_like_structured_appearance_project(project)
                    else []
                ),
                *[rule for anchor in anchors for rule in anchor.get("identity_keep_rules", [])],
                *[rule for anchor in anchors for rule in anchor.get("style_keep_rules", [])],
            ]
        )[:12]
        negative_additions = self._dedupe_text(
            [
                "do not use unselected candidates as positive references",
                *(
                    [
                        "do not redesign the appearance asset",
                        "do not change garment structure or layer logic",
                        "do not replace pattern family, trim placement, or accessory placement without a user request",
                    ]
                    if self._looks_like_structured_appearance_project(project)
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
            "metadata": {"doc": "58", "strong_binding_count": len(strong_reference_bindings)},
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
        requested_count = max(1, min(4, requested_count))
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
            return ["Keeps the selected person's vibe, hair, outfit direction, camera, and lighting"]
        if subject_type == "product":
            return ["Keeps product shape, material, color, proportions, and label position"]
        return ["Keeps the selected style, composition, palette, and lighting"]

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
            parts.append("uses selected project images as the current style anchor")
        return self._short_text(" | ".join(part for part in parts if part), 160)

    def _dedupe_visual_reference_payloads(self, references: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in references:
            identity = str(
                item.get("output_id")
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
        final_ids = {self._output_record_identity(record) for record in final_records}
        annotations: dict[str, dict[str, Any]] = {}
        for attempt, group in attempt_groups.items():
            retry_codes = self._delivery_retry_reason_codes(group)
            for record in group:
                identity = self._output_record_identity(record)
                if not identity:
                    continue
                delivery_state = "final_delivery" if identity in final_ids else "process_only"
                if attempt < final_attempt and final_ids:
                    delivery_state = "superseded"
                annotations[identity] = {
                    "delivery_state": delivery_state,
                    "delivery_attempt_index": attempt,
                    "delivery_final_attempt_index": final_attempt,
                    "delivery_requested_image_count": requested_count,
                    "delivery_group_output_count": len(group),
                    "retry_superseded": delivery_state == "superseded",
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
                        delivery=delivery.get(identity),
                    )
                )
                if len(items) >= max(1, int(limit or 60)):
                    return items
        return items[: max(1, int(limit or 60))]

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
        return chips[:5] or ["通用创意"]

    def _template_label(self, template_id: str | None) -> str:
        if template_id == ECOMMERCE_TEMPLATE_ID:
            return "电商模板"
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

    def _output_refs_from_selection(self, project: ProjectRecord, selected: SelectionResponse) -> list[OutputRef]:
        status = selected.job_status
        selected_candidate_ids = set(selected.selected_result.selected_candidate_ids)
        selected_asset_ids = set(selected.selected_result.selected_asset_ids)
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
        if refs:
            return refs
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
        return refs

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
        return max(1, min(4, int(value)))
    except (TypeError, ValueError):
        return None
