"""Remote provider facade for the V3 LLM Brain."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from dataclasses import dataclass
import json
import os
import threading
import time
from typing import Any

from .contracts import BrainRunRequest
from .prompts import build_remote_payload, system_prompt_for_stage
from .stage_trace import record_stage_event


class BrainProviderUnavailable(RuntimeError):
    """Raised when no remote brain provider is configured."""


class BrainProviderError(RuntimeError):
    """Raised when a configured remote brain provider fails."""


class _BrainProtocolUnsupported(BrainProviderError):
    """The gateway does not expose the selected OpenAI-compatible protocol."""


class BrainTransportTimeoutError(BrainProviderError):
    """The remote Brain transport exceeded one bounded call window."""

    def __init__(
        self,
        *,
        stage: str,
        timeout_seconds: float,
        elapsed_ms: int,
        timeout_phase: str,
        response_started: bool = False,
        first_content_observed: bool = False,
        complete_response_observed: bool = False,
        json_parse_started: bool = False,
        json_parse_completed: bool = False,
    ) -> None:
        super().__init__(
            f"remote Brain provider timed out during {timeout_phase} after {timeout_seconds:.2f} seconds"
        )
        self.stage = str(stage or "unknown")
        self.timeout_seconds = max(0.0, float(timeout_seconds))
        self.elapsed_ms = max(0, int(elapsed_ms))
        self.timeout_phase = _safe_transport_timeout_phase(timeout_phase)
        self.response_started = bool(response_started)
        self.first_content_observed = bool(first_content_observed)
        self.complete_response_observed = bool(complete_response_observed)
        self.json_parse_started = bool(json_parse_started)
        self.json_parse_completed = bool(json_parse_completed)

    def safe_metadata(self) -> dict[str, Any]:
        """Return public-safe timeout facts without endpoint, prompt, or body data."""

        return {
            "schema_version": "v3_brain_transport_failure_v1",
            "stage": self.stage,
            "transport_error_class": "timeout",
            "timeout_phase": self.timeout_phase,
            "timeout_seconds": round(self.timeout_seconds, 3),
            "elapsed_ms": self.elapsed_ms,
            "response_started": self.response_started,
            "first_content_observed": self.first_content_observed,
            "complete_response_observed": self.complete_response_observed,
            "json_parse_started": self.json_parse_started,
            "json_parse_completed": self.json_parse_completed,
        }


class BrainPromptContractInvalid(BrainProviderError):
    """The remote Brain returned a malformed canonical provider-prompt contract."""


class BrainExecutionBudgetExceeded(BrainProviderError):
    """The shared logical Brain budget ended before another remote call."""


class BrainInvalidJsonResponse(BrainProviderError):
    """The remote Brain did not provide a usable serialized JSON response."""

    def __init__(
        self,
        message: str,
        *,
        stage: str = "unknown",
        attempts: int = 1,
        json_recovery_attempted: bool = False,
        json_recovery_succeeded: bool = False,
        json_parse_started: bool = True,
        json_parse_completed: bool = False,
        json_failure_kind: str = "unknown",
    ) -> None:
        super().__init__(message)
        self.stage = _safe_brain_stage(stage)
        self.attempts = max(1, min(2, int(attempts)))
        self.json_recovery_attempted = bool(json_recovery_attempted)
        self.json_recovery_succeeded = bool(json_recovery_succeeded)
        self.json_parse_started = bool(json_parse_started)
        self.json_parse_completed = bool(json_parse_completed)
        self.json_failure_kind = _safe_json_failure_kind(json_failure_kind)

    def safe_metadata(self) -> dict[str, Any]:
        """Return public-safe serialization facts without model text or prompts."""

        return {
            "schema_version": "v3_brain_serialization_failure_v1",
            "stage": self.stage,
            "transport_error_class": "invalid_json_response",
            "error_family": "json_decode",
            "json_failure_kind": self.json_failure_kind,
            "attempts": self.attempts,
            "json_serialization_recovery_attempted": self.json_recovery_attempted,
            "json_serialization_recovery_succeeded": self.json_recovery_succeeded,
            "json_parse_started": self.json_parse_started,
            "json_parse_completed": self.json_parse_completed,
        }


class BrainOutputTruncated(BrainInvalidJsonResponse):
    """The remote Brain exhausted its transport output budget before JSON completed."""

    def safe_metadata(self) -> dict[str, Any]:
        """Return public-safe truncation facts without model text or prompts."""

        return {
            "schema_version": "v3_brain_truncated_response_v1",
            "stage": self.stage,
            "transport_error_class": "truncated_response",
            "error_family": "output_truncated",
            "json_failure_kind": "output_truncated",
            "attempts": self.attempts,
            "json_serialization_recovery_attempted": self.json_recovery_attempted,
            "json_serialization_recovery_succeeded": self.json_recovery_succeeded,
            "json_parse_started": self.json_parse_started,
            "json_parse_completed": self.json_parse_completed,
        }


_SAFE_BRAIN_STAGES = {
    "activation",
    "generate",
    "plan",
    "provider_prompt_developmental_presence_verify",
    "provider_prompt_finalize",
    "provider_prompt_human_naturalness_resign",
    "provider_prompt_professional_capture_resign",
    "remote_intent",
}


def _safe_brain_stage(stage: Any) -> str:
    value = str(stage or "").strip()
    if value in _SAFE_BRAIN_STAGES:
        return value
    return "unknown"


_SAFE_JSON_FAILURE_KINDS = {
    "empty_json",
    "malformed_json",
    "missing_complete_marker",
    "non_object_json",
    "output_truncated",
    "unknown",
}


def _safe_json_failure_kind(kind: Any) -> str:
    value = str(kind or "").strip()
    if value in _SAFE_JSON_FAILURE_KINDS:
        return value
    return "unknown"


class BrainSemanticPreflightMissing(BrainProviderError):
    """The Brain returned a prompt but omitted a required semantic receipt."""


class BrainHumanNaturalnessDecisionMissing(BrainProviderError):
    """The independent Human Realism re-sign lacked its required safe receipt."""


class BrainReferenceChannelOwnershipDecisionMissing(BrainProviderError):
    """The final Brain sign-off omitted the frozen reference-ownership receipt."""


class BrainDevelopmentalAgeDecisionMissing(BrainProviderError):
    """The final Brain sign-off omitted the current-request-owned age receipt."""


class BrainDevelopmentalPresenceDecisionMissing(BrainProviderError):
    """The final Brain sign-off omitted the age-general facial-presence receipt."""


class BrainProfessionalAnchorViewDecisionMissing(BrainProviderError):
    """The final Brain sign-off omitted or changed the frozen anchor view."""


class BrainProviderAdmissionDecisionMissing(BrainProviderError):
    """The final Brain sign-off omitted the provider-admission receipt."""


@dataclass(frozen=True)
class _BrainExecutionBudget:
    """Ephemeral deadline shared by all remote calls in one V3 preparation.

    It is intentionally held in a context variable rather than request metadata:
    a deadline is transport control, never creative evidence, Brain input, or
    persisted job provenance.
    """

    total_seconds: float
    started_at: float

    @property
    def deadline(self) -> float:
        return self.started_at + self.total_seconds

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - time.perf_counter())


_ACTIVE_EXECUTION_BUDGET: ContextVar[_BrainExecutionBudget | None] = ContextVar(
    "v3_active_remote_brain_execution_budget",
    default=None,
)
_ACTIVE_TRANSPORT_TRACE: ContextVar[dict[str, Any] | None] = ContextVar(
    "v3_active_remote_brain_transport_trace",
    default=None,
)


class V3LLMBrainProvider:
    """Small provider adapter that keeps V3 brain calls optional."""

    def __init__(self) -> None:
        self.provider = _env("V3_LLM_BRAIN_PROVIDER") or _preferred_provider()
        self.provider = self.provider.strip().lower()
        self.model = _env("V3_LLM_BRAIN_MODEL") or _default_model(self.provider)
        self.timeout = max(1.0, min(210.0, _float_env("V3_LLM_BRAIN_TIMEOUT_SECONDS", 210.0)))
        # A V3 preparation has more than one legitimate Brain decision: a
        # semantic plan and the final signed renderer direction.  Bound the
        # *logical* preparation as one unit so a later valid sign-off does not
        # inherit a stale per-call deadline or leave a caller waiting without a
        # terminal reason.  This budget change is transport-only; it does not
        # add recovery behavior, change creative ownership, or permit a local
        # prompt fallback.
        self.execution_budget_seconds = _float_env(
            "V3_LLM_BRAIN_EXECUTION_BUDGET_SECONDS",
            max(520.0, (self.timeout * 2.0) + 100.0),
        )
        # A compact V3 plan can still need substantial output allowance when a
        # reasoning-capable remote model accounts for its private deliberation
        # before returning the complete JSON contract.  The old 4200-token
        # default truncated otherwise valid plans at the transport boundary.
        # This is an output-capacity setting only: it neither changes frozen
        # evidence nor permits local JSON/prompt reconstruction.
        self.max_tokens = _int_env("V3_LLM_BRAIN_MAX_TOKENS", 8000)

    @contextmanager
    def execution_scope(self):
        """Share one finite, provider-neutral budget across a V3 preparation."""

        budget = _BrainExecutionBudget(
            total_seconds=max(1.0, float(self.execution_budget_seconds)),
            started_at=time.perf_counter(),
        )
        token = _ACTIVE_EXECUTION_BUDGET.set(budget)
        try:
            yield budget
        finally:
            _ACTIVE_EXECUTION_BUDGET.reset(token)

    def execution_budget_receipt(self) -> dict[str, Any] | None:
        """Return safe, aggregate timing facts without endpoint/error bodies."""

        budget = _ACTIVE_EXECUTION_BUDGET.get()
        if budget is None:
            return None
        remaining = budget.remaining_seconds()
        return {
            "logical_budget_seconds": round(budget.total_seconds, 3),
            "remaining_ms": max(0, int(round(remaining * 1000))),
            "state": "within_budget" if remaining > 0.0 else "exhausted",
        }

    def available(self, *, force: bool = False) -> bool:
        if not _remote_enabled(force=force):
            return False
        try:
            self._credentials()
            return True
        except BrainProviderUnavailable:
            return False

    def run(self, request: BrainRunRequest) -> dict[str, Any]:
        """Run one Brain decision, with one serialization-only remote recovery.

        A malformed JSON reply is not an accepted creative decision.  The
        recovery therefore asks the same remote Brain to re-answer the same
        frozen request once; it never locally repairs JSON, reconstructs a
        prompt, changes a reference, or starts an image operation.
        """

        self._ensure_budget_available()
        if self.provider in {"anthropic", "kimi", "claude"}:
            runner = self._run_anthropic_compatible
        else:
            runner = self._run_openai_compatible
        try:
            return _with_transport_receipt(
                self._run_remote_attempt(runner, request, json_recovery=False),
                attempts=1,
                json_recovery_attempted=False,
                execution_budget=self.execution_budget_receipt(),
            )
        except BrainInvalidJsonResponse:
            try:
                return _with_transport_receipt(
                    self._run_remote_attempt(runner, request, json_recovery=True),
                    attempts=2,
                    json_recovery_attempted=True,
                    execution_budget=self.execution_budget_receipt(),
            )
            except BrainInvalidJsonResponse as recovery_error:
                if isinstance(recovery_error, BrainOutputTruncated):
                    raise BrainOutputTruncated(
                        "remote brain response was truncated after one bounded serialization recovery",
                        stage=request.stage,
                        attempts=2,
                        json_recovery_attempted=True,
                        json_recovery_succeeded=False,
                        json_parse_started=True,
                        json_parse_completed=False,
                    ) from recovery_error
                raise BrainInvalidJsonResponse(
                    "remote brain returned malformed JSON after one bounded serialization recovery",
                    stage=request.stage,
                    attempts=2,
                    json_recovery_attempted=True,
                    json_recovery_succeeded=False,
                    json_parse_started=getattr(recovery_error, "json_parse_started", True),
                    json_parse_completed=getattr(recovery_error, "json_parse_completed", False),
                    json_failure_kind=getattr(recovery_error, "json_failure_kind", "unknown"),
                ) from recovery_error

    def _run_remote_attempt(self, runner: Any, request: BrainRunRequest, *, json_recovery: bool) -> dict[str, Any]:
        timeout_seconds = self._effective_timeout_seconds(request)
        trace = _new_transport_trace(stage=request.stage, json_recovery=json_recovery)
        token = _ACTIVE_TRANSPORT_TRACE.set(trace)
        try:
            return _call_with_timeout(
                lambda: runner(request, json_recovery=json_recovery),
                timeout_seconds=timeout_seconds,
                trace=trace,
            )
        finally:
            _ACTIVE_TRANSPORT_TRACE.reset(token)

    def _ensure_budget_available(self) -> None:
        budget = _ACTIVE_EXECUTION_BUDGET.get()
        if budget is not None and budget.remaining_seconds() <= 0.0:
            raise BrainExecutionBudgetExceeded(
                "remote Brain logical execution budget exhausted before a complete prompt could be signed"
            )

    def _effective_timeout_seconds(self, request: BrainRunRequest) -> float:
        """Use the remaining shared deadline, never a stale full call timeout."""

        budget = _ACTIVE_EXECUTION_BUDGET.get()
        request_cap = _request_timeout_cap_seconds(request)
        base_timeout = min(self.timeout, request_cap) if request_cap is not None else self.timeout
        if budget is None:
            return base_timeout
        remaining = budget.remaining_seconds()
        if remaining <= 0.0:
            raise BrainExecutionBudgetExceeded(
                "remote Brain logical execution budget exhausted before another remote decision"
            )
        # A non-zero timeout is required by all supported transports.  The
        # value is still bounded by the remaining logical preparation budget.
        return max(0.1, min(base_timeout, remaining))

    def _run_openai_compatible(
        self,
        request: BrainRunRequest,
        *,
        json_recovery: bool = False,
    ) -> dict[str, Any]:
        api_key, base_url = self._credentials()
        # DeepSeek is OpenAI-compatible but its deployed endpoint exposes the
        # broadly supported Chat Completions contract rather than the newer
        # Responses contract.  Choosing the transport by the declared Brain
        # provider keeps an image gateway credential from deciding how the
        # Central Brain talks to its own remote model.
        if self.provider == "deepseek":
            return self._run_openai_chat_completions(
                api_key=api_key,
                base_url=base_url,
                request=request,
                json_recovery=json_recovery,
            )
        try:
            return self._run_openai_responses(
                api_key=api_key,
                base_url=base_url,
                request=request,
                json_recovery=json_recovery,
            )
        except _BrainProtocolUnsupported:
            # Some OpenAI-compatible gateways expose Chat Completions but not
            # Responses. This is still the same remote Brain decision: only
            # the wire protocol changes. Auth, timeout, business, and schema
            # failures remain fail-closed and are never retried on another path.
            return self._run_openai_chat_completions(
                api_key=api_key,
                base_url=base_url,
                request=request,
                json_recovery=json_recovery,
            )

    def _run_openai_responses(
        self,
        *,
        api_key: str,
        base_url: str | None,
        request: BrainRunRequest,
        json_recovery: bool = False,
    ) -> dict[str, Any]:
        try:
            from openai import OpenAI

            # Central Brain has one bounded remote attempt.  SDK-level retries
            # would silently multiply a logical request and hide the actual
            # upstream terminal state from the specialized fail-closed gate.
            _mark_transport_event("client_constructing")
            kwargs = _openai_client_kwargs(api_key=api_key, base_url=base_url, max_retries=0)
            client = OpenAI(**kwargs)
            _mark_transport_event("client_constructed")
            _mark_transport_event("request_dispatched")
            response = client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": _system_prompt(request.stage, json_recovery=json_recovery),
                    },
                    {"role": "user", "content": build_remote_payload(request)},
                ],
                text={"format": {"type": "json_object"}},
                timeout=self._effective_timeout_seconds(request),
                max_output_tokens=self.max_tokens,
            )
            _mark_transport_event("complete_response_observed")
            text = getattr(response, "output_text", None) or ""
            if not text:
                text = _response_text_from_openai(response)
            if _response_ended_at_output_limit(response):
                raise BrainOutputTruncated("remote brain response ended at the configured output-token limit")
            _mark_transport_event("json_parse_started")
            parsed = _loads_json_object(text)
            _mark_transport_event("json_parse_completed")
            return parsed
        except BrainInvalidJsonResponse:
            raise
        except Exception as exc:
            if _is_unsupported_brain_protocol_error(exc):
                raise _BrainProtocolUnsupported from exc
            raise BrainProviderError(f"remote brain provider failed: {str(exc)[:240]}") from exc

    def _run_openai_chat_completions(
        self,
        *,
        api_key: str,
        base_url: str | None,
        request: BrainRunRequest,
        json_recovery: bool = False,
    ) -> dict[str, Any]:
        """Run a JSON-only Central Brain request through Chat Completions.

        This is a remote-provider transport adaptation, not a deterministic
        creative fallback.  Callers still receive a provider error and
        specialized templates still fail closed if the remote answer is absent
        or violates its frozen image-set contract.
        """

        try:
            timeout_seconds = self._effective_timeout_seconds(request)
            record_stage_event(
                "brain_provider",
                "stream_request_prepared",
                stage=request.stage,
                extra={
                    "requested_image_count": request.requested_image_count,
                    "timeout_seconds": timeout_seconds,
                },
            )
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": _system_prompt(request.stage, json_recovery=json_recovery),
                    },
                    {"role": "user", "content": build_remote_payload(request)},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "max_tokens": self.max_tokens,
                "stream": True,
            }
            text = _collect_openai_chat_completion_stream(
                url=_chat_completions_url(base_url),
                api_key=api_key,
                payload=payload,
                timeout_seconds=timeout_seconds,
            )
            record_stage_event("brain_provider", "json_parse_started", stage=request.stage)
            _mark_transport_event("json_parse_started")
            parsed = _loads_json_object(text)
            record_stage_event("brain_provider", "json_parse_completed", stage=request.stage)
            _mark_transport_event("json_parse_completed")
            return parsed
        except BrainInvalidJsonResponse:
            raise
        except Exception as exc:
            raise BrainProviderError(f"remote brain provider failed: {str(exc)[:240]}") from exc

    def _run_anthropic_compatible(
        self,
        request: BrainRunRequest,
        *,
        json_recovery: bool = False,
    ) -> dict[str, Any]:
        api_key, base_url = self._credentials()
        if not base_url:
            raise BrainProviderUnavailable("anthropic-compatible brain base URL is not configured")
        try:
            import httpx

            headers = {"content-type": "application/json"}
            token_header = "x-api-key" if self.provider == "anthropic" else "authorization"
            headers[token_header] = api_key if token_header == "x-api-key" else f"Bearer {api_key}"
            url = f"{base_url.rstrip('/')}/v1/messages"
            payload = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": 0.2,
                "system": _system_prompt(request.stage, json_recovery=json_recovery),
                "messages": [{"role": "user", "content": build_remote_payload(request)}],
            }
            _mark_transport_event("client_constructing")
            with httpx.Client(timeout=self._effective_timeout_seconds(request)) as client:
                _mark_transport_event("client_constructed")
                _mark_transport_event("request_dispatched")
                response = client.post(url, headers=headers, json=payload)
                _mark_transport_event("complete_response_observed")
                response.raise_for_status()
            response_json = response.json()
            if _response_ended_at_output_limit(response_json):
                raise BrainOutputTruncated("remote brain response ended at the configured output-token limit")
            _mark_transport_event("json_parse_started")
            parsed = _loads_json_object(_anthropic_text(response_json))
            _mark_transport_event("json_parse_completed")
            return parsed
        except BrainInvalidJsonResponse:
            raise
        except Exception as exc:
            raise BrainProviderError(f"remote brain provider failed: {str(exc)[:240]}") from exc

    def _credentials(self) -> tuple[str, str | None]:
        if self.provider in {"anthropic", "kimi", "claude"}:
            api_key = (
                _env("V3_LLM_BRAIN_API_KEY")
                or _settings_value("anthropic_auth_token")
                or _settings_value("anthropic_api_key")
                or _settings_value("lab_kimi_api_key")
            )
            base_url = _env("V3_LLM_BRAIN_BASE_URL") or _settings_value("anthropic_base_url") or _settings_value("lab_kimi_base_url")
        elif self.provider == "deepseek":
            # DeepSeek is OpenAI-compatible at transport level, but it owns
            # its own configured credential/base URL.  Do not silently route
            # Central Brain calls through the unrelated image gateway simply
            # because OPENAI_API_KEY is also present in the process.
            api_key = (
                _env("V3_LLM_BRAIN_API_KEY")
                or _settings_value("deepseek_llm_api_key")
            )
            base_url = (
                _env("V3_LLM_BRAIN_BASE_URL")
                or _settings_value("deepseek_llm_base_url")
            )
        else:
            api_key = _env("V3_LLM_BRAIN_API_KEY") or _settings_value("openai_api_key") or _settings_value("lab_openai_api_key")
            base_url = _env("V3_LLM_BRAIN_BASE_URL") or _settings_value("openai_base_url") or _settings_value("lab_openai_base_url")
        if not api_key:
            raise BrainProviderUnavailable("remote brain API key is not configured")
        return str(api_key), str(base_url) if base_url else None


def _default_model(provider: str) -> str:
    if provider in {"anthropic", "kimi", "claude"}:
        return _settings_value("kimi_llm_model") or _settings_value("backup_llm_model") or "kimi-for-coding"
    if provider == "deepseek":
        return _settings_value("deepseek_llm_model") or _settings_value("default_llm_model") or "deepseek-v4-pro-260425"
    return _settings_value("openai_llm_model") or _settings_value("default_llm_model") or "gpt-5.5"


def _preferred_provider() -> str:
    configured = str(_settings_value("default_llm_provider") or "").strip().lower()
    if configured in {"openai", "deepseek", "anthropic", "kimi", "claude"}:
        return configured
    if _settings_value("openai_api_key") or _settings_value("lab_openai_api_key"):
        return "openai"
    return _settings_value("default_llm_provider") or "openai"


def _settings_value(name: str) -> Any:
    try:
        from app.config import settings

        return getattr(settings, name, None)
    except Exception:
        return None


def _request_timeout_cap_seconds(request: BrainRunRequest) -> float | None:
    raw = getattr(request, "transport_timeout_seconds", None)
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return max(1.0, min(210.0, value))


def _call_with_timeout(
    callable_obj: Any,
    *,
    timeout_seconds: float,
    trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    started = time.perf_counter()

    def runner() -> None:
        try:
            _mark_transport_event("provider_runner_entered")
            result["value"] = callable_obj()
        except BaseException as exc:  # pragma: no cover - re-raised in caller thread
            result["error"] = exc

    context = copy_context()
    thread = threading.Thread(target=lambda: context.run(runner), name="v3-llm-brain-provider", daemon=True)
    thread.start()
    thread.join(timeout=max(0.1, float(timeout_seconds)))
    if thread.is_alive():
        raise _transport_timeout_from_trace(
            trace or {},
            timeout_seconds=float(timeout_seconds),
            elapsed_ms=int(round((time.perf_counter() - started) * 1000)),
        )
    if "error" in result:
        raise result["error"]
    value = result.get("value")
    if not isinstance(value, dict):
        raise BrainProviderError("remote brain provider returned an invalid payload")
    return value


def _new_transport_trace(*, stage: str, json_recovery: bool) -> dict[str, Any]:
    return {
        "schema_version": "v3_brain_transport_trace_v1",
        "stage": str(stage or "unknown"),
        "json_recovery": bool(json_recovery),
        "last_event": "created",
        "response_started": False,
        "first_content_observed": False,
        "complete_response_observed": False,
        "json_parse_started": False,
        "json_parse_completed": False,
    }


def _mark_transport_event(event: str) -> None:
    trace = _ACTIVE_TRANSPORT_TRACE.get()
    if not isinstance(trace, dict):
        return
    normalized = str(event or "").strip().lower()
    trace["last_event"] = normalized
    if normalized in {"complete_response_observed", "json_parse_started", "json_parse_completed"}:
        trace["response_started"] = True
        trace["first_content_observed"] = True
    if normalized == "response_started":
        trace["response_started"] = True
    if normalized == "first_content_observed":
        trace["response_started"] = True
        trace["first_content_observed"] = True
    if normalized == "complete_response_observed":
        trace["complete_response_observed"] = True
    if normalized == "json_parse_started":
        trace["json_parse_started"] = True
    if normalized == "json_parse_completed":
        trace["json_parse_started"] = True
        trace["json_parse_completed"] = True


def _transport_timeout_from_trace(
    trace: dict[str, Any],
    *,
    timeout_seconds: float,
    elapsed_ms: int,
) -> BrainTransportTimeoutError:
    phase = _transport_timeout_phase(trace)
    return BrainTransportTimeoutError(
        stage=str(trace.get("stage") or "unknown"),
        timeout_seconds=timeout_seconds,
        elapsed_ms=elapsed_ms,
        timeout_phase=phase,
        response_started=bool(trace.get("response_started")),
        first_content_observed=bool(trace.get("first_content_observed")),
        complete_response_observed=bool(trace.get("complete_response_observed")),
        json_parse_started=bool(trace.get("json_parse_started")),
        json_parse_completed=bool(trace.get("json_parse_completed")),
    )


def _transport_timeout_phase(trace: dict[str, Any]) -> str:
    if bool(trace.get("json_parse_started")) and not bool(trace.get("json_parse_completed")):
        return "json_parse_timeout"
    if bool(trace.get("first_content_observed")) or bool(trace.get("response_started")):
        return "read_timeout"
    last_event = str(trace.get("last_event") or "").strip().lower()
    if last_event in {"client_constructing", "created"}:
        return "connect_timeout"
    if last_event == "request_dispatched":
        return "ttfb_timeout"
    return "unknown_transport_timeout"


def _safe_transport_timeout_phase(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {
        "connect_timeout",
        "ttfb_timeout",
        "read_timeout",
        "complete_response_timeout",
        "json_parse_timeout",
        "unknown_transport_timeout",
    }:
        return normalized
    return "unknown_transport_timeout"


def _is_unsupported_brain_protocol_error(error: BaseException) -> bool:
    """Recognize only gateway-level protocol absence, never general failure."""

    status = getattr(error, "status_code", None)
    if status is None:
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
    try:
        return int(status) in {404, 405, 426, 501}
    except (TypeError, ValueError):
        return False


def _chat_completions_url(base_url: str | None) -> str:
    base = str(base_url or "").rstrip("/")
    if not base:
        return "/v1/chat/completions"
    return f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"


def _collect_openai_chat_completion_stream(
    *,
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> str:
    """Collect one streamed Chat Completions JSON response without repairing it locally."""

    import httpx

    headers = {"authorization": f"Bearer {api_key}", "content-type": "application/json"}
    timeout = httpx.Timeout(
        connect=min(20.0, max(0.1, float(timeout_seconds))),
        read=max(0.1, float(timeout_seconds)),
        write=min(30.0, max(0.1, float(timeout_seconds))),
        pool=min(20.0, max(0.1, float(timeout_seconds))),
    )
    chunks: list[str] = []
    done = False
    _mark_transport_event("client_constructing")
    record_stage_event("brain_provider", "stream_client_constructing")
    with httpx.Client(timeout=timeout) as client:
        _mark_transport_event("client_constructed")
        record_stage_event("brain_provider", "stream_client_constructed")
        _mark_transport_event("request_dispatched")
        record_stage_event("brain_provider", "stream_request_dispatched")
        with client.stream("POST", url, headers=headers, json=payload) as response:
            _mark_transport_event("response_started")
            record_stage_event("brain_provider", "stream_response_started")
            response.raise_for_status()
            for raw_line in response.iter_lines():
                line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else str(raw_line or "")
                line = line.strip()
                if not line:
                    continue
                data = line[5:].strip() if line.startswith("data:") else line
                if data == "[DONE]":
                    done = True
                    _mark_transport_event("complete_response_observed")
                    record_stage_event("brain_provider", "stream_complete_response_observed")
                    break
                try:
                    item = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = item.get("choices") if isinstance(item, dict) else None
                choice = choices[0] if isinstance(choices, list) and choices else None
                finish_reason = str(choice.get("finish_reason") or "").strip().lower() if isinstance(choice, dict) else ""
                if isinstance(choice, dict) and (
                    _response_ended_at_output_limit(item, choice=choice)
                    or finish_reason
                    in {
                        "length",
                        "max_tokens",
                        "max_output_tokens",
                        "output_token_limit",
                        "output_tokens_limit",
                    }
                ):
                    raise BrainOutputTruncated("remote brain response ended at the configured output-token limit")
                delta = choice.get("delta") if isinstance(choice, dict) else None
                content = delta.get("content") if isinstance(delta, dict) else None
                if content:
                    _mark_transport_event("first_content_observed")
                    record_stage_event("brain_provider", "stream_first_content_observed")
                    chunks.append(str(content))
    if not done:
        raise BrainInvalidJsonResponse(
            "remote brain stream ended before the complete JSON response marker",
            json_failure_kind="missing_complete_marker",
            json_parse_started=False,
            json_parse_completed=False,
        )
    return "".join(chunks)


def _openai_client_kwargs(*, api_key: str, base_url: str | None, **extra: Any) -> dict[str, Any]:
    try:
        from app.config import openai_sdk_client_kwargs

        return openai_sdk_client_kwargs(api_key=api_key, base_url=base_url, **extra)
    except Exception:
        kwargs: dict[str, Any] = {"api_key": api_key, **extra}
        if base_url:
            kwargs["base_url"] = base_url
        return kwargs


def _env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def _remote_enabled(*, force: bool = False) -> bool:
    raw = os.getenv("V3_LLM_BRAIN_REMOTE_ENABLED")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if force:
        return True
    if _env("V3_LLM_BRAIN_API_KEY"):
        return True
    provider = (_env("V3_LLM_BRAIN_PROVIDER") or _preferred_provider()).strip().lower()
    if provider == "deepseek":
        return bool(_settings_value("deepseek_llm_api_key"))
    if provider in {"anthropic", "kimi", "claude"}:
        return bool(_settings_value("anthropic_auth_token") or _settings_value("anthropic_api_key"))
    return bool(_settings_value("openai_api_key") or _settings_value("lab_openai_api_key"))


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return max(512, min(8000, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


def _loads_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        raise BrainInvalidJsonResponse("remote brain returned empty JSON output", json_failure_kind="empty_json")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as first_error:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise BrainInvalidJsonResponse(
                "remote brain returned malformed JSON output",
                json_failure_kind="malformed_json",
            ) from first_error
        try:
            parsed = json.loads(raw[start : end + 1])
        except json.JSONDecodeError as sliced_error:
            raise BrainInvalidJsonResponse(
                "remote brain returned malformed JSON output",
                json_failure_kind="malformed_json",
            ) from sliced_error
    if not isinstance(parsed, dict):
        raise BrainInvalidJsonResponse(
            "remote brain json output was not an object",
            json_failure_kind="non_object_json",
        )
    return parsed


def _response_ended_at_output_limit(response: Any, *, choice: Any | None = None) -> bool:
    """Recognize provider-neutral transport truncation without reading model text."""

    values: list[Any] = []
    if isinstance(response, dict):
        values.extend(
            [
                response.get("stop_reason"),
                response.get("finish_reason"),
                (response.get("incomplete_details") or {}).get("reason")
                if isinstance(response.get("incomplete_details"), dict)
                else None,
            ]
        )
    else:
        incomplete = getattr(response, "incomplete_details", None)
        values.extend(
            [
                getattr(response, "status", None),
                getattr(incomplete, "reason", None),
            ]
        )
    values.append(getattr(choice, "finish_reason", None))
    normalized = {str(value or "").strip().lower() for value in values}
    return bool(
        normalized
        & {
            "length",
            "max_tokens",
            "max_output_tokens",
            "output_token_limit",
            "output_tokens_limit",
        }
    )


_TRANSPORT_RECEIPT_KEY = "_alchemy_brain_transport"
_JSON_SERIALIZATION_RECOVERY_SUFFIX = """

