from __future__ import annotations

import asyncio
import json
import os
import random
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.repositories import repository
from app.schemas import GenerationJob, JobStatus
from app.services.image_service import run_submitted_image_job, submit_image_job
from app.services.utils import make_id, now_iso
from app.storage import media_store


MAX_SELECTED_STYLES = 8
MAX_IMAGES_PER_STYLE = 4
MAX_TOTAL_IMAGES = 12
MAX_CONCURRENT_GENERATIONS = 3
MAX_RETRIES_PER_VARIANT = 1
MAX_GENERATION_INTERVAL_SECONDS = 60
LAB_PROJECT_ID = "alchemy_lab_rare_style_explorer"
RARE_STYLE_FEATURE_ID = "rare-style-explorer"

STYLE_FAMILIES: dict[str, set[str]] = {
    "film": {"电影、电视与影像类型"},
    "fashion": {"时装、亚文化与人物造型"},
    "product": {"玩具、产品与收藏品呈现", "材质与表面质感"},
    "photography": {"摄影工艺与影像缺陷"},
    "illustration": {"动画、漫画与插画亚种"},
    "graphic": {"平面设计、印刷与海报亚种"},
    "craft": {"工艺、地域视觉与历史媒介"},
    "digital": {"数字、游戏、UI与计算机视觉"},
    "space": {"建筑、空间与场景气质"},
    "material": {"材质与表面质感"},
}
CATEGORY_TO_FAMILY = {category: family for family, categories in STYLE_FAMILIES.items() for category in categories}
MODE_OPTIONS = {"minimal", "product", "character", "poster", "scene", "material-series"}
FRESHNESS_OPTIONS = {"normal", "high"}
GENERIC_WORDS = {
    "a",
    "and",
    "art",
    "cinematic",
    "design",
    "editorial",
    "film",
    "illustration",
    "light",
    "lighting",
    "modern",
    "photo",
    "photography",
    "poster",
    "retro",
    "style",
    "surreal",
    "the",
    "vintage",
    "with",
}
LEGACY_STYLE_ALIASES = {
    "folk_horror_poster_photo": "C002",
    "chrome_y2k_fashion_editorial": "G008",
    "pastel_ceramic_toy_photo": "M005",
    "tropical_vhs_travelogue": "P011",
    "risograph_botanical_catalog": "G001",
    "brutalist_museum_product_plinth": "S005",
    "crt_pixel_interface_still_life": "P012",
    "hand_tinted_archive_portrait": "P022",
}

ANTI_DRIFT = [
    "避免泛化的现代极简风",
    "避免随机多余文字",
    "避免混乱符号",
    "避免手部和面部畸形",
    "避免丢失主体身份",
]


class StylePreset(BaseModel):
    id: str
    version: str = "1.0"
    display_name: str
    short_description: str
    family: str
    category: str
    tags: list[str] = Field(default_factory=list)
    mode_affinity: list[str] = Field(default_factory=list)
    prompt_directives: list[str] = Field(default_factory=list)
    negative_directives: list[str] = Field(default_factory=list)
    freshness: str = "high"
    is_beginner_default: bool = True
    is_enabled: bool = True


class ExplorationRequest(BaseModel):
    idea: str = Field(min_length=1)
    selected_style_ids: list[str] = Field(default_factory=list)
    mode: str = "minimal"
    style_family: str | None = None
    freshness: str = "high"
    target_count: int = Field(default=4, ge=1, le=MAX_TOTAL_IMAGES)
    images_per_style: int = Field(default=1, ge=1, le=MAX_IMAGES_PER_STYLE)
    generation_interval_seconds: float = Field(default=0, ge=0, le=MAX_GENERATION_INTERVAL_SECONDS)
    seed: int | None = None
    style_id: str | None = None
    avoid_generic: bool = True
    aspect_ratio: str | None = None
    provider_preference: str | None = None

    @field_validator("idea")
    @classmethod
    def idea_must_not_be_blank(cls, value: str) -> str:
        clean = " ".join(str(value or "").split())
        if not clean:
            raise ValueError("Please describe what you want to create.")
        return clean


class ComposedPrompt(BaseModel):
    id: str
    session_id: str
    style_preset_id: str
    style_preset_version: str
    idea: str
    final_prompt: str
    prompt_metadata: dict[str, Any] = Field(default_factory=dict)


class ExplorationError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    detail: dict[str, Any] = Field(default_factory=dict)


class GenerationVariant(BaseModel):
    id: str
    session_id: str
    prompt_id: str
    style_preset_id: str
    index_within_style: int
    status: str
    created_at: str
    completed_at: str | None = None
    asset: dict[str, Any] | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    error: ExplorationError | None = None


class ExplorationSession(BaseModel):
    id: str
    feature: str = "rare-style-explorer"
    status: str
    created_at: str
    updated_at: str
    request: ExplorationRequest
    style_presets: list[StylePreset] = Field(default_factory=list)
    prompts: list[ComposedPrompt] = Field(default_factory=list)
    variants: list[GenerationVariant] = Field(default_factory=list)
    favorites: list[str] = Field(default_factory=list)
    errors: list[ExplorationError] = Field(default_factory=list)


class ComparisonCard(BaseModel):
    variant_id: str
    style_preset_id: str
    style_name: str
    status: str
    image_url: str | None = None
    thumbnail_url: str | None = None
    prompt: str
    error: ExplorationError | None = None
    is_favorite: bool = False


class ComparisonGroup(BaseModel):
    style_preset_id: str
    style_name: str
    cards: list[ComparisonCard] = Field(default_factory=list)


