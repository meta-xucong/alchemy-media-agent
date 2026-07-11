"""Optional real-image vision provider for V3 post-generation inspection."""

from __future__ import annotations

import base64
from io import BytesIO
import json
import os
from pathlib import Path
from typing import Any, Protocol

from .contracts import GeneratedOutputResolution


class VisionInspectionProviderUnavailable(RuntimeError):
    """Raised when no configured vision provider can inspect real images."""


class VisionInspectionProviderError(RuntimeError):
    """Raised when a configured vision provider fails during inspection."""


class VisionInspectionProvider(Protocol):
    provider_name: str

    def available(self, *, force: bool = False) -> bool:
        """Return whether this provider can be used in the current runtime."""

    def inspect(
        self,
        resolution: GeneratedOutputResolution,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Inspect a generated output and return a provider-neutral payload."""


class OpenAIVisionInspectionProvider:
    """OpenAI-compatible multimodal adapter used only by the visual cluster."""

    provider_name = "openai_compatible_vision"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds

    def available(self, *, force: bool = False) -> bool:
        if not force and not _env_bool("V3_VISION_INSPECTION_ENABLED", default=False):
            return False
        return bool(self._api_key())

    def inspect(
        self,
        resolution: GeneratedOutputResolution,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not resolution.file_path:
            raise VisionInspectionProviderUnavailable("generated output file is not available")
        path = Path(resolution.file_path)
        if not path.exists() or not path.is_file():
            raise VisionInspectionProviderUnavailable("generated output file is missing")
        api_key = self._api_key()
        if not api_key:
            raise VisionInspectionProviderUnavailable("vision inspection API key is not configured")
        metadata = dict(metadata or {})
        try:
            from openai import OpenAI

            client = OpenAI(**_openai_client_kwargs(api_key=api_key, base_url=self._base_url()))
            prompt = _inspection_prompt(metadata)
            data_url = _image_data_url(path, resolution.mime_type)
            response_payload = self._inspect_with_responses(client, prompt, data_url, metadata)
            return _loads_json_object(response_payload)
        except VisionInspectionProviderUnavailable:
            raise
        except Exception as exc:
            raise VisionInspectionProviderError(f"vision inspection provider failed: {str(exc)[:240]}") from exc

    def _inspect_with_responses(self, client: Any, prompt: str, data_url: str, metadata: dict[str, Any]) -> str:
        model = self._model(metadata)
        timeout = self._timeout()
        reference_data_urls = _inspection_reference_data_urls(metadata)
        response_content = [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": data_url},
            *[{"type": "input_image", "image_url": item} for item in reference_data_urls],
        ]
        try:
            response = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "user",
                        "content": response_content,
                    }
                ],
                text={"format": {"type": "json_object"}},
                timeout=timeout,
                max_output_tokens=1600,
            )
            text = getattr(response, "output_text", None) or _response_text_from_openai(response)
            if text:
                return text
        except Exception:
            pass
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                        *[
                            {"type": "image_url", "image_url": {"url": item}}
                            for item in reference_data_urls
                        ],
                    ],
                }
            ],
            response_format={"type": "json_object"},
            timeout=timeout,
            max_tokens=1600,
        )
        return str(response.choices[0].message.content or "")

    def _api_key(self) -> str | None:
        return (
            self.api_key
            or _env("V3_VISION_INSPECTION_API_KEY")
            or _settings_value("openai_api_key")
            or _settings_value("lab_openai_api_key")
        )

    def _base_url(self) -> str | None:
        return (
            self.base_url
            or _env("V3_VISION_INSPECTION_BASE_URL")
            or _settings_value("openai_base_url")
            or _settings_value("lab_openai_base_url")
        )

    def _model(self, metadata: dict[str, Any]) -> str:
        return str(
            metadata.get("vision_model")
            or self.model
            or _env("V3_VISION_INSPECTION_MODEL")
            or _settings_value("openai_llm_model")
            or _settings_value("default_llm_model")
            or "gpt-5.5"
        )

    def _timeout(self) -> float:
        if self.timeout_seconds is not None:
            return self.timeout_seconds
        try:
            return float(os.getenv("V3_VISION_INSPECTION_TIMEOUT_SECONDS", "90"))
        except ValueError:
            return 90.0


def create_default_vision_provider() -> VisionInspectionProvider:
    return OpenAIVisionInspectionProvider()


def _inspection_prompt(metadata: dict[str, Any]) -> str:
    user_goal = str(metadata.get("user_input") or metadata.get("original_user_input") or "").strip()
    template_id = str(metadata.get("template_id") or metadata.get("scenario_id") or "general_creative")
    project_summary = metadata.get("project_context_summary") or metadata.get("project_memory_summary") or {}
    project_context = metadata.get("project_context_snapshot") if isinstance(metadata.get("project_context_snapshot"), dict) else {}
    reference_policy = (
        metadata.get("resolved_reference_policy_package")
        if isinstance(metadata.get("resolved_reference_policy_package"), dict)
        else project_context.get("resolved_reference_policy_package")
        if isinstance(project_context, dict)
        else {}
    )
    reference_count = len(_inspection_reference_paths(metadata))
    return "\n".join(
        [
            "You are V3's post-generation visual inspector.",
            "Inspect the attached generated image only after it exists.",
            (
                "Image 1 is the generated result. Following images are reference truth/context images in priority order; compare only the channels assigned by the reference policy."
                if reference_count
                else "Image 1 is the generated result; no readable reference image was supplied to this inspection."
            ),
            "Return strict JSON. Do not include markdown.",
            "Judge visible text artifacts, watermarks, collage/split panels, identity or style drift, long-term identity-card continuity, facial-feature aesthetic integrity, eyebrow/eye/nose-mouth/jaw drift, beautiful-realism balance, realism that makes the subject less attractive, product label/logo readability, ecommerce slot fidelity, unrelated objects, anatomy/face artifacts, over-smoothed AI-face realism, reference/prompt complexion direction, age fidelity, human proportion, repeated expression/pose/head angle across a set, weak lifestyle context, lighting/composition mismatch, subject readability, composition balance, exposure stability, color-grade stability, depth/material separation, generic stock-photo finish, overprocessed HDR or synthetic detail, and direct-use visual polish. When reference images are present, independently score identity truth and prompt-owned channel obedience; makeup, hairstyle, wardrobe, expression, pose, camera, light, scene, and mood changes are allowed unless the resolved policy assigns them to the reference. Report source-style leakage even if the image is attractive.",
            "Use beginner-safe wording in summaries. For general_creative, say subject/object/visual direction instead of product/ecommerce language.",
            f"Template: {template_id}",
            f"User goal: {user_goal}",
            f"Project context summary: {json.dumps(project_summary, ensure_ascii=False)[:1200]}",
            f"Resolved reference policy: {json.dumps(reference_policy, ensure_ascii=False)[:2200]}",
            "Allowed issue_codes: visible_text_artifact, watermark_or_signature, faint_corner_watermark, ai_generated_badge_trace, signature_like_artifact, lower_right_mark_artifact, commercial_cleanliness_failure, collage_or_split_panel, identity_drift, bone_structure_drift, face_shape_drift, cheek_jaw_chin_drift, eye_shape_or_spacing_identity_drift, eyebrow_eye_relationship_drift, nose_mouth_relationship_identity_drift, lip_contour_identity_drift, styling_changed_face_geometry, archetype_overrode_reference_identity, same_type_not_same_person, identity_reference_underweighted, hair_or_outfit_drift, camera_distance_drift, identity_card_missing, identity_card_not_applied, identity_feature_drift, eyebrow_shape_drift, eye_shape_or_spacing_drift, nose_mouth_relationship_drift, jaw_chin_direction_drift, unflattering_feature_degradation, beautiful_realism_balance_failure, realism_made_subject_less_attractive, pretty_but_too_ai_filtered, real_but_unflattering, skin_texture_beauty_balance_failure, source_hair_overinherited, source_makeup_overinherited, source_wardrobe_overinherited, source_lighting_overinherited, source_color_temperature_overinherited, source_color_grade_overinherited, source_scene_overinherited, source_camera_overinherited, source_camera_mood_overinherited, source_whole_style_overinherited, reference_used_as_style_when_identity_only, prompt_owned_channel_ignored, selected_anchor_overrode_current_prompt, structured_appearance_lock_misapplied, lighting_mismatch, composition_mismatch, unrelated_object, unrelated_product, product_identity_drift, product_label_drift, product_label_unreadable, product_logo_or_label_obscured, brand_asset_drift, ecommerce_slot_mismatch, ecommerce_suite_role_mismatch, bad_hands_or_body, face_artifact, ai_face_render, plastic_skin, over_smoothed_skin, missing_skin_texture, over_retouching, poreless_beauty_surface, synthetic_fashion_face, weak_photographic_imperfection, synthetic_beauty_filter, doll_like_face, template_smile, over_perfect_symmetry, wax_skin_highlight, uncanny_eye_expression, same_ai_face_repetition, beauty_app_face, idol_photocard_polish, skin_blur_retouching, over_uniform_skin_tone, over_sharp_ai_detail, perfect_smile_repetition, face_slimming_filter, beautified_facial_geometry, generic_ai_beauty_identity, dull_complexion, muddy_skin_tone, underexposed_face, harsh_facial_shadow, overly_matte_documentary_look, tired_expression, unflattering_color_cast, complexion_direction_drift, unintended_skin_darkening, unintended_skin_lightening, unflattering_skin_color_cast, age_identity_drift, age_inappropriate_rendering, suppressed_fair_complexion, forced_tan_or_bronze_cast, gray_brown_skin_cast, head_body_proportion_distortion, oversized_head, compressed_neck_shoulders, unflattering_face_drift, doll_like_child_face, adultified_child_model, synthetic_child_skin, pageant_polish_child_face, frozen_child_smile, unreal_child_eyes, unreal_child_teeth, child_face_ai_render, same_expression_repetition, same_head_angle_repetition, same_pose_repetition, studio_only_when_lifestyle_requested, role_collapse, flat_catalog_lighting, weak_lifestyle_context, repeated_concept_or_prop, reference_guard_ignored, low_commercial_finish, weak_aesthetic_finish, generic_stock_photo_finish, flat_low_contrast_finish, overexposed_washout, underexposed_muddy_frame, unbalanced_color_grade, weak_subject_readability, weak_depth_and_material_separation, unstable_composition_balance, overprocessed_hdr_finish, uncanny_micro_detail, low_resolution_output, policy_or_safety_block, low_confidence_review.",
            'Return keys: {"status":"pass|warning|fail_retryable|fail_final|manual_review","confidence":0.0,"issue_codes":[],"scores":{"artifact_safety":0.0,"composition":0.0,"commercial_finish":0.0,"identity_consistency":0.0,"same_person_readability":0.0,"face_outline_and_proportion":0.0,"brow_eye_geometry":0.0,"nose_mouth_relationship":0.0,"jaw_chin_geometry":0.0,"age_identity_direction":0.0,"prompt_owned_channel_obedience":0.0,"human_realism":0.0,"overall":0.0},"identity_deltas":[],"preserved_elements":[],"drift_warnings":[],"artifact_warnings":[],"summary":[],"retry_patch":{"identity_reinforcement":[]}}',
        ]
    )


def _image_data_url(path: Path, mime_type: str | None) -> str:
    mime = mime_type or _mime_from_path(path)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _inspection_reference_data_urls(metadata: dict[str, Any]) -> list[str]:
    return [_inspection_image_data_url(path) for path in inspection_reference_paths(metadata)]


def inspection_reference_paths(metadata: dict[str, Any], *, identity_only: bool = False) -> list[Path]:
    context = metadata.get("project_context_snapshot")
    if not isinstance(context, dict):
        context = {}
    candidates: list[dict[str, Any]] = []
    for key in ("uploaded_reference_assets", "selected_visual_references", "strong_reference_bindings"):
        values = context.get(key)
        if isinstance(values, list):
            candidates.extend(item for item in values if isinstance(item, dict))
    direct = metadata.get("uploaded_assets")
    if isinstance(direct, list):
        candidates.extend(item for item in direct if isinstance(item, dict))
    ranked = sorted(
        candidates,
        key=lambda item: (
            0 if str(item.get("source_type") or "").lower() == "uploaded" else 1,
            0 if "identity" in str(item.get("use_policy") or item.get("role") or "").lower() else 1,
        ),
    )
    result: list[Path] = []
    seen: set[str] = set()
    for item in ranked:
        if identity_only:
            role_text = " ".join(
                str(item.get(key) or "")
                for key in ("role", "use_policy", "declared_role", "intended_use")
            ).lower()
            if not any(term in role_text for term in ("portrait", "identity", "face", "person", "character")):
                continue
        value = item.get("file_path") or item.get("preview_path") or item.get("thumbnail_path")
        if not value:
            continue
        path = Path(str(value))
        if not path.exists() or not path.is_file():
            continue
        resolved = str(path.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(path)
        if len(result) >= 2:
            break
    return result


def _inspection_reference_paths(metadata: dict[str, Any]) -> list[Path]:
    return inspection_reference_paths(metadata)


def _inspection_image_data_url(path: Path) -> str:
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as raw:
            image = ImageOps.exif_transpose(raw).convert("RGB")
            image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=84, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        return _image_data_url(path, None)


def _mime_from_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def _loads_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        raise VisionInspectionProviderError("vision inspection returned empty output")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise VisionInspectionProviderError("vision inspection returned non-json output")
        parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        raise VisionInspectionProviderError("vision inspection json output was not an object")
    return parsed


def _response_text_from_openai(response: Any) -> str:
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(str(text))
    return "\n".join(chunks)


def _openai_client_kwargs(*, api_key: str, base_url: str | None) -> dict[str, Any]:
    try:
        from app.config import openai_sdk_client_kwargs

        return openai_sdk_client_kwargs(api_key=api_key, base_url=base_url)
    except Exception:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return kwargs


def _settings_value(name: str) -> Any:
    try:
        from app.config import settings

        return getattr(settings, name, None)
    except Exception:
        return None


def _env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
