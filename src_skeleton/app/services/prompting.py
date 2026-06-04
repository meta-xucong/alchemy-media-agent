from __future__ import annotations

import re

from app.schemas import ImagePromptPlan, PromptPatch


def build_prompt_plan(
    *,
    prompt: str,
    count: int = 1,
    size: str = "1024x1024",
    quality: str = "auto",
    output_format: str = "png",
    asset_ids: list[str] | None = None,
) -> ImagePromptPlan:
    inferred_size = _infer_size(prompt, size)
    return ImagePromptPlan(
        main_subject=prompt.strip(),
        scene=_infer_scene(prompt),
        style=_infer_style(prompt),
        composition=_infer_composition(prompt, inferred_size),
        brand_constraints=_infer_brand_constraints(prompt, asset_ids or []),
        negative_constraints=["avoid malformed text", "avoid distorted hands", "avoid unauthorized logos"],
        text=_infer_text(prompt),
        count=count,
        size=inferred_size,
        quality=quality,
        output_format=output_format,
        variables={"asset_ids": asset_ids or []},
    )


def build_revision_patch(*, output_id: str, feedback: str, preserve: list[str] | None = None) -> PromptPatch:
    preserve_values = preserve or ["composition", "main_subject"]
    return PromptPatch(
        base_output_id=output_id,
        preserve=preserve_values,
        change=[feedback.strip()],
        edit_mode="image_edit",
        new_prompt_delta=feedback.strip(),
    )


def apply_patch_to_plan(base_plan: ImagePromptPlan, patch: PromptPatch) -> ImagePromptPlan:
    return base_plan.model_copy(
        update={
            "main_subject": f"{base_plan.main_subject}\nRevision request: {patch.new_prompt_delta}",
            "count": 1,
            "variables": {**base_plan.variables, "prompt_patch": patch.model_dump()},
        }
    )


def _infer_size(prompt: str, requested_size: str) -> str:
    if requested_size != "1024x1024":
        return requested_size
    if any(token in prompt for token in ["竖版", "小红书", "9:16", "竖图"]):
        return "1024x1536"
    if any(token in prompt for token in ["横版", "16:9", "横图"]):
        return "1536x1024"
    return requested_size


def _infer_scene(prompt: str) -> str | None:
    match = re.search(r"(咖啡店|街角|室内|户外|电商|海报|封面|产品图)", prompt)
    return match.group(0) if match else None


def _infer_style(prompt: str) -> str | None:
    styles = [token for token in ["日系", "清爽", "高级", "摄影", "插画", "漫画", "电商", "杂志"] if token in prompt]
    return "，".join(styles) if styles else None


def _infer_composition(prompt: str, size: str) -> str:
    if size == "1024x1536":
        return "Vertical composition with clear central subject and safe title area."
    if size == "1536x1024":
        return "Horizontal composition with clear foreground and background separation."
    return "Balanced square composition."


def _infer_brand_constraints(prompt: str, asset_ids: list[str]) -> list[str]:
    constraints: list[str] = []
    if asset_ids:
        constraints.append("Respect uploaded reference assets and material brief.")
    if "品牌" in prompt:
        constraints.append("Preserve brand palette and premium visual tone.")
    return constraints


def _infer_text(prompt: str) -> dict[str, str | bool]:
    quoted = re.findall(r"[“\"]([^”\"]+)[”\"]", prompt)
    if quoted:
        return {"required": True, "content": quoted[0], "language": "zh-CN"}
    return {"required": "文字" in prompt or "标题" in prompt, "language": "zh-CN"}