class ComparisonBoard(BaseModel):
    session_id: str
    status: str
    idea: str
    groups: list[ComparisonGroup] = Field(default_factory=list)
    favorites: list[str] = Field(default_factory=list)
    errors: list[ExplorationError] = Field(default_factory=list)
    limits: dict[str, int] = Field(default_factory=dict)


class FavoriteSelection(BaseModel):
    variant_ids: list[str] = Field(default_factory=list)


class LabHistoryItem(BaseModel):
    id: str
    job_id: str
    session_id: str | None = None
    module: str = RARE_STYLE_FEATURE_ID
    module_label: str = "Rare Style Explorer"
    title: str
    style_preset_id: str | None = None
    style_name: str | None = None
    style_family: str | None = None
    style_category: str | None = None
    keywords: list[str] = Field(default_factory=list)
    idea: str | None = None
    mode: str | None = None
    mode_label: str | None = None
    freshness: str | None = None
    aspect_ratio: str | None = None
    generation_interval_seconds: float | None = None
    target_count: int | None = None
    images_per_style: int | None = None
    url: str
    thumbnail_url: str | None = None
    format: str = "png"
    width: int | None = None
    height: int | None = None
    provider: str | None = None
    model: str | None = None
    prompt: str | None = None
    final_prompt: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    source: str | None = None


@dataclass
class AlchemyLabStore:
    sessions: dict[str, ExplorationSession]

    def save(self, session: ExplorationSession) -> ExplorationSession:
        self.sessions[session.id] = session
        return session

    def get(self, session_id: str) -> ExplorationSession | None:
        return self.sessions.get(session_id)

    def reset(self) -> None:
        self.sessions.clear()


lab_store = AlchemyLabStore(sessions={})


FALLBACK_STYLE_PRESETS = [
    StylePreset(
        id="folk_horror_poster_photo",
        display_name="褪色民俗恐怖海报",
        short_description="像被太阳晒旧的民俗恐怖电影海报，颗粒、旧纸和紧张留白明显。",
        family="film",
        category="电影、电视与影像类型",
        tags=["poster", "film", "grain"],
        mode_affinity=["poster", "scene", "minimal"],
        prompt_directives=["褪色民俗恐怖海报摄影", "旧纸张颗粒", "低饱和暖色", "主体轮廓清晰", "紧张留白"],
        negative_directives=["不要现代极简海报", "不要长段可读文字"],
    ),
    StylePreset(
        id="chrome_y2k_fashion_editorial",
        display_name="铬色 Y2K 时装大片",
        short_description="高反光铬色、闪光灯和 2000 年代时装杂志质感。",
        family="fashion",
        category="时装、亚文化与人物造型",
        tags=["fashion", "chrome", "editorial"],
        mode_affinity=["character", "minimal", "product"],
        prompt_directives=["铬色 Y2K 时装编辑大片", "镜面银色高光", "硬闪光灯", "杂志级造型", "干净强轮廓"],
        negative_directives=["不要过多饰品", "不要丢失面部身份"],
    ),
    StylePreset(
        id="pastel_ceramic_toy_photo",
        display_name="粉彩陶瓷玩具棚拍",
        short_description="柔和粉彩陶瓷质地，适合产品、盲盒和可爱物件。",
        family="product",
        category="玩具、产品与收藏品呈现",
        tags=["product", "ceramic", "toy"],
        mode_affinity=["product", "material-series", "minimal"],
        prompt_directives=["粉彩陶瓷玩具摄影", "柔和棚拍光", "可读产品轮廓", "干净背景", "圆润釉面反光"],
        negative_directives=["不要杂乱背景", "产品保持可识别"],
    ),
    StylePreset(
        id="tropical_vhs_travelogue",
        display_name="过曝热带 VHS 游记",
        short_description="热带旅行录像截图，过曝、VHS 色偏和模拟媒介缺陷。",
        family="photography",
        category="摄影工艺与影像缺陷",
        tags=["vhs", "travel", "analog"],
        mode_affinity=["scene", "poster", "minimal"],
        prompt_directives=["过曝热带 VHS 旅行影像", "模拟录像色偏", "轻微扫描线", "阳光漂白色彩", "主体在前景"],
        negative_directives=["缺陷层不要过强", "不要画面脏到看不清主体"],
    ),
    StylePreset(
        id="risograph_botanical_catalog",
        display_name="孔版植物图录",
        short_description="Risograph 套色印刷和植物图录版式，适合海报、包装和插画。",
        family="graphic",
        category="平面设计、印刷与海报亚种",
        tags=["risograph", "catalog", "botanical"],
        mode_affinity=["poster", "product", "minimal"],
        prompt_directives=["Risograph 植物图录", "套色错位", "纸张纤维", "明确标题区域", "少量伪文字"],
        negative_directives=["不要长段可读文字", "不要混乱符号"],
    ),
    StylePreset(
        id="brutalist_museum_product_plinth",
        display_name="粗野主义博物馆展台",
        short_description="混凝土展台、博物馆灯光和克制空间层次。",
        family="space",
        category="建筑、空间与场景气质",
        tags=["brutalist", "museum", "product"],
        mode_affinity=["product", "scene", "minimal"],
        prompt_directives=["粗野主义博物馆展台", "混凝土材质", "克制空间层次", "聚焦主体", "柔和顶部展陈光"],
        negative_directives=["不要过度拥挤", "不要让背景压过主体"],
    ),
    StylePreset(
        id="crt_pixel_interface_still_life",
        display_name="CRT 像素界面静物",
        short_description="旧屏幕、像素界面和电子光晕构成的数字媒介静物。",
        family="digital",
        category="数字、游戏、UI与计算机视觉",
        tags=["crt", "pixel", "interface"],
        mode_affinity=["poster", "product", "minimal"],
        prompt_directives=["CRT 像素界面静物", "低分辨率屏幕纹理", "绿色电子光", "玻璃反射", "主体保持清晰"],
        negative_directives=["不要乱码文字堆积", "不要主体变成纯界面"],
    ),
    StylePreset(
        id="hand_tinted_archive_portrait",
        display_name="手工上色档案肖像",
        short_description="旧档案照片上手工淡彩，适合人像和角色方向。",
        family="photography",
        category="摄影工艺与影像缺陷",
        tags=["portrait", "archive", "hand-tinted"],
        mode_affinity=["character", "minimal"],
        prompt_directives=["手工上色档案肖像", "淡彩肤色", "银盐照片颗粒", "面部清晰", "安静正面光"],
        negative_directives=["避免面部畸形", "只保留1-2个关键配饰"],
    ),
]


