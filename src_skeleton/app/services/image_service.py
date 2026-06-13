from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from app.providers.base import ProviderRuntimeError
from app.config import settings
from app.providers.registry import registry
from app.repositories import repository
from app.schemas import (
    AssetIntent,
    CostEstimate,
    GenerationJob,
    GenerationOutput,
    ImageGenerationRequest,
    JobStatus,
    ProviderError,
    ReviseImageRequest,
)
from app.services.asset_planning import (
    AssetPlanError,
    apply_asset_plan_to_prompt_plan,
    asset_context_for_prompt_planner,
    build_advanced_asset_plan,
    logo_overlay_specs,
    validate_asset_plan_with_provider,
)
from app.services.evaluation import score_image_output
from app.services.prompting import apply_patch_to_plan, build_prompt_plan, build_revision_patch
from app.services.safety import check_generation_prompt
from app.services.utils import make_id, now_iso
from app.services.visual_review import review_image_output
from app.services.veyra_auth import (
    VeyraAuthError,
    VeyraInsufficientBalance,
    debit_balance,
    ensure_sufficient_balance,
    load_billing_rule,
)
from app.services.veyra_usage import VeyraUsageRecord, record_veyra_usage
from app.services.work_intensity import apply_work_intensity
from app.storage import media_store


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PreparedImageJob:
    job: GenerationJob
    request: ImageGenerationRequest | None = None
    edit: bool = False


TERMINAL_IMAGE_STATUSES = {
    JobStatus.ready,
    JobStatus.failed,
    JobStatus.provider_not_configured,
    JobStatus.rejected,
    JobStatus.canceled,
}


async def submit_image_job(
    *,
    session_id: str,
    prompt: str,
    asset_mode: str = "basic",
    asset_ids: list[str] | None = None,
    asset_intents: list[AssetIntent] | None = None,
    count: int = 1,
    size: str | None = None,
    quality: str = "auto",
    output_format: str = "png",
    work_intensity: str | None = None,
    provider_preference: str | None = None,
    idempotency_key: str | None = None,
    veyra_user_id: int | None = None,
) -> PreparedImageJob:
    prompt = str(prompt or "").strip()
    if not prompt:
        raise ValueError("请先填写生图提示词。")
    asset_mode = asset_mode or "basic"
    asset_intents = asset_intents or []
    asset_ids = asset_ids or []
    advanced_asset_plan = None
    asset_error = None
    if asset_mode == "advanced":
        if asset_ids:
            asset_error = AssetPlanError("asset_mode_conflict", "基础版素材和高级版素材用途不能混用。")
        else:
            try:
                advanced_asset_plan = build_advanced_asset_plan(asset_intents, user_prompt=prompt)
                asset_ids = [str(item["asset_id"]) for item in advanced_asset_plan.get("assets", [])]
            except AssetPlanError as exc:
                asset_error = exc
    elif asset_intents:
        asset_error = AssetPlanError("asset_mode_conflict", "基础版请求不能携带高级版素材用途。")

    work_intensity = work_intensity or settings.image_work_intensity
    prompt_plan = build_prompt_plan(
        prompt=prompt,
        count=count,
        size=size,
        quality=quality,
        output_format=output_format,
        asset_ids=asset_ids,
    )
    prompt_plan = prompt_plan.model_copy(
        update={
            "variables": {
                **prompt_plan.variables,
                "original_prompt": prompt,
                "pending_work_intensity": work_intensity,
                "prompt_planning_pending": True,
            }
        }
    )
    trace_id = make_id("trace")
    created_at = now_iso()
    job = GenerationJob(
        id=make_id("job"),
        session_id=session_id,
        job_type="image",
        status=JobStatus.created,
        asset_mode=asset_mode,
        asset_plan=advanced_asset_plan,
        prompt_plan=prompt_plan,
        idempotency_key=idempotency_key,
        trace_id=trace_id,
        created_at=created_at,
        updated_at=created_at,
    )
    if asset_error:
        job.status = JobStatus.failed
        job.error = ProviderError(
            code=asset_error.code,
            message=str(asset_error),
            detail=asset_error.detail,
        )
        job.updated_at = now_iso()
        return PreparedImageJob(repository.save_job(job))

    safety_error = check_generation_prompt(prompt)
    if safety_error:
        job.status = JobStatus.rejected
        job.error = safety_error
        job.updated_at = now_iso()
        return PreparedImageJob(repository.save_job(job))

    key = idempotency_key or _idempotency_key(
        session_id,
        prompt_plan.model_dump_json(),
        asset_ids,
        provider_preference,
        work_intensity,
        asset_mode,
    )
    existing = repository.get_job_by_idempotency_key(key)
    if existing:
        return PreparedImageJob(existing)
    job.idempotency_key = key
    job.status = JobStatus.generating
    job.provenance = {
        "asset_mode": asset_mode,
        "original_prompt": prompt,
    }
    job.raw_response_summary = {
        "prompt_planning": {"status": "pending", "work_intensity": work_intensity},
        "asset_mode": asset_mode,
        "asset_plan": advanced_asset_plan,
        "provider_input_plan": advanced_asset_plan.get("provider_input_plan") if advanced_asset_plan else None,
        "async_submission": True,
    }
    job.updated_at = now_iso()
    request = ImageGenerationRequest(
        prompt_plan=prompt_plan,
        asset_ids=asset_ids,
        asset_mode=asset_mode,
        asset_intents=asset_intents,
        asset_plan=advanced_asset_plan,
        provider_preference=provider_preference,
        idempotency_key=key,
        trace_id=trace_id,
        veyra_user_id=veyra_user_id,
    )
    saved = repository.save_job(job)
    _emit_image_events(saved)
    return PreparedImageJob(saved, request, edit=False)