TRANSPORT RECOVERY: Your immediately preceding response could not be parsed as
JSON. Re-evaluate the same frozen request and return one complete, strictly
valid JSON object that satisfies the existing output contract. Do not add
commentary, Markdown, diagnostics, or local workaround instructions. Do not
reuse or quote malformed output; author the full contract again yourself.
""".strip()


def _system_prompt(stage: str, *, json_recovery: bool) -> str:
    """Keep a recovery transport instruction outside creative prompt ownership."""

    return (
        f"{system_prompt_for_stage(stage)}\n\n{_JSON_SERIALIZATION_RECOVERY_SUFFIX}"
        if json_recovery
        else system_prompt_for_stage(stage)
    )


def _with_transport_receipt(
    payload: dict[str, Any],
    *,
    attempts: int,
    json_recovery_attempted: bool,
    execution_budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach only safe transport provenance for adapter/job audit projection."""

    result = dict(payload)
    result[_TRANSPORT_RECEIPT_KEY] = {
        "attempts": attempts,
        "json_serialization_recovery_attempted": json_recovery_attempted,
        "json_serialization_recovery_succeeded": json_recovery_attempted,
        **({"execution_budget": dict(execution_budget)} if execution_budget else {}),
    }
    return result


def pop_transport_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove and validate the private, non-creative transport receipt."""

    raw = payload.pop(_TRANSPORT_RECEIPT_KEY, None)
    if not isinstance(raw, dict):
        return {}
    attempts = raw.get("attempts")
    attempted = raw.get("json_serialization_recovery_attempted")
    succeeded = raw.get("json_serialization_recovery_succeeded")
    if attempts not in {1, 2} or not isinstance(attempted, bool) or not isinstance(succeeded, bool):
        return {}
    if succeeded and not attempted:
        return {}
    receipt = {
        "attempts": attempts,
        "json_serialization_recovery_attempted": attempted,
        "json_serialization_recovery_succeeded": succeeded,
    }
    execution_budget = raw.get("execution_budget")
    if isinstance(execution_budget, dict):
        logical_budget_seconds = execution_budget.get("logical_budget_seconds")
        remaining_ms = execution_budget.get("remaining_ms")
        state = execution_budget.get("state")
        if (
            isinstance(logical_budget_seconds, (int, float))
            and float(logical_budget_seconds) > 0.0
            and isinstance(remaining_ms, int)
            and remaining_ms >= 0
            and state in {"within_budget", "exhausted"}
        ):
            receipt["execution_budget"] = {
                "logical_budget_seconds": float(logical_budget_seconds),
                "remaining_ms": remaining_ms,
                "state": state,
            }
    return receipt


def _response_text_from_openai(response: Any) -> str:
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(str(text))
    return "\n".join(chunks)


def _anthropic_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in payload.get("content", []) if isinstance(payload, dict) else []:
        if isinstance(item, dict) and item.get("type") == "text":
            chunks.append(str(item.get("text") or ""))
    return "\n".join(chunks)