def list_lab_modules() -> dict[str, list[dict[str, str]]]:
    return {
        "modules": [
            {
                "id": RARE_STYLE_FEATURE_ID,
                "title": "Rare Style Explorer",
                "description": "Explore rare visual sub-styles for one image idea.",
            }
        ]
    }


def list_style_presets() -> dict[str, Any]:
    styles = _style_presets()
    return {
        "styles": [style.model_dump() for style in styles if style.is_enabled],
        "limits": limits(),
        "families": _family_options(),
        "modes": _mode_options(),
    }


def limits() -> dict[str, int]:
    return {
        "maxSelectedStyles": MAX_SELECTED_STYLES,
        "maxImagesPerStyle": MAX_IMAGES_PER_STYLE,
        "maxTotalImages": MAX_TOTAL_IMAGES,
        "maxConcurrentGenerations": MAX_CONCURRENT_GENERATIONS,
        "maxRetriesPerVariant": MAX_RETRIES_PER_VARIANT,
        "maxGenerationIntervalSeconds": MAX_GENERATION_INTERVAL_SECONDS,
        "styleLibrarySize": len(_style_presets()),
    }


async def create_exploration_session(request: ExplorationRequest, *, veyra_user_id: int | None = None) -> ExplorationSession:
    request = _normalize_request(request)
    _validate_requested_style_count(request)
    selected = _resolve_styles(request)
    _validate_batch(request, selected)
    timestamp = now_iso()
    session = ExplorationSession(
        id=make_id("lab"),
        status="queued",
        created_at=timestamp,
        updated_at=timestamp,
        request=request,
        style_presets=selected,
    )
    lab_store.save(session)

    media_session = repository.save_session(
        _lab_media_session(session.id, title=f"Alchemy Lab: {request.idea[:48]}")
    )
    prompts = [_compose_prompt(session.id, request, style) for style in selected]
    session.prompts = prompts
    session.variants = [
        GenerationVariant(
            id=make_id("variant"),
            session_id=session.id,
            prompt_id=prompt.id,
            style_preset_id=prompt.style_preset_id,
            index_within_style=index + 1,
            status="queued",
            created_at=now_iso(),
        )
        for prompt in prompts
        for index in range(request.images_per_style)
    ]
    session.status = "running"
    session.updated_at = now_iso()
    lab_store.save(session)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)
    prompt_by_id = {prompt.id: prompt for prompt in prompts}
    fatal_provider_error: ExplorationError | None = None

    async def run_variant(variant: GenerationVariant) -> GenerationVariant:
        nonlocal fatal_provider_error
        if fatal_provider_error:
            return _skipped_variant(variant, fatal_provider_error)
        delay = max(0.0, float(request.generation_interval_seconds or 0))
        order = session.variants.index(variant) if variant in session.variants else 0
        if delay and order:
            await asyncio.sleep(delay * order)
        async with semaphore:
            if fatal_provider_error:
                return _skipped_variant(variant, fatal_provider_error)
            variant.status = "running"
            lab_store.save(session.model_copy(update={"variants": session.variants, "updated_at": now_iso()}))
            prompt = prompt_by_id[variant.prompt_id]
            last_variant = variant
            for attempt in range(MAX_RETRIES_PER_VARIANT + 1):
                try:
                    prepared = await submit_image_job(
                        session_id=media_session.id,
                        prompt=prompt.final_prompt,
                        count=1,
                        size=_size_from_aspect_ratio(request.aspect_ratio),
                        quality="high",
                        output_format="png",
                        provider_preference=request.provider_preference,
                        idempotency_key=f"lab:{session.id}:{variant.id}:attempt:{attempt}",
                        veyra_user_id=veyra_user_id,
                    )
                    job = prepared.job
                    if prepared.request and job.status not in {JobStatus.ready, JobStatus.failed, JobStatus.provider_not_configured, JobStatus.rejected, JobStatus.canceled}:
                        job = await run_submitted_image_job(job.id, prepared.request) or job
                    _attach_lab_history_metadata(job, session=session, variant=variant, prompt=prompt)
                    last_variant = _variant_from_job(variant, job, attempt=attempt)
                    if last_variant.error and _is_fatal_provider_error(last_variant.error):
                        fatal_provider_error = last_variant.error
                    if last_variant.status == "succeeded" or not (last_variant.error and last_variant.error.retryable) or attempt >= MAX_RETRIES_PER_VARIANT:
                        return last_variant
                except Exception as exc:
                    last_variant = _exception_variant(variant, exc, attempt=attempt)
                    if not last_variant.error.retryable or attempt >= MAX_RETRIES_PER_VARIANT:
                        return last_variant
            return last_variant

    results = await asyncio.gather(*(run_variant(variant) for variant in session.variants))
    session.variants = list(results)
    session.errors = [variant.error for variant in session.variants if variant.error]
    succeeded = [variant for variant in session.variants if variant.status == "succeeded"]
    failed = [variant for variant in session.variants if variant.status == "failed"]
    if succeeded and failed:
        session.status = "partial_success"
    elif succeeded:
        session.status = "completed"
    else:
        session.status = "failed"
    session.updated_at = now_iso()
    return lab_store.save(session)


