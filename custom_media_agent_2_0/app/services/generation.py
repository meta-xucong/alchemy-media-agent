from __future__ import annotations

from datetime import datetime

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
from app.services.intent_integrity import preflight_prompt_integrity
from app.services.output_review import review_image_job
from app.services.output_storage import save_provider_output
from app.services.prompt_transform.transformer import fallback_prompt_plan, transform_prompt_plan
from app.services.veyra_auth import VeyraAuthError, VeyraInsufficientBalance, VeyraSub2APIClient
from app.services.veyra_billing_settings import get_billing_rule
from app.services.veyra_usage import VeyraUsageRecord, record_veyra_usage


class V2IntentIntegrityProviderError(V2ImageProviderError):
    def __init__(self, *, code: str, detail: dict):
        super().__init__(
            "V2 intent integrity preflight blocked the provider request.",
            provider="v2_intent_preflight",
            detail=detail,
        )
        self.code = code
        self.retryable = False


async def create_running_image_job(request: CreateImageJobRequest) -> ImageJob:
    request = _with_prompt_transform(request)
    request, preflight = _with_prompt_integrity_preflight(request)
    now = utc_now()
    if preflight.get("status") == "failed":
        return _save_job(
            _failed_job(
                request,
                provider_id="v2_intent_preflight",
                error=V2IntentIntegrityProviderError(
                    code=str(preflight.get("code") or "intent_preflight_failed"),
                    detail={"preflight": preflight},
                ),
                job_id=new_id("job"),
                created_at=now,
            )
        )
    provider = await get_v2_image_provider(request.provider_hint)
    job = ImageJob(
        job_id=new_id("job"),
        run_id=request.run_id,
        status="running",
        provider_id=provider.name,
        model=_requested_model(request.provider_hint) or "unknown",
        prompt_plan=request.prompt_plan,
        outputs=[],
        created_at=now,
        updated_at=now,
    )
    return repository.save_image_job(job)


async def create_image_job(
    request: CreateImageJobRequest,
    *,
    job_id: str | None = None,
    created_at: datetime | None = None,
) -> ImageJob:
    request = _with_prompt_transform(request)
    request, preflight = _with_prompt_integrity_preflight(request)
    job_id = job_id or new_id("job")
    created_at = created_at or utc_now()
    if preflight.get("status") == "failed":
        error = V2IntentIntegrityProviderError(
            code=str(preflight.get("code") or "intent_preflight_failed"),
            detail={"preflight": preflight},
        )
        return _save_job(
            _failed_job(
                request,
                provider_id="v2_intent_preflight",
                error=error,
                job_id=job_id,
                created_at=created_at,
            )
        )
    provider = await get_v2_image_provider(request.provider_hint)
    if not repository.get_image_job(job_id):
        repository.save_image_job(
            ImageJob(
                job_id=job_id,
                run_id=request.run_id,
                status="running",
                provider_id=provider.name,
                model=_requested_model(request.provider_hint) or "unknown",
                prompt_plan=request.prompt_plan,
                outputs=[],
                created_at=created_at,
                updated_at=utc_now(),
            )
        )
    billing_result = None
    billing_rule = get_billing_rule("alchemy:v2")
    billing_required = _should_bill_veyra(request, billing_rule=billing_rule)
    if billing_required:
        try:
            await _ensure_veyra_balance(user_id=int(request.veyra_user_id or 0), amount=billing_rule.charge_amount)
        except (VeyraInsufficientBalance, VeyraAuthError) as exc:
            return _save_job(_failed_job(request, provider_id=provider.name, error=_billing_provider_error(exc), job_id=job_id, created_at=created_at))

    fallback_error = None
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
            fallback_error = exc
        else:
            return _save_job(_failed_job(request, provider_id=exc.provider or provider.name, error=exc, job_id=job_id, created_at=created_at))
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
            fallback_error = exc
        else:
            return _save_job(_failed_job(request, provider_id=exc.provider or provider.name, error=exc, job_id=job_id, created_at=created_at))

    if billing_required:
        try:
            billing_result = await VeyraSub2APIClient().debit(
                user_id=int(request.veyra_user_id or 0),
                amount=billing_rule.charge_amount,
                idempotency_key=f"{billing_rule.key}:image:{job_id}",
                source=billing_rule.source,
                reference_id=job_id,
            )
        except (VeyraInsufficientBalance, VeyraAuthError) as exc:
            return _save_job(_failed_job(request, provider_id=result.provider, error=_billing_provider_error(exc), job_id=job_id, created_at=created_at))

    saved = _save_job(
        _job_from_result(
            request,
            result,
            fallback_error=fallback_error,
            job_id=job_id,
            created_at=created_at,
            billing_result=billing_result,
        )
    )
    if billing_result:
        record_veyra_usage(
            VeyraUsageRecord(
                user_id=billing_result.user_id,
                amount=billing_result.amount,
                balance_after=billing_result.balance_after,
                idempotency_key=billing_result.idempotency_key,
                reference_id=job_id,
                source=billing_rule.source,
                replayed=billing_result.replayed,
            )
        )
    return saved


