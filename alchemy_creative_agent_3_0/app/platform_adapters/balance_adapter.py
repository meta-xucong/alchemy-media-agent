"""V3-owned balance boundary adapter stub."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class V3BalanceEstimate:
    credits_required: int
    currency: str
    metadata: dict


class V3BalanceAdapter:
    adapter_name = "v3_balance_adapter"

    def estimate_planning_cost(self, asset_count: int) -> V3BalanceEstimate:
        return V3BalanceEstimate(
            credits_required=0,
            currency="credits",
            metadata={"runtime_mode": "planning_only", "asset_count": asset_count},
        )

    def estimate_generation_cost(self, asset_count: int, candidate_count: int = 4) -> V3BalanceEstimate:
        return V3BalanceEstimate(
            credits_required=0,
            currency="credits",
            metadata={
                "runtime_mode": "mock_generation",
                "asset_count": asset_count,
                "candidate_count": candidate_count,
            },
        )

    def has_available_credits(self, credits_required: int) -> bool:
        return credits_required == 0
