"""Minimal HTTP MCP adapter for the V1, V2 and Alchemy Lab surfaces.

This module is intentionally an outlet: it knows public HTTP contracts and
safe transport rules, but imports no application service, provider, billing,
queue, or storage implementation.
"""
from __future__ import annotations

import base64
from http.client import HTTPException as HTTPClientError
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_ID = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"


def _tool(name: str, description: str, required: list[str], **properties: Any) -> dict:
    return {"name": name, "description": description, "inputSchema": {"type": "object", "additionalProperties": False, "required": required, "properties": properties}}


_TEXT = {"type": "string", "minLength": 1}
_ID_SCHEMA = {"type": "string", "pattern": _ID}
_SURFACES = {
    "v1": [
        _tool("alchemy_v1_create_session", "Create one V1 orchestration session.", ["project_id"], project_id=_ID_SCHEMA, title=_TEXT),
        _tool("alchemy_v1_upload_asset", "Upload one explicitly selected local image to V1.", ["file_path", "user_confirmed_rights"], file_path=_TEXT, user_confirmed_rights={"type": "boolean"}, role={"type": "string"}),
        _tool("alchemy_v1_create_image_job", "Create one V1 image job through the existing generation path.", ["session_id", "prompt"], session_id=_ID_SCHEMA, prompt=_TEXT, asset_ids={"type": "array", "items": _ID_SCHEMA}, count={"type": "integer", "minimum": 1, "maximum": 10}, size={"type": "string"}),
        _tool("alchemy_v1_get_image_job", "Read exactly one V1 image job.", ["job_id"], job_id=_ID_SCHEMA),
        _tool("alchemy_v1_list_history", "List account-scoped V1 image history.", [], limit={"type": "integer", "minimum": 1, "maximum": 200}, offset={"type": "integer", "minimum": 0}),
        _tool("alchemy_v1_revise_image", "Create one V1 revision from an explicit output; never retries an unknown write.", ["job_id", "output_id", "feedback"], job_id=_ID_SCHEMA, output_id=_ID_SCHEMA, feedback=_TEXT),
    ],
    "v2": [
        _tool("alchemy_v2_create_creative_run", "Create one V2 creative run through the independent V2 service.", ["user_prompt"], user_prompt=_TEXT, template_case_id=_ID_SCHEMA, count={"type": "integer", "minimum": 1, "maximum": 8}),
        _tool("alchemy_v2_get_creative_run", "Read exactly one V2 creative run.", ["run_id"], run_id=_ID_SCHEMA),
        _tool("alchemy_v2_upload_asset", "Upload one explicitly selected local image to V2.", ["file_path"], file_path=_TEXT, role={"type": "string"}, intended_use={"type": "string"}),
        _tool("alchemy_v2_create_image_job", "Create one structured V2 image job.", ["prompt"], prompt=_TEXT, run_id=_ID_SCHEMA, count={"type": "integer", "minimum": 1, "maximum": 10}, size={"type": "string"}, provider_hint={"type": "string"}),
        _tool("alchemy_v2_get_image_job", "Read exactly one V2 image job.", ["job_id"], job_id=_ID_SCHEMA),
        _tool("alchemy_v2_list_history", "List account-scoped V2 image history.", [], limit={"type": "integer", "minimum": 1, "maximum": 200}, offset={"type": "integer", "minimum": 0}),
        _tool("alchemy_v2_search_cases", "Search the V2 prompt-case library.", [], query_text={"type": "string"}, limit={"type": "integer", "minimum": 1, "maximum": 50}),
        _tool("alchemy_v2_get_case", "Read one V2 prompt case.", ["case_id"], case_id=_ID_SCHEMA),
    ],
    "lab": [
        _tool("alchemy_lab_list_modules", "List enabled Alchemy Lab modules.", []),
        _tool("alchemy_lab_list_styles", "List enabled Alchemy Lab styles.", []),
        _tool("alchemy_lab_search_styles", "Search Alchemy Lab styles.", [], query={"type": "string"}),
        _tool("alchemy_lab_upload_reference", "Upload one explicitly selected local Lab reference image.", ["file_path", "user_confirmed_rights"], file_path=_TEXT, user_confirmed_rights={"type": "boolean"}, role={"type": "string"}),
        _tool("alchemy_lab_create_session", "Create one Alchemy Lab exploration session.", ["idea"], idea=_TEXT, selected_style_ids={"type": "array", "items": _ID_SCHEMA}, target_count={"type": "integer", "minimum": 1, "maximum": 24}, images_per_style={"type": "integer", "minimum": 1, "maximum": 4}, reference_assets={"type": "array", "items": {"type": "object"}}),
        _tool("alchemy_lab_get_session", "Read one account-scoped Lab session.", ["session_id"], session_id=_ID_SCHEMA),
        _tool("alchemy_lab_list_history", "List account-scoped Alchemy Lab history.", [], limit={"type": "integer", "minimum": 1, "maximum": 200}),
        _tool("alchemy_lab_update_favorites", "Update favorites for one account-owned Lab session.", ["session_id", "variant_ids"], session_id=_ID_SCHEMA, variant_ids={"type": "array", "items": _ID_SCHEMA}),
    ],
}
VERSIONED_TOOL_SCHEMAS = [item for group in _SURFACES.values() for item in group]
VERSIONED_TOOL_SCHEMAS.insert(0, _tool("alchemy_list_capabilities", "List the API and MCP surfaces available to the authenticated account.", []))
VERSIONED_TOOL_NAMES = frozenset(item["name"] for item in VERSIONED_TOOL_SCHEMAS)


