from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.config import settings
from app.repositories import repository
from app.repositories.memory import utc_now
from app.schemas import (
    CaseRetrievalPlan,
    CreateCreativeRunRequest,
    CreateImageJobRequest,
    CreativeRun,
    ImagePromptPlan,
    SearchPromptCasesRequest,
)
from app.services.case_intelligence import build_case_profile, get_prompt_case, search_prompt_cases
from app.services.claude_orchestrator import orchestrate_creative_request
from app.services.asset_binding import build_asset_context, provider_input_images_from_context
from app.services.generation import create_image_job, create_running_image_job
from app.services.ids import new_id
from app.services.prompting import compose_prompt_plan, summarize_intent, summaries_from_cases
from app.services.safety import run_safety_check
from app.services.task_queue import update_task_snapshot

try:
    from agents import Agent, function_tool  # type: ignore

    AGENTS_SDK_AVAILABLE = True
except Exception:
    Agent = None  # type: ignore
    function_tool = None  # type: ignore
    AGENTS_SDK_AVAILABLE = False


class CreativeManagerRuntime:
    """Deterministic V2 business pipeline with an SDK-compatible tool boundary.

    OpenAI Agents SDK tools are kept as a future planner/tracing capsule, but
    the current end-to-end execution path deliberately stays in domain services
    so template lock, asset binding, safety, providers, storage, and billing
    remain deterministic and auditable.
    """

    def __init__(self) -> None:
        self.sdk_available = AGENTS_SDK_AVAILABLE
        self.sdk_agent_name = "CreativeManagerAgent"
        self._sdk_tools = self._build_sdk_tools_if_available()
        self._sdk_agent = self._build_sdk_agent_if_available()

    def refresh_runtime_config(self) -> None:
        self._sdk_tools = self._build_sdk_tools_if_available()
        self._sdk_agent = self._build_sdk_agent_if_available()

    async def run(self, request: CreateCreativeRunRequest) -> CreativeRun:
        return await self._run_deterministic_manager(request)

    def queue_run(self, request: CreateCreativeRunRequest) -> CreativeRun:
        now = utc_now()
        mode = request.mode_hint or ("template_customize" if request.template_case_id else "smart_enhance")
        run = CreativeRun(
            run_id=new_id("run"),
            status="planning",
            mode=mode,  # type: ignore[arg-type]
            intent_summary=summarize_intent(request.user_prompt),
            trace_id=new_id("trace"),
            next_actions=["Queued for central orchestration. Poll this run_id for updates."],
            created_at=now,
            updated_at=now,
        )
        return repository.save_creative_run(run)

    async def complete_queued_run(self, request: CreateCreativeRunRequest, run_id: str) -> CreativeRun:
        existing = repository.get_creative_run(run_id)
        try:
            return await self._run_deterministic_manager(
                request,
                run_id=run_id,
                trace_id=existing.trace_id if existing else None,
                created_at=existing.created_at if existing else None,
            )
        except Exception as exc:
            now = utc_now()
            fallback = existing or CreativeRun(
                run_id=run_id,
                status="planning",
                mode=request.mode_hint or ("template_customize" if request.template_case_id else "smart_enhance"),  # type: ignore[arg-type]
                intent_summary=summarize_intent(request.user_prompt),
                trace_id=new_id("trace"),
                created_at=now,
                updated_at=now,
            )
            failed = fallback.model_copy(
                update={
                    "status": "failed",
                    "next_actions": [f"Async creative run failed: {exc}"],
                    "updated_at": now,
                }
            )
            return repository.save_creative_run(failed)

    def _build_sdk_agent_if_available(self):
        if not AGENTS_SDK_AVAILABLE or Agent is None:
            return None
        return Agent(
            name="CreativeManagerAgent",
            model=settings.default_agent_model,
            tools=self._sdk_tools,
            instructions=(
                "You are the central manager for Custom Media Agent 2.0. "
                "Use tools and structured outputs to plan template customization, smart enhancement, "
                "safety checks, and image generation. Treat retrieved cases as inspiration, not source "
                "content to copy. Keep all decisions inside the typed tool and run schemas."
            ),
        )

    def _build_sdk_tools_if_available(self):
        if not AGENTS_SDK_AVAILABLE or function_tool is None:
            return []

        @function_tool
        def case_strategist_search(query_text: str, limit: int = 6) -> str:
            """Search the structured case index for relevant prompt cases."""
            response = search_prompt_cases(
                SearchPromptCasesRequest(
                    query_text=query_text,
                    risk_filters=["exclude_protected_ip", "exclude_unlicensed_logo"],
                    limit=max(1, min(limit, 20)),
                )
            )
            return _json_tool_result(response.model_dump(mode="json"))

        @function_tool
        def case_detail(case_id: str) -> str:
            """Return a full prompt case by case_id."""
            case = get_prompt_case(case_id)
            if not case:
                return _json_tool_result({"found": False, "case_id": case_id})
            return _json_tool_result({"found": True, "case": case.model_dump(mode="json")})

        @function_tool
        def case_profile(case_id: str) -> str:
            """Return the structured visual/use-case profile for a prompt case."""
            case = get_prompt_case(case_id)
            if not case:
                return _json_tool_result({"found": False, "case_id": case_id})
            profile = build_case_profile(case)
            return _json_tool_result({"found": True, "case_id": case_id, "profile": profile.model_dump(mode="json")})

        @function_tool
        def prompt_safety_check(user_prompt: str, composed_prompt: str = "", negative_prompt: str = "") -> str:
            """Run the v2 safety guardrail against a draft prompt."""
            prompt_plan = ImagePromptPlan(
                plan_id=new_id("plan"),
                mode="smart_enhance",
                prompt=composed_prompt or user_prompt,
                negative_prompt=negative_prompt,
            )
            decision = run_safety_check(
                scope="creative_manager_tool",
                user_prompt=user_prompt,
                prompt_plan=prompt_plan,
                selected_cases=[],
            )
            return _json_tool_result(decision.model_dump(mode="json"))

        return [case_strategist_search, case_detail, case_profile, prompt_safety_check]

    async def _run_deterministic_manager(
        self,
        request: CreateCreativeRunRequest,
        *,
        run_id: str | None = None,
        trace_id: str | None = None,
        created_at=None,
    ) -> CreativeRun:
        created = created_at or utc_now()
        run_id = run_id or new_id("run")
        trace_id = trace_id or new_id("trace")
        fallback_mode = request.mode_hint or ("template_customize" if request.template_case_id else "smart_enhance")
        progress_events: list[dict[str, Any]] = []
        progress_summary: dict[str, Any] = {}
        self._save_run_stage(
            request,
            run_id=run_id,
            trace_id=trace_id,
            created_at=created,
            status="planning",
            mode=fallback_mode,
            next_actions=["Building the initial case retrieval and asset-understanding plan."],
        )
        fallback_retrieval_plan = self._build_retrieval_plan(request, fallback_mode)
        self._save_run_stage(
            request,
            run_id=run_id,
            trace_id=trace_id,
            created_at=created,
            status="retrieving_cases",
            mode=fallback_mode,
            case_retrieval_plan=fallback_retrieval_plan,
            next_actions=["Matching local provider cases and preparing uploaded assets."],
        )
        template_case = get_prompt_case(request.template_case_id) if request.template_case_id else None
        template_locked = template_case is not None
        candidate_summaries = self._retrieve_candidate_summaries(fallback_retrieval_plan, limit=max(4, fallback_retrieval_plan.limit))
        candidate_summaries = self._prioritize_template_summary(candidate_summaries, request.template_case_id)
        candidate_case_details = self._hydrate_template_and_candidates(
            request.template_case_id,
            candidate_summaries,
            limit=max(4, fallback_retrieval_plan.limit),
        )
        orchestrator_candidate_summaries = candidate_summaries
        orchestrator_candidate_details = candidate_case_details
        if template_locked and template_case:
            orchestrator_candidate_summaries = summaries_from_cases([template_case])
            orchestrator_candidate_details = [template_case]
        asset_context = build_asset_context(request)
        asset_binding_error = _asset_binding_failure(asset_context)
        if asset_binding_error:
            return self._save_run_stage(
                request,
                run_id=run_id,
                trace_id=trace_id,
                created_at=created,
                status="failed",
                mode=fallback_mode,
                case_retrieval_plan=fallback_retrieval_plan,
                selected_cases=orchestrator_candidate_summaries,
                next_actions=[asset_binding_error],
            )
        self._save_run_stage(
            request,
            run_id=run_id,
            trace_id=trace_id,
            created_at=created,
            status="composing_prompt",
            mode=fallback_mode,
            case_retrieval_plan=fallback_retrieval_plan,
            selected_cases=orchestrator_candidate_summaries,
            next_actions=["Claude Code is composing the final prompt from cases, user intent, and asset bindings."],
            progress_events=progress_events,
            progress_summary=progress_summary,
        )

        def on_claude_progress(event: dict[str, Any]) -> None:
            nonlocal progress_summary
            compact_event = _compact_progress_event(event)
            progress_events.append(compact_event)
            progress_summary = _claude_progress_summary(progress_events)
            self._save_run_stage(
                request,
                run_id=run_id,
                trace_id=trace_id,
                created_at=created,
                status="composing_prompt",
                mode=fallback_mode,
                case_retrieval_plan=fallback_retrieval_plan,
                selected_cases=orchestrator_candidate_summaries,
                next_actions=[progress_summary.get("message") or "Claude Code is orchestrating the prompt."],
                progress_events=progress_events,
                progress_summary=progress_summary,
            )

        orchestrator_decision = orchestrate_creative_request(
            request=request,
            fallback_mode=fallback_mode,
            fallback_retrieval_plan=fallback_retrieval_plan,
            candidate_cases=orchestrator_candidate_summaries,
            candidate_case_details=orchestrator_candidate_details,
            progress_callback=on_claude_progress,
        )
        orchestrator_failure = _claude_required_failure_message(orchestrator_decision)
        if orchestrator_failure:
            return self._save_run_stage(
                request,
                run_id=run_id,
                trace_id=trace_id,
                created_at=created,
                status="failed",
                mode=fallback_mode,
                case_retrieval_plan=fallback_retrieval_plan,
                selected_cases=orchestrator_candidate_summaries,
                orchestrator_decision=orchestrator_decision,
                next_actions=[orchestrator_failure],
                progress_events=progress_events,
                progress_summary=progress_summary,
            )
        mode = orchestrator_decision.mode
        retrieval_plan = orchestrator_decision.case_retrieval_plan
        selected_cases = []
        full_cases = []

        if template_locked and template_case:
            full_cases = [template_case]
        else:
            full_case_ids: set[str] = set()
            for case_id in orchestrator_decision.selected_case_ids:
                case = get_prompt_case(case_id)
                if case and case.case_id not in full_case_ids:
                    full_cases.append(case)
                    full_case_ids.add(case.case_id)

            should_expand_with_local_search = (
                orchestrator_decision.provider != "claude-code"
                or bool(orchestrator_decision.fallback_reason)
                or not orchestrator_decision.selected_case_ids
            )
            if should_expand_with_local_search:
                search_response = self._search_cases(retrieval_plan)
                for summary in search_response.cases:
                    case = get_prompt_case(summary.case_id)
                    if case and case.case_id not in full_case_ids:
                        full_cases.append(case)
                        full_case_ids.add(case.case_id)
        if not full_cases:
            search_response = self._search_cases(retrieval_plan)
            for summary in search_response.cases:
                case = get_prompt_case(summary.case_id)
                if case and case.case_id not in {item.case_id for item in full_cases}:
                    full_cases.append(case)
        full_cases = full_cases[: retrieval_plan.limit]
        selected_cases = summaries_from_cases(full_cases)

        prompt_plan = compose_prompt_plan(
            mode=mode,
            user_prompt=request.user_prompt,
            cases=full_cases,
            output={**orchestrator_decision.generation_directives, **request.output},
            orchestrator_decision=orchestrator_decision,
            asset_context=asset_context,
        )
        self._save_run_stage(
            request,
            run_id=run_id,
            trace_id=trace_id,
            created_at=created,
            status="safety_checking",
            mode=mode,
            case_retrieval_plan=retrieval_plan,
            selected_cases=selected_cases,
            prompt_plan=prompt_plan,
            orchestrator_decision=orchestrator_decision,
            next_actions=["Checking safety and provider readiness before image generation."],
            progress_events=progress_events,
            progress_summary=progress_summary,
        )
        safety_decision = run_safety_check(
            scope="creative_run",
            user_prompt=request.user_prompt,
            prompt_plan=prompt_plan,
            selected_cases=selected_cases,
        )

        generation_jobs = []
        status = "completed"
        next_actions = ["Review generated outputs and select a favorite or request revisions."]
        if safety_decision.decision == "blocked":
            status = "blocked_by_policy"
            next_actions = ["Revise the request to remove blocked content."]
        elif safety_decision.decision == "need_user_confirmation":
            status = "waiting_for_user"
            next_actions = ["Collect explicit user authorization before image generation."]
        else:
            image_request = CreateImageJobRequest(
                run_id=run_id,
                prompt_plan=prompt_plan,
                provider_hint=request.output.get("provider_hint")
                or orchestrator_decision.generation_directives.get("provider_hint"),
                input_images=provider_input_images_from_context(asset_context),
                veyra_user_id=request.veyra_user_id,
            )
            running_job = await create_running_image_job(image_request)
            generation_jobs.append(running_job)
            self._save_run_stage(
                request,
                run_id=run_id,
                trace_id=trace_id,
                created_at=created,
                status="generating",
                mode=mode,
                case_retrieval_plan=retrieval_plan,
                selected_cases=selected_cases,
                prompt_plan=prompt_plan,
                safety_decision=safety_decision,
                orchestrator_decision=orchestrator_decision,
                generation_jobs=generation_jobs,
                next_actions=["Submitting the final prompt and required reference images to the selected image provider."],
                progress_events=progress_events,
                progress_summary=progress_summary,
            )
            job = await create_image_job(
                image_request,
                job_id=running_job.job_id,
                created_at=running_job.created_at,
            )
            generation_jobs = [job]
            if job.status == "failed":
                status = "failed"
                next_actions = [_image_job_failure_action(job)]
            else:
                self._save_run_stage(
                    request,
                    run_id=run_id,
                    trace_id=trace_id,
                    created_at=created,
                    status="reviewing",
                    mode=mode,
                    case_retrieval_plan=retrieval_plan,
                    selected_cases=selected_cases,
                    prompt_plan=prompt_plan,
                    safety_decision=safety_decision,
                    orchestrator_decision=orchestrator_decision,
                    generation_jobs=generation_jobs,
                    next_actions=["Reviewing outputs and saving them into the independent V2 history."],
                    progress_events=progress_events,
                    progress_summary=progress_summary,
                )

        run = CreativeRun(
            run_id=run_id,
            status=status,  # type: ignore[arg-type]
            mode=mode,  # type: ignore[arg-type]
            intent_summary=summarize_intent(request.user_prompt),
            case_retrieval_plan=retrieval_plan,
            selected_cases=selected_cases,
            prompt_plan=prompt_plan,
            safety_decision=safety_decision,
            orchestrator_decision=orchestrator_decision,
            generation_jobs=generation_jobs,
            trace_id=trace_id,
            next_actions=next_actions,
            progress_events=progress_events,
            progress_summary=progress_summary,
            created_at=created,
            updated_at=utc_now(),
        )
        return repository.save_creative_run(run)

    def _save_run_stage(
        self,
        request: CreateCreativeRunRequest,
        *,
        run_id: str,
        trace_id: str,
        created_at,
        status: str,
        mode: str,
        case_retrieval_plan: CaseRetrievalPlan | None = None,
        selected_cases=None,
        prompt_plan: ImagePromptPlan | None = None,
        safety_decision=None,
        orchestrator_decision=None,
        generation_jobs=None,
        next_actions: list[str] | None = None,
        progress_events: list[dict[str, Any]] | None = None,
        progress_summary: dict[str, Any] | None = None,
    ) -> CreativeRun:
        run = CreativeRun(
            run_id=run_id,
            status=status,  # type: ignore[arg-type]
            mode=mode,  # type: ignore[arg-type]
            intent_summary=summarize_intent(request.user_prompt),
            case_retrieval_plan=case_retrieval_plan,
            selected_cases=list(selected_cases or []),
            prompt_plan=prompt_plan,
            safety_decision=safety_decision,
            orchestrator_decision=orchestrator_decision,
            generation_jobs=list(generation_jobs or []),
            trace_id=trace_id,
            next_actions=next_actions or [],
            progress_events=list(progress_events or []),
            progress_summary=dict(progress_summary or {}),
            created_at=created_at,
            updated_at=utc_now(),
        )
        saved = repository.save_creative_run(run)
        try:
            update_task_snapshot(saved)
        except Exception:
            pass
        return saved

    def _build_retrieval_plan(self, request: CreateCreativeRunRequest, mode: str) -> CaseRetrievalPlan:
        text = request.user_prompt.lower()
        category_filters: list[str] = []
        use_case_filters: list[str] = []
        style_filters: list[str] = []
        if any(word in text for word in ["marketplace", "listing"]):
            category_filters.append("ecommerce")
        if any(word in text for word in ["product", "ecommerce", "商品", "电商"]):
            use_case_filters.extend(["ecommerce", "product-listing"])
        if any(word in text for word in ["poster", "海报", "event"]):
            category_filters.append("poster")
            use_case_filters.append("poster")
        if any(word in text for word in ["ad", "campaign", "广告"]):
            category_filters.append("ad-creative")
            use_case_filters.append("ad-creative")
        if any(word in text for word in ["portrait", "founder", "人像"]):
            category_filters.append("portrait")
            use_case_filters.append("portrait")
        if any(word in text for word in ["ui", "dashboard", "界面"]):
            category_filters.append("ui")
            use_case_filters.append("ui")
        if any(word in text for word in ["character", "mascot", "角色"]):
            category_filters.append("character")
            use_case_filters.append("character")
        if any(word in text for word in ["premium", "luxury", "高级", "奢华"]):
            style_filters.extend(["premium", "luxury"])
        if any(word in text for word in ["minimal", "clean", "极简", "干净"]):
            style_filters.extend(["minimal", "clean"])
        if mode == "template_customize" and request.template_case_id:
            template = get_prompt_case(request.template_case_id)
            if template:
                category_filters = [template.category]
                use_case_filters = template.use_case_tags[:2]
                style_filters = template.style_tags[:3]
        return CaseRetrievalPlan(
            query_text=request.user_prompt,
            category_filters=_dedupe(category_filters),
            use_case_filters=_dedupe(use_case_filters),
            style_filters=_dedupe(style_filters),
            risk_filters=["exclude_protected_ip", "exclude_unlicensed_logo"],
            limit=6,
            diversity_level="medium",
        )

    def _retrieve_candidate_summaries(self, retrieval_plan: CaseRetrievalPlan, *, limit: int):
        response = self._search_cases(retrieval_plan.model_copy(update={"limit": limit}))
        return response.cases

    def _prioritize_template_summary(self, summaries, template_case_id: str | None):
        if not template_case_id:
            return summaries
        template_summary = next((item for item in summaries if item.case_id == template_case_id), None)
        if not template_summary:
            template = get_prompt_case(template_case_id)
            if template:
                template_summary = summaries_from_cases([template])[0]
        if not template_summary:
            return summaries
        template_summary = template_summary.model_copy(
            update={"why_selected": "Hand-selected template; highest-priority visual anchor."}
        )
        return [template_summary, *[item for item in summaries if item.case_id != template_case_id]]

    def _hydrate_template_and_candidates(self, template_case_id: str | None, summaries, *, limit: int):
        cases = []
        if template_case_id:
            template = get_prompt_case(template_case_id)
            if template:
                cases.append(template)
        for summary in summaries:
            if len(cases) >= limit:
                break
            case = get_prompt_case(summary.case_id)
            if case and case.case_id not in {item.case_id for item in cases}:
                cases.append(case)
        return cases

    def _hydrate_cases(self, summaries):
        cases = []
        for summary in summaries:
            case = get_prompt_case(summary.case_id)
            if case and case.case_id not in {item.case_id for item in cases}:
                cases.append(case)
        return cases

    def _search_cases(self, retrieval_plan: CaseRetrievalPlan):
        return search_prompt_cases(
            SearchPromptCasesRequest(
                query_text=retrieval_plan.query_text,
                category_filters=retrieval_plan.category_filters,
                style_filters=retrieval_plan.style_filters,
                use_case_filters=retrieval_plan.use_case_filters,
                risk_filters=retrieval_plan.risk_filters,
                limit=retrieval_plan.limit,
                diversity_level=retrieval_plan.diversity_level,
            )
        )


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _json_tool_result(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _compact_progress_event(event: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "scope",
        "stage",
        "stage_label",
        "status",
        "provider",
        "model",
        "fallback_model",
        "timeout_seconds",
        "duration_ms",
        "failure_code",
        "attempt",
        "after_compression_retries",
        "created_at",
        "message",
    }
    compact: dict[str, Any] = {}
    for key in allowed:
        value = event.get(key)
        if value not in (None, "", []):
            compact[key] = value
    models = event.get("models")
    if isinstance(models, list) and models:
        compact["models"] = [str(item) for item in models[:5] if str(item).strip()]
    return compact


def _claude_progress_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {}
    last = events[-1]
    completed_events = [
        item
        for item in events
        if item.get("status") in {"success", "missing_decision", "error", "failed"}
        and isinstance(item.get("duration_ms"), (int, float))
    ]
    elapsed_ms = _claude_progress_elapsed_ms(events, completed_events)
    finished_stage_count = len([item for item in completed_events if item.get("status") == "success"])
    retry_count = len(
        [
            item
            for item in events
            if "retry" in str(item.get("stage") or "") or item.get("after_compression_retries")
        ]
    )
    fallback_count = len([item for item in events if item.get("provider") == "claude-code-model-fallback"])
    return {
        "scope": "claude_orchestration",
        "stage": last.get("stage"),
        "stage_label": last.get("stage_label"),
        "status": last.get("status"),
        "provider": last.get("provider"),
        "model": last.get("model"),
        "message": last.get("message") or "Claude Code is orchestrating the prompt.",
        "elapsed_ms": elapsed_ms,
        "last_duration_ms": last.get("duration_ms"),
        "finished_stage_count": finished_stage_count,
        "retry_count": retry_count,
        "fallback_count": fallback_count,
        "events_count": len(events),
        "updated_at": last.get("created_at") or utc_now().isoformat(),
    }


def _claude_progress_elapsed_ms(events: list[dict[str, Any]], completed_events: list[dict[str, Any]]) -> int:
    timestamps: list[datetime] = []
    for item in events:
        raw = str(item.get("created_at") or "").strip()
        if not raw:
            continue
        try:
            timestamps.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
        except ValueError:
            continue
    if len(timestamps) >= 2:
        return max(0, int((timestamps[-1] - timestamps[0]).total_seconds() * 1000))
    return int(sum(float(item.get("duration_ms") or 0) for item in completed_events))


def _asset_binding_failure(asset_context: dict | None) -> str | None:
    if not asset_context:
        return None
    plan = asset_context.get("asset_binding_plan") if isinstance(asset_context.get("asset_binding_plan"), dict) else {}
    conflicts = plan.get("conflicts") if isinstance(plan, dict) else []
    missing = []
    if isinstance(conflicts, list):
        missing = [
            str(item.get("asset_id"))
            for item in conflicts
            if isinstance(item, dict) and item.get("type") == "asset_missing" and item.get("asset_id")
        ]
    if missing:
        return (
            "Uploaded asset binding failed: requested uploaded image(s) are not available to the V2 worker: "
            + ", ".join(sorted(set(missing)))
            + ". Please upload again before generation."
        )
    bindings = plan.get("bindings") if isinstance(plan, dict) else []
    hard_bindings = [item for item in bindings if isinstance(item, dict) and item.get("provider_input_required")]
    provider_plan = plan.get("provider_input_plan") if isinstance(plan, dict) and isinstance(plan.get("provider_input_plan"), dict) else {}
    if hard_bindings and not provider_plan.get("reference_image_count"):
        return "Uploaded asset binding failed: hard visual constraints require provider input images, but no reference image was prepared."
    return None


def _claude_required_failure_message(orchestrator_decision) -> str | None:
    if not settings.claude_orchestrator_enabled:
        return None
    if orchestrator_decision.provider == "claude-code" and not orchestrator_decision.fallback_reason:
        return None
    status = str(orchestrator_decision.invocation_status or "")
    reason = str(orchestrator_decision.fallback_reason or "")
    if status in {"checkpoint_fallback", "fallback"} and (
        reason.startswith("claude_") or reason.startswith("claude_checkpoint")
    ):
        return (
            "Claude Code central orchestration did not produce a recoverable checkpointed decision; "
            "image generation was stopped instead of using a deterministic creative fallback."
        )
    return None


def _image_job_failure_action(job) -> str:
    error = job.error or {}
    message = str(error.get("message") or "").strip()
    if error.get("error_code") == "provider_not_configured":
        provider = job.provider_id or "selected provider"
        return f"{provider} is not configured: {message or 'missing API key'}. Configure the V2 provider key or switch to another configured V2 image model."
    if error.get("error_code") == "provider_rate_limit":
        return f"Image provider is rate limited: {message or 'please wait and retry'}."
    if message:
        return message
    return "Image provider failed before returning an output."