async def create_image_job(
    *,
    session_id: str,
    prompt: str,
    asset_mode: str = "basic",
    asset_ids: list[str] | None = None,
    asset_intents: list[AssetIntent] | None = None,
    count: int = 1,
    size: str | None = None,
    quality: str = "auto",
    output_format: str = "png",
    work_intensity: str | None = None,
    provider_preference: str | None = None,
    idempotency_key: str | None = None,
    veyra_user_id: int | None = None,
) -> GenerationJob:
    prompt = str(prompt or "").strip()
    if not prompt:
        raise ValueError("请先填写生图提示词。")
    asset_mode = asset_mode or "basic"
    asset_intents = asset_intents or []
    asset_ids = asset_ids or []
    advanced_asset_plan = None
    asset_error = None
    if asset_mode == "advanced":
        if asset_ids:
            asset_error = AssetPlanError("asset_mode_conflict", "基础版素材和高级版素材用途不能混用。")
        else:
            try:
                advanced_asset_plan = build_advanced_asset_plan(asset_intents, user_prompt=prompt)
                asset_ids = [str(item["asset_id"]) for item in advanced_asset_plan.get("assets", [])]
            except AssetPlanError as exc:
                asset_error = exc
    elif asset_intents:
        asset_error = AssetPlanError("asset_mode_conflict", "基础版请求不能携带高级版素材用途。")

    work_intensity = work_intensity or settings.image_work_intensity
    prompt_plan = build_prompt_plan(
        prompt=prompt,
        count=count,
        size=size,
        quality=quality,
        output_format=output_format,
        asset_ids=asset_ids,
    )
    trace_id = make_id("trace")
    created_at = now_iso()
    job = GenerationJob(
        id=make_id("job"),
        session_id=session_id,
        job_type="image",
        status=JobStatus.created,
        asset_mode=asset_mode,
        asset_plan=advanced_asset_plan,
        prompt_plan=prompt_plan,
        idempotency_key=idempotency_key,
        trace_id=trace_id,
        created_at=created_at,
        updated_at=created_at,
    )
    if asset_error:
        job.status = JobStatus.failed
        job.error = ProviderError(
            code=asset_error.code,
            message=str(asset_error),
            detail=asset_error.detail,
        )
        job.updated_at = now_iso()
        return repository.save_job(job)

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
        asset_context=asset_context_for_prompt_planner(advanced_asset_plan),
    )
    if advanced_asset_plan:
        prompt_plan = apply_asset_plan_to_prompt_plan(
            prompt_plan,
            original_prompt=prompt,
            asset_plan=advanced_asset_plan,
        )
    job.prompt_plan = prompt_plan
    job.asset_plan = advanced_asset_plan
    job.provenance = {
        "asset_mode": asset_mode,
        "original_prompt": prompt,
        "final_prompt": _history_prompt(job),
    }
    job.raw_response_summary = {
        "prompt_planning": planning_summary,
        "asset_mode": asset_mode,
        "asset_plan": advanced_asset_plan,
        "provider_input_plan": advanced_asset_plan.get("provider_input_plan") if advanced_asset_plan else None,
        "prompt_plan": prompt_plan.variables.get("advanced_prompt_plan") if prompt_plan.variables else None,
    }

    key = idempotency_key or _idempotency_key(
        session_id,
        prompt_plan.model_dump_json(),
        asset_ids,
        provider_preference,
        work_intensity,
        asset_mode,
    )
    existing = repository.get_job_by_idempotency_key(key)
    if existing:
        return existing
    job.idempotency_key = key

    request = ImageGenerationRequest(
        prompt_plan=prompt_plan,
        asset_ids=asset_ids,
        asset_mode=asset_mode,
        asset_intents=asset_intents,
        asset_plan=advanced_asset_plan,
        provider_preference=provider_preference,
        idempotency_key=key,
        trace_id=trace_id,
        veyra_user_id=veyra_user_id,
    )
    return await _run_image_request(job, request, edit=False)


