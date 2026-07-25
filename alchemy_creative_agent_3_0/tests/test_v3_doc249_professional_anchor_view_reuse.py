"""Doc249: Professional anchor-view Brain signoff reuse is exact-bound."""

from __future__ import annotations

import base64

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainProfessionalAnchorViewDecisionMissing,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.product_api.contracts import CreateCreativeJobRequest
from alchemy_creative_agent_3_0.app.product_api.service import (
    ProductJobRecord,
    ProductJobStatusValue,
    V3ProductApiService,
)
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import (
    ProfessionalModeRuntimeBridge,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import (
    EcommerceRemoteBrainTestProvider,
)


CAPTURE_SCOPE = "character_card_face_identity"


def _decision() -> dict[str, object]:
    return {
        "contract_version": "v3_professional_anchor_view_decision_v3",
        "target_view_role": "standard_front",
        "capture_presentation": "neutral_identity_evidence_capture",
        "capture_continuity": "establish_neutral_capture",
        "capture_scope": CAPTURE_SCOPE,
        "framing_standard": "consistent_head_and_upper_shoulders_reference_crop",
        "crop_policy": "head_top_margin_full_face_neck_and_upper_shoulders_visible",
        "torso_scope": "visible_neck_collar_and_upper_shoulders",
        "aspect_ratio_standard": "honor_frozen_rendering_size_as_reference_card_aspect_ratio",
        "source_viewpoint_inheritance": "identity_only_do_not_inherit_source_pose_angle",
        "front_pose_normalization": "standard_front_model_card_view",
        "face_axis_alignment": "camera_facing_front_model_card_view",
        "status": "approved",
        "owner": "remote_v3_llm_brain",
    }


def _requirement() -> dict[str, object]:
    return {
        "required": True,
        "frozen_binding": {
            "envelope_id": "envelope_doc249",
            "ledger_id": "ledger_doc249",
        },
        **_decision(),
    }


def _binding(**overrides: object) -> dict[str, object]:
    binding: dict[str, object] = {
        "project_id": "project_doc249",
        "source_asset_id": "v3_asset_doc249",
        "source_sha256": "0" * 64,
        "target_view_role": "standard_front",
        "capture_scope": CAPTURE_SCOPE,
        "reference_semantics": "identity_only_two_derivative_evidence_v1",
        "rendering_contract": "size:1024x1536|quality:strict|reference_card",
        "candidate_contract": "standard_front:candidate:1",
        "operation_context": "visual_asset_doc249:standard_front:1:round1",
    }
    binding.update(overrides)
    return binding


def _reuse_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract_version": "v3_professional_anchor_view_decision_reuse_v1",
        "provenance": "trusted_prior_remote_brain_decision_v1",
        "source_binding": _binding(),
        "current_binding": _binding(),
        "decision": _decision(),
    }
    payload.update(overrides)
    return payload


def _finalizer_request(
    *,
    reuse: dict[str, object] | None = None,
    current_binding: dict[str, object] | None = None,
) -> BrainRunRequest:
    metadata: dict[str, object] = {
        "canonical_prompt_context": {
            "professional_anchor_view_decision": _requirement(),
            "professional_face_identity_quality_contract": {
                "contract_version": "v3_professional_face_identity_quality_contract_v1",
                "owner": "remote_v3_llm_brain",
                "scope": CAPTURE_SCOPE,
            },
            "frozen_binding": {
                "envelope_id": "envelope_doc249",
                "ledger_id": "ledger_doc249",
            },
        }
    }
    if reuse is not None:
        metadata["trusted_professional_anchor_view_decision_reuse"] = reuse
        metadata["professional_anchor_view_decision_current_binding"] = (
            current_binding if current_binding is not None else _binding()
        )
    return BrainRunRequest(
        user_input="Prepare one Character Card Face Identity capture.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        project_id="project_doc249",
        requested_image_count=1,
        metadata=metadata,
    )


