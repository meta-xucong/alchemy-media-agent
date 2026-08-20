import base64
import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.creative_core.central_brain import CentralCreativeBrain
from alchemy_creative_agent_3_0.app.generation_router import (
    GenerationRequest,
    McpMaterializationProvider,
    ProductionImageGenerationProvider,
)
from alchemy_creative_agent_3_0.app.generation_router.providers import ReferenceInputAdmissionError
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore
from alchemy_creative_agent_3_0.app.project_mode.ecommerce_view_activation import (
    DisabledEcommerceViewActivationIssuer,
)
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.reference_projection import (
    ProductTruthSource,
    build_physical_product_projection,
    build_product_truth_admission,
)
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    LibraryVisualAssetCreateRequest,
    ProjectVisualAssetBindingService,
    VisualAssetLibraryCatalog,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    CharacterCardSlot,
    CharacterCardState,
    apply_face_identity_pack_to_card,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import (
    AnchorView,
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    RootSourceProvenance,
)
from alchemy_creative_agent_3_0.app.visual_assets.formal_slot_acceptance import (
    FormalSlotAcceptanceCore,
    FormalSlotCandidateSummary,
    FormalSlotRequirementSummary,
    FormalSlotSharedReviewSummary,
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
from alchemy_creative_agent_3_0.app.scenario_packs import ScenarioSelection
from alchemy_creative_agent_3_0.app.shared_capabilities import (
    AssetBindingPlanner,
    AssetRole,
    AssetRoleAnalyzer,
    CapabilityInput,
    UploadedAssetInfo,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service


@pytest.fixture(autouse=True)
def _standard_reference_capacity_for_product_scope_tests(monkeypatch):
    """Keep truth-admission tests independent from the active gateway profile."""

    monkeypatch.setattr(
        ProductionImageGenerationProvider,
        "configured_reference_image_capacity",
        classmethod(lambda cls: cls.max_provider_reference_images),
    )


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (96, 72), color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _image(path: Path, color: tuple[int, int, int]) -> Path:
    path.write_bytes(_png_bytes(color))
    return path


def _reference(
    *,
    asset_id: str,
    role: str,
    path: Path,
) -> dict[str, object]:
    metadata = {
        "provider_input_required": True,
        "codex_native_reference_channel": (
            "product_truth" if role == "product_reference" else "portrait_identity"
        ),
    }
    return {
        "asset_id": asset_id,
        "role": role,
        "file_path": str(path),
        "filename": path.name,
        "mime_type": "image/png",
        "provider_input_required": True,
        "metadata": metadata,
    }


def _template_plan(
    *,
    selected_product_ids: list[str] | None,
    pool_product_ids: list[str],
) -> dict[str, object]:
    deliverable_metadata: dict[str, object] = {
        "product_truth_pool_asset_ids": list(pool_product_ids),
    }
    if selected_product_ids is not None:
        deliverable_metadata.update(
            {
                "product_truth_selection_role": "lifestyle_primary_product_view",
                "selected_product_truth_asset_ids": list(selected_product_ids),
                "admitted_product_truth_asset_ids": list(selected_product_ids),
                "max_product_truth_source_refs_per_output": 2,
                "product_truth_selection_source": (
                    "remote_brain_image_set_plan.evidence_dimensions_by_output"
                ),
            }
        )
    return {
        "plan_id": "template_plan_ecommerce_truth_scope",
        "template_id": "ecommerce_template",
        "scenario_id": "ecommerce",
        "owner": "ecommerce_scenario_pack",
        "creative_direction_owner": "remote_v3_llm_brain",
        "requested_image_count": 1,
        "effective_image_count": 1,
        "deliverables": [
            {
                "deliverable_id": "deliverable_1",
                "output_index": 1,
                "image_intent": "show the product faithfully",
                "source": "remote_v3_llm_brain",
                "factual_acceptance": ["product_truth"],
                "metadata": deliverable_metadata,
            }
        ],
        "provenance": [],
    }


def _generation_request(
    *,
    references: list[dict[str, object]],
    selected_product_ids: list[str] | None,
    pool_product_ids: list[str],
) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_ecommerce_truth_scope",
        asset_type=AssetType.ECOMMERCE_MAIN_IMAGE,
        platform=Platform.ECOMMERCE_GENERIC,
        aspect_ratio="1:1",
        purpose="professional ecommerce product image",
        priority=1,
    )
    request = GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_ecommerce_truth_scope",
            asset_id=asset.asset_id,
            visual_prompt="professional product image",
            text_policy="do_not_render_final_text_in_image_model",
        ),
        condition_plan=ConditionPlan(
            condition_plan_id="condition_ecommerce_truth_scope",
            asset_id=asset.asset_id,
        ),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_ecommerce_truth_scope",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "uploaded_assets": references,
            "professional_product_truth_required": True,
            "professional_ecommerce_product_truth_pool_asset_ids": list(pool_product_ids),
            "template_deliverable_plan": _template_plan(
                selected_product_ids=selected_product_ids,
                pool_product_ids=pool_product_ids,
            ),
        },
    )
    by_asset_id = {str(item["asset_id"]): item for item in references}
    sources = []
    for asset_id in pool_product_ids:
        path = Path(str(by_asset_id[asset_id]["file_path"]))
        content_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        consent = f"fixture:{asset_id}:consent"
        rights = f"fixture:{asset_id}:rights"
        receipt_digest = hashlib.sha256(
            "|".join(
                (
                    "v3_upload_authorization_receipt_v1",
                    asset_id,
                    content_sha256,
                    "product_reference",
                    "product_truth",
                    consent,
                    rights,
                )
            ).encode("utf-8")
        ).hexdigest()
        sources.append(
            ProductTruthSource(
                asset_id=asset_id,
                content_sha256=content_sha256,
                consent_reference=consent,
                rights_reference=rights,
                receipt_digest=receipt_digest,
                role="product_reference",
                product_truth_channel="product_truth",
                readiness="ready",
                file_integrity="sha256_verified",
                provenance="fixture_product_api",
            )
        )
    admission = build_product_truth_admission(
        project_id="ecommerce_scope_project",
        job_id="ecommerce_scope_job",
        sources=sources,
        product_truth_plan_digest=hashlib.sha256(
            b"ecommerce_scope_plan_digest"
        ).hexdigest(),
    )
    request.metadata.update(
        {
            "project_id": admission.project_id,
            "job_id": admission.job_id,
            "professional_ecommerce_contract_authority": "v3_product_api",
            "professional_ecommerce_product_truth_admission": admission.model_dump(),
        }
    )
    if selected_product_ids is not None:
        projection = build_physical_product_projection(
            job_id=admission.job_id,
            output_index=1,
            admission=admission,
            selected_product_asset_ids=selected_product_ids,
            selection_source="remote_brain_image_set_plan.evidence_dimensions_by_output",
            selection_role=(
                "product_detail_or_print_view"
                if len(selected_product_ids) == 2
                else "lifestyle_primary_product_view"
            ),
            cap_reservation=2,
        )
        request.metadata["professional_ecommerce_physical_product_projection"] = (
            projection.model_dump()
        )
        request.metadata["professional_ecommerce_physical_product_projections"] = {
            "1": projection.model_dump()
        }
    return request


