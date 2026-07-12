"""Deterministic fallback brain for V3 when remote LLM planning is unavailable."""

from __future__ import annotations

from .context_digest import clean_text, clean_text_list
from .contracts import (
    BrainCheckpoint,
    BrainImageSetPlan,
    BrainIntentSummary,
    BrainProjectMemoryDigest,
    BrainPromptGuidance,
    BrainPromptReview,
    BrainRunRequest,
    BrainRunResult,
    BrainUserVisibleSummary,
)
from ..creative_core.prompt_language import (
    product_language_allowed,
    split_positive_and_negative_prompt,
    strip_negated_product_phrases,
)
from ..creative_core.rules import stable_id
from ..shared_capabilities.activation import build_task_profile_and_intent


SINGLE_FRAME_HARD_CONSTRAINT = (
    "Each output is one single complete image frame; do not create collages, split screens, contact sheets, "
    "storyboards, before-after comparisons, or multi-panel layouts."
)
SINGLE_FRAME_NEGATIVE_RULES = [
    "avoid collage layouts",
    "avoid split-screen frames",
    "avoid contact sheets",
    "avoid storyboard panels",
    "avoid before-after comparison layouts",
    "avoid grids of separate images inside one output",
]


def build_fallback_result(request: BrainRunRequest, *, warning: str | None = None) -> BrainRunResult:
    allow_product_language = product_language_allowed(
        template_id=request.template_id,
        scenario_id=request.scenario_id,
        user_input=request.user_input,
        metadata=request.metadata,
        uploaded_assets=request.uploaded_assets,
        reference_assets=request.reference_assets,
    )
    project_context = request.project_context or {}
    visual_cluster = _visual_cluster_from_request(request)
    doc58 = _doc58_cluster_plans(visual_cluster)
    selected_outputs = list(request.selected_output_assets or [])
    uploaded_refs = list(request.uploaded_assets or [])
    reference_assets = list(request.reference_assets or [])
    negative_notes = clean_text_list(
        [
            *project_context.get("rejected_style_tags", []),
            *project_context.get("negative_direction_notes", []),
            *project_context.get("negative_visual_directions", []),
            *_cluster_negative_rules(visual_cluster),
        ],
        limit=12,
    )
    tone = clean_text_list(
        [
            *project_context.get("confirmed_visual_tone", []),
            *_cluster_style_rules(visual_cluster),
        ],
        limit=10,
    )
    goal = clean_text(project_context.get("goal_summary") or request.user_input, 260)
    use_scene = _scene_hint(request.user_input, allow_product_language=allow_product_language)
    mood = _mood_hints(request.user_input, tone, allow_product_language=allow_product_language)
    variation_mode = _variation_mode(request)
    shot_plan = _shot_plan(
        request.requested_image_count,
        request.user_input,
        bool(selected_outputs or reference_assets),
        variation_mode,
        suite_role_plan=doc58["suite_role_plan"],
    )
    variation_rules = _variation_mode_rules(variation_mode)
    human_anchor = _cluster_human_identity_anchor(visual_cluster)
    human_variation = _cluster_human_variation_plan(visual_cluster)
    if not human_variation:
        human_anchor, human_variation = _fallback_human_variation_contract(
            request=request,
            variation_mode=variation_mode,
            allow_product_language=allow_product_language,
        )
    human_variation_applies = bool(human_variation.get("applies"))
    human_prompt_addons = _string_values(human_variation.get("prompt_additions")) if human_variation_applies else []
    human_negative_addons = _string_values(human_variation.get("negative_additions")) if human_variation_applies else []
    human_review_rules = _string_values(human_variation.get("batch_review_rules")) if human_variation_applies else []
    continuity_rules = clean_text_list(
        [
            *[f"keep human identity anchor: {item}" for item in _string_values(human_anchor.get("locked_traits"))[:4]],
            *_continuity_rules(selected_outputs, reference_assets, tone),
            *_string_values(doc58["strong_reference_plan"].get("prompt_additions"))[:4],
            *_cluster_keep_rules(visual_cluster),
        ],
        limit=10,
    )
    negative_rules = list(
        dict.fromkeys(
            [
                *negative_notes,
                *_string_values(doc58["strong_reference_plan"].get("negative_additions")),
                *_string_values(doc58["batch_review"].get("retry_patch", {}).get("negative_additions")),
                *human_negative_addons,
                *SINGLE_FRAME_NEGATIVE_RULES,
                "avoid cluttered composition",
                "avoid random visible text",
            ]
        )
    )

    intent = BrainIntentSummary(
        user_goal=goal,
        scene=use_scene,
        audience=_audience_hint(request.user_input),
        output_use=_output_use(request.user_input, allow_product_language=allow_product_language),
        visual_mood=mood,
        must_keep=clean_text_list(
            [
                "main subject must stay clear and recognizable",
                (
                    "commercial image should be ready for publishing"
                    if allow_product_language
                    else "image should be polished and ready to use"
                ),
                *project_context.get("required_text_or_facts", []),
            ],
            limit=8,
        ),
        avoid=negative_rules[:8],
    )
    memory_digest = BrainProjectMemoryDigest(
        has_project_context=bool(project_context),
        selected_reference_count=len(selected_outputs),
        uploaded_reference_count=len(uploaded_refs) + len(reference_assets),
        positive_style_rules=clean_text_list([*tone, *_selected_reference_labels(selected_outputs)], limit=8),
        continuity_rules=continuity_rules,
        negative_rules=negative_rules,
    )
    image_plan = BrainImageSetPlan(
        set_goal=f"{variation_rules['set_goal']} for: {goal}",
        image_count=request.requested_image_count,
        size=request.requested_image_size,
        shot_plan=shot_plan,
        composition_rules=[
            "keep the subject prominent",
            "use clean commercial composition" if allow_product_language else "use clean professional composition",
            "leave usable negative space for later copy"
            if allow_product_language
            else "leave optional clean blank space when useful",
            "make each output a single complete frame",
            *variation_rules["composition_rules"],
            *_cluster_composition_rules(visual_cluster)[:3],
        ],
        quality_bar=[
            "polished lighting",
            "clear subject identity",
            "consistent style across the set",
            "no unreadable generated text",
            *variation_rules["quality_bar"],
            *human_review_rules[:3],
            *_cluster_quality_checks(visual_cluster)[:3],
        ],
    )
    optimized = _optimized_direction(request, mood, continuity_rules)
    prompt_guidance = BrainPromptGuidance(
        optimized_direction=optimized,
        visual_direction_addons=[
            optimized,
            *_cluster_prompt_addons(visual_cluster)[:4],
            *_string_values(doc58["strong_reference_plan"].get("prompt_additions"))[:4],
            *_suite_role_prompt_addons(doc58["suite_role_plan"], request.requested_image_count),
            *human_prompt_addons,
            "premium but natural commercial finish"
            if allow_product_language
            else "premium but natural professional finish",
            "coherent color palette and lighting across all outputs",
            variation_rules["prompt_addon"],
        ],
        style_notes=mood,
        layout_notes=image_plan.composition_rules,
        hard_constraints=[
            "Preserve the user's requested subject and usage scenario.",
            "Do not add visible captions, slogans, badges, or UI text into the image.",
            SINGLE_FRAME_HARD_CONSTRAINT,
            *variation_rules["hard_constraints"],
            *(
                [
                    "Follow the planned suite roles so the set has purposeful differences instead of repeating one image."
                ]
                if doc58["suite_role_plan"].get("roles")
                else []
            ),
            *(
                [
                    "Keep human identity, face direction, and body type consistent without copying the exact same expression, pose, head angle, or camera angle across the batch."
                ]
                if human_variation_applies
                else []
            ),
            *continuity_rules[:4],
        ],
        negative_prompt_addons=negative_rules,
        consistency_strategy=(
            "Use selected project images as strong style references and keep lighting, palette, framing, and subject treatment aligned."
            if selected_outputs or reference_assets
            else "Use the project goal as the first style anchor until the user selects a reference image."
        ),
    )
    prompt_review = BrainPromptReview(
        status="passed",
        checks=[
            "user goal preserved",
            "project context read",
            "selected references prioritized",
            f"general variation mode applied: {variation_mode}",
            "Doc58 identity anchor and suite director applied" if doc58["applies"] else "Doc58 suite director not required",
            "human identity and natural variation balanced" if human_variation_applies else "human variation not required",
            "visual capability cluster read" if visual_cluster else "visual capability cluster not required",
            "unsafe visible text avoided",
        ],
        fixes_applied=[
            "expanded vague request into a concrete commercial visual direction"
            if allow_product_language
            else "expanded vague request into a concrete visual direction",
            "added consistency constraints for same-project continuation",
            f"matched image-set plan to {variation_mode}",
            "assigned distinct image roles for the set" if doc58["suite_role_plan"].get("roles") else "",
            "used selected output as a strong project anchor" if doc58["strong_reference_plan"].get("active_anchor_ids") else "",
            "kept person identity stable while allowing natural expression, pose, angle, and hair styling changes"
            if human_variation_applies
            else "",
        ],
        warnings=[warning] if warning else [],
    )
    visible = BrainUserVisibleSummary(
        headline="V3 已经整理好更清晰的画面方向。",
        done=[
            "已理解这次图片的用途",
            "已整理画面风格和氛围",
            "已沿用项目里选中的参考" if selected_outputs else "已准备第一版视觉方向",
            "已检查生图前的描述是否清楚",
        ],
        next=[
            "生成这一组图片",
            "挑选满意结果作为后续参考",
            "沿着同一风格继续扩展",
        ],
        progress_messages=[
            "理解项目目标",
            "整理画面方向",
            "读取已选参考" if selected_outputs else "准备第一版风格锚点",
            "检查最终描述",
        ],
    )
    checkpoints = _build_checkpoints(
        request=request,
        intent=intent,
        memory_digest=memory_digest,
        image_plan=image_plan,
        prompt_guidance=prompt_guidance,
        prompt_review=prompt_review,
        visual_cluster=visual_cluster,
        human_variation_applies=human_variation_applies,
        warning=warning,
    )
    task_profile, activation_intent = build_task_profile_and_intent(
        user_input=request.user_input,
        job_id=stable_id("capability_job", request.project_id, request.user_input, request.stage),
        project_id=request.project_id,
        template_id=request.template_id or "general_template",
        scenario_id=request.scenario_id or "general_creative",
        uploaded_assets=list(request.uploaded_assets or []),
        reference_assets=list(request.reference_assets or []),
        product_profile=dict(request.product_profile or {}),
        metadata={
            **dict(request.metadata or {}),
            "requested_image_count": request.requested_image_count,
            "requested_image_size": request.requested_image_size,
        },
        template_policy=request.template_capability_policy,
    )
    checkpoints.insert(
        1 if checkpoints else 0,
        BrainCheckpoint(
            checkpoint_id="task_profile_and_capability_activation",
            stage="activation",
            summary="Classified the visual task and proposed evidence-backed capabilities.",
            inputs=["user request", "declared references", "template capability policy"],
            outputs=[task_profile.profile_id, activation_intent.intent_id],
            metadata={"hidden_reasoning_exposed": False},
        ),
    )
    return BrainRunResult(
        enabled=True,
        skipped=False,
        llm_used=False,
        fallback_used=True,
        provider="local",
        model="deterministic_v3_brain",
        intent_summary=intent,
        project_memory_digest=memory_digest,
        image_set_plan=image_plan,
        prompt_guidance=prompt_guidance,
        prompt_review=prompt_review,
        user_visible_summary=visible,
        checkpoints=checkpoints,
        warnings=[warning] if warning else [],
        audit={
            "source": "v3_local_fallback",
            "remote_reasoning_visible": False,
            "selected_outputs_used": len(selected_outputs),
            "reference_assets_used": len(reference_assets),
            "human_natural_variation": human_variation,
            "human_identity_anchor": human_anchor,
            "doc58": doc58,
        },
        visual_task_profile=task_profile,
        capability_activation_intent=activation_intent,
    )


