"""Unregistered Photography vertical-agent skeleton for the P1 milestone."""

from __future__ import annotations

from ..schemas import CommercialBrief, CreativeJob
from .base import VerticalAgentPack


class PhotographyAgentFamily(VerticalAgentPack):
    """Schema-preserving placeholder that cannot win selection while inactive."""

    name = "photography_agent_family"
    supported_industries: list[str] = []
    supported_scenarios = ["photography"]
    activation_ready = False

    def match(self, creative_job: CreativeJob, commercial_brief: CommercialBrief | None = None) -> float:
        del creative_job, commercial_brief
        return 0.0

    def metadata(self) -> dict[str, object]:
        return {
            **super().metadata(),
            "activation_ready": False,
            "registered_in_default_vertical_registry": False,
            "phase": "P1",
            "named_profile_selection": "user_explicit_ui_only",
            "contributes_runtime_behavior": False,
        }
