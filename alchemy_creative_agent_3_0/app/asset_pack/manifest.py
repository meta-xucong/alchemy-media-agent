"""Manifest helpers for planning-only asset packs."""

from __future__ import annotations

from ..schemas import PackagedAsset


def manifest_entry(asset: PackagedAsset) -> dict:
    render_manifest = asset.metadata.get("render_manifest")
    return {
        "asset_id": asset.asset_id,
        "asset_type": asset.asset_type,
        "platform": asset.platform,
        "aspect_ratio": asset.aspect_ratio,
        "purpose": asset.purpose,
        "layout_plan_id": asset.layout_plan_id,
        "prompt_compilation_id": asset.prompt_compilation_id,
        "evaluation_id": asset.evaluation_id,
        "selected_candidate_id": asset.metadata.get("selected_candidate_id"),
        "rendering_required": asset.metadata.get("rendering_required", False),
        "render_manifest": render_manifest,
        "editable_text_layers": render_manifest.get("editable_text_layers", []) if render_manifest else [],
        "warnings": asset.metadata.get("warnings", []),
    }
