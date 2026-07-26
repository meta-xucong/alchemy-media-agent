"""Explicit host-side resolver for persisted Professional asset metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from alchemy_creative_agent_3_0.app.visual_assets import (
    PersistentVisualAssetCatalog,
    PersistentVisualAssetLibraryCatalog,
    ProfessionalModeBinding,
    bind_professional_mode,
)
from alchemy_creative_agent_3_0.app.visual_assets.binding import MAX_IDENTITY_REFERENCE_VIEWS


def persistent_professional_binding_resolver(
    storage_root: str | Path,
) -> Callable[..., ProfessionalModeBinding | None]:
    """Build a resolver from an explicitly configured metadata catalog root.

    The root is process configuration, not MCP input. This helper reads only
    the existing People Asset/Face Identity metadata and delegates lifecycle
    validation to ``bind_professional_mode``. It never reads credentials,
    source images, or Web Provider configuration.
    """

    legacy_catalog = PersistentVisualAssetCatalog(storage_root)
    library_catalog = PersistentVisualAssetLibraryCatalog(storage_root)

    def resolve(
        *,
        project_id: str,
        people_asset_id: str,
        job_id: str,
        reference_view_ids: list[str],
    ) -> ProfessionalModeBinding | None:
        asset = legacy_catalog.get(project_id, people_asset_id)
        if asset is None or not asset.active_pack_version_id:
            return _resolve_library_character_card_binding(
                library_catalog,
                project_id=project_id,
                people_asset_id=people_asset_id,
                job_id=job_id,
                reference_view_ids=reference_view_ids,
            )
        pack = legacy_catalog.get_pack(project_id, people_asset_id, asset.active_pack_version_id)
        if pack is None:
            return _resolve_library_character_card_binding(
                library_catalog,
                project_id=project_id,
                people_asset_id=people_asset_id,
                job_id=job_id,
                reference_view_ids=reference_view_ids,
            )
        return bind_professional_mode(
            job_id=job_id,
            project_id=project_id,
            asset=asset,
            module=asset.face_identity_module,
            pack=pack,
            reference_view_ids=reference_view_ids,
        )

    return resolve


def _resolve_library_character_card_binding(
    catalog: PersistentVisualAssetLibraryCatalog,
    *,
    project_id: str,
    people_asset_id: str,
    job_id: str,
    reference_view_ids: list[str],
) -> ProfessionalModeBinding | None:
    """Resolve Doc178 library Character Card face slots as existing binding evidence.

    The Visual Asset Library is now the user-facing Professional asset
    authority.  This adapter reads only metadata for already-active Face
    Identity slots and projects it into the existing ProfessionalModeBinding
    contract consumed by the MCP relay.  It does not create packs, prompts,
    artifacts, reviews, retries, or delivery records.
    """

    try:
        asset = catalog.get(owner_scope=project_id, visual_asset_id=people_asset_id)
    except Exception:
        return None
    if asset is None or asset.lifecycle_status != "active":
        return None
    active_version = asset.active_version()
    if active_version is None or active_version.lifecycle_status != "active" or not active_version.activation_confirmed:
        return None
    card = asset.character_card
    if card.face_identity_status != "active":
        return None
    face_version_id = str(card.face_identity_version_id or asset.active_version_id or "").strip()
    if not face_version_id:
        return None
    if len(reference_view_ids) > MAX_IDENTITY_REFERENCE_VIEWS:
        return None
    known_outputs: dict[str, str] = {}
    for slot in card.face_slots.values():
        if slot.state != "active" or not slot.output_id:
            continue
        if slot.formal_slot_receipt is None:
            continue
        if slot.formal_slot_receipt.winner_output_id != slot.output_id:
            continue
        known_outputs[slot.output_id] = slot.output_id
    selected: list[str] = []
    for view_id in reference_view_ids:
        if view_id in selected:
            continue
        if view_id not in known_outputs:
            return None
        selected.append(view_id)
    if not selected:
        return None
    return ProfessionalModeBinding(
        job_id=job_id,
        project_id=project_id,
        people_asset_id=asset.visual_asset_id,
        face_module_id=face_version_id,
        pack_version_id=face_version_id,
        identity_view_ids=selected,
    )
