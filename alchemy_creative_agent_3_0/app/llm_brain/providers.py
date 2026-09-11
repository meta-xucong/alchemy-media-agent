"""Remote provider facade for the V3 LLM Brain."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from dataclasses import dataclass
import json
import os
import re
import threading
import time
from typing import Any

from .contracts import (
    BRAIN_EXECUTION_BUDGET_DEFAULT_SECONDS,
    BRAIN_EXECUTION_BUDGET_HANDOFF_SECONDS,
    BRAIN_TRANSPORT_TIMEOUT_PHASES,
    BRAIN_TRANSPORT_TIMEOUT_DEFAULT_SECONDS,
    BRAIN_TRANSPORT_TIMEOUT_MAX_SECONDS,
    BRAIN_TRANSPORT_TIMEOUT_MIN_SECONDS,
    BrainRunRequest,
)
from .prompts import build_remote_payload, system_prompt_for_stage
from .stage_trace import record_stage_event


class BrainProviderUnavailable(RuntimeError):
    """Raised when no remote brain provider is configured."""

    def __init__(self, message: str, *, reason_code: str = "provider_unavailable") -> None:
        super().__init__(message)
        self.reason_code = str(reason_code or "provider_unavailable").strip() or "provider_unavailable"


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
        request_dispatched: bool = False,
        request_acceptance: str | None = None,
        request_call_entered: bool = False,
        response_started: bool = False,
        first_content_observed: bool = False,
        complete_response_observed: bool = False,
        json_parse_started: bool = False,
        json_parse_completed: bool = False,
    ) -> None:
        super().__init__(
            f"remote Brain provider timed out during {timeout_phase} after {timeout_seconds:.2f} seconds"
        )
        self.stage = _safe_brain_stage(stage)
        self.timeout_seconds = max(0.0, float(timeout_seconds))
        self.elapsed_ms = max(0, int(elapsed_ms))
        self.timeout_phase = _safe_transport_timeout_phase(timeout_phase)
        self.request_acceptance = _safe_request_acceptance(
            request_acceptance,
            request_dispatched=request_dispatched,
            request_call_entered=request_call_entered,
            response_started=response_started,
        )
        self.request_dispatched = self.request_acceptance == "dispatched"
        self.request_call_entered = bool(
            request_call_entered
            or self.request_dispatched
            or self.request_acceptance == "unknown"
        )
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
            "request_acceptance": self.request_acceptance,
            "response_started": self.response_started,
            "first_content_observed": self.first_content_observed,
            "complete_response_observed": self.complete_response_observed,
            "json_parse_started": self.json_parse_started,
            "json_parse_completed": self.json_parse_completed,
        }


class BrainPromptContractInvalid(BrainProviderError):
    """The remote Brain returned a malformed canonical provider-prompt contract."""


class BrainPromptRequestContractInvalid(BrainPromptContractInvalid):
    """The local frozen request contract is invalid before a Brain call."""


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

    def __init__(self, message: str, **kwargs: Any) -> None:
        # An output-limit signal is raised before the response is handed to
        # the JSON parser. Enforce that invariant at the exception boundary
        # so provider implementations and test doubles cannot accidentally
        # publish it as a parse failure.
        kwargs["json_parse_started"] = False
        kwargs["json_parse_completed"] = False
        super().__init__(message, **kwargs)

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


class _TransportCancellation:
    """Close resources owned by a timed-out remote transport attempt.

    The provider facade still supports synchronous SDKs, so one outer worker
    thread remains the last-resort deadline guard. Network transports register
    their own close methods here; a timeout can then terminate the actual HTTP
    operation instead of merely abandoning its worker.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._callbacks: dict[int, Any] = {}
        self._next_token = 0
        self._cancelled = False

    def register(self, callback: Any) -> int | None:
        if not callable(callback):
            return None
        with self._lock:
            if self._cancelled:
                call_now = True
                token = None
            else:
                self._next_token += 1
                token = self._next_token
                self._callbacks[token] = callback
                call_now = False
        if call_now:
            self._dispatch(callback)
        return token

    def unregister(self, token: int | None) -> None:
        if token is None:
            return
        with self._lock:
            self._callbacks.pop(token, None)

    def cancel(self) -> None:
        with self._lock:
            if self._cancelled:
                return
            self._cancelled = True
            callbacks = list(self._callbacks.values())
            self._callbacks.clear()
        for callback in callbacks:
            self._dispatch(callback)

    @classmethod
    def _dispatch(cls, callback: Any) -> None:
        """Start close without letting a third-party cleanup block the deadline."""

        try:
            threading.Thread(
                target=cls._invoke,
                args=(callback,),
                name="v3-llm-brain-transport-close",
                daemon=True,
            ).start()
        except BaseException:
            # The outer timeout remains authoritative even if a best-effort
            # close worker cannot be started.
            return

    @staticmethod
    def _invoke(callback: Any) -> None:
        try:
            callback()
        except BaseException:
            # Cancellation is best effort. The original timeout remains the
            # authoritative failure even when an SDK close method is noisy.
            return


_ACTIVE_EXECUTION_BUDGET: ContextVar[_BrainExecutionBudget | None] = ContextVar(
    "v3_active_remote_brain_execution_budget",
    default=None,
)
_ACTIVE_TRANSPORT_TRACE: ContextVar[dict[str, Any] | None] = ContextVar(
    "v3_active_remote_brain_transport_trace",
    default=None,
)
_ACTIVE_TRANSPORT_CANCELLATION: ContextVar[_TransportCancellation | None] = ContextVar(
    "v3_active_remote_brain_transport_cancellation",
    default=None,
)
_STREAM_PROGRESS_GRACE_SECONDS = 30.0
_TRANSPORT_TRACE_ATTR = "_v3_brain_transport_trace"
_TRANSPORT_FAILURE_RECEIPT_ATTR = "_v3_brain_transport_failure_receipt"
_TRANSPORT_ATTEMPT_RECEIPT_KEY = "_alchemy_brain_transport_attempt"
_BRAIN_OUTPUT_TOKEN_DEFAULT = 20_000
_BRAIN_OUTPUT_TOKEN_MAX = 32_768


