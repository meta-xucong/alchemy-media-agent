from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.repositories import repository
from app.schemas import GenerationJob, JobStatus
from app.services.image_service import run_submitted_image_job, submit_image_job
from app.services.utils import make_id, now_iso


MAX_SELECTED_STYLES = 8
MAX_IMAGES_PER_STYLE = 2
MAX_TOTAL_IMAGES = 12
MAX_CONCURRENT_GENERATIONS = 3
MAX_RETRIES_PER_VARIANT = 1
LAB_PROJECT_ID = "alchemy_lab_rare_style_explorer"

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
    images_per_style: int = Field(default=1, ge=1, le=MAX_IMAGES_PER_STYLE)
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


STYLE_PRESETS = [
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
                "id": "rare-style-explorer",
                "title": "rare-style-explorer",
                "description": "Explore rare visual sub-styles for one image idea.",
            }
        ]
    }


def list_style_presets() -> dict[str, Any]:
    return {
        "styles": [style.model_dump() for style in STYLE_PRESETS if style.is_enabled],
        "limits": limits(),
    }


def limits() -> dict[str, int]:
    return {
        "maxSelectedStyles": MAX_SELECTED_STYLES,
        "maxImagesPerStyle": MAX_IMAGES_PER_STYLE,
        "maxTotalImages": MAX_TOTAL_IMAGES,
        "maxConcurrentGenerations": MAX_CONCURRENT_GENERATIONS,
        "maxRetriesPerVariant": MAX_RETRIES_PER_VARIANT,
    }


async def create_exploration_session(request: ExplorationRequest, *, veyra_user_id: int | None = None) -> ExplorationSession:
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

    async def run_variant(variant: GenerationVariant) -> GenerationVariant:
        async with semaphore:
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
                    last_variant = _variant_from_job(variant, job, attempt=attempt)
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
    enabled = [style for style in STYLE_PRESETS if style.is_enabled]
    by_id = {style.id: style for style in enabled}
    style_ids = request.selected_style_ids or [style.id for style in enabled if style.is_beginner_default][:4]
    selected = []
    missing = []
    for style_id in style_ids:
        style = by_id.get(style_id)
        if not style:
            missing.append(style_id)
            continue
        if request.style_family and style.family != request.style_family:
            continue
        selected.append(style)
    if missing:
        raise ValueError(f"Unknown style preset: {', '.join(missing)}")
    if not selected:
        raise ValueError("Please choose at least one available style.")
    return selected


def _validate_batch(request: ExplorationRequest, selected: list[StylePreset]) -> None:
    if len(selected) > MAX_SELECTED_STYLES:
        raise ValueError(f"Choose no more than {MAX_SELECTED_STYLES} styles.")
    total = len(selected) * request.images_per_style
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
            "source": "alchemy_lab_behavior_compatible_rare_style_explorer",
        },
    )


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
    return variant.model_copy(
        update={
            "status": "failed",
            "completed_at": now_iso(),
            "provider_metadata": {
                "provider": job.provider,
                "model": job.model,
                "status": job.status.value if isinstance(job.status, JobStatus) else str(job.status),
            },
            "error": ExplorationError(
                code=error.code if error else "generation_failed",
                message=error.message if error else "This style could not be generated.",
                retryable=(bool(error.retryable) if error else False) and attempt < MAX_RETRIES_PER_VARIANT,
                detail={**(error.detail if error else {}), "attempt": attempt},
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
