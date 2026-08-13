"""Phase 2 red contracts for Doc270's server-only shadow matcher.

The fixtures use only in-memory Project Mode/upload records and an injected
image-evidence callback.  They do not create a job, select a Provider, call
MCP/ImageGen, or change an existing projection.  Phase 2 is deliberately
red: the resolver seam does not exist until the separately audited runtime
milestone implements it.
"""

from __future__ import annotations

from copy import deepcopy
import inspect
from typing import Any

import pytest

from alchemy_creative_agent_3_0.app.project_mode import source_library
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    ProjectReferenceSourceType,
    ProjectReferenceStatus,
    ProjectReferenceUsePolicy,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _handlers,
    _project,
    _ready_product_upload,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import (
    _add_product_references,
)


def _project_library(tmp_path, *, template_id: str = "general_template") -> tuple[Any, dict[str, Any], dict[str, Any], list[str]]:
    handlers, _catalog = _handlers(tmp_path)
    if template_id == "ecommerce_template":
        project = _project(handlers)
    else:
        project = handlers.post_projects(
            {
                "user_goal": "Create an ordinary source-supported scene.",
                "primary_template_id": template_id,
            }
        )["project"]
    asset_ids = [
        _ready_product_upload(
            handlers,
            filename=f"phase2-original-{index}.png",
            color=(30 + index * 30, 80 + index * 20, 130 + index * 10),
        )
        for index in range(1, 5)
    ]
    if template_id == "ecommerce_template":
        _add_product_references(handlers, project["project_id"], asset_ids)
    else:
        for asset_id in asset_ids:
            handlers.post_project_reference(
                project["project_id"],
                {"asset_ref_id": asset_id, "source_type": "uploaded", "use_policy": "general"},
            )
    current = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    snapshot = source_library.build_project_source_library(
        project_id=current.project_id,
        references=current.reference_assets,
        upload_lookup=handlers.service.get_uploaded_asset,
    )
    return handlers, project, snapshot, asset_ids


def _entry(snapshot: dict[str, Any], asset_id: str) -> dict[str, Any]:
    return next(item for item in snapshot["entries"] if item["asset_id"] == asset_id)


def _requirement(
    *,
    project_id: str,
    output_index: int,
    kind: str,
    source_snapshot_digest: str,
    strength: str = "hard",
    maximum_sources: int = 1,
) -> dict[str, Any]:
    requirement = {
        "schema_version": "doc270_reference_requirement_v1",
        "issuer": {
            "authority": "v3_server_template_requirement_issuer",
            "schema_version": "doc270_requirement_issuer_v1",
            "version": "doc270_phase2_contract_fixture_v1",
        },
        "project_id": project_id,
        "command_plan_binding": {
            "command_id": f"server-command-{project_id}",
            "plan_id": f"server-plan-{project_id}",
            "plan_version": 1,
        },
        "output_index": output_index,
        "output_identity": f"server-output-{output_index}",
        "requirement_nonce": f"server-nonce-{project_id}-{output_index}-{kind}",
        "source_library_snapshot_digest": source_snapshot_digest,
        "template_id": "general_template",
        "original_source_channel": "project_uploaded_original",
        "kind": kind,
        "strength": strength,
        "maximum_sources": maximum_sources,
    }
    requirement["requirement_digest"] = source_library.canonical_digest(requirement)
    return requirement


def _evidence(
    entry: dict[str, Any], *, project_id: str, affordance: str, view_kind: str, subject_kind: str
) -> dict[str, Any]:
    profile = {
        "schema_version": "doc270_source_evidence_profile_v2",
        "analyzer": {
            "authority": "v3_server_image_evidence",
            "schema_version": "doc270_image_evidence_analyzer_v1",
            "version": "controlled-test-evidence-v1",
        },
        "project_id": project_id,
        "reference_id": entry["reference_id"],
        "asset_id": entry["asset_id"],
        "content_sha256": entry["content_sha256"],
        "evidence_state": "observed",
        "subject_kind": subject_kind,
        "view_kind": view_kind,
        "affordances": [affordance],
    }
    profile["profile_digest"] = source_library.canonical_digest(profile)
    return profile


