from __future__ import annotations

from app.config import settings
from app.schemas import VideoGenerationRequest
from app.providers.base import ProviderCapabilities, ProviderNotConfiguredError


class SeedanceVideoProvider:
    name = "seedance"

    async def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider=self.name,
            configured=False,
            models=["seedance-2.0"],
            operations=["text_to_video", "image_to_video", "reference_to_video"],
            limits={"sync_mode": "async_task", "note": "Live Seedance task API wiring is not implemented in this MVP."},
            reason="Seedance video provider is a documented async placeholder until live task API wiring is implemented.",
        )

    async def create_task(self, request: VideoGenerationRequest) -> dict:
        if not settings.byteplus_api_key:
            return {"status": "provider_not_configured", "experimental": True}
        # Fill endpoint and payload from the current BytePlus/Volcengine docs.
        raise ProviderNotConfiguredError("Seedance live video task creation is not wired in MVP.", provider=self.name)

    async def get_task(self, provider_task_id: str) -> dict:
        return {
            "provider": self.name,
            "provider_task_id": provider_task_id,
            "status": "provider_not_configured",
            "experimental": True,
        }

    async def cancel_task(self, provider_task_id: str) -> None:
        return None
