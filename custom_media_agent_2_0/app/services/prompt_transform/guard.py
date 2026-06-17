from __future__ import annotations

import re


TITLE_MARKERS = ("文案标题", "标题", "字体", "字形", "字效", "title", "headline", "font", "typography")
TITLE_STYLE_MARKERS = (
    "Q版",
    "卡通",
    "圆润",
    "可爱",
    "儿童",
    "泡泡",
    "手写",
    "贴纸",
    "cartoon",
    "cute",
    "rounded",
    "handwritten",
    "sticker",
)
COLOR_MARKERS = ("色彩", "颜色", "配色", "色调", "主色", "color", "palette")
LIMIT_MARKERS = (
    "限制",
    "要求",
    "禁止",
    "不要",
    "不能",
    "不得",
    "必须",
    "只生成",
    "避免",
    "required",
    "must",
    "do not",
    "avoid",
    "without",
    "only",
    "no ",
)
TEXT_MARKERS = ("文字", "文案", "标语", "标题", "copy", "text", "slogan", "headline")
LOGO_MARKERS = ("logo", "Logo", "标志", "品牌标识", "品牌名")
COMPOSITION_MARKERS = ("构图", "布局", "版式", "排版", "composition", "layout", "framing")
PROMPT_IDENTIFIER_REPLACEMENTS = (
    (r"\bcase_github_[a-z0-9_.-]+\b", "selected visual reference"),
    (r"\bgithub_evolinkai_[a-z0-9_.-]+\b", "curated visual reference"),
    (r"\basset_[a-z0-9_.-]+\b", "uploaded visual reference"),
    (r"\bcase_id\b", "selected visual reference"),
    (r"\basset_id\b", "uploaded visual reference"),
    (r"\bprovider_id\b", "source"),
    (r"\bsource_url\b", "source"),
    (r"\bapi[_ -]?key\b", "credential"),
    (r"\bapi\b", "service"),
    (r"\brepository\b", "source collection"),
    (r"\bstorage\b", "asset location"),
    (r"\bEvoLinkAI\b", "curated reference"),
)
MAX_CONSTRAINT_CHARS = 360


