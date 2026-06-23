"""V3 independent navigation entry contract."""

V3_NAV_ENTRY = {
    "id": "alchemy_creative_agent_3_0",
    "label": "Alchemy Creative Agent 3.0",
    "title_bar_entry": True,
    "route": "/creative-agent-v3",
    "owned_by": "alchemy_creative_agent_3_0",
}


def get_navigation_entry() -> dict:
    return dict(V3_NAV_ENTRY)

