from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    CommercialAssetPack,
    PackagedAsset,
    Platform,
    SeriesPlan,
)


def _result(*, metadata: dict, candidate_metadata: dict | None = None):
    spec = AssetSpec(
        asset_id="asset_doc297",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="4:5",
        purpose="mode projection regression fixture",
    )
    packaged = PackagedAsset(
        asset_id=spec.asset_id,
        asset_type=spec.asset_type,
        platform=spec.platform,
        aspect_ratio=spec.aspect_ratio,
        purpose=spec.purpose,
        uri="memory://doc297-output",
        metadata={
            "selected_candidate_id": "candidate_doc297",
            "candidate_metadata": dict(candidate_metadata or {}),
        },
    )
    return SimpleNamespace(
        planning_result_id="planning_doc297",
        metadata=dict(metadata),
        creative_job=SimpleNamespace(metadata={}),
        series_plan=SeriesPlan(
            series_plan_id="series_doc297",
            job_id="job_doc297",
            assets=[spec],
        ),
        asset_pack=CommercialAssetPack(
            asset_pack_id="pack_doc297",
            job_id="job_doc297",
            assets=[packaged],
            planning_only=False,
        ),
        evaluation_reports=[],
        prompt_compilations=[],
    )


def _record(result):
    return SimpleNamespace(
        job_id="job_doc297",
        status=ProductJobStatusValue.GENERATED,
        request=SimpleNamespace(
            user_input="doc297 fixture",
            effective_brand_id=None,
            metadata={},
        ),
        planning_result=None,
        generation_result=result,
        scenario_resolution=None,
        selected_result=None,
        balance_estimate={},
        lifecycle=None,
    )


def _enforced_envelope(capability_projection: dict) -> dict:
    return {
        "activation_mode": "enforced",
        "envelope_id": "envelope_doc297",
        "execution_fingerprint": "fingerprint_doc297",
        "activation_plan": {
            "plan_id": "plan_doc297",
            "fingerprint": "plan_fingerprint_doc297",
            "catalog_version": "catalog_doc297",
            "activation_mode": "enforced",
            "dependency_order": ["visual_grammar", "suite_direction"],
            "active_capabilities": [
                {"capability_id": "visual_grammar", "activation_mode": "required"},
                {"capability_id": "suite_direction", "activation_mode": "required"},
            ],
            "inactive_capabilities": [],
        },
        "active_capability_ids": ["visual_grammar", "suite_direction"],
        "resolved_constraint_ledger": {
            "ledger_id": "ledger_doc297",
            "provider_projection": {
                "capability_projection": capability_projection,
            },
        },
    }


_ONE_PIXEL_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def _mode_restore_result(mode: str, image_count: int):
    specs = [
        AssetSpec(
            asset_id=f"asset_doc297_{index}",
            asset_type=AssetType.SOCIAL_COVER,
            platform=Platform.GENERIC_SOCIAL,
            aspect_ratio="4:5",
            purpose="mode restore regression fixture",
            priority=index,
        )
        for index in range(1, image_count + 1)
    ]
    packaged = [
        PackagedAsset(
            asset_id=spec.asset_id,
            asset_type=spec.asset_type,
            platform=spec.platform,
            aspect_ratio=spec.aspect_ratio,
            purpose=spec.purpose,
            uri=f"memory://doc297-output-{index}",
            metadata={
                "selected_candidate_id": f"candidate_doc297_{index}",
                "candidate_metadata": {
                    "output_id": f"v3_output_{index:020x}",
                    "output_index": index,
                },
            },
        )
        for index, spec in enumerate(specs, 1)
    ]
    capability_projection = {
        "effective_variation_mode": mode,
        "mode_execution_policy": {"mode": mode, "role_strategy": f"{mode}_roles"},
        "mode_quality_profile": {"mode": mode, "profile": "regression"},
        "variation_execution_mode": mode,
        "variation_execution_requested_image_count": image_count,
        "variation_execution_contract_enforced": True,
    }
    if image_count > 1:
        capability_projection.update(
            {
                "role_specific_generation_plan": {
                    "mode": mode,
                    "role_recipes": [
                        {"index": index, "role_key": f"{mode}_role_{index}"}
                        for index in range(1, image_count + 1)
                    ],
                },
                "variation_execution_contract": {"mode": mode, "count": image_count},
                "variation_execution_contract_binding": {"mode": mode, "count": image_count},
                "variation_execution_suite_direction_authoritative": True,
            }
        )
    envelope = _enforced_envelope(capability_projection)
    if image_count == 1:
        envelope["activation_plan"]["dependency_order"] = ["visual_grammar"]
        envelope["activation_plan"]["active_capabilities"] = [
            {"capability_id": "visual_grammar", "activation_mode": "required"}
        ]
        envelope["active_capability_ids"] = ["visual_grammar"]
    return SimpleNamespace(
        planning_result_id="planning_doc297_mode_restore",
        metadata={
            "scenario_id": "general_creative",
            "template_id": "general_template",
            "requested_image_count": image_count,
            "effective_variation_mode": mode,
            "capability_execution_envelope": envelope,
        },
        creative_job=SimpleNamespace(metadata={}),
        series_plan=SeriesPlan(
            series_plan_id="series_doc297_mode_restore",
            job_id="job_doc297_mode_restore",
            assets=specs,
        ),
        asset_pack=CommercialAssetPack(
            asset_pack_id="pack_doc297_mode_restore",
            job_id="job_doc297_mode_restore",
            assets=packaged,
            planning_only=False,
        ),
        evaluation_reports=[],
        prompt_compilations=[],
    )


