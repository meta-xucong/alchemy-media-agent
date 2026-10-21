"""Explicit Bridge receipt consumer, never a default routing strategy."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from .providers import GenerationRequest, ProductionImageGenerationProvider


RENDER_BRIDGE_SIZES = ("1024x1024", "1024x768", "768x1024")
RENDER_BRIDGE_PROFILES = ("fake-image", "codex-image", "midjourney-manual")
RENDER_BRIDGE_FORMATS = ("png", "jpeg")


def render_bridge_options(execution_profile_id="fake-image", output_format="png", *, uploaded_asset_ids=()):
    """Bounded adapter contract, not a declaration of real-tool acceptance."""
    if execution_profile_id not in RENDER_BRIDGE_PROFILES:
        raise ValueError("render_bridge_profile_unknown")
    if output_format not in RENDER_BRIDGE_FORMATS:
        raise ValueError("render_bridge_output_format_unsupported")
    if execution_profile_id == "midjourney-manual" and uploaded_asset_ids:
        raise ValueError("render_bridge_profile_references_unsupported")
    return execution_profile_id, output_format


def render_bridge_inputs(uploaded_asset_ids=None, size="1024x1024") -> tuple[list[str], str]:
    """Validate, never normalize, reorder, or silently trim a caller's inputs."""
    ids = [] if uploaded_asset_ids is None else uploaded_asset_ids
    if (
        not isinstance(ids, (list, tuple))
        or len(ids) > 2
        or any(not isinstance(value, str) or not value.strip() or value != value.strip() for value in ids)
        or len(set(ids)) != len(ids)
        or size not in RENDER_BRIDGE_SIZES
    ):
        raise ValueError("render_bridge_native_inputs_invalid")
    return list(ids), size


def _compatible_identity(value) -> dict[str, Any]:
    """Keep old square/no-reference journal and checkpoint identities stable."""
    result = asdict(value)
    for field, default in (("uploaded_asset_ids", ()), ("reference_sha256", ()), ("size", "1024x1024"), ("output_format", "png")):
        if field in result:
            if result[field] == default or (default == () and not result[field]):
                result.pop(field)
            elif isinstance(result[field], tuple):
                result[field] = list(result[field])
    # The original registration already included the fake profile. The original
    # plan marker did not, so only plan identities omit that default field.
    if isinstance(value, RenderBridgePlanIdentity) and value.execution_profile_id == "fake-image":
        result.pop("execution_profile_id")
    return result


