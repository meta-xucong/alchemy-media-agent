from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import (
    McpMaterializationHandoffStore,
)
from alchemy_creative_agent_3_0.app.product_api.body_cross_view_review_provider import (
    OpenAICompatibleBodyCrossViewReviewProvider,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    default_body_refresh_presentation_intent,
    default_body_silhouette_backdrop_presentation_contract,
    default_body_silhouette_garment_continuity_contract,
    default_body_silhouette_hair_continuity_contract,
    validate_body_silhouette_garment_continuity_contract,
)
from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
    body_silhouette_integrated_whole_person_synthesis_contract,
    body_silhouette_mcp_materialization_channel_contract,
)


def _strict_contract() -> dict[str, object]:
    return {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "count": 1,
        "api_operation": "image_edit",
        "size_normalization": "white_matte_contain_to_contract_size",
        "body_refresh_source_mode": "inference_first",
        "body_silhouette_mcp_materialization_channel_contract": (
            body_silhouette_mcp_materialization_channel_contract()
        ),
        "body_silhouette_integrated_whole_person_synthesis_contract": (
            body_silhouette_integrated_whole_person_synthesis_contract()
        ),
        "body_refresh_presentation_intent": default_body_refresh_presentation_intent().model_dump(
            mode="json"
        ),
        "body_silhouette_garment_continuity_contract": (
            default_body_silhouette_garment_continuity_contract()
        ),
        "body_silhouette_hair_continuity_contract": (
            default_body_silhouette_hair_continuity_contract()
        ),
        "body_silhouette_backdrop_presentation_contract": (
            default_body_silhouette_backdrop_presentation_contract()
        ),
    }


def test_default_garment_contract_freezes_identity_not_only_categories() -> None:
    contract = default_body_silhouette_garment_continuity_contract()

    assert contract["contract_version"] == "professional_body_silhouette_garment_continuity_v2"
    assert contract["top_garment_identity"] == "plain_white_short_sleeve_top"
    assert contract["top_material"] == "plain_cotton_jersey"
    assert contract["top_cut"] == "crew_neck_short_sleeve"
    assert contract["bottom_garment_identity"] == "light_blue_denim_shorts"
    assert contract["bottom_material"] == "lightweight_light_blue_denim"
    assert contract["bottom_cut"] == "straight_mid_thigh_shorts"
    assert contract["footwear_identity"] == "plain_white_ankle_socks"
    assert contract["surface_treatment"] == "graphic_free"
    assert contract["not_body_proportion_truth"] is True
    assert contract["not_identity_truth"] is True
    assert contract["not_age_truth"] is True
    assert "target_age_scope" not in contract
    assert "body_morphology_profile" not in contract


def test_renderer_directive_carries_exact_garment_identity_and_prompt(tmp_path) -> None:
    store = McpMaterializationHandoffStore(storage_root=tmp_path / "handoffs")
    handoff = store.ensure_pending(
        operation_id="body-garment-identity-test",
        prompt="canonical body prompt",
        prompt_sha256="p" * 64,
        reference_assets=[],
        rendering_contract=_strict_contract(),
        require_body_rendering_contract=True,
    )

    request = store.public_renderer_request(handoff["handoff_id"])
    directive = request["renderer_execution_directive"]
    garment = directive["garment_continuity"]

    assert garment["top_garment_identity"] == "plain_white_short_sleeve_top"
    assert garment["top_material"] == "plain_cotton_jersey"
    assert garment["top_cut"] == "crew_neck_short_sleeve"
    assert garment["bottom_garment_identity"] == "light_blue_denim_shorts"
    assert garment["bottom_material"] == "lightweight_light_blue_denim"
    assert garment["bottom_cut"] == "straight_mid_thigh_shorts"
    assert garment["footwear_identity"] == "plain_white_ankle_socks"
    assert garment["surface_treatment"] == "graphic_free"

    prompt = request["renderer_prompt"].lower()
    assert "plain white short-sleeve cotton top" in prompt
    assert "light-blue lightweight denim shorts" in prompt
    assert "plain white ankle socks" in prompt
    assert "same garment identity" in prompt
    assert "colorway, material, cut" in prompt
    assert "body morphology profile" not in json.dumps(garment, sort_keys=True).lower()


def test_cross_view_review_instructions_name_the_frozen_outfit() -> None:
    provider = OpenAICompatibleBodyCrossViewReviewProvider(
        api_key="configured",
        base_url="https://vision.example/v1",
        model="vision-model",
        output_store=object(),  # type: ignore[arg-type]
        transport=object(),  # type: ignore[arg-type]
    )

    instructions = provider.instructions.lower()
    assert "plain white short-sleeve cotton top" in instructions
    assert "light-blue lightweight denim shorts" in instructions
    assert "plain white ankle socks" in instructions
    assert "category match alone is not enough" in instructions


def test_garment_identity_contract_cannot_become_age_or_body_truth() -> None:
    contract = default_body_silhouette_garment_continuity_contract()

    assert contract["scope"] == (
        "professional_character_card_body_silhouette_mcp_materialization_only"
    )
    assert contract["not_age_truth"] is True
    assert contract["not_body_proportion_truth"] is True
    assert contract["not_identity_truth"] is True
    assert all(
        "age" not in str(value).lower()
        and "morphology" not in str(value).lower()
        for key, value in contract.items()
        if key not in {"not_age_truth", "not_body_proportion_truth", "not_identity_truth"}
    )


def test_historical_v1_garment_contract_is_read_only_and_not_upgraded() -> None:
    current = default_body_silhouette_garment_continuity_contract()
    legacy = {
        key: value
        for key, value in current.items()
        if key
        not in {
            "top_garment_identity",
            "top_material",
            "top_cut",
            "bottom_garment_identity",
            "bottom_material",
            "bottom_cut",
            "footwear_identity",
            "surface_treatment",
        }
    }
    legacy.update(
        {
            "contract_version": "professional_body_silhouette_garment_continuity_v1",
            "required_continuity": [
                "same_top_garment_identity",
                "same_bottom_garment_identity",
                "same_footwear_identity",
                "same_colorway_between_views",
                "same_material_and_cut_between_views",
                "same_graphic_free_surface_between_views",
            ],
            "forbidden": [
                "top_garment_swap_between_views",
                "bottom_garment_swap_between_views",
                "footwear_swap_between_views",
                "colorway_change_between_views",
                "material_or_cut_change_between_views",
                "graphic_logo_or_pattern_appears",
                "extra_layer_added_or_removed_between_views",
            ],
        }
    )

    readable = validate_body_silhouette_garment_continuity_contract(
        legacy,
        require_identity=False,
    )
    assert readable["contract_version"] == "professional_body_silhouette_garment_continuity_v1"
    assert "bottom_garment_identity" not in readable

    try:
        validate_body_silhouette_garment_continuity_contract(legacy, require_identity=True)
    except ValueError as exc:
        assert str(exc) == "Body garment continuity identity contract required"
    else:
        raise AssertionError("legacy v1 must not satisfy a new strict Body materialization")
