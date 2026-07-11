"""Human photorealism and anti-AI-face guidance for the V3 visual cluster."""

from __future__ import annotations

import re
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
HUMAN_REALISM_PLUGIN_METADATA_KEY = "human_realism_plugin"

_HUMAN_TERMS = {
    "portrait",
    "photo portrait",
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
    "fashion model",
    "child model",
    "kid model",
    "baby",
    "boy",
    "child",
    "children",
    "person wearing",
    "wearing the product",
    "model wearing",
    "hand holding",
    "holding the product",
    "skin detail",
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
    "\u7537\u5b69",
    "\u513f\u7ae5",
    "\u5c0f\u670b\u53cb",
    "\u5b9d\u5b9d",
    "\u7a7f\u7740",
    "\u4e0a\u8eab",
    "\u624b",
    "\u76ae\u80a4",
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
    "toy figure",
    "vinyl toy",
    "mascot",
    "clay figure",
}

_CHINESE_STYLIZED_TERMS = {
    "\u52a8\u6f2b",
    "\u6f2b\u753b",
    "\u63d2\u753b",
    "\u5361\u901a",
    "\u4e8c\u6b21\u5143",
    "\u6e32\u67d3",
    "\u4e09\u7ef4",
    "\u73a9\u5076",
    "\u516c\u4ed4",
    "\u5409\u7965\u7269",
}

_NEGATION_TERMS = {
    "avoid",
    "no",
    "not",
    "without",
    "reject",
    "remove",
    "prevent",
    "不要",
    "避免",
    "拒绝",
    "不能",
    "不要有",
    "不是",
}

_PRODUCT_WITH_HUMAN_TERMS = {
    "apparel",
    "clothing",
    "clothes",
    "fashion",
    "garment",
    "dress",
    "skirt",
    "shirt",
    "jacket",
    "coat",
    "pants",
    "shoes",
    "accessory",
    "accessories",
    "beauty",
    "makeup",
    "skincare",
    "fitness",
    "lifestyle",
    "wearing",
    "on model",
    "model shot",
    "product in use",
    "handheld",
    "hand-held",
}

_CHINESE_PRODUCT_WITH_HUMAN_TERMS = {
    "\u670d\u88c5",
    "\u5973\u88c5",
    "\u7537\u88c5",
    "\u88d9",
    "\u5916\u5957",
    "\u978b",
    "\u914d\u9970",
    "\u7f8e\u5986",
    "\u62a4\u80a4",
    "\u5065\u8eab",
    "\u751f\u6d3b\u65b9\u5f0f",
    "\u4e0a\u8eab",
    "\u7a7f\u7740",
    "\u624b\u6301",
    "\u624b\u62ff",
}

_CHILD_TERMS = {
    "child",
    "children",
    "kid",
    "kids",
    "baby",
    "boy",
    "girl",
    "teen",
    "toddler",
}

_CHINESE_CHILD_TERMS = {
    "\u513f\u7ae5",
    "\u5c0f\u670b\u53cb",
    "\u5b69\u5b50",
    "\u5b9d\u5b9d",
    "\u7537\u5b69",
    "\u5973\u5b69",
    "\u5c11\u5e74",
    "\u5c11\u5973",
}

_EXPLICIT_AGE_TERMS = _CHILD_TERMS | {
    "adult",
    "young adult",
    "middle-aged",
    "middle aged",
    "senior",
    "elderly",
    "older person",
}

_CHINESE_EXPLICIT_AGE_TERMS = _CHINESE_CHILD_TERMS | {
    "\u6210\u5e74\u4eba",
    "\u9752\u5e74",
    "\u4e2d\u5e74",
    "\u8001\u5e74",
    "\u8001\u4eba",
}

_HAND_OR_SKIN_TERMS = {
    "hand",
    "hands",
    "skin",
    "finger",
    "fingers",
    "holding",
    "handheld",
    "hand-held",
}

_CHINESE_HAND_OR_SKIN_TERMS = {
    "\u624b",
    "\u624b\u6301",
    "\u624b\u62ff",
    "\u624b\u6307",
    "\u76ae\u80a4",
}

_LOW_KEY_TERMS = {
    "low-key",
    "low key",
    "dark",
    "dim light",
    "dimly lit",
    "dim available light",
    "night",
    "spotlight",
    "shadow-rich",
    "deep shadow",
    "understated exposure",
}

