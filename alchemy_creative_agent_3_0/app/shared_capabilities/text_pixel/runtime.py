"""Read-only compatibility adapter for retired deterministic text delivery.

Doc111 requires text to be generated as part of the provider-native complete
image.  This module intentionally contains no font loading, OCR, raster
composition, geometry application, or local retry implementation.  Old stored
contracts remain decodable and return an explicit migration result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...creative_core.rules import stable_id
from .contracts import CopyRenderPlan, CopyRenderPlanBatch, TextPixelDelivery, TextPixelDeliveryAttempt, TextPixelDeliveryBatch


@dataclass(frozen=True)
class LicensedFont:
    """Historical record shape only; no font can be selected or loaded."""

    font_id: str
    version: str
    file_path: str
    supported_locales: tuple[str, ...]
    license_id: str
    expected_sha256: str | None = None
    production_approved: bool = False

    def provenance(self) -> dict[str, Any]:
        return {
            "font_id": self.font_id,
            "font_version": self.version,
            "font_path": self.file_path,
            "font_license_id": self.license_id,
            "deterministic_text_pixel_delivery_retired": True,
        }


@dataclass(frozen=True)
class FontResolution:
    font: LicensedFont | None
    issue_code: str | None = "deterministic_text_pixel_delivery_retired"
    provenance: dict[str, Any] | None = None


class FontRegistry:
    """Compatibility facade that can never activate a local font path."""

    def __init__(self, fonts: list[LicensedFont] | None = None) -> None:
        self.fonts = list(fonts or [])

    @classmethod
    def from_environment(cls) -> "FontRegistry":
        return cls()

    def resolve(self, locale: str | None, *, require_production_approval: bool) -> FontResolution:
        del locale, require_production_approval
        return FontResolution(None)


@dataclass(frozen=True)
class TextPixelRuntimeSettings:
    enabled: bool = False
    production_activation_enabled: bool = False
    allow_development_fonts: bool = False
    min_contrast_ratio: float = 4.5
    max_deterministic_repairs: int = 0

    @classmethod
    def from_environment(cls) -> "TextPixelRuntimeSettings":
        return cls()


@dataclass(frozen=True)
class OcrResult:
    available: bool
    engine_id: str
    text: str = ""
    confidence: float | None = None
    details: dict[str, Any] | None = None


class StaticOcrEngine:
    """Deprecated test facade; it never inspects pixels."""

    def __init__(self, text: str = "", *, available: bool = False, confidence: float | None = None) -> None:
        self.text, self.available, self.confidence, self.paths = text, available, confidence, []

    def inspect(self, image_path: str, locale: str | None) -> OcrResult:
        del image_path, locale
        return OcrResult(False, "retired_text_pixel_ocr", details={"deterministic_text_pixel_delivery_retired": True})


class TesseractOcrEngine(StaticOcrEngine):
    """Compatibility name only; no local OCR process is launched."""

    def __init__(self, executable: str | None = None) -> None:
        del executable
        super().__init__()


class TextPixelDeliveryRuntime:
    """Return the Doc111 provider-native requirement for historical inputs."""

    capability_id = "text_pixel_delivery"

    def __init__(self, output_store: Any | None = None, **_: Any) -> None:
        self.output_store = output_store

    def deliver(
        self,
        *,
        plan: CopyRenderPlan | dict[str, Any] | None,
        frozen_activation_plan: Any = None,
        source_output: Any = None,
        candidate_id: str | None = None,
        asset_id: str | None = None,
    ) -> TextPixelDelivery:
        del frozen_activation_plan, candidate_id
        try:
            parsed = plan if isinstance(plan, CopyRenderPlan) else CopyRenderPlan.model_validate(plan)
        except Exception:
            return TextPixelDelivery(
                delivery_id=stable_id("text_pixel_delivery", "invalid"),
                status="blocked",
                issue_codes=["copy_render_plan_invalid", "deterministic_text_pixel_delivery_retired"],
                user_visible_summary=["Historical text-render plans cannot activate local text delivery."],
                metadata={"deterministic_text_pixel_delivery_retired": True},
            )
        source_output_id = str(getattr(source_output, "output_id", "") or parsed.source_lineage.source_output_id or "") or None
        return self._provider_native_required(parsed, source_output_id, asset_id)

    def deliver_many(
        self,
        *,
        plans: CopyRenderPlanBatch | list[CopyRenderPlan | dict[str, Any]] | dict[str, Any] | None,
        frozen_activation_plan: Any = None,
        source_outputs_by_plan: dict[str, Any] | None = None,
        candidate_ids_by_plan: dict[str, str] | None = None,
        asset_ids_by_plan: dict[str, str] | None = None,
    ) -> TextPixelDeliveryBatch:
        del frozen_activation_plan, candidate_ids_by_plan
        try:
            batch = (
                plans
                if isinstance(plans, CopyRenderPlanBatch)
                else CopyRenderPlanBatch.model_validate(plans)
                if isinstance(plans, dict)
                else CopyRenderPlanBatch(plans=list(plans or []))
            )
        except Exception:
            return TextPixelDeliveryBatch(
                batch_id=stable_id("text_pixel_delivery_batch", "invalid"),
                deliveries=[
                    TextPixelDelivery(
                        delivery_id=stable_id("text_pixel_delivery", "invalid"),
                        status="blocked",
                        issue_codes=["copy_render_plan_batch_invalid", "deterministic_text_pixel_delivery_retired"],
                        metadata={"deterministic_text_pixel_delivery_retired": True},
                    )
                ],
                metadata={"deterministic_text_pixel_delivery_retired": True},
            )
        source_outputs_by_plan = source_outputs_by_plan or {}
        asset_ids_by_plan = asset_ids_by_plan or {}
        deliveries: list[TextPixelDelivery] = []
        mappings: dict[str, str] = {}
        for plan in batch.plans:
            source = source_outputs_by_plan.get(plan.plan_id)
            asset_id = asset_ids_by_plan.get(plan.plan_id) or plan.source_lineage.source_asset_id
            deliveries.append(self._provider_native_required(plan, str(getattr(source, "output_id", "") or "") or None, asset_id))
            if asset_id:
                mappings[plan.plan_id] = str(asset_id)
        return TextPixelDeliveryBatch(
            batch_id=stable_id("text_pixel_delivery_batch", batch.batch_id, "provider_native_required"),
            deliveries=deliveries,
            source_asset_ids_by_plan=mappings,
            metadata={"deterministic_text_pixel_delivery_retired": True, "provider_native_required": True},
        )

    def _provider_native_required(
        self,
        plan: CopyRenderPlan,
        source_output_id: str | None,
        asset_id: str | None,
    ) -> TextPixelDelivery:
        return TextPixelDelivery(
            delivery_id=stable_id("text_pixel_delivery", plan.plan_id, source_output_id or asset_id or "none"),
            copy_render_plan_id=plan.plan_id,
            status="provider_native_required",
            text_policy=plan.text_policy,
            locale=plan.locale,
            source_output_id=source_output_id,
            artifact_lineage={"source_asset_id": asset_id or plan.source_lineage.source_asset_id},
            attempts=[
                TextPixelDeliveryAttempt(
                    attempt_id=stable_id("text_pixel_attempt", plan.plan_id, "retired"),
                    attempt_index=0,
                    stage="eligibility",
                    status="provider_native_required",
                    source_output_id=source_output_id,
                    issue_codes=["deterministic_text_pixel_delivery_retired"],
                )
            ],
            issue_codes=["deterministic_text_pixel_delivery_retired"],
            user_visible_summary=["Use a provider-native complete image for any requested text."],
            metadata={"deterministic_text_pixel_delivery_retired": True, "provider_native_required": True},
        )