def get_exploration_session(session_id: str) -> ExplorationSession | None:
    return lab_store.get(session_id)


def update_favorites(session_id: str, selection: FavoriteSelection) -> ExplorationSession | None:
    session = lab_store.get(session_id)
    if not session:
        return None
    valid_ids = {variant.id for variant in session.variants}
    favorites = [variant_id for variant_id in selection.variant_ids if variant_id in valid_ids]
    session.favorites = favorites
    session.updated_at = now_iso()
    return lab_store.save(session)


def list_lab_history(*, limit: int = 50) -> dict[str, Any]:
    records = media_store.list_history_records(limit=10000)
    items = [
        item
        for item in (_lab_history_item_from_record(record) for record in records)
        if item is not None
    ]
    items.sort(key=lambda item: item.created_at or item.updated_at or "", reverse=True)
    return {"items": [item.model_dump() for item in items[:limit]], "total": len(items)}


def comparison_board(session: ExplorationSession) -> ComparisonBoard:
    style_by_id = {style.id: style for style in session.style_presets}
    prompt_by_id = {prompt.id: prompt for prompt in session.prompts}
    groups: list[ComparisonGroup] = []
    for style in session.style_presets:
        cards = []
        for variant in [item for item in session.variants if item.style_preset_id == style.id]:
            prompt = prompt_by_id.get(variant.prompt_id)
            cards.append(
                ComparisonCard(
                    variant_id=variant.id,
                    style_preset_id=style.id,
                    style_name=style.display_name,
                    status=variant.status,
                    image_url=variant.asset.get("url") if variant.asset else None,
                    thumbnail_url=variant.asset.get("thumbnail_url") if variant.asset else None,
                    prompt=prompt.final_prompt if prompt else "",
                    error=variant.error,
                    is_favorite=variant.id in session.favorites,
                )
            )
        groups.append(ComparisonGroup(style_preset_id=style.id, style_name=style_by_id[style.id].display_name, cards=cards))
    return ComparisonBoard(
        session_id=session.id,
        status=session.status,
        idea=session.request.idea,
        groups=groups,
        favorites=list(session.favorites),
        errors=list(session.errors),
        limits=limits(),
    )


def _resolve_styles(request: ExplorationRequest) -> list[StylePreset]:
    enabled = [style for style in _style_presets() if style.is_enabled]
    by_id = {style.id: style for style in enabled}
    for legacy_id, canonical_id in LEGACY_STYLE_ALIASES.items():
        if canonical_id in by_id:
            by_id[legacy_id] = by_id[canonical_id]
    explicit_id = (request.style_id or "").strip()
    style_ids = [explicit_id] if explicit_id else list(request.selected_style_ids or [])
    if not style_ids:
        return _auto_select_styles(request, enabled)
    selected = []
    selected_ids: set[str] = set()
    missing = []
    for style_id in style_ids:
        style = by_id.get(style_id)
        if not style:
            missing.append(style_id)
            continue
        if style.id in selected_ids:
            continue
        selected_ids.add(style.id)
        selected.append(style)
    if missing:
        raise ValueError(f"Unknown style preset: {', '.join(missing)}")
    if not selected:
        raise ValueError("Please choose at least one available style.")
    return selected


def _validate_requested_style_count(request: ExplorationRequest) -> None:
    if len(request.selected_style_ids or []) > MAX_SELECTED_STYLES:
        raise ValueError(f"Choose no more than {MAX_SELECTED_STYLES} styles.")


def _validate_batch(request: ExplorationRequest, selected: list[StylePreset]) -> None:
    if len(request.selected_style_ids or []) > MAX_SELECTED_STYLES:
        raise ValueError(f"Choose no more than {MAX_SELECTED_STYLES} styles.")
    if len(selected) > MAX_SELECTED_STYLES:
        raise ValueError(f"Choose no more than {MAX_SELECTED_STYLES} styles.")
    total = len(selected) * _images_per_style_for_request(request)
    if total > MAX_TOTAL_IMAGES:
        raise ValueError(f"That is too many images for one run. Maximum is {MAX_TOTAL_IMAGES}.")