class _MissingAnchorDecisionProvider:
    provider = "doc249_missing_anchor_decision"
    model = "fixture"

    def available(self, *, force: bool = False) -> bool:
        return True

    def run(self, request):  # noqa: ANN001
        return {
            "canonical_provider_prompts": [
                {
                    "output_index": 1,
                    "prompt": (
                        "Photographer-shot standard-front model-card portrait on a clean white background; "
                        "same person, complete hair outline, small natural headroom, visible neck, collar "
                        "and upper shoulders, consistent photographer distance, mature commercial photo finish."
                    ),
                    "review_status": "approved",
                }
            ]
        }


def test_doc249_missing_fresh_anchor_decision_still_fails_closed() -> None:
    with pytest.raises(BrainProfessionalAnchorViewDecisionMissing):
        V3LLMBrainAdapter(provider=_MissingAnchorDecisionProvider()).finalize_canonical_provider_prompts(
            _finalizer_request()
        )


def test_doc249_exact_bound_reused_signed_anchor_decision_can_authorize_prompt() -> None:
    prompts, audit = V3LLMBrainAdapter(provider=_MissingAnchorDecisionProvider()).finalize_canonical_provider_prompts(
        _finalizer_request(reuse=_reuse_payload())
    )

    assert prompts[0].professional_anchor_view_decision is not None
    assert prompts[0].professional_anchor_view_decision.target_view_role == "standard_front"
    assert audit["professional_anchor_view_decision_signed"] is True
    assert audit["professional_anchor_view_decision_reuse_applied"] is True
    assert audit["professional_anchor_view_decision_reuse_provenance"] == (
        "trusted_prior_remote_brain_decision_v1"
    )


@pytest.mark.parametrize(
    "payload",
    [
        _reuse_payload(
            source_binding=_binding(source_asset_id="wrong_source"),
        ),
        _reuse_payload(
            current_binding=_binding(target_view_role="profile"),
        ),
        _reuse_payload(
            current_binding=_binding(source_asset_id="wrong_current_source"),
        ),
        _reuse_payload(
            decision={**_decision(), "contract_version": "v3_professional_anchor_view_decision_v2"},
        ),
        _reuse_payload(
            decision={**_decision(), "owner": "local_fixture"},
        ),
        _reuse_payload(
            decision={**_decision(), "status": "pending"},
        ),
        _reuse_payload(
            provenance="user_supplied_metadata",
        ),
    ],
)
def test_doc249_reused_anchor_decision_mismatch_fails_closed(payload: dict[str, object]) -> None:
    with pytest.raises(BrainProfessionalAnchorViewDecisionMissing):
        V3LLMBrainAdapter(provider=_MissingAnchorDecisionProvider()).finalize_canonical_provider_prompts(
            _finalizer_request(reuse=payload)
        )


def test_doc249_self_consistent_reuse_payload_that_does_not_match_current_request_fails_closed() -> None:
    self_consistent_wrong = _reuse_payload(
        source_binding=_binding(source_asset_id="wrong_but_self_consistent"),
        current_binding=_binding(source_asset_id="wrong_but_self_consistent"),
    )

    with pytest.raises(BrainProfessionalAnchorViewDecisionMissing):
        V3LLMBrainAdapter(provider=_MissingAnchorDecisionProvider()).finalize_canonical_provider_prompts(
            _finalizer_request(
                reuse=self_consistent_wrong,
                current_binding=_binding(source_asset_id="v3_asset_doc249"),
            )
        )


class _RuntimeProviderMissingAnchorDecision(EcommerceRemoteBrainTestProvider):
    def __init__(self) -> None:
        super().__init__()
        self.finalizer_metadata: list[dict[str, object]] = []

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage == "provider_prompt_finalize":
            self.finalizer_metadata.append(dict(request.metadata or {}))
            for item in payload.get("canonical_provider_prompts", []):
                item.pop("professional_anchor_view_decision", None)
        return payload