_CHINESE_LOW_KEY_TERMS = {
    "\u6697\u8c03",
    "\u4f4e\u8c03",
    "\u5c40\u90e8\u805a\u5149",
    "\u591c",
    "\u9634\u5f71",
}

_HIGH_KEY_TERMS = {
    "daylight",
    "clean bright",
    "high-key",
    "high key",
    "sunny",
    "bright exposure",
    "soft daylight",
}

_CHINESE_HIGH_KEY_TERMS = {
    "\u660e\u4eae",
    "\u65e5\u5149",
    "\u9ad8\u8c03",
    "\u5e72\u51c0\u900f\u4eae",
}

_ANTI_AI_FACE_ISSUES = {
    "ai_face_render",
    "plastic_skin",
    "over_smoothed_skin",
    "missing_skin_texture",
    "synthetic_beauty_filter",
    "over_retouching",
    "poreless_beauty_surface",
    "synthetic_fashion_face",
    "weak_photographic_imperfection",
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
    "beautiful_realism_balance_failure",
    "realism_made_subject_less_attractive",
    "pretty_but_too_ai_filtered",
    "real_but_unflattering",
    "skin_texture_beauty_balance_failure",
    "unflattering_feature_degradation",
    "suppressed_fair_complexion",
    "forced_tan_or_bronze_cast",
    "gray_brown_skin_cast",
    "head_body_proportion_distortion",
    "oversized_head",
    "compressed_neck_shoulders",
    "unflattering_face_drift",
    "same_expression_repetition",
    "same_head_angle_repetition",
    "same_pose_repetition",
    "doll_like_child_face",
    "adultified_child_model",
    "synthetic_child_skin",
    "pageant_polish_child_face",
    "frozen_child_smile",
    "unreal_child_eyes",
    "unreal_child_teeth",
    "child_face_ai_render",
    "age_identity_drift",
    "age_inappropriate_rendering",
    "complexion_direction_drift",
    "unintended_skin_darkening",
    "unintended_skin_lightening",
    "unflattering_skin_color_cast",
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
        activation = self._activation(
            user_input=user_input,
            subject_type=subject_type,
            scenario_id=scenario_id,
            template_id=template_id,
            metadata=metadata,
        )
        applies = bool(activation.get("applies"))
        reason = str(activation.get("primary_reason") or activation.get("disabled_reason") or "unknown")
        guidance_id = stable_id("human_photorealism_guidance", project_id, job_id, scenario_id, user_input, variation_mode)
        if not applies:
            return HumanPhotorealismGuidance(
                guidance_id=guidance_id,
                project_id=project_id,
                job_id=job_id,
                applies=False,
                subject_type=subject_type,
                variation_mode=variation_mode,
                metadata={
                    "disabled_reason": reason,
                    "doc": "65",
                    "doc91_human_realism_plugin": True,
                    HUMAN_REALISM_PLUGIN_METADATA_KEY: activation,
                },
            )

        realism_level = self._realism_level(user_input, metadata)
        human_subject_kind = str(activation.get("human_subject_kind") or "person")
        style_profile = str(activation.get("style_profile") or "neutral_real_camera")
        rendering_profile = dict(activation.get("universal_rendering_profile") or {})
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
            "prefer quiet neutral expression or imperfect half-smile over a sweet template smile unless the user explicitly asks for a big smile",
            "preserve the subject's natural complexion direction from the reference or explicit prompt; exposure and color grading must not accidentally gray, darken, bleach, tan, or flatten the skin",
            "preserve the requested or referenced age band through age-consistent facial and body relationships without adultification, infantilization, or doll-like morphology",
            "preserve natural head-to-body proportion, balanced neck and shoulder line, and flattering upper-body crop in close portraits",
            "keep harmonious natural facial features, awake eyes, relaxed facial muscles, and a flattering real-camera face angle without beauty-filter reshaping",
        ]
        positives.extend(_rendering_positive_fragments(rendering_profile))
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
            "over-polished collectible portrait-card finish",
            "skin-blur retouching",
            "flawless porcelain mask",
            "over-uniform skin tone",
            "over-sharp AI detail",
            "perfect smile repeated across outputs",
            "auto face-slimming",
            "enlarged beauty-filter eyes",
            "perfect V-shaped chin",
            "culturally generic idol-style beauty retouch",
            "liquified face proportions",
            "algorithmically pretty generic face",
            "too-clean stock-photo model face",
            "uniform luminous skin",
            "dewy plastic makeup skin",
            "cosmetic-ad poreless glow",
            "bright sun erasing all face texture",
            "sweet template celebrity smile",
            "perfect cute influencer smile",
            "dull complexion",
            "muddy skin tone",
            "gray or green skin color cast",
            "underexposed face",
            "harsh facial shadow",
            "tired expression",
            "overly matte documentary look",
            "unintended complexion darkening or lightening",
            "unrequested tan, bronze, gray, yellow, or green facial cast",
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
            "age-inappropriate facial morphology",
            "adultification or infantilization",
            "age-inappropriate beauty retouching",
        ]
        negatives.extend(_rendering_negative_fragments(rendering_profile))
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
            "face remains attractive and correctly exposed without losing real skin texture or the requested complexion direction",
            "exposure and color grading preserve the reference or explicitly requested complexion rather than imposing a demographic default",
            "facial and body morphology remain consistent with the requested or referenced age band",
            "close crops keep natural head, neck, shoulder, and upper-body proportions",
        ]
        review_targets.extend(_rendering_review_targets(rendering_profile))
        review_targets.extend(_string_list(casebook.get("review_targets")))
        casebook_retry = casebook.get("retry_patch_templates") if isinstance(casebook.get("retry_patch_templates"), dict) else {}
        retry_patch_templates = {
            "prompt_additions": _dedupe([*positives[:5], *_string_list(casebook_retry.get("prompt_additions"))]),
            "negative_additions": _dedupe([*negatives, *_string_list(casebook_retry.get("negative_additions"))]),
            "artifact_repair": [
                "repair the face toward natural photographed skin texture, believable expression, realistic eyes, non-plastic highlights, and real lens depth",
                "repair toward soft real-camera capture: fine grain, slight edge softness, natural skin tone variation, loose hair, fabric detail, and a candid non-template expression",
                "repair away from face-slimming filters, enlarged beauty eyes, liquified jaw/chin, and generic AI-beauty identity while keeping the person attractive",
                "repair prompt-defined facial lighting so its intended exposure key preserves skin pores, under-eye texture, lip detail, and natural neck/shoulder tonal variation instead of a poreless glow",
                "repair template-smile portraits toward a quiet neutral expression or imperfect half-smile with natural mouth tension",
                "repair exposure or color-cast drift while preserving the reference or explicitly requested complexion direction; avoid whitening masks, forced tanning, skin smoothing, or face replacement",
                "repair age drift toward the requested or referenced age band with age-consistent face, eyes, cheeks, teeth, neck, shoulders, expression, and skin response",
                "repair close portrait framing so the head-to-body ratio, neck, shoulders, and upper-body crop look natural and flattering",
                *_rendering_retry_fragments(rendering_profile),
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
                "doc91_human_realism_plugin": True,
                "doc92_style_aware_ai_feel_suppression": True,
                "doc94_universal_rendering_profile": True,
                HUMAN_REALISM_PLUGIN_METADATA_KEY: activation,
                "universal_rendering_profile": rendering_profile,
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

    @classmethod
    def is_human_realism_issue_code(cls, issue_code: str) -> bool:
        return str(issue_code or "").strip() in _ANTI_AI_FACE_ISSUES

    def retry_patch_for_issue_codes(
        self,
        issue_codes: list[str],
        *,
        child_model: bool = False,
    ) -> dict[str, list[str]]:
        filtered = [code for code in _dedupe(issue_codes) if code in _ANTI_AI_FACE_ISSUES]
        if not filtered:
            return {}
        legacy_age_issue = child_model or any(
            code.startswith(("child_", "doll_like_child", "adultified_child", "synthetic_child", "pageant_"))
            for code in filtered
        )
        user_input = "real human photography with natural identity, age fidelity, and no synthetic beauty-face rendering"
        guidance = self.build(
            project_id=None,
            job_id=None,
            scenario_id="doc91_retry_repair",
            template_id="shared_visual_cluster",
            user_input=user_input,
            subject_type="character",
            variation_mode="delivery_suite",
            has_identity_reference=True,
            metadata={
                "force_human_realism_plugin": True,
                "human_subject_kind": "person",
                "human_realism_strictness": "commercial_strict",
                "age_fidelity": "follow_explicit_prompt" if legacy_age_issue else "preserve_reference",
                "legacy_age_issue_alias": legacy_age_issue,
            },
        )
        review = self.review(
            guidance=guidance,
            project_id=None,
            job_id=None,
            issue_codes=filtered,
            metadata={"doc91_retry_patch_owner": self.module_id},
        )
        return {
            key: _string_list(value)
            for key, value in review.retry_patch.items()
            if isinstance(value, list) and _string_list(value)
        }

    def _activation(
        self,
        *,
        user_input: str,
        subject_type: str,
        scenario_id: str,
        template_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if _truthy(metadata.get("disable_human_photorealism")):
            return _activation_payload(
                applies=False,
                primary_reason="disabled_by_metadata",
                disabled_reason="disabled_by_metadata",
                disabled_by_style=False,
                subject_type=subject_type,
            )
        if _truthy(metadata.get("force_human_realism_plugin")):
            forced_kind = str(metadata.get("human_subject_kind") or "person")
            rendering_profile = _universal_rendering_profile("", metadata=metadata)
            return _activation_payload(
                applies=True,
                primary_reason="forced_by_metadata",
                reason_codes=["forced_by_metadata"],
                subject_type=subject_type,
                human_subject_kind=forced_kind,
                strictness=str(metadata.get("human_realism_strictness") or "commercial_strict"),
                style_profile=str(metadata.get("human_realism_style_profile") or rendering_profile["profile_id"]),
                universal_rendering_profile=rendering_profile,
                evidence={"metadata": ["force_human_realism_plugin"]},
            )

        text = _combined_activation_text(
            user_input=user_input,
            scenario_id=scenario_id,
            template_id=template_id,
            subject_type=subject_type,
            metadata=metadata,
        )
        if _stylized_requested(text):
            return _activation_payload(
                applies=False,
                primary_reason="stylized_request",
                disabled_reason="stylized_request",
                disabled_by_style=True,
                subject_type=subject_type,
                evidence={"stylized_request": True},
            )

        reason_codes: list[str] = []
        evidence: dict[str, Any] = {}
        if subject_type == "character":
            reason_codes.append("character_subject_policy")
            evidence["subject_type"] = subject_type
        if _contains_any(text, _HUMAN_TERMS) or _contains_any(text, _CHINESE_HUMAN_TERMS):
            reason_codes.append("human_prompt_signal")
        if _contains_any(text, _PRODUCT_WITH_HUMAN_TERMS) or _contains_any(text, _CHINESE_PRODUCT_WITH_HUMAN_TERMS):
            reason_codes.append("product_with_human_signal")
        if any(role in text for role in ["face_reference", "person_reference", "portrait_reference"]):
            reason_codes.append("face_or_person_reference")
        if any(token in text for token in ["ecommerce", "product", "listing"]) and "product_with_human_signal" in reason_codes:
            reason_codes.append("ecommerce_human_model_detected")

        explicit_age_signal = _contains_any(text, _EXPLICIT_AGE_TERMS) or _contains_any(text, _CHINESE_EXPLICIT_AGE_TERMS)
        is_hand_or_skin = _contains_any(text, _HAND_OR_SKIN_TERMS) or _contains_any(text, _CHINESE_HAND_OR_SKIN_TERMS)
        if any(token in reason_codes for token in ["product_with_human_signal", "ecommerce_human_model_detected"]):
            human_subject_kind = "product_on_person"
            strictness = "commercial_strict"
        elif is_hand_or_skin and not any(token in text for token in ["face", "\u8138", "portrait", "\u4eba\u50cf"]):
            human_subject_kind = "hand_or_skin_detail"
            strictness = "balanced"
            reason_codes.append("hand_or_skin_detail_detected")
        elif "model" in text or "\u6a21\u7279" in text:
            human_subject_kind = "person"
            strictness = "commercial_strict"
        else:
            human_subject_kind = "person"
            strictness = "commercial_strict" if any(token in text for token in ["commercial", "cover", "campaign", "\u5546\u4e1a", "\u5c01\u9762"]) else "balanced"
        if explicit_age_signal:
            reason_codes.append("explicit_age_fidelity_signal")

        reason_codes = _dedupe(reason_codes)
        if not reason_codes:
            return _activation_payload(
                applies=False,
                primary_reason="no_human_signal",
                disabled_reason="no_human_signal",
                disabled_by_style=False,
                subject_type=subject_type,
            )

        evidence["text_signals"] = reason_codes
        rendering_profile = _universal_rendering_profile(
            text,
            metadata={**metadata, "age_fidelity": "follow_explicit_prompt" if explicit_age_signal else metadata.get("age_fidelity")},
        )
        return _activation_payload(
            applies=True,
            primary_reason=reason_codes[0],
            reason_codes=reason_codes,
            subject_type=subject_type,
            human_subject_kind=human_subject_kind,
            strictness=strictness,
            style_profile=rendering_profile["profile_id"],
            universal_rendering_profile=rendering_profile,
            evidence=evidence,
        )

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
    normalized = str(text or "").lower()
    for term in terms:
        candidate = str(term or "").lower()
        if not candidate:
            continue
        if candidate.isascii():
            if re.search(rf"(?<![a-z0-9]){re.escape(candidate)}(?![a-z0-9])", normalized):
                return True
        elif candidate in normalized:
            return True
    return False


def _combined_activation_text(
    *,
    user_input: str,
    scenario_id: str,
    template_id: str,
    subject_type: str,
    metadata: dict[str, Any],
) -> str:
    pieces = [
        user_input,
        scenario_id,
        template_id,
        subject_type,
        str(metadata.get("quality_mode") or ""),
        str(metadata.get("human_subject_kind") or ""),
        str(metadata.get("image_purpose") or ""),
        str(metadata.get("variation_mode") or ""),
        _flatten_text(metadata.get("template_policy")),
        _flatten_text(metadata.get("product_profile")),
        _flatten_text(metadata.get("uploaded_asset_roles")),
        _flatten_text(metadata.get("asset_role_summary")),
        _flatten_text(metadata.get("brain_summary")),
        _flatten_text(metadata.get("llm_brain_summary")),
        _flatten_text(metadata.get("project_context_summary")),
    ]
    return " ".join(part for part in pieces if part).lower()


def _flatten_text(value: Any, *, max_items: int = 80) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        parts: list[str] = []
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                break
            parts.append(str(key))
            parts.append(_flatten_text(item, max_items=max_items))
        return " ".join(part for part in parts if part)
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten_text(item, max_items=max_items) for item in list(value)[:max_items])
    return str(value)


def _stylized_requested(text: str) -> bool:
    stylized_terms = [*_STYLIZED_TERMS, *_CHINESE_STYLIZED_TERMS]
    for term in stylized_terms:
        index = text.find(term)
        while index >= 0:
            prefix = text[max(0, index - 28) : index]
            if not any(negation in prefix for negation in _NEGATION_TERMS):
                return True
            index = text.find(term, index + len(term))
    return False


def _universal_rendering_profile(text: str, *, metadata: dict[str, Any]) -> dict[str, Any]:
    explicit = metadata.get("human_rendering_profile")
    explicit = dict(explicit) if isinstance(explicit, dict) else {}
    low_key = _contains_any(text, _LOW_KEY_TERMS) or _contains_any(text, _CHINESE_LOW_KEY_TERMS)
    high_key = _contains_any(text, _HIGH_KEY_TERMS) or _contains_any(text, _CHINESE_HIGH_KEY_TERMS)
    exposure_key = str(explicit.get("exposure_key") or metadata.get("exposure_key") or "").strip().lower()
    if exposure_key not in {"low", "medium", "high", "prompt_defined"}:
        exposure_key = "low" if low_key else "high" if high_key else "prompt_defined"
    skin_specularity = str(
        explicit.get("skin_specularity") or metadata.get("skin_specularity") or "prompt_defined"
    ).strip().lower()
    if skin_specularity not in {"matte", "natural", "luminous", "prompt_defined"}:
        skin_specularity = "prompt_defined"
    age_fidelity = str(
        explicit.get("age_fidelity") or metadata.get("age_fidelity") or "preserve_reference"
    ).strip().lower()
    if age_fidelity not in {"preserve_reference", "follow_explicit_prompt", "neutral"}:
        age_fidelity = "preserve_reference"
    complexion_policy = str(
        explicit.get("complexion_policy") or metadata.get("complexion_policy") or "preserve_reference"
    ).strip().lower()
    if complexion_policy not in {"preserve_reference", "follow_explicit_prompt", "neutral"}:
        complexion_policy = "preserve_reference"
    profile_id = {
        "low": "low_key_texture_preserving",
        "high": "high_key_texture_preserving",
        "medium": "balanced_texture_preserving",
    }.get(exposure_key, "neutral_real_camera")
    return {
        "profile_id": profile_id,
        "real_human_intent": True,
        "exposure_key": exposure_key,
        "contrast_direction": str(explicit.get("contrast_direction") or "prompt_defined"),
        "color_temperature": str(explicit.get("color_temperature") or "prompt_defined"),
        "skin_specularity": skin_specularity,
        "skin_texture": str(explicit.get("skin_texture") or "natural"),
        "complexion_policy": complexion_policy,
        "age_fidelity": age_fidelity,
        "identity_priority": str(explicit.get("identity_priority") or "normal"),
        "doc": "94",
    }


def _rendering_positive_fragments(profile: dict[str, Any]) -> list[str]:
    exposure_key = str(profile.get("exposure_key") or "prompt_defined")
    fragments: list[str] = []
    if exposure_key == "low":
        fragments.extend(
            [
                "under a low exposure key, keep readable facial planes, fine skin texture, and controlled highlight roll-off without oily or waxy shine",
                "preserve the prompt's shadow depth and contrast instead of replacing it with generic bright commercial face lighting",
            ]
        )
    elif exposure_key == "high":
        fragments.extend(
            [
                "under a high exposure key, keep eyelid, under-eye, lip, pore, neck, and shoulder detail instead of washing the face into a uniform glow",
                "use prompt-consistent flattering light while preserving natural complexion and real texture rather than a whitening or smoothing filter",
            ]
        )
    else:
        fragments.append(
            "follow the prompt's exposure and color direction while preserving facial texture, natural complexion, and believable highlight response"
        )
    return fragments


def _rendering_negative_fragments(profile: dict[str, Any]) -> list[str]:
    exposure_key = str(profile.get("exposure_key") or "prompt_defined")
    if exposure_key == "low":
        return [
            "oily forehead or cheeks in low-key light",
            "waxy nose-bridge highlight",
            "crushed facial planes with lost identity detail",
            "generic high-key commercial face lighting overriding the prompt",
        ]
    if exposure_key == "high":
        return [
            "washed-out facial texture",
            "bright exposure erasing eyelid, lip, pore, neck, or shoulder detail",
            "uniform whitening-mask glow",
        ]
    return ["prompt-inconsistent facial exposure", "plastic or waxy highlight response"]


def _rendering_review_targets(profile: dict[str, Any]) -> list[str]:
    exposure_key = str(profile.get("exposure_key") or "prompt_defined")
    return [
        f"skin texture and facial planes remain believable under the requested {exposure_key} exposure direction",
        "complexion follows reference truth or explicit prompt direction without demographic defaults",
        "age identity remains consistent without adultification, infantilization, or doll-like morphology",
    ]


def _rendering_retry_fragments(profile: dict[str, Any]) -> list[str]:
    exposure_key = str(profile.get("exposure_key") or "prompt_defined")
    if exposure_key == "low":
        return [
            "repair low-key facial rendering with restrained specular highlights, readable bone planes, real pores, and preserved shadow atmosphere"
        ]
    if exposure_key == "high":
        return [
            "repair high-key facial rendering so bright exposure retains pores, eyelid folds, lip texture, under-eye detail, and natural complexion"
        ]
    return ["repair facial exposure and skin response to match the prompt while preserving natural texture and complexion"]


def _activation_payload(
    *,
    applies: bool,
    primary_reason: str,
    subject_type: str,
    reason_codes: list[str] | None = None,
    disabled_reason: str | None = None,
    disabled_by_style: bool = False,
    human_subject_kind: str = "none",
    strictness: str = "off",
    style_profile: str = "neutral_real_camera",
    universal_rendering_profile: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if applies and human_subject_kind == "none":
        human_subject_kind = "person"
    if applies and strictness == "off":
        strictness = "balanced"
    review_codes = list(_ANTI_AI_FACE_ISSUES) if applies else []
    return {
        "applies": applies,
        "primary_reason": primary_reason,
        "reason_codes": _dedupe(reason_codes or ([primary_reason] if applies else [])),
        "disabled_reason": disabled_reason,
        "disabled_by_style": disabled_by_style,
        "subject_type": subject_type,
        "human_subject_kind": human_subject_kind,
        "strictness": strictness,
        "style_profile": style_profile if applies else "stylized_disabled" if disabled_by_style else "off",
        "universal_rendering_profile": dict(universal_rendering_profile or {}),
        "review_issue_codes": review_codes,
        "evidence": evidence or {},
        "doc": "91",
        "doc92": True,
    }


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
