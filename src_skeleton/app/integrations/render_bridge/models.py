from __future__ import annotations

import base64
import hashlib
from io import BytesIO
import warnings
from typing import Literal
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field
from .client import BridgeError


class PreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    content_base64: str = Field(min_length=1, max_length=1398104)
    mime_type: Literal["image/png", "image/jpeg"]


class PreviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    client_request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    project_id: str = Field(min_length=1, max_length=128)
    prompt: str = Field(min_length=1, max_length=16000)
    profile_id: Literal["fake-image", "codex-image", "midjourney-manual"] = "fake-image"
    width: int = Field(default=32, ge=1, le=40000000)
    height: int = Field(default=32, ge=1, le=40000000)
    seed: int = Field(default=0, ge=0, le=4294967295)
    references: list[PreviewInput] = Field(default_factory=list, max_length=8)
    acknowledge_test_only: Literal[True]


def validate_image(content: bytes, mime: str, *, expected_hash=None, expected_size=None,
                   max_bytes=1048576, max_pixels=40000000):
    if not content or len(content) > max_bytes:
        raise BridgeError("media_size_invalid", status=422, retryable=False)
    digest = hashlib.sha256(content).hexdigest()
    if (expected_hash is not None and digest != expected_hash) or (
            expected_size is not None and len(content) != expected_size):
        raise BridgeError("media_integrity_mismatch", status=422, retryable=False)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                width, height = image.size
                if (mime not in {"image/png", "image/jpeg"} or
                        image.format != {"image/png": "PNG", "image/jpeg": "JPEG"}[mime] or
                        width * height > max_pixels or getattr(image, "n_frames", 1) != 1):
                    raise ValueError()
                image.verify()
            with Image.open(BytesIO(content)) as image:
                image.load()
    except Exception:
        raise BridgeError("invalid_image", status=422, retryable=False) from None
    return {"original_sha256": digest, "size": len(content), "mime_type": mime,
            "dimensions": {"width": width, "height": height}}


def decode_inputs(request: PreviewCreate):
    values = []
    for reference in request.references:
        try:
            content = base64.b64decode(reference.content_base64, validate=True)
        except ValueError:
            raise BridgeError("invalid_input_encoding", status=422, retryable=False) from None
        values.append((content, validate_image(content, reference.mime_type)))
    return values
