from __future__ import annotations

from app.config import settings
from app.providers.doubao_image import DoubaoImageProvider
from app.providers.openai_image import OpenAIGPTImageProvider
from app.providers.gemini_image import GeminiImageProvider
from app.providers.identity_sidecar import IdentityNativeSidecarProvider
from app.providers.mock_image import MockImageProvider
from app.providers.seedance_video import SeedanceVideoProvider
from app.providers.base import ProviderCapabilityMismatchError, ProviderNotConfiguredError


class ProviderRegistry:
    def __init__(self):
        self.image_providers = {
            "openai_gpt_image": OpenAIGPTImageProvider(),
            "doubao_image": DoubaoImageProvider(),
            "gemini_image": GeminiImageProvider(),
            "identity_native_sidecar": IdentityNativeSidecarProvider(),
        }
        if settings.mock_image_provider_enabled:
            self.image_providers["mock_image"] = MockImageProvider()
        self.video_providers = {
            "seedance": SeedanceVideoProvider(),
        }

    def image(self, preferred: str | None = None):
        if preferred:
            return self._require_image(preferred)
        return self._require_image(settings.default_image_provider)

    async def select_image(self, preferred: str | None = None):
        provider_name = preferred or settings.default_image_provider
        provider = self._require_image(provider_name)
        caps = await provider.capabilities()
        if caps.configured:
            return provider
        fallback_name = self.alternate_image_name(provider_name)
        if fallback_name:
            fallback = self._require_image(fallback_name)
            fallback_caps = await fallback.capabilities()
            if fallback_caps.configured:
                return fallback
        if preferred:
            raise ProviderNotConfiguredError(caps.reason or "Provider is not configured.", provider=provider.name)
        if settings.mock_image_provider_enabled and "mock_image" in self.image_providers:
            return self.image_providers["mock_image"]
        raise ProviderNotConfiguredError(caps.reason or "Default image provider is not configured.", provider=provider.name)

    def video(self, preferred: str | None = None):
        provider_name = preferred or settings.default_video_provider
        if provider_name not in self.video_providers:
            raise ProviderCapabilityMismatchError(f"Unknown video provider: {provider_name}", provider=provider_name)
        return self.video_providers[provider_name]

    async def list_capabilities(self):
        image_caps = [await provider.capabilities() for provider in self.image_providers.values()]
        video_caps = [await provider.capabilities() for provider in self.video_providers.values()]
        return {"image": image_caps, "video": video_caps}

    def _require_image(self, provider_name: str):
        if provider_name not in self.image_providers:
            raise ProviderCapabilityMismatchError(f"Unknown image provider: {provider_name}", provider=provider_name)
        return self.image_providers[provider_name]

    def alternate_image_name(self, provider_name: str | None) -> str | None:
        if (
            provider_name == "openai_gpt_image"
            and "gemini_image" in self.image_providers
            and settings.gemini_image_generation_enabled
        ):
            return "gemini_image"
        if provider_name == "gemini_image" and "openai_gpt_image" in self.image_providers:
            return "openai_gpt_image"
        return None


registry = ProviderRegistry()
