"""Opt-in, read-only V3 frozen-input facade for Render Bridge.

This is not a generation route or a native result importer. It only projects an
already approved, single-image Standard plan through the existing materializer.
Registration remains explicitly unavailable until native checkpoint, review and
usage authorities expose an outcome-queryable commit boundary.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from ..generation_router.providers import (
    ProductionImageGenerationProvider,
    build_provider_generation_request,
)
from ..reference_input_plan import PLAN_KEY, ReferenceInputPlan


class BridgeNativeFacadeError(ValueError):
    """Safe, bounded failure code; never expose storage paths or prompt errors."""

    def __init__(self, code: str, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class NativeFreezeTarget:
    project_id: str
    job_id: str
    asset_id: str


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()


class RenderBridgeNativeFacade:
    """Alchemy-owned facade composed from existing read-only service lookups.

    ``actor_user_id`` must come from the host's authenticated session, never a
    request body. Both project and job owners are checked on every operation.
    Unowned/auth-disabled targets are intentionally unsupported in this stage.
    No client, store, queue, worker, provider call or network access is created.
    """

    def __init__(
        self,
        *,
        get_job_record: Callable[[str], Any],
        get_project_record: Callable[[str], Any],
        enabled: bool = False,
        max_reference_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        self.enabled = enabled
        self._get_job = get_job_record
        self._get_project = get_project_record
        self._max_reference_bytes = max_reference_bytes

    def _target(
        self, actor_user_id: int, target: NativeFreezeTarget, *, require_eligible: bool = True
    ) -> tuple[Any, Any, str]:
        if not self.enabled:
            raise BridgeNativeFacadeError("render_bridge_native_disabled", 404)
        if type(actor_user_id) is not int or actor_user_id <= 0:
            raise BridgeNativeFacadeError("render_bridge_authenticated_owner_required", 403)
        if not isinstance(target, NativeFreezeTarget) or any(
            not isinstance(value, str) or not value.strip() for value in asdict(target).values()
        ):
            raise BridgeNativeFacadeError("render_bridge_target_invalid", 400)
        # Copy before materialization: the canonical materializer annotates its
        # request metadata, and live stores can return cached record objects.
        record = copy.deepcopy(self._get_job(target.job_id))
        project = copy.deepcopy(self._get_project(target.project_id))
        if record is None or project is None:
            raise BridgeNativeFacadeError("render_bridge_target_not_found", 404)
        metadata = dict(record.request.metadata or {})
        project_metadata = dict(project.metadata or {})
        if (
            record.job_id != target.job_id
            or project.project_id != target.project_id
            or metadata.get("project_id") != target.project_id
            or target.job_id not in project.job_ids
            or type(metadata.get("veyra_user_id")) is not int
            or metadata["veyra_user_id"] != actor_user_id
            or type(project_metadata.get("veyra_user_id")) is not int
            or project_metadata["veyra_user_id"] != actor_user_id
        ):
            raise BridgeNativeFacadeError("render_bridge_target_not_found", 404)
        if require_eligible and (
            str(project.status) != "active" or str(record.status) != "planned" or record.generation_result is not None
        ):
            raise BridgeNativeFacadeError("render_bridge_target_not_eligible")
        if require_eligible and any(metadata.get(key) for key in ("cancel_requested", "canceled", "cancelled", "deleted_at")):
            raise BridgeNativeFacadeError("render_bridge_target_not_eligible")
        if record.planning_result is None:
            raise BridgeNativeFacadeError("render_bridge_frozen_plan_missing")
        revision = _digest(
            {
                "target": asdict(target),
                "actor": actor_user_id,
                "request": record.request.model_dump(mode="json"),
                "planning_result": record.planning_result.model_dump(mode="json"),
                "project_updated_at": project.updated_at,
                "project_status": str(project.status),
                "project_owner": project_metadata["veyra_user_id"],
                "project_job_ids": list(project.job_ids),
            }
        )
        return record, project, revision

    def freeze(
        self,
        actor_user_id: int,
        target: NativeFreezeTarget,
        *,
        expected_revision: str | None = None,
    ) -> dict[str, Any]:
        """Return exact canonical input facts, not a runnable Bridge task."""

        public, _paths = self._freeze(actor_user_id, target, expected_revision=expected_revision)
        return public

    def _freeze(
        self,
        actor_user_id: int,
        target: NativeFreezeTarget,
        *,
        expected_revision: str | None = None,
    ) -> tuple[dict[str, Any], tuple[Path, ...]]:
        record, _project, revision = self._target(actor_user_id, target)
        if expected_revision is not None and expected_revision != revision:
            raise BridgeNativeFacadeError("render_bridge_target_revision_changed")
        plan = record.planning_result
        if len(plan.series_plan.assets) != 1 or plan.series_plan.assets[0].asset_id != target.asset_id:
            raise BridgeNativeFacadeError("render_bridge_single_image_target_required")
        if plan.creative_job.job_id != target.job_id:
            raise BridgeNativeFacadeError("render_bridge_frozen_plan_binding_invalid")

        def one(items: list[Any]) -> Any:
            matches = [item for item in items if item.asset_id == target.asset_id]
            if len(matches) != 1:
                raise BridgeNativeFacadeError("render_bridge_frozen_plan_incomplete")
            return matches[0]

        generation_plan = one(plan.generation_plans)
        try:
            logical = ReferenceInputPlan.from_dict(
                generation_plan.metadata.get(PLAN_KEY),
                job_id=target.job_id,
                project_id=target.project_id,
            )
            request_logical = ReferenceInputPlan.from_dict(
                record.request.metadata.get(PLAN_KEY),
                job_id=target.job_id,
                project_id=target.project_id,
            )
        except (TypeError, ValueError):
            raise BridgeNativeFacadeError("render_bridge_frozen_reference_plan_missing") from None
        if logical.as_dict() != request_logical.as_dict():
            raise BridgeNativeFacadeError("render_bridge_frozen_reference_plan_mismatch")
        # Standard's existing direct path explicitly does not create crops.
        # Professional/legacy derivative construction is not a read-only seam.
        if logical.as_dict()["project_mode"] != "standard":
            raise BridgeNativeFacadeError("render_bridge_readonly_mode_unsupported")
        if generation_plan.metadata.get("project_id") != target.project_id:
            raise BridgeNativeFacadeError("render_bridge_frozen_plan_binding_invalid")
        if generation_plan.metadata.get("generation_channel", "provider") != "provider":
            raise BridgeNativeFacadeError("render_bridge_existing_channel_unsupported")
        if generation_plan.metadata.get("requested_image_count", 1) != 1:
            raise BridgeNativeFacadeError("render_bridge_single_image_target_required")
        # Bound reads before invoking the shared materializer, which verifies
        # exact bytes/order against this server-owned reference plan itself.
        for source in logical.references(verify_bytes=False):
            content = self._read_reference_bytes(Path(source["file_path"]))
            if hashlib.sha256(content).hexdigest() != source["content_sha256"]:
                raise BridgeNativeFacadeError("render_bridge_reference_changed")
        request = build_provider_generation_request(
            asset_spec=plan.series_plan.assets[0],
            layout_plan=one(plan.layout_plans),
            prompt_compilation=one(plan.prompt_compilations),
            condition_plan=one(plan.condition_plans),
            generation_plan=generation_plan,
            job_id=target.job_id,
        )
        materializer = ProductionImageGenerationProvider(output_store=object())
        try:
            materialization = materializer.materialize_final_prompt(request)
        except Exception:
            raise BridgeNativeFacadeError("render_bridge_canonical_materialization_blocked") from None
        if materialization.prompt_source != "remote_brain_canonical":
            raise BridgeNativeFacadeError("render_bridge_brain_approval_required")
        if hashlib.sha256(materialization.generation_prompt.encode("utf-8")).hexdigest() != materialization.prompt_sha256:
            raise BridgeNativeFacadeError("render_bridge_prompt_integrity_mismatch")
        paths: list[Path] = []
        references: list[dict[str, Any]] = []
        for index, item in enumerate(materialization.reference_assets):
            path = Path(item["file_path"])
            content = self._read_reference_bytes(path)
            content_hash = hashlib.sha256(content).hexdigest()
            paths.append(path)
            references.append(
                {
                    "reference_id": f"reference_{index}_{content_hash}",
                    "asset_id": item.get("asset_id"),
                    "index": index,
                    "sha256": content_hash,
                    "size_bytes": len(content),
                    "mime_type": item.get("mime_type"),
                    "role": item.get("role"),
                    "source_type": item.get("source_type"),
                    "truth_layers": list(item.get("truth_layers") or []),
                    "reference_truth_layer": item.get("reference_truth_layer"),
                    "forbidden_inheritance_channels": list(item.get("forbidden_inheritance_channels") or []),
                }
            )
        contract = {
            "prompt": materialization.generation_prompt,
            "prompt_sha256": materialization.prompt_sha256,
            "prompt_source": materialization.prompt_source,
            "operation": "image_edit" if references else "image_generate",
            "references": references,
            "image_options": {
                "size": materialization.size,
                "quality": materialization.quality,
                "output_format": materialization.output_format,
                "input_fidelity": materialization.input_fidelity,
                "background": materialization.background,
                "moderation": materialization.moderation,
                "output_compression": materialization.output_compression,
            },
        }
        # Re-read after materialization, not after dispatch: this facade never
        # dispatches. A changed/canceled/deleted target cannot yield a snapshot.
        _latest, _latest_project, latest_revision = self._target(actor_user_id, target)
        if latest_revision != revision:
            raise BridgeNativeFacadeError("render_bridge_target_revision_changed")
        return {
            "schema_version": "alchemy_render_bridge_frozen_input_v1",
            "status": "frozen",
            "target": asdict(target),
            "target_revision": revision,
            "frozen_request_id": "rb_freeze_" + _digest({"revision": revision, "contract": contract}),
            **contract,
            "native_registration_connected": False,
            "submission_ready": False,
            "blockers": [
                "native_registration_unavailable",
                "bridge_v1_rendering_options_not_negotiated",
            ],
        }, tuple(paths)

    def _read_reference_bytes(self, path: Path) -> bytes:
        try:
            if not path.is_file() or path.stat().st_size > self._max_reference_bytes:
                raise BridgeNativeFacadeError("render_bridge_reference_unavailable")
            with path.open("rb") as handle:
                content = handle.read(self._max_reference_bytes + 1)
            if not content or len(content) > self._max_reference_bytes:
                raise BridgeNativeFacadeError("render_bridge_reference_unavailable")
            return content
        except OSError:
            raise BridgeNativeFacadeError("render_bridge_reference_unavailable") from None

    def read_reference(
        self,
        actor_user_id: int,
        target: NativeFreezeTarget,
        *,
        frozen_request_id: str,
        reference_id: str,
    ) -> tuple[bytes, str]:
        """Recheck current authority and hash; never accept a caller file path."""

        snapshot, paths = self._freeze(actor_user_id, target)
        if snapshot["frozen_request_id"] != frozen_request_id:
            raise BridgeNativeFacadeError("render_bridge_frozen_request_changed")
        for reference, path in zip(snapshot["references"], paths, strict=True):
            if reference["reference_id"] == reference_id:
                content = self._read_reference_bytes(path)
                if hashlib.sha256(content).hexdigest() != reference["sha256"]:
                    raise BridgeNativeFacadeError("render_bridge_reference_changed")
                # Authority is checked again after the file read.
                self._target_revision(actor_user_id, target, snapshot["target_revision"])
                return content, reference["mime_type"] or "application/octet-stream"
        raise BridgeNativeFacadeError("render_bridge_reference_not_found", 404)

    def _target_revision(self, actor_user_id: int, target: NativeFreezeTarget, revision: str) -> None:
        _record, _project, current = self._target(actor_user_id, target)
        if current != revision:
            raise BridgeNativeFacadeError("render_bridge_target_revision_changed")

    def registration_status(
        self, actor_user_id: int, target: NativeFreezeTarget, *, import_key: str
    ) -> dict[str, Any]:
        """Unavailable is not 'not found' and must never authorize a retry."""

        self._target(actor_user_id, target)
        if not isinstance(import_key, str) or not import_key.strip() or len(import_key) > 256:
            raise BridgeNativeFacadeError("render_bridge_import_key_invalid", 400)
        return {
            "status": "blocked",
            "reason_code": "native_registration_unavailable",
            "native_registration_connected": False,
            "native_registration_ref": None,
            "retry_safe": False,
            "effect": "none",
        }

    def register_receipt(
        self, actor_user_id: int, target: NativeFreezeTarget, *, import_key: str
    ) -> dict[str, Any]:
        """Explicitly reject registration; no artifacts or receipts are stored."""

        return self.registration_status(actor_user_id, target, import_key=import_key)
