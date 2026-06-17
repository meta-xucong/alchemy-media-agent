from __future__ import annotations

import asyncio

from app.config import settings
from app.repositories import repository
from app.schemas import CreateImageJobRequest, ImagePromptPlan
from app.services import generation as generation_service
from app.services.image_history import list_image_history
from app.services.prompt_transform.guard import extract_constraints
from app.services.prompt_transform.mode import resolve_modes
from app.services.prompt_transform.transformer import transform_prompt_plan


def setup_function() -> None:
    repository.reset()


def test_guard_extracts_commerce_constraints_without_internal_ids() -> None:
    constraints = extract_constraints(
        "产品目标人群是宝妈为主，文案标题设计偏儿童Q版卡通化，色彩偏淡彩，限制：不要水印，不要品牌logo"
    )

    assert "目标人群：宝妈为主" in constraints
    assert "标题字体/标题设计：文案标题设计偏儿童Q版卡通化" in constraints
    assert "色彩：偏淡彩" in constraints
    assert "限制：不要水印，不要品牌logo" in constraints


def test_guard_compacts_v2_template_lock_constraints_without_losing_user_limits() -> None:
    prompt = (
        "TEMPLATE LOCK: the selected case is the highest-priority visual template. "
        "Visual Grammar Lock: inherit the selected template 'Premium skincare product hero image' as visual grammar, not literal content. "
        "Strong lock: preserve its main visual presence, composition framework, spatial hierarchy, layout rhythm, lighting logic, background density, mood, typography/information treatment, and design language. "
        "User semantic content controls the actual subject, product, food, brand, copy, QR code, offer, and business meaning: "
        "Create a premium studio product hero image for a deep emerald glass serum bottle with warm gold cap, ivory minimal background, soft rim lighting, glossy glass reflections, elegant negative space, no visible brand logo, no readable text. "
        "Uploaded assets are evidence and slot variables. "
        "Conflict policy: visual grammar wins over Claude draft wording and uploaded source layout; user semantics win over the anchor's original literal subject and copy. "
        "Client request to adapt into the template: Create a premium studio product hero image for a deep emerald glass serum bottle with warm gold cap, ivory minimal background, no visible brand logo, no readable text."
    )

    constraints = extract_constraints(prompt)
    joined = "\n".join(constraints)

    assert any(item.startswith("模板锁：") for item in constraints)
    assert "no visible brand logo" in joined
    assert "no readable text" in joined
    assert len(constraints) <= 6
    assert all(len(item) <= 360 for item in constraints)
    assert "Conflict policy: visual grammar wins over Claude draft wording" not in joined


def test_guard_splits_english_prompt_clauses_before_marker_extraction() -> None:
    prompt = (
        "Create a realistic sweet-style portrait photo of a beautiful fictional East Asian adult woman in her late 20s. "
        "Soft natural makeup, warm gentle smile, fresh warm pastel palette, waist-up framing. "
        "No visible brand logos, no readable text, non-sensual, tasteful."
    )

    constraints = extract_constraints(prompt)
    joined = "\n".join(constraints)

    assert "色彩：fresh warm pastel" in joined
    assert "Logo/品牌：No visible brand logos" in joined
    assert all(len(item) < 180 for item in constraints)
    assert "Create a realistic sweet-style portrait" not in joined


def test_mode_resolver_keeps_template_customize_stable_by_default() -> None:
    template_plan = ImagePromptPlan(plan_id="plan_template", mode="template_customize", prompt="Use selected template.")
    enhance_plan = ImagePromptPlan(plan_id="plan_enhance", mode="smart_enhance", prompt="Make a poster.")
    explicit_plan = ImagePromptPlan(
        plan_id="plan_explicit",
        mode="template_customize",
        prompt="Make a poster.",
        user_variables={"prompt_transform_mode": "enhanced"},
    )

    assert resolve_modes(template_plan)["fidelity_mode"] == "original"
    assert resolve_modes(enhance_plan)["fidelity_mode"] == "strict"
    assert resolve_modes(explicit_plan)["fidelity_mode"] == "strict"