class VersionedToolError(ValueError):
    def __init__(self, code: str, *, http_status: int | None = None, outcome_unknown: bool = False):
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.outcome_unknown = outcome_unknown
        self.context: dict[str, str] = {}

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"code": self.code, "automatic_retry": False, **self.context}
        if self.http_status is not None:
            result["http_status"] = self.http_status
        if self.outcome_unknown:
            result.update({"outcome_unknown": True, "instruction": "Do not repeat the write; query the existing resource first."})
        elif self.http_status == 401:
            result["instruction"] = "Use a valid Alchemy API key or existing account session."
        return result


def _validate(value: Any, schema: dict[str, Any]) -> None:
    kind = schema.get("type")
    if kind == "object":
        valid = type(value) is dict and not (set(value) - set(schema.get("properties", {}))) and all(key in value for key in schema.get("required", []))
        if valid:
            for key, item in value.items():
                _validate(item, schema["properties"][key])
    elif kind == "array":
        valid = type(value) is list and len(value) >= schema.get("minItems", 0)
        if valid:
            for item in value:
                _validate(item, schema["items"])
    elif kind == "string":
        valid = type(value) is str and bool(value.strip()) and (not schema.get("pattern") or re.fullmatch(schema["pattern"], value) is not None)
    elif kind == "integer":
        valid = type(value) is int and schema.get("minimum", value) <= value <= schema.get("maximum", value)
    elif kind == "boolean":
        valid = type(value) is bool
    else:
        valid = True
    if not valid:
        raise VersionedToolError("versioned_tool_invalid_arguments")


