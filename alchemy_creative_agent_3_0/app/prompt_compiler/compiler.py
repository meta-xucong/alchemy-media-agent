"""Prompt compiler facade for V3 foundation."""

from __future__ import annotations

from ..agents.prompt_compiler_agent import PromptCompilerAgent
from ..schemas import BrandProfile, CommercialBrief, CreativePlan, LayoutPlan, PromptCompilationResult


class PromptCompiler:
    def __init__(self) -> None:
        self.agent = PromptCompilerAgent()

    def compile(
        self,
        brief: CommercialBrief,
        creative_plan: CreativePlan,
        layout_plan: LayoutPlan,
        brand_profile: BrandProfile,
    ) -> PromptCompilationResult:
        return self.agent.compile_prompt(brief, creative_plan, layout_plan, brand_profile).output

