"""V3 vertical agent extension package."""

from .ai_manga_drama_pack import AIMangaDramaAgentFamily
from .base import VerticalAgentPack
from .brand_ip_pack import BrandIPAgentFamily
from .default_commercial_pack import DefaultCommercialPack
from .ecommerce_pack import EcommerceAgentFamily
from .local_service_pack import LocalServiceAgentFamily
from .registry import VerticalAgentRegistry
from .restaurant_pack import RestaurantAgentFamily

__all__ = [
    "AIMangaDramaAgentFamily",
    "BrandIPAgentFamily",
    "DefaultCommercialPack",
    "EcommerceAgentFamily",
    "LocalServiceAgentFamily",
    "RestaurantAgentFamily",
    "VerticalAgentPack",
    "VerticalAgentRegistry",
]