def test_mode_resolver_accepts_transform_and_fidelity_aliases() -> None:
    strict_plan = ImagePromptPlan(
        plan_id="plan_strict_alias",
        mode="template_customize",
        prompt="Make a poster.",
        user_variables={"prompt_transform_mode": "strict"},
    )
    original_plan = ImagePromptPlan(
        plan_id="plan_original_alias",
        mode="smart_enhance",
        prompt="Make a poster.",
        user_variables={"prompt_transform_mode": "original"},
    )
    off_plan = ImagePromptPlan(
        plan_id="plan_off_alias",
        mode="smart_enhance",
        prompt="Make a poster.",
        user_variables={"prompt_transform_mode": "off"},
    )

    assert resolve_modes(strict_plan)["fidelity_mode"] == "strict"
    assert resolve_modes(original_plan)["fidelity_mode"] == "original"
    assert resolve_modes(off_plan)["fidelity_mode"] == "off"


def test_mode_resolver_ignores_deprecated_prompt_transform_strength() -> None:
    plan = ImagePromptPlan(
        plan_id="plan_deprecated_strength",
        mode="template_customize",
        prompt="限制：不要水印，标题必须清晰。",
        user_variables={"prompt_transform_mode": "enhanced", "prompt_transform_strength": "strict"},
    )

    mode_info = resolve_modes(plan)

    assert mode_info["transform_mode"] == "enhanced"
    assert mode_info["fidelity_mode"] == "strict"
    assert "transform_strength" not in mode_info


def test_transformer_prefers_existing_generation_prompt_and_preserves_prompt_field() -> None:
    plan = ImagePromptPlan(
        plan_id="plan_transform",
        mode="smart_enhance",
        prompt="Original plan prompt should stay untouched.",
        user_variables={
            "generation_prompt": "文案标题设计偏儿童Q版卡通化，限制：不要水印",
            "prompt_transform_mode": "enhanced",
        },
    )

    transformed = transform_prompt_plan(plan)

    assert transformed.prompt == "Original plan prompt should stay untouched."
    assert transformed.user_variables["generation_prompt"].startswith("提示词保真规则")
    assert "文案标题设计偏儿童Q版卡通化" in transformed.user_variables["generation_prompt"]
    metadata = transformed.user_variables["prompt_transform"]
    assert metadata["fidelity_mode"] == "strict"
    assert metadata["applied"] is True
    assert metadata["constraint_count"] >= 1
    assert "case_id" not in str(metadata)
    assert "asset_id" not in str(metadata)
    assert "provider_id" not in str(metadata)
    assert "source_url" not in str(metadata)


def test_transformer_enhanced_mode_uses_fixed_guard_without_strength_metadata() -> None:
    plan = ImagePromptPlan(
        plan_id="plan_fixed_enhanced",
        mode="smart_enhance",
        prompt="标题必须清晰，限制：不要水印，不要Logo。",
        user_variables={"prompt_transform_mode": "enhanced", "prompt_transform_strength": "strict"},
    )

    transformed = transform_prompt_plan(plan)
    generation_prompt = transformed.user_variables["generation_prompt"]
    metadata = transformed.user_variables["prompt_transform"]

    assert "prompt_transform_strength" not in transformed.user_variables
    assert "transform_strength" not in metadata
    assert "不得把明确的禁止项" in generation_prompt
    assert "不要水印" in generation_prompt


def test_transformer_sanitizes_internal_identifiers_from_final_prompt_and_metadata() -> None:
    plan = ImagePromptPlan(
        plan_id="plan_no_internal_leaks",
        mode="smart_enhance",
        prompt=(
            "Use case_github_evolinkai_ad_0001 and asset_product_123 as references. "
            "case_id asset_id provider_id source_url api_key API EvoLinkAI repository storage."
        ),
        user_variables={"prompt_transform_mode": "enhanced"},
    )

    transformed = transform_prompt_plan(plan)
    generation_prompt = transformed.user_variables["generation_prompt"]
    metadata_text = str(transformed.user_variables["prompt_transform"])

    for leaked in (
        "case_github_evolinkai_ad_0001",
        "asset_product_123",
        "case_id",
        "asset_id",
        "provider_id",
        "source_url",
        "api_key",
        "API",
        "EvoLinkAI",
        "repository",
        "storage",
    ):
        assert leaked not in generation_prompt
        assert leaked not in metadata_text
    assert "selected visual reference" in generation_prompt
    assert "uploaded visual reference" in generation_prompt


