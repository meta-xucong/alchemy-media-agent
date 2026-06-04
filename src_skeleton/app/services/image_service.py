from __future__ import annotations

import hashlib

from app.providers.base import ProviderRuntimeError
from app.config import settings
from app.providers.registry import registry
from app.repositories import repository
from app.schemas import (
    CostEstimate,
    GenerationJob,
    GenerationOutput,
    ImageGenerationRequest,
    JobStatus,
    ProviderError,
    ReviseImageRequest,
)
from app.services.evaluation import score_image_output
from app.services.prompting import apply_patch_to_plan, build_prompt_plan, build_revision_patch
from app.services.safety import check_generation_prompt
from app.services.utils import make_id, now_iso
from app.services.work_intensity import apply_work_intensity
from app.storage import media_store


async def create_image_job(
    *,
    session_id: str,
    prompt: str,
    asset_ids: list[str] | None = None,
    count: int = 1,
    size: str = "1024x1024",
    quality: str = "auto",
    output_format: str = "png",
    work_intensity: str | None = None,
    provider_preference: str | None = None,
    idempotency_key: str | None = None,
) -> GenerationJob:
    asset_ids = asset_ids or []
    work_intensity = work_intensity or settings.image_work_intensity
    prompt_plan = build_prompt_plan(
        prompt=prompt,
        count=count,
        size=size,
        quality=quality,
        output_format=output_format,
        asset_ids=asset_ids,
    )
    key = idempotency_key or _idempotency_key(session_id, prompt_plan.model_dump_json(), asset_ids, provider_preference, work_intensity)
    existing = repository.get_job_by_idempotency_key(key)
    if existing:
        return existing

    trace_id = make_id("trace")
    created_at = now_iso()
    job = GenerationJob(
        id=make_id("job"),
        session_id=session_id,
        job_type="image",
        status=JobStatus.created,
        prompt_plan=prompt_plan,
        idempotency_key=key,
        trace_id=trace_id,
        created_at=created_at,
        updated_at=created_at,
    )

    safety_error = check_generation_prompt(prompt)
    if safety_error:
        job.status = JobStatus.rejected
        job.error = safety_error
        job.updated_at = now_iso()
        return repository.save_job(job)

    prompt_plan, planning_summary = await apply_work_intensity(
        prompt_plan,
        original_prompt=prompt,
        work_intensity=work_intensity,
        provider_preference=provider_preference,
    )
    job.prompt_plan = prompt_plan
    job.raw_response_summary = {"prompt_planning": planning_summary}

    request = ImageGenerationRequest(
        prompt_plan=prompt_plan,
        asset_ids=asset_ids,
        provider_preference=provider_preference,
        idempotency_key=key,
        trace_id=trace_id,
    )
    return await _run_image_request(job, request, edit=False)


async def revise_image_job(job_id: str, request: ReviseImageRequest) -> GenerationJob | None:
    source_job = repository.get_job(job_id)
    source_output = repository.get_output(request.output_id)
    if not source_job or not source_output or not source_job.prompt_plan or source_output.job_id != source_job.id:
        return None

    patch = build_revision_patch(output_id=request.output_id, feedback=request.feedback, preserve=request.preserve)
    prompt_plan = apply_patch_to_plan(source_job.prompt_plan, patch)
    trace_id = make_id("trace")
    created_at = now_iso()
    revision = GenerationJob(
        id=make_id("job"),
        session_id=source_job.session_id,
        job_type="image",
        status=JobStatus.created,
        prompt_plan=prompt_plan,
        provider=source_job.provider,
        model=source_job.model,
        trace_id=trace_id,
        version_parent_id=request.output_id,
        raw_response_summary={"prompt_patch": patch.model_dump()},
        created_at=created_at,
        updated_at=created_at,
    )
    image_request = ImageGenerationRequest(
        prompt_plan=prompt_plan,
        asset_ids=prompt_plan.variables.get("asset_ids", []),
        provider_preference=request.provider_preference,
        trace_id=trace_id,
        source_output_id=request.output_id,
    )
    return await _run_image_request(revision, image_request, edit=True)


async def _run_image_request(job: GenerationJob, request: ImageGenerationRequest, *, edit: bool) -> GenerationJob:
    job.status = JobStatus.generating
    job.updated_at = now_iso()
    try:
        provider = await registry.select_image(request.provider_preference)
        result = await _try_image_provider(job, request, provider, edit=edit)
        job.raw_response_summary = {**job.raw_response_summary, **result.raw_response_summary}
        job.status = JobStatus.ready
    except ProviderRuntimeError as exc:
        fallback_error = await _try_image_fallback(job, request, edit=edit, primary_error=exc)
        if fallback_error is None:
            job.status = JobStatus.ready
        else:
            job.provider = fallback_error.provider or job.provider
            job.status = JobStatus.provider_not_configured if fallback_error.code == "provider_not_configured" else JobStatus.failed
            job.error = ProviderError(
                code=fallback_error.code,
                message=str(fallback_error),
                provider=fallback_error.provider,
                retryable=fallback_error.retryable,
                detail=fallback_error.detail,
            )
            if not job.cost_estimate:
                job.cost_estimate = CostEstimate(provider=fallback_error.provider or "unknown", model="unknown")
    job.updated_at = now_iso()
    saved = repository.save_job(job)
    if saved.status == JobStatus.ready:
        _persist_history_records(saved)
    _emit_image_events(saved)
    return saved