def test_doc297_projects_frozen_multi_image_mode_into_candidate_and_lifecycle():
    policy = {"mode": "creative_exploration", "role_strategy": "concept_lanes"}
    role_plan = {
        "mode": "creative_exploration",
        "role_recipes": [{"role_key": "concept_clean_bright"}],
    }
    quality = {"profile": "broad", "mode": "creative_exploration"}
    result = _result(
        metadata={
            "requested_image_count": 2,
            "effective_variation_mode": "creative_exploration",
            "variation_execution_contract_enforced": True,
            "capability_execution_envelope": _enforced_envelope(
                {
                    "mode_execution_policy": policy,
                    "role_specific_generation_plan": role_plan,
                    "mode_quality_profile": quality,
                    "variation_execution_contract": {"mode": "creative_exploration", "count": 2},
                    "variation_execution_requested_image_count": 2,
                }
            ),
            "llm_brain": {
                "llm_used": True,
                "fallback_used": False,
                "prompt_review": {"status": "blocked", "checks": ["planning_only"]},
                "audit": {
                    "remote_canonical_provider_prompts_received": True,
                    "canonical_provider_prompt_stage": "provider_prompt_finalize",
                    "canonical_provider_prompt_stages": ["provider_prompt_finalize"],
                    "canonical_provider_prompt_binding": {
                        "activation_plan_id": "plan_doc297",
                        "execution_envelope_id": "envelope_doc297",
                        "constraint_ledger_id": "ledger_doc297",
                    },
                },
                "canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": "A complete, approved renderer instruction with enough detail.",
                        "review_status": "approved",
                        "prompt_status": "complete",
                        "semantic_coverage": "complete",
                    },
                    {
                        "output_index": 2,
                        "prompt": "Another complete, approved renderer instruction with enough detail.",
                        "review_status": "approved",
                        "prompt_status": "complete",
                        "semantic_coverage": "complete",
                    },
                ],
            },
        },
        candidate_metadata={
            "output_id": "output_doc297",
            "llm_brain": {"prompt_review": {"status": "blocked"}},
        },
    )
    service = V3ProductApiService()

    projected = service._project_candidate_metadata_from_result(  # noqa: SLF001
        result,
        result.asset_pack.assets[0].metadata["candidate_metadata"],
    )

    assert projected["mode_execution_policy"] == policy
    assert projected["role_specific_generation_plan"] == role_plan
    assert projected["mode_quality_profile"] == quality
    assert projected["variation_execution_contract"]["mode"] == "creative_exploration"
    assert projected["mode_execution_audit"]["contract_status"] == "active"
    assert projected["llm_brain"]["prompt_review"]["status"] == "approved"
    assert projected["llm_brain"]["prompt_review"]["source"] == "canonical_provider_prompts"
    assert projected["llm_brain"]["planning_prompt_review"]["status"] == "blocked"

    lifecycle = service._build_lifecycle(_record(result))  # noqa: SLF001
    lifecycle_metadata = lifecycle.candidates[0].metadata
    assert lifecycle_metadata["mode_execution_policy"] == policy
    assert lifecycle_metadata["role_specific_generation_plan"] == role_plan
    assert lifecycle_metadata["mode_quality_profile"] == quality
    assert lifecycle_metadata["llm_brain"]["prompt_review"]["status"] == "approved"

    public_series = service._asset_series(result, ProductJobStatusValue.GENERATED)  # noqa: SLF001
    public_candidates = service._candidate_summaries(result)  # noqa: SLF001
    assert public_series[0].metadata["candidate_metadata"]["mode_execution_policy"] == policy
    assert public_candidates[0].metadata["mode_quality_profile"] == quality


