"""Explicit host-side resolver for persisted Professional asset metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from alchemy_creative_agent_3_0.app.visual_assets import (
    PersistentVisualAssetCatalog,
    ProfessionalModeBinding,
    bind_professional_mode,
)


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