def _job_from_result(
    request: CreateImageJobRequest,
    result,
    *,
    job_id: str,
    created_at: datetime,
    fallback_error: V2ImageProviderError | None = None,
    billing_result=None,
) -> ImageJob:
    now = utc_now()
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
                "user_prompt": request.prompt_plan.user_variables.get("user_prompt"),
                "input_images": [image.model_dump(mode="json") for image in request.input_images],
                "generation_prompt": request.prompt_plan.user_variables.get("generation_prompt"),
                "prompt_transform": request.prompt_plan.user_variables.get("prompt_transform"),
                "prompt_integrity": request.prompt_plan.user_variables.get("prompt_integrity"),
                "provider_input_plan": request.prompt_plan.user_variables.get("provider_input_plan"),
                "visual_grammar_contract": request.prompt_plan.user_variables.get("visual_grammar_contract"),
                "information_integrity_lock_enabled": request.prompt_plan.user_variables.get(
                    "information_integrity_lock_enabled"
                ),
                "information_integrity_contract": request.prompt_plan.user_variables.get(
                    "information_integrity_contract"
                ),
                "raw_response_summary": result.raw_response_summary,
                "veyra_user_id": request.veyra_user_id,
                "veyra_billing": _billing_metadata(billing_result),
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
        created_at=created_at,
        updated_at=now,
    )


def _failed_job(
    request: CreateImageJobRequest,
    *,
    provider_id: str,
    error: V2ImageProviderError,
    job_id: str,
    created_at: datetime,
) -> ImageJob:
    now = utc_now()
    return ImageJob(
        job_id=job_id,
        run_id=request.run_id,
        status="failed",
        provider_id=provider_id,
        model=_requested_model(request.provider_hint) or "unknown",
        prompt_plan=request.prompt_plan,
        outputs=[],
        error=_provider_error_payload(error),
        created_at=created_at,
        updated_at=now,
    )


def _with_prompt_transform(request: CreateImageJobRequest) -> CreateImageJobRequest:
    try:
        prompt_plan = transform_prompt_plan(request.prompt_plan)
    except Exception as exc:
        prompt_plan = fallback_prompt_plan(request.prompt_plan, exc)
    if prompt_plan is request.prompt_plan:
        return request
    return request.model_copy(update={"prompt_plan": prompt_plan})


def _with_prompt_integrity_preflight(request: CreateImageJobRequest) -> tuple[CreateImageJobRequest, dict]:
    variables = dict(request.prompt_plan.user_variables or {})
    effective_prompt = str(variables.get("generation_prompt") or request.prompt_plan.prompt)
    trace = variables.get("prompt_integrity") if isinstance(variables.get("prompt_integrity"), dict) else None
    provider_plan = variables.get("provider_input_plan") if isinstance(variables.get("provider_input_plan"), dict) else {}
    enriched_trace = preflight_prompt_integrity(
        trace=trace,
        effective_prompt=effective_prompt,
        input_images=request.input_images,
        provider_input_plan=provider_plan,
    )
    variables["prompt_integrity"] = enriched_trace
    prompt_plan = request.prompt_plan.model_copy(update={"user_variables": variables})
    return request.model_copy(update={"prompt_plan": prompt_plan}), dict(enriched_trace.get("preflight") or {})


def _can_fallback_to_mock(provider_hint: str | None) -> bool:
    requested = _requested_provider(provider_hint)
    return settings.allow_mock_fallback and requested in {"", "auto", None}


def _requested_provider(provider_hint: str | None) -> str:
    requested = provider_hint
    if requested in {None, "", "auto"}:
        requested = settings.image_generation_provider or "auto"
    if requested == "gemini_image" and not settings.gemini_image_generation_enabled:
        return "auto"
    return requested if requested != "" else "auto"


def _requested_model(provider_hint: str | None) -> str | None:
    provider = _requested_provider(provider_hint)
    if provider == "openai_gpt_image":
        return settings.openai_image_model
    if provider == "doubao_image":
        return settings.doubao_image_model
    if provider == "gemini_image" and settings.gemini_image_generation_enabled:
        return settings.gemini_image_model
    if provider == "mock_image":
        return "mock-image-v2-native"
    if provider == "auto":
        if settings.openai_api_key:
            return settings.openai_image_model
        if settings.doubao_image_api_key:
            return settings.doubao_image_model
        if settings.gemini_api_key and settings.gemini_image_generation_enabled:
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
        "provider": error.provider,
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


def _should_bill_veyra(request: CreateImageJobRequest, *, billing_rule=None) -> bool:
    billing_rule = billing_rule or get_billing_rule("alchemy:v2")
    return bool(
        settings.veyra_auth_enabled
        and billing_rule.enabled
        and request.veyra_user_id
        and billing_rule.charge_amount > 0
    )


async def _ensure_veyra_balance(*, user_id: int, amount: float) -> None:
    account = await VeyraSub2APIClient().account(user_id)
    if float(account.balance) + 1e-9 < float(amount):
        raise VeyraInsufficientBalance("Insufficient sub2api balance.")


def _billing_metadata(result) -> dict | None:
    if not result:
        return None
    return {
        "amount": result.amount,
        "balance_after": result.balance_after,
        "idempotency_key": result.idempotency_key,
        "replayed": result.replayed,
    }


def _billing_provider_error(error: Exception) -> V2ImageProviderError:
    if isinstance(error, VeyraInsufficientBalance):
        return VeyraBillingProviderError(
            "账户余额不足，请先充值后再生成。",
            provider="veyra_billing",
            code="veyra_insufficient_balance",
            retryable=False,
            detail={"reason": "user_balance_insufficient"},
        )
    return VeyraBillingProviderError(
        "Veyra billing failed.",
        provider="veyra_billing",
        code=getattr(error, "code", "veyra_billing_error"),
        retryable=True,
        detail={},
    )


class VeyraBillingProviderError(V2ImageProviderError):
    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        code: str = "veyra_billing_error",
        retryable: bool = False,
        detail: dict | None = None,
    ):
        super().__init__(message, provider=provider, detail=detail)
        self.code = code
        self.retryable = retryable