def _runtime_request(tmp_path, *, trusted: bool) -> dict[str, object]:
    source = tmp_path / "identity-root.png"
    Image.new("RGB", (640, 640), (170, 135, 120)).save(source)
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role="standard_front",
        capture_scope=CAPTURE_SCOPE,
    )
    return {
        "user_input": "Prepare one Character Card Face Identity capture.",
        "scenario_selection": {"scenario_id": "general_creative"},
        "uploaded_assets": [
            {
                "asset_id": "v3_asset_doc249",
                "role": "face_reference",
                "file_path": str(source),
                "use_policy": "identity",
                "strength": "hard",
            }
        ],
        "metadata": {
            "project_id": "project_doc249",
            "requested_image_count": 1,
            "require_real_images": True,
            "professional_mode": True,
            "professional_anchor_pack_preparation": True,
            "professional_planning_metadata": planning,
            "trusted_professional_anchor_view_decision_reuse": _reuse_payload(),
        },
        **({"trusted_professional_anchor_view_decision_reuse": True} if trusted else {}),
    }


def test_doc249_user_metadata_reuse_is_not_forwarded_without_trusted_runtime_flag(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _RuntimeProviderMissingAnchorDecision()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))

    result = runtime.plan_job(_runtime_request(tmp_path, trusted=False))

    assert result.status.value == "blocked"
    assert "capability_activation_failed: professional_anchor_view_decision_missing" in result.warnings
    assert provider.finalizer_metadata
    assert all(
        "trusted_professional_anchor_view_decision_reuse" not in item
        for item in provider.finalizer_metadata
    )


def test_doc249_top_level_runtime_reuse_flag_is_rejected(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _RuntimeProviderMissingAnchorDecision()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))

    with pytest.raises(ValueError, match="internal runtime flag"):
        runtime.plan_job(_runtime_request(tmp_path, trusted=True))


def test_doc249_internal_runtime_request_forwards_current_binding_to_brain(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _RuntimeProviderMissingAnchorDecision()
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))
    request = ScenarioRuntimeRequest.model_validate(_runtime_request(tmp_path, trusted=False))
    reuse = _reuse_payload()
    request.metadata = {
        **dict(request.metadata),
        "trusted_professional_anchor_view_decision_reuse": reuse,
        "professional_anchor_view_decision_current_binding": reuse["current_binding"],
    }
    request = request.model_copy(
        update={"trusted_professional_anchor_view_decision_reuse": True}
    )

    result = runtime.plan_job(request)

    assert result.status.value == "planned"
    assert provider.finalizer_metadata
    assert provider.finalizer_metadata[-1]["trusted_professional_anchor_view_decision_reuse"][
        "current_binding"
    ] == provider.finalizer_metadata[-1][
        "professional_anchor_view_decision_current_binding"
    ]


