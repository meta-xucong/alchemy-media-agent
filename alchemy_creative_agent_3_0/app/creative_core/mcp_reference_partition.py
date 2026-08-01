"""Closed server-owned reference partition contract for MCP Body materialization."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class McpBodyReferencePartition(BaseModel):
    """Typed Body truth and Face identity partition for strict MCP requests."""

    model_config = ConfigDict(extra="forbid", strict=True)

    contract_version: Literal["body_mcp_reference_partition_v1"] = (
        "body_mcp_reference_partition_v1"
    )
    body_proportion_reference: dict[str, Any]
    face_identity_reference: dict[str, Any]

    @field_validator("body_proportion_reference", "face_identity_reference")
    @classmethod
    def channel_dicts_are_plain_dicts(cls, value: dict[str, Any]) -> dict[str, Any]:
        if type(value) is not dict:
            raise ValueError("body_mcp_reference_partition_channel_invalid")
        return value

    @model_validator(mode="after")
    def validate_closed_channels(self) -> "McpBodyReferencePartition":
        body = self.body_proportion_reference
        face = self.face_identity_reference
        if set(body) != {"role", "truth_layer", "asset_count", "asset_hashes"}:
            raise ValueError("body_mcp_reference_partition_body_fields_invalid")
        if set(face) != {
            "role",
            "truth_layer",
            "identity_continuity_only",
            "asset_count",
            "asset_hashes",
        }:
            raise ValueError("body_mcp_reference_partition_face_fields_invalid")
        if body["role"] != "body_proportion_reference":
            raise ValueError("body_mcp_reference_partition_body_role_invalid")
        if body["truth_layer"] != "body_proportion_truth":
            raise ValueError("body_mcp_reference_partition_body_truth_invalid")
        if face["role"] != "face_identity_reference":
            raise ValueError("body_mcp_reference_partition_face_role_invalid")
        if face["truth_layer"] != "identity_continuity":
            raise ValueError("body_mcp_reference_partition_face_truth_invalid")
        if face["identity_continuity_only"] is not True:
            raise ValueError("body_mcp_reference_partition_face_scope_invalid")
        for channel in (body, face):
            if type(channel["asset_count"]) is not int or channel["asset_count"] <= 0:
                raise ValueError("body_mcp_reference_partition_count_invalid")
            hashes = channel["asset_hashes"]
            if type(hashes) is not list or channel["asset_count"] != len(hashes) or not hashes:
                raise ValueError("body_mcp_reference_partition_hash_count_invalid")
            if any(type(item) is not str or not item.strip() for item in hashes):
                raise ValueError("body_mcp_reference_partition_hash_invalid")
        return self


def build_mcp_body_reference_partition(
    reference_assets: list[dict[str, Any]],
) -> McpBodyReferencePartition:
    """Derive one partition from already server-resolved reference assets.

    The input is deliberately not a public upload payload.  It must already
    contain the server-owned role/truth admission, and the output retains
    only closed channel roles, truth labels, counts, and stable fingerprints.
    """

    body_assets: list[dict[str, Any]] = []
    face_assets: list[dict[str, Any]] = []
    for raw in reference_assets:
        item = dict(raw or {})
        role = str(item.get("role") or "").strip().lower()
        if role == "body_proportion_reference":
            body_assets.append(item)
        elif role == "face_reference":
            face_assets.append(item)
        else:
            raise ValueError("body_mcp_reference_partition_role_invalid")
    if not body_assets or not face_assets:
        raise ValueError("body_mcp_reference_partition_channel_missing")

    def fingerprint(item: dict[str, Any]) -> str:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        declared = str(
            item.get("source_integrity_id")
            or item.get("sha256")
            or metadata.get("source_integrity_id")
            or metadata.get("sha256")
            or ""
        ).strip()
        if declared:
            return declared
        file_path = str(item.get("file_path") or item.get("storage_path") or "").strip()
        if file_path and Path(file_path).is_file():
            digest = hashlib.sha256()
            with Path(file_path).open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        raise ValueError("body_mcp_reference_partition_fingerprint_missing")

    for item in body_assets:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        truth_layer = str(
            item.get("reference_truth_layer") or metadata.get("reference_truth_layer") or ""
        ).strip()
        if truth_layer != "body_proportion_truth":
            raise ValueError("body_mcp_reference_partition_body_truth_invalid")

    return McpBodyReferencePartition(
        body_proportion_reference={
            "role": "body_proportion_reference",
            "truth_layer": "body_proportion_truth",
            "asset_count": len(body_assets),
            "asset_hashes": [fingerprint(item) for item in body_assets],
        },
        face_identity_reference={
            "role": "face_identity_reference",
            "truth_layer": "identity_continuity",
            "identity_continuity_only": True,
            "asset_count": len(face_assets),
            "asset_hashes": [fingerprint(item) for item in face_assets],
        },
    )