def _compose_prompt(session_id: str, request: ExplorationRequest, style: StylePreset) -> ComposedPrompt:
    prompt_lines = [
        f"{request.idea}",
        "稀有风格方向：" + "，".join(style.prompt_directives),
        "组合规则：一个强主风格，最多一个材质/光色层，最多一个版式/空间层，缺陷层保持轻量。",
        "图像要求：主体轮廓清晰，视觉识别度强，高细节。",
        "避免：" + "，".join([*ANTI_DRIFT, *style.negative_directives]),
    ]
    if request.mode == "product":
        prompt_lines.append("产品要求：造型可读，干净背景，无杂物，产品保持可识别。")
    elif request.mode == "character":
        prompt_lines.append("人物要求：面部清晰，姿态有表现力，只保留1-2个关键配饰。")
    elif request.mode == "poster":
        prompt_lines.append("海报要求：少量伪文字，明确标题区域，不要长段可读文字。")
    return ComposedPrompt(
        id=make_id("prompt"),
        session_id=session_id,
        style_preset_id=style.id,
        style_preset_version=style.version,
        idea=request.idea,
        final_prompt="\n".join(prompt_lines),
        prompt_metadata={
            "family": style.family,
            "mode": request.mode,
            "freshness": request.freshness,
            "style_family": style.family,
            "target_count": request.target_count,
            "generation_interval_seconds": request.generation_interval_seconds,
            "avoid_generic": request.avoid_generic,
            "source": "alchemy_lab_behavior_compatible_rare_style_explorer",
        },
    )


def _normalize_request(request: ExplorationRequest) -> ExplorationRequest:
    mode = str(request.mode or "minimal").strip()
    freshness = str(request.freshness or "high").strip()
    family = str(request.style_family or "").strip() or None
    if mode not in MODE_OPTIONS:
        mode = "minimal"
    if freshness not in FRESHNESS_OPTIONS:
        freshness = "high"
    if family not in STYLE_FAMILIES:
        family = None
    update: dict[str, Any] = {"mode": mode, "freshness": freshness, "style_family": family}
    if not _has_manual_style_selection(request):
        update["images_per_style"] = 1
    return request.model_copy(update=update)


def _has_manual_style_selection(request: ExplorationRequest) -> bool:
    return bool((request.style_id or "").strip() or request.selected_style_ids)


def _images_per_style_for_request(request: ExplorationRequest) -> int:
    return request.images_per_style if _has_manual_style_selection(request) else 1


def _auto_select_styles(request: ExplorationRequest, enabled: list[StylePreset]) -> list[StylePreset]:
    pool = [style for style in enabled if not request.style_family or style.family == request.style_family]
    if not pool:
        pool = enabled
    count = max(1, min(int(request.target_count or 4), MAX_SELECTED_STYLES, MAX_TOTAL_IMAGES))
    rng = random.Random(request.seed)
    selected: list[StylePreset] = []
    used_categories: set[str] = set()
    used_terms: list[set[str]] = []
    while pool and len(selected) < count:
        selected_ids = {item.id for item in selected}
        candidates = [
            style
            for style in pool
            if style.id not in selected_ids
            and (style.category not in used_categories or len(used_categories) >= 4)
            and (not request.avoid_generic or not _too_similar(style, used_terms))
        ]
        if not candidates:
            candidates = [style for style in pool if style.id not in selected_ids]
        if not candidates:
            break
        style = _weighted_style_choice(rng, candidates, freshness=request.freshness, avoid_generic=request.avoid_generic)
        selected.append(style)
        used_categories.add(style.category)
        terms = _meaningful_terms(style)
        if terms:
            used_terms.append(terms)
    if not selected:
        selected = [style for style in enabled if style.is_beginner_default][: min(4, count)]
    if not selected:
        raise ValueError("Please choose at least one available style.")
    return selected


def _weighted_style_choice(rng: random.Random, styles: list[StylePreset], *, freshness: str, avoid_generic: bool) -> StylePreset:
    weights = [_style_weight(style, freshness=freshness, avoid_generic=avoid_generic) for style in styles]
    total = sum(weights)
    if total <= 0:
        return rng.choice(styles)
    threshold = rng.random() * total
    current = 0.0
    for style, weight in zip(styles, weights):
        current += weight
        if current >= threshold:
            return style
    return styles[-1]


def _style_weight(style: StylePreset, *, freshness: str, avoid_generic: bool) -> float:
    weight = 1.0
    terms = _meaningful_terms(style)
    if freshness == "high":
        if len(terms) >= 4:
            weight *= 1.4
        if style.freshness == "high":
            weight *= 1.25
    if avoid_generic:
        token_count = max(1, len(re.findall(r"[a-z0-9]+", " ".join(style.tags).lower())))
        specificity = len(terms) / token_count
        if len(terms) <= 1 or specificity < 0.35:
            weight *= 0.3
    return weight


def _meaningful_terms(style: StylePreset) -> set[str]:
    text = " ".join([*style.tags, style.display_name, style.short_description]).lower()
    words = re.findall(r"[a-z0-9]+", text)
    return {word for word in words if len(word) > 2 and word not in GENERIC_WORDS}


def _too_similar(style: StylePreset, seen_term_sets: list[set[str]]) -> bool:
    terms = _meaningful_terms(style)
    if not terms:
        return False
    for seen in seen_term_sets:
        shared = terms & seen
        if len(shared) >= 2 and len(shared) / max(1, min(len(terms), len(seen))) >= 0.5:
            return True
    return False


@lru_cache(maxsize=1)
def _style_presets() -> tuple[StylePreset, ...]:
    external = _load_external_style_library()
    if external:
        return tuple(external)
    return tuple(FALLBACK_STYLE_PRESETS)


def _load_external_style_library() -> list[StylePreset]:
    path = _rare_style_library_path()
    if not path:
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    raw_styles = data.get("styles") if isinstance(data, dict) else None
    if not isinstance(raw_styles, list):
        return []
    presets = [_style_from_library_item(item) for item in raw_styles if isinstance(item, dict)]
    return [preset for preset in presets if preset]


