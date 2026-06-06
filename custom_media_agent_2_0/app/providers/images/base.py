from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.schemas import ImagePromptPlan, ProviderInputImage


class V2ImageProviderCapabilities(BaseModel):
    provider: str
    configured: bool
    models: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    input_roles: list[str] = Field(default_factory=list)
    limits: dict[str, Any] = Field(default_factory=dict)
    is_mock: bool = False
    reason: str | None = None


class V2ImageProviderOutput(BaseModel):
    b64_json: str
    mime_type: str = "image/png"
    format: str = "png"
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class V2ImageProviderRequest(BaseModel):
    run_id: str | None = None
    prompt_plan: ImagePromptPlan
    input_images: list[ProviderInputImage] = Field(default_factory=list)


class V2ImageProviderResult(BaseModel):
    provider: str
    model: str
    outputs: list[V2ImageProviderOutput]
    raw_response_summary: dict[str, Any] = Field(default_factory=dict)


class V2ImageProviderError(Exception):
    code = "provider_error"
    retryable = False

    def __init__(self, message: str, *, provider: str | None = None, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.provider = provider
        self.detail = detail or {}


class V2ImageProviderNotConfiguredError(V2ImageProviderError):
    code = "provider_not_configured"


class V2ImageProviderRuntimeError(V2ImageProviderError):
    code = "provider_runtime_error"


class V2ImageProviderRateLimitError(V2ImageProviderError):
    code = "provider_rate_limit"
    retryable = True


class V2ImageProvider(Protocol):
    name: str

    async def capabilities(self) -> V2ImageProviderCapabilities: ...

    async def generate(self, request: V2ImageProviderRequest) -> V2ImageProviderResult: ...