def build_skipped_result(request: BrainRunRequest, reason: str) -> BrainRunResult:
    result = build_fallback_result(request, warning=reason)
    result.enabled = False
    result.skipped = True
    result.fallback_used = True
    result.provider = "disabled"
    result.audit = {**result.audit, "skip_reason": reason}
    return result


def _visual_cluster_from_request(request: BrainRunRequest) -> dict:
    shared = request.shared_capabilities if isinstance(request.shared_capabilities, dict) else {}
    direct = shared.get("visual_cluster")
    if isinstance(direct, dict) and direct:
        return direct
    for result in shared.get("results", []) if isinstance(shared.get("results"), list) else []:
        if not isinstance(result, dict) or result.get("module_id") != "visual_capability_cluster":
            continue
        facts = result.get("facts")
        if isinstance(facts, dict) and isinstance(facts.get("visual_capability_cluster"), dict):
            return facts["visual_capability_cluster"]
    context_snapshot = request.project_context.get("visual_grammar_snapshot") if isinstance(request.project_context, dict) else None
    if isinstance(context_snapshot, dict) and context_snapshot:
        return {
            "project_identity_anchors": request.project_context.get("project_identity_anchors", []),
            "strong_reference_continuation_plan": request.project_context.get("strong_reference_continuation_plan", {}),
            "general_suite_role_plan": request.project_context.get("general_suite_role_plan", {}),
            "batch_identity_diversity_review": request.project_context.get("batch_identity_diversity_review", {}),
            "project_snapshot": context_snapshot,
            "profile": {
                "style_signals": context_snapshot.get("style_rules", []),
                "composition_rules": context_snapshot.get("composition_rules", []),
                "palette_notes": context_snapshot.get("palette_rules", []),
                "lighting_notes": context_snapshot.get("lighting_rules", []),
                "negative_rules": context_snapshot.get("negative_directions", []),
            },
            "consistency_guard": {
                "continuity_strength": context_snapshot.get("continuity_strength", "weak"),
                "keep_rules": context_snapshot.get("style_rules", []),
                "avoid_rules": context_snapshot.get("negative_directions", []),
            },
        }
    return {}


