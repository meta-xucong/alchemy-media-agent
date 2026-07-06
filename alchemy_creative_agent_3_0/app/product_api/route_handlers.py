"""Thin framework-neutral route handler facade for V3 API adapters."""

from __future__ import annotations

from typing import Any

from ..app_shell import get_scenario_hub_contract
from ..project_mode import InMemoryProjectStore, ProjectTemplateRegistry, V3ProjectModeService
from .service import V3ProductApiService


class V3ProductRouteHandlers:
    """Method names mirror the reserved V3 route contract."""

    def __init__(
        self,
        service: V3ProductApiService | None = None,
        project_store: InMemoryProjectStore | None = None,
        template_registry: ProjectTemplateRegistry | None = None,
    ) -> None:
        self.service = service or V3ProductApiService()
        self.project_service = V3ProjectModeService(
            product_service=self.service,
            project_store=project_store,
            template_registry=template_registry,
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

    def get_history(self, limit: int = 20) -> dict[str, Any]:
        return self.service.list_history(limit=limit).model_dump(mode="json")

    def get_projects(self, limit: int = 20, owner_user_id: int | None = None) -> dict[str, Any]:
        return self.project_service.list_projects(limit=limit, owner_user_id=owner_user_id).model_dump(mode="json")

    def get_project_outputs(self, limit: int = 60, owner_user_id: int | None = None, compact: bool = False) -> dict[str, Any]:
        return self.project_service.list_project_outputs(limit=limit, owner_user_id=owner_user_id, compact=compact)

    def post_projects(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.create_project(payload).model_dump(mode="json")

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self.project_service.get_project(project_id).model_dump(mode="json")

    def post_project_archive(self, project_id: str) -> dict[str, Any]:
        return self.project_service.archive_project(project_id).model_dump(mode="json")

    def get_project_timeline(self, project_id: str) -> dict[str, Any]:
        return self.project_service.list_timeline(project_id).model_dump(mode="json")

    def get_project_context(self, project_id: str) -> dict[str, Any]:
        return self.project_service.get_project_context(project_id).model_dump(mode="json")

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

    def post_project_job_generate(self, project_id: str, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.project_service.generate_project_job(project_id, job_id, payload or {}).model_dump(mode="json")

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
