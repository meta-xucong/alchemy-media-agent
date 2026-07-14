import base64
from io import BytesIO
from pathlib import Path
import shutil
from uuid import uuid4

from PIL import Image
import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.app_shell import (
    API_NAMESPACE,
    get_minimal_ui_contract,
    render_minimal_job_view,
)
from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.platform_adapters import V3BalanceAdapter, V3BalanceEstimate
from alchemy_creative_agent_3_0.app.product_api import (
    CreateBrandRequest,
    CreateCreativeJobRequest,
    GenerateJobRequest,
    ProductJobStatusValue,
    SelectResultRequest,
    V3ProductApiService,
)
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import PersistentProductJobStore
from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore
from alchemy_creative_agent_3_0.app.schemas import IndustryCategory, Platform


_RUNTIME_ROOTS: list[Path] = []


@pytest.fixture(autouse=True)
def _cleanup_runtime_product_api_stores():
    yield
    while _RUNTIME_ROOTS:
        root = _RUNTIME_ROOTS.pop()
        shutil.rmtree(root, ignore_errors=True)


def _test_store_root(name: str) -> Path:
    root = Path(__file__).resolve().parent / "_runtime_product_api" / f"{name}_{uuid4().hex}"
    root.mkdir(parents=True)
    _RUNTIME_ROOTS.append(root)
    return root


class TrackingBalanceAdapter(V3BalanceAdapter):
    adapter_name = "tracking_v3_balance_adapter"

    def __init__(self) -> None:
        self.estimated_asset_counts: list[int] = []
        self.checked_credits: list[int] = []

    def estimate_planning_cost(self, asset_count: int) -> V3BalanceEstimate:
        self.estimated_asset_counts.append(asset_count)
        return V3BalanceEstimate(
            credits_required=0,
            currency="credits",
            metadata={"runtime_mode": "tracking_test", "asset_count": asset_count},
        )

    def has_available_credits(self, credits_required: int) -> bool:
        self.checked_credits.append(credits_required)
        return True


def _service(name: str = "default") -> tuple[V3ProductApiService, BrandProfileService, TrackingBalanceAdapter]:
    brand_service = BrandProfileService(BrandProfileStore(_test_store_root(name)))
    balance = TrackingBalanceAdapter()
    return V3ProductApiService(brand_profile_service=brand_service, balance_adapter=balance), brand_service, balance


def test_v3_product_api_creates_and_retrieves_creative_job_status() -> None:
    service, _, balance = _service("create_job")

    created = service.create_job(
        {"user_input": "帮我做一组奶茶店夏季新品促销图，要清爽、高级一点，适合小红书和外卖平台。"}
    )
    fetched = service.get_job(created.job_id)

    assert created.status == ProductJobStatusValue.PLANNED
    assert fetched.job_id == created.job_id
    assert fetched.api_namespace == "/api/v3/creative-agent"
    assert fetched.routes["create_job"] == "/api/v3/creative-agent/jobs"
    assert fetched.routes["create_creative_job"] == "/v3/creative-jobs"
    assert fetched.routes["create_product_brand"] == "/v3/brands"
    assert fetched.campaign is not None
    assert fetched.campaign.business_goal
    assert fetched.asset_series
    assert fetched.style_continuation is not None
    assert fetched.style_continuation.enabled is False
    assert fetched.balance_estimate["metadata"]["adapter"] == "tracking_v3_balance_adapter"
    assert balance.estimated_asset_counts == [len(fetched.asset_series)]
    assert fetched.metadata["v3_independent_product_api"] is True


def test_gateway_managed_background_timeout_is_terminal_and_stale_worker_cannot_reopen_it() -> None:
    service, _, _ = _service("gateway_background_timeout")
    created = service.create_job({"user_input": "Create one clean still-life image."})

    pending = service.mark_job_generating(
        created.job_id,
        background_attempt_id="attempt_one",
        background_timeout_seconds=675,
    )
    stale_watchdog = service.mark_job_generation_timed_out(
        created.job_id,
        background_attempt_id="different_attempt",
        timeout_seconds=675,
    )
    timed_out = service.mark_job_generation_timed_out(
        created.job_id,
        background_attempt_id="attempt_one",
        timeout_seconds=675,
    )
    late_worker = service.generate_job(
        created.job_id,
        {
            "metadata": {
                "_v3_background_worker_claim": True,
                "_v3_background_generation_attempt_id": "attempt_one",
            }
        },
    )

    assert pending.status == ProductJobStatusValue.GENERATING
    assert pending.metadata["background_generation_watchdog"]["timeout_seconds"] == 675
    assert stale_watchdog.status == ProductJobStatusValue.GENERATING
    assert timed_out.status == ProductJobStatusValue.BLOCKED
    assert timed_out.metadata["provider_failure_retry"]["fresh_upstream_requests"] == 1
    assert timed_out.metadata["generation_lifecycle_timeout"]["timeout_seconds"] == 675
    assert "gateway_managed_lifecycle_timeout" in " ".join(timed_out.warnings)
    assert late_worker.status == ProductJobStatusValue.BLOCKED


