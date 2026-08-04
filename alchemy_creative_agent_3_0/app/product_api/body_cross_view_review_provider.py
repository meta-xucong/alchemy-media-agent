"""Server-owned Body cross-view review provider.

This provider reviews the three generated Body Silhouette outputs together.
It is deliberately separate from Body source proportion analysis: the five
source references are not renderer inputs and are not sent here.  The only
images consumed are the generated front/side/rear outputs selected by the
formal slot receipts.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from ..shared_capabilities.visual_cluster.vision_provider import (
    _lab_vision_enabled,
    _lab_vision_setting,
)
from ..visual_assets.body_cross_view_review import (
    BODY_CROSS_VIEW_BLOCKING_ISSUE_CODES,
    BODY_CROSS_VIEW_DIMENSION_EVIDENCE_CODES,
    BODY_CROSS_VIEW_DIMENSIONS,
    BODY_CROSS_VIEW_PIXEL_EVIDENCE_CODE,
    BODY_CROSS_VIEW_SLOT_KEYS,
    BodyCrossViewReviewReceipt,
    build_body_cross_view_review_receipt,
    build_body_cross_view_unavailable_receipt,
)
from .outputs import V3GeneratedOutputStore


_ALLOWED_DIMENSION_VALUES = frozenset({"pass", "fail", "unknown"})
_REVIEW_SCHEMA_NAME = "body_cross_view_review_v1"


class BodyCrossViewReviewError(RuntimeError):
    """Closed provider failure; raw upstream details stay out of receipts."""


@dataclass(frozen=True)
class BodyCrossViewImagePayload:
    slot_key: str
    output_id: str
    content: bytes
    mime_type: str


class BodyCrossViewReviewTransport(Protocol):
    def review(
        self,
        images: Sequence[BodyCrossViewImagePayload],
        *,
        instructions: str,
        response_schema: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any] | str:
        """Return a closed JSON-compatible cross-view review payload."""


class BodyCrossViewReviewProvider(Protocol):
    def available(self, *, force: bool = False) -> bool: ...

    def review_body_cross_view(
        self,
        *,
        asset: Any,
        card: Any,
        attempt_identity: Any,
        body_refresh_analysis_context: Any,
        body_source_admission: Any,
        formal_receipts: Mapping[str, Any],
        view_output_ids: Mapping[str, str],
    ) -> BodyCrossViewReviewReceipt: ...


class OpenAICompatibleBodyCrossViewReviewTransport:
    """OpenAI-compatible Responses transport for three generated outputs."""

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def review(
        self,
        images: Sequence[BodyCrossViewImagePayload],
        *,
        instructions: str,
        response_schema: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any] | str:
        if not self.api_key or not self.base_url or not self.model:
            raise BodyCrossViewReviewError("body_cross_view_review_provider_unavailable")
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                max_retries=0,
            )
            content: list[dict[str, Any]] = [{"type": "input_text", "text": instructions}]
            for image in images:
                encoded = base64.b64encode(image.content).decode("ascii")
                content.append(
                    {
                        "type": "input_text",
                        "text": f"Generated Body Silhouette output: {image.slot_key}",
                    }
                )
                content.append(
                    {
                        "type": "input_image",
                        "image_url": f"data:{image.mime_type};base64,{encoded}",
                    }
                )
            response = client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": content}],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": _REVIEW_SCHEMA_NAME,
                        "strict": True,
                        "schema": dict(response_schema),
                    }
                },
                timeout=timeout_seconds,
                max_output_tokens=900,
            )
        except BodyCrossViewReviewError:
            raise
        except Exception as exc:
            raise BodyCrossViewReviewError("body_cross_view_review_provider_unavailable") from exc
        output_text = str(getattr(response, "output_text", "") or "").strip()
        if not output_text:
            raise BodyCrossViewReviewError("body_cross_view_review_response_invalid")
        try:
            return json.loads(output_text)
        except (TypeError, ValueError) as exc:
            raise BodyCrossViewReviewError("body_cross_view_review_response_invalid") from exc


class OpenAICompatibleBodyCrossViewReviewProvider:
    """Review front/side/rear Body outputs and return a typed receipt."""

    provider_name = "configured_body_cross_view_review_provider"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        model: str | None,
        output_store: V3GeneratedOutputStore,
        timeout_seconds: float = 90.0,
        transport: BodyCrossViewReviewTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.output_store = output_store
        self.timeout_seconds = timeout_seconds
        self.response_schema = build_body_cross_view_review_response_schema()
        self.instructions = _build_body_cross_view_review_instructions(self.response_schema)
        self.transport = transport or (
            OpenAICompatibleBodyCrossViewReviewTransport(
                api_key=api_key or "",
                base_url=base_url or "",
                model=model or "",
            )
            if api_key and base_url and model
            else None
        )

    def available(self, *, force: bool = False) -> bool:
        del force
        return self.transport is not None

    def review_body_cross_view(
        self,
        *,
        asset: Any,
        card: Any,
        attempt_identity: Any,
        body_refresh_analysis_context: Any,
        body_source_admission: Any,
        formal_receipts: Mapping[str, Any],
        view_output_ids: Mapping[str, str],
    ) -> BodyCrossViewReviewReceipt:
        del asset, card, formal_receipts
        attempt_id = str(getattr(attempt_identity, "attempt_id", "") or "").strip()
        source_digest = _source_evidence_digest(
            body_refresh_analysis_context,
            body_source_admission,
        )
        safe_output_ids = {
            slot_key: str(view_output_ids.get(slot_key, "") or "").strip()
            for slot_key in BODY_CROSS_VIEW_SLOT_KEYS
        }
        try:
            if not self.available(force=True):
                raise BodyCrossViewReviewError("body_cross_view_review_provider_unavailable")
            images = self._read_view_images(safe_output_ids)
            raw_response = self.transport.review(  # type: ignore[union-attr]
                images,
                instructions=self.instructions,
                response_schema=self.response_schema,
                timeout_seconds=self.timeout_seconds,
            )
            dimensions, issue_codes = _parse_review_response(raw_response)
        except BodyCrossViewReviewError:
            return build_body_cross_view_unavailable_receipt(
                attempt_id=attempt_id,
                source_evidence_id_digest=source_digest,
                view_output_ids=safe_output_ids,
            )
        status = (
            "pass"
            if all(dimensions[dimension] == "pass" for dimension in BODY_CROSS_VIEW_DIMENSIONS)
            and not issue_codes
            else "fail"
        )
        evidence_codes = [BODY_CROSS_VIEW_PIXEL_EVIDENCE_CODE]
        evidence_codes.extend(
            BODY_CROSS_VIEW_DIMENSION_EVIDENCE_CODES[dimension]
            for dimension in BODY_CROSS_VIEW_DIMENSIONS
            if dimensions[dimension] == "pass"
        )
        return build_body_cross_view_review_receipt(
            attempt_id=attempt_id,
            source_evidence_id_digest=source_digest,
            view_output_ids=safe_output_ids,
            status=status,
            dimensions=dimensions,
            evidence_codes=evidence_codes,
            issue_codes=issue_codes,
            real_pixel_review_verified=True,
        )

    def _read_view_images(
        self,
        view_output_ids: Mapping[str, str],
    ) -> list[BodyCrossViewImagePayload]:
        images: list[BodyCrossViewImagePayload] = []
        for slot_key in BODY_CROSS_VIEW_SLOT_KEYS:
            output_id = str(view_output_ids.get(slot_key, "") or "").strip()
            record = self.output_store.get_output(output_id)
            if record is None:
                raise BodyCrossViewReviewError("body_cross_view_output_unavailable")
            path = Path(str(record.file_path or ""))
            if not path.is_file():
                raise BodyCrossViewReviewError("body_cross_view_output_unavailable")
            try:
                content = path.read_bytes()
            except Exception as exc:
                raise BodyCrossViewReviewError("body_cross_view_output_unavailable") from exc
            expected_sha = str((record.metadata or {}).get("content_sha256") or "").strip().lower()
            if expected_sha and hashlib.sha256(content).hexdigest() != expected_sha:
                raise BodyCrossViewReviewError("body_cross_view_output_hash_mismatch")
            mime_type = str(record.mime_type or "image/png").strip().lower()
            if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
                raise BodyCrossViewReviewError("body_cross_view_output_unavailable")
            images.append(
                BodyCrossViewImagePayload(
                    slot_key=slot_key,
                    output_id=output_id,
                    content=content,
                    mime_type=mime_type,
                )
            )
        return images


def build_body_cross_view_review_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["dimensions", "issue_codes"],
        "properties": {
            "dimensions": {
                "type": "object",
                "additionalProperties": False,
                "required": list(BODY_CROSS_VIEW_DIMENSIONS),
                "properties": {
                    dimension: {"type": "string", "enum": ["pass", "fail", "unknown"]}
                    for dimension in BODY_CROSS_VIEW_DIMENSIONS
                },
            },
            "issue_codes": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": list(BODY_CROSS_VIEW_BLOCKING_ISSUE_CODES),
                },
                "uniqueItems": True,
                "maxItems": len(BODY_CROSS_VIEW_BLOCKING_ISSUE_CODES),
            },
        },
    }


def create_configured_body_cross_view_review_provider(
    *,
    output_store: V3GeneratedOutputStore,
) -> OpenAICompatibleBodyCrossViewReviewProvider | None:
    if not _lab_vision_enabled():
        return None
    api_key = _lab_vision_setting("api_key")
    base_url = _lab_vision_setting("base_url")
    model = _lab_vision_setting("model")
    if not all(isinstance(value, str) and value.strip() for value in (api_key, base_url, model)):
        return None
    return OpenAICompatibleBodyCrossViewReviewProvider(
        api_key=api_key.strip(),
        base_url=base_url.strip(),
        model=model.strip(),
        output_store=output_store,
    )


def _build_body_cross_view_review_instructions(response_schema: Mapping[str, Any]) -> str:
    return (
        "Review exactly these three generated Body Silhouette outputs together: "
        "front_full, side_full, and rear_full. Decide only whether they can be "
        "activated as one coherent full-body model for the current Body refresh. "
        "Check age-stage consistency, head-to-body scale, natural head-neck-shoulder-"
        "torso-limb body chain, front/side/rear body volume consistency, garment "
        "continuity, pure white backdrop consistency, hair continuity, and whether "
        "the person is synthesized as one natural body rather than a head-body "
        "composite. For garment continuity, require the exact same top, bottom, "
        "and footwear identity across front/side/rear. The frozen outfit identity "
        "for this modeling-card contract is a plain white short-sleeve cotton top "
        "with a crew-neck cut, light-blue lightweight denim shorts with a straight "
        "mid-thigh cut, and plain white ankle socks. category match alone is not "
        "enough: any colorway, material, cut, graphics, logo, or added-layer drift "
        "must fail `garment_consistency`. Return only strict JSON "
        "matching this schema; do not include "
        "raw observations, paths, IDs, measurements, biometric vectors, or prose: "
        + json.dumps(dict(response_schema), sort_keys=True, separators=(",", ":"))
    )


def _parse_review_response(raw_response: Mapping[str, Any] | str) -> tuple[dict[str, str], list[str]]:
    if isinstance(raw_response, str):
        raw_response = json.loads(raw_response)
    if not isinstance(raw_response, Mapping):
        raise BodyCrossViewReviewError("body_cross_view_review_response_invalid")
    if set(raw_response) != {"dimensions", "issue_codes"}:
        raise BodyCrossViewReviewError("body_cross_view_review_response_invalid")
    raw_dimensions = raw_response.get("dimensions")
    if not isinstance(raw_dimensions, Mapping):
        raise BodyCrossViewReviewError("body_cross_view_review_response_invalid")
    if set(raw_dimensions) != set(BODY_CROSS_VIEW_DIMENSIONS):
        raise BodyCrossViewReviewError("body_cross_view_review_response_invalid")
    dimensions = {dimension: str(raw_dimensions[dimension]).strip() for dimension in BODY_CROSS_VIEW_DIMENSIONS}
    if any(value not in _ALLOWED_DIMENSION_VALUES for value in dimensions.values()):
        raise BodyCrossViewReviewError("body_cross_view_review_response_invalid")
    raw_issues = raw_response.get("issue_codes")
    if not isinstance(raw_issues, list):
        raise BodyCrossViewReviewError("body_cross_view_review_response_invalid")
    issue_codes = [str(code).strip() for code in raw_issues if str(code).strip()]
    if len(issue_codes) != len(set(issue_codes)):
        raise BodyCrossViewReviewError("body_cross_view_review_response_invalid")
    if any(code not in BODY_CROSS_VIEW_BLOCKING_ISSUE_CODES for code in issue_codes):
        raise BodyCrossViewReviewError("body_cross_view_review_response_invalid")
    if any(dimensions[dimension] != "pass" for dimension in BODY_CROSS_VIEW_DIMENSIONS) and not issue_codes:
        raise BodyCrossViewReviewError("body_cross_view_review_response_invalid")
    return dimensions, issue_codes


def _source_evidence_digest(context: Any, admission: Any) -> str:
    context_digest = str(getattr(context, "source_evidence_id_digest", "") or "").strip().lower()
    method = getattr(admission, "source_evidence_id_digest", None)
    admission_digest = str(method() if callable(method) else "").strip().lower()
    return admission_digest or context_digest


__all__ = [
    "BodyCrossViewImagePayload",
    "BodyCrossViewReviewError",
    "BodyCrossViewReviewTransport",
    "OpenAICompatibleBodyCrossViewReviewProvider",
    "OpenAICompatibleBodyCrossViewReviewTransport",
    "build_body_cross_view_review_response_schema",
    "create_configured_body_cross_view_review_provider",
]
