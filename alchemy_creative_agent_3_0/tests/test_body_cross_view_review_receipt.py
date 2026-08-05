from __future__ import annotations

import base64
import hashlib
import json
from io import BytesIO

import pytest

from PIL import Image

from test_body_analysis_profile_lifecycle_freeze import _profile_context

from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import (
    McpMaterializationError,
    McpMaterializationHandoffStore,
)
from alchemy_creative_agent_3_0.app.product_api.body_cross_view_review_provider import (
    OpenAICompatibleBodyCrossViewReviewProvider,
)
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import (
    ProductApiAnchorPackPreparationHost,
)
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.visual_assets.body_silhouette_source_standard import (
    body_silhouette_integrated_whole_person_synthesis_contract,
    body_silhouette_mcp_materialization_channel_contract,
)
from alchemy_creative_agent_3_0.app.visual_assets.body_cross_view_review import (
    BODY_CROSS_VIEW_DIMENSION_EVIDENCE_CODES,
    BODY_CROSS_VIEW_DIMENSIONS,
    BODY_CROSS_VIEW_PIXEL_EVIDENCE_CODE,
    BodyCrossViewReviewReceipt,
    build_body_cross_view_review_receipt,
    build_body_cross_view_unavailable_receipt,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    BodySourceAdmission,
    default_body_refresh_presentation_intent,
    default_body_silhouette_backdrop_presentation_contract,
    default_body_silhouette_garment_continuity_contract,
    default_body_silhouette_hair_continuity_contract,
)


