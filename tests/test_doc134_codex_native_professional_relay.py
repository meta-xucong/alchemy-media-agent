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
from alchemy_creative_agent_3_0.app.generation_router.providers import ProviderPromptMaterialization
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import (
    ECOMMERCE_PRODUCT_TRUTH_DETAIL_ROLE,
    ECOMMERCE_PRODUCT_TRUTH_SELECTION_ROLES,
)
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
import services.alchemy_codex_local_adapter.native_planner as native_planner_module
from services.alchemy_codex_local_adapter.professional_binding import (
    ProfessionalBindingResolution,
    visual_asset_library_professional_binding_resolver,
)


class _CapturingRuntime:
    def __init__(self, runtime: ScenarioRuntime, *, mutate_result=None) -> None:
        self.runtime = runtime
        self.mutate_result = mutate_result
        self.payloads: list[dict[str, Any]] = []
        self.last_result = None

    def plan_job(self, payload: dict[str, Any]):
        self.payloads.append(payload)
        self.last_result = self.runtime.plan_job(payload)
        if self.mutate_result is not None:
            self.last_result = self.mutate_result(self.last_result, payload)
        return self.last_result


class _ProductTruthSelectionFaultProvider(EcommerceRemoteBrainTestProvider):
    def __init__(self, selection_fault: str) -> None:
        super().__init__()
        self.selection_fault = selection_fault

    def run(self, request):
        payload = super().run(request)
        if request.stage != "plan":
            return payload
        image_set_plan = payload.get("image_set_plan")
        entries = (
            image_set_plan.get("evidence_dimensions_by_output")
            if isinstance(image_set_plan, dict)
            else None
        )
        if not isinstance(entries, list) or not entries:
            return payload
        first_entry = entries[0]
        if not isinstance(first_entry, dict):
            return payload
        product_ids = [
            str(item.get("asset_id") or "").strip()
            for item in request.uploaded_assets
            if isinstance(item, dict)
            and (
                str((item.get("metadata") or {}).get("codex_native_reference_channel") or "").strip()
                == "product_truth"
                or str(item.get("role") or "").strip() == "product_reference"
            )
            and str(item.get("asset_id") or "").strip()
        ]
        if self.selection_fault == "missing":
            first_entry.pop("selected_product_truth_asset_ids", None)
        elif self.selection_fault == "empty":
            first_entry["selected_product_truth_asset_ids"] = []
        elif self.selection_fault == "unknown":
            first_entry["selected_product_truth_asset_ids"] = ["unknown_product_truth_asset"]
        elif self.selection_fault == "duplicate":
            selected = product_ids[0] if product_ids else "missing_product_truth_asset"
            first_entry["selected_product_truth_asset_ids"] = [selected, selected]
        elif self.selection_fault == "missing_role":
            first_entry.pop("product_truth_selection_role", None)
        elif self.selection_fault == "unknown_role":
            first_entry["product_truth_selection_role"] = "unsupported_catalogue_role"
        elif self.selection_fault == "non_detail_two":
            first_entry["product_truth_selection_role"] = "lifestyle_primary_product_view"
            first_entry["selected_product_truth_asset_ids"] = product_ids[:2] or ["missing_a", "missing_b"]
        elif self.selection_fault == "full_pool":
            first_entry["product_truth_selection_role"] = "product_detail_or_print_view"
            first_entry["selected_product_truth_asset_ids"] = list(product_ids)
        return payload


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


