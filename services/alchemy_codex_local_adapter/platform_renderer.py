"""Explicit, local-only OpenAI Platform Image API renderer for Doc117 B2.

This sidecar does not import V3 Web providers, read their environment, or
offer their routes as a fallback.  Its only live endpoint is the fixed official
OpenAI Platform Image API endpoint.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import socket
from typing import Any, Protocol
from urllib import error as urlerror
from urllib import request as urlrequest

from .contracts import (
    LOCAL_EVIDENCE_SCOPE,
    LocalModeAdapterError,
    PLATFORM_OPENAI_GPT_IMAGE_2_MODEL,
    PLATFORM_OPENAI_GPT_IMAGE_2_RENDERER,
    PlatformRenderedImage,
    _clean_direction,
    require_identifier,
)


OFFICIAL_PLATFORM_API_BASE = "https://api.openai.com/v1"
IMAGE_GENERATIONS_PATH = "/images/generations"
LOCAL_IMAGE_API_KEY_FILE_ENV = "ALCHEMY_CODEX_LOCAL_IMAGE_API_KEY_FILE"


@dataclass(frozen=True)
class PlatformHttpResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes


class PlatformHttpTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: dict[str, Any],
        timeout_s: float,
    ) -> PlatformHttpResponse: ...


class _PlatformTimeout(Exception):
    pass


class _PlatformTransportFailure(Exception):
    pass


class UrllibOfficialImageTransport:
    """A one-request stdlib transport; it is never started by Web Mode."""

    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: dict[str, Any],
        timeout_s: float,
    ) -> PlatformHttpResponse:
        request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_object = urlrequest.Request(url=url, data=request_body, headers=dict(headers), method="POST")
        try:
            with urlrequest.urlopen(request_object, timeout=timeout_s) as response:  # noqa: S310 - URL is a fixed constant.
                return PlatformHttpResponse(
                    status_code=int(response.status),
                    headers={str(key).lower(): str(value) for key, value in response.headers.items()},
                    body=response.read(),
                )
        except urlerror.HTTPError as exc:
            return PlatformHttpResponse(
                status_code=int(exc.code),
                headers={str(key).lower(): str(value) for key, value in exc.headers.items()} if exc.headers else {},
                body=exc.read(64 * 1024),
            )
        except (socket.timeout, TimeoutError) as exc:
            raise _PlatformTimeout from exc
        except urlerror.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise _PlatformTimeout from exc
            raise _PlatformTransportFailure from exc
        except OSError as exc:
            raise _PlatformTransportFailure from exc


class PlatformImageRenderer:
    """Generate exactly one whole image from one recorded Local Mode direction."""

    def __init__(
        self,
        *,
        live_platform_opt_in: bool = False,
        transport: PlatformHttpTransport | None = None,
        environment: Mapping[str, str] | None = None,
        user_home: str | Path | None = None,
        repository_root: str | Path | None = None,
        request_timeout_s: float = 120.0,
        base_url: str | None = None,
    ) -> None:
        if base_url is not None:
            raise LocalModeAdapterError(
                "codex_local_platform_renderer_base_url_forbidden",
                "The Local Mode Platform renderer has a fixed official API base URL.",
            )
        if not 5.0 <= float(request_timeout_s) <= 180.0:
            raise LocalModeAdapterError("codex_local_platform_renderer_invalid_timeout", "Platform renderer timeout must be between 5 and 180 seconds.")
        self._live_platform_opt_in = bool(live_platform_opt_in)
        self._transport = transport or UrllibOfficialImageTransport()
        self._mock_transport = transport is not None
        self._environment = environment
        self._user_home = Path(user_home).resolve() if user_home else Path.home().resolve()
        self._repository_root = Path(repository_root).resolve() if repository_root else Path(__file__).resolve().parents[2]
        self._timeout_s = float(request_timeout_s)

    def render(self, *, direction: str, role_id: str) -> PlatformRenderedImage:
        """Call the official Image API once. There is no retry or provider fallback."""

        clean_direction = _clean_direction(direction)
        clean_role_id = require_identifier(role_id, "role_id")
        authorization = self._authorization_header()
        payload = {
            "model": PLATFORM_OPENAI_GPT_IMAGE_2_MODEL,
            "prompt": clean_direction,
            "n": 1,
            "size": "auto",
            "quality": "auto",
            "background": "auto",
            "output_format": "png",
        }
        request_summary = {
            "api_base": OFFICIAL_PLATFORM_API_BASE,
            "endpoint": IMAGE_GENERATIONS_PATH,
            "model": PLATFORM_OPENAI_GPT_IMAGE_2_MODEL,
            "role_id": clean_role_id,
            "n": 1,
            "size": "auto",
            "quality": "auto",
            "background": "auto",
            "output_format": "png",
            "prompt_sha256": f"sha256:{hashlib.sha256(clean_direction.encode('utf-8')).hexdigest()}",
        }
        try:
            response = self._transport.post_json(
                url=f"{OFFICIAL_PLATFORM_API_BASE}{IMAGE_GENERATIONS_PATH}",
                headers={
                    "Authorization": authorization,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                payload=payload,
                timeout_s=self._timeout_s,
            )
        except (_PlatformTimeout, TimeoutError) as exc:
            raise LocalModeAdapterError("codex_local_platform_renderer_timeout", "Official Platform image request timed out.") from exc
        except _PlatformTransportFailure as exc:
            raise LocalModeAdapterError("codex_local_platform_renderer_transport_failed", "Official Platform image request could not be completed.") from exc

        if response.status_code >= 500:
            raise LocalModeAdapterError(
                f"codex_local_platform_renderer_upstream_{response.status_code}",
                "Official Platform image service returned a server error.",
            )
        if response.status_code != 200:
            raise LocalModeAdapterError(
                f"codex_local_platform_renderer_api_{response.status_code}",
                "Official Platform image request was rejected.",
            )

        response_summary = {
            "http_status": response.status_code,
            "response_body_sha256": f"sha256:{hashlib.sha256(response.body).hexdigest()}",
        }
        request_id = str(response.headers.get("x-request-id") or "").strip()
        if request_id and len(request_id) <= 256:
            response_summary["request_id"] = request_id
        try:
            body = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LocalModeAdapterError("codex_local_platform_renderer_invalid_response", "Official Platform image response was not valid JSON.") from exc
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            raise LocalModeAdapterError("codex_local_platform_renderer_empty_response", "Official Platform image response contained no single final image.")
        encoded_image = data[0].get("b64_json")
        if not isinstance(encoded_image, str) or not encoded_image.strip():
            raise LocalModeAdapterError("codex_local_platform_renderer_empty_response", "Official Platform image response did not include image bytes.")
        try:
            image_bytes = base64.b64decode(encoded_image, validate=True)
        except (ValueError, TypeError) as exc:
            raise LocalModeAdapterError("codex_local_platform_renderer_invalid_image_payload", "Official Platform image payload was not valid base64.") from exc
        if not image_bytes:
            raise LocalModeAdapterError("codex_local_platform_renderer_empty_response", "Official Platform image payload was empty.")
        response_summary["returned_image_count"] = 1
        response_summary["evidence_scope"] = LOCAL_EVIDENCE_SCOPE
        return PlatformRenderedImage(
            image_bytes=image_bytes,
            mime_type="image/png",
            request_summary=request_summary,
            response_summary=response_summary,
        )

    def _authorization_header(self) -> str:
        if self._mock_transport:
            # Test transports exercise the contract without a user credential or live request.
            return "Bearer mock-local-contract-only"
        if not self._live_platform_opt_in:
            raise LocalModeAdapterError(
                "codex_local_platform_renderer_disabled",
                "Explicit live Platform Image API opt-in is required.",
            )
        return f"Bearer {self._read_dedicated_api_key()}"

    def _read_dedicated_api_key(self) -> str:
        environment = self._environment if self._environment is not None else os.environ
        configured_path = str(environment.get(LOCAL_IMAGE_API_KEY_FILE_ENV) or "").strip()
        if not configured_path:
            raise LocalModeAdapterError(
                "codex_local_platform_renderer_key_missing",
                "Dedicated Local Mode Platform API key file is not configured.",
            )
        raw_path = Path(configured_path).expanduser()
        if not raw_path.is_absolute() or raw_path.is_symlink():
            raise LocalModeAdapterError("codex_local_platform_renderer_key_file_invalid", "Dedicated key file path is invalid.")
        try:
            key_path = raw_path.resolve(strict=True)
        except (OSError, FileNotFoundError) as exc:
            raise LocalModeAdapterError("codex_local_platform_renderer_key_file_unreadable", "Dedicated key file cannot be read.") from exc
        if not key_path.is_file() or self._repository_root == key_path or self._repository_root in key_path.parents:
            raise LocalModeAdapterError("codex_local_platform_renderer_key_file_invalid", "Dedicated key file must not be in the repository.")
        if self._user_home != key_path and self._user_home not in key_path.parents:
            raise LocalModeAdapterError("codex_local_platform_renderer_key_file_invalid", "Dedicated key file must be under the user home directory.")
        try:
            api_key = key_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise LocalModeAdapterError("codex_local_platform_renderer_key_file_unreadable", "Dedicated key file cannot be read.") from exc
        if not 16 <= len(api_key) <= 4096 or any(ord(character) < 33 or ord(character) > 126 for character in api_key):
            raise LocalModeAdapterError("codex_local_platform_renderer_key_file_invalid", "Dedicated key file has invalid contents.")
        return api_key
