"""Manifest catalog facade over the existing shared capability registry."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import (
    CapabilityCatalogEntry,
    CapabilityCatalogSnapshot,
    CapabilityCost,
    CapabilityGraphAudit,
    VisualCapabilityManifest,
)


VISUAL_CLUSTER_EXECUTOR = "visual_capability_cluster"


class VisualCapabilityRegistry:
    """Owns manifests while reusing the one existing execution registry."""

    def __init__(self, execution_registry: Any) -> None:
        self.execution_registry = execution_registry
        self._entries: dict[tuple[str, str], CapabilityCatalogEntry] = {}
        self._latest: dict[str, str] = {}

    @classmethod
    def with_default_manifests(cls, execution_registry: Any) -> "VisualCapabilityRegistry":
        registry = cls(execution_registry)
        for manifest, executor_ref in default_manifest_inventory():
            registry.register_manifest(manifest, executor_ref)
        return registry

    def register_manifest(self, manifest: VisualCapabilityManifest, executor_ref: str) -> None:
        key = (manifest.capability_id, manifest.version)
        if key in self._entries:
            raise ValueError(f"capability manifest already registered: {manifest.capability_id}@{manifest.version}")
        if self.execution_registry.get(executor_ref) is None:
            raise ValueError(f"executor is not registered: {executor_ref}")
        self._entries[key] = CapabilityCatalogEntry(manifest=manifest, executor_ref=executor_ref)
        self._latest[manifest.capability_id] = manifest.version

    def unregister_manifest(self, capability_id: str) -> None:
        versions = [key for key in self._entries if key[0] == capability_id]
        for key in versions:
            self._entries.pop(key, None)
        self._latest.pop(capability_id, None)

    def manifest(self, capability_id: str, version: str | None = None) -> VisualCapabilityManifest | None:
        selected_version = version or self._latest.get(capability_id)
        entry = self._entries.get((capability_id, selected_version or ""))
        return entry.manifest if entry else None

    def manifests(self, enabled_only: bool = True) -> list[VisualCapabilityManifest]:
        manifests = [
            entry.manifest
            for (capability_id, version), entry in self._entries.items()
            if self._latest.get(capability_id) == version
        ]
        if enabled_only:
            manifests = [item for item in manifests if item.status == "enabled"]
        return sorted(manifests, key=lambda item: item.capability_id)

    def catalog_snapshot(self, template_id: str, scenario_id: str) -> CapabilityCatalogSnapshot:
        entries: list[CapabilityCatalogEntry] = []
        for manifest in self.manifests(enabled_only=True):
            if manifest.compatible_templates and template_id not in manifest.compatible_templates:
                continue
            if template_id in manifest.forbidden_templates:
                continue
            entry = self._entries[(manifest.capability_id, manifest.version)]
            entries.append(entry)
        version = stable_id(
            "capability_catalog",
            template_id,
            scenario_id,
            *[f"{item.manifest.capability_id}@{item.manifest.version}" for item in entries],
        )
        return CapabilityCatalogSnapshot(
            catalog_version=version,
            template_id=template_id,
            scenario_id=scenario_id,
            entries=entries,
        )

    def resolve_executor(self, capability_id: str, version: str | None = None) -> Any | None:
        selected_version = version or self._latest.get(capability_id)
        entry = self._entries.get((capability_id, selected_version or ""))
        return self.execution_registry.get(entry.executor_ref) if entry else None

    def executor_ref(self, capability_id: str, version: str | None = None) -> str | None:
        selected_version = version or self._latest.get(capability_id)
        entry = self._entries.get((capability_id, selected_version or ""))
        return entry.executor_ref if entry else None

    def validate_graph(self, capability_ids: list[str]) -> CapabilityGraphAudit:
        selected = list(dict.fromkeys(capability_ids))
        missing: list[str] = []
        graph: dict[str, list[str]] = {}
        for capability_id in selected:
            manifest = self.manifest(capability_id)
            if manifest is None:
                missing.append(capability_id)
                continue
            graph[capability_id] = list(manifest.dependencies)
            missing.extend(dep for dep in manifest.dependencies if self.manifest(dep) is None)
        order: list[str] = []
        visiting: list[str] = []
        visited: set[str] = set()
        cycles: list[list[str]] = []

        def visit(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                index = visiting.index(node)
                cycles.append([*visiting[index:], node])
                return
            visiting.append(node)
            for dependency in graph.get(node, []):
                if dependency in graph:
                    visit(dependency)
            visiting.pop()
            visited.add(node)
            if node in graph:
                order.append(node)

        for capability_id in selected:
            visit(capability_id)
        return CapabilityGraphAudit(
            valid=not missing and not cycles,
            dependency_order=order,
            missing_dependencies=sorted(set(missing)),
            cycles=cycles,
        )


def default_manifest_inventory() -> list[tuple[VisualCapabilityManifest, str]]:
    universal_templates = ["general_template", "ecommerce_template"]
    visual_stages = [
        "creative_strategy",
        "generation_prompt",
        "negative_prompt",
        "provider_input_plan",
        "post_generation_review",
        "retry_patch",
    ]

    def manifest(
        capability_id: str,
        display_name: str,
        executor_ref: str,
        *,
        entities: list[str] | None = None,
        dependencies: list[str] | None = None,
        optional_dependencies: list[str] | None = None,
        stages: list[str] | None = None,
        threshold: float = 0.5,
        profiles: list[str] | None = None,
        evidence: list[str] | None = None,
    ) -> tuple[VisualCapabilityManifest, str]:
        return (
            VisualCapabilityManifest(
                capability_id=capability_id,
                display_name=display_name,
                supported_entity_types=list(entities or []),
                activation_evidence_schema=list(evidence or []),
                minimum_activation_confidence=threshold,
                dependencies=list(dependencies or []),
                optional_dependencies=list(optional_dependencies or []),
                compatible_templates=universal_templates,
                supported_profiles=list(profiles or ["balanced"]),
                contribution_stages=list(stages or visual_stages),
                estimated_cost=CapabilityCost(latency=1, token=1),
                audit_tags=["doc101", "doc102"],
            ),
            executor_ref,
        )

    return [
        manifest("asset_understanding", "Asset understanding", "asset_role_analyzer", stages=["asset_analysis"], threshold=0.0),
        manifest("reference_inventory", "Reference inventory", "asset_binding_planner", dependencies=["asset_understanding"], stages=["reference_policy"], threshold=0.0),
        manifest("project_context_digest", "Project context digest", "history_reference", stages=["reference_policy"], threshold=0.0),
        manifest("reference_channel_policy", "Reference channel policy", VISUAL_CLUSTER_EXECUTOR, dependencies=["reference_inventory"], stages=["reference_policy", "generation_prompt", "negative_prompt", "provider_input_plan"], threshold=0.4),
        manifest("visual_grammar", "Visual grammar", "visual_grammar_lock", stages=["creative_strategy", "generation_prompt"], threshold=0.0),
        manifest("universal_visual_quality", "Universal visual quality", VISUAL_CLUSTER_EXECUTOR, dependencies=["visual_grammar"], threshold=0.0, profiles=["balanced", "strict"]),
        manifest("human_realism", "Human realism", VISUAL_CLUSTER_EXECUTOR, entities=["person"], dependencies=["universal_visual_quality"], evidence=["visible_person", "real_human_output"], threshold=0.55, profiles=["balanced", "strict", "child_strict"]),
        manifest("portrait_identity", "Portrait identity", VISUAL_CLUSTER_EXECUTOR, entities=["person"], dependencies=["reference_channel_policy", "universal_visual_quality"], evidence=["portrait_reference", "selected_identity_reference"], threshold=0.65, profiles=["balanced", "strong"]),
        manifest("product_identity", "Product identity", VISUAL_CLUSTER_EXECUTOR, entities=["product", "generic_object", "food", "vehicle"], dependencies=["universal_visual_quality"], optional_dependencies=["reference_channel_policy"], evidence=["product_intent", "product_reference"], threshold=0.5, profiles=["described_concept", "reference_truth"]),
        manifest("scene_continuity", "Scene continuity", VISUAL_CLUSTER_EXECUTOR, entities=["scene", "building", "interior_space"], dependencies=["reference_channel_policy", "universal_visual_quality"], evidence=["scene_reference", "scene_preservation"], threshold=0.6),
        manifest("typography_layout", "Typography and layout", VISUAL_CLUSTER_EXECUTOR, entities=["text_layout", "brand_asset"], dependencies=["universal_visual_quality"], evidence=["target_text", "layout_intent"], threshold=0.55),
        manifest("suite_direction", "Suite direction", VISUAL_CLUSTER_EXECUTOR, dependencies=["universal_visual_quality"], evidence=["multiple_outputs", "continuation_mode"], threshold=0.4),
        manifest("commercial_quality", "Delivery quality", "output_review", dependencies=["universal_visual_quality"], stages=["post_generation_review", "export_validation"], threshold=0.0, profiles=["balanced", "commercial_strict"]),
    ]