def _product_truth_selection_mutator(
    selection_by_output_index: dict[int, list[str]],
    *,
    role_by_output_index: dict[int, str] | None = None,
):
    def mutate(result, _payload):
        if result.planning_result is None:
            return result
        updated_generation_plans = []
        for index, generation_plan in enumerate(result.planning_result.generation_plans, start=1):
            metadata = dict(generation_plan.metadata or {})
            if index in selection_by_output_index:
                metadata["selected_product_truth_asset_ids"] = list(selection_by_output_index[index])
            if role_by_output_index is not None and index in role_by_output_index:
                metadata["product_truth_selection_role"] = role_by_output_index[index]
            updated_generation_plans.append(generation_plan.model_copy(update={"metadata": metadata}))
        planning_result = result.planning_result.model_copy(
            update={"generation_plans": updated_generation_plans}
        )
        return result.model_copy(update={"planning_result": planning_result})

    return mutate


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
    monkeypatch: pytest.MonkeyPatch,
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
    product_ids = [item.asset_id for item in request.reference_inputs]
    brain = EcommerceRemoteBrainTestProvider()
    capturing = _CapturingRuntime(
        ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)),
    )
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: capturing,
        professional_binding_resolver=visual_asset_library_professional_binding_resolver(library_root),
    )
    materialization_overrides: list[dict[str, Any] | None] = []
    materialization_overrides_by_asset_id: list[dict[str, dict[str, Any]] | None] = []
    materialized_reference_assets: list[dict[str, Any]] = []
    original_materializer = CodexNativeImageGenPlanner._canonical_materializations

    def capture_materializations(planning_result, *, metadata_overrides=None, metadata_overrides_by_asset_id=None):
        materialization_overrides.append(metadata_overrides)
        materialization_overrides_by_asset_id.append(metadata_overrides_by_asset_id)
        materializations = original_materializer(
            planning_result,
            metadata_overrides=metadata_overrides,
            metadata_overrides_by_asset_id=metadata_overrides_by_asset_id,
        )
        materialized_reference_assets.extend(materializations[0].reference_assets)
        return materializations

    monkeypatch.setattr(
        CodexNativeImageGenPlanner,
        "_canonical_materializations",
        staticmethod(capture_materializations),
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert result["provenance"]["professional_mode"] is True
    assert result["provenance"]["professional_identity_reference_strategy"] == (
        "visual_asset_library_product_model_v1"
    )
    contract = result["outputs"][0]["reference_input_contract"]
    assert contract["declared_reference_count"] == 4
    # The canonical Provider materializer expands the two identity sources into
    # feature-detail + geometry inputs, then admits the one selected product
    # truth crop: 2*identity + 1*product = 5 renderer references.
    assert contract["admitted_reference_count"] == 5
    assert len(result["outputs"][0]["reference_image_paths"]) == 5
    assert contract["professional_identity_source_asset_ids"] == [root_source_id, output_id]
    assert contract["product_truth_pool_asset_ids"] == product_ids
    assert contract["product_truth_selection_role"] == "lifestyle_primary_product_view"
    assert contract["selected_product_truth_asset_ids"] == [product_ids[0]]
    assert contract["admitted_product_truth_asset_ids"] == [product_ids[0]]
    assert contract["source_sha256"] == [
        _sha256(library_root.parent / "v3_uploads" / root_source_id / "original.png"),
        _sha256(library_root.parent / "v3_outputs" / output_id / "original.png"),
        contract["product_truth_pool_source_sha256"][product_ids[0]],
    ]
    assert [item["asset_id"] for item in contract["omitted_product_truth"]] == [product_ids[1]]
    assert set(contract["admitted_reference_source_asset_ids"]) == {
        root_source_id,
        output_id,
        product_ids[0],
    }
    assert contract["admitted_reference_derivative_asset_ids"]
    assert set(contract["admitted_reference_derivative_asset_ids"]).isdisjoint(
        {root_source_id, output_id, *product_ids}
    )
    assert capturing.payloads[0]["metadata"]["professional_product_model_planning"] is True
    assert materialization_overrides == [{}]
    assert len(materialization_overrides_by_asset_id) == 1
    per_asset_overrides = materialization_overrides_by_asset_id[0] or {}
    assert len(per_asset_overrides) == 1
    provider_facing_assets = next(iter(per_asset_overrides.values()))["reference_assets"]
    assert {
        item["asset_id"]
        for item in provider_facing_assets
    } == {root_source_id, output_id, product_ids[0]}
    assert capturing.payloads[0]["metadata"]["professional_identity_reference_strategy"] == (
        "visual_asset_library_product_model_v1"
    )
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
    deliverable_context = finalizer["metadata"]["canonical_prompt_context"]["deliverables"][0]
    assert deliverable_context["metadata"]["product_truth_selection_role"] == "lifestyle_primary_product_view"
    assert deliverable_context["metadata"]["selected_product_truth_asset_ids"] == [product_ids[0]]
    product_materialized_refs = [
        item
        for item in materialized_reference_assets
        if str(item.get("source_asset_id") or item.get("asset_id") or "") in product_ids
    ]
    assert product_materialized_refs
    assert {
        str(item.get("source_asset_id") or item.get("asset_id") or "")
        for item in product_materialized_refs
    } == {product_ids[0]}
    assert all(item.get("role") != "portrait_identity" for item in product_materialized_refs)
    assert all(
        not str(item.get("derivative_kind") or "").startswith("portrait_identity")
        for item in product_materialized_refs
    )
    assert any(
        item.get("reference_truth_layer") == "product_identity_truth"
        or "product_identity_truth" in list(item.get("truth_layers") or [])
        for item in product_materialized_refs
    )


def test_professional_ecommerce_full_product_pool_selection_fails_before_capacity(
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
    products = [
        _write_png(tmp_path / f"product-{index}.png", color=(80 + index, 145, 210))
        for index in range(4)
    ]
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            products[0],
            template_id="ecommerce_template",
            platform_profile="generic",
            user_input="Create one controlled product-on-model catalogue image for the supplied garment.",
            reference_inputs=[
                {"channel": "product_truth", "file_path": str(product)}
                for product in products
            ],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
        )
    )
    product_ids = [item.asset_id for item in request.reference_inputs]
    brain = EcommerceRemoteBrainTestProvider()
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: _CapturingRuntime(
            ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)),
            mutate_result=_product_truth_selection_mutator(
                {1: product_ids},
                role_by_output_index={1: "product_detail_or_print_view"},
            ),
        ),
        professional_binding_resolver=visual_asset_library_professional_binding_resolver(library_root),
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "blocked"
    assert result["code"] == "codex_native_imagegen_product_truth_selection_invalid"


