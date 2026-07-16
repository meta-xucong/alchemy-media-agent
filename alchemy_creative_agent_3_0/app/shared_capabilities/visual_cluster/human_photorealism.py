"""Human photorealism and anti-AI-face guidance for the V3 visual cluster."""

from __future__ import annotations

import re
from typing import Any

from ...creative_core.rules import stable_id
from .contracts import AntiAIFaceReviewResult, HumanPhotorealismGuidance


HUMAN_PHOTOREALISM_MODULE_ID = "human_photorealism_layer"
ANTI_AI_FACE_REVIEW_MODULE_ID = "anti_ai_face_review"
HUMAN_REALISM_PLUGIN_METADATA_KEY = "human_realism_plugin"

# Doc128 deliberately keeps these dimensions broad.  They are shared review
# semantics, not a prompt vocabulary, a demographic classifier, or template
# art direction.  Older detailed codes are accepted only through the alias
# normalizer below so existing history remains readable.
HUMAN_REALISM_REVIEW_DIMENSIONS = (
    "human_rendering_artifact",
    "human_anatomy_or_proportion",
    "human_age_or_identity_fidelity",
    "human_skin_or_retouch",
    "human_scene_coherence",
)

_LEGACY_HUMAN_AGE_ALIASES = {
    "adultified_child_model",
    "pageant_polish_child_face",
    "frozen_child_smile",
    "unreal_child_eyes",
    "unreal_child_teeth",
    "child_face_ai_render",
    "age_inappropriate_rendering",
}
_LEGACY_HUMAN_SKIN_ALIASES = {
    "synthetic_child_skin",
    "plastic_skin",
    "over_smoothed_skin",
    "missing_skin_texture",
    "over_retouching",
    "poreless_beauty_surface",
    "skin_blur_retouching",
    "over_uniform_skin_tone",
    "dull_complexion",
    "muddy_skin_tone",
    "unflattering_color_cast",
    "suppressed_fair_complexion",
    "forced_tan_or_bronze_cast",
    "gray_brown_skin_cast",
}
_LEGACY_HUMAN_ANATOMY_ALIASES = {
    "bad_hands_or_body",
    "head_body_proportion_distortion",
    "oversized_head",
    "compressed_neck_shoulders",
}
_LEGACY_HUMAN_SCENE_ALIASES = {
    "flat_scene_lighting",
    "airbrushed_background_texture",
    "synthetic_material_response",
    "frozen_centered_pose",
}


def normalize_human_realism_issue_code(issue_code: str) -> str:
    """Map historical fine-grained reviewer labels to Doc128 dimensions.

    The mapping is intentionally one-way: it preserves old records without
    allowing legacy labels to become a new Provider prompt or review contract.
    """

    normalized = str(issue_code or "").strip()
    if normalized in HUMAN_REALISM_REVIEW_DIMENSIONS:
        return normalized
    if normalized in _LEGACY_HUMAN_AGE_ALIASES:
        return "human_age_or_identity_fidelity"
    if normalized in _LEGACY_HUMAN_SKIN_ALIASES:
        return "human_skin_or_retouch"
    if normalized in _LEGACY_HUMAN_ANATOMY_ALIASES:
        return "human_anatomy_or_proportion"
    if normalized in _LEGACY_HUMAN_SCENE_ALIASES:
        return "human_scene_coherence"
    # These labels are shared with Portrait Identity or suite-direction review.
    # Do not steal their owner merely because old Human Realism lists happened
    # to mention them.
    if normalized in {"age_identity_drift", "same_expression_repetition", "same_head_angle_repetition", "same_pose_repetition"}:
        return normalized
    if normalized in _ANTI_AI_FACE_ISSUES:
        return "human_rendering_artifact"
    return normalized

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