async def revise_image_job(job_id: str, request: ReviseImageRequest, *, veyra_user_id: int | None = None) -> GenerationJob | None:
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
        provider_preference=request.provider_preference or source_job.provider,
        trace_id=trace_id,
        source_output_id=request.output_id,
        veyra_user_id=veyra_user_id,
    )
    return await _run_image_request(revision, image_request, edit=True)


async def submit_revise_image_job(job_id: str, request: ReviseImageRequest, *, veyra_user_id: int | None = None) -> PreparedImageJob | None:
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
        status=JobStatus.generating,
        prompt_plan=prompt_plan,
        provider=source_job.provider,
        model=source_job.model,
        trace_id=trace_id,
        version_parent_id=request.output_id,
        raw_response_summary={"prompt_patch": patch.model_dump(), "async_submission": True},
        created_at=created_at,
        updated_at=created_at,
    )
    image_request = ImageGenerationRequest(
        prompt_plan=prompt_plan,
        asset_ids=prompt_plan.variables.get("asset_ids", []),
        provider_preference=request.provider_preference or source_job.provider,
        trace_id=trace_id,
        source_output_id=request.output_id,
        veyra_user_id=veyra_user_id,
    )
    saved = repository.save_job(revision)
    _emit_image_events(saved)
    return PreparedImageJob(saved, image_request, edit=True)


async def run_submitted_image_job(job_id: str, request: ImageGenerationRequest, *, edit: bool = False) -> GenerationJob | None:
    job = repository.get_job(job_id)
    if not job:
        return None
    if job.status in TERMINAL_IMAGE_STATUSES:
        return job
    try:
        if not edit:
            job, request = await _prepare_submitted_image_run(job, request)
        return await _run_image_request(job, request, edit=edit)
    except Exception as exc:
        logger.exception("V1 image background job failed: %s", job_id)
        failed = repository.get_job(job_id) or job
        failed.status = JobStatus.failed
        failed.error = ProviderError(
            code="background_job_failed",
            message="V1 image background job failed.",
            retryable=True,
            detail={
                "error_type": type(exc).__name__,
                "message": str(exc)[:1000],
            },
        )
        failed.updated_at = now_iso()
        saved = repository.save_job(failed)
        _emit_image_events(saved)
        return saved


