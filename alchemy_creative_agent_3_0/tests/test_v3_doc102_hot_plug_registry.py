from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import VisualCapabilityManifest
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.plugins import BaseVisualCapabilityPlugin


class FuturePlugin(BaseVisualCapabilityPlugin):
    capability_id = "future_scene_material"

    def contribute(self, context):
        return self.contribution(context, prompt=["future material rule"], stages=["generation_prompt"])


def test_hot_plug_adds_catalog_and_plugin_without_brain_source_change() -> None:
    runtime = ScenarioRuntime()
    runtime.register_visual_capability(
        VisualCapabilityManifest(
            capability_id="future_scene_material",
            display_name="Future scene material",
            contribution_stages=["generation_prompt"],
            compatible_templates=["general_template"],
        ),
        "visual_capability_cluster",
        FuturePlugin(),
    )
    snapshot = runtime.visual_capability_registry.catalog_snapshot("general_template", "general_creative")
    assert snapshot.manifest("future_scene_material") is not None
    assert runtime.visual_cluster_plugin_registry.plugin("future_scene_material") is not None


def test_hot_plug_rolls_back_manifest_when_plugin_registration_fails() -> None:
    runtime = ScenarioRuntime()
    runtime.visual_cluster_plugin_registry.register(FuturePlugin())
    try:
        runtime.register_visual_capability(
            VisualCapabilityManifest(
                capability_id="future_scene_material",
                display_name="Duplicate",
                contribution_stages=["generation_prompt"],
            ),
            "visual_capability_cluster",
            FuturePlugin(),
        )
    except ValueError:
        pass
    assert runtime.visual_capability_registry.manifest("future_scene_material") is None
