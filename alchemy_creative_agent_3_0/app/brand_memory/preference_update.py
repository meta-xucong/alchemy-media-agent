"""Preference update helpers reserved for V3 brand memory expansion."""

from __future__ import annotations

from ..schemas import MemoryUpdate


def should_apply_memory_update(update: MemoryUpdate) -> bool:
    """Return whether a proposed update is eligible for explicit persistence."""

    return bool(
        update.action == "propose"
        and update.accepted_asset_ids
        and not update.metadata.get("planning_only")
        and not update.metadata.get("candidate_rejected")
        and not update.applied
    )
