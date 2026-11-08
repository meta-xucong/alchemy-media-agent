from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.contracts import GenerateContinuation
from alchemy_creative_agent_3_0.app.schemas import ProviderStrategy
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import (
    EcommerceRemoteBrainTestProvider,
    ecommerce_test_service,
)


def _service(tmp_path) -> V3ProductApiService:
    return V3ProductApiService(brand_profile_service=BrandProfileService(BrandProfileStore(tmp_path / "brand_memory")))


def _ecommerce_service(tmp_path) -> V3ProductApiService:
    return ecommerce_test_service(
        brand_profile_service=BrandProfileService(BrandProfileStore(tmp_path / "brand_memory"))
    )


def _create_general_job(service: V3ProductApiService):
    return service.create_job(
        {
            "user_input": "生成一组夏日清凉东方美女写真，干净明亮，适合社媒封面",
            "scenario_selection": {
                "scenario_id": "general_creative",
                "mode_id": "social_cover",
                "preset_id": "social_cover",
            },
        }
    )


def test_visual_retry_no_result_keeps_safe_pre_provider_provenance(tmp_path) -> None:
    service = _service(tmp_path)
    runtime_result = type(
        "BlockedRuntimeResult",
        (),
        {
            "status": type("Status", (), {"value": "blocked"})(),
            "capability_run": None,
            "metadata": {
                "capability_activation_error": "CapabilityActivationError",
                "remote_creative_brain_outcome": {
                    "schema_version": "v3_remote_creative_brain_outcome_v1",
                    "state": "blocked",
                    "reason_code": "remote_brain_unavailable",
                    "outcome_class": "remote_provider_error",
                    "llm_used": False,
                    "fallback_used": True,
                    "raw_error": "must not leak",
                },
            },
        },
    )()

    outcome = service._retry_no_result_outcome(runtime_result)  # noqa: SLF001

    assert outcome == {
        "reason_code": "retry_remote_brain_blocked",
        "runtime_status": "blocked",
        "provider_request_started": False,
        "remote_brain_outcome": {
            "schema_version": "v3_remote_creative_brain_outcome_v1",
            "state": "blocked",
            "reason_code": "remote_brain_unavailable",
            "outcome_class": "remote_provider_error",
            "llm_used": False,
            "fallback_used": True,
        },
    }


def test_unbound_general_mock_retry_is_withheld_without_a_local_prompt_patch(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)

    generated = service.generate_job_with_continuation(
        created.job_id,
        {
            "quality_mode": "standard",
        },
        continuation=GenerateContinuation(
            job_id=created.job_id,
            force_visual_retry_issue_codes=("visible_text_artifact",),
            max_visual_retry_attempts=1,
        ),
    )

    internal_result = _internal_generation_result(service, created.job_id)
    retry_summary = internal_result.metadata["visual_auto_retry"]
    internal_assets = internal_result.asset_pack.assets
    assert generated.status == ProductJobStatusValue.GENERATED
    assert retry_summary["enabled"] is True
    assert retry_summary["executed_count"] == 0
    assert retry_summary["append_only"] is True
    assert retry_summary["records"][0]["status"] == "skipped"
    assert retry_summary["records"][0]["blocked_reason"] == "empty_retry_patch"
    assert "visible_text_artifact" in retry_summary["issue_codes"]
    assert internal_assets
    assert not any(asset.metadata.get("candidate_metadata", {}).get("visual_auto_retry_output") for asset in internal_assets)
    assert generated.metadata["visual_auto_retry"]["append_only"] is True
    assert "retry_patch" not in generated.metadata["visual_auto_retry"]["records"][0]


