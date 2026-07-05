"""Human photorealism and anti-AI-face guidance for the V3 visual cluster."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .casebook_recipes import (
    VISUAL_CASEBOOK_RECIPE_LIBRARY_ID,
    VISUAL_HUMAN_ATTRACTIVE_REALISM_BALANCE_ID,
    VISUAL_HUMAN_EAST_ASIAN_FAIR_COMPLEXION_GUARD_ID,
    VISUAL_HUMAN_REAL_CAMERA_TUNING_ID,
    human_photorealism_casebook,
)
from .contracts import AntiAIFaceReviewResult, HumanPhotorealismGuidance


HUMAN_PHOTOREALISM_MODULE_ID = "human_photorealism_layer"
ANTI_AI_FACE_REVIEW_MODULE_ID = "anti_ai_face_review"

_HUMAN_TERMS = {
    "portrait",
    "photo portrait",
    "photoreal",
    "photorealistic",
    "real person",
    "realistic person",
    "model",
    "woman",
    "girl",
    "man",
    "face",
    "fashion photo",
    "lifestyle photo",
    "editorial portrait",
    "beauty portrait",
}

_CHINESE_HUMAN_TERMS = {
    "\u4eba\u50cf",
    "\u771f\u4eba",
    "\u5199\u771f",
    "\u6444\u5f71",
    "\u7167\u7247",
    "\u6a21\u7279",
    "\u7f8e\u5973",
    "\u4eba\u7269",
    "\u5973\u751f",
    "\u5973\u5b69",
    "\u8138",
    "\u534a\u8eab",
    "\u5168\u8eab",
    "\u8857\u62cd",
}

_STYLIZED_TERMS = {
    "anime",
    "manga",
    "cartoon",
    "illustration",
    "illustrated",
    "cg",
    "cgi",
    "3d render",
    "game character",
}

_CHINESE_STYLIZED_TERMS = {
    "\u52a8\u6f2b",
    "\u6f2b\u753b",
    "\u63d2\u753b",
    "\u5361\u901a",
    "\u4e8c\u6b21\u5143",
    "\u6e32\u67d3",
    "\u4e09\u7ef4",
}

_ANTI_AI_FACE_ISSUES = {
    "ai_face_render",
    "plastic_skin",
    "over_smoothed_skin",
    "missing_skin_texture",
    "synthetic_beauty_filter",
    "doll_like_face",
    "template_smile",
    "over_perfect_symmetry",
    "wax_skin_highlight",
    "uncanny_eye_expression",
    "same_ai_face_repetition",
    "beauty_app_face",
    "idol_photocard_polish",
    "skin_blur_retouching",
    "over_uniform_skin_tone",
    "over_sharp_ai_detail",
    "perfect_smile_repetition",
    "face_slimming_filter",
    "beautified_facial_geometry",
    "generic_ai_beauty_identity",
    "dull_complexion",
    "muddy_skin_tone",
    "underexposed_face",
    "harsh_facial_shadow",
    "overly_matte_documentary_look",
    "tired_expression",
    "unflattering_color_cast",
    "suppressed_fair_complexion",
    "forced_tan_or_bronze_cast",
    "gray_brown_skin_cast",
    "head_body_proportion_distortion",
    "oversized_head",
    "compressed_neck_shoulders",
    "unflattering_face_drift",
}


class HumanPhotorealismLayer:
    """Build reusable prompt/review guidance for photoreal human outputs."""

    module_id = HUMAN_PHOTOREALISM_MODULE_ID

    def build(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        scenario_id: str,
        template_id: str,
        user_input: str,
        subject_type: str,
        variation_mode: str,
        has_identity_reference: bool,
        metadata: dict[str, Any] | None = None,
    ) -> HumanPhotorealismGuidance:
        metadata = dict(metadata or {})
        applies, reason = self._applies(
            user_input=user_input,
            subject_type=subject_type,
            scenario_id=scenario_id,
            template_id=template_id,
            metadata=metadata,
        )
        guidance_id = stable_id("human_photorealism_guidance", project_id, job_id, scenario_id, user_input, variation_mode)
        if not applies:
            return HumanPhotorealismGuidance(
                guidance_id=guidance_id,
                project_id=project_id,
                job_id=job_id,
                applies=False,
                subject_type=subject_type,
                variation_mode=variation_mode,
                metadata={"disabled_reason": reason, "doc": "65"},
            )

        realism_level = self._realism_level(user_input, metadata)
        positives = [
            "real camera photograph, not a rendered or AI-beauty face",
            "natural human skin texture with subtle pores, fine detail, and small tonal variation",
            "tiny believable skin imperfections, natural under-eye detail, and non-uniform cheek texture where appropriate",
            "real lens perspective, natural depth of field, and photographed facial planes rather than a flat beauty-filter mask",
            "slight natural facial asymmetry; relaxed facial muscles and believable micro-expression",
            "realistic hairline, baby hairs, flyaway hair, and non-perfect hair strands",
            "natural eye moisture and catchlights; avoid glassy or uncanny eyes",
            "skin responds to light like real skin, with soft but not plastic highlights",
            "soft 35mm or CCD-inspired real-camera imperfections: fine grain, slight edge softness, subtle halation, and mild handheld framing",
            "skin tone is not perfectly uniform; preserve under-eye texture, eyelid detail, neck/shoulder tonal variation, and tiny smile-line hints",
            "attractive commercial portrait, but grounded in a real captured moment rather than a beauty-app or idol photocard finish",
            "commercial polish means camera-ready human realism, not skin blur, face slimming, enlarged eyes, or liquified facial geometry",
            "retain individual facial character: real eyelid folds, lip texture, natural jaw contour, and small non-identical cheek transitions",
            "in bright daylight, keep pore-level skin detail, under-eye shadows, lip texture, and tiny neck or shoulder tone differences instead of a uniform glow",
            "prefer quiet neutral expression or imperfect half-smile over a sweet template smile unless the user explicitly asks for a big smile",
            "healthy clear complexion and fresh bright skin tone created by soft natural bounce light, not by skin whitening or beauty-filter smoothing",
            "clean high-key summer daylight keeps the face flattering, awake, and fresh while preserving natural skin tone, ethnicity, and real texture",
            "gentle cheek warmth and natural lip color keep the portrait attractive without returning to poreless glow",
            "for East Asian fresh, summer, or beauty portrait briefs, keep a clean fair luminous complexion when the user did not request tan, dark, or bronze skin",
            "do not darken or tan East Asian skin by default; use high-key daylight, soft bounce light, and color balance to keep the face clear and luminous",
            "preserve natural head-to-body proportion, balanced neck and shoulder line, and flattering upper-body crop in close portraits",
            "keep harmonious natural facial features, awake eyes, relaxed facial muscles, and a flattering real-camera face angle without beauty-filter reshaping",
        ]
        if has_identity_reference:
            positives.append(
                "preserve the reference person's recognizable identity direction while making the face look more like a real photographed person"
            )
        positives.extend(self._mode_positive_fragments(variation_mode))
        casebook = human_photorealism_casebook(
            variation_mode=variation_mode,
            realism_level=realism_level,
            has_identity_reference=has_identity_reference,
        )
        positives.extend(_string_list(casebook.get("positive_prompt_fragments")))

        negatives = [
            "plastic skin",
            "over-smoothed skin",
            "airbrushed face without texture",
            "AI beauty filter",
            "synthetic influencer face",
            "doll-like face",
            "porcelain mask skin",
            "over-perfect facial symmetry",
            "template smile",
            "uncanny eyes",
            "wax-like skin highlights",
            "CGI face",
            "beauty-filter face",
            "generic AI influencer face",
            "over-sharpened glossy eyes",
            "identical face angle across the whole set",
            "beauty-app face",
            "idol photocard polish",
            "skin-blur retouching",
            "flawless porcelain mask",
            "over-uniform skin tone",
            "over-sharp AI detail",
            "perfect smile repeated across outputs",
            "auto face-slimming",
            "enlarged beauty-filter eyes",
            "perfect V-shaped chin",
            "flawless K-idol beauty retouch",
            "liquified face proportions",
            "algorithmically pretty generic face",
            "too-clean stock-photo model face",
            "uniform luminous skin",
            "dewy plastic makeup skin",
            "cosmetic-ad poreless glow",
            "bright sun erasing all face texture",
            "sweet K-idol template smile",
            "perfect cute influencer smile",
            "dull complexion",
            "muddy skin tone",
            "gray or green skin color cast",
            "underexposed face",
            "harsh facial shadow",
            "tired expression",
            "overly matte documentary look",
            "unflattering dark tan or bronze cast unless requested",
            "suppressed fair complexion",
            "unnecessarily darkened East Asian skin",
            "forced tan or bronze cast unless requested",
            "gray-brown skin cast",
            "dull yellow or green facial cast",
            "fake whitening mask",
            "bleached beauty-filter skin",
            "oversized head",
            "enlarged face scale",
            "short compressed neck",
            "compressed shoulders",
            "warped upper body",
            "pinched torso",
            "bad head-to-body ratio",
            "awkward shoulder crop",
            "unflattering face drift",
            "flattened facial attractiveness",
            "skin whitening filter",
            "beauty-app glow",
        ]
        negatives.extend(_string_list(casebook.get("negative_prompt_fragments")))
        preserve = [
            "keep the same broad face shape, age direction, body type, and recognizable identity cues",
            "allow expression, pose, head angle, camera angle, crop, and small hair styling changes so the set feels photographed",
            "preserve identity through stable facial feature relationships, not by repeating the exact same still",
        ]
        preserve.extend(_string_list(casebook.get("reference_preserve_rules")))
        do_not_inherit = [
            "do not inherit over-smoothed skin, doll-like expression, waxy highlights, or AI-beauty-face artifacts from the reference",
            "do not copy the exact same expression, face angle, or gaze across the whole set",
            "do not carry forward obvious AI badges, generated-image marks, watermarks, synthetic eye highlights, or plastic skin from a reference",
        ]
        do_not_inherit.extend(_string_list(casebook.get("reference_do_not_inherit_rules")))
        review_targets = [
            "skin texture remains visible and natural",
            "expression is specific and believable",
            "face has natural asymmetry without identity drift",
            "eyes and highlights do not feel synthetic",
            "the set does not repeat the same AI-beauty face",
            "the image looks like a real photographed campaign frame rather than a retouched render",
            "real-camera imperfection is visible without making the image look low quality",
            "face avoids beauty-app polish, idol photocard symmetry, and skin-blur retouching",
            "commercial finish is camera-ready and human, not beautified facial geometry",
            "face looks fresh, healthy, bright, and attractive without losing real skin texture or natural skin tone",
            "East Asian fresh portraits keep fair luminous complexion unless a darker or tanned look is explicitly requested",
            "close crops keep natural head, neck, shoulder, and upper-body proportions",
        ]
        review_targets.extend(_string_list(casebook.get("review_targets")))
        casebook_retry = casebook.get("retry_patch_templates") if isinstance(casebook.get("retry_patch_templates"), dict) else {}
        retry_patch_templates = {
            "prompt_additions": _dedupe([*positives[:5], *_string_list(casebook_retry.get("prompt_additions"))]),
            "negative_additions": _dedupe([*negatives, *_string_list(casebook_retry.get("negative_additions"))]),
            "artifact_repair": [
                "repair the face toward natural photographed skin texture, believable expression, realistic eyes, non-plastic highlights, and real lens depth",
                "repair toward soft real-camera capture: fine grain, slight edge softness, natural skin tone variation, loose hair, fabric detail, and a candid non-template expression",
                "repair away from face-slimming filters, enlarged beauty eyes, liquified jaw/chin, and generic AI-beauty identity while keeping the person attractive",
                "repair bright outdoor portraits so sunlight preserves skin pores, under-eye texture, lip detail, and natural neck/shoulder tonal variation instead of a poreless glow",
                "repair template-smile portraits toward a quiet neutral expression or imperfect half-smile with natural mouth tension",
                "repair dull or underexposed portraits with soft natural bounce light, healthy clear complexion, clean bright summer daylight, gentle cheek warmth, and natural skin tone preserved",
                "repair East Asian fresh portraits toward clean fair luminous complexion through exposure, bounce light, and color balance; avoid fake whitening, skin smoothing, or face replacement",
                "repair close portrait framing so the head-to-body ratio, neck, shoulders, and upper-body crop look natural and flattering",
                *_string_list(casebook_retry.get("artifact_repair")),
            ],
            "identity_reinforcement": _dedupe([*preserve, *_string_list(casebook_retry.get("identity_reinforcement"))]),
        }
        return HumanPhotorealismGuidance(
            guidance_id=guidance_id,
            project_id=project_id,
            job_id=job_id,
            applies=True,
            subject_type=subject_type,
            realism_level=realism_level,
            variation_mode=variation_mode,
            positive_prompt_fragments=_dedupe(positives),
            negative_prompt_fragments=_dedupe(negatives),
            reference_preserve_rules=_dedupe(preserve),
            reference_do_not_inherit_rules=_dedupe(do_not_inherit),
            review_targets=_dedupe(review_targets),
            retry_patch_templates=retry_patch_templates,
            user_visible_summary=[
                "Keeps the person recognizable",
                "Adds real-photo skin, expression, and hair detail",
                "Avoids repeated AI-beauty faces",
            ],
            metadata={
                "doc": "65",
                "module_id": self.module_id,
                "enable_reason": reason,
                "has_identity_reference": has_identity_reference,
                "doc68_casebook_recipe": True,
                "casebook_recipe_library": VISUAL_CASEBOOK_RECIPE_LIBRARY_ID,
                "doc70_human_real_camera_tuning": True,
                "doc71_human_attractive_realism_balance": True,
                "doc72_east_asian_fair_complexion_guard": True,
                "human_real_camera_tuning_library": VISUAL_HUMAN_REAL_CAMERA_TUNING_ID,
                "human_attractive_realism_balance_library": VISUAL_HUMAN_ATTRACTIVE_REALISM_BALANCE_ID,
                "human_east_asian_fair_complexion_guard_library": VISUAL_HUMAN_EAST_ASIAN_FAIR_COMPLEXION_GUARD_ID,
            },
        )

    def review(
        self,
        *,
        guidance: HumanPhotorealismGuidance,
        project_id: str | None,
        job_id: str | None,
        issue_codes: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AntiAIFaceReviewResult:
        issue_codes = [code for code in _dedupe(issue_codes or []) if code in _ANTI_AI_FACE_ISSUES]
        review_id = stable_id("anti_ai_face_review", project_id, job_id, guidance.guidance_id, ",".join(issue_codes))
        if not guidance.applies:
            return AntiAIFaceReviewResult(
                review_id=review_id,
                project_id=project_id,
                job_id=job_id,
                applies=False,
                status="not_applicable",
                metadata={"doc": "65", **dict(metadata or {})},
            )
        retry_patch = dict(guidance.retry_patch_templates) if issue_codes else {}
        return AntiAIFaceReviewResult(
            review_id=review_id,
            project_id=project_id,
            job_id=job_id,
            applies=True,
            status="retry_recommended" if issue_codes else "planned",
            issue_codes=issue_codes,
            severity="medium" if issue_codes else "pass",
            retry_patch=retry_patch,
            user_visible_summary=(
                ["Face realism needs one cleaner retry", "V3 prepared more natural skin and expression guidance"]
                if issue_codes
                else ["Face realism will be checked after generation"]
            ),
            metadata={"doc": "65", **dict(metadata or {})},
        )

    def _applies(
        self,
        *,
        user_input: str,
        subject_type: str,
        scenario_id: str,
        template_id: str,
        metadata: dict[str, Any],
    ) -> tuple[bool, str]:
        if _truthy(metadata.get("disable_human_photorealism")):
            return False, "disabled_by_metadata"
        text = " ".join([user_input, scenario_id, template_id, str(metadata.get("quality_mode") or "")]).lower()
        if _contains_any(text, _STYLIZED_TERMS) or any(term in user_input for term in _CHINESE_STYLIZED_TERMS):
            return False, "stylized_request"
        if subject_type == "character":
            return True, "character_subject_policy"
        if _contains_any(text, _HUMAN_TERMS) or any(term in user_input for term in _CHINESE_HUMAN_TERMS):
            return True, "human_prompt_signal"
        return False, "no_human_signal"

    def _realism_level(self, user_input: str, metadata: dict[str, Any]) -> str:
        text = " ".join([user_input, str(metadata.get("quality_mode") or "")]).lower()
        if any(token in text for token in ["beauty", "editorial", "commercial", "cover", "campaign"]):
            return "commercial_photoreal"
        if any(term in user_input for term in ["\u5546\u4e1a", "\u5c01\u9762", "\u5199\u771f"]):
            return "commercial_photoreal"
        return "natural_photoreal"

    def _mode_positive_fragments(self, variation_mode: str) -> list[str]:
        mode = str(variation_mode or "").strip().lower()
        if mode == "selection_candidates":
            return [
                "make each option feel like a different real shutter moment, with changed expression, pose, gaze, and head angle"
            ]
        if mode in {"creative_explore", "creative_exploration"}:
            return ["keep photographic realism even while exploring a bolder scene, wardrobe, or mood"]
        if mode in {"layout_adaptation", "format_layout_adaptation"}:
            return ["adapt crop and layout while preserving natural face scale, skin texture, and believable expression"]
        return ["make the set feel like a directed real photoshoot with varied but coherent human moments"]


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
