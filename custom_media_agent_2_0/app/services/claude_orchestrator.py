from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import hashlib
import time
from pathlib import Path
from typing import Any

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


_RECENT_INVOCATIONS: list[OrchestratorInvocationRecord] = []
_MAX_RECENT_INVOCATIONS = 30
_NON_RETRYABLE_CLAUDE_FAILURES = {"claude_output_token_limit", "claude_timeout"}
_CLAUDE_DECISION_CACHE_SCHEMA = "claude_decision_v7_compact_output_budget"
_CLAUDE_INLINE_JSON_CHAR_BUDGET = 1500
_CLAUDE_INLINE_FINAL_PROMPT_CHAR_BUDGET = 1100
_CLAUDE_INLINE_NEGATIVE_PROMPT_CHAR_BUDGET = 240
_CLAUDE_INLINE_RATIONALE_CHAR_BUDGET = 140


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


def orchestrate_creative_request(
    *,
    request: CreateCreativeRunRequest,
    fallback_mode: str,
    fallback_retrieval_plan: CaseRetrievalPlan,
    candidate_cases: list[PromptCaseSummary],
    candidate_case_details: list[PromptCase] | None = None,
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

    cached_raw_decision = _read_cached_decision(cache_key)
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

    semantic_cached = _read_semantic_cached_decision(cache_metadata)
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

    attempts = max(1, settings.claude_orchestrator_max_attempts)
    errors: list[str] = []
    raw_decision: dict[str, Any] | None = None
    used_attempts = 0
    for attempt in range(1, attempts + 1):
        used_attempts = attempt
        try:
            raw_decision = _invoke_claude_file_mode(
                request=request,
                fallback=fallback,
                candidate_cases=candidate_cases,
                candidate_case_details=candidate_case_details or [],
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
    success_records = [item for item in recent if item.status in {"success", "cache_hit", "semantic_cache_hit"}]
    failure_records = [item for item in recent if item.status in {"fallback", "error"}]
    latency_values = [item.latency_ms for item in recent if isinstance(item.latency_ms, int)]
    return OrchestratorStatusResponse(
        enabled=settings.claude_orchestrator_enabled,
        cli=settings.claude_orchestrator_cli,
        model=settings.claude_orchestrator_model,
        tools=settings.claude_orchestrator_tools,
        fallback_model=settings.claude_orchestrator_fallback_model,
        cache_enabled=settings.claude_orchestrator_cache_enabled,
        cache_entries=len(cache),
        max_attempts=settings.claude_orchestrator_max_attempts,
        timeout_seconds=settings.claude_orchestrator_timeout_seconds,
        max_output_tokens=settings.claude_orchestrator_max_output_tokens,
        recent_invocations=recent[:10],
        last_success_at=success_records[0].created_at if success_records else None,
        last_failure_at=failure_records[0].created_at if failure_records else None,
        average_latency_ms=int(sum(latency_values) / len(latency_values)) if latency_values else None,
    )


def reset_orchestrator_observability() -> None:
    _RECENT_INVOCATIONS.clear()


def _invoke_claude_file_mode(
    *,
    request: CreateCreativeRunRequest,
    fallback: CreativeOrchestratorDecision,
    candidate_cases: list[PromptCaseSummary],
    candidate_case_details: list[PromptCase],
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
        return _invoke_claude_inline_json(command=command, workspace=workspace)
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
    _apply_claude_cli_acceleration_flags(command_line)
    if settings.claude_orchestrator_model:
        command_line.extend(["--model", settings.claude_orchestrator_model])
    if settings.claude_orchestrator_fallback_model:
        command_line.extend(["--fallback-model", settings.claude_orchestrator_fallback_model])
    env = dict(os.environ)
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    env.setdefault("CLAUDE_CODE_ATTRIBUTION_HEADER", "0")
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(settings.claude_orchestrator_max_output_tokens)
    try:
        completed = subprocess.run(
            command_line,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings.claude_orchestrator_timeout_seconds,
            check=False,
            cwd=str(workspace),
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        _write_text(workspace / "claude_stdout.txt", _timeout_output(exc.stdout))
        _write_text(workspace / "claude_stderr.txt", _timeout_output(exc.stderr))
        raise ClaudeInvocationError("claude_timeout") from exc
    _write_text(workspace / "claude_stdout.txt", completed.stdout or "")
    _write_text(workspace / "claude_stderr.txt", completed.stderr or "")
    failure = _classify_claude_failure(completed.stdout, completed.stderr, completed.returncode)
    if failure:
        raise ClaudeInvocationError(failure)
    if completed.returncode != 0:
        return None
    decision = _read_claude_decision(workspace)
    if isinstance(decision, dict):
        return decision
    return _parse_json_from_text(completed.stdout or "")


def _invoke_claude_inline_json(*, command: list[str], workspace: Path) -> dict[str, Any] | None:
    prompt = _build_inline_json_prompt(workspace)
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
        "--effort",
        settings.claude_orchestrator_effort,
        "--bare",
        "--no-session-persistence",
    ]
    _apply_claude_cli_acceleration_flags(command_line)
    if settings.claude_orchestrator_model:
        command_line.extend(["--model", settings.claude_orchestrator_model])
    if settings.claude_orchestrator_fallback_model:
        command_line.extend(["--fallback-model", settings.claude_orchestrator_fallback_model])
    env = dict(os.environ)
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    env.setdefault("CLAUDE_CODE_ATTRIBUTION_HEADER", "0")
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(settings.claude_orchestrator_max_output_tokens)
    try:
        completed = subprocess.run(
            command_line,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings.claude_orchestrator_timeout_seconds,
            check=False,
            cwd=str(workspace),
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        _write_text(workspace / "claude_stdout.txt", _timeout_output(exc.stdout))
        _write_text(workspace / "claude_stderr.txt", _timeout_output(exc.stderr))
        raise ClaudeInvocationError("claude_timeout") from exc
    _write_text(workspace / "claude_stdout.txt", completed.stdout or "")
    _write_text(workspace / "claude_stderr.txt", completed.stderr or "")
    failure = _classify_claude_failure(completed.stdout, completed.stderr, completed.returncode)
    if failure:
        raise ClaudeInvocationError(failure)
    if completed.returncode != 0:
        return None
    decision = _parse_structured_output(completed.stdout or "")
    if isinstance(decision, dict):
        _write_json(workspace / "decision.json", decision)
        return decision
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
    final_prompt = _truncate(
        _sanitize_downstream_prompt(_text_value(raw.get("final_prompt")) or _text_value(generation_directives.get("prompt"))),
        1600,
    )
    negative_prompt = _truncate(
        _text_value(raw.get("negative_prompt")) or _text_value(generation_directives.get("negative_prompt")),
        420,
    )
    prompt_rationale = _truncate(
        _text_value(raw.get("prompt_rationale")) or _text_value(raw.get("rationale")),
        220,
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
        generation_directives={**fallback.generation_directives, **generation_directives, **provider_parameters},
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
            if value is not None:
                merged[str(key)] = value
    if "count" in merged:
        try:
            merged["count"] = max(1, min(int(merged["count"]), 8))
        except Exception:
            merged.pop("count", None)
    return merged


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
    _write_json(workspace / "context.json", {"request": request.model_dump(mode="json")})
    _write_json(workspace / "candidate_cases.json", [item.model_dump(mode="json") for item in candidate_cases])
    _write_json(workspace / "candidate_case_details.json", [_case_detail_for_claude(item) for item in candidate_case_details])
    _write_json(workspace / "uploaded_assets.json", asset_context.get("uploaded_assets", []))
    _write_json(workspace / "template_lock_contract.json", asset_context.get("template_lock_contract") or {})
    _write_json(workspace / "asset_binding_policy.json", asset_context.get("asset_binding_plan") or {})
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
                "- 如果 context.request.template_case_id 非空，它是用户手选原型，优先级高于自动检索和补充风格。",
                "- 有手选原型时，selected_case_ids[0] 必须保留该 template_case_id；final_prompt 必须在该原型的构图、背景、色彩、氛围、版式和主体关系基础上替换/改写用户主体。",
                "- 有手选原型时，不得把多卡片、信息图、海报版式、注释排版或复杂背景原型简化成普通单人肖像/纯背景棚拍；除非原型本身就是这种结构。",
                "- 如果手选原型包含 typography、notes、cards、labels、feature sheet 或 infographic，negative_prompt 不要禁止 text；只禁止错误文字、乱码、品牌 logo、水印和签名。",
                "- 用户补充的感觉、用途、风格词只作为次级约束；如果与手选原型冲突，以手选原型为准。",
                "- 如果存在 uploaded_assets.json 和 asset_binding_policy.json，上传图只能作为证据和模板 slot 变量；有手选原型时，上传图不得覆盖原型构图、光影、版式、背景密度、空间层级、氛围和视觉节奏。",
                "- asset_binding_policy.json 中的 fusion_mode、placement_intent、target_surface 和 review_expectations 是硬素材意图约束；尤其是 Logo/主体/人脸/背景，不得被你改写成泛泛风格参考。",
                "- 如果 Logo 的 fusion_mode 是 logo_product_surface，必须把上传 Logo 作为真实参考图融入目标物体表面；不得输出为海报角标、页脚、水印、边框贴片或自行虚构的新 Logo。",
                "- 如果上传图是主体、Logo、人脸或必须背景，请在 final_prompt 中把它称为 uploaded reference image，并要求 provider 使用图片输入；不要只把硬约束降级为文字描述。",
                "- candidate_case_details.json 中的 visual_signal_brief 是系统提炼出的视觉 DNA，优先关注强调色、材质、光影、构图和审美方向。",
                "- 不要只迁移背景主色；如果案例有小面积但关键的金色、墨绿、玻璃高光、金属边缘或深色对比，也要判断是否应抽象迁移。",
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


def _build_file_tool_prompt() -> str:
    return "\n".join(
        [
            "请阅读当前目录内的 MISSION.md、context.json、candidate_cases.json、candidate_case_details.json、fallback_decision.json、OUTPUT_CONTRACT.json、decision_template.json。",
            "如果存在 uploaded_assets.json、template_lock_contract.json、asset_binding_policy.json，也必须读取。它们定义上传图视觉摘要、模板锁合同和素材绑定 slot。",
            "先独立判断用户真正想要的图片目标、审美方向、用途和风险，再从候选案例中选择最适合启发提示词的案例。",
            "candidate_cases.json 是轻量索引，candidate_case_details.json 包含可复用的 prompt atoms、视觉特征、visual_signal_brief 和截断后的原始提示词。",
            "visual_signal_brief 是系统预提炼的视觉 DNA：请特别判断强调色、材质、光影、构图和审美方向；不要只复用背景主色而忽略小面积但关键的点缀色或材质边缘。",
            "如果 context.json 中 request.template_case_id 非空，它是用户手选原型，必须作为最高优先级视觉锚点，并保留为 selected_case_ids 的第一项。",
            "有手选原型时，不要改选其他案例作为主风格；只能在手选原型基础上融合用户主体和兼容的补充要求。",
            "有手选原型时，必须迁移原型的版式结构、空间层级、背景密度、排版/注释处理和主体位置；不要把海报/信息图/多卡片原型改写成普通单人肖像。",
            "有手选原型且存在上传图时，上传图只能填入 replaceable slots：主体、商品身份、Logo、人脸、文字内容或小道具；不得覆盖模板的构图、光影、整体风格和视觉节奏。",
            "必须遵守 asset_binding_policy 中的 fusion_mode、placement_intent、target_surface 和 review_expectations；这些字段是上传素材的真实意图判定，不是可选说明。",
            "若 Logo 的 fusion_mode=logo_product_surface，final_prompt 必须要求 uploaded reference image 中的 Logo 被自然印刷/刺绣/贴附到目标物体表面，并明确禁止被放成海报下方、角标、水印或独立贴片。",
            "无手选原型时，可以自由融合上传图和召回案例，但硬素材约束仍需要通过 provider input images 保真。",
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
    template_lock_contract = _read_json(workspace / "template_lock_contract.json") or {}
    uploaded_assets = _read_json_list(workspace / "uploaded_assets.json")
    template_case_id = (context.get("request") or {}).get("template_case_id")
    fallback_selected_case_ids = fallback.get("selected_case_ids", [])
    if template_case_id:
        fallback_selected_case_ids = [template_case_id]
    payload = {
        "task": "Return one compact image prompt decision as JSON only.",
        "rules": (
            "Template mode: selected_case_ids=[template_case_id] only. Template controls composition, layout, background, "
            "palette, lighting, mood, text/card treatment, hierarchy, subject relation. User/assets fill slots only. Obey "
            "asset_binding_policy; hard refs stay input images. logo_product_surface means logo on target surface, never "
            f"badge/watermark/sticker. If template uses labels/cards, ban garbled text, not all text. final_prompt<={_CLAUDE_INLINE_FINAL_PROMPT_CHAR_BUDGET}; "
            f"negative<={_CLAUDE_INLINE_NEGATIVE_PROMPT_CHAR_BUDGET}; rationale<={_CLAUDE_INLINE_RATIONALE_CHAR_BUDGET}; "
            f"total JSON<={_CLAUDE_INLINE_JSON_CHAR_BUDGET}; no ids/URLs/API/brand copying."
        ),
        "user_request": (context.get("request") or {}).get("user_prompt", ""),
        "template_case_id": template_case_id,
        "requested_output": (context.get("request") or {}).get("output", {}),
        "fallback": {
            "mode": fallback.get("mode"),
            "selected_case_ids": fallback_selected_case_ids[:3],
            "generation_directives": fallback.get("generation_directives"),
        },
        "template_lock_contract": _compact_template_lock(template_lock_contract),
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
    resolved = shutil.which(configured)
    if not resolved and os.name == "nt" and Path(configured).suffix.lower() not in {".cmd", ".exe", ".bat", ".ps1"}:
        resolved = shutil.which(f"{configured}.cmd") or shutil.which(f"{configured}.exe")
    if resolved:
        return [resolved]
    if Path(configured).exists():
        return [configured]
    return None


def _apply_claude_cli_acceleration_flags(command_line: list[str]) -> None:
    if "--effort" not in command_line:
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
    text = f"{stdout or ''}\n{stderr or ''}".lower()
    if ("context canceled" in text or "context deadline exceeded" in text) and ("kimi" in text or "api.kimi.com" in text):
        return "kimi_context_canceled"
    if "context canceled" in text:
        return "upstream_context_canceled"
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
    if "api error" in text:
        return "claude_api_error"
    if returncode != 0:
        return f"claude_cli_exit_{returncode}"
    return None


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
        "template_case_id": request.template_case_id,
        "assets": _request_assets_for_cache(request),
        "output": request.output,
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
        "aspect_ratio": output.get("aspect_ratio"),
        "count": output.get("count"),
        "quality": output.get("quality"),
        "provider_hint": output.get("provider_hint"),
    }
    return {
        "cache_schema": _CLAUDE_DECISION_CACHE_SCHEMA,
        "normalized_user_prompt": normalized_prompt,
        "prompt_tokens": tokens,
        "mode": request.mode_hint or fallback_mode,
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
    for key in ["cache_schema", "mode", "template_case_id", "output_signature", "assets"]:
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