def test_professional_ecommerce_two_selected_products_exceed_preflight_provider_capacity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_source_id = "v3_asset_root"
    output_id = "v3_output_front"
    _write_root_upload_evidence(tmp_path, root_source_id=root_source_id)
    asset, library_root = _library_with_active_front(
        tmp_path,
        root_source_id=root_source_id,
        output_id=output_id,
    )
    products = [
        _write_png(tmp_path / f"product-{index}.png", color=(80 + index, 145, 210))
        for index in range(2)
    ]
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            products[0],
            template_id="ecommerce_template",
            platform_profile="generic",
            user_input="Create one controlled product-on-model catalogue image for the supplied garment.",
            reference_inputs=[
                {"channel": "product_truth", "file_path": str(product)}
                for product in products
            ],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
        )
    )
    product_ids = [item.asset_id for item in request.reference_inputs]
    materializer_calls = 0

    def fail_if_materialized(*args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal materializer_calls
        materializer_calls += 1
        raise AssertionError("over-budget detail selection must fail before Provider materialization")

    monkeypatch.setattr(
        CodexNativeImageGenPlanner,
        "_canonical_materializations",
        staticmethod(fail_if_materialized),
    )
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: _CapturingRuntime(
            ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())),
            mutate_result=_product_truth_selection_mutator(
                {1: product_ids},
                role_by_output_index={1: "product_detail_or_print_view"},
            ),
        ),
        professional_binding_resolver=visual_asset_library_professional_binding_resolver(library_root),
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "blocked"
    assert result["code"] == "codex_native_imagegen_reference_input_capacity_exceeded"
    assert materializer_calls == 0


def test_professional_ecommerce_two_selected_products_pass_when_materialized_capacity_allows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_source_id = "v3_asset_root"
    output_id = "v3_output_front"
    _write_root_upload_evidence(tmp_path, root_source_id=root_source_id)
    asset, library_root = _library_with_active_front(
        tmp_path,
        root_source_id=root_source_id,
        output_id=output_id,
    )
    products = [
        _write_png(tmp_path / f"product-{index}.png", color=(80 + index, 145, 210))
        for index in range(2)
    ]
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            products[0],
            template_id="ecommerce_template",
            platform_profile="generic",
            user_input="Create one detail-oriented product-on-model catalogue image for the supplied garment.",
            reference_inputs=[
                {"channel": "product_truth", "file_path": str(product)}
                for product in products
            ],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
        )
    )
    product_ids = [item.asset_id for item in request.reference_inputs]
    materializer_calls = 0

    def capacity_allowing_materializations(
        planning_result,
        *,
        metadata_overrides=None,
        metadata_overrides_by_asset_id=None,
    ):
        nonlocal materializer_calls
        materializer_calls += 1
        output_asset_id = str(planning_result.series_plan.assets[0].asset_id)
        provider_assets = list(
            ((metadata_overrides_by_asset_id or {}).get(output_asset_id) or {}).get("reference_assets")
            or []
        )
        assert {
            item["asset_id"]
            for item in provider_assets
        } == {root_source_id, output_id, *product_ids}
        compact_reference_assets = []
        for item in provider_assets:
            asset_id = str(item.get("asset_id") or "")
            compact_reference_assets.append(
                {
                    "asset_id": asset_id,
                    "source_asset_id": asset_id,
                    "file_path": item.get("file_path"),
                }
            )
        assert len(compact_reference_assets) == 4
        return [
            ProviderPromptMaterialization(
                generation_prompt="Frozen detail product-on-model prompt.",
                prompt_sha256="0" * 64,
                size="1024x1536",
                quality="high",
                output_format="png",
                reference_assets=compact_reference_assets,
                asset_plan={},
                protected_user_direction="",
                prompt_audit={},
                input_fidelity=None,
            )
        ]

    monkeypatch.setattr(
        CodexNativeImageGenPlanner,
        "_canonical_materializations",
        staticmethod(capacity_allowing_materializations),
    )
    monkeypatch.setattr(
        CodexNativeImageGenPlanner,
        "_professional_product_model_provider_budget",
        staticmethod(
            lambda server_owned_references: {
                "contract_version": "professional_ecommerce_provider_reference_budget_v1",
                "max_provider_reference_images": 5,
                "identity_source_asset_ids": [item.asset_id for item in server_owned_references],
                "identity_derivative_reference_count": 3,
                "product_truth_derivative_reference_count_per_source": 1,
                "max_product_truth_source_refs_per_output": 2,
                "owner": "codex_native_professional_planner",
                "basis": "provider_materialized_reference_derivative_count",
            }
        ),
    )
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: _CapturingRuntime(
            ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())),
            mutate_result=_product_truth_selection_mutator(
                {1: product_ids},
                role_by_output_index={1: "product_detail_or_print_view"},
            ),
        ),
        professional_binding_resolver=visual_asset_library_professional_binding_resolver(library_root),
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert materializer_calls == 1
    contract = result["outputs"][0]["reference_input_contract"]
    assert contract["product_truth_selection_role"] == "product_detail_or_print_view"
    assert contract["selected_product_truth_asset_ids"] == product_ids
    assert contract["admitted_product_truth_asset_ids"] == product_ids
    assert contract["admitted_reference_count"] == 4