@pytest.mark.parametrize(
    ("mode", "role_strategy"),
    [
        ("selection_candidates", "near_neighbor_candidates"),
        ("delivery_suite", "purposeful_delivery_roles"),
        ("creative_exploration", "concept_lanes"),
        ("format_layout_adaptation", "format_roles"),
    ],
)
def test_doc297_projection_preserves_each_multi_image_mode_policy(mode, role_strategy):
    result = _result(
        metadata={
            "requested_image_count": 2,
            "effective_variation_mode": mode,
            "capability_execution_envelope": _enforced_envelope(
                {
                    "mode_execution_policy": {"mode": mode, "role_strategy": role_strategy},
                    "role_specific_generation_plan": {"mode": mode, "role_recipes": [{"role_key": "role_1"}]},
                    "mode_quality_profile": {"mode": mode},
                    "variation_execution_contract": {"mode": mode, "count": 2},
                    "variation_execution_requested_image_count": 2,
                }
            ),
        }
    )

    projected = V3ProductApiService()._project_candidate_metadata_from_result(  # noqa: SLF001
        result,
        result.asset_pack.assets[0].metadata["candidate_metadata"],
    )

    assert projected["mode_execution_policy"] == {"mode": mode, "role_strategy": role_strategy}
    assert projected["role_specific_generation_plan"]["mode"] == mode
    assert projected["mode_quality_profile"]["mode"] == mode
    assert projected["mode_execution_audit"]["contract_status"] == "active"


def test_doc297_single_image_mode_is_audited_without_fabricating_variation_receipt():
    result = _result(
        metadata={
            "requested_image_count": 1,
            "effective_variation_mode": "format_layout_adaptation",
            "capability_activation_plan": {
                "plan_id": "plan_doc297_single",
                "fingerprint": "fingerprint_doc297_single",
                "catalog_version": "catalog_doc297",
                "activation_mode": "enforced",
                "dependency_order": [
                    "visual_grammar",
                    "universal_visual_quality",
                    "commercial_quality",
                    "human_realism",
                ],
                "active_capabilities": [
                    {
                        "capability_id": "visual_grammar",
                        "activation_mode": "required",
                        "reason_codes": ["template_required"],
                        "evidence_ids": ["evidence_visual_grammar"],
                        "confidence": 1.0,
                    },
                    {"capability_id": "universal_visual_quality", "activation_mode": "required"},
                    {"capability_id": "commercial_quality", "activation_mode": "required"},
                    {
                        "capability_id": "human_realism",
                        "activation_mode": "required",
                        "reason_codes": ["visible_person"],
                        "evidence_ids": ["evidence_person"],
                        "confidence": 0.9,
                    },
                ],
                "inactive_capabilities": [
                    {
                        "capability_id": "suite_direction",
                        "reason_code": "single_image_not_applicable",
                        "evidence_ids": ["evidence_single_image"],
                    }
                ],
            },
            "llm_brain": {
                "capability_activation_intent": {
                    "requested_capabilities": [
                        {
                            "capability_id": "scene_continuity",
                            "activation_mode": "recommended",
                            "reason_codes": ["scene_reference"],
                            "evidence_ids": ["evidence_scene"],
                            "confidence": 0.8,
                        }
                    ],
                    "rejected_capabilities": [
                        {
                            "capability_id": "suite_direction",
                            "reason_code": "single_image_not_applicable",
                            "evidence_ids": ["evidence_single_image"],
                            "confidence": 1.0,
                        }
                    ],
                }
            },
        },
        candidate_metadata={"output_id": "output_doc297_single"},
    )
    service = V3ProductApiService()

    projected = service._project_candidate_metadata_from_result(  # noqa: SLF001
        result,
        result.asset_pack.assets[0].metadata["candidate_metadata"],
    )

    assert projected["mode_execution_audit"] == {
        "schema_version": "v3_mode_execution_audit_v1",
        "mode": "format_layout_adaptation",
        "requested_image_count": 1,
        "contract_status": "not_applicable",
        "suite_direction_active": False,
        "projection_source": None,
    }
    assert "variation_execution_contract" not in projected
    assert "role_specific_generation_plan" not in projected

    activation_audit = service._capability_activation_audit_from_result(result)  # noqa: SLF001
    assert activation_audit["active_capability_ids"][-1] == "human_realism"
    assert activation_audit["inactive_capability_ids"] == ["suite_direction"]
    assert activation_audit["fingerprint"] == "fingerprint_doc297_single"
    assert activation_audit["active_evidence_ids"]["human_realism"] == ["evidence_person"]
    assert activation_audit["inactive_evidence_ids"]["suite_direction"] == ["evidence_single_image"]
    assert activation_audit["requested_capability_details"]["scene_continuity"]["confidence"] == 0.8
    assert activation_audit["rejected_capability_details"]["suite_direction"]["reason_code"] == (
        "single_image_not_applicable"
    )
    status_metadata = service._project_mode_status_metadata(_record(result))  # noqa: SLF001
    assert status_metadata["mode_execution_audit"]["contract_status"] == "not_applicable"
    public_activation_audit = status_metadata["capability_activation_audit"]
    assert public_activation_audit["activation_mode"] == "enforced"
    assert public_activation_audit["active_capability_ids"][-1] == "human_realism"
    assert not {
        "plan_id",
        "fingerprint",
        "plan_provenance",
        "active_evidence_ids",
        "inactive_evidence_ids",
    } & set(public_activation_audit)


