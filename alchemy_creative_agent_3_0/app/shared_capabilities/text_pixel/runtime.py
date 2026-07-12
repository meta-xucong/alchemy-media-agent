"""Read-compatible contracts for the retired deterministic text-pixel runtime.

Doc111 makes provider-native complete-image generation the only forward text
path. The legacy structures below remain importable so old records can be
read, but public delivery calls never initialize or execute a local font, OCR,
or raster-composition workflow.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import TYPE_CHECKING, Any, Protocol

from ...creative_core.rules import stable_id
from .contracts import CopyRenderPlan, CopyRenderPlanBatch, TextPixelDelivery, TextPixelDeliveryAttempt, TextPixelDeliveryBatch

if TYPE_CHECKING:
    from ...product_api.outputs import V3GeneratedOutputRecord, V3GeneratedOutputStore


_SUPPORTED_LOCALES = {"en-US", "zh-CN", "ru-RU"}
_REPAIRABLE_ISSUES = {"layout_overflow", "safe_area_violation", "text_low_contrast"}
_COPY_CORRECTION_ISSUES = {
    "copy_claim_blocked",
    "copy_requires_review",
    "required_copy_missing",
    "ocr_text_mismatch",
    "forbidden_text_detected",
    "glyph_unavailable",
    "font_unavailable",
    "font_license_unverified",
    "ocr_runtime_unavailable",
    "unsupported_locale",
}


@dataclass(frozen=True)
class LicensedFont:
    font_id: str
    version: str
    file_path: str
    supported_locales: tuple[str, ...]
    license_id: str
    expected_sha256: str | None = None
    production_approved: bool = False

    def provenance(self) -> dict[str, Any]:
        path = Path(self.file_path)
        digest = _file_sha256(path) if path.is_file() else None
        return {
            "font_id": self.font_id,
            "font_version": self.version,
            "font_path": str(path),
            "font_license_id": self.license_id,
            "font_sha256": digest,
            "font_expected_sha256": self.expected_sha256,
            "production_approved": self.production_approved,
        }


@dataclass(frozen=True)
class FontResolution:
    font: LicensedFont | None
    issue_code: str | None = None
    provenance: dict[str, Any] | None = None


class FontRegistry:
    """Only explicitly declared and verified fonts may be selected."""

    def __init__(self, fonts: list[LicensedFont] | None = None) -> None:
        self.fonts = list(fonts or [])

    @classmethod
    def from_environment(cls) -> "FontRegistry":
        raw = os.getenv("V3_TEXT_PIXEL_FONT_MANIFEST_JSON", "").strip()
        entries: list[dict[str, Any]] = []
        if raw:
            try:
                parsed = json.loads(raw)
                entries = parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                entries = []
        elif os.getenv("V3_TEXT_PIXEL_FONT_PATH"):
            entries = [
                {
                    "font_id": os.getenv("V3_TEXT_PIXEL_FONT_ID", "configured_font"),
                    "version": os.getenv("V3_TEXT_PIXEL_FONT_VERSION", "unversioned"),
                    "file_path": os.getenv("V3_TEXT_PIXEL_FONT_PATH", ""),
                    "supported_locales": os.getenv("V3_TEXT_PIXEL_FONT_LOCALES", "").split(","),
                    "license_id": os.getenv("V3_TEXT_PIXEL_FONT_LICENSE_ID", ""),
                    "expected_sha256": os.getenv("V3_TEXT_PIXEL_FONT_SHA256") or None,
                    "production_approved": _env_bool("V3_TEXT_PIXEL_FONT_PRODUCTION_APPROVED"),
                }
            ]
        fonts: list[LicensedFont] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                locales = tuple(str(item).strip() for item in entry.get("supported_locales", []) if str(item).strip())
                fonts.append(
                    LicensedFont(
                        font_id=str(entry.get("font_id") or "").strip(),
                        version=str(entry.get("version") or "").strip(),
                        file_path=str(entry.get("file_path") or "").strip(),
                        supported_locales=locales,
                        license_id=str(entry.get("license_id") or "").strip(),
                        expected_sha256=str(entry.get("expected_sha256") or "").strip() or None,
                        production_approved=bool(entry.get("production_approved")),
                    )
                )
            except Exception:
                continue
        return cls(fonts)

    def resolve(self, locale: str | None, *, require_production_approval: bool) -> FontResolution:
        if locale not in _SUPPORTED_LOCALES:
            return FontResolution(None, "unsupported_locale")
        last_failure: FontResolution | None = None
        for font in self.fonts:
            if locale not in font.supported_locales:
                continue
            provenance = font.provenance()
            if not Path(font.file_path).is_file():
                last_failure = FontResolution(None, "font_unavailable", provenance)
                continue
            if not font.license_id:
                last_failure = FontResolution(None, "font_license_unverified", provenance)
                continue
            digest = provenance.get("font_sha256")
            if require_production_approval and (
                not font.production_approved or not font.expected_sha256 or digest != font.expected_sha256
            ):
                last_failure = FontResolution(None, "font_license_unverified", provenance)
                continue
            return FontResolution(font, None, provenance)
        return last_failure or FontResolution(None, "font_unavailable")


@dataclass(frozen=True)
class TextPixelRuntimeSettings:
    enabled: bool = False
    production_activation_enabled: bool = False
    allow_development_fonts: bool = False
    min_contrast_ratio: float = 4.5
    max_deterministic_repairs: int = 1

    @classmethod
    def from_environment(cls) -> "TextPixelRuntimeSettings":
        return cls(
            enabled=_env_bool("V3_TEXT_PIXEL_DELIVERY_ENABLED"),
            production_activation_enabled=_env_bool("V3_TEXT_PIXEL_DELIVERY_PRODUCTION_ENABLED"),
            allow_development_fonts=_env_bool("V3_TEXT_PIXEL_ALLOW_DEVELOPMENT_FONTS"),
        )


@dataclass(frozen=True)
class OcrResult:
    available: bool
    engine_id: str
    text: str = ""
    confidence: float | None = None
    details: dict[str, Any] | None = None


class OcrEngine(Protocol):
    def inspect(self, image_path: str, locale: str | None) -> OcrResult:
        ...


class TesseractOcrEngine:
    """Optional real OCR adapter. It always receives the final raster path."""

    locale_languages = {"en-US": "eng", "zh-CN": "chi_sim", "ru-RU": "rus"}

    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("tesseract")

    def inspect(self, image_path: str, locale: str | None) -> OcrResult:
        if not self.executable:
            return OcrResult(False, "tesseract", details={"reason": "tesseract_not_configured"})
        language = self.locale_languages.get(locale or "")
        if not language:
            return OcrResult(False, "tesseract", details={"reason": "unsupported_locale"})
        try:
            completed = subprocess.run(
                [self.executable, image_path, "stdout", "-l", language, "--psm", "6"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except Exception as exc:
            return OcrResult(False, "tesseract", details={"reason": type(exc).__name__})
        if completed.returncode != 0:
            return OcrResult(False, "tesseract", details={"reason": completed.stderr[-300:]})
        return OcrResult(True, "tesseract", text=completed.stdout.strip(), details={"final_pixel_path": image_path})


class StaticOcrEngine:
    """Explicit test double; production must use a real final-pixel OCR engine."""

    def __init__(self, text: str, *, available: bool = True, confidence: float | None = 0.99) -> None:
        self.text = text
        self.available = available
        self.confidence = confidence
        self.paths: list[str] = []

    def inspect(self, image_path: str, locale: str | None) -> OcrResult:
        self.paths.append(image_path)
        return OcrResult(self.available, "static_test_ocr", self.text, self.confidence, {"final_pixel_path": image_path})


@dataclass(frozen=True)
class CompositionOutcome:
    rendered: bool
    image_bytes: bytes | None = None
    bounds_px: dict[str, int] | None = None
    font_size_px: int | None = None
    line_count: int = 0
    contrast_ratio: float | None = None
    foreground_color: str | None = None
    issue_codes: tuple[str, ...] = ()


class PillowDeterministicCompositor:
    renderer_id = "pillow_deterministic_text_compositor_v1"

    def compose(self, source_path: str, plan: CopyRenderPlan, font: LicensedFont, *, repair: bool = False) -> CompositionOutcome:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except Exception:
            return CompositionOutcome(False, issue_codes=("compositor_runtime_unavailable",))
        if not plan.expected_copy:
            return CompositionOutcome(False, issue_codes=("required_copy_missing",))
        try:
            with Image.open(source_path) as raw:
                image = raw.convert("RGBA")
        except Exception:
            return CompositionOutcome(False, issue_codes=("source_output_unreadable",))
        if not _font_supports_text(font.file_path, plan.expected_copy):
            return CompositionOutcome(False, issue_codes=("glyph_unavailable",))
        safe = plan.normalized_safe_area.as_pixel_box(*image.size)
        margin = max(4, round(min(safe["w"], safe["h"]) * 0.04))
        available_w = max(1, safe["w"] - margin * 2)
        available_h = max(1, safe["h"] - margin * 2)
        max_size = max(12, min(round(available_h * (0.48 if repair else 0.58)), round(available_w * 0.16)))
        min_size = 10
        chosen: tuple[Any, list[str], int, tuple[int, int, int, int]] | None = None
        for size in range(max_size, min_size - 1, -1):
            try:
                face = ImageFont.truetype(font.file_path, size=size)
            except Exception:
                return CompositionOutcome(False, issue_codes=("font_unavailable",))
            lines = _wrap_text(ImageDraw.Draw(image), plan.expected_copy, face, available_w, plan.locale)
            line_height = max(1, round(size * 1.22))
            text_height = line_height * len(lines)
            widths = [ImageDraw.Draw(image).textbbox((0, 0), item, font=face)[2] for item in lines] or [0]
            if text_height <= available_h and max(widths) <= available_w:
                chosen = (face, lines, line_height, (max(widths), text_height, available_w, available_h))
                break
        if chosen is None:
            return CompositionOutcome(False, issue_codes=("layout_overflow",))
        face, lines, line_height, dimensions = chosen
        foreground = None if repair else plan.foreground_color
        if foreground is None:
            foreground = _best_contrast_color(image, safe)
        contrast = _contrast_ratio(_average_luminance(image, safe), _luminance(_parse_color(foreground)))
        if contrast < 4.5 and repair:
            foreground = _best_contrast_color(image, safe)
            contrast = _contrast_ratio(_average_luminance(image, safe), _luminance(_parse_color(foreground)))
        draw = ImageDraw.Draw(image)
        total_h = line_height * len(lines)
        x = safe["x"] + margin
        y = safe["y"] + margin
        if plan.normalized_safe_area.anchor.startswith("bottom"):
            y = safe["y"] + safe["h"] - margin - total_h
        elif plan.normalized_safe_area.anchor in {"center", "top_center", "bottom_center"}:
            if plan.normalized_safe_area.anchor == "center":
                y = safe["y"] + (safe["h"] - total_h) // 2
        actual_left = image.width
        actual_top = image.height
        actual_right = 0
        actual_bottom = 0
        for index, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=face)
            width = bbox[2] - bbox[0]
            line_x = x
            if plan.normalized_safe_area.anchor.endswith("center") or plan.normalized_safe_area.anchor == "center":
                line_x = safe["x"] + (safe["w"] - width) // 2
            line_y = y + index * line_height
            draw.text((line_x, line_y), line, font=face, fill=foreground)
            actual_left = min(actual_left, line_x + bbox[0])
            actual_top = min(actual_top, line_y + bbox[1])
            actual_right = max(actual_right, line_x + bbox[2])
            actual_bottom = max(actual_bottom, line_y + bbox[3])
        bounds = {
            "x": max(0, actual_left),
            "y": max(0, actual_top),
            "w": max(0, actual_right - actual_left),
            "h": max(0, actual_bottom - actual_top),
        }
        issues = () if contrast >= 4.5 else ("text_low_contrast",)
        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="PNG", optimize=False)
        return CompositionOutcome(
            True,
            buffer.getvalue(),
            bounds,
            face.size,
            len(lines),
            round(contrast, 4),
            foreground,
            issues,
        )


class TextPixelDeliveryRuntime:
    """Shared post-generation delivery stage with a one-repair ceiling."""

    capability_id = "text_pixel_delivery"

    def __init__(
        self,
        output_store: V3GeneratedOutputStore,
        *,
        font_registry: FontRegistry | None = None,
        ocr_engine: OcrEngine | None = None,
        settings: TextPixelRuntimeSettings | None = None,
        compositor: PillowDeterministicCompositor | None = None,
    ) -> None:
        self.output_store = output_store
        # Accept historical injection arguments for direct-caller compatibility,
        # but deliberately retain none of them. This avoids probing fonts/OCR
        # or preparing a compositor in every new V3 job.
        _ = (font_registry, ocr_engine, settings, compositor)

    def deliver(
        self,
        *,
        plan: CopyRenderPlan | dict[str, Any] | None,
        frozen_activation_plan: dict[str, Any] | None,
        source_output: V3GeneratedOutputRecord | None,
        candidate_id: str,
        asset_id: str,
    ) -> TextPixelDelivery:
        if plan is None:
            return self._result(status="not_requested")
        try:
            render_plan = plan if isinstance(plan, CopyRenderPlan) else CopyRenderPlan.model_validate(plan)
        except Exception as exc:
            return self._result(status="blocked", issue_codes=["copy_render_plan_invalid"], summary=["Text delivery plan needs correction."], details={"error": str(exc)[:240]})
        result = self._result(
            plan=render_plan,
            source_output_id=source_output.output_id if source_output else render_plan.source_lineage.source_output_id,
        )
        # Doc111 retires this renderer for every execution path, including
        # direct callers.  Keep the contract readable but never select a font,
        # compose pixels, repair a layout, or replace the provider asset.
        result.status = "provider_native_required"
        result.issue_codes = ["deterministic_text_pixel_delivery_retired"]
        result.user_visible_summary = ["Final text, when requested, must be generated and reviewed as part of the complete provider image."]
        result.metadata["legacy_read_compatibility"] = True
        return result

        # Historical execution logic is retained below temporarily to keep
        # archived implementation archaeology readable. It is unreachable and
        # must not be re-enabled as a fallback.
        frozen_id = str((frozen_activation_plan or {}).get("plan_id") or "").strip()
        active = {str(item) for item in ((frozen_activation_plan or {}).get("dependency_order") or [])}
        if render_plan.source_lineage.capability_activation_plan_id != frozen_id:
            return self._blocked(result, "frozen_plan_mismatch", "Text delivery stayed blocked because its frozen-plan lineage did not match.")
        if self.capability_id not in active:
            return self._planned_only(result, "Text delivery is recorded but its shared capability was not active in the frozen plan.")
        if not self.settings.enabled:
            return self._planned_only(result, "Text delivery is planned only; the shared runtime gate is off.")
        if source_output is None or not source_output.file_path:
            return self._blocked(result, "source_output_unreadable", "Text delivery needs a readable generated background.")
        # ``source_asset_id`` remains immutable provenance.  A scenario may
        # use a recipe/slot identity that differs from the generated asset ID;
        # Product API resolves one concrete output before this stage runs.
        # A shared generation retry may replace only the background output while
        # retaining this exact frozen plan.  The original output remains in
        # lineage, while the currently reviewed output is recorded per attempt.
        policy = self._policy_eligibility(result, render_plan, source_output)
        if policy is not None:
            return policy
        resolution = self.font_registry.resolve(
            render_plan.locale,
            require_production_approval=self.settings.production_activation_enabled,
        )
        if resolution.font is None:
            return self._blocked(result, resolution.issue_code or "font_unavailable", "Text delivery needs an approved font for this locale.", provenance=resolution.provenance)
        if not self.settings.production_activation_enabled and not self.settings.allow_development_fonts:
            return self._blocked(result, "production_activation_disabled", "Text delivery is gated off until a deployment-approved activation is enabled.", provenance=resolution.provenance)

        outcome = self.compositor.compose(source_output.file_path, render_plan, resolution.font)
        result = self._append_composition(result, outcome, source_output, render_plan, resolution.font, candidate_id, asset_id, stage="composition", attempt_index=0)
        if not outcome.rendered:
            return self._finish_unrendered(result, outcome)
        review = self._review(render_plan, outcome, result.current_output_id)
        result = self._append_review(result, review, attempt_index=0)
        if review["passed"]:
            return self._passed(result)

        if set(review["issues"]).intersection(_REPAIRABLE_ISSUES) and self.settings.max_deterministic_repairs >= 1:
            repaired = self.compositor.compose(source_output.file_path, render_plan, resolution.font, repair=True)
            result = self._append_composition(result, repaired, source_output, render_plan, resolution.font, candidate_id, asset_id, stage="deterministic_repair", attempt_index=1)
            if repaired.rendered:
                repaired_review = self._review(render_plan, repaired, result.current_output_id)
                result = self._append_review(result, repaired_review, attempt_index=1)
                if repaired_review["passed"]:
                    return self._passed(result)
                review = repaired_review
            else:
                review = {"passed": False, "issues": list(repaired.issue_codes), "summary": "The deterministic text repair did not fit the approved area."}
        return self._recovery_exhausted(result, review)

    def deliver_many(
        self,
        *,
        plans: CopyRenderPlanBatch | list[CopyRenderPlan | dict[str, Any]] | dict[str, Any] | None,
        frozen_activation_plan: dict[str, Any] | None,
        source_outputs_by_plan: dict[str, V3GeneratedOutputRecord | None],
        candidate_ids_by_plan: dict[str, str],
        asset_ids_by_plan: dict[str, str],
    ) -> TextPixelDeliveryBatch:
        """Deliver an ordered set of independently bound copy plans.

        The batch is deliberately owned by the shared runtime: templates
        provide plan lineage once and never loop a single-plan renderer,
        reviewer, or retry protocol themselves.
        """

        try:
            if isinstance(plans, CopyRenderPlanBatch):
                plan_batch = plans
            elif isinstance(plans, dict):
                plan_batch = CopyRenderPlanBatch.model_validate(plans)
            else:
                plan_batch = CopyRenderPlanBatch(plans=list(plans or []))
        except Exception as exc:
            invalid = self._result(
                status="blocked",
                issue_codes=["copy_render_plan_batch_invalid"],
                summary=["Text delivery plans need correction."],
                details={"error": str(exc)[:240]},
            )
            return TextPixelDeliveryBatch(
                batch_id=stable_id("text_pixel_delivery_batch", "invalid"),
                deliveries=[invalid],
                metadata={"append_only": True, "invalid_batch": True},
            )

        deliveries: list[TextPixelDelivery] = []
        source_asset_ids_by_plan: dict[str, str] = {}
        for plan in plan_batch.plans:
            asset_id = str(asset_ids_by_plan.get(plan.plan_id) or plan.source_lineage.source_asset_id or "").strip()
            if asset_id:
                source_asset_ids_by_plan[plan.plan_id] = asset_id
            delivery = self.deliver(
                plan=plan,
                frozen_activation_plan=frozen_activation_plan,
                source_output=source_outputs_by_plan.get(plan.plan_id),
                candidate_id=str(candidate_ids_by_plan.get(plan.plan_id) or asset_id or plan.plan_id),
                asset_id=asset_id or plan.plan_id,
            )
            deliveries.append(delivery)
        return TextPixelDeliveryBatch(
            batch_id=stable_id("text_pixel_delivery_batch", plan_batch.batch_id),
            deliveries=deliveries,
            source_asset_ids_by_plan=source_asset_ids_by_plan,
            metadata={
                "append_only": True,
                "copy_render_plan_batch_id": plan_batch.batch_id,
                "delivery_count": len(deliveries),
            },
        )

    def _policy_eligibility(self, result: TextPixelDelivery, plan: CopyRenderPlan, source_output: V3GeneratedOutputRecord) -> TextPixelDelivery | None:
        if plan.text_policy == "forbidden":
            ocr = self.ocr_engine.inspect(source_output.file_path, plan.locale)
            if not ocr.available:
                return self._blocked(result, "ocr_runtime_unavailable", "A text-forbidden delivery needs final-pixel OCR before it can pass.")
            if _normalize_copy(ocr.text, plan.locale):
                return self._correction(result, "forbidden_text_detected", "The text-forbidden image contains visible text that needs correction.")
            result.attempts.append(self._attempt(result, 0, "review", "passed", source_output.output_id, issue_codes=[], details={"ocr_engine": ocr.engine_id, "final_pixel_review": True}))
            result.review_passed = True
            result.status = "passed"
            result.user_visible_summary = ["The final image passed the text-forbidden check."]
            result.gate_c_eligible = bool(self.settings.production_activation_enabled)
            return result
        if plan.claim_review_state == "blocked":
            return self._correction(result, "copy_claim_blocked", "Blocked copy was omitted and needs an approved correction.")
        if plan.claim_review_state == "requires_review":
            return self._correction(result, "copy_requires_review", "Copy needs review before final pixels can be delivered.")
        if plan.text_policy == "optional" and not plan.expected_copy:
            result.status = "not_requested"
            result.review_passed = True
            result.user_visible_summary = ["No optional text was requested for this delivery."]
            return result
        if not plan.expected_copy:
            return self._correction(result, "required_copy_missing", "Approved copy is required before text pixels can be delivered.")
        if plan.locale not in _SUPPORTED_LOCALES:
            return self._blocked(result, "unsupported_locale", "This text locale is not available in the shared runtime.")
        return None

    def _append_composition(self, result: TextPixelDelivery, outcome: CompositionOutcome, source: V3GeneratedOutputRecord, plan: CopyRenderPlan, font: LicensedFont, candidate_id: str, asset_id: str, *, stage: str, attempt_index: int) -> TextPixelDelivery:
        derived: V3GeneratedOutputRecord | None = None
        if outcome.rendered and outcome.image_bytes:
            encoded = base64.b64encode(outcome.image_bytes).decode("ascii")
            derived = self.output_store.save_base64_output(
                job_id=source.job_id,
                candidate_id=stable_id("text_pixel_candidate", candidate_id, plan.plan_id, attempt_index),
                asset_id=asset_id,
                provider="v3_deterministic_text_compositor",
                model=self.compositor.renderer_id,
                encoded_image=encoded,
                mime_type="image/png",
                output_format="png",
                metadata={
                    "text_pixel_delivery": True,
                    "text_pixel_source_output_id": source.output_id,
                    "copy_render_plan_id": plan.plan_id,
                    "capability_activation_plan_id": plan.source_lineage.capability_activation_plan_id,
                    "renderer": self.compositor.renderer_id,
                    "font": font.provenance(),
                    "geometry": {"safe_area": plan.normalized_safe_area.model_dump(mode="json"), "rendered_bounds_px": outcome.bounds_px},
                    "composition_attempt_index": attempt_index,
                    "composition_stage": stage,
                    "append_only": True,
                },
            )
            result.rendered = True
            result.current_output_id = derived.output_id
            result.artifact_lineage = {
                "renderer": self.compositor.renderer_id,
                "font": font.provenance(),
                "source_output_id": source.output_id,
                "derived_output_id": derived.output_id,
                "safe_area": plan.normalized_safe_area.model_dump(mode="json"),
                "rendered_bounds_px": outcome.bounds_px,
            }
        result.attempts.append(
            self._attempt(
                result,
                attempt_index,
                stage,
                "rendered" if outcome.rendered else "blocked",
                source.output_id,
                derived.output_id if derived else None,
                issue_codes=list(outcome.issue_codes),
                details={
                    "line_count": outcome.line_count,
                    "font_size_px": outcome.font_size_px,
                    "contrast_ratio": outcome.contrast_ratio,
                    "foreground_color": outcome.foreground_color,
                    "append_only": True,
                },
            )
        )
        return result

    def _review(self, plan: CopyRenderPlan, outcome: CompositionOutcome, output_id: str | None) -> dict[str, Any]:
        record = self.output_store.get_output(output_id or "") if output_id else None
        if record is None:
            return {"passed": False, "issues": ["derived_output_unreadable"], "summary": "The composed text image could not be reviewed."}
        ocr = self.ocr_engine.inspect(record.file_path, plan.locale)
        issues = list(outcome.issue_codes)
        if not ocr.available:
            issues.append("ocr_runtime_unavailable")
        elif _normalize_copy(ocr.text, plan.locale) != _normalize_copy(plan.expected_copy or "", plan.locale):
            issues.append("ocr_text_mismatch")
        if not _inside_safe_area(outcome.bounds_px or {}, plan.normalized_safe_area.as_pixel_box(record.width or 1, record.height or 1)):
            issues.append("safe_area_violation")
        if (outcome.contrast_ratio or 0.0) < self.settings.min_contrast_ratio:
            issues.append("text_low_contrast")
        issues = _dedupe(issues)
        return {
            "passed": not issues,
            "issues": issues,
            "summary": "Final text pixels passed OCR and layout review." if not issues else "Final text pixels need review or correction.",
            "details": {"ocr_engine": ocr.engine_id, "ocr_text": ocr.text, "ocr_confidence": ocr.confidence, "final_pixel_review": True},
        }

    def _append_review(self, result: TextPixelDelivery, review: dict[str, Any], *, attempt_index: int) -> TextPixelDelivery:
        result.attempts.append(self._attempt(result, attempt_index, "review", "passed" if review["passed"] else "failed", result.source_output_id, result.current_output_id, issue_codes=review["issues"], details=review.get("details") or {}))
        result.issue_codes = _dedupe([*result.issue_codes, *review["issues"]])
        result.user_visible_summary = [str(review["summary"])]
        return result

    def _finish_unrendered(self, result: TextPixelDelivery, outcome: CompositionOutcome) -> TextPixelDelivery:
        issues = _dedupe([*result.issue_codes, *outcome.issue_codes])
        if set(issues).intersection(_COPY_CORRECTION_ISSUES):
            return self._correction(result, issues[0], "Text delivery needs a corrected copy plan or supported font.")
        return self._blocked(result, issues[0] if issues else "composition_failed", "Text delivery could not compose final pixels.")

    def _recovery_exhausted(self, result: TextPixelDelivery, review: dict[str, Any]) -> TextPixelDelivery:
        issues = _dedupe([*result.issue_codes, *review.get("issues", [])])
        result.issue_codes = issues
        if set(issues).intersection(_COPY_CORRECTION_ISSUES):
            return self._correction(result, next(item for item in issues if item in _COPY_CORRECTION_ISSUES), "Final text pixels need a copy correction; no generation retry was started.")
        result.status = "repair_exhausted"
        result.review_passed = False
        result.recovery = {"deterministic_repair_attempts": 1, "append_only": True, "generation_retry": self._generation_retry_signal(result, issues)}
        result.attempts.append(self._attempt(result, 1, "generation_retry_signal", "eligible" if result.recovery["generation_retry"]["eligible"] else "not_eligible", result.source_output_id, result.current_output_id, issue_codes=issues, details=result.recovery["generation_retry"]))
        result.user_visible_summary = ["One deterministic text repair was retained; the final text delivery still needs review."]
        return result

    def _generation_retry_signal(self, result: TextPixelDelivery, issues: list[str]) -> dict[str, Any]:
        eligible = "text_low_contrast" in issues
        return {
            "eligible": eligible,
            "reason_codes": ["text_background_readability_failure"] if eligible else [],
            "retry_patch": {
                "composition_repair": ["create a calmer, high-separation background in the approved text safe area while preserving the requested subject"],
                "negative_additions": ["busy texture or unreadable detail in the approved text safe area"],
            } if eligible else {},
            "frozen_plan_required": True,
            "append_only": True,
        }

    def _result(self, *, plan: CopyRenderPlan | None = None, status: str = "not_requested", source_output_id: str | None = None, issue_codes: list[str] | None = None, summary: list[str] | None = None, details: dict[str, Any] | None = None) -> TextPixelDelivery:
        return TextPixelDelivery(
            delivery_id=stable_id("text_pixel_delivery", plan.plan_id if plan else "none", source_output_id or "none"),
            copy_render_plan_id=plan.plan_id if plan else None,
            status=status,
            text_policy=plan.text_policy if plan else None,
            locale=plan.locale if plan else None,
            source_output_id=source_output_id,
            issue_codes=list(issue_codes or []),
            user_visible_summary=list(summary or []),
            metadata={
                "details": details or {},
                "production_activation_enabled": False,
                "append_only": True,
                "deterministic_text_pixel_delivery_retired": True,
            },
        )

    def _attempt(self, result: TextPixelDelivery, index: int, stage: str, status: str, source_output_id: str | None, derived_output_id: str | None = None, *, issue_codes: list[str], details: dict[str, Any]) -> TextPixelDeliveryAttempt:
        return TextPixelDeliveryAttempt(
            attempt_id=stable_id("text_pixel_attempt", result.delivery_id, index, stage, status, derived_output_id or ""),
            attempt_index=index,
            stage=stage,
            status=status,
            source_output_id=source_output_id,
            derived_output_id=derived_output_id,
            issue_codes=_dedupe(issue_codes),
            details=details,
        )

    def _blocked(self, result: TextPixelDelivery, issue: str, message: str, *, provenance: dict[str, Any] | None = None) -> TextPixelDelivery:
        result.status = "blocked"
        result.issue_codes = _dedupe([*result.issue_codes, issue])
        result.artifact_lineage = {**result.artifact_lineage, **({"font": provenance} if provenance else {})}
        result.user_visible_summary = [message]
        return result

    def _correction(self, result: TextPixelDelivery, issue: str, message: str) -> TextPixelDelivery:
        result.status = "requires_copy_correction"
        result.issue_codes = _dedupe([*result.issue_codes, issue])
        result.user_visible_summary = [message]
        return result

    def _planned_only(self, result: TextPixelDelivery, message: str) -> TextPixelDelivery:
        result.status = "planned_only"
        result.user_visible_summary = [message]
        return result

    def _passed(self, result: TextPixelDelivery) -> TextPixelDelivery:
        result.status = "passed"
        result.review_passed = True
        result.issue_codes = []
        result.gate_c_eligible = bool(self.settings.production_activation_enabled)
        result.recovery = {"deterministic_repair_attempts": max((item.attempt_index for item in result.attempts if item.stage == "deterministic_repair"), default=0), "append_only": True}
        result.user_visible_summary = ["Final text pixels passed OCR, layout, contrast, and copy-policy review."]
        return result


def _wrap_text(draw: Any, text: str, face: Any, max_width: int, locale: str | None) -> list[str]:
    tokens = list(text) if locale == "zh-CN" else text.split(" ")
    separator = "" if locale == "zh-CN" else " "
    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = token if not current else f"{current}{separator}{token}"
        if current and draw.textbbox((0, 0), candidate, font=face)[2] > max_width:
            lines.append(current)
            current = token
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [text]


def _font_supports_text(path: str, text: str) -> bool:
    try:
        from PIL import ImageFont
        face = ImageFont.truetype(path, size=32)
        replacement = bytes(face.getmask("\ufffd"))
        for character in text:
            if character.isspace():
                continue
            glyph = bytes(face.getmask(character))
            if glyph == replacement and character != "\ufffd":
                return False
        return True
    except Exception:
        return False


def _average_luminance(image: Any, box: dict[str, int]) -> float:
    crop = image.crop((box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"])).convert("RGB")
    pixels = list(crop.getdata())
    if not pixels:
        return 0.0
    return sum(_luminance(pixel) for pixel in pixels) / len(pixels)


def _best_contrast_color(image: Any, box: dict[str, int]) -> str:
    background = _average_luminance(image, box)
    return "#000000" if _contrast_ratio(background, 0.0) >= _contrast_ratio(background, 1.0) else "#ffffff"


def _parse_color(value: str) -> tuple[int, int, int]:
    text = str(value or "#000000").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(part * 2 for part in text)
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except Exception:
        return 0, 0, 0


def _luminance(color: tuple[int, int, int]) -> float:
    values = []
    for channel in color:
        scaled = channel / 255.0
        values.append(scaled / 12.92 if scaled <= 0.04045 else ((scaled + 0.055) / 1.055) ** 2.4)
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def _contrast_ratio(left: float, right: float) -> float:
    high, low = max(left, right), min(left, right)
    return (high + 0.05) / (low + 0.05)


def _inside_safe_area(bounds: dict[str, int], safe: dict[str, int]) -> bool:
    if not bounds or bounds.get("w", 0) <= 0 or bounds.get("h", 0) <= 0:
        return False
    return (
        bounds["x"] >= safe["x"]
        and bounds["y"] >= safe["y"]
        and bounds["x"] + bounds["w"] <= safe["x"] + safe["w"]
        and bounds["y"] + bounds["h"] <= safe["y"] + safe["h"]
    )


def _normalize_copy(value: str, locale: str | None) -> str:
    text = "".join(str(value or "").casefold().split())
    return text.replace("，", ",").replace("。", ".") if locale == "zh-CN" else text


def _file_sha256(path: Path) -> str | None:
    try:
        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}
