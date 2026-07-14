from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service


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


def test_visual_auto_retry_appends_outputs_without_overwriting_originals(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {
                "force_visual_retry_issue_codes": ["visible_text_artifact"],
                "max_visual_retry_attempts": 1,
            },
        },
    )

    internal_result = _internal_generation_result(service, created.job_id)
    retry_summary = internal_result.metadata["visual_auto_retry"]
    internal_assets = internal_result.asset_pack.assets
    retry_candidates = [
        asset
        for asset in internal_assets
        if asset.metadata.get("candidate_metadata", {}).get("visual_auto_retry_output")
    ]
    original_candidates = [
        asset
        for asset in internal_assets
        if not asset.metadata.get("candidate_metadata", {}).get("visual_auto_retry_output")
    ]

    assert generated.status == ProductJobStatusValue.GENERATED
    assert retry_summary["enabled"] is True
    assert retry_summary["executed_count"] == 1
    assert retry_summary["append_only"] is True
    assert retry_summary["records"][0]["status"] == "executed"
    assert "visible_text_artifact" in retry_summary["issue_codes"]
    assert original_candidates
    assert retry_candidates
    assert {candidate.metadata["selected_candidate_id"] for candidate in original_candidates}.isdisjoint(
        {candidate.metadata["selected_candidate_id"] for candidate in retry_candidates}
    )
    assert all(
        candidate.metadata["candidate_metadata"]["visual_auto_retry_attempt"] == 1
        for candidate in retry_candidates
    )
    assert generated.metadata["visual_auto_retry"]["append_only"] is True
    assert "retry_patch" not in generated.metadata["visual_auto_retry"]["records"][0]


def test_visual_auto_retry_stops_when_same_issue_repeats_in_strict_mode(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "strict",
            "metadata": {
                "force_visual_retry_issue_codes": ["collage_or_split_panel"],
                "max_visual_retry_attempts": 2,
            },
        },
    )

    retry_summary = _internal_generation_result(service, created.job_id).metadata["visual_auto_retry"]
    records = retry_summary["records"]

    assert retry_summary["max_attempts"] == 2
    assert retry_summary["executed_count"] == 1
    assert [record["status"] for record in records] == ["executed", "blocked"]
    assert records[-1]["blocked_reason"] == "same_issue_repeated"
    assert records[-1]["original_job_id"] == created.job_id


def test_visual_auto_retry_executes_for_product_label_issue_from_active_ledger(tmp_path, monkeypatch) -> None:
    service = _ecommerce_service(tmp_path)
    monkeypatch.setattr(
        service,
        "_visual_retry_patch_from_issues",
        lambda _codes: (_ for _ in ()).throw(AssertionError("enforced retry must not use legacy issue mapper")),
    )


def _internal_generation_result(service: V3ProductApiService, job_id: str):
    record = service.job_store.get(job_id)
    assert record is not None
    assert record.generation_result is not None
    return record.generation_result
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

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {
                "force_visual_retry_issue_codes": ["product_label_unreadable"],
                "visual_retry_patch": {"product_reinforcement": ["FORGED REQUEST PATCH"]},
                "max_visual_retry_attempts": 1,
            },
        },
    )

    retry_summary = _internal_generation_result(service, created.job_id).metadata["visual_auto_retry"]
    patch_text = " ".join(
        str(item)
        for item in retry_summary["records"][0]["retry_patch"].get("product_reinforcement", [])
    )

    assert retry_summary["executed_count"] == 1
    assert "product_label_unreadable" in retry_summary["issue_codes"]
    assert "label/logo" in patch_text
    assert "FORGED REQUEST PATCH" not in patch_text


def test_visual_auto_retry_skips_empty_patch_without_provider_loop(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {
                "force_visual_retry_issue_codes": ["visible_text_artifact"],
                "force_empty_visual_retry_patch": True,
            },
        },
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

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "explore",
            "metadata": {
                "force_visual_retry_issue_codes": ["visible_text_artifact"],
                "max_visual_retry_attempts": 1,
            },
        },
    )

    retry_summary = generated.metadata["visual_auto_retry"]

    assert retry_summary["enabled"] is False
    assert retry_summary["executed_count"] == 0
    assert retry_summary["records"] == []
    assert not any(candidate.metadata.get("visual_auto_retry_output") for candidate in generated.candidates)
