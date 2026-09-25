"""Thin, authenticated calls to the existing V3 HTTP product endpoints.

No service/store/provider imports, automatic retries or alternate billing path.
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

API = "/api/v3/creative-agent"
MAX_UPLOAD_BYTES = 12 * 1024 * 1024  # Existing V3 upload limit, also enforced by server.
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_ID = {"type": "string", "pattern": r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"}
_TEXT = {"type": "string", "minLength": 1}
_IDS = {"type": "array", "items": _ID, "uniqueItems": True}


def _tool(name: str, description: str, required: list[str], **properties: Any) -> dict:
    return {"name": name, "description": description, "inputSchema": {
        "type": "object", "additionalProperties": False,
        "required": required, "properties": properties,
    }}


PRODUCT_TOOL_SCHEMAS = [
    _tool("alchemy_create_project", "Create a project through the existing account/API. No image generation.",
          ["user_goal"], user_goal=_TEXT, title=_TEXT, primary_template_id=_ID, uploaded_asset_ids=_IDS),
    _tool("alchemy_upload_asset", "Upload ONLY a local image explicitly selected/authorized by the user. Sends file bytes, not a server path. No image generation.",
          ["file_path"], file_path=_TEXT, role=_TEXT),
    _tool("alchemy_create_generation", "Create and auto-generate ONCE in a project using the normal Web billing/review flow. May charge the current account. Returns the original operation/job ID; do not repeat on timeout.",
          ["project_id", "user_input"], project_id=_ID, user_input=_TEXT, template_id=_ID,
          uploaded_asset_ids=_IDS, requested_image_count={"type": "integer", "minimum": 1, "maximum": 16},
          requested_image_size=_TEXT, quality_mode={"type": "string", "enum": ["standard", "explore", "strict"]},
          use_project_context={"type": "boolean"}),
    _tool("alchemy_get_generation", "Query EXACTLY ONE project_id (before a Job exists) or job_id. Uses existing status/recovery semantics; never submits a new generation.",
          [], project_id=_ID, job_id=_ID),
    _tool("alchemy_list_outputs", "List a project's original delivery and review lists separately. URLs require the same account credential. No quality verdict is calculated here.",
          ["project_id"], project_id=_ID, limit={"type": "integer", "minimum": 1, "maximum": 60}),
    _tool("alchemy_select_outputs", "Select explicit output IDs using the existing project selection gate. A held selection is not success; no generation or direct winner write.",
          ["project_id", "job_id", "selected_output_ids"], project_id=_ID, job_id=_ID,
          selected_output_ids={**_IDS, "minItems": 1}),
]
PRODUCT_TOOL_NAMES = frozenset(tool["name"] for tool in PRODUCT_TOOL_SCHEMAS)


class ProductToolError(ValueError):
    """Safe transport diagnostics, never an invented business Job status."""
    def __init__(self, code: str, *, http_status: int | None = None, outcome_unknown: bool = False):
        super().__init__(code)
        self.code, self.http_status, self.outcome_unknown = code, http_status, outcome_unknown
        self.context: dict[str, str] = {}

    def as_dict(self) -> dict:
        result = {"code": self.code, "automatic_retry": False, **self.context}
        if self.http_status is not None:
            result["http_status"] = self.http_status
        if self.outcome_unknown:
            result["outcome_unknown"] = True
            result["instruction"] = "Do not repeat the write; check the existing project/operation or upload first."
        elif self.http_status == 401 or self.code == "product_session_required":
            result["instruction"] = "Sign in through the existing account flow and supply a valid session."
        return result


def _validate(value: Any, schema: dict) -> None:
    """Validate only the small JSON-schema subset declared by these six tools."""
    kind = schema["type"]
    expected = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}[kind]
    valid = type(value) is expected
    if valid and kind == "object":
        valid = not (set(value) - schema["properties"].keys()) and all(k in value for k in schema["required"])
        if valid:
            for key, item in value.items():
                _validate(item, schema["properties"][key])
    elif valid and kind == "array":
        valid = len(value) >= schema.get("minItems", 0)
        for item in value:
            _validate(item, schema["items"])
        valid = valid and (not schema.get("uniqueItems") or len(set(value)) == len(value))
    elif valid and kind == "string":
        valid = bool(value.strip()) and (not schema.get("pattern") or re.fullmatch(schema["pattern"], value) is not None)
    elif valid and kind == "integer":
        valid = schema.get("minimum", value) <= value <= schema.get("maximum", value)
    if not valid or ("enum" in schema and value not in schema["enum"]):
        raise ProductToolError("product_tool_invalid_arguments")


# Copy existing product facts only. No new scores, decisions, IDs or state mapping.
# In particular raw metadata, Brain prompts, provider receipts and local paths do not escape.
_FIELDS = frozenset("""
project project_id title primary_template_id job_ids job_id status state operation_id current_operation
terminal pending created_at updated_at metadata candidates asset_series selected_result job_status
asset_id filename mime_type size_bytes role content_sha256 output_id candidate_id selected
selected_candidate_ids selected_asset_ids selected_output_ids selected_output_refs output_ref_id
items review_items project_outputs project_output_counts project_review_counts total limit has_more next_cursor
final_delivery final_delivery_status automatic_delivery_available manual_confirmation_required
final_delivery_output_count delivery_gate_applies partial_delivery recommended_output_ids recommendation
post_generation_review review_status verification_state certification_state public_delivery_state
quality_assessment quality_failure evidence_state review_reason mode real_pixel_review_attempted
real_pixel_review_certified review_evidence_receipt_status selection_status selection_held hold_reason
continuation_available selected_template_id template_id generation_lifecycle_failure failure_family
failure_category failure_code retry_allowed provider_request_started background_planning_started
background_planning_pending next_actions id code error
""".split())
_LINKS = frozenset({"download_url", "preview_url", "thumbnail_url", "content_url", "upload_url"})
_LINK_PATTERN = re.compile(r"^/api/v3/creative-agent/(outputs|uploads)/[A-Za-z0-9_-]+/(download|preview|thumbnail|content)$")


def _compact(value: Any) -> Any:
    if isinstance(value, list):
        return [_compact(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in _LINKS:
            if isinstance(item, str) and _LINK_PATTERN.fullmatch(item):
                result[key] = item
        elif key in {"project_output_counts", "project_review_counts"} and isinstance(item, dict):
            result[key] = {k: v for k, v in item.items() if re.fullmatch(_ID["pattern"], k) and type(v) is int}
        elif key == "error" and not isinstance(item, dict):
            continue  # Never echo an unstructured exception containing paths/secrets.
        elif key in _FIELDS:
            result[key] = _compact(item)
    return result


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a session or replay a write to a redirected target.


class ProductTools:
    def __init__(self, base_url: str, session_token: str, *, opener: Any = None):
        try:
            url = urlsplit(base_url)
            valid = (url.scheme in {"https", "http"} and bool(url.hostname)
                     and not url.username and not url.password and not url.query and not url.fragment
                     and url.path in {"", "/"} and url.port != 0
                     and (url.scheme == "https" or url.hostname in {"127.0.0.1", "localhost", "::1"})
                     and not any(ord(c) <= 32 for c in base_url))
        except ValueError:
            valid = False
        if not valid:
            raise ProductToolError("product_api_url_invalid")
        if not re.fullmatch(r"[A-Za-z0-9._~+/=-]{1,8192}", session_token):
            raise ProductToolError("product_session_required")
        self.base_url, self._token = base_url.rstrip("/"), session_token
        self._opener = opener or build_opener(ProxyHandler({}), _NoRedirect())

    @classmethod
    def from_environment(cls) -> ProductTools:
        # Explicit configuration only; no browser-cookie/password discovery.
        return cls(os.environ.get("ALCHEMY_PRODUCT_API_BASE_URL", ""),
                   os.environ.get("ALCHEMY_PRODUCT_SESSION_TOKEN", ""))

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = Request(self.base_url + API + path, data=data, method=method, headers={
            "Accept": "application/json", "Content-Type": "application/json",
            "Authorization": "Bearer " + self._token,
        })
        try:
            with self._opener.open(request, timeout=30) as response:
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
                original_code = detail.get("code", detail.get("error_code")) if isinstance(detail, dict) else None
                if isinstance(original_code, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,95}", original_code) and self._token not in original_code:
                    code = original_code
            except (ValueError, OSError):
                pass
            finally:
                exc.close()
            raise ProductToolError(code, http_status=exc.code,
                                   outcome_unknown=method != "GET" and (exc.code >= 500 or exc.code == 408)) from None
        except (URLError, OSError, ValueError, HTTPClientError) as exc:
            code = "product_api_unavailable" if isinstance(exc, (URLError, OSError, HTTPClientError)) else "product_api_response_invalid"
            raise ProductToolError(code, outcome_unknown=method != "GET") from None

    def call(self, name: str, arguments: Any) -> dict:
        schema = next((s["inputSchema"] for s in PRODUCT_TOOL_SCHEMAS if s["name"] == name), None)
        if schema is None:
            raise ProductToolError("product_tool_unknown")
        _validate(arguments, schema)
        args = dict(arguments)
        try:
            if name == "alchemy_create_project":
                result = self._request("POST", "/projects", args)
            elif name == "alchemy_upload_asset":
                result = self._upload(args)
            elif name == "alchemy_create_generation":
                metadata = {"require_real_images": True, "requested_image_count": args.get("requested_image_count", 1)}
                if "requested_image_size" in args:
                    metadata["requested_image_size"] = args["requested_image_size"]
                result = self._request("POST", f"/projects/{args['project_id']}/jobs", {
                    "user_input": args["user_input"], "template_id": args.get("template_id", "general_template"),
                    "uploaded_asset_ids": args.get("uploaded_asset_ids", []),
                    "use_project_context": args.get("use_project_context", True), "metadata": metadata,
                    "auto_generate": {"quality_mode": args.get("quality_mode", "standard"), "metadata": metadata},
                })
            elif name == "alchemy_get_generation":
                if len(args) != 1:
                    raise ProductToolError("product_tool_invalid_arguments")
                result = self._request("GET", f"/jobs/{args['job_id']}" if "job_id" in args
                                       else f"/projects/{args['project_id']}")
            elif name == "alchemy_list_outputs":
                result = self._request("GET", "/project-outputs?" + urlencode({
                    "project_id": args["project_id"], "compact": "true", "limit": args.get("limit", 60)}))
            else:
                result = self._request("POST", f"/projects/{args['project_id']}/jobs/{args['job_id']}/select",
                                       {"selected_output_ids": args["selected_output_ids"]})
        except ProductToolError as exc:
            exc.context.update({key: args[key] for key in ("project_id", "job_id") if key in args})
            raise
        public = _compact(result)
        if "project_id" in args:
            public.setdefault("project_id", args["project_id"])
        return public

    def _upload(self, args: dict) -> dict:
        path = Path(args["file_path"])
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(path.suffix.lower())
        try:
            if not path.is_absolute() or str(path).startswith(("\\\\", "//")) or not mime or not path.is_file():
                raise ValueError("not an authorized local image path")
            with path.open("rb") as handle:
                content = handle.read(MAX_UPLOAD_BYTES + 1)
            signature_ok = (content.startswith(b"\x89PNG\r\n\x1a\n") if mime == "image/png" else
                            content.startswith(b"\xff\xd8\xff") if mime == "image/jpeg" else
                            content[:4] == b"RIFF" and content[8:12] == b"WEBP")
            if not 0 < len(content) <= MAX_UPLOAD_BYTES or not signature_ok:
                raise ValueError("unsupported image")
        except (OSError, ValueError):
            raise ProductToolError("product_upload_file_invalid") from None
        payload = {"filename": path.name, "mime_type": mime, "size_bytes": len(content)}
        if "role" in args:
            payload["role"] = args["role"]
        created = self._request("POST", "/uploads", payload)
        asset_id = created.get("asset_id")
        if not isinstance(asset_id, str) or not re.fullmatch(_ID["pattern"], asset_id):
            raise ProductToolError("product_api_response_invalid", outcome_unknown=True)
        try:
            if created.get("status") != "upload_requested":
                return created
            stored = self._request("PUT", f"/uploads/{asset_id}/content", {
                "content_base64": base64.b64encode(content).decode("ascii"), "mime_type": mime})
            if stored.get("status") != "stored":
                return stored
            return self._request("POST", f"/uploads/{asset_id}/complete", {})
        except ProductToolError as exc:
            exc.context["asset_id"] = asset_id
            raise