def _cluster_profile(visual_cluster: dict) -> dict:
    profile = visual_cluster.get("profile") if isinstance(visual_cluster, dict) else {}
    return profile if isinstance(profile, dict) else {}


def _cluster_snapshot(visual_cluster: dict) -> dict:
    snapshot = visual_cluster.get("project_snapshot") if isinstance(visual_cluster, dict) else {}
    return snapshot if isinstance(snapshot, dict) else {}


def _cluster_guard(visual_cluster: dict) -> dict:
    guard = visual_cluster.get("consistency_guard") if isinstance(visual_cluster, dict) else {}
    return guard if isinstance(guard, dict) else {}


def _cluster_quality(visual_cluster: dict) -> dict:
    quality = visual_cluster.get("quality_review") if isinstance(visual_cluster, dict) else {}
    return quality if isinstance(quality, dict) else {}


def _cluster_identity_profiles(visual_cluster: dict) -> list[dict]:
    profiles = visual_cluster.get("identity_lock_profiles") if isinstance(visual_cluster, dict) else []
    return [item for item in profiles if isinstance(item, dict)] if isinstance(profiles, list) else []


def _cluster_human_identity_anchor(visual_cluster: dict) -> dict:
    anchor = visual_cluster.get("human_identity_anchor_profile") if isinstance(visual_cluster, dict) else {}
    return dict(anchor) if isinstance(anchor, dict) else {}