def test_professional_ecommerce_truth_pool_suppresses_only_product_role_conflict(tmp_path) -> None:
    product_a = _image(tmp_path / "product-a.png", (220, 70, 70))
    product_b = _image(tmp_path / "product-b.png", (70, 160, 220))
    face = _image(tmp_path / "face.png", (200, 170, 150))
    planner = AssetBindingPlanner()

    result = planner.execute(
        CapabilityInput(
            job_id="job_ecommerce_truth_pool",
            scenario_id="ecommerce",
            user_input="Create a professional ecommerce product image.",
            uploaded_assets=[
                UploadedAssetInfo(
                    asset_id="product_a",
                    role=AssetRole.PRODUCT_REFERENCE,
                    file_path=str(product_a),
                    filename=product_a.name,
                ),
                UploadedAssetInfo(
                    asset_id="product_b",
                    role=AssetRole.PRODUCT_REFERENCE,
                    file_path=str(product_b),
                    filename=product_b.name,
                ),
                UploadedAssetInfo(
                    asset_id="face_reference",
                    role=AssetRole.FACE_REFERENCE,
                    file_path=str(face),
                    filename=face.name,
                ),
            ],
            metadata={
                "professional_product_truth_required": True,
                "professional_ecommerce_product_truth_pool_asset_ids": ["product_a", "product_b"],
            },
        )
    )

    assert not any(
        warning.code == "asset_binding_role_conflict"
        and warning.metadata.get("asset_ids") == ["product_a", "product_b"]
        for warning in result.warnings
    )


