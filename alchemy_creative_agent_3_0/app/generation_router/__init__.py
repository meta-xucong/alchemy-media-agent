"""V3 generation routing package."""

from .candidates import candidate_ids, has_hard_failure, rank_evaluated_candidates, select_best_candidate
from .providers import (
    build_provider_generation_request,
    GenerationProvider,
    GenerationRequest,
    GenerationResponse,
    MockGenerationProvider,
    McpMaterializationProvider,
    PlanningOnlyGenerationProvider,
    ProductionImageGenerationProvider,
    safe_runtime_execution_budget,
)
from .router import GenerationRouter

__all__ = [
    "GenerationProvider",
    "GenerationRequest",
    "GenerationResponse",
    "build_provider_generation_request",
    "GenerationRouter",
    "MockGenerationProvider",
    "McpMaterializationProvider",
    "PlanningOnlyGenerationProvider",
    "ProductionImageGenerationProvider",
    "safe_runtime_execution_budget",
    "candidate_ids",
    "has_hard_failure",
    "rank_evaluated_candidates",
    "select_best_candidate",
]
