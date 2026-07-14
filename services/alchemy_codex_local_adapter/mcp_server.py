"""Doc118 native ImageGen stdio MCP: planning only, with no image transport."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from .contracts import CodexNativeImageGenError, NativeImageGenPlanRequest
from .facade import CodexNativeImageGenFacade


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "prepare_native_imagegen_plan",
        "description": "Prepare an Alchemy V3 prompt plan for one explicit Codex Native ImageGen request; no image is created or imported.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["user_input", "template_id", "requested_image_count", "requested_image_size", "reference_declarations"],
            "properties": {
                "user_input": {"type": "string", "minLength": 1, "maxLength": 8000},
                "template_id": {"type": "string"},
                "requested_image_count": {"type": "integer", "minimum": 1, "maximum": 16},
                "requested_image_size": {"type": ["string", "null"]},
                "reference_declarations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["channel", "attached_in_current_codex_conversation"],
                        "properties": {
                            "channel": {"type": "string"},
                            "attached_in_current_codex_conversation": {"type": "boolean"},
                        },
                    },
                },
            },
        },
    }
]


def _tool_result(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def _tool_error(exc: CodexNativeImageGenError) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(exc.as_dict(), ensure_ascii=False)}], "isError": True}


def _prepare_native_imagegen_plan(adapter: CodexNativeImageGenFacade, args: dict[str, Any]) -> dict[str, Any]:
    request = NativeImageGenPlanRequest.from_mcp_arguments(args)
    return adapter.prepare_native_imagegen_plan(request)


def dispatch(adapter: CodexNativeImageGenFacade, request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        result: dict[str, Any] = {
            "protocolVersion": str((request.get("params") or {}).get("protocolVersion") or "2025-03-26"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "alchemy-codex-native-imagegen", "version": "0.3.1-doc118-n1"},
        }
    elif method == "tools/list":
        result = {"tools": TOOL_SCHEMAS}
    elif method == "tools/call":
        params = request.get("params") or {}
        name = str(params.get("name") or "")
        args = params.get("arguments") or {}
        handlers: dict[str, Callable[[CodexNativeImageGenFacade, dict[str, Any]], dict[str, Any]]] = {
            "prepare_native_imagegen_plan": _prepare_native_imagegen_plan,
        }
        if name not in handlers:
            result = {"content": [{"type": "text", "text": '{"code":"codex_native_imagegen_unknown_tool"}'}], "isError": True}
        else:
            try:
                result = _tool_result(handlers[name](adapter, dict(args) if isinstance(args, dict) else {}))
            except CodexNativeImageGenError as exc:
                result = _tool_error(exc)
    else:
        result = {"code": -32601, "message": "Method not found"}
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Doc118 native ImageGen planning-only stdio MCP bridge")
    parser.add_argument("--enable-native-imagegen", action="store_true")
    arguments = parser.parse_args()
    adapter = CodexNativeImageGenFacade(enabled=arguments.enable_native_imagegen)
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
