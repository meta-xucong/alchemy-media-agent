"""Doc169: developmental transitions decouple source contour from identity."""

from __future__ import annotations

import inspect

from PIL import Image

from app.services.provider_reference import prepare_reference_truth_derivatives
from alchemy_creative_agent_3_0.app.generation_router import ProductionImageGenerationProvider


def test_doc169_provider_derivative_is_feature_truth_without_source_contour_authority(
    tmp_path,
) -> None:
    source = tmp_path / "identity-root.png"
    Image.new("RGB", (800, 800), (176, 112, 72)).save(source)
    derivatives = prepare_reference_truth_derivatives(
        source,
        asset_id="identity_root_doc169",
        truth_layers=["portrait_identity_truth"],
        reference_policy={
            "source_role": "portrait_identity_reference",
            "identity_geometry": "hard",
            "body_identity": "prompt_owned",
            "natural_complexion_direction": "prompt_owned",
            "hair_direction": "prompt_owned",
            "makeup_style": "prompt_owned",
            "wardrobe_structure": "prompt_owned",
            "accessory_system": "prompt_owned",
            "lighting_color": "prompt_owned",
            "scene_background": "prompt_owned",
            "camera_composition": "prompt_owned",
            "mood_art_direction": "prompt_owned",
            "style_finish": "prompt_owned",
            "prompt_owned_channels": [
                "body_identity",
                "natural_complexion_direction",
                "hair_direction",
                "makeup_style",
                "wardrobe_structure",
                "accessory_system",
                "lighting_color",
                "scene_background",
                "camera_composition",
                "mood_art_direction",
                "style_finish",
            ],
        },
        portrait_identity_derivative_kinds=(
            "portrait_identity_stage_flexible_feature_crop",
        ),
    )

    assert len(derivatives) == 1
    derivative = derivatives[0]
    assert derivative["derivative_kind"] == "portrait_identity_stage_flexible_feature_crop"
    assert derivative["truth_layer"] == "portrait_identity_truth"
    assert derivative["identity_evidence_scope"] == "feature_detail"
    assert derivative["identity_stage_dependent_contour_suppressed"] is True
    assert derivative["identity_source_complexion_authority_suppressed"] is True
    assert derivative["fallback_to_original"] is False

    with Image.open(derivative["path"]) as image:
        corner = image.convert("RGB").getpixel((4, 4))
        center = image.convert("RGB").getpixel((image.width // 2, image.height // 2))
        lower_side = image.convert("RGB").getpixel(
            (int(image.width * 0.20), int(image.height * 0.78))
        )
    assert max(corner) - min(corner) < 20
    assert center[0] > center[2] + 30
    assert max(lower_side) - min(lower_side) < 20


def test_doc169_selection_contains_no_age_or_face_recipe() -> None:
    source = inspect.getsource(
        ProductionImageGenerationProvider._portrait_identity_derivative_kinds  # noqa: SLF001
    ).lower()
    for forbidden in (
        "child",
        "kidswear",
        "baby fat",
        "cheek",
        "jaw ratio",
        "big eyes",
        "teeth",
        "re.compile",
    ):
        assert forbidden not in source
