from __future__ import annotations

import base64
import hashlib
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from app.config import settings


async def signed_output_url(*, output_id: str, source_path: Path, storage_root: Path | None = None) -> str | None:
    if not _enabled():
        return None
    try:
        if not source_path.exists() or not source_path.is_file():
            return None
        resolved = source_path.resolve()
        root = (storage_root or settings.media_storage_root).resolve()
        generated_root = (root / "generated_images").resolve()
    except OSError:
        return None
    if generated_root != resolved and generated_root not in resolved.parents:
        return None

    relative_path = resolved.relative_to(root).as_posix()
    expires = int(time.time()) + max(30, settings.media_acceleration_url_ttl_seconds)
    uri = f"/dl/v1/{quote(relative_path, safe='/')}"
    url = _signed_url(uri=uri, expires=expires)
    if settings.media_acceleration_verify_remote and not await _remote_exists(url):
        return None
    return url


def _enabled() -> bool:
    return bool(
        settings.media_acceleration_enabled
        and settings.media_acceleration_base_url
        and settings.media_acceleration_signing_secret
    )


def _signed_url(*, uri: str, expires: int) -> str:
    secret = settings.media_acceleration_signing_secret or ""
    digest = hashlib.md5(f"{expires}{uri} {secret}".encode("utf-8")).digest()
    signature = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{settings.media_acceleration_base_url}{uri}?expires={expires}&md5={signature}"


async def _remote_exists(url: str) -> bool:
    timeout = max(0.2, settings.media_acceleration_verify_timeout_seconds)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.head(url)
    except httpx.HTTPError:
        return False
    return 200 <= response.status_code < 300
