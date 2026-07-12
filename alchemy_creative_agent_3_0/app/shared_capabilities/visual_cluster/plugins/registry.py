"""Registry for independently replaceable Visual Cluster contribution plugins."""

from __future__ import annotations

from ...activation import CapabilityActivationPlan, CapabilityContribution
from .base import MetadataCapabilityPlugin, VisualCapabilityPlugin, VisualPluginContext
from .human_realism import HumanRealismPlugin
from .nonhuman_subject_identity import NonhumanSubjectIdentityPlugin
from .portrait_identity import PortraitIdentityPlugin
from .product_identity import ProductIdentityPlugin
from .reference_channel_policy import ReferenceChannelPolicyPlugin
from .scene_continuity import SceneContinuityPlugin
from .suite_direction import SuiteDirectionPlugin
from .typography_layout import TypographyLayoutPlugin
from .universal_visual_quality import CommercialQualityPlugin, UniversalVisualQualityPlugin, VisualGrammarPlugin


class VisualClusterPluginRegistry:
    def __init__(self, plugins: list[VisualCapabilityPlugin] | None = None) -> None:
        defaults: list[VisualCapabilityPlugin] = [
            MetadataCapabilityPlugin("asset_understanding", ["asset_analysis"]),
            MetadataCapabilityPlugin("reference_inventory", ["reference_policy"]),
            MetadataCapabilityPlugin("project_context_digest", ["reference_policy"]),
            ReferenceChannelPolicyPlugin(),
            VisualGrammarPlugin(),
            UniversalVisualQualityPlugin(),
            HumanRealismPlugin(),
            PortraitIdentityPlugin(),
            NonhumanSubjectIdentityPlugin(),
            ProductIdentityPlugin(),
            SceneContinuityPlugin(),
            TypographyLayoutPlugin(),
            SuiteDirectionPlugin(),
            CommercialQualityPlugin(),
        ]
        self._plugins = {plugin.capability_id: plugin for plugin in (plugins or defaults)}

    def register(self, plugin: VisualCapabilityPlugin) -> None:
        if plugin.capability_id in self._plugins:
            raise ValueError(f"visual plugin already registered: {plugin.capability_id}")
        self._plugins[plugin.capability_id] = plugin

    def unregister(self, capability_id: str) -> None:
        self._plugins.pop(capability_id, None)

    def plugin(self, capability_id: str) -> VisualCapabilityPlugin | None:
        return self._plugins.get(capability_id)

    def contributions(self, plan: CapabilityActivationPlan, cluster: dict) -> list[CapabilityContribution]:
        result: list[CapabilityContribution] = []
        for active in plan.active_capabilities:
            plugin = self.plugin(active.capability_id)
            if plugin is None:
                continue
            result.append(plugin.contribute(VisualPluginContext(plan=plan, active=active, cluster=cluster)))
        return result
