from types import SimpleNamespace

from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.shared_capabilities import CapabilityInput, SharedCapabilityRegistry
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    GeneratedOutputResolution,
    OutputQualityReviewMerger,
    VisualInspectionReport,
)


def test_doc66_visual_cluster_exports_reference_closure_and_mode_quality_profile() -> None:
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        CapabilityInput(
            job_id="job_doc66_cluster",
            scenario_id="general_creative",
            user_input="Create same-model East Asian summer portrait alternatives with green dyed hair and natural pose changes",
            metadata={
                "template_id": "general_creative",
                "requested_image_count": 3,
                "variation_mode": "selection_candidates",
                "project_context_snapshot": {
                    "project_id": "project_doc66_cluster",
                    "template_id": "general_creative",
                    "selected_output_assets": [
                        {
                            "output_id": "selected_portrait_output",
                            "asset_id": "selected_portrait_output",
                            "file_path": "C:/tmp/selected_portrait_output.png",
                        }
                    ],
                },
            },
        ),
        module_ids=["visual_capability_cluster"],
    )

    cluster = result.results[-1].facts["visual_capability_cluster"]
    closure = cluster["strong_reference_closure_package"]
    mode_profile = cluster["mode_quality_profile"]
    role_plan = cluster["role_specific_generation_plan"]

    assert closure["active"] is True
    assert closure["reference_strength"] == "hard"
    assert "selected_portrait_output" in closure["provider_reference_required_ids"]
    assert any("identity truth" in item for item in closure["provider_prompt_rules"])
    assert any("expression" in item for item in closure["allowed_variations"])
    assert mode_profile["mode"] == "selection_candidates"
    assert "small visible pose/expression/crop differences" in mode_profile["review_priorities"]
    assert "strong_reference_closure" in cluster["child_module_ids"]
    assert "mode_quality_profile" in cluster["child_module_ids"]
    assert any("identity truth" in item for item in role_plan["prompt_additions"])
    assert any("same exact still repeated" in item for item in role_plan["negative_additions"])


def test_doc66_mode_quality_profiles_are_distinct_across_general_modes() -> None:
    registry = SharedCapabilityRegistry.with_default_modules()
    profiles = {}

    for mode in ["selection_candidates", "delivery_suite", "creative_exploration", "format_layout_adaptation"]:
        result = registry.run(
            CapabilityInput(
                job_id=f"job_doc66_{mode}",
                scenario_id="general_creative",
                user_input="Create a clean summer portrait set",
                metadata={
                    "template_id": "general_creative",
                    "variation_mode": mode,
                    "project_context_snapshot": {"project_id": f"project_doc66_{mode}", "template_id": "general_creative"},
                },
            ),
            module_ids=["visual_capability_cluster"],
        )
        cluster = result.results[-1].facts["visual_capability_cluster"]
        profiles[mode] = cluster["mode_quality_profile"]

    assert profiles["selection_candidates"]["retry_triggers"] != profiles["delivery_suite"]["retry_triggers"]
    assert "creative_distance_missing" in profiles["creative_exploration"]["retry_triggers"]
    assert "format_layout_collapse" in profiles["format_layout_adaptation"]["retry_triggers"]
    assert "delivery_suite_role_collapse" in profiles["delivery_suite"]["retry_triggers"]


def test_doc66_post_generation_review_builds_candidate_scoped_signal_package() -> None:
    merger = OutputQualityReviewMerger()
    inspection = VisualInspectionReport(
        inspection_id="inspection_doc66_retry",
        project_id="project_doc66_review",
        job_id="job_doc66_review",
        candidate_id="candidate_doc66_retry",
        output_id="output_doc66_retry",
        mode="vision",
        status="fail_retryable",
        confidence=0.91,
        detected_issues=[
            {"code": "faint_corner_watermark", "retryable": True},
            {"code": "identity_drift", "retryable": True},
        ],
        retryable=True,
        retry_patch={
            "artifact_repair": ["remove any lower-right watermark or AI mark"],
            "identity_reinforcement": ["keep the selected person's broad face shape and hair direction"],
            "negative_additions": ["watermark", "changed identity"],
        },
    )

    package = merger.build_package(
        job_id="job_doc66_review",
        project_id="project_doc66_review",
        resolutions=[
            GeneratedOutputResolution(
                resolution_id="resolution_doc66",
                project_id="project_doc66_review",
                job_id="job_doc66_review",
                candidate_id="candidate_doc66_retry",
                output_id="output_doc66_retry",
                status="ready",
            )
        ],
        inspections=[inspection],
        max_attempts=1,
    )

    signal_package = package.real_review_signal_package
    assert signal_package is not None
    assert signal_package.retryable_candidate_ids == ["candidate_doc66_retry"]
    assert signal_package.retryable_output_ids == ["output_doc66_retry"]
    assert signal_package.issue_summary["faint_corner_watermark"] == 1
    assert signal_package.reference_continuity_status == "retryable_issue"
    assert signal_package.candidate_signals[0].recommended_action == "retry"
    assert "artifact" in signal_package.candidate_signals[0].metadata["issue_groups"]
    assert "identity" in signal_package.candidate_signals[0].metadata["issue_groups"]


def test_doc66_product_api_prefers_real_review_signal_for_precise_retry() -> None:
    service = V3ProductApiService()
    result = SimpleNamespace(
        metadata={
            "visual_cluster": {
                "quality_review_reports": [
                    {"metadata": {"post_generation": True}, "status": "fail_retryable"},
                ],
                "real_review_signal_package": {
                    "candidate_signals": [
                        {
                            "candidate_id": "candidate_doc66_retry",
                            "output_id": "output_doc66_retry",
                            "recommended_action": "retry",
                            "retryable_issue_codes": ["visible_text_artifact"],
                            "retry_patch": {
                                "artifact_repair": ["remove visible text and watermark"],
                                "negative_additions": ["visible text", "watermark"],
                            },
                            "metadata": {"issue_groups": ["artifact"]},
                        }
                    ]
                },
            }
        }
    )

    codes, patch, source = service._visual_retry_signal(result, {})

    assert source == "real_review_signal_package"
    assert codes == ["visible_text_artifact"]
    assert patch["target_candidate_ids"] == ["candidate_doc66_retry"]
    assert patch["target_output_ids"] == ["output_doc66_retry"]
    assert "remove visible text and watermark" in patch["artifact_repair"]
    assert "artifact" in patch["issue_groups"]
