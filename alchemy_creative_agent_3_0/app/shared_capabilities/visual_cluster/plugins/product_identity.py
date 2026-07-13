from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext


class ProductIdentityPlugin(BaseVisualCapabilityPlugin):
    capability_id = "product_identity"

    def contribute(self, context: VisualPluginContext):
        issues = ["product_identity_drift", "product_label_drift", "brand_asset_drift"]
        return self.contribution(
            context,
            prompt=[
                "preserve the product geometry, silhouette, material, color, proportions, structural parts, pattern, and label placement when reference truth is available",
                "allow background, camera, lighting, and context changes without replacing the product",
            ],
            negative=["avoid generic product replacement", "avoid changed labels, logos, structure, pattern, or proportions"],
            review={"issue_codes": issues, "score_dimensions": ["product_fidelity"]},
            retry={
                "issue_codes": issues,
                "templates": {
                    "product_reinforcement": [
                        "preserve the supplied product's label/logo placement, readable label hierarchy, package silhouette, materials, proportions, and visible identity without inventing new copy",
                    ],
                    "negative_additions": [
                        "changed product label",
                        "changed logo placement",
                        "generic replacement packaging",
                    ],
                },
            },
            stages=["generation_prompt", "negative_prompt", "provider_input_plan", "post_generation_review", "retry_patch"],
        )