def _png_b64() -> str:
    import io

    buffer = io.BytesIO()
    Image.new("RGB", (24, 24), (170, 135, 120)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _ready_asset(service: V3ProductApiService, *, role: str = "face_reference") -> str:
    record = service.create_uploaded_asset(
        {
            "filename": "identity.png",
            "mime_type": "image/png",
            "size_bytes": 100,
            "role": role,
        }
    )
    service.store_uploaded_asset_content(
        record.asset_id,
        {"content_base64": _png_b64(), "mime_type": "image/png"},
    )
    service.complete_uploaded_asset(record.asset_id)
    return record.asset_id


def _source_record(
    service: V3ProductApiService,
    *,
    root_asset_id: str,
    supplement_asset_id: str,
    project_id: str = "project_doc249",
    view_role: str = "standard_front",
    operation_id: str = "visual_asset_doc249:standard_front:1:round1",
) -> ProductJobRecord:
    planning = ProfessionalModeRuntimeBridge.anchor_pack_preparation_metadata(
        view_role=view_role,  # type: ignore[arg-type]
        capture_scope=CAPTURE_SCOPE,
    )
    request = CreateCreativeJobRequest.model_validate(
        {
            "user_input": "Prepare one Character Card Face Identity capture.",
            "uploaded_asset_ids": [root_asset_id, supplement_asset_id],
            "metadata": {
                "project_id": project_id,
                "professional_mode": True,
                "professional_anchor_pack_preparation": True,
                "professional_planning_metadata": planning,
                "professional_reference_stage": view_role,
                "professional_anchor_capture_scope": CAPTURE_SCOPE,
                "professional_anchor_candidate_index": 1,
                "requested_image_size": "1024x1536",
                "quality_mode": "strict",
                "generation_channel": "mcp",
                "mcp_operation_id": operation_id,
                "frozen_remote_creative_brain": {
                    "brain_result": {
                        "llm_used": True,
                        "fallback_used": False,
                        "audit": {
                            "professional_anchor_view_decisions": [_decision()],
                        },
                    }
                },
            },
        }
    )
    record = ProductJobRecord(
        request=request,
        status=ProductJobStatusValue.PLANNED,
        job_id_value="job_doc249_source",
    )
    service.job_store.save(record)
    return record


def test_doc249_product_api_trusted_host_builds_reuse_binding_for_same_job(tmp_path) -> None:
    service = V3ProductApiService()
    service.asset_store.storage_root = tmp_path / "uploads"
    root = _ready_asset(service)
    supplement = _ready_asset(service)
    source = _source_record(service, root_asset_id=root, supplement_asset_id=supplement)
    request = CreateCreativeJobRequest.model_validate(
        {
            "user_input": source.request.user_input,
            "uploaded_asset_ids": [root, supplement],
            "metadata": {
                "project_id": "project_doc249",
                "professional_anchor_candidate_index": 1,
                "requested_image_size": "1024x1536",
                "quality_mode": "strict",
            },
        }
    )

    payload = service._professional_anchor_view_decision_reuse_payload(  # noqa: SLF001
        request,
        source=source,
        view_role="standard_front",
        capture_scope=CAPTURE_SCOPE,
        reference_evidence_ids=[root, supplement],
        mcp_operation_id="visual_asset_doc249:standard_front:1:round1",
    )
    request.metadata = {
        **dict(request.metadata),
        "trusted_professional_anchor_view_decision_reuse": payload,
        "professional_anchor_view_decision_current_binding": payload["current_binding"],
    }

    runtime_request = service._runtime_request_payload(request)  # noqa: SLF001

    assert not isinstance(runtime_request, dict)
    assert runtime_request.trusted_professional_anchor_view_decision_reuse is True
    assert runtime_request.metadata["trusted_professional_anchor_view_decision_reuse"][
        "source_binding"
    ] == runtime_request.metadata["trusted_professional_anchor_view_decision_reuse"][
        "current_binding"
    ]


def test_doc249_provider_stage_plan_continuation_does_not_invoke_mcp_decision_reuse(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    provider = EcommerceRemoteBrainTestProvider()
    service = V3ProductApiService(
        scenario_runtime=ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))
    )
    service.asset_store.storage_root = tmp_path / "uploads"
    root = _ready_asset(service)
    first = service.create_professional_anchor_preparation_job(
        {
            "user_input": "Prepare one straight-on Face Identity anchor of this same person.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_asset_ids": [root],
            "metadata": {
                "project_id": "project_doc249_provider_continuation",
                "requested_image_count": 1,
                "require_real_images": True,
            },
        },
        view_role="standard_front",
    )
    assert first.status == ProductJobStatusValue.PLANNED

    def _unexpected_doc249_reuse(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Provider continuation must not invoke Doc249 MCP reuse")

    monkeypatch.setattr(
        service,
        "_professional_anchor_view_decision_reuse_payload",
        _unexpected_doc249_reuse,
    )

    second = service.create_professional_anchor_preparation_job(
        {
            "user_input": "Prepare one straight-on Face Identity anchor of this same person.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_asset_ids": [root],
            "metadata": {
                "project_id": "project_doc249_provider_continuation",
                "requested_image_count": 1,
                "require_real_images": True,
            },
        },
        view_role="standard_front",
        reference_evidence_ids=[root],
        stage_plan_source_job_id=first.job_id,
    )

    assert second.status == ProductJobStatusValue.PLANNED


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", "wrong_project"),
        ("source_asset_id", "wrong_asset"),
        ("target_view_role", "profile"),
        ("capture_scope", "anchor_pack"),
        ("reference_semantics", "identity_only_single_root_reference_v1"),
        ("rendering_contract", "other_rendering"),
        ("candidate_contract", "standard_front:candidate:2"),
        ("candidate_contract", ""),
        ("operation_context", "wrong_operation"),
        ("operation_context", ""),
    ],
)
def test_doc249_product_api_reuse_binding_mismatch_fails_closed(tmp_path, field: str, value: str) -> None:
    service = V3ProductApiService()
    service.asset_store.storage_root = tmp_path / "uploads"
    root = _ready_asset(service)
    supplement = _ready_asset(service)
    source = _source_record(service, root_asset_id=root, supplement_asset_id=supplement)
    request = CreateCreativeJobRequest.model_validate(
        {
            "user_input": source.request.user_input,
            "uploaded_asset_ids": [root, supplement],
            "metadata": {
                "project_id": "project_doc249",
                "professional_anchor_candidate_index": 1,
                "requested_image_size": "1024x1536",
                "quality_mode": "strict",
            },
        }
    )
    kwargs = {
        "view_role": "standard_front",
        "capture_scope": CAPTURE_SCOPE,
        "reference_evidence_ids": [root, supplement],
        "mcp_operation_id": "visual_asset_doc249:standard_front:1:round1",
    }
    if field == "project_id":
        request.metadata["project_id"] = value
    elif field == "source_asset_id":
        other = _ready_asset(service)
        request.uploaded_asset_ids = [other, supplement]
        kwargs["reference_evidence_ids"] = [other, supplement]
    elif field == "target_view_role":
        kwargs["view_role"] = value
    elif field == "capture_scope":
        kwargs["capture_scope"] = value
    elif field == "reference_semantics":
        kwargs["reference_evidence_ids"] = [root]
    elif field == "candidate_contract":
        if value:
            request.metadata["professional_anchor_candidate_index"] = 2
        else:
            request.metadata.pop("professional_anchor_candidate_index", None)
    elif field == "operation_context":
        kwargs["mcp_operation_id"] = value
    elif field == "rendering_contract":
        request.metadata["professional_anchor_rendering_contract"] = value

    with pytest.raises(ValueError, match="professional_anchor_view_decision_reuse"):
        service._professional_anchor_view_decision_reuse_payload(  # noqa: SLF001
            request,
            source=source,
            **kwargs,
        )


