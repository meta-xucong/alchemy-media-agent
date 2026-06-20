from __future__ import annotations

import asyncio
import json
import os
import random
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.repositories import repository
from app.schemas import GenerationJob, JobStatus
from app.services.alchemy_lab_quality import (
    QUALITY_ENHANCEMENT_OPTIONS,
    enhance_lab_prompt,
    local_quality_prompt,
    quality_summary,
)
from app.services.alchemy_lab_intent_director import (
    intent_prompt_block,
    plan_lab_intent,
    public_intent_metadata,
    style_family_hints,
)
from app.services.alchemy_lab_reference_policy import (
    LabReferencePolicyError,
    build_lab_reference_plan,
    lab_reference_metadata,
    public_reference_history_metadata,
)
from app.services.alchemy_lab_reference_prompt import append_lab_reference_prompt
from app.services.alchemy_lab_uploads_models import LabReferenceAssetInput
from app.services.image_service import run_submitted_image_job, submit_image_job
from app.services.utils import make_id, now_iso
from app.storage import media_store


MAX_SELECTED_STYLES = 8
MAX_IMAGES_PER_STYLE = 4
MAX_TOTAL_IMAGES = 12
MAX_CONCURRENT_GENERATIONS = 1
MAX_RETRIES_PER_VARIANT = 1
MAX_GENERATION_INTERVAL_SECONDS = 60
DEFAULT_GENERATION_INTERVAL_SECONDS = 8
MAX_RATE_LIMIT_BACKOFF_SECONDS = 180
TERMINAL_SESSION_STATUSES = {"completed", "partial_success", "failed"}
LAB_PROJECT_ID = "alchemy_lab_rare_style_explorer"
LAB_SOURCE_PREFIX = "alchemy_lab"
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
PRODUCT_REFERENCE_SHOWCASE_FAMILIES = {"film", "graphic", "illustration", "photography", "product", "space", "material", "digital"}
PRODUCT_REFERENCE_AVOID_FAMILIES = {"fashion"}
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
    generation_interval_seconds: float = Field(default=DEFAULT_GENERATION_INTERVAL_SECONDS, ge=0, le=MAX_GENERATION_INTERVAL_SECONDS)
    seed: int | None = None
    style_id: str | None = None
    avoid_generic: bool = True
    aspect_ratio: str | None = None
    provider_preference: str | None = None
    quality_enhancement: str = "auto"
    reference_assets: list[LabReferenceAssetInput] = Field(default_factory=list)
    reference_mode: str = "guided"
    intent_director: str = "auto"

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_quality_mode(cls, data: Any) -> Any:
        if isinstance(data, dict) and "quality_enhancement" not in data and "quality_enhancement_mode" in data:
            return {**data, "quality_enhancement": data.get("quality_enhancement_mode")}
        return data

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
    progress: dict[str, Any] = Field(default_factory=dict)
    reference_plan: dict[str, Any] | None = None
    intent_plan: dict[str, Any] | None = None


class ComparisonCard(BaseModel):
    variant_id: str
    style_preset_id: str
    style_name: str
    status: str
    image_url: str | None = None
    thumbnail_url: str | None = None
    prompt: str
    quality: dict[str, Any] = Field(default_factory=dict)
    reference: dict[str, Any] = Field(default_factory=dict)
    intent: dict[str, Any] = Field(default_factory=dict)
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
    quality_enhancement_mode: str | None = None
    quality_enhancement_strategy: str | None = None
    quality_enhancement_applied: bool = False
    text_hierarchy_applied: bool = False
    text_hierarchy_summary: str | None = None
    art_direction_summary: str | None = None
    intent_summary: str | None = None
    intent_target_use: str | None = None
    intent_confidence: str | None = None
    reference_summary: str | None = None
    reference_asset_roles: list[dict[str, Any]] = Field(default_factory=list)
    reference_warnings: list[str] = Field(default_factory=list)
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
_background_tasks: set[asyncio.Task] = set()


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
        "defaultGenerationIntervalSeconds": DEFAULT_GENERATION_INTERVAL_SECONDS,
        "maxRateLimitBackoffSeconds": MAX_RATE_LIMIT_BACKOFF_SECONDS,
        "styleLibrarySize": len(_style_presets()),
    }


async def create_exploration_session(request: ExplorationRequest, *, veyra_user_id: int | None = None) -> ExplorationSession:
    session = await prepare_exploration_session(request, veyra_user_id=veyra_user_id)
    if _should_run_inline(session.request):
        return await run_exploration_session(session.id, veyra_user_id=veyra_user_id)
    _schedule_exploration_session(session.id, veyra_user_id=veyra_user_id)
    return session


