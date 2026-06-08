from __future__ import annotations

import re

from app.schemas import ImagePromptPlan, PromptPatch


def build_prompt_plan(
    *,
    prompt: str,
    count: int = 1,
    size: str | None = None,
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
        negative_constraints=["避免错别字或乱码", "避免文字被拆开或多余空格", "避免肢体和手部畸形", "避免未授权 Logo"],
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
            "main_subject": f"{base_plan.main_subject}\n修改要求：{patch.new_prompt_delta}",
            "count": 1,
            "variables": {**base_plan.variables, "prompt_patch": patch.model_dump()},
        }
    )


def _infer_size(prompt: str, requested_size: str | None) -> str | None:
    if requested_size:
        return requested_size
    return None


def _infer_scene(prompt: str) -> str | None:
    match = re.search(r"(咖啡店|街角|室内|户外|电商|海报|封面|产品图)", prompt)
    return match.group(0) if match else None


def _infer_style(prompt: str) -> str | None:
    styles = [token for token in ["日系", "清爽", "高级", "摄影", "插画", "漫画", "电商", "杂志"] if token in prompt]
    return "，".join(styles) if styles else None


def _infer_composition(prompt: str, size: str | None) -> str:
    if size == "1024x1536":
        return "竖版构图，主体清晰居中，预留安全标题区域。"
    if size == "1536x1024":
        return "横版构图，前景与背景层次清楚。"
    return "均衡方图构图，主体明确，四周留白干净。"


def _infer_brand_constraints(prompt: str, asset_ids: list[str]) -> list[str]:
    constraints: list[str] = []
    if asset_ids:
        constraints.append("尊重上传参考素材及其素材摘要。")
    if "品牌" in prompt:
        constraints.append("保持品牌配色和高级视觉气质。")
    return constraints


def _infer_text(prompt: str) -> dict[str, str | bool]:
    quoted = [item.strip() for item in re.findall(r"[“\"「『《]([^”\"」』》]+)[”\"」』》]", prompt) if item.strip()]
    if quoted:
        return {"required": True, "content": quoted[0], "language": "zh-CN"}
    return {"required": "文字" in prompt or "标题" in prompt, "language": "zh-CN"}