def test_provider_emits_selected_product_truth_and_preserves_non_product_references(tmp_path) -> None:
    product_a = _reference(
        asset_id="product_a",
        role="product_reference",
        path=_image(tmp_path / "product-a.png", (220, 70, 70)),
    )
    product_b = _reference(
        asset_id="product_b",
        role="product_reference",
        path=_image(tmp_path / "product-b.png", (70, 160, 220)),
    )
    product_c = _reference(
        asset_id="product_c",
        role="product_reference",
        path=_image(tmp_path / "product-c.png", (80, 210, 110)),
    )
    face = _reference(
        asset_id="face_reference",
        role="face_reference",
        path=_image(tmp_path / "face.png", (200, 170, 150)),
    )
    request = _generation_request(
        references=[product_a, product_b, product_c, face],
        selected_product_ids=["product_b"],
        pool_product_ids=["product_a", "product_b", "product_c"],
    )

    assets = ProductionImageGenerationProvider()._reference_assets(request)  # noqa: SLF001

    assert [item["asset_id"] for item in assets] == ["product_b", "face_reference"]
    assert request.metadata["professional_ecommerce_product_truth_projection"] == {
        "output_index": 1,
        "selected_product_truth_asset_ids": ["product_b"],
        "suppressed_product_truth_asset_ids": ["product_a", "product_c"],
    }


def test_mcp_provider_uses_the_same_professional_ecommerce_truth_scope(tmp_path) -> None:
    product_a = _reference(
        asset_id="product_a",
        role="product_reference",
        path=_image(tmp_path / "product-a.png", (220, 70, 70)),
    )
    product_b = _reference(
        asset_id="product_b",
        role="product_reference",
        path=_image(tmp_path / "product-b.png", (70, 160, 220)),
    )
    face = _reference(
        asset_id="face_reference",
        role="face_reference",
        path=_image(tmp_path / "face.png", (200, 170, 150)),
    )
    request = _generation_request(
        references=[product_a, product_b, face],
        selected_product_ids=["product_a"],
        pool_product_ids=["product_a", "product_b"],
    )

    assets = McpMaterializationProvider()._reference_assets(request)  # noqa: SLF001

    assert [item["asset_id"] for item in assets] == ["product_a", "face_reference"]


def test_professional_ecommerce_truth_scope_fails_closed_without_frozen_selection(tmp_path) -> None:
    product_a = _reference(
        asset_id="product_a",
        role="product_reference",
        path=_image(tmp_path / "product-a.png", (220, 70, 70)),
    )
    product_b = _reference(
        asset_id="product_b",
        role="product_reference",
        path=_image(tmp_path / "product-b.png", (70, 160, 220)),
    )
    request = _generation_request(
        references=[product_a, product_b],
        selected_product_ids=None,
        pool_product_ids=["product_a", "product_b"],
    )

    with pytest.raises(ReferenceInputAdmissionError, match="selection"):
        ProductionImageGenerationProvider()._reference_assets(request)  # noqa: SLF001


def test_product_truth_scope_keeps_five_image_cap_after_selection(tmp_path) -> None:
    products = [
        _reference(
            asset_id=f"product_{index}",
            role="product_reference",
            path=_image(tmp_path / f"product-{index}.png", (120 + index, 80, 150)),
        )
        for index in range(3)
    ]
    faces = [
        _reference(
            asset_id=f"face_{index}",
            role="face_reference",
            path=_image(tmp_path / f"face-{index}.png", (190, 150 + index, 130)),
        )
        for index in range(5)
    ]
    request = _generation_request(
        references=[*products, *faces],
        selected_product_ids=["product_1"],
        pool_product_ids=["product_0", "product_1", "product_2"],
    )

    with pytest.raises(ReferenceInputAdmissionError, match="cannot accept all declared"):
        ProductionImageGenerationProvider()._reference_assets(request)  # noqa: SLF001

    assert request.metadata["provider_reference_resolution_audit"]["capacity_exceeded"] == {
        "reference_count": 6,
        "maximum_reference_images": 5,
    }