async def prepare_exploration_session(request: ExplorationRequest, *, veyra_user_id: int | None = None) -> ExplorationSession:
    request = _normalize_request(request)
    _validate_requested_style_count(request)
    intent_plan = await plan_lab_intent(request=request, veyra_user_id=veyra_user_id)
    reference_plan = _build_reference_plan_for_request(request, veyra_user_id=veyra_user_id, intent_plan=intent_plan)
    selected = _resolve_styles(request, intent_plan=intent_plan)
    _validate_batch(request, selected)
    timestamp = now_iso()
    variant_counts = _variant_counts_by_style(request, selected)
    total_variants = sum(variant_counts.values())
    session = ExplorationSession(
        id=make_id("lab"),
        status="queued",
        created_at=timestamp,
        updated_at=timestamp,
        request=request,
        style_presets=selected,
        progress=_progress_payload(total=total_variants, status="queued", message="等待开始串行生成。"),
        reference_plan=reference_plan,
        intent_plan=intent_plan,
    )
    lab_store.save(session)

    prompts = [_compose_prompt(session.id, request, style, reference_plan=reference_plan, intent_plan=intent_plan) for style in selected]
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
        for index in range(variant_counts.get(prompt.style_preset_id, 0))
    ]
    session.updated_at = now_iso()
    session.progress = _progress_payload(total=len(session.variants), status="queued", message="已建立任务，将逐张生成。")
    return lab_store.save(session)


