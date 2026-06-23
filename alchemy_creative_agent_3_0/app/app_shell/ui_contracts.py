"""V3 UI boundary contract placeholders."""

from .minimal_ui import get_minimal_ui_contract

V3_UI_CONTRACT = {
    "entry": "independent_v3_ui",
    "default_mode": "natural_language_commercial_series",
    "calls_only_v3_api_namespace": "/api/v3/creative-agent",
    "does_not_share_v1_v2_workflow_state": True,
    "minimal_ux": get_minimal_ui_contract(),
}


def get_ui_contract() -> dict:
    return dict(V3_UI_CONTRACT)
