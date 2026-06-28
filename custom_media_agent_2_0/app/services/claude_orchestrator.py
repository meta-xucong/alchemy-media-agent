from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import hashlib
import inspect
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.config import settings
from app.repositories.memory import utc_now
from app.schemas import (
    CaseRetrievalPlan,
    CreateCreativeRunRequest,
    CreativeOrchestratorDecision,
    OrchestratorInvocationRecord,
    OrchestratorStatusResponse,
    PromptCase,
    PromptCaseSummary,
    PromptDirectives,
    StageCommand,
)
from app.services.ids import new_id
from app.services.asset_binding import build_asset_context
from app.services.uploaded_assets import get_uploaded_asset
from app.services.visual_signals import build_case_visual_signals
from app.services.visual_grammar_lock import build_visual_grammar_contract


_RECENT_INVOCATIONS: list[OrchestratorInvocationRecord] = []
_MAX_RECENT_INVOCATIONS = 30
_NON_RETRYABLE_CLAUDE_FAILURES = {"claude_output_token_limit", "claude_timeout"}
_CHECKPOINT_RETRYABLE_CLAUDE_FAILURES = {
    "claude_output_token_limit",
    "claude_soft_timeout",
    "claude_timeout",
    "claude_structured_output_retries_exhausted",
    "claude_policy_refusal",
    "claude_api_error",
    "claude_reasoning_not_supported",
    "kimi_context_canceled",
    "kimi_sub2api_502",
    "kimi_no_available_accounts",
    "kimi_upstream_error",
    "upstream_context_canceled",
}
_CLAUDE_CODE_IMMEDIATE_MODEL_FALLBACK_FAILURES = {
    "claude_policy_refusal",
    "claude_api_error",
    "claude_reasoning_not_supported",
    "kimi_context_canceled",
    "kimi_sub2api_502",
    "kimi_no_available_accounts",
    "kimi_upstream_error",
    "upstream_context_canceled",
}
_CLAUDE_DECISION_CACHE_SCHEMA = "claude_decision_v10_template_anchor_skeleton_lock"
_CLAUDE_INLINE_JSON_CHAR_BUDGET = 1500
_CLAUDE_INLINE_FINAL_PROMPT_CHAR_BUDGET = 1100
_CLAUDE_INLINE_NEGATIVE_PROMPT_CHAR_BUDGET = 240
_CLAUDE_INLINE_RATIONALE_CHAR_BUDGET = 140
_CLAUDE_CHECKPOINT_MAX_OUTPUT_TOKENS = 4096
_INTERNAL_GENERATION_KEYS = {
    "prompt",
    "negative_prompt",
    "revision_source",
    "disable_semantic_cache",
    "prompt_transform_mode",
    "prompt_transform_profile",
}
ClaudeProgressCallback = Callable[[dict[str, Any]], None]


_CLAUDE_STAGE_LABELS = {
    "intent": "意图与素材理解",
    "visual_strategy": "视觉语法锁",
    "generation_decision": "最终提示词压缩",
    "generation_decision_recovery": "压缩恢复",
    "single_stage_decision": "单阶段 Claude 决策",
}
_MULTIMODAL_SOURCE_ROLES = {"subject_reference", "logo_reference", "face_reference", "background_reference"}
_MULTIMODAL_FUSION_MODES = {
    "subject_identity",
    "template_slot_replacement",
    "logo_product_surface",
    "logo_canvas_brand_mark",
    "logo_template_slot",
    "composite_content_source",
    "face_identity",
    "background_identity",
}
_MULTIMODAL_REQUIRED_SOURCE_REASONS = {
    "provider_input_images_required",
    "hard_reference_input_image",
    "asset_binding_requires_visual_understanding",
    "prompt_requests_uploaded_image_understanding",
}


@dataclass(frozen=True)
class ClaudeSourceSelection:
    provider: str
    model: str
    stage_kwargs: dict[str, Any]
    reason: str
    multimodal_requested: bool = False


class ClaudeInvocationError(RuntimeError):
    pass


CLAUDE_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "mode": {"type": "string", "enum": ["template_customize", "smart_enhance", "revision", "batch"]},
        "selected_case_ids": {"type": "array", "items": {"type": "string"}},
        "case_retrieval_plan": {"type": "object"},
        "final_prompt": {"type": "string"},
        "negative_prompt": {"type": "string"},
        "provider_parameters": {"type": "object"},
        "prompt_rationale": {"type": "string"},
        "prompt_directives": {"type": "object"},
        "stage_commands": {"type": "array", "items": {"type": "object"}},
        "generation_directives": {"type": "object"},
        "quality_gates": {"type": "object"},
        "confidence": {"type": "number"},
    },
    "required": ["mode", "selected_case_ids", "final_prompt"],
}

CLAUDE_INLINE_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "mode": {"type": "string", "enum": ["template_customize", "smart_enhance", "revision", "batch"]},
        "selected_case_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "final_prompt": {"type": "string", "minLength": 30, "maxLength": _CLAUDE_INLINE_FINAL_PROMPT_CHAR_BUDGET},
        "negative_prompt": {"type": "string", "maxLength": _CLAUDE_INLINE_NEGATIVE_PROMPT_CHAR_BUDGET},
        "provider_parameters": {"type": "object", "additionalProperties": True},
        "prompt_rationale": {"type": "string", "maxLength": _CLAUDE_INLINE_RATIONALE_CHAR_BUDGET},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "mode",
        "selected_case_ids",
        "final_prompt",
        "negative_prompt",
        "provider_parameters",
        "prompt_rationale",
        "confidence",
    ],
}

CLAUDE_INTENT_CHECKPOINT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "stage": {"type": "string", "enum": ["intent"]},
        "mode": {"type": "string", "enum": ["template_customize", "smart_enhance", "revision", "batch"]},
        "primary_subject": {"type": "string", "maxLength": 180},
        "scene_goal": {"type": "string", "maxLength": 260},
        "must_keep": {"type": "array", "items": {"type": "string", "maxLength": 100}, "maxItems": 6},
        "must_avoid": {"type": "array", "items": {"type": "string", "maxLength": 80}, "maxItems": 6},
        "asset_requirements": {"type": "array", "items": {"type": "object"}, "maxItems": 5},
        "risk_notes": {"type": "array", "items": {"type": "string", "maxLength": 80}, "maxItems": 4},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["stage", "mode", "primary_subject", "scene_goal", "must_keep", "must_avoid", "confidence"],
}

CLAUDE_VISUAL_STRATEGY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "stage": {"type": "string", "enum": ["visual_strategy"]},
        "selected_case_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "composition": {"type": "string", "maxLength": 260},
        "lighting": {"type": "string", "maxLength": 180},
        "palette": {"type": "string", "maxLength": 180},
        "spatial_hierarchy": {"type": "string", "maxLength": 220},
        "template_lock_notes": {"type": "string", "maxLength": 220},
        "asset_fusion_notes": {"type": "string", "maxLength": 220},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "stage",
        "selected_case_ids",
        "composition",
        "lighting",
        "palette",
        "spatial_hierarchy",
        "confidence",
    ],
}


def orchestrate_creative_request(
    *,
    request: CreateCreativeRunRequest,
    fallback_mode: str,
    fallback_retrieval_plan: CaseRetrievalPlan,
    candidate_cases: list[PromptCaseSummary],
    candidate_case_details: list[PromptCase] | None = None,
    progress_callback: ClaudeProgressCallback | None = None,
) -> CreativeOrchestratorDecision:
    started = time.perf_counter()
    fallback = _fallback_decision(
        request=request,
        fallback_mode=fallback_mode,
        fallback_retrieval_plan=fallback_retrieval_plan,
        candidate_cases=candidate_cases,
        reason=None if not settings.claude_orchestrator_enabled else "claude_orchestrator_not_used",
    )
    cache_key = _cache_key(
        request=request,
        fallback_mode=fallback_mode,
        fallback_retrieval_plan=fallback_retrieval_plan,
        candidate_cases=candidate_cases,
    )
    cache_metadata = _cache_metadata(
        request=request,
        fallback_mode=fallback_mode,
        candidate_cases=candidate_cases,
    )
    cache_read_disabled = _disable_claude_cache_read(request.output)
    workspace_id = fallback.decision_id
    if not settings.claude_orchestrator_enabled:
        decision = fallback.model_copy(
            update={
                "invocation_status": "disabled",
                "latency_ms": _elapsed_ms(started),
                "attempts": 0,
                "cache_key": cache_key,
                "workspace_id": workspace_id,
            }
        )
        _record_invocation(decision)
        return decision

    cached_raw_decision = None if cache_read_disabled else _read_cached_decision(cache_key)
    if cached_raw_decision:
        decision = _normalize_decision(
            cached_raw_decision,
            fallback=fallback,
            fallback_retrieval_plan=fallback_retrieval_plan,
            candidate_cases=candidate_cases,
        ).model_copy(
            update={
                "invocation_status": "cache_hit",
                "latency_ms": _elapsed_ms(started),
                "attempts": 0,
                "cache_hit": True,
                "cache_key": cache_key,
                "workspace_id": workspace_id,
            }
        )
        _record_invocation(decision)
        return decision

    semantic_cached = None if cache_read_disabled else _read_semantic_cached_decision(cache_metadata)
    if semantic_cached:
        cached_key, cached_raw_decision, score = semantic_cached
        decision = _normalize_decision(
            cached_raw_decision,
            fallback=fallback,
            fallback_retrieval_plan=fallback_retrieval_plan,
            candidate_cases=candidate_cases,
        ).model_copy(
            update={
                "invocation_status": "semantic_cache_hit",
                "latency_ms": _elapsed_ms(started),
                "attempts": 0,
                "cache_hit": True,
                "cache_key": f"{cache_key}:semantic:{cached_key}:{score:.2f}",
                "workspace_id": workspace_id,
            }
        )
        _record_invocation(decision)
        return decision

    if settings.claude_checkpoint_orchestrator_enabled:
        raw_decision = None
        errors: list[str] = []
        used_attempts = 0
        try:
            raw_decision, checkpoint_meta = _invoke_claude_checkpoint_mode(
                request=request,
                fallback=fallback,
                candidate_cases=candidate_cases,
                candidate_case_details=candidate_case_details or [],
                progress_callback=progress_callback,
            )
            used_attempts = int(checkpoint_meta.get("attempts") or 0)
        except ClaudeInvocationError as exc:
            errors.append(f"claude_checkpoint_error:{exc}")
        except Exception as exc:
            errors.append(f"claude_checkpoint_error:{exc!r}")

        if raw_decision:
            _write_cached_decision(cache_key, raw_decision, metadata=cache_metadata)
            decision = _normalize_decision(
                raw_decision,
                fallback=fallback,
                fallback_retrieval_plan=fallback_retrieval_plan,
                candidate_cases=candidate_cases,
            ).model_copy(
                update={
                    "invocation_status": "checkpoint_success",
                    "latency_ms": _elapsed_ms(started),
                    "attempts": used_attempts,
                    "cache_hit": False,
                    "cache_key": cache_key,
                    "workspace_id": workspace_id,
                    "claude_stage_trace": checkpoint_meta.get("trace") or [],
                }
            )
            _record_invocation(decision)
            return decision

        decision = fallback.model_copy(
            update={
                "fallback_reason": errors[-1] if errors else "claude_checkpoint_missing_decision",
                "invocation_status": "checkpoint_fallback",
                "latency_ms": _elapsed_ms(started),
                "attempts": used_attempts,
                "cache_key": cache_key,
                "workspace_id": workspace_id,
                "claude_stage_trace": checkpoint_meta.get("trace") if "checkpoint_meta" in locals() else [],
            }
        )
        _record_invocation(decision)
        return decision

    attempts = max(1, settings.claude_orchestrator_max_attempts)
    errors: list[str] = []
    raw_decision: dict[str, Any] | None = None
    used_attempts = 0
    for attempt in range(1, attempts + 1):
        used_attempts = attempt
        try:
            raw_decision = _invoke_claude_file_mode_compat(
                request=request,
                fallback=fallback,
                candidate_cases=candidate_cases,
                candidate_case_details=candidate_case_details or [],
                progress_callback=progress_callback,
            )
            if raw_decision:
                break
            errors.append("claude_missing_decision")
        except ClaudeInvocationError as exc:
            failure_code = str(exc)
            errors.append(f"claude_invoke_error:{failure_code}")
            if failure_code in _NON_RETRYABLE_CLAUDE_FAILURES:
                break
        except Exception as exc:
            errors.append(f"claude_invoke_error:{exc!r}")
        if attempt < attempts and settings.claude_orchestrator_retry_delay_seconds > 0:
            time.sleep(settings.claude_orchestrator_retry_delay_seconds)

    if not raw_decision:
        reason = errors[-1] if errors else "claude_missing_decision"
        decision = fallback.model_copy(
            update={
                "fallback_reason": reason,
                "invocation_status": "fallback",
                "latency_ms": _elapsed_ms(started),
                "attempts": used_attempts,
                "cache_key": cache_key,
                "workspace_id": workspace_id,
            }
        )
        _record_invocation(decision)
        return decision

    _write_cached_decision(cache_key, raw_decision, metadata=cache_metadata)
    decision = _normalize_decision(
        raw_decision,
        fallback=fallback,
        fallback_retrieval_plan=fallback_retrieval_plan,
        candidate_cases=candidate_cases,
    ).model_copy(
        update={
            "invocation_status": "success",
            "latency_ms": _elapsed_ms(started),
            "attempts": used_attempts,
            "cache_hit": False,
            "cache_key": cache_key,
            "workspace_id": workspace_id,
        }
    )
    _record_invocation(decision)
    return decision


def _fallback_decision(
    *,
    request: CreateCreativeRunRequest,
    fallback_mode: str,
    fallback_retrieval_plan: CaseRetrievalPlan,
    candidate_cases: list[PromptCaseSummary],
    reason: str | None,
) -> CreativeOrchestratorDecision:
    selected_case_ids: list[str] = []
    if request.template_case_id:
        selected_case_ids.append(request.template_case_id)
    else:
        selected_case_ids.extend(item.case_id for item in candidate_cases[: fallback_retrieval_plan.limit])
    selected_case_ids = _dedupe(selected_case_ids)[: fallback_retrieval_plan.limit]
    return CreativeOrchestratorDecision(
        decision_id=new_id("orc"),
        provider="deterministic-fallback",
        mode=fallback_mode,  # type: ignore[arg-type]
        selected_case_ids=selected_case_ids,
        case_retrieval_plan=fallback_retrieval_plan,
        prompt_directives=PromptDirectives(
            visual_strategy="Use the local provider index as recall evidence, then compose a safe custom prompt.",
            case_selection_rationale="Claude Code orchestration is disabled or unavailable; deterministic recall selected the cases.",
        ),
        stage_commands=[
            StageCommand(stage="retrieve_cases", reason="Recall candidate prompt cases from local provider index."),
            StageCommand(stage="compose_prompt", reason="Compose a new client-specific prompt from reusable case principles."),
            StageCommand(stage="safety_check", reason="Apply policy and commercial-safety checks before generation."),
            StageCommand(stage="generate", reason="Call the configured image provider after the prompt plan is approved."),
        ],
        generation_directives=dict(request.output),
        quality_gates={
            "no_raw_case_image_copying": True,
            "no_unlicensed_logo_copying": True,
            "prefer_commercial_composition": True,
        },
        confidence=0.55,
        fallback_reason=reason,
        created_at=utc_now(),
    )


def get_orchestrator_status() -> OrchestratorStatusResponse:
    cache = _read_cache_store()
    recent = list(_RECENT_INVOCATIONS)
    success_records = [
        item for item in recent if item.status in {"success", "checkpoint_success", "cache_hit", "semantic_cache_hit"}
    ]
    failure_records = [item for item in recent if item.status in {"fallback", "checkpoint_fallback", "error"}]
    latency_values = [item.latency_ms for item in recent if isinstance(item.latency_ms, int)]
    return OrchestratorStatusResponse(
        enabled=settings.claude_orchestrator_enabled,
        cli=settings.claude_orchestrator_cli,
        model=settings.claude_orchestrator_model,
        multimodal_model=settings.claude_orchestrator_multimodal_model,
        tools=settings.claude_orchestrator_tools,
        fallback_model=settings.claude_orchestrator_fallback_model,
        cache_enabled=settings.claude_orchestrator_cache_enabled,
        cache_entries=len(cache),
        max_attempts=settings.claude_orchestrator_max_attempts,
        timeout_seconds=settings.claude_orchestrator_timeout_seconds,
        max_output_tokens=settings.claude_orchestrator_max_output_tokens,
        checkpoint_enabled=settings.claude_checkpoint_orchestrator_enabled,
        fallback_models=_claude_code_model_fallback_queue(),
        fallback_base_url_configured=bool(settings.claude_orchestrator_fallback_base_url),
        fallback_auth_token_configured=bool(settings.claude_orchestrator_fallback_auth_token),
        recent_invocations=recent[:10],
        last_success_at=success_records[0].created_at if success_records else None,
        last_failure_at=failure_records[0].created_at if failure_records else None,
        average_latency_ms=int(sum(latency_values) / len(latency_values)) if latency_values else None,
    )