@pytest.mark.parametrize("budget_value", [None, 0, 3, "not-an-int"])
def test_professional_ecommerce_requires_provider_reference_budget_before_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    budget_value: Any,
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
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            product,
            template_id="ecommerce_template",
            platform_profile="generic",
            user_input="Create one product-on-model catalogue image.",
            reference_inputs=[{"channel": "product_truth", "file_path": str(product)}],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
        )
    )
    materializer_calls = 0

    def invalid_budget(server_owned_references):  # noqa: ANN001
        return {
            "contract_version": "professional_ecommerce_provider_reference_budget_v1",
            "max_provider_reference_images": 5,
            "identity_source_asset_ids": [item.asset_id for item in server_owned_references],
            "identity_derivative_reference_count": 4,
            "product_truth_derivative_reference_count_per_source": 1,
            "max_product_truth_source_refs_per_output": budget_value,
            "owner": "codex_native_professional_planner",
            "basis": "provider_materialized_reference_derivative_count",
        }

    def fail_if_materialized(*args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal materializer_calls
        materializer_calls += 1
        raise AssertionError("invalid provider budget must fail before Provider materialization")

    monkeypatch.setattr(
        CodexNativeImageGenPlanner,
        "_professional_product_model_provider_budget",
        staticmethod(invalid_budget),
    )
    monkeypatch.setattr(
        CodexNativeImageGenPlanner,
        "_canonical_materializations",
        staticmethod(fail_if_materialized),
    )
    capturing_runtime = _CapturingRuntime(
        ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())),
    )
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: capturing_runtime,
        professional_binding_resolver=visual_asset_library_professional_binding_resolver(library_root),
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "blocked"
    assert result["code"] == "codex_native_imagegen_planning_blocked"
    assert materializer_calls == 0
    assert capturing_runtime.last_result is not None
    assert "ecommerce_product_truth_selection_capacity_contract_missing" in " ".join(
        capturing_runtime.last_result.warnings
    )


@pytest.mark.parametrize(
    ("selection_fault", "expected_reason"),
    [
        ("missing", "ecommerce_product_truth_selection_invalid"),
        ("empty", "ecommerce_product_truth_selection_invalid"),
        ("unknown", "ecommerce_product_truth_selection_unknown_asset"),
        ("duplicate", "ecommerce_product_truth_selection_duplicate"),
        ("missing_role", "ecommerce_product_truth_selection_invalid"),
        ("unknown_role", "ecommerce_product_truth_selection_invalid"),
    ],
)
def test_professional_ecommerce_remote_product_selection_fail_closed(
    tmp_path: Path,
    selection_fault: str,
    expected_reason: str,
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
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            product,
            template_id="ecommerce_template",
            platform_profile="generic",
            user_input="Create one controlled product-on-model catalogue image for the supplied garment.",
            reference_inputs=[{"channel": "product_truth", "file_path": str(product)}],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
        )
    )
    capturing_runtime = _CapturingRuntime(
        ScenarioRuntime(
            llm_brain_adapter=V3LLMBrainAdapter(
                provider=_ProductTruthSelectionFaultProvider(selection_fault)
            )
        )
    )
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: capturing_runtime,
        professional_binding_resolver=visual_asset_library_professional_binding_resolver(library_root),
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "blocked"
    assert result["code"] == "codex_native_imagegen_planning_blocked"
    assert capturing_runtime.last_result is not None
    assert expected_reason in " ".join(capturing_runtime.last_result.warnings)


def test_professional_ecommerce_remote_non_detail_two_product_selection_fails_closed(
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
    products = [
        _write_png(tmp_path / f"product-{index}.png", color=(80 + index, 145, 210))
        for index in range(2)
    ]
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            products[0],
            template_id="ecommerce_template",
            platform_profile="generic",
            user_input="Create one controlled product-on-model catalogue image for the supplied garment.",
            reference_inputs=[
                {"channel": "product_truth", "file_path": str(product)}
                for product in products
            ],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
        )
    )
    capturing_runtime = _CapturingRuntime(
        ScenarioRuntime(
            llm_brain_adapter=V3LLMBrainAdapter(
                provider=_ProductTruthSelectionFaultProvider("non_detail_two")
            )
        )
    )
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: capturing_runtime,
        professional_binding_resolver=visual_asset_library_professional_binding_resolver(library_root),
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "blocked"
    assert result["code"] == "codex_native_imagegen_planning_blocked"
    assert capturing_runtime.last_result is not None
    assert "ecommerce_product_truth_selection_invalid" in " ".join(capturing_runtime.last_result.warnings)


@pytest.mark.parametrize("requested_count", [1, 6])
def test_professional_ecommerce_remote_payload_requires_product_truth_selection(
    requested_count: int,
) -> None:
    request = BrainRunRequest(
        user_input="Create product-on-model catalogue imagery from supplied identity and product truth.",
        stage="plan",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        requested_image_count=requested_count,
        metadata={
            "professional_product_truth_required": True,
            "professional_product_model_planning": True,
        },
    )

    payload = json.loads(build_remote_payload(request))

    evidence_schema = payload["return_schema"]["image_set_plan"]["evidence_dimensions_by_output"][0]
    assert evidence_schema["output_index"] == (
        f"1-based integer from 1 through requested_image_count ({requested_count}); never 0"
    )
    assert evidence_schema["evidence_dimensions"] == []
    assert evidence_schema["product_truth_selection_role"] == (
        "one of lifestyle_primary_product_view|playful_environment_interaction_view|"
        "walking_or_lookback_view|back_or_structure_view|product_detail_or_print_view; "
        "only product_detail_or_print_view may select two product_truth asset IDs when "
        "ecommerce_creative_context.provider_reference_budget.max_product_truth_source_refs_per_output >= 2"
    )
    assert evidence_schema["selected_product_truth_asset_ids"] == [
        "one or two uploaded product_truth asset_id strings from the frozen product truth pool"
    ]
    instructions = payload["ecommerce_context_instructions"]
    normalized_instructions = " ".join(instructions.split())
    assert "output_index must be a 1-based integer" in instructions
    assert "evidence_dimensions must be exactly an empty list []" in instructions
    assert "product_truth_selection_role must be exactly one of" in instructions
    assert "selected_product_truth_asset_ids must be a list" in instructions
    assert "Select one product truth for ordinary lifestyle" in normalized_instructions
    assert "Select a second product truth only when product_truth_selection_role is" in normalized_instructions
    assert "max_product_truth_source_refs_per_output as a hard renderer-admission budget" in normalized_instructions
    assert "When that budget is 1, a detail or print output must still select only" in normalized_instructions
    assert "fail-closed rather than silently trimming or replacing product truth" in normalized_instructions
    assert "apparel_on_model_evidence_profile requests more than one output" not in instructions


def test_professional_ecommerce_product_truth_role_enum_is_consistent_across_boundaries() -> None:
    request = BrainRunRequest(
        user_input="Create product-on-model catalogue imagery from supplied identity and product truth.",
        stage="plan",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        requested_image_count=6,
        metadata={
            "professional_product_truth_required": True,
            "professional_product_model_planning": True,
        },
    )

    payload = json.loads(build_remote_payload(request))

    role_schema = payload["return_schema"]["image_set_plan"]["evidence_dimensions_by_output"][0][
        "product_truth_selection_role"
    ]
    schema_roles = set(role_schema.split("one of ", 1)[1].split("; ", 1)[0].split("|"))
    assert schema_roles == ECOMMERCE_PRODUCT_TRUTH_SELECTION_ROLES
    assert schema_roles == native_planner_module._ECOMMERCE_PRODUCT_TRUTH_SELECTION_ROLES
    assert ECOMMERCE_PRODUCT_TRUTH_DETAIL_ROLE == native_planner_module._ECOMMERCE_PRODUCT_TRUTH_DETAIL_ROLE
    assert ECOMMERCE_PRODUCT_TRUTH_DETAIL_ROLE in schema_roles


def test_professional_ecommerce_remote_payload_combines_apparel_and_product_selection_contracts() -> None:
    request = BrainRunRequest(
        user_input="Create a professional product-on-model apparel set.",
        stage="plan",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        requested_image_count=6,
        metadata={
            "professional_product_truth_required": True,
            "professional_product_model_planning": True,
            "ecommerce_creative_context": {
                "apparel_on_model_evidence_profile": {
                    "applies": True,
                    "allowed_evidence_dimensions": ["front_apparel_truth", "back_apparel_truth"],
                    "required_distinct_dimension_count": 2,
                }
            },
        },
    )

    payload = json.loads(build_remote_payload(request))

    evidence_schema = payload["return_schema"]["image_set_plan"]["evidence_dimensions_by_output"][0]
    assert evidence_schema["evidence_dimensions"] == [
        "allowed active apparel evidence profile values only; every item must be a string"
    ]
    assert "product_truth_selection_role" in evidence_schema
    assert "selected_product_truth_asset_ids" in evidence_schema
    instructions = payload["ecommerce_context_instructions"]
    assert "apparel_on_model_evidence_profile requests more than one output" in instructions
    assert "product_truth_selection_role must be exactly one of" in instructions
    assert "selected_product_truth_asset_ids must be a list" in instructions


def test_professional_ecommerce_remote_payload_preserves_provider_reference_budget() -> None:
    request = BrainRunRequest(
        user_input="Create a professional product-on-model detail set.",
        stage="plan",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        requested_image_count=6,
        metadata={
            "professional_product_truth_required": True,
            "professional_product_model_planning": True,
            "ecommerce_creative_context": {
                "provider_reference_budget": {
                    "contract_version": "professional_ecommerce_provider_reference_budget_v1",
                    "max_provider_reference_images": 5,
                    "identity_derivative_reference_count": 4,
                    "product_truth_derivative_reference_count_per_source": 1,
                    "max_product_truth_source_refs_per_output": 1,
                    "owner": "codex_native_professional_planner",
                    "basis": "provider_materialized_reference_derivative_count",
                }
            },
        },
    )

    payload = json.loads(build_remote_payload(request))

    budget = payload["ecommerce_creative_context"]["provider_reference_budget"]
    assert budget["max_provider_reference_images"] == 5
    assert budget["identity_derivative_reference_count"] == 4
    assert budget["max_product_truth_source_refs_per_output"] == 1
    assert "identity_source_asset_ids" not in budget
    assert "max_product_truth_source_refs_per_output as a hard renderer-admission budget" in (
        " ".join(payload["ecommerce_context_instructions"].split())
    )


def test_professional_ecommerce_native_planner_sends_brain_safe_provider_budget(
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
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            product,
            template_id="ecommerce_template",
            platform_profile="generic",
            user_input="Create one professional product-on-model image.",
            reference_inputs=[{"channel": "product_truth", "file_path": str(product)}],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
        )
    )
    capturing_runtime = _CapturingRuntime(
        ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())),
    )
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: capturing_runtime,
        professional_binding_resolver=visual_asset_library_professional_binding_resolver(library_root),
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    runtime_metadata = capturing_runtime.payloads[0]["metadata"]
    brain_budget = runtime_metadata["ecommerce_creative_context"]["provider_reference_budget"]
    assert brain_budget["identity_derivative_reference_count"] == 4
    assert brain_budget["max_product_truth_source_refs_per_output"] == 1
    assert "identity_source_asset_ids" not in brain_budget
    reference_contract = result["outputs"][0]["reference_input_contract"]
    assert reference_contract["professional_identity_source_asset_ids"] == [root_source_id, output_id]
    assert reference_contract["selected_product_truth_asset_ids"]
    assert "provider_reference_budget" not in reference_contract


@pytest.mark.parametrize("stage", ["plan", "provider_prompt_finalize"])
def test_professional_ecommerce_beach_lifestyle_intent_is_preserved_in_brain_payload(
    stage: str,
) -> None:
    request = BrainRunRequest(
        user_input=(
            "Create six Taobao and Xiaohongshu style kidswear beach product photos "
            "with the bound child model wearing the blue skirted swimsuit. The set "
            "should feel like happy beach play, natural laughter, water interaction, "
            "walking or looking back, and one garment back-structure view."
        ),
        stage=stage,
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        requested_image_count=6,
        metadata={
            "professional_product_truth_required": True,
            "professional_product_model_planning": True,
            "ecommerce_creative_context": {
                "product_set_style": "kidswear_beach_lifestyle_product_on_model",
                "role_specific_creative_intent": [
                    "joyful laugh",
                    "playful beach/water interaction",
                    "natural walking or looking-back movement",
                    "back/structure garment view",
                ],
            },
        },
    )

    payload = json.loads(build_remote_payload(request))

    instructions = payload["ecommerce_context_instructions"]
    normalized_instructions = " ".join(instructions.split())
    assert "preserve that user-owned creative" in normalized_instructions
    assert "static catalogue card" in normalized_instructions
    assert "naturally participating in the scene" in normalized_instructions
    assert "age-appropriate joyful expression" in normalized_instructions
    assert "beach/water interaction" in normalized_instructions
    assert "natural walking or looking-back movement" in normalized_instructions
    assert "back/structure garment view" in normalized_instructions
    assert "ordinary expression" in normalized_instructions
    assert "must not occupy the set's main emotional direction" in normalized_instructions
    serialized_payload = json.dumps(payload, ensure_ascii=False)
    assert "Avoid unsafe or playful action framing" not in serialized_payload
    assert "keep it as normal children clothing product photography" not in serialized_payload
    assert "shared Visual Capability" not in instructions
    assert payload["ecommerce_creative_context"]["role_specific_creative_intent"] == [
        "joyful laugh",
        "playful beach/water interaction",
        "natural walking or looking-back movement",
        "back/structure garment view",
    ]


def test_general_remote_payload_does_not_require_product_truth_selection() -> None:
    request = BrainRunRequest(
        user_input="Create a simple general image.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={},
    )

    payload = json.loads(build_remote_payload(request))

    assert "selected_product_truth_asset_ids" not in json.dumps(payload, ensure_ascii=False)


def test_professional_ecommerce_n6_uses_product_truth_pool_per_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_source_id = "v3_asset_root"
    output_id = "v3_output_front"
    _write_root_upload_evidence(tmp_path, root_source_id=root_source_id)
    asset, library_root = _library_with_active_front(
        tmp_path,
        root_source_id=root_source_id,
        output_id=output_id,
    )
    products = [
        _write_png(tmp_path / f"product-{index}.png", color=(80 + index, 145, 210))
        for index in range(4)
    ]
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            products[0],
            template_id="ecommerce_template",
            requested_image_count=6,
            platform_profile="generic",
            user_input="Create six controlled product-on-model catalogue images for the supplied garment.",
            reference_inputs=[
                {"channel": "product_truth", "file_path": str(product)}
                for product in products
            ],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
        )
    )
    product_ids = [item.asset_id for item in request.reference_inputs]
    selection_by_output = {
        1: [product_ids[0]],
        2: [product_ids[1]],
        3: [product_ids[2]],
        4: [product_ids[3]],
        5: [product_ids[0]],
        6: [product_ids[1]],
    }
    brain = EcommerceRemoteBrainTestProvider()
    capturing = _CapturingRuntime(
        ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=brain)),
    )
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: capturing,
        professional_binding_resolver=visual_asset_library_professional_binding_resolver(library_root),
    )
    materialized_by_output: dict[int, list[dict[str, Any]]] = {}
    original_materializer = CodexNativeImageGenPlanner._canonical_materializations

    def capture_materializations(planning_result, *, metadata_overrides=None, metadata_overrides_by_asset_id=None):
        materializations = original_materializer(
            planning_result,
            metadata_overrides=metadata_overrides,
            metadata_overrides_by_asset_id=metadata_overrides_by_asset_id,
        )
        for index, materialization in enumerate(materializations, start=1):
            materialized_by_output[index] = list(materialization.reference_assets)
        return materializations

    monkeypatch.setattr(
        CodexNativeImageGenPlanner,
        "_canonical_materializations",
        staticmethod(capture_materializations),
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert len(result["outputs"]) == 6
    assert len({tuple(item) for item in selection_by_output.values()}) > 1
    for output in result["outputs"]:
        index = output["output_index"]
        contract = output["reference_input_contract"]
        expected_selected = selection_by_output[index]
        assert contract["professional_identity_source_asset_ids"] == [root_source_id, output_id]
        assert contract["product_truth_pool_asset_ids"] == product_ids
        assert contract["selected_product_truth_asset_ids"] == expected_selected
        assert contract["admitted_product_truth_asset_ids"] == expected_selected
        assert contract["admitted_reference_count"] == 5
        assert len(output["reference_image_paths"]) == 5
        assert contract["source_sha256"][2:] == [
            contract["product_truth_pool_source_sha256"][asset_id]
            for asset_id in expected_selected
        ]
        assert {
            item.get("source_asset_id") or item.get("asset_id")
            for item in materialized_by_output[index]
        } == {root_source_id, output_id, *expected_selected}
        assert contract["admitted_reference_derivative_asset_ids"]
        assert set(contract["admitted_reference_derivative_asset_ids"]).isdisjoint(
            {root_source_id, output_id, *product_ids}
        )
        assert all(
            omitted["asset_id"] not in expected_selected
            and omitted["reason"] == "not_selected_for_this_frozen_deliverable"
            for omitted in contract["omitted_product_truth"]
        )


@pytest.mark.parametrize("selection_fault", ["missing_contract", "empty_selection", "mapping_mismatch"])
def test_professional_ecommerce_native_planner_blocks_invalid_product_selection_before_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selection_fault: str,
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
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            product,
            template_id="ecommerce_template",
            platform_profile="generic",
            user_input="Create one controlled product-on-model catalogue image for the supplied garment.",
            reference_inputs=[{"channel": "product_truth", "file_path": str(product)}],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
        )
    )
    original_selection = CodexNativeImageGenPlanner._professional_product_truth_selection_by_asset
    materializer_calls = 0

    def corrupt_selection(self, **kwargs):  # noqa: ANN001
        selection = original_selection(self, **kwargs)
        assert isinstance(selection, dict)
        assert not selection.get("blocked")
        output_asset_id = str(kwargs["planning_result"].series_plan.assets[0].asset_id)
        if selection_fault == "missing_contract":
            return {}
        if selection_fault == "mapping_mismatch":
            return {f"{output_asset_id}_wrong": dict(selection[output_asset_id])}
        mutated = dict(selection[output_asset_id])
        mutated["selected_product_truth_asset_ids"] = []
        return {output_asset_id: mutated}

    def fail_if_materialized(*args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal materializer_calls
        materializer_calls += 1
        raise AssertionError("invalid product selection must fail before Provider materialization")

    monkeypatch.setattr(
        CodexNativeImageGenPlanner,
        "_professional_product_truth_selection_by_asset",
        corrupt_selection,
    )
    monkeypatch.setattr(
        CodexNativeImageGenPlanner,
        "_canonical_materializations",
        staticmethod(fail_if_materialized),
    )
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: _CapturingRuntime(
            ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())),
        ),
        professional_binding_resolver=visual_asset_library_professional_binding_resolver(library_root),
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "blocked"
    assert result["code"] == "codex_native_imagegen_product_truth_selection_missing"
    assert materializer_calls == 0
    assert "outputs" not in result


def test_professional_ecommerce_native_planner_does_not_leak_unselected_product_pool_to_provider_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    product_ids = [item.asset_id for item in request.reference_inputs]
    captured_provider_assets: list[dict[str, Any]] = []
    original_materializer = CodexNativeImageGenPlanner._canonical_materializations

    def capture_materializations(planning_result, *, metadata_overrides=None, metadata_overrides_by_asset_id=None):
        per_output = metadata_overrides_by_asset_id or {}
        assert len(per_output) == 1
        captured_provider_assets.extend(next(iter(per_output.values()))["reference_assets"])
        return original_materializer(
            planning_result,
            metadata_overrides=metadata_overrides,
            metadata_overrides_by_asset_id=metadata_overrides_by_asset_id,
        )

    monkeypatch.setattr(
        CodexNativeImageGenPlanner,
        "_canonical_materializations",
        staticmethod(capture_materializations),
    )
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: _CapturingRuntime(
            ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())),
        ),
        professional_binding_resolver=visual_asset_library_professional_binding_resolver(library_root),
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    contract = result["outputs"][0]["reference_input_contract"]
    assert contract["product_truth_pool_asset_ids"] == product_ids
    assert contract["selected_product_truth_asset_ids"] == [product_ids[0]]
    assert [item["asset_id"] for item in contract["omitted_product_truth"]] == [product_ids[1]]
    assert {
        item["asset_id"]
        for item in captured_provider_assets
    } == {root_source_id, output_id, product_ids[0]}
    assert product_ids[1] not in {
        item.get("asset_id") for item in captured_provider_assets
    }
    assert product_ids[1] not in contract["admitted_reference_source_asset_ids"]
    assert product_ids[1] not in contract["reference_image_paths"] if "reference_image_paths" in contract else True


def test_professional_ecommerce_planning_only_acceptance_reads_nested_receipt() -> None:
    product_ids = ["product_a", "product_b"]
    report = {
        "planning_receipt": {"remote_brain_call_count": 0, "stages": []},
        "planner_result": {
            "status": "planned_for_codex_native_imagegen",
            "requested_output_count": 2,
            "planning_receipt": {
                "remote_brain_call_count": 2,
                "stages": ["plan", "provider_prompt_finalize"],
            },
            "outputs": [
                {
                    "reference_image_paths": ["root", "root_detail", "winner", "winner_detail", "product_a"],
                    "reference_input_contract": {
                        "selected_product_truth_asset_ids": ["product_a"],
                        "product_truth_pool_asset_ids": product_ids,
                        "product_truth_pool_source_sha256": {"product_a": "sha-a", "product_b": "sha-b"},
                        "admitted_product_truth_asset_ids": ["product_a"],
                        "admitted_reference_source_asset_ids": ["root", "winner", "product_a"],
                        "professional_identity_source_asset_ids": ["root", "winner"],
                        "admitted_reference_count": 5,
                    },
                },
                {
                    "reference_image_paths": ["root", "root_detail", "winner", "winner_detail", "product_b"],
                    "reference_input_contract": {
                        "selected_product_truth_asset_ids": ["product_b"],
                        "product_truth_pool_asset_ids": product_ids,
                        "product_truth_pool_source_sha256": {"product_a": "sha-a", "product_b": "sha-b"},
                        "admitted_product_truth_asset_ids": ["product_b"],
                        "admitted_reference_source_asset_ids": ["root", "winner", "product_b"],
                        "professional_identity_source_asset_ids": ["root", "winner"],
                        "admitted_reference_count": 5,
                    },
                },
            ],
        },
        "mutation_delta": {
            "jobs": 0,
            "candidates": 0,
            "handoffs": 0,
            "outputs": 0,
            "formal_receipts": 0,
            "slots": 0,
            "activations": 0,
        },
    }

    summary = CodexNativeImageGenPlanner.planning_only_acceptance_summary(
        report,
        expected_image_count=2,
        required_identity_source_asset_ids=["root", "winner"],
    )

    assert summary == {
        "remote_brain_two_stage": True,
        "exact_n": True,
        "selected_product_truth_from_pool_each_output": True,
        "final_refs_lte_provider_cap_each_output": True,
        "required_identity_source_present_each_output": True,
        "no_unselected_product_truth_leak": True,
        "pool_hash_parity_stable": True,
        "mutation_delta_zero": True,
    }


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
        product_ids = [item.asset_id for item in request.reference_inputs]
        planner = CodexNativeImageGenPlanner(
            runtime_factory=lambda: _CapturingRuntime(
                ScenarioRuntime(
                    llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())
                ),
            ),
            professional_binding_resolver=resolver,
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
