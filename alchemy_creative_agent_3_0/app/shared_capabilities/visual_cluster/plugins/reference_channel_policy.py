from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext, as_dict, string_list


class ReferenceChannelPolicyPlugin(BaseVisualCapabilityPlugin):
    capability_id = "reference_channel_policy"

    def contribute(self, context: VisualPluginContext):
        package = as_dict(context.cluster.get("resolved_reference_policy_package"))
        if not package.get("applies"):
            return self.contribution(context)
        return self.contribution(
            context,
            prompt=string_list(package.get("provider_prompt_rules")),
            negative=string_list(package.get("provider_negative_rules")),
            provider_requirements=[{"type": "resolved_reference_policy", "package_id": package.get("package_id")}],
            stages=["reference_policy", "generation_prompt", "negative_prompt", "provider_input_plan"],
        )
