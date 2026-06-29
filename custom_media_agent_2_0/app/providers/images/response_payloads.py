from __future__ import annotations

import asyncio
import base64
import binascii
import re
from typing import Any

import httpx

from app.providers.images.base import V2ImageProviderOutput, V2ImageProviderRuntimeError


_MAX_FETCHED_IMAGE_BYTES = 32 * 1024 * 1024
_IMAGE_FIELD_KEYS = (
    "b64_json",
    "base64",
    "image_base64",
    "image_b64",
    "image",
    "url",
    "image_url",
    "output_url",
    "result",
)
_CONTAINER_KEYS = ("data", "output", "outputs", "images", "results", "items", "content", "parts")
_KNOWN_OBJECT_KEYS = (
    *_CONTAINER_KEYS,
    *_IMAGE_FIELD_KEYS,
    "mime_type",
    "content_type",
    "format",
    "width",
    "height",
    "size",
    "dimensions",
)


async def outputs_from_image_response(
    response: Any,
    plan: Any,
    *,
    provider: str,
    missing_message: str,
    index: int,
    operation: str,
    reference_count: int,
    default_format: str = "png",
    default_mime_type: str | None = None,
    url_timeout_seconds: float = 60.0,
) -> list[V2ImageProviderOutput]:
    outputs: list[V2ImageProviderOutput] = []
    for entry in _candidate_entries(response):
        extracted = await _extract_image_payload(entry, url_timeout_seconds=url_timeout_seconds)
        if not extracted:
            continue
        encoded, mime_type, fmt, delivery = extracted
        final_format = _normalize_format(fmt or default_format)
        final_mime = mime_type or default_mime_type or f"image/{final_format}"
        width, height = _dimensions_from_entry(entry) or _dimensions_from_plan(plan)
        outputs.append(
            V2ImageProviderOutput(
                b64_json=encoded,
                mime_type=final_mime,
                format=final_format,
                width=width,
                height=height,
                metadata={
                    "request_index": index,
                    "api_operation": operation,
                    "reference_image_count": reference_count,
                    "response_delivery": delivery,
                },
            )
        )
    if not outputs:
        raise V2ImageProviderRuntimeError(
            missing_message,
            provider=provider,
            detail={
                "request_index": index,
                "operation": operation,
                "reference_image_count": reference_count,
                "response_summary": response_summary(response),
            },
        )
    return outputs


def response_summary(response: Any) -> dict[str, Any]:
    plain = _to_plain(response)
    summary: dict[str, Any] = {"type": type(response).__name__}
    if isinstance(plain, dict):
        keys = sorted(str(key) for key in plain.keys())
        summary["keys"] = keys[:20]
        for key in ("data", "output", "outputs", "images", "results"):
            value = plain.get(key)
            if isinstance(value, list):
                summary[f"{key}_count"] = len(value)
                if value:
                    first = _to_plain(value[0])
                    if isinstance(first, dict):
                        summary[f"first_{key}_keys"] = sorted(str(item) for item in first.keys())[:20]
                break
    elif isinstance(plain, list):
        summary["list_count"] = len(plain)
        if plain:
            first = _to_plain(plain[0])
            summary["first_type"] = type(first).__name__
            if isinstance(first, dict):
                summary["first_keys"] = sorted(str(key) for key in first.keys())[:20]
    else:
        summary["value_type"] = type(plain).__name__
    return summary


def _candidate_entries(value: Any) -> list[Any]:
    plain = _to_plain(value)
    if isinstance(plain, list):
        return plain
    if not isinstance(plain, dict):
        return [plain]
    entries: list[Any] = []
    for key in _CONTAINER_KEYS:
        nested = plain.get(key)
        if isinstance(nested, list):
            entries.extend(nested)
    if not entries:
        entries.append(plain)
    return entries


async def _extract_image_payload(
    value: Any,
    *,
    url_timeout_seconds: float,
    depth: int = 0,
    trust_base64: bool = False,
) -> tuple[str, str | None, str | None, str] | None:
    if depth > 6:
        return None
    plain = _to_plain(value)
    if isinstance(plain, str):
        return await _payload_from_string(plain, url_timeout_seconds=url_timeout_seconds, trust_base64=trust_base64)
    if isinstance(plain, list):
        for item in plain:
            extracted = await _extract_image_payload(
                item,
                url_timeout_seconds=url_timeout_seconds,
                depth=depth + 1,
                trust_base64=trust_base64,
            )
            if extracted:
                return extracted
        return None
    if not isinstance(plain, dict):
        return None
    for key in _IMAGE_FIELD_KEYS:
        if key not in plain:
            continue
        key_trusts_base64 = key in {"b64_json", "base64", "image_base64", "image_b64"}
        extracted = await _extract_image_payload(
            plain[key],
            url_timeout_seconds=url_timeout_seconds,
            depth=depth + 1,
            trust_base64=trust_base64 or key_trusts_base64,
        )
        if extracted:
            return extracted
    for key in _CONTAINER_KEYS:
        if key not in plain:
            continue
        extracted = await _extract_image_payload(
            plain[key],
            url_timeout_seconds=url_timeout_seconds,
            depth=depth + 1,
            trust_base64=trust_base64,
        )
        if extracted:
            return extracted
    return None


