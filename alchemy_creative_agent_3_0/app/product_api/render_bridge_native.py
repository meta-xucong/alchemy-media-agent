"""Bounded, explicitly selected native receipt registration for fake-image.

The journal is an import deduplication/execution audit, NOT a billing ledger.
Real renderer profiles remain unavailable until their option contract is proven.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import time
from typing import Any
from uuid import uuid4

from PIL import Image

from ..generation_router.render_bridge_provider import RenderBridgeRegistration
from .render_bridge_facade import BridgeNativeFacadeError, NativeFreezeTarget, RenderBridgeNativeFacade, _digest


class NativeRenderBridgeGateway:
    def __init__(
        self,
        *,
        facade: RenderBridgeNativeFacade,
        service: Any,
        journal_root: Path,
        enabled: bool = False,
        project_service: Any | None = None,
    ) -> None:
        self.facade = facade
        self.service = service
        self.journal_root = Path(journal_root)
        self.enabled = enabled
        self.project_service = project_service

    def _enabled(self) -> None:
        if not self.enabled:
            raise BridgeNativeFacadeError("render_bridge_native_disabled", 404)

    def prepare(
        self, actor_user_id: int, target: NativeFreezeTarget, *, execution_profile_id: str = "fake-image"
    ) -> dict[str, Any]:
        self._enabled()
        if execution_profile_id != "fake-image":
            raise BridgeNativeFacadeError("render_bridge_profile_unverified")
        record, _project, _revision = self.facade._target(actor_user_id, target)
        marker = dict(record.request.metadata or {}).get("render_bridge_native_plan")
        if (
            not isinstance(marker, dict)
            or marker.get("schema_version") != "render_bridge_native_plan_v1"
            or marker.get("owner_user_id") != actor_user_id
            or marker.get("project_id") != target.project_id
        ):
            raise BridgeNativeFacadeError("render_bridge_native_plan_required")
        frozen = self.facade.freeze(actor_user_id, target)
        options = frozen["image_options"]
        if frozen["references"] or options != {
            "size": "1024x1024",
            "quality": "auto",
            "output_format": "png",
            "input_fidelity": None,
            "background": None,
            "moderation": None,
            "output_compression": None,
        }:
            raise BridgeNativeFacadeError("render_bridge_native_subset_unsupported")
        return {
            **frozen,
            "native_registration_connected": True,
            "submission_ready": True,
            "execution_profile_id": "fake-image",
            "execution_profile_revision": "1",
            "test_fixture": True,
            "blockers": [],
        }

    def _journal_path(self, actor_user_id: int, target: NativeFreezeTarget) -> Path:
        return self.journal_root / (_digest({"actor": actor_user_id, **asdict(target)}) + ".json")

    def _plan_project(self, actor_user_id: int, project_id: str):
        self._enabled()
        if self.project_service is None:
            raise BridgeNativeFacadeError("render_bridge_plan_service_unavailable", 503)
        project = self.project_service.project_store.get_project(project_id)
        if (
            type(actor_user_id) is not int
            or actor_user_id <= 0
            or project is None
            or project.metadata.get("veyra_user_id") != actor_user_id
            or str(project.status) != "active"
        ):
            raise BridgeNativeFacadeError("render_bridge_target_not_found", 404)
        return project

    def _plan_path(self, actor_user_id: int, project_id: str, plan_key: str) -> Path:
        if not isinstance(plan_key, str) or not plan_key.strip() or len(plan_key) > 128:
            raise BridgeNativeFacadeError("render_bridge_plan_key_invalid", 400)
        return self.journal_root / ("plan_" + _digest({"actor": actor_user_id, "project": project_id, "key": plan_key}) + ".json")

    def _lookup_plan(self, actor_user_id: int, project_id: str, journal: dict[str, Any]) -> dict[str, Any]:
        project = self._plan_project(actor_user_id, project_id)
        status = self.service.lookup_render_bridge_plan(
            project_id=project_id, owner_user_id=actor_user_id,
            user_input=journal["user_input"], plan_key=journal["plan_key"],
        )
        if status is None:
            return {"status": "plan_unknown", "plan_key": journal["plan_key"], "retry_safe": False}
        record = self.service.get_job_record(status.job_id)
        if record is None:
            return {"status": "plan_unknown", "plan_key": journal["plan_key"], "retry_safe": False}
        if status.job_id not in project.job_ids:
            # Reconcile only a proven durable plan. This call must take the
            # existing-record branch and cannot re-enter Brain planning.
            if project.updated_at != journal["project_revision"]:
                raise BridgeNativeFacadeError("render_bridge_target_revision_changed")
            self.project_service.create_render_bridge_plan(
                project_id=project_id, owner_user_id=actor_user_id,
                user_input=journal["user_input"], plan_key=journal["plan_key"],
            )
        plan = record.planning_result
        if plan is None or len(plan.series_plan.assets) != 1 or record.request.metadata.get("cancel_requested"):
            return {"status": "plan_blocked", "plan_key": journal["plan_key"], "job_id": record.job_id}
        return {
            "status": "planned",
            "plan_key": journal["plan_key"],
            "target": asdict(NativeFreezeTarget(project_id, record.job_id, plan.series_plan.assets[0].asset_id)),
        }

    def create_plan(
        self, actor_user_id: int, project_id: str, user_input: str, plan_key: str,
    ) -> dict[str, Any]:
        project = self._plan_project(actor_user_id, project_id)
        if not isinstance(user_input, str) or not user_input.strip() or len(user_input) > 16_000:
            raise BridgeNativeFacadeError("render_bridge_plan_input_invalid", 400)
        path = self._plan_path(actor_user_id, project_id, plan_key)
        with self._lock(path):
            journal = self._read(path)
            if journal is not None:
                if journal["user_input"] != user_input:
                    raise BridgeNativeFacadeError("render_bridge_plan_key_conflict")
                # Missing native outcome after a prior attempt is never an
                # instruction to repeat a possibly running Brain request.
                return self._lookup_plan(actor_user_id, project_id, journal)
            journal = {
                "status": "plan_intent", "plan_key": plan_key, "user_input": user_input,
                "project_revision": project.updated_at, "actor_user_id": actor_user_id, "project_id": project_id,
            }
            self._write(path, journal)
            try:
                self.project_service.create_render_bridge_plan(
                    project_id=project_id, owner_user_id=actor_user_id, user_input=user_input, plan_key=plan_key
                )
            except Exception:
                self._write(path, {**journal, "status": "plan_unknown"})
                return {"status": "plan_unknown", "plan_key": plan_key, "retry_safe": False}
            outcome = self._lookup_plan(actor_user_id, project_id, journal)
            self._write(path, {**journal, "status": outcome["status"], "outcome": outcome})
            return outcome

    def plan_status(self, actor_user_id: int, project_id: str, plan_key: str) -> dict[str, Any]:
        self._plan_project(actor_user_id, project_id)
        path = self._plan_path(actor_user_id, project_id, plan_key)
        with self._lock(path):
            journal = self._read(path)
            if journal is None:
                return {"status": "not_planned", "plan_key": plan_key}
            outcome = self._lookup_plan(actor_user_id, project_id, journal)
            self._write(path, {**journal, "status": outcome["status"], "outcome": outcome})
            return outcome

    def cancel_target(self, actor_user_id: int, target: NativeFreezeTarget) -> dict[str, Any]:
        self._enabled()
        self.facade._target(actor_user_id, target, require_eligible=False)
        with self._lock(self._journal_path(actor_user_id, target)):
            return self.service.cancel_render_bridge_plan(
                project_id=target.project_id, job_id=target.job_id, owner_user_id=actor_user_id
            )

    @contextmanager
    def _lock(self, path: Path):
        """One native target writer, cross-process; no database transaction spans review."""

        self.journal_root.mkdir(parents=True, exist_ok=True)
        with path.with_suffix(".lock").open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            deadline = time.monotonic() + 1.0
            while True:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise BridgeNativeFacadeError("render_bridge_registration_in_progress", 409) from None
                    time.sleep(0.025)
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _read(path: Path) -> dict[str, Any] | None:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
        try:
            temporary.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _assert_current(
        self, actor_user_id: int, target: NativeFreezeTarget, binding: RenderBridgeRegistration
    ) -> None:
        record, project, revision = self.facade._target(actor_user_id, target, require_eligible=False)
        metadata = dict(record.request.metadata or {})
        if str(project.status) != "active" or any(
            metadata.get(key) for key in ("cancel_requested", "canceled", "cancelled", "deleted_at")
        ):
            raise BridgeNativeFacadeError("render_bridge_target_not_eligible")
        if revision != binding.target_revision:
            raise BridgeNativeFacadeError("render_bridge_target_revision_changed")
        if str(record.status) != "planned" or record.generation_result is not None:
            native = (
                record.generation_result.metadata.get("render_bridge_registration")
                if record.generation_result is not None else None
            )
            if native != binding.safe_metadata() or str(record.status) not in {"finalizing", "generated", "blocked"}:
                raise BridgeNativeFacadeError("render_bridge_target_not_eligible")

    @staticmethod
    def _validate_artifact(artifact_bytes: bytes, original_sha256: str) -> None:
        if (
            not isinstance(artifact_bytes, bytes)
            or not 0 < len(artifact_bytes) <= 1_048_576
            or not isinstance(original_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", original_sha256)
            or hashlib.sha256(artifact_bytes).hexdigest() != original_sha256
        ):
            raise BridgeNativeFacadeError("render_bridge_artifact_hash_mismatch")
        try:
            with Image.open(BytesIO(artifact_bytes)) as image:
                if image.format != "PNG" or image.size != (1024, 1024) or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("unsupported image")
                image.verify()
        except Exception:
            raise BridgeNativeFacadeError("render_bridge_artifact_invalid") from None

    def _registered(
        self, path: Path, journal: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        audit = journal.get("execution_audit") or {
            "kind": "native_registration_execution_audit",
            "receipt_id": journal["binding"]["receipt_id"],
            "registration_key": journal["binding"]["registration_key"],
            "native_registration_ref": result["native_registration_ref"],
            "billing_event": False,
        }
        public = {**result, "execution_audit_count": 1, "retry_safe": False}
        # Persist the first native outcome. Subsequent replays return this same
        # registration receipt; current review progress is queried separately.
        if journal.get("status") == "registered":
            return dict(journal["outcome"])
        self._write(path, {**journal, "status": "registered", "outcome": public, "execution_audit": audit})
        return public

    def register_receipt(
        self,
        actor_user_id: int,
        target: NativeFreezeTarget,
        *,
        import_key: str,
        frozen_request_id: str,
        receipt_id: str,
        original_sha256: str,
        artifact_bytes: bytes,
        execution_profile_id: str = "fake-image",
    ) -> dict[str, Any]:
        self._enabled()
        self.facade._target(actor_user_id, target, require_eligible=False)
        if execution_profile_id != "fake-image":
            raise BridgeNativeFacadeError("render_bridge_profile_unverified")
        if any(not isinstance(value, str) or not value.strip() or len(value) > 256 for value in (import_key, receipt_id)):
            raise BridgeNativeFacadeError("render_bridge_receipt_identity_invalid", 400)
        self._validate_artifact(artifact_bytes, original_sha256)
        path = self._journal_path(actor_user_id, target)
        with self._lock(path):
            journal = self._read(path)
            if journal is None:
                frozen = self.prepare(actor_user_id, target, execution_profile_id=execution_profile_id)
                if frozen["frozen_request_id"] != frozen_request_id:
                    raise BridgeNativeFacadeError("render_bridge_frozen_request_changed")
                binding = RenderBridgeRegistration(
                    registration_key=_digest({"actor": actor_user_id, **asdict(target), "import_key": import_key}),
                    **asdict(target),
                    frozen_request_id=frozen_request_id,
                    target_revision=frozen["target_revision"],
                    prompt_sha256=frozen["prompt_sha256"],
                    receipt_id=receipt_id,
                    original_sha256=original_sha256,
                    execution_profile_id=execution_profile_id,
                )
                journal = {"status": "intent", "import_key": import_key, "binding": asdict(binding)}
                self._write(path, journal)
            else:
                binding = RenderBridgeRegistration(**journal["binding"])
                if (
                    journal["import_key"] != import_key
                    or binding.frozen_request_id != frozen_request_id
                    or binding.receipt_id != receipt_id
                    or binding.original_sha256 != original_sha256
                    or binding.execution_profile_id != execution_profile_id
                ):
                    raise BridgeNativeFacadeError("render_bridge_receipt_conflict")
                if journal["status"] == "rejected":
                    return dict(journal["outcome"])
            # Every retry queries the actual native checkpoint before any write.
            outcome = self.service.lookup_render_bridge_registration(binding)
            if outcome["status"] == "registered":
                return self._registered(path, journal, outcome)
            self._assert_current(actor_user_id, target, binding)
            try:
                outcome = self.service.register_render_bridge_result(
                    binding,
                    artifact_bytes,
                    assert_current=lambda: self._assert_current(actor_user_id, target, binding),
                )
            except BridgeNativeFacadeError as exc:
                outcome = {"status": "rejected", "reason_code": exc.code, "retry_safe": False}
                self._write(path, {**journal, "status": "rejected", "outcome": outcome})
                raise
            except Exception:
                # The service may have committed before its response was lost.
                # Do not retry here. The next query reconciles the same binding.
                outcome = {"status": "import_unknown", "reason_code": "native_outcome_unknown", "retry_safe": False}
                self._write(path, {**journal, "status": "import_unknown", "outcome": outcome})
                return outcome
            if outcome["status"] != "registered":
                outcome = {"status": "import_unknown", "reason_code": "native_outcome_unknown", "retry_safe": False}
                self._write(path, {**journal, "status": "import_unknown", "outcome": outcome})
                return outcome
            return self._registered(path, journal, outcome)

    def registration_status(
        self, actor_user_id: int, target: NativeFreezeTarget, *, import_key: str
    ) -> dict[str, Any]:
        self._enabled()
        self.facade._target(actor_user_id, target, require_eligible=False)
        path = self._journal_path(actor_user_id, target)
        with self._lock(path):
            journal = self._read(path)
            if journal is None:
                self.facade._target(actor_user_id, target)
                return {"status": "not_registered", "retry_safe": True}
            if journal["import_key"] != import_key:
                raise BridgeNativeFacadeError("render_bridge_receipt_conflict")
            if journal["status"] == "rejected":
                return dict(journal["outcome"])
            binding = RenderBridgeRegistration(**journal["binding"])
            outcome = self.service.lookup_render_bridge_registration(binding)
            if outcome["status"] == "registered":
                return self._registered(path, journal, outcome)
            self._assert_current(actor_user_id, target, binding)
            return {
                "status": "import_unknown",
                "reason_code": "native_checkpoint_incomplete",
                "retry_safe": outcome["status"] in {"not_registered", "output_checkpointed"},
            }