def test_product_api_issues_product_truth_pool_only_for_trusted_professional_binding(tmp_path, monkeypatch) -> None:
    service = V3ProductApiService()
    service.asset_store.storage_root = tmp_path / "uploads"
    asset_ids = []
    for index in range(2):
        upload = service.create_uploaded_asset(
            {
                "filename": f"product-{index}.png",
                "mime_type": "image/png",
                "size_bytes": len(_png_bytes((120 + index, 80, 150))),
                "role": "product_reference",
            }
        )
        service.store_uploaded_asset_content(
            upload.asset_id,
            {
                "content_base64": base64.b64encode(_png_bytes((120 + index, 80, 150))).decode(
                    "ascii"
                ),
                "mime_type": "image/png",
            },
        )
        service.complete_uploaded_asset(upload.asset_id)
        asset_ids.append(upload.asset_id)

    request = CreateCreativeJobRequest(
        user_input="Create a professional ecommerce product image.",
        scenario_selection=ScenarioSelection(scenario_id="ecommerce"),
        uploaded_asset_ids=asset_ids,
        metadata={
            "template_id": "ecommerce_template",
            "frozen_visual_asset_binding_set": {"state": "empty"},
        },
    )
    service._prepare_ecommerce_creative_context(request)  # noqa: SLF001

    assert request.metadata["professional_product_truth_required"] is True
    assert request.metadata["professional_ecommerce_product_truth_pool_asset_ids"] == asset_ids
    assert request.metadata["ecommerce_creative_context"]["product_truth_reference_pool"] == [
        {
            "asset_id": asset_id,
            "reference_channel": "product_truth",
            "source_type": "uploaded",
        }
        for asset_id in asset_ids
    ]
    assert request.metadata["ecommerce_creative_context"]["provider_reference_budget"] == {
        "max_product_truth_source_refs_per_output": 2,
        "max_total_reference_images": 5,
    }

    monkeypatch.setattr(
        ProductionImageGenerationProvider,
        "configured_reference_image_capacity",
        classmethod(lambda cls: 1),
    )
    constrained_request = CreateCreativeJobRequest(
        user_input="Create a professional ecommerce product image.",
        scenario_selection=ScenarioSelection(scenario_id="ecommerce"),
        uploaded_asset_ids=asset_ids,
        metadata={
            "template_id": "ecommerce_template",
            "frozen_visual_asset_binding_set": {"state": "empty"},
        },
    )
    service._prepare_ecommerce_creative_context(constrained_request)  # noqa: SLF001

    assert constrained_request.metadata["ecommerce_creative_context"]["provider_reference_budget"] == {
        "max_product_truth_source_refs_per_output": 1,
        "max_total_reference_images": 1,
    }


