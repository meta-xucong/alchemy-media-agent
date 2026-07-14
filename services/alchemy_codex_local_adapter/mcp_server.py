"""Minimal stdio MCP bridge for the Doc117 Phase A--B adapter.

It implements only stdio JSON-RPC.  There is deliberately no HTTP route,
background worker, process control, polling loop, or Codex CLI invocation.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from .contracts import LocalJobSpec, LocalModeAdapterError
from .facade import CodexLocalExecutionFacade
from .platform_renderer import PlatformImageRenderer


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "create_local_job",
        "description": "Create an explicitly selected, frozen Codex Local Mode job.",
        "inputSchema": {
            "type": "object",
            "required": [
                "job_id",
                "project_id",
                "template_id",
                "scenario_id",
                "protected_user_intent",
                "role_ids",
                "normalized_intent",
                "capability_execution_envelope",
                "resolved_constraint_ledger",
            ],
            "properties": {
                "job_id": {"type": "string"},
                "project_id": {"type": "string"},
                "template_id": {"type": "string"},
                "scenario_id": {"type": "string"},
                "protected_user_intent": {"type": "string"},
                "role_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "normalized_intent": {"type": "object"},
                "capability_execution_envelope": {"type": "object"},
                "resolved_constraint_ledger": {"type": "object"},
                "permitted_reference_files": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "get_render_contract",
        "description": "Read the frozen, public-safe local render contract.",
        "inputSchema": {"type": "object", "required": ["job_id"], "properties": {"job_id": {"type": "string"}}},
    },
    {
        "name": "record_creative_direction",
        "description": "Append one natural-language whole-image direction for a frozen role.",
        "inputSchema": {
            "type": "object",
            "required": ["job_id", "role_id", "direction"],
            "properties": {"job_id": {"type": "string"}, "role_id": {"type": "string"}, "direction": {"type": "string"}},
        },
    },
    {
        "name": "render_platform_candidate",
        "description": "Explicitly render one frozen role through the official Platform Image API, then import its API materialization.",
        "inputSchema": {
            "type": "object",
            "required": ["job_id", "role_id", "live_platform_opt_in"],
            "properties": {
                "job_id": {"type": "string"},
                "role_id": {"type": "string"},
                "live_platform_opt_in": {"type": "boolean", "const": True},
            },
        },
    },
    {
        "name": "get_local_job_status",
        "description": "Read public-safe Local Mode status. Phase A--B returns no certified delivery.",
        "inputSchema": {"type": "object", "required": ["job_id"], "properties": {"job_id": {"type": "string"}}},
    },
    {
        "name": "review_candidate",
        "description": "Reserved for shared review in Phase C; currently fails closed.",
        "inputSchema": {"type": "object", "required": ["job_id", "candidate_id"], "properties": {"job_id": {"type": "string"}, "candidate_id": {"type": "string"}}},
    },
    {
        "name": "request_bounded_revision",
        "description": "Reserved for shared retry in Phase C; currently fails closed.",
        "inputSchema": {"type": "object", "required": ["job_id", "candidate_id"], "properties": {"job_id": {"type": "string"}, "candidate_id": {"type": "string"}}},
    },
    {
        "name": "finalize_local_job",
        "description": "Reserved for shared final delivery in Phase C; currently fails closed.",
        "inputSchema": {"type": "object", "required": ["job_id"], "properties": {"job_id": {"type": "string"}}},
    },
]


def _tool_result(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def _tool_error(exc: LocalModeAdapterError) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(exc.as_dict(), ensure_ascii=False)}], "isError": True}


def _create_job(adapter: CodexLocalExecutionFacade, args: dict[str, Any]) -> Any:
    return adapter.create_local_job(
        LocalJobSpec(
            job_id=str(args.get("job_id") or ""),
            project_id=str(args.get("project_id") or ""),
            template_id=str(args.get("template_id") or ""),
            scenario_id=str(args.get("scenario_id") or ""),
            protected_user_intent=str(args.get("protected_user_intent") or ""),
            role_ids=tuple(args.get("role_ids") or ()),
            normalized_intent=dict(args.get("normalized_intent") or {}),
            capability_execution_envelope=dict(args.get("capability_execution_envelope") or {}),
            resolved_constraint_ledger=dict(args.get("resolved_constraint_ledger") or {}),
            permitted_reference_files=tuple(args.get("permitted_reference_files") or ()),
        )
    )


def _render_platform_candidate(adapter: CodexLocalExecutionFacade, args: dict[str, Any]) -> Any:
    candidate = adapter.render_platform_candidate(
        str(args.get("job_id") or ""),
        str(args.get("role_id") or ""),
        renderer=PlatformImageRenderer(live_platform_opt_in=bool(args.get("live_platform_opt_in"))),
    )
    return candidate.storage_record()


def dispatch(adapter: CodexLocalExecutionFacade, request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        result: dict[str, Any] = {
            "protocolVersion": str((request.get("params") or {}).get("protocolVersion") or "2025-03-26"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "alchemy-codex-local-mode", "version": "0.2.0-doc117-b2"},
        }
    elif method == "tools/list":
        result = {"tools": TOOL_SCHEMAS}
    elif method == "tools/call":
        params = request.get("params") or {}
        name = str(params.get("name") or "")
        args = params.get("arguments") or {}
        handlers: dict[str, Callable[[CodexLocalExecutionFacade, dict[str, Any]], Any]] = {
            "create_local_job": _create_job,
            "get_render_contract": lambda service, value: service.get_render_contract(str(value.get("job_id") or "")),
            "record_creative_direction": lambda service, value: service.record_creative_direction(
                str(value.get("job_id") or ""), str(value.get("role_id") or ""), str(value.get("direction") or "")
            ),
            "render_platform_candidate": _render_platform_candidate,
            "get_local_job_status": lambda service, value: service.get_local_job_status(str(value.get("job_id") or "")),
            "review_candidate": lambda service, value: service.review_candidate(
                str(value.get("job_id") or ""), str(value.get("candidate_id") or "")
            ),
            "request_bounded_revision": lambda service, value: service.request_bounded_revision(
                str(value.get("job_id") or ""), str(value.get("candidate_id") or "")
            ),
            "finalize_local_job": lambda service, value: service.finalize_local_job(str(value.get("job_id") or "")),
        }
        if name not in handlers:
            result = {"content": [{"type": "text", "text": '{"code":"codex_local_unknown_tool"}'}], "isError": True}
        else:
            try:
                result = _tool_result(handlers[name](adapter, dict(args) if isinstance(args, dict) else {}))
            except LocalModeAdapterError as exc:
                result = _tool_error(exc)
    else:
        result = {"code": -32601, "message": "Method not found"}
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Doc117 local stdio MCP bridge")
    parser.add_argument("--storage-root", default=".codex-local-mode-storage")
    parser.add_argument("--enable-local-mode", action="store_true")
    arguments = parser.parse_args()
    adapter = CodexLocalExecutionFacade(arguments.storage_root, enabled=arguments.enable_local_mode)
    for raw_line in sys.stdin:
        try:
            request = json.loads(raw_line)
            if not isinstance(request, dict):
                raise ValueError("JSON-RPC request must be an object")
            response = dispatch(adapter, request)
        except (ValueError, json.JSONDecodeError) as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