def _png_base64(color: tuple[int, int, int] = (200, 210, 220)) -> str:
    buffer = BytesIO()
    Image.new("RGB", (24, 36), color=color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class _CrossViewTransport:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def review(self, images, *, instructions, response_schema, timeout_seconds):  # noqa: ANN001
        self.calls.append(
            {
                "slot_keys": [image.slot_key for image in images],
                "output_ids": [image.output_id for image in images],
                "instructions": instructions,
                "response_schema": response_schema,
                "timeout_seconds": timeout_seconds,
            }
        )
        return dict(self.response)


def _receipt(*, status: str = "pass", issue_codes: list[str] | None = None):
    return build_body_cross_view_review_receipt(
        attempt_id="body_refresh_attempt_0123456789abcdef0123456789abcdef",
        source_evidence_id_digest="a" * 64,
        view_output_ids={
            "body.front_full": "front-output",
            "body.side_full": "side-output",
            "body.rear_full": "rear-output",
        },
        status=status,
        evidence_codes=(
            [
                BODY_CROSS_VIEW_PIXEL_EVIDENCE_CODE,
                *BODY_CROSS_VIEW_DIMENSION_EVIDENCE_CODES.values(),
            ]
            if status == "pass"
            else []
        ),
        issue_codes=issue_codes or [],
        dimensions={dimension: "pass" for dimension in BODY_CROSS_VIEW_DIMENSIONS},
    )


def test_cross_view_receipt_is_required_for_reference_assisted_activation() -> None:
    receipt = build_body_cross_view_unavailable_receipt(
        attempt_id="body_refresh_attempt_0123456789abcdef0123456789abcdef",
        source_evidence_id_digest="a" * 64,
        view_output_ids={
            "body.front_full": "front-output",
            "body.side_full": "side-output",
            "body.rear_full": "rear-output",
        },
    )

    assert receipt.activation_eligible is False
    assert receipt.status == "fail"
    assert receipt.issue_codes == ("body_cross_view_review_unavailable",)


def test_cross_view_receipt_rejects_missing_or_failed_visual_dimensions() -> None:
    receipt = _receipt(status="fail", issue_codes=["front_side_rear_body_volume_conflict"])

    assert receipt.status == "fail"
    assert receipt.activation_eligible is False
    assert receipt.issue_codes == ("front_side_rear_body_volume_conflict",)

    with pytest.raises(ValueError, match="body_cross_view"):
        build_body_cross_view_review_receipt(
            attempt_id=receipt.attempt_id,
            source_evidence_id_digest=receipt.source_evidence_id_digest,
            view_output_ids=receipt.view_output_ids,
            status="pass",
            evidence_codes=[],
            issue_codes=[],
            dimensions={"age_stage_consistency": "unknown"},
        )


def test_cross_view_receipt_blocks_view_specific_age6_proportion_drift() -> None:
    for code in (
        "view_specific_limb_length_drift",
        "view_specific_body_maturity_drift",
        "front_side_rear_stature_ratio_conflict",
    ):
        receipt = _receipt(status="fail", issue_codes=[code])
        assert receipt.status == "fail"
        assert receipt.activation_eligible is False
        assert receipt.issue_codes == (code,)


def test_cross_view_receipt_binds_exact_outputs_and_source_digest() -> None:
    receipt = _receipt()
    assert isinstance(receipt, BodyCrossViewReviewReceipt)
    assert receipt.activation_eligible is True
    assert receipt.receipt_digest == hashlib.sha256(
        json.dumps(receipt.canonical_payload(include_digest=False), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_body_handoff_submit_requires_typed_renderer_execution_receipt(tmp_path) -> None:
    store = McpMaterializationHandoffStore(storage_root=tmp_path / "handoffs")
    contract = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "output_format": "png",
        "count": 1,
        "body_refresh_source_mode": "inference_first",
        "body_silhouette_mcp_materialization_channel_contract": body_silhouette_mcp_materialization_channel_contract(),
        "body_silhouette_integrated_whole_person_synthesis_contract": (
            body_silhouette_integrated_whole_person_synthesis_contract()
        ),
        "body_refresh_presentation_intent": default_body_refresh_presentation_intent().model_dump(mode="json"),
        "body_silhouette_garment_continuity_contract": default_body_silhouette_garment_continuity_contract(),
        "body_silhouette_hair_continuity_contract": default_body_silhouette_hair_continuity_contract(),
        "body_silhouette_backdrop_presentation_contract": default_body_silhouette_backdrop_presentation_contract(),
    }
    handoff = store.ensure_pending(
        operation_id="body-cross-view-test",
        prompt="canonical",
        prompt_sha256="p" * 64,
        reference_assets=[],
        rendering_contract=contract,
        require_body_rendering_contract=True,
    )
    request = store.public_renderer_request(handoff["handoff_id"])
    with pytest.raises(McpMaterializationError) as exc_info:
        store.submit(
            handoff["handoff_id"],
            nonce=handoff["nonce"],
            prompt_sha256=handoff["prompt_sha256"],
            reference_asset_hashes=handoff["reference_asset_hashes"],
            artifact_bytes=b"png",
            renderer_prompt_sha256=request["renderer_prompt_sha256"],
            renderer_execution_directive_sha256=handoff["renderer_execution_directive_sha256"],
        )
    assert exc_info.value.code == "mcp_materialization_renderer_execution_receipt_required"


def test_openai_compatible_cross_view_provider_builds_pass_receipt_from_three_outputs(
    tmp_path,
) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    output_ids: dict[str, str] = {}
    for index, slot_key in enumerate(
        ("body.front_full", "body.side_full", "body.rear_full"),
        start=1,
    ):
        record = output_store.save_base64_output(
            job_id=f"job-{index}",
            candidate_id=f"candidate-{index}",
            asset_id="asset-body",
            provider="openai_gpt_image",
            model="gpt-image-2",
            encoded_image=_png_base64((180 + index, 190, 200)),
            mime_type="image/png",
            output_format="png",
        )
        output_ids[slot_key] = record.output_id
    transport = _CrossViewTransport(
        {
            "dimensions": {dimension: "pass" for dimension in BODY_CROSS_VIEW_DIMENSIONS},
            "issue_codes": [],
        }
    )
    provider = OpenAICompatibleBodyCrossViewReviewProvider(
        api_key="configured",
        base_url="https://vision.example/v1",
        model="vision-model",
        output_store=output_store,
        transport=transport,
    )

    receipt = provider.review_body_cross_view(
        asset=object(),
        card=object(),
        attempt_identity=type(
            "Attempt",
            (),
            {"attempt_id": "body_refresh_attempt_0123456789abcdef0123456789abcdef"},
        )(),
        body_refresh_analysis_context=type(
            "Context",
            (),
            {
                "source_evidence_id_digest": "a" * 64,
                "target_age_scope": "age_6_child_only",
            },
        )(),
        body_source_admission=type(
            "Admission",
            (),
            {"source_evidence_id_digest": lambda self: "a" * 64},
        )(),
        formal_receipts={},
        view_output_ids=output_ids,
    )

    assert receipt.activation_eligible is True
    assert receipt.real_pixel_review_verified is True
    assert transport.calls[0]["slot_keys"] == [
        "body.front_full",
        "body.side_full",
        "body.rear_full",
    ]
    assert "Body proportion source references" not in transport.calls[0]["instructions"]
    assert "category match alone is not enough" in transport.calls[0]["instructions"]
    instructions = transport.calls[0]["instructions"].lower()
    assert "approximately six-year-old school-age child" in instructions
    assert "not teen, adolescent, or adult fashion-model proportions" in instructions
    assert "same compact stature, body depth, shoulder width, and limb scale" in instructions
    assert "front_side_rear_stature_ratio_conflict" in instructions
    assert "view_specific_limb_length_drift" in instructions


def test_cross_view_review_instructions_do_not_apply_age6_without_frozen_scope(
    tmp_path,
) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    output_ids: dict[str, str] = {}
    for index, slot_key in enumerate(
        ("body.front_full", "body.side_full", "body.rear_full"),
        start=1,
    ):
        record = output_store.save_base64_output(
            job_id=f"job-no-age-{index}",
            candidate_id=f"candidate-no-age-{index}",
            asset_id="asset-body-no-age",
            provider="openai_gpt_image",
            model="gpt-image-2",
            encoded_image=_png_base64((160 + index, 170, 180)),
            mime_type="image/png",
            output_format="png",
        )
        output_ids[slot_key] = record.output_id
    transport = _CrossViewTransport(
        {
            "dimensions": {dimension: "pass" for dimension in BODY_CROSS_VIEW_DIMENSIONS},
            "issue_codes": [],
        }
    )
    provider = OpenAICompatibleBodyCrossViewReviewProvider(
        api_key="configured",
        base_url="https://vision.example/v1",
        model="vision-model",
        output_store=output_store,
        transport=transport,
    )

    provider.review_body_cross_view(
        asset=object(),
        card=object(),
        attempt_identity=type(
            "Attempt",
            (),
            {"attempt_id": "body_refresh_attempt_0123456789abcdef0123456789abcdef"},
        )(),
        body_refresh_analysis_context=type(
            "Context",
            (),
            {"source_evidence_id_digest": "a" * 64},
        )(),
        body_source_admission=type(
            "Admission",
            (),
            {"source_evidence_id_digest": lambda self: "a" * 64},
        )(),
        formal_receipts={},
        view_output_ids=output_ids,
    )

    instructions = transport.calls[0]["instructions"].lower()
    assert "six-year-old" not in instructions
    assert "school-age child" not in instructions
    assert "not teen, adolescent, or adult fashion-model proportions" not in instructions
    assert "colorway, material, cut, graphics, logo, or added-layer drift" in transport.calls[0][
        "instructions"
    ]
    assert "canonical garment identity" in transport.calls[0]["instructions"].lower()
    assert "mid-blue matte cotton-denim relaxed knee-length shorts" in transport.calls[0][
        "instructions"
    ]


def test_openai_compatible_cross_view_provider_fails_closed_when_output_missing(
    tmp_path,
) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    provider = OpenAICompatibleBodyCrossViewReviewProvider(
        api_key="configured",
        base_url="https://vision.example/v1",
        model="vision-model",
        output_store=output_store,
        transport=_CrossViewTransport(
            {
                "dimensions": {dimension: "pass" for dimension in BODY_CROSS_VIEW_DIMENSIONS},
                "issue_codes": [],
            }
        ),
    )

    receipt = provider.review_body_cross_view(
        asset=object(),
        card=object(),
        attempt_identity=type(
            "Attempt",
            (),
            {"attempt_id": "body_refresh_attempt_0123456789abcdef0123456789abcdef"},
        )(),
        body_refresh_analysis_context=type(
            "Context",
            (),
            {"source_evidence_id_digest": "a" * 64},
        )(),
        body_source_admission=type(
            "Admission",
            (),
            {"source_evidence_id_digest": lambda self: "a" * 64},
        )(),
        formal_receipts={},
        view_output_ids={
            "body.front_full": "v3_output_00000000000000000001",
            "body.side_full": "v3_output_00000000000000000002",
            "body.rear_full": "v3_output_00000000000000000003",
        },
    )

    assert receipt.activation_eligible is False
    assert receipt.issue_codes == ("body_cross_view_review_unavailable",)


def test_product_api_host_forwards_cross_view_review_to_configured_provider(tmp_path) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    view_output_ids: dict[str, str] = {}
    for index, slot_key in enumerate(
        ("body.front_full", "body.side_full", "body.rear_full"),
        start=1,
    ):
        record = output_store.save_base64_output(
            job_id=f"job-{index}",
            candidate_id=f"candidate-{index}",
            asset_id="asset-body",
            provider="openai_gpt_image",
            model="gpt-image-2",
            encoded_image=_png_base64((160, 170 + index, 180)),
            mime_type="image/png",
            output_format="png",
        )
        view_output_ids[slot_key] = record.output_id

    provider = OpenAICompatibleBodyCrossViewReviewProvider(
        api_key="configured",
        base_url="https://vision.example/v1",
        model="vision-model",
        output_store=output_store,
        transport=_CrossViewTransport(
            {
                "dimensions": {dimension: "pass" for dimension in BODY_CROSS_VIEW_DIMENSIONS},
                "issue_codes": [],
            }
        ),
    )
    service = V3ProductApiService(
        body_proportion_source_analyzer=object(),
        body_cross_view_review_provider=provider,
        output_store=output_store,
    )
    host = ProductApiAnchorPackPreparationHost(service)
    attempt, context = _profile_context()
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=[f"body-source-{index}" for index in range(5)],
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=["face.front", "face.profile", "face.rear"],
    )

    receipt = host.review_body_refresh_cross_view(
        asset=object(),
        card=object(),
        attempt_identity=attempt,
        body_refresh_analysis_context=context,
        body_source_admission=admission,
        formal_receipts={},
        view_output_ids=view_output_ids,
    )

    assert receipt.activation_eligible is True