def test_project_mode_bound_visual_asset_freezes_before_ecommerce_truth_preflight(tmp_path) -> None:
    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "outputs")
    service = ecommerce_test_service(output_store=output_store)
    service.asset_store.storage_root = tmp_path / "uploads"
    catalog = VisualAssetLibraryCatalog()
    binding_service = ProjectVisualAssetBindingService(catalog)
    handlers = V3ProductRouteHandlers(
        service=service,
        project_store=InMemoryProjectStore(),
        visual_asset_library_catalog=catalog,
        project_visual_asset_binding_service=binding_service,
        ecommerce_view_activation_issuer=DisabledEcommerceViewActivationIssuer(),
    )

    product_ids = []
    for index in range(4):
        upload = handlers.post_uploads(
            {
                "filename": f"product-{index}.png",
                "mime_type": "image/png",
                "size_bytes": len(_png_bytes((120 + index, 80, 150))),
                "role": "product_reference",
            }
        )
        handlers.put_upload_content(
            upload["asset_id"],
            {
                "content_base64": base64.b64encode(_png_bytes((120 + index, 80, 150))).decode("ascii"),
                "mime_type": "image/png",
            },
        )
        handlers.post_upload_complete(upload["asset_id"])
        product_ids.append(upload["asset_id"])

    people_asset = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Bound person",
            asset_type="people",
            root_source_asset_id="v3_asset_people_root",
            consent_reference="user-authorized-source",
            preparation_intent="A neutral reusable people reference.",
        ),
    )
    face_output_ids = [
        output_store.save_base64_output(
            job_id=f"job_visual_asset_anchor_{index}",
            candidate_id=f"candidate_visual_asset_anchor_{index}",
            asset_id=f"asset_visual_asset_anchor_{index}",
            provider="fixture",
            model="fixture",
            encoded_image=base64.b64encode(_png_bytes((180, 150, 120))).decode("ascii"),
        ).output_id
        for index in range(3)
    ]
    people_asset = catalog.activate_version(
        owner_scope="local_default",
        visual_asset_id=people_asset.visual_asset_id,
        version_id="pack_people_v1",
        approved_evidence_ids=["fixture-three-face-chain"],
    )
    catalog.save(
        people_asset.model_copy(
            update={
                "character_card": _active_face_card(
                    visual_asset_id=people_asset.visual_asset_id,
                    output_ids=face_output_ids,
                )
            }
        )
    )
    project = handlers.post_projects(
        {"user_goal": "Create an ecommerce image set", "primary_template_id": "ecommerce_template"}
    )["project"]
    handlers.post_project_visual_asset_binding(
        project["project_id"],
        {
            "visual_asset_id": people_asset.visual_asset_id,
            "selected_version_id": people_asset.active_version_id,
            "confirm_binding": True,
        },
    )

    job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create the ecommerce image set using the supplied product evidence.",
            "uploaded_asset_ids": product_ids,
        },
    )
    record = service.get_job_record(job["job_id"])

    assert record is not None
    assert job["status"] == "planned"
    assert record.request.metadata["frozen_visual_asset_binding_set"]["state"] == "valid"
    assert record.request.metadata["professional_product_truth_required"] is True
    assert record.request.metadata["professional_ecommerce_product_truth_pool_asset_ids"] == product_ids


def test_project_mode_receipt_bound_visual_asset_resolves_its_active_face_winners(tmp_path) -> None:
    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "outputs")
    service = ecommerce_test_service(output_store=output_store)
    service.asset_store.storage_root = tmp_path / "uploads"
    catalog = VisualAssetLibraryCatalog()
    binding_service = ProjectVisualAssetBindingService(catalog)
    handlers = V3ProductRouteHandlers(
        service=service,
        project_store=InMemoryProjectStore(),
        visual_asset_library_catalog=catalog,
        project_visual_asset_binding_service=binding_service,
        ecommerce_view_activation_issuer=DisabledEcommerceViewActivationIssuer(),
    )

    product_ids = []
    for index in range(4):
        upload = handlers.post_uploads(
            {
                "filename": f"product-{index}.png",
                "mime_type": "image/png",
                "size_bytes": len(_png_bytes((120 + index, 80, 150))),
                "role": "product_reference",
            }
        )
        handlers.put_upload_content(
            upload["asset_id"],
            {
                "content_base64": base64.b64encode(_png_bytes((120 + index, 80, 150))).decode("ascii"),
                "mime_type": "image/png",
            },
        )
        handlers.post_upload_complete(upload["asset_id"])
        product_ids.append(upload["asset_id"])

    people_asset = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Receipt-bound person",
            asset_type="people",
            root_source_asset_id="v3_asset_people_root",
            consent_reference="user-authorized-source",
            preparation_intent="A neutral reusable people reference.",
        ),
    )
    face_output_ids = [
        output_store.save_base64_output(
            job_id=f"job_face_{role}",
            candidate_id=f"candidate_face_{role}",
            asset_id=f"asset_face_{role}",
            provider="fixture",
            model="fixture",
            encoded_image=base64.b64encode(_png_bytes((180, 150, 120))).decode("ascii"),
        ).output_id
        for role in ("front", "three_quarter", "profile")
    ]
    card = _active_face_card(
        visual_asset_id=people_asset.visual_asset_id,
        output_ids=face_output_ids,
    )
    people_asset = catalog.activate_version(
        owner_scope="local_default",
        visual_asset_id=people_asset.visual_asset_id,
        version_id="pack_people_receipt_v1",
        approved_evidence_ids=["formal_face_slot_receipts_verified"],
    )
    catalog.save(people_asset.model_copy(update={"character_card": card}))

    project = handlers.post_projects(
        {"user_goal": "Create an ecommerce image set", "primary_template_id": "ecommerce_template"}
    )["project"]
    handlers.post_project_visual_asset_binding(
        project["project_id"],
        {
            "visual_asset_id": people_asset.visual_asset_id,
            "selected_version_id": people_asset.active_version_id,
            "confirm_binding": True,
        },
    )

    job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create the ecommerce image set using the supplied product evidence.",
            "uploaded_asset_ids": product_ids,
        },
    )
    record = service.get_job_record(job["job_id"])

    assert record is not None
    assert job["status"] == "planned"
    assert [
        item["output_id"]
        for item in record.request.metadata["visual_asset_library_reference_assets"]
    ] == face_output_ids
    assert record.request.metadata["professional_ecommerce_product_truth_pool_asset_ids"] == product_ids
    face_chain_bindings = record.request.metadata[
        "visual_asset_library_formal_face_chain_bindings"
    ]
    assert set(face_chain_bindings) == set(face_output_ids)
    assert {
        item["chain_kind"] for item in face_chain_bindings.values()
    } == {"formal_face_identity_v1"}

    runtime_payload = service._runtime_request_payload(record.request)  # noqa: SLF001
    capability_input = CapabilityInput(
        job_id="job_formal_face_chain",
        scenario_id="ecommerce",
        user_input=record.request.user_input,
        uploaded_assets=runtime_payload["uploaded_assets"],
        metadata=runtime_payload["metadata"],
    )
    role_analysis = AssetRoleAnalyzer().execute(capability_input)
    planned = AssetBindingPlanner().execute(
        capability_input.model_copy(update={"prior_results": [role_analysis]})
    )
    assert not any(
        warning.code == "asset_binding_role_conflict"
        and warning.metadata.get("asset_ids") == face_output_ids
        for warning in planned.warnings
    )

    unrelated_face = _image(tmp_path / "unrelated-face.png", (220, 160, 120))
    conflicting_input = capability_input.model_copy(
        update={
            "uploaded_assets": [
                *capability_input.uploaded_assets,
                UploadedAssetInfo(
                    asset_id="unrelated_face_upload",
                    role=AssetRole.FACE_REFERENCE,
                    file_path=str(unrelated_face),
                    filename=unrelated_face.name,
                ),
            ]
        }
    )
    conflicting_analysis = AssetRoleAnalyzer().execute(conflicting_input)
    conflicting_plan = AssetBindingPlanner().execute(
        conflicting_input.model_copy(update={"prior_results": [conflicting_analysis]})
    )
    assert any(
        warning.code == "asset_binding_role_conflict"
        and "unrelated_face_upload" in warning.metadata.get("asset_ids", [])
        for warning in conflicting_plan.warnings
    )