def test_background_worker_failure_is_terminal_without_claiming_a_provider_timeout() -> None:
    service, _, _ = _service("background_worker_failure")
    created = service.create_job({"user_input": "Create one clean still-life image."})
    service.mark_job_generating(
        created.job_id,
        background_attempt_id="invalid_request_attempt",
        background_timeout_seconds=675,
    )

    failed = service.mark_job_generation_worker_failed(
        created.job_id,
        background_attempt_id="invalid_request_attempt",
        failure_code="background_generation_request_invalid",
    )
    late_worker = service.generate_job(
        created.job_id,
        {
            "metadata": {
                "_v3_background_worker_claim": True,
                "_v3_background_generation_attempt_id": "invalid_request_attempt",
            }
        },
    )

    assert failed.status == ProductJobStatusValue.BLOCKED
    assert failed.metadata["generation_lifecycle_failure"] == {
        "background_attempt_id": "invalid_request_attempt",
        "failure_code": "background_generation_request_invalid",
        "status": "terminal_failure",
        "owner": "v3_background_generation_worker",
    }
    assert "provider_failure_retry" not in failed.metadata
    assert "background_generation_request_invalid" in " ".join(failed.warnings)
    assert late_worker.status == ProductJobStatusValue.BLOCKED


def test_partial_persisted_output_remains_visible_when_a_later_role_blocks_the_job() -> None:
    output_store = V3GeneratedOutputStore(storage_root=_test_store_root("partial_output") / "outputs")
    brand_service = BrandProfileService(BrandProfileStore(_test_store_root("partial_output_brand")))
    service = V3ProductApiService(
        brand_profile_service=brand_service,
        balance_adapter=TrackingBalanceAdapter(),
        output_store=output_store,
    )
    created = service.create_job(
        {
            "user_input": "Create a two-image clean glass still-life set.",
            "metadata": {"requested_image_count": 2},
        }
    )
    record = service.job_store.get(created.job_id)
    assert record is not None
    record.status = ProductJobStatusValue.BLOCKED
    record.warnings.append("later_role_provider_failure")
    service.job_store.save(record)

    buffer = BytesIO()
    Image.new("RGB", (8, 8), color=(190, 210, 220)).save(buffer, format="PNG")
    persisted = output_store.save_base64_output(
        job_id=created.job_id,
        candidate_id="candidate_partial_first_role",
        asset_id="asset_partial_first_role",
        provider="test_provider",
        model="gpt-image-2",
        encoded_image=base64.b64encode(buffer.getvalue()).decode("ascii"),
        mime_type="image/png",
        output_format="png",
    )

    recovered = service.get_job(created.job_id)
    history = service.list_history()

    assert recovered.status == ProductJobStatusValue.GENERATED
    assert [candidate.output_id for candidate in recovered.candidates] == [persisted.output_id]
    assert recovered.metadata["partial_generation_recovery"] == {
        "status": "partial_output_preserved",
        "source_record_status": "blocked",
        "delivered_output_count": 1,
        "remaining_roles_failed": True,
        "append_only_history_preserved": True,
    }
    assert any("recoverable partial result" in warning for warning in recovered.warnings)
    assert history.items[0].status == ProductJobStatusValue.GENERATED
    assert history.items[0].candidate_count == 1


def test_job_polling_closes_an_expired_background_watchdog_when_timer_delivery_is_lost() -> None:
    service, _, _ = _service("gateway_background_polling_timeout")
    created = service.create_job({"user_input": "Create one clean still-life image."})
    service.mark_job_generating(
        created.job_id,
        background_attempt_id="polling_attempt",
        background_timeout_seconds=5,
    )
    record = service.job_store.get(created.job_id)
    assert record is not None
    record.request.metadata["background_generation_watchdog"]["started_at"] = "2000-01-01T00:00:00+00:00"

    expired = service.get_job(created.job_id)

    assert expired.status == ProductJobStatusValue.BLOCKED
    assert expired.metadata["generation_lifecycle_timeout"]["owner"] == "v3_background_generation_watchdog"


