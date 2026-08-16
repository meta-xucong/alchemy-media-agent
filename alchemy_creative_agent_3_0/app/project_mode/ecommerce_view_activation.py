"""Private Doc270 E31 policy and evidence ports for Professional E-Commerce.

This module has no public route and no Provider dependency.  A deployment may
enable it only with a server-controlled policy source and an evidence adapter.
Without both, E31 stays disabled and existing Doc263 behaviour is unchanged.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Protocol

from .source_library import canonical_digest
from .source_evidence import OpenAICompatibleSourceEvidenceAnalyzer


PHASE4_CAPABILITY = {
    "schema_version": "doc270_ecommerce_view_activation_capability_v1",
    "issuer": "v3_doc270_ecommerce_activation_registry",
    "capability_id": "doc270_ecommerce_view_activation",
    "capability_version": "doc270_phase4_ecommerce_view_activation_v1",
    "template_id": "ecommerce_template",
    "enabled": True,
}
REQUIREMENT_KINDS = frozenset(
    {"object_front_presentation", "object_rear_structure", "object_detail"}
)
_SEMANTIC_PROFILE_KEYS = frozenset(
    {"evidence_state", "subject_kind", "view_kind", "affordances"}
)
_SEMANTIC_SUBJECT_KINDS = (
    "object_or_product",
    "person",
    "brand_or_graphic",
)
_SEMANTIC_VIEW_KINDS = (
    "front",
    "rear",
    "detail_or_macro",
    "environment_wide",
    "packaging",
)
_SEMANTIC_AFFORDANCES = (
    "object_front_presentation",
    "object_back_or_structure",
    "object_detail",
    "environment",
    "logo_or_mark",
)
# This route's vision model may spend hidden reasoning tokens before emitting
# the strict JSON response. Keep both compatible protocols on one E31-only
# budget so either transport retains room for the four-field contract.
E31_SOURCE_ANALYSIS_OUTPUT_TOKEN_BUDGET = 640
_ANALYZER_IDENTITY = {
    "authority": "v3_server_image_evidence",
    "schema_version": "doc270_image_evidence_analyzer_v1",
    "version": "doc270_server_image_evidence_v1",
}


class EcommerceSourceEvidenceAnalyzer(Protocol):
    """Return semantic observations for one already verified product source.

    The entry includes ``analysis_bytes`` only for the duration of this call.
    An analyzer never supplies or echoes project/reference/asset/SHA bindings;
    the issuer constructs and verifies those server-owned facts itself.
    """

    def analyze(self, *, project_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        ...


class EcommerceViewActivationIssuer(Protocol):
    """Private composition-root contract for the E31 enablement boundary."""

    def capability(self, *, project_id: str) -> dict[str, Any] | None:
        ...

    def supports_output_count(self, *, expected_output_count: int) -> bool:
        ...

    def issue(
        self,
        *,
        project_id: str,
        expected_output_count: int,
        entries: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        ...


class DisabledEcommerceViewActivationIssuer:
    """Production-safe default: no matching or policy assertion occurs."""

    def capability(self, *, project_id: str) -> dict[str, Any] | None:
        return None

    def supports_output_count(self, *, expected_output_count: int) -> bool:
        return False

    def issue(
        self,
        *,
        project_id: str,
        expected_output_count: int,
        entries: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        return None


@dataclass(frozen=True)
class ConfiguredEcommerceViewActivationIssuer:
    """A server-owned policy resolver paired with a typed evidence adapter."""

    requirements_by_output_count: dict[int, tuple[dict[str, Any], ...]]
    analyzer: EcommerceSourceEvidenceAnalyzer
    policy_authority: str = "v3_ecommerce_deliverable_policy"
    policy_version: str = "doc270_ecommerce_view_policy_v1"
    enabled: bool = True

    def capability(self, *, project_id: str) -> dict[str, Any] | None:
        return dict(PHASE4_CAPABILITY) if self.enabled else None

    def supports_output_count(self, *, expected_output_count: int) -> bool:
        requirements = self.requirements_by_output_count.get(expected_output_count)
        if not requirements or len(requirements) != expected_output_count:
            return False
        normalized = [dict(item) for item in requirements]
        indexes = [item.get("output_index") for item in normalized]
        return (
            set(indexes) == set(range(1, expected_output_count + 1))
            and len(indexes) == expected_output_count
            and all(str(item.get("kind") or "") in REQUIREMENT_KINDS for item in normalized)
        )

    def issue(
        self,
        *,
        project_id: str,
        expected_output_count: int,
        entries: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if (
            self.capability(project_id=project_id) is None
            or not self.supports_output_count(expected_output_count=expected_output_count)
        ):
            return None
        requirements = self.requirements_by_output_count.get(expected_output_count)
        if not requirements:
            return None
        normalized_requirements = [dict(item) for item in requirements]
        evidence_profiles: list[dict[str, Any]] = []
        unavailable_entries = 0
        invalid_response = False
        # Bound each source-analysis invocation to one admitted original. The
        # adapter never receives prompt, browser data, history, or a broad
        # all-upload fallback set.
        for entry in entries:
            try:
                analyzed = self.analyzer.analyze(project_id=project_id, entries=[dict(entry)])
            except Exception:
                unavailable_entries += 1
                continue
            if (
                not isinstance(analyzed, list)
                or len(analyzed) != 1
                or not isinstance(analyzed[0], dict)
            ):
                unavailable_entries += 1
                continue
            profile = _bound_observed_profile(project_id=project_id, entry=entry, semantic=analyzed[0])
            if profile is None:
                invalid_response = True
                continue
            evidence_profiles.append(profile)
        if invalid_response:
            # A malformed response cannot be used as negative evidence. Close
            # operationally and let a later explicit submit obtain a fresh,
            # schema-valid observation rather than blaming the source image.
            return {"outcome": "source_analysis_unavailable"}
        if not evidence_profiles:
            # A malformed analyzer response is not evidence that the user's
            # original is wrong. Treat it like an unavailable observation so
            # no durable product-input closure blocks a later manual retry.
            return {"outcome": "source_analysis_unavailable"}
        return {
            "outcome": "ready",
            "analysis_complete": unavailable_entries == 0,
            "capability": dict(PHASE4_CAPABILITY),
            "requirements": normalized_requirements,
            "evidence_profiles": [dict(item) for item in evidence_profiles if isinstance(item, dict)],
            "provenance": {
                "authority": self.policy_authority,
                "version": self.policy_version,
            },
        }


@dataclass(frozen=True)
class ConfiguredStaticEvidenceAnalyzer:
    """Controlled-test adapter, never selected by production environment config.

    This adapter is intentionally unavailable to ``issuer_from_environment``.
    Its fixture table must still name an exact current association, asset, and
    SHA; it cannot infer semantics from file names or upload ordering.
    """

    profiles: tuple[dict[str, Any], ...]
    authority: str = "v3_server_image_evidence"
    schema_version: str = "doc270_image_evidence_analyzer_v1"
    version: str = "doc270_server_image_evidence_v1"

    def analyze(self, *, project_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        if len(entries) != 1:
            return None
        current = {
            (str(item.get("reference_id") or ""), str(item.get("asset_id") or ""), str(item.get("content_sha256") or "")): item
            for item in entries
            if isinstance(item, dict)
        }
        result: list[dict[str, Any]] = []
        for profile in self.profiles:
            reference_id = str(profile.get("reference_id") or "")
            asset_id = str(profile.get("asset_id") or "")
            content_sha256 = str(profile.get("content_sha256") or "").lower()
            if (reference_id, asset_id, content_sha256) not in current:
                return None
            result.append(
                {
                    "evidence_state": "observed",
                    "subject_kind": profile.get("subject_kind"),
                    "view_kind": profile.get("view_kind"),
                    "affordances": profile.get("affordances"),
                }
            )
        return result


class OpenAICompatibleEcommerceSourceEvidenceAnalyzer:
    """Dedicated E-Commerce source-observation port.

    This is intentionally not the post-generation Vision inspector. It sees
    one verified original's temporary bytes and returns only typed observation
    fields. Project/asset identifiers, paths, SHA values, prompts, and command
    metadata never cross this adapter boundary.
    """

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        model: str | None,
        timeout_seconds: float = 30.0,
        preferred_protocol: str = "responses",
    ) -> None:
        self.api_key = str(api_key or "").strip()
        self.base_url = str(base_url or "").strip()
        self.model = str(model or "").strip()
        self.timeout_seconds = max(0.5, min(float(timeout_seconds), 90.0))
        normalized_protocol = str(preferred_protocol or "").strip().lower()
        if normalized_protocol not in {"responses", "chat"}:
            raise ValueError("ecommerce_source_analysis_protocol_invalid")
        self.preferred_protocol = normalized_protocol

    def available(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def analyze(self, *, project_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        del project_id
        if not self.available() or len(entries) != 1:
            return None
        entry = entries[0]
        content = entry.get("analysis_bytes") if isinstance(entry, dict) else None
        mime_type = str(entry.get("mime_type") or "").strip().lower() if isinstance(entry, dict) else ""
        if not isinstance(content, bytes) or not content or mime_type not in {
            "image/png", "image/jpeg", "image/webp",
        }:
            return None
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key, base_url=self.base_url, max_retries=0)
            data_url = f"data:{mime_type};base64,{base64.b64encode(content).decode('ascii')}"
            parsed = self._analyze_with_protocol_compatibility(client, data_url)
        except Exception:
            return None
        return [parsed] if isinstance(parsed, dict) else None

    def _analyze_with_protocol_compatibility(self, client: Any, data_url: str) -> dict[str, Any]:
        instruction = _semantic_analysis_instruction()
        if self.preferred_protocol == "chat":
            return self._analyze_with_chat(client, instruction, data_url)
        try:
            response = client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": instruction},
                            {"type": "input_image", "image_url": data_url},
                        ],
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "ecommerce_source_evidence",
                        "strict": True,
                        "schema": _semantic_response_schema(),
                    }
                },
                timeout=self.timeout_seconds,
                max_output_tokens=E31_SOURCE_ANALYSIS_OUTPUT_TOKEN_BUDGET,
            )
        except Exception as exc:
            # Use the same gateway compatibility rule as V3's existing Vision
            # route. A timed-out request may have reached the upstream model,
            # so it is never resent through a second protocol.
            if _is_timeout_error(exc) or not _is_protocol_compatibility_error(exc):
                raise
        else:
            raw = str(getattr(response, "output_text", "") or "")
            return _validated_semantic_response(json.loads(raw))
        return self._analyze_with_chat(client, instruction, data_url)

    def _analyze_with_chat(self, client: Any, instruction: str, data_url: str) -> dict[str, Any]:
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            response_format={"type": "json_object"},
            timeout=self.timeout_seconds,
            max_tokens=E31_SOURCE_ANALYSIS_OUTPUT_TOKEN_BUDGET,
        )
        return _validated_semantic_response(
            json.loads(str(response.choices[0].message.content or ""))
        )


def issuer_from_environment() -> EcommerceViewActivationIssuer:
    """Build the only production configuration source for Phase4 activation.

    The bundled server-owned policy is used unless
    `ALCHEMY_DOC270_ECOMMERCE_VIEW_POLICY_PATH` selects an override. An
    unreadable, malformed, or disabled config returns a disabled issuer. Its
    content is never exposed through Project Mode APIs.
    """

    configured = str(os.getenv("ALCHEMY_DOC270_ECOMMERCE_VIEW_POLICY_PATH") or "").strip()
    policy_path = Path(configured) if configured else Path(__file__).with_name("policies") / "doc270_ecommerce_view_policy_v1.json"
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return DisabledEcommerceViewActivationIssuer()
    allowed_policy_fields = {
        "enabled",
        "requirements_by_output_count",
        "policy_authority",
        "policy_version",
    }
    if (
        not isinstance(payload, dict)
        or set(payload) - allowed_policy_fields
        or payload.get("enabled") is not True
    ):
        return DisabledEcommerceViewActivationIssuer()
    raw_requirements = payload.get("requirements_by_output_count")
    if not isinstance(raw_requirements, dict):
        return DisabledEcommerceViewActivationIssuer()
    try:
        requirements = {
            int(count): tuple(dict(item) for item in values)
            for count, values in raw_requirements.items()
            if isinstance(values, list) and int(count) > 0
        }
    except (TypeError, ValueError):
        return DisabledEcommerceViewActivationIssuer()
    if not requirements:
        return DisabledEcommerceViewActivationIssuer()
    analyzer = _configured_production_analyzer()
    if analyzer is None:
        return DisabledEcommerceViewActivationIssuer()
    return ConfiguredEcommerceViewActivationIssuer(
        requirements_by_output_count=requirements,
        analyzer=analyzer,
        policy_authority=str(payload.get("policy_authority") or "v3_ecommerce_deliverable_policy"),
        policy_version=str(payload.get("policy_version") or "doc270_ecommerce_view_policy_v1"),
    )


def ecommerce_view_activation_health() -> dict[str, str | bool]:
    """Return a safe deployment-readiness summary without testing a remote call."""

    issuer = issuer_from_environment()
    capability = issuer.capability(project_id="healthcheck")
    return {
        "component": "doc270_ecommerce_source_analysis",
        "configured": isinstance(issuer, ConfiguredEcommerceViewActivationIssuer),
        "enabled": bool(isinstance(capability, dict) and capability.get("enabled") is True),
        "network_checked": False,
    }


def _configured_production_analyzer() -> EcommerceSourceEvidenceAnalyzer | None:
    """Build the repository-owned dynamic analyzer from deployment settings.

    The policy file supplies only versioned deliverable requirements. It never
    contains per-project references, assets, SHA values, or semantic profiles.
    Missing credentials/model/endpoint makes the E31 capability unavailable.
    """

    try:
        timeout_seconds = float(os.getenv("ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_TIMEOUT_SECONDS", "30"))
    except ValueError:
        return None
    api_key = os.getenv("ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_API_KEY")
    base_url = os.getenv("ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_BASE_URL")
    model = os.getenv("ALCHEMY_DOC270_ECOMMERCE_SOURCE_ANALYSIS_MODEL")
    preferred_protocol = "responses"
    if not all(isinstance(value, str) and value.strip() for value in (api_key, base_url, model)):
        api_key, base_url, model = _existing_v3_lab_vision_route()
        # The existing LAB route is a V3-controlled Doubao/BytePlus visual
        # route. Its Chat image JSON contract is certified independently;
        # call it directly so a Responses attempt cannot consume the same
        # source-analysis operation before the known-compatible protocol.
        preferred_protocol = "chat"
    # E31 owns product deliverable policy, but its image observation transport
    # is the shared scenario-neutral source-evidence foundation.
    analyzer = OpenAICompatibleSourceEvidenceAnalyzer(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        preferred_protocol=preferred_protocol,
    )
    return analyzer if analyzer.available() else None


def _existing_v3_lab_vision_route() -> tuple[str | None, str | None, str | None]:
    """Read only the existing configured V3 vision route, never the Brain.

    This mirrors the server-owned Body source-analysis wiring. It deliberately
    avoids generic OpenAI/LLM/image-generation settings so source analysis is
    enabled only when the deployment has already designated a visual model.
    """

    try:
        from ..shared_capabilities.visual_cluster.vision_provider import (
            _lab_vision_enabled,
            _lab_vision_setting,
        )
    except Exception:
        return None, None, None
    if not _lab_vision_enabled():
        return None, None, None
    values = tuple(_lab_vision_setting(field) for field in ("api_key", "base_url", "model"))
    if not all(isinstance(value, str) and value.strip() for value in values):
        return None, None, None
    return values[0].strip(), values[1].strip(), values[2].strip()


def _is_timeout_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    text = str(exc).strip().lower()
    return "timeout" in name or "timed out" in text or "time-out" in text


def _is_protocol_compatibility_error(exc: Exception) -> bool:
    """Allow one Chat fallback only for an explicit Responses incompatibility."""

    name = type(exc).__name__.lower()
    text = str(exc).strip().lower()
    protocol_terms = ("responses endpoint", "responses api", "responses protocol", "unsupported endpoint")
    return (
        ("badrequest" in name or "notfound" in name)
        and any(term in text for term in protocol_terms)
    )


def _bound_observed_profile(
    *,
    project_id: str,
    entry: dict[str, Any],
    semantic: dict[str, Any],
) -> dict[str, Any] | None:
    if not _semantic_response_is_valid(semantic):
        return None
    reference_id = str(entry.get("reference_id") or "").strip()
    asset_id = str(entry.get("asset_id") or "").strip()
    content_sha256 = str(entry.get("content_sha256") or "").strip().lower()
    if not reference_id or not asset_id or len(content_sha256) != 64:
        return None
    profile = {
        "schema_version": "doc270_source_evidence_profile_v2",
        "analyzer": dict(_ANALYZER_IDENTITY),
        "project_id": project_id,
        "reference_id": reference_id,
        "asset_id": asset_id,
        "content_sha256": content_sha256,
        **semantic,
    }
    profile["profile_digest"] = canonical_digest(profile)
    return profile


def _semantic_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["evidence_state", "subject_kind", "view_kind", "affordances"],
        "properties": {
            "evidence_state": {"type": "string", "enum": ["observed"]},
            "subject_kind": {"type": "string", "enum": list(_SEMANTIC_SUBJECT_KINDS)},
            "view_kind": {"type": "string", "enum": list(_SEMANTIC_VIEW_KINDS)},
            "affordances": {
                "type": "array",
                "minItems": 1,
                "uniqueItems": True,
                "items": {"type": "string", "enum": list(_SEMANTIC_AFFORDANCES)},
            },
        },
    }


def _semantic_analysis_instruction() -> str:
    """Return the fixed, source-safe Chat contract for one image observation."""

    return (
        "Inspect only the supplied image. Return exactly one JSON object and nothing else: "
        "no Markdown, explanation, code fence, or extra keys. "
        "The object must contain exactly these four fields: "
        "evidence_state, subject_kind, view_kind, affordances. "
        "evidence_state must be exactly 'observed'. "
        "subject_kind must be one of: " + ", ".join(_SEMANTIC_SUBJECT_KINDS) + ". "
        "view_kind must be one of: " + ", ".join(_SEMANTIC_VIEW_KINDS) + ". "
        "affordances must be a non-empty JSON array of unique strings, each one of: "
        + ", ".join(_SEMANTIC_AFFORDANCES) + ". "
        "Do not infer identity, filename, product name, project, user intent, or prompt."
    )


def _semantic_response_is_valid(payload: Any) -> bool:
    if not isinstance(payload, dict) or set(payload) != _SEMANTIC_PROFILE_KEYS:
        return False
    affordances = payload.get("affordances")
    if (
        not isinstance(affordances, list)
        or not affordances
        or any(not isinstance(item, str) for item in affordances)
    ):
        return False
    return (
        payload.get("evidence_state") == "observed"
        and payload.get("subject_kind") in _SEMANTIC_SUBJECT_KINDS
        and payload.get("view_kind") in _SEMANTIC_VIEW_KINDS
        and len(affordances) == len(set(affordances))
        and all(item in _SEMANTIC_AFFORDANCES for item in affordances)
    )


def _validated_semantic_response(payload: Any) -> dict[str, Any]:
    if not _semantic_response_is_valid(payload):
        raise ValueError("ecommerce_source_evidence_response_invalid")
    return dict(payload)
