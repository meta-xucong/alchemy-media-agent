from __future__ import annotations

import base64
import io
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

from app.providers.images.base import (
    V2ImageProviderCapabilities,
    V2ImageProviderOutput,
    V2ImageProviderRequest,
    V2ImageProviderResult,
)


class V2MockImageProvider:
    name = "mock_image"

    async def capabilities(self) -> V2ImageProviderCapabilities:
        return V2ImageProviderCapabilities(
            provider=self.name,
            configured=True,
            models=["mock-image-v2-native"],
            operations=["generate", "image_reference"],
            input_roles=[
                "style_reference",
                "subject_reference",
                "logo_reference",
                "face_reference",
                "background_reference",
                "composition_reference",
                "color_reference",
            ],
            limits={"max_batch": 8, "max_reference_images": 5},
            is_mock=True,
        )

    async def generate(self, request: V2ImageProviderRequest) -> V2ImageProviderResult:
        plan = request.prompt_plan
        count = _count(plan)
        width, height = _dimensions(plan)
        outputs: list[V2ImageProviderOutput] = []
        for index in range(count):
            encoded = _render_mock_image(
                prompt=plan.prompt,
                width=width or 1024,
                height=height or 1024,
                index=index + 1,
                reference_count=len(request.input_images),
            )
            outputs.append(
                V2ImageProviderOutput(
                    b64_json=encoded,
                    mime_type="image/png",
                    format="png",
                    width=width,
                    height=height,
                    metadata={
                        "mock": True,
                        "variant_index": index + 1,
                        "reference_image_count": len(request.input_images),
                        "api_operation": "v2.mock.generate",
                    },
                )
            )
        return V2ImageProviderResult(
            provider=self.name,
            model="mock-image-v2-native",
            outputs=outputs,
            raw_response_summary={"output_count": len(outputs), "native_v2": True},
        )


def _render_mock_image(*, prompt: str, width: int, height: int, index: int, reference_count: int) -> str:
    image = Image.new("RGB", (width, height), (245, 241, 233))
    draw = ImageDraw.Draw(image)
    accent = (38, 92, 73)
    draw.rectangle((0, 0, width, max(8, height // 90)), fill=accent)
    draw.rectangle((0, height - max(8, height // 90), width, height), fill=accent)
    font = ImageFont.load_default()
    title = f"V2 Native Mock #{index}"
    subtitle = f"input images: {reference_count}"
    draw.text((width * 0.08, height * 0.12), title, fill=(28, 28, 28), font=font)
    draw.text((width * 0.08, height * 0.16), subtitle, fill=accent, font=font)
    y = int(height * 0.24)
    for line in wrap(prompt.replace("\n", " "), width=56)[:12]:
        draw.text((width * 0.08, y), line, fill=(52, 48, 43), font=font)
        y += 20
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return base64.b64encode(output.getvalue()).decode("ascii")


def _count(plan) -> int:
    try:
        value = int(plan.provider_parameters.get("count", 1))
    except Exception:
        value = 1
    return max(1, min(value, 8))


def _dimensions(plan) -> tuple[int | None, int | None]:
    size = _size(plan)
    try:
        width, height = size.lower().split("x", 1)
        return int(width), int(height)
    except (AttributeError, ValueError):
        return None, None


def _size(plan) -> str:
    params = plan.provider_parameters or {}
    size = params.get("size") or params.get("aspect_ratio") or "1024x1024"
    if isinstance(size, str) and "x" in size:
        return size
    mapping = {
        "1:1": "1024x1024",
        "2:3": "1024x1536",
        "3:2": "1536x1024",
        "3:4": "1024x1536",
        "4:3": "1536x1024",
        "9:16": "1024x1536",
        "16:9": "1536x1024",
    }
    return mapping.get(str(size), "1024x1024")
