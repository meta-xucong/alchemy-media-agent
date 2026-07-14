import base64
import sys
from types import SimpleNamespace
from io import BytesIO
from pathlib import Path

from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.providers import V3LLMBrainProvider
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode import PersistentProjectStore
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)
from app.schemas import ImageGenerationResult


def _png_base64(width: int = 80, height: int = 80) -> str:
    from PIL import Image

    image = Image.new("RGB", (width, height), color=(80, 120, 160))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _write_reference(path: Path) -> Path:
    path.write_bytes(base64.b64decode(_png_base64()))
    return path


def test_general_runtime_runs_v3_brain_before_prompt_compilation(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "false")
    runtime = ScenarioRuntime()

    response = runtime.plan_job(
        {
            "user_input": "生成一张清爽高级的夏季饮料宣传图，画面干净明亮，适合社媒封面",
            "scenario_selection": {
                "scenario_id": "general_creative",
                "preset_id": "campaign_poster",
                "parameters": {"requested_image_count": 3},
            },
            "metadata": {
                "template_id": "general_template",
                "requested_image_count": 3,
                "project_context_snapshot": {
                    "project_id": "project_brain_test",
                    "goal_summary": "清爽高级的夏季饮料宣传图",
                    "confirmed_visual_tone": ["清爽", "高级"],
                    "selected_output_assets": [{"output_id": "v3_output_selected", "selection_reason": "bright premium style"}],
                    "selected_reference_assets": [
                        {
                            "asset_ref_id": "v3_output_selected",
                            "source_type": "generated_selected",
                            "use_policy": "style",
                        }
                    ],
                    "negative_direction_notes": ["不要暗色脏乱背景"],
                },
            },
        }
    )

    assert response.status == "planned"
    assert response.metadata["llm_brain"]["enabled"] is True
    assert response.metadata["llm_brain"]["fallback_used"] is True
    assert response.metadata["llm_brain"]["checkpoints"]
    assert response.metadata["llm_brain"]["checkpoints"][0]["checkpoint_id"] == "intent"
    assert response.metadata["shared_capabilities"]["visual_cluster"]["project_id"] == "project_brain_test"
    result = response.planning_result
    assert result is not None
    assert result.metadata["llm_brain"]["project_memory_digest"]["selected_reference_count"] == 1
    prompt = result.prompt_compilations[0]
    assert "V3 refined direction" in prompt.visual_prompt
    assert "夏季饮料" in prompt.visual_prompt
    assert "不要暗色脏乱背景" in prompt.negative_prompt
    assert prompt.metadata["llm_brain_enabled"] is True


def test_llm_brain_adapter_skips_non_general_scope(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "false")
    request = BrainRunRequest(
        user_input="生成一组商品图",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
    )

    result = V3LLMBrainAdapter().run(request)

    assert result.skipped is True
    assert result.enabled is False
    assert result.provider == "disabled"
    assert "general template" in result.audit["skip_reason"]


def test_general_brain_uses_variation_mode_for_candidate_batches(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "false")
    adapter = V3LLMBrainAdapter()
    request = adapter.build_request(
        user_input="同一个东方夏日人物，小幅变化姿势，多给几张相似备选写真",
        stage="generate",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={
            "requested_image_count": 3,
            "variation_mode": "selection_candidates",
            "effective_variation_mode": "selection_candidates",
            "variation_mode_source": "manual",
        },
    )

    result = adapter.run(request)

    assert result.fallback_used is True
    assert result.image_set_plan.shot_plan[0].startswith("near-identical candidate")
    assert "near-neighbor options" in result.prompt_guidance.visual_direction_addons[-1]
    assert "general variation mode applied: selection_candidates" in result.prompt_review.checks
    assert result.audit["human_natural_variation"]["applies"] is True
    addons = " ".join(result.prompt_guidance.visual_direction_addons)
    negatives = " ".join(result.prompt_guidance.negative_prompt_addons)
    assert "same recognizable person and body type" in addons
    assert "natural professional variation in expression" in addons
    assert "same exact expression in every image" in negatives
    assert "human identity and natural variation balanced" in result.prompt_review.checks


