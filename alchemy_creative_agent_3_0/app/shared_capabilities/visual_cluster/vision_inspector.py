"""Post-generation visual inspection helpers for Doc55."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...creative_core.rules import stable_id
from .contracts import GeneratedOutputResolution, VisualInspectionReport
from .vision_provider import (
    VisionInspectionProvider,
    VisionInspectionProviderError,
    VisionInspectionProviderUnavailable,
    create_default_vision_provider,
)


_WATERMARK_OR_TEXT_ISSUES = {
    "visible_text_artifact",
    "watermark_or_signature",
    "faint_corner_watermark",
    "ai_generated_badge_trace",
    "signature_like_artifact",
    "lower_right_mark_artifact",
    "third_party_aigc_metadata",
    "provider_provenance_mismatch",
}

_AESTHETIC_STABILITY_ISSUES = {
    "weak_aesthetic_finish",
    "generic_stock_photo_finish",
    "flat_low_contrast_finish",
    "overexposed_washout",
    "underexposed_muddy_frame",
    "unbalanced_color_grade",
    "weak_subject_readability",
    "weak_depth_and_material_separation",
    "unstable_composition_balance",
    "overprocessed_hdr_finish",
    "uncanny_micro_detail",
    "low_resolution_output",
}

_BEAUTIFUL_REALISM_ISSUES = {
    "identity_card_missing",
    "identity_card_not_applied",
    "identity_feature_drift",
    "eyebrow_shape_drift",
    "eye_shape_or_spacing_drift",
    "nose_mouth_relationship_drift",
    "jaw_chin_direction_drift",
    "unflattering_feature_degradation",
    "beautiful_realism_balance_failure",
    "realism_made_subject_less_attractive",
    "pretty_but_too_ai_filtered",
    "real_but_unflattering",
    "skin_texture_beauty_balance_failure",
}

_DOC86_PORTRAIT_IDENTITY_ISSUES = {
    "bone_structure_drift",
    "face_shape_drift",
    "cheek_jaw_chin_drift",
    "eye_shape_or_spacing_identity_drift",
    "eyebrow_eye_relationship_drift",
    "nose_mouth_relationship_identity_drift",
    "lip_contour_identity_drift",
    "age_impression_drift",
    "styling_changed_face_geometry",
    "archetype_overrode_reference_identity",
    "same_type_not_same_person",
    "identity_reference_underweighted",
}

_DOC87_REFERENCE_BOUNDARY_ISSUES = {
    "source_lighting_overinherited",
    "source_color_temperature_overinherited",
    "source_scene_overinherited",
    "source_wardrobe_overinherited",
    "source_camera_mood_overinherited",
    "reference_used_as_style_when_identity_only",
    "prompt_style_underweighted",
    "makeup_changed_face_geometry",
    "hair_change_replaced_identity",
    "retry_repaired_artifact_but_changed_identity",
}

_DOC88_REFERENCE_BALANCE_ISSUES = {
    "prompt_mood_regression",
    "prompt_color_tone_regression",
    "approved_style_anchor_ignored",
    "identity_repair_damaged_prompt_direction",
    "overconstrained_identity_prompt",
    "scenario_specific_negative_overfit",
}

RETRYABLE_ISSUE_CODES = {
    *_AESTHETIC_STABILITY_ISSUES,
    *_BEAUTIFUL_REALISM_ISSUES,
    *_DOC86_PORTRAIT_IDENTITY_ISSUES,
    *_DOC87_REFERENCE_BOUNDARY_ISSUES,
    *_DOC88_REFERENCE_BALANCE_ISSUES,
    "visible_text_artifact",
    "watermark_or_signature",
    "faint_corner_watermark",
    "ai_generated_badge_trace",
    "signature_like_artifact",
    "lower_right_mark_artifact",
    "third_party_aigc_metadata",
    "provider_provenance_mismatch",
    "commercial_cleanliness_failure",
    "collage_or_split_panel",
    "identity_drift",
    "hair_or_outfit_drift",
    "camera_distance_drift",
    "lighting_mismatch",
    "composition_mismatch",
    "unrelated_object",
    "unrelated_product",
    "product_identity_drift",
    "product_label_drift",
    "product_label_unreadable",
    "product_logo_or_label_obscured",
    "brand_asset_drift",
    "ecommerce_slot_mismatch",
    "ecommerce_suite_role_mismatch",
    "bad_hands_or_body",
    "face_artifact",
    "ai_face_render",
    "plastic_skin",
    "over_smoothed_skin",
    "missing_skin_texture",
    "over_retouching",
    "poreless_beauty_surface",
    "synthetic_fashion_face",
    "weak_photographic_imperfection",
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
    "same_expression_repetition",
    "same_head_angle_repetition",
    "same_pose_repetition",
    "studio_only_when_lifestyle_requested",
    "role_collapse",
    "flat_catalog_lighting",
    "weak_lifestyle_context",
    "repeated_concept_or_prop",
    "reference_guard_ignored",
    "low_commercial_finish",
}

FINAL_ISSUE_CODES = {
    "policy_or_safety_block",
    "severe_face_artifact",
    "severe_body_artifact",
}

MANUAL_REVIEW_ISSUE_CODES = {
    "file_missing",
    "file_unreadable",
    "vision_provider_unavailable",
    "low_confidence_review",
    "provider_error",
}


class VisionOutputInspector:
    """Inspect resolved generated outputs without owning provider execution."""

    def __init__(
        self,
        *,
        vision_provider: VisionInspectionProvider | None = None,
        min_confidence: float = 0.65,
    ) -> None:
        self.vision_provider = vision_provider
        self.min_confidence = max(0.0, min(1.0, min_confidence))

    def inspect(
        self,
        resolution: GeneratedOutputResolution,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> VisualInspectionReport:
        metadata = dict(metadata or {})
        fake_codes = _string_list(metadata.get("post_generation_fake_issue_codes"))
        fake_confidence = _safe_float(metadata.get("post_generation_fake_confidence"), default=0.9)
        if fake_codes:
            return self._fake_report(resolution, fake_codes, fake_confidence, metadata)
        if resolution.status != "ready":
            return self._manual_report(resolution, resolution.status, metadata)
        mode = self._inspection_mode(metadata)
        if mode in {"vision_model", "hybrid"}:
            return self._vision_model_report(resolution, mode=mode, metadata=metadata)
        if mode == "metadata_only":
            return self._metadata_report(resolution, metadata)
        return self._local_report(resolution, metadata)

    def _inspection_mode(self, metadata: dict[str, Any]) -> str:
        raw_mode = str(
            metadata.get("vision_inspection_mode")
            or metadata.get("post_generation_inspection_mode")
            or ""
        ).strip().lower()
        if _truthy(metadata.get("enable_real_vision_inspection")) and not raw_mode:
            raw_mode = "hybrid"
        if raw_mode in {"metadata_only", "local_image_heuristic", "vision_model", "hybrid"}:
            return raw_mode
        provider = self._provider()
        if provider is not None and provider.available(force=False):
            return "hybrid"
        return "local_image_heuristic"

    def _provider(self) -> VisionInspectionProvider | None:
        if self.vision_provider is None:
            self.vision_provider = create_default_vision_provider()
        return self.vision_provider

    def _vision_model_report(
        self,
        resolution: GeneratedOutputResolution,
        *,
        mode: str,
        metadata: dict[str, Any],
    ) -> VisualInspectionReport:
        provider = self._provider()
        if provider is None or not provider.available(force=True):
            return self._manual_report(resolution, "vision_provider_unavailable", metadata, mode=mode)
        try:
            payload = provider.inspect(resolution, metadata=metadata)
        except VisionInspectionProviderUnavailable:
            return self._manual_report(resolution, "vision_provider_unavailable", metadata, mode=mode)
        except VisionInspectionProviderError as exc:
            return self._manual_report(
                resolution,
                "provider_error",
                metadata,
                mode=mode,
                evidence_extra={"provider_error": str(exc)[:240]},
            )
        return self._from_provider_payload(
            resolution,
            payload,
            mode=mode,
            provider_name=getattr(provider, "provider_name", "vision_provider"),
            metadata=metadata,
        )

    def _from_provider_payload(
        self,
        resolution: GeneratedOutputResolution,
        payload: dict[str, Any],
        *,
        mode: str,
        provider_name: str,
        metadata: dict[str, Any],
    ) -> VisualInspectionReport:
        issue_codes = _provider_issue_codes(payload)
        confidence = _safe_float(payload.get("confidence"), default=0.5)
        if confidence < self.min_confidence:
            issue_codes = _dedupe([*issue_codes, "low_confidence_review"])
            status = "manual_review"
            retryable = False
        else:
            status = _status_from_issues(issue_codes, str(payload.get("status") or ""))
            retryable = status == "fail_retryable"
        retry_patch = _merge_retry_patches(_retry_patch_for_issues(issue_codes), payload.get("retry_patch") if retryable else {})
        detected_issues = [_issue_payload(code, confidence) for code in issue_codes]
        score_card = _provider_score_card(payload.get("scores"), status)
        user_summary = _string_list(payload.get("summary")) or _summary_for_status(status, issue_codes)
        return VisualInspectionReport(
            inspection_id=stable_id("visual_inspection", resolution.job_id, resolution.candidate_id, resolution.output_id, mode, ",".join(issue_codes)),
            project_id=resolution.project_id,
            job_id=resolution.job_id,
            candidate_id=resolution.candidate_id,
            asset_id=resolution.asset_id,
            output_id=resolution.output_id,
            mode=mode,
            status=status,
            confidence=confidence,
            score_card=score_card,
            detected_issues=detected_issues,
            preserved_elements=_string_list(payload.get("preserved_elements")),
            drift_warnings=_string_list(payload.get("drift_warnings")),
            artifact_warnings=_string_list(payload.get("artifact_warnings")),
            retryable=retryable,
            retry_patch=retry_patch if retryable else {},
            evidence={
                "resolution_status": resolution.status,
                "file_path": resolution.file_path,
                "provider_name": provider_name,
                "provider_status": payload.get("status"),
                "provider_issue_codes": issue_codes,
            },
            user_visible_summary=user_summary[:4],
            metadata={"doc": "55", "vision_provider": provider_name, **_public_metadata(metadata)},
        )

    def _metadata_report(
        self,
        resolution: GeneratedOutputResolution,
        metadata: dict[str, Any],
    ) -> VisualInspectionReport:
        return VisualInspectionReport(
            inspection_id=stable_id("visual_inspection", resolution.job_id, resolution.candidate_id, resolution.output_id, "metadata"),
            project_id=resolution.project_id,
            job_id=resolution.job_id,
            candidate_id=resolution.candidate_id,
            asset_id=resolution.asset_id,
            output_id=resolution.output_id,
            mode="metadata_only",
            status="pass",
            confidence=0.55,
            score_card=_score_card("pass"),
            detected_issues=[],
            preserved_elements=["generated output metadata"],
            retryable=False,
            evidence={"resolution_status": resolution.status, "file_path": resolution.file_path},
            user_visible_summary=["V3 confirmed the generated image record is usable."],
            metadata={"doc": "55", **_public_metadata(metadata)},
        )

    def _local_report(
        self,
        resolution: GeneratedOutputResolution,
        metadata: dict[str, Any],
    ) -> VisualInspectionReport:
        warnings = list(resolution.warnings)
        evidence: dict[str, Any] = {
            "resolution_status": resolution.status,
            "width": resolution.width,
            "height": resolution.height,
            "file_path": resolution.file_path,
        }
        if resolution.file_path and not Path(resolution.file_path).exists():
            return self._manual_report(resolution, "file_unreadable", metadata)
        opened_width = resolution.width
        opened_height = resolution.height
        local_image_issue_codes: list[str] = []
        local_image_evidence: dict[str, Any] = {}
        if resolution.file_path:
            try:
                from PIL import Image

                with Image.open(resolution.file_path) as image:
                    opened_width, opened_height = image.size
                    image.verify()
                if _truthy(metadata.get("enable_local_aesthetic_heuristics")):
                    with Image.open(resolution.file_path) as image:
                        local_image_issue_codes, local_image_evidence = _local_image_quality_issue_codes(
                            image,
                            opened_width,
                            opened_height,
                        )
            except Exception:
                return self._manual_report(resolution, "file_unreadable", metadata)
        issue_codes, local_evidence = self._local_file_issue_codes(resolution)
        issue_codes = _dedupe([*issue_codes, *local_image_issue_codes])
        local_evidence = {**local_evidence, **local_image_evidence}
        if issue_codes:
            retry_patch = _retry_patch_for_issues(issue_codes)
            detected_issues = [_issue_payload(code, 0.9) for code in issue_codes]
            return VisualInspectionReport(
                inspection_id=stable_id(
                    "visual_inspection",
                    resolution.job_id,
                    resolution.candidate_id,
                    resolution.output_id,
                    "local",
                    ",".join(issue_codes),
                ),
                project_id=resolution.project_id,
                job_id=resolution.job_id,
                candidate_id=resolution.candidate_id,
                asset_id=resolution.asset_id,
                output_id=resolution.output_id,
                mode="local_image_heuristic",
                status="fail_retryable",
                confidence=0.9,
                score_card=_score_card("fail_retryable"),
                detected_issues=detected_issues,
                preserved_elements=["generated output file"],
                artifact_warnings=[
                    issue["message"]
                    for issue in detected_issues
                    if issue["code"] in _WATERMARK_OR_TEXT_ISSUES
                ],
                retryable=True,
                retry_patch=retry_patch,
                evidence={**evidence, **local_evidence},
                user_visible_summary=_summary_for_status("fail_retryable", issue_codes),
                metadata={"doc": "55", "warnings": warnings, **_public_metadata(metadata)},
            )
        evidence["width"] = opened_width
        evidence["height"] = opened_height
        score_card = {
            "file_readiness": 1.0,
            "artifact_safety": 0.86,
            "composition": 0.78,
            "commercial_finish": 0.78,
            "overall": 0.82,
        }
        summary = ["V3 checked the generated image file.", "No clear issue needs automatic retry."]
        return VisualInspectionReport(
            inspection_id=stable_id("visual_inspection", resolution.job_id, resolution.candidate_id, resolution.output_id, "local"),
            project_id=resolution.project_id,
            job_id=resolution.job_id,
            candidate_id=resolution.candidate_id,
            asset_id=resolution.asset_id,
            output_id=resolution.output_id,
            mode="local_image_heuristic",
            status="pass" if not warnings else "warning",
            confidence=0.72,
            score_card=score_card,
            detected_issues=[],
            preserved_elements=["generated output file"],
            artifact_warnings=[],
            retryable=False,
            evidence=evidence,
            user_visible_summary=summary,
            metadata={"doc": "55", "warnings": warnings, **_public_metadata(metadata)},
        )

    def _local_file_issue_codes(
        self,
        resolution: GeneratedOutputResolution,
    ) -> tuple[list[str], dict[str, Any]]:
        if not resolution.file_path:
            return [], {}
        path = Path(resolution.file_path)
        if not path.exists() or not path.is_file():
            return [], {}
        try:
            data = path.read_bytes()
        except OSError:
            return [], {}
        lower = data.lower()
        has_openai_c2pa = b"cabx" in lower and b"openai" in lower and b"c2pa" in lower
        has_aigc_metadata = b'"aigc"' in lower or b"'aigc'" in lower or (b"aigc" in lower and b"tc260pg" in lower)
        expected_openai = _is_openai_gpt_image_output(resolution)
        issue_codes: list[str] = []
        if has_aigc_metadata:
            issue_codes.append("third_party_aigc_metadata")
            issue_codes.append("ai_generated_badge_trace")
        if expected_openai and has_aigc_metadata and not has_openai_c2pa:
            issue_codes.append("provider_provenance_mismatch")
        lower_right_mark, mark_evidence = _lower_right_mark_risk(path)
        if lower_right_mark:
            issue_codes.append("lower_right_mark_artifact")
            issue_codes.append("ai_generated_badge_trace")
        return _dedupe(issue_codes), {
            "provider": resolution.provider,
            "model": resolution.model,
            "expected_openai_gpt_image": expected_openai,
            "has_openai_c2pa_signal": has_openai_c2pa,
            "has_aigc_metadata": has_aigc_metadata,
            **mark_evidence,
        }

    def _fake_report(
        self,
        resolution: GeneratedOutputResolution,
        issue_codes: list[str],
        confidence: float,
        metadata: dict[str, Any],
    ) -> VisualInspectionReport:
        detected_issues = [_issue_payload(code, confidence) for code in issue_codes]
        if confidence < 0.65:
            status = "manual_review"
            retryable = False
            detected_issues.append(_issue_payload("low_confidence_review", confidence, retryable=False))
        elif any(code in MANUAL_REVIEW_ISSUE_CODES for code in issue_codes):
            status = "manual_review"
            retryable = False
        elif any(code in FINAL_ISSUE_CODES for code in issue_codes):
            status = "fail_final"
            retryable = False
        elif any(code in RETRYABLE_ISSUE_CODES for code in issue_codes):
            status = "fail_retryable"
            retryable = True
        else:
            status = "warning"
            retryable = False
        retry_patch = _retry_patch_for_issues(issue_codes) if retryable else {}
        return VisualInspectionReport(
            inspection_id=stable_id("visual_inspection", resolution.job_id, resolution.candidate_id, resolution.output_id, "fake", ",".join(issue_codes)),
            project_id=resolution.project_id,
            job_id=resolution.job_id,
            candidate_id=resolution.candidate_id,
            asset_id=resolution.asset_id,
            output_id=resolution.output_id,
            mode="fake_for_tests",
            status=status,
            confidence=confidence,
            score_card=_score_card(status),
            detected_issues=detected_issues,
            artifact_warnings=[
                issue["message"]
                for issue in detected_issues
                if issue["code"] in _WATERMARK_OR_TEXT_ISSUES
            ],
            retryable=retryable,
            retry_patch=retry_patch,
            evidence={"fake_issue_codes": issue_codes, "resolution_status": resolution.status},
            user_visible_summary=_summary_for_status(status, issue_codes),
            metadata={"doc": "55", "fake_for_tests": True, **_public_metadata(metadata)},
        )

    def _manual_report(
        self,
        resolution: GeneratedOutputResolution,
        reason_code: str,
        metadata: dict[str, Any],
        *,
        mode: str = "metadata_only",
        evidence_extra: dict[str, Any] | None = None,
    ) -> VisualInspectionReport:
        issue = _issue_payload(reason_code if reason_code in MANUAL_REVIEW_ISSUE_CODES else "file_missing", 0.4, retryable=False)
        return VisualInspectionReport(
            inspection_id=stable_id("visual_inspection", resolution.job_id, resolution.candidate_id, resolution.output_id, reason_code),
            project_id=resolution.project_id,
            job_id=resolution.job_id,
            candidate_id=resolution.candidate_id,
            asset_id=resolution.asset_id,
            output_id=resolution.output_id,
            mode=mode,
            status="manual_review",
            confidence=0.35,
            score_card=_score_card("manual_review"),
            detected_issues=[issue],
            retryable=False,
            evidence={"resolution_status": resolution.status, "warnings": list(resolution.warnings), **dict(evidence_extra or {})},
            user_visible_summary=["This image needs manual confirmation before automatic retry."],
            metadata={"doc": "55", **_public_metadata(metadata)},
        )


def _local_image_quality_issue_codes(image: Any, width: int | None, height: int | None) -> tuple[list[str], dict[str, Any]]:
    issue_codes: list[str] = []
    evidence: dict[str, Any] = {
        "opened_width": width,
        "opened_height": height,
        "local_aesthetic_heuristic": "doc77_conservative_file_level",
    }
    if width and height and min(width, height) < 512:
        issue_codes.append("low_resolution_output")
    try:
        from PIL import ImageStat

        sample = image.convert("RGB")
        sample.thumbnail((256, 256))
        gray = sample.convert("L")
        stat = ImageStat.Stat(gray)
        mean_luma = float(stat.mean[0])
        contrast = float(stat.stddev[0])
        histogram = gray.histogram()
        total = float(sum(histogram) or 1.0)
        bright_ratio = sum(histogram[235:]) / total
        dark_ratio = sum(histogram[:25]) / total
        evidence.update(
            {
                "mean_luma": round(mean_luma, 2),
                "contrast_stddev": round(contrast, 2),
                "bright_pixel_ratio": round(bright_ratio, 4),
                "dark_pixel_ratio": round(dark_ratio, 4),
            }
        )
        if mean_luma > 230 and bright_ratio > 0.62 and contrast < 52:
            issue_codes.append("overexposed_washout")
        if mean_luma < 38 and dark_ratio > 0.55 and contrast < 50:
            issue_codes.append("underexposed_muddy_frame")
        if 70 < mean_luma < 210 and contrast < 11:
            issue_codes.append("flat_low_contrast_finish")
    except Exception as exc:  # pragma: no cover - defensive; file readability was already verified.
        evidence["local_quality_heuristic_error"] = str(exc)[:160]
    return _dedupe(issue_codes), evidence


def _issue_payload(code: str, confidence: float, retryable: bool | None = None) -> dict[str, Any]:
    is_retryable = code in RETRYABLE_ISSUE_CODES if retryable is None else retryable
    severity = "high" if code in FINAL_ISSUE_CODES else "medium" if is_retryable else "low"
    return {
        "code": code,
        "severity": severity,
        "retryable": is_retryable,
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "message": _issue_message(code),
    }


def _issue_message(code: str) -> str:
    messages = {
        "visible_text_artifact": "Possible visible generated text was detected.",
        "watermark_or_signature": "Possible watermark or signature risk was detected.",
        "faint_corner_watermark": "A faint corner watermark or mark may be visible.",
        "ai_generated_badge_trace": "A possible AI-generated badge or label trace was detected.",
        "signature_like_artifact": "A signature-like artifact may be visible.",
        "lower_right_mark_artifact": "A lower-right corner mark may be visible.",
        "third_party_aigc_metadata": "Third-party AIGC provenance metadata was detected in the generated file.",
        "provider_provenance_mismatch": "The generated file provenance does not match the requested image provider.",
        "commercial_cleanliness_failure": "The image may not be clean enough for direct commercial use.",
        "collage_or_split_panel": "The image may look like a collage or split-panel layout.",
        "identity_drift": "The subject may have drifted from the selected reference.",
        "hair_or_outfit_drift": "Hair or outfit direction may have drifted.",
        "composition_mismatch": "Composition may not match the intended direction.",
        "lighting_mismatch": "Lighting may not match the intended direction.",
        "unrelated_object": "An unrelated object may have appeared.",
        "unrelated_product": "An unrelated subject or object may have appeared.",
        "product_identity_drift": "A referenced subject or object may have drifted.",
        "product_label_drift": "The visible product label or logo may have changed from the reference.",
        "product_label_unreadable": "The visible product label or logo may be too unclear for a product image.",
        "product_logo_or_label_obscured": "The product label or logo may be covered, cropped, darkened, or hidden.",
        "brand_asset_drift": "A referenced brand or visual asset may have drifted.",
        "ecommerce_slot_mismatch": "The generated image may not match the requested ecommerce image role.",
        "ecommerce_suite_role_mismatch": "The product image set may not preserve the requested ecommerce role sequence.",
        "camera_distance_drift": "Camera distance may have drifted from the intended direction.",
        "bad_hands_or_body": "Body or hand details may need cleanup.",
        "face_artifact": "Face details may need cleanup.",
        "ai_face_render": "The face may look more generated than photographed.",
        "plastic_skin": "Skin may look too plastic or synthetic.",
        "over_smoothed_skin": "Skin texture may be over-smoothed.",
        "missing_skin_texture": "Natural pores and fine skin detail may be missing.",
        "over_retouching": "The image may look too retouched rather than naturally photographed.",
        "poreless_beauty_surface": "Skin may look too poreless or beauty-filtered.",
        "synthetic_fashion_face": "The face may look like a generic generated fashion portrait.",
        "weak_photographic_imperfection": "The photo may lack natural camera, skin, hair, fabric, or environment detail.",
        "synthetic_beauty_filter": "The face may look like a synthetic beauty filter.",
        "doll_like_face": "The face may look doll-like rather than photographed.",
        "template_smile": "The expression may feel template-like or repeated.",
        "over_perfect_symmetry": "The face may look unnaturally symmetrical.",
        "wax_skin_highlight": "Skin highlights may look waxy or unreal.",
        "uncanny_eye_expression": "The eyes or expression may feel uncanny.",
        "same_ai_face_repetition": "The set may repeat the same AI-beauty face too strongly.",
        "beauty_app_face": "The face may look like a beauty-app filter rather than a camera photo.",
        "idol_photocard_polish": "The portrait may look too much like a perfect photocard still.",
        "skin_blur_retouching": "Skin may look blurred by retouching instead of naturally textured.",
        "over_uniform_skin_tone": "Skin tone may look too uniform to feel photographed.",
        "over_sharp_ai_detail": "Details may look digitally over-sharpened or generated.",
        "perfect_smile_repetition": "The smile may feel too perfect or repeated across the set.",
        "face_slimming_filter": "The face may look reshaped by a beauty or slimming filter.",
        "beautified_facial_geometry": "Facial geometry may look overly beautified rather than naturally photographed.",
        "generic_ai_beauty_identity": "The person may look like a generic AI beauty identity instead of an individual.",
        "dull_complexion": "The complexion may look too dull for a fresh portrait.",
        "muddy_skin_tone": "Skin tone may look muddy or gray rather than clean and healthy.",
        "underexposed_face": "The face may be too dark or under-lit.",
        "harsh_facial_shadow": "Facial shadow may be too harsh or unflattering.",
        "overly_matte_documentary_look": "The portrait may look too matte or plain instead of fresh and flattering.",
        "tired_expression": "The expression may look too tired for the requested portrait.",
        "unflattering_color_cast": "The image may have an unflattering color cast on the skin.",
        "suppressed_fair_complexion": "The portrait may have suppressed the clean fair complexion expected by the brief.",
        "forced_tan_or_bronze_cast": "The skin may have been pushed toward an unrequested tan or bronze cast.",
        "gray_brown_skin_cast": "The skin may have a gray-brown cast instead of clean luminous color.",
        "head_body_proportion_distortion": "Head-to-body proportion may look distorted.",
        "oversized_head": "The head or face scale may look too large for the body.",
        "compressed_neck_shoulders": "The neck or shoulder line may look compressed by the crop.",
        "unflattering_face_drift": "The face may have drifted into a less flattering version of the intended person.",
        "same_expression_repetition": "The set may repeat the same expression too strongly.",
        "same_head_angle_repetition": "The set may repeat the same head angle too strongly.",
        "same_pose_repetition": "The set may repeat the same pose too strongly.",
        "studio_only_when_lifestyle_requested": "A lifestyle or context frame may still look like a studio packshot.",
        "role_collapse": "Different images in the set may be serving the same role.",
        "flat_catalog_lighting": "Lighting may feel too flat for the requested commercial scene.",
        "weak_lifestyle_context": "The image may need a more believable real-use context.",
        "repeated_concept_or_prop": "The set may repeat the same concept or prop too much.",
        "reference_guard_ignored": "The selected reference may not have been followed closely enough.",
        "low_commercial_finish": "The image may need a cleaner and more polished finish.",
        "identity_card_missing": "The project identity card may be missing from the generation guidance.",
        "identity_card_not_applied": "The selected identity card may not have been applied strongly enough.",
        "identity_feature_drift": "Identity-critical facial feature relationships may have drifted.",
        "eyebrow_shape_drift": "Eyebrow shape, thickness, or arc may have drifted into a less flattering design.",
        "eye_shape_or_spacing_drift": "Eye shape, spacing, or eyelid direction may have drifted.",
        "nose_mouth_relationship_drift": "The nose-mouth relationship may have drifted from the intended person.",
        "jaw_chin_direction_drift": "Jaw or chin direction may have drifted from the intended person.",
        "unflattering_feature_degradation": "Facial features may have become less attractive during realism tuning.",
        "beautiful_realism_balance_failure": "The image may not balance beauty and realistic photographed texture well enough.",
        "realism_made_subject_less_attractive": "Realism tuning may have made the face less attractive.",
        "pretty_but_too_ai_filtered": "The face may be pretty but too AI-filtered or poreless.",
        "real_but_unflattering": "The face may look real but not flattering enough for commercial use.",
        "skin_texture_beauty_balance_failure": "Skin texture and beauty may be out of balance.",
        "weak_aesthetic_finish": "The image may need a stronger direct-use visual finish.",
        "generic_stock_photo_finish": "The image may feel too generic rather than intentionally directed.",
        "flat_low_contrast_finish": "The image may look too flat or low-contrast.",
        "overexposed_washout": "The image may be too washed out or overexposed.",
        "underexposed_muddy_frame": "The image may be too dark, muddy, or underexposed.",
        "unbalanced_color_grade": "The image may have an unstable or unbalanced color grade.",
        "weak_subject_readability": "The main subject may not read clearly enough.",
        "weak_depth_and_material_separation": "Depth, texture, or material separation may be too weak.",
        "unstable_composition_balance": "The composition may feel unbalanced or accidental.",
        "overprocessed_hdr_finish": "The image may look overprocessed or HDR-heavy.",
        "uncanny_micro_detail": "Small details may look synthetic or overly generated.",
        "low_resolution_output": "The generated image may be too small for reliable direct use.",
        "file_missing": "Generated image file could not be found.",
        "file_unreadable": "Generated image file could not be read.",
        "vision_provider_unavailable": "Vision inspection provider is unavailable.",
        "low_confidence_review": "Review confidence is too low for automatic retry.",
        "policy_or_safety_block": "The image may need safety review.",
        "provider_error": "Vision inspection provider failed.",
    }
    return messages.get(code, code.replace("_", " "))


def _retry_patch_for_issues(issue_codes: list[str]) -> dict[str, Any]:
    prompt_additions: list[str] = []
    negative_additions: list[str] = []
    artifact_repair: list[str] = []
    composition_repair: list[str] = []
    identity_reinforcement: list[str] = []
    product_reinforcement: list[str] = []
    object_removal_instruction: list[str] = []
    for code in issue_codes:
        if code in _WATERMARK_OR_TEXT_ISSUES:
            negative_additions.extend(
                [
                    "visible text",
                    "watermark",
                    "signature",
                    "AI-generated mark",
                    "AIGC metadata mark",
                    "third-party AI badge",
                    "corner text",
                    "lower-right logo",
                    "semi-transparent mark",
                    "random letters",
                    "badge trace",
                ]
            )
            artifact_repair.append(
                "keep the image completely clean with no generated text, corner watermark, signature, badge, AI mark, lower-right logo, third-party AIGC label, or semi-transparent mark"
            )
        elif code == "collage_or_split_panel":
            negative_additions.extend(["collage", "split screen", "multi-panel layout"])
            composition_repair.append("generate one complete single-frame image")
        elif code in {"identity_drift", "hair_or_outfit_drift", "camera_distance_drift"}:
            identity_reinforcement.append(
                "preserve the exact uploaded portrait identity truth if present: face ratio, eye shape and spacing, eyebrow arc, nose-mouth relationship, jaw/chin direction, natural age impression, body identity direction, and skin-tone direction; use selected generated references only as continuation support when an uploaded truth source exists"
            )
            identity_reinforcement.append(
                "preserve broad hair direction and outfit category; follow the current prompt for lens, lighting, scene, and camera mood unless they are explicitly locked as style guidance; when styling defines the project, also preserve garment structure, layer logic, material behavior, pattern family, trim placement, and accessory placement"
            )
        elif code == "reference_guard_ignored":
            identity_reinforcement.append("use uploaded portrait identity truth as the main source when present; do not let the written prompt or a selected generated frame replace the person's facial identity")
            identity_reinforcement.append("selected reference should remain the identity or product truth source instead of being treated as optional decoration")
            product_reinforcement.append("if a product or object reference exists, preserve its exact silhouette, proportions, material, label/logo placement, packaging surface, and visible text shapes from the uploaded product truth source")
            negative_additions.extend(["reference ignored", "changed reference subject", "changed reference object"])
        elif code in _DOC86_PORTRAIT_IDENTITY_ISSUES:
            prompt_additions.extend(
                [
                    "Doc86 same-person repair: regenerate as the same person from the portrait reference, not merely the same beauty type",
                    "preserve underlying bone structure and facial-feature relationships before applying styling",
                    "style changes may affect makeup, wardrobe, hair arrangement, lighting, pose, expression, and scene, but must not reshape face geometry",
                    "reduce generic beauty archetype pressure so target-style, delicate, or premium styling does not redesign the face",
                    "preserve the current prompt's intended color, lighting, scene, composition, and atmosphere while repairing identity",
                ]
            )
            identity_reinforcement.extend(
                [
                    "keep face width/length ratio, cheek volume, jawline slope, chin scale, eye spacing/base eye shape, eyebrow-eye relationship, nose-mouth relationship, lip contour, and age impression from the reference",
                    "same person under changed styling, not a similar-looking new model",
                ]
            )
            negative_additions.extend(
                [
                    "same type but different person",
                    "generic AI beauty replacement",
                    "face slimming",
                    "V-shaped jaw replacement",
                    "eye enlargement",
                    "eye spacing drift",
                    "nose reshaping",
                    "lip reshaping",
                    "jaw or chin remodeling",
                    "age impression drift",
                    "style changed face geometry",
                ]
            )
        elif code in _DOC87_REFERENCE_BOUNDARY_ISSUES:
            prompt_additions.extend(
                [
                    "Doc87 reference-boundary repair: preserve the same person's face geometry from the portrait reference, but follow the current prompt for image direction",
                    "use the reference for identity only unless the user explicitly marked it as style guidance",
                    "do not copy source lighting, source color temperature, source scene, source wardrobe, source camera mood, or the original shoot style",
                    "follow the current prompt's lighting, color grade, background, camera angle, mood, wardrobe, and art direction",
                ]
            )
            identity_reinforcement.extend(
                [
                    "preserve the same person's face geometry while changing prompt-owned style channels",
                    "artifact or watermark repair must not replace the face with a cleaner generic beauty face",
                ]
            )
            negative_additions.extend(
                [
                    "copied source lighting",
                    "copied source color temperature",
                    "copied source scene",
                    "copied source camera mood",
                    "copied source wardrobe",
                    "reference used as full style template",
                    "prompt style ignored",
                    "same type but different person after cleanup",
                ]
                )
        elif code in _DOC88_REFERENCE_BALANCE_ISSUES:
            prompt_additions.extend(
                [
                    "Doc88 balance repair: preserve the current prompt's requested mood, color, light, scene, camera, composition, and art direction while keeping uploaded portrait identity recognizable",
                    "use uploaded portrait references as identity truth, not as a whole-photo tone, lighting, or scene template",
                    "use user-approved generated outputs only as positive visual direction anchors when they do not conflict with the current prompt",
                ]
            )
            identity_reinforcement.extend(
                [
                    "same person inside the current prompt's atmosphere",
                    "identity, approved direction, and prompt mood must all survive the retry",
                ]
            )
            negative_additions.extend(
                [
                    "prompt mood regression",
                    "prompt color or lighting regression",
                    "identity repair that damages requested atmosphere",
                    "approved visual direction ignored",
                    "overloaded identity negative prompt",
                    "scenario-specific template face",
                ]
            )
        elif code in {"product_identity_drift", "brand_asset_drift"}:
            product_reinforcement.append("preserve the supplied product or brand asset truth source exactly: same instance, shape, colors, material, proportions, surface finish, packaging silhouette, and logo/label placement")
        elif code in {"product_label_drift", "product_label_unreadable", "product_logo_or_label_obscured"}:
            product_reinforcement.append(
                "preserve the existing product label/logo exactly from the reference when visible; keep it readable, high-contrast, and unobscured"
            )
            artifact_repair.append("do not rewrite, translate, invent, blur, crop, darken, cover, or replace the visible product label/logo")
            negative_additions.extend(
                [
                    "invented product label",
                    "rewritten logo",
                    "unreadable product label",
                    "covered product logo",
                    "blurred label text",
                    "darkened product label",
                ]
            )
        elif code in {"composition_mismatch", "lighting_mismatch", "low_commercial_finish", "flat_catalog_lighting"}:
            prompt_additions.append("make the image cleaner, more polished, and closer to the project visual direction")
            if code == "flat_catalog_lighting":
                prompt_additions.append("add directional real-world light, material highlight behavior, natural shadow depth, and scene atmosphere")
                negative_additions.extend(["flat catalog lighting", "plain studio-only lighting"])
        elif code in _AESTHETIC_STABILITY_ISSUES:
            prompt_additions.extend(
                [
                    "raise the foundation aesthetic finish with intentional framing, clear subject readability, balanced exposure, stable color grade, natural contrast, and believable depth",
                    "make the result feel like a directed real-camera image rather than a generic stock render or accidental snapshot",
                    "preserve useful material, skin, fabric, hair, surface, and environment texture without overprocessed HDR or synthetic micro-detail",
                ]
            )
            composition_repair.extend(
                [
                    "recenter the visual hierarchy around one readable subject and remove accidental empty or cluttered balance",
                    "repair exposure and color so the image is neither washed out, muddy, overly flat, nor strangely color-shifted",
                ]
            )
            artifact_repair.append(
                "avoid AI-looking micro-sharpness, waxy detail, overprocessed contrast, and generic stock-photo polish"
            )
            negative_additions.extend(
                [
                    "generic stock photo",
                    "weak aesthetic finish",
                    "flat low-contrast image",
                    "washed-out exposure",
                    "muddy underexposed frame",
                    "unstable color grade",
                    "unclear subject",
                    "weak depth separation",
                    "accidental composition",
                    "overprocessed HDR",
                    "synthetic micro detail",
                    "AI-looking sharpness",
                ]
            )
        elif code in {"weak_lifestyle_context", "studio_only_when_lifestyle_requested"}:
            prompt_additions.append("make the frame feel like a real-use lifestyle or context scene with believable environment depth, surface contact, and natural use cues")
            composition_repair.append("avoid another studio-only packshot when the role asks for lifestyle, context, or scenario coverage")
            negative_additions.extend(["studio-only repetition", "empty product packshot", "weak lifestyle context"])
        elif code in {"role_collapse", "repeated_concept_or_prop"}:
            prompt_additions.append("separate the image roles clearly and use a different scene duty, camera distance, surface, or prop language for this output")
            composition_repair.append("avoid repeating the same concept, prop, crop, or image duty across the whole set")
            negative_additions.extend(["repeated concept", "same prop repeated", "same image role repeated"])
        elif code in {"unrelated_object", "unrelated_product"}:
            object_removal_instruction.append("remove unrelated objects or props that were not requested")
            negative_additions.extend(["unrelated object", "unrequested prop"])
        elif code in {"bad_hands_or_body", "face_artifact"}:
            artifact_repair.append("prioritize natural anatomy, clean facial structure, and realistic body details")
            negative_additions.extend(["distorted hands", "face artifacts", "warped anatomy"])
        elif code in {
            "suppressed_fair_complexion",
            "forced_tan_or_bronze_cast",
            "gray_brown_skin_cast",
            "head_body_proportion_distortion",
            "oversized_head",
            "compressed_neck_shoulders",
            "unflattering_face_drift",
        }:
            prompt_additions.extend(
                [
                    "for East Asian fresh portrait styling, restore a clean fair luminous complexion through high-key daylight, soft bounce light, exposure, and color balance",
                    "do not darken or tan East Asian skin by default unless the user explicitly asked for a tan, dark, bronze, or sun-tanned look",
                    "keep the person attractive and realistic with harmonious natural facial features, awake eyes, relaxed facial muscles, and a flattering real-camera face angle",
                    "preserve natural head-to-body proportion, balanced neck and shoulder line, and flattering upper-body crop",
                ]
            )
            artifact_repair.append(
                "repair complexion toward clean fair luminous East Asian skin tone with real texture; avoid fake whitening masks, bleached beauty filters, or skin smoothing"
            )
            composition_repair.append(
                "repair the close crop so face scale, head-to-body ratio, neck, shoulders, and upper-body proportions look natural and flattering"
            )
            negative_additions.extend(
                [
                    "suppressed fair complexion",
                    "unnecessarily darkened East Asian skin",
                    "forced tan or bronze cast",
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
                ]
            )
        elif code in _BEAUTIFUL_REALISM_ISSUES:
            prompt_additions.extend(
                [
                    "repair the image with Doc78 beautiful realism: beauty is the visual goal, realism is the rendering method",
                    "preserve same-person facial feature relationships: attractive eyebrow shape and arc, awake eye shape and spacing, eyelid direction, nose-mouth relationship, jaw/chin direction, cheek volume, face ratio, and neck/shoulder balance",
                    "make realism come from photographed skin texture, soft natural light, hair strands, fabric detail, lens depth, natural facial tension, and small asymmetries",
                    "keep a clean fresh luminous complexion when the brief implies East Asian beauty; do not force tan, muddy skin, harsh shadow, or tired documentary ugliness",
                ]
            )
            identity_reinforcement.append(
                "use the selected image or project identity card as the truth source; vary pose, gaze, expression, scene, and camera angle without changing identity-critical face design"
            )
            artifact_repair.extend(
                [
                    "repair facial features before style: eyebrows, eyes, nose-mouth spacing, jaw/chin, cheek volume, and face ratio must remain beautiful and recognizable",
                    "if the face is pretty but too filtered, restore subtle pores, eyelid detail, hair flyaways, fabric texture, and real shadow transitions without reshaping the face",
                    "if the face is real but unflattering, recover soft flattering light, relaxed facial muscles, graceful eyebrow design, and a better camera angle while preserving identity",
                ]
            )
            negative_additions.extend(
                [
                    "ugly realism",
                    "realism made face less attractive",
                    "real but ugly face",
                    "harsh documentary ugliness",
                    "bad eyebrow design",
                    "ugly eyebrow shape",
                    "drooping eyebrows",
                    "mismatched brows",
                    "random eyebrow thickness drift",
                    "sleepy dull eyes",
                    "unflattering nose-mouth drift",
                    "jaw or chin direction drift",
                    "facial feature degradation",
                    "pretty but poreless AI filter",
                    "over-smoothed beauty face",
                    "flat facial attractiveness",
                    "dull complexion",
                    "muddy skin tone",
                ]
            )
        elif code in {
            "ai_face_render",
            "plastic_skin",
            "over_smoothed_skin",
            "missing_skin_texture",
            "over_retouching",
            "poreless_beauty_surface",
            "synthetic_fashion_face",
            "weak_photographic_imperfection",
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
            "same_expression_repetition",
            "same_head_angle_repetition",
            "same_pose_repetition",
        }:
            prompt_additions.extend(
                [
                    "render the person as a real camera photograph with natural skin texture, subtle pores, and believable expression",
                    "preserve identity while varying expression, gaze, head angle, pose, and camera angle naturally",
                    "add natural camera, skin, hair, fabric, and environment imperfections while keeping a polished professional finish",
                    "reduce beauty-app polish with soft 35mm or CCD-like capture, skin tone variation, eyelid/under-eye detail, loose hair, and candid mouth tension",
                    "preserve individual facial geometry without face-slimming, enlarged beauty eyes, perfect V-shaped chin, or generic AI-beauty proportions",
                    "restore fresh attractiveness with soft natural bounce light, healthy clear complexion, clean bright daylight, gentle cheek warmth, and natural skin tone preserved",
                ]
            )
            artifact_repair.append(
                "repair the face away from AI-beauty rendering toward real photographed skin, natural asymmetry, realistic eyes, and non-waxy highlights"
            )
            artifact_repair.append(
                "remove skin-blur retouching and idol photocard polish; keep the person attractive but visibly camera-captured"
            )
            artifact_repair.append(
                "remove beauty-filter facial reshaping; keep natural jaw contour, real eyelid folds, lip texture, and slight facial asymmetry"
            )
            artifact_repair.append(
                "lift dull or dark facial lighting with real bounce light and healthier color balance while retaining visible skin texture and natural skin tone"
            )
            identity_reinforcement.append(
                "keep broad face shape, age direction, body type, hair direction, and recognizable identity cues while avoiding a copied template face"
            )
            negative_additions.extend(
                [
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
                    "same exact AI face repeated",
                    "poreless beauty surface",
                    "over-retouched fashion face",
                    "synthetic fashion face",
                    "same exact expression repeated",
                    "same exact pose repeated",
                    "beauty-app face",
                    "idol photocard polish",
                    "skin-blur retouching",
                    "flawless porcelain mask",
                    "over-uniform skin tone",
                    "over-sharp AI detail",
                    "perfect smile repeated",
                    "face-slimming filter",
                    "beautified facial geometry",
                    "generic AI beauty identity",
                    "enlarged beauty-filter eyes",
                    "perfect V-shaped chin",
                    "liquified face proportions",
                    "dull complexion",
                    "muddy skin tone",
                    "underexposed face",
                    "harsh facial shadow",
                    "overly matte documentary look",
                    "tired expression",
                    "unflattering skin color cast",
                    "skin whitening filter",
                    "beauty-app glow",
                ]
            )
        elif code in {"ecommerce_slot_mismatch", "ecommerce_suite_role_mismatch"}:
            prompt_additions.append("preserve the requested ecommerce slot for this output and do not substitute another listing role")
            composition_repair.append("separate ecommerce roles clearly: main image, feature proof, lifestyle scene, detail proof, trust cue, and cover-safe image must stay distinct")
            negative_additions.extend(
                [
                    "wrong ecommerce image role",
                    "requested listing slot ignored",
                    "feature image replaced by detail image",
                    "lifestyle image replaced by studio packshot",
                ]
            )
    return {
        "prompt_additions": _dedupe(prompt_additions),
        "negative_additions": _dedupe(negative_additions),
        "artifact_repair": _dedupe(artifact_repair),
        "composition_repair": _dedupe(composition_repair),
        "identity_reinforcement": _dedupe(identity_reinforcement),
        "product_reinforcement": _dedupe(product_reinforcement),
        "object_removal_instruction": _dedupe(object_removal_instruction),
    }


def _score_card(status: str) -> dict[str, float]:
    if status == "fail_retryable":
        return {"artifact_safety": 0.42, "composition": 0.64, "commercial_finish": 0.58, "overall": 0.55}
    if status == "fail_final":
        return {"artifact_safety": 0.2, "composition": 0.4, "commercial_finish": 0.35, "overall": 0.3}
    if status == "manual_review":
        return {"artifact_safety": 0.5, "composition": 0.5, "commercial_finish": 0.5, "overall": 0.5}
    if status == "warning":
        return {"artifact_safety": 0.74, "composition": 0.72, "commercial_finish": 0.7, "overall": 0.72}
    return {"artifact_safety": 0.9, "composition": 0.84, "commercial_finish": 0.84, "overall": 0.86}


def _is_openai_gpt_image_output(resolution: GeneratedOutputResolution) -> bool:
    provider = str(resolution.provider or "").strip().lower()
    model = str(resolution.model or "").strip().lower()
    if provider == "openai_gpt_image":
        return True
    return model in {"gpt-image-2", "gpt-image-1"} or model.startswith("gpt-image-")


def _summary_for_status(status: str, issue_codes: list[str]) -> list[str]:
    if status == "fail_retryable":
        return ["V3 found a fixable visual issue.", "A cleaner retry direction is ready."]
    if status == "fail_final":
        return ["This image is not recommended for direct use.", "The record is kept, but automatic retry is not used."]
    if status == "manual_review":
        return ["This image needs manual confirmation before automatic retry."]
    if status == "warning":
        return ["V3 found a minor risk, but the image can still be reviewed."]
    return ["V3 checked the image.", "No clear visual issue was found."]


def _public_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in metadata.items()
        if key
        in {
            "template_id",
            "scenario_id",
            "project_id",
            "quality_mode",
            "post_generation_fake_issue_codes",
            "post_generation_fake_confidence",
            "vision_inspection_mode",
            "enable_real_vision_inspection",
            "vision_model",
        }
    }


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _safe_float(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _provider_issue_codes(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("issue_codes") or payload.get("detected_issue_codes") or payload.get("detected_issues")
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        return _dedupe([str(item.get("code") or "").strip() for item in raw])
    return _dedupe(_string_list(raw))


def _status_from_issues(issue_codes: list[str], provider_status: str) -> str:
    normalized = provider_status.strip().lower()
    if any(code in FINAL_ISSUE_CODES for code in issue_codes):
        return "fail_final"
    if any(code in RETRYABLE_ISSUE_CODES for code in issue_codes):
        return "fail_retryable"
    if normalized in {"pass", "warning", "fail_final", "manual_review"}:
        return normalized
    if issue_codes:
        return "warning"
    return "pass"


def _provider_score_card(scores: Any, status: str) -> dict[str, float]:
    if not isinstance(scores, dict):
        return _score_card(status)
    result = _score_card(status)
    for key, value in scores.items():
        result[str(key)] = _safe_float(value, default=result.get(str(key), 0.5))
    return result


def _merge_retry_patches(*patches: Any) -> dict[str, Any]:
    merged: dict[str, list[str]] = {}
    for patch in patches:
        if not isinstance(patch, dict):
            continue
        for key, value in patch.items():
            values = _string_list(value)
            if values:
                merged.setdefault(str(key), []).extend(values)
    return {key: _dedupe(values) for key, values in merged.items() if _dedupe(values)}


def _lower_right_mark_risk(path: Path) -> tuple[bool, dict[str, Any]]:
    try:
        from PIL import Image, ImageFilter, ImageStat

        with Image.open(path) as image:
            gray = image.convert("L")
            width, height = gray.size
            if width < 180 or height < 180:
                return False, {"lower_right_mark_scan": "skipped_small_image"}
            strip = gray.crop((int(width * 0.72), int(height * 0.86), width, int(height * 0.98)))
            edges = strip.filter(ImageFilter.FIND_EDGES)
            pixel_count = max(1, strip.width * strip.height)
            edge_ratio = _threshold_ratio(edges, 35, pixel_count)
            strong_edge_ratio = _threshold_ratio(edges, 65, pixel_count)
            local_std = float(ImageStat.Stat(strip).stddev[0])
            horizontal_band_ratio = _horizontal_text_band_ratio(edges)
            compact_mark_score = (strong_edge_ratio * 0.55) + (horizontal_band_ratio * 0.45)
            # Generated marks usually appear as compact semi-transparent text
            # or a small logo in the lower-right corner. Flower edges, fabric
            # folds and bokeh can be busy but rarely form repeated horizontal
            # text-like bands, so only high-confidence evidence may trigger
            # automatic retry.
            text_like_edge = edge_ratio >= 0.145 and strong_edge_ratio >= 0.12
            band_like_edge = strong_edge_ratio >= 0.095 and horizontal_band_ratio >= 0.17
            risk = (
                edge_ratio >= 0.145
                and strong_edge_ratio >= 0.095
                and (text_like_edge or band_like_edge)
                and 8.0 <= local_std <= 48.0
                and (text_like_edge or compact_mark_score >= 0.125)
            )
            confidence = "high" if risk else "low"
            return risk, {
                "lower_right_mark_scan": "done",
                "lower_right_edge_ratio": round(edge_ratio, 4),
                "lower_right_strong_edge_ratio": round(strong_edge_ratio, 4),
                "lower_right_horizontal_band_ratio": round(horizontal_band_ratio, 4),
                "lower_right_mark_confidence": confidence,
                "lower_right_mark_evidence_type": "compact_text_or_logo_like" if risk else "ambiguous_texture",
                "lower_right_luma_std": round(local_std, 2),
            }
    except Exception:
        return False, {"lower_right_mark_scan": "unavailable"}


def _threshold_ratio(image: Any, threshold: int, pixel_count: int) -> float:
    mask = image.point(lambda value: 255 if value > threshold else 0)
    histogram = mask.histogram()
    return float(histogram[255]) / float(pixel_count)


def _horizontal_text_band_ratio(image: Any) -> float:
    width, height = image.size
    if width <= 0 or height <= 0:
        return 0.0
    rows = []
    pixels = image.load()
    for y in range(height):
        active = 0
        for x in range(width):
            if pixels[x, y] > 65:
                active += 1
        ratio = active / float(width)
        if 0.08 <= ratio <= 0.55:
            rows.append(1)
        else:
            rows.append(0)
    if not rows:
        return 0.0
    clustered = 0
    run = 0
    for value in rows:
        if value:
            run += 1
            continue
        if 2 <= run <= 12:
            clustered += run
        run = 0
    if 2 <= run <= 12:
        clustered += run
    return clustered / float(height)
