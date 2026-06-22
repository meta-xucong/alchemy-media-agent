from __future__ import annotations

import re

from app.schemas import ImagePromptPlan, PromptPatch


A4_PORTRAIT_SIZE = "2400x3392"
A4_LANDSCAPE_SIZE = "3392x2400"
PORTRAIT_SIZE = "1024x1536"
LANDSCAPE_SIZE = "1536x1024"
SQUARE_SIZE = "1024x1024"


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
    base_generation_prompt = str((base_plan.variables or {}).get("generation_prompt") or base_plan.main_subject or "").strip()
    revision_prompt = _revision_generation_prompt(base_generation_prompt=base_generation_prompt, patch=patch)
    return base_plan.model_copy(
        update={
            "main_subject": revision_prompt,
            "count": 1,
            "variables": {
                **base_plan.variables,
                "generation_prompt": revision_prompt,
                "revision_feedback": patch.new_prompt_delta,
                "revision_base_generation_prompt": base_generation_prompt,
                "prompt_patch": patch.model_dump(),
            },
        }
    )


def _revision_generation_prompt(*, base_generation_prompt: str, patch: PromptPatch) -> str:
    feedback = patch.new_prompt_delta.strip()
    preserve = "、".join(item for item in patch.preserve if item) or "主体、构图、光影、色彩和整体视觉节奏"
    return "\n".join(
        part
        for part in [
            "以输入图片作为唯一视觉参考继续修改。",
            f"修改要求（最高优先级，必须执行）：{feedback}",
            f"保持不变：{preserve}；尽量保留人物身份、姿态、构图、光影、色彩、背景密度和整体风格一致。",
            "如果原始提示词或输入图片中的局部物体与修改要求冲突，必须以修改要求为准；被替换的原物体不要保留。",
            f"原始提示词仅作低优先级风格/构图参考：{base_generation_prompt}",
        ]
        if part.strip()
    )


def _infer_size(prompt: str, requested_size: str | None) -> str | None:
    if requested_size:
        return requested_size.strip() or None
    prompt_text = prompt or ""
    if _mentions_a4(prompt_text):
        if _mentions_landscape(prompt_text):
            return A4_LANDSCAPE_SIZE
        return A4_PORTRAIT_SIZE
    if _mentions_square(prompt_text):
        return SQUARE_SIZE
    if _mentions_portrait(prompt_text):
        return PORTRAIT_SIZE
    if _mentions_landscape(prompt_text):
        return LANDSCAPE_SIZE
    return None


def _mentions_a4(prompt: str) -> bool:
    return bool(
        re.search(
            r"(?<![A-Za-z0-9])A\s*4(?![A-Za-z0-9])|A4\s*(?:大小|尺寸|画幅|比例|版式|纸|图|海报)?",
            prompt,
            flags=re.IGNORECASE,
        )
    )


def _mentions_square(prompt: str) -> bool:
    return bool(re.search(r"(方图|正方形|方形|1\s*[:：]\s*1|\bsquare\b)", prompt, flags=re.IGNORECASE))


def _mentions_portrait(prompt: str) -> bool:
    return bool(
        re.search(
            r"(竖版|竖向|纵向|竖图|竖幅|海报竖版|9\s*[:：]\s*16|3\s*[:：]\s*4|\bportrait\b)",
            prompt,
            flags=re.IGNORECASE,
        )
    )


def _mentions_landscape(prompt: str) -> bool:
    return bool(
        re.search(
            r"(横版|横向|横图|横幅|宽幅|16\s*[:：]\s*9|4\s*[:：]\s*3|\blandscape\b)",
            prompt,
            flags=re.IGNORECASE,
        )
    )


def _infer_scene(prompt: str) -> str | None:
    match = re.search(r"(咖啡店|街角|室内|户外|电商|海报|封面|产品图)", prompt)
    return match.group(0) if match else None


def _infer_style(prompt: str) -> str | None:
    styles = [token for token in ["日系", "清爽", "高级", "摄影", "插画", "漫画", "电商", "杂志"] if token in prompt]
    return "，".join(styles) if styles else None


def _infer_composition(prompt: str, size: str | None) -> str:
    orientation = _orientation_from_size(size)
    if orientation == "portrait":
        return "竖版构图，主体清晰居中，预留安全标题区域。"
    if orientation == "landscape":
        return "横版构图，前景与背景层次清楚。"
    return "均衡方图构图，主体明确，四周留白干净。"


def _orientation_from_size(size: str | None) -> str:
    try:
        width_text, height_text = str(size or "").lower().split("x", 1)
        width = int(width_text.strip())
        height = int(height_text.strip())
    except (AttributeError, ValueError):
        return "square"
    if height > width:
        return "portrait"
    if width > height:
        return "landscape"
    return "square"


def _infer_brand_constraints(prompt: str, asset_ids: list[str]) -> list[str]:
    constraints: list[str] = []
    if asset_ids:
        constraints.append("尊重上传参考素材及其素材摘要。")
    if "品牌" in prompt:
        constraints.append("保持品牌配色和高级视觉气质。")
    return constraints


def _infer_text(prompt: str) -> dict[str, str | bool]:
    quoted = [item.strip() for item in re.findall(r"[“\"「『《]([^”\"」』》]+)[”\"」』》]", prompt) if item.strip()]
    replacement_targets = _quoted_replacement_targets(prompt)
    if replacement_targets:
        return {"required": True, "content": "；".join(replacement_targets), "language": "zh-CN"}
    retained = [item for item in quoted if not _quoted_text_is_removal_or_replacement(prompt, item)]
    if retained:
        return {"required": True, "content": retained[0], "language": "zh-CN"}
    return {"required": "文字" in prompt or "标题" in prompt, "language": "zh-CN"}


def _quoted_replacement_targets(prompt: str) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for item in re.findall(r"(?:改成|换成|替换为|替换成)\s*[“\"「『《]([^”\"」』》]+)[”\"」』》]", prompt):
        clean = item.strip()
        if clean and clean not in seen:
            targets.append(clean)
            seen.add(clean)
    return targets


def _quoted_text_is_removal_or_replacement(prompt: str, text: str) -> bool:
    escaped = re.escape(text)
    patterns = [
        rf"(?:去掉|去除|移除|删除|擦除|清除|不要|不保留).{{0,24}}[“\"「『《]{escaped}[”\"」』》]",
        rf"[“\"「『《]{escaped}[”\"」』》].{{0,16}}(?:去掉|去除|移除|删除|擦除|清除|不要|不保留)",
        rf"把[“\"「『《]{escaped}[”\"」』》].{{0,24}}(?:改成|换成|替换为|替换成)",
        rf"[“\"「『《]{escaped}[”\"」』》]\s*(?:改成|换成|替换为|替换成)",
    ]
    return any(re.search(pattern, prompt) for pattern in patterns)