def _cluster_human_variation_plan(visual_cluster: dict) -> dict:
    plan = visual_cluster.get("human_natural_variation_plan") if isinstance(visual_cluster, dict) else {}
    return dict(plan) if isinstance(plan, dict) else {}


def _fallback_human_variation_contract(
    *,
    request: BrainRunRequest,
    variation_mode: str,
    allow_product_language: bool,
) -> tuple[dict, dict]:
    applies = bool(request.requested_image_count >= 2 and not allow_product_language)
    if not applies:
        return {}, {"applies": False, "variation_mode": variation_mode, "metadata": {"source": "fallback_no_cluster"}}
    anchor = {
        "applies": True,
        "anchor_source": "prompt_only",
        "locked_traits": [
            "same recognizable person and body type",
            "same identity direction while the current prompt owns hair, makeup, wardrobe, lighting, scene, camera, and style",
            "same visual world",
        ],
        "metadata": {
            "source": "fallback_no_cluster",
            "doc67_boundary_safe": True,
            "doc93_reference_channel_safe": True,
        },
    }
    plan = {
        "applies": True,
        "variation_mode": variation_mode,
        "identity_strength": "medium",
        "diversity_strength": "subtle" if variation_mode == "selection_candidates" else "medium",
        "prompt_additions": [
            "Keep the same recognizable person and body type across the set.",
            "Allow natural professional variation in expression, gaze, pose, head angle, camera angle, crop, and small hair styling details.",
            "Each image should feel like a different frame from the same professional shoot, not a duplicate of the same still.",
        ],
        "negative_additions": [
            "same exact expression in every image",
            "same exact head angle in every image",
            "same exact pose in every image",
            "cloned stills",
        ],
        "batch_review_rules": [
            "at least two outputs differ in expression or gaze",
            "at least two outputs differ in pose or body/head angle",
            "batch should not repeat the exact same expression, head angle, and pose across most images",
        ],
        "metadata": {"source": "fallback_no_cluster", "doc67_boundary_safe": True},
    }
    return anchor, plan