async def _prepare_submitted_image_run(job: GenerationJob, request: ImageGenerationRequest) -> tuple[GenerationJob, ImageGenerationRequest]:
    if not job.prompt_plan:
        return job, request
    variables = job.prompt_plan.variables or {}
    if not variables.get("prompt_planning_pending"):
        return job, request

    original_prompt = str(variables.get("original_prompt") or job.provenance.get("original_prompt") or job.prompt_plan.main_subject)
    work_intensity = str(variables.get("pending_work_intensity") or settings.image_work_intensity)
    prompt_plan, planning_summary = await apply_work_intensity(
        job.prompt_plan,
        original_prompt=original_prompt,
        work_intensity=work_intensity,
        provider_preference=request.provider_preference,
        asset_context=asset_context_for_prompt_planner(request.asset_plan),
    )
    if request.asset_plan:
        prompt_plan = apply_asset_plan_to_prompt_plan(
            prompt_plan,
            original_prompt=original_prompt,
            asset_plan=request.asset_plan,
        )

    prompt_plan = prompt_plan.model_copy(
        update={
            "variables": {
                **prompt_plan.variables,
                "prompt_planning_pending": False,
            }
        }
    )
    job.prompt_plan = prompt_plan
    job.asset_plan = request.asset_plan
    job.provenance = {
        **job.provenance,
        "asset_mode": request.asset_mode,
        "original_prompt": original_prompt,
        "final_prompt": _history_prompt(job),
    }
    job.raw_response_summary = {
        **job.raw_response_summary,
        "prompt_planning": planning_summary,
        "asset_mode": request.asset_mode,
        "asset_plan": request.asset_plan,
        "provider_input_plan": request.asset_plan.get("provider_input_plan") if request.asset_plan else None,
        "prompt_plan": prompt_plan.variables.get("advanced_prompt_plan") if prompt_plan.variables else None,
    }
    job.updated_at = now_iso()
    repository.save_job(job)
    return job, request.model_copy(update={"prompt_plan": prompt_plan, "asset_plan": request.asset_plan})


async def _run_image_request(job: GenerationJob, request: ImageGenerationRequest, *, edit: bool) -> GenerationJob:
    job.status = JobStatus.generating
    job.updated_at = now_iso()
    requested_provider = request.provider_preference or settings.default_image_provider
    job.raw_response_summary = {
        **job.raw_response_summary,
        "requested_image_provider": requested_provider,
        "requested_image_model": _requested_image_model(requested_provider),
    }
    billing_result = None
    billing_rule = None
    billing_required = False
    try:
        billing_rule = await load_billing_rule(settings.veyra_billing_rule_key_v1)
        billing_required = _should_bill_veyra(request, billing_rule)
        if billing_required:
            await ensure_sufficient_balance(user_id=int(request.veyra_user_id or 0), amount=billing_rule.charge_amount)
    except (VeyraInsufficientBalance, VeyraAuthError) as exc:
        job.status = JobStatus.failed
        job.error = _billing_provider_error(exc)
        job.updated_at = now_iso()
        saved = repository.save_job(job)
        _emit_image_events(saved)
        return saved

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

    if job.status == JobStatus.ready and billing_required and billing_rule:
        try:
            billing_result = await debit_balance(
                user_id=int(request.veyra_user_id or 0),
                amount=billing_rule.charge_amount,
                idempotency_key=f"{billing_rule.key}:image:{job.id}",
                source=billing_rule.source,
                reference_id=job.id,
            )
            job.raw_response_summary = {
                **job.raw_response_summary,
                "veyra_billing": _billing_metadata(billing_result),
            }
            _attach_billing_metadata(job, billing_result)
        except (VeyraInsufficientBalance, VeyraAuthError) as exc:
            _discard_job_outputs(job)
            job.status = JobStatus.failed
            job.error = _billing_provider_error(exc)
            job.updated_at = now_iso()
            saved = repository.save_job(job)
            _emit_image_events(saved)
            return saved
    job.updated_at = now_iso()
    saved = repository.save_job(job)
    if saved.status == JobStatus.ready:
        if billing_result:
            record_veyra_usage(
                VeyraUsageRecord(
                    user_id=billing_result.user_id,
                    amount=billing_result.amount,
                    balance_after=billing_result.balance_after,
                    idempotency_key=billing_result.idempotency_key,
                    reference_id=job.id,
                    source=billing_result.source,
                    replayed=billing_result.replayed,
                )
            )
        _persist_history_records(saved)
    _emit_image_events(saved)
    return saved