def test_brain_request_excludes_retired_internal_copy_render_plans() -> None:
    adapter = V3LLMBrainAdapter()
    request = adapter.build_request(
        user_input="Create one neutral creative image.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={
            "text_pixel_delivery_internal": {
                "copy_render_plans": [
                    {
                        "expected_copy": "Private approved headline",
                        "locale": "zh-CN",
                        "source_lineage": {"source_asset_id": "asset_private"},
                        "metadata": {"slot": "private-template-role", "platform": "private-platform"},
                    }
                ]
            }
        },
    )

    assert "text_pixel_delivery_internal" not in request.metadata
    assert "copy_render_plan" not in request.metadata
    assert "Private approved headline" not in str(request.metadata)
    assert "private-template-role" not in str(request.metadata)
    assert "private-platform" not in str(request.metadata)


def test_brain_request_exposes_literal_provider_native_copy_without_template_geometry() -> None:
    request = V3LLMBrainAdapter().build_request(
        user_input="Create one neutral creative image.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={
            "scenario_parameters": {
                "approved_copy": "Approved provider-native headline",
            }
        },
    )

    assert request.metadata["provider_native_text_requirements"] == ["Approved provider-native headline"]
    assert "feature_image_1" not in str(request.metadata["provider_native_text_requirements"])


def test_general_brain_uses_doc58_suite_roles_and_strong_anchor(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "false")
    adapter = V3LLMBrainAdapter()
    request = adapter.build_request(
        user_input="Create a green-haired East Asian summer portrait suite with the same model but different useful shots",
        stage="generate",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={
            "requested_image_count": 3,
            "variation_mode": "delivery_suite",
            "project_context_snapshot": {
                "project_id": "project_doc58_brain",
                "context_version": "context_doc58",
                "goal_summary": "green-haired East Asian summer portrait suite",
                "confirmed_visual_tone": ["summer daylight", "clean portrait"],
                "selected_output_assets": [
                    {
                        "output_id": "v3_output_anchor",
                        "asset_id": "asset_anchor",
                        "candidate_id": "candidate_anchor",
                        "selection_reason": "best identity anchor",
                        "metadata": {"file_path": "D:/tmp/anchor.png"},
                    }
                ],
                "strong_reference_continuation_plan": {
                    "active_anchor_ids": ["anchor_1"],
                    "provider_required_reference_ids": ["asset_anchor"],
                    "prompt_additions": ["use selected project output as the strongest positive reference"],
                    "negative_additions": ["same exact expression, pose, and head angle across the full batch"],
                },
                "general_suite_role_plan": {
                    "variation_mode": "delivery_suite",
                    "requested_image_count": 3,
                    "roles": [
                        {"label": "cover_hero", "purpose": "Cover image", "shot_instruction": "hero portrait with strongest first impression"},
                        {"label": "portrait_or_subject_focus", "purpose": "Subject focus", "shot_instruction": "closer subject-led frame"},
                        {"label": "side_or_three_quarter_angle", "purpose": "Angle variation", "shot_instruction": "three-quarter angle from the same shoot"},
                    ],
                },
                "batch_identity_diversity_review": {
                    "applies": True,
                    "retry_patch": {"negative_additions": ["cloned stills"]},
                },
                "visual_grammar_snapshot": {
                    "snapshot_id": "snapshot_doc58",
                    "project_id": "project_doc58_brain",
                    "context_version": "context_doc58",
                    "positive_anchor_output_ids": ["v3_output_anchor"],
                    "style_rules": ["summer daylight", "green hair direction"],
                    "continuity_strength": "strong",
                },
            },
        },
    )

    result = adapter.run(request)

    assert result.fallback_used is True
    assert result.image_set_plan.shot_plan[0].startswith("Cover image")
    assert result.image_set_plan.shot_plan[2].startswith("Angle variation")
    joined_addons = " ".join(result.prompt_guidance.visual_direction_addons)
    joined_negatives = " ".join(result.prompt_guidance.negative_prompt_addons)
    assert "Planned image role 1 (cover_hero)" in joined_addons
    assert "strongest positive reference" in joined_addons
    assert "cloned stills" in joined_negatives
    assert "Doc58 identity anchor and suite director applied" in result.prompt_review.checks
    assert result.audit["doc58"]["strong_reference_plan"]["active_anchor_ids"] == ["anchor_1"]


