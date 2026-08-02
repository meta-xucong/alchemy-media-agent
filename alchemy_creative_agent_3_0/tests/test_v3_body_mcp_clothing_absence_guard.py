"""Red tests for strict Body MCP clothing-absence prompt containment.

Correction model:
the typed Body presentation contract owns short sleeves/shorts/barefoot, while
the Brain canonical prompt must never positively request an unclothed subject
or take over scene/wardrobe authority.  The guard belongs at the Body MCP
canonical-prompt/handoff boundary.  It must not leak into Expression or
ordinary MCP. A schema-changing correction supersedes the old attempt; the
generic handoff store does not gain a replan/invalidation state.
"""

from __future__ import annotations

import pytest

from app.providers.base import ProviderRuntimeError
from alchemy_creative_agent_3_0.app.generation_router.providers import McpMaterializationProvider
from alchemy_creative_agent_3_0.app.product_api.anchor_pack_host import _character_card_stage_mcp_prompt_current
from alchemy_creative_agent_3_0.app.visual_assets import body_silhouette_source_standard as body_contracts
from alchemy_creative_agent_3_0.tests.test_v3_doc245_body_formal_slot_receipt_seam import (
    _mcp_body_generation_request,
)


POSITIVE_CLOTHING_ABSENCE_PROMPT = (
    "Full-body front-view Body Silhouette materialization. Render an unclothed silhouette, "
    "with no clothing and no garments. Keep the subject centered on a uniform white field."
)

SAFE_PRESENTATION_PROMPT = (
    "Full-body front-view Body Silhouette materialization. Not nude; wearing short sleeves "
    "and shorts, completely barefoot."
)


def test_strict_body_mcp_rejects_positive_clothing_absence_before_handoff_creation() -> None:
    provider = McpMaterializationProvider()

    with pytest.raises(ProviderRuntimeError) as exc_info:
        provider._build_app_request(  # noqa: SLF001
            _mcp_body_generation_request(
                POSITIVE_CLOTHING_ABSENCE_PROMPT,
                source_mode="inference_first",
            )
        )

    detail = getattr(exc_info.value, "detail", {})
    assert detail["failure_code"] == "character_card_body_mcp_clothing_absence_contract_invalid"
    assert "unclothed" not in repr(detail).lower()
    assert "no clothing" not in repr(detail).lower()


def test_body_clothing_absence_guard_does_not_false_positive_safe_presentation() -> None:
    findings = body_contracts.body_silhouette_mcp_materialization_prompt_findings(
        SAFE_PRESENTATION_PROMPT
    )

    assert "clothing_absence_positive_semantics_present" not in findings


def test_body_brain_recovery_prompt_rejects_clothing_absence_but_expression_isolated() -> None:
    assert not _character_card_stage_mcp_prompt_current(
        "body.front_full",
        POSITIVE_CLOTHING_ABSENCE_PROMPT,
    )

    expression_prompt = (
        "Expression smile capture. Keep the subject smiling and do not infer any Body wardrobe "
        "or clothing channel from this expression stage."
    )
    assert _character_card_stage_mcp_prompt_current("expression.smile", expression_prompt)

    provider = McpMaterializationProvider()
    provider._assert_character_card_body_mcp_materialization_prompt_current(  # noqa: SLF001
        {
            "professional_character_card_stage": "expression_set",
            "professional_character_card_slot": "expression.smile",
        },
        POSITIVE_CLOTHING_ABSENCE_PROMPT,
    )
