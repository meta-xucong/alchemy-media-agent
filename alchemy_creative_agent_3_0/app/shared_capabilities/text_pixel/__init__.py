"""Read-compatible contracts for retired local text-pixel execution.

Forward text delivery is provider-native complete-image generation (Doc111).
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
    LicensedFont,
    OcrResult,
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
    "LicensedFont",
    "NormalizedSafeArea",
    "OcrResult",
    "StaticOcrEngine",
    "TextPixelDelivery",
    "TextPixelDeliveryBatch",
    "TextPixelDeliveryAttempt",
    "TextPixelDeliveryRuntime",
    "TextPixelRuntimeSettings",
    "TesseractOcrEngine",
]
