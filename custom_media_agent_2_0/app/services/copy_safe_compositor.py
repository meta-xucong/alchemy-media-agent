"""Optional deterministic V2 text overlay for information-dense artifacts."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any


def apply_deterministic_text_overlay(
    content: bytes,
    *,
    delivery_contract: dict[str, Any] | None,
    output_format: str,
) -> tuple[bytes, dict[str, Any]]:
    """Overlay only explicit, pre-approved V2 text slots.

    The creative pipeline must supply concrete slot geometry and an explicit
    font path.  This function intentionally refuses to guess a location or
    font, because guessing would reintroduce the same text-fidelity problem it
    exists to prevent.
    """

    contract = delivery_contract if isinstance(delivery_contract, dict) else {}
    overlay = contract.get("deterministic_text_overlay") if isinstance(contract.get("deterministic_text_overlay"), dict) else {}
    items = [item for item in overlay.get("items", []) if isinstance(item, dict)]
    if not items:
        return content, {"applied": False, "reason": "no_explicit_overlay_slots", "verified_field_ids": []}
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ModuleNotFoundError:
        return content, {"applied": False, "reason": "pillow_unavailable", "verified_field_ids": []}

    try:
        with Image.open(io.BytesIO(content)) as source:
            image = source.convert("RGBA")
        draw = ImageDraw.Draw(image)
        verified: list[str] = []
        for item in items:
            text = str(item.get("text") or "").strip()
            field_id = str(item.get("field_id") or "").strip()
            box = item.get("box")
            font_path = Path(str(item.get("font_path") or ""))
            if not text or not field_id or not isinstance(box, list) or len(box) != 4 or not font_path.is_file():
                return content, {"applied": False, "reason": "overlay_slot_invalid", "verified_field_ids": verified}
            x, y, width, height = [int(value) for value in box]
            if width <= 0 or height <= 0:
                return content, {"applied": False, "reason": "overlay_box_invalid", "verified_field_ids": verified}
            size = max(8, min(int(item.get("font_size") or height), height))
            font = ImageFont.truetype(str(font_path), size=size)
            color = item.get("color") or "#111111"
            draw.multiline_text((x, y), text, fill=color, font=font, spacing=max(1, size // 6))
            verified.append(field_id)
        target = io.BytesIO()
        fmt = "JPEG" if output_format.lower() in {"jpg", "jpeg"} else output_format.upper()
        if fmt == "JPEG":
            image.convert("RGB").save(target, format=fmt, quality=95)
        else:
            image.save(target, format=fmt)
        return target.getvalue(), {"applied": True, "reason": None, "verified_field_ids": verified}
    except (OSError, ValueError, TypeError):
        return content, {"applied": False, "reason": "overlay_render_failed", "verified_field_ids": []}
