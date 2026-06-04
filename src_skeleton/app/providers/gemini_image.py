from __future__ import annotations

from app.config import settings
from app.schemas import CostEstimate, ImageGenerationRequest, ImageGenerationResult
from app.providers.base import ProviderCapabilities, ProviderNotConfiguredError


class GeminiImageProvider:
    name = "gemini_image"

    async def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider=self.name,
            configured=False,
            models=[settings.gemini_image_model],
            operations=["generate", "edit"],
            limits={
                "note": "Live Gemini image SDK wiring is not implemented in this MVP.",
                "api_key_configured": bool(settings.gemini_image_api_key),
                "base_url_configured": bool(settings.gemini_image_base_url),
            },
            reason="Gemini image provider is reserved as a documented placeholder until live google-genai SDK wiring is implemented.",
        )

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        raise ProviderNotConfiguredError("Gemini image provider is a stub until google-genai SDK wiring is implemented.", provider=self.name)

    async def edit(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        raise ProviderNotConfiguredError("Gemini image edit provider is a stub until google-genai SDK wiring is implemented.", provider=self.name)

    async def estimate_cost(self, request: ImageGenerationRequest) -> CostEstimate:
        return CostEstimate(
            provider=self.name,
            model=settings.gemini_image_model,
            estimated_cost=0.0,
            detail={"note": "Fill from Gemini pricing before live use.", "count": request.prompt_plan.count},
        )
