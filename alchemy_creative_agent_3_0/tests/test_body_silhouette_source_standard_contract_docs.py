"""Deterministic checks for the Body Silhouette source-standard document gate.

Gate B is intentionally document-only.  These tests read the approved Gate A
documents as text and verify static contract invariants without importing
runtime helpers, touching media/evidence storage, or executing planning.
"""

from __future__ import annotations

import re
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DOC_ROOT = PACKAGE_ROOT / "docs" / "visual_assets"
CONTRACT = DOC_ROOT / "PROFESSIONAL_MODE_BODY_SILHOUETTE_SOURCE_STANDARD_CONTRACT.md"
INDEX = DOC_ROOT / "PROFESSIONAL_MODE_DOCUMENT_SET_INDEX.md"


def _contract_text() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def _index_text() -> str:
    return INDEX.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)", text, re.S | re.M)
    assert match, f"missing section: {heading}"
    return match.group("body")


def _squash(text: str) -> str:
    return " ".join(text.split())


def test_body_source_standard_covers_only_existing_three_body_slots() -> None:
    text = _contract_text()
    for slot in ("body.front_full", "body.side_full", "body.rear_full"):
        assert slot in text

    scope = _section(text, "4. Scope of body views")
    assert "No new slot is introduced by this document." in scope
    assert "4.1 `body.front_full`" in scope
    assert "4.2 `body.side_full`" in scope
    assert "4.3 `body.rear_full`" in scope


def test_universal_dimensions_are_present_and_scene_neutral() -> None:
    text = _contract_text()
    dimensions = _section(text, "5. Universal source-standard dimensions")
    for heading in (
        "5.1 Body-chain coherence",
        "5.2 Stage-aware proportion",
        "5.3 Head-neck-shoulder continuity",
        "5.4 Torso, limbs, and joints",
        "5.5 Stance and ground contact",
        "5.6 Cross-view parity",
    ):
        assert heading in dimensions

    assert "must be person-stage-aware and scene-neutral" in dimensions
    assert "must not encode a fixed head-count ratio" in _squash(dimensions)
    for forbidden_recipe in (
        "child-specific recipe",
        "swimwear rule",
        "poolside rule",
        "kidswear rule",
        "E-Commerce-specific body style",
    ):
        assert forbidden_recipe in dimensions


def test_source_classes_are_provenance_only_not_certification() -> None:
    text = _contract_text()
    source = _section(text, "6. Source-class semantics")
    assert "`body_source` remains provenance only. It does not certify quality." in source
    for source_class in ("`observed`", "`user_described`", "`brain_inferred`"):
        assert source_class in source

    assert "observed source does not automatically mean realistic or commercial-ready" in source
    assert "cannot certify visual body realism by itself" in source
    assert "this wording does not assign a quality grade or certification" in source
    assert "must not be overclaimed as observed body truth" in source


def test_no_runtime_grade_receipt_activation_or_slot_authority_is_created() -> None:
    text = _contract_text()
    authority = _section(text, "1. Authority and non-authority")
    compatibility = _section(text, "10. Historical compatibility")
    tests = _section(text, "12. Future Gate B test matrix")

    for phrase in (
        "does **not** authorize implementation",
        "runtime field changes, grades, receipts, activation changes, storage changes",
        "runtime fields, grades, receipts, or migrations",
    ):
        assert phrase in text

    assert "introduce `commercial` grade or certification state" in compatibility
    assert "no runtime `commercial` grade or certification field appears" in tests
    assert (
        "They do not create a runtime field, receipt value, activation state, grade, or certification."
        in _squash(text)
    )
    assert "No new slot is introduced by this document." in text
    assert "Character Card generation prompts" in authority


def test_face_body_shared_and_downstream_ownership_boundaries_are_explicit() -> None:
    text = _contract_text()
    face_body = _section(text, "7. Face Identity and Body Silhouette boundary")
    downstream = _section(text, "8. Relationship to downstream body-only projection")
    shared = _section(text, "9. Relationship to shared Human Realism")

    assert "Face Identity remains the facial identity truth owner." in face_body
    assert "Body Silhouette owns:" in face_body
    assert "Body Silhouette must not alter Face Identity facial geometry." in face_body
    assert "Face Identity must not be treated as precise body-proportion evidence." in face_body

    assert "The existing Professional body-only runtime projection remains current." in downstream
    assert "This source-standard contract does not change:" in downstream
    assert "body-only reference channel" in downstream
    assert "provider cap" in downstream

    assert "Shared Human Realism may own general issue-code semantics" in shared
    assert "Shared Human Realism must not own:" in shared
    assert "Character Card Body Silhouette lifecycle" in shared
    assert "a child, swimwear, poolside, or E-Commerce-specific body recipe" in shared


def test_historical_assets_remain_readable_without_migration_or_auto_failure() -> None:
    text = _contract_text()
    compatibility = _section(text, "10. Historical compatibility")
    for phrase in (
        "Historical Body Silhouette assets remain readable",
        "invalidate existing active Body Silhouette slots",
        "mark historical slots as failed",
        "trigger automatic migration",
        "alter activation receipts",
        "legacy_body_silhouette_valid_for_current_contract",
        "not_automatically_certified_for_upgraded_source_standard",
    ):
        assert phrase in compatibility


def test_document_keeps_generation_planning_host_and_storage_out_of_scope() -> None:
    text = _contract_text()
    stop = _section(text, "14. Current stop condition")
    for blocked_action in (
        "Do not implement code",
        "regenerate Body Silhouette",
        "update Character Card generation prompts",
        "change slots",
        "change review/activation/storage",
        "run planning-only",
        "run Host/MCP/ImageGen",
        "write formal project records",
    ):
        assert blocked_action in _squash(stop)


def test_index_registers_contract_as_document_only_without_runtime_authority() -> None:
    index = _index_text()
    assert "PROFESSIONAL_MODE_BODY_SILHOUETTE_SOURCE_STANDARD_CONTRACT.md" in index
    section = index.split("### Body Silhouette Source Standard Contract", 1)[1].split("### M5", 1)[0]
    assert "Gate A document-only contract" in section
    assert "observed`, `user_described`, and `brain_inferred` as provenance" in _squash(section)
    squashed_section = _squash(section)
    assert "does not authorize Character Card generation changes" in squashed_section
    assert "runtime fields, grades, planning, Host/MCP/ImageGen" in squashed_section
