"""Explicit Professional Mode binding helpers.

This module only validates asset evidence and produces a sanitized binding. It
does not invoke the Brain, Provider, review, retry, or storage systems.
"""

from __future__ import annotations

from .contracts import (
    AnchorView,
    FaceIdentityModule,
    IdentityAnchorPackVersion,
    PeopleAsset,
    ProfessionalModeBinding,
)


MAX_IDENTITY_REFERENCE_VIEWS = 3


def select_reference_views(pack: IdentityAnchorPackVersion, requested_view_ids: list[str]) -> list[str]:
    """Select a bounded, ordered, active view subset from a reviewed pack."""

    selected: list[str] = []
    known = {item.view_id: item for item in pack.anchor_views if item.active}
    for view_id in requested_view_ids:
        if view_id in selected:
            continue
        if view_id not in known:
            raise ValueError("identity view is missing or inactive in the selected pack")
        selected.append(view_id)
    if len(selected) > MAX_IDENTITY_REFERENCE_VIEWS:
        raise ValueError("a Professional Mode job may use at most three identity views")
    return selected


def bind_professional_mode(
    *,
    job_id: str,
    project_id: str,
    asset: PeopleAsset,
    module: FaceIdentityModule,
    pack: IdentityAnchorPackVersion,
    reference_view_ids: list[str],
) -> ProfessionalModeBinding:
    """Create an explicit per-job binding after all project/lifecycle checks."""

    if project_id != asset.project_id or project_id != pack.root_source_provenance.project_id:
        raise ValueError("People Asset, pack root, and job must belong to the same project")
    if module.people_asset_id != asset.people_asset_id or module.module_id != asset.face_identity_module.module_id:
        raise ValueError("selected Face Identity Module does not belong to the People Asset")
    if pack.people_asset_id != asset.people_asset_id:
        raise ValueError("selected anchor pack does not belong to the People Asset")
    if asset.status != "active" or module.status != "active" or pack.status != "active":
        raise ValueError("Professional Mode requires an active People Asset, module, and pack")
    if asset.active_pack_version_id != pack.pack_version_id or module.active_version_id != pack.pack_version_id:
        raise ValueError("selected People Asset and Face Identity Module must use the active pack version")
    if not pack.user_activation_confirmed:
        raise ValueError("Professional Mode requires user activation of the face pack")
    if len(reference_view_ids) > MAX_IDENTITY_REFERENCE_VIEWS:
        raise ValueError("a Professional Mode job may use at most three identity views")
    selected = select_reference_views(pack, reference_view_ids)
    return ProfessionalModeBinding(
        job_id=job_id,
        project_id=project_id,
        people_asset_id=asset.people_asset_id,
        face_module_id=module.module_id,
        pack_version_id=pack.pack_version_id,
        identity_view_ids=selected,
    )
