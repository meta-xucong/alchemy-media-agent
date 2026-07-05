"""Human identity consistency balanced with natural professional variation."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import HumanIdentityAnchorProfile, HumanNaturalVariationPlan


HUMAN_KEYWORDS = (
    "person",
    "portrait",
    "model",
    "woman",
    "girl",
    "man",
    "boy",
    "face",
    "spokesperson",
    "character",
    "people",
    "\u7f8e\u5973",
    "\u4eba\u7269",
    "\u4eba\u50cf",
    "\u5199\u771f",
    "\u6a21\u7279",
    "\u5973\u5b69",
    "\u5973\u751f",
    "\u5973\u6027",
    "\u7537\u4eba",
    "\u7537\u6027",
    "\u8096\u50cf",
    "\u540c\u4e00\u4e2a\u4eba",
)

EXACT_COPY_KEYWORDS = (
    "same pose",
    "same expression",
    "same angle",
    "exact copy",
    "identical",
    "\u53ea\u6539\u80cc\u666f",
    "\u53ea\u6539\u5c3a\u5bf8",
    "\u5b8c\u5168\u4e00\u6837",
    "\u4e00\u6a21\u4e00\u6837",
    "\u540c\u4e00\u59ff\u52bf",
    "\u540c\u4e00\u8868\u60c5",
    "\u540c\u4e00\u89d2\u5ea6",
)

MODE_DIVERSITY = {
    "selection_candidates": ("strong", "subtle"),
    "delivery_suite": ("strong", "medium"),
    "creative_exploration": ("medium", "broad"),
    "format_layout_adaptation": ("strong", "subtle"),
}


class HumanNaturalVariationPolicy:
    """Build Doc56 prompt guidance for human-led multi-image jobs."""

    def build(
        self,
        *,
        user_input: str,
        project_id: str | None,
        job_id: str | None,
        requested_image_count: int,
        variation_mode: str | None,
        selected_outputs: list[dict[str, Any]] | None = None,
        selected_references: list[dict[str, Any]] | None = None,
        uploaded_references: list[dict[str, Any]] | None = None,
        identity_lock_profiles: list[dict[str, Any]] | None = None,
    ) -> tuple[HumanIdentityAnchorProfile, HumanNaturalVariationPlan]:
        selected_outputs = list(selected_outputs or [])
        selected_references = list(selected_references or [])
        uploaded_references = list(uploaded_references or [])
        identity_lock_profiles = list(identity_lock_profiles or [])
        text = str(user_input or "")
        is_human = self._is_human_led(text, selected_references, uploaded_references, identity_lock_profiles)
        exact_copy = self._has_exact_copy_request(text)
        mode = self._normalize_mode(variation_mode)
        has_reference = bool(selected_outputs or selected_references or uploaded_references or identity_lock_profiles)
        applies = bool(is_human and requested_image_count >= 2)
        identity_strength, diversity_strength = MODE_DIVERSITY.get(mode, MODE_DIVERSITY["delivery_suite"])
        if not has_reference and identity_strength == "strong":
            identity_strength = "medium"
        if exact_copy:
            diversity_strength = "minimal"

        anchor = HumanIdentityAnchorProfile(
            applies=applies,
            confidence="high" if has_reference and applies else "medium" if applies else "low",
            anchor_source=self._anchor_source(selected_outputs, selected_references, uploaded_references, identity_lock_profiles),
            stable_identity_traits=[
                "same recognizable person direction",
                "consistent face shape and facial feature relationships",
                "consistent age band, skin tone direction, and overall model presence",
            ]
            if applies
            else [],
            stable_body_traits=[
                "consistent body type and body proportions",
                "plausible same-model height and build direction",
            ]
            if applies
            else [],
            stable_style_traits=[
                "same professional visual world",
                "consistent lighting and palette language",
                "same broad styling category",
            ]
            if applies
            else [],
            locked_traits=[
                "recognizable identity direction",
                "body type and proportions",
                "major hair color and broad length range",
                "major wardrobe category when relevant",
            ]
            if applies
            else [],
            flexible_traits=self._variation_axes(mode, exact_copy) if applies else [],
            forbidden_drift=[
                "face swap",
                "age drift",
                "ethnicity or person identity drift",
                "large body type change",
                "major hair color or length change unless requested",
                "cloned stills across the whole batch",
            ]
            if applies
            else [],
            metadata={
                "has_reference": has_reference,
                "exact_copy_request": exact_copy,
                "requested_image_count": requested_image_count,
                "variation_mode": mode,
            },
        )
        plan = HumanNaturalVariationPlan(
            applies=applies,
            variation_mode=mode,
            identity_strength=identity_strength,
            diversity_strength=diversity_strength,
            per_image_variation_axes=self._variation_axes(mode, exact_copy) if applies else [],
            prompt_additions=self._prompt_additions(mode, has_reference, exact_copy) if applies else [],
            negative_additions=self._negative_additions(exact_copy) if applies else [],
            batch_review_rules=self._batch_review_rules(mode, exact_copy) if applies else [],
            user_visible_summary=[
                "已保持人物相貌和身材方向一致",
                "已让表情、动作、角度和构图自然变化",
                "会避免整组图片像同一张定格复制",
            ]
            if applies and not exact_copy
            else ["已按你的要求降低人物变化幅度"] if applies else [],
            metadata={
                "policy_id": stable_id("human_natural_variation", project_id, job_id, text, mode, requested_image_count),
                "has_reference": has_reference,
                "exact_copy_request": exact_copy,
                "doc": "56",
            },
        )
        return anchor, plan

    def _is_human_led(
        self,
        text: str,
        selected_references: list[dict[str, Any]],
        uploaded_references: list[dict[str, Any]],
        identity_lock_profiles: list[dict[str, Any]],
    ) -> bool:
        lowered = text.lower()
        if any(keyword in lowered or keyword in text for keyword in HUMAN_KEYWORDS):
            return True
        for profile in identity_lock_profiles:
            if str(profile.get("subject_type") or "").lower() in {"character", "person", "portrait", "human"}:
                return True
        for item in [*selected_references, *uploaded_references]:
            role = str(item.get("role") or item.get("asset_role") or item.get("use_policy") or "").lower()
            if any(token in role for token in ["face", "identity", "portrait", "person", "human", "character"]):
                return True
        return False

    def _has_exact_copy_request(self, text: str) -> bool:
        lowered = text.lower()
        return any(keyword in lowered or keyword in text for keyword in EXACT_COPY_KEYWORDS)

    def _normalize_mode(self, mode: str | None) -> str:
        value = str(mode or "").strip()
        if value == "auto":
            return "delivery_suite"
        if value in MODE_DIVERSITY:
            return value
        return "delivery_suite"

    def _anchor_source(
        self,
        selected_outputs: list[dict[str, Any]],
        selected_references: list[dict[str, Any]],
        uploaded_references: list[dict[str, Any]],
        identity_lock_profiles: list[dict[str, Any]],
    ) -> str | None:
        if selected_outputs:
            return "selected_output"
        if selected_references:
            return "selected_reference"
        if uploaded_references:
            return "uploaded_reference"
        if identity_lock_profiles:
            return "identity_lock_profile"
        return "prompt_only"

    def _variation_axes(self, mode: str, exact_copy: bool) -> list[str]:
        if exact_copy:
            return ["crop", "format", "minor lighting polish"]
        if mode == "format_layout_adaptation":
            return ["crop", "camera distance", "negative space", "subject scale", "layout balance"]
        if mode == "creative_exploration":
            return ["expression", "gaze", "pose", "head angle", "scene mood", "camera language", "styling idea"]
        if mode == "selection_candidates":
            return ["expression", "gaze", "pose", "head angle", "hand placement", "crop", "camera distance"]
        return ["expression", "gaze", "pose", "body turn", "head angle", "camera distance", "framing", "small hair movement"]

    def _prompt_additions(self, mode: str, has_reference: bool, exact_copy: bool) -> list[str]:
        if exact_copy:
            return [
                "Follow the user's exact-copy instruction while preserving the same recognizable person and body type.",
                "Only vary the specifically requested non-identity details.",
            ]
        additions = [
            "Keep the same recognizable person and body type across the set.",
            "Allow natural professional variation in expression, gaze, pose, head angle, camera angle, crop, and small hair styling details.",
            "Each image should feel like a different frame from the same professional shoot, not a duplicate of the same still.",
            "Preserve broad hair color and length direction while allowing natural movement, parting, volume, or shoot-day styling variation.",
        ]
        if has_reference:
            additions.append(
                "Use the reference as an identity and style anchor, not as an instruction to copy the exact same expression, pose, head angle, or crop."
            )
        if mode == "selection_candidates":
            additions.append("Create close alternatives with small but visible differences so the user can pick the best frame.")
        elif mode == "delivery_suite":
            additions.append("Create useful role variety across the same shoot: hero, lifestyle moment, crop, and framing variation.")
        elif mode == "creative_exploration":
            additions.append("Explore broader creative direction while keeping the person recognizable.")
        elif mode == "format_layout_adaptation":
            additions.append("Prioritize layout, crop, and negative-space variation while keeping the person consistent.")
        return additions

    def _negative_additions(self, exact_copy: bool) -> list[str]:
        values = [
            "identity drift",
            "face swap",
            "major body-shape drift",
            "major hair color or length drift unless requested",
        ]
        if not exact_copy:
            values.extend(
                [
                    "same exact expression in every image",
                    "same exact head angle in every image",
                    "same exact pose in every image",
                    "cloned stills",
                    "mannequin-like repeated face",
                ]
            )
        return values

    def _batch_review_rules(self, mode: str, exact_copy: bool) -> list[str]:
        if exact_copy:
            return ["respect exact-copy user instruction", "check identity drift without forcing variation"]
        return [
            "at least two outputs differ in expression or gaze",
            "at least two outputs differ in pose or body/head angle",
            "at least two outputs differ in crop, camera distance, or framing",
            "batch should not repeat the exact same expression, head angle, and pose across most images",
            f"variation budget follows {mode}",
        ]