def _cluster_style_rules(visual_cluster: dict) -> list[str]:
    profile = _cluster_profile(visual_cluster)
    snapshot = _cluster_snapshot(visual_cluster)
    return clean_text_list(
        [
            *profile.get("style_signals", []),
            *snapshot.get("style_rules", []),
            *profile.get("lighting_notes", []),
            *profile.get("palette_notes", []),
        ],
        limit=10,
    )


def _cluster_keep_rules(visual_cluster: dict) -> list[str]:
    guard = _cluster_guard(visual_cluster)
    snapshot = _cluster_snapshot(visual_cluster)
    return clean_text_list(
        [
            *guard.get("keep_rules", []),
            *snapshot.get("style_rules", []),
            *snapshot.get("lighting_rules", []),
            *snapshot.get("palette_rules", []),
        ],
        limit=10,
    )


def _cluster_negative_rules(visual_cluster: dict) -> list[str]:
    profile = _cluster_profile(visual_cluster)
    snapshot = _cluster_snapshot(visual_cluster)
    guard = _cluster_guard(visual_cluster)
    return clean_text_list(
        [
            *profile.get("negative_rules", []),
            *snapshot.get("negative_directions", []),
            *guard.get("avoid_rules", []),
        ],
        limit=12,
    )


def _cluster_composition_rules(visual_cluster: dict) -> list[str]:
    profile = _cluster_profile(visual_cluster)
    snapshot = _cluster_snapshot(visual_cluster)
    return clean_text_list(
        [
            *profile.get("composition_rules", []),
            *snapshot.get("composition_rules", []),
            *profile.get("layout_notes", []),
            *profile.get("lens_notes", []),
        ],
        limit=8,
    )


def _cluster_quality_checks(visual_cluster: dict) -> list[str]:
    quality = _cluster_quality(visual_cluster)
    return clean_text_list(quality.get("checklist", []), limit=6)


def _cluster_prompt_addons(visual_cluster: dict) -> list[str]:
    profile = _cluster_profile(visual_cluster)
    snapshot = _cluster_snapshot(visual_cluster)
    guard = _cluster_guard(visual_cluster)
    role_plan = visual_cluster.get("role_specific_generation_plan") if isinstance(visual_cluster, dict) else {}
    if not isinstance(role_plan, dict):
        role_plan = {}
    role_metadata = role_plan.get("metadata") if isinstance(role_plan.get("metadata"), dict) else {}
    identity_plan = role_metadata.get("identity_hero_selection_plan") if isinstance(role_metadata, dict) else {}
    strict_policy = role_metadata.get("strict_visual_review_policy") if isinstance(role_metadata, dict) else {}
    addons: list[str] = []
    if snapshot.get("continuity_strength") == "strong":
        addons.append("strongly follow selected project image anchors for lighting, palette, framing, and subject treatment")
    addons.extend(profile.get("lighting_notes", []))
    addons.extend(profile.get("palette_notes", []))
    addons.extend(guard.get("keep_rules", []))
    addons.extend(role_plan.get("prompt_additions", []))
    if isinstance(identity_plan, dict):
        addons.extend(identity_plan.get("prompt_additions", []))
    if isinstance(strict_policy, dict):
        addons.extend(strict_policy.get("prompt_additions", []))
    return clean_text_list(addons, limit=12)


