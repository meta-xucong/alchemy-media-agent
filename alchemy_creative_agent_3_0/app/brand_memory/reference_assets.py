"""Reference asset helpers for V3-owned brand memory."""

from __future__ import annotations

from ..schemas import ReferenceAsset


def reference_asset_ids(reference_assets: list[ReferenceAsset]) -> list[str]:
    return [asset.asset_id for asset in reference_assets]

