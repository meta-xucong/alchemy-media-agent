"""V3-owned generation provider contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..creative_core.rules import stable_id
from ..condition_engine.providers import ProviderCapabilities
from ..schemas import AssetSpec, CandidateResult, ConditionPlan, GenerationPlan, LayoutPlan, PromptCompilationResult


class GenerationRequest(BaseModel):
    asset_spec: AssetSpec | None = None
    layout_plan: LayoutPlan | None = None
    prompt_compilation: PromptCompilationResult
    condition_plan: ConditionPlan
    generation_plan: GenerationPlan
    metadata: dict = Field(default_factory=dict)


class GenerationResponse(BaseModel):
    candidates: list[CandidateResult]
    provider_metadata: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class GenerationProvider:
    """Provider interface for V3 generation and deterministic mock generation."""

    provider_name = "generation_provider"
    provider_version = "v3.2-generation-loop-mvp"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.provider_name,
            version=self.provider_version,
            supports_generation=True,
            supports_batch=True,
            requires_gpu=False,
            requires_network=False,
            is_deterministic=True,
        )

    def is_available(self) -> bool:
        return True

    def health_check(self) -> dict:
        return {"provider_name": self.provider_name, "available": self.is_available()}

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        raise NotImplementedError


class PlanningOnlyGenerationProvider(GenerationProvider):
    provider_name = "planning_only_generation_provider"
    provider_version = "v3.0-foundation"

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        candidate = CandidateResult(
            candidate_id=stable_id("candidate", request.generation_plan.asset_id, request.prompt_compilation.prompt_compilation_id),
            asset_id=request.generation_plan.asset_id,
            provider=self.provider_name,
            prompt_compilation_id=request.prompt_compilation.prompt_compilation_id,
            condition_plan_id=request.condition_plan.condition_plan_id,
            is_mock=True,
            metadata={"runtime_mode": "planning_only", "provider_version": self.provider_version},
        )
        return GenerationResponse(
            candidates=[candidate],
            provider_metadata={"provider_name": self.provider_name, "provider_version": self.provider_version},
            warnings=["No real image generation is executed in V3.0 foundation."],
        )


class MockGenerationProvider(GenerationProvider):
    """Deterministic V3.2 candidate provider used by the closed-loop MVP."""

    provider_name = "mock_generation_provider"
    provider_version = "v3.2-generation-loop-mvp"

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        candidate_count = max(1, request.generation_plan.candidate_count)
        refine_round = int(request.metadata.get("refine_round", request.generation_plan.metadata.get("refine_round", 0) or 0))
        profile = str(request.generation_plan.metadata.get("mock_profile", request.metadata.get("mock_profile", "balanced")))
        candidates: list[CandidateResult] = []
        warnings: list[str] = []

        for index in range(candidate_count):
            quality_score, problem_codes = self._candidate_profile(profile, index, refine_round)
            hard_failure = "provider_failure" in problem_codes or "missing_product_area" in problem_codes
            candidate_id = stable_id(
                "candidate",
                request.generation_plan.asset_id,
                request.prompt_compilation.prompt_compilation_id,
                self.provider_name,
                refine_round,
                index,
                profile,
            )
            candidates.append(
                CandidateResult(
                    candidate_id=candidate_id,
                    asset_id=request.generation_plan.asset_id,
                    uri=f"mock://v3/{candidate_id}",
                    provider=self.provider_name,
                    prompt_compilation_id=request.prompt_compilation.prompt_compilation_id,
                    condition_plan_id=request.condition_plan.condition_plan_id,
                    is_mock=True,
                    metadata={
                        "runtime_mode": "mock_generation",
                        "provider_version": self.provider_version,
                        "candidate_index": index,
                        "refine_round": refine_round,
                        "mock_profile": profile,
                        "mock_quality_score": quality_score,
                        "forced_problem_codes": problem_codes,
                        "hard_failure": hard_failure,
                        "asset_id": request.generation_plan.asset_id,
                    },
                )
            )
        if profile == "all_hard_failure":
            warnings.append("Mock profile produced only hard-failure candidates.")
        return GenerationResponse(
            candidates=candidates,
            provider_metadata={
                "provider_name": self.provider_name,
                "provider_version": self.provider_version,
                "runtime_mode": "mock_generation",
                "refine_round": refine_round,
                "mock_profile": profile,
            },
            warnings=warnings,
        )

    def _candidate_profile(self, profile: str, index: int, refine_round: int) -> tuple[float, list[str]]:
        if profile == "needs_refinement":
            if refine_round == 0:
                return (0.61 - index * 0.02, ["commercial_hook_missing"] if index == 0 else ["fake_text_risk"])
            return (0.86 - index * 0.03, [])
        if profile == "exhaust_retries":
            return (0.61 - index * 0.02, ["commercial_hook_missing"] if index == 0 else ["brand_style_missing"])
        if profile == "hard_failure_first":
            if index == 0:
                return (0.30, ["missing_product_area"])
            return (0.84 - index * 0.02, [])
        if profile == "all_hard_failure":
            return (0.25, ["missing_product_area"])
        if index == 0:
            return (0.86, [])
        if index == 1:
            return (0.80, [])
        if index == 2:
            return (0.67, ["commercial_hook_missing"])
        return (0.42, ["provider_failure"])
