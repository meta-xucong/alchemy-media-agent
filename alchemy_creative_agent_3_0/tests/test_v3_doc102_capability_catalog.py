import pytest

from alchemy_creative_agent_3_0.app.shared_capabilities import SharedCapabilityRegistry
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    VisualCapabilityManifest,
    VisualCapabilityRegistry,
)


def _registry():
    execution = SharedCapabilityRegistry.with_default_modules()
    return execution, VisualCapabilityRegistry.with_default_manifests(execution)


def test_default_catalog_contains_extensible_logical_capabilities() -> None:
    _, registry = _registry()
    ids = {item.capability_id for item in registry.manifests()}
    assert {"human_realism", "portrait_identity", "product_identity", "scene_continuity"} <= ids


def test_catalog_reuses_existing_executor_instances() -> None:
    execution, registry = _registry()
    assert registry.resolve_executor("human_realism") is execution.get("visual_capability_cluster")
    assert registry.resolve_executor("portrait_identity") is execution.get("visual_capability_cluster")


def test_duplicate_manifest_version_is_rejected() -> None:
    _, registry = _registry()
    manifest = registry.manifest("human_realism")
    with pytest.raises(ValueError, match="already registered"):
        registry.register_manifest(manifest, "visual_capability_cluster")


def test_unknown_executor_is_rejected() -> None:
    _, registry = _registry()
    with pytest.raises(ValueError, match="executor is not registered"):
        registry.register_manifest(
            VisualCapabilityManifest(capability_id="future", display_name="Future"),
            "missing_executor",
        )


def test_graph_detects_missing_dependency() -> None:
    execution, registry = _registry()
    registry.register_manifest(
        VisualCapabilityManifest(
            capability_id="future",
            display_name="Future",
            dependencies=["not_installed"],
        ),
        "output_review",
    )
    audit = registry.validate_graph(["future"])
    assert audit.valid is False
    assert "not_installed" in audit.missing_dependencies


def test_catalog_snapshot_excludes_disabled_manifest() -> None:
    execution, registry = _registry()
    registry.register_manifest(
        VisualCapabilityManifest(capability_id="disabled_future", display_name="Disabled", status="disabled"),
        "output_review",
    )
    snapshot = registry.catalog_snapshot("general_template", "general_creative")
    assert snapshot.manifest("disabled_future") is None
