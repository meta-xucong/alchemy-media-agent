"""Server-owned Doc281 output-plan binding envelopes.

The issuer deliberately transports only frozen digest facts.  Source IDs,
paths, prompts, provider responses, and browser supplied fields never cross
this boundary.  The output store remains responsible for binding a skeleton
to its newly-created output record ID.
"""

from __future__ import annotations

from typing import Any, Mapping


_DIGEST_LENGTH = 64


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
