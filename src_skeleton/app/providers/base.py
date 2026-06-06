from __future__ import annotations

from typing import Protocol, Any
from pydantic import BaseModel, Field
from app.schemas import CostEstimate, ImageGenerationRequest, ImageGenerationResult, VideoGenerationRequest


class ProviderCapabilities(BaseModel):
    provider: str
    configured: bool
    models: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    model_capabilities: list[dict[str, Any]] = Field(default_factory=list)
    advanced_asset_roles: list[str] = Field(default_factory=list)
    limits: dict[str, Any] = Field(default_factory=dict)
    is_mock: bool = False
    reason: str | None = None


class ProviderRuntimeError(Exception):
    code = "provider_error"
    retryable = False

    def __init__(self, message: str, *, provider: str | None = None, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.provider = provider
        self.detail = detail or {}


class ProviderNotConfiguredError(ProviderRuntimeError):
    code = "provider_not_configured"


class ProviderCapabilityMismatchError(ProviderRuntimeError):
    code = "provider_capability_mismatch"


class ProviderRateLimitError(ProviderRuntimeError):
    code = "rate_limit_error"
    retryable = True


class ImageProvider(Protocol):
    name: str

    async def capabilities(self) -> ProviderCapabilities: ...
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult: ...
    async def edit(self, request: ImageGenerationRequest) -> ImageGenerationResult: ...
    async def estimate_cost(self, request: ImageGenerationRequest) -> CostEstimate: ...


class VideoProvider(Protocol):
    name: str

    async def capabilities(self) -> ProviderCapabilities: ...
    async def create_task(self, request: VideoGenerationRequest) -> dict[str, Any]: ...
    async def get_task(self, provider_task_id: str) -> dict[str, Any]: ...
    async def cancel_task(self, provider_task_id: str) -> None: ...
