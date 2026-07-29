"""Document-only checks for Body Silhouette refresh source-mode governance."""

from __future__ import annotations

import re
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DOC_ROOT = PACKAGE_ROOT / "docs" / "visual_assets"
HANDOFF = DOC_ROOT / "PROFESSIONAL_MODE_BODY_SILHOUETTE_SOURCE_STANDARD_GATE_C_HANDOFF.md"
INDEX = DOC_ROOT / "PROFESSIONAL_MODE_DOCUMENT_SET_INDEX.md"


def _handoff_text() -> str:
    return HANDOFF.read_text(encoding="utf-8")


def _index_text() -> str:
    return INDEX.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)", text, re.S | re.M)
    assert match, f"missing section: {heading}"
    return match.group("body")


def _squash(text: str) -> str:
    return " ".join(text.split())


def test_body_refresh_source_mode_has_two_closed_modes_and_supersedes_global_observed_only() -> None:
    source_mode = _section(_handoff_text(), "9. Body refresh source-mode closure")
    squashed = _squash(source_mode)

    assert "body_refresh_source_mode:" in source_mode
    assert "reference_assisted" in source_mode
    assert "inference_first" in source_mode
    assert "observed-only wording is now narrowed" in source_mode
    assert "applies to the `reference_assisted` source mode only" in squashed
    assert "not be interpreted as a global precondition" in squashed
    assert "Observed Body-only admission is required for `reference_assisted`" in squashed
    assert "it is not required for `inference_first`" in squashed


def test_source_mode_and_reference_admission_are_server_owned_not_client_forged() -> None:
    source_mode = _section(_handoff_text(), "9. Body refresh source-mode closure")
    squashed = _squash(source_mode)

    assert "resolved by the Character Card / Visual Asset Library owning layer" in squashed
    assert "never accepted from client metadata" in source_mode
    assert "Client-provided `body_reference_admission`" in source_mode
    assert "cannot make a request `reference_assisted`" in squashed
    for forbidden in (
        "raw `body_facts`",
        "file path",
        "filename",
        "output id",
        "provider payload",
        "free prompt prose",
        "paths, URLs, provider payloads, asset ids, or output ids",
    ):
        assert forbidden in source_mode or forbidden in squashed


def test_reference_assisted_requires_server_resolved_body_truth_and_keeps_channels_separate() -> None:
    source_mode = _section(_handoff_text(), "9. Body refresh source-mode closure")
    assisted = source_mode.split("### 9.1 `reference_assisted`", 1)[1].split("### 9.2", 1)[0]
    squashed = _squash(assisted)

    for required in (
        "source class is `observed`",
        "role is `body_proportion_reference`",
        "`metadata.reference_truth_layer` is `body_proportion_truth`",
        "consent or rights provenance is present",
    ):
        assert required in assisted

    assert "similar-person full-body proportion reference" in squashed
    assert "must not be represented as, the same person as the current Character Card subject" in squashed
    assert "source provenance is bound to the current Professional Character Card Body refresh/card request" in squashed
    assert "not as same-person identity evidence" in squashed
    assert "not Face Identity truth" in assisted
    assert "current subject's Face Identity remains owned by the existing Character Card Face Identity references" in squashed
    assert "cannot replace, override, or weaken those Face Identity references" in squashed
    for forbidden_lock in (
        "wardrobe",
        "pose",
        "lighting",
        "camera",
        "expression",
        "background",
        "scene",
        "product identity",
        "swimwear",
        "poolside",
        "kidswear",
        "E-Commerce",
        "Photography",
        "General deliverable semantics",
    ):
        assert forbidden_lock in assisted


def test_inference_first_is_valid_without_reference_but_cannot_claim_body_truth() -> None:
    source_mode = _section(_handoff_text(), "9. Body refresh source-mode closure")
    inference = source_mode.split("### 9.2 `inference_first`", 1)[1].split("### 9.3", 1)[0]
    squashed = _squash(inference)

    assert "valid Body Silhouette modeling path when no admitted Body reference is available" in squashed
    assert "active Face Identity continuity references" in inference
    assert "server-owned age-stage/body-context if such typed context exists" in inference
    assert "scene-neutral `system_inferred_body_model` context" in inference
    assert "does not claim a specific observed age, body measurement, body vector, or body truth" in squashed
    for forbidden_truth in (
        "`body_evidence_ids`",
        "`body_proportion_reference`",
        "`body_proportion_truth`",
        "observed source claims",
        "biometric vectors",
        "raw user text",
        "paths",
        "URLs",
        "provider payloads",
        "asset ids",
        "output ids",
    ):
        assert forbidden_truth in inference