def test_transformer_preserves_newlines_when_no_identifier_sanitization_is_needed() -> None:
    prompt = "Line one with spacing.\nLine two remains separate."
    plan = ImagePromptPlan(plan_id="plan_newlines", mode="template_customize", prompt=prompt)

    transformed = transform_prompt_plan(plan)

    assert transformed.user_variables["generation_prompt"] == prompt
    assert transformed.user_variables["prompt_transform"]["fidelity_mode"] == "original"


def test_transformer_original_and_off_modes_pass_through() -> None:
    stable_plan = ImagePromptPlan(
        plan_id="plan_stable",
        mode="template_customize",
        prompt="TEMPLATE LOCK prompt remains unchanged.",
    )
    off_plan = ImagePromptPlan(
        plan_id="plan_off",
        mode="smart_enhance",
        prompt="Creative prompt remains plain.",
        user_variables={"prompt_transform_mode": "exploration"},
    )

    stable = transform_prompt_plan(stable_plan)
    off = transform_prompt_plan(off_plan)

    assert stable.user_variables["generation_prompt"] == stable_plan.prompt
    assert stable.user_variables["prompt_transform"]["fidelity_mode"] == "original"
    assert stable.user_variables["prompt_transform"]["applied"] is False
    assert off.user_variables["generation_prompt"] == off_plan.prompt
    assert off.user_variables["prompt_transform"]["fidelity_mode"] == "off"
    assert off.user_variables["prompt_transform"]["applied"] is False


def test_transformer_is_idempotent_for_already_transformed_plan() -> None:
    plan = ImagePromptPlan(
        plan_id="plan_idempotent",
        mode="smart_enhance",
        prompt="文案标题设计偏儿童Q版卡通化",
    )

    once = transform_prompt_plan(plan)
    twice = transform_prompt_plan(once)

    assert twice.user_variables["generation_prompt"] == once.user_variables["generation_prompt"]
    assert twice.user_variables["generation_prompt"].count("提示词保真规则") == 1


def test_generation_applies_prompt_transform_to_job_and_history(tmp_path) -> None:
    object.__setattr__(settings, "persist_image_history", True)
    object.__setattr__(settings, "image_history_path", tmp_path / "image_history.jsonl")
    object.__setattr__(settings, "storage_dir", tmp_path / "storage")
    request = CreateImageJobRequest(
        prompt_plan=ImagePromptPlan(
            plan_id="plan_generation",
            mode="smart_enhance",
            prompt="文案标题设计偏儿童Q版卡通化，限制：不要水印",
            provider_parameters={"count": 1},
        ),
        provider_hint="mock_image",
    )

    job = asyncio.run(generation_service.create_image_job(request, job_id="job_prompt_transform"))

    assert job.status == "completed"
    assert job.prompt_plan.prompt == request.prompt_plan.prompt
    generation_prompt = job.prompt_plan.user_variables["generation_prompt"]
    assert generation_prompt.startswith("提示词保真规则")
    assert job.prompt_plan.user_variables["prompt_transform"]["fidelity_mode"] == "strict"
    assert job.prompt_plan.user_variables["prompt_transform"]["applied"] is True
    history = list_image_history(limit=10, include_all=True)
    assert history.total == 1
    assert history.items[0].prompt == generation_prompt
    assert history.items[0].metadata["final_prompt"] == generation_prompt
    assert history.items[0].metadata["prompt_transform"]["fidelity_mode"] == "strict"


def test_generation_transform_failure_falls_back_without_blocking(monkeypatch) -> None:
    def fail_transform(plan):
        raise RuntimeError("transform exploded")

    monkeypatch.setattr(generation_service, "transform_prompt_plan", fail_transform)
    request = CreateImageJobRequest(
        prompt_plan=ImagePromptPlan(
            plan_id="plan_fallback",
            mode="smart_enhance",
            prompt="Plain fallback prompt.",
            provider_parameters={"count": 1},
        ),
        provider_hint="mock_image",
    )

    job = asyncio.run(generation_service.create_image_job(request, job_id="job_prompt_transform_fallback"))

    assert job.status == "completed"
    assert job.prompt_plan.user_variables["generation_prompt"] == "Plain fallback prompt."
    assert job.prompt_plan.user_variables["prompt_transform"]["fallback_used"] is True
    assert "RuntimeError" in job.prompt_plan.user_variables["prompt_transform"]["error"]
