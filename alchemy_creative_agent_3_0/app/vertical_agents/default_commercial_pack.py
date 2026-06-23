"""Default commercial vertical pack."""

from .base import VerticalAgentPack


class DefaultCommercialPack(VerticalAgentPack):
    name = "default_commercial_pack"
    supported_industries = ["unknown", "local_service_general", "beverage", "hospitality"]
    supported_scenarios = ["brand_or_commercial_poster", "generic_promotion"]

    def match(self, creative_job, commercial_brief=None) -> float:
        return 0.1

