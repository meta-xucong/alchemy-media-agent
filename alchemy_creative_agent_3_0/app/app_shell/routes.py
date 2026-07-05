"""V3-owned route namespace contract."""

API_NAMESPACE = "/api/v3/creative-agent"
PRODUCT_API_NAMESPACE = "/v3"

ROUTE_CONTRACTS = {
    "scenario_hub": f"{API_NAMESPACE}/scenarios",
    "history": f"{API_NAMESPACE}/history",
    "projects": f"{API_NAMESPACE}/projects",
    "get_project": f"{API_NAMESPACE}/projects/{{project_id}}",
    "create_project_job": f"{API_NAMESPACE}/projects/{{project_id}}/jobs",
    "project_timeline": f"{API_NAMESPACE}/projects/{{project_id}}/timeline",
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