def _server_context(
    *, handlers: Any, project: dict[str, Any], requirement: dict[str, Any], evidence_by_reference: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Private read boundaries, never a caller snapshot/requirement surface."""

    plan_binding = {
        "project_id": project["project_id"],
        "command_plan_binding": deepcopy(requirement["command_plan_binding"]),
        "output_index": requirement["output_index"],
        "output_identity": requirement["output_identity"],
        "requirement_nonce": requirement["requirement_nonce"],
        "requirement_digest": requirement["requirement_digest"],
        "source_library_snapshot_digest": requirement["source_library_snapshot_digest"],
        "issuer": deepcopy(requirement["issuer"]),
    }

    return {
        "project_id": project["project_id"],
        "command_binding": deepcopy(requirement["command_plan_binding"]),
        "project_lookup": lambda project_id: handlers.project_service._require_project(project_id),  # noqa: SLF001
        "upload_lookup": handlers.service.get_uploaded_asset,
        "requirement_lookup": lambda binding: deepcopy(requirement),
        "plan_binding_lookup": lambda binding: deepcopy(plan_binding),
        "evidence_lookup": lambda entry: deepcopy(evidence_by_reference.get(entry["reference_id"])),
    }


def _resolve(*, server_context: dict[str, Any]) -> dict[str, Any]:
    """Call the planned server-only seam; no snapshot/requirement is caller input."""

    return source_library.resolve_doc270_shadow_reference_requirements(  # type: ignore[attr-defined]
        project_id=server_context["project_id"],
        command_plan_binding=deepcopy(server_context["command_binding"]),
        trusted_project_lookup=server_context["project_lookup"],
        upload_lookup=server_context["upload_lookup"],
        trusted_requirement_lookup=server_context["requirement_lookup"],
        trusted_plan_binding_lookup=server_context["plan_binding_lookup"],
        evidence_lookup=server_context["evidence_lookup"],
    )


def _assert_receipt_binding(
    receipt: dict[str, Any], *, snapshot: dict[str, Any], requirement: dict[str, Any]
) -> None:
    assert receipt["schema_version"] == "doc270_reference_resolution_receipt_v1"
    assert receipt["project_id"] == requirement["project_id"]
    assert receipt["output_index"] == requirement["output_index"]
    assert receipt["source_library_snapshot_digest"] == snapshot["snapshot_digest"]
    assert receipt["source_resolver"] == {
        "authority": "v3_doc270_shadow_matcher",
        "version": "doc270_shadow_matcher_v1",
    }
    assert receipt["requirement_digest"] == requirement["requirement_digest"]
    assert receipt["receipt_digest"] == source_library.canonical_digest(
        {key: value for key, value in receipt.items() if key != "receipt_digest"}
    )


def test_doc270_phase2_default_not_observed_profile_cannot_fake_a_resolved_match(tmp_path) -> None:
    handlers, project, snapshot, _asset_ids = _project_library(tmp_path)
    requirement = _requirement(
        project_id=project["project_id"], output_index=1, kind="object_rear_structure", source_snapshot_digest=snapshot["snapshot_digest"]
    )

    receipt = _resolve(server_context=_server_context(handlers=handlers, project=project, requirement=requirement, evidence_by_reference={}))

    _assert_receipt_binding(receipt, snapshot=snapshot, requirement=requirement)
    assert receipt["state"] == "insufficient_evidence"
    assert receipt["matched_references"] == []
    assert receipt["shadow_only"] is True


@pytest.mark.parametrize(
    ("kind", "affordance", "view_kind", "subject_kind"),
    [
        ("object_rear_structure", "object_back_or_structure", "rear", "object_or_product"),
        ("person_environment_context", "environment", "environment_wide", "person"),
        ("brand_scene_material", "logo_or_mark", "packaging", "brand_or_graphic"),
    ],
)
def test_doc270_phase2_shadow_matcher_uses_sha_bound_server_evidence_across_domains(
    tmp_path,
    kind: str,
    affordance: str,
    view_kind: str,
    subject_kind: str,
) -> None:
    handlers, project, snapshot, asset_ids = _project_library(tmp_path)
    candidate = _entry(snapshot, asset_ids[2])
    requirement = _requirement(project_id=project["project_id"], output_index=2, kind=kind, source_snapshot_digest=snapshot["snapshot_digest"])

    receipt = _resolve(server_context=_server_context(
        handlers=handlers,
        project=project,
        requirement=requirement,
        evidence_by_reference={candidate["reference_id"]: _evidence(
            candidate,
            project_id=project["project_id"],
            affordance=affordance,
            view_kind=view_kind,
            subject_kind=subject_kind,
        )},
    ))

    _assert_receipt_binding(receipt, snapshot=snapshot, requirement=requirement)
    assert receipt["state"] == "resolved"
    assert receipt["matched_references"] == [
        {
            "reference_id": candidate["reference_id"],
            "asset_id": candidate["asset_id"],
            "content_sha256": candidate["content_sha256"],
            "profile_digest": _evidence(
                candidate,
                project_id=project["project_id"],
                affordance=affordance,
                view_kind=view_kind,
                subject_kind=subject_kind,
            )["profile_digest"],
        }
    ]
    assert receipt["shadow_only"] is True


@pytest.mark.parametrize("mutation", ["sha_drift", "duplicate_reference", "cross_project", "generated_history", "visual_asset"])
def test_doc270_phase2_invalid_candidate_channels_or_snapshot_binding_never_resolve(tmp_path, mutation: str) -> None:
    handlers, project, snapshot, asset_ids = _project_library(tmp_path)
    candidate = _entry(snapshot, asset_ids[0])
    requirement = _requirement(project_id=project["project_id"], output_index=1, kind="object_detail", source_snapshot_digest=snapshot["snapshot_digest"])
    durable_project = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    if mutation == "sha_drift":
        record = handlers.service.get_uploaded_asset(asset_ids[0])
        assert record is not None
        from pathlib import Path

        Path(str(record.file_path)).write_bytes(b"doc270-phase2-replaced-source")
    elif mutation == "duplicate_reference":
        durable_project.reference_assets.append(deepcopy(durable_project.reference_assets[0]))
        handlers.project_service.project_store.save_project(durable_project)
    elif mutation == "cross_project":
        durable_project.reference_assets = [
            item for item in durable_project.reference_assets if item.asset_ref_id != asset_ids[0]
        ]
        handlers.project_service.project_store.save_project(durable_project)
    elif mutation == "generated_history":
        durable_project.reference_assets[0] = durable_project.reference_assets[0].model_copy(
            update={"source_type": ProjectReferenceSourceType.GENERATED_SELECTED}
        )
        handlers.project_service.project_store.save_project(durable_project)
    else:
        durable_project.reference_assets[0] = durable_project.reference_assets[0].model_copy(
            # No ProjectReference enum admits Visual Assets.  A corrupted
            # persisted raw value must still be rejected before matching.
            update={"source_type": "visual_asset_library"}
        )
        handlers.project_service.project_store.save_project(durable_project)

    receipt = _resolve(server_context=_server_context(
        handlers=handlers,
        project=project,
        requirement=requirement,
        evidence_by_reference={candidate["reference_id"]: _evidence(
            candidate,
            project_id=project["project_id"],
            affordance="object_detail",
            view_kind="detail_or_macro",
            subject_kind="object_or_product",
        )},
    ))

    assert receipt["state"] == "invalid"
    assert receipt["matched_references"] == []
    assert handlers.project_service._require_project(project["project_id"]).job_ids == []  # noqa: SLF001


@pytest.mark.parametrize("replay", ["missing_project", "different_project", "different_command", "newer_plan", "different_output"])
def test_doc270_phase2_server_requirement_is_not_replayable_across_command_plan_or_output(tmp_path, replay: str) -> None:
    handlers, project, snapshot, asset_ids = _project_library(tmp_path)
    candidate = _entry(snapshot, asset_ids[0])
    requirement = _requirement(
        project_id=project["project_id"], output_index=1, kind="object_rear_structure", source_snapshot_digest=snapshot["snapshot_digest"]
    )
    context = _server_context(
        handlers=handlers,
        project=project,
        requirement=requirement,
        evidence_by_reference={candidate["reference_id"]: _evidence(
            candidate, project_id=project["project_id"], affordance="object_back_or_structure", view_kind="rear", subject_kind="object_or_product"
        )},
    )
    if replay == "missing_project":
        context["project_id"] = "project-missing"
    elif replay == "different_project":
        context["project_id"] = "project-other"
    elif replay == "different_command":
        context["command_binding"]["command_id"] = "server-command-replayed"
    elif replay == "newer_plan":
        context["command_binding"]["plan_version"] = 2
    else:
        original_lookup = context["plan_binding_lookup"]
        context["plan_binding_lookup"] = lambda binding: {
            **original_lookup(binding), "output_identity": "server-output-replayed"
        }

    receipt = _resolve(server_context=context)

    assert receipt["state"] == "invalid"
    assert receipt["matched_references"] == []
    if replay == "missing_project":
        assert receipt["rationale_codes"] == ["trusted_project_unavailable"]
        assert "project-missing" not in str(receipt)
        assert "traceback" not in str(receipt).lower()
    assert handlers.project_service._require_project(project["project_id"]).job_ids == []  # noqa: SLF001


@pytest.mark.parametrize("binding", ["wrong_project", "wrong_reference", "wrong_asset", "wrong_sha", "wrong_analyzer"])
def test_doc270_phase2_self_digested_wrong_evidence_binding_is_invalid(tmp_path, binding: str) -> None:
    handlers, project, snapshot, asset_ids = _project_library(tmp_path)
    candidate = _entry(snapshot, asset_ids[1])
    requirement = _requirement(
        project_id=project["project_id"], output_index=1, kind="object_detail", source_snapshot_digest=snapshot["snapshot_digest"]
    )
    evidence = _evidence(
        candidate, project_id=project["project_id"], affordance="object_detail", view_kind="detail_or_macro", subject_kind="object_or_product"
    )
    if binding == "wrong_project":
        evidence["project_id"] = "project-other"
    elif binding == "wrong_reference":
        evidence["reference_id"] = "association-other"
    elif binding == "wrong_asset":
        evidence["asset_id"] = "asset-other"
    elif binding == "wrong_sha":
        evidence["content_sha256"] = "e" * 64
    else:
        evidence["analyzer"]["version"] = "untrusted-analyzer-v2"
    evidence["profile_digest"] = source_library.canonical_digest(
        {key: value for key, value in evidence.items() if key != "profile_digest"}
    )

    receipt = _resolve(server_context=_server_context(
        handlers=handlers, project=project, requirement=requirement, evidence_by_reference={candidate["reference_id"]: evidence}
    ))

    assert receipt["state"] == "invalid"
    assert receipt["matched_references"] == []


@pytest.mark.parametrize("maximum_sources", [0, -1, 99])
def test_doc270_phase2_invalid_or_oversized_candidate_policy_never_selects_the_full_library(tmp_path, maximum_sources: int) -> None:
    handlers, project, snapshot, asset_ids = _project_library(tmp_path)
    requirement = _requirement(
        project_id=project["project_id"], output_index=1, kind="object_detail", source_snapshot_digest=snapshot["snapshot_digest"], maximum_sources=maximum_sources
    )
    evidence = {
        _entry(snapshot, asset_id)["reference_id"]: _evidence(
            _entry(snapshot, asset_id), project_id=project["project_id"], affordance="object_detail", view_kind="detail_or_macro", subject_kind="object_or_product"
        )
        for asset_id in asset_ids
    }

    receipt = _resolve(server_context=_server_context(
        handlers=handlers, project=project, requirement=requirement, evidence_by_reference=evidence
    ))

    assert receipt["state"] == "invalid"
    assert receipt["matched_references"] == []


def test_doc270_phase2_shadow_receipt_is_ephemeral_and_repeated_calls_do_not_write_state(tmp_path) -> None:
    handlers, project, snapshot, asset_ids = _project_library(tmp_path)
    candidate = _entry(snapshot, asset_ids[0])
    requirement = _requirement(
        project_id=project["project_id"], output_index=1, kind="object_rear_structure", source_snapshot_digest=snapshot["snapshot_digest"]
    )
    before = deepcopy(handlers.project_service._require_project(project["project_id"]))  # noqa: SLF001
    before_uploads = {
        asset_id: handlers.service.get_uploaded_asset(asset_id).model_dump(mode="json")
        for asset_id in asset_ids
    }
    context = _server_context(
        handlers=handlers,
        project=project,
        requirement=requirement,
        evidence_by_reference={candidate["reference_id"]: _evidence(
            candidate, project_id=project["project_id"], affordance="object_back_or_structure", view_kind="rear", subject_kind="object_or_product"
        )},
    )

    first = _resolve(server_context=context)
    second = _resolve(server_context=context)

    assert first == second
    after = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    assert after.model_dump(mode="json") == before.model_dump(mode="json")
    assert after.job_ids == []
    assert [item.model_dump(mode="json") for item in after.reference_assets] == [
        item.model_dump(mode="json") for item in before.reference_assets
    ]
    assert {
        asset_id: handlers.service.get_uploaded_asset(asset_id).model_dump(mode="json")
        for asset_id in asset_ids
    } == before_uploads


def test_doc270_phase2_resolver_has_no_persistence_boundary_and_returns_ephemeral_receipt(tmp_path) -> None:
    handlers, project, snapshot, asset_ids = _project_library(tmp_path)
    candidate = _entry(snapshot, asset_ids[0])
    context = _server_context(
        handlers=handlers,
        project=project,
        snapshot=snapshot,
        asset_ids=asset_ids,
        requirement=_requirement(
            project_id=project["project_id"],
            output_index=1,
            kind="object_rear_structure",
            source_snapshot_digest=snapshot["snapshot_digest"],
        ),
        evidence={
            candidate["reference_id"]: _evidence(
                candidate,
                project_id=project["project_id"],
                affordance="object_back_or_structure",
                view_kind="rear",
                subject_kind="object_or_product",
            )
        },
        candidates={candidate["reference_id"]: candidate},
    )
    resolver = source_library.resolve_doc270_shadow_reference_requirements  # type: ignore[attr-defined]
    parameters = inspect.signature(resolver).parameters
    forbidden = {
        "project_store",
        "job_store",
        "output_store",
        "receipt_store",
        "audit_store",
        "persistence_store",
        "save_receipt",
        "write_receipt",
        "persist_receipt",
        "write_audit",
    }
    assert not forbidden.intersection(parameters)
    assert not any(
        any(token in name.lower() for token in ("persist", "save", "write"))
        for name in parameters
    )
    receipt = _resolve(server_context=context)
    assert set(receipt) <= {
        "receipt_version",
        "state",
        "project_id",
        "output_index",
        "source_library_snapshot_digest",
        "requirement_digest",
        "matched_references",
        "rationale_codes",
        "receipt_digest",
    }
    assert receipt["state"] in {"resolved", "insufficient_evidence", "ambiguous", "invalid", "not_applicable"}


def test_doc270_phase2_unknown_requirement_kind_is_invalid_even_with_server_marker(tmp_path) -> None:
    handlers, project, snapshot, asset_ids = _project_library(tmp_path)
    candidate = _entry(snapshot, asset_ids[0])
    requirement = _requirement(
        project_id=project["project_id"], output_index=1, kind="arbitrary_browserish_taxonomy", source_snapshot_digest=snapshot["snapshot_digest"]
    )

    receipt = _resolve(server_context=_server_context(
        handlers=handlers,
        project=project,
        requirement=requirement,
        evidence_by_reference={candidate["reference_id"]: _evidence(
            candidate, project_id=project["project_id"], affordance="object_back_or_structure", view_kind="rear", subject_kind="object_or_product"
        )},
    ))

    assert receipt["state"] == "invalid"
    assert receipt["matched_references"] == []


@pytest.mark.parametrize("mutation", ["stale_snapshot", "omitted_entry", "added_entry", "content_replaced"])
def test_doc270_phase2_rederives_authoritative_sources_and_never_accepts_a_caller_snapshot(tmp_path, mutation: str) -> None:
    handlers, project, snapshot, asset_ids = _project_library(tmp_path)
    candidate = _entry(snapshot, asset_ids[0])
    requirement = _requirement(
        project_id=project["project_id"], output_index=1, kind="object_detail", source_snapshot_digest=snapshot["snapshot_digest"]
    )
    stale_but_self_consistent = deepcopy(snapshot)
    durable_project = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    if mutation == "omitted_entry":
        durable_project.reference_assets = durable_project.reference_assets[1:]
        handlers.project_service.project_store.save_project(durable_project)
    elif mutation == "added_entry":
        durable_project.reference_assets.append(deepcopy(durable_project.reference_assets[0]))
        handlers.project_service.project_store.save_project(durable_project)
    elif mutation == "content_replaced":
        record = handlers.service.get_uploaded_asset(asset_ids[0])
        assert record is not None
        from pathlib import Path

        Path(str(record.file_path)).write_bytes(b"doc270-phase2-later-byte-replacement")
    else:
        # The stale dict is deliberately retained only as a hostile caller
        # object. The future resolver must not expose a parameter for it.
        stale_but_self_consistent["entries"] = list(reversed(stale_but_self_consistent["entries"]))
        stale_but_self_consistent["snapshot_digest"] = source_library.canonical_digest(
            {key: value for key, value in stale_but_self_consistent.items() if key != "snapshot_digest"}
        )
    context = _server_context(
        handlers=handlers,
        project=project,
        requirement=requirement,
        evidence_by_reference={candidate["reference_id"]: _evidence(
            candidate, project_id=project["project_id"], affordance="object_detail", view_kind="detail_or_macro", subject_kind="object_or_product"
        )},
    )
    context["caller_snapshot"] = stale_but_self_consistent

    resolver = source_library.resolve_doc270_shadow_reference_requirements  # type: ignore[attr-defined]
    assert "source_library_snapshot" not in inspect.signature(resolver).parameters
    receipt = _resolve(server_context=context)

    if mutation == "stale_snapshot":
        assert receipt["state"] == "resolved"
        assert receipt["matched_references"] == [
            {
                "reference_id": candidate["reference_id"],
                "asset_id": candidate["asset_id"],
                "content_sha256": candidate["content_sha256"],
                "profile_digest": _evidence(
                    candidate,
                    project_id=project["project_id"],
                    affordance="object_detail",
                    view_kind="detail_or_macro",
                    subject_kind="object_or_product",
                )["profile_digest"],
            }
        ]
        assert receipt["source_library_snapshot_digest"] == snapshot["snapshot_digest"]
        assert receipt["receipt_digest"] == source_library.canonical_digest(
            {key: value for key, value in receipt.items() if key != "receipt_digest"}
        )
    else:
        assert receipt["state"] == "invalid"
        assert receipt["matched_references"] == []


def test_doc270_phase2_bounded_unique_evidence_tie_uses_recorded_non_filename_tie_break(tmp_path) -> None:
    handlers, project, snapshot, asset_ids = _project_library(tmp_path)
    candidates = [_entry(snapshot, asset_id) for asset_id in asset_ids[:3]]
    requirement = _requirement(
        project_id=project["project_id"], output_index=3, kind="object_detail", source_snapshot_digest=snapshot["snapshot_digest"], maximum_sources=2
    )
    evidence = {
        candidate["reference_id"]: _evidence(
            candidate, project_id=project["project_id"], affordance="object_detail", view_kind="detail_or_macro", subject_kind="object_or_product"
        )
        for candidate in reversed(candidates)
    }

    receipt = _resolve(server_context=_server_context(
        handlers=handlers, project=project, requirement=requirement, evidence_by_reference=evidence
    ))

    assert receipt["state"] == "resolved"
    assert len(receipt["matched_references"]) == 2
    assert len({item["reference_id"] for item in receipt["matched_references"]}) == 2
    assert receipt["ranking_tie_break"] == "canonical_evidence_binding_v1"
    assert all("phase2-original" not in str(item) for item in receipt["matched_references"])


def test_doc270_phase2_browser_or_metadata_requirement_cannot_issue_semantic_authority(tmp_path) -> None:
    handlers, project, snapshot, asset_ids = _project_library(tmp_path)
    candidate = _entry(snapshot, asset_ids[1])
    forged_requirement = _requirement(
        project_id=project["project_id"], output_index=1, kind="object_rear_structure", source_snapshot_digest=snapshot["snapshot_digest"]
    )
    forged_requirement["issuer"]["authority"] = "browser_metadata"
    forged_requirement["requirement_digest"] = source_library.canonical_digest(
        {key: value for key, value in forged_requirement.items() if key != "requirement_digest"}
    )

    receipt = _resolve(server_context=_server_context(
        handlers=handlers,
        project=project,
        requirement=forged_requirement,
        evidence_by_reference={candidate["reference_id"]: _evidence(
            candidate,
            project_id=project["project_id"],
            affordance="object_back_or_structure",
            view_kind="rear",
            subject_kind="object_or_product",
        )},
    ))

    assert receipt["state"] == "invalid"
    assert receipt["matched_references"] == []


def test_doc270_phase2_general_prompt_only_is_not_applicable_and_does_not_create_ecommerce_receipt(tmp_path) -> None:
    handlers, project, snapshot, _asset_ids = _project_library(tmp_path)
    requirement = _requirement(
        project_id=project["project_id"], output_index=1, kind="no_reference", source_snapshot_digest=snapshot["snapshot_digest"], strength="optional"
    )

    receipt = _resolve(server_context=_server_context(handlers=handlers, project=project, requirement=requirement, evidence_by_reference={}))

    assert receipt["state"] == "not_applicable"
    assert receipt["matched_references"] == []
    view = handlers.get_project(project["project_id"])
    assert "doc270_source_library_binding_receipts" not in view["metadata"]
    assert "current_operation" not in view["metadata"]


def test_doc270_phase2_ecommerce_shadow_result_preserves_doc263_doc269_active_authority(tmp_path) -> None:
    handlers, project, snapshot, asset_ids = _project_library(tmp_path, template_id="ecommerce_template")
    candidate = _entry(snapshot, asset_ids[3])
    requirement = _requirement(
        project_id=project["project_id"], output_index=1, kind="object_detail", source_snapshot_digest=snapshot["snapshot_digest"]
    )
    requirement["template_id"] = "ecommerce_template"
    requirement["requirement_digest"] = source_library.canonical_digest(
        {key: value for key, value in requirement.items() if key != "requirement_digest"}
    )
    before = deepcopy(handlers.project_service._require_project(project["project_id"]))  # noqa: SLF001

    receipt = _resolve(server_context=_server_context(
        handlers=handlers,
        project=project,
        requirement=requirement,
        evidence_by_reference={candidate["reference_id"]: _evidence(
            candidate,
            project_id=project["project_id"],
            affordance="object_detail",
            view_kind="detail_or_macro",
            subject_kind="object_or_product",
        )},
    ))

    assert receipt["state"] == "resolved"
    assert receipt["shadow_only"] is True
    after = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    assert after.model_dump(mode="json") == before.model_dump(mode="json")
    assert after.job_ids == []


def test_doc270_phase2_photography_never_consumes_ecommerce_requirement_or_receipt(tmp_path) -> None:
    handlers, project, snapshot, asset_ids = _project_library(tmp_path)
    candidate = _entry(snapshot, asset_ids[0])
    requirement = _requirement(
        project_id=project["project_id"], output_index=1, kind="object_rear_structure", source_snapshot_digest=snapshot["snapshot_digest"]
    )
    requirement["template_id"] = "photographer_template"
    requirement["requirement_digest"] = source_library.canonical_digest(
        {key: value for key, value in requirement.items() if key != "requirement_digest"}
    )

    receipt = _resolve(server_context=_server_context(
        handlers=handlers,
        project=project,
        requirement=requirement,
        evidence_by_reference={candidate["reference_id"]: _evidence(
            candidate,
            project_id=project["project_id"],
            affordance="object_back_or_structure",
            view_kind="rear",
            subject_kind="object_or_product",
        )},
    ))

    assert receipt["state"] == "not_applicable"
    assert "ecommerce" not in str(receipt).lower()
