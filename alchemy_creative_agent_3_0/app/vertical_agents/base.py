"""Vertical agent extension contracts for V3."""

from __future__ import annotations

from typing import Any

from ..schemas import CommercialBrief, CreativeJob


class VerticalAgentPack:
    name = "vertical_agent_pack"
    supported_industries: list[str] = []
    supported_scenarios: list[str] = []

    def match(self, creative_job: CreativeJob, commercial_brief: CommercialBrief | None = None) -> float:
        industry = self._industry_value(commercial_brief)
        scenario = self._scenario_value(commercial_brief)
        if industry in self.supported_industries:
            return 0.8
        if scenario in self.supported_scenarios:
            return 0.6
        return 0.0

    def refine_commercial_brief(self, context: Any) -> Any:
        return context.commercial_brief

    def refine_creative_plan(self, context: Any) -> Any:
        return context.creative_plan

    def refine_series_plan(self, context: Any) -> Any:
        return context.series_plan

    def refine_layout_plan(self, context: Any, layout_plan: Any) -> Any:
        return layout_plan

    def refine_prompt_compilation(self, context: Any, prompt_compilation: Any) -> Any:
        return prompt_compilation

    def refine_evaluation_policy(self, context: Any) -> dict[str, Any]:
        return {
            "pack": self.name,
            "mode": "schema_preserving_default",
            "commercial_score_delta": 0.0,
            "brand_consistency_score_delta": 0.0,
            "layout_score_delta": 0.0,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "selected_vertical_pack": self.name,
            "supported_industries": self.supported_industries,
            "supported_scenarios": self.supported_scenarios,
            "extends_v3_standard_schemas": True,
            "forks_runtime": False,
        }

    def _job_text(self, creative_job: CreativeJob | None) -> str:
        if creative_job is None:
            return ""
        return str(creative_job.metadata.get("normalized_input") or creative_job.raw_user_input).lower()

    def _industry_value(self, commercial_brief: CommercialBrief | None) -> str:
        if commercial_brief is None:
            return ""
        return str(getattr(commercial_brief.industry, "value", commercial_brief.industry))

    def _scenario_value(self, commercial_brief: CommercialBrief | None) -> str:
        if commercial_brief is None:
            return ""
        return str(commercial_brief.scenario)

    def _contains_any(self, text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword.lower() in text for keyword in keywords)

    def _append_unique(self, current: list[Any], additions: list[Any]) -> list[Any]:
        return list(dict.fromkeys([*current, *additions]))

    def _metadata(self, current: dict[str, Any], stage: str, **extra: Any) -> dict[str, Any]:
        entry = {
            "pack": self.name,
            "stage": stage,
            "extends_v3_standard_schemas": True,
            "forks_runtime": False,
            **extra,
        }
        return {
            **current,
            "selected_vertical_pack": self.name,
            "vertical_specializations": [*current.get("vertical_specializations", []), entry],
        }
