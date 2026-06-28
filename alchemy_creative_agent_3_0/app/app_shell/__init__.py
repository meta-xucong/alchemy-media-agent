"""V3 app shell boundary package."""

from .minimal_ui import get_minimal_ui_contract, render_minimal_job_view
from .navigation import get_navigation_entry
from .routes import API_NAMESPACE, PRODUCT_API_NAMESPACE, get_product_route_aliases, get_route_contracts
from .scenario_hub import get_scenario_hub_contract
from .ui_contracts import get_ui_contract

__all__ = [
    "API_NAMESPACE",
    "PRODUCT_API_NAMESPACE",
    "get_minimal_ui_contract",
    "get_navigation_entry",
    "get_product_route_aliases",
    "get_route_contracts",
    "get_scenario_hub_contract",
    "get_ui_contract",
    "render_minimal_job_view",
]
