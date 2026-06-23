"""Vertical agent registry for V3 foundation."""

from __future__ import annotations

from .ai_manga_drama_pack import AIMangaDramaAgentFamily
from .base import VerticalAgentPack
from .brand_ip_pack import BrandIPAgentFamily
from .default_commercial_pack import DefaultCommercialPack
from .ecommerce_pack import EcommerceAgentFamily
from .local_service_pack import LocalServiceAgentFamily
from .restaurant_pack import RestaurantAgentFamily
from ..schemas import CommercialBrief, CreativeJob


class VerticalAgentRegistry:
    def __init__(self, packs: list[VerticalAgentPack] | None = None) -> None:
        self.default_pack = DefaultCommercialPack()
        self.packs = packs or [
            EcommerceAgentFamily(),
            RestaurantAgentFamily(),
            LocalServiceAgentFamily(),
            BrandIPAgentFamily(),
            AIMangaDramaAgentFamily(),
            self.default_pack,
        ]

    def register(self, pack: VerticalAgentPack) -> None:
        self.packs.append(pack)

    def select_pack(self, creative_job: CreativeJob, commercial_brief: CommercialBrief | None = None) -> VerticalAgentPack:
        best_pack = self.default_pack
        best_score = -1.0
        for pack in self.packs:
            score = pack.match(creative_job, commercial_brief)
            if score > best_score:
                best_pack = pack
                best_score = score
        return best_pack if best_score > 0 else self.default_pack

