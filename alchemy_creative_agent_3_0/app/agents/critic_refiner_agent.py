"""Critic and refinement agent stubs for V3.0."""

from __future__ import annotations

from .base import BaseAgent
from ..evaluation.refine_policy import RuleBasedRefinementProvider
from ..schemas import EvaluationReport, RefinementPlan


class CriticRefinerAgent(BaseAgent):
    agent_name = "CriticRefinerAgent"

    def __init__(self) -> None:
        self.refinement_provider = RuleBasedRefinementProvider()

    def propose_refinement(self, evaluation: EvaluationReport) -> RefinementPlan | None:
        return self.refinement_provider.propose_refinement(evaluation)