def test_project_mode_receipt_bound_visual_asset_fails_closed_without_active_face_chain(tmp_path) -> None:
    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "outputs")
    service = ecommerce_test_service(output_store=output_store)
    service.asset_store.storage_root = tmp_path / "uploads"
    catalog = VisualAssetLibraryCatalog()
    binding_service = ProjectVisualAssetBindingService(catalog)
    handlers = V3ProductRouteHandlers(
        service=service,
        project_store=InMemoryProjectStore(),
        visual_asset_library_catalog=catalog,
        project_visual_asset_binding_service=binding_service,
        ecommerce_view_activation_issuer=DisabledEcommerceViewActivationIssuer(),
    )
    upload = handlers.post_uploads(
        {
            "filename": "product.png",
            "mime_type": "image/png",
            "size_bytes": len(_png_bytes((120, 80, 150))),
            "role": "product_reference",
        }
    )
    handlers.put_upload_content(
        upload["asset_id"],
        {
            "content_base64": base64.b64encode(_png_bytes((120, 80, 150))).decode("ascii"),
            "mime_type": "image/png",
        },
    )
    handlers.post_upload_complete(upload["asset_id"])
    people_asset = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Broken receipt-bound person",
            asset_type="people",
            root_source_asset_id="v3_asset_people_root",
            consent_reference="user-authorized-source",
            preparation_intent="A neutral reusable people reference.",
        ),
    )
    face_output_ids = [
        output_store.save_base64_output(
            job_id=f"job_face_{role}",
            candidate_id=f"candidate_face_{role}",
            asset_id=f"asset_face_{role}",
            provider="fixture",
            model="fixture",
            encoded_image=base64.b64encode(_png_bytes((180, 150, 120))).decode("ascii"),
        ).output_id
        for role in ("front", "three_quarter", "profile")
    ]
    card = _active_face_card(
        visual_asset_id=people_asset.visual_asset_id,
        output_ids=face_output_ids,
    )
    broken_slots = dict(card.face_slots)
    broken_slots["face.profile"] = CharacterCardSlot(
        slot_key="face.profile",
        module="face_identity",
    )
    broken_card = card.model_copy(update={"face_slots": broken_slots})
    people_asset = catalog.activate_version(
        owner_scope="local_default",
        visual_asset_id=people_asset.visual_asset_id,
        version_id="pack_people_broken_receipt_v1",
        approved_evidence_ids=["formal_face_slot_receipts_verified"],
    )
    catalog.save(people_asset.model_copy(update={"character_card": broken_card}))
    project = handlers.post_projects(
        {"user_goal": "Create an ecommerce image set", "primary_template_id": "ecommerce_template"}
    )["project"]
    handlers.post_project_visual_asset_binding(
        project["project_id"],
        {
            "visual_asset_id": people_asset.visual_asset_id,
            "selected_version_id": people_asset.active_version_id,
            "confirm_binding": True,
        },
    )

    with pytest.raises(ValueError, match="visual_asset_library_active_face_chain_invalid"):
        handlers.post_project_job(
            project["project_id"],
            {
                "template_id": "ecommerce_template",
                "user_input": "Create the ecommerce image set using the supplied product evidence.",
                "uploaded_asset_ids": [upload["asset_id"]],
            },
        )