def reset_orchestrator_observability() -> None:
    _RECENT_INVOCATIONS.clear()


def _invoke_claude_checkpoint_mode(
    *,
    request: CreateCreativeRunRequest,
    fallback: CreativeOrchestratorDecision,
    candidate_cases: list[PromptCaseSummary],
    candidate_case_details: list[PromptCase],
    progress_callback: ClaudeProgressCallback | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    command = _resolve_claude_command()
    if not command:
        return None, {"attempts": 0, "trace": []}
    workspace = _build_workspace(
        request=request,
        fallback=fallback,
        candidate_cases=candidate_cases,
        candidate_case_details=candidate_case_details,
    )
    trace: list[dict[str, Any]] = []
    attempts = 0

    intent, attempt_count = _invoke_checkpoint_stage_with_micro(
        command=command,
        workspace=workspace,
        stage_name="intent",
        schema=CLAUDE_INTENT_CHECKPOINT_SCHEMA,
        prompt=_build_checkpoint_stage_prompt(workspace, stage_name="intent_micro"),
        micro_prompt=_build_checkpoint_stage_prompt(workspace, stage_name="intent_micro"),
        ultra_micro_prompt=_build_checkpoint_stage_prompt(workspace, stage_name="intent_ultra_micro"),
        trace=trace,
        progress_callback=progress_callback,
    )
    attempts += attempt_count
    if not intent:
        _write_json(workspace / "orchestration_trace.json", {"stages": trace, "final_status": "checkpoint_failed"})
        return None, {"attempts": attempts, "trace": trace}
    _write_json(workspace / "stage_01_intent_checkpoint.json", intent)

    visual_first_stage = "visual_strategy_micro" if request.template_case_id else "visual_strategy_ultra_micro"
    visual, attempt_count = _invoke_checkpoint_stage_with_micro(
        command=command,
        workspace=workspace,
        stage_name="visual_strategy",
        schema=CLAUDE_VISUAL_STRATEGY_SCHEMA,
        prompt=_build_checkpoint_stage_prompt(workspace, stage_name=visual_first_stage, checkpoints={"intent": intent}),
        micro_prompt=_build_checkpoint_stage_prompt(workspace, stage_name="visual_strategy_micro", checkpoints={"intent": intent}),
        ultra_micro_prompt=_build_checkpoint_stage_prompt(
            workspace,
            stage_name="visual_strategy_ultra_micro",
            checkpoints={"intent": intent},
        ),
        trace=trace,
        progress_callback=progress_callback,
    )
    attempts += attempt_count
    if not visual:
        decision, attempt_count = _invoke_checkpoint_stage_with_micro(
            command=command,
            workspace=workspace,
            stage_name="generation_decision_recovery",
            schema=CLAUDE_INLINE_DECISION_SCHEMA,
            prompt=_build_checkpoint_stage_prompt(
                workspace,
                stage_name="generation_decision_recovery",
                checkpoints={"intent": intent},
            ),
            micro_prompt=_build_checkpoint_stage_prompt(
                workspace,
                stage_name="generation_decision_recovery_ultra_micro",
                checkpoints={"intent": intent},
            ),
            ultra_micro_prompt=_build_checkpoint_stage_prompt(
                workspace,
                stage_name="generation_decision_recovery_ultra_micro",
                checkpoints={"intent": intent},
            ),
            trace=trace,
            progress_callback=progress_callback,
        )
        attempts += attempt_count
        visual = _visual_strategy_from_partial(intent=intent, raw_decision=decision or {}, fallback=fallback)
        compressed = _compress_checkpoint_decision(
            decision or {},
            intent=intent,
            visual_strategy=visual,
            fallback=fallback,
        )
        _write_json(workspace / "stage_02_visual_strategy_checkpoint.json", visual)
        if decision:
            _write_json(workspace / "stage_03_generation_decision.json", decision)
        _write_json(workspace / "compressed_decision.json", compressed)
        _write_json(
            workspace / "orchestration_trace.json",
            {
                "stages": trace,
                "final_status": "recovered_from_intent_checkpoint",
                "recovery_reason": "visual_strategy_checkpoint_unavailable",
            },
        )
        return compressed, {"attempts": attempts, "trace": trace, "recovery": "intent_checkpoint_compaction"}
    _write_json(workspace / "stage_02_visual_strategy_checkpoint.json", visual)

    decision, attempt_count = _invoke_checkpoint_stage_with_micro(
        command=command,
        workspace=workspace,
        stage_name="generation_decision",
        schema=CLAUDE_INLINE_DECISION_SCHEMA,
        prompt=_build_checkpoint_stage_prompt(
            workspace,
            stage_name="generation_decision_micro",
            checkpoints={"intent": intent, "visual_strategy": visual},
        ),
        micro_prompt=_build_checkpoint_stage_prompt(
            workspace,
            stage_name="generation_decision_micro",
            checkpoints={"intent": intent, "visual_strategy": visual},
        ),
        ultra_micro_prompt=_build_checkpoint_stage_prompt(
            workspace,
            stage_name="generation_decision_ultra_micro",
            checkpoints={"intent": intent, "visual_strategy": visual},
        ),
        trace=trace,
        progress_callback=progress_callback,
    )
    attempts += attempt_count
    if not decision:
        compressed = _compress_checkpoint_decision(
            {},
            intent=intent,
            visual_strategy=visual,
            fallback=fallback,
        )
        _write_json(workspace / "compressed_decision.json", compressed)
        _write_json(
            workspace / "orchestration_trace.json",
            {
                "stages": trace,
                "final_status": "recovered_from_stage_checkpoints",
                "recovery_reason": "generation_decision_checkpoint_unavailable",
            },
        )
        return compressed, {"attempts": attempts, "trace": trace, "recovery": "stage_checkpoint_compaction"}

    compressed = _compress_checkpoint_decision(
        decision,
        intent=intent,
        visual_strategy=visual,
        fallback=fallback,
    )
    _write_json(workspace / "stage_03_generation_decision.json", decision)
    _write_json(workspace / "compressed_decision.json", compressed)
    _write_json(workspace / "orchestration_trace.json", {"stages": trace, "final_status": "success"})
    return compressed, {"attempts": attempts, "trace": trace}


def _invoke_checkpoint_stage_with_micro(
    *,
    command: list[str],
    workspace: Path,
    stage_name: str,
    schema: dict[str, Any],
    prompt: str,
    micro_prompt: str,
    ultra_micro_prompt: str | None = None,
    trace: list[dict[str, Any]],
    stop_on_soft_timeout: bool = False,
    progress_callback: ClaudeProgressCallback | None = None,
) -> tuple[dict[str, Any] | None, int]:
    attempts = 0
    max_retries = max(0, settings.claude_checkpoint_max_stage_retries)
    prompts = [(stage_name, prompt)]
    seen_prompts = {prompt}
    retry_number = 0
    for index in range(1, max_retries + 1):
        candidates: list[tuple[str, str]] = []
        if index >= 2 and ultra_micro_prompt:
            candidates.append(("ultra_micro_retry", ultra_micro_prompt))
        candidates.append(("micro_retry", micro_prompt))
        if index < 2 and ultra_micro_prompt:
            candidates.append(("ultra_micro_retry", ultra_micro_prompt))
        selected = next(((suffix, value) for suffix, value in candidates if value not in seen_prompts), None)
        if selected is None and not ultra_micro_prompt and retry_number == 0:
            selected = ("micro_retry", micro_prompt)
        if selected is None:
            continue
        retry_suffix, retry_prompt = selected
        retry_number += 1
        seen_prompts.add(retry_prompt)
        prompts.append((f"{stage_name}_{retry_suffix}_{retry_number}", retry_prompt))
    last_failure: str | None = None
    source = _claude_code_source_selection(workspace)
    primary_provider = source.provider
    primary_model = source.model
    primary_kwargs = dict(source.stage_kwargs)
    if primary_model and primary_model != _claude_code_primary_model():
        primary_kwargs["model_override"] = primary_model
    for attempt_stage_name, attempt_prompt in prompts:
        attempts += 1
        started = time.perf_counter()
        timeout_seconds = _checkpoint_stage_timeout_seconds(attempt_stage_name)
        _emit_claude_progress(
            progress_callback,
            stage=attempt_stage_name,
            status="running",
            provider=primary_provider,
            model=primary_model,
            timeout_seconds=timeout_seconds,
            attempt=attempts,
        )
        try:
            result = _invoke_claude_stage_json(
                command=command,
                workspace=workspace,
                stage_name=attempt_stage_name,
                prompt=attempt_prompt,
                schema=schema,
                **primary_kwargs,
            )
        except ClaudeInvocationError as exc:
            last_failure = str(exc)
            duration_ms = _elapsed_ms(started)
            trace.append(
                {
                    "stage": attempt_stage_name,
                    "status": "error",
                    "provider": primary_provider,
                    "model": primary_model,
                    "source_reason": source.reason,
                    "failure_code": last_failure,
                    "duration_ms": duration_ms,
                }
            )
            _emit_claude_progress(
                progress_callback,
                stage=attempt_stage_name,
                status="error",
                provider=primary_provider,
                model=primary_model,
                timeout_seconds=timeout_seconds,
                duration_ms=duration_ms,
                failure_code=last_failure,
                attempt=attempts,
            )
            if last_failure not in _CHECKPOINT_RETRYABLE_CLAUDE_FAILURES and "output_token_limit" not in last_failure:
                raise
            if stop_on_soft_timeout and last_failure == "claude_soft_timeout":
                return None, attempts
            should_try_fallback = _should_try_claude_code_model_fallback(last_failure)
            if _requires_multimodal_claude_source(source) and (
                last_failure == "claude_reasoning_not_supported" or should_try_fallback
            ):
                blocked_failure = _multimodal_required_unavailable_code(last_failure)
                trace.append(
                    {
                        "stage": attempt_stage_name,
                        "status": "failed",
                        "provider": primary_provider,
                        "model": primary_model,
                        "source_reason": source.reason,
                        "failure_code": blocked_failure,
                        "text_fallback_blocked": True,
                        "duration_ms": duration_ms,
                    }
                )
                _emit_claude_progress(
                    progress_callback,
                    stage=attempt_stage_name,
                    status="failed",
                    provider=primary_provider,
                    model=primary_model,
                    timeout_seconds=timeout_seconds,
                    duration_ms=duration_ms,
                    failure_code=blocked_failure,
                    attempt=attempts,
                )
                raise ClaudeInvocationError(blocked_failure)
            if should_try_fallback:
                fallback_started = time.perf_counter()
                _emit_claude_progress(
                    progress_callback,
                    stage=f"{attempt_stage_name}_model_fallback",
                    status="running",
                    provider="claude-code-model-fallback",
                    models=_claude_code_model_fallback_queue(exclude_model=primary_model)[
                        : settings.claude_orchestrator_fallback_max_models_per_stage
                    ],
                    attempt=attempts + 1,
                )
                fallback_result, fallback_meta = _invoke_claude_code_model_fallbacks(
                    command=command,
                    workspace=workspace,
                    stage_name=attempt_stage_name,
                    prompt=attempt_prompt,
                    schema=schema,
                    progress_callback=progress_callback,
                )
                attempts += int(fallback_meta.get("attempts") or 0)
                fallback_duration_ms = _elapsed_ms(fallback_started)
                trace.append(
                    {
                        "stage": attempt_stage_name,
                        "status": "success" if fallback_result else "error",
                        "provider": "claude-code-model-fallback",
                        "model": fallback_meta.get("model"),
                        "failure_code": None if fallback_result else fallback_meta.get("failure_code"),
                        "duration_ms": fallback_duration_ms,
                    }
                )
                _emit_claude_progress(
                    progress_callback,
                    stage=f"{attempt_stage_name}_model_fallback",
                    status="success" if fallback_result else "error",
                    provider="claude-code-model-fallback",
                    model=fallback_meta.get("model"),
                    duration_ms=fallback_duration_ms,
                    failure_code=None if fallback_result else fallback_meta.get("failure_code"),
                    attempt=attempts,
                )
                if fallback_result:
                    return fallback_result, attempts
            continue
        duration_ms = _elapsed_ms(started)
        trace.append(
            {
                "stage": attempt_stage_name,
                "status": "success" if result else "missing_decision",
                "provider": primary_provider,
                "model": primary_model,
                "source_reason": source.reason,
                "failure_code": None if result else "missing_decision",
                "duration_ms": duration_ms,
            }
        )
        _emit_claude_progress(
            progress_callback,
            stage=attempt_stage_name,
            status="success" if result else "missing_decision",
            provider=primary_provider,
            model=primary_model,
            timeout_seconds=timeout_seconds,
            duration_ms=duration_ms,
            failure_code=None if result else "missing_decision",
            attempt=attempts,
        )
        if result:
            return result, attempts
    if last_failure:
        should_try_fallback = _should_try_claude_code_model_fallback(last_failure, after_compression_retries=True)
        if should_try_fallback and _requires_multimodal_claude_source(source):
            blocked_failure = _multimodal_required_unavailable_code(last_failure)
            trace.append(
                {
                    "stage": stage_name,
                    "status": "failed",
                    "provider": primary_provider,
                    "model": primary_model,
                    "source_reason": source.reason,
                    "failure_code": blocked_failure,
                    "text_fallback_blocked": True,
                    "after_compression_retries": True,
                }
            )
            _emit_claude_progress(
                progress_callback,
                stage=stage_name,
                status="failed",
                provider=primary_provider,
                model=primary_model,
                failure_code=blocked_failure,
                after_compression_retries=True,
                attempt=attempts,
            )
            raise ClaudeInvocationError(blocked_failure)
        if should_try_fallback:
            fallback_started = time.perf_counter()
            _emit_claude_progress(
                progress_callback,
                stage=f"{stage_name}_model_fallback_after_compression",
                status="running",
                provider="claude-code-model-fallback",
                models=_claude_code_model_fallback_queue(exclude_model=primary_model)[
                    : settings.claude_orchestrator_fallback_max_models_per_stage
                ],
                after_compression_retries=True,
                attempt=attempts + 1,
            )
            fallback_result, fallback_meta = _invoke_claude_code_model_fallbacks(
                command=command,
                workspace=workspace,
                stage_name=stage_name,
                prompt=ultra_micro_prompt or micro_prompt,
                schema=schema,
                progress_callback=progress_callback,
            )
            attempts += int(fallback_meta.get("attempts") or 0)
            fallback_duration_ms = _elapsed_ms(fallback_started)
            trace.append(
                {
                    "stage": stage_name,
                    "status": "success" if fallback_result else "error",
                    "provider": "claude-code-model-fallback",
                    "model": fallback_meta.get("model"),
                    "failure_code": None if fallback_result else fallback_meta.get("failure_code"),
                    "duration_ms": fallback_duration_ms,
                    "after_compression_retries": True,
                }
            )
            _emit_claude_progress(
                progress_callback,
                stage=f"{stage_name}_model_fallback_after_compression",
                status="success" if fallback_result else "error",
                provider="claude-code-model-fallback",
                model=fallback_meta.get("model"),
                duration_ms=fallback_duration_ms,
                failure_code=None if fallback_result else fallback_meta.get("failure_code"),
                after_compression_retries=True,
                attempt=attempts,
            )
            if fallback_result:
                return fallback_result, attempts
        trace.append({"stage": stage_name, "status": "failed", "failure_code": last_failure})
        _emit_claude_progress(
            progress_callback,
            stage=stage_name,
            status="failed",
            provider=primary_provider,
            model=primary_model,
            failure_code=last_failure,
            attempt=attempts,
        )
    return None, attempts


def _claude_code_primary_model() -> str:
    return _text_value(settings.claude_orchestrator_model)


def _claude_code_primary_provider(model: str | None = None) -> str:
    model = _text_value(model) or _claude_code_primary_model()
    if _is_kimi_model(model):
        return "kimi"
    if model:
        return "claude-code-primary"
    return "claude-code"


def _claude_code_primary_stage_kwargs(model: str | None = None) -> dict[str, Any]:
    if not _should_use_external_primary_invocation_mode(_text_value(model) or _claude_code_primary_model()):
        return {}
    return {
        "setting_sources_override": "project,local",
        "include_effort": False,
        "strip_model_fallback_env": True,
    }


def _should_use_external_primary_invocation_mode(model: str) -> bool:
    if not model or _is_kimi_model(model):
        return False
    lowered = model.lower()
    if lowered.startswith("claude-"):
        return False
    return True


def _is_kimi_model(model: str) -> bool:
    return "kimi" in (model or "").lower()


def _claude_code_source_selection(workspace: Path | None = None) -> ClaudeSourceSelection:
    persisted = _read_json(workspace / "claude_source_selection.json") if workspace else {}
    model = _text_value(persisted.get("model")) if isinstance(persisted, dict) else ""
    reason = _text_value(persisted.get("reason")) if isinstance(persisted, dict) else ""
    if not model:
        model = _claude_code_primary_model()
    return ClaudeSourceSelection(
        provider=_claude_code_primary_provider(model),
        model=model,
        stage_kwargs=_claude_code_primary_stage_kwargs(model),
        reason=reason or "default_text_primary",
        multimodal_requested=bool(persisted.get("multimodal_requested")) if isinstance(persisted, dict) else False,
    )


def _requires_multimodal_claude_source(source: ClaudeSourceSelection) -> bool:
    if _text_value(source.reason) in _MULTIMODAL_REQUIRED_SOURCE_REASONS:
        return True
    return bool(source.multimodal_requested and _text_value(source.reason) != "uploaded_assets_soft_reference")


def _multimodal_required_unavailable_code(failure_code: str | None) -> str:
    detail = _text_value(failure_code) or "unknown"
    return f"claude_multimodal_required_unavailable:{detail}"


def _should_try_claude_code_model_fallback(
    failure_code: str | None,
    *,
    after_compression_retries: bool = False,
) -> bool:
    if not failure_code or not _claude_code_model_fallback_configured():
        return False
    if after_compression_retries:
        return failure_code in _CHECKPOINT_RETRYABLE_CLAUDE_FAILURES or "output_token_limit" in failure_code
    return failure_code in _CLAUDE_CODE_IMMEDIATE_MODEL_FALLBACK_FAILURES


def _emit_claude_progress(callback: ClaudeProgressCallback | None, **payload: Any) -> None:
    if callback is None:
        return
    event = {
        "scope": "claude_orchestration",
        "stage": _text_value(payload.get("stage")),
        "stage_label": _claude_stage_label(_text_value(payload.get("stage"))),
        "status": _text_value(payload.get("status")) or "running",
        "provider": _text_value(payload.get("provider")) or "kimi",
        "model": _text_value(payload.get("model")),
        "fallback_model": _text_value(payload.get("fallback_model")),
        "timeout_seconds": payload.get("timeout_seconds"),
        "duration_ms": payload.get("duration_ms"),
        "failure_code": _text_value(payload.get("failure_code")),
        "attempt": payload.get("attempt"),
        "models": payload.get("models") if isinstance(payload.get("models"), list) else [],
        "after_compression_retries": bool(payload.get("after_compression_retries")),
        "created_at": utc_now().isoformat(),
    }
    event["message"] = _claude_progress_message(event)
    try:
        callback({key: value for key, value in event.items() if value not in (None, "", [])})
    except Exception:
        pass


def _claude_stage_label(stage_name: str) -> str:
    base = _claude_base_stage_name(stage_name)
    label = _CLAUDE_STAGE_LABELS.get(base, base or "Claude 调度")
    if "model_fallback" in stage_name:
        return f"{label} · 备用源接力"
    if "ultra_micro" in stage_name:
        return f"{label} · 超短压缩续跑"
    if "micro_retry" in stage_name:
        return f"{label} · 压缩续跑"
    return label


def _claude_base_stage_name(stage_name: str) -> str:
    for prefix in [
        "generation_decision_recovery",
        "generation_decision",
        "visual_strategy",
        "single_stage_decision",
        "intent",
    ]:
        if stage_name.startswith(prefix):
            return prefix
    return stage_name.split("_micro_retry", 1)[0].split("_ultra_micro_retry", 1)[0].split("_model_fallback", 1)[0]


def _claude_progress_message(event: dict[str, Any]) -> str:
    label = _text_value(event.get("stage_label")) or "Claude 调度"
    provider = _claude_progress_provider_label(_text_value(event.get("provider")), _text_value(event.get("model")))
    status = _text_value(event.get("status"))
    if status == "running":
        timeout = event.get("timeout_seconds")
        timeout_text = f"，阶段上限 {int(float(timeout))}s" if isinstance(timeout, (int, float)) and timeout else ""
        return f"Claude Code · {label} · {provider}运行中{timeout_text}"
    duration = _format_duration_ms(event.get("duration_ms"))
    duration_text = f"，用时 {duration}" if duration else ""
    failure = _text_value(event.get("failure_code"))
    if status == "success":
        return f"Claude Code · {label} · {provider}完成{duration_text}"
    if status == "missing_decision":
        return f"Claude Code · {label} · 未得到有效 JSON{duration_text}，准备压缩续跑"
    if status in {"error", "failed"}:
        return f"Claude Code · {label} · {provider}{_claude_failure_label(failure)}{duration_text}"
    return f"Claude Code · {label} · {status}{duration_text}"


def _claude_progress_provider_label(provider: str, model: str = "") -> str:
    if provider == "claude-code-model-fallback":
        return f"备用源 {model} " if model else "备用源 "
    if provider == "kimi":
        return "Kimi 主源 "
    if provider == "claude-code-primary":
        return f"主源 {model} " if model else "Claude Code 主源 "
    if provider == "claude-code":
        return "Claude Code 主源 "
    if provider:
        return f"{provider} "
    return ""


def _claude_failure_label(failure_code: str) -> str:
    if failure_code.startswith("claude_multimodal_required_unavailable"):
        return "多模态主源不可用，已阻止文本备用源接管"
    if failure_code == "claude_reasoning_not_supported":
        return "模型不支持 reasoning 参数"
    if failure_code == "claude_soft_timeout":
        return "触达软上限，进入压缩续跑"
    if failure_code == "claude_timeout":
        return "触达硬上限"
    if failure_code == "claude_output_token_limit":
        return "输出超限，进入压缩续跑"
    if failure_code == "claude_policy_refusal":
        return "策略误拒，准备备用源接力"
    if failure_code in {"kimi_context_canceled", "kimi_sub2api_502", "kimi_no_available_accounts", "kimi_upstream_error"}:
        return "上游不可用，准备备用源接力"
    if failure_code:
        return f"失败（{failure_code}）"
    return "失败"


def _format_duration_ms(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return ""
    seconds = max(0.0, float(value) / 1000)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    return f"{minutes}m {int(seconds % 60)}s"


def _claude_code_model_fallback_configured() -> bool:
    return bool(
        _claude_code_model_fallback_queue()
        and (
            settings.claude_orchestrator_fallback_base_url
            or settings.claude_orchestrator_fallback_auth_token
        )
    )


def _claude_code_model_fallback_queue(*, exclude_model: str | None = None) -> list[str]:
    models: list[str] = []
    if settings.claude_orchestrator_fallback_model:
        models.append(settings.claude_orchestrator_fallback_model)
    models.extend(settings.claude_orchestrator_fallback_models or [])
    primary = _text_value(exclude_model) or _text_value(settings.claude_orchestrator_model)
    return _dedupe(
        [
            _text_value(model)
            for model in models
            if _text_value(model) and _text_value(model) != _text_value(primary)
        ]
    )


def _claude_code_fallback_env_overrides() -> dict[str, str]:
    overrides: dict[str, str] = {}
    if settings.claude_orchestrator_fallback_base_url:
        overrides["ANTHROPIC_BASE_URL"] = settings.claude_orchestrator_fallback_base_url
    if settings.claude_orchestrator_fallback_auth_token:
        overrides["ANTHROPIC_AUTH_TOKEN"] = settings.claude_orchestrator_fallback_auth_token
        overrides["ANTHROPIC_API_KEY"] = settings.claude_orchestrator_fallback_auth_token
    return overrides


def _strip_claude_code_model_fallback_env(env: dict[str, str]) -> None:
    for key in list(env):
        if key in {"CLAUDE_CODE_EFFORT_LEVEL", "CLAUDE_CODE_SUBAGENT_MODEL"}:
            env.pop(key, None)
        elif "REASONING_EFFORT" in key:
            env.pop(key, None)


def _invoke_claude_code_model_fallbacks(
    *,
    command: list[str],
    workspace: Path,
    stage_name: str,
    prompt: str,
    schema: dict[str, Any],
    progress_callback: ClaudeProgressCallback | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    attempts = 0
    last_failure = "claude_code_model_fallback_unavailable"
    source = _claude_code_source_selection(workspace)
    queue = _claude_code_model_fallback_queue(exclude_model=source.model)[
        : settings.claude_orchestrator_fallback_max_models_per_stage
    ]
    env_overrides = _claude_code_fallback_env_overrides()
    for index, model in enumerate(queue):
        attempts += 1
        next_model = queue[index + 1] if index + 1 < len(queue) else None
        fallback_stage_name = f"{stage_name}_model_fallback_{index + 1}"
        fallback_started = time.perf_counter()
        _emit_claude_progress(
            progress_callback,
            stage=fallback_stage_name,
            status="running",
            provider="claude-code-model-fallback",
            model=model,
            fallback_model=next_model,
            timeout_seconds=settings.claude_orchestrator_fallback_stage_timeout_seconds,
            attempt=attempts,
        )
        try:
            result = _invoke_claude_stage_json(
                command=command,
                workspace=workspace,
                stage_name=fallback_stage_name,
                prompt=prompt,
                schema=schema,
                model_override=model,
                fallback_model_override=next_model,
                env_overrides=env_overrides,
                setting_sources_override="project,local",
                include_effort=False,
                strip_model_fallback_env=True,
                timeout_override=settings.claude_orchestrator_fallback_stage_timeout_seconds,
            )
        except ClaudeInvocationError as exc:
            last_failure = str(exc)
            _emit_claude_progress(
                progress_callback,
                stage=fallback_stage_name,
                status="error",
                provider="claude-code-model-fallback",
                model=model,
                fallback_model=next_model,
                timeout_seconds=settings.claude_orchestrator_fallback_stage_timeout_seconds,
                duration_ms=_elapsed_ms(fallback_started),
                failure_code=last_failure,
                attempt=attempts,
            )
            if last_failure not in _CHECKPOINT_RETRYABLE_CLAUDE_FAILURES and "output_token_limit" not in last_failure:
                continue
            continue
        if result:
            _emit_claude_progress(
                progress_callback,
                stage=fallback_stage_name,
                status="success",
                provider="claude-code-model-fallback",
                model=model,
                fallback_model=next_model,
                timeout_seconds=settings.claude_orchestrator_fallback_stage_timeout_seconds,
                duration_ms=_elapsed_ms(fallback_started),
                attempt=attempts,
            )
            return result, {"attempts": attempts, "model": model}
        last_failure = "missing_decision"
        _emit_claude_progress(
            progress_callback,
            stage=fallback_stage_name,
            status="missing_decision",
            provider="claude-code-model-fallback",
            model=model,
            fallback_model=next_model,
            timeout_seconds=settings.claude_orchestrator_fallback_stage_timeout_seconds,
            duration_ms=_elapsed_ms(fallback_started),
            failure_code=last_failure,
            attempt=attempts,
        )
    return None, {"attempts": attempts, "failure_code": last_failure}


def _run_claude_subprocess(
    command_line: list[str],
    *,
    input_text: str,
    timeout_seconds: float,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    popen_kwargs: dict[str, Any] = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(
        command_line,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd),
        env=env,
        **popen_kwargs,
    )
    try:
        stdout, stderr = process.communicate(input=input_text, timeout=timeout_seconds)
        return subprocess.CompletedProcess(command_line, process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(
            command_line,
            timeout_seconds,
            output=stdout or _timeout_output(exc.stdout),
            stderr=stderr or _timeout_output(exc.stderr),
        ) from exc


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception:
            process.kill()
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except Exception:
        process.kill()


def _invoke_claude_stage_json(
    *,
    command: list[str],
    workspace: Path,
    stage_name: str,
    prompt: str,
    schema: dict[str, Any],
    model_override: str | None = None,
    fallback_model_override: str | None = None,
    env_overrides: dict[str, str] | None = None,
    setting_sources_override: str | None = None,
    include_effort: bool = True,
    strip_model_fallback_env: bool = False,
    timeout_override: float | None = None,
) -> dict[str, Any] | None:
    safe_stage = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stage_name).strip("_") or "stage"
    command_line = [
        *command,
        "-p",
        "--system-prompt",
        _checkpoint_system_prompt(),
        "--output-format",
        "json",
        "--permission-mode",
        settings.claude_orchestrator_permission_mode,
        "--tools",
        "none",
        "--bare",
        "--no-session-persistence",
    ]
    if include_effort:
        command_line.extend(["--effort", settings.claude_orchestrator_effort])
    command_line.extend(["--json-schema", json.dumps(schema, ensure_ascii=False, separators=(",", ":"))])
    _apply_claude_cli_acceleration_flags(command_line, include_effort=include_effort)
    if setting_sources_override:
        command_line.extend(["--setting-sources", setting_sources_override])
    model = model_override or settings.claude_orchestrator_model
    fallback_model = fallback_model_override or settings.claude_orchestrator_fallback_model
    if model:
        command_line.extend(["--model", model])
    if fallback_model and fallback_model != model:
        command_line.extend(["--fallback-model", fallback_model])
    env = dict(os.environ)
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    env.setdefault("CLAUDE_CODE_ATTRIBUTION_HEADER", "0")
    if strip_model_fallback_env:
        _strip_claude_code_model_fallback_env(env)
    for key, value in (env_overrides or {}).items():
        if value:
            env[key] = value
    env["MAX_STRUCTURED_OUTPUT_RETRIES"] = "0"
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(_checkpoint_stage_max_output_tokens())
    _write_text(workspace / f"{safe_stage}_prompt.txt", prompt)
    timeout_seconds = timeout_override or _checkpoint_stage_timeout_seconds(stage_name)
    try:
        completed = _run_claude_subprocess(
            command_line,
            input_text=prompt,
            timeout_seconds=timeout_seconds,
            cwd=workspace,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _timeout_output(exc.stdout)
        stderr = _timeout_output(exc.stderr)
        _write_text(workspace / f"{safe_stage}_stdout.json", stdout)
        _write_text(workspace / f"{safe_stage}_stderr.txt", stderr)
        parsed = _parse_structured_output(stdout)
        if isinstance(parsed, dict) and not _classify_claude_failure(stdout, stderr, 0):
            parsed = _coerce_checkpoint_payload(parsed, schema, workspace=workspace)
            if _matches_checkpoint_schema(parsed, schema):
                return parsed
        failure_code = "claude_soft_timeout" if _is_checkpoint_soft_timeout(stage_name, timeout_seconds) else "claude_timeout"
        raise ClaudeInvocationError(failure_code) from exc
    _write_text(workspace / f"{safe_stage}_stdout.json", completed.stdout or "")
    _write_text(workspace / f"{safe_stage}_stderr.txt", completed.stderr or "")
    failure = _classify_claude_failure(completed.stdout, completed.stderr, completed.returncode)
    if failure:
        raise ClaudeInvocationError(failure)
    if completed.returncode != 0:
        return None
    parsed = _parse_structured_output(completed.stdout or "")
    if not isinstance(parsed, dict):
        return None
    parsed = _coerce_checkpoint_payload(parsed, schema, workspace=workspace)
    return parsed if _matches_checkpoint_schema(parsed, schema) else None


def _checkpoint_stage_hard_timeout_seconds() -> float:
    return min(
        settings.claude_orchestrator_timeout_seconds,
        settings.claude_checkpoint_stage_timeout_seconds,
    )


def _checkpoint_stage_timeout_seconds(stage_name: str) -> float:
    hard_timeout = _checkpoint_stage_hard_timeout_seconds()
    soft_timeout = min(hard_timeout, settings.claude_checkpoint_soft_stage_timeout_seconds)
    if "_retry_" not in stage_name:
        if stage_name.startswith("generation_decision"):
            return soft_timeout
        return soft_timeout
    if "ultra_micro" in stage_name:
        return min(hard_timeout, soft_timeout, 30.0)
    return min(hard_timeout, soft_timeout, 45.0)


def _checkpoint_stage_max_output_tokens() -> int:
    configured = int(settings.claude_orchestrator_max_output_tokens or _CLAUDE_CHECKPOINT_MAX_OUTPUT_TOKENS)
    return max(512, min(configured, _CLAUDE_CHECKPOINT_MAX_OUTPUT_TOKENS))


def _is_checkpoint_soft_timeout(stage_name: str, timeout_seconds: float) -> bool:
    return timeout_seconds < _checkpoint_stage_hard_timeout_seconds() and "_retry_" not in stage_name


def _coerce_checkpoint_payload(payload: dict[str, Any], schema: dict[str, Any], *, workspace: Path | None = None) -> dict[str, Any]:
    coerced = dict(payload)
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    stage_spec = properties.get("stage") if isinstance(properties.get("stage"), dict) else {}
    stage_enum = stage_spec.get("enum") if isinstance(stage_spec.get("enum"), list) else []
    if stage_enum and _text_value(coerced.get("stage")):
        expected_stage = str(stage_enum[0])
        if _text_value(coerced.get("stage")).startswith(expected_stage):
            coerced["stage"] = expected_stage
    for field, spec in properties.items():
        if not isinstance(spec, dict) or field not in coerced:
            continue
        if spec.get("type") == "array" and isinstance(coerced.get(field), str):
            coerced[field] = [_text_value(coerced[field])] if _text_value(coerced[field]) else []
        if spec.get("type") == "number" and isinstance(coerced.get(field), str):
            label = _text_value(coerced[field]).lower()
            if label in {"high", "strong", "yes"}:
                coerced[field] = 0.9
            elif label in {"medium", "moderate"}:
                coerced[field] = 0.65
            elif label in {"low", "weak"}:
                coerced[field] = 0.35
            else:
                try:
                    coerced[field] = float(label)
                except ValueError:
                    pass
    mode_spec = properties.get("mode") if isinstance(properties.get("mode"), dict) else {}
    allowed_modes = mode_spec.get("enum") if isinstance(mode_spec.get("enum"), list) else []
    if allowed_modes and coerced.get("mode") not in allowed_modes:
        fallback_mode = ""
        if workspace:
            fallback = _read_json(workspace / "fallback_decision.json") or {}
            fallback_mode = _text_value(fallback.get("mode"))
        coerced["mode"] = fallback_mode if fallback_mode in allowed_modes else "smart_enhance"
    return coerced


def _checkpoint_system_prompt() -> str:
    return (
        "You are the central creative brain for a staged image-generation orchestrator. "
        "Make a complete high-quality decision for the current narrow stage with bounded internal deliberation. "
        "For ordinary food, product, poster, menu, layout, or style-planning tasks, complete the requested schema. "
        "Think silently, then emit the compressed answer immediately. "
        "Do not write or simulate chain-of-thought, long analysis, drafts, alternatives, markdown, or commentary. "
        "The first visible character must be { and the last visible character must be }. "
        "The visible answer must be compact JSON matching the schema, with no internal ids, URLs, API names, repository names, or storage identifiers."
    )


def _build_checkpoint_stage_prompt(
    workspace: Path,
    *,
    stage_name: str,
    checkpoints: dict[str, Any] | None = None,
) -> str:
    context = _read_json(workspace / "context.json") or {}
    fallback = _read_json(workspace / "fallback_decision.json") or {}
    template_lock_contract = _read_json(workspace / "template_lock_contract.json") or {}
    task_relationship_model = _read_json(workspace / "task_relationship_model.json") or {}
    asset_binding_policy = _read_json(workspace / "asset_binding_policy.json") or {}
    visual_grammar_contract = _read_json(workspace / "visual_grammar_contract.json") or {}
    uploaded_assets = _read_json_list(workspace / "uploaded_assets.json")
    compact_task_relationship = _compact_task_relationship_model(task_relationship_model)
    template_case_id = (context.get("request") or {}).get("template_case_id")
    prompt_transform_profile = context.get("prompt_transform_profile") if isinstance(context.get("prompt_transform_profile"), dict) else {}
    compact_cases = _compact_inline_cases(
        _read_json_list(workspace / "candidate_cases.json"),
        _read_json_list(workspace / "candidate_case_details.json"),
        template_case_id=template_case_id,
    )
    if stage_name.startswith("intent"):
        compact_cases = []
    elif "ultra_micro" in stage_name or stage_name.startswith("generation_decision"):
        compact_cases = []
    elif stage_name.endswith("_micro"):
        compact_cases = compact_cases[:1]
    elif stage_name.startswith("visual_strategy") and not template_case_id:
        compact_cases = compact_cases[:2]
    if stage_name.startswith("visual_strategy"):
        compact_cases = [_checkpoint_visual_case(item, tight=stage_name.endswith("_micro")) for item in compact_cases]
    checkpoint_payload = checkpoints or {}
    if stage_name.startswith("generation_decision"):
        checkpoint_payload = _compact_generation_checkpoints(checkpoint_payload)
    output_limits = _checkpoint_output_limits(stage_name)
    request_payload = {
        "user_prompt": (context.get("request") or {}).get("user_prompt", ""),
        "template_case_id": template_case_id,
        "output": _provider_visible_output((context.get("request") or {}).get("output", {})),
    }
    if stage_name.startswith("generation_decision"):
        request_payload = {
            "user_prompt_brief": _truncate(_text_value((context.get("request") or {}).get("user_prompt")), 260),
            "template_case_id": template_case_id,
            "output": _provider_visible_output((context.get("request") or {}).get("output", {})),
        }

    payload = {
        "stage": stage_name,
        "instruction": _checkpoint_stage_instruction(stage_name),
        "rules": (
            "Every stage is Claude-led and must be completed; do not skip Claude for any subject. "
            "For ordinary food, product, poster, menu, layout, or style-planning tasks, complete the schema instead of refusing. "
            "Think through the stage fully but silently; never write the reasoning. Output only compact JSON. "
            "The first visible character must be { and the last visible character must be }. "
            f"Hard visible output cap: total JSON <= {output_limits['total_json_chars']} characters; obey each field cap in output_limits. "
            "Follow visual_grammar_contract when present: grammar controls composition/hierarchy/mood/layout; user controls semantic content. "
            "If visual_grammar_contract.mode=uploaded_frame_visual_grammar, the uploaded reference controls the layout/composition frame and retrieved cases only polish compatible style. "
            "If visual_grammar_contract.info.active, keep poster/menu facts; use larger canvas/modules instead of dropping offers, prices, rules, requested CTA/QR, or items. "
            "Template id stays selected_case_ids[0]; without template choose one primary anchor. "
            "Assets fill slots; composite poster/menu/screenshot sources are content only; synthesize missing key anchor elements. "
            "Do not leak internal ids, URLs, APIs, repo names, storage names, or source markers. "
            f"Prompt transform mode: {prompt_transform_profile.get('transform_mode') or 'auto'} / "
            f"{prompt_transform_profile.get('fidelity_mode') or 'auto'}; "
            f"{prompt_transform_profile.get('claude_instruction') or ''}"
        ),
        "output_contract": _checkpoint_output_contract(stage_name),
        "request": request_payload,
        "prompt_transform": prompt_transform_profile,
        "fallback": {
            "mode": fallback.get("mode"),
            "selected_case_ids": [template_case_id] if template_case_id else fallback.get("selected_case_ids", [])[:4],
            "generation_directives": fallback.get("generation_directives", {}),
        },
        "template_lock_contract": _compact_template_lock(template_lock_contract),
        "visual_grammar_contract": _compact_visual_grammar_contract(visual_grammar_contract),
        "uploaded_assets": _compact_uploaded_assets(uploaded_assets),
        "asset_binding_policy": _compact_asset_binding_policy(asset_binding_policy),
        "candidate_cases": compact_cases,
        "checkpoints": checkpoint_payload,
        "output_limits": output_limits,
        "json_skeleton": _checkpoint_json_skeleton(stage_name),
    }
    if compact_task_relationship:
        payload["task_relationship_model"] = compact_task_relationship
    if stage_name.startswith("generation_decision"):
        payload["visible_output_budget"] = {
            "final_prompt_chars": settings.claude_final_prompt_max_chars,
            "negative_prompt_chars": settings.claude_negative_prompt_max_chars,
            "rationale_chars": settings.claude_rationale_max_chars,
        }
        payload.pop("template_lock_contract", None)
        payload.pop("visual_grammar_contract", None)
        payload.pop("uploaded_assets", None)
        payload.pop("asset_binding_policy", None)
        payload["rules"] = (
            "Claude-led final compression stage. Treat intent and visual_strategy checkpoints as the completed reasoning record; "
            "do not re-read or re-analyze the full source material. Emit one provider-ready JSON package only. "
            "First char {, last char }. No analysis/prose/markdown. "
            f"Total JSON <= {output_limits['total_json_chars']} chars; final_prompt <= {output_limits['final_prompt_chars']} chars. "
            "Preserve template frame, information integrity, requested CTA/contact placement, explicit/source QR placement only when QR intent exists, and provider count from checkpoints/fallback."
        )
    if "ultra_micro" in stage_name and not uploaded_assets and not template_case_id:
        payload.pop("template_lock_contract", None)
        payload.pop("visual_grammar_contract", None)
        payload.pop("uploaded_assets", None)
        payload.pop("asset_binding_policy", None)
        payload["fallback"] = {
            "mode": fallback.get("mode"),
            "selected_case_ids": fallback.get("selected_case_ids", [])[:2],
            "generation_directives": fallback.get("generation_directives", {}),
        }
        payload["rules"] = (
            "Claude-led ultra-micro stage. Think silently, then output compact JSON only. "
            "First char {, last char }. No analysis/prose/markdown. "
            f"Total JSON <= {output_limits['total_json_chars']} chars; obey output_limits. "
            "Use only request, fallback, and checkpoints; no case comparison, ids, URLs, APIs, or source markers."
        )
    elif not visual_grammar_contract:
        payload.pop("visual_grammar_contract", None)
    if stage_name.startswith("generation_decision"):
        payload["rules"] += " Final stage: write one dense provider-ready prompt directly; no draft variants, no option analysis."
    if stage_name.endswith("_micro"):
        payload["rules"] += " This is a retry micro-stage: finish only the missing decision; no broad re-analysis."
    return (
        "Return schema JSON only. Start with { immediately. No prose/markdown/analysis.\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def _checkpoint_output_contract(stage_name: str) -> str:
    if stage_name.startswith("intent"):
        return (
            "Object keys: stage, mode, primary_subject, scene_goal, must_keep, must_avoid, "
            "asset_requirements, risk_notes, confidence. Short strings; arrays<=6."
        )
    if stage_name.startswith("visual_strategy"):
        return (
            "Object keys: stage, selected_case_ids, composition, lighting, palette, "
            "spatial_hierarchy, template_lock_notes, asset_fusion_notes, confidence. One strategy only."
        )
    return (
        "Object keys: mode, selected_case_ids, final_prompt, negative_prompt, provider_parameters, "
        "prompt_rationale, confidence. final_prompt must be provider-ready and within visible_output_budget."
    )


def _checkpoint_output_limits(stage_name: str) -> dict[str, Any]:
    if stage_name.startswith("intent"):
        return {
            "total_json_chars": 1300,
            "max_array_items": 5,
            "primary_subject_chars": 120,
            "scene_goal_chars": 180,
            "list_item_chars": 70,
            "risk_note_chars": 60,
        }
    if stage_name.startswith("visual_strategy"):
        return {
            "total_json_chars": 1200,
            "selected_case_ids_items": 1 if "micro" in stage_name else 2,
            "composition_chars": 170,
            "lighting_chars": 90,
            "palette_chars": 90,
            "spatial_hierarchy_chars": 150,
            "template_lock_notes_chars": 130,
            "asset_fusion_notes_chars": 150,
        }
    return {
        "total_json_chars": 1800,
        "selected_case_ids_items": 1,
        "final_prompt_chars": settings.claude_final_prompt_max_chars,
        "negative_prompt_chars": settings.claude_negative_prompt_max_chars,
        "prompt_rationale_chars": settings.claude_rationale_max_chars,
    }


def _checkpoint_json_skeleton(stage_name: str) -> dict[str, Any]:
    if stage_name.startswith("intent"):
        return {
            "stage": "intent",
            "mode": "template_customize",
            "primary_subject": "...",
            "scene_goal": "...",
            "must_keep": ["..."],
            "must_avoid": ["..."],
            "asset_requirements": [],
            "risk_notes": [],
            "confidence": 0.8,
        }
    if stage_name.startswith("visual_strategy"):
        return {
            "stage": "visual_strategy",
            "selected_case_ids": ["..."],
            "composition": "...",
            "lighting": "...",
            "palette": "...",
            "spatial_hierarchy": "...",
            "template_lock_notes": "...",
            "asset_fusion_notes": "...",
            "confidence": 0.8,
        }
    return {
        "mode": "template_customize",
        "selected_case_ids": ["..."],
        "final_prompt": "...",
        "negative_prompt": "",
        "provider_parameters": {"count": 1},
        "prompt_rationale": "...",
        "confidence": 0.8,
    }


def _matches_checkpoint_schema(payload: dict[str, Any], schema: dict[str, Any]) -> bool:
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    for field in required:
        if not isinstance(field, str):
            continue
        if field not in payload:
            return False
        value = payload.get(field)
        if value is None or value == "":
            return False
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    for field, spec in properties.items():
        if field not in payload or not isinstance(spec, dict):
            continue
        allowed = spec.get("enum")
        if isinstance(allowed, list) and payload[field] not in allowed:
            return False
    return True


def _checkpoint_visual_case(item: dict[str, Any], *, tight: bool) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    visual = item.get("visual_signal_brief") if isinstance(item.get("visual_signal_brief"), dict) else {}
    return {
        "case_id": item.get("case_id"),
        "title": _truncate(_text_value(item.get("title")), 38 if tight else 48),
        "category": item.get("category"),
        "summary": _truncate(_text_value(item.get("summary")), 42 if tight else 60),
        "style_tags": (item.get("style_tags") or [])[: (1 if tight else 2)],
        "use_case_tags": (item.get("use_case_tags") or [])[:1],
        "visual_brief": _truncate(_text_value(visual.get("brief")), 70 if tight else 90),
    }


def _compact_generation_checkpoints(checkpoints: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(checkpoints, dict):
        return {}
    compact: dict[str, Any] = {}
    intent = checkpoints.get("intent")
    if isinstance(intent, dict):
        compact["intent"] = {
            "mode": intent.get("mode"),
            "primary_subject": _truncate(_text_value(intent.get("primary_subject")), 160),
            "scene_goal": _truncate(_text_value(intent.get("scene_goal")), 220),
            "must_keep": [_truncate(_text_value(item), 80) for item in (intent.get("must_keep") or [])[:6] if _text_value(item)],
            "must_avoid": [_truncate(_text_value(item), 70) for item in (intent.get("must_avoid") or [])[:4] if _text_value(item)],
        }
    visual = checkpoints.get("visual_strategy")
    if isinstance(visual, dict):
        compact["visual_strategy"] = {
            "selected_case_ids": [str(item) for item in (visual.get("selected_case_ids") or [])[:3] if str(item).strip()],
            "composition": _truncate(_text_value(visual.get("composition")), 220),
            "lighting": _truncate(_text_value(visual.get("lighting")), 140),
            "palette": _truncate(_text_value(visual.get("palette")), 140),
            "spatial_hierarchy": _truncate(_text_value(visual.get("spatial_hierarchy")), 180),
            "template_lock_notes": _truncate(_text_value(visual.get("template_lock_notes")), 120),
            "asset_fusion_notes": _truncate(_text_value(visual.get("asset_fusion_notes")), 120),
        }
    return compact


def _checkpoint_stage_instruction(stage_name: str) -> str:
    if stage_name.startswith("intent"):
        return (
            "Understand the user's concrete image goal. Output subject, scene goal, must_keep, must_avoid, "
            "asset requirements, risk notes, and confidence. Do not choose final wording yet."
        )
    if stage_name.startswith("visual_strategy") and "ultra_micro" in stage_name:
        return (
            "From the intent checkpoint only, decide one compact visual strategy: composition, lighting, palette, "
            "and spatial hierarchy. Do not compare cases, list alternatives, or write the final image prompt yet."
        )
    if stage_name.startswith("visual_strategy"):
        return (
            "Choose the reusable visual strategy: selected cases, composition, lighting, palette, hierarchy, "
            "template lock notes, and asset fusion notes. Do not write the final image prompt yet."
        )
    return (
        "Using prior checkpoints, output the final concise image prompt package for the provider. "
        "Preserve all hard request constraints while keeping visible fields short."
    )


def _compress_checkpoint_decision(
    raw: dict[str, Any],
    *,
    intent: dict[str, Any],
    visual_strategy: dict[str, Any],
    fallback: CreativeOrchestratorDecision,
) -> dict[str, Any]:
    selected_case_ids = raw.get("selected_case_ids")
    if not isinstance(selected_case_ids, list) or not selected_case_ids:
        selected_case_ids = visual_strategy.get("selected_case_ids") if isinstance(visual_strategy.get("selected_case_ids"), list) else []
    selected_case_ids = [str(item) for item in selected_case_ids if str(item).strip()]
    template_case_id = _template_case_id_from_fallback(fallback)
    if template_case_id:
        selected_case_ids = [template_case_id]
    selected_case_ids = _dedupe(selected_case_ids or fallback.selected_case_ids)[:4]

    final_prompt = _sanitize_downstream_prompt(_text_value(raw.get("final_prompt")))
    if not final_prompt:
        final_prompt = _fallback_prompt_from_checkpoints(intent=intent, visual_strategy=visual_strategy)
    negative_prompt = _text_value(raw.get("negative_prompt"))
    rationale = _text_value(raw.get("prompt_rationale")) or _text_value(visual_strategy.get("composition"))
    provider_parameters = raw.get("provider_parameters") if isinstance(raw.get("provider_parameters"), dict) else {}

    return {
        "mode": raw.get("mode") if raw.get("mode") in {"template_customize", "smart_enhance", "revision", "batch"} else fallback.mode,
        "selected_case_ids": selected_case_ids,
        "final_prompt": _truncate(final_prompt, settings.claude_final_prompt_max_chars),
        "negative_prompt": _truncate(negative_prompt, settings.claude_negative_prompt_max_chars),
        "provider_parameters": provider_parameters,
        "prompt_rationale": _truncate(rationale, settings.claude_rationale_max_chars),
        "confidence": _bounded_float(raw.get("confidence"), _bounded_float(visual_strategy.get("confidence"), 0.78)),
    }


def _visual_strategy_from_partial(
    *,
    intent: dict[str, Any],
    raw_decision: dict[str, Any],
    fallback: CreativeOrchestratorDecision,
) -> dict[str, Any]:
    selected_case_ids = raw_decision.get("selected_case_ids") if isinstance(raw_decision.get("selected_case_ids"), list) else []
    selected_case_ids = [str(item) for item in selected_case_ids if str(item).strip()]
    template_case_id = _template_case_id_from_fallback(fallback)
    if template_case_id:
        selected_case_ids = [template_case_id]
    selected_case_ids = _dedupe(selected_case_ids or fallback.selected_case_ids)[:4]
    final_prompt = _text_value(raw_decision.get("final_prompt"))
    scene_goal = _text_value(intent.get("scene_goal"))
    primary_subject = _text_value(intent.get("primary_subject"))
    must_keep = ", ".join(_text_value(item) for item in (intent.get("must_keep") or [])[:4] if _text_value(item))
    composition = _truncate(
        _sanitize_downstream_prompt(final_prompt or scene_goal or primary_subject or "Claude intent checkpoint defines the core image goal."),
        240,
    )
    if must_keep:
        composition = _truncate(f"{composition}; preserve {must_keep}", 260)
    return {
        "stage": "visual_strategy",
        "selected_case_ids": selected_case_ids,
        "composition": composition,
        "lighting": "Keep the selected template or request-compatible lighting; avoid expanding beyond the compressed Claude intent.",
        "palette": "Use a restrained palette compatible with the selected template and uploaded reference image.",
        "spatial_hierarchy": "Selected template frame first; uploaded hard-reference subject fills the replaceable subject slot.",
        "template_lock_notes": "Selected template remains the locked frame when present.",
        "asset_fusion_notes": "Hard uploaded identities remain provider input images and must not be reduced to text-only prompts.",
        "confidence": _bounded_float(raw_decision.get("confidence"), _bounded_float(intent.get("confidence"), 0.72)),
    }


def _fallback_prompt_from_checkpoints(*, intent: dict[str, Any], visual_strategy: dict[str, Any]) -> str:
    pieces = [
        _text_value(intent.get("primary_subject")),
        _text_value(intent.get("scene_goal")),
        _text_value(visual_strategy.get("composition")),
        _text_value(visual_strategy.get("lighting")),
        _text_value(visual_strategy.get("palette")),
        _text_value(visual_strategy.get("spatial_hierarchy")),
        _text_value(visual_strategy.get("asset_fusion_notes")),
    ]
    return _sanitize_downstream_prompt(", ".join(piece for piece in pieces if piece))


def _invoke_claude_file_mode(
    *,
    request: CreateCreativeRunRequest,
    fallback: CreativeOrchestratorDecision,
    candidate_cases: list[PromptCaseSummary],
    candidate_case_details: list[PromptCase],
    progress_callback: ClaudeProgressCallback | None = None,
) -> dict[str, Any] | None:
    command = _resolve_claude_command()
    if not command:
        return None
    workspace = _build_workspace(
        request=request,
        fallback=fallback,
        candidate_cases=candidate_cases,
        candidate_case_details=candidate_case_details,
    )
    if not _uses_file_tools():
        return _invoke_claude_inline_json(command=command, workspace=workspace, progress_callback=progress_callback)
    source = _claude_code_source_selection(workspace)
    prompt = _build_file_tool_prompt()
    command_line = [
        *command,
        "-p",
        "--system-prompt",
        _system_prompt(),
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(CLAUDE_INLINE_DECISION_SCHEMA, ensure_ascii=False, separators=(",", ":")),
        "--permission-mode",
        settings.claude_orchestrator_permission_mode,
        "--tools",
        settings.claude_orchestrator_tools,
        "--bare",
        "--no-session-persistence",
        "--add-dir",
        str(workspace),
    ]
    include_effort = bool(source.stage_kwargs.get("include_effort", True))
    _apply_claude_cli_acceleration_flags(command_line, include_effort=include_effort)
    if source.stage_kwargs.get("setting_sources_override"):
        command_line.extend(["--setting-sources", str(source.stage_kwargs["setting_sources_override"])])
    if source.model:
        command_line.extend(["--model", source.model])
    if settings.claude_orchestrator_fallback_model:
        command_line.extend(["--fallback-model", settings.claude_orchestrator_fallback_model])
    env = dict(os.environ)
    if source.stage_kwargs.get("strip_model_fallback_env"):
        _strip_claude_code_model_fallback_env(env)
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    env.setdefault("CLAUDE_CODE_ATTRIBUTION_HEADER", "0")
    env.setdefault("MAX_STRUCTURED_OUTPUT_RETRIES", "1")
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(settings.claude_orchestrator_max_output_tokens)
    started = time.perf_counter()
    _emit_claude_progress(
        progress_callback,
        stage="single_stage_decision",
        status="running",
        provider=source.provider,
        model=source.model,
        timeout_seconds=settings.claude_orchestrator_timeout_seconds,
        attempt=1,
    )
    try:
        completed = _run_claude_subprocess(
            command_line,
            input_text=prompt,
            timeout_seconds=settings.claude_orchestrator_timeout_seconds,
            cwd=workspace,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        _write_text(workspace / "claude_stdout.txt", _timeout_output(exc.stdout))
        _write_text(workspace / "claude_stderr.txt", _timeout_output(exc.stderr))
        _emit_claude_progress(
            progress_callback,
            stage="single_stage_decision",
            status="error",
            provider=source.provider,
            model=source.model,
            timeout_seconds=settings.claude_orchestrator_timeout_seconds,
            duration_ms=_elapsed_ms(started),
            failure_code="claude_timeout",
            attempt=1,
        )
        raise ClaudeInvocationError("claude_timeout") from exc
    _write_text(workspace / "claude_stdout.txt", completed.stdout or "")
    _write_text(workspace / "claude_stderr.txt", completed.stderr or "")
    failure = _classify_claude_failure(completed.stdout, completed.stderr, completed.returncode)
    if failure:
        _emit_claude_progress(
            progress_callback,
            stage="single_stage_decision",
            status="error",
            provider=source.provider,
            model=source.model,
            timeout_seconds=settings.claude_orchestrator_timeout_seconds,
            duration_ms=_elapsed_ms(started),
            failure_code=failure,
            attempt=1,
        )
        raise ClaudeInvocationError(failure)
    if completed.returncode != 0:
        _emit_claude_progress(
            progress_callback,
            stage="single_stage_decision",
            status="missing_decision",
            provider=source.provider,
            model=source.model,
            timeout_seconds=settings.claude_orchestrator_timeout_seconds,
            duration_ms=_elapsed_ms(started),
            failure_code="nonzero_exit",
            attempt=1,
        )
        return None
    decision = _read_claude_decision(workspace)
    if isinstance(decision, dict):
        _emit_claude_progress(
            progress_callback,
            stage="single_stage_decision",
            status="success",
            provider=source.provider,
            model=source.model,
            timeout_seconds=settings.claude_orchestrator_timeout_seconds,
            duration_ms=_elapsed_ms(started),
            attempt=1,
        )
        return decision
    parsed = _parse_json_from_text(completed.stdout or "")
    _emit_claude_progress(
        progress_callback,
        stage="single_stage_decision",
        status="success" if parsed else "missing_decision",
        provider=source.provider,
        model=source.model,
        timeout_seconds=settings.claude_orchestrator_timeout_seconds,
        duration_ms=_elapsed_ms(started),
        failure_code=None if parsed else "missing_decision",
        attempt=1,
    )
    return parsed


def _invoke_claude_file_mode_compat(
    *,
    request: CreateCreativeRunRequest,
    fallback: CreativeOrchestratorDecision,
    candidate_cases: list[PromptCaseSummary],
    candidate_case_details: list[PromptCase],
    progress_callback: ClaudeProgressCallback | None = None,
) -> dict[str, Any] | None:
    kwargs = {
        "request": request,
        "fallback": fallback,
        "candidate_cases": candidate_cases,
        "candidate_case_details": candidate_case_details,
    }
    if _callable_accepts_keyword(_invoke_claude_file_mode, "progress_callback"):
        return _invoke_claude_file_mode(**kwargs, progress_callback=progress_callback)
    provider = _claude_code_primary_provider()
    model = _claude_code_primary_model()
    _emit_claude_progress(
        progress_callback,
        stage="single_stage_decision",
        status="running",
        provider=provider,
        model=model,
        timeout_seconds=settings.claude_orchestrator_timeout_seconds,
        attempt=1,
    )
    started = time.perf_counter()
    try:
        result = _invoke_claude_file_mode(**kwargs)
    except ClaudeInvocationError as exc:
        _emit_claude_progress(
            progress_callback,
            stage="single_stage_decision",
            status="error",
            provider=provider,
            model=model,
            timeout_seconds=settings.claude_orchestrator_timeout_seconds,
            duration_ms=_elapsed_ms(started),
            failure_code=str(exc),
            attempt=1,
        )
        raise
    _emit_claude_progress(
        progress_callback,
        stage="single_stage_decision",
        status="success" if result else "missing_decision",
        provider=provider,
        model=model,
        timeout_seconds=settings.claude_orchestrator_timeout_seconds,
        duration_ms=_elapsed_ms(started),
        failure_code=None if result else "missing_decision",
        attempt=1,
    )
    return result


def _callable_accepts_keyword(func: Any, keyword: str) -> bool:
    try:
        parameters = inspect.signature(func).parameters.values()
    except (TypeError, ValueError):
        return True
    for parameter in parameters:
        if parameter.kind is inspect.Parameter.VAR_KEYWORD or parameter.name == keyword:
            return True
    return False


def _invoke_claude_inline_json(
    *,
    command: list[str],
    workspace: Path,
    progress_callback: ClaudeProgressCallback | None = None,
) -> dict[str, Any] | None:
    prompt = _build_inline_json_prompt(workspace)
    source = _claude_code_source_selection(workspace)
    include_effort = bool(source.stage_kwargs.get("include_effort", True))
    command_line = [
        *command,
        "-p",
        "--system-prompt",
        _system_prompt(),
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(CLAUDE_INLINE_DECISION_SCHEMA, ensure_ascii=False, separators=(",", ":")),
        "--permission-mode",
        settings.claude_orchestrator_permission_mode,
        "--tools",
        "none",
        "--bare",
        "--no-session-persistence",
    ]
    if include_effort:
        command_line.extend(["--effort", settings.claude_orchestrator_effort])
    _apply_claude_cli_acceleration_flags(command_line, include_effort=include_effort)
    if source.stage_kwargs.get("setting_sources_override"):
        command_line.extend(["--setting-sources", str(source.stage_kwargs["setting_sources_override"])])
    if source.model:
        command_line.extend(["--model", source.model])
    if settings.claude_orchestrator_fallback_model:
        command_line.extend(["--fallback-model", settings.claude_orchestrator_fallback_model])
    env = dict(os.environ)
    if source.stage_kwargs.get("strip_model_fallback_env"):
        _strip_claude_code_model_fallback_env(env)
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    env.setdefault("CLAUDE_CODE_ATTRIBUTION_HEADER", "0")
    env.setdefault("MAX_STRUCTURED_OUTPUT_RETRIES", "1")
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(settings.claude_orchestrator_max_output_tokens)
    started = time.perf_counter()
    _emit_claude_progress(
        progress_callback,
        stage="single_stage_decision",
        status="running",
        provider=source.provider,
        model=source.model,
        timeout_seconds=settings.claude_orchestrator_timeout_seconds,
        attempt=1,
    )
    try:
        completed = _run_claude_subprocess(
            command_line,
            input_text=prompt,
            timeout_seconds=settings.claude_orchestrator_timeout_seconds,
            cwd=workspace,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        _write_text(workspace / "claude_stdout.txt", _timeout_output(exc.stdout))
        _write_text(workspace / "claude_stderr.txt", _timeout_output(exc.stderr))
        _emit_claude_progress(
            progress_callback,
            stage="single_stage_decision",
            status="error",
            provider=source.provider,
            model=source.model,
            timeout_seconds=settings.claude_orchestrator_timeout_seconds,
            duration_ms=_elapsed_ms(started),
            failure_code="claude_timeout",
            attempt=1,
        )
        raise ClaudeInvocationError("claude_timeout") from exc
    _write_text(workspace / "claude_stdout.txt", completed.stdout or "")
    _write_text(workspace / "claude_stderr.txt", completed.stderr or "")
    failure = _classify_claude_failure(completed.stdout, completed.stderr, completed.returncode)
    if failure:
        _emit_claude_progress(
            progress_callback,
            stage="single_stage_decision",
            status="error",
            provider=source.provider,
            model=source.model,
            timeout_seconds=settings.claude_orchestrator_timeout_seconds,
            duration_ms=_elapsed_ms(started),
            failure_code=failure,
            attempt=1,
        )
        raise ClaudeInvocationError(failure)
    if completed.returncode != 0:
        _emit_claude_progress(
            progress_callback,
            stage="single_stage_decision",
            status="missing_decision",
            provider=source.provider,
            model=source.model,
            timeout_seconds=settings.claude_orchestrator_timeout_seconds,
            duration_ms=_elapsed_ms(started),
            failure_code="nonzero_exit",
            attempt=1,
        )
        return None
    decision = _parse_structured_output(completed.stdout or "")
    if isinstance(decision, dict):
        _write_json(workspace / "decision.json", decision)
        _emit_claude_progress(
            progress_callback,
            stage="single_stage_decision",
            status="success",
            provider=source.provider,
            model=source.model,
            timeout_seconds=settings.claude_orchestrator_timeout_seconds,
            duration_ms=_elapsed_ms(started),
            attempt=1,
        )
        return decision
    _emit_claude_progress(
        progress_callback,
        stage="single_stage_decision",
        status="missing_decision",
        provider=source.provider,
        model=source.model,
        timeout_seconds=settings.claude_orchestrator_timeout_seconds,
        duration_ms=_elapsed_ms(started),
        failure_code="missing_decision",
        attempt=1,
    )
    return None


def _normalize_decision(
    raw: dict[str, Any],
    *,
    fallback: CreativeOrchestratorDecision,
    fallback_retrieval_plan: CaseRetrievalPlan,
    candidate_cases: list[PromptCaseSummary],
) -> CreativeOrchestratorDecision:
    raw = _coerce_claude_decision_shape(raw)
    candidate_ids = {item.case_id for item in candidate_cases}
    selected_case_ids = [
        str(item)
        for item in raw.get("selected_case_ids", [])
        if str(item).strip() and (str(item) in candidate_ids or str(item) in fallback.selected_case_ids)
    ]
    template_case_id = _template_case_id_from_fallback(fallback)
    if template_case_id:
        selected_case_ids = [template_case_id]
    else:
        selected_case_ids = _dedupe(selected_case_ids or fallback.selected_case_ids)[: fallback_retrieval_plan.limit]
    retrieval_plan = _normalize_retrieval_plan(raw.get("case_retrieval_plan"), fallback_retrieval_plan)
    generation_directives = raw.get("generation_directives") if isinstance(raw.get("generation_directives"), dict) else {}
    provider_parameters = _normalize_provider_parameters(raw.get("provider_parameters"), generation_directives)
    provider_parameters = _apply_request_output_overrides(provider_parameters, fallback.generation_directives)
    final_prompt = _truncate(
        _sanitize_downstream_prompt(_text_value(raw.get("final_prompt")) or _text_value(generation_directives.get("prompt"))),
        settings.claude_final_prompt_max_chars,
    )
    negative_prompt = _truncate(
        _text_value(raw.get("negative_prompt")) or _text_value(generation_directives.get("negative_prompt")),
        settings.claude_negative_prompt_max_chars,
    )
    prompt_rationale = _truncate(
        _text_value(raw.get("prompt_rationale")) or _text_value(raw.get("rationale")),
        settings.claude_rationale_max_chars,
    )
    quality_gates = raw.get("quality_gates") if isinstance(raw.get("quality_gates"), dict) else {}
    return CreativeOrchestratorDecision(
        decision_id=new_id("orc"),
        provider="claude-code",
        mode=raw.get("mode") if raw.get("mode") in {"template_customize", "smart_enhance", "revision", "batch"} else fallback.mode,
        selected_case_ids=selected_case_ids,
        case_retrieval_plan=retrieval_plan,
        final_prompt=final_prompt,
        negative_prompt=negative_prompt,
        provider_parameters=provider_parameters,
        prompt_rationale=prompt_rationale,
        prompt_directives=_normalize_prompt_directives(raw.get("prompt_directives")),
        stage_commands=_normalize_stage_commands(raw.get("stage_commands")),
        generation_directives=_apply_request_output_overrides(
            {**generation_directives, **provider_parameters},
            fallback.generation_directives,
        ),
        quality_gates={**fallback.quality_gates, **quality_gates},
        confidence=_bounded_float(raw.get("confidence"), 0.78 if raw.get("selected_case_ids") else fallback.confidence),
        created_at=utc_now(),
    )


def _normalize_retrieval_plan(raw: Any, fallback: CaseRetrievalPlan) -> CaseRetrievalPlan:
    if not isinstance(raw, dict):
        return fallback
    payload = fallback.model_dump()
    for key in ["query_text", "category_filters", "use_case_filters", "style_filters", "risk_filters", "limit", "diversity_level"]:
        if key in raw:
            payload[key] = raw[key]
    try:
        return CaseRetrievalPlan.model_validate(payload)
    except Exception:
        return fallback


def _normalize_stage_commands(raw: Any) -> list[StageCommand]:
    commands: list[StageCommand] = []
    if not isinstance(raw, list):
        return commands
    for item in raw[:12]:
        if not isinstance(item, dict):
            continue
        try:
            commands.append(StageCommand.model_validate(item))
        except Exception:
            continue
    return commands


def _template_case_id_from_fallback(fallback: CreativeOrchestratorDecision) -> str | None:
    if fallback.mode != "template_customize" or not fallback.selected_case_ids:
        return None
    return fallback.selected_case_ids[0]


def _coerce_claude_decision_shape(raw: dict[str, Any]) -> dict[str, Any]:
    payload = dict(raw)
    selected_cases = payload.get("selected_cases")
    if "selected_case_ids" not in payload and isinstance(selected_cases, list):
        payload["selected_case_ids"] = [
            str(item.get("case_id"))
            for item in selected_cases
            if isinstance(item, dict) and str(item.get("case_id", "")).strip()
        ]
    generated = payload.get("generation_directives") if isinstance(payload.get("generation_directives"), dict) else {}
    if not _text_value(payload.get("final_prompt")) and _text_value(generated.get("prompt")):
        payload["final_prompt"] = _text_value(generated.get("prompt"))
    if not _text_value(payload.get("negative_prompt")) and _text_value(generated.get("negative_prompt")):
        payload["negative_prompt"] = _text_value(generated.get("negative_prompt"))
    if not isinstance(payload.get("provider_parameters"), dict):
        payload["provider_parameters"] = _normalize_provider_parameters(None, generated)
    if not isinstance(payload.get("prompt_directives"), dict):
        rationale = _selection_rationale_from_cases(selected_cases)
        prompt = _text_value(payload.get("final_prompt")) or _text_value(generated.get("prompt"))
        if prompt or rationale:
            payload["prompt_directives"] = {
                "visual_strategy": prompt,
                "case_selection_rationale": rationale,
                "reusable_prompt_atoms": [
                    value
                    for value in [
                        _text_value(generated.get("style")),
                        _text_value(generated.get("mood")),
                    ]
                    if value
                ],
                "composition": _text_value(generated.get("composition")) or None,
                "lighting": _text_value(generated.get("lighting")) or None,
                "color_palette": _text_value(generated.get("color_palette")) or None,
                "negative_prompt_additions": _split_negative_prompt(generated.get("negative_prompt")),
                "safety_notes": ["Use selected cases as abstract references only; do not copy brands, logos, or raw images."],
            }
    return payload


def _normalize_provider_parameters(raw: Any, generation_directives: dict[str, Any] | None = None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    directives = generation_directives if isinstance(generation_directives, dict) else {}
    for key in [
        "aspect_ratio",
        "count",
        "quality",
        "provider_hint",
        "output_format",
        "size",
        "background",
        "work_intensity",
    ]:
        if key in directives:
            merged[key] = directives[key]
    if isinstance(raw, dict):
        for key, value in raw.items():
            if value is not None and str(key) not in _INTERNAL_GENERATION_KEYS:
                merged[str(key)] = value
    if "count" in merged:
        try:
            merged["count"] = max(1, min(int(merged["count"]), 8))
        except Exception:
            merged.pop("count", None)
    return merged


def _apply_request_output_overrides(params: dict[str, Any], request_output: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(params or {})
    for key, value in (request_output or {}).items():
        if value is not None and str(key) not in _INTERNAL_GENERATION_KEYS:
            merged[str(key)] = value
    if "count" not in merged:
        merged["count"] = 1
    try:
        merged["count"] = max(1, min(int(merged["count"]), 8))
    except Exception:
        merged["count"] = 1
    return merged


def _provider_visible_output(output: dict[str, Any] | None) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in dict(output or {}).items()
        if str(key) not in _INTERNAL_GENERATION_KEYS
    }


def _disable_claude_cache_read(output: dict[str, Any] | None) -> bool:
    value = (output or {}).get("disable_semantic_cache")
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _prompt_transform_profile(request: CreateCreativeRunRequest, *, fallback_mode: str) -> dict[str, str]:
    output = request.output or {}
    requested = str(output.get("prompt_transform_mode") or "").strip().lower()
    v2_mode = str(request.mode_hint or fallback_mode or "").strip()
    if requested not in {"stable", "enhanced", "exploration", "original", "strict", "off"}:
        requested = _default_prompt_transform_mode(v2_mode)
        source = "v2_mode_fallback"
    else:
        source = "output.prompt_transform_mode"

    alias_map = {
        "original": "stable",
        "strict": "enhanced",
        "off": "exploration",
    }
    transform_mode = alias_map.get(requested, requested)
    fidelity_mode = {
        "stable": "original",
        "enhanced": "strict",
        "exploration": "off",
    }.get(transform_mode, "strict")
    return {
        "source": source,
        "v2_mode": v2_mode,
        "transform_mode": transform_mode,
        "fidelity_mode": fidelity_mode,
        "claude_instruction": _prompt_transform_claude_instruction(transform_mode),
    }


def _default_prompt_transform_mode(v2_mode: str) -> str:
    if v2_mode == "template_customize":
        return "stable"
    if v2_mode in {"smart_enhance", "revision", "batch"}:
        return "enhanced"
    return "enhanced"


def _prompt_transform_claude_instruction(transform_mode: str) -> str:
    if transform_mode == "stable":
        return (
            "Stable mode: preserve the selected template and user intent closely; avoid unnecessary new creative direction. "
            "Produce a clean final prompt without extra prompt-guard wrapping."
        )
    if transform_mode == "exploration":
        return (
            "Exploration mode: deliberately choose a visibly different creative path from stable mode. Vary at least one "
            "major artistic lever such as camera angle, pose, lighting mood, background depth, framing, color contrast, "
            "material atmosphere, or scene staging; make the final prompt read as an intentional creative alternative, "
            "not only a slightly richer version of the baseline. Still obey safety, selected template priority, uploaded "
            "hard references, exact required text/logo constraints, and explicit negative requirements."
        )
    return (
        "Enhanced mode: optimize the creative prompt while preserving hard constraints; emphasize exact text, logo, "
        "template lock, uploaded asset intent, composition requirements, and negative requirements so downstream generation "
        "does not weaken them."
    )


def _selection_rationale_from_cases(selected_cases: Any) -> str:
    if not isinstance(selected_cases, list):
        return ""
    notes: list[str] = []
    for item in selected_cases[:4]:
        if isinstance(item, dict):
            case_id = _text_value(item.get("case_id"))
            reason = _text_value(item.get("reason"))
            if case_id and reason:
                notes.append(f"{case_id}: {reason}")
    return "; ".join(notes)


def _split_negative_prompt(value: Any) -> list[str]:
    text = _text_value(value)
    if not text:
        return []
    return [item.strip() for item in text.replace("，", ",").split(",") if item.strip()][:8]


def _normalize_prompt_directives(raw: Any) -> PromptDirectives:
    if not isinstance(raw, dict):
        return PromptDirectives()
    payload = dict(raw)
    for key in ["visual_strategy", "case_selection_rationale", "composition", "lighting", "color_palette"]:
        if key in payload:
            payload[key] = _text_value(payload[key])
    for key in ["reusable_prompt_atoms", "negative_prompt_additions", "safety_notes"]:
        value = payload.get(key)
        if isinstance(value, list):
            payload[key] = [_text_value(item) for item in value if _text_value(item)]
        elif value:
            payload[key] = [_text_value(value)]
    try:
        return PromptDirectives.model_validate(payload)
    except Exception:
        return PromptDirectives(
            visual_strategy=_text_value(raw.get("visual_strategy")),
            case_selection_rationale=_text_value(raw.get("case_selection_rationale")),
            reusable_prompt_atoms=[],
            composition=_text_value(raw.get("composition")) or None,
            lighting=_text_value(raw.get("lighting")) or None,
            color_palette=_text_value(raw.get("color_palette")) or None,
            negative_prompt_additions=[],
            safety_notes=[],
        )


def _text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return ", ".join(_text_value(item) for item in value if _text_value(item))
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_text_value(item)}" for key, item in value.items() if _text_value(item))
    return str(value).strip()


def _sanitize_downstream_prompt(value: str) -> str:
    clean = str(value or "")
    replacements = [
        (r"\bcase_github_[a-z0-9_.-]+\b", "selected visual reference"),
        (r"\bgithub_evolinkai_[a-z0-9_.-]+\b", "curated visual reference"),
        (r"\basset_[a-z0-9_.-]+\b", "uploaded visual reference"),
        (r"\bprovider_id\b", "source"),
        (r"\bsource_url\b", "source"),
        (r"\bapi[_ -]?key\b", "credential"),
        (r"\bEvoLinkAI\b", "curated reference"),
    ]
    for pattern, replacement in replacements:
        clean = re.sub(pattern, replacement, clean, flags=re.IGNORECASE)
    return " ".join(clean.split())


def _build_workspace(
    *,
    request: CreateCreativeRunRequest,
    fallback: CreativeOrchestratorDecision,
    candidate_cases: list[PromptCaseSummary],
    candidate_case_details: list[PromptCase],
) -> Path:
    workspace = settings.claude_orchestrator_workspace_dir / fallback.decision_id
    workspace.mkdir(parents=True, exist_ok=True)
    asset_context = build_asset_context(request)
    source_selection = _select_claude_source_for_request(request=request, asset_context=asset_context)
    visual_grammar_contract = build_visual_grammar_contract(
        mode=fallback.mode,
        user_prompt=request.user_prompt,
        cases=candidate_case_details,
        asset_context=asset_context,
        orchestrator_decision=fallback,
    )
    prompt_transform_profile = _prompt_transform_profile(request, fallback_mode=fallback.mode)
    _write_json(
        workspace / "context.json",
        {
            "request": request.model_dump(mode="json"),
            "prompt_transform_profile": prompt_transform_profile,
        },
    )
    _write_json(workspace / "candidate_cases.json", [item.model_dump(mode="json") for item in candidate_cases])
    _write_json(workspace / "candidate_case_details.json", [_case_detail_for_claude(item) for item in candidate_case_details])
    _write_json(workspace / "uploaded_assets.json", asset_context.get("uploaded_assets", []))
    _write_json(workspace / "task_relationship_model.json", asset_context.get("task_relationship_model") or {})
    _write_json(workspace / "template_lock_contract.json", asset_context.get("template_lock_contract") or {})
    _write_json(workspace / "asset_binding_policy.json", asset_context.get("asset_binding_plan") or {})
    _write_json(workspace / "visual_grammar_contract.json", visual_grammar_contract or {})
    _write_json(workspace / "claude_source_selection.json", source_selection)
    _write_json(workspace / "fallback_decision.json", fallback.model_dump(mode="json"))
    _write_json(workspace / "OUTPUT_CONTRACT.json", CLAUDE_DECISION_SCHEMA)
    _write_json(workspace / "decision_template.json", _decision_template(fallback))
    _write_text(
        workspace / "MISSION.md",
        "\n".join(
            [
                "# Claude Image Creative Orchestrator Mission",
                "",
                "- 你是 Custom Media Agent 2.0 的最高层中枢大脑，不是普通检索器。",
                "- 你的任务是审美判断、案例取舍、提示词策略、生成调度和质量门禁。",
                "- 本地结构化检索只提供候选证据；最终选择和组合由你裁决。",
                "- visual_grammar_contract.json 定义视觉语法锁：模板或主锚点控制构图、主体框架、视觉层级、氛围、光影、背景密度、排版节奏和设计语言；用户控制语义内容。",
                "- 如果 context.request.template_case_id 非空，它是用户手选原型，视觉语法强锁，优先级高于自动检索、Claude 草稿和上传图布局。",
                "- 有手选原型时，selected_case_ids[0] 必须保留该 template_case_id；final_prompt 必须在该原型的视觉语法基础上替换/改写用户主体，不得只借颜色/边框。",
                "- 有手选原型时，不得把多卡片、信息图、海报版式、注释排版或复杂背景原型简化成普通单人肖像/纯背景棚拍；除非原型本身就是这种结构。",
                "- 没有手选原型时，也必须选定一个主视觉语法锚点；不要平均融合多个案例导致无主构图。辅助案例只能提供局部光影、材质、配色或行业细节。",
                "- 如果手选原型包含 typography、notes、cards、labels、feature sheet 或 infographic，negative_prompt 不要禁止 text；只禁止错误文字、乱码、品牌 logo、水印和签名。",
                "- 用户补充的感觉、用途、风格词只作为次级约束；如果与手选原型冲突，以手选原型为准。",
                "- 如果存在 uploaded_assets.json 和 asset_binding_policy.json，上传图只能作为证据和 slot 变量；有手选原型或自动锚点时，上传图不得覆盖视觉语法的构图、光影、版式、背景密度、空间层级、氛围和视觉节奏。",
                "- If task_relationship_model.json says primary_relationship=replace_template_food_subject or replace_template_subject, uploaded images are concrete replacement subjects for template slots; do not downgrade them to style signals or composite_content_source.",
                "- asset_binding_policy.json 中的 fusion_mode、placement_intent、target_surface 和 review_expectations 是硬素材意图约束；尤其是 Logo/主体/人脸/背景，不得被你改写成泛泛风格参考。",
                "- 如果上传图是成品海报、菜单、周卡、信息表、截图，或 fusion_mode=composite_content_source，只提取语义内容和硬引用；不得继承其整体网格、背景和版式；只有用户明确要求或源图确有二维码时才保留二维码/扫码位。",
                "- 如果视觉语法需要大主图、主视觉场景、信息带或留白区，而上传素材没有对应图片，你必须自动生成符合用户主题的虚拟内容补齐。",
                "- 如果 Logo 的 fusion_mode 是 logo_product_surface，必须把上传 Logo 作为真实参考图融入目标物体表面；不得输出为海报角标、页脚、水印、边框贴片或自行虚构的新 Logo。",
                "- 如果上传图是主体、Logo、人脸或必须背景，请在 final_prompt 中把它称为 uploaded reference image，并要求 provider 使用图片输入；不要只把硬约束降级为文字描述。",
                "- candidate_case_details.json 中的 visual_signal_brief 是系统提炼出的视觉 DNA，优先关注强调色、材质、光影、构图和审美方向。",
                "- 不要只迁移背景主色；如果案例有小面积但关键的金色、墨绿、玻璃高光、金属边缘或深色对比，也要判断是否应抽象迁移。",
                "- context.prompt_transform_profile 定义本次提示词转换档位：enhanced/strict 需要更强保真和硬约束保护；stable/original 需要轻整理、贴近原意；exploration/off 必须主动给出可见差异化的创意替代方案，例如改变角度、姿态、光影情绪、背景层次、裁切、色彩对比、材质氛围或场景调度中的至少一类，但仍必须服从安全、模板优先级、上传硬引用、精确文字/Logo约束和用户明确禁项。",
                "- context.request.output 若含非 auto/default 的 size/aspect_ratio，即手动画幅锁；可在该画幅内探索，但不得改写尺寸/比例。",
                "- 你必须直接输出 final_prompt、negative_prompt、provider_parameters 和 prompt_rationale。",
                "- final_prompt 是给 gpt-image-2 或兼容 ImageProvider 的最终输入，不要让下游再猜你的审美意图。",
                "- final_prompt 不得包含内部 case_id、asset_id、provider_id、source_url、API 或仓库工程标识。",
                "- 输出必须是机器可执行 JSON，写入 decision.json。",
                "- decision.json 必须简洁，建议小于 5000 字符；最多选择 4 个案例；不要输出长篇分析。",
                "- 不得要求人类中途阅读报告后再继续。",
                "- 不得绕过版权、安全和商用风险门禁。",
            ]
        ),
    )
    return workspace


def _select_claude_source_for_request(*, request: CreateCreativeRunRequest, asset_context: dict[str, Any]) -> dict[str, Any]:
    text_model = _claude_code_primary_model()
    multimodal_model = _text_value(settings.claude_orchestrator_multimodal_model)
    needs_multimodal, reason = _request_needs_multimodal_claude(request=request, asset_context=asset_context)
    selected = multimodal_model if needs_multimodal and multimodal_model else text_model
    if not selected:
        return {
            "provider": "claude-code",
            "model": None,
            "reason": "claude_default_model",
            "multimodal_requested": needs_multimodal,
        }
    return {
        "provider": _claude_code_primary_provider(selected),
        "model": selected,
        "reason": reason if needs_multimodal and selected == multimodal_model else "default_text_primary",
        "multimodal_requested": needs_multimodal,
        "default_text_model": text_model,
        "multimodal_model": multimodal_model,
    }


def _request_needs_multimodal_claude(*, request: CreateCreativeRunRequest, asset_context: dict[str, Any]) -> tuple[bool, str]:
    uploaded_assets = asset_context.get("uploaded_assets") if isinstance(asset_context.get("uploaded_assets"), list) else []
    provider_images = (
        asset_context.get("provider_input_images") if isinstance(asset_context.get("provider_input_images"), list) else []
    )
    provider_plan = asset_context.get("provider_input_plan") if isinstance(asset_context.get("provider_input_plan"), dict) else {}
    binding_plan = asset_context.get("asset_binding_plan") if isinstance(asset_context.get("asset_binding_plan"), dict) else {}
    bindings = binding_plan.get("bindings") if isinstance(binding_plan.get("bindings"), list) else []
    if not uploaded_assets and not provider_images and not bindings and not request.assets:
        return False, "no_uploaded_assets"
    if provider_plan.get("reference_image_count") or provider_plan.get("requires_image_reference"):
        return True, "provider_input_images_required"
    for item in provider_images:
        if not isinstance(item, dict):
            continue
        role = _text_value(item.get("role"))
        fusion_mode = _text_value(item.get("fusion_mode"))
        if item.get("provider_input_required") or role in _MULTIMODAL_SOURCE_ROLES or fusion_mode in _MULTIMODAL_FUSION_MODES:
            return True, "hard_reference_input_image"
    for item in bindings:
        if not isinstance(item, dict):
            continue
        role = _text_value(item.get("role"))
        fusion_mode = _text_value(item.get("fusion_mode"))
        if item.get("provider_input_required") or role in _MULTIMODAL_SOURCE_ROLES or fusion_mode in _MULTIMODAL_FUSION_MODES:
            return True, "asset_binding_requires_visual_understanding"
    prompt = request.user_prompt.lower()
    if uploaded_assets and re.search(
        r"(识别|看图|读图|图片里|图中|保留.*图|二维码|qr|文案|菜单|海报|截图|产品|logo|商标|人脸|人物|食物|菜品|优惠|价格|套餐|购买)",
        prompt,
        flags=re.IGNORECASE,
    ):
        return True, "prompt_requests_uploaded_image_understanding"
    return False, "uploaded_assets_soft_reference"


def _build_file_tool_prompt() -> str:
    return "\n".join(
        [
            "请阅读当前目录内的 MISSION.md、context.json、candidate_cases.json、candidate_case_details.json、fallback_decision.json、OUTPUT_CONTRACT.json、decision_template.json。",
            "If task_relationship_model.json exists, read it before choosing prompt strategy; it defines whether uploads replace template slots, supply semantic content, or only serve as references.",
            "如果存在 uploaded_assets.json、template_lock_contract.json、asset_binding_policy.json、visual_grammar_contract.json，也必须读取。它们定义上传图视觉摘要、模板锁合同、素材绑定 slot 和视觉语法锁。",
            "先独立判断用户真正想要的图片目标、审美方向、用途和风险，再从候选案例中选择最适合启发提示词的案例。",
            "candidate_cases.json 是轻量索引，candidate_case_details.json 包含可复用的 prompt atoms、视觉特征、visual_signal_brief 和截断后的原始提示词。",
            "visual_signal_brief 是系统预提炼的视觉 DNA：请特别判断强调色、材质、光影、构图和审美方向；不要只复用背景主色而忽略小面积但关键的点缀色或材质边缘。",
            "如果 context.json 中 request.template_case_id 非空，它是用户手选原型，必须作为最高优先级视觉语法锚点，并保留为 selected_case_ids 的第一项。",
            "有手选原型时，不要改选其他案例作为主风格；只能在手选原型基础上融合用户主体和兼容的补充要求。",
            "有手选原型时，必须迁移原型的视觉语法：主体框架、构图重心、空间层级、背景密度、排版/注释处理、主视觉强度和设计语言；不要把海报/信息图/多卡片原型改写成普通单人肖像。",
            "无手选原型时，也必须选定一个主视觉语法锚点，最多用 1-2 个辅助案例提供局部风格；不得平均融合成无主构图。",
            "有视觉语法锚点且存在上传图时，上传图只能填入 replaceable slots：主体、商品身份、Logo、人脸、文字内容、明确要求或源图确有的二维码、小道具；不得覆盖锚点的构图、光影、整体风格和视觉节奏。",
            "必须遵守 asset_binding_policy 中的 fusion_mode、placement_intent、target_surface 和 review_expectations；这些字段是上传素材的真实意图判定，不是可选说明。",
            "If task_relationship_model.primary_relationship is replace_template_food_subject or replace_template_subject, final_prompt must frame uploaded images as replacement subjects for existing template slots, not as a new layout, style reference, or composite content sheet.",
            "若 fusion_mode=composite_content_source，上传图是内容证据而不是主画面参考；不得复制它的整页布局、菜单网格、截图结构或背景密度；不得为了通用 CTA 凭空添加二维码或扫码占位。",
            "若视觉语法锚点需要关键主视觉而上传素材没有对应素材，自动生成符合用户主题的虚拟主视觉补齐。",
            "若 Logo 的 fusion_mode=logo_product_surface，final_prompt 必须要求 uploaded reference image 中的 Logo 被自然印刷/刺绣/贴附到目标物体表面，并明确禁止被放成海报下方、角标、水印或独立贴片。",
            "无手选原型时，可以灵活适配上传图和召回案例，但必须保留一个主视觉语法锚点；硬素材约束仍需要通过 provider input images 保真。",
            "没有手选原型时，你可以推翻 fallback_decision 的 selected_case_ids、prompt_directives 和 generation_directives，但必须保留安全边界。",
            "必须输出 final_prompt、negative_prompt、provider_parameters 和 prompt_rationale。final_prompt 要精简、原创、可直接用于 gpt-image-2。",
            "final_prompt 不得包含内部 case_id、asset_id、provider_id、source_url、API 或仓库工程标识。",
            "只输出必要字段；selected_case_ids 最多 4 个；每个说明字段保持 1-2 句话；不要把候选案例原文复制到 decision.json。",
            "请把最终机器可执行决策写入当前目录下文件名严格等于 decision.json 的文件，不要使用绝对路径，格式遵守 OUTPUT_CONTRACT.json。",
            "stdout 只输出 decision-ready。",
            "工作目录就是当前目录。",
        ]
    )


def _build_inline_json_prompt(workspace: Path) -> str:
    context = _read_json(workspace / "context.json") or {}
    fallback = _read_json(workspace / "fallback_decision.json") or {}
    asset_binding_policy = _read_json(workspace / "asset_binding_policy.json") or {}
    task_relationship_model = _read_json(workspace / "task_relationship_model.json") or {}
    template_lock_contract = _read_json(workspace / "template_lock_contract.json") or {}
    visual_grammar_contract = _read_json(workspace / "visual_grammar_contract.json") or {}
    uploaded_assets = _read_json_list(workspace / "uploaded_assets.json")
    template_case_id = (context.get("request") or {}).get("template_case_id")
    prompt_transform_profile = context.get("prompt_transform_profile") if isinstance(context.get("prompt_transform_profile"), dict) else {}
    fallback_selected_case_ids = fallback.get("selected_case_ids", [])
    if template_case_id:
        fallback_selected_case_ids = [template_case_id]
    payload = {
        "task": "Return one compact image prompt decision as JSON only.",
        "rules": (
            "Visual grammar lock: anchor controls composition, main visual presence, layout rhythm, hierarchy, background density, "
            "palette, lighting, mood, text/card treatment, subject relation, and design language; user/assets control semantic content. "
            "If visual_grammar_contract.mode=uploaded_frame_visual_grammar, uploaded layout/composition controls the frame and cases only supply compatible polish. "
            "Template mode: selected_case_ids=[template_case_id] only. No-template mode: choose one primary grammar anchor, not an average hybrid. Obey "
            "asset_binding_policy; hard refs stay input images. logo_product_surface means logo on target surface, never "
            "badge/watermark/sticker. composite_content_source means extract content only, do not copy uploaded layout. "
            "If task_relationship_model says replace_template_food_subject or replace_template_subject, uploads are replacement subjects for existing template slots. "
            f"If anchor needs a hero/key visual and uploads lack it, synthesize suitable virtual content. If template uses labels/cards, ban garbled text, not all text. final_prompt<={_CLAUDE_INLINE_FINAL_PROMPT_CHAR_BUDGET}; "
            f"negative<={_CLAUDE_INLINE_NEGATIVE_PROMPT_CHAR_BUDGET}; rationale<={_CLAUDE_INLINE_RATIONALE_CHAR_BUDGET}; "
            f"total JSON<={_CLAUDE_INLINE_JSON_CHAR_BUDGET}; no ids/URLs/API/brand copying. "
            f"Prompt transform: {prompt_transform_profile.get('transform_mode') or 'auto'} / "
            f"{prompt_transform_profile.get('fidelity_mode') or 'auto'}; "
            f"{prompt_transform_profile.get('claude_instruction') or ''}"
        ),
        "user_request": (context.get("request") or {}).get("user_prompt", ""),
        "template_case_id": template_case_id,
        "requested_output": _provider_visible_output((context.get("request") or {}).get("output", {})),
        "prompt_transform": prompt_transform_profile,
        "fallback": {
            "mode": fallback.get("mode"),
            "selected_case_ids": fallback_selected_case_ids[:3],
            "generation_directives": fallback.get("generation_directives"),
        },
        "template_lock_contract": _compact_template_lock(template_lock_contract),
        "visual_grammar_contract": _compact_visual_grammar_contract(visual_grammar_contract),
        "task_relationship_model": _compact_task_relationship_model(task_relationship_model),
        "uploaded_assets": _compact_uploaded_assets(uploaded_assets),
        "asset_binding_policy": _compact_asset_binding_policy(asset_binding_policy),
        "candidate_cases": _compact_inline_cases(
            _read_json_list(workspace / "candidate_cases.json"),
            _read_json_list(workspace / "candidate_case_details.json"),
            template_case_id=template_case_id,
        ),
    }
    return (
        "Return compact JSON only. final_prompt is the exact image prompt. "
        f"Total JSON <= {_CLAUDE_INLINE_JSON_CHAR_BUDGET} chars; final_prompt <= {_CLAUDE_INLINE_FINAL_PROMPT_CHAR_BUDGET} chars. "
        "Use dense visual directives. No markdown/prose/analysis/chain-of-thought/extra keys.\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def _compact_inline_cases(
    summaries: list[Any],
    details: list[Any],
    *,
    template_case_id: str | None = None,
) -> list[dict[str, Any]]:
    details_by_id = {str(item.get("case_id")): item for item in details if isinstance(item, dict)}
    compact: list[dict[str, Any]] = []
    source_items = summaries
    if template_case_id:
        source_items = [item for item in summaries if isinstance(item, dict) and str(item.get("case_id")) == template_case_id]
    for item in source_items[: (1 if template_case_id else 3)]:
        if not isinstance(item, dict):
            continue
        detail = details_by_id.get(str(item.get("case_id")), {})
        compact.append(
            {
                "case_id": item.get("case_id"),
                "title": _truncate(_text_value(item.get("title")), 52),
                "category": item.get("category"),
                "summary": _truncate(_text_value(item.get("summary")), 70 if template_case_id else 56),
                "style_tags": item.get("style_tags", [])[: (3 if template_case_id else 2)],
                "use_case_tags": item.get("use_case_tags", [])[: (3 if template_case_id else 2)],
                "prompt_atoms": {}
                if template_case_id
                else _compact_atoms(detail.get("prompt_atoms", {}) if isinstance(detail, dict) else {}),
                "raw_visual_skeleton": _compact_case_excerpt(_text_value(detail.get("raw_prompt_excerpt")), limit=300)
                if template_case_id and isinstance(detail, dict)
                else "",
                "visual_signal_brief": _compact_visual_signal_brief(
                    detail.get("visual_signal_brief", {}) if isinstance(detail, dict) else {},
                    tight=bool(template_case_id),
                ),
            }
        )
    return compact


def _compact_atoms(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    compact: dict[str, str] = {}
    for key in ["composition", "lighting", "color_palette", "mood"]:
        value = _text_value(raw.get(key))
        if value:
            compact[key] = _truncate(value, 50)
    return compact


def _compact_visual_signal_brief(raw: Any, *, tight: bool = False) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    compact: dict[str, Any] = {}
    brief = _text_value(raw.get("brief"))
    if brief:
        compact["brief"] = _truncate(brief, 90 if tight else 105)
    keys = [
        "accent_color_signals",
        "material_signals",
        "lighting_signals",
        "composition_signals",
    ]
    for key in keys:
        value = raw.get(key)
        if isinstance(value, list):
            compact[key] = [
                _truncate(_text_value(item), 32 if tight else 38)
                for item in value[:1]
                if _text_value(item)
            ]
    reusable = raw.get("reusable_principles")
    if isinstance(reusable, list):
        compact["reusable_principles"] = [
            _truncate(_text_value(item), 48 if tight else 56)
            for item in reusable[:1]
            if _text_value(item)
        ]
    return compact


def _compact_template_lock(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return {}
    return {
        "priority": raw.get("priority"),
        "locked": (raw.get("locked_elements") or [])[:4],
        "slots": (raw.get("replaceable_slots") or [])[:4],
        "policy": raw.get("conflict_policy"),
    }


def _compact_visual_grammar_contract(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return {}
    source_risk = raw.get("source_layout_risk") if isinstance(raw.get("source_layout_risk"), dict) else {}
    information_integrity = raw.get("information_integrity") if isinstance(raw.get("information_integrity"), dict) else {}
    asset_frame_strategy = raw.get("asset_frame_strategy") if isinstance(raw.get("asset_frame_strategy"), dict) else {}
    return {
        "mode": raw.get("mode"),
        "strength": raw.get("lock_strength"),
        "primary_title": _truncate(_text_value(raw.get("primary_anchor_title")), 54),
        "aux_titles": [_truncate(_text_value(item), 36) for item in (raw.get("auxiliary_case_titles") or [])[:2]],
        "locked": (raw.get("locked_visual_grammar") or [])[:6],
        "replaceable": (raw.get("replaceable_semantic_content") or [])[:5],
        "anchor": _truncate(_text_value(raw.get("anchor_directive") or raw.get("visual_signal_brief")), 240),
        "source_layout_risk": {
            "detected": bool(source_risk.get("detected")),
            "markers": (source_risk.get("markers") or [])[:5],
        },
        "info": {
            "active": bool(information_integrity.get("active")),
            "priority": information_integrity.get("priority"),
            "fields": (information_integrity.get("critical_fields") or [])[:5],
            "canvas": _truncate(_text_value(information_integrity.get("canvas_policy")), 110),
        },
        "asset_frame_strategy": {
            "mode": asset_frame_strategy.get("mode"),
            "frame_source": asset_frame_strategy.get("frame_source"),
            "uploaded_layout_may_override_case": asset_frame_strategy.get("uploaded_layout_may_override_case"),
            "content_extraction": asset_frame_strategy.get("content_extraction"),
            "reason": _truncate(_text_value(asset_frame_strategy.get("reason")), 110),
        },
        "policy": _truncate(_text_value(raw.get("conflict_policy")), 180),
    }


def _compact_task_relationship_model(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return {}
    return {
        "primary_relationship": raw.get("primary_relationship"),
        "frame_owner": raw.get("frame_owner"),
        "uploaded_asset_role": raw.get("uploaded_asset_role"),
        "target_surface": raw.get("target_surface"),
        "target_label": raw.get("target_label"),
        "asset_count": raw.get("uploaded_asset_count"),
        "content_extraction": bool(raw.get("content_extraction")),
        "template_slot_replacement": bool(raw.get("template_slot_replacement")),
        "provider_input_priority": raw.get("provider_input_priority"),
        "review": (raw.get("review_expectations") or [])[:3],
        "directive": _truncate(_text_value(raw.get("prompt_directive")), 180),
    }


def _compact_uploaded_assets(raw: list[Any]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        brief = item.get("brief") if isinstance(item.get("brief"), dict) else {}
        compact.append(
            {
                "role": item.get("role"),
                "constraint_strength": item.get("constraint_strength"),
                "status": item.get("status"),
                "visual_summary": _truncate(_text_value(brief.get("visual_summary")), 90),
                "identity_requirements": (brief.get("identity_requirements") or [])[:2],
                "style_signals": (brief.get("style_signals") or [])[:2],
                "provider_input_required": brief.get("provider_input_required"),
            }
        )
    return compact


def _compact_asset_binding_policy(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    bindings: list[dict[str, Any]] = []
    template_mode = raw.get("mode") == "template_lock"
    for item in (raw.get("bindings") or [])[: (3 if template_mode else 5)]:
        if not isinstance(item, dict):
            continue
        binding: dict[str, Any] = {
            "role": item.get("role"),
            "strength": item.get("constraint_strength"),
            "slot": item.get("binding_slot"),
            "fusion": item.get("fusion_mode"),
            "placement": _compact_placement_intent(item.get("placement_intent")),
            "surface": item.get("target_surface"),
            "input_required": item.get("provider_input_required"),
            "review": (item.get("review_expectations") or [])[:2],
        }
        if not template_mode:
            binding["allowed"] = (item.get("allowed_to_override") or [])[:2]
            binding["blocked"] = (item.get("not_allowed_to_override") or [])[:3]
            binding["conflict"] = _truncate(_text_value(item.get("conflict_resolution")), 70)
        bindings.append(binding)
    return {
        "mode": raw.get("mode"),
        "bindings": bindings,
        "conflicts": (raw.get("conflicts") or [])[: (1 if template_mode else 3)],
        "provider_input_plan": _compact_provider_input_plan(raw.get("provider_input_plan")),
    }


def _compact_placement_intent(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "mode": raw.get("mode"),
        "target_surface": raw.get("target_surface"),
        "target_label": raw.get("target_label"),
        "source": raw.get("source"),
        "instruction": _truncate(_text_value(raw.get("instruction")), 55),
    }


def _compact_provider_input_plan(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "operation": raw.get("operation"),
        "reference_count": raw.get("reference_image_count"),
        "requires_reference": raw.get("requires_image_reference"),
        "fusion_modes": (raw.get("fusion_modes") or [])[:3],
        "review": (raw.get("review_expectations") or [])[:2],
    }


def _compact_case_excerpt(value: str, *, limit: int) -> str:
    clean = _text_value(value)
    if not clean:
        return ""
    markers = [
        "background",
        "floor",
        "reflect",
        "typography",
        "composition",
        "centered",
        "oversized",
        "giant",
        "model",
        "leaning",
        "lighting",
        "poster",
        "card",
        "annotation",
    ]
    sentences = re.split(r"(?<=[.!?。！？])\s+", clean)
    picked: list[str] = []
    for sentence in sentences:
        compact = _sanitize_case_excerpt_sentence(sentence)
        lowered = compact.lower()
        if compact and any(marker in lowered for marker in markers):
            picked.append(compact)
        if len(picked) >= 4:
            break
    if picked:
        clean = " ".join(picked)
    else:
        clean = _sanitize_case_excerpt_sentence(clean)
    return _truncate(clean, limit)


def _sanitize_case_excerpt_sentence(value: str) -> str:
    clean = _text_value(value)
    if not clean:
        return ""
    clean = re.sub(r"[\"“”][^\"“”]{1,90}[\"“”]", "campaign copy", clean)
    clean = re.sub(r"\b[A-Z][A-Z0-9]{3,}(?:\s+[A-Z0-9]{2,}){0,4}\b", "campaign text", clean)
    clean = re.sub(r"\{argument[^{}]*\}", "requested variant", clean)
    return _truncate(clean, 220)


def _system_prompt() -> str:
    return (
        "You are the highest-level creative orchestration brain for a custom image generation agent. "
        "Return only compact executable JSON matching the schema. No markdown, explanations, analysis, "
        f"chain-of-thought, or extra keys. Keep total JSON under {_CLAUDE_INLINE_JSON_CHAR_BUDGET} characters."
    )


def _case_detail_for_claude(case: PromptCase) -> dict[str, Any]:
    visual_signals = build_case_visual_signals(case)
    return {
        "case_id": case.case_id,
        "title": case.title,
        "category": case.category,
        "summary": case.summary,
        "style_tags": case.style_tags,
        "use_case_tags": case.use_case_tags,
        "risk_tags": case.risk_tags,
        "prompt_atoms": case.prompt_atoms,
        "visual_features": case.visual_features,
        "visual_signal_brief": visual_signals.as_dict(),
        "quality_score": case.quality_score,
        "license_policy": case.license_policy.model_dump(mode="json"),
        "raw_prompt_excerpt": _truncate(case.raw_prompt, 900),
    }


def _decision_template(fallback: CreativeOrchestratorDecision) -> dict[str, Any]:
    return {
        "mode": fallback.mode,
        "selected_case_ids": fallback.selected_case_ids,
        "case_retrieval_plan": fallback.case_retrieval_plan.model_dump(),
        "final_prompt": "",
        "negative_prompt": "",
        "provider_parameters": {
            "aspect_ratio": fallback.generation_directives.get("aspect_ratio"),
            "count": fallback.generation_directives.get("count"),
            "quality": fallback.generation_directives.get("quality"),
            "provider_hint": fallback.generation_directives.get("provider_hint"),
        },
        "prompt_rationale": "",
        "prompt_directives": {
            "visual_strategy": "",
            "case_selection_rationale": "",
            "reusable_prompt_atoms": [],
            "composition": "",
            "lighting": "",
            "color_palette": "",
            "negative_prompt_additions": [],
            "safety_notes": [],
        },
        "stage_commands": [item.model_dump() for item in fallback.stage_commands],
        "generation_directives": fallback.generation_directives,
        "quality_gates": fallback.quality_gates,
        "confidence": fallback.confidence,
    }


def _resolve_claude_command() -> list[str] | None:
    configured = str(settings.claude_orchestrator_cli or "claude").strip()
    if not configured:
        return None
    resolved = None
    if os.name == "nt" and Path(configured).suffix.lower() not in {".cmd", ".exe", ".bat", ".ps1"}:
        resolved = shutil.which(f"{configured}.cmd") or shutil.which(f"{configured}.exe")
    resolved = resolved or shutil.which(configured)
    if resolved:
        return [resolved]
    if Path(configured).exists():
        return [configured]
    return None


def _apply_claude_cli_acceleration_flags(command_line: list[str], *, include_effort: bool = True) -> None:
    if include_effort and "--effort" not in command_line:
        command_line.extend(["--effort", settings.claude_orchestrator_effort])
    if settings.claude_orchestrator_disable_slash_commands and "--disable-slash-commands" not in command_line:
        command_line.append("--disable-slash-commands")


def _parse_json_from_text(text: str) -> dict[str, Any] | None:
    cleaned = str(text or "").strip()
    if not cleaned:
        return None
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def _classify_claude_failure(stdout: str | None, stderr: str | None, returncode: int) -> str | None:
    if returncode == 0 and _has_successful_structured_result(stdout):
        return None
    text = f"{stdout or ''}\n{stderr or ''}".lower()
    if "reasoning" in text and ("not supported" in text or "not valid" in text):
        return "claude_reasoning_not_supported"
    if "usage policy" in text or '"stop_reason":"refusal"' in text or '"stop_reason": "refusal"' in text:
        return "claude_policy_refusal"
    if ("context canceled" in text or "context deadline exceeded" in text) and ("kimi" in text or "api.kimi.com" in text):
        return "kimi_context_canceled"
    if "context canceled" in text:
        return "upstream_context_canceled"
    if "no available accounts" in text or ("api_error_status" in text and "503" in text and "available" in text):
        return "kimi_no_available_accounts"
    if "api.kimi.com" in text:
        return "kimi_upstream_error"
    if "502" in text and ("kimi" in text or "sub2api" in text):
        return "kimi_sub2api_502"
    if (
        "output token maximum" in text
        or "max_output_tokens" in text
        or "claude_code_max_output_tokens" in text
        or "response exceeded" in text and "output token" in text
    ):
        return "claude_output_token_limit"
    if "error_max_structured_output_retries" in text or "failed to provide valid structured output" in text:
        return "claude_structured_output_retries_exhausted"
    if "api error" in text:
        return "claude_api_error"
    if returncode != 0:
        return f"claude_cli_exit_{returncode}"
    return None


def _has_successful_structured_result(stdout: str | None) -> bool:
    try:
        parsed = json.loads(str(stdout or "").strip())
    except Exception:
        return False
    if not isinstance(parsed, dict):
        return False
    if parsed.get("type") == "result" and parsed.get("is_error") is False:
        structured = parsed.get("structured_output")
        if isinstance(structured, dict):
            return True
        result = parsed.get("result")
        return isinstance(result, str) and isinstance(_parse_json_from_text(result), dict)
    return False


def _timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _parse_structured_output(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(str(text or "").strip())
    except Exception:
        return _parse_json_from_text(text)
    if isinstance(parsed, dict):
        structured = parsed.get("structured_output")
        if isinstance(structured, dict):
            return structured
        result = parsed.get("result")
        if isinstance(result, str):
            return _parse_json_from_text(result)
        return parsed
    return None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _read_json_list(path: Path) -> list[Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _read_claude_decision(workspace: Path) -> dict[str, Any] | None:
    direct = _read_json(workspace / "decision.json")
    if direct:
        return direct
    ignored = {"fallback_decision.json", "decision_template.json", "OUTPUT_CONTRACT.json"}
    for path in sorted(workspace.glob("*decision.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.name in ignored:
            continue
        parsed = _read_json(path)
        if parsed:
            return parsed
    return None


def _cache_key(
    *,
    request: CreateCreativeRunRequest,
    fallback_mode: str,
    fallback_retrieval_plan: CaseRetrievalPlan,
    candidate_cases: list[PromptCaseSummary],
) -> str:
    payload = {
        "cache_schema": _CLAUDE_DECISION_CACHE_SCHEMA,
        "user_prompt": request.user_prompt,
        "mode_hint": request.mode_hint,
        "prompt_transform": _prompt_transform_profile(request, fallback_mode=fallback_mode),
        "template_case_id": request.template_case_id,
        "assets": _request_assets_for_cache(request),
        "output": _provider_visible_output(request.output),
        "fallback_mode": fallback_mode,
        "retrieval_plan": fallback_retrieval_plan.model_dump(mode="json"),
        "candidate_case_ids": [item.case_id for item in candidate_cases[:8]],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _read_cached_decision(cache_key: str) -> dict[str, Any] | None:
    if not settings.claude_orchestrator_cache_enabled:
        return None
    cache = _read_cache_store()
    cached = cache.get(cache_key)
    return _cached_decision_payload(cached)


def _read_semantic_cached_decision(metadata: dict[str, Any]) -> tuple[str, dict[str, Any], float] | None:
    if not settings.claude_orchestrator_cache_enabled or not settings.claude_orchestrator_semantic_cache_enabled:
        return None
    cache = _read_cache_store()
    best: tuple[str, dict[str, Any], float] | None = None
    for cached_key, entry in cache.items():
        if not isinstance(cached_key, str) or not isinstance(entry, dict):
            continue
        cached_metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else None
        cached_decision = _cached_decision_payload(entry)
        if not cached_metadata or not cached_decision:
            continue
        score = _semantic_cache_score(metadata, cached_metadata)
        if score < settings.claude_orchestrator_semantic_cache_threshold:
            continue
        if best is None or score > best[2]:
            best = (cached_key, cached_decision, score)
    return best


def _write_cached_decision(cache_key: str, raw_decision: dict[str, Any], *, metadata: dict[str, Any]) -> None:
    if not settings.claude_orchestrator_cache_enabled:
        return
    cache = _read_cache_store()
    cache[cache_key] = {
        "cache_schema": _CLAUDE_DECISION_CACHE_SCHEMA,
        "created_at": utc_now().isoformat(),
        "metadata": metadata,
        "decision": raw_decision,
    }
    try:
        settings.claude_orchestrator_cache_path.parent.mkdir(parents=True, exist_ok=True)
        settings.claude_orchestrator_cache_path.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        return


def _read_cache_store() -> dict[str, Any]:
    if not settings.claude_orchestrator_cache_path.exists():
        return {}
    try:
        parsed = json.loads(settings.claude_orchestrator_cache_path.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _cached_decision_payload(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    decision = entry.get("decision")
    if isinstance(decision, dict):
        return decision
    if "mode" in entry or "selected_case_ids" in entry or "final_prompt" in entry or "prompt_directives" in entry:
        return entry
    return None


def _cache_metadata(
    *,
    request: CreateCreativeRunRequest,
    fallback_mode: str,
    candidate_cases: list[PromptCaseSummary],
) -> dict[str, Any]:
    normalized_prompt = _normalize_prompt_for_cache(request.user_prompt)
    tokens = sorted(_prompt_cache_tokens(normalized_prompt))
    output = request.output or {}
    output_signature = {
        key: output.get(key)
        for key in ("aspect_ratio", "size", "count", "quality", "provider_hint")
        if output.get(key) not in (None, "", "auto", "default")
    }
    prompt_transform_profile = _prompt_transform_profile(request, fallback_mode=fallback_mode)
    return {
        "cache_schema": _CLAUDE_DECISION_CACHE_SCHEMA,
        "normalized_user_prompt": normalized_prompt,
        "prompt_tokens": tokens,
        "mode": request.mode_hint or fallback_mode,
        "prompt_transform": {
            "transform_mode": prompt_transform_profile["transform_mode"],
            "fidelity_mode": prompt_transform_profile["fidelity_mode"],
        },
        "template_case_id": request.template_case_id or "",
        "output_signature": output_signature,
        "assets": _request_assets_for_cache(request),
        "candidate_case_ids": [item.case_id for item in candidate_cases[:4]],
    }


def _request_assets_for_cache(request: CreateCreativeRunRequest) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for item in request.assets or []:
        if isinstance(item, str):
            assets.append(_asset_cache_payload(item))
        elif hasattr(item, "model_dump"):
            payload = item.model_dump(mode="json")
            assets.append(_asset_cache_payload(
                str(payload.get("asset_id") or ""),
                role=payload.get("role"),
                constraint_strength=payload.get("constraint_strength"),
            ))
    return assets


def _asset_cache_payload(asset_id: str, *, role: str | None = None, constraint_strength: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "asset_id": asset_id,
        "role": role,
        "constraint_strength": constraint_strength,
    }
    if not asset_id:
        return payload
    asset = get_uploaded_asset(asset_id)
    if not asset:
        return payload
    brief = asset.brief
    payload.update(
        {
            "status": asset.status,
            "updated_at": asset.updated_at.isoformat(),
            "size_bytes": asset.size_bytes,
            "mime_type": asset.mime_type,
            "asset_role": asset.role,
            "asset_constraint_strength": asset.constraint_strength,
            "brief_role": brief.role if brief else None,
            "brief_summary": (brief.visual_summary if brief else "")[:320],
            "provider_input_required": brief.provider_input_required if brief else None,
        }
    )
    return payload


def _semantic_cache_score(current: dict[str, Any], cached: dict[str, Any]) -> float:
    for key in ["cache_schema", "mode", "prompt_transform", "template_case_id", "output_signature", "assets"]:
        if current.get(key) != cached.get(key):
            return 0.0
    current_cases = [str(item) for item in current.get("candidate_case_ids", []) if str(item)]
    cached_cases = [str(item) for item in cached.get("candidate_case_ids", []) if str(item)]
    if current_cases and cached_cases:
        overlap = len(set(current_cases[:3]) & set(cached_cases[:3]))
        required = min(2, len(current_cases[:3]), len(cached_cases[:3]))
        if overlap < required:
            return 0.0
    current_tokens = set(current.get("prompt_tokens", []))
    cached_tokens = set(cached.get("prompt_tokens", []))
    if not current_tokens or not cached_tokens:
        return 0.0
    intersection = len(current_tokens & cached_tokens)
    union = len(current_tokens | cached_tokens)
    return intersection / max(1, union)


def _normalize_prompt_for_cache(prompt: str) -> str:
    lowered = str(prompt or "").lower().strip()
    punctuation = "，。！？、；：,.!?;:()（）[]【】{}<>《》\"'`~@#$%^&*_+=|\\/—-"
    table = str.maketrans({char: " " for char in punctuation})
    return " ".join(lowered.translate(table).split())


def _prompt_cache_tokens(normalized_prompt: str) -> set[str]:
    tokens: set[str] = set()
    for raw in normalized_prompt.split():
        token = raw.strip()
        if not token:
            continue
        if any("\u4e00" <= char <= "\u9fff" for char in token):
            tokens.update(_cjk_ngrams(token))
        elif len(token) >= 3:
            tokens.add(token)
    return tokens


def _cjk_ngrams(text: str) -> set[str]:
    chars = [char for char in text if "\u4e00" <= char <= "\u9fff"]
    if len(chars) <= 1:
        return set(chars)
    grams = {"".join(chars[index : index + 2]) for index in range(len(chars) - 1)}
    if len(chars) >= 3:
        grams.update("".join(chars[index : index + 3]) for index in range(len(chars) - 2))
    return grams


def _record_invocation(decision: CreativeOrchestratorDecision) -> None:
    record = OrchestratorInvocationRecord(
        invocation_id=new_id("orc_call"),
        provider=decision.provider,
        status=decision.invocation_status,
        fallback_reason=decision.fallback_reason,
        latency_ms=decision.latency_ms,
        attempts=decision.attempts,
        cache_hit=decision.cache_hit,
        cache_key=decision.cache_key,
        workspace_id=decision.workspace_id,
        selected_case_ids=decision.selected_case_ids,
        created_at=decision.created_at,
    )
    _RECENT_INVOCATIONS.insert(0, record)
    del _RECENT_INVOCATIONS[_MAX_RECENT_INVOCATIONS:]


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _uses_file_tools() -> bool:
    configured = str(settings.claude_orchestrator_tools or "").strip().lower()
    return configured not in {"", "none", "false", "off", "0"}


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _truncate(text: str, limit: int) -> str:
    clean = str(text or "")
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _bounded_float(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        return fallback
    return max(0.0, min(1.0, parsed))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique
