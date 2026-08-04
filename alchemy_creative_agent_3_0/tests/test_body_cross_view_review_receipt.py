from __future__ import annotations

import hashlib
import json

import pytest

from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import (
    McpMaterializationError,
    McpMaterializationHandoffStore,
)
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
    default_body_refresh_presentation_intent,
    default_body_silhouette_backdrop_presentation_contract,
    default_body_silhouette_hair_continuity_contract,
)


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
