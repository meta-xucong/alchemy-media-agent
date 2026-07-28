"""Doc134: cross-module Professional body-proportion projection regressions.

These tests prove the runtime body reference path is not an E-Commerce-only
special case.  The Remote Brain test doubles below emit explicit typed
per-output body receipts; no fixture infers body applicability from prompt
text, filenames, or public MCP reference metadata.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from alchemy_creative_agent_3_0.app.generation_router.providers import (
    ProviderPromptMaterialization,
)
from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.visual_assets import (
    PersistentVisualAssetLibraryCatalog,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import (
    EcommerceRemoteBrainTestProvider,
)
from alchemy_creative_agent_3_0.tests.photography_test_support import (
    PhotographyRemoteBrainTestProvider,
)
from services.alchemy_codex_local_adapter.contracts import (
    NativeProfessionalImageGenPlanRequest,
)
from services.alchemy_codex_local_adapter.native_planner import (
    CodexNativeImageGenPlanner,
)
from services.alchemy_codex_local_adapter.professional_binding import (
    visual_asset_library_professional_binding_resolver,
)
from tests.test_doc134_codex_native_professional_relay import (
    _CapturingRuntime,
    _arguments,
    _library_with_active_front,
    _sha256,
    _write_png,
    _write_root_upload_evidence,
)


def _receipt_entry(index: int, requirement: str, view_kind: str | None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "output_index": index,
        "evidence_dimensions": [],
        "professional_body_proportion_requirement": requirement,
    }
    if view_kind is not None:
        entry["professional_body_view_kind"] = view_kind
    return entry


def _apply_body_receipts(
    payload: dict[str, Any],
    *,
    count: int,
    requirement_by_index: dict[int, str],
    view_by_index: dict[int, str | None],
) -> dict[str, Any]:
    image_set_plan = payload.get("image_set_plan")
    if not isinstance(image_set_plan, dict):
        return payload
    entries = image_set_plan.get("evidence_dimensions_by_output")
    if not isinstance(entries, list):
        entries = [_receipt_entry(index, "not_required", None) for index in range(1, count + 1)]
        image_set_plan["evidence_dimensions_by_output"] = entries
    for index in range(1, count + 1):
        entry = entries[index - 1]
        requirement = requirement_by_index.get(index, "not_required")
        view_kind = view_by_index.get(index)
        if isinstance(entry, dict):
            entry["professional_body_proportion_requirement"] = requirement
            if requirement == "not_required":
                entry.pop("professional_body_view_kind", None)
            else:
                entry["professional_body_view_kind"] = view_kind or "front_full"
    return payload


class _BodyReceiptEcommerceProvider(EcommerceRemoteBrainTestProvider):
    def __init__(
        self,
        *,
        requirement_by_index: dict[int, str] | None = None,
        view_by_index: dict[int, str | None] | None = None,
    ) -> None:
        super().__init__()
        self.requirement_by_index = dict(requirement_by_index or {})
        self.view_by_index = dict(view_by_index or {})

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        return _apply_body_receipts(
            payload,
            count=request.requested_image_count,
            requirement_by_index=self.requirement_by_index,
            view_by_index=self.view_by_index,
        )


class _BodyReceiptPhotographyProvider(PhotographyRemoteBrainTestProvider):
    def __init__(
        self,
        *,
        requirement_by_index: dict[int, str] | None = None,
        view_by_index: dict[int, str | None] | None = None,
    ) -> None:
        super().__init__()
        self.requirement_by_index = dict(requirement_by_index or {})
        self.view_by_index = dict(view_by_index or {})

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        return _apply_body_receipts(
            payload,
            count=request.requested_image_count,
            requirement_by_index=self.requirement_by_index,
            view_by_index=self.view_by_index,
        )


def _capture_materializations(monkeypatch: pytest.MonkeyPatch) -> list[list[dict[str, Any]]]:
    captured: list[list[dict[str, Any]]] = []
    original = CodexNativeImageGenPlanner._canonical_materializations

    def capture(planning_result, *, metadata_overrides=None, metadata_overrides_by_asset_id=None):  # noqa: ANN001
        materializations = original(
            planning_result,
            metadata_overrides=metadata_overrides,
            metadata_overrides_by_asset_id=metadata_overrides_by_asset_id,
        )
        captured.extend([list(item.reference_assets) for item in materializations])
        return materializations

    monkeypatch.setattr(
        CodexNativeImageGenPlanner,
        "_canonical_materializations",
        staticmethod(capture),
    )
    return captured


def _professional_planner(
    *,
    library_root: Path,
    provider: Any,
) -> CodexNativeImageGenPlanner:
    runtime = _CapturingRuntime(
        ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)),
    )
    return CodexNativeImageGenPlanner(
        runtime_factory=lambda: runtime,
        professional_binding_resolver=visual_asset_library_professional_binding_resolver(library_root),
    )


def _body_truth_refs(materialized_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in materialized_refs
        if str(item.get("reference_truth_layer") or "") == "body_proportion_truth"
    ]


def _trusted_professional_body_metadata() -> dict[str, Any]:
    return {
        "require_real_images": True,
        "professional_body_proportion_receipt_required": True,
        "professional_mode": "professional",
        "local_mcp_professional_relay": True,
        "professional_body_proportion_contract_source": "server_owned_professional_binding_resolver",
        "professional_mode_binding_record": {
            "server_owned_binding_resolver_validated": True,
        },
    }


def _remote_payload_for_body_metadata(
    metadata: dict[str, Any],
    *,
    scenario_id: str = "general_creative",
    template_id: str = "general_template",
) -> dict[str, Any]:
    return json.loads(
        build_remote_payload(
            BrainRunRequest(
                user_input="Create one Professional visible-body human image.",
                stage="plan",
                scenario_id=scenario_id,
                template_id=template_id,
                requested_image_count=1,
                metadata=dict(metadata),
            )
        )
    )


def _payload_contains_body_receipt_schema(payload: dict[str, Any]) -> bool:
    serialized = json.dumps(payload.get("return_schema", {}), ensure_ascii=False)
    return (
        "professional_body_proportion_requirement" in serialized
        or "professional_body_view_kind" in serialized
    )


@pytest.mark.parametrize(
    ("scenario_id", "template_id"),
    [
        ("general_creative", "general_template"),
        ("photography", "photographer_template"),
        ("ecommerce", "ecommerce_template"),
    ],
)
def test_direct_remote_payload_rejects_lone_professional_body_receipt_boolean(
    scenario_id: str,
    template_id: str,
) -> None:
    payload = _remote_payload_for_body_metadata(
        {
            "require_real_images": True,
            "professional_body_proportion_receipt_required": True,
        },
        scenario_id=scenario_id,
        template_id=template_id,
    )

    assert not _payload_contains_body_receipt_schema(payload)


@pytest.mark.parametrize(
    "metadata",
    [
        {
            **_trusted_professional_body_metadata(),
            "professional_mode": "standard",
        },
        {
            **_trusted_professional_body_metadata(),
            "local_mcp_professional_relay": False,
        },
        {
            **_trusted_professional_body_metadata(),
            "professional_body_proportion_contract_source": "public_metadata",
        },
        {
            **_trusted_professional_body_metadata(),
            "professional_mode_binding_record": None,
        },
        {
            "require_real_images": True,
            "professional_body_proportion_receipt_required": True,
            "professional_body_proportion_server_context": {
                "professional_mode": "standard",
                "local_mcp_professional_relay": True,
                "professional_body_proportion_contract_source": "server_owned_professional_binding_resolver",
                "professional_mode_binding_record": {
                    "server_owned_binding_resolver_validated": True,
                },
            },
        },
    ],
)
def test_direct_remote_payload_body_receipt_schema_requires_trusted_professional_context(
    metadata: dict[str, Any],
) -> None:
    payload = _remote_payload_for_body_metadata(metadata)

    assert not _payload_contains_body_receipt_schema(payload)


@pytest.mark.parametrize(
    "metadata",
    [
        _trusted_professional_body_metadata(),
        {
            "require_real_images": True,
            "professional_body_proportion_receipt_required": True,
            "professional_body_proportion_server_context": {
                "professional_mode": "professional",
                "local_mcp_professional_relay": True,
                "professional_body_proportion_contract_source": "server_owned_professional_binding_resolver",
                "professional_mode_binding_record": {
                    "server_owned_binding_resolver_validated": True,
                },
            },
        },
    ],
)
def test_direct_remote_payload_accepts_only_server_owned_body_receipt_context(
    metadata: dict[str, Any],
) -> None:
    payload = _remote_payload_for_body_metadata(
        metadata,
        scenario_id="photography",
        template_id="photographer_template",
    )
    evidence_schema = payload["return_schema"]["image_set_plan"]["evidence_dimensions_by_output"][0]

    assert evidence_schema["professional_body_proportion_requirement"].startswith(
        "closed Professional body receipt"
    )
    assert "front_full|side_full|rear_full" in evidence_schema["professional_body_view_kind"]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "server_owned_binding_resolver_validated" not in serialized


def _assert_single_body_only_projection(
    *,
    result: dict[str, Any],
    materialized_refs: list[dict[str, Any]],
    body_source_id: str,
    body_path: Path,
    view_kind: str = "front_full",
) -> None:
    contract = result["outputs"][0]["reference_input_contract"]
    body_refs = _body_truth_refs(materialized_refs)
    assert contract["professional_body_proportion_requirement"] in {
        "visible_body_required",
        "full_body_required",
    }
    assert contract["professional_body_view_kind"] == view_kind
    assert contract["professional_body_source_asset_id"] == body_source_id
    admitted_sources = contract["admitted_reference_source_asset_ids"]
    assert body_source_id in admitted_sources
    assert contract["declared_reference_count"] == len(admitted_sources)
    assert contract["admitted_body_proportion_source_asset_ids"] == [body_source_id]
    assert contract["admitted_body_proportion_derivative_asset_ids"] == [
        f"{body_source_id}::body_proportion_reference"
    ]
    assert len(body_refs) == 1
    body_ref = body_refs[0]
    assert body_ref["asset_id"] == f"{body_source_id}::body_proportion_reference"
    assert body_ref["source_asset_id"] == body_source_id
    assert body_ref["role"] == "body_proportion_reference"
    assert body_ref["body_view_kind"] == view_kind
    assert body_ref["provider_reference_derivative"] is True
    assert body_ref["body_reference_policy"] == (
        "body_scale_neck_shoulder_torso_limb_developmental_stage_only"
    )
    assert set(body_ref["forbidden_inheritance_channels"]) >= {
        "wardrobe",
        "pose",
        "lighting",
        "camera",
        "background",
        "expression",
        "scene",
        "product_identity",
    }
    assert [item.get("file_path") for item in materialized_refs].count(str(body_path)) == 1
    assert len(materialized_refs) <= 5
    serialized = json.dumps(materialized_refs).lower()
    assert "provider_payload" not in serialized
    assert "prompt_fragment" not in serialized


@pytest.mark.parametrize(
    ("template_id", "provider_factory", "extra_args"),
    [
        ("general_template", _BodyReceiptEcommerceProvider, {}),
        (
            "photographer_template",
            _BodyReceiptPhotographyProvider,
            {
                "platform_profile": None,
                "photography_mode": "single_hero",
                "photographer_profile_id": "general_photography",
            },
        ),
    ],
)
def test_professional_general_and_photography_visible_body_admit_body_only_truth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    template_id: str,
    provider_factory: Any,
    extra_args: dict[str, Any],
) -> None:
    if template_id == "photographer_template":
        monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    root_source_id = "v3_asset_root"
    face_output_id = "v3_output_front"
    body_output_id = "v3_output_body_front_full"
    _write_root_upload_evidence(tmp_path, root_source_id=root_source_id)
    asset, library_root = _library_with_active_front(
        tmp_path,
        root_source_id=root_source_id,
        output_id=face_output_id,
        include_body=True,
        body_output_id=body_output_id,
    )
    captured = _capture_materializations(monkeypatch)
    provider = provider_factory(
        requirement_by_index={1: "visible_body_required"},
        view_by_index={1: "front_full"},
    )
    planner = _professional_planner(library_root=library_root, provider=provider)
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            tmp_path / "unused.png",
            template_id=template_id,
            reference_inputs=[],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
            user_input="Create one Professional visible-human image.",
            **extra_args,
        )
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert captured
    _assert_single_body_only_projection(
        result=result,
        materialized_refs=captured[0],
        body_source_id=body_output_id,
        body_path=library_root.parent / "v3_outputs" / body_output_id / "original.png",
    )
    assert result["outputs"][0]["reference_input_contract"]["source_sha256"][-1] == _sha256(
        library_root.parent / "v3_outputs" / body_output_id / "original.png"
    )


def test_professional_ecommerce_visible_body_admits_body_product_and_identity_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_source_id = "v3_asset_root"
    face_output_id = "v3_output_front"
    body_output_id = "v3_output_body_front_full"
    _write_root_upload_evidence(tmp_path, root_source_id=root_source_id)
    asset, library_root = _library_with_active_front(
        tmp_path,
        root_source_id=root_source_id,
        output_id=face_output_id,
        include_body=True,
        body_output_id=body_output_id,
    )
    product = _write_png(tmp_path / "product.png", color=(80, 145, 210))
    captured = _capture_materializations(monkeypatch)
    provider = _BodyReceiptEcommerceProvider(
        requirement_by_index={1: "visible_body_required"},
        view_by_index={1: "front_full"},
    )
    planner = _professional_planner(library_root=library_root, provider=provider)
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            product,
            template_id="ecommerce_template",
            platform_profile="generic",
            reference_inputs=[{"channel": "product_truth", "file_path": str(product)}],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
            user_input="Create one Professional product-on-person visible-body image.",
        )
    )
    product_id = request.reference_inputs[0].asset_id

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert captured
    _assert_single_body_only_projection(
        result=result,
        materialized_refs=captured[0],
        body_source_id=body_output_id,
        body_path=library_root.parent / "v3_outputs" / body_output_id / "original.png",
    )
    contract = result["outputs"][0]["reference_input_contract"]
    assert contract["selected_product_truth_asset_ids"] == [product_id]
    assert contract["admitted_product_truth_asset_ids"] == [product_id]
    source_ids = [
        str(item.get("source_asset_id") or item.get("asset_id") or "")
        for item in captured[0]
    ]
    assert source_ids.count(root_source_id) == 1
    assert source_ids.count(face_output_id) == 1
    assert source_ids.count(product_id) == 1
    assert source_ids.count(body_output_id) == 1


@pytest.mark.parametrize(
    ("template_id", "provider_factory", "extra_args"),
    [
        ("general_template", _BodyReceiptEcommerceProvider, {}),
        (
            "photographer_template",
            _BodyReceiptPhotographyProvider,
            {
                "platform_profile": None,
                "photography_mode": "single_hero",
                "photographer_profile_id": "general_photography",
            },
        ),
        (
            "ecommerce_template",
            _BodyReceiptEcommerceProvider,
            {"platform_profile": "generic"},
        ),
    ],
)
def test_professional_not_required_outputs_do_not_leak_body_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    template_id: str,
    provider_factory: Any,
    extra_args: dict[str, Any],
) -> None:
    if template_id == "photographer_template":
        monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    root_source_id = "v3_asset_root"
    face_output_id = "v3_output_front"
    body_output_id = "v3_output_body_front_full"
    _write_root_upload_evidence(tmp_path, root_source_id=root_source_id)
    asset, library_root = _library_with_active_front(
        tmp_path,
        root_source_id=root_source_id,
        output_id=face_output_id,
        include_body=True,
        body_output_id=body_output_id,
    )
    reference_inputs: list[dict[str, str]] = []
    reference_path = tmp_path / "unused.png"
    if template_id == "ecommerce_template":
        product = _write_png(tmp_path / "product.png", color=(80, 145, 210))
        reference_path = product
        reference_inputs = [{"channel": "product_truth", "file_path": str(product)}]
    captured = _capture_materializations(monkeypatch)
    provider = provider_factory(
        requirement_by_index={1: "not_required"},
        view_by_index={1: None},
    )
    planner = _professional_planner(library_root=library_root, provider=provider)
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            reference_path,
            template_id=template_id,
            reference_inputs=reference_inputs,
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
            user_input="Create one Professional face-only or non-body image.",
            **extra_args,
        )
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "planned_for_codex_native_imagegen"
    contract = result["outputs"][0]["reference_input_contract"]
    assert contract["professional_body_proportion_requirement"] == "not_required"
    assert contract["professional_body_view_kind"] is None
    assert contract["professional_body_source_asset_id"] is None
    assert contract["admitted_body_proportion_source_asset_ids"] == []
    assert captured
    assert _body_truth_refs(captured[0]) == []
    admitted_sources = contract["admitted_reference_source_asset_ids"]
    assert contract["declared_reference_count"] == len(admitted_sources)
    assert body_output_id not in admitted_sources


@pytest.mark.parametrize(
    ("template_id", "provider_factory", "extra_args"),
    [
        ("general_template", _BodyReceiptEcommerceProvider, {}),
        (
            "photographer_template",
            _BodyReceiptPhotographyProvider,
            {
                "platform_profile": None,
                "photography_mode": "single_hero",
                "photographer_profile_id": "general_photography",
            },
        ),
        (
            "ecommerce_template",
            _BodyReceiptEcommerceProvider,
            {"platform_profile": "generic"},
        ),
    ],
)
def test_professional_visible_body_blocks_when_exact_body_slot_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    template_id: str,
    provider_factory: Any,
    extra_args: dict[str, Any],
) -> None:
    if template_id == "photographer_template":
        monkeypatch.setenv("V3_PHOTOGRAPHY_PRODUCTION_ENABLED", "true")
    root_source_id = "v3_asset_root"
    face_output_id = "v3_output_front"
    _write_root_upload_evidence(tmp_path, root_source_id=root_source_id)
    asset, library_root = _library_with_active_front(
        tmp_path,
        root_source_id=root_source_id,
        output_id=face_output_id,
        include_body=False,
    )
    reference_inputs: list[dict[str, str]] = []
    reference_path = tmp_path / "unused.png"
    if template_id == "ecommerce_template":
        product = _write_png(tmp_path / "product.png", color=(80, 145, 210))
        reference_path = product
        reference_inputs = [{"channel": "product_truth", "file_path": str(product)}]
    materializer_calls = 0

    def fail_if_materialized(*_args, **_kwargs):  # noqa: ANN002, ANN003
        nonlocal materializer_calls
        materializer_calls += 1
        raise AssertionError("missing Body Silhouette must block before materialization")

    monkeypatch.setattr(
        CodexNativeImageGenPlanner,
        "_canonical_materializations",
        staticmethod(fail_if_materialized),
    )
    provider = provider_factory(
        requirement_by_index={1: "visible_body_required"},
        view_by_index={1: "front_full"},
    )
    planner = _professional_planner(library_root=library_root, provider=provider)
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            reference_path,
            template_id=template_id,
            reference_inputs=reference_inputs,
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
            user_input="Create one Professional visible-human image.",
            **extra_args,
        )
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "blocked"
    assert result["code"] == "codex_native_imagegen_professional_body_reference_missing"
    assert materializer_calls == 0


@pytest.mark.parametrize(
    "invalid_body_slot_case",
    [
        "missing_slot",
        "inactive",
        "review_unverified",
        "parity_unverified",
        "receipt_missing",
        "output_hash_mismatch",
    ],
)
def test_professional_body_required_blocks_for_invalid_active_body_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_body_slot_case: str,
) -> None:
    root_source_id = "v3_asset_root"
    face_output_id = "v3_output_front"
    body_output_id = "v3_output_body_front_full"
    _write_root_upload_evidence(tmp_path, root_source_id=root_source_id)
    asset, library_root = _library_with_active_front(
        tmp_path,
        root_source_id=root_source_id,
        output_id=face_output_id,
        include_body=invalid_body_slot_case != "missing_slot",
        body_output_id=body_output_id,
    )
    if invalid_body_slot_case != "missing_slot":
        catalog = PersistentVisualAssetLibraryCatalog(library_root)
        saved = catalog.get(owner_scope="local_default", visual_asset_id=asset.visual_asset_id)
        assert saved is not None
        card = saved.character_card
        slots = dict(card.body_slots)
        slot = slots["body.front_full"]
        if invalid_body_slot_case == "inactive":
            slots["body.front_full"] = slot.model_copy(update={"state": "blocked"})
        elif invalid_body_slot_case == "review_unverified":
            # Active Body Silhouette slots cannot be review_unverified by the
            # Character Card model itself; this valid intermediate state must
            # remain readable while being ineligible as runtime body truth.
            slots["body.front_full"] = slot.model_copy(
                update={"state": "reviewing", "review_verified": False}
            )
        elif invalid_body_slot_case == "parity_unverified":
            slots["body.front_full"] = slot.model_copy(
                update={"state": "reviewing", "prompt_reference_parity_verified": False}
            )
        elif invalid_body_slot_case == "receipt_missing":
            slots["body.front_full"] = slot.model_copy(update={"formal_slot_receipt": None})
        elif invalid_body_slot_case == "output_hash_mismatch":
            output_json = library_root.parent / "v3_outputs" / body_output_id / "output.json"
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            payload["metadata"]["output_sha256"] = "0" * 64
            output_json.write_text(json.dumps(payload), encoding="utf-8")
        if invalid_body_slot_case != "output_hash_mismatch":
            updated = saved.model_copy(
                update={"character_card": card.model_copy(update={"body_slots": slots})}
            )
            catalog.save(updated)

    resolver = visual_asset_library_professional_binding_resolver(library_root)
    resolved = resolver(
        project_id="project_professional",
        people_asset_id=asset.visual_asset_id,
        job_id="job_professional_invalid_body",
        reference_view_ids=["face_front"],
    )
    assert resolved is not None
    assert resolved.body_references == ()
    materializer_calls = 0

    def fail_if_materialized(*_args, **_kwargs):  # noqa: ANN002, ANN003
        nonlocal materializer_calls
        materializer_calls += 1
        raise AssertionError("invalid Body Silhouette must block before materialization")

    monkeypatch.setattr(
        CodexNativeImageGenPlanner,
        "_canonical_materializations",
        staticmethod(fail_if_materialized),
    )
    planner = _professional_planner(
        library_root=library_root,
        provider=_BodyReceiptEcommerceProvider(
            requirement_by_index={1: "visible_body_required"},
            view_by_index={1: "front_full"},
        ),
    )
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(
        _arguments(
            tmp_path / "unused.png",
            template_id="general_template",
            reference_inputs=[],
            people_asset_id=asset.visual_asset_id,
            professional_identity_view_ids=["face_front"],
            user_input="Create one Professional visible-body image.",
        )
    )

    result = planner.prepare_frozen_professional_native_imagegen_plan(request)

    assert result["status"] == "blocked"
    assert result["code"] == "codex_native_imagegen_professional_body_reference_missing"
    assert materializer_calls == 0