def test_doc297_empty_authoritative_projection_never_erases_provider_candidate_facts():
    result = _result(
        metadata={
            "capability_execution_envelope": _enforced_envelope({}),
        },
        candidate_metadata={
            "mode_execution_policy": {"mode": "selection_candidates"},
            "mode_quality_profile": {"profile": "micro"},
        },
    )
    service = V3ProductApiService()

    projected = service._project_candidate_metadata_from_result(  # noqa: SLF001
        result,
        result.asset_pack.assets[0].metadata["candidate_metadata"],
    )

    assert projected["mode_execution_policy"] == {"mode": "selection_candidates"}
    assert projected["mode_quality_profile"] == {"profile": "micro"}


def test_doc297_enforced_empty_ledger_does_not_leak_dormant_outer_visual_cluster():
    envelope = _enforced_envelope({})
    envelope["provider_projection"] = {
        "visual_cluster": {
            "mode_execution_policy": {"mode": "delivery_suite"},
            "role_specific_generation_plan": {"mode": "delivery_suite"},
        }
    }
    result = _result(
        metadata={"capability_execution_envelope": envelope},
        candidate_metadata={"output_id": "output_doc297_raw_cluster"},
    )

    projected = V3ProductApiService()._project_candidate_metadata_from_result(  # noqa: SLF001
        result,
        result.asset_pack.assets[0].metadata["candidate_metadata"],
    )

    assert "mode_execution_policy" not in projected
    assert "role_specific_generation_plan" not in projected
    assert projected["mode_execution_audit"]["mode"] is None
    assert projected["mode_execution_audit"]["contract_status"] == "missing"
    assert projected["mode_execution_audit"]["projection_status"] == "missing"


def test_doc297_enforced_single_image_reads_resolved_mode_identity_without_suite_recipe():
    envelope = _enforced_envelope({})
    envelope["activation_plan"]["dependency_order"] = ["visual_grammar"]
    envelope["activation_plan"]["active_capabilities"] = [
        {"capability_id": "visual_grammar", "activation_mode": "required"},
    ]
    envelope["active_capability_ids"] = ["visual_grammar"]
    envelope["normalized_job_intent"] = {"effective_image_count": 1}
    envelope["resolved_constraint_ledger"]["provider_projection"]["capability_projection"] = {
        "effective_variation_mode": "format_layout_adaptation"
    }
    result = _result(
        metadata={
            "requested_image_count": 1,
            "capability_execution_envelope": envelope,
        },
        candidate_metadata={"output_id": "output_doc297_single_mode"},
    )

    service = V3ProductApiService()
    projection = service._authoritative_mode_execution_projection(result)  # noqa: SLF001
    audit = service._mode_execution_audit_from_result(result, projection)  # noqa: SLF001

    assert projection == {
        "effective_variation_mode": "format_layout_adaptation",
        "mode_execution_projection_source": (
            "resolved_constraint_ledger.provider_projection.capability_projection"
        ),
    }
    assert audit == {
        "schema_version": "v3_mode_execution_audit_v1",
        "mode": "format_layout_adaptation",
        "requested_image_count": 1,
        "contract_status": "not_applicable",
        "suite_direction_active": False,
        "projection_source": "resolved_constraint_ledger.provider_projection.capability_projection",
    }
    projected = service._project_candidate_metadata_from_result(  # noqa: SLF001
        result,
        result.asset_pack.assets[0].metadata["candidate_metadata"],
    )
    assert projected["mode_execution_audit"]["mode"] == "format_layout_adaptation"
    assert "variation_execution_contract" not in projected
    assert "role_specific_generation_plan" not in projected


