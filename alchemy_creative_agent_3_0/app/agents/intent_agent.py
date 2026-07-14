"""Intent agent for creating CreativeJob from natural language."""

from __future__ import annotations

from .base import AgentResult, BaseAgent
from ..creative_core.rules import (
    RULE_VERSION,
    detect_continuation_request,
    detect_industry,
    detect_platforms,
    normalize_input,
    stable_id,
)
from ..schemas import CreativeJob, Locale


class IntentAgent(BaseAgent):
    agent_name = "IntentAgent"

    def create_job(
        self,
        raw_user_input: str,
        optional_brand_id: str | None = None,
        optional_template_id: str | None = None,
        uploaded_asset_ids: list[str] | None = None,
        locale: Locale = Locale.ZH_CN,
        job_instance_id: str | None = None,
    ) -> AgentResult[CreativeJob]:
        normalized = normalize_input(raw_user_input)
        requires_clarification = not normalized
        industry = detect_industry(normalized)
        platforms = detect_platforms(normalized)
        job = CreativeJob(
            # A Product API submission is an append-only event, not an implicit
            # deduplication key. Direct, deterministic planning callers keep
            # their historical stable ID by omitting this value; the Product
            # API supplies an opaque server-owned instance ID for every root
            # or continuation Job so an equal prompt cannot overwrite an
            # earlier provider/review history.
            job_id=stable_id(
                "job",
                raw_user_input,
                optional_brand_id,
                optional_template_id,
                job_instance_id,
            ),
            raw_user_input=raw_user_input,
            locale=locale,
            optional_brand_id=optional_brand_id,
            optional_template_id=optional_template_id,
            uploaded_asset_ids=uploaded_asset_ids or [],
            requires_clarification=requires_clarification,
            clarification_questions=["Please describe the commercial visual you need."] if requires_clarification else [],
            metadata=self.metadata(
                normalized_input=normalized,
                inferred_industry=industry.value,
                detected_platforms=[platform.value for platform in platforms],
                continuation_request=detect_continuation_request(normalized),
                rules_version=RULE_VERSION,
            ),
        )
        return AgentResult(output=job, reasoning_summary="Created V3 CreativeJob from deterministic intent rules.")