async def _try_image_provider(job: GenerationJob, request: ImageGenerationRequest, provider, *, edit: bool) -> object:
    job.provider = provider.name
    job.cost_estimate = await provider.estimate_cost(request)
    result = await provider.edit(request) if edit else await provider.generate(request)
    job.provider = result.provider
    job.model = result.model
    job.outputs = _store_outputs(job, result.outputs)
    return result


async def _try_image_fallback(
    job: GenerationJob,
    request: ImageGenerationRequest,
    *,
    edit: bool,
    primary_error: ProviderRuntimeError,
) -> ProviderRuntimeError | None:
    fallback_name = registry.alternate_image_name(primary_error.provider)
    if edit or not fallback_name:
        return primary_error
    try:
        fallback_provider = await registry.select_image(fallback_name)
        result = await _try_image_provider(job, request, fallback_provider, edit=edit)
        job.raw_response_summary = {
            **job.raw_response_summary,
            **result.raw_response_summary,
            "image_provider_fallback": {
                "from": primary_error.provider,
                "to": fallback_provider.name,
                "reason": primary_error.code,
                "primary_error": {
                    "message": str(primary_error),
                    "detail": primary_error.detail,
                },
            },
        }
        return None
    except ProviderRuntimeError as fallback_error:
        fallback_error.detail = {
            **fallback_error.detail,
            "primary_provider": primary_error.provider,
            "primary_error_code": primary_error.code,
            "primary_error_message": str(primary_error),
        }
        return fallback_error


def _store_outputs(job: GenerationJob, provider_outputs: list[dict]) -> list[GenerationOutput]:
    stored: list[GenerationOutput] = []
    for item in provider_outputs:
        output_id = make_id("out")
        output_format = item.get("format") or (job.prompt_plan.output_format if job.prompt_plan else "png")
        url = media_store.save_base64_output(
            job_id=job.id,
            output_id=output_id,
            b64_json=item["b64_json"],
            output_format=output_format,
        )
        width = item.get("width")
        height = item.get("height")
        stored.append(
            GenerationOutput(
                id=output_id,
                job_id=job.id,
                url=url,
                thumbnail_url=media_store.thumbnail_url(output_id),
                format=output_format,
                width=width,
                height=height,
                score=score_image_output(job.prompt_plan, output_format, width, height) if job.prompt_plan else None,
                version_parent_id=job.version_parent_id,
                metadata={key: value for key, value in item.items() if key not in {"b64_json"}},
            )
        )
    return stored


def _persist_history_records(job: GenerationJob) -> None:
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
                "work_intensity": _history_work_intensity(job),
                "work_intensity_label": _history_work_intensity_label(job),
                "prompt": _history_prompt(job),
                "size": job.prompt_plan.size if job.prompt_plan else None,
                "version_parent_id": output.version_parent_id,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
            }
        )


def _history_work_intensity(job: GenerationJob) -> str | None:
    if not job.prompt_plan or not job.prompt_plan.variables:
        return None
    value = job.prompt_plan.variables.get("work_intensity")
    return str(value) if value else None


def _history_work_intensity_label(job: GenerationJob) -> str | None:
    if not job.prompt_plan or not job.prompt_plan.variables:
        return None
    value = job.prompt_plan.variables.get("work_intensity_label")
    return str(value) if value else None


def _history_prompt(job: GenerationJob) -> str | None:
    if not job.prompt_plan:
        return None
    generation_prompt = job.prompt_plan.variables.get("generation_prompt") if job.prompt_plan.variables else None
    if generation_prompt:
        return str(generation_prompt)
    parts = [
        job.prompt_plan.main_subject,
        job.prompt_plan.scene,
        job.prompt_plan.style,
        job.prompt_plan.composition,
    ]
    return "，".join(part for part in parts if part)


def _idempotency_key(
    session_id: str,
    prompt_plan_json: str,
    asset_ids: list[str],
    provider_preference: str | None,
    work_intensity: str | None,
) -> str:
    payload = "|".join([session_id, prompt_plan_json, ",".join(sorted(asset_ids)), provider_preference or "", work_intensity or ""])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _emit_image_events(job: GenerationJob) -> None:
    repository.append_event(
        job.session_id,
        "job.status",
        {"job_id": job.id, "job_type": job.job_type, "status": job.status.value, "trace_id": job.trace_id},
    )
    for output in job.outputs:
        repository.append_event(
            job.session_id,
            "generation.output",
            {"job_id": job.id, "output_id": output.id, "url": output.url, "format": output.format},
        )
