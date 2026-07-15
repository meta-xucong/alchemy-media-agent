"""Doc59 mode-aware role director for V3 visual suites."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import (
    ModeDifferentiationReview,
    ModeExecutionPolicy,
    ModeRoleRecipe,
    RoleSpecificGenerationPlan,
)


ALLOWED_MODES = {
    "selection_candidates",
    "delivery_suite",
    "creative_exploration",
    "format_layout_adaptation",
}


class ModeAwareRoleDirector:
    """Build executable per-image role contracts for the four General modes."""

    def build(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        user_input: str,
        mode: str | None,
        requested_image_count: int,
        subject_type: str = "generic",
        scenario_id: str | None = None,
        template_id: str | None = None,
        has_identity_anchor: bool = False,
    ) -> RoleSpecificGenerationPlan:
        normalized_mode = normalize_mode(mode)
        normalized_subject = _normalize_subject_type(subject_type)
        count = max(1, min(4, int(requested_image_count or 1)))
        policy = self._policy(normalized_mode, has_identity_anchor=has_identity_anchor)
        raw_recipes = self._recipe_dicts(
            mode=normalized_mode,
            subject_type=normalized_subject,
            scenario_id=scenario_id,
        )[:count]
        # Doc128: the General mode director owns only neutral role structure.
        # Historical casebook overlays remain readable in old records but must
        # not add static camera/light/prompt atoms to a new job.
        recipes = [
            self._recipe_model(
                project_id=project_id,
                job_id=job_id,
                mode=normalized_mode,
                subject_type=normalized_subject,
                recipe=recipe,
                index=index,
            )
            for index, recipe in enumerate(raw_recipes, 1)
        ]
        prompt_additions = [
            f"Output {recipe.index} must serve the role '{recipe.label}': {recipe.prompt_pressure}"
            for recipe in recipes
        ]
        negative_additions = _dedupe(
            rule
            for recipe in recipes
            for rule in recipe.negative_pressure
        )
        return RoleSpecificGenerationPlan(
            plan_id=stable_id(
                "role_specific_generation_plan",
                project_id,
                job_id,
                normalized_mode,
                normalized_subject,
                count,
                user_input,
            ),
            project_id=project_id,
            job_id=job_id,
            mode=normalized_mode,
            subject_type=normalized_subject,
            requested_image_count=count,
            policy=policy,
            role_recipes=recipes,
            prompt_additions=prompt_additions,
            negative_additions=negative_additions,
            user_visible_summary=[
                _mode_user_summary(normalized_mode),
                f"{count} output role(s) planned.",
            ],
            metadata={
                "doc": "59",
                "scenario_id": scenario_id,
                "template_id": template_id,
                "has_identity_anchor": has_identity_anchor,
                "mode_role_director": True,
            },
        )

    def review(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        role_plan: RoleSpecificGenerationPlan,
        generated_candidates: list[dict[str, Any]] | None = None,
    ) -> ModeDifferentiationReview:
        candidates = [dict(item) for item in generated_candidates or [] if isinstance(item, dict)]
        issue_codes: list[str] = []
        role_checks = [
            f"{recipe.index}. {recipe.label}: {recipe.purpose}"
            for recipe in role_plan.role_recipes
        ]
        if len(role_plan.role_recipes) < role_plan.requested_image_count:
            issue_codes.append("mode_role_gap")
        if candidates:
            role_keys = [
                _candidate_role_key(candidate)
                for candidate in candidates
            ]
            role_keys = [key for key in role_keys if key]
            if not role_keys:
                issue_codes.append("mode_role_metadata_missing")
            elif len(set(role_keys)) < min(len(role_keys), len(role_plan.role_recipes)):
                issue_codes.append("mode_role_duplication")
            if role_plan.mode == "delivery_suite" and len(set(role_keys)) <= 1 and len(role_keys) > 1:
                issue_codes.append("delivery_suite_role_collapse")
            if role_plan.mode == "format_layout_adaptation":
                layouts = [
                    str(candidate.get("requested_image_size") or candidate.get("aspect_ratio") or "").strip()
                    for candidate in candidates
                ]
                if len([item for item in layouts if item]) > 1 and len(set(layouts)) <= 1:
                    issue_codes.append("format_layout_collapse")
            if role_plan.mode == "selection_candidates" and len(set(role_keys)) > 2 and len(role_keys) <= 2:
                issue_codes.append("selection_candidate_distance_risk")
        status = "retry_recommended" if issue_codes else ("pass" if candidates else "planned")
        coverage = "collapsed" if any("collapse" in code or "duplication" in code for code in issue_codes) else (
            "partial" if issue_codes else ("covered" if candidates else "planned")
        )
        retry_patch = self._retry_patch(role_plan, issue_codes)
        return ModeDifferentiationReview(
            review_id=stable_id(
                "mode_differentiation_review",
                project_id,
                job_id,
                role_plan.mode,
                ",".join(issue_codes),
            ),
            project_id=project_id,
            job_id=job_id,
            mode=role_plan.mode,
            status=status,
            role_coverage_status=coverage,
            issue_codes=_dedupe(issue_codes),
            role_checks=role_checks,
            retry_patch=retry_patch,
            user_visible_summary=_review_summary(role_plan.mode, status),
            metadata={
                "doc": "59",
                "candidate_count": len(candidates),
                "role_count": len(role_plan.role_recipes),
                "append_only": True,
            },
        )

    def _policy(self, mode: str, *, has_identity_anchor: bool) -> ModeExecutionPolicy:
        data = {
            "selection_candidates": {
                "mode_meaning": "close options for choosing the best frame",
                "visual_distance_budget": "micro",
                "anchor_strength": "strongest_available_anchor",
                "scene_change_allowed": False,
                "role_strategy": "near_neighbor_candidates",
                "role_difference_requirement": "one or two small visible axes per output",
                "review_priority": "same identity or product, not exact cloned stills",
                "user_visible_label": "Close options",
            },
            "delivery_suite": {
                "mode_meaning": "a useful set under one approved direction",
                "visual_distance_budget": "moderate",
                "anchor_strength": "strong",
                "scene_change_allowed": True,
                "role_strategy": "purposeful_delivery_roles",
                "role_difference_requirement": "different shot family or different image duty",
                "review_priority": "role coverage and project consistency",
                "user_visible_label": "Make a set",
            },
            "creative_exploration": {
                "mode_meaning": "several distinct visual directions before locking one",
                "visual_distance_budget": "broad",
                "anchor_strength": "medium_unless_locked",
                "scene_change_allowed": True,
                "role_strategy": "concept_lanes",
                "role_difference_requirement": "different concept, mood, palette, scene, or lens",
                "review_priority": "keep core subject while avoiding near-identical ideas",
                "user_visible_label": "Explore ideas",
            },
            "format_layout_adaptation": {
                "mode_meaning": "same idea adapted to different crops or layouts",
                "visual_distance_budget": "layout_only",
                "anchor_strength": "strongest_available_anchor",
                "scene_change_allowed": False,
                "role_strategy": "format_roles",
                "role_difference_requirement": "aspect ratio, crop, negative space, or placement changes",
                "review_priority": "format fit and identity/style preservation",
                "user_visible_label": "Adapt size/layout",
            },
        }[mode]
        return ModeExecutionPolicy(
            policy_id=stable_id("mode_execution_policy", mode, has_identity_anchor),
            mode=mode,
            user_visible_summary=[_mode_user_summary(mode)],
            metadata={"doc": "59", "has_identity_anchor": has_identity_anchor},
            **data,
        )

    def _recipe_dicts(
        self,
        *,
        mode: str,
        subject_type: str,
        scenario_id: str | None,
    ) -> list[dict[str, Any]]:
        if mode == "selection_candidates":
            return _selection_candidate_recipes(subject_type)
        if mode == "creative_exploration":
            return _creative_exploration_recipes(subject_type)
        if mode == "format_layout_adaptation":
            return _format_layout_recipes(subject_type)
        if subject_type == "product":
            return _product_delivery_recipes()
        if subject_type == "character":
            return _human_delivery_recipes()
        return _generic_delivery_recipes()

    def _recipe_model(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        mode: str,
        subject_type: str,
        recipe: dict[str, Any],
        index: int,
    ) -> ModeRoleRecipe:
        role_key = str(recipe["role_key"])
        recipe_metadata = dict(recipe.get("metadata") or {})
        return ModeRoleRecipe(
            role_id=stable_id("mode_role_recipe", project_id, job_id, mode, index, role_key),
            index=index,
            role_key=role_key,
            label=str(recipe["label"]),
            purpose=str(recipe["purpose"]),
            shot_family=str(recipe.get("shot_family") or ""),
            camera_distance=str(recipe.get("camera_distance") or ""),
            angle_rule=str(recipe.get("angle_rule") or ""),
            crop_rule=str(recipe.get("crop_rule") or ""),
            scene_rule=str(recipe.get("scene_rule") or ""),
            variation_axes=_string_list(recipe.get("variation_axes")),
            must_keep_rules=_string_list(recipe.get("must_keep_rules")),
            must_not_rules=_string_list(recipe.get("must_not_rules")),
            prompt_pressure=str(recipe.get("prompt_pressure") or ""),
            negative_pressure=_string_list(recipe.get("negative_pressure")),
            review_checks=_string_list(recipe.get("review_checks")),
            user_visible_summary=_string_list(recipe.get("user_visible_summary")),
            metadata={
                **recipe_metadata,
                "doc": str(recipe_metadata.get("doc") or recipe.get("doc") or "59"),
                "subject_type": subject_type,
                "mode": mode,
            },
        )

    def _retry_patch(self, role_plan: RoleSpecificGenerationPlan, issue_codes: list[str]) -> dict[str, Any]:
        if not issue_codes:
            return {}
        return {
            "prompt_additions": [
                "generate each output with its own role-specific camera distance, crop, angle, scene duty, or layout duty",
                *role_plan.prompt_additions[:4],
            ],
            "negative_additions": _dedupe(
                [
                    "same crop and camera distance for every output",
                    "duplicated pose across the whole batch",
                    "same image duty repeated for all outputs",
                    *role_plan.negative_additions[:6],
                ]
            ),
            "reason_codes": _dedupe(issue_codes),
        }


def normalize_mode(mode: str | None) -> str:
    value = str(mode or "").strip()
    if value == "format_adaptation":
        value = "format_layout_adaptation"
    return value if value in ALLOWED_MODES else "delivery_suite"


def _normalize_subject_type(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if text in {"character", "human", "person", "portrait"}:
        return "character"
    if text in {"product", "object", "sku"}:
        return "product"
    return "generic"


def _base_keep(subject_type: str) -> list[str]:
    if subject_type == "character":
        return [
            "same recognizable person direction",
            "same body identity direction",
            "prompt-directed hair, wardrobe, and lighting unless those channels are explicitly locked",
        ]
    if subject_type == "product":
        return [
            "same product shape, material, color, proportions, and label position",
            "same product identity",
            "same lighting language",
        ]
    return ["same core subject direction", "same style language", "same lighting and palette family"]


def _common_negative() -> list[str]:
    return [
        "collage",
        "split screen",
        "visible text",
        "watermark",
        "signature",
        "same exact still repeated",
    ]


def _selection_candidate_recipes(subject_type: str) -> list[dict[str, Any]]:
    keep = _base_keep(subject_type)
    return [
        _recipe("candidate_best_frame", "Best frame", "Closest approved direction", "same shot family", "same or very close", "front or slight angle", "minor framing shift", "same scene", ["best frame", "micro crop"], keep, "Stay very close to the approved direction; vary only one small presentation detail."),
        _recipe("candidate_expression_shift", "Expression option", "Compare expression or gaze", "same shot family", "same", "same camera angle", "same crop family", "same scene", ["expression", "gaze"], keep, "Keep everything comparable; change expression, gaze, or tiny head angle only."),
        _recipe("candidate_pose_shift", "Pose option", "Compare pose or hand placement", "same shot family", "same", "same or slight body angle", "same crop family", "same scene", ["pose", "hand placement"], keep, "Keep the same visual setup; change pose or hand placement slightly."),
        _recipe("candidate_crop_shift", "Crop option", "Compare framing", "same shot family", "slightly different", "same", "slight crop or negative-space change", "same scene", ["crop", "negative space"], keep, "Keep the same subject and style; only adjust crop or camera distance subtly."),
    ]


def _human_delivery_recipes() -> list[dict[str, Any]]:
    keep = _base_keep("character")
    return [
        _recipe(
            "cover_hero",
            "Cover hero",
            "Strong first impression",
            "hero portrait",
            "medium portrait",
            "front or slight three-quarter",
            "square or vertical cover-safe crop",
            "primary scene",
            ["camera distance", "subject scale", "cover-safe negative space"],
            keep,
            "Create the main cover frame: direct or near-camera gaze, open shoulders, clean hero posture, natural head/body scale, square or vertical cover-safe portrait framing, a quiet neutral expression or imperfect half-smile with slight asymmetry, and cover-safe rhythm.",
            metadata=_portrait_role_lanes(
                expression="quiet neutral expression or imperfect half-smile with slight asymmetry, not a sweet template smile",
                gaze="direct or near-camera gaze",
                pose="open shoulders with clean hero posture",
                gesture="minimal hands or relaxed hand line; keep the cover uncluttered",
                subject_scale="medium portrait or medium-close cover scale",
                scene_depth="simple primary background with clean negative space",
                clone_avoidance="do not reuse the same tight crop, side profile, wide lifestyle distance, horizontal banner crop, or letterboxed framing as other roles",
            ),
            negative_pressure=[
                *_common_negative(),
                "same tight face crop as the subject-focus role",
                "same side profile as the angle role",
                "same wide environmental distance as the scene role",
                "horizontal banner crop",
                "letterboxed portrait",
                "wide panorama cover",
                "oversized head",
                "compressed shoulders",
            ],
        ),
        _recipe(
            "subject_focus",
            "Subject focus",
            "Closer identity/detail frame",
            "portrait detail",
            "closer portrait",
            "natural angle",
            "face and upper body focus",
            "same shoot",
            ["expression", "crop", "hair or styling detail"],
            keep,
            "Create a closer identity/detail frame: softer expression or slight off-camera gaze, shallow depth, hair texture, real skin light, balanced face scale, natural neck/shoulder line, and upper-body detail without copying the cover still.",
            metadata=_portrait_role_lanes(
                expression="softer, more intimate expression than the cover hero",
                gaze="slightly off-camera or gentle near-camera gaze",
                pose="closer upper-body pose with subtle head tilt",
                gesture="one natural styling detail such as hair movement or hand near hair if it feels realistic",
                subject_scale="closer face and upper-body crop",
                scene_depth="shallow depth with background kept simple",
                clone_avoidance="do not repeat the cover posture, wide context crop, or identical front-facing smile",
            ),
            negative_pressure=[
                *_common_negative(),
                "same cover posture",
                "same wide context crop",
                "same front-facing smile as every other image",
                "oversized head",
                "compressed neck",
                "awkward shoulder crop",
            ],
        ),
        _recipe(
            "side_or_three_quarter_angle",
            "Angle variation",
            "Side or three-quarter view",
            "angle portrait",
            "medium",
            "side or three-quarter",
            "different framing",
            "same shoot",
            ["head angle", "body turn", "gaze direction", "shoulder line"],
            keep,
            "Create a real side or three-quarter angle: visible body turn, different head angle, gaze toward the scene, natural hair movement, and a different shoulder line while preserving identity.",
            metadata=_portrait_role_lanes(
                expression="calm candid expression, clearly different from the cover smile",
                gaze="away from camera or toward the scene",
                pose="visible body turn with side or three-quarter head angle",
                gesture="natural shoulder line or hair movement that supports the angle change",
                subject_scale="medium portrait with a different face plane",
                scene_depth="same shoot world with enough background to show the angle",
                clone_avoidance="do not make another front-facing duplicate; avoid changing identity through an extreme profile",
            ),
            negative_pressure=[
                *_common_negative(),
                "front-facing duplicate",
                "same smile and head angle as the anchor",
                "extreme profile that causes identity drift",
            ],
        ),
        _recipe(
            "wide_scene_or_context",
            "Scene context",
            "Wider story frame",
            "wide environmental portrait",
            "wider",
            "natural scene angle",
            "more surrounding space",
            "expanded same-world scene",
            ["scene depth", "camera distance", "body scale", "environment interaction"],
            keep,
            "Create a wider lifestyle/context frame: more environment, three-quarter or full-body scale when possible, walking, seated, leaning, or interacting with the seaside scene while staying the same person.",
            metadata=_portrait_role_lanes(
                expression="relaxed lifestyle expression, not a repeated headshot smile",
                gaze="toward the scene, horizon, or camera depending on natural composition",
                pose="walking, seated, leaning, or three-quarter body pose",
                gesture="natural arm or hand placement connected to the environment",
                subject_scale="wider three-quarter or full-body scale when possible",
                scene_depth="clear seaside or lifestyle depth with the person integrated into the environment",
                clone_avoidance="do not create another close headshot or studio-like crop",
            ),
            negative_pressure=[
                *_common_negative(),
                "another close headshot",
                "same studio-like crop",
                "unrelated props or product objects",
            ],
        ),
    ]


def _product_delivery_recipes() -> list[dict[str, Any]]:
    keep = _base_keep("product")
    return [
        _recipe("hero_object", "Hero object", "Main object image", "object hero", "medium", "front or three-quarter", "balanced main crop", "clean primary setup", ["scale", "placement"], keep, "Create a product/object-first hero image with clear silhouette and premium finish."),
        _recipe("context_scene", "Context scene", "Object in use or in scene", "context image", "medium-wide", "natural scene angle", "more environment", "realistic contextual setup", ["scene", "surface", "props"], keep, "Create a realistic context image that shows the object naturally in its scene."),
        _recipe("detail_or_material_closeup", "Detail closeup", "Material/detail proof", "detail closeup", "close", "detail angle", "tight crop", "same product setup", ["texture", "material", "detail"], keep, "Create a closer detail or material image that proves finish and texture."),
        _recipe("layout_safe_cover", "Layout cover", "Cover-safe version", "layout cover", "medium", "clean angle", "broader contextual crop", "clean layout-safe setup", ["negative space", "crop"], keep, "Create a cover version with a broader, naturally balanced contextual composition."),
    ]


def _generic_delivery_recipes() -> list[dict[str, Any]]:
    keep = _base_keep("generic")
    return [
        _recipe("hero_subject", "Hero image", "Main visual", "hero image", "medium", "front or natural angle", "balanced crop", "primary scene", ["subject scale"], keep, "Create the strongest main image under the approved direction."),
        _recipe("detail_focus", "Detail focus", "Closer subject detail", "detail image", "close", "natural detail angle", "closer crop", "same visual world", ["detail", "crop"], keep, "Create a closer detail or subject-focus image."),
        _recipe("alternate_angle", "Alternate angle", "Different angle", "alternate shot", "medium", "different angle", "different framing", "same visual world", ["angle", "pose"], keep, "Create an alternate angle that feels like part of the same set."),
        _recipe("wide_context", "Context image", "Wider context", "wide image", "wide", "context angle", "wider crop", "expanded same-world scene", ["scene", "camera distance"], keep, "Create a wider context image that expands the visual story."),
    ]


def _creative_exploration_recipes(subject_type: str) -> list[dict[str, Any]]:
    keep = _base_keep(subject_type)[:2]
    return [
        _recipe("concept_clean_bright", "Clean bright idea", "Clear approachable direction", "clean concept", "medium", "simple clear angle", "balanced crop", "bright simple scene", ["mood", "palette"], keep, "Explore a clean, bright, high-clarity direction."),
        _recipe("concept_editorial", "Editorial idea", "More styled direction", "editorial concept", "medium", "styled magazine angle", "designed crop", "styled set", ["styling", "art direction"], keep, "Explore a more editorial, magazine-like direction."),
        _recipe("concept_cinematic", "Cinematic idea", "Atmospheric direction", "cinematic concept", "medium-wide", "dramatic lens angle", "deeper crop", "atmospheric scene", ["light", "depth", "scene"], keep, "Explore a more cinematic direction with stronger depth and atmosphere."),
        _recipe("concept_minimal_or_graphic", "Minimal idea", "Shape/layout direction", "minimal concept", "medium", "graphic angle", "layout-forward crop", "minimal scene", ["shape", "negative space"], keep, "Explore a simpler, more graphic composition with stronger shape and spacing."),
    ]


def _format_layout_recipes(subject_type: str) -> list[dict[str, Any]]:
    keep = _base_keep(subject_type)
    return [
        _recipe("vertical_cover", "Vertical cover", "Tall cover adaptation", "format adaptation", "medium", "same approved angle", "vertical crop with safe margins", "same idea", ["vertical crop", "top/bottom space"], keep, "Keep the approved idea and adapt it to a vertical cover crop."),
        _recipe("square_feed", "Square feed", "Square feed adaptation", "format adaptation", "medium", "same approved angle", "square balanced crop", "same idea", ["square crop", "balanced subject"], keep, "Keep the approved idea and adapt it to a square feed layout."),
        _recipe("horizontal_banner", "Horizontal banner", "Wide banner adaptation", "format adaptation", "medium-wide", "same approved angle", "horizontal crop with side space", "same idea", ["wide crop", "side negative space"], keep, "Keep the approved idea and adapt it to a horizontal banner layout."),
        _recipe("tight_crop_or_detail", "Tight crop", "Close crop adaptation", "format adaptation", "close", "same approved angle", "tight crop or detail-safe crop", "same idea", ["tight crop", "detail"], keep, "Keep the approved idea and adapt it to a tighter crop or detail-safe version."),
    ]


def _recipe(
    role_key: str,
    label: str,
    purpose: str,
    shot_family: str,
    camera_distance: str,
    angle_rule: str,
    crop_rule: str,
    scene_rule: str,
    variation_axes: list[str],
    must_keep_rules: list[str],
    prompt_pressure: str,
    *,
    must_not_rules: list[str] | None = None,
    negative_pressure: list[str] | None = None,
    review_checks: list[str] | None = None,
    user_visible_summary: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "role_key": role_key,
        "label": label,
        "purpose": purpose,
        "shot_family": shot_family,
        "camera_distance": camera_distance,
        "angle_rule": angle_rule,
        "crop_rule": crop_rule,
        "scene_rule": scene_rule,
        "variation_axes": variation_axes,
        "must_keep_rules": must_keep_rules,
        "must_not_rules": must_not_rules
        or ["do not create a collage", "do not add visible text", "do not duplicate the exact same still"],
        "prompt_pressure": prompt_pressure,
        "negative_pressure": negative_pressure or _common_negative(),
        "review_checks": review_checks
        or [
            f"role is visibly {label}",
            "output follows one complete image frame",
            "output does not repeat another role as the same shot",
        ],
        "user_visible_summary": user_visible_summary or [label, purpose],
        "metadata": metadata or {},
    }


def _portrait_role_lanes(
    *,
    expression: str,
    gaze: str,
    pose: str,
    gesture: str,
    subject_scale: str,
    scene_depth: str,
    clone_avoidance: str,
) -> dict[str, Any]:
    return {
        "doc": "62",
        "extends": "59",
        "portrait_suite_director": True,
        "expression_lane": expression,
        "gaze_lane": gaze,
        "pose_lane": pose,
        "gesture_lane": gesture,
        "subject_scale_lane": subject_scale,
        "scene_depth_lane": scene_depth,
        "clone_avoidance_rule": clone_avoidance,
    }


def _candidate_role_key(candidate: dict[str, Any]) -> str:
    metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
    recipe = candidate.get("mode_role_recipe") or metadata.get("mode_role_recipe")
    if isinstance(recipe, dict):
        return str(recipe.get("role_key") or recipe.get("label") or "").strip()
    for key in ("mode_role_key", "suite_role", "role"):
        value = candidate.get(key) or metadata.get(key)
        if value:
            return str(value).strip()
    return ""


def _mode_user_summary(mode: str) -> str:
    return {
        "selection_candidates": "Prepared close options for picking the best image.",
        "delivery_suite": "Prepared a purposeful set with different image jobs.",
        "creative_exploration": "Prepared different creative directions.",
        "format_layout_adaptation": "Prepared crop and layout adaptations.",
    }.get(mode, "Prepared a coherent image set.")


def _review_summary(mode: str, status: str) -> list[str]:
    if status == "retry_recommended":
        return ["Some images repeated the same job.", "A role-specific retry can separate the set better."]
    if status == "pass":
        return ["The set keeps the chosen mode and separates image jobs."]
    return [_mode_user_summary(mode)]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _dedupe(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
