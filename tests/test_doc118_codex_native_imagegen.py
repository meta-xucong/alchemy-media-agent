"""Doc118 N1 contract regression: initially red before implementation."""

from services.alchemy_codex_local_adapter.native_planner import CodexNativeImageGenPlanner


def test_native_planner_has_no_generation_provider_surface() -> None:
    planner = CodexNativeImageGenPlanner()
    assert callable(planner.prepare_native_imagegen_plan)
