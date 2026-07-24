from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from alchemy_creative_agent_3_0.app.generation_router import (
    GenerationRequest,
    ProductionImageGenerationProvider,
    build_provider_generation_request,
)
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)
from app.services.provider_reference import prepare_reference_truth_derivatives
from app.providers.base import ProviderRuntimeError


def _image(path: Path, color: tuple[int, int, int]) -> Path:
    Image.new("RGB", (720, 720), color=color).save(path, format="PNG")
    return path


def _request(
    root: Path,
    front: Path,
    three_quarter: Path,
    *,
    third_output_id: str = "three_quarter_output",
) -> GenerationRequest:
    policy = [
        {
            "source_asset_id": source_id,
            "source_role": "portrait_identity_reference",
            "identity_geometry": "hard",
            "prompt_owned_channels": ["hair_direction", "lighting_color", "scene_background"],
        }
        for source_id in ("root_asset", "front_output", third_output_id)
    ]
    asset = AssetSpec(
        asset_id="profile_asset",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="Professional profile anchor candidate",
    )
    uploaded_assets = [
        {
            "asset_id": "root_asset",
            "file_path": str(root),
            "source_type": "uploaded",
            "role": "face_reference",
            "use_policy": "identity",
            "strength": "hard",
            "provider_input_required": True,
            "metadata": {
                "reference_sanitization": {
                    "suppress_full_frame_provider_reference": True,
                    "reason_codes": ["professional_identity_only"],
                }
            },
        },
    ]
    for asset_id, path in (("front_output", front), (third_output_id, three_quarter)):
        uploaded_assets.append(
            {
                "asset_id": asset_id,
                "output_id": asset_id,
                "file_path": str(path),
                "source_type": "selected_output",
                "role": "face_reference",
                "use_policy": "identity",
                "strength": "hard",
                "provider_input_required": True,
                "source_integrity_id": f"sha256:{asset_id}",
                "metadata": {"canonical_output_binding": True},
            }
        )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_professional_budget",
            asset_id=asset.asset_id,
            visual_prompt="Create a faithful right-facing profile portrait with natural human realism.",
            negative_prompt="generic face, beauty filter, identity drift",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["plain white studio"],
            layout_notes=["profile portrait"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_professional_budget", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_professional_budget",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_professional_budget",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "user_input": "Create a faithful right-facing profile portrait with natural human realism.",
            "professional_mode": "professional",
            "professional_identity_reference_strategy": "serial_anchor_pack_root_reuse_v1",
            "professional_reference_stage": "profile",
            "uploaded_assets": uploaded_assets,
            "visual_cluster": {
                "resolved_reference_policy_package": {
                    "applies": True,
                    "policies": policy,
                }
            },
        },
    )


def _reverse_45_request(root: Path, front: Path, profile: Path, right25: Path) -> GenerationRequest:
    request = _request(root, front, right25, third_output_id="right25_output")
    uploaded_assets = list(request.metadata["uploaded_assets"])
    uploaded_assets.append(
        {
            "asset_id": "profile_output",
            "output_id": "profile_output",
            "file_path": str(profile),
            "source_type": "selected_output",
            "role": "face_reference",
            "use_policy": "identity",
            "strength": "hard",
            "provider_input_required": True,
            "source_integrity_id": "sha256:profile_output",
            "metadata": {"canonical_output_binding": True},
        }
    )
    by_id = {str(item.get("asset_id")): item for item in uploaded_assets}
    ordered_assets = [
        by_id["root_asset"],
        by_id["front_output"],
        by_id["profile_output"],
        by_id["right25_output"],
    ]
    metadata = dict(request.metadata)
    metadata.update(
        {
            "professional_reference_stage": "reverse_three_quarter",
            "professional_anchor_capture_scope": "character_card_face_identity",
            "uploaded_assets": ordered_assets,
            "professional_anchor_reference_assets": [
                by_id["front_output"],
                by_id["profile_output"],
                by_id["right25_output"],
            ],
        }
    )
    return request.model_copy(update={"metadata": metadata})