def _rare_style_library_path() -> Path | None:
    candidates = []
    configured = os.getenv("ALCHEMY_RARE_STYLE_LIBRARY_PATH", "").strip()
    if configured:
        candidates.append(Path(configured))
    repo_root = Path(__file__).resolve().parents[3]
    candidates.extend(
        [
            Path(__file__).resolve().parents[1] / "data" / "rare_style_library.json",
            repo_root / ".codex_inspect_refs" / "vsc-skills" / "rare-style-explorer" / "references" / "style_library.json",
        ]
    )
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _style_from_library_item(item: dict[str, Any]) -> StylePreset | None:
    style_id = str(item.get("style_id") or "").strip()
    name = str(item.get("中文风格名") or "").strip()
    category = str(item.get("类别") or "").strip()
    if not style_id or not name or not category:
        return None
    family = CATEGORY_TO_FAMILY.get(category, "material")
    visual_dna = str(item.get("视觉DNA / 关键词") or "").strip()
    material_light = str(item.get("材质/色彩/光线") or "").strip()
    tokens = str(item.get("English prompt tokens") or "").strip()
    risk = str(item.get("容易翻车") or "").strip()
    fix = str(item.get("补救提示") or "").strip()
    suitable = str(item.get("适合主体") or item.get("适合做") or "").strip()
    directives = [part for part in [name, visual_dna, material_light] if part]
    negatives = [part for part in [risk, fix] if part]
    return StylePreset(
        id=style_id,
        version="rare-style-library",
        display_name=name,
        short_description=visual_dna or suitable or tokens,
        family=family,
        category=category,
        tags=[tag for tag in re.split(r"[,，/ ]+", tokens) if tag][:10],
        mode_affinity=_mode_affinity_for_style(family, category, suitable),
        prompt_directives=directives,
        negative_directives=negatives,
        freshness="high" if item.get("来源批次") else "normal",
        is_beginner_default=style_id in {"C002", "G008", "M005", "P011"},
        is_enabled=True,
    )


def _mode_affinity_for_style(family: str, category: str, suitable: str) -> list[str]:
    text = " ".join([family, category, suitable])
    modes = ["minimal"]
    if family in {"product", "material", "space"} or any(word in text for word in ["产品", "包装", "器物", "玩具"]):
        modes.append("product")
    if family in {"fashion", "photography"} or any(word in text for word in ["角色", "人物", "头像", "肖像"]):
        modes.append("character")
    if family in {"graphic", "illustration", "digital"} or any(word in text for word in ["海报", "封面", "图标"]):
        modes.append("poster")
    if family in {"film", "space"} or "场景" in text:
        modes.append("scene")
    if family in {"material", "craft"}:
        modes.append("material-series")
    return list(dict.fromkeys(modes))


def _family_options() -> list[dict[str, str]]:
    labels = {
        "film": "电影/影像",
        "fashion": "时装/人物",
        "product": "产品/材质",
        "photography": "摄影/缺陷",
        "illustration": "插画/动画",
        "graphic": "平面/海报",
        "craft": "工艺/地域",
        "digital": "数字/UI",
        "space": "建筑/空间",
        "material": "表面材质",
    }
    return [{"id": key, "label": labels[key]} for key in STYLE_FAMILIES]


def _mode_options() -> list[dict[str, str]]:
    labels = {
        "minimal": "快速探索",
        "product": "产品图",
        "character": "人物角色",
        "poster": "海报封面",
        "scene": "叙事场景",
        "material-series": "材质系列",
    }
    return [{"id": key, "label": labels[key]} for key in ["minimal", "product", "character", "poster", "scene", "material-series"]]


def _variant_from_job(variant: GenerationVariant, job: GenerationJob, *, attempt: int = 0) -> GenerationVariant:
    if job.status == JobStatus.ready and job.outputs:
        output = job.outputs[0]
        return variant.model_copy(
            update={
                "status": "succeeded",
                "completed_at": now_iso(),
                "asset": {
                    "output_id": output.id,
                    "job_id": job.id,
                    "url": output.url,
                    "thumbnail_url": output.thumbnail_url,
                    "width": output.width,
                    "height": output.height,
                    "format": output.format,
                },
                "provider_metadata": {
                    "provider": job.provider,
                    "model": job.model,
                    "requested_provider": job.raw_response_summary.get("requested_image_provider") if job.raw_response_summary else None,
                    "requested_model": job.raw_response_summary.get("requested_image_model") if job.raw_response_summary else None,
                    "attempt": attempt,
                },
            }
        )
    error = job.error
    exploration_error = _exploration_error_from_provider_error(error, attempt=attempt) if error else None
    return variant.model_copy(
        update={
            "status": "failed",
            "completed_at": now_iso(),
            "provider_metadata": {
                "provider": job.provider,
                "model": job.model,
                "status": job.status.value if isinstance(job.status, JobStatus) else str(job.status),
            },
            "error": exploration_error
            or ExplorationError(
                code="generation_failed",
                message="这个风格暂时无法生成。",
                retryable=False,
                detail={"attempt": attempt},
            ),
        }
    )


