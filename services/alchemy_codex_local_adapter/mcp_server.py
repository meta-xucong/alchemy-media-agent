"""Doc183 shared V3 materialization plus legacy native ImageGen MCP tools."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from .contracts import (
    CodexNativeImageGenError,
    NativeImageGenPlanRequest,
    NativeProfessionalImageGenPlanRequest,
    NativeSpecializedImageGenPlanRequest,
)
from .facade import CodexNativeImageGenFacade
from .materialized_bridge import MaterializedBridgeError, V3MaterializedMcpBridge


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "prepare_shared_mcp_materialization",
        "description": "Read one frozen V3 MCP handoff from localhost. The prompt, references, and rendering parameters are the exact Web Provider contract; the tool does not replan or render.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["handoff_id"],
            "properties": {
                "handoff_id": {"type": "string"},
                "v3_base_url": {"type": ["string", "null"]},
            },
        },
    },
    {
        "name": "submit_shared_mcp_materialization",
        "description": "Submit exactly one local Codex ImageGen artifact to a frozen V3 handoff. The shared V3 Provider/output/review/retry/Character Card pipeline consumes it; this tool never writes a candidate or slot itself.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["handoff_id", "nonce", "prompt_sha256", "reference_asset_hashes"],
            "properties": {
                "handoff_id": {"type": "string"},
                "nonce": {"type": "string"},
                "prompt_sha256": {"type": "string"},
                "reference_asset_hashes": {"type": "array", "items": {"type": "string"}},
                "artifact_path": {"type": ["string", "null"]},
                "artifact_base64": {"type": ["string", "null"]},
                "v3_base_url": {"type": ["string", "null"]},
            },
        },
    },
    {
        "name": "prepare_native_imagegen_plan",
        "description": "Prepare exact canonical V3 GPT Image 2 prompts and admitted reference paths for one explicit Codex Native ImageGen request; the MCP never creates, imports, or stores an image.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["user_input", "template_id", "requested_image_count", "requested_image_size", "reference_inputs"],
            "properties": {
                "user_input": {"type": "string", "minLength": 1, "maxLength": 8000},
                "template_id": {"type": "string"},
                "requested_image_count": {"type": "integer", "minimum": 1, "maximum": 16},
                "requested_image_size": {"type": ["string", "null"]},
                "reference_inputs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["channel", "file_path"],
                        "properties": {
                            "channel": {"type": "string"},
                            "file_path": {"type": "string"},
                        },
                    },
                },
            },
        },
    }
    ,
    {
        "name": "prepare_frozen_specialized_native_imagegen_plan",
        "description": "Freeze one explicit E-Commerce or Photography V3 plan through its normal required remote Brain/runtime contract, then return only the exact canonical Web Provider prompt and admitted reference paths for Codex conversation ImageGen. It never creates a Web request, project, artifact, candidate, review, retry, or delivery.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "user_input",
                "template_id",
                "requested_image_count",
                "requested_image_size",
                "reference_inputs",
                "platform_profile",
                "photography_mode",
                "photographer_profile_id",
            ],
            "properties": {
                "user_input": {"type": "string", "minLength": 1, "maxLength": 8000},
                "template_id": {"enum": ["ecommerce_template", "photographer_template"]},
                "requested_image_count": {"type": "integer", "minimum": 1, "maximum": 16},
                "requested_image_size": {"type": ["string", "null"]},
                "reference_inputs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["channel", "file_path"],
                        "properties": {
                            "channel": {"type": "string"},
                            "file_path": {"type": "string"},
                        },
                    },
                },
                "platform_profile": {"type": ["string", "null"]},
                "photography_mode": {"type": ["string", "null"]},
                "photographer_profile_id": {"type": ["string", "null"]},
            },
        },
    },
    {
        "name": "prepare_frozen_professional_native_imagegen_plan",
        "description": "Resolve an explicit server-owned People Asset binding and freeze the existing V3 Professional Mode plan, then return only the exact canonical provider prompt and admitted reference paths for conversation-only Codex ImageGen. The MCP never accepts a binding/pack record and never creates a project, artifact, candidate, review, retry, or delivery.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "user_input",
                "template_id",
                "requested_image_count",
                "requested_image_size",
                "reference_inputs",
                "project_id",
                "people_asset_id",
                "professional_identity_view_ids",
            ],
            "properties": {
                "user_input": {"type": "string", "minLength": 1, "maxLength": 8000},
                "template_id": {"enum": ["general_template", "ecommerce_template", "photographer_template"]},
                "requested_image_count": {"type": "integer", "minimum": 1, "maximum": 16},
                "requested_image_size": {"type": ["string", "null"]},
                "reference_inputs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["channel", "file_path"],
                        "properties": {
                            "channel": {"type": "string"},
                            "file_path": {"type": "string"},
                        },
                    },
                },
                "project_id": {"type": "string"},
                "people_asset_id": {"type": "string"},
                "professional_identity_view_ids": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {"type": "string"},
                },
                "professional_reference_stage": {
                    "type": ["string", "null"],
                    "enum": ["standard_front", "three_quarter", "profile", None],
                },
                "platform_profile": {"type": ["string", "null"]},
                "photography_mode": {"type": ["string", "null"]},
                "photographer_profile_id": {"type": ["string", "null"]},
            },
        },
    },
]


def _tool_result(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def _tool_error(exc: CodexNativeImageGenError) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(exc.as_dict(), ensure_ascii=False)}], "isError": True}


def _bridge_error(exc: MaterializedBridgeError) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps({"code": exc.code, "message": str(exc)}, ensure_ascii=False)}],
        "isError": True,
    }


def _prepare_shared_mcp_materialization(args: dict[str, Any]) -> dict[str, Any]:
    bridge = V3MaterializedMcpBridge(args.get("v3_base_url"))
    return bridge.get_handoff(str(args.get("handoff_id") or ""))


def _submit_shared_mcp_materialization(args: dict[str, Any]) -> dict[str, Any]:
    bridge = V3MaterializedMcpBridge(args.get("v3_base_url"))
    return bridge.submit(
        handoff_id=str(args.get("handoff_id") or ""),
        nonce=str(args.get("nonce") or ""),
        prompt_sha256=str(args.get("prompt_sha256") or ""),
        reference_asset_hashes=[str(item or "") for item in (args.get("reference_asset_hashes") or [])],
        artifact_path=args.get("artifact_path"),
        artifact_base64=args.get("artifact_base64"),
    )


def _prepare_native_imagegen_plan(adapter: CodexNativeImageGenFacade, args: dict[str, Any]) -> dict[str, Any]:
    request = NativeImageGenPlanRequest.from_mcp_arguments(args)
    return adapter.prepare_native_imagegen_plan(request)


def _prepare_frozen_specialized_native_imagegen_plan(
    adapter: CodexNativeImageGenFacade,
    args: dict[str, Any],
) -> dict[str, Any]:
    request = NativeSpecializedImageGenPlanRequest.from_mcp_arguments(args)
    return adapter.prepare_frozen_specialized_native_imagegen_plan(request)


def _prepare_frozen_professional_native_imagegen_plan(
    adapter: CodexNativeImageGenFacade,
    args: dict[str, Any],
) -> dict[str, Any]:
    request = NativeProfessionalImageGenPlanRequest.from_mcp_arguments(args)
    return adapter.prepare_frozen_professional_native_imagegen_plan(request)


def dispatch(adapter: CodexNativeImageGenFacade, request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        result: dict[str, Any] = {
            "protocolVersion": str((request.get("params") or {}).get("protocolVersion") or "2025-03-26"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "alchemy-codex-native-imagegen", "version": "0.9.0-doc183-shared-materialization"},
        }
    elif method == "tools/list":
        result = {"tools": TOOL_SCHEMAS}
    elif method == "tools/call":
        params = request.get("params") or {}
        name = str(params.get("name") or "")
        args = params.get("arguments") or {}
        handlers: dict[str, Callable[[CodexNativeImageGenFacade, dict[str, Any]], dict[str, Any]]] = {
            "prepare_native_imagegen_plan": _prepare_native_imagegen_plan,
            "prepare_frozen_specialized_native_imagegen_plan": _prepare_frozen_specialized_native_imagegen_plan,
            "prepare_frozen_professional_native_imagegen_plan": _prepare_frozen_professional_native_imagegen_plan,
        }
        bridge_handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "prepare_shared_mcp_materialization": _prepare_shared_mcp_materialization,
            "submit_shared_mcp_materialization": _submit_shared_mcp_materialization,
        }
        if name in bridge_handlers:
            try:
                result = _tool_result(bridge_handlers[name](dict(args) if isinstance(args, dict) else {}))
            except MaterializedBridgeError as exc:
                result = _bridge_error(exc)
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
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
    parser = argparse.ArgumentParser(description="Doc130/131 canonical-prompt stdio MCP bridge")
    parser.add_argument("--enable-native-imagegen", action="store_true")
    parser.add_argument(
        "--professional-asset-catalog-root",
        help="Explicit metadata-only People Asset catalog root for Professional planning; never an MCP field.",
    )
    arguments = parser.parse_args()
    adapter = CodexNativeImageGenFacade(
        enabled=arguments.enable_native_imagegen,
        professional_asset_catalog_root=arguments.professional_asset_catalog_root,
    )

    # MCP JSON is UTF-8 regardless of the host console code page.  Without
    # this explicit stream contract, Windows decodes a user-authorized Chinese
    # reference filename through the active OEM/ANSI code page and the
    # resolver reports a false ``path_unavailable`` failure before V3 sees it.
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
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