def _build_checkpoints(
    *,
    request: BrainRunRequest,
    intent: BrainIntentSummary,
    memory_digest: BrainProjectMemoryDigest,
    image_plan: BrainImageSetPlan,
    prompt_guidance: BrainPromptGuidance,
    prompt_review: BrainPromptReview,
    visual_cluster: dict,
    human_variation_applies: bool,
    warning: str | None,
) -> list[BrainCheckpoint]:
    visual_snapshot = _cluster_snapshot(visual_cluster)
    guard = _cluster_guard(visual_cluster)
    checkpoint_specs = [
        (
            "intent",
            "understood the user's requested subject, scene, and output use",
            [request.user_input],
            [intent.user_goal, intent.output_use or ""],
            [],
        ),
        (
            "context",
            "read project memory and selected references",
            [
                f"selected outputs: {memory_digest.selected_reference_count}",
                f"uploaded references: {memory_digest.uploaded_reference_count}",
            ],
            [*memory_digest.continuity_rules[:3], *memory_digest.negative_rules[:2]],
            [],
        ),
        (
            "visual_strategy",
            "translated visual memory into reusable style rules",
            [
                f"continuity: {visual_snapshot.get('continuity_strength', 'weak')}",
                f"positive anchors: {len(visual_snapshot.get('positive_anchor_output_ids', []) or [])}",
                f"human natural variation: {human_variation_applies}",
            ],
            [*prompt_guidance.style_notes[:3], *prompt_guidance.layout_notes[:2]],
            guard.get("warnings", []) if isinstance(guard.get("warnings"), list) else [],
        ),
        (
            "prompt_guidance",
            "expanded the simple request into a ready-to-generate image direction",
            prompt_guidance.visual_direction_addons[:3],
            [prompt_guidance.optimized_direction],
            [],
        ),
        (
            "pre_generation_review",
            "checked that the prompt preserves the request and avoids unwanted artifacts",
            prompt_review.checks[:4],
            prompt_review.fixes_applied[:4],
            prompt_review.warnings,
        ),
        (
            "post_generation_review",
            "prepared the result checklist for generated images",
            _cluster_quality_checks(visual_cluster)[:4],
            ["review actual images after provider returns candidates"],
            [],
        ),
    ]
    checkpoints: list[BrainCheckpoint] = []
    for stage, summary, inputs, outputs, warnings in checkpoint_specs:
        stage_warnings = clean_text_list([*warnings, warning] if warning and stage == "pre_generation_review" else warnings, limit=6)
        checkpoints.append(
            BrainCheckpoint(
                checkpoint_id=stage,
                stage=stage,
                status="warning" if stage_warnings else "completed",
                summary=summary,
                inputs=clean_text_list(inputs, limit=6),
                outputs=clean_text_list(outputs, limit=6, text_limit=220),
                warnings=stage_warnings,
                metadata={
                    "v3_checkpoint_brain": True,
                    "visual_cluster_present": bool(visual_cluster),
                },
            )
        )
    return checkpoints


def _scene_hint(text: str, *, allow_product_language: bool) -> str:
    lower = text.lower()
    if "小红书" in text or "xiaohongshu" in lower:
        return "social cover"
    if "poster" in lower or "海报" in text:
        return "poster"
    if "banner" in lower or "横幅" in text:
        return "banner"
    return "commercial visual" if allow_product_language else "creative visual"


def _audience_hint(text: str) -> str | None:
    if "女性" in text or "美女" in text or "girl" in text.lower() or "woman" in text.lower():
        return "style-conscious consumer audience"
    if "电商" in text or "amazon" in text.lower():
        return "online shoppers"
    return None


def _output_use(text: str, *, allow_product_language: bool = False) -> str:
    lower = text.lower()
    if "社媒" in text or "social" in lower or "小红书" in text:
        return "social media publishing"
    if "封面" in text or "cover" in lower:
        return "cover image"
    return "commercial publishing" if allow_product_language else "creative publishing"


def _mood_hints(text: str, tone: list[str], *, allow_product_language: bool) -> list[str]:
    candidates = [*tone]
    keyword_map = [
        ("清爽", "fresh and clean"),
        ("高级", "premium"),
        ("夏季", "bright summer atmosphere"),
        ("干净", "minimal and clean"),
        ("明亮", "bright lighting"),
        ("自然", "natural"),
        ("美女", "stylish portrait-led visual"),
    ]
    for keyword, label in keyword_map:
        if keyword in text and label not in candidates:
            candidates.append(label)
    default_mood = "polished commercial style" if allow_product_language else "polished creative style"
    return clean_text_list(candidates or [default_mood, "clean bright lighting"], limit=8)


