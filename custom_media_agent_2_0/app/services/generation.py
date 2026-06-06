from __future__ import annotations

from app.config import settings
from app.providers.images import (
    V2ImageProviderError,
    V2ImageProviderNotConfiguredError,
    V2ImageProviderRequest,
    get_v2_image_provider,
)
from app.repositories import repository
from app.repositories.memory import utc_now
from app.schemas import CreateImageJobRequest, ImageJob, ImageOutput
from app.services.ids import new_id
from app.services.image_history import persist_image_job_history
from app.services.output_review import review_image_job
from app.services.output_storage import save_provider_output


async def create_image_job(request: CreateImageJobRequest) -> ImageJob:
    provider = await get_v2_image_provider(request.provider_hint)
    try:
        result = await provider.generate(
            V2ImageProviderRequest(
                run_id=request.run_id,
                prompt_plan=request.prompt_plan,
                input_images=request.input_images,
            )
        )
    except V2ImageProviderNotConfiguredError as exc:
        if _can_fallback_to_mock(request.provider_hint):
            fallback_provider = await get_v2_image_provider("mock_image")
            result = await fallback_provider.generate(
                V2ImageProviderRequest(
                    run_id=request.run_id,
                    prompt_plan=request.prompt_plan,
                    input_images=request.input_images,
                )
            )
            return _save_job(_job_from_result(request, result, fallback_error=exc))
        return _save_job(_failed_job(request, provider_id=exc.provider or provider.name, error=exc))
    except V2ImageProviderError as exc:
        if _can_fallback_to_mock(request.provider_hint):
            fallback_provider = await get_v2_image_provider("mock_image")
            result = await fallback_provider.generate(
                V2ImageProviderRequest(
                    run_id=request.run_id,
                    prompt_plan=request.prompt_plan,
                    input_images=request.input_images,
                )
            )
            return _save_job(_job_from_result(request, result, fallback_error=exc))
        return _save_job(_failed_job(request, provider_id=exc.provider or provider.name, error=exc))
    return _save_job(_job_from_result(request, result))


def _job_from_result(request: CreateImageJobRequest, result, fallback_error: V2ImageProviderError | None = None) -> ImageJob:
    now = utc_now()
    job_id = new_id("job")
    outputs: list[ImageOutput] = []
    for item in result.outputs:
        output = ImageOutput(
            output_id=new_id("out"),
            job_id=job_id,
            url="",
            metadata={
                **item.metadata,
                "native_v2": True,
                "live": not bool(item.metadata.get("mock")),
                "requested_provider": _requested_provider(request.provider_hint),
                "actual_provider": result.provider,
                "requested_model": _requested_model(request.provider_hint),
                "actual_model": result.model,
                "provider_fallback": _fallback_payload(fallback_error),
                "input_images": [image.model_dump(mode="json") for image in request.input_images],
                "provider_input_plan": request.prompt_plan.user_variables.get("provider_input_plan"),
                "raw_response_summary": result.raw_response_summary,
            },
            score=_default_score(item.metadata, fallback_error=fallback_error),
            created_at=now,
        )
        outputs.append(
            save_provider_output(
                job_id=job_id,
                output=output,
                encoded=item.b64_json,
                output_format=item.format,
                mime_type=item.mime_type,
            )
        )
    return ImageJob(
        job_id=job_id,
        run_id=request.run_id,
        status="completed",
        provider_id=result.provider,
        model=result.model,
        prompt_plan=request.prompt_plan,
        outputs=outputs,
        error=_provider_error_payload(fallback_error) if fallback_error else None,
        created_at=now,
        updated_at=now,
    )


def _failed_job(request: CreateImageJobRequest, *, provider_id: str, error: V2ImageProviderError) -> ImageJob:
    now = utc_now()
    return ImageJob(
        job_id=new_id("job"),
        run_id=request.run_id,
        status="failed",
        provider_id=provider_id,
        model=_requested_model(request.provider_hint) or "unknown",
        prompt_plan=request.prompt_plan,
        outputs=[],
        error=_provider_error_payload(error),
        created_at=now,
        updated_at=now,
    )


def _can_fallback_to_mock(provider_hint: str | None) -> bool:
    requested = _requested_provider(provider_hint)
    return settings.allow_mock_fallback and requested in {"", "auto", None}


def _requested_provider(provider_hint: str | None) -> str:
    requested = provider_hint
    if requested in {None, "", "auto"}:
        requested = settings.image_generation_provider or "auto"
    return requested if requested != "" else "auto"


def _requested_model(provider_hint: str | None) -> str | None:
    provider = _requested_provider(provider_hint)
    if provider == "openai_gpt_image":
        return settings.openai_image_model
    if provider == "gemini_image":
        return settings.gemini_image_model
    if provider == "mock_image":
        return "mock-image-v2-native"
    if provider == "auto":
        if settings.openai_api_key:
            return settings.openai_image_model
        if settings.gemini_api_key:
            return settings.gemini_image_model
        return "mock-image-v2-native"
    return None


def _fallback_payload(error: V2ImageProviderError | None) -> dict | None:
    if not error:
        return None
    return {
        "from_provider": error.provider,
        "error_code": error.code,
        "message": str(error),
        "detail": error.detail,
    }


def _provider_error_payload(error: V2ImageProviderError | None) -> dict | None:
    if not error:
        return None
    return {
        "error_code": error.code,
        "message": str(error),
        "detail": error.detail,
        "retryable": bool(getattr(error, "retryable", False)),
        "native_v2": True,
    }


def _default_score(metadata: dict, *, fallback_error: V2ImageProviderError | None = None) -> dict:
    if metadata.get("mock"):
        return {
            "goal_match": 0.78,
            "composition": 0.82,
            "lighting": 0.8,
            "brand_safety": 0.86,
        }
    score = {
        "prompt_adherence": 0.85,
        "asset_consistency": 0.85,
        "text_quality": 0.85,
        "composition": 0.85,
        "subject_integrity": 0.85,
        "safety": 1.0,
        "technical": 1.0,
    }
    if fallback_error:
        score["asset_consistency"] = 0.7
    return score


def _save_job(job: ImageJob) -> ImageJob:
    reviewed = review_image_job(job)
    saved = repository.save_image_job(reviewed)
    persist_image_job_history(saved)
    return saved
