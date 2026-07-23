from __future__ import annotations

from types import SimpleNamespace

from alchemy_creative_agent_3_0.app.generation_router.providers import (
    GenerationRequest,
    ProductionImageGenerationProvider,
)
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities import CapabilityInput
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    AdaptiveReferenceRetriever,
    IdentityDriftGuard,
    IdentityRepairStrategyRouter,
    StrongReferenceBinding,
    SubjectContinuityAssetPackBuilder,
    VisualCapabilityClusterModule,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.adaptive_reference import (
    infer_target_framing,
)


class _StaticReferenceProfiler:
    def profile_reference(self, path: str) -> dict:
        if "profile" in path:
            return {
                "status": "ready",
                "view_hint": "right_profile",
                "framing_hint": "head_shoulders",
                "face_detection_confidence": 0.94,
                "embedding_persisted": False,
            }
        return {
            "status": "ready",
            "view_hint": "front",
            "framing_hint": "head_shoulders",
            "face_detection_confidence": 0.92,
            "embedding_persisted": False,
        }


def _binding(
    source_id: str,
    *,
    source_type: str,
    path: str,
    selected: bool = False,
    score: float | None = None,
) -> StrongReferenceBinding:
    metadata = {"selected_output_anchor": selected}
    if score is not None:
        metadata["post_generation_review"] = {"fused_identity_score": score, "geometry_score": score}
    return StrongReferenceBinding(
        binding_id=f"binding_{source_id}",
        source_type=source_type,
        source_id=source_id,
        asset_id=source_id,
        output_id=source_id if "generated" in source_type or selected else None,
        file_path=path,
        role="generated_identity_reference" if selected or "generated" in source_type else "face_reference",
        strength="medium" if selected else "hard",
        use_policy="identity",
        lock_targets=["face_identity"],
        provider_input_required=True,
        confidence=0.9,
        metadata=metadata,
    )


def _package(
    bindings: list[StrongReferenceBinding],
    *,
    selected_outputs: list[dict] | None = None,
):
    guard = IdentityDriftGuard().build(
        project_id="project_doc97",
        job_id="job_doc97",
        subject_type="character",
        strong_bindings=bindings,
        selected_outputs=selected_outputs or [],
    )
    package = SubjectContinuityAssetPackBuilder(reference_profiler=_StaticReferenceProfiler()).build(
        project_id="project_doc97",
        job_id="job_doc97",
        subject_type="character",
        strong_bindings=bindings,
        drift_guard=guard,
    )
    return guard, package


def test_doc97_user_selected_master_leads_but_uploaded_root_is_retained() -> None:
    selected = _binding(
        "selected_generated",
        source_type="selected_output",
        path="D:/selected_profile.png",
        selected=True,
        score=0.77,
    )
    root = _binding("uploaded_root", source_type="uploaded", path="D:/root_front.png")
    guard, package = _package([selected, root], selected_outputs=[{"output_id": "selected_generated"}])
    plan = AdaptiveReferenceRetriever().build(
        project_id="project_doc97",
        job_id="job_doc97",
        user_input="生成右侧脸的城市夜景人像",
        package=package,
    )

    assert package.user_selected_master_ids == ["selected_generated"]
    assert package.uploaded_root_truth_ids == ["uploaded_root"]
    assert plan.ordered_source_ids[:2] == ["selected_generated", "uploaded_root"]
    assert plan.preserve_uploaded_root is True
    assert guard.root_comparison_required is True


def test_doc97_low_scored_unselected_generated_support_is_quarantined() -> None:
    root = _binding("uploaded_root", source_type="uploaded", path="D:/root_front.png")
    weak = _binding(
        "generated_weak",
        source_type="generated_reference",
        path="D:/weak_profile.png",
        score=0.61,
    )
    guard, package = _package([root, weak])

    assert guard.quarantined_generated_ids == ["generated_weak"]
    assert package.quarantined_ids == ["generated_weak"]
    assert "generated_weak" not in package.provider_candidate_ids