async def _payload_from_string(
    value: str,
    *,
    url_timeout_seconds: float,
    trust_base64: bool,
) -> tuple[str, str | None, str | None, str] | None:
    text = value.strip()
    if not text:
        return None
    data_url = re.match(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", text, flags=re.DOTALL)
    if data_url:
        mime_type = data_url.group(1).lower()
        return data_url.group(2).strip(), mime_type, _format_from_mime(mime_type), "data_url"
    if text.startswith(("http://", "https://")):
        return await _fetch_image_url_as_b64(text, timeout_seconds=url_timeout_seconds)
    if trust_base64:
        return text, None, None, "b64_json"
    if _looks_like_image_base64(text):
        return text, None, None, "base64"
    return None


async def _fetch_image_url_as_b64(url: str, *, timeout_seconds: float) -> tuple[str, str | None, str | None, str]:
    timeout = httpx.Timeout(max(1.0, timeout_seconds), connect=min(20.0, max(1.0, timeout_seconds)))
    last_error: httpx.HTTPError | None = None
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for attempt in range(1, 4):
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    break
                except httpx.HTTPError as exc:
                    last_error = exc
                    if attempt >= 3:
                        raise
                    await asyncio.sleep(min(1.5 * attempt, 4.0))
    except httpx.HTTPError as exc:
        raise V2ImageProviderRuntimeError(
            "Image URL response could not be fetched.",
            provider=None,
            detail={
                "url": _redacted_url(url),
                "error_type": type(exc).__name__,
                "message": str(exc)[:500],
                "attempts": 3,
            },
            retryable=True,
        ) from exc
    if last_error:
        delivery_suffix = "_after_retry"
    else:
        delivery_suffix = ""
    content = response.content
    if len(content) > _MAX_FETCHED_IMAGE_BYTES:
        raise V2ImageProviderRuntimeError(
            "Image URL response is too large.",
            provider=None,
            detail={"url": _redacted_url(url), "byte_count": len(content), "max_bytes": _MAX_FETCHED_IMAGE_BYTES},
        )
    mime_type = _content_type(response.headers.get("content-type")) or _mime_from_magic(content)
    return base64.b64encode(content).decode("ascii"), mime_type, _format_from_mime(mime_type), "url" + delivery_suffix


def _looks_like_image_base64(value: str) -> bool:
    if len(value) < 100:
        return False
    try:
        content = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return False
    return _mime_from_magic(content) is not None


def _to_plain(value: Any) -> Any:
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    for attr in ("model_dump", "dict", "to_dict"):
        method = getattr(value, attr, None)
        if callable(method):
            try:
                return method()
            except TypeError:
                try:
                    return method(mode="json")
                except TypeError:
                    pass
    try:
        plain = vars(value)
    except TypeError:
        plain = {}
    if plain:
        return plain
    object_fields: dict[str, Any] = {}
    for key in _KNOWN_OBJECT_KEYS:
        try:
            attr_value = getattr(value, key)
        except Exception:
            continue
        if callable(attr_value):
            continue
        object_fields[key] = attr_value
    return object_fields or value


def _dimensions_from_entry(entry: Any) -> tuple[int | None, int | None] | None:
    plain = _to_plain(entry)
    if not isinstance(plain, dict):
        return None
    for key in ("size", "dimensions"):
        parsed = _dimensions_from_size(plain.get(key))
        if parsed:
            return parsed
    width = _int_or_none(plain.get("width"))
    height = _int_or_none(plain.get("height"))
    if width and height:
        return width, height
    return None


def _dimensions_from_plan(plan: Any) -> tuple[int | None, int | None]:
    params = getattr(plan, "provider_parameters", None) or {}
    size = params.get("size") or params.get("aspect_ratio")
    return _dimensions_from_size(size) or (None, None)


def _dimensions_from_size(value: Any) -> tuple[int | None, int | None] | None:
    if not value:
        return None
    raw = str(value).strip().lower()
    if "x" in raw:
        try:
            width, height = raw.split("x", 1)
            return int(width), int(height)
        except ValueError:
            return None
    mapping = {
        "1:1": (1024, 1024),
        "2:3": (1024, 1536),
        "3:2": (1536, 1024),
        "3:4": (1024, 1536),
        "4:3": (1536, 1024),
        "9:16": (1024, 1536),
        "16:9": (1536, 1024),
    }
    return mapping.get(raw)


def _mime_from_magic(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        return "image/gif"
    return None


def _format_from_mime(mime_type: str | None) -> str | None:
    if not mime_type:
        return None
    subtype = mime_type.split("/", 1)[-1].split(";", 1)[0].lower()
    if subtype == "jpg":
        return "jpeg"
    if subtype in {"png", "jpeg", "webp", "gif"}:
        return subtype
    return None


def _normalize_format(value: str | None) -> str:
    raw = str(value or "png").split("/", 1)[-1].lower()
    if raw == "jpg":
        raw = "jpeg"
    return raw if raw in {"png", "jpeg", "webp", "gif"} else "png"


def _content_type(value: str | None) -> str | None:
    if not value:
        return None
    content_type = value.split(";", 1)[0].strip().lower()
    return content_type if content_type.startswith("image/") else None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _redacted_url(url: str) -> str:
    return url.split("?", 1)[0][:300]
