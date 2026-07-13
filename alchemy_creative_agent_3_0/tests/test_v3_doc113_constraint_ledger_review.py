"""Doc113 Phase 4/5 constraint resolution and non-certifying review tests."""

from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.generation_router.providers import GenerationProvider
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    GeneratedOutputResolution,
    VisionOutputInspector,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import active_review_contract


def _hard_product_plan(monkeypatch):
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    return ScenarioRuntime().plan_job(
        {
            "user_input": "Create one faithful image of the supplied steel bottle with no visible marketing copy.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_assets": [{"asset_id": "bottle", "role": "product_reference"}],
            "product_profile": {"product_name": "steel bottle", "material": "steel"},
            "metadata": {"requested_image_count": 1},
        }
    )


def test_ledger_resolves_owner_channel_strength_and_provider_projection(monkeypatch) -> None:
    result = _hard_product_plan(monkeypatch)
    ledger = result.metadata["resolved_constraint_ledger"]
    envelope = result.metadata["capability_execution_envelope"]

    assert envelope["resolved_constraint_ledger"]["ledger_id"] == ledger["ledger_id"]
    assert {entry["channel"] for entry in ledger["entries"]} >= {
        "user_intent",
        "canvas",
        "text_policy",
        "deliverable_role",
        "product_truth",
    }
    assert all(entry["resolution"] == "accepted" for entry in ledger["entries"])
    assert ledger["provider_projection"]["protected_user_intent"].startswith("Create one faithful")
    assert ledger["intent_id"] == result.metadata["normalized_v3_job_intent"]["intent_id"]
    assert ledger["audit_summary"]["deliverable_owner"] == "general_template"
    assert set(ledger["audit_summary"]["applied_constraint_ids"]) == {
        entry["constraint_id"] for entry in ledger["entries"]
    }
    assert ledger["hard_semantic_contract"] is True
    assert "visual_cluster" not in ledger["provider_projection"]
    assert "composed_visual_contribution" not in ledger["provider_projection"]
    assert ledger["provider_projection"]["legacy_adapter"]["fallback_allowed"] is False


def test_no_visible_text_wins_over_competing_literal_copy_and_template_copy_intent(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    result = ScenarioRuntime().plan_job(
        {
            "user_input": "Create a clean bottle campaign image with no visible text or headline.",
            "scenario_selection": {"scenario_id": "general_creative", "parameters": {"requested_image_count": 1}},
            "metadata": {
                "requested_image_count": 1,
                "approved_literal_copy": ["SUMMER SALE"],
            },
        }
    )

    ledger = result.metadata["resolved_constraint_ledger"]
    entries = ledger["entries"]
    rejected = [entry for entry in entries if entry["channel"] == "visible_text" and entry["resolution"] == "rejected"]

    assert result.metadata["normalized_v3_job_intent"]["visible_text_policy"] == "forbidden"
    assert ledger["provider_projection"]["text_policy"] == "provider_native_text_forbidden"
    assert rejected and ["SUMMER SALE"] in rejected[0]["requested_value"]
    assert any(item["resolution"] == "copy_rejected_no_visible_text_wins" for item in ledger["conflicts"])


def test_enforced_provider_reads_only_the_resolved_capability_projection(monkeypatch) -> None:
    result = _hard_product_plan(monkeypatch)
    request = SimpleNamespace(
        metadata={
            "capability_execution_envelope": result.metadata["capability_execution_envelope"],
            "visual_cluster": {"human_photorealism_guidance": {"applies": True, "forged": True}},
        },
        generation_plan=SimpleNamespace(metadata={}),
        asset_spec=SimpleNamespace(priority=1),
    )

    projection = GenerationProvider()._visual_cluster(request)

    assert projection.get("human_photorealism_guidance", {}).get("forged") is not True


def test_local_only_review_cannot_certify_hard_semantic_contract(monkeypatch, tmp_path: Path) -> None:
    result = _hard_product_plan(monkeypatch)
    image_path = tmp_path / "bottle.png"
    Image.new("RGB", (1024, 1024), color=(220, 230, 238)).save(image_path)
    resolution = GeneratedOutputResolution(
        resolution_id="doc113-hard-resolution",
        job_id="doc113-hard-job",
        candidate_id="doc113-hard-candidate",
        output_id="doc113-hard-output",
        file_path=str(image_path),
        width=1024,
        height=1024,
        status="ready",
    )
    metadata = {
        **result.metadata,
        "vision_inspection_mode": "local_image_heuristic",
    }

    report = VisionOutputInspector(vision_provider=None).inspect(resolution, metadata=metadata)

    assert report.status == "manual_review"
    assert report.mode == "local_image_heuristic"
    assert report.verification_state == "unverified"
    assert "hard_semantic_contract_unverified" in [item["code"] for item in report.detected_issues]
    assert report.evidence["required_pixel_review"] is True


def test_review_contract_reads_hard_semantics_from_frozen_ledger(monkeypatch) -> None:
    result = _hard_product_plan(monkeypatch)

    contract = active_review_contract(result.metadata)

    assert contract["enforced"] is True
    assert contract["hard_semantic_contract"] is True
    assert contract["requires_pixel_review"] is True
    assert contract["legacy_fallback_rejected"] is False