def test_unbound_general_mock_retry_does_not_enter_a_second_generation_loop(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)
    original_generate = service.scenario_runtime.generate_job
    invocation_count = 0

    # Exercise the production-only no-pixel guard while keeping this unit test
    # offline.  The outer service sees a real-provider strategy; the injected
    # runtime returns the normal deterministic fixture instead of networking.
    monkeypatch.setattr(service, "_provider_strategy_for_generate", lambda *_args, **_kwargs: ProviderStrategy.DEFAULT_IMAGE_PROVIDER)

    def generate_with_empty_retry(*args, **kwargs):  # noqa: ANN002,ANN003
        nonlocal invocation_count
        invocation_count += 1
        kwargs["provider_strategy"] = ProviderStrategy.MOCK_GENERATION
        runtime_result = original_generate(*args, **kwargs)
        if invocation_count != 2:
            return runtime_result
        assert runtime_result.generation_result is not None
        empty_pack = runtime_result.generation_result.asset_pack.model_copy(update={"assets": []})
        empty_result = runtime_result.generation_result.model_copy(update={"asset_pack": empty_pack})
        return runtime_result.model_copy(update={"generation_result": empty_result})

    monkeypatch.setattr(service.scenario_runtime, "generate_job", generate_with_empty_retry)

    service.generate_job_with_continuation(
        created.job_id,
        {
            "quality_mode": "standard",
        },
        continuation=GenerateContinuation(
            job_id=created.job_id,
            force_visual_retry_issue_codes=("visible_text_artifact",),
            max_visual_retry_attempts=1,
        ),
    )

    internal_result = _internal_generation_result(service, created.job_id)
    retry_summary = internal_result.metadata["visual_auto_retry"]

    assert invocation_count == 1
    assert retry_summary["executed_count"] == 0
    assert retry_summary["records"][0]["status"] == "skipped"
    assert retry_summary["records"][0]["blocked_reason"] == "empty_retry_patch"
    assert not any(
        asset.metadata.get("candidate_metadata", {}).get("visual_auto_retry_output")
        for asset in internal_result.asset_pack.assets
    )
    assert not internal_result.metadata.get("retry_generation_result_ids")


def test_unbound_general_mock_retry_never_repeats_a_local_issue_patch_in_strict_mode(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)

    generated = service.generate_job_with_continuation(
        created.job_id,
        {
            "quality_mode": "strict",
        },
        continuation=GenerateContinuation(
            job_id=created.job_id,
            force_visual_retry_issue_codes=("collage_or_split_panel",),
            max_visual_retry_attempts=2,
        ),
    )

    retry_summary = _internal_generation_result(service, created.job_id).metadata["visual_auto_retry"]
    records = retry_summary["records"]

    assert retry_summary["max_attempts"] == 2
    assert retry_summary["executed_count"] == 0
    assert [record["status"] for record in records] == ["skipped"]
    assert records[-1]["blocked_reason"] == "empty_retry_patch"
    assert records[-1]["original_job_id"] == created.job_id


def test_visual_auto_retry_executes_for_product_label_issue_from_active_ledger(tmp_path, monkeypatch) -> None:
    brain_provider = EcommerceRemoteBrainTestProvider()
    service = ecommerce_test_service(
        brain_provider=brain_provider,
        brand_profile_service=BrandProfileService(BrandProfileStore(tmp_path / "brand_memory")),
    )
    monkeypatch.setattr(
        service,
        "_visual_retry_patch_from_issues",
        lambda _codes: (_ for _ in ()).throw(AssertionError("enforced retry must not use legacy issue mapper")),
    )
    monkeypatch.setattr(
        service,
        "_ledger_retry_patch",
        lambda _ledger, _codes: (_ for _ in ()).throw(AssertionError("enforced retry must not build ledger prose")),
    )
    created = service.create_job(
        {
            "user_input": "Create a clean ecommerce product set for a drink can",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "parameters": {"requested_image_count": 1},
            },
            "uploaded_asset_ids": ["product_drink_can"],
            "product_profile": {
                "product_category": "drink",
                "materials": ["turquoise can", "lime mint label"],
                "selling_points": ["Fresh summer taste"],
            },
        }
    )

    generated = service.generate_job_with_continuation(
        created.job_id,
        {
            "quality_mode": "standard",
        },
        continuation=GenerateContinuation(
            job_id=created.job_id,
            force_visual_retry_issue_codes=("product_label_unreadable",),
            visual_retry_patch={"product_reinforcement": ["FORGED REQUEST PATCH"]},
            max_visual_retry_attempts=1,
        ),
    )

    retry_summary = _internal_generation_result(service, created.job_id).metadata["visual_auto_retry"]
    finalizer_requests = [item for item in brain_provider.requests if item["stage"] == "provider_prompt_finalize"]
    assert finalizer_requests
    retry_context = finalizer_requests[-1]["metadata"]["canonical_prompt_context"]

    assert retry_summary["executed_count"] == 1
    assert "product_label_unreadable" in retry_summary["issue_codes"]
    assert retry_summary["records"][0]["retry_patch"] == {}
    assert retry_context["retry_evidence"] == {
        "active": True,
        "issue_codes": ["product_label_unreadable"],
    }
    assert "FORGED REQUEST PATCH" not in str(retry_context)
    assert "prompt_additions" not in str(retry_context)