def test_doc297_enforced_top_level_provider_projection_is_not_mode_authority():
    envelope = _enforced_envelope({})
    envelope["resolved_constraint_ledger"]["provider_projection"]["effective_variation_mode"] = (
        "delivery_suite"
    )
    result = _result(
        metadata={
            "effective_variation_mode": "delivery_suite",
            "capability_execution_envelope": envelope,
        }
    )

    projection = V3ProductApiService()._authoritative_mode_execution_projection(result)  # noqa: SLF001

    assert projection == {}


def test_doc297_shadow_empty_ledger_projection_is_a_safe_empty_projection():
    envelope = _enforced_envelope({})
    envelope["activation_mode"] = "shadow"
    envelope["activation_plan"]["activation_mode"] = "shadow"
    envelope["provider_projection"] = {
        "visual_cluster": {
            "mode_execution_policy": {"mode": "delivery_suite"},
        }
    }
    result = _result(metadata={"capability_execution_envelope": envelope})

    projection = V3ProductApiService()._authoritative_mode_execution_projection(result)  # noqa: SLF001

    assert projection == {}


def test_doc297_incomplete_canonical_prompt_does_not_override_blocked_review():
    result = _result(
        metadata={
            "llm_brain": {
                "llm_used": True,
                "fallback_used": False,
                "prompt_review": {"status": "blocked"},
                "audit": {
                    "remote_canonical_provider_prompts_received": True,
                    "canonical_provider_prompt_stage": "provider_prompt_finalize",
                    "canonical_provider_prompt_stages": ["provider_prompt_finalize"],
                },
                "canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": "too short",
                        "review_status": "approved",
                        "prompt_status": "complete",
                        "semantic_coverage": "complete",
                    }
                ],
            }
        },
        candidate_metadata={"llm_brain": {"prompt_review": {"status": "blocked"}}},
    )
    service = V3ProductApiService()

    projected = service._project_candidate_metadata_from_result(  # noqa: SLF001
        result,
        result.asset_pack.assets[0].metadata["candidate_metadata"],
    )

    assert projected["llm_brain"]["prompt_review"] == {"status": "blocked"}
    assert "llm_brain_prompt_review" not in projected


def test_doc297_canonical_prompts_without_request_count_stay_blocked():
    brain = {
        "llm_used": True,
        "fallback_used": False,
        "audit": {
            "remote_canonical_provider_prompts_received": True,
            "canonical_provider_prompt_stage": "provider_prompt_finalize",
            "canonical_provider_prompt_stages": ["provider_prompt_finalize"],
        },
        "canonical_provider_prompts": [
            {
                "output_index": 1,
                "prompt": "A complete-looking canonical renderer instruction without a count receipt.",
                "review_status": "approved",
                "prompt_status": "complete",
                "semantic_coverage": "complete",
            }
        ],
    }
    for metadata in (
        {"llm_brain": brain},
        {
            "capability_execution_envelope": _enforced_envelope(
                {"mode_execution_policy": {"mode": "selection_candidates"}}
            ),
            "llm_brain": brain,
        },
    ):
        result = _result(metadata=metadata)
        assert V3ProductApiService()._canonical_prompt_review_from_result(result) is None  # noqa: SLF001


def test_doc297_records_mode_projection_conflict_without_hiding_provider_fact():
    result = _result(
        metadata={
            "requested_image_count": 2,
            "capability_execution_envelope": _enforced_envelope(
                {"mode_execution_policy": {"mode": "creative_exploration"}}
            ),
        },
        candidate_metadata={
            "mode_execution_policy": {"mode": "selection_candidates"},
        },
    )

    projected = V3ProductApiService()._project_candidate_metadata_from_result(  # noqa: SLF001
        result,
        result.asset_pack.assets[0].metadata["candidate_metadata"],
    )

    assert projected["mode_execution_policy"] == {"mode": "selection_candidates"}
    assert projected["mode_execution_audit"]["projection_conflicts"] == ["mode_execution_policy"]


