"""Scenario-neutral deterministic text-pixel delivery primitives.

This package deliberately owns no template, marketplace, or provider policy.
Templates can provide a frozen, internal :class:`CopyRenderPlan`; final-pixel
composition, review, repair, and lineage are handled here.
"""

from .contracts import (
    CopyRenderPlan,
    CopyRenderPlanBatch,
    CopyRenderSourceLineage,
    NormalizedSafeArea,
    TextPixelDelivery,
    TextPixelDeliveryBatch,
    TextPixelDeliveryAttempt,
)
from .runtime import (
    FontRegistry,
    FontPreflightResult,
    LicensedFont,
    OcrPreflightResult,
    OcrResult,
    ProductionTextPixelCertification,
    StaticOcrEngine,
    TextPixelRuntimeSettings,
    TextPixelDeliveryRuntime,
    TesseractOcrEngine,
)

__all__ = [
    "CopyRenderPlan",
    "CopyRenderPlanBatch",
    "CopyRenderSourceLineage",
    "FontRegistry",
    "FontPreflightResult",
    "LicensedFont",
    "NormalizedSafeArea",
    "OcrResult",
    "OcrPreflightResult",
    "ProductionTextPixelCertification",
    "StaticOcrEngine",
    "TextPixelDelivery",
    "TextPixelDeliveryBatch",
    "TextPixelDeliveryAttempt",
    "TextPixelDeliveryRuntime",
    "TextPixelRuntimeSettings",
    "TesseractOcrEngine",
]
