"""Explicit Bridge receipt consumer, never a default routing strategy."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import hashlib
import json
from types import SimpleNamespace
from typing import Any, Callable

from .providers import GenerationRequest, ProductionImageGenerationProvider


@dataclass(frozen=True)
class RenderBridgePlanIdentity:
    project_id: str
    owner_user_id: int
    plan_key: str
    user_input_sha256: str

    @property
    def instance_id(self) -> str:
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def safe_metadata(self) -> dict[str, Any]:
        return {"schema_version": "render_bridge_native_plan_v1", **asdict(self)}


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

    @property
    def output_id(self) -> str:
        identity = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return "v3_output_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]

    def safe_metadata(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "output_id": self.output_id,
            "billing": "unchanged_v3_zero_credit_stub",
            "test_fixture": self.execution_profile_id == "fake-image",
        }


class RenderBridgeReceiptProvider(ProductionImageGenerationProvider):
    """Feed verified pixels through the normal provider's persistence path."""

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
        if hashlib.sha256(artifact_bytes).hexdigest() != binding.original_sha256:
            raise ValueError("render_bridge_artifact_hash_mismatch")
        self.binding = binding
        self.artifact_bytes = artifact_bytes
        self.assert_current = assert_current

    def _select_provider(self, reference_assets: list[dict[str, Any]]) -> str:
        if reference_assets:
            raise ValueError("render_bridge_references_unsupported")
        return "render_bridge"

    def _run_app_provider_with_timeout_retry(
        self, provider_name, app_request, reference_assets, *, reference_input_execution, output_index
    ):
        plan = app_request.prompt_plan
        if (
            reference_assets
            or plan.variables.get("provider_prompt_sha256") != self.binding.prompt_sha256
            or plan.size != "1024x1024"
            or plan.quality != "auto"
            or plan.output_format != "png"
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
                    "mime_type": "image/png",
                    "format": "png",
                    "width": 1024,
                    "height": 1024,
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