def test_doc97_explicit_selection_overrides_automatic_quarantine_with_audit() -> None:
    root = _binding("uploaded_root", source_type="uploaded", path="D:/root_front.png")
    weak_selected = _binding(
        "selected_weak",
        source_type="selected_output",
        path="D:/selected_profile.png",
        selected=True,
        score=0.61,
    )
    guard, package = _package(
        [weak_selected, root],
        selected_outputs=[{"output_id": "selected_weak"}],
    )

    assert guard.user_override_ids == ["selected_weak"]
    assert "selected_weak" in package.provider_candidate_ids
    assert package.uploaded_root_truth_ids == ["uploaded_root"]


def test_doc97_view_aware_retrieval_prefers_matching_reference_inside_same_authority() -> None:
    root_front = _binding("root_front", source_type="uploaded", path="D:/root_front.png")
    root_profile = _binding("root_profile", source_type="uploaded", path="D:/root_profile.png")
    _guard, package = _package([root_front, root_profile])
    plan = AdaptiveReferenceRetriever().build(
        project_id="project_doc97",
        job_id="job_doc97",
        user_input="右侧脸特写，安静自然的纪实摄影",
        package=package,
    )

    assert plan.target_view == "right_profile"
    assert plan.ordered_source_ids[0] == "root_profile"


def test_doc97_cluster_exposes_injectable_child_module_contracts() -> None:
    module = VisualCapabilityClusterModule(
        subject_asset_pack_builder=SubjectContinuityAssetPackBuilder(
            reference_profiler=_StaticReferenceProfiler()
        )
    )
    result = module.execute(
        CapabilityInput(
            job_id="job_doc97_cluster",
            scenario_id="general_creative",
            user_input="使用同一个人物，生成右侧脸写实人像",
            metadata={
                "template_id": "general_template",
                "project_context_snapshot": {
                    "project_id": "project_doc97",
                    "template_id": "general_template",
                    "selected_output_assets": [
                        {
                            "output_id": "selected_generated",
                            "asset_id": "selected_generated",
                            "file_path": "D:/selected_profile.png",
                            "source_type": "selected_output",
                            "metadata": {"post_generation_review": {"fused_identity_score": 0.84}},
                        }
                    ],
                    "uploaded_reference_assets": [
                        {
                            "asset_ref_id": "uploaded_root",
                            "asset_id": "uploaded_root",
                            "file_path": "D:/root_front.png",
                            "source_type": "uploaded",
                            "role": "face_reference",
                            "use_policy": "identity",
                        }
                    ],
                },
            },
        )
    )
    cluster = result.facts["visual_capability_cluster"]

    assert cluster["subject_continuity_asset_package"]["applies"] is True
    assert cluster["adaptive_reference_selection_plan"]["applies"] is True
    assert cluster["identity_drift_guard_plan"]["applies"] is True
    assert cluster["identity_repair_strategy_plan"]["strategy"] == "regenerate_from_ranked_identity_pack"
    assert "subject_continuity_asset_pack" in cluster["child_module_ids"]
    assert "adaptive_reference_retriever" in cluster["child_module_ids"]


def _provider_request(cluster: dict, user_input: str) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_doc97",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="same-person portrait",
    )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_doc97",
            asset_id=asset.asset_id,
            visual_prompt=user_input,
            negative_prompt="different person",
            text_policy="do_not_render_final_text_in_image_model",
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_doc97", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc97",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={"user_input": user_input, "visual_cluster": cluster},
    )