async def _try_image_provider(job: GenerationJob, request: ImageGenerationRequest, provider, *, edit: bool) -> object:
    job.provider = provider.name
    asset_plan = request.asset_plan or job.asset_plan
    if asset_plan:
        validate_asset_plan_with_provider(asset_plan, await provider.capabilities())
    job.cost_estimate = await provider.estimate_cost(request)
    result = await provider.edit(request) if edit else await provider.generate(request)
    job.provider = result.provider
    job.model = result.model
    job.outputs = _store_outputs(job, result.outputs, request=request)
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
        fallback_info = {
            "from": primary_error.provider,
            "to": fallback_provider.name,
            "reason": primary_error.code,
            "primary_error": {
                "message": str(primary_error),
                "detail": primary_error.detail,
            },
        }
        for output in job.outputs:
            output.metadata = {
                **output.metadata,
                "requested_provider": primary_error.provider,
                "actual_provider": fallback_provider.name,
                "provider_fallback": fallback_info,
            }
        job.raw_response_summary = {
            **job.raw_response_summary,
            **result.raw_response_summary,
            "image_provider_fallback": fallback_info,
        }
        return None
    except ProviderRuntimeError as fallback_error:
        fallback_error.detail = {
            **fallback_error.detail,
            "primary_provider": primary_error.provider,
            "primary_error_code": primary_error.code,
            "primary_error_message": str(primary_error),
            "primary_error_detail": primary_error.detail,
            "fallback_provider": fallback_error.provider,
            "fallback_error_code": fallback_error.code,
            "fallback_error_message": str(fallback_error),
        }
        return fallback_error


def _store_outputs(job: GenerationJob, provider_outputs: list[dict], *, request: ImageGenerationRequest) -> list[GenerationOutput]:
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
                metadata={
                    **{key: value for key, value in item.items() if key not in {"b64_json"}},
                    "actual_provider": job.provider,
                    "actual_model": job.model,
                    "requested_provider": _requested_history_provider(job),
                    "requested_model": _requested_history_model(job),
                    "veyra_user_id": request.veyra_user_id,
                    "veyra_billing": job.raw_response_summary.get("veyra_billing"),
                },
            )
        )
        _apply_advanced_postprocess(job, stored[-1])
        review = review_image_output(job, stored[-1])
        if review:
            stored[-1].visual_review = review
            stored[-1].metadata["visual_review"] = review.model_dump()
    return stored


def _persist_history_records(job: GenerationJob) -> None:
    session = repository.get_session(job.session_id) if job.session_id else None
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
                "requested_provider": _requested_history_provider(job),
                "requested_model": _requested_history_model(job),
                "provider_fallback": job.raw_response_summary.get("image_provider_fallback"),
                "asset_mode": job.asset_mode,
                "asset_intents": _history_asset_intents(job),
                "asset_plan": job.asset_plan,
                "asset_vision_profiles": _history_asset_vision_profiles(job),
                "provider_input_plan": _history_provider_input_plan(job),
                "visual_review": output.visual_review.model_dump() if output.visual_review else None,
                "prompt_plan": job.prompt_plan.variables.get("advanced_prompt_plan") if job.prompt_plan and job.prompt_plan.variables else None,
                "original_prompt": job.provenance.get("original_prompt") or (job.prompt_plan.variables.get("original_prompt") if job.prompt_plan and job.prompt_plan.variables else None),
                "final_prompt": _history_prompt(job),
                "source_app": session.project_id if session else None,
                "idempotency_key": job.idempotency_key,
                "work_intensity": _history_work_intensity(job),
                "work_intensity_label": _history_work_intensity_label(job),
                "prompt": _history_prompt(job),
                "size": job.prompt_plan.size if job.prompt_plan else None,
                "version_parent_id": output.version_parent_id,
                "veyra_user_id": output.metadata.get("veyra_user_id"),
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