@pytest.mark.parametrize(
    "decisions",
    [
        [],
        [_decision(), _decision()],
        [{**_decision(), "contract_version": "v3_professional_anchor_view_decision_v2"}],
        [{**_decision(), "status": "pending"}],
        [{**_decision(), "owner": "local_fixture"}],
    ],
)
def test_doc249_product_api_accepts_only_one_signed_v3_source_decision(
    tmp_path,
    decisions: list[dict[str, object]],
) -> None:
    service = V3ProductApiService()
    service.asset_store.storage_root = tmp_path / "uploads"
    root = _ready_asset(service)
    supplement = _ready_asset(service)
    source = _source_record(service, root_asset_id=root, supplement_asset_id=supplement)
    metadata = dict(source.request.metadata)
    frozen = dict(metadata["frozen_remote_creative_brain"])
    brain = dict(frozen["brain_result"])
    audit = dict(brain["audit"])
    audit["professional_anchor_view_decisions"] = decisions
    brain["audit"] = audit
    frozen["brain_result"] = brain
    source.request.metadata = {**metadata, "frozen_remote_creative_brain": frozen}
    request = CreateCreativeJobRequest.model_validate(
        {
            "user_input": source.request.user_input,
            "uploaded_asset_ids": [root, supplement],
            "metadata": {
                "project_id": "project_doc249",
                "professional_anchor_candidate_index": 1,
                "requested_image_size": "1024x1536",
                "quality_mode": "strict",
            },
        }
    )

    assert (
        service._professional_anchor_view_decision_reuse_payload(  # noqa: SLF001
            request,
            source=source,
            view_role="standard_front",
            capture_scope=CAPTURE_SCOPE,
            reference_evidence_ids=[root, supplement],
            mcp_operation_id="visual_asset_doc249:standard_front:1:round1",
        )
        == {}
    )