def test_inference_first_acceptance_requires_review_proof_not_generation_alone() -> None:
    source_mode = _section(_handoff_text(), "9. Body refresh source-mode closure")
    inference = source_mode.split("### 9.2 `inference_first`", 1)[1].split("### 9.3", 1)[0]
    squashed = _squash(inference)

    assert "success condition for `inference_first` is review proof, not source proof" in inference
    for required_gate in (
        "shared review",
        "Body source-standard positive evidence",
        "formal slot receipts",
        "card-level cross-view parity",
    ):
        assert required_gate in squashed
    assert "A generated image is not an accepted Body slot by itself" in squashed
    assert "absence of an observed reference is not an entry blocker for this mode" in squashed


def test_source_standard_evidence_missing_is_not_reference_missing() -> None:
    source_mode = _section(_handoff_text(), "9. Body refresh source-mode closure")
    squashed = _squash(source_mode)

    assert "`source_standard_evidence_missing` is a candidate-review proof failure" in source_mode
    assert "not the same as “observed Body reference missing.”" in source_mode
    assert "must remain distinguishable from a `reference_assisted` source admission failure" in squashed


def test_compatibility_activation_downstream_and_scene_isolation_remain_explicit() -> None:
    source_mode = _section(_handoff_text(), "9. Body refresh source-mode closure")
    shared = source_mode.split("### 9.3 Shared acceptance and compatibility rules", 1)[1]
    squashed = _squash(shared)

    for invariant in (
        "Face references are identity continuity evidence, not body truth",
        "Existing active Body slots, historical receipts, and old readback records",
        "not invalidated, migrated, recomputed, relabelled as observed, or overwritten",
        "Append-only pending refresh state and explicit activation",
        "No source mode may replace active Body slots without a later activation gate",
        "Downstream General, Photography, and E-Commerce isolation",
        "Provider cap and Provider role isolation",
        "`reference_assisted` may add one Body-only reference",
        "`inference_first` may not fabricate one",
    ):
        assert invariant in squashed

    for forbidden_recipe in (
        "six-year-old",
        "swimwear",
        "poolside",
        "kidswear",
        "E-Commerce",
        "wardrobe",
        "pose",
        "lighting",
        "camera",
        "expression",
        "fixed head/body-ratio recipe",
    ):
        assert forbidden_recipe in squashed


def test_index_registers_two_mode_source_contract_without_runtime_authority() -> None:
    index = _index_text()
    section = index.split("### Body Silhouette Source Standard Contract", 1)[1].split("### M5", 1)[0]
    squashed = _squash(section)

    assert "reference_assisted" in section
    assert "inference_first" in section
    assert "server-resolved ready `body_proportion_reference`" in section
    assert "`body_proportion_truth` with consent or rights provenance" in section
    assert "valid scene-neutral Body Silhouette modeling path when no observed Body reference exists" in squashed
    assert "source mode is server-owned and cannot be forged" in squashed
    assert "Historical brain-inferred active Body slots remain readable" in squashed
    assert "not relabelled observed" in squashed
    assert "pending refresh and explicit activation remain separate gates" in squashed
    assert "similar-person Body source is bound to the current refresh/card request" in squashed
    assert "not current-person identity truth" in squashed
    assert "cannot replace the Character Card Face Identity references" in squashed


def test_mcp_body_materialization_channel_contract_is_documented_without_generation_authority() -> None:
    mcp = _section(_handoff_text(), "10. MCP Body materialization channel contract closure")
    squashed = _squash(mcp)

    assert "professional_body_silhouette_mcp_materialization_channel_v1" in mcp
    assert "professional_character_card_body_silhouette_mcp_materialization_only" in mcp
    assert "inference_first" in mcp
    assert "reference_assisted" in mcp
    for allowed in (
        "body proportion",
        "body scale",
        "neck/shoulder continuity",
        "torso/limb relationship",
        "developmental-stage body context",
        "stance/ground contact",
        "cross-view body parity",
    ):
        assert allowed in mcp

    assert "Character Card Face Identity references remain identity-continuity" in mcp
    assert "they do not become Body truth, wardrobe truth, pose truth, scene truth" in squashed
    assert "All non-Body-owned channels must remain unspecified" in mcp
    for forbidden_channel in (
        "wardrobe",
        "attire",
        "formal or business styling",
        "suit/headshot",
        "facial expression",
        "professional pose",
        "scene",
        "studio",
        "lighting",
        "camera",
        "background",
        "product",
        "General",
        "Photography",
        "E-Commerce",
    ):
        assert forbidden_channel in mcp

    assert "reject a stale frozen handoff before MCP handoff creation" in squashed
    assert "old wardrobe, formal/business, expression/professional-pose, or scene/studio channel findings" in squashed
    assert "Negative or scene-neutral wording" in mcp
    assert "This closure does not change the standard three-candidate requirement" in mcp
    assert "shared review" in squashed
    assert "formal slot receipt" in squashed
    assert "card-level cross-view parity" in mcp
    assert "explicit activation" in mcp
    assert "downstream General/Photography/E-Commerce projection" in squashed
    assert "provider cap" in mcp
    assert "It authorizes no real generation by itself" in mcp