def test_public_job_cannot_supply_formal_face_chain_bindings() -> None:
    service = V3ProductApiService()

    with pytest.raises(
        ValueError,
        match="runtime_metadata_server_owned: visual_asset_library_formal_face_chain_bindings",
    ):
        service.create_job(
            {
                "user_input": "Create one professional ecommerce image.",
                "scenario_selection": {"scenario_id": "ecommerce"},
                "metadata": {
                    "visual_asset_library_formal_face_chain_bindings": {
                        "untrusted_output": {
                            "chain_id": "sha256:forged",
                            "chain_kind": "formal_face_identity_v1",
                        }
                    }
                },
            }
        )


def _active_face_card(*, visual_asset_id: str, output_ids: list[str]) -> CharacterCardState:
    roles = ("standard_front", "three_quarter", "profile")
    if len(output_ids) != len(roles):
        raise ValueError("fixture requires three active face outputs")
    shared_review = FormalSlotSharedReviewSummary(
        status="pass",
        evidence_codes=["fixture_shared_review_passed"],
        score_dimensions=["identity_consistency"],
    )
    requirement = FormalSlotRequirementSummary(
        status="pass",
        evidence_codes=["fixture_requirement_passed"],
        dimensions={"fixture_score": 1.0},
    )
    views = []
    for role, output_id in zip(roles, output_ids, strict=True):
        receipt = FormalSlotAcceptanceCore().accept(
            module="face_identity",
            slot_key=f"face_identity.{role}",
            acceptance_mode="standard_three_candidate",
            candidates=[
                FormalSlotCandidateSummary(
                    candidate_index=index,
                    candidate_id=f"candidate_{role}_{index}",
                    output_id=output_id if index == 1 else f"{output_id}_alternate_{index}",
                    reviewed=True,
                    shared_review=shared_review,
                )
                for index in (1, 2, 3)
            ],
            framing_summary=requirement,
            parity_summary=requirement,
            identity_summary=requirement,
            ranking_key=lambda candidate, winner_output_id=output_id: (
                1.0 if candidate.output_id == winner_output_id else 0.5
            ),
            reload_public_projection_verified=True,
        )
        views.append(
            AnchorView(
                view_id=f"view_{role}",
                view_role=role,
                output_id=output_id,
                source_candidate_ids=[candidate.candidate_id for candidate in receipt.candidates],
                identity_scores=IdentityScoreSummary(
                    same_face_score=0.95,
                    visual_quality_score=0.9,
                    distinctive_feature_score=0.94,
                    human_realism_score=0.9,
                ),
                formal_slot_receipt=receipt,
            )
        )
    pack = IdentityAnchorPackVersion(
        pack_version_id="pack_people_receipt_v1",
        people_asset_id=visual_asset_id,
        status="active",
        anchor_views=views,
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id="v3_asset_people_root",
            project_id="project_fixture",
            consent_reference="user-authorized-source",
        ),
        user_activation_confirmed=True,
    )
    return apply_face_identity_pack_to_card(
        CharacterCardState.initial(card_version_id="card_people_receipt_v1"),
        pack,
    )


