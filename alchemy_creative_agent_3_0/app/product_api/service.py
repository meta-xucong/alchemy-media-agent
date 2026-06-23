"""Framework-neutral V3 product API service.

Route handlers can wrap this service later. The service deliberately exposes
product concepts such as jobs, asset series, candidates, selected result, and
balance estimate instead of image-model controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..app_shell.navigation import get_navigation_entry
from ..app_shell.routes import API_NAMESPACE, get_route_contracts
from ..brand_memory.profile_service import BrandProfileService
from ..creative_core.pipeline import run_creative_planning, run_generation_loop
from ..creative_core.rules import RULE_VERSION, stable_id
from ..platform_adapters import V3BalanceAdapter, V3BalanceEstimate
from ..schemas import BrandProfile, MemoryUpdate, PackagedAsset, PlanningResult, Recommendation, ReferenceAsset
from .contracts import (
    AssetSeriesItem,
    BrandApiResponse,
    CampaignSummary,
    CandidateSummary,
    CreateBrandRequest,
    CreateCreativeJobRequest,
    GenerateJobRequest,
    ProductJobStatus,
    ProductJobStatusValue,
    SelectResultRequest,
    SelectionResponse,
    SelectedResult,
    StyleContinuationSummary,
)


QUALITY_MODE_TO_MOCK_PROFILE = {
    "standard": "balanced",
    "explore": "needs_refinement",
    "strict": "balanced",
}


@dataclass
class ProductJobRecord:
    request: CreateCreativeJobRequest
    status: ProductJobStatusValue
    planning_result: PlanningResult | None = None
    generation_result: PlanningResult | None = None
    selected_result: SelectedResult | None = None
    balance_estimate: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def job_id(self) -> str:
        result = self.generation_result or self.planning_result
        if result is None:
            return "job_unavailable"
        return result.creative_job.job_id


class InMemoryProductJobStore:
    """Small deterministic job store for V3 product API tests and adapters."""

    def __init__(self) -> None:
        self._records: dict[str, ProductJobRecord] = {}

    def save(self, record: ProductJobRecord) -> ProductJobRecord:
        self._records[record.job_id] = record
        return record

    def get(self, job_id: str) -> ProductJobRecord | None:
        return self._records.get(job_id)


class V3ProductApiService:
    """V3-owned product API facade over the Creative Core."""

    def __init__(
        self,
        brand_profile_service: BrandProfileService | None = None,
        balance_adapter: V3BalanceAdapter | None = None,
        job_store: InMemoryProductJobStore | None = None,
    ) -> None:
        self.brand_profile_service = brand_profile_service or BrandProfileService()
        self.balance_adapter = balance_adapter or V3BalanceAdapter()
        self.job_store = job_store or InMemoryProductJobStore()

    def create_creative_job(self, request: CreateCreativeJobRequest | dict[str, Any]) -> ProductJobStatus:
        create_request = self._coerce_create_job_request(request)
        planning_result = run_creative_planning(
            user_input=create_request.user_input,
            optional_brand_id=create_request.effective_brand_id,
            brand_profile_service=self.brand_profile_service,
        )
        estimate = self._estimate_for_result(planning_result)
        record = ProductJobRecord(
            request=create_request,
            status=ProductJobStatusValue.PLANNED,
            planning_result=planning_result,
            balance_estimate=estimate,
        )
        self.job_store.save(record)
        return self._status_from_record(record)

    def create_job(self, request: CreateCreativeJobRequest | dict[str, Any]) -> ProductJobStatus:
        return self.create_creative_job(request)

    def get_job(self, job_id: str) -> ProductJobStatus:
        record = self.job_store.get(job_id)
        if record is None:
            return self._not_found_status(job_id)
        return self._status_from_record(record)

    def generate_asset_series(
        self,
        job_id: str,
        request: GenerateJobRequest | dict[str, Any] | None = None,
    ) -> ProductJobStatus:
        record = self.job_store.get(job_id)
        if record is None:
            return self._not_found_status(job_id)
        generate_request = self._coerce_generate_request(request or {})
        if not self.balance_adapter.has_available_credits(record.balance_estimate.get("credits_required", 0)):
            record.status = ProductJobStatusValue.BLOCKED
            record.warnings.append("Insufficient V3 balance adapter credits for this operation.")
            self.job_store.save(record)
            return self._status_from_record(record)
        generation_result = run_generation_loop(
            user_input=record.request.user_input,
            optional_brand_id=record.request.effective_brand_id,
            brand_profile_service=self.brand_profile_service,
            mock_profile=QUALITY_MODE_TO_MOCK_PROFILE[generate_request.quality_mode],
            apply_memory_update=False,
        )
        record.generation_result = generation_result
        record.status = ProductJobStatusValue.GENERATED
        record.balance_estimate = self._estimate_for_result(generation_result)
        self.job_store.save(record)
        return self._status_from_record(record)

    def generate_job(
        self,
        job_id: str,
        request: GenerateJobRequest | dict[str, Any] | None = None,
    ) -> ProductJobStatus:
        return self.generate_asset_series(job_id, request)

    def select_result(
        self,
        job_id: str,
        request: SelectResultRequest | dict[str, Any] | None = None,
    ) -> SelectionResponse:
        record = self.job_store.get(job_id)
        if record is None:
            selected = SelectedResult(metadata={"selection_status": "job_not_found"})
            status = self._not_found_status(job_id)
            return SelectionResponse(
                job_id=job_id,
                status=ProductJobStatusValue.NOT_FOUND,
                selected_result=selected,
                job_status=status,
                warnings=["Creative job was not found in the V3 product API store."],
                metadata={"source": "V3ProductApiService", "rules_version": RULE_VERSION},
            )
        select_request = self._coerce_select_request(request or {})
        result = record.generation_result or record.planning_result
        if result is None:
            record.status = ProductJobStatusValue.FAILED
            record.warnings.append("Creative job has no planning or generation result to select.")
            self.job_store.save(record)
            selected = SelectedResult(metadata={"selection_status": "missing_result"})
            return SelectionResponse(
                job_id=job_id,
                status=record.status,
                selected_result=selected,
                job_status=self._status_from_record(record),
                warnings=list(record.warnings),
                metadata={"source": "V3ProductApiService", "rules_version": RULE_VERSION},
            )

        selected_assets = self._selected_assets(result, select_request)
        selected_candidate_ids = [
            asset.metadata["selected_candidate_id"]
            for asset in selected_assets
            if asset.metadata.get("selected_candidate_id")
        ]
        selected_asset_ids = [asset.asset_id for asset in selected_assets]
        update = self._memory_update_for_selection(result.asset_pack.brand_memory_update, selected_asset_ids)
        memory_update_applied = False
        if update is not None and select_request.apply_memory_update:
            memory_update_applied = self.brand_profile_service.apply_memory_update(update) is not None

        selected = SelectedResult(
            selected_candidate_ids=selected_candidate_ids,
            selected_asset_ids=selected_asset_ids,
            asset_pack_id=result.asset_pack.asset_pack_id,
            memory_update_id=update.memory_update_id if update else None,
            memory_update_applied=memory_update_applied,
            metadata={
                "selection_status": "selected",
                "source": "V3ProductApiService",
                "apply_memory_update_requested": select_request.apply_memory_update,
            },
        )
        record.selected_result = selected
        record.status = ProductJobStatusValue.SELECTED
        self.job_store.save(record)
        return SelectionResponse(
            job_id=job_id,
            status=record.status,
            selected_result=selected,
            job_status=self._status_from_record(record),
            warnings=list(record.warnings),
            metadata={"source": "V3ProductApiService", "rules_version": RULE_VERSION},
        )

    def create_brand(self, request: CreateBrandRequest | dict[str, Any]) -> BrandApiResponse:
        create_request = self._coerce_create_brand_request(request)
        brand_id = create_request.brand_id or stable_id(
            "brand",
            create_request.brand_name or "unnamed",
            ",".join(create_request.visual_tone),
            ",".join(create_request.color_palette),
        )
        profile = BrandProfile(
            brand_id=brand_id,
            brand_name=create_request.brand_name,
            industry=create_request.industry,
            is_temporary=False,
            visual_tone=list(create_request.visual_tone),
            color_palette=list(create_request.color_palette),
            layout_preference=create_request.layout_preference,
            typography_preference=create_request.typography_preference,
            copywriting_tone=create_request.copywriting_tone,
            platform_history=list(create_request.platform_history),
            metadata={
                **create_request.metadata,
                "source": "V3ProductApiService",
                "created_via_v3_product_api": True,
                "rules_version": RULE_VERSION,
            },
        )
        saved = self.brand_profile_service.save_profile(profile)
        return BrandApiResponse(
            status="created",
            brand=saved,
            api_namespace=API_NAMESPACE,
            route=get_route_contracts()["create_brand"],
            metadata={"source": "V3ProductApiService", "rules_version": RULE_VERSION},
        )

    def get_brand(self, brand_id: str) -> BrandApiResponse:
        profile = self.brand_profile_service.load_profile(brand_id)
        route = get_route_contracts()["get_brand"].format(brand_id=brand_id)
        if profile is None:
            return BrandApiResponse(
                status="not_found",
                brand=None,
                api_namespace=API_NAMESPACE,
                route=route,
                warnings=["Brand profile was not found in the V3 brand memory store."],
                metadata={"source": "V3ProductApiService", "rules_version": RULE_VERSION},
            )
        return BrandApiResponse(
            status="found",
            brand=profile,
            api_namespace=API_NAMESPACE,
            route=route,
            metadata={"source": "V3ProductApiService", "rules_version": RULE_VERSION},
        )

    def estimate_balance(self, asset_count: int) -> dict[str, Any]:
        return self._balance_estimate_to_dict(self.balance_adapter.estimate_planning_cost(asset_count))

    def _status_from_record(self, record: ProductJobRecord) -> ProductJobStatus:
        result = record.generation_result or record.planning_result
        if result is None:
            return self._not_found_status(record.job_id)
        asset_pack = result.asset_pack
        nav = get_navigation_entry()
        return ProductJobStatus(
            job_id=result.creative_job.job_id,
            status=record.status,
            api_namespace=API_NAMESPACE,
            ui_entry_route=nav["route"],
            brand_id=result.brand_profile.brand_id,
            planning_result_id=record.planning_result.planning_result_id if record.planning_result else None,
            generation_result_id=record.generation_result.planning_result_id if record.generation_result else None,
            asset_pack_id=asset_pack.asset_pack_id,
            campaign=self._campaign_summary(record, result),
            asset_series=self._asset_series(result, record.status),
            candidates=self._candidate_summaries(result),
            style_continuation=self._style_continuation_summary(record, result),
            selected_result=record.selected_result,
            balance_estimate=dict(record.balance_estimate),
            routes=get_route_contracts(),
            warnings=list(dict.fromkeys(record.warnings + asset_pack.manifest.get("warnings", []))),
            metadata={
                "source": "V3ProductApiService",
                "rules_version": RULE_VERSION,
                "v3_independent_product_api": True,
                "balance_adapter": self.balance_adapter.adapter_name,
                "selected_vertical_pack": result.metadata.get("selected_vertical_pack"),
                "exposes_product_concepts_only": True,
            },
        )

    def _not_found_status(self, job_id: str) -> ProductJobStatus:
        nav = get_navigation_entry()
        return ProductJobStatus(
            job_id=job_id,
            status=ProductJobStatusValue.NOT_FOUND,
            api_namespace=API_NAMESPACE,
            ui_entry_route=nav["route"],
            routes=get_route_contracts(),
            warnings=["Creative job was not found in the V3 product API store."],
            metadata={
                "source": "V3ProductApiService",
                "rules_version": RULE_VERSION,
                "v3_independent_product_api": True,
            },
        )

    def _campaign_summary(self, record: ProductJobRecord, result: PlanningResult) -> CampaignSummary:
        brief = result.commercial_brief
        campaign = record.request.campaign
        return CampaignSummary(
            campaign_id=campaign.campaign_id if campaign and campaign.campaign_id else brief.brief_id,
            campaign_name=campaign.campaign_name if campaign else brief.metadata.get("campaign_name"),
            scenario=brief.scenario,
            business_goal=campaign.business_goal if campaign and campaign.business_goal else brief.business_goal,
            target_platforms=list(campaign.platforms) if campaign and campaign.platforms else list(brief.target_platforms),
            commercial_hooks=list(brief.commercial_hooks),
            metadata={
                "brief_id": brief.brief_id,
                "industry": brief.industry.value,
                "confidence": brief.confidence,
                "request_campaign_supplied": campaign is not None,
            },
        )

    def _style_continuation_summary(
        self,
        record: ProductJobRecord,
        result: PlanningResult,
    ) -> StyleContinuationSummary:
        requested_brand_id = record.request.continue_style_from_brand_id or record.request.brand_id
        enabled = requested_brand_id is not None and not result.brand_profile.is_temporary
        return StyleContinuationSummary(
            enabled=enabled,
            source_brand_id=requested_brand_id,
            visual_tone=list(result.brand_profile.visual_tone),
            color_palette=list(result.brand_profile.color_palette),
            reference_asset_count=len(result.brand_profile.reference_assets),
            metadata={
                "brand_id": result.brand_profile.brand_id,
                "brand_profile_temporary": result.brand_profile.is_temporary,
            },
        )

    def _asset_series(self, result: PlanningResult, status: ProductJobStatusValue) -> list[AssetSeriesItem]:
        packaged_by_id = {asset.asset_id: asset for asset in result.asset_pack.assets}
        items: list[AssetSeriesItem] = []
        for asset in result.series_plan.assets:
            packaged = packaged_by_id.get(asset.asset_id)
            render_manifest = packaged.metadata.get("render_manifest") if packaged else None
            selected_candidate_id = packaged.metadata.get("selected_candidate_id") if packaged else None
            item_status = "generated" if selected_candidate_id else status.value
            if status == ProductJobStatusValue.SELECTED and selected_candidate_id:
                item_status = "selected"
            items.append(
                AssetSeriesItem(
                    asset_id=asset.asset_id,
                    asset_type=asset.asset_type.value,
                    platform=asset.platform,
                    aspect_ratio=asset.aspect_ratio,
                    purpose=asset.purpose,
                    status=item_status,
                    selected_candidate_id=selected_candidate_id,
                    preview_uri=packaged.uri if packaged else None,
                    editable_text_layer_count=len(render_manifest.get("editable_text_layers", [])) if render_manifest else 0,
                    metadata={
                        "requires_text_overlay": asset.requires_text_overlay,
                        "requires_brand_consistency": asset.requires_brand_consistency,
                    },
                )
            )
        return items

    def _candidate_summaries(self, result: PlanningResult) -> list[CandidateSummary]:
        candidates: list[CandidateSummary] = []
        evals_by_candidate_id = {
            report.candidate_id: report for report in result.evaluation_reports if report.candidate_id is not None
        }
        assets_by_id = {asset.asset_id: asset for asset in result.series_plan.assets}
        selected_candidate_ids = {
            asset.metadata.get("selected_candidate_id")
            for asset in result.asset_pack.assets
            if asset.metadata.get("selected_candidate_id")
        }
        for asset in result.asset_pack.assets:
            candidate_id = asset.metadata.get("selected_candidate_id")
            if not candidate_id:
                continue
            report = evals_by_candidate_id.get(candidate_id)
            asset_spec = assets_by_id.get(asset.asset_id)
            candidates.append(
                CandidateSummary(
                    candidate_id=candidate_id,
                    asset_id=asset.asset_id,
                    platform=asset_spec.platform if asset_spec else asset.platform,
                    preview_uri=asset.uri,
                    overall_score=report.overall_score if report else None,
                    recommendation=report.recommendation.value if report else None,
                    selected=candidate_id in selected_candidate_ids,
                    metadata={"asset_pack_id": result.asset_pack.asset_pack_id},
                )
            )
        return candidates

    def _selected_assets(self, result: PlanningResult, request: SelectResultRequest) -> list[PackagedAsset]:
        assets = result.asset_pack.assets
        if request.selected_candidate_id:
            return [
                asset
                for asset in assets
                if asset.metadata.get("selected_candidate_id") == request.selected_candidate_id
            ]
        if request.selected_asset_id:
            return [asset for asset in assets if asset.asset_id == request.selected_asset_id]
        return list(assets)

    def _memory_update_for_selection(
        self,
        update: MemoryUpdate | None,
        selected_asset_ids: list[str],
    ) -> MemoryUpdate | None:
        if update is None:
            return None
        selected_asset_set = set(selected_asset_ids)
        selected_refs = [
            ref for ref in update.new_reference_assets if ref.metadata.get("candidate_id") or ref.asset_id in selected_asset_set
        ]
        filtered = update.model_copy(deep=True)
        filtered.accepted_asset_ids = [asset_id for asset_id in update.accepted_asset_ids if asset_id in selected_asset_set]
        if not filtered.accepted_asset_ids:
            filtered.accepted_asset_ids = list(selected_asset_ids)
        filtered.new_reference_assets = selected_refs or list(update.new_reference_assets)
        filtered.metadata = {
            **filtered.metadata,
            "selected_via_v3_product_api": True,
            "selected_asset_ids": list(selected_asset_ids),
        }
        return filtered

    def _estimate_for_result(self, result: PlanningResult) -> dict[str, Any]:
        estimate = self.balance_adapter.estimate_planning_cost(len(result.series_plan.assets))
        return self._balance_estimate_to_dict(estimate)

    def _balance_estimate_to_dict(self, estimate: V3BalanceEstimate) -> dict[str, Any]:
        return {
            "credits_required": estimate.credits_required,
            "currency": estimate.currency,
            "metadata": {**estimate.metadata, "adapter": self.balance_adapter.adapter_name},
        }

    def _coerce_create_job_request(self, request: CreateCreativeJobRequest | dict[str, Any]) -> CreateCreativeJobRequest:
        if isinstance(request, CreateCreativeJobRequest):
            return request
        return CreateCreativeJobRequest.model_validate(request)

    def _coerce_generate_request(self, request: GenerateJobRequest | dict[str, Any]) -> GenerateJobRequest:
        if isinstance(request, GenerateJobRequest):
            return request
        return GenerateJobRequest.model_validate(request)

    def _coerce_select_request(self, request: SelectResultRequest | dict[str, Any]) -> SelectResultRequest:
        if isinstance(request, SelectResultRequest):
            return request
        return SelectResultRequest.model_validate(request)

    def _coerce_create_brand_request(self, request: CreateBrandRequest | dict[str, Any]) -> CreateBrandRequest:
        if isinstance(request, CreateBrandRequest):
            return request
        return CreateBrandRequest.model_validate(request)


V3ProductApi = V3ProductApiService


def create_default_product_api() -> V3ProductApiService:
    return V3ProductApiService()
