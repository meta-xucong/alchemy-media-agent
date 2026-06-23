"""V3-owned product API boundary."""

from .contracts import (
    AssetSeriesItem,
    BrandApiResponse,
    CampaignRequest,
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
from .service import V3ProductApi, V3ProductApiService, create_default_product_api

__all__ = [
    "AssetSeriesItem",
    "BrandApiResponse",
    "CampaignRequest",
    "CampaignSummary",
    "CandidateSummary",
    "CreateBrandRequest",
    "CreateCreativeJobRequest",
    "GenerateJobRequest",
    "ProductJobStatus",
    "ProductJobStatusValue",
    "SelectResultRequest",
    "SelectedResult",
    "SelectionResponse",
    "StyleContinuationSummary",
    "V3ProductApi",
    "V3ProductApiService",
    "create_default_product_api",
]