def test_public_product_truth_scope_marker_cannot_be_forged() -> None:
    service = V3ProductApiService()

    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        service.create_job(
            {
                "user_input": "Create an ecommerce product image.",
                "scenario_selection": {"scenario_id": "ecommerce"},
                "metadata": {"professional_product_truth_required": True},
            }
        )


def test_central_planning_preserves_product_truth_scope_for_provider_materialization() -> None:
    result = CentralCreativeBrain().run_creative_planning(
        user_input="Create a professional ecommerce product image.",
        optional_template_id="ecommerce_template",
        runtime_metadata=_central_ecommerce_product_truth_metadata(),
    )

    metadata = result.generation_plans[0].metadata

    _assert_central_generation_metadata_preserves_product_truth_scope(metadata)


def test_central_generation_loop_preserves_product_truth_scope_for_provider_materialization() -> None:
    result = CentralCreativeBrain().run_generation_loop(
        user_input="Create a professional ecommerce product image.",
        optional_template_id="ecommerce_template",
        runtime_metadata=_central_ecommerce_product_truth_metadata(),
    )

    metadata = result.generation_plans[0].metadata

    _assert_central_generation_metadata_preserves_product_truth_scope(metadata)


def _central_ecommerce_product_truth_metadata() -> dict[str, object]:
    return {
        "scenario_id": "ecommerce",
        "template_id": "ecommerce_template",
        "requested_image_count": 1,
        "uploaded_assets": [
            {
                "asset_id": "product_a",
                "role": "product_reference",
                "metadata": {"codex_native_reference_channel": "product_truth"},
            },
            {
                "asset_id": "product_b",
                "role": "product_reference",
                "metadata": {"codex_native_reference_channel": "product_truth"},
            },
        ],
        "reference_assets": [],
        "llm_brain": {
            "llm_used": True,
            "fallback_used": False,
            "image_set_plan": {
                "image_count": 1,
                "shot_plan": ["show the product faithfully"],
            },
        },
        "ecommerce_creative_context": {
            "provider_reference_budget": {
                "max_product_truth_source_refs_per_output": 2
            }
        },
        "professional_product_truth_required": True,
        "professional_ecommerce_product_truth_pool_asset_ids": ["product_a", "product_b"],
        "professional_ecommerce_contract_authority": "v3_product_api",
        "professional_ecommerce_product_truth_admission": {
            "schema_version": "doc263_product_truth_admission_v1",
            "canonical_asset_ids": ["product_a", "product_b"],
            "source_binding_digest": "fixture-admission-digest",
        },
        "professional_ecommerce_physical_product_projection": {
            "schema_version": "doc263_physical_product_reference_projection_v1",
            "output_index": 1,
            "selected_product_asset_ids": ["product_a"],
            "projection_digest": "fixture-projection-digest",
        },
        "professional_ecommerce_physical_product_projections": {
            "1": {
                "schema_version": "doc263_physical_product_reference_projection_v1",
                "output_index": 1,
                "selected_product_asset_ids": ["product_a"],
                "projection_digest": "fixture-projection-digest",
            }
        },
    }


def _assert_central_generation_metadata_preserves_product_truth_scope(metadata: dict[str, object]) -> None:
    assert metadata["professional_product_truth_required"] is True
    assert metadata["professional_ecommerce_product_truth_pool_asset_ids"] == [
        "product_a",
        "product_b",
    ]
    assert metadata["ecommerce_creative_context"]["provider_reference_budget"] == {
        "max_product_truth_source_refs_per_output": 2
    }
    assert metadata["professional_ecommerce_contract_authority"] == "v3_product_api"
    assert metadata["professional_ecommerce_product_truth_admission"]["canonical_asset_ids"] == [
        "product_a",
        "product_b",
    ]
    assert metadata["professional_ecommerce_physical_product_projection"][
        "selected_product_asset_ids"
    ] == ["product_a"]
    assert metadata["professional_ecommerce_physical_product_projections"]["1"] == metadata[
        "professional_ecommerce_physical_product_projection"
    ]
