"""Standalone stdio MCP entry point for Alchemy's authenticated HTTP tools.

This outlet reuses the same HTTP adapters as the repository MCP server and
intentionally excludes local image-generation planning and handoff tools.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from .product_tools import PRODUCT_TOOL_NAMES, PRODUCT_TOOL_SCHEMAS, ProductToolError, ProductTools
from .versioned_tools import VERSIONED_TOOL_NAMES, VERSIONED_TOOL_SCHEMAS, VersionedToolError, VersionedTools


TOOL_SCHEMAS = [*PRODUCT_TOOL_SCHEMAS, *VERSIONED_TOOL_SCHEMAS]
SUPPORTED_HANDSHAKE_VERSIONS = frozenset({"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"})
LATEST_HANDSHAKE_VERSION = "2025-11-25"
MODERN_PROTOCOL_VERSION = "2026-07-28"
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"


def _text_result(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def _is_modern_request(request: dict[str, Any]) -> bool:
    if request.get("method") == "server/discover":
        return True
    params = request.get("params") or {}
    meta = params.get("_meta") if isinstance(params, dict) else None
    return isinstance(meta, dict) and PROTOCOL_VERSION_META_KEY in meta


def _response(request_id: Any, result: dict[str, Any], *, modern: bool) -> dict[str, Any]:
    if modern:
        result = dict(result)
        result["resultType"] = "complete"
        if "tools" in result and "ttlMs" not in result:
            result.update({"ttlMs": 0, "cacheScope": "public"})
        result.setdefault("_meta", {SERVER_INFO_META_KEY: {"name": "alchemy-api-mcp", "version": "1.0.0"}})
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def dispatch(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    modern = _is_modern_request(request)
    if modern:
        params = request.get("params") or {}
        meta = params.get("_meta") if isinstance(params, dict) else None
        requested_version = meta.get(PROTOCOL_VERSION_META_KEY) if isinstance(meta, dict) else None
        client_capabilities = meta.get("io.modelcontextprotocol/clientCapabilities") if isinstance(meta, dict) else None
        if not isinstance(requested_version, str) or not isinstance(client_capabilities, dict):
            missing = []
            if not isinstance(requested_version, str):
                missing.append(PROTOCOL_VERSION_META_KEY)
            if not isinstance(client_capabilities, dict):
                missing.append("io.modelcontextprotocol/clientCapabilities")
            return {"jsonrpc": "2.0", "id": request_id, "error": {
                "code": -32602, "message": "Invalid params",
                "data": {"missing": missing},
            }}
        if requested_version != MODERN_PROTOCOL_VERSION:
            return {"jsonrpc": "2.0", "id": request_id, "error": {
                "code": -32022, "message": "Unsupported protocol version",
                "data": {"supported": [MODERN_PROTOCOL_VERSION], "requested": requested_version},
            }}
    if method == "notifications/initialized":
        return None
    if isinstance(method, str) and method.startswith("notifications/") and "id" not in request:
        return None
    if method == "ping" and not modern:
        result = {}
    elif method == "server/discover":
        result = {
            "supportedVersions": [MODERN_PROTOCOL_VERSION],
            "capabilities": {"tools": {"listChanged": False}},
            "ttlMs": 0,
            "cacheScope": "public",
        }
    elif method == "initialize":
        requested_version = str((request.get("params") or {}).get("protocolVersion") or "")
        negotiated_version = requested_version if requested_version in SUPPORTED_HANDSHAKE_VERSIONS else LATEST_HANDSHAKE_VERSION
        result = {
            "protocolVersion": negotiated_version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "alchemy-api-mcp", "version": "1.0.0"},
        }
    elif method == "tools/list":
        result = {"tools": TOOL_SCHEMAS}
    elif method == "tools/call":
        params = request.get("params") or {}
        name = str(params.get("name") or "")
        arguments = params.get("arguments") or {}
        try:
            if name in PRODUCT_TOOL_NAMES:
                payload = ProductTools.from_environment().call(name, arguments)
            elif name in VERSIONED_TOOL_NAMES:
                payload = VersionedTools.from_environment().call(name, arguments)
            else:
                return _response(request_id, {
                    **_text_result({"code": "alchemy_mcp_unknown_tool"}), "isError": True,
                }, modern=modern)
            result = _text_result(payload)
        except (ProductToolError, VersionedToolError) as exc:
            result = {**_text_result(exc.as_dict()), "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
    return _response(request_id, result, modern=modern)


def main() -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    for raw_line in sys.stdin:
        try:
            request = json.loads(raw_line)
            if not isinstance(request, dict):
                raise ValueError("JSON-RPC request must be an object")
            response = dispatch(request)
        except (ValueError, json.JSONDecodeError) as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