class V3LLMBrainProvider:
    """Small provider adapter that keeps V3 brain calls optional."""

    def __init__(self) -> None:
        self.provider = _env("V3_LLM_BRAIN_PROVIDER") or _preferred_provider()
        self.provider = self.provider.strip().lower()
        self.model = _env("V3_LLM_BRAIN_MODEL") or _default_model(self.provider)
        # A provider-specific reasoning control is opt-in. The collector can
        # observe private reasoning without changing the model's creative
        # decision policy; transport compatibility must not silently change
        # the reasoning behavior of every DeepSeek route.
        self.reasoning_effort = _configured_reasoning_effort(self.provider)
        self.timeout = max(
            BRAIN_TRANSPORT_TIMEOUT_MIN_SECONDS,
            min(
                BRAIN_TRANSPORT_TIMEOUT_MAX_SECONDS,
                _float_env(
                    "V3_LLM_BRAIN_TIMEOUT_SECONDS",
                    BRAIN_TRANSPORT_TIMEOUT_DEFAULT_SECONDS,
                ),
            ),
        )
        # A V3 preparation has more than one legitimate Brain decision: a
        # semantic plan and the final signed renderer direction.  Bound the
        # *logical* preparation as one unit so a later valid sign-off does not
        # inherit a stale per-call deadline or leave a caller waiting without a
        # terminal reason.  This budget change is transport-only; it does not
        # add recovery behavior, change creative ownership, or permit a local
        # prompt fallback.
        self.execution_budget_seconds = _float_env(
            "V3_LLM_BRAIN_EXECUTION_BUDGET_SECONDS",
            max(
                BRAIN_EXECUTION_BUDGET_DEFAULT_SECONDS,
                self.timeout + BRAIN_EXECUTION_BUDGET_HANDOFF_SECONDS,
            ),
        )
        # A compact V3 plan can still need substantial output allowance when a
        # reasoning-capable remote model accounts for its private deliberation
        # before returning the complete JSON contract.  The previous 12000
        # ceiling was observed to terminate the same frozen request before its
        # JSON answer.  This is an output-capacity setting only: it neither
        # changes frozen evidence nor permits local JSON/prompt reconstruction.
        self.max_tokens = _int_env("V3_LLM_BRAIN_MAX_TOKENS", _BRAIN_OUTPUT_TOKEN_DEFAULT)

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
        return bool(self.availability(force=force).get("available"))

    def availability(self, *, force: bool = False) -> dict[str, Any]:
        """Return a safe configuration diagnosis without performing a network call."""

        provider = str(self.provider or "unknown").strip().lower() or "unknown"
        model = str(self.model or "unknown").strip() or "unknown"
        if not _remote_enabled(force=force):
            return {
                "available": False,
                "reason_code": "remote_disabled",
                "provider": provider,
                "model": model,
                "health_checked": False,
            }
        try:
            _api_key, base_url = self._credentials()
        except BrainProviderUnavailable:
            return {
                "available": False,
                "reason_code": "missing_credentials",
                "provider": provider,
                "model": model,
                "health_checked": False,
            }
        if base_url and not str(base_url).lower().startswith(("http://", "https://")):
            return {
                "available": False,
                "reason_code": "invalid_configuration",
                "provider": provider,
                "model": model,
                "health_checked": False,
            }
        return {
            "available": True,
            "reason_code": "configured",
            "provider": provider,
            "model": model,
            "health_checked": False,
        }

    def run(self, request: BrainRunRequest) -> dict[str, Any]:
        """Run one Brain decision with bounded transport and JSON recovery.

        A malformed JSON reply is not an accepted creative decision.  The
        recovery therefore asks the same remote Brain to re-answer the same
        frozen request once; it never locally repairs JSON, reconstructs a
        prompt, changes a reference, or starts an image operation.  A
        transient transport/upstream failure gets the same one bounded retry,
        but only while the existing shared execution budget still has time.
        """

        try:
            self._ensure_budget_available()
        except BrainExecutionBudgetExceeded as exc:
            _annotate_transport_failure(
                exc,
                attempts=0,
                json_recovery_attempted=False,
                transient_recovery_attempted=False,
                stage=request.stage,
            )
            raise
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
        except BrainInvalidJsonResponse as first_error:
            try:
                return _with_transport_receipt(
                    self._run_remote_attempt(runner, request, json_recovery=True),
                    attempts=2,
                    json_recovery_attempted=True,
                    execution_budget=self.execution_budget_receipt(),
            )
            except BrainInvalidJsonResponse as recovery_error:
                _annotate_transport_failure(
                    recovery_error,
                    attempts=2,
                    json_recovery_attempted=True,
                    transient_recovery_attempted=False,
                )
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
            except BrainProviderError as recovery_error:
                _annotate_transport_failure(
                    recovery_error,
                    attempts=2,
                    json_recovery_attempted=True,
                    transient_recovery_attempted=False,
                )
                raise recovery_error from first_error
        except BrainProviderError as first_error:
            if not _is_retryable_transient_provider_error(first_error):
                _annotate_transport_failure(
                    first_error,
                    attempts=1,
                    json_recovery_attempted=False,
                    transient_recovery_attempted=False,
                )
                raise
            # Keep the shared logical deadline authoritative.  A retry must
            # never reset the budget or turn an auth/contract failure into a
            # second remote call.
            if _ACTIVE_EXECUTION_BUDGET.get() is None:
                _annotate_transport_failure(
                    first_error,
                    attempts=1,
                    json_recovery_attempted=False,
                    transient_recovery_attempted=False,
                )
                raise
            try:
                self._ensure_budget_available()
            except BrainExecutionBudgetExceeded as budget_error:
                _annotate_transport_failure(
                    budget_error,
                    attempts=1,
                    json_recovery_attempted=False,
                    transient_recovery_attempted=False,
                )
                raise budget_error from first_error
            try:
                recovered = self._run_remote_attempt(runner, request, json_recovery=False)
            except BrainProviderError as recovery_error:
                _annotate_transport_failure(
                    recovery_error,
                    attempts=2,
                    json_recovery_attempted=False,
                    transient_recovery_attempted=True,
                )
                raise recovery_error from first_error
            return _with_transport_receipt(
                recovered,
                attempts=2,
                json_recovery_attempted=False,
                transient_recovery_attempted=True,
                execution_budget=self.execution_budget_receipt(),
            )

    def _run_remote_attempt(self, runner: Any, request: BrainRunRequest, *, json_recovery: bool) -> dict[str, Any]:
        timeout_seconds, maximum_deadline = self._effective_timeout_and_deadline(request)
        trace = _new_transport_trace(stage=request.stage, json_recovery=json_recovery)
        token = _ACTIVE_TRANSPORT_TRACE.set(trace)
        try:
            value = _call_with_timeout(
                lambda: runner(request, json_recovery=json_recovery),
                timeout_seconds=timeout_seconds,
                trace=trace,
                maximum_deadline=maximum_deadline,
            )
            if isinstance(value, dict):
                # Successful responses need the same closed attempt evidence
                # as failures. The adapter may reject the returned canonical
                # contract after this point, so do not discard the transport
                # phase simply because the wire call returned HTTP 200.
                result = dict(value)
                attempt_receipt = _safe_transport_trace_receipt(trace)
                if any(
                    bool(attempt_receipt.get(key))
                    for key in (
                        "request_dispatched",
                        "response_started",
                        "first_content_observed",
                        "complete_response_observed",
                        "json_parse_started",
                        "json_parse_completed",
                    )
                ) or attempt_receipt.get("request_acceptance") == "unknown":
                    result[_TRANSPORT_ATTEMPT_RECEIPT_KEY] = attempt_receipt
                return result
            return value
        except BaseException as exc:
            # Keep only a closed transport trace on the exception.  The
            # adapter can aggregate it across a bounded recovery chain while
            # prompt, URL, headers, body, and provider response text remain
            # outside durable metadata.
            setattr(exc, _TRANSPORT_TRACE_ATTR, _safe_transport_trace_receipt(trace))
            raise
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

        timeout_seconds, _ = self._effective_timeout_and_deadline(request)
        return timeout_seconds

    def _effective_timeout_and_deadline(self, request: BrainRunRequest) -> tuple[float, float | None]:
        """Return one transport timeout and its absolute progress ceiling.

        The hard timeout intentionally leaves room for one bounded streaming
        progress grace window.  When a real-image planning request also has a
        canonical-finalizer reserve, the grace ceiling must stop at the end of
        the planning window rather than at the full logical deadline.  Keeping
        both values from one clock snapshot prevents the outer worker guard
        from silently borrowing the downstream handoff reserve.
        """

        budget = _ACTIVE_EXECUTION_BUDGET.get()
        request_cap = _request_timeout_cap_seconds(request)
        base_timeout = min(self.timeout, request_cap) if request_cap is not None else self.timeout
        if budget is None:
            return base_timeout, None
        now = time.perf_counter()
        remaining = max(0.0, budget.deadline - now)
        if remaining <= 0.0:
            raise BrainExecutionBudgetExceeded(
                "remote Brain logical execution budget exhausted before another remote decision"
            )
        # A real-image preparation has two required remote decisions: the
        # semantic plan and the canonical renderer sign-off.  The provider's
        # transient retry is bounded inside ``run``, but without a stage-aware
        # reserve a slow first plan can consume the handoff window with its
        # retry and leave the finalizer only a few seconds.  Keep the existing
        # shared budget and retry policy; make the already-defined handoff
        # portion authoritative for the later finalizer instead of letting a
        # plan retry borrow it.
        finalizer_reserve = _required_finalizer_reserve_seconds(request)
        available_for_stage = remaining - finalizer_reserve
        if available_for_stage < BRAIN_TRANSPORT_TIMEOUT_MIN_SECONDS:
            if finalizer_reserve:
                raise BrainExecutionBudgetExceeded(
                    "remote Brain logical execution budget must preserve the canonical finalizer handoff window"
                )
            raise BrainExecutionBudgetExceeded(
                "remote Brain logical execution budget exhausted before another remote decision"
            )
        # ``_call_with_timeout`` may grant one bounded progress grace window
        # when a streaming response is still producing semantic content.  A
        # real-image plan must pay for that grace from its own stage window;
        # otherwise the nominal timeout cap can still cross the finalizer
        # handoff floor and leave the canonical sign-off with a partial
        # budget.  Keep the existing grace behavior, but make it budget-
        # neutral for the later stage.
        progress_grace_reserve = min(_STREAM_PROGRESS_GRACE_SECONDS, base_timeout)
        stage_timeout_budget = available_for_stage - progress_grace_reserve
        if finalizer_reserve and stage_timeout_budget < BRAIN_TRANSPORT_TIMEOUT_MIN_SECONDS:
            raise BrainExecutionBudgetExceeded(
                "remote Brain logical execution budget must preserve the canonical finalizer handoff window"
            )
        # A non-zero timeout is required by all supported transports.  The
        # value is still bounded by the remaining logical preparation budget.
        return (
            max(0.1, min(base_timeout, stage_timeout_budget if finalizer_reserve else available_for_stage)),
            now + available_for_stage,
        )

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
        # Chat Completions is the portable OpenAI-compatible contract.  A
        # gateway may accept the request but leave the newer Responses route
        # hanging instead of returning a protocol error, so Responses is an
        # explicit opt-in rather than an implicit first attempt.
        if (_env("V3_LLM_BRAIN_TRANSPORT") or "chat").strip().lower() != "responses":
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
            _mark_transport_event("protocol_fallback")
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
        timeout_seconds = self._effective_timeout_seconds(request)
        started = time.perf_counter()
        try:
            from openai import OpenAI

            # Central Brain has one bounded remote attempt.  SDK-level retries
            # would silently multiply a logical request and hide the actual
            # upstream terminal state from the specialized fail-closed gate.
            _mark_transport_event("client_constructing")
            kwargs = _openai_client_kwargs(api_key=api_key, base_url=base_url, max_retries=0)
            client = OpenAI(**kwargs)
            _mark_transport_event("client_constructed")
            client_registration = _register_transport_close(client)
            try:
                _mark_transport_event("complete_response_call_entered")
                _mark_transport_event("request_call_entered")
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
                    timeout=timeout_seconds,
                    max_output_tokens=self.max_tokens,
                )
                _mark_transport_event("request_dispatched")
                _mark_transport_event("complete_response_started")
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
            finally:
                _unregister_transport_close(client_registration)
        except BrainTransportTimeoutError:
            raise
        except BrainInvalidJsonResponse:
            raise
        except Exception as exc:
            _mark_transport_dispatch_from_exception(exc)
            if _is_transport_timeout_exception(exc):
                raise _transport_timeout_from_trace(
                    _ACTIVE_TRANSPORT_TRACE.get() or {},
                    timeout_seconds=timeout_seconds,
                    elapsed_ms=int(round((time.perf_counter() - started) * 1000)),
                ) from exc
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

        timeout_seconds = self._effective_timeout_seconds(request)
        started = time.perf_counter()
        try:
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
            reasoning_effort = getattr(self, "reasoning_effort", None)
            if reasoning_effort:
                payload["reasoning_effort"] = reasoning_effort
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
        except BrainTransportTimeoutError:
            raise
        except BrainInvalidJsonResponse:
            raise
        except Exception as exc:
            _mark_transport_dispatch_from_exception(exc)
            if _is_transport_timeout_exception(exc):
                raise _transport_timeout_from_trace(
                    _ACTIVE_TRANSPORT_TRACE.get() or {},
                    timeout_seconds=timeout_seconds,
                    elapsed_ms=int(round((time.perf_counter() - started) * 1000)),
                ) from exc
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
        timeout_seconds = self._effective_timeout_seconds(request)
        started = time.perf_counter()
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
            with httpx.Client(timeout=timeout_seconds) as client:
                client_registration = _register_transport_close(client)
                try:
                    _mark_transport_event("client_constructed")
                    _mark_transport_event("complete_response_call_entered")
                    _mark_transport_event("request_call_entered")
                    response = client.post(url, headers=headers, json=payload)
                    _mark_transport_event("request_dispatched")
                    _mark_transport_event("complete_response_started")
                    _mark_transport_event("complete_response_observed")
                    response.raise_for_status()
                finally:
                    _unregister_transport_close(client_registration)
            _mark_transport_event("json_parse_started")
            response_json = response.json()
            if _response_ended_at_output_limit(response_json):
                raise BrainOutputTruncated("remote brain response ended at the configured output-token limit")
            parsed = _loads_json_object(_anthropic_text(response_json))
            _mark_transport_event("json_parse_completed")
            return parsed
        except BrainTransportTimeoutError:
            raise
        except BrainInvalidJsonResponse:
            raise
        except Exception as exc:
            _mark_transport_dispatch_from_exception(exc)
            if _is_transport_timeout_exception(exc):
                raise _transport_timeout_from_trace(
                    _ACTIVE_TRANSPORT_TRACE.get() or {},
                    timeout_seconds=timeout_seconds,
                    elapsed_ms=int(round((time.perf_counter() - started) * 1000)),
                ) from exc
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
        return _settings_value("deepseek_llm_model") or _settings_value("default_llm_model") or "deepseek-v4-pro"
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
    return max(
        BRAIN_TRANSPORT_TIMEOUT_MIN_SECONDS,
        min(BRAIN_TRANSPORT_TIMEOUT_MAX_SECONDS, value),
    )