def test_doc297_frozen_mode_and_count_win_over_stale_result_metadata():
    result = _result(
        metadata={
            "requested_image_count": 1,
            "effective_variation_mode": "selection_candidates",
            "capability_execution_envelope": {
                **_enforced_envelope(
                    {
                        "mode_execution_policy": {"mode": "creative_exploration"},
                        "variation_execution_contract": {"mode": "creative_exploration", "count": 2},
                    }
                ),
                "normalized_job_intent": {"effective_image_count": 2},
            },
        }
    )
    service = V3ProductApiService()

    projection = service._authoritative_mode_execution_projection(result)  # noqa: SLF001
    audit = service._mode_execution_audit_from_result(result, projection)  # noqa: SLF001

    assert audit["mode"] == "creative_exploration"
    assert audit["requested_image_count"] == 2
    assert audit["contract_status"] == "active"


def test_doc297_ledger_role_recipe_requires_exact_output_binding():
    recipe = {
        "index": 1,
        "role_key": "concept_clean_bright",
        "label": "Clean bright concept",
        "purpose": "show the main concept clearly",
    }
    result = _result(
        metadata={
            "capability_execution_envelope": _enforced_envelope(
                {
                    "mode_execution_policy": {"mode": "creative_exploration"},
                    "role_specific_generation_plan": {
                        "mode": "creative_exploration",
                        "role_recipes": [recipe],
                    },
                    "mode_role_recipe": recipe,
                }
            )
        },
        candidate_metadata={"output_id": "output_doc297_role", "output_index": 1},
    )
    service = V3ProductApiService()

    projected = service._project_candidate_metadata_from_result(  # noqa: SLF001
        result,
        result.asset_pack.assets[0].metadata["candidate_metadata"],
    )

    assert projected["mode_role_recipe"] == recipe

    unbound = service._project_candidate_metadata_from_result(  # noqa: SLF001
        result,
        {
            "output_id": "output_doc297_unbound",
            "output_index": 2,
            "mode_role_recipe": recipe,
        },
    )
    assert "mode_role_recipe" not in unbound


def test_doc297_general_opaque_provider_role_binding_survives_semantic_role_projection():
    semantic_recipe = {
        "index": 1,
        "role_key": "cover_hero",
        "label": "Cover hero",
        "purpose": "show the approved direction as the primary presentation",
    }
    provider_recipe = {
        **semantic_recipe,
        "role_key": "template_deliverable_doc297_1",
        "metadata": {"semantic_role_key": "cover_hero"},
    }
    result = _result(
        metadata={
            "capability_execution_envelope": _enforced_envelope(
                {
                    "mode_execution_policy": {"mode": "delivery_suite"},
                    "role_specific_generation_plan": {
                        "mode": "delivery_suite",
                        "role_recipes": [semantic_recipe],
                    },
                    "mode_role_recipe": semantic_recipe,
                }
            )
        },
        candidate_metadata={
            "output_id": "output_doc297_opaque_role",
            "output_index": 1,
            "mode_role_recipe": provider_recipe,
        },
    )

    projected = V3ProductApiService()._project_candidate_metadata_from_result(  # noqa: SLF001
        result,
        result.asset_pack.assets[0].metadata["candidate_metadata"],
    )

    assert projected["mode_role_recipe"] == provider_recipe
    assert projected["mode_role_recipe"]["role_key"] == "template_deliverable_doc297_1"
    assert projected["mode_role_recipe"]["metadata"]["semantic_role_key"] == "cover_hero"
    assert projected["mode_execution_audit"]["projection_conflicts"] == ["mode_role_recipe"]


def test_doc297_mode_review_drops_an_unbound_raw_recipe_fallback():
    result = _result(
        metadata={},
        candidate_metadata={
            "output_id": "output_doc297_unbound_review",
            "mode_role_recipe": {
                "index": 2,
                "role_key": "wrong_output_role",
            },
        },
    )

    payload = V3ProductApiService()._mode_review_candidates(result)[0]  # noqa: SLF001

    assert payload["mode_role_recipe"] == {}
    assert "mode_role_recipe" not in payload["metadata"]


def test_doc297_recovery_view_can_read_the_frozen_envelope_from_creative_job():
    result = _result(metadata={"requested_image_count": 2})
    result.creative_job.metadata = {
        "capability_execution_envelope": _enforced_envelope(
            {
                "mode_execution_policy": {"mode": "format_layout_adaptation"},
                "variation_execution_requested_image_count": 2,
            }
        )
    }
    service = V3ProductApiService()

    projection = service._authoritative_mode_execution_projection(result)  # noqa: SLF001
    audit = service._mode_execution_audit_from_result(result, projection)  # noqa: SLF001

    assert projection["mode_execution_policy"]["mode"] == "format_layout_adaptation"
    assert audit["requested_image_count"] == 2
    assert audit["projection_source"].endswith("capability_projection")


