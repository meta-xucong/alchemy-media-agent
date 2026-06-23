"""Thin framework-neutral route handler facade for V3 API adapters."""

from __future__ import annotations

from typing import Any

from .service import V3ProductApiService


class V3ProductRouteHandlers:
    """Method names mirror the reserved V3 route contract."""

    def __init__(self, service: V3ProductApiService | None = None) -> None:
        self.service = service or V3ProductApiService()

    def post_jobs(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.service.create_job(payload).model_dump(mode="json")

    def post_creative_jobs(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post_jobs(payload)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self.service.get_job(job_id).model_dump(mode="json")

    def get_creative_job(self, job_id: str) -> dict[str, Any]:
        return self.get_job(job_id)

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