def _required_finalizer_reserve_seconds(request: BrainRunRequest) -> float:
    """Reserve the existing handoff window before a real-image pre-finalizer call.

    Ordinary compatibility planning may still use the complete remaining
    budget.  Real-image plan and generate preparation calls are different: the
    runtime will not send a provider operation until the remote Brain signs
    the canonical prompt, so either pre-finalizer call must not consume the
    only bounded window in which that sign-off can complete.
    """

    if str(getattr(request, "stage", "") or "").strip() not in {"plan", "generate"}:
        return 0.0
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    policy = getattr(request, "template_capability_policy", None)
    requires_remote_brain = bool(
        metadata.get("require_real_images")
        or metadata.get("real_image_generation")
        or getattr(policy, "requires_remote_creative_brain", False)
    )
    return float(BRAIN_EXECUTION_BUDGET_HANDOFF_SECONDS) if requires_remote_brain else 0.0


def _call_with_timeout(
    callable_obj: Any,
    *,
    timeout_seconds: float,
    trace: dict[str, Any] | None = None,
    maximum_deadline: float | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    started = time.perf_counter()
    timeout_seconds = max(0.1, float(timeout_seconds))
    cancellation = _TransportCancellation()
    hard_deadline = started + timeout_seconds
    progress_grace_seconds = min(_STREAM_PROGRESS_GRACE_SECONDS, timeout_seconds)
    progress_grace_deadline = hard_deadline + progress_grace_seconds
    execution_budget = _ACTIVE_EXECUTION_BUDGET.get()
    if maximum_deadline is None:
        maximum_deadline = (
            execution_budget.deadline
            if execution_budget is not None
            else progress_grace_deadline
        )
    elif execution_budget is not None:
        # The caller may provide a narrower stage ceiling (for example, the
        # planning window before a canonical-finalizer reserve).  Never allow
        # that ceiling to escape the shared logical deadline.
        maximum_deadline = min(float(maximum_deadline), execution_budget.deadline)

    def runner() -> None:
        cancellation_token = _ACTIVE_TRANSPORT_CANCELLATION.set(cancellation)
        try:
            _mark_transport_event("provider_runner_entered")
            result["value"] = callable_obj()
        except BaseException as exc:  # pragma: no cover - re-raised in caller thread
            result["error"] = exc
        finally:
            _ACTIVE_TRANSPORT_CANCELLATION.reset(cancellation_token)

    context = copy_context()
    thread = threading.Thread(target=lambda: context.run(runner), name="v3-llm-brain-provider", daemon=True)
    thread.start()
    observed_progress = 0
    deadline = min(hard_deadline, maximum_deadline)
    while thread.is_alive():
        now = time.perf_counter()
        remaining = deadline - now
        if remaining <= 0.0:
            current_progress = int((trace or {}).get("semantic_progress_event_count") or 0)
            if current_progress > observed_progress and current_progress and now < maximum_deadline:
                observed_progress = current_progress
                deadline = min(maximum_deadline, now + progress_grace_seconds)
                continue
            cancellation.cancel()
            # A transport that owns a closeable response should terminate
            # promptly. Keep the grace join short for an uncooperative SDK so
            # the caller still receives a deterministic terminal failure.
            thread.join(timeout=min(0.25, max(0.05, timeout_seconds * 0.1)))
            if trace is not None:
                trace["transport_cancel_requested"] = True
                trace["transport_worker_stopped"] = not thread.is_alive()
            raise _transport_timeout_from_trace(
                trace or {},
                timeout_seconds=timeout_seconds,
                elapsed_ms=int(round((time.perf_counter() - started) * 1000)),
            )
        thread.join(timeout=min(0.25, remaining))
        current_progress = int((trace or {}).get("semantic_progress_event_count") or 0)
        if current_progress > observed_progress:
            observed_progress = current_progress
            deadline = min(maximum_deadline, max(deadline, time.perf_counter() + progress_grace_seconds))
    if thread.is_alive():  # pragma: no cover - defensive loop invariant
        cancellation.cancel()
        raise _transport_timeout_from_trace(
            trace or {},
            timeout_seconds=timeout_seconds,
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
        "response_kind": "",
        "timeout_phase_hint": "",
        "request_call_entered": False,
        "request_acceptance": "not_started",
        "request_dispatched": False,
        "response_started": False,
        "first_content_observed": False,
        "reasoning_content_observed": False,
        "reasoning_chunk_count": 0,
        "complete_response_started": False,
        "complete_response_observed": False,
        "json_parse_started": False,
        "json_parse_completed": False,
        "progress_event_count": 0,
        "semantic_progress_event_count": 0,
        "protocol_fallback_attempted": False,
    }


def _mark_transport_event(event: str) -> None:
    trace = _ACTIVE_TRANSPORT_TRACE.get()
    if not isinstance(trace, dict):
        return
    normalized = str(event or "").strip().lower()
    trace["last_event"] = normalized
    if normalized in {"json_parse_started", "json_parse_completed"}:
        trace["response_started"] = True
        _set_transport_acceptance(trace, "dispatched")
    if normalized == "response_started":
        trace["response_started"] = True
        _set_transport_acceptance(trace, "dispatched")
    if normalized == "request_dispatched":
        trace["request_call_entered"] = True
        _set_transport_acceptance(trace, "dispatched")
        trace["response_started"] = bool(trace.get("response_started"))
    if normalized == "request_call_entered":
        trace["request_call_entered"] = True
    if normalized == "stream_response_call_entered":
        trace["response_kind"] = "stream"
        trace["request_call_entered"] = True
    if normalized == "complete_response_call_entered":
        trace["response_kind"] = "complete"
        trace["request_call_entered"] = True
    if normalized == "complete_response_started":
        trace["complete_response_started"] = True
    if normalized == "first_content_observed":
        trace["response_started"] = True
        _set_transport_acceptance(trace, "dispatched")
        trace["first_content_observed"] = True
    if normalized == "reasoning_content_observed":
        trace["response_started"] = True
        _set_transport_acceptance(trace, "dispatched")
        trace["reasoning_content_observed"] = True
        trace["reasoning_chunk_count"] = int(trace.get("reasoning_chunk_count") or 0) + 1
    if normalized == "complete_response_observed":
        trace["response_started"] = True
        _set_transport_acceptance(trace, "dispatched")
        trace["complete_response_observed"] = True
    if normalized == "protocol_fallback":
        trace["protocol_fallback_attempted"] = True
    if normalized == "json_parse_started":
        trace["json_parse_started"] = True
    if normalized == "json_parse_completed":
        trace["json_parse_started"] = True
        trace["json_parse_completed"] = True
    if normalized == "semantic_progress":
        trace["semantic_progress_event_count"] = int(
            trace.get("semantic_progress_event_count") or 0
        ) + 1
        trace["last_semantic_progress_at"] = time.perf_counter()
    if normalized in {"stream_chunk_observed", "stream_progress"}:
        trace["progress_event_count"] = int(trace.get("progress_event_count") or 0) + 1
        trace["last_progress_at"] = time.perf_counter()


_REQUEST_ACCEPTANCE_STATES = frozenset({"not_started", "dispatched", "unknown"})
_REQUEST_ACCEPTANCE_RANK = {"not_started": 0, "unknown": 1, "dispatched": 2}


def _set_transport_acceptance(trace: dict[str, Any], value: str) -> None:
    """Update acceptance monotonically across protocol fallback attempts."""

    normalized = str(value or "").strip().lower()
    if normalized not in _REQUEST_ACCEPTANCE_STATES:
        return
    current = str(trace.get("request_acceptance") or "not_started").strip().lower()
    if current not in _REQUEST_ACCEPTANCE_STATES:
        current = "not_started"
    if _REQUEST_ACCEPTANCE_RANK[normalized] < _REQUEST_ACCEPTANCE_RANK[current]:
        normalized = current
    trace["request_acceptance"] = normalized
    trace["request_dispatched"] = normalized == "dispatched"


def _safe_request_acceptance(
    value: Any,
    *,
    request_dispatched: bool = False,
    request_call_entered: bool = False,
    response_started: bool = False,
) -> str:
    """Normalize transport acceptance without treating call entry as proof."""

    normalized = str(value or "").strip().lower()
    if request_dispatched or response_started:
        return "dispatched"
    if request_call_entered and normalized in {"", "not_started"}:
        return "unknown"
    if normalized in _REQUEST_ACCEPTANCE_STATES:
        return normalized
    if request_call_entered:
        return "unknown"
    return "not_started"


def _aggregate_request_acceptance(receipts: list[dict[str, Any]]) -> str:
    """Prefer the strongest evidence across bounded attempts."""

    states = {
        _safe_request_acceptance(
            item.get("request_acceptance"),
            request_dispatched=bool(item.get("request_dispatched")),
            request_call_entered=bool(item.get("request_call_entered")),
            response_started=bool(item.get("response_started")),
        )
        for item in receipts
    }
    if "dispatched" in states:
        return "dispatched"
    if "unknown" in states:
        return "unknown"
    return "not_started"


def _safe_transport_trace_receipt(trace: dict[str, Any] | None) -> dict[str, Any]:
    """Return a closed failure trace with no provider-native payload data."""

    trace = trace if isinstance(trace, dict) else {}
    response_started = bool(
        trace.get("response_started")
        or trace.get("first_content_observed")
        or trace.get("complete_response_observed")
        or trace.get("json_parse_started")
        or trace.get("json_parse_completed")
    )
    request_acceptance = _safe_request_acceptance(
        trace.get("request_acceptance"),
        request_dispatched=bool(trace.get("request_dispatched")),
        request_call_entered=bool(trace.get("request_call_entered")),
        response_started=response_started,
    )
    return {
        "schema_version": "v3_brain_transport_attempt_v1",
        "stage": _safe_brain_stage(trace.get("stage")),
        "request_acceptance": request_acceptance,
        "request_dispatched": request_acceptance == "dispatched",
        "response_started": response_started,
        "first_content_observed": bool(trace.get("first_content_observed")),
        "complete_response_observed": bool(trace.get("complete_response_observed")),
        "json_parse_started": bool(trace.get("json_parse_started") or trace.get("json_parse_completed")),
        "json_parse_completed": bool(trace.get("json_parse_completed")),
        "json_recovery": bool(trace.get("json_recovery")),
        "protocol_fallback_attempted": bool(trace.get("protocol_fallback_attempted")),
    }


def _annotate_transport_failure(
    exc: BaseException,
    *,
    attempts: int,
    json_recovery_attempted: bool,
    transient_recovery_attempted: bool,
    stage: str | None = None,
) -> BaseException:
    """Attach bounded attempt facts to a provider exception for safe audit."""

    trace = getattr(exc, _TRANSPORT_TRACE_ATTR, None)
    receipt = _safe_transport_trace_receipt(trace if isinstance(trace, dict) else None)
    receipt.update(
        {
            "attempts": max(0, min(2, int(attempts))),
            "json_serialization_recovery_attempted": bool(json_recovery_attempted),
            "transient_recovery_attempted": bool(transient_recovery_attempted),
        }
    )
    if receipt.get("stage") == "unknown" and stage:
        receipt["stage"] = _safe_brain_stage(stage)
    setattr(exc, _TRANSPORT_FAILURE_RECEIPT_ATTR, receipt)
    return exc


def transport_failure_receipt(exc: BaseException) -> dict[str, Any]:
    """Aggregate closed attempt facts across one bounded exception chain."""

    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen and len(chain) < 8:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    # Keep both layers of evidence.  A budget guard may be the terminal
    # exception and carry an annotated receipt with ``request_dispatched``
    # false, while its cause is the prior transport attempt that did dispatch.
    # Dropping the cause trace would misclassify a real upstream call as a
    # local preflight failure.
    receipts: list[dict[str, Any]] = []
    for item in chain:
        annotated = getattr(item, _TRANSPORT_FAILURE_RECEIPT_ATTR, None)
        if isinstance(annotated, dict):
            receipts.append(annotated)
        trace = getattr(item, _TRANSPORT_TRACE_ATTR, None)
        if isinstance(trace, dict):
            receipts.append(_safe_transport_trace_receipt(trace))
    if not receipts:
        return {}
    stage = next(
        (
            str(item.get("stage") or "")
            for item in receipts
            if str(item.get("stage") or "").strip()
            and str(item.get("stage") or "").strip() in _SAFE_BRAIN_STAGES
            and str(item.get("stage") or "").strip() != "unknown"
        ),
        "unknown",
    )
    attempts = max(
        int(item.get("attempts") or 0)
        for item in receipts
        if isinstance(item.get("attempts"), int) and not isinstance(item.get("attempts"), bool)
    ) if any(
        isinstance(item.get("attempts"), int) and not isinstance(item.get("attempts"), bool)
        for item in receipts
    ) else 0
    return {
        "schema_version": "v3_brain_transport_attempt_v1",
        "stage": stage if stage in _SAFE_BRAIN_STAGES else "unknown",
        "attempts": max(0, min(2, attempts)),
        "request_acceptance": _aggregate_request_acceptance(receipts),
        "request_dispatched": _aggregate_request_acceptance(receipts) == "dispatched",
        "response_started": any(bool(item.get("response_started")) for item in receipts),
        "first_content_observed": any(bool(item.get("first_content_observed")) for item in receipts),
        "complete_response_observed": any(bool(item.get("complete_response_observed")) for item in receipts),
        "json_parse_started": any(bool(item.get("json_parse_started")) for item in receipts),
        "json_parse_completed": any(bool(item.get("json_parse_completed")) for item in receipts),
        "json_recovery": any(bool(item.get("json_recovery")) for item in receipts),
        "protocol_fallback_attempted": any(
            bool(item.get("protocol_fallback_attempted")) for item in receipts
        ),
        "json_serialization_recovery_attempted": any(
            bool(item.get("json_serialization_recovery_attempted")) for item in receipts
        ),
        "transient_recovery_attempted": any(
            bool(item.get("transient_recovery_attempted")) for item in receipts
        ),
    }


def _register_transport_close(resource: Any) -> tuple[_TransportCancellation, int] | None:
    cancellation = _ACTIVE_TRANSPORT_CANCELLATION.get()
    close = getattr(resource, "close", None)
    if cancellation is None or not callable(close):
        return None
    token = cancellation.register(close)
    return (cancellation, token) if token is not None else None


def _unregister_transport_close(registration: tuple[_TransportCancellation, int] | None) -> None:
    if registration is None:
        return
    cancellation, token = registration
    cancellation.unregister(token)


def _transport_timeout_from_trace(
    trace: dict[str, Any],
    *,
    timeout_seconds: float,
    elapsed_ms: int,
) -> BrainTransportTimeoutError:
    request_acceptance = _safe_request_acceptance(
        trace.get("request_acceptance"),
        request_dispatched=bool(trace.get("request_dispatched")),
        request_call_entered=bool(trace.get("request_call_entered")),
        response_started=bool(trace.get("response_started")),
    )
    phase = _transport_timeout_phase(trace)
    return BrainTransportTimeoutError(
        stage=_safe_brain_stage(trace.get("stage")),
        timeout_seconds=timeout_seconds,
        elapsed_ms=elapsed_ms,
        timeout_phase=phase,
        request_dispatched=request_acceptance == "dispatched",
        request_acceptance=request_acceptance,
        request_call_entered=bool(trace.get("request_call_entered")),
        response_started=bool(trace.get("response_started")),
        first_content_observed=bool(trace.get("first_content_observed")),
        complete_response_observed=bool(trace.get("complete_response_observed")),
        json_parse_started=bool(trace.get("json_parse_started")),
        json_parse_completed=bool(trace.get("json_parse_completed")),
    )


def _transport_timeout_phase(trace: dict[str, Any]) -> str:
    if bool(trace.get("json_parse_started")) and not bool(trace.get("json_parse_completed")):
        return "json_parse_timeout"
    hinted_phase = str(trace.get("timeout_phase_hint") or "").strip().lower()
    if hinted_phase in BRAIN_TRANSPORT_TIMEOUT_PHASES:
        return hinted_phase
    if bool(trace.get("first_content_observed")) or bool(trace.get("response_started")):
        return "read_timeout"
    if bool(trace.get("complete_response_started")) and not bool(trace.get("complete_response_observed")):
        return "complete_response_timeout"
    last_event = str(trace.get("last_event") or "").strip().lower()
    if last_event in {"client_constructing", "created"}:
        return "connect_timeout"
    if last_event == "request_dispatched":
        return "ttfb_timeout"
    return "unknown_transport_timeout"


def _safe_transport_timeout_phase(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in BRAIN_TRANSPORT_TIMEOUT_PHASES:
        return normalized
    return "unknown_transport_timeout"


def _is_unsupported_brain_protocol_error(error: BaseException) -> bool:
    """Recognize only gateway-level protocol absence, never general failure."""

    status = getattr(error, "status_code", None)
    if status is None:
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
    try:
        status = int(status)
    except (TypeError, ValueError):
        return False
    if status in {405, 426, 501}:
        return True
    if status != 404:
        return False
    # A 404 can mean either "this gateway has no Responses route" or "the
    # configured model/deployment does not exist". Only the former is safe to
    # negotiate to Chat Completions; switching protocols cannot repair a
    # missing model and would hide the real upstream failure.
    text_parts = [str(error or "")]
    response = getattr(error, "response", None)
    for candidate in (
        getattr(response, "text", None),
        getattr(response, "reason_phrase", None),
    ):
        if isinstance(candidate, str):
            text_parts.append(candidate)
    text = " ".join(text_parts).lower()
    if re.search(r"\b(?:model|deployment|engine)\b.{0,80}\b(?:not found|does not exist|不存在)\b", text):
        return False
    if re.search(r"\b(?:not found|does not exist)\b.{0,80}\b(?:model|deployment|engine)\b", text):
        return False
    if any(
        token in text
        for token in (
            "responses",
            "response route",
            "endpoint",
            "route",
            "method",
            "unsupported",
            "not implemented",
            "does not support",
        )
    ):
        return True
    # Some OpenAI-compatible gateways answer an unimplemented /responses route
    # with a bare ``404 Not Found`` and put the only useful evidence on the
    # request URL. Treat that exact route as protocol negotiation, while
    # keeping model/deployment 404s terminal above.
    request = getattr(error, "request", None) or getattr(response, "request", None)
    url = str(getattr(request, "url", "") or "").lower()
    return bool(re.search(r"/(?:v1/)?responses(?:[/?#]|$)", url))


def _exception_chain(error: BaseException) -> list[BaseException]:
    """Return a finite exception chain without retaining provider details."""

    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen and len(chain) < 8:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


def _is_transport_timeout_exception(error: BaseException) -> bool:
    """Recognize timeout types even when an SDK wraps their original cause."""

    for item in _exception_chain(error):
        module = str(item.__class__.__module__ or "").strip().lower()
        name = str(item.__class__.__name__ or "").strip().lower()
        if "timeout" in name and module.startswith(("httpx", "httpcore", "openai")):
            return True
    return False


def _mark_transport_dispatch_from_exception(error: BaseException) -> None:
    """Record acceptance evidence without guessing from SDK call entry."""

    trace = _ACTIVE_TRANSPORT_TRACE.get()
    if not isinstance(trace, dict):
        return
    for item in _exception_chain(error):
        status = getattr(item, "status_code", None)
        if status is None:
            response = getattr(item, "response", None)
            status = getattr(response, "status_code", None)
        if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599:
            trace["request_call_entered"] = True
            _set_transport_acceptance(trace, "dispatched")
            return
        module = str(item.__class__.__module__ or "").strip().lower()
        name = str(item.__class__.__name__ or "").strip().lower()
        if not module.startswith(("httpx", "httpcore", "openai")):
            continue
        if "timeout" in name or any(
            token in name
            for token in (
                "connecterror",
                "connectionerror",
                "networkerror",
                "readerror",
                "writeerror",
                "protocolerror",
            )
        ):
            if bool(trace.get("response_started")) or bool(trace.get("first_content_observed")):
                _set_transport_acceptance(trace, "dispatched")
            elif bool(trace.get("request_call_entered")):
                # The SDK call was entered, but a timeout/connection error
                # before a response does not tell us whether request bytes
                # were accepted by the upstream.  Keep this distinct from
                # both a proven dispatch and a pre-call failure.
                _set_transport_acceptance(trace, "unknown")
            else:
                _set_transport_acceptance(trace, "not_started")
            if "connect" in name:
                trace["timeout_phase_hint"] = "connect_timeout"
            elif "read" in name:
                trace["timeout_phase_hint"] = (
                    "complete_response_timeout"
                    if trace.get("response_kind") == "complete"
                    else "read_timeout"
                )
            elif trace.get("response_kind") == "complete":
                trace["timeout_phase_hint"] = "complete_response_timeout"
            return


_RETRYABLE_TRANSIENT_HTTP_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

_RETRYABLE_TRANSIENT_PROVIDER_MESSAGE_PATTERNS = (
    re.compile(
        r"\b(?:http|status|error|upstream)\s*(?:code|status)?\s*[:=]?\s*"
        r"(?:408|409|425|429|500|502|503|504)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:bad gateway|gateway timeout|service unavailable|temporarily unavailable|"
        r"connection reset|connection aborted|remote protocol error)\b",
        flags=re.IGNORECASE,
    ),
)


def _is_retryable_transient_provider_error(error: BaseException) -> bool:
    """Allow one retry only for known transient transport/upstream failures."""

    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen and len(chain) < 8:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__

    for item in chain:
        if isinstance(item, (BrainExecutionBudgetExceeded, BrainPromptContractInvalid, BrainInvalidJsonResponse)):
            return False
        if isinstance(item, BrainTransportTimeoutError):
            return True
        if _is_transport_timeout_exception(item):
            return True
        for candidate in (
            getattr(item, "status_code", None),
            getattr(getattr(item, "response", None), "status_code", None),
        ):
            if isinstance(candidate, int) and not isinstance(candidate, bool):
                return candidate in _RETRYABLE_TRANSIENT_HTTP_STATUS_CODES
        module = str(item.__class__.__module__ or "").lower()
        name = str(item.__class__.__name__ or "").lower()
        if module.startswith(("httpx", "httpcore", "openai")) and any(
            token in name
            for token in ("connecterror", "connectionerror", "networkerror", "readerror", "writeerror", "protocolerror")
        ):
            return True
        message = str(item or "")
        if any(pattern.search(message) for pattern in _RETRYABLE_TRANSIENT_PROVIDER_MESSAGE_PATTERNS):
            return True
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

    def consume_event(data: str) -> None:
        """Consume one complete SSE data event without mixing reasoning in."""

        nonlocal done
        if data.strip() == "[DONE]":
            done = True
            _mark_transport_event("complete_response_observed")
            record_stage_event("brain_provider", "stream_complete_response_observed")
            return
        try:
            item = json.loads(data)
        except json.JSONDecodeError:
            return
        choices = item.get("choices") if isinstance(item, dict) else None
        choice = choices[0] if isinstance(choices, list) and choices else None
        finish_reason = (
            str(choice.get("finish_reason") or "").strip().lower()
            if isinstance(choice, dict)
            else ""
        )
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
        reasoning_content = _stream_delta_text(delta, "reasoning_content")
        if reasoning_content:
            trace = _ACTIVE_TRANSPORT_TRACE.get()
            first_reasoning_observed = not bool(
                isinstance(trace, dict) and trace.get("reasoning_content_observed")
            )
            _mark_transport_event("reasoning_content_observed")
            _mark_transport_event("semantic_progress")
            if first_reasoning_observed:
                record_stage_event(
                    "brain_provider",
                    "stream_reasoning_content_observed",
                    stage=str(trace.get("stage") or "unknown") if isinstance(trace, dict) else None,
                    extra={"reasoning_content_observed": True},
                )
        content = _stream_delta_text(delta, "content")
        if content:
            _mark_transport_event("first_content_observed")
            _mark_transport_event("semantic_progress")
            record_stage_event("brain_provider", "stream_first_content_observed")
            chunks.append(str(content))

    def consume_if_complete(data: str) -> bool:
        """Parse a line-buffered event only after it forms valid JSON."""

        try:
            json.loads(data)
        except json.JSONDecodeError:
            return False
        consume_event(data)
        return True

    _mark_transport_event("client_constructing")
    record_stage_event("brain_provider", "stream_client_constructing")
    with httpx.Client(timeout=timeout) as client:
        client_registration = _register_transport_close(client)
        try:
            _mark_transport_event("client_constructed")
            record_stage_event("brain_provider", "stream_client_constructed")
            _mark_transport_event("stream_response_call_entered")
            _mark_transport_event("request_call_entered")
            record_stage_event("brain_provider", "stream_request_call_entered")
            with client.stream("POST", url, headers=headers, json=payload) as response:
                _mark_transport_event("request_dispatched")
                record_stage_event("brain_provider", "stream_request_dispatched")
                response_registration = _register_transport_close(response)
                try:
                    _mark_transport_event("response_started")
                    record_stage_event("brain_provider", "stream_response_started")
                    response.raise_for_status()
                    event_data: list[str] = []
                    for raw_line in response.iter_lines():
                        line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else str(raw_line or "")
                        line = line.rstrip("\r")
                        _mark_transport_event("stream_chunk_observed")
                        if not line.strip():
                            if event_data:
                                data = "\n".join(event_data)
                                event_data.clear()
                                consume_if_complete(data)
                            if done:
                                break
                            continue
                        if line.lstrip().startswith(":"):
                            # SSE comment/heartbeat; it is transport progress,
                            # never semantic response content.
                            continue
                        if line.startswith("data:"):
                            data = line[5:].lstrip()
                            if data.strip() == "[DONE]":
                                if event_data:
                                    pending = "\n".join(event_data)
                                    event_data.clear()
                                    consume_if_complete(pending)
                                consume_event("[DONE]")
                                break
                            # A few lightweight gateways omit the SSE blank
                            # delimiter between complete single-line events.
                            # Treat a complete pending line as that explicit
                            # gateway boundary only when the next data line
                            # arrives.  Never consume the first line eagerly:
                            # a real multi-line event owns its buffer until a
                            # blank line, DONE, or EOF flushes it.
                            if event_data and len(event_data) == 1 and consume_if_complete(event_data[0]):
                                event_data.clear()
                            event_data.append(data)
                            continue
                        # Keep compatibility with gateways that emit one JSON
                        # object per line without the SSE data prefix.
                        if line.strip() == "[DONE]":
                            if event_data:
                                pending = "\n".join(event_data)
                                event_data.clear()
                                consume_if_complete(pending)
                            consume_event("[DONE]")
                            break
                        if event_data and len(event_data) == 1 and consume_if_complete(event_data[0]):
                            event_data.clear()
                        if not event_data and consume_if_complete(line.strip()):
                            if done:
                                break
                    if event_data and not done:
                        consume_if_complete("\n".join(event_data))
                finally:
                    _unregister_transport_close(response_registration)
        finally:
            _unregister_transport_close(client_registration)
    if not done:
        raise BrainInvalidJsonResponse(
            "remote brain stream ended before the complete JSON response marker",
            json_failure_kind="missing_complete_marker",
            json_parse_started=False,
            json_parse_completed=False,
        )
    return "".join(chunks)


def _stream_delta_text(delta: Any, key: str) -> str:
    """Read text from string or structured OpenAI-compatible delta parts."""

    if not isinstance(delta, dict):
        return ""
    value = delta.get(key)
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for item in value:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "".join(parts)


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
        return max(512, min(_BRAIN_OUTPUT_TOKEN_MAX, int(os.getenv(name, str(default)))))
    except ValueError:
        return max(512, min(_BRAIN_OUTPUT_TOKEN_MAX, int(default)))


_SUPPORTED_REASONING_EFFORTS = frozenset({"low", "medium", "high", "max", "xhigh"})


def _configured_reasoning_effort(provider: str) -> str | None:
    """Return only an explicitly configured, supported effort control."""

    configured = _env("V3_LLM_BRAIN_REASONING_EFFORT")
    if configured is None:
        return None
    normalized = configured.strip().lower()
    if normalized in {"", "default", "provider"}:
        return None
    return normalized if normalized in _SUPPORTED_REASONING_EFFORTS else None


def _loads_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        raise BrainInvalidJsonResponse("remote brain returned empty JSON output", json_failure_kind="empty_json")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        # Do not salvage a prose prefix/suffix locally.  The remote Brain owns
        # the JSON serialization contract; a bounded semantic re-answer is the
        # only permitted recovery path.
        raise BrainInvalidJsonResponse(
            "remote brain returned malformed JSON output",
            json_failure_kind="malformed_json",
        ) from error
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
    transient_recovery_attempted: bool = False,
    execution_budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach only safe transport provenance for adapter/job audit projection."""

    result = dict(payload)
    attempt_receipt = result.pop(_TRANSPORT_ATTEMPT_RECEIPT_KEY, None)
    receipt = {
        "attempts": attempts,
        "json_serialization_recovery_attempted": json_recovery_attempted,
        "json_serialization_recovery_succeeded": json_recovery_attempted,
        **({"execution_budget": dict(execution_budget)} if execution_budget else {}),
    }
    if isinstance(attempt_receipt, dict):
        receipt["transport_attempt"] = _safe_transport_trace_receipt(attempt_receipt)
    if transient_recovery_attempted:
        receipt["transient_recovery_attempted"] = True
        receipt["transient_recovery_succeeded"] = True
    result[_TRANSPORT_RECEIPT_KEY] = receipt
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
    transport_attempt = raw.get("transport_attempt")
    if transport_attempt is not None:
        if not isinstance(transport_attempt, dict):
            return {}
        transport_attempt = _safe_transport_trace_receipt(transport_attempt)
        if transport_attempt.get("stage") == "unknown":
            return {}
        receipt["transport_attempt"] = transport_attempt
        receipt.update(
            {
                "request_acceptance": transport_attempt["request_acceptance"],
                "request_dispatched": transport_attempt["request_dispatched"],
                "response_started": transport_attempt["response_started"],
                "first_content_observed": transport_attempt["first_content_observed"],
                "complete_response_observed": transport_attempt["complete_response_observed"],
                "json_parse_started": transport_attempt["json_parse_started"],
                "json_parse_completed": transport_attempt["json_parse_completed"],
            }
        )
    transient_attempted = raw.get("transient_recovery_attempted")
    transient_succeeded = raw.get("transient_recovery_succeeded")
    if transient_attempted is not None or transient_succeeded is not None:
        if transient_attempted is not True or transient_succeeded is not True:
            return {}
        receipt["transient_recovery_attempted"] = True
        receipt["transient_recovery_succeeded"] = True
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