def _attach_lab_history_metadata(
    job: GenerationJob,
    *,
    session: ExplorationSession,
    variant: GenerationVariant,
    prompt: ComposedPrompt,
) -> None:
    if not job.outputs:
        return
    style = next((item for item in session.style_presets if item.id == variant.style_preset_id), None)
    if not style:
        return
    metadata = {
        "source_app": LAB_PROJECT_ID,
        "module": RARE_STYLE_FEATURE_ID,
        "module_label": "Rare Style Explorer",
        "idea": session.request.idea,
        "style_preset_id": style.id,
        "style_name": style.display_name,
        "style_family": style.family,
        "style_category": style.category,
        "keywords": style.tags,
        "mode": session.request.mode,
        "mode_label": _lab_mode_label(session.request.mode),
        "freshness": session.request.freshness,
        "aspect_ratio": session.request.aspect_ratio or "square",
        "target_count": session.request.target_count,
        "images_per_style": session.request.images_per_style,
        "generation_interval_seconds": session.request.generation_interval_seconds,
        "variant_id": variant.id,
        "prompt_id": prompt.id,
    }
    for output in job.outputs:
        output.metadata = {**output.metadata, "alchemy_lab": metadata}
    job.raw_response_summary = {**(job.raw_response_summary or {}), "alchemy_lab": metadata}
    repository.save_job(job)
    _append_lab_history_records(job, metadata)


def _append_lab_history_records(job: GenerationJob, metadata: dict[str, Any]) -> None:
    for output in job.outputs:
        if output.format not in {"png", "jpeg", "webp"}:
            continue
        media_store.save_history_record(
            {
                "id": output.id,
                "job_id": job.id,
                "session_id": job.session_id,
                "url": output.url,
                "thumbnail_url": output.thumbnail_url or output.url,
                "format": output.format,
                "width": output.width,
                "height": output.height,
                "provider": job.provider,
                "model": job.model,
                "requested_provider": job.raw_response_summary.get("requested_image_provider") if job.raw_response_summary else None,
                "requested_model": job.raw_response_summary.get("requested_image_model") if job.raw_response_summary else None,
                "provider_fallback": job.raw_response_summary.get("image_provider_fallback") if job.raw_response_summary else None,
                "asset_mode": job.asset_mode,
                "asset_intents": [],
                "asset_vision_profiles": [],
                "visual_review": output.visual_review.model_dump() if output.visual_review else None,
                "prompt_plan": job.prompt_plan.variables.get("advanced_prompt_plan") if job.prompt_plan and job.prompt_plan.variables else None,
                "original_prompt": job.provenance.get("original_prompt") if job.provenance else None,
                "final_prompt": job.provenance.get("final_prompt") if job.provenance else None,
                "source_app": LAB_PROJECT_ID,
                "idempotency_key": job.idempotency_key,
                "work_intensity": job.prompt_plan.variables.get("work_intensity") if job.prompt_plan and job.prompt_plan.variables else None,
                "work_intensity_label": job.prompt_plan.variables.get("work_intensity_label") if job.prompt_plan and job.prompt_plan.variables else None,
                "prompt": job.provenance.get("final_prompt") if job.provenance else None,
                "size": job.prompt_plan.size if job.prompt_plan else None,
                "version_parent_id": output.version_parent_id,
                "veyra_user_id": output.metadata.get("veyra_user_id"),
                "alchemy_lab": metadata,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
            }
        )


def is_lab_history_record(record: dict[str, Any]) -> bool:
    if record.get("source_app") == LAB_PROJECT_ID:
        return True
    if str(record.get("idempotency_key") or "").startswith("lab:"):
        return True
    if record.get("alchemy_lab"):
        return True
    return False


def _lab_history_item_from_record(record: dict[str, Any]) -> LabHistoryItem | None:
    if not is_lab_history_record(record):
        return None
    metadata = record.get("alchemy_lab") if isinstance(record.get("alchemy_lab"), dict) else {}
    prompt = str(record.get("final_prompt") or record.get("prompt") or "")
    source_prompt = "\n".join(
        str(value)
        for value in [record.get("original_prompt"), record.get("prompt"), record.get("final_prompt")]
        if value
    )
    inferred = _infer_lab_metadata_from_prompt(source_prompt)
    data = {**inferred, **metadata}
    style_name = _clean_lab_text(data.get("style_name")) or _clean_lab_text(inferred.get("style_name"))
    idea = (
        _clean_lab_text(data.get("idea"))
        or _infer_lab_idea(record.get("original_prompt"))
        or _infer_lab_idea(prompt)
    )
    title = f"Rare Style Explorer · {style_name}" if style_name else "Rare Style Explorer"
    return LabHistoryItem(
        id=str(record.get("id")),
        job_id=str(record.get("job_id") or ""),
        session_id=record.get("session_id"),
        title=title,
        style_preset_id=_clean_lab_text(data.get("style_preset_id")),
        style_name=style_name,
        style_family=_clean_lab_text(data.get("style_family")),
        style_category=_clean_lab_text(data.get("style_category")),
        keywords=[str(item) for item in (data.get("keywords") or []) if str(item).strip()][:8],
        idea=idea,
        mode=_clean_lab_text(data.get("mode")),
        mode_label=_clean_lab_text(data.get("mode_label")) or _lab_mode_label(data.get("mode")),
        freshness=_clean_lab_text(data.get("freshness")),
        aspect_ratio=_clean_lab_text(data.get("aspect_ratio")),
        generation_interval_seconds=_float_or_none(data.get("generation_interval_seconds")),
        target_count=_int_or_none(data.get("target_count")),
        images_per_style=_int_or_none(data.get("images_per_style")),
        url=str(record.get("url") or ""),
        thumbnail_url=record.get("thumbnail_url") or record.get("url"),
        format=str(record.get("format") or "png"),
        width=_int_or_none(record.get("width")),
        height=_int_or_none(record.get("height")),
        provider=record.get("provider"),
        model=record.get("model"),
        prompt=record.get("prompt"),
        final_prompt=record.get("final_prompt") or record.get("prompt"),
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
        source=record.get("source"),
    )


