from __future__ import annotations

import asyncio

from app.config import settings
from app.providers.images.base import V2ImageProvider, V2ImageProviderCapabilities
from app.providers.images.gemini_image import V2GeminiImageProvider
from app.providers.images.mock import V2MockImageProvider
from app.providers.images.openai_gpt_image_2 import V2OpenAIGPTImage2Provider


def _providers() -> dict[str, V2ImageProvider]:
    return {
        "openai_gpt_image": V2OpenAIGPTImage2Provider(),
        "gemini_image": V2GeminiImageProvider(),
        "mock_image": V2MockImageProvider(),
    }


async def get_v2_image_provider(provider_hint: str | None = None) -> V2ImageProvider:
    providers = _providers()
    requested = _normalize_provider(provider_hint)
    if requested == "gemini_image" and not settings.gemini_image_generation_enabled:
        requested = "auto"
    if requested != "auto":
        return providers.get(requested) or providers["mock_image"]
    provider_order = ["openai_gpt_image"]
    if settings.gemini_image_generation_enabled:
        provider_order.append("gemini_image")
    for provider_id in provider_order:
        provider = providers[provider_id]
        capabilities = await provider.capabilities()
        if capabilities.configured:
            return provider
    return providers["mock_image"]


async def list_v2_image_provider_capabilities() -> list[V2ImageProviderCapabilities]:
    providers = _providers()
    return await asyncio.gather(*(provider.capabilities() for provider in providers.values()))


def _normalize_provider(provider_hint: str | None) -> str:
    requested = provider_hint
    if requested in {None, "", "auto"}:
        requested = settings.image_generation_provider or "auto"
    if requested == "gemini_image" and not settings.gemini_image_generation_enabled:
        return "auto"
    if requested == "":
        return "auto"
    if requested not in {"auto", "openai_gpt_image", "gemini_image", "mock_image"}:
        return "auto"
    return requested
