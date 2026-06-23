"""Generation router wrapper."""

from __future__ import annotations

from .providers import GenerationProvider, GenerationRequest, GenerationResponse, MockGenerationProvider, PlanningOnlyGenerationProvider
from ..schemas import ProviderStrategy


class GenerationRouter:
    def __init__(self, provider: GenerationProvider | None = None) -> None:
        self.provider = provider
        self.providers: dict[ProviderStrategy, GenerationProvider] = {
            ProviderStrategy.PLANNING_ONLY: PlanningOnlyGenerationProvider(),
            ProviderStrategy.MOCK_GENERATION: MockGenerationProvider(),
        }

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        provider = self.provider or self.providers.get(request.generation_plan.provider_strategy)
        if provider is None:
            provider = self.providers[ProviderStrategy.PLANNING_ONLY]
        return provider.generate(request)
