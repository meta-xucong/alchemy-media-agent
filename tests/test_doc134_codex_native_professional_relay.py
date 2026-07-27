"""Doc134: Professional frozen-plan MCP relay contracts for M5 acceptance.

The relay is a conversation-only projection of the existing V3 planning path.
It never owns a catalog, Provider, candidate/review/retry store, or delivery
record.  The resolver supplied by an embedding host is the only trusted seam
for server-owned People Asset bindings; a default relay without that seam
must fail closed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from alchemy_creative_agent_3_0.app.generation_router import (
    ProductionImageGenerationProvider,
    build_provider_generation_request,
)
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.visual_assets import (
    CharacterCardSlot,
    InMemoryVisualAssetCatalog,
    LibraryVisualAssetCreateRequest,
    bind_professional_mode,
    PersistentVisualAssetLibraryCatalog,
    PersistentProjectVisualAssetBindingService,
    ProfessionalModeBinding,
    ProjectVisualAssetBindingRequest,
)
from alchemy_creative_agent_3_0.app.visual_assets.formal_slot_acceptance import (
    FormalSlotCandidateSummary,
    FormalSlotReceipt,
    FormalSlotRequirementSummary,
    FormalSlotSharedReviewSummary,
)
from alchemy_creative_agent_3_0.tests.professional_mode_test_support import (
    catalog_with_active_face_identity_pack,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider
from services.alchemy_codex_local_adapter.contracts import (
    CodexNativeImageGenError,
    NativeProfessionalImageGenPlanRequest,
    NativeReferenceInput,
)
from services.alchemy_codex_local_adapter.facade import CodexNativeImageGenFacade
from services.alchemy_codex_local_adapter.mcp_server import TOOL_SCHEMAS, dispatch
from services.alchemy_codex_local_adapter.native_planner import CodexNativeImageGenPlanner
from services.alchemy_codex_local_adapter.professional_binding import (
    ProfessionalBindingResolution,
    visual_asset_library_professional_binding_resolver,
)


class _CapturingRuntime:
    def __init__(self, runtime: ScenarioRuntime) -> None:
        self.runtime = runtime
        self.payloads: list[dict[str, Any]] = []
        self.last_result = None

    def plan_job(self, payload: dict[str, Any]):
        self.payloads.append(payload)
        self.last_result = self.runtime.plan_job(payload)
        return self.last_result


def _write_png(path: Path, *, color: tuple[int, int, int] = (129, 91, 77)) -> Path:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), color=color).save(path, format="PNG")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolver(catalog: InMemoryVisualAssetCatalog):
    def resolve(*, project_id: str, people_asset_id: str, job_id: str, reference_view_ids: list[str]):
        asset = catalog.get(project_id, people_asset_id)
        if asset is None or not asset.active_pack_version_id:
            return None
        pack = catalog.get_pack(project_id, people_asset_id, asset.active_pack_version_id)
        if pack is None:
            return None
        return bind_professional_mode(
            job_id=job_id,
            project_id=project_id,
            asset=asset,
            module=asset.face_identity_module,
            pack=pack,
            reference_view_ids=reference_view_ids,
        )

    return resolve


def _arguments(reference: Path, **overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "user_input": "Create a natural, realistic portrait of the selected person in a quiet studio.",
        "template_id": "general_template",
        "requested_image_count": 1,
        "requested_image_size": "1024x1024",
        "reference_inputs": [{"channel": "portrait_identity", "file_path": str(reference)}],
        "project_id": "project_professional",
        "people_asset_id": "person_1",
        "professional_identity_view_ids": ["front_1", "three_quarter_1", "profile_1"],
    }
    values.update(overrides)
    return values


def _shared_review_summary() -> FormalSlotSharedReviewSummary:
    return FormalSlotSharedReviewSummary(
        status="pass",
        evidence_codes=["shared_visual_review_verified"],
        score_dimensions=["identity_or_subject_consistency", "generic_visual_quality"],
        framing_delta_dimensions=["face_identity_view_framing_delta"],
    )


def _requirement_summary(code: str) -> FormalSlotRequirementSummary:
    return FormalSlotRequirementSummary(
        status="pass",
        evidence_codes=[code],
        dimensions={"summary_score": 0.95},
    )


def _face_receipt(*, role: str, output_id: str) -> FormalSlotReceipt:
    candidates = [
        FormalSlotCandidateSummary(
            candidate_index=index,
            candidate_id=f"candidate_{role}_{index}",
            output_id=f"output_{role}_{index}" if index != 3 else output_id,
            reviewed=True,
            selected_as_winner=index == 3,
            shared_review=_shared_review_summary(),
        )
        for index in (1, 2, 3)
    ]
    return FormalSlotReceipt(
        module="face_identity",
        slot_key=f"face_identity.{role}",
        acceptance_mode="standard_three_candidate",
        reviewed_candidate_count=3,
        candidates=candidates,
        winner_candidate_id=f"candidate_{role}_3",
        winner_output_id=output_id,
        winner_shared_review=candidates[2].shared_review,
        framing_summary=_requirement_summary("face_identity_view_framing_verified"),
        parity_summary=_requirement_summary("face_identity_reference_parity_verified"),
        identity_summary=_requirement_summary("face_identity_shared_identity_verified"),
        reload_public_projection_verified=True,
    )


def _write_root_upload_evidence(
    repository_root: Path,
    *,
    root_source_id: str,
) -> Path:
    upload_dir = repository_root / ".media_storage" / "v3_uploads" / root_source_id
    original = _write_png(upload_dir / "original.png", color=(129, 91, 77))
    digest = _sha256(original)
    (upload_dir / "asset.json").write_text(
        json.dumps(
            {
                "asset_id": root_source_id,
                "filename": "root.png",
                "mime_type": "image/png",
                "size_bytes": original.stat().st_size,
                "role": "face_reference",
                "status": "ready",
                "metadata": {
                    "source_sha256": digest,
                    "consent_reference": "user-authorized-local-reference-test",
                    "v3_owned_upload": True,
                },
            }
        ),
        encoding="utf-8",
    )
    return original


def _library_with_active_front(
    repository_root: Path,
    *,
    project_id: str = "project_professional",
    root_source_id: str = "v3_asset_root",
    output_id: str = "v3_output_front",
    bind_to_project: bool = True,
):
    library_root = repository_root / ".media_storage" / "v3_visual_asset_library"
    catalog = PersistentVisualAssetLibraryCatalog(library_root)
    created = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Model A",
            asset_type="people",
            root_source_asset_id=root_source_id,
            consent_reference="user-authorized-local-reference-test",
            preparation_intent="Reusable Professional model identity.",
        ),
    )
    activated = catalog.activate_version(
        owner_scope="local_default",
        visual_asset_id=created.visual_asset_id,
        version_id="card_v1",
        approved_evidence_ids=[output_id],
    )
    output_original = _write_png(
        library_root.parent / "v3_outputs" / output_id / "original.png",
        color=(131, 92, 78),
    )
    (output_original.parent / "output.json").write_text(
        json.dumps(
            {
                "output_id": output_id,
                "file_path": str(output_original.resolve()),
                "metadata": {"output_sha256": _sha256(output_original)},
            }
        ),
        encoding="utf-8",
    )
    card = activated.character_card
    front_slot = CharacterCardSlot(
        slot_key="face.front",
        module="face_identity",
        state="active",
        output_id=output_id,
        source_candidate_ids=["candidate_standard_front_1", "candidate_standard_front_2", "candidate_standard_front_3"],
        candidate_attempt_count=3,
        review_verified=True,
        prompt_reference_parity_verified=True,
        formal_slot_receipt=_face_receipt(role="standard_front", output_id=output_id).model_dump(mode="json"),
    )
    updated_slots = dict(card.face_slots)
    updated_slots["face.front"] = front_slot
    updated_card = card.model_copy(
        update={
            "face_identity_status": "active",
            "face_identity_version_id": "face_v1",
            "user_activation_confirmed": True,
            "face_slots": updated_slots,
        }
    )
    updated = activated.model_copy(
        update={
            "provenance": {**activated.provenance, "project_id": project_id},
            "character_card": updated_card,
        }
    )
    saved = catalog.save(updated)
    if bind_to_project:
        binding_service = PersistentProjectVisualAssetBindingService(catalog, library_root)
        binding_service.bind(
            owner_scope="local_default",
            project_id=project_id,
            request=ProjectVisualAssetBindingRequest(
                visual_asset_id=saved.visual_asset_id,
                selected_version_id=saved.active_version_id,
                confirm_binding=True,
            ),
        )
    return saved, library_root


def _provider_materializations(runtime_result) -> list[Any]:
    plan = runtime_result.planning_result
    assert plan is not None
    assets = {item.asset_id: item for item in plan.series_plan.assets}
    layouts = {item.asset_id: item for item in plan.layout_plans}
    prompts = {item.asset_id: item for item in plan.prompt_compilations}
    conditions = {item.asset_id: item for item in plan.condition_plans}
    generations = {item.asset_id: item for item in plan.generation_plans}
    materializer = ProductionImageGenerationProvider(output_store=object())
    return [
        materializer.materialize_final_prompt(
            build_provider_generation_request(
                asset_spec=asset,
                layout_plan=layouts[asset.asset_id],
                prompt_compilation=prompts[asset.asset_id],
                condition_plan=conditions[asset.asset_id],
                generation_plan=generations[asset.asset_id],
                job_id=plan.creative_job.job_id,
            )
        )
        for asset in plan.series_plan.assets
    ]


def test_professional_relay_requires_server_owned_binding_and_projects_existing_frozen_plan(tmp_path: Path) -> None:
    reference = _write_png(tmp_path / "root.png")
    catalog = catalog_with_active_face_identity_pack()
    brain = EcommerceRemoteBrainTestProvider()
    capturing = _CapturingRuntime(ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)))
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: capturing,
        professional_binding_resolver=_resolver(catalog),
    )

    parsed_request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(_arguments(reference))
    result = planner.prepare_frozen_professional_native_imagegen_plan(parsed_request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert result["requested_output_count"] == 1
    assert result["provenance"]["professional_mode"] is True
    assert result["provenance"]["professional_binding"]["pack_version_id"] == "pack_1"
    assert result["provenance"]["professional_reference_stage"] == "standard_front"
    assert result["provenance"]["professional_identity_reference_strategy"] == "serial_anchor_pack_root_reuse_v1"
    assert result["provenance"]["professional_serial_intent_sha256"] == hashlib.sha256(
        parsed_request.user_input.encode("utf-8")
    ).hexdigest()
    assert result["provenance"]["delivery_state"] == "conversation_only_not_certified"
    frozen = capturing.last_result.metadata["capability_activation_plan"]
    assert frozen["metadata"]["professional_mode"] is True
    assert "portrait_identity" in frozen["dependency_order"]
    assert brain.requests and brain.requests[0]["metadata"].get("professional_mode_binding_record") is None

    expected = _provider_materializations(capturing.last_result)
    output = result["outputs"][0]
    assert output["imagegen_prompt"] == expected[0].generation_prompt
    assert output["provider_prompt_sha256"] == expected[0].prompt_sha256
    assert output["provider_prompt_sha256"] == hashlib.sha256(output["imagegen_prompt"].encode("utf-8")).hexdigest()
    assert output["reference_image_paths"] == [item["file_path"] for item in expected[0].reference_assets]
    assert output["reference_input_contract"]["source_sha256"] == [parsed_request.reference_inputs[0].source_sha256]


def test_professional_relay_does_not_downgrade_explicit_specialist_template(tmp_path: Path) -> None:
    reference = _write_png(tmp_path / "root.png")
    catalog = catalog_with_active_face_identity_pack()
    brain = EcommerceRemoteBrainTestProvider()
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)),
        professional_binding_resolver=_resolver(catalog),
    )
    result = planner.prepare_frozen_professional_native_imagegen_plan(
        NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                reference,
                template_id="ecommerce_template",
                platform_profile="generic",
                user_input="Create the selected person's factual product portrait without visible copy.",
            )
        )
    )
    assert result["status"] == "planned_for_codex_native_imagegen"
    assert result["provenance"]["scenario_id"] == "ecommerce"
    assert brain.requests and brain.requests[0]["scenario_id"] == "ecommerce"


def test_professional_ecommerce_product_refs_do_not_infer_serial_identity_stage(
    tmp_path: Path,
) -> None:
    product = _write_png(tmp_path / "product.png")

    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            product,
            template_id="ecommerce_template",
            platform_profile="generic",
            reference_inputs=[{"channel": "product_truth", "file_path": str(product)}],
            professional_identity_view_ids=["face_front"],
        )
    )

    assert request.professional_reference_stage is None
    assert [item.channel for item in request.reference_inputs] == ["product_truth"]


def test_visual_asset_library_resolver_requires_verified_root_truth(
    tmp_path: Path,
) -> None:
    asset, library_root = _library_with_active_front(tmp_path)

    resolver = visual_asset_library_professional_binding_resolver(library_root)

    assert resolver(
        project_id="project_professional",
        people_asset_id=asset.visual_asset_id,
        job_id="job_professional",
        reference_view_ids=["face_front"],
    ) is None


def test_visual_asset_library_resolver_projects_root_and_stable_view_selectors(
    tmp_path: Path,
) -> None:
    root_source_id = "v3_asset_root"
    output_id = "v3_output_front"
    _write_root_upload_evidence(tmp_path, root_source_id=root_source_id)
    asset, library_root = _library_with_active_front(
        tmp_path,
        root_source_id=root_source_id,
        output_id=output_id,
    )

    resolver = visual_asset_library_professional_binding_resolver(library_root)
    resolved = resolver(
        project_id="project_professional",
        people_asset_id=asset.visual_asset_id,
        job_id="job_professional",
        reference_view_ids=["face_front"],
    )

    assert isinstance(resolved, ProfessionalBindingResolution)
    assert resolved.binding.people_asset_id == asset.visual_asset_id
    assert resolved.binding.identity_view_ids == ["face_front"]
    assert [item.channel for item in resolved.identity_references] == [
        "portrait_identity",
        "selected_identity_reference",
    ]
    assert [item.asset_id for item in resolved.identity_references] == [
        root_source_id,
        output_id,
    ]
    assert all(item.server_owned is True for item in resolved.identity_references)
    assert resolver(
        project_id="project_professional",
        people_asset_id=asset.visual_asset_id,
        job_id="job_professional",
        reference_view_ids=[output_id],
    ) is None


def test_visual_asset_library_resolver_requires_project_binding(
    tmp_path: Path,
) -> None:
    root_source_id = "v3_asset_root"
    output_id = "v3_output_front"
    _write_root_upload_evidence(tmp_path, root_source_id=root_source_id)
    asset, library_root = _library_with_active_front(
        tmp_path,
        root_source_id=root_source_id,
        output_id=output_id,
        bind_to_project=False,
    )

    resolver = visual_asset_library_professional_binding_resolver(library_root)

    assert resolver(
        project_id="project_professional",
        people_asset_id=asset.visual_asset_id,
        job_id="job_professional",
        reference_view_ids=["face_front"],
    ) is None


def test_professional_ecommerce_plan_requires_identity_and_product_truth_refs(
    tmp_path: Path,
) -> None:
    root_source_id = "v3_asset_root"
    output_id = "v3_output_front"
    _write_root_upload_evidence(tmp_path, root_source_id=root_source_id)
    asset, library_root = _library_with_active_front(
        tmp_path,
        root_source_id=root_source_id,
        output_id=output_id,
    )
    product_a = _write_png(tmp_path / "product-front.png", color=(80, 145, 210))
    product_b = _write_png(tmp_path / "product-back.png", color=(88, 150, 220))
    brain = EcommerceRemoteBrainTestProvider()
    capturing = _CapturingRuntime(ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)))
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: capturing,
        professional_binding_resolver=visual_asset_library_professional_binding_resolver(library_root),
    )

    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            product_a,
            template_id="ecommerce_template",
            platform_profile="generic",
            user_input="Create one controlled product-on-model catalogue image for the supplied garment.",
            reference_inputs=[
                {"channel": "product_truth", "file_path": str(product_a)},
                {"channel": "product_truth", "file_path": str(product_b)},
            ],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
        )
    )
    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert result["provenance"]["professional_mode"] is True
    assert result["provenance"]["professional_identity_reference_strategy"] == (
        "visual_asset_library_product_model_v1"
    )
    contract = result["outputs"][0]["reference_input_contract"]
    product_ids = [item.asset_id for item in request.reference_inputs]
    assert contract["declared_reference_count"] == 4
    assert contract["admitted_reference_count"] >= 4
    assert contract["professional_identity_source_asset_ids"] == [root_source_id, output_id]
    assert contract["product_truth_source_asset_ids"] == product_ids
    assert set(contract["admitted_reference_source_asset_ids"]) == {
        root_source_id,
        output_id,
        *product_ids,
    }
    assert capturing.payloads[0]["metadata"]["professional_product_model_planning"] is True
    uploaded_assets = capturing.payloads[0]["uploaded_assets"]
    uploaded_metadata = [dict(item.metadata or {}) for item in uploaded_assets]
    assert [item["codex_native_server_owned_reference"] for item in uploaded_metadata] == [
        True,
        True,
        False,
        False,
    ]
    assert [item["codex_native_selected_identity_reference"] for item in uploaded_metadata] == [
        False,
        True,
        False,
        False,
    ]
    assert [item["codex_native_reference_channel"] for item in uploaded_metadata] == [
        "portrait_identity",
        "portrait_identity",
        "product_truth",
        "product_truth",
    ]
    finalizer = [request for request in brain.requests if request["stage"] == "provider_prompt_finalize"][-1]
    bindings = finalizer["metadata"]["canonical_prompt_context"]["reference_bindings"]
    assert [item["role"] for item in bindings] == ["face_reference", "face_reference", "product_reference", "product_reference"]
    assert all("codex_native_reference_channel" not in item for item in bindings)


def test_professional_ecommerce_plan_fails_closed_when_binding_parts_are_missing(
    tmp_path: Path,
) -> None:
    root_source_id = "v3_asset_root"
    output_id = "v3_output_front"
    _write_root_upload_evidence(tmp_path, root_source_id=root_source_id)
    asset, library_root = _library_with_active_front(
        tmp_path,
        root_source_id=root_source_id,
        output_id=output_id,
    )
    product = _write_png(tmp_path / "product.png", color=(80, 145, 210))

    def plan_with_resolver(resolver):
        planner = CodexNativeImageGenPlanner(
            runtime_factory=lambda: ScenarioRuntime(
                llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())
            ),
            professional_binding_resolver=resolver,
        )
        request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                product,
                template_id="ecommerce_template",
                platform_profile="generic",
                reference_inputs=[{"channel": "product_truth", "file_path": str(product)}],
                people_asset_id=asset.visual_asset_id,
                professional_identity_view_ids=["face_front"],
            )
        )
        return planner.prepare_frozen_professional_native_imagegen_plan(request)

    complete_result = plan_with_resolver(
        visual_asset_library_professional_binding_resolver(library_root)
    )
    assert complete_result["status"] == "planned_for_codex_native_imagegen"

    asset_without_root, library_without_root = _library_with_active_front(
        tmp_path / "missing-root",
        root_source_id=root_source_id,
        output_id=output_id,
    )
    assert asset_without_root.visual_asset_id
    missing_root_result = plan_with_resolver(
        visual_asset_library_professional_binding_resolver(library_without_root)
    )
    assert missing_root_result["status"] == "blocked"
    assert missing_root_result["code"] == "codex_native_imagegen_professional_binding_unavailable"

    (library_root.parent / "v3_outputs" / output_id / "original.png").unlink()
    missing_winner_result = plan_with_resolver(
        visual_asset_library_professional_binding_resolver(library_root)
    )
    assert missing_winner_result["status"] == "blocked"
    assert missing_winner_result["code"] == "codex_native_imagegen_professional_binding_unavailable"

    root_ref = NativeReferenceInput(
        channel="portrait_identity",
        file_path=str(_write_png(tmp_path / "root-direct.png")),
        source_sha256=_sha256(tmp_path / "root-direct.png"),
        source_asset_id=root_source_id,
        server_owned=True,
    )

    def incomplete_resolver(**kwargs):
        return ProfessionalBindingResolution(
            binding=ProfessionalModeBinding(
                job_id=kwargs["job_id"],
                project_id=kwargs["project_id"],
                people_asset_id=kwargs["people_asset_id"],
                face_module_id="face_v1",
                pack_version_id="card_v1",
                identity_view_ids=list(kwargs["reference_view_ids"]),
            ),
            identity_references=(root_ref,),
        )

    incomplete_result = plan_with_resolver(incomplete_resolver)
    assert incomplete_result["status"] == "blocked"
    assert incomplete_result["code"] == "codex_native_imagegen_professional_identity_references_missing"

    no_product_request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            product,
            template_id="ecommerce_template",
            platform_profile="generic",
            reference_inputs=[],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
        )
    )
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: ScenarioRuntime(
            llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())
        ),
        professional_binding_resolver=incomplete_resolver,
    )
    no_product_result = planner.prepare_frozen_professional_native_imagegen_plan(no_product_request)
    assert no_product_result["status"] == "blocked"
    assert no_product_result["code"] in {
        "codex_native_imagegen_professional_identity_references_missing",
        "codex_native_imagegen_professional_product_binding_incomplete",
    }


def test_professional_relay_without_resolver_and_mcp_unknown_fields_fail_closed(tmp_path: Path) -> None:
    reference = _write_png(tmp_path / "root.png")
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(_arguments(reference))
    blocked = CodexNativeImageGenPlanner(runtime_factory=ScenarioRuntime).prepare_frozen_professional_native_imagegen_plan(request)
    assert blocked["status"] == "blocked"
    assert blocked["code"] == "codex_native_imagegen_professional_binding_unavailable"

    with pytest.raises(CodexNativeImageGenError) as exc:
        NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
            _arguments(reference, professional_mode_binding_record={"mode": "professional"})
        )
    assert exc.value.code == "codex_native_imagegen_invalid_input"


def test_professional_relay_accepts_exact_persisted_timestamp_identifiers(tmp_path: Path) -> None:
    reference = _write_png(tmp_path / "root.png")
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            reference,
            project_id="project_doc165_20260718T133110Z",
            people_asset_id="person_78c335f8908848b6",
        )
    )

    assert request.project_id == "project_doc165_20260718T133110Z"
    assert request.people_asset_id == "person_78c335f8908848b6"


def test_professional_serial_reference_stage_requires_root_then_reviewed_winners(tmp_path: Path) -> None:
    root = _write_png(tmp_path / "root.png")
    winner = _write_png(tmp_path / "front-winner.png")
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            root,
            reference_inputs=[
                {"channel": "portrait_identity", "file_path": str(root)},
                {"channel": "selected_identity_reference", "file_path": str(winner)},
            ],
            professional_reference_stage="three_quarter",
        )
    )
    assert request.professional_reference_stage == "three_quarter"

    with pytest.raises(CodexNativeImageGenError) as exc:
        NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
            _arguments(
                root,
                reference_inputs=[
                    {"channel": "portrait_identity", "file_path": str(root)},
                    {"channel": "portrait_identity", "file_path": str(winner)},
                ],
                professional_reference_stage="three_quarter",
            )
        )
    assert exc.value.code == "codex_native_imagegen_professional_reference_chain_invalid"


def test_professional_serial_stage_reaches_canonical_materializer_with_bounded_reference_count(tmp_path: Path) -> None:
    from PIL import Image

    root = _write_png(tmp_path / "root.png")
    front = tmp_path / "front-winner.png"
    three_quarter = tmp_path / "three-quarter-winner.png"
    Image.new("RGB", (32, 32), color=(120, 92, 80)).save(front, format="PNG")
    Image.new("RGB", (32, 32), color=(121, 92, 80)).save(three_quarter, format="PNG")
    catalog = catalog_with_active_face_identity_pack()
    brain = EcommerceRemoteBrainTestProvider()
    capturing = _CapturingRuntime(ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)))
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: capturing,
        professional_binding_resolver=_resolver(catalog),
    )

    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            root,
            reference_inputs=[
                {"channel": "portrait_identity", "file_path": str(root)},
                {"channel": "selected_identity_reference", "file_path": str(front)},
                {"channel": "selected_identity_reference", "file_path": str(three_quarter)},
            ],
            professional_reference_stage="profile",
        )
    )
    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    output = result["outputs"][0]
    assert len(output["reference_image_paths"]) == 5
    assert output["reference_input_contract"]["admitted_reference_count"] == 5
    finalizer = [request for request in brain.requests if request["stage"] == "provider_prompt_finalize"][-1]
    reference_bindings = finalizer["metadata"]["canonical_prompt_context"]["reference_bindings"]
    assert [item["professional_anchor_lineage_role"] for item in reference_bindings] == [
        "identity_root",
        "prior_view_winner",
        "prior_view_winner",
    ]
    assert [request["stage"] for request in brain.requests] == [
        "plan",
        "provider_prompt_finalize",
        "provider_prompt_professional_capture_resign",
    ]
    assert result["provenance"]["canonical_prompt_signing"]["stages"] == [
        "provider_prompt_finalize",
        "provider_prompt_professional_capture_resign",
    ]


def test_professional_serial_relay_uses_the_formal_neutral_anchor_preparation_contract(tmp_path: Path) -> None:
    root = _write_png(tmp_path / "root.png")
    catalog = catalog_with_active_face_identity_pack()
    brain = EcommerceRemoteBrainTestProvider()
    capturing = _CapturingRuntime(ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)))
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: capturing,
        professional_binding_resolver=_resolver(catalog),
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(
        NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
            _arguments(root, professional_reference_stage="standard_front")
        )
    )

    assert result["status"] == "planned_for_codex_native_imagegen"
    metadata = capturing.payloads[0]["metadata"]
    assert metadata["professional_anchor_pack_preparation"] is True
    planning = metadata["professional_planning_metadata"]
    assert planning["professional_reference_stage"] == "standard_front"
    assert planning["professional_face_identity_quality_contract"]["capture_presentation"] == (
        "neutral_identity_evidence_capture"
    )
    finalizer = [request for request in brain.requests if request["stage"] == "provider_prompt_finalize"][-1]
    context = finalizer["metadata"]["canonical_prompt_context"]
    assert context["professional_anchor_view_decision"]["capture_presentation"] == (
        "neutral_identity_evidence_capture"
    )


def test_professional_mcp_schema_and_dispatch_are_explicit_and_safe(tmp_path: Path) -> None:
    names = [tool["name"] for tool in TOOL_SCHEMAS]
    assert names == [
        "prepare_shared_mcp_materialization",
        "submit_shared_mcp_materialization",
        "prepare_native_imagegen_plan",
        "prepare_frozen_specialized_native_imagegen_plan",
        "prepare_frozen_professional_native_imagegen_plan",
    ]
    schema = next(item for item in TOOL_SCHEMAS if item["name"] == "prepare_frozen_professional_native_imagegen_plan")
    assert schema["inputSchema"]["additionalProperties"] is False
    assert "professional_mode_binding_record" not in schema["inputSchema"]["properties"]
    assert "pack_version_id" not in schema["inputSchema"]["properties"]
    assert "job_id" not in schema["inputSchema"]["properties"]

    adapter = CodexNativeImageGenFacade(enabled=True)
    response = dispatch(
        adapter,
        {
            "jsonrpc": "2.0",
            "id": 134,
            "method": "tools/call",
            "params": {
                "name": "prepare_frozen_professional_native_imagegen_plan",
                "arguments": _arguments(tmp_path / "missing.png"),
            },
        },
    )
    assert response is not None
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["code"] == "codex_native_imagegen_reference_path_unavailable"
