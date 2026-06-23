"""Rule-based commercial brief builder."""

from __future__ import annotations

from .base import AgentResult, BaseAgent
from ..creative_core.rules import (
    RULE_VERSION,
    business_goal_for_scenario,
    default_platforms_for_industry,
    detect_commercial_hooks,
    detect_industry,
    detect_negative_styles,
    detect_platforms,
    detect_scenario,
    detect_selling_points,
    detect_visual_tones,
    normalize_input,
    stable_id,
)
from ..schemas import CommercialBrief, CreativeJob


class CommercialStrategyAgent(BaseAgent):
    agent_name = "CommercialStrategyAgent"

    def create_brief(self, job: CreativeJob) -> AgentResult[CommercialBrief]:
        normalized = str(job.metadata.get("normalized_input") or normalize_input(job.raw_user_input))
        industry = detect_industry(normalized)
        scenario = detect_scenario(normalized)
        platforms = detect_platforms(normalized) or default_platforms_for_industry(industry)
        visual_tone = detect_visual_tones(normalized, industry)
        risks = detect_negative_styles(normalized)
        brief = CommercialBrief(
            brief_id=stable_id("brief", job.job_id, scenario, industry.value),
            job_id=job.job_id,
            industry=industry,
            scenario=scenario,
            business_goal=business_goal_for_scenario(scenario),
            target_platforms=platforms,
            target_audience="local commercial consumers" if industry.value.startswith("restaurant") else "platform shoppers or local customers",
            commercial_hooks=detect_commercial_hooks(normalized, scenario, industry),
            selling_points=detect_selling_points(normalized),
            visual_tone=visual_tone,
            copy_strategy="short Chinese commercial headline with clear offer and CTA",
            platform_notes={"detected_from_input": [platform.value for platform in detect_platforms(normalized)]},
            risks=risks,
            confidence=0.82 if industry.value != "unknown" else 0.62,
            metadata=self.metadata(rules_version=RULE_VERSION, normalized_input=normalized),
        )
        return AgentResult(output=brief, reasoning_summary="Built deterministic CommercialBrief from V3 rules.")