def test_doc297_enforced_missing_frozen_count_does_not_use_stale_result_count():
    result = _result(
        metadata={
            "requested_image_count": 2,
            "capability_execution_envelope": _enforced_envelope(
                {"mode_execution_policy": {"mode": "delivery_suite"}}
            ),
        }
    )
    service = V3ProductApiService()

    projection = service._authoritative_mode_execution_projection(result)  # noqa: SLF001
    audit = service._mode_execution_audit_from_result(result, projection)  # noqa: SLF001

    assert audit["requested_image_count"] is None
    assert audit["contract_status"] == "missing"


def test_doc297_enforced_prompt_binding_requires_nonempty_envelope_and_ledger_ids():
    result = _result(
        metadata={
            "requested_image_count": 1,
            "capability_execution_envelope": _enforced_envelope(
                {"mode_execution_policy": {"mode": "selection_candidates"}}
            ),
            "llm_brain": {
                "llm_used": True,
                "fallback_used": False,
                "audit": {
                    "remote_canonical_provider_prompts_received": True,
                    "canonical_provider_prompt_stage": "provider_prompt_finalize",
                    "canonical_provider_prompt_stages": ["provider_prompt_finalize"],
                    "canonical_provider_prompt_binding": {
                        "activation_plan_id": "plan_doc297",
                        "execution_envelope_id": "",
                        "constraint_ledger_id": "",
                    },
                },
                "canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": "A complete-looking prompt with a deliberately invalid binding.",
                        "review_status": "approved",
                        "prompt_status": "complete",
                        "semantic_coverage": "complete",
                    }
                ],
            },
        }
    )
    result.metadata["capability_execution_envelope"]["envelope_id"] = ""
    result.metadata["capability_execution_envelope"]["resolved_constraint_ledger"]["ledger_id"] = ""

    assert V3ProductApiService()._canonical_prompt_review_from_result(result) is None  # noqa: SLF001


def test_doc297_fallback_canonical_prompts_never_approve_public_review():
    result = _result(
        metadata={
            "llm_brain": {
                "llm_used": False,
                "fallback_used": True,
                "prompt_review": {"status": "blocked"},
                "audit": {
                    "remote_canonical_provider_prompts_received": True,
                    "canonical_provider_prompt_stage": "provider_prompt_finalize",
                    "canonical_provider_prompt_stages": ["provider_prompt_finalize"],
                },
                "canonical_provider_prompts": [
                    {
                        "output_index": 1,
                        "prompt": "A complete-looking prompt that must still remain blocked.",
                        "review_status": "approved",
                        "prompt_status": "complete",
                        "semantic_coverage": "complete",
                    }
                ],
            }
        },
        candidate_metadata={"llm_brain": {"prompt_review": {"status": "blocked"}}},
    )

    projected = V3ProductApiService()._project_candidate_metadata_from_result(  # noqa: SLF001
        result,
        result.asset_pack.assets[0].metadata["candidate_metadata"],
    )

    assert projected["llm_brain"]["prompt_review"] == {"status": "blocked"}


def test_doc297_doc270_phase3_status_exposes_both_public_audits(monkeypatch):
    result = _result(
        metadata={
            "requested_image_count": 2,
            "capability_execution_envelope": _enforced_envelope(
                {
                    "effective_variation_mode": "delivery_suite",
                    "mode_execution_policy": {"mode": "delivery_suite"},
                    "variation_execution_contract": {"mode": "delivery_suite", "count": 2},
                    "variation_execution_mode": "delivery_suite",
                    "variation_execution_requested_image_count": 2,
                    "variation_execution_contract_enforced": True,
                }
            ),
        }
    )
    service = V3ProductApiService()
    monkeypatch.setattr(
        service,
        "_doc270_general_activation_public_state",
        lambda _record: {"state": "activated_resolved"},
    )

    status = service._doc270_general_phase3_safe_status(_record(result))  # noqa: SLF001

    assert status is not None
    assert status.metadata["effective_variation_mode"] == "delivery_suite"
    assert status.metadata["variation_execution_mode"] == "delivery_suite"
    assert status.metadata["mode_execution_audit"]["mode"] == "delivery_suite"
    public_activation_audit = status.metadata["capability_activation_audit"]
    assert public_activation_audit["activation_mode"] == "enforced"
    assert public_activation_audit["active_capability_ids"] == ["visual_grammar", "suite_direction"]
    assert "plan_id" not in public_activation_audit
    assert "fingerprint" not in public_activation_audit
    assert "active_evidence_ids" not in public_activation_audit


