from __future__ import annotations

from app.schemas import CostEstimate, ImageGenerationRequest, ImageGenerationResult
from app.providers.base import ProviderCapabilities


MOCK_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)
MOCK_JPEG_BASE64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAx"
    "NDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
    "MjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAA"
    "F9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNk"
    "ZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6"
    "erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBh"
    "JBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3"
    "eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/"
    "9oADAMBAAIRAxEAPwD3+iiigD//2Q=="
)
MOCK_WEBP_BASE64 = "UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEAAUAmJaQAA3AA/vz0AAA="


class MockImageProvider:
    name = "mock_image"
    model = "mock-image-v1"

    async def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider=self.name,
            configured=True,
            models=[self.model],
            operations=["generate", "edit", "multi_turn_edit"],
            limits={
                "max_batch": 10,
                "formats": ["png", "jpeg", "webp"],
                "sync_mode": "sync",
                "note": "Local deterministic provider for tests and smoke checks.",
            },
            is_mock=True,
        )

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        plan = request.prompt_plan
        width, height = _parse_size(plan.size)
        outputs = [
            {
                "b64_json": _placeholder_for(plan.output_format),
                "mime_type": f"image/{plan.output_format}",
                "width": width,
                "height": height,
                "format": plan.output_format,
                "mock_index": index,
            }
            for index in range(plan.count)
        ]
        return ImageGenerationResult(
            provider=self.name,
            model=self.model,
            outputs=outputs,
            raw_response_summary={
                "mode": "mock",
                "output_count": len(outputs),
                "prompt_chars": len(_render_prompt(plan)),
            },
        )

    async def edit(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        result = await self.generate(request)
        result.raw_response_summary["operation"] = "edit"
        result.raw_response_summary["source_output_id"] = request.source_output_id
        return result

    async def estimate_cost(self, request: ImageGenerationRequest) -> CostEstimate:
        return CostEstimate(
            provider=self.name,
            model=self.model,
            estimated_cost=0.0,
            detail={"mode": "mock", "count": request.prompt_plan.count},
        )


def _parse_size(size: str) -> tuple[int, int]:
    try:
        width, height = size.lower().split("x", 1)
        return int(width), int(height)
    except (ValueError, AttributeError):
        return 1024, 1024


def _placeholder_for(output_format: str) -> str:
    if output_format == "jpeg":
        return MOCK_JPEG_BASE64
    if output_format == "webp":
        return MOCK_WEBP_BASE64
    return MOCK_PNG_BASE64


def _render_prompt(plan) -> str:
    if plan.variables.get("generation_prompt"):
        return plan.variables["generation_prompt"]
    return "\n".join(
        part
        for part in [
            plan.main_subject,
            plan.scene or "",
            plan.style or "",
            plan.composition or "",
            ", ".join(plan.brand_constraints),
            ", ".join(plan.negative_constraints),
        ]
        if part
    )