def _expression_request(front: Path) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="expression_asset",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="2:3",
        purpose="Professional expression card candidate",
    )
    front_reference = {
        "asset_id": "front_output",
        "output_id": "front_output",
        "file_path": str(front),
        "source_type": "selected_output",
        "role": "face_reference",
        "use_policy": "identity",
        "strength": "hard",
        "provider_input_required": True,
        "source_integrity_id": "sha256:front_output",
        "metadata": {"canonical_output_binding": True},
    }
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_expression_budget",
            asset_id=asset.asset_id,
            visual_prompt="Create the same Character Card front portrait with a laugh expression only.",
            negative_prompt="different crop, different camera distance",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["inherit approved face.front card"],
            layout_notes=["2:3 head-neck-upper-shoulders card framing"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_expression_budget", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_expression_budget",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_expression_budget",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "user_input": "Create a front Character Card laugh keyframe.",
            "professional_mode": "professional",
            "professional_identity_reference_strategy": "character_card_shared_identity_v1",
            "professional_character_card_preparation": True,
            "professional_character_card_stage": "expression_set",
            "professional_character_card_slot": "expression.laugh",
            "professional_anchor_reference_assets": [front_reference],
            "uploaded_assets": [front_reference],
        },
    )


def test_root_identity_derivative_can_be_reused_without_second_ai_generation(tmp_path: Path) -> None:
    root = _image(tmp_path / "root.png", (220, 180, 160))
    derivatives = prepare_reference_truth_derivatives(
        root,
        asset_id="root_asset",
        truth_layers=["portrait_identity_truth"],
        portrait_identity_derivative_kinds=("portrait_identity_geometry_crop",),
    )

    assert len(derivatives) == 1
    assert derivatives[0]["derivative_kind"] == "portrait_identity_geometry_crop"


def test_professional_profile_uses_five_references_root_once_and_winners_twice(tmp_path: Path) -> None:
    request = _request(
        _image(tmp_path / "root.png", (220, 180, 160)),
        _image(tmp_path / "front.png", (220, 181, 160)),
        _image(tmp_path / "three-quarter.png", (220, 182, 160)),
    )
    provider = ProductionImageGenerationProvider()
    references = provider._reference_assets(request)  # noqa: SLF001
    plan = provider._asset_plan(request, references)  # noqa: SLF001

    assert plan["provider_input_plan"]["reference_image_count"] == 5
    assert [item["source_asset_id"] for item in plan["assets"]] == [
        "root_asset",
        "front_output",
        "front_output",
        "three_quarter_output",
        "three_quarter_output",
    ]
    assert [item["derivative_kind"] for item in plan["assets"]] == [
        "portrait_identity_pose_geometry_crop",
        "portrait_identity_crop",
        "portrait_identity_pose_geometry_crop",
        "portrait_identity_crop",
        "portrait_identity_pose_geometry_crop",
    ]
    evidence = plan["provider_input_plan"]["view_conditioned_evidence"]
    assert evidence["ready"] is True
    assert evidence["required_source_scopes"] == {
        "root_asset": ["pose_geometry"],
        "front_output": ["feature_detail", "pose_geometry"],
        "three_quarter_output": ["feature_detail", "pose_geometry"],
    }

    legacy_metadata = dict(request.metadata)
    legacy_metadata.pop("professional_identity_reference_strategy", None)
    legacy_request = request.model_copy(update={"metadata": legacy_metadata})
    legacy_provider = ProductionImageGenerationProvider()
    legacy_references = legacy_provider._reference_assets(legacy_request)
    legacy_plan = legacy_provider._asset_plan(legacy_request, legacy_references)  # noqa: SLF001
    assert legacy_plan["provider_input_plan"]["reference_image_count"] == 6