def test_real_image_request_allows_remote_brain_without_v3_specific_key(monkeypatch) -> None:
    monkeypatch.delenv("V3_LLM_BRAIN_REMOTE_ENABLED", raising=False)
    monkeypatch.delenv("V3_LLM_BRAIN_API_KEY", raising=False)

    class FakeBrainProvider:
        provider = "openai"
        model = "test-brain-model"
        force_seen = False

        def available(self, *, force: bool = False) -> bool:
            self.force_seen = force
            return force

        def run(self, request):  # noqa: ANN001
            assert request.metadata["require_real_images"] is True
            return {
                "prompt_guidance": {
                    "optimized_direction": "remote refined summer portrait direction",
                    "style_notes": ["remote premium summer light"],
                    "consistency_strategy": "remote selected references stay strongest",
                },
                "user_visible_summary": {
                    "headline": "V3 has refined this image direction.",
                    "progress_messages": ["Remote brain understood the project"],
                },
                "checkpoints": [
                    {
                        "checkpoint_id": "intent",
                        "stage": "remote_intent",
                        "status": "completed",
                        "summary": "Remote brain clarified the intent.",
                    }
                ],
            }

    provider = FakeBrainProvider()
    adapter = V3LLMBrainAdapter(provider=provider)
    request = adapter.build_request(
        user_input="Create a refined summer portrait set",
        stage="generate",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={"require_real_images": True, "requested_image_count": 2},
    )

    result = adapter.run(request)

    assert provider.force_seen is True
    assert result.llm_used is True
    assert result.fallback_used is False
    assert result.provider == "openai"
    assert result.prompt_guidance.optimized_direction == "remote refined summer portrait direction"
    assert len(result.checkpoints) >= 6
    assert result.checkpoints[0].stage == "remote_intent"
    assert {checkpoint.checkpoint_id for checkpoint in result.checkpoints} >= {
        "intent",
        "context",
        "visual_strategy",
        "prompt_guidance",
        "pre_generation_review",
        "post_generation_review",
    }


def test_remote_brain_default_timeout_allows_slow_reasoning(monkeypatch) -> None:
    monkeypatch.delenv("V3_LLM_BRAIN_TIMEOUT_SECONDS", raising=False)

    provider = V3LLMBrainProvider()

    assert provider.timeout >= 120


def test_remote_brain_uses_declared_deepseek_brain_not_openai_image_gateway(monkeypatch) -> None:
    """A configured default Brain must win over an unrelated OpenAI image key."""

    from app.config import settings

    monkeypatch.delenv("V3_LLM_BRAIN_PROVIDER", raising=False)
    monkeypatch.delenv("V3_LLM_BRAIN_MODEL", raising=False)
    monkeypatch.delenv("V3_LLM_BRAIN_API_KEY", raising=False)
    monkeypatch.delenv("V3_LLM_BRAIN_BASE_URL", raising=False)
    monkeypatch.setattr(settings, "default_llm_provider", "deepseek")
    monkeypatch.setattr(settings, "default_llm_model", "deepseek-primary")
    monkeypatch.setattr(settings, "deepseek_llm_model", "deepseek-primary")
    monkeypatch.setattr(settings, "deepseek_llm_api_key", "deepseek-test-key")
    monkeypatch.setattr(settings, "deepseek_llm_base_url", "https://brain.example.test/v1")
    monkeypatch.setattr(settings, "openai_api_key", "image-gateway-key")
    monkeypatch.setattr(settings, "openai_base_url", "https://image.example.test/v1")

    provider = V3LLMBrainProvider()

    assert provider.provider == "deepseek"
    assert provider.model == "deepseek-primary"
    assert provider.available(force=True) is True
    api_key, base_url = provider._credentials()  # noqa: SLF001 - configuration boundary assertion
    assert api_key == "deepseek-test-key"
    assert base_url == "https://brain.example.test/v1"


