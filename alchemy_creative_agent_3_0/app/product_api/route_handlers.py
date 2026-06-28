"""Thin framework-neutral route handler facade for V3 API adapters."""

from __future__ import annotations

from typing import Any

from ..app_shell import get_scenario_hub_contract
from .service import V3ProductApiService


class V3ProductRouteHandlers:
    """Method names mirror the reserved V3 route contract."""

    def __init__(self, service: V3ProductApiService | None = None) -> None:
        self.service = service or V3ProductApiService()

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
