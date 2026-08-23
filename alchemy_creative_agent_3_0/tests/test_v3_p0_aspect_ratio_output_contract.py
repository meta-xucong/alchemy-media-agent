import base64
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.module import (
    VisualCapabilityClusterModule,
)


def _png_base64(size: tuple[int, int]) -> str:
    image = Image.new("RGB", size, (120, 150, 180))
    output = BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def test_explicit_brain_aspect_ratio_is_applied_to_persisted_pixels(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path)

    record = store.save_base64_output(
        job_id="job_test_aspect",
        candidate_id="candidate_test_aspect",
        asset_id="asset_test_aspect",
        provider="openai_gpt_image",
        model="gpt-image-2",
        encoded_image=_png_base64((1536, 1024)),
        metadata={
            "requested_image_size": "1536x1024",
            "requested_image_aspect_ratio": "2.35:1",
            "requested_image_aspect_ratio_source": "remote_brain_user_intent",
        },
    )

    assert (record.width, record.height) == (1536, 654)
    assert record.metadata["aspect_ratio_normalization"] == "server_crop_to_explicit_user_ratio"
    assert record.metadata["aspect_ratio_source_dimensions"] == {"width": 1536, "height": 1024}
    assert record.metadata["aspect_ratio_actual_dimensions"] == {"width": 1536, "height": 654}


def test_browser_size_without_explicit_brain_ratio_is_not_cropped(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path)

    record = store.save_base64_output(
        job_id="job_test_browser_size",
        candidate_id="candidate_test_browser_size",
        asset_id="asset_test_browser_size",
        provider="openai_gpt_image",
        model="gpt-image-2",
        encoded_image=_png_base64((1536, 1024)),
        metadata={"requested_image_size": "1536x1024"},
    )

    assert (record.width, record.height) == (1536, 1024)
    assert "aspect_ratio_normalization" not in record.metadata


def test_human_realism_uses_brain_visible_person_when_product_policy_also_applies() -> None:
    capability_input = SimpleNamespace(
        metadata={
            "visual_task_profile": {
                "subject_entities": [
                    {"entity_type": "product", "visible_in_target": True},
                    {"entity_type": "person", "visible_in_target": True},
                ]
            }
        }
    )

    resolved = VisualCapabilityClusterModule._human_subject_type_from_brain_profile(
        capability_input,
        fallback_subject_type="product",
    )

    assert resolved == "character"


def test_human_realism_keeps_product_policy_without_visible_person() -> None:
    capability_input = SimpleNamespace(
        metadata={
            "visual_task_profile": {
                "subject_entities": [
                    {"entity_type": "product", "visible_in_target": True},
                ]
            }
        }
    )

    resolved = VisualCapabilityClusterModule._human_subject_type_from_brain_profile(
        capability_input,
        fallback_subject_type="product",
    )

    assert resolved == "product"
