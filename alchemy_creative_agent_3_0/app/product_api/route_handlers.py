"""Thin framework-neutral route handler facade for V3 API adapters."""

from __future__ import annotations

from typing import Any

from ..app_shell import get_scenario_hub_contract
from ..project_mode import InMemoryProjectStore, ProjectTemplateRegistry, V3ProjectModeService
from ..visual_assets import (
    AnchorPackPreparationHost,
    LibraryVisualAssetCreateRequest,
    PeopleAssetActivationRequest,
    PeopleAssetCreateRequest,
    PeopleAssetLifecycleService,
    PeopleAssetPrepareRequest,
    ProjectVisualAssetBindingRequest,
    ProjectVisualAssetBindingService,
    VisualAssetLibraryCatalog,
    VisualAssetLibraryLifecycleService,
)
from .service import V3ProductApiService


class V3ProductRouteHandlers:
    """Method names mirror the reserved V3 route contract."""

    def __init__(
        self,
        service: V3ProductApiService | None = None,
        project_store: InMemoryProjectStore | None = None,
        template_registry: ProjectTemplateRegistry | None = None,
        anchor_pack_preparation_host: AnchorPackPreparationHost | None = None,
        visual_asset_library_catalog: VisualAssetLibraryCatalog | None = None,
        project_visual_asset_binding_service: ProjectVisualAssetBindingService | None = None,
        visual_asset_owner_scope: str = "local_default",
    ) -> None:
        self.service = service or V3ProductApiService()
        self.project_service = V3ProjectModeService(
            product_service=self.service,
            project_store=project_store,
            template_registry=template_registry,
        )
        self.people_asset_service = PeopleAssetLifecycleService(
            self.service.visual_asset_catalog,
            root_source_resolver=self.service.asset_store.get_upload,
            anchor_pack_host=anchor_pack_preparation_host,
        )
        self.visual_asset_owner_scope = visual_asset_owner_scope.strip() or "local_default"
        self.visual_asset_library_catalog = visual_asset_library_catalog or VisualAssetLibraryCatalog()
        self.visual_asset_library_service = VisualAssetLibraryLifecycleService(
            self.visual_asset_library_catalog,
            root_source_resolver=self.service.asset_store.get_upload,
            anchor_pack_host=anchor_pack_preparation_host,
        )
        self.project_visual_asset_binding_service = (
            project_visual_asset_binding_service
            or ProjectVisualAssetBindingService(self.visual_asset_library_catalog)
        )

    def post_jobs(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.service.create_job(payload).model_dump(mode="json")

    def post_creative_jobs(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post_jobs(payload)

    def post_uploads(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.service.create_uploaded_asset(payload).model_dump(mode="json")

    def put_upload_content(self, asset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = self.service.store_uploaded_asset_content(asset_id, payload)
        if record is None:
            raise KeyError("uploaded asset not found")
        return record.model_dump(mode="json")

    def post_upload_complete(self, asset_id: str) -> dict[str, Any]:
        record = self.service.complete_uploaded_asset(asset_id)
        if record is None:
            raise KeyError("uploaded asset not found")
        return record.model_dump(mode="json")

    def get_upload(self, asset_id: str) -> dict[str, Any]:
        record = self.service.get_uploaded_asset(asset_id)
        if record is None:
            raise KeyError("uploaded asset not found")
        return record.model_dump(mode="json")

    def get_scenarios(self) -> dict[str, Any]:
        return get_scenario_hub_contract()

    def get_photographer_profiles(self) -> dict[str, Any]:
        return self.service.get_photographer_profiles()

    def get_history(self, limit: int = 20) -> dict[str, Any]:
        return self.service.list_history(limit=limit).model_dump(mode="json")

    def get_projects(self, limit: int = 20, owner_user_id: int | None = None) -> dict[str, Any]:
        return self.project_service.list_projects(limit=limit, owner_user_id=owner_user_id).model_dump(mode="json")

    def get_project_outputs(
        self,
        limit: int = 60,
        owner_user_id: int | None = None,
        compact: bool = False,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        return self.project_service.list_project_outputs(
            limit=limit,
            owner_user_id=owner_user_id,
            compact=compact,
            project_id=project_id,
        )

    def post_projects(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.create_project(payload).model_dump(mode="json")

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self.project_service.get_project(project_id).model_dump(mode="json")

    def post_project_archive(self, project_id: str) -> dict[str, Any]:
        return self.project_service.archive_project(project_id).model_dump(mode="json")

    def delete_project(self, project_id: str) -> dict[str, Any]:
        return self.project_service.delete_project(project_id)

    def get_project_timeline(self, project_id: str) -> dict[str, Any]:
        return self.project_service.list_timeline(project_id).model_dump(mode="json")

    def get_project_context(self, project_id: str) -> dict[str, Any]:
        return self.project_service.get_project_context(project_id).model_dump(mode="json")

    # Doc173 library-first public surface.  These methods deliberately do not
    # call the historical project-scoped People Asset lifecycle above.  Legacy
    # routes stay available for read/recovery only while new assets are owned
    # by the user/workspace library and projects only hold explicit bindings.
    def get_visual_assets(self, owner_scope: str | None = None) -> dict[str, Any]:
        resolved_owner_scope = self._visual_asset_owner_scope(owner_scope)
        return {
            "visual_assets": [
                self._visual_asset_public_record(item)
                for item in self.visual_asset_library_service.list(owner_scope=resolved_owner_scope)
            ]
        }

    def post_visual_assets(self, payload: dict[str, Any], owner_scope: str | None = None) -> dict[str, Any]:
        request = LibraryVisualAssetCreateRequest.model_validate(payload)
        asset = self.visual_asset_library_service.create_draft(
            owner_scope=self._visual_asset_owner_scope(owner_scope),
            request=request,
        )
        return {"visual_asset": self._visual_asset_public_record(asset)}

    def get_visual_asset(self, visual_asset_id: str, owner_scope: str | None = None) -> dict[str, Any]:
        asset = self.visual_asset_library_service.get(
            owner_scope=self._visual_asset_owner_scope(owner_scope),
            visual_asset_id=visual_asset_id,
        )
        return {"visual_asset": self._visual_asset_public_record(asset)}

    def post_visual_asset_prepare(
        self,
        visual_asset_id: str,
        payload: dict[str, Any],
        owner_scope: str | None = None,
    ) -> dict[str, Any]:
        if payload:
            raise ValueError("visual_asset_prepare_payload_must_be_empty")
        asset = self.visual_asset_library_service.prepare(
            owner_scope=self._visual_asset_owner_scope(owner_scope),
            visual_asset_id=visual_asset_id,
        )
        return {"visual_asset": self._visual_asset_public_record(asset)}

    def post_visual_asset_activate(
        self,
        visual_asset_id: str,
        payload: dict[str, Any],
        owner_scope: str | None = None,
    ) -> dict[str, Any]:
        version_id = str(payload.get("version_id") or "").strip()
        confirmed = payload.get("confirm_activation") is True
        if not version_id:
            raise ValueError("visual_asset_version_required")
        asset = self.visual_asset_library_service.activate(
            owner_scope=self._visual_asset_owner_scope(owner_scope),
            visual_asset_id=visual_asset_id,
            version_id=version_id,
            confirm_activation=confirmed,
        )
        return {"visual_asset": self._visual_asset_public_record(asset)}

    def post_visual_asset_archive(
        self,
        visual_asset_id: str,
        payload: dict[str, Any],
        owner_scope: str | None = None,
    ) -> dict[str, Any]:
        if payload.get("confirm_archive") is not True:
            raise ValueError("visual_asset_archive_confirmation_required")
        asset = self.visual_asset_library_service.archive(
            owner_scope=self._visual_asset_owner_scope(owner_scope),
            visual_asset_id=visual_asset_id,
        )
        return {"visual_asset": self._visual_asset_public_record(asset)}

    def get_project_visual_asset_bindings(self, project_id: str) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        binding_set = self.project_visual_asset_binding_service.current(project_id=project_id)
        return self._project_visual_asset_binding_public_record(binding_set)

    def post_project_visual_asset_binding(
        self,
        project_id: str,
        payload: dict[str, Any],
        owner_scope: str | None = None,
    ) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        request = ProjectVisualAssetBindingRequest.model_validate(payload)
        self.project_visual_asset_binding_service.bind(
            owner_scope=self._visual_asset_owner_scope(owner_scope),
            project_id=project_id,
            request=request,
        )
        return self.get_project_visual_asset_bindings(project_id)

    def delete_project_visual_asset_binding(
        self,
        project_id: str,
        binding_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        self.project_visual_asset_binding_service.remove(
            project_id=project_id,
            binding_id=binding_id,
            confirm_removal=payload.get("confirm_removal") is True,
        )
        return self.get_project_visual_asset_bindings(project_id)

    def _visual_asset_owner_scope(self, supplied_owner_scope: str | None) -> str:
        value = str(supplied_owner_scope or self.visual_asset_owner_scope).strip()
        return value or "local_default"

    @staticmethod
    def _visual_asset_public_record(asset: Any) -> dict[str, Any]:
        """Safe browser projection: no source IDs, prompt or review internals."""

        active_version = asset.active_version()
        return {
            "visual_asset_id": asset.visual_asset_id,
            "display_name": asset.display_name,
            "asset_type": asset.asset_type,
            "lifecycle_status": asset.lifecycle_status,
            "active_version_id": asset.active_version_id,
            "available_for_projects": bool(active_version and asset.lifecycle_status == "active"),
            "latest_preparation": (
                {
                    "status": active_version.lifecycle_status,
                    "user_activation_confirmed": active_version.activation_confirmed,
                }
                if active_version is not None
                else None
            ),
        }

    @staticmethod
    def _project_visual_asset_binding_public_record(binding_set: Any) -> dict[str, Any]:
        return {
            "project_id": binding_set.project_id,
            "state": binding_set.state,
            "bindings": [
                {
                    "binding_id": item.binding_id,
                    "visual_asset_id": item.visual_asset_id,
                    "selected_version_id": item.selected_version_id,
                    "asset_type": item.asset_type,
                    "status": item.status,
                }
                for item in binding_set.bindings
            ],
        }

    def get_project_people_assets(self, project_id: str) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        return {
            "project_id": project_id,
            "people_assets": [self._people_asset_public_record(project_id, item) for item in self.people_asset_service.list(project_id)],
        }

    def post_project_people_asset(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        request = PeopleAssetCreateRequest.model_validate(payload)
        asset = self.people_asset_service.create_draft(project_id, request)
        return {"people_asset": asset.model_dump(mode="json"), "lifecycle_state": "draft"}

    def get_project_people_asset(self, project_id: str, people_asset_id: str) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        asset = self.people_asset_service.get(project_id, people_asset_id)
        return {"people_asset": self._people_asset_public_record(project_id, asset)}

    def _people_asset_public_record(self, project_id: str, asset: Any) -> dict[str, Any]:
        """Expose only lifecycle truth needed to restore the Professional UI.

        The browser must be able to recover a pending review after refresh, but
        it must not receive prompts, candidate payloads, provider details or
        raw pixel evidence. Pack history is projected to view/status facts only.
        """

        record = asset.model_dump(mode="json")
        latest = None
        try:
            history = self.people_asset_service.catalog.list_pack_history(project_id, asset.people_asset_id)
            if history:
                snapshot = history[-1].pack_snapshot
                latest = {
                    "status": snapshot.status,
                    "pack_version_id": snapshot.pack_version_id,
                    "user_activation_confirmed": snapshot.user_activation_confirmed,
                    "anchor_views": [
                        {"view_role": view.view_role, "active": view.active}
                        for view in snapshot.anchor_views
                    ],
                }
        except (AttributeError, KeyError, IndexError):
            latest = None
        if latest is not None:
            record["latest_preparation"] = latest
        return record

    def post_project_people_asset_prepare(
        self,
        project_id: str,
        people_asset_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        PeopleAssetPrepareRequest.model_validate(payload)
        result = self.people_asset_service.prepare_pack(project_id, people_asset_id)
        return {"preparation": result.model_dump(mode="json")}

    def post_project_people_asset_activate(
        self,
        project_id: str,
        people_asset_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.project_service.get_project(project_id)
        request = PeopleAssetActivationRequest.model_validate(payload)
        asset = self.people_asset_service.activate_pack(project_id, people_asset_id, request)
        return {"people_asset": asset.model_dump(mode="json"), "lifecycle_state": "active"}

    def post_project_reference(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.add_project_reference(project_id, payload).model_dump(mode="json")

    def patch_project_reference(self, project_id: str, reference_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.update_project_reference(project_id, reference_id, payload).model_dump(mode="json")

    def post_project_reference_remove(self, project_id: str, reference_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.project_service.remove_project_reference(project_id, reference_id, payload or {}).model_dump(mode="json")

    def post_project_feedback(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.add_project_feedback(project_id, payload).model_dump(mode="json")

    def post_project_brand_memory_proposal(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.create_brand_memory_proposal(project_id, payload).model_dump(mode="json")

    def post_project_brand_memory_confirm(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.confirm_brand_memory_proposal(project_id, payload).model_dump(mode="json")

    def post_project_output_unselect(self, project_id: str, output_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.project_service.unselect_project_output(project_id, output_id, payload or {})

    def post_project_output_reject(self, project_id: str, output_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.reject_project_output(project_id, output_id, payload)

    def post_project_job(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.create_project_job(project_id, payload).model_dump(mode="json")

    def post_project_ecommerce_slot_continuation(
        self,
        project_id: str,
        parent_job_id: str,
        slot_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self.project_service.create_ecommerce_slot_continuation(
            project_id,
            parent_job_id,
            slot_id,
            payload,
        ).model_dump(mode="json")

    def get_project_ecommerce_slot_delivery(
        self,
        project_id: str,
        root_job_id: str,
        slot_id: str,
    ) -> dict[str, Any]:
        return self.project_service.get_ecommerce_slot_delivery(
            project_id,
            root_job_id,
            slot_id,
        ).model_dump(mode="json")

    def post_project_photography_role_continuation(
        self,
        project_id: str,
        parent_job_id: str,
        role_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return self.project_service.create_photography_role_continuation(
            project_id,
            parent_job_id,
            role_id,
            payload,
        ).model_dump(mode="json")

    def get_project_photography_role_delivery(
        self,
        project_id: str,
        root_job_id: str,
        role_id: str,
    ) -> dict[str, Any]:
        return self.project_service.get_photography_role_delivery(
            project_id,
            root_job_id,
            role_id,
        ).model_dump(mode="json")

    def post_project_job_generate(self, project_id: str, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.project_service.generate_project_job(project_id, job_id, payload or {}).model_dump(mode="json")

    def mark_project_job_generating(
        self,
        project_id: str,
        job_id: str,
        *,
        background_attempt_id: str | None = None,
        background_timeout_seconds: float | None = None,
        background_runtime_id: str | None = None,
    ) -> dict[str, Any]:
        return self.project_service.mark_project_job_generating(
            project_id,
            job_id,
            background_attempt_id=background_attempt_id,
            background_timeout_seconds=background_timeout_seconds,
            background_runtime_id=background_runtime_id,
        ).model_dump(mode="json")

    def mark_project_job_generation_timed_out(
        self,
        project_id: str,
        job_id: str,
        *,
        background_attempt_id: str,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        return self.project_service.mark_project_job_generation_timed_out(
            project_id,
            job_id,
            background_attempt_id=background_attempt_id,
            timeout_seconds=timeout_seconds,
        ).model_dump(mode="json")

    def mark_project_job_generation_worker_failed(
        self,
        project_id: str,
        job_id: str,
        *,
        background_attempt_id: str,
        failure_code: str,
    ) -> dict[str, Any]:
        return self.project_service.mark_project_job_generation_worker_failed(
            project_id,
            job_id,
            background_attempt_id=background_attempt_id,
            failure_code=failure_code,
        ).model_dump(mode="json")

    def post_project_job_select(self, project_id: str, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.project_service.select_project_job(project_id, job_id, payload or {})

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self.service.get_job(job_id).model_dump(mode="json")

    def get_creative_job(self, job_id: str) -> dict[str, Any]:
        return self.get_job(job_id)

    def get_job_export(self, job_id: str) -> dict[str, Any]:
        return self.service.export_job(job_id).model_dump(mode="json")

    def get_job_export_download(self, job_id: str) -> dict[str, Any]:
        return self.service.export_job_download(job_id).model_dump(mode="json")

    def post_generate(self, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.service.generate_job(job_id, payload or {}).model_dump(mode="json")

    def post_creative_job_generate(self, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.post_generate(job_id, payload)

    def post_select(self, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.service.select_result(job_id, payload or {}).model_dump(mode="json")

    def post_creative_job_select(self, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.post_select(job_id, payload)

    def post_brands(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.service.create_brand(payload).model_dump(mode="json")

    def post_product_brands(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post_brands(payload)

    def get_brand(self, brand_id: str) -> dict[str, Any]:
        return self.service.get_brand(brand_id).model_dump(mode="json")

    def get_product_brand(self, brand_id: str) -> dict[str, Any]:
        return self.get_brand(brand_id)