@dataclass(frozen=True)
class RenderBridgePlanIdentity:
    project_id: str
    owner_user_id: int
    plan_key: str
    user_input_sha256: str
    uploaded_asset_ids: tuple[str, ...] = ()
    size: str = "1024x1024"
    execution_profile_id: str = "fake-image"
    output_format: str = "png"

    @property
    def instance_id(self) -> str:
        return hashlib.sha256(
            json.dumps(_compatible_identity(self), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def safe_metadata(self) -> dict[str, Any]:
        return {"schema_version": "render_bridge_native_plan_v1", **_compatible_identity(self)}


@dataclass(frozen=True)
class RenderBridgeRegistration:
    """Internal service-owned identity, not a public request-body schema."""

    registration_key: str
    project_id: str
    job_id: str
    asset_id: str
    frozen_request_id: str
    target_revision: str
    prompt_sha256: str
    receipt_id: str
    original_sha256: str
    execution_profile_id: str = "fake-image"
    execution_profile_revision: str = "1"
    uploaded_asset_ids: tuple[str, ...] = ()
    reference_sha256: tuple[str, ...] = ()
    size: str = "1024x1024"
    output_format: str = "png"

    @property
    def output_id(self) -> str:
        identity = json.dumps(_compatible_identity(self), sort_keys=True, separators=(",", ":"))
        return "v3_output_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]

    def safe_metadata(self) -> dict[str, Any]:
        return {
            **_compatible_identity(self),
            "output_id": self.output_id,
            "billing": "unchanged_v3_zero_credit_stub",
            "test_fixture": self.execution_profile_id == "fake-image",
            **({"development_only": True, "real_tool_verified": False}
               if self.execution_profile_id != "fake-image" else {}),
        }


class RenderBridgeReceiptProvider(ProductionImageGenerationProvider):
    """Feed verified pixels through the normal provider's persistence path.

    This adapter never starts a renderer. Fake images remain synthetic; explicit
    real-profile development receipts do not imply account/tool acceptance.
    """

    provider_name = "render_bridge_receipt_provider"
    provider_version = "render_bridge_receipt_v1"

    def __init__(
        self,
        *,
        output_store: Any,
        binding: RenderBridgeRegistration,
        artifact_bytes: bytes,
        assert_current: Callable[[], None],
    ) -> None:
        super().__init__(output_store=output_store)
        if not isinstance(binding, RenderBridgeRegistration):
            raise ValueError("render_bridge_registration_untrusted")
        render_bridge_options(binding.execution_profile_id, binding.output_format, uploaded_asset_ids=binding.uploaded_asset_ids)
        if hashlib.sha256(artifact_bytes).hexdigest() != binding.original_sha256:
            raise ValueError("render_bridge_artifact_hash_mismatch")
        self.binding = binding
        self.artifact_bytes = artifact_bytes
        self.assert_current = assert_current

    def _select_provider(self, reference_assets: list[dict[str, Any]]) -> str:
        self._validate_references(reference_assets)
        return "render_bridge"

    def _validate_references(self, reference_assets) -> None:
        if (
            [item.get("asset_id") for item in reference_assets] != list(self.binding.uploaded_asset_ids)
            or [hashlib.sha256(Path(item["file_path"]).read_bytes()).hexdigest() for item in reference_assets]
            != list(self.binding.reference_sha256)
        ):
            raise ValueError("render_bridge_frozen_references_mismatch")

    def _run_app_provider_with_timeout_retry(
        self, provider_name, app_request, reference_assets, *, reference_input_execution, output_index
    ):
        plan = app_request.prompt_plan
        self._validate_references(reference_assets)
        if (
            plan.variables.get("provider_prompt_sha256") != self.binding.prompt_sha256
            or plan.size != self.binding.size
            or plan.quality != "auto"
            or plan.output_format != self.binding.output_format
            or any(getattr(plan, field, None) is not None for field in ("background", "moderation", "output_compression"))
            or plan.variables.get("input_fidelity") is not None
        ):
            raise ValueError("render_bridge_frozen_contract_mismatch")
        self.assert_current()
        self._last_provider_failure_retry_summary = {
            "executed_count": 1,
            "fresh_upstream_requests": 0,
            "max_attempts": 1,
            "final_status": "succeeded",
            "attempts": [],
            "source": "already_rendered_bridge_receipt",
        }
        return SimpleNamespace(
            provider="render_bridge",
            model=f"{self.binding.execution_profile_id}:{self.binding.execution_profile_revision}",
            outputs=[
                {
                    "b64_json": base64.b64encode(self.artifact_bytes).decode("ascii"),
                    "mime_type": f"image/{self.binding.output_format}",
                    "format": self.binding.output_format,
                    "width": int(self.binding.size.split("x")[0]),
                    "height": int(self.binding.size.split("x")[1]),
                    "api_operation": "image.generate",
                }
            ],
            raw_response_summary={"render_bridge_registration": self.binding.safe_metadata()},
        )

    def _native_output_checkpoint_id(self, request: GenerationRequest, *, output_index: int) -> str:
        if (
            output_index != 0
            or request.metadata.get("job_id") != self.binding.job_id
            or request.metadata.get("project_id") != self.binding.project_id
            or request.generation_plan.asset_id != self.binding.asset_id
        ):
            raise ValueError("render_bridge_checkpoint_binding_mismatch")
        self.assert_current()
        return self.binding.output_id


@dataclass(frozen=True)
class RenderBridgeCloudContinuation:
    """Server-owned identity for exactly one frozen cloud continuation."""

    execution_key: str
    frozen: dict[str, Any]

    @property
    def output_id(self) -> str:
        identity = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return "v3_output_" + hashlib.sha256(identity.encode()).hexdigest()[:20]

    def safe_metadata(self) -> dict[str, Any]:
        return {
            "execution_key": self.execution_key,
            "frozen_request_id": self.frozen["frozen_request_id"],
            "target": self.frozen["target"],
            "output_id": self.output_id,
            "development_only": True,
            "formal_delivery": False,
            "upstream_may_charge": True,
        }


class RenderBridgeCloudProvider(ProductionImageGenerationProvider):
    """Configured production transport; no alternate planning or retry policy."""

    def __init__(self, *, output_store, binding, assert_current):
        super().__init__(output_store=output_store)
        if not isinstance(binding, RenderBridgeCloudContinuation):
            raise ValueError("render_bridge_cloud_binding_untrusted")
        self.binding = binding
        self.assert_current = assert_current

    def _build_app_request(self, request):
        app_request, provider, references = super()._build_app_request(request)
        frozen = self.binding.frozen
        plan = app_request.prompt_plan
        options = frozen["image_options"]
        if (
            plan.variables.get("generation_prompt") != frozen["prompt"]
            or plan.variables.get("provider_prompt_sha256") != frozen["prompt_sha256"]
            or plan.variables.get("provider_prompt_source") != "remote_brain_canonical"
            or any(getattr(plan, field, None) != options[field] for field in options if field != "input_fidelity")
            or plan.variables.get("input_fidelity") != options["input_fidelity"]
            or [item.get("asset_id") for item in references] != [item["asset_id"] for item in frozen["references"]]
            or [hashlib.sha256(Path(item["file_path"]).read_bytes()).hexdigest() for item in references]
            != [item["sha256"] for item in frozen["references"]]
        ):
            raise ValueError("render_bridge_cloud_frozen_contract_mismatch")
        self.assert_current()
        return app_request, provider, references

    def _run_app_provider_with_timeout_retry(self, *args, **kwargs):
        self.assert_current()
        result = super()._run_app_provider_with_timeout_retry(*args, **kwargs)
        result.raw_response_summary = {
            **dict(result.raw_response_summary or {}),
            "render_bridge_cloud_continuation": self.binding.safe_metadata(),
        }
        return result

    def _native_output_checkpoint_id(self, request, *, output_index):
        target = self.binding.frozen["target"]
        if (output_index != 0 or request.metadata.get("job_id") != target["job_id"]
            or request.metadata.get("project_id") != target["project_id"]
            or request.generation_plan.asset_id != target["asset_id"]):
            raise ValueError("render_bridge_cloud_checkpoint_binding_mismatch")
        self.assert_current()
        return self.binding.output_id