async def run_exploration_session(session_id: str, *, veyra_user_id: int | None = None) -> ExplorationSession:
    session = lab_store.get(session_id)
    if not session:
        raise ValueError("Exploration session not found.")
    if session.status in TERMINAL_SESSION_STATUSES:
        return session

    fatal_provider_error: ExplorationError | None = None
    total = len(session.variants)
    session.status = "running"
    session.progress = _progress_payload(
        total=total,
        completed=_completed_variant_count(session),
        failed=_failed_variant_count(session),
        current=0,
        status="running",
        message="正在准备提示词增强，然后逐张串行生成。",
    )
    session.updated_at = now_iso()
    lab_store.save(session)
    await _ensure_session_prompts_enhanced(session)

    media_session = repository.save_session(
        _lab_media_session(session.id, title=f"Alchemy Lab: {session.request.idea[:48]}")
    )
    prompt_by_id = {prompt.id: prompt for prompt in session.prompts}

    async def run_variant(variant: GenerationVariant) -> GenerationVariant:
        nonlocal fatal_provider_error
        if fatal_provider_error:
            return _skipped_variant(variant, fatal_provider_error)
        variant.status = "running"
        session.updated_at = now_iso()
        lab_store.save(session)
        prompt = prompt_by_id[variant.prompt_id]
        last_variant = variant
        for attempt in range(MAX_RETRIES_PER_VARIANT + 1):
            try:
                prepared = await submit_image_job(
                    session_id=media_session.id,
                    prompt=prompt.final_prompt,
                    asset_mode="lab_reference" if session.reference_plan else "basic",
                    external_asset_plan=session.reference_plan,
                    count=1,
                    size=_size_from_aspect_ratio(session.request.aspect_ratio),
                    quality="high",
                    output_format="png",
                    work_intensity="lab_quality",
                    provider_preference=session.request.provider_preference,
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
                await _sleep_before_retry(last_variant.error, attempt=attempt)
            except Exception as exc:
                last_variant = _exception_variant(variant, exc, attempt=attempt)
                if not last_variant.error.retryable or attempt >= MAX_RETRIES_PER_VARIANT:
                    return last_variant
                await _sleep_before_retry(last_variant.error, attempt=attempt)
        return last_variant

    for index, variant in enumerate(list(session.variants)):
        if fatal_provider_error:
            result = _skipped_variant(variant, fatal_provider_error)
        else:
            session.progress = _progress_payload(
                total=total,
                completed=_completed_variant_count(session),
                failed=_failed_variant_count(session),
                current=index + 1,
                current_variant_id=variant.id,
                status="running",
                message=f"正在生成第 {index + 1}/{total} 张。",
            )
            session.updated_at = now_iso()
            lab_store.save(session)
            result = await run_variant(variant)
        _replace_variant(session, result)
        session.errors = [item.error for item in session.variants if item.error]
        wait_seconds = _cooldown_after_variant(session.request, result, is_last=index >= total - 1)
        session.progress = _progress_payload(
            total=total,
            completed=_completed_variant_count(session),
            failed=_failed_variant_count(session),
            current=index + 1,
            current_variant_id=result.id,
            status="running",
            next_wait_seconds=wait_seconds,
            message=_variant_progress_message(index=index, total=total, result=result),
        )
        session.updated_at = now_iso()
        lab_store.save(session)
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

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
    session.progress = _progress_payload(
        total=total,
        completed=len(succeeded),
        failed=len(failed),
        current=total,
        status=session.status,
        message=f"串行生成结束：成功 {len(succeeded)} 张，失败 {len(failed)} 张。",
    )
    return lab_store.save(session)


def get_exploration_session(session_id: str) -> ExplorationSession | None:
    return lab_store.get(session_id)


def public_exploration_session(session: ExplorationSession) -> dict[str, Any]:
    payload = session.model_dump()
    reference_plan = payload.get("reference_plan")
    if isinstance(reference_plan, dict):
        payload["reference_plan"] = _public_reference_plan(reference_plan)
    return payload


def update_favorites(session_id: str, selection: FavoriteSelection) -> ExplorationSession | None:
    session = lab_store.get(session_id)
    if not session:
        return None
    valid_ids = {variant.id for variant in session.variants}
    favorites = [variant_id for variant_id in selection.variant_ids if variant_id in valid_ids]
    session.favorites = favorites
    session.updated_at = now_iso()
    return lab_store.save(session)


def _public_reference_plan(reference_plan: dict[str, Any]) -> dict[str, Any]:
    public_assets = []
    for item in reference_plan.get("assets") or []:
        if not isinstance(item, dict):
            continue
        public_assets.append(
            {
                "role": item.get("role"),
                "role_label": item.get("role_label"),
                "constraint_strength": item.get("constraint_strength"),
                "priority": item.get("priority"),
                "provider_input_mode": item.get("provider_input_mode"),
                "mime_type": item.get("mime_type"),
                "brief": item.get("brief"),
                "visual_summary": item.get("visual_summary"),
                "notes": item.get("notes"),
                "requires_image_reference": bool(item.get("requires_image_reference")),
                "director_directive": item.get("director_directive") or {},
            }
        )
    provider_input_plan = reference_plan.get("provider_input_plan") if isinstance(reference_plan.get("provider_input_plan"), dict) else {}
    return {
        "asset_mode": reference_plan.get("asset_mode"),
        "source": reference_plan.get("source"),
        "summary": reference_plan.get("summary"),
        "public_summary": reference_plan.get("public_summary"),
        "assets": public_assets,
        "warnings": reference_plan.get("warnings") or [],
        "provider_input_plan": {
            key: value
            for key, value in provider_input_plan.items()
            if key not in {"reference_asset_ids"}
        },
        "prompt_constraints": reference_plan.get("prompt_constraints") or [],
    }


def list_lab_history(*, limit: int = 50, include_mock: bool = False) -> dict[str, Any]:
    records = media_store.list_history_records(limit=10000)
    items = [
        item
        for item in (_lab_history_item_from_record(record) for record in records)
        if item is not None
    ]
    if not include_mock:
        items = [item for item in items if not _is_mock_lab_history_item(item)]
    items.sort(key=lambda item: item.created_at or item.updated_at or "", reverse=True)
    return {"items": [item.model_dump() for item in items[:limit]], "total": len(items)}


def _is_mock_lab_history_item(item: LabHistoryItem) -> bool:
    provider = str(item.provider or "").strip().lower()
    model = str(item.model or "").strip().lower()
    return provider in {"mock", "mock_image"} or model.startswith("mock-")


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
                    quality=quality_summary(prompt.prompt_metadata) if prompt else {},
                    reference=_reference_summary_for_prompt(prompt),
                    intent=_intent_summary_for_prompt(prompt),
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


def _should_run_inline(request: ExplorationRequest) -> bool:
    return str(request.provider_preference or "").strip() == "mock_image"


async def _ensure_session_prompts_enhanced(session: ExplorationSession) -> None:
    if not session.prompts:
        return
    enhanced: list[ComposedPrompt] = []
    for index, prompt in enumerate(session.prompts):
        quality = (prompt.prompt_metadata or {}).get("quality_enhancement")
        if isinstance(quality, dict):
            enhanced.append(prompt)
            continue
        style = next((item for item in session.style_presets if item.id == prompt.style_preset_id), None)
        if not style:
            enhanced.append(prompt)
            continue
        session.progress = {
            **(session.progress or {}),
            "message": f"正在准备第 {index + 1}/{len(session.prompts)} 个风格的提示词增强。",
            "updated_at": now_iso(),
        }
        session.updated_at = now_iso()
        lab_store.save(session)
        enhanced.append(
            await enhance_lab_prompt(
                request=session.request,
                style=style,
                prompt=prompt,
                selected_styles=session.style_presets,
                composer_factory=local_quality_prompt,
            )
        )
    session.prompts = enhanced
    session.updated_at = now_iso()
    lab_store.save(session)


def _schedule_exploration_session(session_id: str, *, veyra_user_id: int | None = None) -> None:
    task = asyncio.create_task(_run_exploration_session_guarded(session_id, veyra_user_id=veyra_user_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _run_exploration_session_guarded(session_id: str, *, veyra_user_id: int | None = None) -> None:
    try:
        await run_exploration_session(session_id, veyra_user_id=veyra_user_id)
    except Exception as exc:
        session = lab_store.get(session_id)
        if not session:
            return
        error = ExplorationError(
            code="session_background_failed",
            message="批量生成后台任务失败。",
            retryable=True,
            detail={"error_type": type(exc).__name__, "message": str(exc)[:500]},
        )
        session.errors = [*session.errors, error]
        for variant in session.variants:
            if variant.status in {"queued", "running"}:
                _replace_variant(session, _exception_variant(variant, exc, attempt=MAX_RETRIES_PER_VARIANT))
        succeeded = _completed_variant_count(session)
        failed = _failed_variant_count(session)
        session.status = "partial_success" if succeeded else "failed"
        session.progress = _progress_payload(
            total=len(session.variants),
            completed=succeeded,
            failed=failed,
            status=session.status,
            message=f"后台任务异常停止：成功 {succeeded} 张，失败 {failed} 张。",
        )
        session.updated_at = now_iso()
        lab_store.save(session)


def _replace_variant(session: ExplorationSession, replacement: GenerationVariant) -> None:
    session.variants = [replacement if item.id == replacement.id else item for item in session.variants]


def _completed_variant_count(session: ExplorationSession) -> int:
    return sum(1 for item in session.variants if item.status == "succeeded")


def _failed_variant_count(session: ExplorationSession) -> int:
    return sum(1 for item in session.variants if item.status == "failed")


def _progress_payload(
    *,
    total: int,
    completed: int = 0,
    failed: int = 0,
    current: int = 0,
    current_variant_id: str | None = None,
    status: str = "queued",
    next_wait_seconds: float = 0.0,
    message: str = "",
) -> dict[str, Any]:
    total = max(0, int(total or 0))
    completed = max(0, int(completed or 0))
    failed = max(0, int(failed or 0))
    current = max(0, int(current or 0))
    percent = 100 if total <= 0 else min(100, round(((completed + failed) / total) * 100))
    return {
        "status": status,
        "total": total,
        "completed": completed,
        "failed": failed,
        "current": current,
        "current_variant_id": current_variant_id,
        "pending": max(0, total - completed - failed),
        "percent": percent,
        "next_wait_seconds": round(max(0.0, float(next_wait_seconds or 0)), 2),
        "message": message,
        "updated_at": now_iso(),
    }


async def _sleep_before_retry(error: ExplorationError | None, *, attempt: int) -> None:
    delay = _retry_backoff_seconds(error, attempt=attempt)
    if delay > 0:
        await asyncio.sleep(delay)


def _cooldown_after_variant(request: ExplorationRequest, variant: GenerationVariant, *, is_last: bool) -> float:
    if is_last:
        return 0.0
    if variant.error and _is_rate_or_service_pressure(variant.error):
        retry_after = _retry_after_from_error(variant.error)
        base = retry_after if retry_after is not None else max(30.0, float(request.generation_interval_seconds or 0) * 2)
        return _jittered_delay(min(max(base, 30.0), MAX_RATE_LIMIT_BACKOFF_SECONDS), variant.id)
    provider = str(request.provider_preference or "").strip().lower()
    if provider in {"mock_image", "mock"} and "generation_interval_seconds" not in getattr(request, "model_fields_set", set()):
        return 0.0
    return max(0.0, float(request.generation_interval_seconds or 0))


def _retry_backoff_seconds(error: ExplorationError | None, *, attempt: int) -> float:
    if not error:
        return 0.0
    retry_after = _retry_after_from_error(error)
    if retry_after is not None:
        return min(max(retry_after, 1.0), MAX_RATE_LIMIT_BACKOFF_SECONDS)
    base = 8.0 if _is_rate_or_service_pressure(error) else 2.0
    delay = min(base * (2 ** max(0, attempt)), MAX_RATE_LIMIT_BACKOFF_SECONDS)
    return _jittered_delay(delay, f"{error.code}:{attempt}")


def _retry_after_from_error(error: ExplorationError) -> float | None:
    for key in ["retry_after_seconds", "upstream_retry_after_seconds"]:
        value = error.detail.get(key)
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    local_guard = error.detail.get("local_rate_guard")
    if isinstance(local_guard, dict):
        try:
            number = float(local_guard.get("retry_after_seconds"))
        except (TypeError, ValueError):
            number = 0.0
        if number > 0:
            return number
    return None


def _is_rate_or_service_pressure(error: ExplorationError) -> bool:
    text = " ".join(
        [
            error.code,
            error.message,
            str(error.detail.get("error_type", "")),
            str(error.detail.get("rate_limit_scope", "")),
            str(error.detail.get("upstream_error_hint", "")),
            str(error.detail.get("message", "")),
        ]
    ).lower()
    markers = [
        "rate_limit",
        "rate limit",
        "429",
        "too many requests",
        "temporarily unavailable",
        "service unavailable",
        "503",
        "502",
        "504",
        "timeout",
        "timed out",
        "cooldown",
    ]
    return any(marker in text for marker in markers)


def _jittered_delay(base_seconds: float, key: str) -> float:
    base = max(0.0, float(base_seconds or 0))
    if base <= 0:
        return 0.0
    rng = random.Random(f"{key}:{int(time.time() // 30)}")
    return min(MAX_RATE_LIMIT_BACKOFF_SECONDS, base + rng.uniform(0.0, min(6.0, base * 0.25)))


def _variant_progress_message(*, index: int, total: int, result: GenerationVariant) -> str:
    current = index + 1
    if result.status == "succeeded":
        return f"第 {current}/{total} 张已完成，等待后继续下一张。"
    if result.error and _is_rate_or_service_pressure(result.error):
        return f"第 {current}/{total} 张遇到上游限流或服务繁忙，已进入冷却等待。"
    return f"第 {current}/{total} 张失败，继续串行处理剩余任务。"


def _resolve_styles(request: ExplorationRequest, *, intent_plan: dict[str, Any] | None = None) -> list[StylePreset]:
    enabled = [style for style in _style_presets() if style.is_enabled]
    by_id = {style.id: style for style in enabled}
    for legacy_id, canonical_id in LEGACY_STYLE_ALIASES.items():
        if canonical_id in by_id:
            by_id[legacy_id] = by_id[canonical_id]
    explicit_id = (request.style_id or "").strip()
    style_ids = [explicit_id] if explicit_id else list(request.selected_style_ids or [])
    if not style_ids:
        return _auto_select_styles(request, enabled, intent_plan=intent_plan)
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
    total = _target_total_for_request(request, selected)
    capacity = len(selected) * _images_per_style_for_request(request)
    if total > capacity:
        raise ValueError("Choose more styles or lower the total image count.")
    if total > MAX_TOTAL_IMAGES:
        raise ValueError(f"That is too many images for one run. Maximum is {MAX_TOTAL_IMAGES}.")


def _compose_prompt(
    session_id: str,
    request: ExplorationRequest,
    style: StylePreset,
    *,
    reference_plan: dict[str, Any] | None = None,
    intent_plan: dict[str, Any] | None = None,
) -> ComposedPrompt:
    prompt_lines = [
        f"{request.idea}",
        "稀有风格方向：" + "，".join(style.prompt_directives),
        "组合规则：一个强主风格，最多一个材质/光色层，最多一个版式/空间层，缺陷层保持轻量。",
        "图像要求：主体轮廓清晰，视觉识别度强，高细节。",
        "避免：" + "，".join([*ANTI_DRIFT, *style.negative_directives]),
    ]
    intent_block = intent_prompt_block(intent_plan)
    if intent_block:
        prompt_lines.append(intent_block)
    if request.mode == "product":
        prompt_lines.append("产品要求：造型可读，干净背景，无杂物，产品保持可识别。")
    elif request.mode == "character":
        prompt_lines.append("人物要求：面部清晰，姿态有表现力，只保留1-2个关键配饰。")
    elif request.mode == "poster":
        prompt_lines.append("海报要求：少量伪文字，明确标题区域，不要长段可读文字。")
    final_prompt = append_lab_reference_prompt("\n".join(prompt_lines), reference_plan)
    reference_metadata = lab_reference_metadata(reference_plan)
    intent_metadata = public_intent_metadata(intent_plan)
    return ComposedPrompt(
        id=make_id("prompt"),
        session_id=session_id,
        style_preset_id=style.id,
        style_preset_version=style.version,
        idea=request.idea,
        final_prompt=final_prompt,
        prompt_metadata={
            "family": style.family,
            "mode": request.mode,
            "freshness": request.freshness,
            "style_family": style.family,
            "target_count": request.target_count,
            "generation_interval_seconds": request.generation_interval_seconds,
            "avoid_generic": request.avoid_generic,
            "quality_enhancement_mode": request.quality_enhancement,
            "source": "alchemy_lab_behavior_compatible_rare_style_explorer",
            "intent_director": intent_metadata,
            **reference_metadata,
        },
    )


def _normalize_request(request: ExplorationRequest) -> ExplorationRequest:
    mode = str(request.mode or "minimal").strip()
    freshness = str(request.freshness or "high").strip()
    family = str(request.style_family or "").strip() or None
    quality_enhancement = str(request.quality_enhancement or "auto").strip().lower()
    reference_mode = str(request.reference_mode or "guided").strip().lower()
    intent_director = str(request.intent_director or "auto").strip().lower()
    if mode not in MODE_OPTIONS:
        mode = "minimal"
    if freshness not in FRESHNESS_OPTIONS:
        freshness = "high"
    if family not in STYLE_FAMILIES:
        family = None
    if quality_enhancement not in QUALITY_ENHANCEMENT_OPTIONS:
        quality_enhancement = "auto"
    if reference_mode not in {"off", "guided"}:
        reference_mode = "guided"
    if intent_director not in {"auto", "off"}:
        intent_director = "auto"
    update: dict[str, Any] = {
        "mode": mode,
        "freshness": freshness,
        "style_family": family,
        "quality_enhancement": quality_enhancement,
        "reference_mode": reference_mode,
        "intent_director": intent_director,
    }
    return request.model_copy(update=update)


def _build_reference_plan_for_request(
    request: ExplorationRequest,
    *,
    veyra_user_id: int | None = None,
    intent_plan: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if request.reference_mode == "off" or not request.reference_assets:
        return None
    try:
        return build_lab_reference_plan(
            request.reference_assets,
            user_prompt=request.idea,
            veyra_user_id=veyra_user_id,
            intent_plan=intent_plan,
        )
    except LabReferencePolicyError as exc:
        raise ValueError(str(exc)) from exc


def _reference_summary_for_prompt(prompt: ComposedPrompt | None) -> dict[str, Any]:
    if not prompt:
        return {}
    metadata = prompt.prompt_metadata or {}
    return {
        "summary": metadata.get("reference_summary"),
        "asset_roles": metadata.get("reference_asset_roles") or [],
        "provider_input_plan": metadata.get("provider_input_plan"),
        "warnings": metadata.get("reference_warnings") or [],
    }


def _intent_summary_for_prompt(prompt: ComposedPrompt | None) -> dict[str, Any]:
    if not prompt:
        return public_intent_metadata(None)
    metadata = prompt.prompt_metadata or {}
    intent = metadata.get("intent_director")
    return intent if isinstance(intent, dict) else public_intent_metadata(None)


def _has_manual_style_selection(request: ExplorationRequest) -> bool:
    return bool((request.style_id or "").strip() or request.selected_style_ids)


def _images_per_style_for_request(request: ExplorationRequest) -> int:
    return max(1, min(int(request.images_per_style or 1), MAX_IMAGES_PER_STYLE))


def _target_total_for_request(request: ExplorationRequest, selected: list[StylePreset] | None = None) -> int:
    if selected and _has_manual_style_selection(request) and "target_count" not in getattr(request, "model_fields_set", set()):
        return max(1, len(selected) * _images_per_style_for_request(request))
    return max(1, min(int(request.target_count or 1), MAX_TOTAL_IMAGES))


def _variant_counts_by_style(request: ExplorationRequest, selected: list[StylePreset]) -> dict[str, int]:
    if not selected:
        return {}
    max_per_style = max(1, min(int(request.images_per_style or 1), MAX_IMAGES_PER_STYLE))
    target_total = min(_target_total_for_request(request, selected), len(selected) * max_per_style)
    counts: dict[str, int] = {style.id: 0 for style in selected}
    remaining = target_total
    for style in selected:
        if remaining <= 0:
            break
        count = min(max_per_style, remaining)
        counts[style.id] = count
        remaining -= count
    return counts


def _auto_select_styles(
    request: ExplorationRequest,
    enabled: list[StylePreset],
    *,
    intent_plan: dict[str, Any] | None = None,
) -> list[StylePreset]:
    pool = [style for style in enabled if not request.style_family or style.family == request.style_family]
    if not request.style_family:
        hinted_families = _auto_style_families_for_request(request, intent_plan=intent_plan)
        if hinted_families:
            hinted_pool = [style for style in pool if style.family in hinted_families]
            if hinted_pool:
                pool = hinted_pool
    if not pool:
        pool = enabled
    per_style = _images_per_style_for_request(request)
    target_total = max(1, min(int(request.target_count or 4), MAX_TOTAL_IMAGES))
    count = max(1, min((target_total + per_style - 1) // per_style, MAX_SELECTED_STYLES, len(pool)))
    rng = random.Random(request.seed)
    selected: list[StylePreset] = []
    used_categories: set[str] = set()
    used_families: set[str] = set()
    used_terms: list[set[str]] = []
    while pool and len(selected) < count:
        selected_ids = {item.id for item in selected}
        candidates = [
            style
            for style in pool
            if style.id not in selected_ids
            and (style.family not in used_families or len(used_families) >= 4)
            and (style.category not in used_categories or len(used_categories) >= 4)
            and (not request.avoid_generic or not _too_similar(style, used_terms))
        ]
        if not candidates:
            candidates = [style for style in pool if style.id not in selected_ids]
        if not candidates:
            break
        style = _weighted_style_choice(rng, candidates, freshness=request.freshness, avoid_generic=request.avoid_generic)
        selected.append(style)
        used_families.add(style.family)
        used_categories.add(style.category)
        terms = _meaningful_terms(style)
        if terms:
            used_terms.append(terms)
    if not selected:
        selected = [style for style in enabled if style.is_beginner_default][: min(4, count)]
    if not selected:
        raise ValueError("Please choose at least one available style.")
    return selected


def _auto_style_families_for_request(request: ExplorationRequest, *, intent_plan: dict[str, Any] | None = None) -> set[str]:
    if str(request.intent_director or "auto").strip().lower() == "off":
        return set()
    hinted = set(style_family_hints(intent_plan))
    if _should_use_product_reference_showcase_sampling(request, intent_plan=intent_plan):
        return set(PRODUCT_REFERENCE_SHOWCASE_FAMILIES) - set(PRODUCT_REFERENCE_AVOID_FAMILIES)
    return hinted


def _should_use_product_reference_showcase_sampling(
    request: ExplorationRequest,
    *,
    intent_plan: dict[str, Any] | None = None,
) -> bool:
    if str(request.intent_director or "auto").strip().lower() == "off":
        return False
    if not request.reference_assets:
        return False
    if _has_manual_style_selection(request) or request.style_family:
        return False
    if _target_total_for_request(request) < 3:
        return False
    mode = str(request.mode or "").strip().lower()
    target_use = str((intent_plan or {}).get("target_use") or "").strip().lower()
    text = request.idea.lower()
    if mode in {"product", "material-series"} or target_use in {"product", "packaging", "material"}:
        return True
    return any(marker in text for marker in ["产品", "商品", "包装", "瓶", "罐", "product", "packaging", "bottle"])


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
    quality = quality_summary(prompt.prompt_metadata)
    reference = public_reference_history_metadata(session.reference_plan)
    intent = public_intent_metadata(session.intent_plan)
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
        "intent_summary": intent.get("summary"),
        "intent_target_use": intent.get("target_use"),
        "intent_confidence": intent.get("confidence"),
        "intent_director": intent,
        **quality,
        **reference,
    }
    for output in job.outputs:
        output.metadata = {**output.metadata, "alchemy_lab": metadata}
    job.raw_response_summary = {**(job.raw_response_summary or {}), "alchemy_lab": metadata}
    repository.save_job(job)
    _append_lab_history_records(job, metadata, prompt=prompt)


def _append_lab_history_records(job: GenerationJob, metadata: dict[str, Any], *, prompt: ComposedPrompt) -> None:
    original_prompt = job.provenance.get("original_prompt") if job.provenance else None
    final_prompt = job.provenance.get("final_prompt") if job.provenance else None
    original_prompt = original_prompt or prompt.idea
    final_prompt = final_prompt or prompt.final_prompt
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
                "asset_intents": metadata.get("reference_asset_roles") or [],
                "asset_vision_profiles": [],
                "provider_input_plan": metadata.get("provider_input_plan"),
                "visual_review": output.visual_review.model_dump() if output.visual_review else None,
                "prompt_plan": job.prompt_plan.variables.get("advanced_prompt_plan") if job.prompt_plan and job.prompt_plan.variables else None,
                "original_prompt": original_prompt,
                "final_prompt": final_prompt,
                "source_app": LAB_PROJECT_ID,
                "idempotency_key": job.idempotency_key,
                "work_intensity": job.prompt_plan.variables.get("work_intensity") if job.prompt_plan and job.prompt_plan.variables else None,
                "work_intensity_label": job.prompt_plan.variables.get("work_intensity_label") if job.prompt_plan and job.prompt_plan.variables else None,
                "prompt": final_prompt,
                "size": job.prompt_plan.size if job.prompt_plan else None,
                "version_parent_id": output.version_parent_id,
                "veyra_user_id": output.metadata.get("veyra_user_id"),
                "alchemy_lab": metadata,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
            }
        )


def is_lab_history_record(record: dict[str, Any]) -> bool:
    source_app = str(record.get("source_app") or "")
    if source_app == LAB_PROJECT_ID:
        return True
    if source_app.startswith(f"{LAB_SOURCE_PREFIX}_") or source_app.startswith(f"{LAB_SOURCE_PREFIX}:"):
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
    module = _lab_module_from_record(data, record)
    module_label = _lab_module_label(module, data)
    style_name = _clean_lab_text(data.get("style_name")) or _clean_lab_text(inferred.get("style_name"))
    idea = (
        _clean_lab_text(data.get("idea"))
        or _infer_lab_idea(record.get("original_prompt"))
        or _infer_lab_idea(prompt)
    )
    title = f"{module_label} · {style_name}" if style_name else module_label
    return LabHistoryItem(
        id=str(record.get("id")),
        job_id=str(record.get("job_id") or ""),
        session_id=record.get("session_id"),
        module=module,
        module_label=module_label,
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
        quality_enhancement_mode=_clean_lab_text(data.get("quality_enhancement_mode")),
        quality_enhancement_strategy=_clean_lab_text(data.get("quality_enhancement_strategy")),
        quality_enhancement_applied=bool(data.get("quality_enhancement_applied")),
        text_hierarchy_applied=bool(data.get("text_hierarchy_applied")),
        text_hierarchy_summary=_clean_lab_text(data.get("text_hierarchy_summary")),
        art_direction_summary=_clean_lab_text(data.get("art_direction_summary")),
        intent_summary=_clean_lab_text(data.get("intent_summary")),
        intent_target_use=_clean_lab_text(data.get("intent_target_use")),
        intent_confidence=_clean_lab_text(data.get("intent_confidence")),
        reference_summary=_clean_lab_text(data.get("reference_summary")),
        reference_asset_roles=[
            {
                "role": str(item.get("role") or ""),
                "role_label": str(item.get("role_label") or ""),
                "constraint_strength": str(item.get("constraint_strength") or ""),
            }
            for item in (data.get("reference_asset_roles") or [])
            if isinstance(item, dict)
        ],
        reference_warnings=[str(item) for item in (data.get("reference_warnings") or []) if str(item).strip()],
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


def _lab_module_from_record(data: dict[str, Any], record: dict[str, Any]) -> str:
    module = _clean_lab_text(data.get("module")) or _clean_lab_text(record.get("module"))
    if module:
        return module
    source_app = _clean_lab_text(record.get("source_app")) or ""
    if source_app == LAB_PROJECT_ID:
        return RARE_STYLE_FEATURE_ID
    if source_app.startswith(f"{LAB_SOURCE_PREFIX}_"):
        return source_app.removeprefix(f"{LAB_SOURCE_PREFIX}_").replace("_", "-")
    if source_app.startswith(f"{LAB_SOURCE_PREFIX}:"):
        return source_app.removeprefix(f"{LAB_SOURCE_PREFIX}:").replace("_", "-")
    return RARE_STYLE_FEATURE_ID


def _lab_module_label(module: str, data: dict[str, Any]) -> str:
    label = _clean_lab_text(data.get("module_label")) or _clean_lab_text(data.get("feature_label"))
    if label:
        return label
    if module in {RARE_STYLE_FEATURE_ID, LAB_PROJECT_ID}:
        return "Rare Style Explorer"
    words = [part for part in re.split(r"[-_\s]+", module) if part]
    if not words:
        return "Alchemy Lab"
    return " ".join(word[:1].upper() + word[1:] for word in words)


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
