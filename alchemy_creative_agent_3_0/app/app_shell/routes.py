"""V3-owned route namespace contract."""

API_NAMESPACE = "/api/v3/creative-agent"
PRODUCT_API_NAMESPACE = "/v3"

ROUTE_CONTRACTS = {
    "scenario_hub": f"{API_NAMESPACE}/scenarios",
    "photographer_profiles": f"{API_NAMESPACE}/scenarios/photography/photographer-profiles",
    "history": f"{API_NAMESPACE}/history",
    "projects": f"{API_NAMESPACE}/projects",
    "get_project": f"{API_NAMESPACE}/projects/{{project_id}}",
    "create_project_job": f"{API_NAMESPACE}/projects/{{project_id}}/jobs",
    "create_photography_role_continuation": f"{API_NAMESPACE}/projects/{{project_id}}/jobs/{{parent_job_id}}/photography-roles/{{role_id}}/continuations",
    "get_photography_role_delivery": f"{API_NAMESPACE}/projects/{{project_id}}/jobs/{{root_job_id}}/photography-roles/{{role_id}}/delivery",
    "project_timeline": f"{API_NAMESPACE}/projects/{{project_id}}/timeline",
    # Historical project-scoped People Asset routes remain readable only.
    # New Visual Asset Library and project-binding routes below own all new
    # Professional/asset writes under Doc173.
    "project_people_assets": f"{API_NAMESPACE}/projects/{{project_id}}/people-assets",
    "project_people_asset": f"{API_NAMESPACE}/projects/{{project_id}}/people-assets/{{people_asset_id}}",
    "prepare_project_people_asset": f"{API_NAMESPACE}/projects/{{project_id}}/people-assets/{{people_asset_id}}/prepare",
    "activate_project_people_asset": f"{API_NAMESPACE}/projects/{{project_id}}/people-assets/{{people_asset_id}}/activate",
    "visual_assets": f"{API_NAMESPACE}/visual-assets",
    "visual_asset": f"{API_NAMESPACE}/visual-assets/{{visual_asset_id}}",
    "prepare_visual_asset": f"{API_NAMESPACE}/visual-assets/{{visual_asset_id}}/prepare",
    "activate_visual_asset": f"{API_NAMESPACE}/visual-assets/{{visual_asset_id}}/activate",
    "prepare_visual_asset_character_card": f"{API_NAMESPACE}/visual-assets/{{visual_asset_id}}/character-card/prepare",
    "activate_visual_asset_character_card": f"{API_NAMESPACE}/visual-assets/{{visual_asset_id}}/character-card/activate",
    "archive_visual_asset": f"{API_NAMESPACE}/visual-assets/{{visual_asset_id}}/archive",
    "project_visual_asset_bindings": f"{API_NAMESPACE}/projects/{{project_id}}/visual-asset-bindings",
    "project_visual_asset_binding": (
        f"{API_NAMESPACE}/projects/{{project_id}}/visual-asset-bindings/{{binding_id}}"
    ),
    "create_job": f"{API_NAMESPACE}/jobs",
    "get_job": f"{API_NAMESPACE}/jobs/{{job_id}}",
    "generate": f"{API_NAMESPACE}/jobs/{{job_id}}/generate",
    "select": f"{API_NAMESPACE}/jobs/{{job_id}}/select",
    "get_brand": f"{API_NAMESPACE}/brands/{{brand_id}}",
    "create_brand": f"{API_NAMESPACE}/brands",
    "estimate_balance": f"{API_NAMESPACE}/balance/estimate",
}

PRODUCT_ROUTE_ALIASES = {
    "create_creative_job": f"{PRODUCT_API_NAMESPACE}/creative-jobs",
    "get_creative_job": f"{PRODUCT_API_NAMESPACE}/creative-jobs/{{job_id}}",
    "generate_creative_job": f"{PRODUCT_API_NAMESPACE}/creative-jobs/{{job_id}}/generate",
    "select_creative_job": f"{PRODUCT_API_NAMESPACE}/creative-jobs/{{job_id}}/select",
    "get_product_brand": f"{PRODUCT_API_NAMESPACE}/brands/{{brand_id}}",
    "create_product_brand": f"{PRODUCT_API_NAMESPACE}/brands",
}


def get_route_contracts() -> dict:
    return {**ROUTE_CONTRACTS, **PRODUCT_ROUTE_ALIASES}


def get_product_route_aliases() -> dict:
    return dict(PRODUCT_ROUTE_ALIASES)