def test_project_timeout_handler_records_one_safe_terminal_timeline_item() -> None:
    service, _, _ = _service("project_gateway_background_timeout")
    handlers = V3ProductRouteHandlers(service)
    project = handlers.post_projects({"user_goal": "Create one clean still-life image."})
    created = handlers.post_project_job(
        project["project"]["project_id"],
        {"template_id": "general_template", "user_input": "Create one clean still-life image."},
    )

    pending = handlers.mark_project_job_generating(
        project["project"]["project_id"],
        created["job_id"],
        background_attempt_id="project_attempt_one",
    )
    timed_out = handlers.mark_project_job_generation_timed_out(
        project["project"]["project_id"],
        created["job_id"],
        background_attempt_id="project_attempt_one",
        timeout_seconds=675,
    )
    timeline = handlers.get_project_timeline(project["project"]["project_id"])

    assert pending["status"] == "generating"
    assert timed_out["status"] == "blocked"
    assert timed_out["metadata"]["generation_lifecycle_timeout"]["owner"] == "v3_background_generation_watchdog"
    assert any(
        item["related_job_id"] == created["job_id"] and item["item_type"] == "job_blocked"
        for item in timeline["items"]
    )


def test_project_background_worker_failure_records_one_safe_terminal_timeline_item() -> None:
    service, _, _ = _service("project_background_worker_failure")
    handlers = V3ProductRouteHandlers(service)
    project = handlers.post_projects({"user_goal": "Create one clean still-life image."})
    created = handlers.post_project_job(
        project["project"]["project_id"],
        {"template_id": "general_template", "user_input": "Create one clean still-life image."},
    )

    handlers.mark_project_job_generating(
        project["project"]["project_id"],
        created["job_id"],
        background_attempt_id="project_invalid_request",
    )
    failed = handlers.mark_project_job_generation_worker_failed(
        project["project"]["project_id"],
        created["job_id"],
        background_attempt_id="project_invalid_request",
        failure_code="background_generation_request_invalid",
    )
    timeline = handlers.get_project_timeline(project["project"]["project_id"])

    assert failed["status"] == "blocked"
    assert failed["metadata"]["generation_lifecycle_failure"]["owner"] == "v3_background_generation_worker"
    blocked_items = [
        item
        for item in timeline["items"]
        if item["related_job_id"] == created["job_id"] and item["item_type"] == "job_blocked"
    ]
    assert len(blocked_items) == 1
    assert blocked_items[0]["metadata"]["failure_code"] == "background_generation_request_invalid"


def test_persistent_product_job_store_restores_project_job_contract_after_restart() -> None:
    root = _test_store_root("persistent_product_job_store")
    job_root = root / "jobs"
    project_root = root / "projects"
    first_service = V3ProductApiService(job_store=PersistentProductJobStore(job_root))
    first_handlers = V3ProductRouteHandlers(
        service=first_service,
        project_store=PersistentProjectStore(project_root),
    )
    project = first_handlers.post_projects({"user_goal": "Create one clean still-life image."})
    created = first_handlers.post_project_job(
        project["project"]["project_id"],
        {"template_id": "general_template", "user_input": "Create one clean still-life image."},
    )
    first_service.mark_job_generating(
        created["job_id"],
        background_attempt_id="persistent_attempt",
        background_timeout_seconds=675,
    )

    restarted_service = V3ProductApiService(job_store=PersistentProductJobStore(job_root))
    restarted_handlers = V3ProductRouteHandlers(
        service=restarted_service,
        project_store=PersistentProjectStore(project_root),
    )
    restored = restarted_handlers.get_job(created["job_id"])
    restored_project = restarted_handlers.get_project(project["project"]["project_id"])

    assert restored["status"] == "generating"
    assert restored["metadata"]["background_generation_watchdog"]["background_attempt_id"] == "persistent_attempt"
    assert created["job_id"] in restored_project["project"]["job_ids"]


def test_v3_product_api_accepts_campaign_and_style_continuation_product_concepts() -> None:
    service, _, _ = _service("campaign")
    brand = service.create_brand(
        {
            "brand_id": "brand_product_api_campaign",
            "brand_name": "Campaign Tea",
            "industry": IndustryCategory.BEVERAGE,
            "visual_tone": ["fresh", "precise"],
            "color_palette": ["mint green"],
        }
    )

    created = service.create_job(
        {
            "user_input": "沿用品牌风格，做一组新品上市图。",
            "continue_style_from_brand_id": brand.brand.brand_id,
            "campaign": {
                "campaign_id": "campaign_summer_launch",
                "campaign_name": "Summer launch",
                "business_goal": "new product launch",
                "platforms": [Platform.XIAOHONGSHU],
            },
        }
    )

    assert created.campaign.campaign_id == "campaign_summer_launch"
    assert created.campaign.campaign_name == "Summer launch"
    assert created.campaign.business_goal == "new product launch"
    assert created.campaign.target_platforms == [Platform.XIAOHONGSHU]
    assert created.style_continuation.enabled is True
    assert created.style_continuation.source_brand_id == "brand_product_api_campaign"
    assert "seed" not in created.model_dump_json()
    assert "sampler" not in created.model_dump_json()


