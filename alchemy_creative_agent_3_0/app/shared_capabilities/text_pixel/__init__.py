"""Scenario-neutral deterministic text-pixel delivery primitives.

This package deliberately owns no template, marketplace, or provider policy.
Templates can provide a frozen, internal :class:`CopyRenderPlan`; final-pixel
composition, review, repair, and lineage are handled here.
"""

from .contracts import (
    CopyRenderPlan,
    CopyRenderSourceLineage,
    NormalizedSafeArea,
    TextPixelDelivery,
    TextPixelDeliveryAttempt,
)
from .runtime import (
    FontRegistry,
    LicensedFont,
    OcrResult,
    StaticOcrEngine,
    TextPixelRuntimeSettings,
    TextPixelDeliveryRuntime,
    TesseractOcrEngine,
)

__all__ = [
    "CopyRenderPlan",
    "CopyRenderSourceLineage",
    "FontRegistry",
    "LicensedFont",
    "NormalizedSafeArea",
    "OcrResult",
    "StaticOcrEngine",
    "TextPixelDelivery",
    "TextPixelDeliveryAttempt",
    "TextPixelDeliveryRuntime",
    "TextPixelRuntimeSettings",
    "TesseractOcrEngine",
]