def test_doc190_character_card_reverse_45_uses_original_front_as_framing_reference_without_mirror(
    tmp_path: Path,
) -> None:
    request = _reverse_45_request(
        _image(tmp_path / "root.png", (220, 180, 160)),
        _image(tmp_path / "front.png", (220, 181, 160)),
        _image(tmp_path / "profile.png", (220, 183, 160)),
        _image(tmp_path / "right25.png", (220, 182, 160)),
    )
    provider = ProductionImageGenerationProvider()
    references = provider._reference_assets(request)  # noqa: SLF001
    plan = provider._asset_plan(request, references)  # noqa: SLF001

    assert plan["provider_input_plan"]["reference_image_count"] == 5
    assert [(item["source_asset_id"], item["derivative_kind"]) for item in plan["assets"]] == [
        ("root_asset", "portrait_identity_pose_geometry_crop"),
        ("front_output", "portrait_identity_crop"),
        ("front_output", "character_card_full_frame_framing_reference"),
        ("profile_output", "portrait_identity_pose_geometry_crop"),
        ("right25_output", "portrait_identity_crop"),
    ]
    evidence = plan["provider_input_plan"]["view_conditioned_evidence"]
    assert evidence["ready"] is True
    assert evidence["required_source_scopes"] == {
        "root_asset": ["pose_geometry"],
        "front_output": ["feature_detail", "card_framing"],
        "profile_output": ["pose_geometry"],
        "right25_output": ["feature_detail"],
    }
    framing_reference = plan["assets"][2]
    assert framing_reference["provider_reference_derivative"] is False
    assert framing_reference["identity_evidence_scope"] == "card_framing"
    assert framing_reference["reference_truth_layer"] == "character_card_framing_truth"
    assert framing_reference["character_card_framing_mirrored"] is False
    assert framing_reference["character_card_framing_reference_mode"] == "independent_original_card_framing"
    assert framing_reference["asset_id"] == "front_output"
    assert framing_reference["storage_path"] == str(request.metadata["uploaded_assets"][1]["file_path"])
    assert "horizontal flip" in framing_reference["prompt_constraints"][0]


def test_doc216_expression_set_uses_front_full_frame_as_first_provider_reference(
    tmp_path: Path,
) -> None:
    request = _expression_request(_image(tmp_path / "front.png", (220, 181, 160)))
    provider = ProductionImageGenerationProvider()
    references = provider._reference_assets(request)  # noqa: SLF001
    plan = provider._asset_plan(request, references)  # noqa: SLF001

    assert plan["provider_input_plan"]["reference_image_count"] == 3
    assert [(item["source_asset_id"], item["derivative_kind"]) for item in plan["assets"]] == [
        ("front_output", "character_card_full_frame_framing_reference"),
        ("front_output", "portrait_identity_crop"),
        ("front_output", "portrait_identity_pose_geometry_crop"),
    ]
    assert plan["assets"][0]["identity_evidence_scope"] == "card_framing"
    assert plan["provider_input_plan"]["reference_image_asset_ids"][0] == "front_output"


def test_doc190_provider_request_projection_preserves_character_card_reference_scope(
    tmp_path: Path,
) -> None:
    request = _reverse_45_request(
        _image(tmp_path / "root.png", (220, 180, 160)),
        _image(tmp_path / "front.png", (220, 181, 160)),
        _image(tmp_path / "profile.png", (220, 183, 160)),
        _image(tmp_path / "right25.png", (220, 182, 160)),
    )
    generation_metadata = dict(request.generation_plan.metadata or {})
    generation_metadata.update(
        {
            "professional_identity_reference_strategy": "serial_anchor_pack_root_reuse_v1",
            "professional_reference_stage": "reverse_three_quarter",
            "professional_anchor_capture_scope": "character_card_face_identity",
            "professional_anchor_reference_assets": list(
                request.metadata["professional_anchor_reference_assets"]
            ),
            "uploaded_assets": list(request.metadata["uploaded_assets"]),
            "visual_cluster": request.metadata["visual_cluster"],
        }
    )
    projected = build_provider_generation_request(
        asset_spec=request.asset_spec,
        layout_plan=request.layout_plan,
        prompt_compilation=request.prompt_compilation,
        condition_plan=request.condition_plan,
        generation_plan=request.generation_plan.model_copy(update={"metadata": generation_metadata}),
        job_id="job_doc190_projection",
    )
    provider = ProductionImageGenerationProvider()
    references = provider._reference_assets(projected)  # noqa: SLF001
    plan = provider._asset_plan(projected, references)  # noqa: SLF001

    assert projected.metadata["professional_anchor_capture_scope"] == "character_card_face_identity"
    assert len(projected.metadata["professional_anchor_reference_assets"]) == 3
    assert [(item["source_asset_id"], item["derivative_kind"]) for item in plan["assets"]] == [
        ("root_asset", "portrait_identity_pose_geometry_crop"),
        ("front_output", "portrait_identity_crop"),
        ("front_output", "character_card_full_frame_framing_reference"),
        ("profile_output", "portrait_identity_pose_geometry_crop"),
        ("right25_output", "portrait_identity_crop"),
    ]