def sanitize_prompt_identifiers(prompt: str) -> str:
    clean = str(prompt or "")
    for pattern, replacement in PROMPT_IDENTIFIER_REPLACEMENTS:
        clean = re.sub(pattern, replacement, clean, flags=re.IGNORECASE)
    lines = [" ".join(line.split()) for line in clean.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def extract_constraints(prompt: str) -> list[str]:
    text = _clean_text(prompt)
    if not text:
        return []

    constraints: list[str] = _v2_lock_constraints(text)
    clauses = _prompt_clauses(_user_constraint_source(text))
    for clause in clauses:
        clause_added = False
        if _is_title_style_constraint(clause):
            constraints.append(f"标题字体/标题设计：{clause}")
            clause_added = True
        audience = _target_audience(clause)
        if audience:
            constraints.append(f"目标人群：{audience}")
            clause_added = True
        color = _color_constraint(clause)
        if color:
            constraints.append(f"色彩：{color}")
            clause_added = True
        if _is_logo_constraint(clause):
            constraints.append(f"Logo/品牌：{clause}")
            clause_added = True
        if not clause_added and _is_required_text_constraint(clause):
            constraints.append(f"文字/文案：{clause}")
            clause_added = True
        if not clause_added and _is_composition_constraint(clause):
            constraints.append(f"构图/版式：{clause}")

    limit = _limit_constraint(text)
    if limit:
        constraints.append(limit)
    return _dedupe([_compact_constraint(item) for item in constraints])


def build_guard_instructions(constraints: list[str]) -> str:
    clean_constraints = [item.strip() for item in constraints if item and item.strip()]
    lines = [
        "提示词保真规则：",
        "只能在不改变原意的前提下增强提示词表达，不得删除、弱化或转移用户的硬性约束。",
        "如果约束之间存在冲突，优先保留用户明确指定的主体、文字、字体、颜色、构图、Logo、素材使用方式和限制项。",
        "不得把明确的禁止项、文字内容、Logo位置、模板锁、素材用途或尺寸方向降级为泛泛风格建议。",
        "如果生成模型可能忽略硬约束，请在最终提示词中重复强调这些约束，但不要引入新的创意方向。",
    ]
    if clean_constraints:
        lines.append("硬性约束：")
        lines.extend(f"- {item}" for item in clean_constraints)
    return "\n".join(lines)


def build_original_prompt_instructions() -> str:
    return "\n".join(
        [
            "原始提示词模式：",
            "保留用户原始提示词，不进行优化、扩写、翻译、总结、重排或改写。",
            "下游图像生成应逐字尊重原始请求，不自行添加风格、构图、受众、文字或限制条件。",
        ]
    )


def wrap_guarded_prompt(prompt: str, instructions: str) -> str:
    clean_prompt = str(prompt or "").strip()
    clean_instructions = str(instructions or "").strip()
    if not clean_instructions:
        return clean_prompt
    return f"{clean_instructions}\n\n用户原始提示词：\n{clean_prompt}"


def _clean_text(prompt: str) -> str:
    return re.sub(r"\s+", " ", str(prompt or "").replace("\r", "\n")).strip()


def _prompt_clauses(text: str) -> list[str]:
    return [part.strip(" ：:") for part in re.split(r"[，。；;、\n]+|(?<=[A-Za-z0-9\)])[,.;](?=\s|$)", text) if part.strip(" ：:")]


def _v2_lock_constraints(text: str) -> list[str]:
    lowered = text.lower()
    constraints: list[str] = []
    if "template lock:" in lowered or "selected case is the highest-priority visual template" in lowered:
        constraints.append(
            "模板锁：selected template is the highest-priority visual grammar; preserve composition, spatial hierarchy, lighting logic, background density, mood, layout rhythm, and typography-safe areas."
        )
    elif "auto visual grammar lock:" in lowered:
        constraints.append(
            "视觉语法锚点：use one primary curated case as the main visual grammar anchor; preserve its composition discipline, subject hierarchy, lighting logic, mood, background density, and layout rhythm."
        )
    if "uploaded assets are evidence and slot variables" in lowered:
        constraints.append(
            "素材使用：uploaded assets are evidence and template-slot variables; hard identity assets should stay as provider input images when supported."
        )
    if "only replace the original subject" in lowered or "user semantic content controls" in lowered:
        constraints.append(
            "语义替换：user semantic content controls the actual subject, product, copy, logo, offer, and business meaning while the visual grammar controls the frame."
        )
    return constraints


def _user_constraint_source(text: str) -> str:
    snippets: list[str] = []
    patterns = (
        r"Client request to adapt into the template:\s*(.+?)(?:\.\s*Subordinate draft|\.\s*Downstream|\.\s*Follow these|$)",
        r"User semantic content controls.+?business meaning:\s*(.+?)(?:\.\s*Uploaded assets|\.\s*Conflict policy|$)",
        r"Create a high-quality custom image for this client request:\s*(.+?)(?:\.\s*Follow these|\.\s*Use the selected cases|$)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            snippet = match.group(1).strip(" .：:")
            if snippet:
                snippets.append(snippet)
    if not snippets:
        return text
    return ". ".join(_dedupe(snippets))


def _is_title_style_constraint(clause: str) -> bool:
    lowered = clause.lower()
    return any(marker.lower() in lowered for marker in TITLE_MARKERS) and any(
        marker.lower() in lowered for marker in TITLE_STYLE_MARKERS
    )


def _target_audience(clause: str) -> str:
    match = re.search(r"(?:产品)?目标人群(?:是|为|:|：)?(.+)", clause)
    if not match:
        match = re.search(r"(?:target audience|audience)(?:\s+is|\s*:)?\s+(.+)", clause, flags=re.IGNORECASE)
    return match.group(1).strip(" ：:") if match else ""


def _color_constraint(clause: str) -> str:
    lowered = clause.lower()
    for marker in COLOR_MARKERS:
        marker_lower = marker.lower()
        if marker_lower in lowered:
            index = lowered.find(marker_lower)
            value = clause[index + len(marker) :].strip(" ：:")
            return value or clause
    return ""


def _is_required_text_constraint(clause: str) -> bool:
    lowered = clause.lower()
    if not any(marker.lower() in lowered for marker in TEXT_MARKERS):
        return False
    return any(marker.lower() in lowered for marker in LIMIT_MARKERS) or bool(re.search(r"[“\"'].*[”\"']", clause))


def _is_logo_constraint(clause: str) -> bool:
    lowered = clause.lower()
    if not any(marker.lower() in lowered for marker in LOGO_MARKERS):
        return False
    return any(marker.lower() in lowered for marker in LIMIT_MARKERS) or bool(
        re.search(r"(放在|印在|绣在|贴在|位于|place|print|embroider|attach|on\s+)", clause, flags=re.IGNORECASE)
    )


def _is_composition_constraint(clause: str) -> bool:
    lowered = clause.lower()
    return any(marker.lower() in lowered for marker in COMPOSITION_MARKERS) and any(
        marker.lower() in lowered for marker in LIMIT_MARKERS
    )


def _limit_constraint(text: str) -> str:
    text = _user_constraint_source(text)
    match = re.search(r"(限制|要求|禁止|避免)(?:：|:)(.+)", text)
    if match and match.group(2).strip():
        return f"{match.group(1)}：{match.group(2).strip()}"
    negative_clauses = [
        clause
        for clause in _prompt_clauses(text)
        if any(clause.lower().startswith(marker.lower()) for marker in LIMIT_MARKERS)
    ]
    return "限制：" + "，".join(negative_clauses) if negative_clauses else ""


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _compact_constraint(value: str) -> str:
    clean = _clean_text(value)
    if len(clean) <= MAX_CONSTRAINT_CHARS:
        return clean
    return clean[: MAX_CONSTRAINT_CHARS - 3].rstrip(" ,.;，。；") + "..."
