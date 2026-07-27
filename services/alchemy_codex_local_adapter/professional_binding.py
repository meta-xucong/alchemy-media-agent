"""Explicit host-side resolver for persisted Professional asset metadata."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Callable

from alchemy_creative_agent_3_0.app.visual_assets import (
    FrozenVisualAssetBindingSet,
    PersistentVisualAssetCatalog,
    PersistentProjectVisualAssetBindingService,
    PersistentVisualAssetLibraryCatalog,
    ProfessionalModeBinding,
    bind_professional_mode,
)

from .contracts import NativeReferenceInput


@dataclass(frozen=True)
class ProfessionalBindingResolution:
    """Server-owned Professional binding plus renderer-usable identity refs.

    The MCP caller supplies only opaque selectors.  This object is produced by
    a trusted host resolver after reading server-owned asset metadata; it is
    not accepted from public tool arguments.
    """

    binding: ProfessionalModeBinding
    identity_references: tuple[NativeReferenceInput, ...] = ()
    binding_snapshot: FrozenVisualAssetBindingSet | None = None


_FACE_SLOT_SELECTOR_BY_KEY = {
    "face.front": "face_front",
    "face.front_three_quarter": "face_front_three_quarter",
    "face.profile": "face_profile",
    "face.reverse_three_quarter": "face_reverse_three_quarter",
    "face.rear_head": "face_rear_head",
}


def persistent_professional_binding_resolver(
    storage_root: str | Path,
) -> Callable[..., ProfessionalModeBinding | None]:
    """Build a resolver from an explicitly configured metadata catalog root.

    The root is process configuration, not MCP input. This helper reads only
    the existing People Asset/Face Identity metadata and delegates lifecycle
    validation to ``bind_professional_mode``. It never reads credentials,
    source images, or Web Provider configuration.
    """

    catalog = PersistentVisualAssetCatalog(storage_root)

    def resolve(
        *,
        project_id: str,
        people_asset_id: str,
        job_id: str,
        reference_view_ids: list[str],
    ) -> ProfessionalModeBinding | None:
        asset = catalog.get(project_id, people_asset_id)
        if asset is None or not asset.active_pack_version_id:
            return None
        pack = catalog.get_pack(project_id, people_asset_id, asset.active_pack_version_id)
        if pack is None:
            return None
        return bind_professional_mode(
            job_id=job_id,
            project_id=project_id,
            asset=asset,
            module=asset.face_identity_module,
            pack=pack,
            reference_view_ids=reference_view_ids,
        )

    return resolve


def visual_asset_library_professional_binding_resolver(
    storage_root: str | Path,
    *,
    owner_scope: str = "local_default",
) -> Callable[..., ProfessionalBindingResolution | None]:
    """Resolve active Character Card identity from the Visual Asset Library.

    Doc259's product-on-model native path uses the public Visual Asset Library
    as the user-visible source of truth.  The historical
    ``PersistentVisualAssetCatalog`` resolver cannot see those active card
    slots, so this adapter projects the already-activated Character Card face
    slots into the same typed Professional binding used by the runtime.

    Image paths are resolved only from server-owned output IDs stored inside
    the active library record.  The MCP caller cannot provide or override
    those paths.
    """

    library_root = Path(storage_root)
    catalog = PersistentVisualAssetLibraryCatalog(library_root)
    binding_service = PersistentProjectVisualAssetBindingService(catalog, library_root)
    storage_parent = library_root.parent
    output_root = storage_parent / "v3_outputs"
    upload_root = storage_parent / "v3_uploads"

    def resolve(
        *,
        project_id: str,
        people_asset_id: str,
        job_id: str,
        reference_view_ids: list[str],
    ) -> ProfessionalBindingResolution | None:
        asset = catalog.get(owner_scope=owner_scope, visual_asset_id=people_asset_id)
        if asset is None:
            return None
        if asset.lifecycle_status != "active" or not asset.active_version_id:
            return None
        current_bindings = binding_service.current(project_id=project_id)
        if current_bindings.state != "valid":
            return None
        matching_bindings = [
            item
            for item in current_bindings.bindings
            if item.visual_asset_id == asset.visual_asset_id
            and item.owner_scope == owner_scope
            and item.selected_version_id == asset.active_version_id
            and item.asset_type == "people"
            and item.status == "active"
        ]
        if len(matching_bindings) != 1:
            return None
        selected_binding = matching_bindings[0]
        binding_snapshot = FrozenVisualAssetBindingSet(
            binding_set_id=_stable_binding_set_id(project_id, job_id, selected_binding.binding_id),
            project_id=project_id,
            job_id=job_id,
            bindings=[selected_binding],
            state="valid",
        )
        if not reference_view_ids:
            return None
        root_source_id = str(asset.root_source_provenance.source_asset_id or "").strip()
        if not root_source_id:
            return None
        root_reference = _resolve_root_reference(
            root_source_id,
            upload_root=upload_root,
        )
        if root_reference is None:
            return None
        root_path, root_digest = root_reference
        card = asset.character_card
        active_slots = [
            slot
            for slot in card.face_slots.values()
            if slot.state == "active"
            and slot.output_id
            and slot.review_verified
            and slot.prompt_reference_parity_verified
            and slot.formal_slot_receipt is not None
        ]
        by_selector: dict[str, object] = {}
        for slot in active_slots:
            safe_slot_id = _FACE_SLOT_SELECTOR_BY_KEY.get(str(slot.slot_key))
            if safe_slot_id:
                by_selector[safe_slot_id] = slot
        selected = []
        for view_id in reference_view_ids:
            slot = by_selector.get(str(view_id).strip())
            if slot is None:
                return None
            if slot in selected:
                return None
            selected.append(slot)
        identity_references: list[NativeReferenceInput] = [
            NativeReferenceInput(
                channel="portrait_identity",
                file_path=str(root_path.resolve()),
                source_sha256=root_digest,
                source_asset_id=root_source_id,
                server_owned=True,
            )
        ]
        for slot in selected:
            output_id = str(slot.output_id)
            image_path = output_root / output_id / "original.png"
            output_reference = _validated_output_reference(
                output_id,
                image_path=image_path,
            )
            if output_reference is None:
                return None
            image_path, digest = output_reference
            identity_references.append(
                NativeReferenceInput(
                    channel="selected_identity_reference",
                    file_path=str(image_path.resolve()),
                    source_sha256=digest,
                    source_asset_id=output_id,
                    output_id=output_id,
                    server_owned=True,
                )
            )
        face_module_id = (
            card.face_identity_version_id
            or asset.active_version_id
            or f"face_identity_{asset.visual_asset_id}"
        )
        binding = ProfessionalModeBinding(
            job_id=job_id,
            project_id=project_id,
            people_asset_id=asset.visual_asset_id,
            face_module_id=face_module_id,
            pack_version_id=asset.active_version_id,
            identity_view_ids=list(reference_view_ids),
        )
        return ProfessionalBindingResolution(
            binding=binding,
            identity_references=tuple(identity_references),
            binding_snapshot=binding_snapshot,
        )

    return resolve


def _sha256_file(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def _stable_binding_set_id(project_id: str, job_id: str, binding_id: str) -> str:
    digest = hashlib.sha256(f"{project_id}\n{job_id}\n{binding_id}".encode("utf-8")).hexdigest()
    return f"frozen_binding_set_{digest[:16]}"


def _resolve_root_reference(
    root_source_id: str,
    *,
    upload_root: Path,
) -> tuple[Path, str] | None:
    """Find the immutable root portrait only from server-owned upload evidence.

    The resolver reads only the current server-owned media root. Append-only
    validation evidence can be used by an explicit reconciliation task to
    restore this store, but it must not become an implicit runtime data source.
    ``asset.json`` and ``original.png`` must agree on asset id, ready status,
    face-reference role, consent, and source hash. Generated winners are never
    used as a root substitute.
    """

    return _validated_root_asset_json(
        upload_root / root_source_id / "asset.json",
        root_source_id=root_source_id,
    )


def _validated_root_asset_json(asset_json: Path, *, root_source_id: str) -> tuple[Path, str] | None:
    if not asset_json.is_file():
        return None
    original = asset_json.parent / "original.png"
    if not original.is_file():
        return None
    try:
        payload = json.loads(asset_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("asset_id") or "").strip() != root_source_id:
        return None
    if str(payload.get("status") or "").strip() != "ready":
        return None
    if str(payload.get("role") or "").strip() != "face_reference":
        return None
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if not str(metadata.get("consent_reference") or payload.get("consent_reference") or "").strip():
        return None
    expected_hash = str(metadata.get("source_sha256") or "").strip().lower()
    if len(expected_hash) != 64:
        return None
    actual_hash = _sha256_file(original)
    if actual_hash is None or actual_hash.lower() != expected_hash:
        return None
    return original.resolve(), actual_hash


def _validated_output_reference(output_id: str, *, image_path: Path) -> tuple[Path, str] | None:
    if not image_path.is_file():
        return None
    output_json = image_path.parent / "output.json"
    if not output_json.is_file():
        return None
    try:
        payload = json.loads(output_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("output_id") or "").strip() != output_id:
        return None
    manifest_path = str(payload.get("file_path") or "").strip()
    if manifest_path:
        try:
            if Path(manifest_path).resolve() != image_path.resolve():
                return None
        except (OSError, RuntimeError, ValueError):
            return None
    actual_hash = _sha256_file(image_path)
    if actual_hash is None:
        return None
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    for key in ("output_sha256", "source_sha256", "file_sha256"):
        expected_hash = str(metadata.get(key) or payload.get(key) or "").strip().lower()
        if expected_hash and expected_hash != actual_hash.lower():
            return None
    return image_path.resolve(), actual_hash