# These patterns describe a rendered-looking word as a physical object's
# content or placement, rather than as the requested rendering medium for the
# complete image.  They deliberately name only generic surface semantics: the
# same distinction applies to packaging, a book cover, a garment, a sign, or
# another reference-bound object.
_ILLUSTRATION_OBJECT_DETAIL_PATTERNS = (
    re.compile(
        r"\b(?:illustration|illustrated)\s+(?:placement|print|pattern|motif|graphic|detail|element|artwork|design)\b"
    ),
    re.compile(
        r"\b(?:front|back|side|surface|cover|label|package|product)\s+(?:illustration|illustrated)\b"
    ),
    re.compile(r"(?:插画|插图|漫画)(?:位置|摆放|图案|印花|元素|细节|设计)"),
)

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
    "minor",
    "school-age",
    "school age",
    "schoolchild",
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
    "\u5b66\u9f84",
    "\u672a\u6210\u5e74",
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
    "flat_scene_lighting",
    "airbrushed_background_texture",
    "synthetic_material_response",
    "frozen_centered_pose",
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
        brain_owned_forward_execution = bool(metadata.get("brain_owned_forward_execution"))
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
        rendering_profile = dict(activation.get("universal_rendering_profile") or {})
        if human_subject_kind == "hand_or_skin_detail":
            return self._hand_or_skin_guidance(
                guidance_id=guidance_id,
                project_id=project_id,
                job_id=job_id,
                subject_type=subject_type,
                variation_mode=variation_mode,
                realism_level=realism_level,
                activation=activation,
                rendering_profile=rendering_profile,
                brain_owned_forward_execution=brain_owned_forward_execution,
            )
        positives = [
            "Render the visible person as a physically credible real-camera photograph; preserve explicit or reference-backed identity and age direction.",
            "Keep anatomy, skin and material response, light, depth, contact, and the surrounding scene physically coherent.",
            "Preserve the requested mood and prompt-owned styling without synthetic beauty filtering or generic rendered-person artifacts.",
        ]
        negatives = [
            "Do not introduce synthetic beauty filtering, anatomy distortion, or incoherent photographic rendering.",
        ]
        preserve = (
            [
                "Preserve identity-critical facial geometry and explicit age direction; current prompt owns hair, wardrobe, lighting, scene, and style unless another frozen channel locks them.",
            ]
            if has_identity_reference
            else []
        )
        do_not_inherit = [
            "Do not copy reference artifacts or widen reference-owned channels while improving human rendering.",
        ]
        review_targets = list(HUMAN_REALISM_REVIEW_DIMENSIONS)
        retry_patch_templates = {
            "prompt_additions": [
                "Repair photographic human naturalness and physical coherence without changing user-owned creative direction.",
            ],
            "negative_additions": [
                "Do not introduce synthetic beauty rendering, anatomy distortion, or reference-channel drift.",
            ],
            "identity_reinforcement": preserve,
        }
        semantic_contract = self._semantic_contract(
            activation=activation,
            human_subject_kind=human_subject_kind,
            review_targets=review_targets,
        )
        return HumanPhotorealismGuidance(
            guidance_id=guidance_id,
            project_id=project_id,
            job_id=job_id,
            applies=True,
            subject_type=subject_type,
            realism_level=realism_level,
            variation_mode=variation_mode,
            semantic_contract=semantic_contract,
            positive_prompt_fragments=[] if brain_owned_forward_execution else _dedupe(positives),
            negative_prompt_fragments=[] if brain_owned_forward_execution else _dedupe(negatives),
            reference_preserve_rules=[] if brain_owned_forward_execution else _dedupe(preserve),
            reference_do_not_inherit_rules=[] if brain_owned_forward_execution else _dedupe(do_not_inherit),
            review_targets=_dedupe(review_targets),
            retry_patch_templates={} if brain_owned_forward_execution else retry_patch_templates,
            user_visible_summary=[
                "Keeps the person recognizable",
                "Adds real-photo skin, expression, and hair detail",
                "Avoids repeated AI-beauty faces",
            ],
            metadata={
                "doc": "128",
                "module_id": self.module_id,
                "enable_reason": reason,
                "doc91_human_realism_plugin": True,
                "doc128_shared_constraint_contract": True,
                HUMAN_REALISM_PLUGIN_METADATA_KEY: activation,
                "provider_safety_profile": {
                    "applies": bool(activation.get("safety_sensitive_person")),
                    "contract": "safety_sensitive_person_v1",
                    "internal_anatomy_or_quality_terms_suppressed": bool(
                        activation.get("safety_sensitive_person")
                    ),
                    "reference_scope": "resolved_channels_only",
                },
                "universal_rendering_profile": rendering_profile,
                "has_identity_reference": has_identity_reference,
                "brain_owned_forward_execution": brain_owned_forward_execution,
            },
        )

    def _hand_or_skin_guidance(
        self,
        *,
        guidance_id: str,
        project_id: str | None,
        job_id: str | None,
        subject_type: str,
        variation_mode: str,
        realism_level: str,
        activation: dict[str, Any],
        rendering_profile: dict[str, Any],
        brain_owned_forward_execution: bool,
    ) -> HumanPhotorealismGuidance:
        """Keep the shared human capability precise for a hand/skin detail."""
        positives = [
            "Render the requested visible hand or skin detail with credible anatomy, physical object contact, and real-camera material response.",
        ]
        negatives = [
            "Do not introduce anatomy distortion, impossible contact, or synthetic surface rendering.",
        ]
        do_not_inherit = [
            "Do not copy reference artifacts or widen reference-owned channels while improving human rendering.",
        ]
        review_targets = [
            "human_anatomy_or_proportion",
            "human_skin_or_retouch",
            "human_scene_coherence",
        ]
        retry_patch_templates = {
            "prompt_additions": [
                "Repair photographic human naturalness and physical coherence without changing user-owned creative direction.",
            ],
            "negative_additions": [
                "Do not introduce synthetic beauty rendering, anatomy distortion, or reference-channel drift.",
            ],
            "identity_reinforcement": [],
        }
        return HumanPhotorealismGuidance(
            guidance_id=guidance_id,
            project_id=project_id,
            job_id=job_id,
            applies=True,
            subject_type=subject_type,
            realism_level=realism_level,
            variation_mode=variation_mode,
            semantic_contract=self._semantic_contract(
                activation=activation,
                human_subject_kind="hand_or_skin_detail",
                review_targets=review_targets,
            ),
            positive_prompt_fragments=[] if brain_owned_forward_execution else _dedupe(positives),
            negative_prompt_fragments=[] if brain_owned_forward_execution else _dedupe(negatives),
            reference_preserve_rules=[],
            reference_do_not_inherit_rules=[] if brain_owned_forward_execution else do_not_inherit,
            review_targets=review_targets,
            retry_patch_templates={} if brain_owned_forward_execution else retry_patch_templates,
            user_visible_summary=[
                "Adds real-camera hand and skin detail",
                "Checks finger anatomy and physical object contact",
            ],
            metadata={
                "doc": "128",
                "module_id": self.module_id,
                "enable_reason": "hand_or_skin_detail_detected",
                "doc91_human_realism_plugin": True,
                "doc128_shared_constraint_contract": True,
                "human_detail_scope": "hand_or_skin_only",
                HUMAN_REALISM_PLUGIN_METADATA_KEY: activation,
                "universal_rendering_profile": rendering_profile,
                "has_identity_reference": False,
                "brain_owned_forward_execution": brain_owned_forward_execution,
            },
        )

    @staticmethod
    def _semantic_contract(
        *,
        activation: dict[str, Any],
        human_subject_kind: str,
        review_targets: list[str],
    ) -> dict[str, Any]:
        """Return typed Human Realism obligations, never Provider prose.

        The contract deliberately uses a small closed vocabulary.  The remote
        Brain decides how to honour it in the complete canonical image prompt;
        deterministic code must not translate it into a local word stack.
        """

        is_detail = human_subject_kind == "hand_or_skin_detail"
        return {
            "contract_version": "v3_human_realism_semantic_v1",
            "capability_id": "human_realism",
            "rendering_goal": "photographic_human_detail" if is_detail else "photographic_real_person",
            "quality_axes": list(dict.fromkeys(str(item) for item in review_targets if str(item))),
            "identity_age_fidelity": "explicit_or_reference_backed" if not is_detail else "not_applicable",
            "physical_coherence": "required",
            "reference_boundary": "resolved_channels_only",
            "ordinary_age_appropriate_context": bool(activation.get("safety_sensitive_person")),
            "creative_direction_owner": "remote_v3_llm_brain",
            "provider_prompt_owner": "remote_v3_llm_brain",
        }

    def review(
        self,
        *,
        guidance: HumanPhotorealismGuidance,
        project_id: str | None,
        job_id: str | None,
        issue_codes: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AntiAIFaceReviewResult:
        issue_codes = _dedupe(
            normalize_human_realism_issue_code(code)
            for code in issue_codes or []
            if self.is_human_realism_issue_code(code)
        )
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
        plugin_metadata = dict(guidance.metadata.get(HUMAN_REALISM_PLUGIN_METADATA_KEY) or {})
        hand_detail = plugin_metadata.get("human_subject_kind") == "hand_or_skin_detail"
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
                (
                    ["Hand and skin realism needs one cleaner retry", "V3 prepared anatomy and grip guidance"]
                    if hand_detail
                    else ["Face realism needs one cleaner retry", "V3 prepared more natural skin and expression guidance"]
                )
                if issue_codes
                else ["Hand and skin realism will be checked after generation"] if hand_detail else ["Face realism will be checked after generation"]
            ),
            metadata={"doc": "65", **dict(metadata or {})},
        )

    @classmethod
    def is_human_realism_issue_code(cls, issue_code: str) -> bool:
        normalized = str(issue_code or "").strip()
        return normalized in _ANTI_AI_FACE_ISSUES or normalize_human_realism_issue_code(normalized) in HUMAN_REALISM_REVIEW_DIMENSIONS

    def retry_patch_for_issue_codes(
        self,
        issue_codes: list[str],
        *,
        child_model: bool = False,
    ) -> dict[str, list[str]]:
        # ``child_model`` is read-only compatibility for older callers.  It
        # must not select a child-specific retry path or contribute wording.
        del child_model
        normalized = _dedupe(
            normalize_human_realism_issue_code(code)
            for code in issue_codes
            if self.is_human_realism_issue_code(code)
        )
        if not normalized:
            return {}
        return {
            "prompt_additions": [
                "Repair photographic human naturalness and physical coherence without changing user-owned creative direction.",
            ],
            "negative_additions": [
                "Do not introduce synthetic beauty rendering, anatomy distortion, or reference-channel drift.",
            ],
            "review_dimensions": normalized,
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
        text = _combined_activation_text(
            user_input=user_input,
            scenario_id=scenario_id,
            template_id=template_id,
            subject_type=subject_type,
            metadata=metadata,
        )
        safety_sensitive_person = _is_safety_sensitive_person(text) or _truthy(
            metadata.get("safety_sensitive_person")
        )
        # Enforced V3 jobs arrive here only after the remote Brain has decided
        # whether a style term applies to the whole image or merely to an
        # object surface.  Do not run the legacy keyword classifier again:
        # doing so made a cartoon graphic on a child's dress disable the
        # shared real-person capability for an otherwise photographic image.
        if _truthy(metadata.get("human_realism_execution_required")):
            if _frozen_rendering_intent_is_whole_image_stylized(metadata):
                return _activation_payload(
                    applies=False,
                    primary_reason="frozen_rendering_intent_conflict",
                    disabled_reason="frozen_rendering_intent_conflict",
                    disabled_by_style=True,
                    subject_type=subject_type,
                    evidence={"frozen_rendering_intent": dict(metadata.get("frozen_rendering_intent") or {})},
                )
            forced_kind = str(metadata.get("human_subject_kind") or "person")
            rendering_profile = _universal_rendering_profile("", metadata=metadata)
            return _activation_payload(
                applies=True,
                primary_reason="frozen_human_realism_execution",
                reason_codes=["frozen_human_realism_execution"],
                subject_type=subject_type,
                human_subject_kind=forced_kind,
                strictness=str(metadata.get("human_realism_strictness") or "commercial_strict"),
                style_profile=str(metadata.get("human_realism_style_profile") or rendering_profile["profile_id"]),
                universal_rendering_profile=rendering_profile,
                evidence={"frozen_rendering_intent": dict(metadata.get("frozen_rendering_intent") or {})},
                safety_sensitive_person=safety_sensitive_person,
            )
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
                safety_sensitive_person=safety_sensitive_person,
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
        if _people_explicitly_excluded(text):
            return _activation_payload(
                applies=False,
                primary_reason="no_visible_person_evidence",
                disabled_reason="no_visible_person_evidence",
                disabled_by_style=False,
                subject_type=subject_type,
                evidence={"explicit_person_exclusion": True},
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
        if "product_with_human_signal" in reason_codes:
            reason_codes.append("product_on_person_detected")

        explicit_age_signal = _has_explicit_age_direction(text)
        is_hand_or_skin = _contains_any(text, _HAND_OR_SKIN_TERMS) or _contains_any(text, _CHINESE_HAND_OR_SKIN_TERMS)
        face_is_explicitly_excluded = _contains_any(
            text,
            {
                "no face",
                "without a face",
                "without face",
                "face out of frame",
                "no visible face",
                "不露脸",
                "无脸",
                "不出现脸",
            },
        )
        has_visible_face = (
            _contains_any(text, {"face", "portrait"}) or _contains_any(text, {"脸", "人像"})
        ) and not face_is_explicitly_excluded
        # A hand, finger, or skin-quality mention is often incidental in a
        # full-person request.  Detail-only guidance is appropriate only
        # when the request is genuinely about that crop.  This is deliberately
        # subject-generic: it does not introduce an age, apparel, or template
        # branch.
        has_full_person_context = (
            subject_type == "character"
            or _contains_any(
                text,
                _HUMAN_TERMS - {"hand holding", "holding the product", "skin detail", "face", "portrait"},
            )
            or _contains_any(text, _CHINESE_HUMAN_TERMS - _CHINESE_HAND_OR_SKIN_TERMS)
        )
        if is_hand_or_skin and not has_visible_face and not has_full_person_context:
            human_subject_kind = "hand_or_skin_detail"
            strictness = "balanced"
            reason_codes.append("hand_or_skin_detail_detected")
        elif any(token in reason_codes for token in ["product_with_human_signal", "product_on_person_detected"]):
            human_subject_kind = "product_on_person"
            strictness = "commercial_strict"
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
        evidence["safety_sensitive_person"] = safety_sensitive_person
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
            safety_sensitive_person=safety_sensitive_person,
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
        return [
            "when multiple people are rendered, make the set feel like a directed real photoshoot with distinct but coherent shutter moments in expression, gaze, head angle, and body orientation; do not repeat one centered front-facing presentation pose"
        ]


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


def _people_explicitly_excluded(text: str) -> bool:
    """Respect an explicit flat-lay/no-person request before activation.

    This is evidence admission, not a classifier: it only recognises a direct
    instruction that people are absent.  A garment's audience alone can never
    create a Human Realism execution requirement.
    """

    normalized = str(text or "").lower()
    return any(
        phrase in normalized
        for phrase in (
            "no people",
            "no person",
            "without people",
            "without a person",
            "without any person",
            "no human",
            "without humans",
            "无人",
            "没有人",
            "不含人物",
        )
    )


def _has_explicit_age_direction(text: str) -> bool:
    """Recognize explicit age declarations without inferring age from appearance."""

    if _contains_any(text, _EXPLICIT_AGE_TERMS) or _contains_any(text, _CHINESE_EXPLICIT_AGE_TERMS):
        return True
    normalized = str(text or "").lower()
    return bool(
        re.search(r"\b(?:age|aged)\s*\d{1,2}\b", normalized)
        or re.search(r"\b\d{1,2}\s*(?:-| )?year(?:s)?[- ]old\b", normalized)
        or re.search(r"(?:\d{1,2}|[一二三四五六七八九十]{1,3})\s*岁", normalized)
    )


def _is_safety_sensitive_person(text: str) -> bool:
    """Recognize an explicitly young person without inferring age from appearance.

    This is a narrow, shared Human Realism auxiliary signal.  It controls only
    framework-owned Provider wording; it neither rewrites a user's request nor
    creates a template, deliverable, or Provider route for children.
    """

    if _contains_any(text, _CHILD_TERMS) or _contains_any(text, _CHINESE_CHILD_TERMS):
        return True
    normalized = str(text or "").lower()
    matches = re.findall(r"\b(?:age|aged)\s*(\d{1,2})\b|\b(\d{1,2})\s*(?:-| )?year(?:s)?[- ]old\b", normalized)
    if any(0 <= int(first or second) < 18 for first, second in matches):
        return True
    return bool(re.search(r"\b\d{1,2}\s*\u5c81", normalized))


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
            if _stylized_term_describes_object_detail(text, term, index):
                index = text.find(term, index + len(term))
                continue
            if not any(negation in prefix for negation in _NEGATION_TERMS):
                return True
            index = text.find(term, index + len(term))
    return False


def _frozen_rendering_intent_is_whole_image_stylized(metadata: dict[str, Any]) -> bool:
    """Read only a Brain-frozen decision; never infer it from prompt tokens."""

    intent = metadata.get("frozen_rendering_intent")
    if not isinstance(intent, dict):
        return False
    return (
        str(intent.get("stylization_scope") or "") == "whole_image"
        and str(intent.get("rendering_mode") or "") in {"stylized", "mixed"}
    )


def _stylized_term_describes_object_detail(text: str, term: str, index: int) -> bool:
    """Keep an object's artwork fact from changing the whole-image style.

    A word such as ``illustration`` is a style signal only when it directs the
    rendering of the image or subject.  In a reference-truth request it can
    also describe a product's visible print, motif, or placement.  Treating
    the latter as a style instruction would silently suppress shared Human
    Realism for an otherwise real-person photograph.
    """

    if term not in {"illustration", "illustrated", "插画", "插图", "漫画"}:
        return False
    window = text[max(0, index - 48) : index + len(term) + 72]
    return any(pattern.search(window) for pattern in _ILLUSTRATION_OBJECT_DETAIL_PATTERNS)


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
        "scene_photographic_coherence": str(
            explicit.get("scene_photographic_coherence")
            or metadata.get("scene_photographic_coherence")
            or "preserve_physical_light_depth_contact"
        ),
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
    safety_sensitive_person: bool = False,
) -> dict[str, Any]:
    if applies and human_subject_kind == "none":
        human_subject_kind = "person"
    if applies and strictness == "off":
        strictness = "balanced"
    review_codes = list(HUMAN_REALISM_REVIEW_DIMENSIONS) if applies else []
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
        "safety_sensitive_person": bool(safety_sensitive_person),
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
