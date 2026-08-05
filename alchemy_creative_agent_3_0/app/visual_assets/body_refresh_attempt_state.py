"""Private durable cursor for one reference-assisted Body refresh attempt.

This module is lifecycle bookkeeping, not a second candidate/review authority.
It freezes the already validated Body analysis context and records the latest
reviewed-candidate cursor so an official resume cannot restart candidate one.
CharacterCard remains the authority for shared review, formal receipts, and
cross-view parity.
"""

from __future__ import annotations

from datetime import UTC, datetime
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from typing import Any, Literal

from pydantic import ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator

from ..schemas.models import V3BaseModel
from .body_proportion_evidence_profile import BodyRefreshAnalysisContext
from .body_cross_view_review import BodyCrossViewReviewReceipt
from .character_card import (
    BODY_SLOT_KEYS,
    BodyRefreshAttemptIdentity,
    BodyRefreshPresentationIntent,
    BodySilhouetteBackdropPresentationContract,
    BodySilhouetteHairContinuityContract,
    BodySourceAdmission,
)
from .formal_slot_acceptance import FormalSlotReceipt


class BodyRefreshAttemptStateError(RuntimeError):
    """Closed failure for missing, stale, forged, or inconsistent state."""


class BodyRefreshCandidateCheckpoint(V3BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_key: Literal["body.front_full", "body.side_full", "body.rear_full"]
    candidate_index: StrictInt = Field(ge=1, le=3)
    attempt_round: StrictInt = Field(ge=1)
    candidate_digest: StrictStr
    review_status: Literal["pass", "fail"]
    review_receipt_digest: StrictStr
    # These are private durable identity bindings.  They deliberately do not
    # appear in safe_metadata(); resume must locate the one server-owned job
    # and output without exposing raw job/output identifiers publicly.
    operation_id: StrictStr
    output_id: StrictStr

    @field_validator("operation_id", "output_id")
    @classmethod
    def require_private_identity_token(cls, value: str) -> str:
        cleaned = str(value).strip()
        if not cleaned or not re.fullmatch(r"[A-Za-z0-9_.:-]+", cleaned):
            raise ValueError("body_refresh_private_identity_invalid")
        return cleaned

    @field_validator("candidate_digest", "review_receipt_digest")
    @classmethod
    def require_checkpoint_digest(cls, value: str) -> str:
        cleaned = str(value).strip().lower()
        if not _DIGEST_RE.fullmatch(cleaned):
            raise ValueError("body_refresh_checkpoint_digest_invalid")
        return cleaned


class BodyRefreshAttemptState(V3BaseModel):
    """Private safe state; raw source material is intentionally absent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["body_refresh_attempt_state_v1"] = (
        "body_refresh_attempt_state_v1"
    )
    state_id: StrictStr
    visual_asset_id: StrictStr
    attempt_identity: BodyRefreshAttemptIdentity
    analysis_context: BodyRefreshAnalysisContext
    body_source_admission: BodySourceAdmission
    presentation_intent: BodyRefreshPresentationIntent
    hair_continuity: BodySilhouetteHairContinuityContract
    backdrop: BodySilhouetteBackdropPresentationContract
    next_slot_key: Literal["body.front_full", "body.side_full", "body.rear_full"] | None
    next_candidate_index: StrictInt | None = Field(default=None, ge=1, le=3)
    candidate_checkpoints: tuple[BodyRefreshCandidateCheckpoint, ...] = ()
    analyzer_call_count: StrictInt = Field(ge=1)
    status: Literal[
        "in_progress",
        "interrupted",
        "awaiting_slot_acceptance",
        "awaiting_cross_view",
        "pending_refresh",
        "activated",
    ] = "in_progress"
    formal_receipt_digests: tuple[StrictStr, ...] = ()
    cross_view_parity_digest: StrictStr | None = None
    cross_view_review_receipt: BodyCrossViewReviewReceipt | None = None
    activation_digest: StrictStr | None = None
    updated_at: StrictStr

    @model_validator(mode="after")
    def validate_authority_boundary(self) -> "BodyRefreshAttemptState":
        if self.analysis_context.attempt_id != self.attempt_identity.attempt_id:
            raise ValueError("body_refresh_attempt_state_attempt_mismatch")
        if self.analysis_context.append_only_revision != self.attempt_identity.append_only_revision:
            raise ValueError("body_refresh_attempt_state_revision_mismatch")
        if self.analysis_context.source_mode != "reference_assisted":
            raise ValueError("body_refresh_attempt_state_source_mode_invalid")
        if len(self.body_source_admission.body_evidence_ids) != 5:
            raise ValueError("body_refresh_attempt_state_source_admission_invalid")
        if (
            self.analysis_context.source_evidence_id_digest
            != self.body_source_admission.source_evidence_id_digest()
        ):
            raise ValueError("body_refresh_attempt_state_source_digest_mismatch")
        expected_slots = list(BODY_SLOT_KEYS)
        seen: set[tuple[str, int]] = set()
        for checkpoint in self.candidate_checkpoints:
            key = (checkpoint.slot_key, checkpoint.candidate_index)
            if key in seen:
                raise ValueError("body_refresh_attempt_state_duplicate_candidate")
            seen.add(key)
        if self.status in {"pending_refresh", "awaiting_cross_view"} and self.next_slot_key is not None:
            raise ValueError("body_refresh_attempt_state_pending_cursor_invalid")
        if self.next_slot_key is not None and self.next_slot_key not in expected_slots:
            raise ValueError("body_refresh_attempt_state_slot_invalid")
        for digest in self.formal_receipt_digests:
            _require_digest(digest, "formal receipt digest")
        if self.cross_view_parity_digest is not None:
            _require_digest(self.cross_view_parity_digest, "cross-view parity digest")
            if self.cross_view_review_receipt is None:
                raise ValueError("body_refresh_cross_view_review_receipt_required")
            if not self.cross_view_review_receipt.activation_eligible:
                raise ValueError("body_refresh_cross_view_review_receipt_not_eligible")
            if self.cross_view_parity_digest != self.cross_view_review_receipt.receipt_digest:
                raise ValueError("body_refresh_cross_view_parity_receipt_mismatch")
            if self.status not in {"pending_refresh", "activated"}:
                raise ValueError("body_refresh_cross_view_parity_status_invalid")
        if self.cross_view_review_receipt is not None:
            if self.cross_view_review_receipt.attempt_id != self.attempt_identity.attempt_id:
                raise ValueError("body_refresh_cross_view_receipt_attempt_mismatch")
            if (
                self.cross_view_review_receipt.source_evidence_id_digest
                != self.body_source_admission.source_evidence_id_digest()
            ):
                raise ValueError("body_refresh_cross_view_receipt_source_mismatch")
        if self.activation_digest is not None:
            _require_digest(self.activation_digest, "activation digest")
            if self.status != "activated":
                raise ValueError("body_refresh_attempt_state_activation_status_invalid")
        if self.status == "activated" and self.activation_digest is None:
            raise ValueError("body_refresh_attempt_state_activation_digest_required")
        return self

    @property
    def reviewed_candidate_count(self) -> int:
        return len(self.candidate_checkpoints)

    def safe_metadata(self) -> dict[str, Any]:
        """Public-safe projection; no profile, admission IDs, or raw material."""

        return {
            "contract_version": self.contract_version,
            "state_id": self.state_id,
            "attempt_id": self.attempt_identity.attempt_id,
            "append_only_revision": self.attempt_identity.append_only_revision,
            "source_mode": self.analysis_context.source_mode,
            "source_binding_digest": self.analysis_context.source_binding_digest,
            "source_evidence_id_digest": self.analysis_context.source_evidence_id_digest,
            "profile_digest": self.analysis_context.profile_digest,
            "next_slot_key": self.next_slot_key,
            "next_candidate_index": self.next_candidate_index,
            "reviewed_candidate_count": self.reviewed_candidate_count,
            "analyzer_call_count": self.analyzer_call_count,
            "status": self.status,
            "cross_view_review_receipt_digest": (
                self.cross_view_review_receipt.receipt_digest
                if self.cross_view_review_receipt is not None
                else None
            ),
            "cross_view_review_status": (
                self.cross_view_review_receipt.status
                if self.cross_view_review_receipt is not None
                else None
            ),
            "activation_digest": self.activation_digest,
        }


class BodyRefreshAttemptStateStore:
    """Append-only private JSON state store for the refresh coordinator."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.root / ".transaction.lock"
        self._thread_lock = threading.RLock()

    @contextmanager
    def _transaction_lock(self):
        """Use advisory locking so a crashed process leaves no stale mutex."""

        with self._thread_lock:
            with self._lock_path.open("a+b") as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if os.name == "nt":
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _state_filename(visual_asset_id: str, attempt_id: str) -> str:
        key = hashlib.sha256(f"{visual_asset_id}\0{attempt_id}".encode("utf-8")).hexdigest()
        return f"body_refresh_attempt_{key}.json"

    @staticmethod
    def _pointer_filename(visual_asset_id: str) -> str:
        key = hashlib.sha256(visual_asset_id.encode("utf-8")).hexdigest()
        return f"body_refresh_current_{key}.json"

    def _path(self, visual_asset_id: str, attempt_id: str) -> Path:
        return self.root / self._state_filename(visual_asset_id, attempt_id)

    def _pointer_path(self, visual_asset_id: str) -> Path:
        return self.root / self._pointer_filename(visual_asset_id)

    def begin(
        self,
        *,
        visual_asset_id: str,
        attempt_identity: BodyRefreshAttemptIdentity,
        analysis_context: BodyRefreshAnalysisContext,
        body_source_admission: BodySourceAdmission,
        presentation_intent: BodyRefreshPresentationIntent | None = None,
        hair_continuity: BodySilhouetteHairContinuityContract | None = None,
        backdrop: BodySilhouetteBackdropPresentationContract | None = None,
        analyzer_call_count: int = 1,
    ) -> BodyRefreshAttemptState:
        if not isinstance(attempt_identity, BodyRefreshAttemptIdentity):
            raise BodyRefreshAttemptStateError("typed attempt identity required")
        if not isinstance(analysis_context, BodyRefreshAnalysisContext):
            raise BodyRefreshAttemptStateError("typed analysis context required")
        if not isinstance(body_source_admission, BodySourceAdmission):
            raise BodyRefreshAttemptStateError("typed Body source admission required")
        if presentation_intent is None:
            presentation_intent = BodyRefreshPresentationIntent()
        if hair_continuity is None:
            hair_continuity = BodySilhouetteHairContinuityContract()
        if backdrop is None:
            backdrop = BodySilhouetteBackdropPresentationContract()
        if not isinstance(presentation_intent, BodyRefreshPresentationIntent):
            raise BodyRefreshAttemptStateError("typed presentation intent required")
        if not isinstance(hair_continuity, BodySilhouetteHairContinuityContract):
            raise BodyRefreshAttemptStateError("typed hair continuity required")
        if not isinstance(backdrop, BodySilhouetteBackdropPresentationContract):
            raise BodyRefreshAttemptStateError("typed backdrop required")
        if analyzer_call_count != 1:
            raise BodyRefreshAttemptStateError("body refresh analyzer must be called exactly once")
        now = datetime.now(UTC).isoformat()
        state = BodyRefreshAttemptState(
            state_id=f"body_refresh_state_{hashlib.sha256(f'{visual_asset_id}\0{attempt_identity.attempt_id}'.encode()).hexdigest()[:32]}",
            visual_asset_id=visual_asset_id,
            attempt_identity=attempt_identity,
            analysis_context=analysis_context,
            body_source_admission=body_source_admission,
            presentation_intent=presentation_intent,
            hair_continuity=hair_continuity,
            backdrop=backdrop,
            next_slot_key="body.front_full",
            next_candidate_index=1,
            analyzer_call_count=analyzer_call_count,
            updated_at=now,
        )
        self._write(state)
        return state

    def _write(self, state: BodyRefreshAttemptState) -> None:
        path = self._path(state.visual_asset_id, state.attempt_identity.attempt_id)
        payload = json.dumps(
            state.model_dump(mode="json"), ensure_ascii=True, sort_keys=True, indent=2
        ).encode("utf-8")
        with self._transaction_lock():
            self._atomic_replace(path, payload)
            pointer_payload = json.dumps(
                {
                    "contract_version": "body_refresh_current_pointer_v1",
                    "visual_asset_id": state.visual_asset_id,
                    "attempt_id": state.attempt_identity.attempt_id,
                    "state_id": state.state_id,
                    "state_filename": path.name,
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            ).encode("utf-8")
            self._atomic_replace(self._pointer_path(state.visual_asset_id), pointer_payload)

    @staticmethod
    def _atomic_replace(path: Path, payload: bytes) -> None:
        temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temp.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)

    def load(self, *, visual_asset_id: str, attempt_id: str) -> BodyRefreshAttemptState:
        path = self._path(visual_asset_id, attempt_id)
        if not path.exists():
            raise BodyRefreshAttemptStateError("body refresh attempt state missing")
        try:
            return BodyRefreshAttemptState.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except BodyRefreshAttemptStateError:
            raise
        except Exception as exc:
            raise BodyRefreshAttemptStateError("body refresh attempt state invalid") from exc

    def load_current(self, *, visual_asset_id: str) -> BodyRefreshAttemptState:
        pointer_path = self._pointer_path(visual_asset_id)
        if not pointer_path.exists():
            raise BodyRefreshAttemptStateError("body refresh current pointer missing")
        try:
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise BodyRefreshAttemptStateError("body refresh current pointer invalid") from exc
        if not isinstance(pointer, dict) or set(pointer) != {
            "contract_version",
            "visual_asset_id",
            "attempt_id",
            "state_id",
            "state_filename",
        }:
            raise BodyRefreshAttemptStateError("body refresh current pointer invalid")
        if pointer.get("contract_version") != "body_refresh_current_pointer_v1":
            raise BodyRefreshAttemptStateError("body refresh current pointer contract invalid")
        if pointer.get("visual_asset_id") != visual_asset_id:
            raise BodyRefreshAttemptStateError("body refresh current pointer asset mismatch")
        attempt_id = pointer.get("attempt_id")
        state_filename = pointer.get("state_filename")
        if not isinstance(attempt_id, str) or not attempt_id:
            raise BodyRefreshAttemptStateError("body refresh current pointer attempt invalid")
        if state_filename != self._state_filename(visual_asset_id, attempt_id):
            raise BodyRefreshAttemptStateError("body refresh current pointer state mismatch")
        try:
            state = self.load(visual_asset_id=visual_asset_id, attempt_id=attempt_id)
        except BodyRefreshAttemptStateError:
            raise
        if (
            state.visual_asset_id != visual_asset_id
            or state.attempt_identity.attempt_id != attempt_id
            or state.state_id != pointer.get("state_id")
        ):
            raise BodyRefreshAttemptStateError("body refresh current pointer state mismatch")
        return state

    def checkpoint_reviewed_candidate(
        self,
        state: BodyRefreshAttemptState,
        *,
        slot_key: str,
        candidate_index: int,
        attempt_round: int,
        candidate_digest: str,
        review_status: str,
        review_receipt_digest: str,
        operation_id: str,
        output_id: str,
    ) -> BodyRefreshAttemptState:
        if review_status not in {"pass", "fail"}:
            raise BodyRefreshAttemptStateError("closed candidate review status required")
        _require_digest(candidate_digest, "candidate digest")
        _require_digest(review_receipt_digest, "review receipt digest")
        if type(attempt_round) is not int or attempt_round < 1:
            raise BodyRefreshAttemptStateError("candidate attempt round must be positive")
        _require_private_identity(operation_id, "operation id")
        _require_private_identity(output_id, "output id")
        if state.next_slot_key != slot_key or state.next_candidate_index != candidate_index:
            raise BodyRefreshAttemptStateError("body refresh candidate cursor mismatch")
        if any(
            item.slot_key == slot_key and item.candidate_index == candidate_index
            for item in state.candidate_checkpoints
        ):
            raise BodyRefreshAttemptStateError("body refresh candidate already checkpointed")
        checkpoint = BodyRefreshCandidateCheckpoint(
            slot_key=slot_key,
            candidate_index=candidate_index,
            attempt_round=attempt_round,
            candidate_digest=candidate_digest,
            review_status=review_status,  # type: ignore[arg-type]
            review_receipt_digest=review_receipt_digest,
            operation_id=operation_id,
            output_id=output_id,
        )
        checkpoints = (*state.candidate_checkpoints, checkpoint)
        if candidate_index < 3:
            next_slot_key = slot_key
            next_candidate_index = candidate_index + 1
            status: Literal["in_progress", "interrupted", "pending_refresh"] = "interrupted"
        else:
            next_slot_key = slot_key  # formal authority must accept this slot first
            next_candidate_index = None
            status = "awaiting_slot_acceptance"
        updated = state.model_copy(
            update={
                "candidate_checkpoints": checkpoints,
                "next_slot_key": next_slot_key,
                "next_candidate_index": next_candidate_index,
                "status": status,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        self._write(updated)
        return updated

    def reconcile_reviewed_candidate(
        self,
        state: BodyRefreshAttemptState,
        *,
        slot_key: str,
        candidate_index: int,
        attempt_round: int,
        candidate_digest: str,
        review_status: str,
        review_receipt_digest: str,
        operation_id: str,
        output_id: str,
    ) -> BodyRefreshAttemptState:
        """Refresh one existing candidate's review receipt without moving the cursor."""

        if review_status not in {"pass", "fail"}:
            raise BodyRefreshAttemptStateError("closed candidate review status required")
        _require_digest(candidate_digest, "candidate digest")
        _require_digest(review_receipt_digest, "review receipt digest")
        if type(attempt_round) is not int or attempt_round < 1:
            raise BodyRefreshAttemptStateError("candidate attempt round must be positive")
        _require_private_identity(operation_id, "operation id")
        _require_private_identity(output_id, "output id")
        matching = [
            item
            for item in state.candidate_checkpoints
            if item.slot_key == slot_key and item.candidate_index == candidate_index
        ]
        if len(matching) != 1:
            raise BodyRefreshAttemptStateError("body refresh checkpoint identity mismatch")
        existing = matching[0]
        if (
            existing.attempt_round != attempt_round
            or existing.candidate_digest != candidate_digest
            or existing.operation_id != operation_id
            or existing.output_id != output_id
        ):
            raise BodyRefreshAttemptStateError("body refresh checkpoint identity mismatch")
        updated_checkpoint = existing.model_copy(
            update={
                "review_status": review_status,
                "review_receipt_digest": review_receipt_digest,
            }
        )
        updated = state.model_copy(
            update={
                "candidate_checkpoints": tuple(
                    updated_checkpoint
                    if item.slot_key == slot_key and item.candidate_index == candidate_index
                    else item
                    for item in state.candidate_checkpoints
                ),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        self._write(updated)
        return updated

    def record_formal_receipt(
        self,
        state: BodyRefreshAttemptState,
        *,
        formal_receipt: FormalSlotReceipt,
    ) -> BodyRefreshAttemptState:
        if not isinstance(formal_receipt, FormalSlotReceipt):
            raise BodyRefreshAttemptStateError("typed formal slot receipt required")
        slot_key = formal_receipt.slot_key
        if formal_receipt.module != "body_silhouette":
            raise BodyRefreshAttemptStateError("Body formal receipt module mismatch")
        if formal_receipt.acceptance_mode != "standard_three_candidate":
            raise BodyRefreshAttemptStateError("Body formal receipt acceptance mode mismatch")
        if formal_receipt.reviewed_candidate_count != 3:
            raise BodyRefreshAttemptStateError("Body formal receipt requires three candidates")
        formal_receipt_digest = hashlib.sha256(
            json.dumps(
                formal_receipt.model_dump(mode="json"),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if state.status != "awaiting_slot_acceptance" or state.next_slot_key != slot_key:
            raise BodyRefreshAttemptStateError("formal receipt boundary mismatch")
        slot_items = [item for item in state.candidate_checkpoints if item.slot_key == slot_key]
        if len(slot_items) != 3:
            raise BodyRefreshAttemptStateError("formal receipt requires three reviewed candidates")
        slot_index = list(BODY_SLOT_KEYS).index(slot_key)
        if slot_index < len(BODY_SLOT_KEYS) - 1:
            next_slot_key: str | None = BODY_SLOT_KEYS[slot_index + 1]
            next_candidate_index: int | None = 1
            status: Literal["interrupted", "awaiting_cross_view", "pending_refresh"] = "interrupted"
        else:
            next_slot_key = None
            next_candidate_index = None
            status = "awaiting_cross_view"
        updated = state.model_copy(
            update={
                "formal_receipt_digests": (*state.formal_receipt_digests, formal_receipt_digest),
                "next_slot_key": next_slot_key,
                "next_candidate_index": next_candidate_index,
                "status": status,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        self._write(updated)
        return updated

    def record_cross_view_review(
        self,
        state: BodyRefreshAttemptState,
        *,
        receipt: BodyCrossViewReviewReceipt,
    ) -> BodyRefreshAttemptState:
        if not isinstance(receipt, BodyCrossViewReviewReceipt):
            raise BodyRefreshAttemptStateError("typed cross-view review receipt required")
        if state.status != "awaiting_cross_view":
            raise BodyRefreshAttemptStateError("cross-view parity boundary mismatch")
        try:
            receipt.require_binding(
                attempt_id=state.attempt_identity.attempt_id,
                source_evidence_id_digest=state.body_source_admission.source_evidence_id_digest(),
                view_output_ids=dict(receipt.view_output_ids),
            )
        except Exception as exc:
            raise BodyRefreshAttemptStateError("cross-view review receipt binding mismatch") from exc
        for slot_key, output_id in receipt.view_output_ids.items():
            if not any(
                checkpoint.slot_key == slot_key and checkpoint.output_id == output_id
                for checkpoint in state.candidate_checkpoints
            ):
                raise BodyRefreshAttemptStateError("cross-view review output checkpoint mismatch")
        update: dict[str, Any] = {
            "cross_view_review_receipt": receipt,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if receipt.activation_eligible:
            update.update(
                {
                    "cross_view_parity_digest": receipt.receipt_digest,
                    "status": "pending_refresh",
                }
            )
        updated = state.model_copy(
            update=update
        )
        self._write(updated)
        return updated

    def record_cross_view_parity(
        self,
        state: BodyRefreshAttemptState,
        *,
        parity_digest: str,
    ) -> BodyRefreshAttemptState:
        _require_digest(parity_digest, "cross-view parity digest")
        raise BodyRefreshAttemptStateError(
            "body refresh cross-view parity requires typed joint review receipt"
        )

    def record_activation(
        self,
        state: BodyRefreshAttemptState,
        *,
        activation_digest: str,
    ) -> BodyRefreshAttemptState:
        _require_digest(activation_digest, "activation digest")
        if state.status != "pending_refresh":
            raise BodyRefreshAttemptStateError("body refresh activation boundary mismatch")
        if state.cross_view_parity_digest is None or state.cross_view_review_receipt is None:
            raise BodyRefreshAttemptStateError("body refresh activation requires cross-view review receipt")
        if not state.cross_view_review_receipt.activation_eligible:
            raise BodyRefreshAttemptStateError("body refresh activation requires passing cross-view review")
        updated = state.model_copy(
            update={
                "activation_digest": activation_digest,
                "status": "activated",
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        self._write(updated)
        return updated


_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_digest(value: str, label: str) -> str:
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value.lower()):
        raise BodyRefreshAttemptStateError(f"{label} must be a 64-hex digest")
    return value.lower()


def _require_private_identity(value: str, label: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned or not re.fullmatch(r"[A-Za-z0-9_.:-]+", cleaned):
        raise BodyRefreshAttemptStateError(f"{label} must be a private identity token")
    return cleaned