def _history_asset_intents(job: GenerationJob) -> list[dict]:
    if not job.asset_plan:
        return []
    return [
        {
            "asset_id": item.get("asset_id"),
            "role": item.get("role"),
            "role_label": item.get("role_label"),
            "priority": item.get("priority"),
            "preservation": item.get("preservation"),
            "strength": item.get("strength"),
        }
        for item in job.asset_plan.get("assets", [])
    ]


def _history_asset_vision_profiles(job: GenerationJob) -> list[dict]:
    if not job.asset_plan:
        return []
    profiles = []
    for item in job.asset_plan.get("assets", []):
        profile = item.get("vision_profile")
        if profile:
            profiles.append(profile)
    return profiles


def _history_provider_input_plan(job: GenerationJob) -> dict | None:
    if not job.asset_plan:
        return None
    value = job.asset_plan.get("provider_input_plan")
    return dict(value) if isinstance(value, dict) else None


def _requested_history_provider(job: GenerationJob) -> str | None:
    value = job.raw_response_summary.get("requested_image_provider") if job.raw_response_summary else None
    return str(value) if value else None


def _requested_history_model(job: GenerationJob) -> str | None:
    value = job.raw_response_summary.get("requested_image_model") if job.raw_response_summary else None
    return str(value) if value else None


def _requested_image_model(provider: str | None) -> str | None:
    if provider == "gemini_image" and settings.gemini_image_generation_enabled:
        return settings.gemini_image_model
    if provider == "openai_gpt_image":
        return settings.openai_image_model
    return settings.default_image_model


def _should_bill_veyra(request: ImageGenerationRequest, billing_rule) -> bool:
    return bool(settings.veyra_auth_enabled and billing_rule.enabled and request.veyra_user_id and billing_rule.charge_amount > 0)


def _billing_metadata(result) -> dict | None:
    if not result:
        return None
    return {
        "amount": result.amount,
        "balance_after": result.balance_after,
        "idempotency_key": result.idempotency_key,
        "source": result.source,
        "replayed": result.replayed,
    }


def _attach_billing_metadata(job: GenerationJob, billing_result) -> None:
    metadata = _billing_metadata(billing_result)
    if not metadata:
        return
    for output in job.outputs:
        output.metadata = {
            **output.metadata,
            "veyra_billing": metadata,
        }


def _discard_job_outputs(job: GenerationJob) -> None:
    for output in list(job.outputs):
        media_store.delete_output_file(output_id=output.id, job_id=job.id, output_format=output.format)
        media_store.delete_history_record(output.id)
        repository.delete_output(output.id)
    job.outputs = []


def _billing_provider_error(error: Exception) -> ProviderError:
    if isinstance(error, VeyraInsufficientBalance):
        return ProviderError(
            code="veyra_insufficient_balance",
            message="Sub2api balance is insufficient.",
            provider="veyra_billing",
            retryable=False,
            detail={},
        )
    return ProviderError(
        code=getattr(error, "code", "veyra_billing_error"),
        message="Veyra billing failed.",
        provider="veyra_billing",
        retryable=True,
        detail={},
    )


def _idempotency_key(
    session_id: str,
    prompt_plan_json: str,
    asset_ids: list[str],
    provider_preference: str | None,
    work_intensity: str | None,
    asset_mode: str = "basic",
) -> str:
    payload = "|".join([session_id, prompt_plan_json, ",".join(sorted(asset_ids)), provider_preference or "", work_intensity or "", asset_mode])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _apply_advanced_postprocess(job: GenerationJob, output: GenerationOutput) -> None:
    if not job.asset_plan:
        return
    for spec in logo_overlay_specs(job.asset_plan):
        step = _apply_logo_overlay(job, output, spec)
        output.metadata.setdefault("postprocess_steps", []).append(step)
        job.postprocess_steps.append(step)