def test_v3_product_api_generates_selects_and_applies_brand_memory_update() -> None:
    service, brand_service, balance = _service("select")
    brand_response = service.create_brand(
        {
            "brand_id": "brand_product_api",
            "brand_name": "Test Tea",
            "industry": IndustryCategory.BEVERAGE,
            "visual_tone": ["fresh", "clean"],
            "color_palette": ["mint green", "cream white"],
            "platform_history": [Platform.XIAOHONGSHU],
        }
    )

    created = service.create_job(
        {
            "user_input": "沿用上次风格，帮我做一组奶茶店端午节活动图，适合小红书。",
            "continue_style_from_brand_id": brand_response.brand.brand_id,
        }
    )
    generated = service.generate_job(created.job_id)
    selected = service.select_result(generated.job_id)
    updated = brand_service.load_profile("brand_product_api")

    assert generated.status == ProductJobStatusValue.GENERATED
    assert generated.candidates
    assert selected.status == ProductJobStatusValue.SELECTED
    assert selected.selected_result.selected_candidate_ids
    assert selected.selected_result.memory_update_applied is True
    assert updated is not None
    assert updated.successful_asset_ids
    assert balance.checked_credits == [0]


def test_v3_product_api_does_not_accept_low_level_generation_controls() -> None:
    with pytest.raises(ValidationError):
        CreateCreativeJobRequest.model_validate({"user_input": "做一个活动图", "seed": 123})
    with pytest.raises(ValidationError):
        CreateCreativeJobRequest.model_validate({"user_input": "做一个活动图", "metadata": {"sampler": "hidden"}})
    with pytest.raises(ValidationError):
        GenerateJobRequest.model_validate({"quality_mode": "standard", "metadata": {"adapter scale": 0.8}})
    with pytest.raises(ValidationError):
        SelectResultRequest.model_validate({"metadata": {"node graph": {"name": "internal"}}})
    with pytest.raises(ValidationError):
        CreateBrandRequest.model_validate({"brand_name": "Hidden", "metadata": {"LoRA": "internal"}})

    service, _, _ = _service("product_only")
    status = service.create_job({"user_input": "做一个活动宣传图，适合小红书。"})
    payload = status.model_dump_json()

    assert "seed" not in payload
    assert "sampler" not in payload
    assert "node graph" not in payload


def test_minimal_ui_contract_uses_semantic_controls_and_v3_routes() -> None:
    service, _, _ = _service("ui")
    status = service.create_job({"user_input": "帮我做一个活动宣传图，适合小红书。"})
    contract = get_minimal_ui_contract()
    html = render_minimal_job_view(status.model_dump(mode="json"))

    assert contract["entry_route"] == "/creative-agent-v3"
    assert contract["api_namespace"] == API_NAMESPACE
    assert contract["calls_only_v3_api_namespace"] == API_NAMESPACE
    assert any(control["element"] == "textarea" and control["label"] == "Creative request" for control in contract["semantic_controls"])
    assert 'aria-label="Create creative job"' in html
    assert 'name="user_input"' in html
    assert 'id="v3-job-status"' in html
    assert status.job_id in html


def test_framework_neutral_route_handlers_return_product_status_payloads() -> None:
    service, _, _ = _service("routes")
    handlers = V3ProductRouteHandlers(service)

    created = handlers.post_jobs({"user_input": "帮我做一张清爽活动海报，适合小红书。"})
    generated = handlers.post_generate(created["job_id"])
    selected = handlers.post_select(created["job_id"])

    assert created["api_namespace"] == "/api/v3/creative-agent"
    assert generated["status"] == "generated"
    assert generated["asset_series"]
    assert selected["selected_result"]["selected_asset_ids"]


def test_framework_neutral_route_handlers_support_v37_product_aliases() -> None:
    service, _, _ = _service("route_aliases")
    handlers = V3ProductRouteHandlers(service)

    brand = handlers.post_product_brands(
        {
            "brand_id": "brand_product_api_alias",
            "brand_name": "Alias Tea",
            "industry": IndustryCategory.BEVERAGE,
        }
    )
    created = handlers.post_creative_jobs(
        {
            "user_input": "帮我做一组茶饮新品发布图，适合社交平台。",
            "brand_id": brand["brand"]["brand_id"],
        }
    )
    fetched = handlers.get_creative_job(created["job_id"])
    generated = handlers.post_creative_job_generate(created["job_id"], {"quality_mode": "strict"})
    selected = handlers.post_creative_job_select(created["job_id"])

    assert brand["route"] == "/api/v3/creative-agent/brands"
    assert fetched["routes"]["get_creative_job"] == "/v3/creative-jobs/{job_id}"
    assert generated["status"] == "generated"
    assert selected["status"] == "selected"
