from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext, as_dict, string_list
from ..reference_channel_policy import reference_channel_issue_codes


class ReferenceChannelPolicyPlugin(BaseVisualCapabilityPlugin):
    capability_id = "reference_channel_policy"

    def contribute(self, context: VisualPluginContext):
        package = as_dict(context.cluster.get("resolved_reference_policy_package"))
        if not package.get("applies"):
            return self.contribution(context)
        issues = sorted(reference_channel_issue_codes(package))
        return self.contribution(
            context,
            prompt=string_list(package.get("provider_prompt_rules")),
            negative=string_list(package.get("provider_negative_rules")),
            provider_requirements=[{"type": "resolved_reference_policy", "package_id": package.get("package_id")}],
            review={
                "issue_codes": issues,
                "score_dimensions": ["reference_channel_fidelity", "prompt_ownership"],
            },
            retry={"issue_codes": issues, "require_reference_image": True},
            stages=[
                "reference_policy",
                "generation_prompt",
                "negative_prompt",
                "provider_input_plan",
                "post_generation_review",
                "retry_patch",
            ],
        )
