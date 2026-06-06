from __future__ import annotations

from app.config import settings
from app.schemas import ImageJob, ImageOutput, ImageReviewDecision
from app.services.ids import new_id

try:
    from agents import Agent  # type: ignore

    VISUAL_REVIEW_SDK_AVAILABLE = True
except Exception:
    Agent = None  # type: ignore
    VISUAL_REVIEW_SDK_AVAILABLE = False


class VisualReviewAgentRuntime:
    """OpenAI Agents SDK boundary for image quality review.

    The first productionization step keeps live vision calls disabled by
    default, but routes review decisions through a dedicated agent surface so a
    vision-capable Runner can be attached without changing output schemas.
    """

    def __init__(self) -> None:
        self.sdk_available = VISUAL_REVIEW_SDK_AVAILABLE
        self.agent = self._build_agent()

    def refresh_runtime_config(self) -> None:
        self.agent = self._build_agent()

    def refine(self, output: ImageOutput, job: ImageJob, baseline: ImageReviewDecision) -> ImageReviewDecision:
        if not settings.output_review_agent_enabled:
            return baseline.model_copy(update={"reviewer": "rule-reviewer", "analysis_mode": "metadata_rules"})

        notes = list(baseline.notes)
        risks = list(baseline.detected_risks)
        directives = list(baseline.revision_directives)
        trace_id = new_id("review_trace")

        if not self.sdk_available or self.agent is None:
            notes.append("VisualCriticAgent is enabled but the OpenAI Agents SDK is not available in this runtime.")
            risks.append("visual_review_agent_unavailable")
            return baseline.model_copy(
                update={
                    "notes": _dedupe(notes),
                    "detected_risks": _dedupe(risks),
                    "revision_directives": _dedupe(directives),
                    "reviewer": "visual-critic-agent-unavailable",
                    "analysis_mode": "metadata_rules",
                    "agent_trace_id": trace_id,
                }
            )

        notes.append(
            "VisualCriticAgent SDK boundary executed with provider metadata and prompt evidence; live vision-model inspection is not configured yet."
        )
        directives.append("Inspect the rendered image with a vision-capable review model before automatic customer delivery.")
        if output.metadata.get("mock"):
            risks.append("visual_review_used_mock_asset")
        if job.prompt_plan.risk_notes:
            risks.append("prompt_plan_risk_notes_present")

        return baseline.model_copy(
            update={
                "notes": _dedupe(notes),
                "detected_risks": _dedupe(risks),
                "revision_directives": _dedupe(directives),
                "reviewer": "visual-critic-agent",
                "analysis_mode": "sdk_agent_metadata_fallback",
                "agent_trace_id": trace_id,
            }
        )

    def status(self) -> dict:
        return {
            "enabled": settings.output_review_agent_enabled,
            "sdk_available": self.sdk_available,
            "agent_name": "VisualCriticAgent",
            "model": settings.output_review_agent_model or settings.default_agent_model,
            "analysis_mode": "sdk_agent_metadata_fallback"
            if settings.output_review_agent_enabled and self.sdk_available
            else "metadata_rules",
        }

    def _build_agent(self):
        if not VISUAL_REVIEW_SDK_AVAILABLE or Agent is None:
            return None
        return Agent(
            name="VisualCriticAgent",
            model=settings.output_review_agent_model or settings.default_agent_model,
            instructions=(
                "Review generated image outputs against the user goal, prompt plan, safety constraints, "
                "and provider evidence. Prefer structured quality notes, concrete revision directives, "
                "and conservative escalation when the actual pixels are not available."
            ),
        )


visual_review_agent = VisualReviewAgentRuntime()


def apply_visual_review_agent(output: ImageOutput, job: ImageJob, baseline: ImageReviewDecision) -> ImageReviewDecision:
    return visual_review_agent.refine(output, job, baseline)


def get_visual_review_agent_status() -> dict:
    return visual_review_agent.status()


def refresh_visual_review_agent() -> None:
    visual_review_agent.refresh_runtime_config()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique
