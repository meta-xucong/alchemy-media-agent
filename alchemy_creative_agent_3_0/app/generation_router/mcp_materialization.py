"""Shared, explicit MCP image handoff storage for V3.

The legacy Codex relay is intentionally conversation-only.  This module is
the separate opt-in materialized channel: V3 freezes the canonical renderer
contract, a local MCP client submits the resulting image bytes, and the
ordinary V3 provider adapter consumes those bytes.  It never writes a V3
candidate or delivery record by itself.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
from io import BytesIO
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import time
from typing import Any

from ..creative_core.mcp_reference_partition import McpBodyReferencePartition
from ..creative_core.rules import stable_id
from ..visual_assets.body_silhouette_source_standard import (
    BODY_SILHOUETTE_MCP_CLOTHING_ABSENCE_FINDING,
    body_silhouette_mcp_materialization_channel_contract,
    body_silhouette_mcp_materialization_prompt_findings,
    body_silhouette_integrated_whole_person_synthesis_contract,
)
from ..visual_assets.body_proportion_evidence_profile import BodyMorphologyEvidenceProfile
from ..visual_assets.character_card import (
    BodySilhouetteBackdropPresentationContract,
    BodySilhouetteHairContinuityContract,
    BodyRefreshPresentationIntent,
    unspecified_body_refresh_presentation_intent,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


_BODY_RENDERER_EXECUTION_DIRECTIVE_SCHEMA = "v3_body_mcp_renderer_execution_directive_v1"
_BODY_RENDERER_EXECUTION_RECEIPT_SCHEMA = "v3_body_mcp_renderer_execution_receipt_v1"

_BODY_RENDERER_PRESENTATION_PHRASES = {
    "short_sleeve_top": "plain short-sleeve top",
    "shorts": "shorts with legs visible",
    "barefoot": "completely barefoot, no shoes or socks",
}
_BODY_RENDERER_BACKDROP_PHRASES = {
    "solid_white": (
        "perfectly uniform pure solid white backdrop, no gray, no gradient, "
        "no floor, no shadow"
    ),
}

_BODY_MORPHOLOGY_RENDERER_PHRASES = {
    "relative_head_to_stature": {
        "larger": "a relatively larger head-to-stature relationship",
        "proportional": "a proportionate head-to-stature relationship",
        "smaller": "a relatively smaller head-to-stature relationship",
    },
    "shoulder_to_head": {
        "narrower": "shoulders narrower relative to the head",
        "proportional": "shoulders proportionate to the head",
        "wider": "shoulders wider relative to the head",
    },
    "torso_to_leg": {
        "shorter_torso": "a shorter torso relative to leg length",
        "proportional": "a proportionate torso-to-leg relationship",
        "longer_torso": "a longer torso relative to leg length",
    },
    "arm_to_leg": {
        "relatively_shorter": "relatively shorter arms against leg length",
        "proportional": "a proportionate arm-to-leg relationship",
        "relatively_longer": "relatively longer arms against leg length",
    },
    "build": {
        "slender": "a slender natural build",
        "medium": "a medium natural build",
        "sturdy": "a sturdy natural build",
    },
    "neck_shoulder": {
        "narrow_transition": "a narrow natural neck-to-shoulder transition",
        "proportional_transition": "a proportionate natural neck-to-shoulder transition",
        "wide_transition": "a wide natural neck-to-shoulder transition",
    },
    "developmental_stage_context": {
        "early_stage_context": "the frozen early developmental-stage body context",
        "middle_stage_context": "the frozen middle developmental-stage body context",
        "later_stage_context": "the frozen later developmental-stage body context",
        "adult_stage_context": "the frozen adult developmental-stage body context",
        "unknown_stage_context": "no unsupported developmental-stage claim",
    },
    "stance_ground": {
        "grounded_full_contact": "natural full-contact standing and weight bearing",
        "toe_weighted_contact": "natural toe-weighted contact and balanced weight bearing",
        "dynamic_contact": "natural dynamic ground contact and weight transfer",
    },
    "cross_view_support": {
        "multi_view_supported": "the same morphology across front, side, and rear views",
        "front_back_supported": "the same morphology across the supported front and rear views",
        "front_only": "only the morphology supported by the front view",
    },
}


def _canonical_json_sha256(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_body_renderer_execution_directive(
    *,
    canonical_prompt_sha256: str,
    rendering_contract_fingerprint: str,
    nonce: str,
    rendering_contract: dict[str, Any],
) -> dict[str, Any]:
    """Compile the closed Body contract into a renderer-owned directive.

    The Brain canonical prompt and its hash remain immutable.  This separate
    directive is the only server-owned execution context that may add the
    closed Body presentation/backdrop/hair constraints for a renderer.  It
    carries no Body evidence hashes, paths, raw prompt, or provider payload.
    """

    intent = dict(rendering_contract.get("body_refresh_presentation_intent") or {})
    backdrop = dict(rendering_contract.get("body_silhouette_backdrop_presentation_contract") or {})
    hair = dict(rendering_contract.get("body_silhouette_hair_continuity_contract") or {})
    channel = dict(
        rendering_contract.get("body_silhouette_mcp_materialization_channel_contract") or {}
    )
    integrated = rendering_contract.get(
        "body_silhouette_integrated_whole_person_synthesis_contract"
    )
    if integrated != body_silhouette_integrated_whole_person_synthesis_contract():
        raise McpMaterializationError(
            "mcp_materialization_renderer_execution_directive_invalid"
        )
    morphology = rendering_contract.get("body_morphology_profile")
    if rendering_contract.get("body_refresh_source_mode") == "reference_assisted":
        if not isinstance(morphology, dict):
            raise McpMaterializationError(
                "mcp_materialization_body_morphology_profile_missing"
            )
        try:
            bands = dict(morphology["bands"])
            BodyMorphologyEvidenceProfile.model_validate(
                {
                    "contract_version": "body_morphology_evidence_profile_v2",
                    "source_mode": "reference_assisted",
                    "source_truth_layer": "body_proportion_truth",
                    **bands,
                    "source_count": 5,
                    "analysis_receipt": {
                        "owner": "server_owned_body_proportion_analysis",
                        "status": "complete",
                        "analysis_provider": "configured_body_source_analysis_provider",
                    },
                }
            )
            if not isinstance(morphology.get("profile_digest"), str) or len(morphology["profile_digest"]) != 64:
                raise ValueError("profile digest")
            bands_digest = _canonical_json_sha256(bands)
            if morphology.get("bands_digest") != bands_digest:
                raise ValueError("bands digest")
        except Exception as exc:
            raise McpMaterializationError(
                "mcp_materialization_body_morphology_profile_invalid"
            ) from exc
    elif morphology is not None:
        raise McpMaterializationError(
            "mcp_materialization_body_morphology_profile_forbidden"
        )
    directive: dict[str, Any] = {
        "schema_version": _BODY_RENDERER_EXECUTION_DIRECTIVE_SCHEMA,
        "execution_scope": "professional_character_card_body_silhouette_mcp_materialization_only",
        "canonical_prompt_sha256": str(canonical_prompt_sha256),
        "rendering_contract_fingerprint": str(rendering_contract_fingerprint),
        "nonce_sha256": _sha256(str(nonce).encode("utf-8")),
        "source_mode": rendering_contract.get("body_refresh_source_mode"),
        "physical_reference_policy": "face_identity_only",
        "presentation": {
            "top": intent.get("top_presentation"),
            "bottom": intent.get("bottom_presentation"),
            "footwear": intent.get("footwear_presentation"),
        },
        "backdrop": backdrop.get("backdrop"),
        "hair_continuity": {
            "source": hair.get("source"),
            "required_continuity": list(hair.get("required_continuity") or []),
            "allowed_variation": list(hair.get("allowed_variation") or []),
            "forbidden": list(hair.get("forbidden") or []),
            "scope": hair.get("scope"),
        },
        "body_silhouette_execution_constraints": {
            "allowed_body_owned_channels": list(channel.get("allowed_body_owned_channels") or []),
            "face_identity_reference_scope": channel.get("face_identity_reference_scope"),
            "body_reference_scope": channel.get("body_reference_scope"),
            "source_mode_scope": list(channel.get("source_mode_scope") or []),
        },
        "integrated_whole_person_synthesis": integrated,
    }
    if morphology is not None:
        directive["body_morphology_profile"] = morphology
    try:
        top_phrase = _BODY_RENDERER_PRESENTATION_PHRASES[directive["presentation"]["top"]]
        bottom_phrase = _BODY_RENDERER_PRESENTATION_PHRASES[directive["presentation"]["bottom"]]
        footwear_phrase = _BODY_RENDERER_PRESENTATION_PHRASES[directive["presentation"]["footwear"]]
        backdrop_phrase = _BODY_RENDERER_BACKDROP_PHRASES[directive["backdrop"]]
    except KeyError as exc:
        raise McpMaterializationError(
            "mcp_materialization_renderer_execution_directive_invalid"
        ) from exc
    directive["materialization_prompt"] = (
        "Execute the closed server-owned Body Silhouette renderer directive exactly. "
        f"Render a {top_phrase}. Render {bottom_phrase}. Render the subject {footwear_phrase}. "
        f"Use a {backdrop_phrase}. "
        "Preserve hair from the current Face Identity references with the same "
        "hairstyle category, same hair length tier, same bangs-or-parting pattern, "
        "and same overall hair outline. Use Face identity references only as physical "
        "inputs; Body proportion evidence is analysis-only. "
        "Synthesize one coherent whole person in one natural body chain from head, "
        "neck, shoulders, torso, and limbs; preserve anatomical head-neck-shoulder "
        "continuity, natural asymmetry, weight bearing, joint placement, and ground "
        "contact. Never paste, swap, or composite a head onto a body; never use a "
        "mannequin or cardboard stance."
    )
    if isinstance(morphology, dict):
        bands = morphology["bands"]
        try:
            morphology_phrases = [
                _BODY_MORPHOLOGY_RENDERER_PHRASES[field][bands[field]]
                for field in _BODY_MORPHOLOGY_RENDERER_PHRASES
            ]
        except KeyError as exc:
            raise McpMaterializationError(
                "mcp_materialization_renderer_execution_directive_invalid"
            ) from exc
        directive["materialization_prompt"] += (
            " Apply the closed Body morphology profile as one integrated person: "
            + "; ".join(morphology_phrases)
            + "."
        )
    directive["directive_sha256"] = _canonical_json_sha256(directive)
    return directive


def build_body_renderer_execution_receipt(
    *,
    renderer_prompt_sha256: str,
    renderer_execution_directive_sha256: str,
    canonical_prompt_sha256: str,
    rendering_contract_fingerprint: str,
    nonce_sha256: str,
    reference_asset_hashes: list[str],
) -> dict[str, Any]:
    """Return the typed host receipt required by strict Body MCP submit."""

    receipt = {
        "schema_version": _BODY_RENDERER_EXECUTION_RECEIPT_SCHEMA,
        "status": "executed",
        "execution_scope": "professional_character_card_body_silhouette_mcp_materialization_only",
        "renderer_prompt_sha256": str(renderer_prompt_sha256).strip().lower(),
        "renderer_execution_directive_sha256": str(renderer_execution_directive_sha256).strip().lower(),
        "canonical_prompt_sha256": str(canonical_prompt_sha256).strip().lower(),
        "rendering_contract_fingerprint": str(rendering_contract_fingerprint).strip().lower(),
        "nonce_sha256": str(nonce_sha256).strip().lower(),
        "physical_reference_policy": "face_identity_only",
        "reference_asset_hashes": [str(item).strip().lower() for item in reference_asset_hashes],
        "consumed_renderer_prompt": True,
        "consumed_renderer_execution_directive": True,
        "applied_body_presentation_contract": True,
        "applied_body_hair_continuity_contract": True,
        "applied_body_backdrop_contract": True,
        "applied_integrated_whole_person_contract": True,
    }
    receipt["receipt_sha256"] = _canonical_json_sha256(receipt)
    return receipt


def _validate_image(content: bytes) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            return image.size
    except Exception as exc:
        raise ValueError("MCP artifact is not a valid image") from exc


def _parse_size(value: object) -> tuple[int, int] | None:
    raw = str(value or "").strip().lower()
    if not raw or raw == "auto" or "x" not in raw:
        return None
    left, right = raw.split("x", 1)
    try:
        width = int(left)
        height = int(right)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def _normalize_image_size(
    content: bytes,
    *,
    image_format: str,
    target_size: tuple[int, int],
) -> bytes:
    """Fit an MCP image into the frozen rendering size on a white matte canvas.

    This is a transport parity operation, not a creative edit: it never invents
    pixels for the subject and never crops the submitted image.  It only scales
    the submitted artifact down/up to fit inside the Provider-equivalent canvas.
    """

    try:
        from PIL import Image

        target_width, target_height = target_size
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        with Image.open(BytesIO(content)) as image:
            source = image.convert("RGBA")
        source.thumbnail((target_width, target_height), resampling)
        canvas = Image.new("RGBA", (target_width, target_height), (255, 255, 255, 255))
        offset = ((target_width - source.width) // 2, (target_height - source.height) // 2)
        canvas.alpha_composite(source, offset)
        output = BytesIO()
        if image_format == "jpeg":
            canvas.convert("RGB").save(output, format="JPEG", quality=95)
        elif image_format == "webp":
            canvas.save(output, format="WEBP", quality=95)
        else:
            canvas.save(output, format="PNG")
        return output.getvalue()
    except Exception as exc:
        raise ValueError("MCP artifact could not be normalized to the rendering size") from exc


def _default_root() -> Path:
    configured = os.getenv("ALCHEMY_V3_MCP_MATERIALIZATION_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / ".media_storage" / "v3_mcp_materializations"


class McpMaterializationError(ValueError):
    """Safe local handoff contract failure."""

    def __init__(self, code: str, message: str | None = None, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.detail = dict(detail or {})


class McpMaterializationHandoffStore:
    """Append-only-ish pending handoffs; one artifact may be consumed once."""

    schema_version = "v3_mcp_materialization_handoff_v1"
    max_artifact_bytes = 50 * 1024 * 1024

    def __init__(self, storage_root: str | Path | None = None) -> None:
        self.storage_root = Path(storage_root) if storage_root else _default_root()
        self._lock = threading.RLock()

    @contextmanager
    def _transaction_lock(self):
        """Serialize durable handoff state transitions across processes.

        ``threading.RLock`` only protects one Python process.  MCP handoff
        records are durable state and can be touched by the foreground Codex
        submitter, a Product API worker, and a resume process at the same time.
        Hold a small store-level file lock around read-check-write transitions
        so a second process always observes the latest committed state before
        deciding whether a transition is idempotent, conflicting, or allowed.
        """

        with self._lock:
            self.storage_root.mkdir(parents=True, exist_ok=True)
            lock_path = self.storage_root / ".mcp_handoff_store.lock"
            with lock_path.open("a+b") as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                deadline = time.monotonic() + 10.0
                locked = False
                while not locked:
                    try:
                        handle.seek(0)
                        if os.name == "nt":
                            import msvcrt

                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        else:  # pragma: no cover - exercised on non-Windows CI.
                            import fcntl

                            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        locked = True
                    except OSError as exc:
                        if time.monotonic() >= deadline:
                            raise McpMaterializationError(
                                "mcp_materialization_store_lock_timeout"
                            ) from exc
                        time.sleep(0.025)
                try:
                    yield
                finally:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:  # pragma: no cover - exercised on non-Windows CI.
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def ensure_pending(
        self,
        *,
        operation_id: str,
        prompt: str,
        prompt_sha256: str,
        reference_assets: list[dict[str, Any]],
        rendering_contract: dict[str, Any],
        require_body_rendering_contract: bool = False,
    ) -> dict[str, Any]:
        operation = str(operation_id or "").strip()
        prompt_hash = str(prompt_sha256 or "").strip().lower()
        if not operation or not prompt_hash or not str(prompt or "").strip():
            raise McpMaterializationError("mcp_materialization_contract_incomplete")
        hashes = self._reference_hashes(reference_assets)
        reference_fingerprint = self._reference_semantic_fingerprint(reference_assets, hashes)
        safe_rendering_contract = self._safe_rendering_contract(
            rendering_contract,
            require_body_rendering_contract=require_body_rendering_contract,
        )
        strict_body = (
            require_body_rendering_contract is True
            and isinstance(safe_rendering_contract, dict)
            and safe_rendering_contract.get("body_silhouette_mcp_materialization_channel_contract")
            is not None
            and safe_rendering_contract.get("body_refresh_source_mode")
            in {"inference_first", "reference_assisted"}
        )
        if strict_body:
            prompt_findings = body_silhouette_mcp_materialization_prompt_findings(prompt)
            if BODY_SILHOUETTE_MCP_CLOTHING_ABSENCE_FINDING in prompt_findings:
                raise McpMaterializationError(
                    "mcp_materialization_body_clothing_absence_contract_invalid",
                    detail={
                        "failure_code": "character_card_body_mcp_clothing_absence_contract_invalid",
                        "fallback": "blocked",
                    },
                )
        rendering_fingerprint = self._rendering_contract_fingerprint(safe_rendering_contract)
        with self._transaction_lock():
            for revision in range(1, 1000):
                handoff_id = stable_id(
                    "mcp_handoff",
                    operation,
                    prompt_hash,
                    reference_fingerprint,
                    *(("rev", str(revision)) if revision > 1 else ()),
                )
                path = self._record_path(handoff_id)
                existing = self._read(handoff_id)
                if existing is not None:
                    self._validated_renderer_execution_directive(existing)
                    if str(existing.get("prompt_sha256") or "") != prompt_hash:
                        raise McpMaterializationError("mcp_materialization_prompt_mismatch")
                    if existing.get("reference_asset_hashes") != hashes:
                        raise McpMaterializationError("mcp_materialization_reference_mismatch")
                    existing_reference_fingerprint = self._existing_reference_semantic_fingerprint(existing)
                    existing_rendering_fingerprint = self._existing_rendering_contract_fingerprint(existing)
                    contract_mismatch = (
                        bool(existing_reference_fingerprint)
                        and existing_reference_fingerprint != reference_fingerprint
                    ) or (
                        bool(existing_rendering_fingerprint)
                        and existing_rendering_fingerprint != rendering_fingerprint
                    )
                    existing_status = str(existing.get("status") or "").strip().lower()
                    if contract_mismatch:
                        if existing_status == "pending":
                            continue
                        if existing_status == "submitted":
                            raise McpMaterializationError("mcp_materialization_contract_mismatch")
                        if existing_status != "consumed":
                            raise McpMaterializationError("mcp_materialization_contract_mismatch")
                    if str(existing.get("status") or "").strip().lower() != "consumed":
                        return existing
                    continue
                break
            else:
                raise McpMaterializationError("mcp_materialization_revision_exhausted")
            nonce = secrets.token_urlsafe(24)
            renderer_directive = None
            if require_body_rendering_contract:
                renderer_directive = _build_body_renderer_execution_directive(
                    canonical_prompt_sha256=prompt_hash,
                    rendering_contract_fingerprint=rendering_fingerprint,
                    nonce=nonce,
                    rendering_contract=safe_rendering_contract,
                )
            payload = {
                "schema_version": self.schema_version,
                "handoff_id": handoff_id,
                "operation_id": operation,
                "revision": revision,
                "status": "pending",
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "nonce": nonce,
                "canonical_prompt": str(prompt),
                "prompt_sha256": prompt_hash,
                "reference_assets": self._safe_reference_contract(reference_assets, hashes),
                "reference_asset_hashes": hashes,
                "reference_semantic_fingerprint": reference_fingerprint,
                "rendering_contract": safe_rendering_contract,
                "rendering_contract_fingerprint": rendering_fingerprint,
                **(
                    {
                        "renderer_execution_directive": renderer_directive,
                        "renderer_execution_directive_sha256": renderer_directive["directive_sha256"],
                    }
                    if renderer_directive is not None
                    else {}
                ),
                "artifact_file": None,
                "artifact_sha256": None,
                "artifact_format": None,
                "artifact_mime_type": None,
                "consumed_at": None,
            }
            self._write(path, payload)
            return payload

    def get(self, handoff_id: str) -> dict[str, Any] | None:
        with self._transaction_lock():
            return self._read(handoff_id)

    def list_unconsumed_by_operation(self, operation_id: str) -> list[dict[str, Any]]:
        """Return pending/submitted handoffs for one frozen operation.

        This is an internal recovery seam for interrupted MCP materialization
        flows.  The operation id is already scoped by the caller to a specific
        asset/module/slot/candidate/round; callers must still decide whether a
        returned handoff is safe to consume for their stage.
        """

        operation = str(operation_id or "").strip()
        if not operation:
            return []
        with self._transaction_lock():
            if not self.storage_root.is_dir():
                return []
            matches: list[dict[str, Any]] = []
            for path in self.storage_root.glob("mcp_handoff_*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(payload, dict) or payload.get("schema_version") != self.schema_version:
                    continue
                if str(payload.get("operation_id") or "").strip() != operation:
                    continue
                if str(payload.get("status") or "").strip().lower() not in {"pending", "submitted"}:
                    continue
                matches.append(payload)
            return sorted(
                matches,
                key=lambda item: (
                    int(item.get("revision") or 0),
                    str(item.get("created_at") or ""),
                    str(item.get("handoff_id") or ""),
                ),
            )

    def public_view(self, handoff_id: str) -> dict[str, Any]:
        payload = self.get(handoff_id)
        if payload is None:
            raise McpMaterializationError("mcp_materialization_not_found")
        return self._public_view_from_payload(payload)

    def public_renderer_request(self, handoff_id: str) -> dict[str, Any]:
        """Build the single typed request that the host passes to ImageGen.

        The caller must not concatenate the Brain prompt and renderer
        directive itself.  This boundary validates the frozen handoff first,
        then returns the canonical prompt unchanged alongside a separately
        hashed renderer prompt.  Body evidence remains in the typed contract
        and never becomes a physical renderer reference.
        """

        public = self.public_view(handoff_id)
        return self._renderer_request_from_public_view(public)

    @staticmethod
    def _renderer_request_from_public_view(public: dict[str, Any]) -> dict[str, Any]:
        directive = public.get("renderer_execution_directive")
        canonical_prompt = str(public.get("canonical_prompt") or "")
        if not isinstance(directive, dict):
            renderer_prompt = canonical_prompt
        else:
            renderer_prompt = (
                canonical_prompt
                + "\n\n"
                + str(directive.get("materialization_prompt") or "")
            )
        request = {
            "handoff_id": public["handoff_id"],
            "nonce": public["nonce"],
            "canonical_prompt": canonical_prompt,
            "canonical_prompt_sha256": public["prompt_sha256"],
            "renderer_prompt": renderer_prompt,
            "renderer_prompt_sha256": _sha256(renderer_prompt.encode("utf-8")),
            "reference_assets": public["reference_assets"],
            "reference_asset_hashes": public["reference_asset_hashes"],
            "rendering_contract_fingerprint": public.get("rendering_contract_fingerprint"),
            "renderer_execution_directive": directive,
            "renderer_execution_directive_sha256": public.get("renderer_execution_directive_sha256"),
        }
        return request

    @classmethod
    def _validated_renderer_execution_directive(
        cls,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        contract = payload.get("rendering_contract")
        if not isinstance(contract, dict):
            return None
        strict_body = (
            contract.get("body_silhouette_mcp_materialization_channel_contract") is not None
            and contract.get("body_refresh_source_mode") in {"inference_first", "reference_assisted"}
        )
        if not strict_body:
            return None
        raw_directive = payload.get("renderer_execution_directive")
        if not isinstance(raw_directive, dict):
            raise McpMaterializationError(
                "mcp_materialization_renderer_execution_directive_missing"
            )
        rendering_fingerprint = str(payload.get("rendering_contract_fingerprint") or "").strip().lower()
        computed_rendering_fingerprint = cls._rendering_contract_fingerprint(contract)
        if rendering_fingerprint and rendering_fingerprint != computed_rendering_fingerprint:
            raise McpMaterializationError(
                "mcp_materialization_renderer_execution_directive_mismatch"
            )
        rendering_fingerprint = computed_rendering_fingerprint
        expected = _build_body_renderer_execution_directive(
            canonical_prompt_sha256=str(payload.get("prompt_sha256") or ""),
            rendering_contract_fingerprint=rendering_fingerprint,
            nonce=str(payload.get("nonce") or ""),
            rendering_contract=contract,
        )
        if raw_directive != expected or str(payload.get("renderer_execution_directive_sha256") or "") != str(
            expected["directive_sha256"]
        ):
            raise McpMaterializationError(
                "mcp_materialization_renderer_execution_directive_mismatch"
            )
        return expected

    @classmethod
    def _validate_submitted_renderer_prompt_hash(
        cls,
        payload: dict[str, Any],
        directive: dict[str, Any] | None,
    ) -> str | None:
        if directive is None:
            return None
        public = cls._public_view_from_payload(payload)
        expected = cls._renderer_request_from_public_view(public)["renderer_prompt_sha256"]
        stored = str(payload.get("renderer_prompt_sha256") or "").strip().lower()
        if not stored:
            raise McpMaterializationError(
                "mcp_materialization_renderer_prompt_hash_missing"
            )
        if stored != str(expected).lower():
            raise McpMaterializationError(
                "mcp_materialization_renderer_prompt_hash_mismatch"
            )
        return stored

    @classmethod
    def _validated_renderer_execution_receipt(
        cls,
        payload: dict[str, Any],
        directive: dict[str, Any] | None,
        *,
        renderer_prompt_sha256: str | None = None,
        receipt: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if directive is None:
            return None
        public = cls._public_view_from_payload(payload)
        expected_request = cls._renderer_request_from_public_view(public)
        stored_prompt_hash = str(
            renderer_prompt_sha256 or payload.get("renderer_prompt_sha256") or ""
        ).strip().lower()
        expected = build_body_renderer_execution_receipt(
            renderer_prompt_sha256=stored_prompt_hash,
            renderer_execution_directive_sha256=str(directive["directive_sha256"]),
            canonical_prompt_sha256=str(payload.get("prompt_sha256") or ""),
            rendering_contract_fingerprint=str(payload.get("rendering_contract_fingerprint") or ""),
            nonce_sha256=str(directive.get("nonce_sha256") or ""),
            reference_asset_hashes=list(payload.get("reference_asset_hashes") or []),
        )
        raw_receipt = receipt if receipt is not None else payload.get("renderer_execution_receipt")
        if not isinstance(raw_receipt, dict):
            raise McpMaterializationError(
                "mcp_materialization_renderer_execution_receipt_required"
            )
        if stored_prompt_hash != str(expected_request["renderer_prompt_sha256"]).lower():
            raise McpMaterializationError(
                "mcp_materialization_renderer_prompt_hash_mismatch"
            )
        if raw_receipt != expected:
            raise McpMaterializationError(
                "mcp_materialization_renderer_execution_receipt_mismatch"
            )
        return dict(expected)

    @staticmethod
    def _public_view_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
        # The endpoint is local-only, but still return only the fields Codex
        # needs to call ImageGen and submit one image.  No raw response or
        # internal Provider credentials are part of this contract.
        directive = McpMaterializationHandoffStore._validated_renderer_execution_directive(payload)
        view = {
            "schema_version": "v3_mcp_materialization_public_v1",
            "handoff_id": payload["handoff_id"],
            "operation_id": payload["operation_id"],
            "status": payload["status"],
            "nonce": payload["nonce"],
            "canonical_prompt": payload["canonical_prompt"],
            "prompt_sha256": payload["prompt_sha256"],
            "reference_assets": payload["reference_assets"],
            "reference_asset_hashes": payload["reference_asset_hashes"],
            "rendering_contract": payload["rendering_contract"],
            "rendering_contract_fingerprint": payload.get("rendering_contract_fingerprint"),
            "artifact_sha256": payload.get("artifact_sha256"),
            "artifact_format": payload.get("artifact_format"),
        }
        if directive is not None:
            view["renderer_execution_directive"] = directive
            view["renderer_execution_directive_sha256"] = directive["directive_sha256"]
            if payload.get("renderer_prompt_sha256"):
                view["renderer_prompt_sha256"] = payload["renderer_prompt_sha256"]
            if isinstance(payload.get("renderer_execution_receipt"), dict):
                view["renderer_execution_receipt"] = dict(payload["renderer_execution_receipt"])
        return view

    def submit(
        self,
        handoff_id: str,
        *,
        nonce: str,
        prompt_sha256: str,
        reference_asset_hashes: list[str],
        artifact_bytes: bytes,
        renderer_prompt_sha256: str | None = None,
        renderer_execution_directive_sha256: str | None = None,
        renderer_execution_receipt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._transaction_lock():
            payload = self._read(handoff_id)
            if payload is None:
                raise McpMaterializationError("mcp_materialization_not_found")
            directive = self._validated_renderer_execution_directive(payload)
            if directive is not None:
                expected_host_request = self._renderer_request_from_public_view(
                    self._public_view_from_payload(payload)
                )
                if not renderer_prompt_sha256:
                    raise McpMaterializationError(
                        "mcp_materialization_renderer_prompt_hash_required"
                    )
                if str(renderer_prompt_sha256).strip().lower() != str(
                    expected_host_request["renderer_prompt_sha256"]
                ).lower():
                    raise McpMaterializationError(
                        "mcp_materialization_renderer_prompt_hash_mismatch"
                    )
                if not renderer_execution_directive_sha256:
                    raise McpMaterializationError(
                        "mcp_materialization_renderer_execution_directive_hash_required"
                    )
                if str(renderer_execution_directive_sha256).strip().lower() != str(
                    directive["directive_sha256"]
                ).lower():
                    raise McpMaterializationError(
                        "mcp_materialization_renderer_execution_directive_hash_mismatch"
                    )
                safe_renderer_execution_receipt = self._validated_renderer_execution_receipt(
                    payload,
                    directive,
                    renderer_prompt_sha256=str(renderer_prompt_sha256).strip().lower(),
                    receipt=renderer_execution_receipt,
                )
            else:
                safe_renderer_execution_receipt = None
            if str(nonce or "") != str(payload.get("nonce") or ""):
                raise McpMaterializationError("mcp_materialization_nonce_invalid")
            if str(prompt_sha256 or "").strip().lower() != str(payload.get("prompt_sha256") or ""):
                raise McpMaterializationError("mcp_materialization_prompt_mismatch")
            expected_refs = list(payload.get("reference_asset_hashes") or [])
            if list(reference_asset_hashes or []) != expected_refs:
                raise McpMaterializationError("mcp_materialization_reference_mismatch")
            status = str(payload.get("status") or "").strip().lower()
            content = bytes(artifact_bytes or b"")
            if not content or len(content) > self.max_artifact_bytes:
                raise McpMaterializationError("mcp_materialization_artifact_invalid")
            try:
                width, height = _validate_image(content)
            except Exception as exc:
                raise McpMaterializationError(
                    "mcp_materialization_artifact_invalid",
                    "The submitted artifact is not a readable image.",
                ) from exc
            image_format, mime_type = self._image_format(content)
            expected_format = str((payload.get("rendering_contract") or {}).get("output_format") or "png").lower()
            if image_format != expected_format:
                raise McpMaterializationError("mcp_materialization_output_format_mismatch")
            contract = dict(payload.get("rendering_contract") or {})
            expected_size = _parse_size(contract.get("size"))
            original_width, original_height = width, height
            original_sha256 = _sha256(content)
            size_normalization: dict[str, Any] | None = None
            if expected_size is not None and (width, height) != expected_size:
                policy = str(contract.get("size_normalization") or "").strip()
                if policy != "white_matte_contain_to_contract_size":
                    raise McpMaterializationError(
                        "mcp_materialization_output_size_mismatch",
                        detail={
                            "expected_width": expected_size[0],
                            "expected_height": expected_size[1],
                            "artifact_width": width,
                            "artifact_height": height,
                        },
                    )
                try:
                    content = _normalize_image_size(
                        content,
                        image_format=image_format,
                        target_size=expected_size,
                    )
                    width, height = _validate_image(content)
                except Exception as exc:
                    raise McpMaterializationError(
                        "mcp_materialization_output_size_normalization_failed",
                        "The submitted artifact could not be normalized to the frozen rendering size.",
                    ) from exc
                size_normalization = {
                    "policy": policy,
                    "original_width": original_width,
                    "original_height": original_height,
                    "target_width": expected_size[0],
                    "target_height": expected_size[1],
                    "result_width": width,
                    "result_height": height,
                }
            artifact_sha256 = _sha256(content)
            if status in {
                "submitted",
                "consumed",
                "consumed_uncheckpointed",
                "output_checkpointed",
                "job_checkpointed",
            }:
                if str(payload.get("artifact_sha256") or "") == artifact_sha256:
                    self._validate_submitted_renderer_prompt_hash(payload, directive)
                    self._validated_renderer_execution_receipt(payload, directive)
                    return self._public_view_from_payload(payload)
                raise McpMaterializationError("mcp_materialization_artifact_conflict")
            if status != "pending":
                raise McpMaterializationError("mcp_materialization_status_invalid")
            artifact_path = self._artifact_path(str(payload["handoff_id"]), image_format)
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_bytes(content)
            updated = {
                **payload,
                "status": "submitted",
                "updated_at": _now_iso(),
                "artifact_file": str(artifact_path),
                "artifact_sha256": artifact_sha256,
                "artifact_format": image_format,
                "artifact_mime_type": mime_type,
                "artifact_width": width,
                "artifact_height": height,
                **(
                    {"renderer_prompt_sha256": str(renderer_prompt_sha256).strip().lower()}
                    if directive is not None
                    else {}
                ),
                **(
                    {"renderer_execution_receipt": safe_renderer_execution_receipt}
                    if safe_renderer_execution_receipt is not None
                    else {}
                ),
                **(
                    {
                        "artifact_original_sha256": original_sha256,
                        "artifact_size_normalization": size_normalization,
                    }
                    if size_normalization is not None
                    else {}
                ),
            }
            self._write(self._record_path(str(payload["handoff_id"])), updated)
            return self._public_view_from_payload(updated)

    def consume(self, handoff_id: str, *, expected_checkpoint: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._transaction_lock():
            payload = self._read(handoff_id)
            if payload is None:
                raise McpMaterializationError("mcp_materialization_not_found")
            directive = self._validated_renderer_execution_directive(payload)
            status = str(payload.get("status") or "").strip().lower()
            if status not in {
                "submitted",
                "consumed",
                "consumed_uncheckpointed",
                "output_checkpointed",
                "job_checkpointed",
            }:
                raise McpMaterializationError("mcp_materialization_pending")
            self._validate_submitted_renderer_prompt_hash(payload, directive)
            self._validated_renderer_execution_receipt(payload, directive)
            artifact_file = Path(str(payload.get("artifact_file") or ""))
            if not artifact_file.is_file():
                raise McpMaterializationError("mcp_materialization_artifact_missing")
            content = artifact_file.read_bytes()
            if _sha256(content) != str(payload.get("artifact_sha256") or ""):
                raise McpMaterializationError("mcp_materialization_artifact_changed")
            expected = {
                str(key): str(value)
                for key, value in dict(expected_checkpoint or {}).items()
                if str(value or "").strip()
            }
            existing_checkpoint = (
                dict(payload.get("mcp_checkpoint"))
                if isinstance(payload.get("mcp_checkpoint"), dict)
                else {}
            )
            for key in {"job_id", "candidate_id", "output_id"}:
                if (
                    expected.get(key)
                    and existing_checkpoint.get(key)
                    and str(existing_checkpoint.get(key)) != str(expected[key])
                ):
                    raise McpMaterializationError("mcp_materialization_checkpoint_mismatch")
            if status == "submitted":
                updated = {
                    **payload,
                    "status": "consumed_uncheckpointed",
                    "updated_at": _now_iso(),
                    "consumed_at": _now_iso(),
                    "mcp_checkpoint": {
                        "status": "consumed_uncheckpointed",
                        "operation_id": str(payload.get("operation_id") or ""),
                        "handoff_id": str(payload.get("handoff_id") or ""),
                        "artifact_file": str(artifact_file),
                        "artifact_sha256": str(payload.get("artifact_sha256") or ""),
                        **expected,
                    },
                }
                self._write(self._record_path(str(payload["handoff_id"])), updated)
            else:
                updated = payload
            return {
                "artifact_base64": base64.b64encode(content).decode("ascii"),
                "artifact_format": updated.get("artifact_format") or "png",
                "artifact_mime_type": updated.get("artifact_mime_type") or "image/png",
                "artifact_sha256": updated.get("artifact_sha256"),
                "checkpoint_status": updated.get("status"),
                "expected_checkpoint": (
                    dict(updated.get("mcp_checkpoint"))
                    if isinstance(updated.get("mcp_checkpoint"), dict)
                    else expected
                ),
                "output_checkpoint": (
                    dict(updated.get("output_checkpoint"))
                    if isinstance(updated.get("output_checkpoint"), dict)
                    else None
                ),
            }

    def mark_output_checkpoint(
        self,
        handoff_id: str,
        *,
        job_id: str,
        candidate_id: str,
        output_id: str,
        artifact_sha256: str | None = None,
    ) -> dict[str, Any]:
        with self._transaction_lock():
            payload = self._read(handoff_id)
            if payload is None:
                raise McpMaterializationError("mcp_materialization_not_found")
            status = str(payload.get("status") or "").strip().lower()
            if status not in {"consumed_uncheckpointed", "output_checkpointed", "job_checkpointed"}:
                raise McpMaterializationError("mcp_materialization_checkpoint_order_invalid")
            checkpoint = {
                "status": "output_checkpointed",
                "operation_id": str(payload.get("operation_id") or ""),
                "handoff_id": str(payload.get("handoff_id") or ""),
                "job_id": str(job_id or ""),
                "candidate_id": str(candidate_id or ""),
                "output_id": str(output_id or ""),
                "artifact_sha256": str(artifact_sha256 or payload.get("artifact_sha256") or ""),
            }
            existing = payload.get("output_checkpoint")
            if isinstance(existing, dict):
                comparable_keys = {"job_id", "candidate_id", "output_id", "artifact_sha256"}
                for key in comparable_keys:
                    if str(existing.get(key) or "") and str(existing.get(key) or "") != str(checkpoint.get(key) or ""):
                        raise McpMaterializationError("mcp_materialization_output_checkpoint_mismatch")
            updated = {
                **payload,
                "status": "job_checkpointed" if status == "job_checkpointed" else "output_checkpointed",
                "updated_at": _now_iso(),
                "output_checkpoint": {**checkpoint, **(existing if isinstance(existing, dict) else {})},
                "mcp_checkpoint": self._merge_checkpoint_without_rollback(
                    payload,
                    checkpoint,
                    preserve_job=status == "job_checkpointed",
                ),
            }
            self._write(self._record_path(str(payload["handoff_id"])), updated)
            return updated

    def mark_job_checkpoint(
        self,
        handoff_id: str,
        *,
        job_id: str,
        candidate_id: str | None = None,
        output_id: str | None = None,
        generation_result_id: str | None = None,
    ) -> dict[str, Any]:
        with self._transaction_lock():
            payload = self._read(handoff_id)
            if payload is None:
                raise McpMaterializationError("mcp_materialization_not_found")
            status = str(payload.get("status") or "").strip().lower()
            if status not in {"output_checkpointed", "job_checkpointed"}:
                raise McpMaterializationError("mcp_materialization_checkpoint_order_invalid")
            output_checkpoint = (
                dict(payload.get("output_checkpoint"))
                if isinstance(payload.get("output_checkpoint"), dict)
                else {}
            )
            if output_checkpoint:
                if str(job_id or "") and str(output_checkpoint.get("job_id") or "") != str(job_id or ""):
                    raise McpMaterializationError("mcp_materialization_job_checkpoint_mismatch")
                if candidate_id and str(output_checkpoint.get("candidate_id") or "") != str(candidate_id):
                    raise McpMaterializationError("mcp_materialization_job_checkpoint_mismatch")
                if output_id and str(output_checkpoint.get("output_id") or "") != str(output_id):
                    raise McpMaterializationError("mcp_materialization_job_checkpoint_mismatch")
            existing_job_checkpoint = (
                dict(payload.get("job_checkpoint"))
                if isinstance(payload.get("job_checkpoint"), dict)
                else {}
            )
            job_checkpoint = {
                "status": "job_checkpointed",
                "operation_id": str(payload.get("operation_id") or ""),
                "handoff_id": str(payload.get("handoff_id") or ""),
                "job_id": str(job_id or output_checkpoint.get("job_id") or ""),
                "candidate_id": str(candidate_id or output_checkpoint.get("candidate_id") or ""),
                "output_id": str(output_id or output_checkpoint.get("output_id") or ""),
                "generation_result_id": str(generation_result_id or ""),
            }
            if existing_job_checkpoint:
                comparable_keys = {"job_id", "candidate_id", "output_id", "generation_result_id"}
                for key in comparable_keys:
                    if (
                        str(existing_job_checkpoint.get(key) or "")
                        and str(job_checkpoint.get(key) or "")
                        and str(existing_job_checkpoint.get(key) or "")
                        != str(job_checkpoint.get(key) or "")
                    ):
                        raise McpMaterializationError("mcp_materialization_job_checkpoint_mismatch")
                job_checkpoint = {**job_checkpoint, **existing_job_checkpoint}
            updated = {
                **payload,
                "status": "job_checkpointed",
                "updated_at": _now_iso(),
                "job_checkpoint": job_checkpoint,
                "mcp_checkpoint": self._merge_checkpoint_without_rollback(payload, job_checkpoint),
            }
            self._write(self._record_path(str(payload["handoff_id"])), updated)
            return updated

    @staticmethod
    def _merge_checkpoint_without_rollback(
        payload: dict[str, Any],
        checkpoint: dict[str, Any],
        *,
        preserve_job: bool = False,
    ) -> dict[str, Any]:
        merged = {
            **(
                dict(payload.get("mcp_checkpoint"))
                if isinstance(payload.get("mcp_checkpoint"), dict)
                else {}
            ),
            **checkpoint,
        }
        if preserve_job and isinstance(payload.get("job_checkpoint"), dict):
            merged.update(dict(payload["job_checkpoint"]))
            merged["status"] = "job_checkpointed"
        return merged

    def _record_path(self, handoff_id: str) -> Path:
        value = str(handoff_id or "")
        if not value.startswith("mcp_handoff_") or "/" in value or "\\" in value:
            raise McpMaterializationError("mcp_materialization_id_invalid")
        return self.storage_root / f"{value}.json"

    def _artifact_path(self, handoff_id: str, image_format: str) -> Path:
        suffix = {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}[image_format]
        return self.storage_root / f"{handoff_id}.artifact{suffix}"

    def _read(self, handoff_id: str) -> dict[str, Any] | None:
        path = self._record_path(handoff_id)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError:
            return None
        except json.JSONDecodeError as exc:
            raise McpMaterializationError("mcp_materialization_record_corrupt") from exc
        return payload if isinstance(payload, dict) and payload.get("schema_version") == self.schema_version else None

    def _write(self, path: Path, payload: dict[str, Any]) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(
            f"{path.name}.{os.getpid()}.{threading.get_ident()}.{secrets.token_hex(8)}.tmp"
        )
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        for attempt in range(5):
            try:
                temp.replace(path)
                return
            except PermissionError:
                if attempt >= 4:
                    temp.unlink(missing_ok=True)
                    raise
                time.sleep(0.05 * (attempt + 1))

    @staticmethod
    def _reference_hashes(reference_assets: list[dict[str, Any]]) -> list[str]:
        hashes: list[str] = []
        for item in reference_assets:
            data = dict(item or {})
            declared = str(data.get("sha256") or data.get("content_sha256") or "").strip().lower()
            path = str(data.get("file_path") or data.get("storage_path") or "").strip()
            if not declared and path and Path(path).is_file():
                declared = _sha256(Path(path).read_bytes())
            if not declared:
                raise McpMaterializationError("mcp_materialization_reference_hash_missing")
            hashes.append(declared)
        return hashes

    @staticmethod
    def _safe_reference_contract(reference_assets: list[dict[str, Any]], hashes: list[str]) -> list[dict[str, Any]]:
        safe: list[dict[str, Any]] = []
        for index, item in enumerate(reference_assets):
            data = dict(item or {})
            metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            derivative_kind = str(data.get("derivative_kind") or metadata.get("derivative_kind") or "").strip()
            identity_scope = str(
                data.get("identity_evidence_scope") or metadata.get("identity_evidence_scope") or ""
            ).strip()
            output_id = str(data.get("output_id") or metadata.get("output_id") or "").strip()
            source_asset_id = str(
                data.get("source_asset_id") or metadata.get("source_asset_id") or ""
            ).strip()
            reference_truth_layer = str(
                data.get("reference_truth_layer") or metadata.get("reference_truth_layer") or ""
            ).strip()
            identity_group_id = str(
                data.get("identity_evidence_group_id")
                or metadata.get("identity_evidence_group_id")
                or ""
            ).strip()
            framing_reference_mode = str(
                data.get("character_card_framing_reference_mode")
                or metadata.get("character_card_framing_reference_mode")
                or ""
            ).strip()
            framing_mirrored = (
                data.get("character_card_framing_mirrored")
                if "character_card_framing_mirrored" in data
                else metadata.get("character_card_framing_mirrored")
            )
            safe.append(
                {
                    "asset_id": str(data.get("asset_id") or data.get("output_id") or ""),
                    "source_asset_id": source_asset_id or None,
                    "output_id": output_id or None,
                    "file_path": str(data.get("file_path") or data.get("storage_path") or ""),
                    "sha256": hashes[index],
                    "role": str(data.get("role") or data.get("source_type") or "reference"),
                    "derivative_kind": derivative_kind or None,
                    "identity_evidence_scope": identity_scope or None,
                    "identity_evidence_group_id": identity_group_id or None,
                    "reference_truth_layer": reference_truth_layer or None,
                    "character_card_framing_reference_mode": framing_reference_mode or None,
                    "character_card_framing_mirrored": framing_mirrored,
                }
            )
        return safe

    @staticmethod
    def _reference_semantic_tokens(reference_assets: list[dict[str, Any]], hashes: list[str]) -> list[str]:
        tokens: list[str] = []
        for index, item in enumerate(reference_assets):
            data = dict(item or {})
            metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            asset_id = str(data.get("asset_id") or data.get("output_id") or "").strip()
            source_asset_id = str(
                data.get("source_asset_id") or metadata.get("source_asset_id") or ""
            ).strip()
            output_id = str(data.get("output_id") or metadata.get("output_id") or "").strip()
            derivative_kind = str(data.get("derivative_kind") or metadata.get("derivative_kind") or "").strip()
            identity_scope = str(
                data.get("identity_evidence_scope") or metadata.get("identity_evidence_scope") or ""
            ).strip()
            reference_truth_layer = str(
                data.get("reference_truth_layer") or metadata.get("reference_truth_layer") or ""
            ).strip()
            identity_group_id = str(
                data.get("identity_evidence_group_id")
                or metadata.get("identity_evidence_group_id")
                or ""
            ).strip()
            framing_reference_mode = str(
                data.get("character_card_framing_reference_mode")
                or metadata.get("character_card_framing_reference_mode")
                or ""
            ).strip()
            framing_mirrored_raw = (
                data.get("character_card_framing_mirrored")
                if "character_card_framing_mirrored" in data
                else metadata.get("character_card_framing_mirrored")
            )
            if framing_mirrored_raw is None:
                framing_mirrored = ""
            elif isinstance(framing_mirrored_raw, bool):
                framing_mirrored = str(framing_mirrored_raw).lower()
            else:
                framing_mirrored = str(framing_mirrored_raw).strip().lower()
            tokens.append(
                "\x1f".join(
                    [
                        str(index),
                        hashes[index],
                        asset_id,
                        source_asset_id,
                        output_id,
                        derivative_kind,
                        identity_scope,
                        reference_truth_layer,
                        identity_group_id,
                        framing_reference_mode,
                        framing_mirrored,
                    ]
                )
            )
        return tokens

    @classmethod
    def _reference_semantic_fingerprint(
        cls,
        reference_assets: list[dict[str, Any]],
        hashes: list[str],
    ) -> str:
        return hashlib.sha256(
            "|".join(cls._reference_semantic_tokens(reference_assets, hashes)).encode("utf-8")
        ).hexdigest()

    @classmethod
    def _existing_reference_semantic_fingerprint(cls, payload: dict[str, Any]) -> str:
        existing = str(payload.get("reference_semantic_fingerprint") or "").strip().lower()
        if existing:
            return existing
        references = payload.get("reference_assets")
        hashes = payload.get("reference_asset_hashes")
        if not isinstance(references, list) or not isinstance(hashes, list):
            return ""
        try:
            return cls._reference_semantic_fingerprint(
                [dict(item) for item in references if isinstance(item, dict)],
                [str(item) for item in hashes],
            )
        except Exception:
            return ""

    @staticmethod
    def _safe_rendering_contract(
        contract: dict[str, Any],
        *,
        require_body_rendering_contract: bool = False,
    ) -> dict[str, Any]:
        raw = dict(contract or {})
        allowed = {
            "renderer",
            "model",
            "size",
            "quality",
            "output_format",
            "count",
            "api_operation",
            "input_fidelity",
            "input_fidelity_required",
            "size_normalization",
            "body_refresh_source_mode",
        }
        safe = {key: value for key, value in raw.items() if key in allowed}
        expected_body_contract = body_silhouette_mcp_materialization_channel_contract()
        body_channel_present = (
            raw.get("body_silhouette_mcp_materialization_channel_contract") == expected_body_contract
        )
        if not body_channel_present:
            if require_body_rendering_contract:
                raise McpMaterializationError(
                    "mcp_materialization_body_rendering_contract_invalid",
                    detail={"failure_code": "body_channel_missing"},
                )
            return safe
        safe["body_silhouette_mcp_materialization_channel_contract"] = expected_body_contract
        expected_integrated_contract = body_silhouette_integrated_whole_person_synthesis_contract()
        raw_integrated = raw.get(
            "body_silhouette_integrated_whole_person_synthesis_contract"
        )
        if raw_integrated is None and require_body_rendering_contract:
            raise McpMaterializationError(
                "mcp_materialization_body_rendering_contract_invalid",
                detail={"failure_code": "integrated_whole_person_contract_missing"},
            )
        if raw_integrated is not None:
            if raw_integrated != expected_integrated_contract:
                raise McpMaterializationError(
                    "mcp_materialization_body_rendering_contract_invalid",
                    detail={"failure_code": "integrated_whole_person_contract_invalid"},
                )
            safe["body_silhouette_integrated_whole_person_synthesis_contract"] = (
                expected_integrated_contract
            )
        raw_source_mode = raw.get("body_refresh_source_mode")
        if raw_source_mode not in {"inference_first", "reference_assisted"}:
            if require_body_rendering_contract:
                raise McpMaterializationError(
                    "mcp_materialization_body_rendering_contract_invalid",
                    detail={"failure_code": "body_refresh_source_mode_missing"},
                )
            # A body channel without a server-owned strict source mode is a
            # legacy/generic projection: retain only the generic channel and
            # do not emit intent, Body truth, or other strict fields.
            return safe
        safe["body_refresh_source_mode"] = raw_source_mode

        identity_contract = {
            "slot_key": raw.get("slot_key"),
            "candidate_index": raw.get("candidate_index"),
            "candidate_count": raw.get("candidate_count"),
        }
        identity_missing = [key for key, value in identity_contract.items() if value is None]
        identity_binding_required = (
            raw_source_mode == "reference_assisted"
            and raw.get("professional_body_refresh_analysis_context") is not None
        )
        if identity_missing and require_body_rendering_contract and identity_binding_required:
            raise McpMaterializationError(
                "mcp_materialization_body_rendering_contract_invalid",
                detail={"failure_code": "body_rendering_identity_binding_missing"},
            )
        if not identity_missing:
            if (
                type(identity_contract["slot_key"]) is not str
                or identity_contract["slot_key"] not in {"body.front_full", "body.side_full", "body.rear_full"}
                or type(identity_contract["candidate_index"]) is not int
                or identity_contract["candidate_index"] not in {1, 2, 3}
                or type(identity_contract["candidate_count"]) is not int
                or identity_contract["candidate_count"] != 3
            ):
                raise McpMaterializationError(
                    "mcp_materialization_body_rendering_contract_invalid",
                    detail={"failure_code": "body_rendering_identity_binding_invalid"},
                )
            safe.update(identity_contract)

        raw_context = raw.get("professional_body_refresh_analysis_context")
        if raw_source_mode == "reference_assisted":
            if raw_context is not None:
                expected_context_keys = {
                    "contract_version",
                    "schema_version",
                    "source_mode",
                    "attempt_id",
                    "append_only_revision",
                    "source_binding_digest",
                    "source_evidence_id_digest",
                    "profile_digest",
                }
                if (
                    type(raw_context) is not dict
                    or set(raw_context) != expected_context_keys
                    or raw_context.get("contract_version") != "body_refresh_analysis_context_v2"
                    or raw_context.get("schema_version") != "body_morphology_evidence_profile_v2"
                    or raw_context.get("source_mode") != raw_source_mode
                    or type(raw_context.get("append_only_revision")) is not int
                    or raw_context.get("append_only_revision") < 1
                    or any(
                        type(raw_context.get(key)) is not str
                        or len(str(raw_context.get(key))) != 64
                        or any(char not in "0123456789abcdef" for char in str(raw_context.get(key)).lower())
                        for key in ("source_binding_digest", "source_evidence_id_digest", "profile_digest")
                    )
                ):
                    raise McpMaterializationError(
                        "mcp_materialization_body_rendering_contract_invalid",
                        detail={"failure_code": "body_refresh_analysis_context_invalid"},
                    )
                safe["professional_body_refresh_analysis_context"] = dict(raw_context)
        elif raw_context is not None:
            raise McpMaterializationError(
                "mcp_materialization_body_rendering_contract_invalid",
                detail={"failure_code": "body_refresh_analysis_context_forbidden_for_inference"},
            )
        raw_partition = raw.get("body_mcp_reference_partition")
        if raw_source_mode == "reference_assisted":
            if raw_partition is None:
                raise McpMaterializationError(
                    "mcp_materialization_body_rendering_contract_invalid",
                    detail={"failure_code": "body_reference_partition_missing"},
                )
            try:
                safe["body_mcp_reference_partition"] = McpBodyReferencePartition.model_validate(
                    raw_partition
                ).model_dump(mode="json")
            except Exception:
                raise McpMaterializationError(
                    "mcp_materialization_body_rendering_contract_invalid",
                    detail={"failure_code": "body_reference_partition_invalid"},
                ) from None
        elif raw_partition is not None:
            raise McpMaterializationError(
                "mcp_materialization_body_rendering_contract_invalid",
                detail={"failure_code": "body_reference_partition_forbidden_for_inference"},
            )
        raw_intent = raw.get("body_refresh_presentation_intent")
        if raw_intent is None:
            if not require_body_rendering_contract:
                return safe
            raise McpMaterializationError(
                "mcp_materialization_body_rendering_contract_invalid",
                detail={"failure_code": "body_refresh_presentation_intent_missing"},
            )
        unspecified = unspecified_body_refresh_presentation_intent()
        if raw_intent == unspecified:
            if require_body_rendering_contract:
                raise McpMaterializationError(
                    "mcp_materialization_body_rendering_contract_invalid",
                    detail={"failure_code": "body_refresh_presentation_intent_unspecified"},
                )
            safe["body_refresh_presentation_intent"] = unspecified
        else:
            try:
                safe["body_refresh_presentation_intent"] = BodyRefreshPresentationIntent.model_validate(
                    raw_intent
                ).model_dump(mode="json")
            except Exception:
                raise McpMaterializationError(
                    "mcp_materialization_body_rendering_contract_invalid",
                    detail={"failure_code": "body_refresh_presentation_intent_invalid"},
                ) from None
        raw_morphology = raw.get("body_morphology_profile")
        if raw_source_mode == "reference_assisted":
            if raw_morphology is None and require_body_rendering_contract:
                raise McpMaterializationError(
                    "mcp_materialization_body_rendering_contract_invalid",
                    detail={"failure_code": "body_morphology_profile_missing"},
                )
            if raw_morphology is not None:
                try:
                    if set(raw_morphology) != {
                        "schema_version",
                        "profile_digest",
                        "bands_digest",
                        "bands",
                    }:
                        raise ValueError("morphology fields")
                    if raw_morphology["schema_version"] != "body_morphology_evidence_profile_v2":
                        raise ValueError("morphology version")
                    digest = raw_morphology["profile_digest"]
                    if (
                        type(digest) is not str
                        or len(digest) != 64
                        or any(char not in "0123456789abcdef" for char in digest.lower())
                    ):
                        raise ValueError("morphology digest")
                    bands = raw_morphology["bands"]
                    if type(bands) is not dict:
                        raise ValueError("morphology bands")
                    bands_digest = raw_morphology["bands_digest"]
                    if (
                        type(bands_digest) is not str
                        or bands_digest.lower() != _canonical_json_sha256(bands)
                    ):
                        raise ValueError("morphology bands digest")
                    BodyMorphologyEvidenceProfile.model_validate(
                        {
                            "contract_version": "body_morphology_evidence_profile_v2",
                            "source_mode": "reference_assisted",
                            "source_truth_layer": "body_proportion_truth",
                            **bands,
                            "source_count": 5,
                            "analysis_receipt": {
                                "owner": "server_owned_body_proportion_analysis",
                                "status": "complete",
                                "analysis_provider": "configured_body_source_analysis_provider",
                            },
                        }
                    )
                    safe["body_morphology_profile"] = {
                        "schema_version": "body_morphology_evidence_profile_v2",
                        "profile_digest": digest.lower(),
                        "bands_digest": bands_digest.lower(),
                        "bands": dict(bands),
                    }
                except Exception:
                    raise McpMaterializationError(
                        "mcp_materialization_body_rendering_contract_invalid",
                        detail={"failure_code": "body_morphology_profile_invalid"},
                    ) from None
        elif raw_morphology is not None:
            raise McpMaterializationError(
                "mcp_materialization_body_rendering_contract_invalid",
                detail={"failure_code": "body_morphology_profile_forbidden"},
            )
        raw_hair = raw.get("body_silhouette_hair_continuity_contract")
        if raw_hair is None and require_body_rendering_contract:
            raise McpMaterializationError(
                "mcp_materialization_body_rendering_contract_invalid",
                detail={"failure_code": "body_hair_continuity_contract_missing"},
            )
        if raw_hair is not None:
            try:
                safe["body_silhouette_hair_continuity_contract"] = (
                    BodySilhouetteHairContinuityContract.model_validate(raw_hair).model_dump(mode="json")
                )
            except Exception:
                raise McpMaterializationError(
                    "mcp_materialization_body_rendering_contract_invalid",
                    detail={"failure_code": "body_hair_continuity_contract_invalid"},
                ) from None
        raw_backdrop = raw.get("body_silhouette_backdrop_presentation_contract")
        if raw_backdrop is None and require_body_rendering_contract:
            raise McpMaterializationError(
                "mcp_materialization_body_rendering_contract_invalid",
                detail={"failure_code": "body_backdrop_presentation_contract_missing"},
            )
        if raw_backdrop is not None:
            try:
                safe["body_silhouette_backdrop_presentation_contract"] = (
                    BodySilhouetteBackdropPresentationContract.model_validate(raw_backdrop).model_dump(
                        mode="json"
                    )
                )
            except Exception:
                raise McpMaterializationError(
                    "mcp_materialization_body_rendering_contract_invalid",
                    detail={"failure_code": "body_backdrop_presentation_contract_invalid"},
                ) from None
        return safe

    @classmethod
    def _rendering_contract_fingerprint(cls, contract: dict[str, Any]) -> str:
        safe = cls._safe_rendering_contract(contract)
        canonical = json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _existing_rendering_contract_fingerprint(cls, payload: dict[str, Any]) -> str:
        existing = str(payload.get("rendering_contract_fingerprint") or "").strip().lower()
        if existing:
            return existing
        rendering_contract = payload.get("rendering_contract")
        if not isinstance(rendering_contract, dict):
            return ""
        return cls._rendering_contract_fingerprint(rendering_contract)

    @staticmethod
    def _image_format(content: bytes) -> tuple[str, str]:
        try:
            from PIL import Image
            from io import BytesIO

            with Image.open(BytesIO(content)) as image:
                raw = str(image.format or "").lower()
        except Exception as exc:
            raise McpMaterializationError("mcp_materialization_artifact_invalid") from exc
        if raw == "jpg":
            raw = "jpeg"
        if raw not in {"png", "jpeg", "webp"}:
            raise McpMaterializationError("mcp_materialization_artifact_format_invalid")
        return raw, {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}[raw]
