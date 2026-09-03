"""Doc260 review-evidence planning and exact source resolution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ...creative_core.rules import stable_id
from ...creative_core.doc281_output_plan_binding import (
    DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY,
    validate_doc73_binding,
)
from .contracts import ReviewEvidenceChannel, ReviewEvidencePlan


_REQUIRED_CHANNELS = ("product_truth", "person_identity", "prompt_semantics", "selected_output")
_REFERENCE_CHANNELS = ("product_truth", "person_identity")


class ExactReviewEvidenceResolver:
    """Resolve only exact, persisted evidence for one job and output."""

    def __init__(self, *, asset_store: Any, output_store: Any) -> None:
        self.asset_store = asset_store
        self.output_store = output_store

    def resolve(
        self,
        *,
        record: Any,
        resolution: Any,
        server_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the review plan from persisted evidence and server receipts.

        Automatic identity continuity is a server-owned reference channel.  It
        must not be reconstructed from the public request or promoted into the
        formal uploaded ``person_identity`` channel.
        """

        request = getattr(record, "request", None)
        job_id = self._job_id(record, request)
        output_id = str(getattr(resolution, "output_id", "") or "").strip()
        candidate_records = self._candidate_records(resolution)
        requested_channels = self._requested_channels(request)
        binding_reasons = self._resolution_binding_reasons(record, job_id, output_id, resolution)

        server_auto_anchor = self._server_doc73_auto_anchor(
            server_metadata=server_metadata,
            candidate_records=candidate_records,
            request=request,
            resolution=resolution,
            job_id=job_id,
            output_id=output_id,
        )
        excluded_auto_source_ids = (
            set(server_auto_anchor.get("source_ids", ()))
            if server_auto_anchor is not None
            else set()
        )
        specs = self._source_specs(
            candidate_records,
            excluded_source_ids=excluded_auto_source_ids,
        )
        audit_present = any(spec["audit_present"] for spec in specs)
        admitted_specs = [spec for spec in specs if spec["admitted"]]
        active_specs = specs
        uploaded_ids = _dedupe_strings(getattr(request, "uploaded_asset_ids", []) if request is not None else [])
        uploaded_id_set = set(uploaded_ids)
        frozen_anchor_bindings = self._frozen_anchor_bindings(request)
        frozen_anchor_ids = self._frozen_anchor_ids(request) - set(frozen_anchor_bindings)

        source_entries = [
            self._resolve_source(
                spec,
                uploaded_id_set=uploaded_id_set,
                frozen_anchor_ids=frozen_anchor_ids,
                frozen_anchor_bindings=frozen_anchor_bindings,
                current_job_id=job_id,
                request=request,
            )
            for spec in active_specs
        ]
        continuity_state = (
            {
                key: value
                for key, value in server_auto_anchor.items()
                if key in {"state", "role", "reason"}
            }
            if server_auto_anchor is not None
            else self._doc73_continuity_state(
                record=record,
                request=request,
                resolution=resolution,
                candidate_records=candidate_records,
                job_id=job_id,
                output_id=output_id,
            )
        )
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
        selected_binding = frozen_anchor_bindings.get(output_id)
        selected_expected_integrity_id = None
        if isinstance(selected_binding, dict) and not any(
            selected_binding.get(key)
            for key in ("integrity_invalid", "integrity_missing", "job_invalid", "job_missing")
        ):
            selected_expected_integrity_id = selected_binding.get("source_integrity_id") or None
        selected_state, selected_reason = self._selected_output_state(
            job_id=job_id,
            output_id=output_id,
            resolution=resolution,
            binding_reasons=binding_reasons,
            expected_integrity_id=selected_expected_integrity_id,
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
            "doc73_auto_identity_anchor_review": continuity_state,
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
        auto_anchor_assets = []
        if (
            isinstance(server_auto_anchor, dict)
            and server_auto_anchor.get("state") == "available"
            and isinstance(server_auto_anchor.get("entry"), dict)
        ):
            auto_anchor_assets = [self._review_asset(server_auto_anchor["entry"])]
        if uploaded_assets:
            metadata["uploaded_assets"] = uploaded_assets
        if selected_output_assets or auto_anchor_assets:
            metadata["reference_assets"] = [*auto_anchor_assets, *selected_output_assets]
            metadata["doc73_auto_identity_anchor_assets"] = list(auto_anchor_assets)
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
    def _source_specs(
        records: list[dict[str, Any]],
        *,
        excluded_source_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        specs: list[dict[str, Any]] = []
        excluded = {str(value).strip() for value in (excluded_source_ids or set()) if str(value).strip()}
        for item in records:
            audit = item.get("reference_input_execution")
            audit_present = isinstance(audit, dict)
            admitted = ExactReviewEvidenceResolver._is_admitted_pixels_received(audit)
            auto_output_ids = ExactReviewEvidenceResolver._doc73_output_ids(item)
            if "reference_truth_source_ids" in item:
                source_ids = [
                    source_id
                    for source_id in _dedupe_strings(item.get("reference_truth_source_ids"))
                    if source_id not in auto_output_ids and source_id not in excluded
                ]
            else:
                source_ids = [
                    source_id
                    for source_id in _dedupe_strings(item.get("reference_asset_ids"))
                    if source_id not in auto_output_ids and source_id not in excluded
                ]
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
    def _server_doc73_auto_anchor_source_ids(server_metadata: Any) -> set[str]:
        """Collect only IDs that must not fall back into formal source handling."""

        if not isinstance(server_metadata, dict):
            return set()
        result: set[str] = set()
        values = [
            server_metadata.get("doc73_auto_identity_anchor_receipt"),
            server_metadata.get("doc73_auto_identity_anchor_reference"),
        ]
        for value in values:
            if not isinstance(value, dict):
                continue
            for key in ("source_output_id", "output_id", "source_id"):
                source_id = str(value.get(key) or "").strip()
                if source_id:
                    result.add(source_id)
            binding = value.get(DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY)
            if isinstance(binding, dict):
                source_id = str(binding.get("source_output_id") or "").strip()
                if source_id:
                    result.add(source_id)
        return result

    @staticmethod
    def _doc73_target_links_source(
        candidate_records: list[dict[str, Any]],
        source_output_id: str,
    ) -> bool:
        for item in candidate_records:
            if not ExactReviewEvidenceResolver._is_admitted_pixels_received(
                item.get("reference_input_execution")
            ):
                continue
            if "reference_truth_source_ids" in item:
                source_ids = _dedupe_strings(item.get("reference_truth_source_ids"))
            else:
                source_ids = _dedupe_strings(item.get("reference_asset_ids"))
            if source_output_id in source_ids:
                return True
        return False

    def _server_doc73_auto_anchor(
        self,
        *,
        server_metadata: dict[str, Any] | None,
        candidate_records: list[dict[str, Any]],
        request: Any,
        resolution: Any,
        job_id: str,
        output_id: str,
    ) -> dict[str, Any] | None:
        """Resolve the trusted automatic anchor without requiring legacy fields.

        The immutable Doc73 receipt supplies the source integrity fact.  The
        persisted source record and current output still have to match it, and
        a cross-job source is accepted only when the current output's admitted
        reference execution explicitly links that source.
        """

        if not isinstance(server_metadata, dict) or not any(
            key in server_metadata
            for key in (
                "doc73_auto_identity_anchor_receipt",
                "doc73_auto_identity_anchor_reference",
            )
        ):
            return None

        source_ids = self._server_doc73_auto_anchor_source_ids(server_metadata)
        receipt = server_metadata.get("doc73_auto_identity_anchor_receipt")
        reference = server_metadata.get("doc73_auto_identity_anchor_reference")

        def invalid(reason: str, state: str = "invalid") -> dict[str, Any]:
            return {"state": state, "reason": reason, "source_ids": source_ids}

        if not isinstance(receipt, dict) or not isinstance(reference, dict):
            return invalid("doc73_server_receipt_missing")
        if (
            reference.get("origin") != "auto_batch_continuity"
            or reference.get("source_type") != "auto_batch_continuity"
            or reference.get(DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY) != receipt
        ):
            return invalid("doc73_server_receipt_reference_mismatch")

        source_output_id = str(receipt.get("source_output_id") or "").strip()
        source_job_id = str(receipt.get("job_id") or "").strip()
        source_project_id = str(receipt.get("project_id") or "").strip()
        source_asset_id = str(receipt.get("source_asset_id") or "").strip()
        source_candidate_id = str(receipt.get("source_candidate_id") or "").strip()
        source_batch_digest = str(receipt.get("batch_plan_digest") or "").strip()
        if not all(
            (
                source_output_id,
                source_job_id,
                source_project_id,
                source_asset_id,
                source_candidate_id,
                source_batch_digest,
            )
        ):
            return invalid("doc73_server_receipt_incomplete")
        if not validate_doc73_binding(
            receipt,
            expected_job_id=source_job_id,
            expected_project_id=source_project_id,
            expected_batch_plan_digest=source_batch_digest,
            expected_output_id=source_output_id,
            expected_source_asset_id=source_asset_id,
            expected_source_plan_position=0,
            expected_source_candidate_id=source_candidate_id,
        ):
            return invalid("doc73_server_receipt_invalid")
        if (
            str(reference.get("output_id") or reference.get("source_id") or "").strip()
            != source_output_id
        ):
            return invalid("doc73_server_reference_output_mismatch")

        try:
            source_record = self.output_store.get_output(source_output_id)
        except Exception:
            return invalid("doc73_anchor_source_lookup_failed", state="unavailable")
        if source_record is None:
            return invalid("doc73_anchor_source_missing", state="unavailable")
        source_metadata = getattr(source_record, "metadata", {})
        source_metadata = source_metadata if isinstance(source_metadata, dict) else {}
        if (
            str(getattr(source_record, "output_id", "") or "").strip() != source_output_id
            or str(getattr(source_record, "job_id", "") or "").strip() != source_job_id
            or str(getattr(source_record, "candidate_id", "") or "").strip() != source_candidate_id
            or str(getattr(source_record, "asset_id", "") or "").strip() != source_asset_id
            or (
                str(source_metadata.get("project_id") or "").strip()
                and str(source_metadata.get("project_id") or "").strip() != source_project_id
            )
            or source_metadata.get(DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY) != receipt
        ):
            return invalid("doc73_anchor_source_record_binding")
        receipt_reader = getattr(self.output_store, "get_doc73_auto_identity_anchor_receipt", None)
        if callable(receipt_reader):
            try:
                stored_receipt = receipt_reader(source_job_id)
            except Exception:
                return invalid("doc73_anchor_source_receipt_lookup_failed", state="unavailable")
            if stored_receipt != receipt:
                return invalid("doc73_anchor_source_receipt_binding")
        try:
            source_state = self._persisted_file_state(
                source_record,
                "auto_batch_continuity",
                expected_integrity_id=str(receipt.get("source_content_sha256") or ""),
            )
        except Exception:
            return invalid("doc73_anchor_source_integrity_lookup_failed", state="unavailable")
        if source_state.get("state") != "available":
            return invalid(
                str(source_state.get("reason") or "doc73_anchor_source_unavailable"),
                state=str(source_state.get("state") or "unavailable"),
            )

        try:
            target_record = self.output_store.get_output(output_id) if output_id else None
        except Exception:
            return invalid("doc73_anchor_target_lookup_failed", state="unavailable")
        request_metadata = getattr(request, "metadata", {}) if request is not None else {}
        request_project_id = (
            str(request_metadata.get("project_id") or "").strip()
            if isinstance(request_metadata, dict)
            else ""
        )
        if target_record is None:
            return invalid("doc73_anchor_target_record_missing", state="unavailable")
        target_metadata = getattr(target_record, "metadata", {})
        target_metadata = target_metadata if isinstance(target_metadata, dict) else {}
        if (
            str(getattr(target_record, "output_id", "") or "").strip() != output_id
            or str(getattr(target_record, "job_id", "") or "").strip() != job_id
            or (
                request_project_id
                and str(target_metadata.get("project_id") or "").strip()
                and str(target_metadata.get("project_id") or "").strip() != request_project_id
            )
            or (
                request_project_id
                and request_project_id != source_project_id
            )
        ):
            return invalid("doc73_anchor_target_record_binding")

        if output_id == source_output_id:
            if job_id != source_job_id:
                return invalid("doc73_anchor_source_job_binding")
            role = "source"
        else:
            if not self._doc73_target_links_source(candidate_records, source_output_id):
                return invalid("doc73_anchor_target_reference_binding")
            try:
                target_state = self._persisted_file_state(target_record, "auto_batch_continuity")
            except Exception:
                return invalid("doc73_anchor_target_integrity_lookup_failed", state="unavailable")
            if target_state.get("state") != "available":
                return invalid(
                    str(target_state.get("reason") or "doc73_anchor_target_unavailable"),
                    state=str(target_state.get("state") or "unavailable"),
                )
            role = "target"

        entry = {
            "source_id": source_output_id,
            "channel": "person_identity",
            "source_type": "auto_batch_continuity",
            "role": "face_reference",
            "state": "available",
            "file_path": str(source_record.file_path),
            "mime_type": source_record.mime_type or "image/png",
            "use_policy": "identity_continuity",
            "output_id": source_output_id,
        }
        return {
            "state": "available",
            "role": role,
            "source_ids": source_ids or {source_output_id},
            "entry": entry,
        }

    @staticmethod
    def _doc73_bindings(record: dict[str, Any]) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []

        def add(value: Any) -> None:
            if isinstance(value, dict) and value.get("origin") == "auto_batch_continuity":
                values.append(value)

        add(record.get(DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY))
        metadata = record.get("metadata")
        if isinstance(metadata, dict):
            add(metadata.get(DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY))
        candidate_metadata = record.get("candidate_metadata")
        if isinstance(candidate_metadata, dict):
            add(candidate_metadata.get(DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY))
        return _dedupe_record_dicts(values)

    @classmethod
    def _doc73_output_ids(cls, record: dict[str, Any]) -> set[str]:
        output_ids: set[str] = set()
        for binding in cls._doc73_bindings(record):
            for key in ("source_output_id", "target_output_id"):
                value = str(binding.get(key) or "").strip()
                if value:
                    output_ids.add(value)
        return output_ids

    def _doc73_continuity_state(
        self,
        *,
        record: Any,
        request: Any,
        resolution: Any,
        candidate_records: list[dict[str, Any]],
        job_id: str,
        output_id: str,
    ) -> dict[str, Any]:
        bindings = [binding for item in candidate_records for binding in self._doc73_bindings(item)]
        bindings = _dedupe_record_dicts(bindings)
        if not bindings:
            return {"state": "not_provided"}
        target_record = self.output_store.get_output(output_id) if output_id else None
        project_id = str(
            (getattr(request, "metadata", {}) or {}).get("project_id")
            if request is not None and isinstance(getattr(request, "metadata", {}), dict)
            else ""
        ).strip()
        if target_record is not None and not project_id:
            project_id = str((target_record.metadata or {}).get("project_id") or "").strip()
        batch_plan_digest = self._doc73_current_batch_plan_digest(request, target_record)
        if not batch_plan_digest:
            return {"state": "invalid", "reason": "doc73_batch_plan_digest_missing"}
        for binding in bindings:
            if not validate_doc73_binding(
                binding,
                expected_job_id=job_id,
                expected_project_id=project_id or None,
                expected_batch_plan_digest=batch_plan_digest,
                expected_output_id=output_id or None,
            ):
                continue
            if target_record is None:
                continue
            if str(binding.get("source_output_id") or "").strip() == output_id:
                if self._doc73_source_record_is_valid(
                    binding,
                    target_record,
                    job_id,
                    project_id,
                    batch_plan_digest,
                ):
                    return {"state": "available", "role": "source"}
                continue
            if str(binding.get("target_output_id") or "").strip() != output_id:
                continue
            if str(target_record.job_id or "").strip() != job_id:
                continue
            if str(target_record.asset_id or "").strip() != str(binding.get("target_asset_id") or "").strip():
                continue
            source_id = str(binding.get("source_output_id") or "").strip()
            source_record = self.output_store.get_output(source_id)
            if source_record is None:
                continue
            source_binding = source_record.metadata.get(DOC73_AUTO_IDENTITY_ANCHOR_BINDING_KEY)
            if not isinstance(source_binding, dict):
                continue
            if str(source_binding.get("binding_digest") or "") != str(binding.get("source_binding_digest") or ""):
                continue
            source_job_id = str(source_binding.get("job_id") or "").strip()
            source_project_id = str(source_binding.get("project_id") or "").strip()
            source_batch_plan_digest = str(source_binding.get("batch_plan_digest") or "").strip()
            if not source_job_id or not source_project_id or not source_batch_plan_digest:
                continue
            if not self._doc73_source_record_is_valid(
                source_binding,
                source_record,
                source_job_id,
                source_project_id,
                source_batch_plan_digest,
            ):
                continue
            target_state = self._persisted_file_state(target_record, "auto_batch_continuity")
            if target_state.get("state") != "available":
                continue
            return {"state": "available", "role": "target"}
        return {"state": "invalid", "reason": "doc73_binding_invalid"}

    @staticmethod
    def _doc73_current_batch_plan_digest(request: Any, target_record: Any) -> str:
        """Read the frozen batch digest from server-owned review context."""

        sources = []
        request_metadata = getattr(request, "metadata", {}) if request is not None else {}
        if isinstance(request_metadata, dict):
            sources.append(request_metadata)
        target_metadata = getattr(target_record, "metadata", {}) if target_record is not None else {}
        if isinstance(target_metadata, dict):
            sources.append(target_metadata)
        for source in sources:
            value = str(source.get("doc73_batch_plan_digest") or "").strip().lower()
            if len(value) == 64 and all(character in "0123456789abcdef" for character in value):
                return value
        return ""

    def _doc73_source_record_is_valid(
        self,
        binding: dict[str, Any],
        output: Any,
        job_id: str,
        project_id: str,
        batch_plan_digest: str,
    ) -> bool:
        expected_project_id = project_id or str((getattr(output, "metadata", {}) or {}).get("project_id") or "").strip()
        if not validate_doc73_binding(
            binding,
            expected_job_id=job_id,
            expected_project_id=expected_project_id or None,
            expected_batch_plan_digest=batch_plan_digest,
            expected_output_id=str(getattr(output, "output_id", "") or "").strip(),
            expected_source_asset_id=str(binding.get("source_asset_id") or "").strip(),
            expected_source_plan_position=0,
            expected_source_candidate_id=str(getattr(output, "candidate_id", "") or "").strip(),
        ):
            return False
        state = self._persisted_file_state(
            output,
            "auto_batch_continuity",
            expected_integrity_id=str(binding.get("source_content_sha256") or ""),
        )
        return state.get("state") == "available"

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

    @staticmethod
    def _frozen_anchor_bindings(request: Any) -> dict[str, dict[str, str]]:
        """Read server-owned output/job/integrity bindings from context."""

        metadata = getattr(request, "metadata", {}) if request is not None else {}
        if not isinstance(metadata, dict):
            return {}

        bindings: dict[str, dict[str, str]] = {}

        def register(
            output_id: str,
            source_job_id: str,
            source_integrity_id: str,
            *,
            require_integrity: bool,
            job_invalid: bool,
            integrity_invalid: bool,
            job_missing: bool = False,
            integrity_missing: bool = False,
        ) -> None:
            if not output_id:
                return
            existing = bindings.get(output_id)
            if existing is None:
                bindings[output_id] = {
                    "source_job_id": source_job_id,
                    "source_integrity_id": source_integrity_id,
                    "require_integrity": "1" if require_integrity else "",
                    "job_invalid": "1" if job_invalid else "",
                    "integrity_invalid": "1" if integrity_invalid else "",
                    "job_missing": "1" if job_missing else "",
                    "integrity_missing": "1" if integrity_missing else "",
                }
                return
            if source_job_id:
                if existing["source_job_id"] and existing["source_job_id"] != source_job_id:
                    existing["source_job_id"] = ""
                    existing["job_invalid"] = "1"
                elif not existing["source_job_id"] and not existing["job_invalid"]:
                    existing["source_job_id"] = source_job_id
                    existing["job_missing"] = ""
            elif job_missing and not existing["source_job_id"] and not existing["job_invalid"]:
                existing["job_missing"] = "1"
            if source_integrity_id:
                if (
                    existing["source_integrity_id"]
                    and existing["source_integrity_id"] != source_integrity_id
                ):
                    existing["source_integrity_id"] = ""
                    existing["integrity_invalid"] = "1"
                elif not existing["source_integrity_id"] and not existing["integrity_invalid"]:
                    existing["source_integrity_id"] = source_integrity_id
                    existing["integrity_missing"] = ""
            elif integrity_missing and not existing["source_integrity_id"] and not existing["integrity_invalid"]:
                existing["integrity_missing"] = "1"
            if require_integrity:
                existing["require_integrity"] = "1"
            if job_invalid:
                existing["job_invalid"] = "1"
            if integrity_invalid:
                existing["integrity_invalid"] = "1"

        def add_binding(
            item: Any,
            *,
            output_keys: tuple[str, ...],
            require_canonical: bool,
            require_integrity: bool,
        ) -> None:
            # Snapshots include complete bindings plus compact view projections;
            # only explicit conflicts remain invalid when the complete claim exists.
            if not isinstance(item, dict):
                return
            nested = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            canonical = (
                item.get("canonical_output_binding") is True
                or nested.get("canonical_output_binding") is True
            )
            if require_canonical and not canonical:
                return
            output_id = next(
                (
                    str(item.get(key) or "").strip()
                    for key in output_keys
                    if str(item.get(key) or "").strip()
                ),
                "",
            )
            if not output_id:
                return
            source_job_values = [
                str(item.get(key) or "").strip()
                for key in ("source_job_id", "job_id", "created_from_job_id")
                if str(item.get(key) or "").strip()
            ]
            source_job_values.extend(
                str(nested.get(key) or "").strip()
                for key in ("source_job_id", "job_id", "created_from_job_id")
                if str(nested.get(key) or "").strip()
            )
            source_job_values = list(dict.fromkeys(source_job_values))
            source_integrity_values = [
                str(value or "").strip()
                for value in (
                    item.get("source_integrity_id"),
                    nested.get("source_integrity_id"),
                )
                if str(value or "").strip()
            ]
            normalized_integrities = list(
                dict.fromkeys(_normalize_integrity_digest(value) for value in source_integrity_values)
            )
            integrity_invalid = any(
                not _normalize_integrity_digest(value) for value in source_integrity_values
            ) or len(normalized_integrities) > 1
            integrity_missing = require_integrity and not normalized_integrities
            if not source_job_values:
                if not require_canonical:
                    return
                register(
                    output_id,
                    "",
                    normalized_integrities[0] if len(normalized_integrities) == 1 and not integrity_invalid else "",
                    require_integrity=require_integrity,
                    job_invalid=False,
                    integrity_invalid=integrity_invalid,
                    job_missing=True,
                    integrity_missing=integrity_missing,
                )
                return
            register(
                output_id,
                source_job_values[0] if len(source_job_values) == 1 else "",
                normalized_integrities[0] if len(normalized_integrities) == 1 and not integrity_invalid else "",
                require_integrity=require_integrity,
                job_invalid=len(source_job_values) > 1,
                integrity_invalid=integrity_invalid,
                integrity_missing=integrity_missing,
            )

        professional_references = metadata.get("professional_anchor_reference_assets", [])
        if isinstance(professional_references, list):
            for item in professional_references:
                add_binding(
                    item,
                    output_keys=("output_id", "created_from_output_id", "asset_id"),
                    require_canonical=False,
                    require_integrity=False,
                )

        snapshot = metadata.get("project_context_snapshot")
        if not isinstance(snapshot, dict):
            return bindings
        snapshot_metadata = snapshot.get("metadata")
        if (
            not isinstance(snapshot_metadata, dict)
            or snapshot_metadata.get("source") != "V3ProjectModeService"
        ):
            return bindings
        snapshot_project_id = str(snapshot.get("project_id") or "").strip()
        request_project_id = str(metadata.get("project_id") or "").strip()
        if not snapshot_project_id or (request_project_id and request_project_id != snapshot_project_id):
            return bindings

        for key in (
            "selected_output_assets",
            "selected_reference_assets",
            "selected_visual_references",
            "strong_reference_bindings",
        ):
            entries = snapshot.get(key)
            if not isinstance(entries, list):
                continue
            for item in entries:
                if not isinstance(item, dict):
                    continue
                item_project_id = str(item.get("project_id") or "").strip()
                if item_project_id and item_project_id != snapshot_project_id:
                    continue
                add_binding(
                    item,
                    output_keys=("output_id", "created_from_output_id"),
                    require_canonical=True,
                    require_integrity=True,
                )
        return bindings

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
        frozen_anchor_bindings: dict[str, dict[str, str]],
        current_job_id: str,
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

        if source_id in frozen_anchor_ids or source_id in frozen_anchor_bindings:
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
            if str(getattr(output, "output_id", "") or "").strip() != source_id:
                return {**base, "state": "invalid", "reason": "output_identity_binding"}
            binding = frozen_anchor_bindings.get(source_id)
            expected_source_job_id = binding.get("source_job_id") if binding is not None else None
            if expected_source_job_id is not None and (
                not expected_source_job_id
                or str(getattr(output, "job_id", "") or "").strip() != expected_source_job_id
            ):
                return {**base, "state": "invalid", "reason": "output_source_job_binding"}
            if str(getattr(output, "job_id", "") or "").strip() == current_job_id:
                return {**base, "state": "invalid", "reason": "reference_output_job_binding"}
            expected_integrity_id = None
            if binding is not None:
                if (
                    binding.get("job_invalid")
                    or binding.get("integrity_invalid")
                    or binding.get("job_missing")
                    or binding.get("integrity_missing")
                    or (
                        binding.get("require_integrity")
                        and not binding.get("source_integrity_id")
                    )
                ):
                    return {**base, "state": "invalid", "reason": "output_source_integrity_binding"}
                expected_integrity_id = binding.get("source_integrity_id") or None
            return {
                **base,
                **self._persisted_file_state(
                    output,
                    "selected_output",
                    expected_integrity_id=expected_integrity_id,
                ),
            }

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

    def _persisted_file_state(
        self,
        record: Any,
        source_type: str,
        *,
        expected_integrity_id: str | None = None,
    ) -> dict[str, Any]:
        path = Path(str(getattr(record, "file_path", "") or ""))
        if not path.is_file():
            return {"state": "unavailable", "file_path": str(path)}
        try:
            actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return {"state": "unavailable", "file_path": str(path)}
        stored_digest, stored_digest_invalid = _record_integrity_digest(record)
        if expected_integrity_id is not None:
            expected_digest = _normalize_integrity_digest(expected_integrity_id)
            if not expected_digest or expected_digest != actual_digest:
                return {
                    "state": "invalid",
                    "file_path": str(path),
                    "reason": f"{source_type}_source_integrity_binding",
                }
            if stored_digest_invalid or (stored_digest and stored_digest != actual_digest):
                return {
                    "state": "invalid",
                    "file_path": str(path),
                    "reason": f"{source_type}_content_integrity",
                }
        elif stored_digest_invalid or not stored_digest or stored_digest != actual_digest:
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
        expected_integrity_id: str | None = None,
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
        output_metadata = output_record.get("metadata") if isinstance(output_record.get("metadata"), dict) else {}
        asset_metadata = metadata.get("asset_metadata") if isinstance(metadata.get("asset_metadata"), dict) else {}
        candidate_metadata = metadata.get("candidate_metadata") if isinstance(metadata.get("candidate_metadata"), dict) else {}
        integrity_values = [
            output_record.get("content_sha256"),
            output_record.get("source_integrity_id"),
            output_metadata.get("content_sha256"),
            output_metadata.get("source_integrity_id"),
            metadata.get("content_sha256"),
            metadata.get("source_integrity_id"),
            asset_metadata.get("content_sha256"),
            asset_metadata.get("source_integrity_id"),
            candidate_metadata.get("content_sha256"),
            candidate_metadata.get("source_integrity_id"),
        ]
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return "unavailable", ["selected_output_unreadable"]
        declared_values = [
            str(value).strip()
            for value in integrity_values
            if str(value or "").strip()
        ]
        normalized_values = [
            _normalize_integrity_digest(value)
            for value in declared_values
        ]
        if any(not value for value in normalized_values):
            return "invalid", ["selected_output_content_integrity"]
        if len(set(normalized_values)) > 1:
            return "invalid", ["selected_output_content_integrity"]
        expected = _normalize_integrity_digest(expected_integrity_id)
        if expected and expected != actual:
            return "invalid", ["selected_output_content_integrity"]
        if normalized_values and normalized_values[0] != actual:
            return "invalid", ["selected_output_content_integrity"]
        if not normalized_values and not expected:
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
            dict.fromkeys(
                "review_evidence_"
                + (
                    str(item["reason"])
                    if str(item["reason"]).startswith(f"{name}_")
                    else f"{name}_{item['reason']}"
                )
                for item in entries
                if item.get("reason")
            )
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
        if entry.get("source_type") in {"selected_output", "auto_batch_continuity"}:
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


def _normalize_integrity_digest(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw.startswith("sha256:"):
        raw = raw.split(":", 1)[1].strip()
    if len(raw) != 64:
        return ""
    try:
        int(raw, 16)
    except ValueError:
        return ""
    return raw


def _record_integrity_digest(record: Any) -> tuple[str, bool]:
    metadata = getattr(record, "metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}
    values = [getattr(record, "content_sha256", None)]
    values.extend(metadata.get(key) for key in (
        "artifact_sha256",
        "content_sha256",
        "output_sha256",
        "original_sha256",
        "source_integrity_id",
    ))
    values = [str(value).strip() for value in values if str(value or "").strip()]
    if not values:
        return "", False
    normalized = [_normalize_integrity_digest(value) for value in values]
    if any(not value for value in normalized):
        return "", True
    unique = list(dict.fromkeys(normalized))
    if len(unique) != 1:
        return "", True
    return unique[0], False


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