def test_selective_generation_keeps_full_brain_plan_and_materializes_only_the_target(tmp_path, monkeypatch) -> None:
    from alchemy_creative_agent_3_0.app.generation_router.router import GenerationRouter

    service = _ecommerce_service(tmp_path)
    service.scenario_runtime.generation_router = GenerationRouter()
    created = service.create_job(
        {
            "user_input": "Create two coordinated summer lifestyle images with distinct compositions",
            "scenario_selection": {
                "scenario_id": "general_creative",
                "parameters": {"requested_image_count": 2},
            },
            "metadata": {"requested_image_count": 2},
        }
    )
    generated = service.generate_job(created.job_id, {"quality_mode": "standard"})
    record = service.job_store.get(created.job_id)
    assert generated.status == ProductJobStatusValue.GENERATED
    assert record is not None and record.generation_result is not None
    original_assets = list(record.generation_result.series_plan.assets)
    assert len(original_assets) == 2
    target_asset_id = original_assets[1].asset_id

    generation_router = service.scenario_runtime.generation_router
    original_generate = generation_router.generate
    materialized_requests = []

    def record_materialization(request):  # noqa: ANN001
        materialized_requests.append(request)
        return original_generate(request)

    monkeypatch.setattr(generation_router, "generate", record_materialization)
    runtime_request = service._runtime_request_payload(  # noqa: SLF001 - trusted retry entry point
        record.request,
        trusted_capability_plan_reuse=True,
    )
    runtime_request["metadata"].update(
        {
            "visual_auto_retry_active": True,
            "visual_auto_retry_attempt": 1,
            "visual_retry_reason_codes": ["weak_aesthetic_finish"],
        }
    )

    retry_runtime_result = service.scenario_runtime.generate_job(
        runtime_request,
        mock_profile="balanced",
        apply_memory_update=False,
        provider_strategy=ProviderStrategy.MOCK_GENERATION,
        quality_mode="standard",
        generation_asset_ids=[target_asset_id],
    )

    assert retry_runtime_result.generation_result is not None
    retry_result = retry_runtime_result.generation_result
    assert len(retry_result.series_plan.assets) == 2
    assert len(retry_result.asset_pack.assets) == 1
    assert retry_result.asset_pack.assets[0].asset_id == target_asset_id
    assert {request.asset_spec.asset_id for request in materialized_requests} == {target_asset_id}
    assert len(retry_result.generation_plans) == 1
    assert retry_result.generation_plans[0].metadata["output_index"] == 1
    assert retry_result.generation_plans[0].metadata["requested_image_count"] == 2


def _internal_generation_result(service: V3ProductApiService, job_id: str):
    record = service.job_store.get(job_id)
    assert record is not None
    assert record.generation_result is not None
    return record.generation_result


def test_visual_auto_retry_skips_empty_patch_without_provider_loop(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)

    generated = service.generate_job_with_continuation(
        created.job_id,
        {
            "quality_mode": "standard",
        },
        continuation=GenerateContinuation(
            job_id=created.job_id,
            force_visual_retry_issue_codes=("visible_text_artifact",),
            force_empty_visual_retry_patch=True,
        ),
    )

    internal_result = _internal_generation_result(service, created.job_id)
    retry_summary = internal_result.metadata["visual_auto_retry"]

    assert retry_summary["executed_count"] == 0
    assert retry_summary["records"][0]["status"] == "skipped"
    assert retry_summary["records"][0]["blocked_reason"] == "empty_retry_patch"
    assert not any(
        candidate.metadata.get("candidate_metadata", {}).get("visual_auto_retry_output")
        for candidate in internal_result.asset_pack.assets
    )


def test_visual_auto_retry_is_off_by_default_in_explore_mode(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)

    generated = service.generate_job_with_continuation(
        created.job_id,
        {
            "quality_mode": "explore",
        },
        continuation=GenerateContinuation(
            job_id=created.job_id,
            force_visual_retry_issue_codes=("visible_text_artifact",),
            max_visual_retry_attempts=1,
        ),
    )

    retry_summary = generated.metadata["visual_auto_retry"]

    assert retry_summary["enabled"] is False
    assert retry_summary["executed_count"] == 0
    assert retry_summary["records"] == []
    assert not any(candidate.metadata.get("visual_auto_retry_output") for candidate in generated.candidates)
