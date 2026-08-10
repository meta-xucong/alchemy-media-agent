"""Doc260 review-evidence planning and exact source resolution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ...creative_core.rules import stable_id
from .contracts import ReviewEvidenceChannel, ReviewEvidencePlan


_REQUIRED_CHANNELS = ("product_truth", "person_identity", "prompt_semantics", "selected_output")
_REFERENCE_CHANNELS = ("product_truth", "person_identity")


class ExactReviewEvidenceResolver:
    """Resolve only exact, persisted evidence for one job and output."""

    def __init__(self, *, asset_store: Any, output_store: Any) -> None:
        self.asset_store = asset_store
        self.output_store = output_store

    def resolve(self, *, record: Any, resolution: Any) -> dict[str, Any]:
        request = getattr(record, "request", None)
        job_id = self._job_id(record, request)
        output_id = str(getattr(resolution, "output_id", "") or "").strip()
        candidate_records = self._candidate_records(resolution)
        requested_channels = self._requested_channels(request)
        binding_reasons = self._resolution_binding_reasons(record, job_id, output_id, resolution)

        specs = self._source_specs(candidate_records)
        audit_present = any(spec["audit_present"] for spec in specs)
        admitted_specs = [spec for spec in specs if spec["admitted"]]
        active_specs = specs
        uploaded_ids = _dedupe_strings(getattr(request, "uploaded_asset_ids", []) if request is not None else [])
        uploaded_id_set = set(uploaded_ids)
        frozen_anchor_ids = self._frozen_anchor_ids(request)

        source_entries = [
            self._resolve_source(
                spec,
                uploaded_id_set=uploaded_id_set,
                frozen_anchor_ids=frozen_anchor_ids,
                request=request,
            )
            for spec in active_specs
        ]
        missing_required = bool(audit_present and not admitted_specs)
        channels: dict[str, ReviewEvidenceChannel] = {}
        for channel in _REFERENCE_CHANNELS:
            entries = [entry for entry in source_entries if entry.get("channel") == channel]
            channels[channel] = self._channel(
                channel,
                requested=requested_channels[channel],
                entries=entries,
                missing_required=missing_required,
            )

        channels["prompt_semantics"] = ReviewEvidenceChannel(
            applicability="required",
            evidence_state="available",
            evidence_ids=("prompt_contract",),
            comparison_allowed=False,
            source_type="prompt_contract",
        )
        selected_state, selected_reason = self._selected_output_state(
            job_id=job_id,
            output_id=output_id,
            resolution=resolution,
            binding_reasons=binding_reasons,
        )
        channels["selected_output"] = ReviewEvidenceChannel(
            applicability="required",
            evidence_state=selected_state,
            evidence_ids=(output_id,) if output_id else (),
            comparison_allowed=False,
            source_type="generated_output" if output_id else None,
            reason_codes=tuple(selected_reason),
        )

        source_binding_digest = stable_id(
            "review_evidence_binding",
            job_id,
            output_id,
            json.dumps(active_specs, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
            ",".join(binding_reasons),
        )
        plan_id = stable_id("review_evidence_plan", job_id, output_id, source_binding_digest)
        plan_data = {
            "contract_version": "review_evidence_plan_v1",
            "plan_id": plan_id,
            "job_id": job_id,
            "output_id": output_id or f"unbound_output_{stable_id('resolution', getattr(resolution, 'resolution_id', ''))}",
            "review_mode": "real_pixel" if selected_state == "available" else "metadata_only",
            "channels": {name: channel.model_dump(mode="json") for name, channel in channels.items()},
            "source_binding_digest": source_binding_digest,
        }
        plan_data["review_plan_digest"] = review_plan_digest(plan_data)
        plan = ReviewEvidencePlan.model_validate(plan_data)

        metadata: dict[str, Any] = {
            "review_evidence_plan": plan.model_dump(mode="json"),
            "review_evidence_plan_digest": plan.review_plan_digest,
            "review_evidence_plan_authority": "exact_review_evidence_resolver",
            "review_reference_evidence_required": any(
                channels[name].applicability == "required" for name in _REFERENCE_CHANNELS
            ),
            "review_reference_evidence_available": any(
                channels[name].evidence_state == "available" for name in _REFERENCE_CHANNELS
            ),
        }
        uploaded_assets = [
            self._review_asset(entry)
            for entry in source_entries
            if entry.get("state") == "available" and entry.get("source_type") == "uploaded"
        ]
        selected_output_assets = [
            self._review_asset(entry)
            for entry in source_entries
            if entry.get("state") == "available" and entry.get("source_type") == "selected_output"
        ]
        if uploaded_assets:
            metadata["uploaded_assets"] = uploaded_assets
        if selected_output_assets:
            metadata["reference_assets"] = selected_output_assets
        return metadata

    @staticmethod
    def _job_id(record: Any, request: Any) -> str:
        value = getattr(record, "job_id", None) or getattr(request, "job_id", None)
        clean = str(value or "").strip()
        return clean or "unbound_job"

    @staticmethod
    def _candidate_records(resolution: Any) -> list[dict[str, Any]]:
        metadata = resolution.metadata if isinstance(getattr(resolution, "metadata", None), dict) else {}
        records: list[dict[str, Any]] = []

        def add(value: Any) -> None:
            if isinstance(value, dict):
                records.append(value)

        add(metadata.get("candidate_metadata"))
        asset_metadata = metadata.get("asset_metadata")
        if isinstance(asset_metadata, dict):
            add(asset_metadata.get("candidate_metadata"))
        output_record = metadata.get("output_record")
        if isinstance(output_record, dict):
            add(output_record)
            add(output_record.get("candidate_metadata"))
            output_metadata = output_record.get("metadata")
            if isinstance(output_metadata, dict):
                add(output_metadata)
                add(output_metadata.get("candidate_metadata"))
        return _dedupe_record_dicts(records)
    @staticmethod
    def _source_specs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        specs: list[dict[str, Any]] = []
        for item in records:
            audit = item.get("reference_input_execution")
            audit_present = isinstance(audit, dict)
            admitted = ExactReviewEvidenceResolver._is_admitted_pixels_received(audit)
            source_ids = _dedupe_strings(item.get("reference_truth_source_ids") or item.get("reference_asset_ids") or [])
            claimed_channel = str(item.get("reference_truth_channel") or item.get("reference_channel") or "").strip().lower()
            claimed_role = str(item.get("reference_truth_role") or item.get("reference_role") or "").strip()
            for source_id in source_ids:
                specs.append(
                    {
                        "source_id": source_id,
                        "admitted": admitted,
                        "audit_present": audit_present,
                        "claimed_channel": claimed_channel,
                        "claimed_role": claimed_role,
                    }
                )
        return _dedupe_specs(specs)

    @staticmethod
    def _is_admitted_pixels_received(audit: Any) -> bool:
        return (
            isinstance(audit, dict)
            and str(audit.get("admission_outcome") or "").lower() == "admitted"
            and str(audit.get("operation_outcome") or "").lower() == "pixels_received"
            and _safe_int(audit.get("reference_count")) > 0
        )

    @staticmethod
    def _frozen_anchor_ids(request: Any) -> set[str]:
        metadata = getattr(request, "metadata", {}) if request is not None else {}
        references = metadata.get("professional_anchor_reference_assets", []) if isinstance(metadata, dict) else []
        return {
            str(item.get("asset_id") or "").strip()
            for item in references
            if isinstance(item, dict) and str(item.get("asset_id") or "").strip()
        }

    def _resolution_binding_reasons(
        self,
        record: Any,
        job_id: str,
        output_id: str,
        resolution: Any,
    ) -> list[str]:
        reasons: list[str] = []
        candidate_id = str(getattr(resolution, "candidate_id", "") or "").strip()
        if str(getattr(resolution, "job_id", "") or "").strip() != job_id:
            reasons.append("resolution_job_binding")
        if not output_id:
            reasons.append("resolution_output_binding")
        expected_mcp_operation = str(
            getattr(getattr(record, "request", None), "metadata", {}).get("mcp_operation_id")
            if isinstance(getattr(getattr(record, "request", None), "metadata", {}), dict)
            else ""
        ).strip()
        observed_mcp_operations: set[str] = set()
        for item in self._candidate_records(resolution):
            for binding in _binding_claims(item):
                if binding.get("job_id") and str(binding["job_id"]).strip() != job_id:
                    reasons.append("operation_job_binding")
                if binding.get("operation_job_id") and str(binding["operation_job_id"]).strip() != job_id:
                    reasons.append("operation_job_binding")
                if binding.get("output_id") and str(binding["output_id"]).strip() != output_id:
                    reasons.append("operation_output_binding")
                if binding.get("candidate_id") and str(binding["candidate_id"]).strip() != candidate_id:
                    reasons.append("operation_candidate_binding")
                operation = str(binding.get("mcp_operation_id") or "").strip()
                if operation:
                    observed_mcp_operations.add(operation)
                    if expected_mcp_operation and operation != expected_mcp_operation:
                        reasons.append("mcp_operation_binding")
        if len(observed_mcp_operations) > 1:
            reasons.append("mcp_operation_binding")
        return list(dict.fromkeys(reasons))
    def _requested_channels(self, request: Any) -> dict[str, bool]:
        product = bool(getattr(request, "product_profile", None)) if request is not None else False
        person = False
        uploaded_ids = _dedupe_strings(getattr(request, "uploaded_asset_ids", []) if request is not None else [])
        for asset_id in uploaded_ids:
            upload = self.asset_store.get_upload(asset_id)
            role = _role_value(getattr(upload, "role", None)) if upload is not None else ""
            product = product or _channel_for_role(role) == "product_truth"
            person = person or _channel_for_role(role) == "person_identity"
        return {"product_truth": product, "person_identity": person}

    def _resolve_source(
        self,
        spec: dict[str, Any],
        *,
        uploaded_id_set: set[str],
        frozen_anchor_ids: set[str],
        request: Any,
    ) -> dict[str, Any]:
        source_id = str(spec["source_id"])
        if source_id in uploaded_id_set:
            upload = self.asset_store.get_upload(source_id)
            actual_channel = _channel_for_role(getattr(upload, "role", None)) if upload is not None else None
            channel = actual_channel or "product_truth"
            base = {
                "source_id": source_id,
                "channel": channel,
                "source_type": "uploaded" if upload is not None else None,
                "role": _role_value(getattr(upload, "role", None)) if upload is not None else None,
            }
            if _claimed_channel_is_invalid(spec.get("claimed_channel"), actual_channel):
                return {**base, "state": "invalid", "reason": "reference_truth_channel"}
            if spec.get("claimed_role") and not _roles_match(spec["claimed_role"], base["role"]):
                return {**base, "state": "invalid", "reason": "reference_truth_role"}
            if upload is None:
                return {**base, "state": "unavailable", "source_type": None}
            if not spec.get("admitted"):
                return {**base, "state": "unavailable", "reason": "reference_not_admitted"}
            return {**base, **self._persisted_file_state(upload, "uploaded")}

        if source_id in frozen_anchor_ids:
            output = self.output_store.get_output(source_id)
            actual_channel = "person_identity"
            channel = actual_channel
            base = {
                "source_id": source_id,
                "channel": channel,
                "source_type": "selected_output" if output is not None else None,
                "role": "face_reference",
            }
            if _claimed_channel_is_invalid(spec.get("claimed_channel"), actual_channel):
                return {**base, "state": "invalid", "reason": "reference_truth_channel"}
            if spec.get("claimed_role") and not _roles_match(spec["claimed_role"], base["role"]):
                return {**base, "state": "invalid", "reason": "reference_truth_role"}
            if output is None:
                return {**base, "state": "unavailable"}
            if not spec.get("admitted"):
                return {**base, "state": "unavailable", "reason": "reference_not_admitted"}
            if str(getattr(output, "job_id", "") or "").strip() == str(getattr(request, "job_id", "") or "").strip():
                return {**base, "state": "invalid", "reason": "reference_output_job_binding"}
            return {**base, **self._persisted_file_state(output, "selected_output")}

        upload = self.asset_store.get_upload(source_id)
        output = self.output_store.get_output(source_id)
        exists_upload = upload is not None
        exists_output = output is not None
        actual_channel = _channel_for_role(getattr(upload, "role", None)) if upload is not None else "person_identity" if output is not None else None
        return {
            "source_id": source_id,
            "state": "invalid" if exists_upload or exists_output else "unavailable",
            "channel": actual_channel or "product_truth",
            "source_type": "uploaded" if exists_upload else "selected_output" if exists_output else None,
            "reason": "source_job_binding" if exists_upload or exists_output else None,
        }

    def _persisted_file_state(self, record: Any, source_type: str) -> dict[str, Any]:
        path = Path(str(getattr(record, "file_path", "") or ""))
        if not path.is_file():
            return {"state": "unavailable", "file_path": str(path)}
        try:
            actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return {"state": "unavailable", "file_path": str(path)}
        expected_digest = str(
            getattr(record, "content_sha256", None)
            or (getattr(record, "metadata", {}) or {}).get("content_sha256", "")
            or ""
        ).strip()
        if not expected_digest or expected_digest != actual_digest:
            return {"state": "invalid", "file_path": str(path), "reason": f"{source_type}_content_integrity"}
        return {
            "state": "unavailable" if getattr(record, "status", "ready") not in {"ready", "stored"} else "available",
            "file_path": str(path),
            "mime_type": getattr(record, "mime_type", None),
            "use_policy": "admitted_generation_reference",
        }

    def _selected_output_state(
        self,
        *,
        job_id: str,
        output_id: str,
        resolution: Any,
        binding_reasons: list[str],
    ) -> tuple[str, list[str]]:
        if binding_reasons:
            return "invalid", binding_reasons
        if str(getattr(resolution, "status", "") or "").strip() != "ready":
            return "unavailable", ["resolution_not_ready"]
        path = Path(str(getattr(resolution, "file_path", "") or ""))
        if not path.is_file():
            return "unavailable", ["selected_output_unreadable"]
        metadata = resolution.metadata if isinstance(getattr(resolution, "metadata", None), dict) else {}
        output_record = metadata.get("output_record") if isinstance(metadata.get("output_record"), dict) else {}
        expected = str(
            output_record.get("content_sha256")
            or (output_record.get("metadata") or {}).get("content_sha256")
            or metadata.get("content_sha256")
            or ""
        ).strip()
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return "unavailable", ["selected_output_unreadable"]
        if not expected or expected != actual:
            return "invalid", ["selected_output_content_integrity"]
        return "available", []

    @staticmethod
    def _channel(
        name: str,
        *,
        requested: bool,
        entries: list[dict[str, Any]],
        missing_required: bool,
    ) -> ReviewEvidenceChannel:
        if not entries:
            state = "unavailable" if requested and missing_required else "not_provided" if requested else "not_applicable"
            applicability = "required" if state == "unavailable" else state
            return ReviewEvidenceChannel(
                applicability=applicability,
                evidence_state=state,
                comparison_allowed=False,
                reason_codes=(f"review_evidence_{name}_{state}",) if state == "unavailable" else (),
            )
        states = {str(item.get("state")) for item in entries}
        state = "invalid" if "invalid" in states else "unavailable" if "unavailable" in states else "available"
        evidence_ids = tuple(str(item["source_id"]) for item in entries if item.get("source_id"))
        source_types = {str(item.get("source_type") or "") for item in entries if item.get("source_type")}
        reasons = tuple(
            f"review_evidence_{name}_{item['reason']}"
            for item in entries
            if item.get("reason")
        )
        return ReviewEvidenceChannel(
            applicability="required",
            evidence_state=state,
            evidence_ids=evidence_ids,
            comparison_allowed=state == "available",
            source_type=next(iter(source_types)) if len(source_types) == 1 else None,
            reason_codes=reasons,
        )

    @staticmethod
    def _review_asset(entry: dict[str, Any]) -> dict[str, Any]:
        asset = {
            "asset_id": entry["source_id"],
            "role": entry.get("role"),
            "source_type": entry.get("source_type"),
            "use_policy": entry.get("use_policy") or "admitted_generation_reference",
            "file_path": entry["file_path"],
            "mime_type": entry.get("mime_type"),
        }
        if entry.get("source_type") == "selected_output":
            asset["output_id"] = entry["source_id"]
        return asset


def review_plan_digest(plan_data: dict[str, Any]) -> str:
    payload = dict(plan_data)
    payload.pop("review_plan_digest", None)
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _dedupe_record_dicts(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        key = json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
        if key not in seen:
            seen.add(key)
            result.append(record)
    return result


def _binding_claims(record: dict[str, Any]) -> list[dict[str, Any]]:
    claims = [record]
    for key in (
        "reference_input_execution",
        "provider_delivery",
        "provider_delivery_binding",
        "provider_delivery_receipt",
        "operation",
        "mcp_materialization",
    ):
        value = record.get(key)
        if isinstance(value, dict):
            claims.append(value)
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        claims.append(metadata)
        for key in (
            "reference_input_execution",
            "provider_delivery",
            "provider_delivery_binding",
            "provider_delivery_receipt",
            "operation",
            "mcp_materialization",
        ):
            value = metadata.get(key)
            if isinstance(value, dict):
                claims.append(value)
    return _dedupe_record_dicts(claims)


def _roles_match(claimed: Any, actual: Any) -> bool:
    aliases = {
        "subject_reference": "product_reference",
        "portrait_identity": "face_reference",
        "identity_reference": "face_reference",
        "character_reference": "face_reference",
        "full_body_reference": "body_proportion_reference",
        "body_reference": "body_proportion_reference",
    }
    claimed_value = aliases.get(_role_value(claimed).lower(), _role_value(claimed).lower())
    actual_value = aliases.get(_role_value(actual).lower(), _role_value(actual).lower())
    return bool(claimed_value and actual_value and claimed_value == actual_value)


def _claimed_channel_is_invalid(claimed: Any, actual_channel: str | None) -> bool:
    value = str(claimed or "").strip().lower()
    if not value:
        return False
    return value not in _REFERENCE_CHANNELS or actual_channel is None or value != actual_channel

def _channel_for_role(role: Any) -> str | None:
    value = _role_value(role).lower()
    if any(token in value for token in ("product", "garment", "item", "logo", "brand")):
        return "product_truth"
    if any(token in value for token in ("face", "portrait", "identity", "person", "character")):
        return "person_identity"
    return None


def _role_value(role: Any) -> str:
    return str(getattr(role, "value", role) or "")


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _dedupe_strings(values: Any) -> list[str]:
    if isinstance(values, (str, bytes, dict)) or values is None:
        return []
    try:
        iterable = iter(values)
    except TypeError:
        iterable = iter(())
    result: list[str] = []
    seen: set[str] = set()
    for value in iterable:
        clean = str(value or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _dedupe_specs(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, bool, str, str]] = set()
    for spec in specs:
        key = (
            str(spec.get("source_id") or ""),
            bool(spec.get("admitted")),
            str(spec.get("claimed_channel") or ""),
            str(spec.get("claimed_role") or ""),
        )
        if key not in seen:
            seen.add(key)
            result.append(spec)
    return result