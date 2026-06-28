"""Deterministic uploaded asset analysis and role suggestion."""

from __future__ import annotations

from collections import Counter
from colorsys import rgb_to_hsv
from pathlib import Path
from typing import Any

from .base import SharedCapabilityModule
from .contracts import (
    AssetRole,
    CapabilityConstraint,
    CapabilityInput,
    CapabilityResult,
    CapabilityStatus,
    CapabilityTargetStage,
    CapabilityWarning,
)
from .utils import role_value


class AssetRoleAnalyzer(SharedCapabilityModule):
    module_id = "asset_role_analyzer"
    version = "v3_shared_capability_001"
    order = 10

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        if not capability_input.uploaded_assets:
            return CapabilityResult(
                module_id=self.module_id,
                version=self.version,
                status=CapabilityStatus.SKIPPED,
                audit_trail=["no uploaded assets to analyze"],
            )

        analyses: list[dict[str, Any]] = []
        warnings: list[CapabilityWarning] = []
        constraints: list[CapabilityConstraint] = []

        for asset in capability_input.uploaded_assets:
            analysis, asset_warnings = self._analyze_asset(asset)
            analyses.append(analysis)
            warnings.extend(asset_warnings)
            constraints.extend(self._constraints_for_analysis(analysis))

        status = CapabilityStatus.WARNING if warnings else CapabilityStatus.SUCCESS
        confidence = 0.78 if analyses and not warnings else 0.55 if analyses else 0.0
        return CapabilityResult(
            module_id=self.module_id,
            version=self.version,
            status=status,
            confidence=confidence,
            facts={"asset_analyses": analyses},
            constraints=constraints,
            warnings=warnings,
            audit_trail=[f"analyzed {len(analyses)} uploaded asset(s)"],
        )

    def _analyze_asset(self, asset) -> tuple[dict[str, Any], list[CapabilityWarning]]:
        role = asset.role or self._suggest_role(asset.filename or asset.asset_id, asset.file_path, asset.metadata)
        path = Path(asset.file_path) if asset.file_path else None
        warnings: list[CapabilityWarning] = []
        base = {
            "asset_id": asset.asset_id,
            "role": role.value,
            "filename": asset.filename,
            "file_path": asset.file_path,
            "uri": asset.uri,
            "identity_requirements": self._identity_requirements(role),
            "provider_input_required": role
            in {
                AssetRole.PRODUCT_REFERENCE,
                AssetRole.LOGO_REFERENCE,
                AssetRole.FACE_REFERENCE,
                AssetRole.BACKGROUND_REFERENCE,
            },
        }
        if path is None or not path.exists():
            warnings.append(
                CapabilityWarning(
                    code="asset_file_missing",
                    message=f"Uploaded asset '{asset.asset_id}' has no readable local file.",
                    asset_id=asset.asset_id,
                )
            )
            return {**base, "stored": False, "style_signals": [], "composition": {}}, warnings

        try:
            from PIL import Image, ImageOps, ImageStat

            with Image.open(path) as raw:
                image = ImageOps.exif_transpose(raw)
                width, height = image.size
                rgb = self._flatten_to_rgb(image)
                sample = rgb.copy()
                sample.thumbnail((96, 96), Image.Resampling.LANCZOS)
                palette = self._palette(sample)
                brightness = self._brightness(sample, ImageStat)
                contrast = self._contrast(sample, ImageStat)
                accent_colors = self._accent_colors(palette)
                style_signals = self._style_signals(
                    brightness=brightness,
                    contrast=contrast,
                    palette=palette,
                    accent_colors=accent_colors,
                    role=role,
                )
                if width < 256 or height < 256:
                    warnings.append(
                        CapabilityWarning(
                            code="asset_resolution_low",
                            message=f"Uploaded asset '{asset.asset_id}' is small at {width}x{height}.",
                            asset_id=asset.asset_id,
                        )
                    )
                return (
                    {
                        **base,
                        "stored": True,
                        "width": width,
                        "height": height,
                        "composition": {
                            "width": width,
                            "height": height,
                            "orientation": self._orientation(width, height),
                            "aspect_ratio": round(width / height, 3) if height else None,
                        },
                        "palette": palette[:8],
                        "brightness": brightness,
                        "contrast": contrast,
                        "style_signals": style_signals,
                    },
                    warnings,
                )
        except Exception as exc:
            warnings.append(
                CapabilityWarning(
                    code="asset_vision_failed",
                    message=f"Local visual analysis failed for '{asset.asset_id}': {type(exc).__name__}.",
                    asset_id=asset.asset_id,
                    metadata={"exception": str(exc)[:180]},
                )
            )
            return {**base, "stored": True, "style_signals": [], "composition": {}}, warnings

    def _constraints_for_analysis(self, analysis: dict[str, Any]) -> list[CapabilityConstraint]:
        role = analysis.get("role")
        asset_id = analysis.get("asset_id")
        constraints: list[CapabilityConstraint] = []
        if role == AssetRole.PRODUCT_REFERENCE.value:
            constraints.append(
                CapabilityConstraint(
                    target_stage=CapabilityTargetStage.PROMPT_COMPILATION,
                    constraint_type="product_identity_preservation",
                    strength="strong",
                    value={
                        "asset_id": asset_id,
                        "requirements": analysis.get("identity_requirements", []),
                    },
                    source=self.module_id,
                )
            )
        if role == AssetRole.LOGO_REFERENCE.value:
            constraints.append(
                CapabilityConstraint(
                    target_stage=CapabilityTargetStage.EVALUATION,
                    constraint_type="logo_exactness_review",
                    strength="strong",
                    value={"asset_id": asset_id, "review": "logo shape and brand mark must not be distorted"},
                    source=self.module_id,
                )
            )
        if role == AssetRole.NEGATIVE_REFERENCE.value:
            constraints.append(
                CapabilityConstraint(
                    target_stage=CapabilityTargetStage.PROMPT_COMPILATION,
                    constraint_type="negative_visual_reference",
                    strength="medium",
                    value={"asset_id": asset_id},
                    source=self.module_id,
                )
            )
        return constraints

    def _suggest_role(self, name: str, file_path: str | None, metadata: dict[str, Any]) -> AssetRole:
        explicit = str(metadata.get("role") or "").strip()
        if explicit:
            return self._normalize_role(explicit)
        lower = name.lower()
        if any(token in lower for token in ["logo", "brand", "mark"]):
            return AssetRole.LOGO_REFERENCE
        if any(token in lower for token in ["face", "portrait", "headshot"]):
            return AssetRole.FACE_REFERENCE
        if any(token in lower for token in ["background", "scene", "backdrop"]):
            return AssetRole.BACKGROUND_REFERENCE
        if any(token in lower for token in ["product", "subject", "sku", "item"]):
            return AssetRole.PRODUCT_REFERENCE
        if any(token in lower for token in ["style", "mood"]):
            return AssetRole.STYLE_REFERENCE
        if any(token in lower for token in ["composition", "layout", "frame"]):
            return AssetRole.COMPOSITION_REFERENCE
        if any(token in lower for token in ["color", "palette"]):
            return AssetRole.COLOR_REFERENCE
        if any(token in lower for token in ["negative", "avoid"]):
            return AssetRole.NEGATIVE_REFERENCE
        return AssetRole.PRODUCT_REFERENCE

    def _normalize_role(self, value: str) -> AssetRole:
        mapping = {
            "subject_reference": AssetRole.PRODUCT_REFERENCE,
            "product_reference": AssetRole.PRODUCT_REFERENCE,
            "style_reference": AssetRole.STYLE_REFERENCE,
            "logo_reference": AssetRole.LOGO_REFERENCE,
            "face_reference": AssetRole.FACE_REFERENCE,
            "background_reference": AssetRole.BACKGROUND_REFERENCE,
            "composition_reference": AssetRole.COMPOSITION_REFERENCE,
            "color_reference": AssetRole.COLOR_REFERENCE,
            "negative_reference": AssetRole.NEGATIVE_REFERENCE,
        }
        return mapping.get(value, AssetRole.UNKNOWN_REFERENCE)

    def _identity_requirements(self, role: AssetRole) -> list[str]:
        if role == AssetRole.PRODUCT_REFERENCE:
            return ["preserve visible product identity", "preserve product shape and key proportions"]
        if role == AssetRole.LOGO_REFERENCE:
            return ["preserve logo shape", "do not invent unreadable brand text"]
        if role == AssetRole.FACE_REFERENCE:
            return ["preserve face identity cues", "avoid identity drift"]
        if role == AssetRole.BACKGROUND_REFERENCE:
            return ["preserve requested background environment when compatible"]
        if role == AssetRole.COMPOSITION_REFERENCE:
            return ["preserve camera angle and spatial layout as an abstract guide"]
        if role == AssetRole.COLOR_REFERENCE:
            return ["preserve key palette and accent-color rhythm"]
        if role == AssetRole.NEGATIVE_REFERENCE:
            return ["avoid visual traits from this reference"]
        return ["use as soft aesthetic evidence only"]

    def _flatten_to_rgb(self, image):
        from PIL import Image

        if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
            rgba = image.convert("RGBA")
            canvas = Image.new("RGB", rgba.size, (255, 255, 255))
            canvas.paste(rgba, mask=rgba.getchannel("A"))
            return canvas
        return image.convert("RGB")

    def _palette(self, image, limit: int = 12) -> list[dict[str, Any]]:
        resized = image.convert("RGB").resize((32, 32))
        raw = resized.tobytes()
        pixels = [(raw[index], raw[index + 1], raw[index + 2]) for index in range(0, len(raw), 3)]
        if not pixels:
            return []
        counts = Counter((self._bucket(r), self._bucket(g), self._bucket(b)) for r, g, b in pixels)
        total = sum(counts.values()) or 1
        return [
            {"hex": f"#{r:02x}{g:02x}{b:02x}", "rgb": [r, g, b], "ratio": round(count / total, 3)}
            for (r, g, b), count in counts.most_common(limit)
        ]

    def _bucket(self, value: int) -> int:
        return max(0, min(255, int(round(value / 32) * 32)))

    def _brightness(self, image, image_stat) -> float:
        stat = image_stat.Stat(image.convert("L"))
        return round((stat.mean[0] if stat.mean else 0) / 255.0, 3)

    def _contrast(self, image, image_stat) -> float:
        stat = image_stat.Stat(image.convert("L"))
        return round((stat.stddev[0] if stat.stddev else 0) / 128.0, 3)

    def _accent_colors(self, palette: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(palette) <= 1:
            return []
        accents: list[dict[str, Any]] = []
        dominant = palette[0].get("rgb") or [0, 0, 0]
        for item in palette[1:]:
            rgb = item.get("rgb") or [0, 0, 0]
            r, g, b = [int(value) for value in rgb[:3]]
            _, saturation, _ = rgb_to_hsv(r / 255, g / 255, b / 255)
            distance = min((((r - dominant[0]) ** 2 + (g - dominant[1]) ** 2 + (b - dominant[2]) ** 2) ** 0.5) / 441.673, 1.0)
            if float(item.get("ratio") or 0) >= 0.006 and saturation >= 0.25 and distance >= 0.18:
                accents.append(item)
            if len(accents) >= 4:
                break
        return accents

    def _style_signals(
        self,
        *,
        brightness: float,
        contrast: float,
        palette: list[dict[str, Any]],
        accent_colors: list[dict[str, Any]],
        role: AssetRole,
    ) -> list[str]:
        signals: list[str] = []
        if brightness >= 0.62:
            signals.append("bright clean lighting")
        elif brightness <= 0.32:
            signals.append("low-key dark lighting")
        if contrast >= 0.5:
            signals.append("high contrast visual structure")
        elif contrast <= 0.24:
            signals.append("soft low-contrast palette")
        if palette:
            signals.append(f"dominant color {palette[0]['hex']}")
        if accent_colors:
            signals.append("distinctive accent colors " + ", ".join(item["hex"] for item in accent_colors[:3]))
        if role_value(role) in {AssetRole.LOGO_REFERENCE.value, AssetRole.PRODUCT_REFERENCE.value, AssetRole.FACE_REFERENCE.value}:
            signals.append("identity preservation required")
        return signals

    def _orientation(self, width: int, height: int) -> str:
        if not width or not height:
            return "unknown"
        ratio = width / height
        if ratio > 1.12:
            return "landscape"
        if ratio < 0.88:
            return "portrait"
        return "square"
