from __future__ import annotations

from app.providers.base import ProviderRuntimeError
from app.providers.registry import registry
from app.repositories import repository
from app.schemas import GenerationJob, JobStatus, ProviderError, VideoGenerationRequest
from app.services.utils import make_id, now_iso


async def create_video_job(
    *,
    session_id: str,
    task_type: str,
    prompt: str,
    asset_ids: list[str] | None = None,
    duration_seconds: int = 6,
    aspect_ratio: str = "9:16",
    resolution: str = "1080p",
    provider_preference: str | None = None,
) -> GenerationJob:
    request = VideoGenerationRequest(
        session_id=session_id,
        task_type=task_type,
        prompt=prompt,
        asset_ids=asset_ids or [],
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        provider_preference=provider_preference,
        experimental=True,
    )
    created_at = now_iso()
    job = GenerationJob(
        id=make_id("job"),
        session_id=session_id,
        job_type="video",
        status=JobStatus.created,
        video_request=request,
        trace_id=make_id("trace"),
        created_at=created_at,
        updated_at=created_at,
    )

    try:
        provider = registry.video(provider_preference)
        job.provider = provider.name
        result = await provider.create_task(request)
    except ProviderRuntimeError as exc:
        job.provider = exc.provider or provider_preference
        result = {"status": exc.code, "message": str(exc)}

    if result.get("status") in {"provider_not_configured", "provider_capability_mismatch"}:
        job.status = JobStatus.provider_not_configured
        job.error = ProviderError(
            code=result.get("status", "provider_not_configured"),
            message=result.get("message") or "视频生成 provider 尚未配置，但已保存 VideoJobRequest。",
            provider=job.provider,
            retryable=False,
            detail={"experimental": True},
        )
    else:
        job.status = JobStatus.submitted
        job.raw_response_summary = result
    job.updated_at = now_iso()
    repository.video_requests[job.id] = request.model_dump()
    saved = repository.save_job(job)
    repository.append_event(
        saved.session_id,
        "job.status",
        {"job_id": saved.id, "job_type": saved.job_type, "status": saved.status.value, "trace_id": saved.trace_id},
    )
    return saved