def _variation_mode(request: BrainRunRequest) -> str:
    allowed = {
        "selection_candidates",
        "delivery_suite",
        "creative_exploration",
        "format_layout_adaptation",
    }
    metadata = dict(request.metadata or {})
    profile = dict(request.product_profile or {})
    value = (
        metadata.get("effective_variation_mode")
        or metadata.get("variation_mode")
        or metadata.get("continuation_mode")
        or profile.get("effective_variation_mode")
        or profile.get("variation_mode")
        or profile.get("continuation_mode")
        or ""
    )
    value = str(value).strip()
    return value if value in allowed else "delivery_suite"


def _variation_mode_rules(mode: str) -> dict[str, list[str] | str]:
    rules: dict[str, dict[str, list[str] | str]] = {
        "selection_candidates": {
            "set_goal": "Create close alternatives under the same visual direction",
            "prompt_addon": "Generate near-neighbor options: same core subject, same style, small differences in framing, viewpoint, lighting, or scene depth.",
            "composition_rules": ["keep variation small and easy to compare"],
            "quality_bar": ["alternatives should feel like one selectable batch"],
            "hard_constraints": ["Do not change the core subject identity, product identity, or overall style direction."],
        },
        "delivery_suite": {
            "set_goal": "Create a coherent multi-image suite",
            "prompt_addon": "Expand the approved direction into a useful image set with clear role variety while keeping one unified look.",
            "composition_rules": ["give each image a clear role while keeping one shared visual system"],
            "quality_bar": ["the set should look publishable together"],
            "hard_constraints": ["Do not replace existing project outputs; create additional companion images."],
        },
        "creative_exploration": {
            "set_goal": "Create creative directions for the same subject",
            "prompt_addon": "Explore visibly different concepts while preserving the requested subject and ready-to-use quality.",
            "composition_rules": ["allow broader mood, styling, and scene variation"],
            "quality_bar": ["each option should be distinct enough to compare as a creative route"],
            "hard_constraints": ["Keep the subject recognizable even when exploring different concepts."],
        },
        "format_layout_adaptation": {
            "set_goal": "Create layout and format adaptations",
            "prompt_addon": "Adapt the same visual direction into useful crops and layouts with clean negative space and strong framing.",
            "composition_rules": ["prioritize crop safety, usable negative space, and layout flexibility"],
            "quality_bar": ["adaptations should work as covers, square posts, or horizontal/vertical layouts"],
            "hard_constraints": ["Do not add generated text; leave clean areas for later design copy when useful."],
        },
    }
    return rules.get(mode, rules["delivery_suite"])


def _shot_plan(
    count: int,
    user_input: str,
    has_reference: bool,
    variation_mode: str,
    *,
    suite_role_plan: dict | None = None,
) -> list[str]:
    roles = suite_role_plan.get("roles") if isinstance(suite_role_plan, dict) else None
    if isinstance(roles, list) and roles:
        planned = [
            f"{str(role.get('purpose') or role.get('label') or 'planned role')}: {str(role.get('shot_instruction') or '').strip()}"
            for role in roles
            if isinstance(role, dict)
        ]
        if planned:
            return planned[: max(1, min(4, count))]
    if variation_mode == "selection_candidates":
        base = [
            "near-identical candidate with the strongest subject treatment",
            "same-style candidate with a small pose or angle change",
            "same-style candidate with subtle framing or expression variation",
            "same-style candidate with a slightly different crop for comparison",
        ]
    elif variation_mode == "creative_exploration":
        base = [
            "clear first creative direction with strong subject focus",
            "second creative direction with a different mood or scene",
            "third creative direction with a different framing or styling idea",
            "layout-flexible creative option for comparison",
        ]
    elif variation_mode == "format_layout_adaptation":
        base = [
            "square-safe composition with clear subject hierarchy",
            "vertical cover-friendly composition with clean negative space",
            "horizontal layout-friendly composition with balanced framing",
            "tight crop or alternate layout while preserving the same style",
        ]
    else:
        base = [
            "hero image with clear subject and strong first impression",
            "supporting variation with different framing but same style",
            "close-up detail or mood-focused variation",
            "wide composition for cover or layout flexibility",
        ]
    if has_reference:
        base[1] = "same-style variation using selected project references"
    if "套图" in user_input:
        base[2] = "series companion image that expands the same story"
    return base[: max(1, min(4, count))]