def test_doc97_provider_applies_ranked_sources_and_keeps_non_identity_reference() -> None:
    cluster = {
        "adaptive_reference_selection_plan": {
            "applies": True,
            "target_view": "right_profile",
            "target_framing": "head_shoulders",
            "ordered_source_ids": ["selected_profile", "uploaded_root"],
            "excluded_source_ids": ["generated_weak"],
            "max_identity_sources": 3,
        },
        "subject_continuity_asset_package": {
            "applies": True,
            "evidence": [
                {
                    "source_id": "selected_profile",
                    "asset_id": "selected_profile",
                    "authority": "user_selected_master",
                    "view_hint": "right_profile",
                    "framing_hint": "head_shoulders",
                    "trust_score": 0.98,
                },
                {
                    "source_id": "uploaded_root",
                    "asset_id": "uploaded_root",
                    "authority": "uploaded_root_truth",
                    "view_hint": "front",
                    "framing_hint": "head_shoulders",
                    "trust_score": 0.95,
                },
                {
                    "source_id": "generated_weak",
                    "asset_id": "generated_weak",
                    "authority": "reviewed_generated_support",
                    "view_hint": "right_profile",
                    "framing_hint": "head_shoulders",
                    "trust_score": 0.50,
                },
            ],
        },
    }
    request = _provider_request(cluster, "右侧脸人像")
    provider = ProductionImageGenerationProvider(output_store=object())
    ordered = provider._apply_adaptive_reference_selection(  # noqa: SLF001
        request,
        [
            {"asset_id": "uploaded_root", "role": "face_reference", "use_policy": "identity"},
            {"asset_id": "generated_weak", "role": "face_reference", "use_policy": "identity"},
            {"asset_id": "style_ref", "role": "style_reference", "use_policy": "style"},
            {"asset_id": "selected_profile", "role": "face_reference", "use_policy": "identity"},
        ],
    )

    assert [item["asset_id"] for item in ordered] == ["selected_profile", "uploaded_root", "style_ref"]
    audit = ordered[0]["metadata"]["doc97_adaptive_reference_selection"]
    assert audit["applied_source_ids"] == ["selected_profile", "uploaded_root"]
    assert audit["target_view"] == "right_profile"


def test_doc190_character_card_upper_shoulders_framing_overrides_negative_half_body_terms() -> None:
    assert (
        infer_target_framing(
            "head, neck and upper shoulders only; not a half-body crop; not zoomed in"
        )
        == "head_shoulders"
    )
    assert infer_target_framing("头部、颈部和上肩景别，禁止大头照、半身照") == "head_shoulders"


def test_doc190_negative_half_body_terms_do_not_request_half_body_framing() -> None:
    assert infer_target_framing("plain white card, no half-body crop") == "unknown"
    assert infer_target_framing("白底建模，禁止半身照") == "unknown"


def test_doc97_generic_provider_blocks_face_local_repair_but_legacy_result_remains_compatible() -> None:
    service = object.__new__(V3ProductApiService)
    blocked = SimpleNamespace(
        metadata={
            "visual_cluster": {
                "identity_repair_strategy_plan": {
                    "applies": True,
                    "allow_face_local_repair": False,
                    "strategy": "regenerate_from_ranked_identity_pack",
                }
            }
        }
    )

    assert service._identity_local_repair_metadata(  # noqa: SLF001
        blocked,
        attempt_index=1,
        reason_codes=["identity_metric_below_commercial_target"],
    ) == {}


def test_doc100_stale_identity_native_capability_cannot_enable_local_pixel_repair() -> None:
    _guard, package = _package(
        [_binding("uploaded_root", source_type="uploaded", path="D:/root_front.png")]
    )
    plan = IdentityRepairStrategyRouter().build(
        project_id="project_doc97",
        job_id="job_doc97",
        package=package,
        metadata={"provider_capabilities": {"identity_native_local_repair": True}},
    )

    assert plan.allow_face_local_repair is False
    assert plan.strategy == "regenerate_from_ranked_identity_pack"
    assert plan.fallback_strategy == "hold_best_reviewed_result"
    assert plan.metadata["sole_renderer"] == "gpt-image-2"