def _apply_logo_overlay(job: GenerationJob, output: GenerationOutput, spec: dict) -> dict[str, object]:
    step = {
        "type": "logo_overlay",
        "asset_id": spec.get("asset_id"),
        "status": "failed",
    }
    try:
        from PIL import Image, ImageOps

        output_path = media_store.output_path(job_id=job.id, output_id=output.id, output_format=output.format)
        logo_path = spec["path"]
        placement = spec.get("placement") or {}
        with Image.open(output_path) as base_image, Image.open(logo_path) as logo_image:
            base = ImageOps.exif_transpose(base_image).convert("RGBA")
            logo = ImageOps.exif_transpose(logo_image).convert("RGBA")
            width_ratio = float(placement.get("width_ratio") or 0.18)
            max_width = max(1, int(base.width * max(0.01, min(width_ratio, 1.0))))
            logo.thumbnail((max_width, max_width), Image.Resampling.LANCZOS)
            x, y = _logo_position(base.size, logo.size, placement)
            opacity = float(placement.get("opacity") if placement.get("opacity") is not None else 1.0)
            if opacity < 1:
                alpha = logo.getchannel("A").point(lambda value: int(value * max(0, min(opacity, 1))))
                logo.putalpha(alpha)
            base.alpha_composite(logo, (x, y))
            if output.format == "jpeg":
                canvas = Image.new("RGB", base.size, (255, 255, 255))
                canvas.paste(base, mask=base.getchannel("A"))
                canvas.save(output_path, "JPEG", quality=94, optimize=True)
            elif output.format == "webp":
                base.save(output_path, "WEBP", quality=94, method=6)
            else:
                base.save(output_path, "PNG", optimize=True)
            output.thumbnail_url = media_store.thumbnail_url(output.id)
            media_store.ensure_thumbnail(output_id=output.id, source_path=output_path)
        step.update({"status": "succeeded", "anchor": placement.get("anchor") or "bottom_right"})
        return step
    except Exception as exc:
        step["message"] = str(exc)[:300]
        return step


def _logo_position(base_size: tuple[int, int], logo_size: tuple[int, int], placement: dict) -> tuple[int, int]:
    base_width, base_height = base_size
    logo_width, logo_height = logo_size
    margin = int(min(base_width, base_height) * float(placement.get("margin_ratio") or 0.06))
    anchor = placement.get("anchor") or "bottom_right"
    if anchor == "custom" and placement.get("x_ratio") is not None and placement.get("y_ratio") is not None:
        return (
            _clamp(int(base_width * float(placement["x_ratio"]) - logo_width / 2), margin, base_width - logo_width - margin),
            _clamp(int(base_height * float(placement["y_ratio"]) - logo_height / 2), margin, base_height - logo_height - margin),
        )
    x_map = {
        "top_left": margin,
        "center_left": margin,
        "bottom_left": margin,
        "top_center": (base_width - logo_width) // 2,
        "center": (base_width - logo_width) // 2,
        "bottom_center": (base_width - logo_width) // 2,
        "top_right": base_width - logo_width - margin,
        "center_right": base_width - logo_width - margin,
        "bottom_right": base_width - logo_width - margin,
    }
    y_map = {
        "top_left": margin,
        "top_center": margin,
        "top_right": margin,
        "center_left": (base_height - logo_height) // 2,
        "center": (base_height - logo_height) // 2,
        "center_right": (base_height - logo_height) // 2,
        "bottom_left": base_height - logo_height - margin,
        "bottom_center": base_height - logo_height - margin,
        "bottom_right": base_height - logo_height - margin,
    }
    return (
        _clamp(x_map.get(anchor, x_map["bottom_right"]), margin, base_width - logo_width - margin),
        _clamp(y_map.get(anchor, y_map["bottom_right"]), margin, base_height - logo_height - margin),
    )


def _clamp(value: int, low: int, high: int) -> int:
    if high < low:
        return max(0, value)
    return max(low, min(value, high))


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