def _infer_lab_metadata_from_prompt(prompt: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for line in str(prompt or "").splitlines():
        clean = line.strip()
        if clean.startswith("稀有风格方向："):
            directives = [part.strip() for part in clean.removeprefix("稀有风格方向：").split("，") if part.strip()]
            if directives:
                metadata["style_name"] = directives[0]
                metadata["keywords"] = directives[:6]
    return metadata


def _infer_lab_idea(prompt: Any) -> str | None:
    for line in str(prompt or "").splitlines():
        clean = line.strip()
        if clean and not clean.startswith(("稀有风格方向：", "组合规则：", "图像要求：", "避免：")):
            return clean
    return None


def _lab_mode_label(mode: Any) -> str | None:
    labels = {item["id"]: item["label"] for item in _mode_options()}
    key = str(mode or "")
    return labels.get(key)


def _clean_lab_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _exploration_error_from_provider_error(error: Any, *, attempt: int = 0) -> ExplorationError:
    detail = dict(getattr(error, "detail", {}) or {})
    upstream_message = str(detail.get("message") or getattr(error, "message", "") or "")
    safe_message = _friendly_provider_error_message(
        code=str(getattr(error, "code", "") or ""),
        provider=str(getattr(error, "provider", "") or ""),
        upstream_message=upstream_message,
    )
    safe_detail = {key: value for key, value in detail.items() if key != "message"}
    safe_detail["attempt"] = attempt
    if upstream_message:
        safe_detail["upstream_error_hint"] = _redact_sensitive_text(upstream_message)[:500]
    return ExplorationError(
        code=str(getattr(error, "code", "") or "provider_error"),
        message=safe_message,
        retryable=bool(getattr(error, "retryable", False)) and attempt < MAX_RETRIES_PER_VARIANT,
        detail=safe_detail,
    )


def _friendly_provider_error_message(*, code: str, provider: str, upstream_message: str) -> str:
    text = upstream_message.lower()
    provider_label = _provider_label(provider)
    if code == "provider_not_configured" or "not configured" in text:
        return f"{provider_label} 还没有配置好，请到“模型与 API”检查 API Key 和模型设置。"
    if "invalid_api_key" in text or "incorrect api key" in text or "authenticationerror" in text or "401" in text:
        return f"{provider_label} API Key 无效，请到“模型与 API”更新后再试。"
    if "rate limit" in text or "429" in text or code == "rate_limit_error":
        return f"{provider_label} 当前限流或额度不足，请稍后再试，或切换可用生图通道。"
    if "temporarily unavailable" in text or "503" in text or "service unavailable" in text:
        return f"{provider_label} 服务暂时不可用，请稍后再试。"
    safe_hint = _redact_sensitive_text(upstream_message).strip()
    if safe_hint:
        return f"{provider_label} 生图失败：{safe_hint[:180]}"
    return f"{provider_label} 生图失败，请检查模型/API 配置或稍后重试。"


def _provider_label(provider: str) -> str:
    labels = {
        "openai_gpt_image": "OpenAI 生图通道",
        "gemini_image": "Gemini 生图通道",
        "doubao_image": "豆包生图通道",
        "mock_image": "Mock 生图通道",
    }
    return labels.get(provider or "", provider or "生图通道")


def _redact_sensitive_text(text: str) -> str:
    return re.sub(r"sk-[A-Za-z0-9_\-*]{8,}", "sk-***", str(text or ""))


def _is_fatal_provider_error(error: ExplorationError) -> bool:
    text = " ".join(
        [
            error.code,
            error.message,
            str(error.detail.get("error_type", "")),
            str(error.detail.get("upstream_error_hint", "")),
        ]
    ).lower()
    return any(marker in text for marker in ["invalid_api_key", "incorrect api key", "authenticationerror", "401", "provider_not_configured"])


def _skipped_variant(variant: GenerationVariant, cause: ExplorationError) -> GenerationVariant:
    return variant.model_copy(
        update={
            "status": "failed",
            "completed_at": now_iso(),
            "error": ExplorationError(
                code="provider_unavailable",
                message=cause.message,
                retryable=False,
                detail={"skipped_after_fatal_provider_error": True, "cause_code": cause.code},
            ),
        }
    )


def _exception_variant(variant: GenerationVariant, exc: Exception, *, attempt: int = 0) -> GenerationVariant:
    return variant.model_copy(
        update={
            "status": "failed",
            "completed_at": now_iso(),
            "error": ExplorationError(
                code="generation_exception",
                message="This style could not be generated.",
                retryable=attempt < MAX_RETRIES_PER_VARIANT,
                detail={"error_type": type(exc).__name__, "message": str(exc)[:500], "attempt": attempt},
            ),
        }
    )


def _size_from_aspect_ratio(aspect_ratio: str | None) -> str | None:
    if aspect_ratio in {"portrait", "9:16", "2:3"}:
        return "1024x1536"
    if aspect_ratio in {"landscape", "16:9", "3:2"}:
        return "1536x1024"
    if aspect_ratio in {"square", "1:1"}:
        return "1024x1024"
    return None


def _lab_media_session(session_id: str, *, title: str):
    from app.schemas import Session

    return Session(id=f"ses_{session_id}", project_id=LAB_PROJECT_ID, title=title, orchestration_mode="runtime_first", created_at=now_iso())