def test_declared_deepseek_brain_uses_remote_chat_completions_transport(monkeypatch) -> None:
    """DeepSeek remains a remote Brain without depending on Responses support."""

    from app.config import settings

    calls: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs):  # noqa: ANN003
            calls["chat_kwargs"] = kwargs
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"remote": true}'))]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):  # noqa: ANN003
            calls["client_kwargs"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

        @property
        def responses(self):
            raise AssertionError("DeepSeek Brain must not use the Responses transport")

    monkeypatch.delenv("V3_LLM_BRAIN_PROVIDER", raising=False)
    monkeypatch.delenv("V3_LLM_BRAIN_MODEL", raising=False)
    monkeypatch.delenv("V3_LLM_BRAIN_API_KEY", raising=False)
    monkeypatch.delenv("V3_LLM_BRAIN_BASE_URL", raising=False)
    monkeypatch.setattr(settings, "default_llm_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_llm_model", "deepseek-primary")
    monkeypatch.setattr(settings, "deepseek_llm_api_key", "deepseek-test-key")
    monkeypatch.setattr(settings, "deepseek_llm_base_url", "https://brain.example.test/v1")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    provider = V3LLMBrainProvider()
    result = provider._run_openai_compatible(  # noqa: SLF001 - provider transport contract
        BrainRunRequest(user_input="Create one remote photography direction.")
    )

    assert result == {"remote": True}
    assert calls["client_kwargs"] == {
        "api_key": "deepseek-test-key",
        "base_url": "https://brain.example.test/v1",
    }
    chat_kwargs = calls["chat_kwargs"]
    assert isinstance(chat_kwargs, dict)
    assert chat_kwargs["model"] == "deepseek-primary"
    assert chat_kwargs["response_format"] == {"type": "json_object"}


def test_remote_brain_explicit_v3_provider_still_overrides_default(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setenv("V3_LLM_BRAIN_PROVIDER", "openai")
    monkeypatch.setenv("V3_LLM_BRAIN_MODEL", "brain-override")
    monkeypatch.setenv("V3_LLM_BRAIN_API_KEY", "brain-override-key")
    monkeypatch.setenv("V3_LLM_BRAIN_BASE_URL", "https://override.example.test/v1")
    monkeypatch.setattr(settings, "default_llm_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_llm_api_key", "deepseek-test-key")

    provider = V3LLMBrainProvider()

    assert provider.provider == "openai"
    assert provider.model == "brain-override"
    api_key, base_url = provider._credentials()  # noqa: SLF001 - configuration boundary assertion
    assert api_key == "brain-override-key"
    assert base_url == "https://override.example.test/v1"


def test_remote_brain_rejects_internally_inconsistent_image_set_plan(monkeypatch) -> None:
    class InconsistentImageSetProvider:
        provider = "openai"
        model = "remote-cardinality-test"

        def available(self, *, force: bool = False) -> bool:
            return True

        def run(self, request):  # noqa: ANN001
            return {
                "image_set_plan": {
                    "set_goal": "incorrectly over-expanded plan",
                    "image_count": 1,
                    "shot_plan": ["first", "second", "third"],
                },
                "prompt_guidance": {"optimized_direction": "remote creative direction remains usable"},
            }

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    adapter = V3LLMBrainAdapter(provider=InconsistentImageSetProvider())
    request = adapter.build_request(
        user_input="Create one calm continuation image.",
        stage="generate",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={"requested_image_count": 1, "require_real_images": True},
    )

    result = adapter.run(request)

    assert result.llm_used is True
    assert result.fallback_used is False
    assert result.image_set_plan.image_count == 1
    assert len(result.image_set_plan.shot_plan) == 1
    assert result.audit["remote_contract_partial_fallback"] is True
    assert result.audit["remote_contract_rejected_sections"] == ["image_set_plan"]


def test_provider_reads_project_reference_assets_for_continuation(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"

    reference_path = _write_reference(tmp_path / "selected-style.png")
    asset = AssetSpec(
        asset_id="asset_v3_brain",
        asset_type=AssetType.SINGLE_IMAGE,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="1:1",
        purpose="same-style continuation",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_v3_brain",
        asset_id=asset.asset_id,
        visual_prompt="clean bright social cover",
        negative_prompt="fake text",
        text_policy="do_not_render_final_text_in_image_model",
        style_notes=["clean"],
        layout_notes=["center subject"],
    )
    request = GenerationRequest(
        asset_spec=asset,
        prompt_compilation=prompt,
        condition_plan=ConditionPlan(condition_plan_id="condition_v3_brain", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_v3_brain",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_v3_brain_provider",
            "reference_assets": [
                {
                    "asset_id": "v3_output_selected",
                    "role": "style",
                    "file_path": str(reference_path),
                    "filename": reference_path.name,
                    "mime_type": "image/png",
                }
            ],
        },
    )

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        assert provider_name == "openai_gpt_image"
        assert app_request.asset_plan["provider_input_plan"]["reference_image_count"] == 1
        assert app_request.asset_plan["assets"][0]["storage_path"] == str(reference_path)
        return ImageGenerationResult(
            provider="openai_gpt_image",
            model="test-image-model",
            outputs=[{"b64_json": _png_base64(), "mime_type": "image/png", "format": "png"}],
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    try:
        provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
        response = provider.generate(request)
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider

    assert response.provider_metadata["reference_asset_count"] == 1
    assert response.candidates[0].metadata["reference_asset_ids"] == ["v3_output_selected"]


def test_selected_generated_output_context_contains_reusable_file_path(tmp_path) -> None:
    project_store = PersistentProjectStore(tmp_path / "v3_projects")
    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "v3_outputs")
    service = V3ProductApiService(output_store=output_store)
    handlers = V3ProductRouteHandlers(service=service, project_store=project_store)
    project = handlers.post_projects({"user_goal": "Create a clean bright portrait-led project"})["project"]
    job = handlers.post_project_job(project["project_id"], {"user_input": "Create the first portrait cover"})
    record = output_store.save_base64_output(
        job_id=job["job_id"],
        candidate_id="candidate_selected_file_path",
        asset_id="asset_selected_file_path",
        provider="test_provider",
        model="test-model",
        encoded_image=_png_base64(),
        mime_type="image/png",
        output_format="png",
    )
    restarted = V3ProductRouteHandlers(
        service=V3ProductApiService(output_store=output_store),
        project_store=PersistentProjectStore(tmp_path / "v3_projects"),
    )

    selected = restarted.post_project_job_select(
        project["project_id"],
        job["job_id"],
        {"selected_candidate_id": "candidate_selected_file_path"},
    )

    context_ref = selected["context"]["selected_reference_assets"][0]
    assert selected["context"]["selected_output_assets"][0]["output_id"] == record.output_id
    assert selected["context"]["visual_continuity_strength"] == "strong"
    assert record.output_id in selected["context"]["visual_grammar_snapshot"]["positive_anchor_output_ids"]
    assert selected["context"]["selected_visual_references"]
    assert context_ref["source_type"] == "generated_selected"
    assert context_ref["file_path"] == record.file_path
    assert context_ref["output_id"] == record.output_id


def test_project_can_select_a_persisted_partial_output_while_the_job_record_remains_blocked(tmp_path) -> None:
    project_store = PersistentProjectStore(tmp_path / "v3_projects")
    output_store = V3GeneratedOutputStore(storage_root=tmp_path / "v3_outputs")
    service = V3ProductApiService(output_store=output_store)
    handlers = V3ProductRouteHandlers(service=service, project_store=project_store)
    project = handlers.post_projects({"user_goal": "Create a clean glass still-life project"})["project"]
    job = handlers.post_project_job(
        project["project_id"],
        {"user_input": "Create a two-image clean glass still-life set."},
    )
    job_record = service.job_store.get(job["job_id"])
    assert job_record is not None
    job_record.status = ProductJobStatusValue.BLOCKED
    job_record.warnings.append("later_role_provider_failure")
    service.job_store.save(job_record)
    output = output_store.save_base64_output(
        job_id=job["job_id"],
        candidate_id="candidate_partial_project_output",
        asset_id="asset_partial_project_output",
        provider="test_provider",
        model="gpt-image-2",
        encoded_image=_png_base64(),
        mime_type="image/png",
        output_format="png",
    )

    selected = handlers.post_project_job_select(
        project["project_id"],
        job["job_id"],
        {"selected_candidate_id": "candidate_partial_project_output"},
    )

    assert selected["status"] == "selected"
    assert selected["job_status"]["metadata"]["selected_from_restored_outputs"] is True
    assert selected["context"]["selected_output_assets"][0]["output_id"] == output.output_id
