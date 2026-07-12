"""Regression coverage for Doc109's settled-delivery Project Mode contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    OutputRef,
    ProjectOutputSelectionStateValue,
    ProjectSelectedOutputState,
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


_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGOUMEhgYGBgYgAD"
    "AAfCAKzG2dL1AAAAAElFTkSuQmCC"
)


def _save_output(store: V3GeneratedOutputStore, *, job_id: str, candidate_id: str, asset_id: str):
    return store.save_base64_output(
        job_id=job_id,
        candidate_id=candidate_id,
        asset_id=asset_id,
        provider="doc109-test",
        model="fixture",
        encoded_image=_PNG_BASE64,
        mime_type="image/png",
        output_format="png",
    )


def test_doc109_background_generation_is_not_selectable_or_visible_until_settled() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a clean launch image"})["project"]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Create the launch image"})

    pending = handlers.mark_project_job_generating(project["project_id"], job["job_id"])
    selected = handlers.post_project_job_select(project["project_id"], job["job_id"], {})
    outputs = handlers.get_project_outputs(project_id=project["project_id"])["items"]

    assert pending["status"] == "generating"
    assert pending["candidates"] == []
    assert pending["asset_series"] == []
    assert pending["metadata"]["delivery_settling"] is True
    assert selected["metadata"]["selection_held"] is True
    assert selected["metadata"]["hold_reason"] == "finalization_pending"
    assert outputs == []


def test_doc109_canonical_resolver_requires_the_exact_candidate_not_another_asset_match(tmp_path: Path) -> None:
    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "outputs")
    handlers = V3ProductRouteHandlers()
    handlers.service.output_store = output_store
    project = handlers.post_projects({"user_goal": "Create a visual"})["project"]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Create the visual"})
    record = _save_output(output_store, job_id=job["job_id"], candidate_id="candidate_other", asset_id="asset_shared")
    service = handlers.project_service

    missing = OutputRef(
        output_ref_id="ref_missing",
        source_type="selected_candidate",
        project_id=project["project_id"],
        job_id=job["job_id"],
        asset_id="asset_shared",
        candidate_id="candidate_requested",
        selected_at="2026-07-13T00:00:00Z",
    )
    exact = OutputRef(
        output_ref_id="ref_exact",
        source_type="selected_candidate",
        project_id=project["project_id"],
        job_id=job["job_id"],
        asset_id="asset_shared",
        candidate_id="candidate_other",
        selected_at="2026-07-13T00:00:00Z",
    )
    project_record = service._require_project(project["project_id"])

    assert service._canonical_selected_output_ref(project_record, missing) is None
    resolved = service._canonical_selected_output_ref(project_record, exact)
    assert resolved is not None
    assert resolved.output_id == record.output_id
    assert resolved.preview_url == record.preview_url
    assert resolved.thumbnail_url == record.thumbnail_url
    assert resolved.download_url == record.download_url
    assert resolved.metadata["canonical_output_binding"] is True
    assert resolved.metadata["source_integrity_id"].startswith("sha256:")


def test_doc109_legacy_asset_only_selection_remains_readable_but_is_suppressed_from_continuation() -> None:
    handlers = V3ProductRouteHandlers()
    project_payload = handlers.post_projects({"user_goal": "Continue an older project"})["project"]
    project = handlers.project_service._require_project(project_payload["project_id"])
    legacy_ref = OutputRef(
        output_ref_id="legacy_asset_only_ref",
        source_type="selected_asset",
        project_id=project.project_id,
        job_id="legacy_job",
        asset_id="legacy_asset_only",
        selected_at="2026-07-13T00:00:00Z",
    )
    project.selected_output_refs.append(legacy_ref)
    project.selected_output_states.append(
        ProjectSelectedOutputState(
            project_id=project.project_id,
            job_id="legacy_job",
            output_id="legacy_asset_only",
            selection_state=ProjectOutputSelectionStateValue.SELECTED,
        )
    )
    handlers.project_service.project_store.save_project(project)

    loaded = handlers.get_project(project.project_id)

    assert loaded["project"]["selected_output_refs"][0]["asset_id"] == "legacy_asset_only"
    assert loaded["context"]["selected_output_assets"] == []
    audit = loaded["context"]["metadata"]["reference_resolution_audit"]
    assert audit["suppressed_selected_outputs"][0]["reason"] == "legacy_or_unavailable_materialized_output"


def test_doc109_selected_output_and_generated_reference_dedupe_by_content_identity() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Create a premium cover"})["project"]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Create the cover"})
    generated = handlers.post_project_job_generate(project["project_id"], job["job_id"], {"quality_mode": "standard"})

    selected = handlers.post_project_job_select(
        project["project_id"],
        job["job_id"],
        {"selected_candidate_id": generated["candidates"][0]["candidate_id"]},
    )

    references = selected["context"]["selected_visual_references"]
    source_ids = [item.get("source_integrity_id") for item in references if item.get("source_integrity_id")]
    assert source_ids
    assert len(source_ids) == len(set(source_ids))
    assert selected["metadata"]["continuation_available"] is not False


def _provider_request(reference_path: Path, *, selected_output: bool = True) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_doc109",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="1:1",
        purpose="general creative visual",
    )
    selected_reference = {
        "source_type": "selected_output" if selected_output else "uploaded",
        "output_id": "v3_output_doc109_selected" if selected_output else None,
        "asset_id": "v3_output_doc109_selected" if selected_output else "upload_doc109",
        "role": "style_reference",
        "use_policy": "style",
        "file_path": str(reference_path),
        "source_integrity_id": "sha256:doc109",
        "metadata": {"canonical_output_binding": selected_output, "source_integrity_id": "sha256:doc109"},
    }
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_doc109",
            asset_id=asset.asset_id,
            visual_prompt="clean product scene without people",
            negative_prompt="portrait, face, watermark",
            text_policy="do_not_render_final_text_in_image_model",
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_doc109", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc109",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
        ),
        metadata={
            "project_id": "project_doc109",
            "uploaded_assets": [
                {
                    "source_type": "uploaded",
                    "asset_id": "upload_doc109",
                    "role": "style_reference",
                    "file_path": str(reference_path),
                }
            ],
            "reference_assets": [selected_reference],
        },
    )


def test_doc109_reference_conditioned_nonperson_prompt_excludes_inactive_portrait_guidance(tmp_path: Path) -> None:
    request = _provider_request(tmp_path / "selected-product.png")
    active_ids = [
        "visual_grammar",
        "universal_visual_quality",
        "product_identity",
        "reference_channel_policy",
    ]
    request.metadata["capability_activation_plan"] = {
        "plan_id": "plan_doc109_product_only",
        "activation_mode": "enforced",
        "dependency_order": active_ids,
    }
    request.generation_plan.metadata["capability_activation_plan"] = request.metadata["capability_activation_plan"]
    request.metadata["visual_cluster"] = {
        "capability_activation_plan_summary": {
            "activation_mode": "enforced",
            "active_capability_ids": active_ids,
        },
        "human_photorealism_guidance": {
            "applies": True,
            "positive_prompt_fragments": ["STALE FACE-SLIMMING HUMAN RULE"],
            "negative_prompt_fragments": ["STALE PLASTIC-SKIN RULE"],
        },
        "portrait_bone_structure_lock": {
            "applies": True,
            "prompt_rules": ["STALE JAW-CHIN PORTRAIT RULE"],
        },
        "strong_reference_closure_package": {
            "active": True,
            "forbidden_drift": ["STALE SAME-PERSON FACE GEOMETRY"],
        },
    }
    references = [
        {
            "asset_id": "v3_output_doc109_selected",
            "source_type": "selected_output",
            "role": "product_reference",
            "use_policy": "product_identity",
            "truth_layers": ["product_identity_truth"],
            "strength": "hard",
        }
    ]
    provider = ProductionImageGenerationProvider()

    prompt = provider._generation_prompt(request, references)  # noqa: SLF001
    negatives = provider._negative_constraints(request)  # noqa: SLF001
    retry_guidance = provider._retry_prompt_guidance(request)  # noqa: SLF001
    execution = "\n".join([prompt, *negatives, *retry_guidance]).lower()

    for forbidden in (
        "stale face-slimming human rule",
        "stale plastic-skin rule",
        "stale jaw-chin portrait rule",
        "stale same-person face geometry",
        "human realism contract",
        "identity-preserving portrait edit",
    ):
        assert forbidden not in execution


def test_doc109_provider_reference_resolver_dedupes_by_source_content_and_records_audit(tmp_path: Path) -> None:
    from PIL import Image

    reference_path = tmp_path / "canonical.png"
    Image.new("RGB", (12, 12), color=(70, 105, 140)).save(reference_path)
    request = _provider_request(reference_path)

    resolved = ProductionImageGenerationProvider()._reference_assets(request)  # noqa: SLF001

    assert len(resolved) == 1
    assert resolved[0]["output_id"] == "v3_output_doc109_selected"
    audit = request.metadata["provider_reference_resolution_audit"]
    assert audit["retained"][0]["source_id"] == "v3_output_doc109_selected"
    assert audit["suppressed"][0]["reason"] == "duplicate_source_content"
    assert audit["no_substitution"] is True


def test_doc109_provider_reference_resolver_rejects_unmaterialized_selected_output(tmp_path: Path) -> None:
    request = _provider_request(tmp_path / "missing.png")

    with pytest.raises(ValueError, match="no substitute provider input"):
        ProductionImageGenerationProvider()._reference_assets(request)  # noqa: SLF001