@pytest.mark.parametrize(
    "mode",
    [
        "selection_candidates",
        "delivery_suite",
        "creative_exploration",
        "format_layout_adaptation",
    ],
)
@pytest.mark.parametrize("image_count", [1, 2])
def test_doc297_output_store_restore_preserves_nested_mode_projection(tmp_path, mode, image_count):
    result = _mode_restore_result(mode, image_count)
    # Model the pre-runtime-patch result: Product API receives the effective
    # General mode, but the nested durable projection has not been completed.
    result.metadata["capability_execution_envelope"]["resolved_constraint_ledger"]["provider_projection"][
        "capability_projection"
    ].pop("effective_variation_mode")
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    service = V3ProductApiService(output_store=output_store)

    for packaged in result.asset_pack.assets:
        index = packaged.metadata["candidate_metadata"]["output_index"]
        output_store.save_base64_output(
            job_id=result.asset_pack.job_id,
            candidate_id=packaged.metadata["selected_candidate_id"],
            asset_id=packaged.asset_id,
            provider="local-test",
            model="fixture",
            encoded_image=_ONE_PIXEL_PNG,
            output_id=packaged.metadata["candidate_metadata"]["output_id"],
            metadata={"output_index": index},
        )

    service._persist_mode_execution_projection_to_output_store(result)  # noqa: SLF001

    persisted = output_store.get_output("v3_output_00000000000000000001")
    assert persisted is not None
    persisted_projection = (
        persisted.metadata["capability_execution_envelope"]["resolved_constraint_ledger"]
        ["provider_projection"]["capability_projection"]
    )
    assert persisted_projection["effective_variation_mode"] == mode
    assert "effective_variation_mode" not in persisted.metadata

    restored = V3ProductApiService(
        output_store=V3GeneratedOutputStore(tmp_path / "outputs"),
    )._status_from_output_store(result.asset_pack.job_id)  # noqa: SLF001

    assert restored is not None
    assert restored.metadata["effective_variation_mode"] == mode
    assert restored.metadata["mode_execution_audit"]["mode"] == mode
    assert restored.metadata["mode_execution_audit"]["requested_image_count"] == image_count
    assert restored.metadata["mode_execution_audit"]["contract_status"] == (
        "not_applicable" if image_count == 1 else "active"
    )
    for candidate in restored.candidates:
        assert candidate.metadata["effective_variation_mode"] == mode
        assert candidate.metadata["variation_execution_mode"] == mode
        if image_count == 1:
            assert "variation_execution_contract" not in candidate.metadata
            assert "role_specific_generation_plan" not in candidate.metadata
        else:
            assert candidate.metadata["variation_execution_contract"] == {"mode": mode, "count": image_count}
            assert candidate.metadata["role_specific_generation_plan"]["mode"] == mode


@pytest.mark.parametrize(
    "mode",
    [
        "selection_candidates",
        "delivery_suite",
        "creative_exploration",
        "format_layout_adaptation",
    ],
)
@pytest.mark.parametrize("image_count", [1, 2])
def test_doc297_closure_status_preserves_nested_mode_execution_facts(mode, image_count):
    result = _mode_restore_result(mode, image_count)
    record = _record(result)
    record.status = ProductJobStatusValue.BLOCKED
    record.request.metadata = {
        "project_id": "project_doc297",
        "template_id": "general_template",
        "provider_deliverability_closure_receipt": {"state": "closed"},
    }

    status = V3ProductApiService()._status_from_record(record)  # noqa: SLF001

    assert status.metadata["effective_variation_mode"] == mode
    assert status.metadata["variation_execution_mode"] == mode
    assert status.metadata["mode_execution_audit"]["mode"] == mode
    assert status.metadata["mode_execution_audit"]["requested_image_count"] == image_count
    assert status.metadata["mode_execution_audit"]["contract_status"] == (
        "not_applicable" if image_count == 1 else "active"
    )
    if image_count == 1:
        assert "variation_execution_contract" not in status.metadata
        assert "role_specific_generation_plan" not in status.metadata
    else:
        assert status.metadata["variation_execution_contract"]["mode"] == mode
        assert status.metadata["role_specific_generation_plan"]["mode"] == mode