def _doc58_cluster_plans(visual_cluster: dict) -> dict[str, Any]:
    if not isinstance(visual_cluster, dict):
        return {
            "applies": False,
            "identity_anchors": [],
            "strong_reference_plan": {},
            "suite_role_plan": {},
            "batch_review": {},
        }
    anchors = visual_cluster.get("project_identity_anchors")
    strong_plan = visual_cluster.get("strong_reference_continuation_plan")
    suite_plan = visual_cluster.get("general_suite_role_plan")
    batch_review = visual_cluster.get("batch_identity_diversity_review")
    payload = {
        "identity_anchors": anchors if isinstance(anchors, list) else [],
        "strong_reference_plan": strong_plan if isinstance(strong_plan, dict) else {},
        "suite_role_plan": suite_plan if isinstance(suite_plan, dict) else {},
        "batch_review": batch_review if isinstance(batch_review, dict) else {},
    }
    payload["applies"] = bool(
        payload["identity_anchors"]
        or payload["strong_reference_plan"]
        or payload["suite_role_plan"].get("roles")
        or payload["batch_review"].get("applies")
    )
    return payload


def _suite_role_prompt_addons(suite_role_plan: dict, count: int) -> list[str]:
    roles = suite_role_plan.get("roles") if isinstance(suite_role_plan, dict) else None
    if not isinstance(roles, list):
        return []
    additions: list[str] = []
    for index, role in enumerate(roles[: max(1, min(4, count))], 1):
        if not isinstance(role, dict):
            continue
        label = clean_text(role.get("label"), 80)
        instruction = clean_text(role.get("shot_instruction"), 180)
        if label and instruction:
            additions.append(f"Planned image role {index} ({label}): {instruction}")
    return additions


def _string_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return clean_text_list(value, limit=20)
    if isinstance(value, str):
        return clean_text_list([value], limit=1)
    return []


def _continuity_rules(selected_outputs: list[dict], reference_assets: list[dict], tone: list[str]) -> list[str]:
    rules: list[str] = []
    if selected_outputs:
        rules.append("keep the selected image style as the strongest project anchor")
        rules.append("match the selected image lighting, palette, lens feeling, and subject scale")
    if reference_assets:
        rules.append("follow active project reference images when composition or mood is relevant")
    for item in tone[:4]:
        rules.append(f"keep confirmed style: {item}")
    return clean_text_list(rules, limit=8)


def _selected_reference_labels(selected_outputs: list[dict]) -> list[str]:
    labels: list[str] = []
    for item in selected_outputs:
        label = item.get("selection_reason") or item.get("output_id") or item.get("candidate_id")
        if label:
            labels.append(str(label))
    return labels


def _optimized_direction(request: BrainRunRequest, mood: list[str], continuity_rules: list[str]) -> str:
    allow_product_language = product_language_allowed(
        template_id=request.template_id,
        scenario_id=request.scenario_id,
        user_input=request.user_input,
        metadata=request.metadata,
        uploaded_assets=request.uploaded_assets,
        reference_assets=request.reference_assets,
    )
    positive_user_input, _explicit_negative_parts = split_positive_and_negative_prompt(request.user_input)
    goal_input = positive_user_input or request.user_input
    goal_source = goal_input if allow_product_language else strip_negated_product_phrases(goal_input)
    goal = clean_text(goal_source, 360)
    mood_text = ", ".join(mood[:5])
    continuity = "; ".join(continuity_rules[:3])
    parts = [
        (
            f"Create a commercially polished image set for: {goal}"
            if allow_product_language
            else f"Create a professionally polished image set for: {goal}"
        ),
        f"Visual mood: {mood_text}" if mood_text else "",
        f"Continuity: {continuity}" if continuity else "",
        "Use clean composition, refined lighting, clear subject hierarchy, and no generated text overlays.",
    ]
    return ". ".join(part for part in parts if part)