def test_standard_mode_keeps_both_identity_derivatives(tmp_path: Path) -> None:
    source = _image(tmp_path / "portrait.png", (220, 180, 160))
    derivatives = prepare_reference_truth_derivatives(
        source,
        asset_id="ordinary_portrait",
        truth_layers=["portrait_identity_truth"],
    )

    assert [item["derivative_kind"] for item in derivatives] == [
        "portrait_identity_crop",
        "portrait_identity_geometry_crop",
    ]


def test_doc214_character_card_expression_set_uses_full_frame_front_as_framing_authority(
    tmp_path: Path,
) -> None:
    front = _image(tmp_path / "front.png", (220, 181, 160))
    request = _request(front, front, front)
    front_asset = {
        "asset_id": "front_output",
        "output_id": "front_output",
        "file_path": str(front),
        "source_type": "selected_output",
        "role": "face_reference",
        "use_policy": "identity",
        "strength": "hard",
        "provider_input_required": True,
        "source_integrity_id": "sha256:front_output",
        "metadata": {"canonical_output_binding": True},
    }
    metadata = dict(request.metadata)
    metadata.update(
        {
            "professional_identity_reference_strategy": "character_card_shared_identity_v1",
            "professional_character_card_stage": "expression_set",
            "professional_character_card_slot": "expression.laugh",
            "professional_reference_stage": "character_card_expression_set",
            "professional_anchor_reference_assets": [front_asset],
            "uploaded_assets": [front_asset],
            "visual_cluster": {
                "resolved_reference_policy_package": {
                    "applies": True,
                    "policies": [
                        {
                            "source_asset_id": "front_output",
                            "source_role": "portrait_identity_reference",
                            "identity_geometry": "hard",
                            "prompt_owned_channels": [
                                "hair_direction",
                                "lighting_color",
                                "scene_background",
                            ],
                        }
                    ],
                }
            },
        }
    )
    request = request.model_copy(update={"metadata": metadata})
    provider = ProductionImageGenerationProvider()
    references = provider._reference_assets(request)  # noqa: SLF001
    plan = provider._asset_plan(request, references)  # noqa: SLF001

    assert plan["provider_input_plan"]["reference_image_count"] == 3
    assert [(item["source_asset_id"], item["derivative_kind"]) for item in plan["assets"]] == [
        ("front_output", "character_card_full_frame_framing_reference"),
        ("front_output", "portrait_identity_crop"),
        ("front_output", "portrait_identity_pose_geometry_crop"),
    ]
    framing_reference = plan["assets"][0]
    assert framing_reference["identity_evidence_scope"] == "card_framing"
    assert framing_reference["reference_truth_layer"] == "character_card_framing_truth"
    assert "framing authority" in " ".join(framing_reference["prompt_constraints"])