def _compact(value: Any) -> Any:
    blocked = {"password", "secret", "token", "api_key", "digest", "storage_path", "file_path", "authorization", "cookie"}
    if isinstance(value, list):
        return [_compact(item) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        lowered = str(key).lower()
        if any(term in lowered for term in blocked):
            continue
        if key.endswith("_url") and isinstance(item, str) and not item.startswith(("/v1/", "/api/v2/", "/api/v3/", "/api/lab/", "http://", "https://")):
            continue
        result[key] = _compact(item)
    return result


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class VersionedTools:
    def __init__(self, base_url: str, session_token: str, *, opener: Any = None):
        try:
            parsed = urlsplit(base_url)
            valid = parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment and parsed.path in {"", "/"} and (parsed.scheme == "https" or parsed.hostname in {"127.0.0.1", "localhost", "::1"})
        except ValueError:
            valid = False
        if not valid or any(ord(char) <= 32 for char in base_url):
            raise VersionedToolError("product_api_url_invalid")
        if not re.fullmatch(r"[A-Za-z0-9._~+/=-]{1,8192}", session_token or ""):
            raise VersionedToolError("product_session_required")
        self.base_url = base_url.rstrip("/")
        self._token = session_token
        self._opener = opener or build_opener(ProxyHandler({}), _NoRedirect())

    @classmethod
    def from_environment(cls) -> "VersionedTools":
        return cls(os.environ.get("ALCHEMY_PRODUCT_API_BASE_URL", ""), os.environ.get("ALCHEMY_PRODUCT_SESSION_TOKEN", ""))

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = Request(self.base_url + path, data=data, method=method, headers={"Accept": "application/json", "Content-Type": "application/json", "Authorization": "Bearer " + self._token})
        try:
            with self._opener.open(request, timeout=60) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("response limit")
            result = json.loads(raw.decode("utf-8"))
            if not isinstance(result, dict):
                raise ValueError("response shape")
            return result
        except HTTPError as exc:
            code = "product_api_http_error"
            try:
                body = json.loads(exc.read(65536).decode("utf-8"))
                detail = body.get("detail", body) if isinstance(body, dict) else {}
                original = detail.get("code", detail.get("error_code")) if isinstance(detail, dict) else None
                if isinstance(original, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,95}", original):
                    code = original
            except (ValueError, OSError):
                pass
            finally:
                exc.close()
            raise VersionedToolError(code, http_status=exc.code, outcome_unknown=method != "GET" and (exc.code >= 500 or exc.code == 408)) from None
        except (URLError, OSError, ValueError, HTTPClientError):
            raise VersionedToolError("product_api_unavailable", outcome_unknown=method != "GET") from None

    def _upload(self, *, path: str, args: dict[str, Any], consent_key: str | None = None) -> dict[str, Any]:
        file_path = Path(args["file_path"])
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(file_path.suffix.lower())
        try:
            if not file_path.is_absolute() or str(file_path).startswith(("\\\\", "//")) or not mime or not file_path.is_file():
                raise ValueError
            content = file_path.read_bytes()
            signature_ok = content.startswith(b"\x89PNG\r\n\x1a\n") if mime == "image/png" else content.startswith(b"\xff\xd8\xff") if mime == "image/jpeg" else content[:4] == b"RIFF" and content[8:12] == b"WEBP"
            if not content or len(content) > MAX_UPLOAD_BYTES or not signature_ok:
                raise ValueError
        except (OSError, ValueError):
            raise VersionedToolError("product_upload_file_invalid") from None
        payload: dict[str, Any] = {"filename": file_path.name, "mime_type": mime, "size_bytes": len(content)}
        for key in ("intended_use", "constraint_strength"):
            if key in args:
                payload[key] = args[key]
        if "role" in args:
            payload["declared_role" if path.startswith("/v1/") else "role"] = args["role"]
        if consent_key:
            payload["consent"] = {"user_confirmed_rights": bool(args[consent_key])}
        created = self._request("POST", path, payload)
        asset_id = created.get("asset_id")
        if not isinstance(asset_id, str) or not re.fullmatch(_ID, asset_id):
            raise VersionedToolError("product_api_response_invalid", outcome_unknown=True)
        try:
            if created.get("status") not in {None, "upload_requested"}:
                return _compact(created)
            stored = self._request("PUT", f"{path}/{asset_id}/content", {"content_base64": base64.b64encode(content).decode("ascii"), "mime_type": mime})
            if stored.get("status") in {"failed", "rejected", "scan_failed", "normalize_failed", "analysis_failed"}:
                return _compact(stored)
            return _compact(self._request("POST", f"{path}/{asset_id}/complete", {}))
        except VersionedToolError as exc:
            exc.context["asset_id"] = asset_id
            raise

    def call(self, name: str, arguments: Any) -> dict[str, Any]:
        schema = next((item["inputSchema"] for item in VERSIONED_TOOL_SCHEMAS if item["name"] == name), None)
        if schema is None:
            raise VersionedToolError("versioned_tool_unknown")
        _validate(arguments, schema)
        args = dict(arguments)
        try:
            if name == "alchemy_list_capabilities":
                result = self._request("GET", "/api/access/capabilities")
            elif name == "alchemy_v1_create_session":
                result = self._request("POST", "/v1/sessions", {key: args[key] for key in ("project_id", "title") if key in args})
            elif name == "alchemy_v1_upload_asset":
                result = self._upload(path="/v1/assets/upload-url", args=args, consent_key="user_confirmed_rights")
            elif name == "alchemy_v1_create_image_job":
                result = self._request("POST", "/v1/image/jobs", {**{key: args[key] for key in ("session_id", "prompt", "asset_ids", "count", "size") if key in args}})
            elif name == "alchemy_v1_get_image_job":
                result = self._request("GET", f"/v1/image/jobs/{args['job_id']}")
            elif name == "alchemy_v1_list_history":
                result = self._request("GET", "/v1/image/history?" + urlencode({key: args[key] for key in ("limit", "offset") if key in args}))
            elif name == "alchemy_v1_revise_image":
                result = self._request("POST", f"/v1/image/jobs/{args['job_id']}/revise", {key: args[key] for key in ("output_id", "feedback") if key in args})
            elif name == "alchemy_v2_create_creative_run":
                output = {"count": args.get("count", 1)}
                result = self._request("POST", "/api/v2/creative/runs", {"user_prompt": args["user_prompt"], "template_case_id": args.get("template_case_id"), "output": output})
            elif name == "alchemy_v2_get_creative_run":
                result = self._request("GET", f"/api/v2/creative/runs/{args['run_id']}")
            elif name == "alchemy_v2_upload_asset":
                result = self._upload(path="/api/v2/uploads", args=args)
            elif name == "alchemy_v2_create_image_job":
                result = self._request("POST", "/api/v2/image/jobs", {"run_id": args.get("run_id"), "prompt_plan": {"plan_id": "mcp_plan", "mode": "smart_enhance", "prompt": args["prompt"], "provider_parameters": {"count": args.get("count", 1), "size": args.get("size") or "1024x1024"}}, "provider_hint": args.get("provider_hint")})
            elif name == "alchemy_v2_get_image_job":
                result = self._request("GET", f"/api/v2/image/jobs/{args['job_id']}")
            elif name == "alchemy_v2_list_history":
                result = self._request("GET", "/api/v2/image/history?" + urlencode({key: args[key] for key in ("limit", "offset") if key in args}))
            elif name == "alchemy_v2_search_cases":
                result = self._request("POST", "/api/v2/prompt-cases/search", {"query_text": args.get("query_text", ""), "limit": args.get("limit", 10)})
            elif name == "alchemy_v2_get_case":
                result = self._request("GET", f"/api/v2/prompt-cases/{args['case_id']}")
            elif name == "alchemy_lab_list_modules":
                result = self._request("GET", "/api/lab/modules")
            elif name == "alchemy_lab_list_styles":
                result = self._request("GET", "/api/lab/rare-style-explorer/styles")
            elif name == "alchemy_lab_search_styles":
                result = self._request("POST", "/api/lab/rare-style-explorer/styles/search", {"query_text": args.get("query", "")})
            elif name == "alchemy_lab_upload_reference":
                result = self._upload(path="/api/lab/uploads", args=args, consent_key="user_confirmed_rights")
            elif name == "alchemy_lab_create_session":
                result = self._request("POST", "/api/lab/rare-style-explorer/sessions", {key: args[key] for key in ("idea", "selected_style_ids", "target_count", "images_per_style", "reference_assets") if key in args})
            elif name == "alchemy_lab_get_session":
                result = self._request("GET", f"/api/lab/rare-style-explorer/sessions/{args['session_id']}")
            elif name == "alchemy_lab_list_history":
                result = self._request("GET", "/api/lab/history?" + urlencode({"limit": args.get("limit", 50)}))
            else:
                result = self._request("POST", f"/api/lab/rare-style-explorer/sessions/{args['session_id']}/favorites", {"variant_ids": args["variant_ids"]})
        except VersionedToolError as exc:
            for key in ("job_id", "run_id", "session_id", "case_id", "asset_id"):
                if key in args:
                    exc.context[key] = str(args[key])
            raise
        return _compact(result)
