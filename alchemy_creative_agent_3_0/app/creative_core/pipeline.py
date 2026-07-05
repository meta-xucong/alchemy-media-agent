"""Public V3 planning pipeline entrypoint."""

from __future__ import annotations

from .central_brain import CentralCreativeBrain
from ..brand_memory.profile_service import BrandProfileService
from ..generation_router import GenerationRouter
from ..schemas import PlanningResult, ProviderStrategy


def run_creative_planning(
    user_input: str,
    optional_brand_id: str | None = None,
    optional_template_id: str | None = None,
    brand_profile_service: BrandProfileService | None = None,
    runtime_metadata: dict | None = None,
    generation_router: GenerationRouter | None = None,
) -> PlanningResult:
    optional_template_id, brand_profile_service = _coerce_legacy_brand_service_arg(
        optional_template_id,
        brand_profile_service,
    )
    brain = CentralCreativeBrain(
        brand_profile_service=brand_profile_service,
        generation_router=generation_router,
    )
    return brain.run_creative_planning(
        user_input=user_input,
        optional_brand_id=optional_brand_id,
        optional_template_id=optional_template_id,
        runtime_metadata=runtime_metadata,
    )


def run_generation_loop(
    user_input: str,
    optional_brand_id: str | None = None,
    optional_template_id: str | None = None,
    brand_profile_service: BrandProfileService | None = None,
    mock_profile: str = "balanced",
    apply_memory_update: bool = False,
    provider_strategy: ProviderStrategy = ProviderStrategy.MOCK_GENERATION,
    runtime_metadata: dict | None = None,
    generation_router: GenerationRouter | None = None,
) -> PlanningResult:
    optional_template_id, brand_profile_service = _coerce_legacy_brand_service_arg(
        optional_template_id,
        brand_profile_service,
    )
    brain = CentralCreativeBrain(
        brand_profile_service=brand_profile_service,
        generation_router=generation_router,
    )
    return brain.run_generation_loop(
        user_input=user_input,
        optional_brand_id=optional_brand_id,
        optional_template_id=optional_template_id,
        mock_profile=mock_profile,
        apply_memory_update=apply_memory_update,
        provider_strategy=provider_strategy,
        runtime_metadata=runtime_metadata,
    )


def _coerce_legacy_brand_service_arg(
    optional_template_id: str | BrandProfileService | None,
    brand_profile_service: BrandProfileService | None,
) -> tuple[str | None, BrandProfileService | None]:
    if isinstance(optional_template_id, BrandProfileService) and brand_profile_service is None:
        return None, optional_template_id
    return optional_template_id, brand_profile_service