def test_doc176_two_source_professional_front_keeps_the_two_reference_budget(tmp_path: Path) -> None:
    root = _image(tmp_path / "root.png", (220, 180, 160))
    supplement = _image(tmp_path / "supplement.png", (218, 182, 164))
    request = _request(root, root, root)
    metadata = dict(request.metadata)
    metadata.update(
        {
            "professional_reference_stage": "standard_front",
            "professional_anchor_initial_multi_source": True,
            "uploaded_assets": [
                {
                    "asset_id": "root_asset",
                    "file_path": str(root),
                    "source_type": "uploaded",
                    "role": "face_reference",
                    "use_policy": "identity",
                    "strength": "hard",
                    "provider_input_required": True,
                    "metadata": {
                        "reference_sanitization": {
                            "suppress_full_frame_provider_reference": True,
                            "reason_codes": ["professional_identity_only"],
                        }
                    },
                },
                {
                    "asset_id": "supplement_asset",
                    "file_path": str(supplement),
                    "source_type": "uploaded",
                    "role": "face_reference",
                    "use_policy": "identity",
                    "strength": "hard",
                    "provider_input_required": True,
                    "metadata": {
                        "reference_sanitization": {
                            "suppress_full_frame_provider_reference": True,
                            "reason_codes": ["professional_identity_only"],
                        }
                    },
                },
            ],
            "visual_cluster": {
                "resolved_reference_policy_package": {
                    "applies": True,
                    "policies": [
                        {
                            "source_asset_id": source_id,
                            "source_role": "portrait_identity_reference",
                            "identity_geometry": "hard",
                            "prompt_owned_channels": ["hair_direction", "lighting_color", "scene_background"],
                        }
                        for source_id in ("root_asset", "supplement_asset")
                    ],
                }
            },
        }
    )
    request = request.model_copy(update={"metadata": metadata})
    provider = ProductionImageGenerationProvider()
    references = provider._reference_assets(request)  # noqa: SLF001
    plan = provider._asset_plan(request, references)  # noqa: SLF001

    assert plan["provider_input_plan"]["reference_image_count"] == 2
    assert [item["source_asset_id"] for item in plan["assets"]] == ["root_asset", "supplement_asset"]
    assert [item["derivative_kind"] for item in plan["assets"]] == [
        "portrait_identity_stage_flexible_feature_crop",
        "portrait_identity_stage_flexible_feature_crop",
    ]


def test_pose_geometry_derivative_preserves_a_view_conditioned_crop_scope(tmp_path: Path) -> None:
    source = _image(tmp_path / "portrait.png", (220, 180, 160))
    derivatives = prepare_reference_truth_derivatives(
        source,
        asset_id="professional_root",
        truth_layers=["portrait_identity_truth"],
        portrait_identity_derivative_kinds=("portrait_identity_pose_geometry_crop",),
    )

    assert len(derivatives) == 1
    derivative = derivatives[0]
    assert derivative["derivative_kind"] == "portrait_identity_pose_geometry_crop"
    assert derivative["identity_evidence_scope"] == "pose_geometry"
    assert derivative["identity_color_retention"] == 0.58
    assert derivative["provider_only"] is True
    assert Path(derivative["path"]).exists()


def test_professional_supplementary_materialization_blocks_when_pose_scope_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _image(tmp_path / "root.png", (220, 180, 160))
    front = _image(tmp_path / "front.png", (220, 181, 160))
    three_quarter = _image(tmp_path / "three-quarter.png", (220, 182, 160))
    request = _request(root, front, three_quarter)

    import app.services.provider_reference as provider_reference

    original = provider_reference.prepare_reference_truth_derivatives

    def without_pose(*args, **kwargs):
        return [
            item
            for item in original(*args, **kwargs)
            if item.get("derivative_kind") != "portrait_identity_pose_geometry_crop"
        ]

    monkeypatch.setattr(provider_reference, "prepare_reference_truth_derivatives", without_pose)
    provider = ProductionImageGenerationProvider()
    with pytest.raises(ProviderRuntimeError) as exc:
        provider.materialize_final_prompt(request)
    assert exc.value.detail["failure_code"] == "professional_view_conditioned_evidence_incomplete"
