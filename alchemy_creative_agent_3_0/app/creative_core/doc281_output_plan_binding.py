"""Server-owned Doc281 output-plan binding envelopes.

The issuer deliberately transports only frozen digest facts.  Source IDs,
paths, prompts, provider responses, and browser supplied fields never cross
this boundary.  The output store remains responsible for binding a skeleton
to its newly-created output record ID.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


_DIGEST_LENGTH = 64
DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY = "doc73_auto_identity_anchor_binding"
DOC73_AUTO_IDENTITY_ANCHOR_SKELETON_KEY = "doc73_auto_identity_anchor_skeleton"
DOC73_AUTO_IDENTITY_ANCHOR_SCHEMA = "doc73_auto_identity_anchor_binding_v1"
DOC73_AUTO_IDENTITY_ANCHOR_ORIGIN = "auto_batch_continuity"
DOC73_AUTO_IDENTITY_ANCHOR_POLICY_VERSION = "doc73_v1"

_DOC73_SOURCE_SKELETON_KEYS = frozenset(
    {
        "schema_version",
        "origin",
        "policy_version",
        "job_id",
        "project_id",
        "batch_plan_digest",
        "source_asset_id",
        "source_plan_position",
        "source_output_index",
        "source_candidate_id",
        "binding_digest",
    }
)
_DOC73_SOURCE_BINDING_KEYS = frozenset(
    {
        *_DOC73_SOURCE_SKELETON_KEYS,
        "source_output_id",
        "source_content_sha256",
        "source_record_binding_digest",
    }
)
_DOC73_TARGET_SKELETON_KEYS = frozenset(
    {
        "schema_version",
        "origin",
        "policy_version",
        "job_id",
        "project_id",
        "batch_plan_digest",
        "source_binding_digest",
        "source_output_id",
        "target_asset_id",
        "target_plan_position",
        "binding_digest",
    }
)
_DOC73_TARGET_BINDING_KEYS = frozenset(
    {
        *_DOC73_TARGET_SKELETON_KEYS,
        "target_output_id",
        "target_record_binding_digest",
    }
)


def doc281_output_index_from_plan_position(value: Any) -> int | None:
    """Translate Central Brain's zero-based asset position to Doc281's index."""

    return value + 1 if type(value) is int and value >= 0 else None


def issue_doc281_output_plan_binding(
    metadata: Mapping[str, Any] | None,
    *,
    job_id: str,
    output_index: int,
    refine_round: int = 0,
) -> dict[str, dict[str, Any]]:
    """Return one exact, server-issued plan skeleton or fail closed.

    Only the initial, planned materialization may receive a skeleton.  A
    retry or an unexpected additional provider pixel record has no authority
    to claim a planned output's disclosure.
    """

    if not isinstance(metadata, Mapping) or not _positive_index(output_index) or refine_round != 0:
        return {}
    frozen_job_id = str(job_id or "").strip()
    if not frozen_job_id:
        return {}

    general = _general_binding(metadata, job_id=frozen_job_id, output_index=output_index)
    if general:
        return {"doc281_output_plan_binding": general}
    ecommerce = _ecommerce_binding(metadata, job_id=frozen_job_id, output_index=output_index)
    return {"doc281_output_plan_binding": ecommerce} if ecommerce else {}


def doc73_batch_plan_digest(*, job_id: str, assets: Any) -> str:
    """Digest only the server-frozen output positions, never creative prose."""

    normalized_assets: list[dict[str, Any]] = []
    for position, asset in enumerate(assets if isinstance(assets, list) else []):
        if isinstance(asset, Mapping):
            asset_id = asset.get("asset_id")
            asset_type = asset.get("asset_type")
            aspect_ratio = asset.get("aspect_ratio")
        else:
            asset_id = getattr(asset, "asset_id", None)
            asset_type = getattr(asset, "asset_type", None)
            aspect_ratio = getattr(asset, "aspect_ratio", None)
        normalized_assets.append(
            {
                "position": position,
                "asset_id": str(asset_id or "").strip(),
                "asset_type": str(getattr(asset_type, "value", asset_type) or "").strip(),
                "aspect_ratio": str(aspect_ratio or "").strip(),
            }
        )
    return _sha256(
        {
            "schema_version": DOC73_AUTO_IDENTITY_ANCHOR_SCHEMA,
            "job_id": str(job_id or "").strip(),
            "assets": normalized_assets,
        }
    )


def issue_doc73_auto_identity_anchor_source_skeleton(
    metadata: Mapping[str, Any] | None,
    *,
    job_id: str,
    project_id: str,
    asset_id: str,
    plan_position: int,
    output_index: int,
    candidate_id: str,
    refine_round: int = 0,
    retry_attempt: int = 0,
) -> dict[str, Any]:
    """Issue a source skeleton only for the initial, planned first output."""

    policy = metadata.get("auto_batch_identity_anchor_policy") if isinstance(metadata, Mapping) else None
    batch_digest = _digest(metadata.get("doc73_batch_plan_digest")) if isinstance(metadata, Mapping) else ""
    values = {
        "schema_version": DOC73_AUTO_IDENTITY_ANCHOR_SCHEMA,
        "origin": DOC73_AUTO_IDENTITY_ANCHOR_ORIGIN,
        "policy_version": DOC73_AUTO_IDENTITY_ANCHOR_POLICY_VERSION,
        "job_id": str(job_id or "").strip(),
        "project_id": str(project_id or "").strip(),
        "batch_plan_digest": batch_digest,
        "source_asset_id": str(asset_id or "").strip(),
        "source_plan_position": plan_position,
        "source_output_index": output_index,
        "source_candidate_id": str(candidate_id or "").strip(),
    }
    if (
        not isinstance(policy, Mapping)
        or policy.get("enabled") is not True
        or type(plan_position) is not int
        or plan_position != 0
        or type(output_index) is not int
        or output_index != 1
        or refine_round != 0
        or retry_attempt != 0
        or not values["job_id"]
        or not values["project_id"]
        or not values["batch_plan_digest"]
        or not values["source_asset_id"]
        or not values["source_candidate_id"]
    ):
        return {}
    return {**values, "binding_digest": _binding_digest(values)}


def issue_doc73_auto_identity_anchor_target_skeleton(
    metadata: Mapping[str, Any] | None,
    *,
    source_binding: Mapping[str, Any],
    job_id: str,
    project_id: str,
    asset_id: str,
    plan_position: int,
) -> dict[str, Any]:
    """Issue a target skeleton from one already-finalized source receipt."""

    batch_digest = _digest(metadata.get("doc73_batch_plan_digest")) if isinstance(metadata, Mapping) else ""
    source_job_id = str(source_binding.get("job_id") or "").strip()
    source_project_id = str(source_binding.get("project_id") or "").strip()
    source_batch_digest = _digest(source_binding.get("batch_plan_digest"))
    source_output_id = str(source_binding.get("source_output_id") or "").strip()
    source_binding_digest = _digest(source_binding.get("binding_digest"))
    values = {
        "schema_version": DOC73_AUTO_IDENTITY_ANCHOR_SCHEMA,
        "origin": DOC73_AUTO_IDENTITY_ANCHOR_ORIGIN,
        "policy_version": DOC73_AUTO_IDENTITY_ANCHOR_POLICY_VERSION,
        "job_id": str(job_id or "").strip(),
        "project_id": str(project_id or "").strip(),
        "batch_plan_digest": batch_digest,
        "source_binding_digest": source_binding_digest,
        "source_output_id": source_output_id,
        "target_asset_id": str(asset_id or "").strip(),
        "target_plan_position": plan_position,
    }
    if (
        not validate_doc73_binding(
            source_binding,
            expected_job_id=source_job_id,
            expected_project_id=source_project_id,
            expected_batch_plan_digest=source_batch_digest,
            expected_output_id=source_output_id,
        )
        or not source_job_id
        or source_job_id != values["job_id"]
        or not source_project_id
        or source_project_id != values["project_id"]
        or not source_batch_digest
        or source_batch_digest != batch_digest
        or not source_output_id
        or not source_binding_digest
        or not values["target_asset_id"]
        or type(plan_position) is not int
        or plan_position <= 0
    ):
        return {}
    return {**values, "binding_digest": _binding_digest(values)}


def finalize_doc73_auto_identity_anchor_binding(
    metadata: Mapping[str, Any] | None,
    *,
    job_id: str,
    project_id: str,
    candidate_id: str,
    asset_id: str,
    output_id: str,
    content_sha256: str,
) -> dict[str, Any]:
    """Finalize a skeleton at the canonical output persistence boundary."""

    result = dict(metadata) if isinstance(metadata, Mapping) else {}
    skeleton = result.pop(DOC73_AUTO_IDENTITY_ANCHOR_SKELETON_KEY, None)
    if not isinstance(skeleton, Mapping):
        return result
    skeleton_keys = set(skeleton)
    if (
        skeleton_keys not in (_DOC73_SOURCE_SKELETON_KEYS, _DOC73_TARGET_SKELETON_KEYS)
        or not _is_digest(skeleton.get("binding_digest"))
        or _binding_digest(skeleton) != skeleton.get("binding_digest")
    ):
        return result
    if not _is_digest(content_sha256):
        return result
    common = {
        "job_id": str(job_id or "").strip(),
        "project_id": str(project_id or "").strip(),
        "batch_plan_digest": _digest(skeleton.get("batch_plan_digest")),
    }
    if set(skeleton) == _DOC73_SOURCE_SKELETON_KEYS:
        if (
            str(skeleton.get("job_id") or "").strip() != common["job_id"]
            or str(skeleton.get("project_id") or "").strip() != common["project_id"]
            or str(skeleton.get("source_asset_id") or "").strip() != str(asset_id or "").strip()
            or str(skeleton.get("source_candidate_id") or "").strip() != str(candidate_id or "").strip()
            or not common["job_id"]
            or not common["project_id"]
            or not common["batch_plan_digest"]
        ):
            return result
        binding = {
            key: skeleton[key]
            for key in _DOC73_SOURCE_SKELETON_KEYS
            if key != "binding_digest"
        }
        binding.update(
            {
                "source_output_id": str(output_id or "").strip(),
                "source_content_sha256": str(content_sha256).strip().lower(),
            }
        )
        binding["binding_digest"] = _binding_digest(binding)
        binding["source_record_binding_digest"] = _record_binding_digest(binding, "source_record_binding_digest")
        if validate_doc73_binding(
            binding,
            expected_job_id=common["job_id"],
            expected_project_id=common["project_id"],
            expected_batch_plan_digest=common["batch_plan_digest"],
            expected_output_id=str(output_id or "").strip(),
            expected_source_asset_id=str(asset_id or "").strip(),
            expected_source_plan_position=0,
            expected_source_candidate_id=str(candidate_id or "").strip(),
        ):
            result[DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY] = binding
        return result
    if set(skeleton) == _DOC73_TARGET_SKELETON_KEYS:
        if (
            str(skeleton.get("job_id") or "").strip() != common["job_id"]
            or str(skeleton.get("project_id") or "").strip() != common["project_id"]
            or str(skeleton.get("target_asset_id") or "").strip() != str(asset_id or "").strip()
            or not common["job_id"]
            or not common["project_id"]
            or not common["batch_plan_digest"]
        ):
            return result
        binding = {
            key: skeleton[key]
            for key in _DOC73_TARGET_SKELETON_KEYS
            if key != "binding_digest"
        }
        binding["target_output_id"] = str(output_id or "").strip()
        binding["binding_digest"] = _binding_digest(binding)
        binding["target_record_binding_digest"] = _record_binding_digest(binding, "target_record_binding_digest")
        if validate_doc73_binding(
            binding,
            expected_job_id=common["job_id"],
            expected_project_id=common["project_id"],
            expected_batch_plan_digest=common["batch_plan_digest"],
            expected_output_id=str(output_id or "").strip(),
            expected_target_asset_id=str(asset_id or "").strip(),
        ):
            result[DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY] = binding
    return result


def validate_doc73_binding(
    value: Any,
    *,
    expected_job_id: str | None = None,
    expected_project_id: str | None = None,
    expected_batch_plan_digest: str | None = None,
    expected_output_id: str | None = None,
    expected_source_asset_id: str | None = None,
    expected_source_plan_position: int | None = None,
    expected_source_candidate_id: str | None = None,
    expected_target_asset_id: str | None = None,
    expected_target_plan_position: int | None = None,
) -> bool:
    """Strictly validate a finalized source or target envelope."""

    if not isinstance(value, Mapping):
        return False
    keys = set(value)
    is_source = keys == _DOC73_SOURCE_BINDING_KEYS
    is_target = keys == _DOC73_TARGET_BINDING_KEYS
    if not (is_source or is_target):
        return False
    if (
        value.get("schema_version") != DOC73_AUTO_IDENTITY_ANCHOR_SCHEMA
        or value.get("origin") != DOC73_AUTO_IDENTITY_ANCHOR_ORIGIN
        or value.get("policy_version") != DOC73_AUTO_IDENTITY_ANCHOR_POLICY_VERSION
    ):
        return False
    for key in ("job_id", "project_id", "batch_plan_digest", "binding_digest"):
        if not str(value.get(key) or "").strip():
            return False
    if not all(_is_digest(value.get(key)) for key in ("batch_plan_digest", "binding_digest")):
        return False
    if str(value.get("job_id") or "").strip() != str(expected_job_id or value.get("job_id") or "").strip():
        return False
    if str(value.get("project_id") or "").strip() != str(expected_project_id or value.get("project_id") or "").strip():
        return False
    if expected_batch_plan_digest is not None and _digest(value.get("batch_plan_digest")) != _digest(expected_batch_plan_digest):
        return False
    if is_source:
        if (
            type(value.get("source_plan_position")) is not int
            or type(value.get("source_output_index")) is not int
            or value.get("source_plan_position") < 0
            or value.get("source_plan_position") != 0
            or value.get("source_output_index") != 1
            or not str(value.get("source_asset_id") or "").strip()
            or not str(value.get("source_candidate_id") or "").strip()
            or not str(value.get("source_output_id") or "").strip()
            or not _is_digest(value.get("source_content_sha256"))
            or not _is_digest(value.get("source_record_binding_digest"))
        ):
            return False
        if expected_source_asset_id is not None and str(value.get("source_asset_id")) != str(expected_source_asset_id):
            return False
        if expected_source_plan_position is not None and value.get("source_plan_position") != expected_source_plan_position:
            return False
        if expected_source_candidate_id is not None and str(value.get("source_candidate_id")) != str(expected_source_candidate_id):
            return False
        actual_output_id = str(value.get("source_output_id") or "").strip()
        if expected_output_id is not None and actual_output_id != str(expected_output_id).strip():
            return False
        return (
            _binding_digest(value) == value.get("binding_digest")
            and _record_binding_digest(value, "source_record_binding_digest") == value.get("source_record_binding_digest")
        )
    if (
        not str(value.get("source_binding_digest") or "").strip()
        or not _is_digest(value.get("source_binding_digest"))
        or not str(value.get("source_output_id") or "").strip()
        or not str(value.get("target_asset_id") or "").strip()
        or type(value.get("target_plan_position")) is not int
        or value.get("target_plan_position") <= 0
        or not str(value.get("target_output_id") or "").strip()
        or not _is_digest(value.get("target_record_binding_digest"))
    ):
        return False
    if expected_target_asset_id is not None and str(value.get("target_asset_id")) != str(expected_target_asset_id):
        return False
    if expected_target_plan_position is not None and value.get("target_plan_position") != expected_target_plan_position:
        return False
    if expected_output_id is not None and str(value.get("target_output_id")) != str(expected_output_id).strip():
        return False
    return (
        _binding_digest(value) == value.get("binding_digest")
        and _record_binding_digest(value, "target_record_binding_digest") == value.get("target_record_binding_digest")
    )


def _binding_digest(value: Mapping[str, Any]) -> str:
    excluded = {"binding_digest", "source_record_binding_digest", "target_record_binding_digest"}
    return _sha256({key: value[key] for key in sorted(value) if key not in excluded})


def _record_binding_digest(value: Mapping[str, Any], record_key: str) -> str:
    return _sha256({key: value[key] for key in sorted(value) if key != record_key})


def _sha256(value: Mapping[str, Any]) -> str:
    canonical = json.dumps(dict(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_digest(value: Any) -> bool:
    return bool(_digest(value)) and all(character in "0123456789abcdef" for character in _digest(value))


def _general_binding(
    metadata: Mapping[str, Any],
    *,
    job_id: str,
    output_index: int,
) -> dict[str, Any] | None:
    identity = metadata.get("doc270_general_command_identity")
    bindings = metadata.get("doc281_general_output_source_bindings_v1")
    projection = metadata.get("doc270_general_original_source_projection")
    if not isinstance(identity, Mapping) or not isinstance(bindings, list) or not isinstance(projection, Mapping):
        return None
    identity_digest = _digest(identity.get("identity_digest"))
    source_receipt_digest = _digest(projection.get("source_receipt_digest"))
    binding = next(
        (
            item
            for item in bindings
            if isinstance(item, Mapping) and item.get("output_index") == output_index
        ),
        None,
    )
    if (
        not identity_digest
        or not source_receipt_digest
        or not isinstance(binding, Mapping)
        or set(binding) != {"output_index", "output_nonce", "output_binding_digest"}
    ):
        return None
    output_nonce = _digest(binding.get("output_nonce"))
    output_binding_digest = _digest(binding.get("output_binding_digest"))
    if not output_nonce or not output_binding_digest:
        return None
    return _envelope(
        job_id=job_id,
        command_identity_digest=identity_digest,
        output_index=output_index,
        output_nonce=output_nonce,
        output_binding_digest=output_binding_digest,
        source_receipt_digest=source_receipt_digest,
    )


def _ecommerce_binding(
    metadata: Mapping[str, Any],
    *,
    job_id: str,
    output_index: int,
) -> dict[str, Any] | None:
    identity = metadata.get("doc270_ecommerce_command_identity")
    receipts = metadata.get("doc270_ecommerce_view_activation_receipts")
    if not isinstance(identity, Mapping) or not isinstance(receipts, list):
        return None
    receipt = next(
        (
            item
            for item in receipts
            if isinstance(item, Mapping) and item.get("output_index") == output_index
        ),
        None,
    )
    identity_digest = _digest(identity.get("identity_digest"))
    output_nonce = _digest(receipt.get("requirement_nonce")) if isinstance(receipt, Mapping) else ""
    output_binding_digest = _digest(receipt.get("receipt_digest")) if isinstance(receipt, Mapping) else ""
    if not identity_digest or not output_nonce or not output_binding_digest:
        return None
    return _envelope(
        job_id=job_id,
        command_identity_digest=identity_digest,
        output_index=output_index,
        output_nonce=output_nonce,
        output_binding_digest=output_binding_digest,
        source_receipt_digest=output_binding_digest,
    )


def _envelope(**values: Any) -> dict[str, Any]:
    return {"schema_version": "doc281_output_plan_binding_v1", **values}


def _positive_index(value: Any) -> bool:
    return type(value) is int and value >= 1


def _digest(value: Any) -> str:
    normalized = str(value or "").strip()
    return normalized if len(normalized) == _DIGEST_LENGTH else ""
