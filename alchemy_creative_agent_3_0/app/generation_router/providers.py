"""V3-owned generation provider contracts."""

from __future__ import annotations

import asyncio
from pathlib import Path
import threading
from typing import Any

from pydantic import BaseModel, Field

from ..creative_core.rules import stable_id
from ..condition_engine.providers import ProviderCapabilities
from ..schemas import AssetSpec, CandidateResult, ConditionPlan, GenerationPlan, LayoutPlan, PromptCompilationResult


class GenerationRequest(BaseModel):
    asset_spec: AssetSpec | None = None
    layout_plan: LayoutPlan | None = None
    prompt_compilation: PromptCompilationResult
    condition_plan: ConditionPlan
    generation_plan: GenerationPlan
    metadata: dict = Field(default_factory=dict)


class GenerationResponse(BaseModel):
    candidates: list[CandidateResult]
    provider_metadata: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class GenerationProvider:
    """Provider interface for V3 generation and deterministic mock generation."""

    provider_name = "generation_provider"
    provider_version = "v3.2-generation-loop-mvp"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.provider_name,
            version=self.provider_version,
            supports_generation=True,
            supports_batch=True,
            requires_gpu=False,
            requires_network=False,
            is_deterministic=True,
        )

    def is_available(self) -> bool:
        return True

    def health_check(self) -> dict:
        return {"provider_name": self.provider_name, "available": self.is_available()}

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        raise NotImplementedError


class PlanningOnlyGenerationProvider(GenerationProvider):
    provider_name = "planning_only_generation_provider"
    provider_version = "v3.0-foundation"

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        candidate = CandidateResult(
            candidate_id=stable_id("candidate", request.generation_plan.asset_id, request.prompt_compilation.prompt_compilation_id),
            asset_id=request.generation_plan.asset_id,
            provider=self.provider_name,
            prompt_compilation_id=request.prompt_compilation.prompt_compilation_id,
            condition_plan_id=request.condition_plan.condition_plan_id,
            is_mock=True,
            metadata={"runtime_mode": "planning_only", "provider_version": self.provider_version},
        )
        return GenerationResponse(
            candidates=[candidate],
            provider_metadata={"provider_name": self.provider_name, "provider_version": self.provider_version},
            warnings=["No real image generation is executed in V3.0 foundation."],
        )


class MockGenerationProvider(GenerationProvider):
    """Deterministic V3.2 candidate provider used by the closed-loop MVP."""

    provider_name = "mock_generation_provider"
    provider_version = "v3.2-generation-loop-mvp"

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        candidate_count = max(1, request.generation_plan.candidate_count)
        refine_round = int(request.metadata.get("refine_round", request.generation_plan.metadata.get("refine_round", 0) or 0))
        profile = str(request.generation_plan.metadata.get("mock_profile", request.metadata.get("mock_profile", "balanced")))
        candidates: list[CandidateResult] = []
        warnings: list[str] = []

        for index in range(candidate_count):
            quality_score, problem_codes = self._candidate_profile(profile, index, refine_round)
            hard_failure = "provider_failure" in problem_codes or "missing_product_area" in problem_codes
            candidate_id = stable_id(
                "candidate",
                request.generation_plan.asset_id,
                request.prompt_compilation.prompt_compilation_id,
                self.provider_name,
                refine_round,
                index,
                profile,
            )
            candidates.append(
                CandidateResult(
                    candidate_id=candidate_id,
                    asset_id=request.generation_plan.asset_id,
                    uri=f"mock://v3/{candidate_id}",
                    provider=self.provider_name,
                    prompt_compilation_id=request.prompt_compilation.prompt_compilation_id,
                    condition_plan_id=request.condition_plan.condition_plan_id,
                    is_mock=True,
                    metadata={
                        "runtime_mode": "mock_generation",
                        "provider_version": self.provider_version,
                        "candidate_index": index,
                        "refine_round": refine_round,
                        "mock_profile": profile,
                        "mock_quality_score": quality_score,
                        "forced_problem_codes": problem_codes,
                        "hard_failure": hard_failure,
                        "asset_id": request.generation_plan.asset_id,
                    },
                )
            )
        if profile == "all_hard_failure":
            warnings.append("Mock profile produced only hard-failure candidates.")
        return GenerationResponse(
            candidates=candidates,
            provider_metadata={
                "provider_name": self.provider_name,
                "provider_version": self.provider_version,
                "runtime_mode": "mock_generation",
                "refine_round": refine_round,
                "mock_profile": profile,
            },
            warnings=warnings,
        )

    def _candidate_profile(self, profile: str, index: int, refine_round: int) -> tuple[float, list[str]]:
        if profile == "needs_refinement":
            if refine_round == 0:
                return (0.61 - index * 0.02, ["commercial_hook_missing"] if index == 0 else ["fake_text_risk"])
            return (0.86 - index * 0.03, [])
        if profile == "exhaust_retries":
            return (0.61 - index * 0.02, ["commercial_hook_missing"] if index == 0 else ["brand_style_missing"])
        if profile == "hard_failure_first":
            if index == 0:
                return (0.30, ["missing_product_area"])
            return (0.84 - index * 0.02, [])
        if profile == "all_hard_failure":
            return (0.25, ["missing_product_area"])
        if index == 0:
            return (0.86, [])
        if index == 1:
            return (0.80, [])
        if index == 2:
            return (0.67, ["commercial_hook_missing"])
        return (0.42, ["provider_failure"])


class ProductionImageGenerationProvider(GenerationProvider):
    """V3-owned adapter that reuses configured V1/V2 image provider credentials."""

    provider_name = "production_image_generation_provider"
    provider_version = "v3.8b-provider-output-production"

    def __init__(self, output_store: Any | None = None) -> None:
        if output_store is None:
            from ..product_api.outputs import V3GeneratedOutputStore

            output_store = V3GeneratedOutputStore()
        self.output_store = output_store

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.provider_name,
            version=self.provider_version,
            supports_generation=True,
            supports_batch=True,
            requires_gpu=False,
            requires_network=True,
            is_deterministic=False,
        )

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        app_request, provider_name, reference_assets = self._build_app_request(request)
        result = _run_async_blocking(self._generate_with_app_provider(provider_name, app_request))
        candidates: list[CandidateResult] = []
        warnings: list[str] = []
        outputs = list(getattr(result, "outputs", []) or [])
        if not outputs:
            raise ValueError("V3 production provider returned no image outputs.")
        for index, output in enumerate(outputs[:1]):
            encoded = output.get("b64_json")
            if not encoded:
                warnings.append("Provider output did not include image bytes and was skipped.")
                continue
            candidate_id = stable_id(
                "candidate",
                request.generation_plan.asset_id,
                request.prompt_compilation.prompt_compilation_id,
                getattr(result, "provider", provider_name),
                getattr(result, "model", ""),
                index,
            )
            record = self.output_store.save_base64_output(
                job_id=str(request.metadata.get("job_id") or request.generation_plan.metadata.get("job_id") or "v3_job"),
                candidate_id=candidate_id,
                asset_id=request.generation_plan.asset_id,
                provider=str(getattr(result, "provider", provider_name)),
                model=str(getattr(result, "model", "") or ""),
                encoded_image=str(encoded),
                mime_type=output.get("mime_type"),
                output_format=output.get("format") or app_request.prompt_plan.output_format,
                width=output.get("width"),
                height=output.get("height"),
                metadata={
                    "source": self.provider_name,
                    "provider_version": self.provider_version,
                    "prompt_compilation_id": request.prompt_compilation.prompt_compilation_id,
                    "condition_plan_id": request.condition_plan.condition_plan_id,
                    "reference_asset_count": len(reference_assets),
                    "provider_raw_summary": getattr(result, "raw_response_summary", {}) or {},
                    "api_operation": output.get("api_operation"),
                    "request_index": output.get("request_index"),
                },
            )
            candidates.append(
                CandidateResult(
                    candidate_id=candidate_id,
                    asset_id=request.generation_plan.asset_id,
                    file_path=record.file_path,
                    uri=record.thumbnail_url,
                    provider=str(getattr(result, "provider", provider_name)),
                    prompt_compilation_id=request.prompt_compilation.prompt_compilation_id,
                    condition_plan_id=request.condition_plan.condition_plan_id,
                    is_mock=False,
                    metadata={
                        "runtime_mode": "production_image_generation",
                        "provider_version": self.provider_version,
                        "actual_provider": str(getattr(result, "provider", provider_name)),
                        "actual_model": str(getattr(result, "model", "") or ""),
                        "output_id": record.output_id,
                        "url": record.download_url,
                        "download_url": record.download_url,
                        "preview_url": record.preview_url,
                        "thumbnail_url": record.thumbnail_url,
                        "mime_type": record.mime_type,
                        "format": record.output_format,
                        "width": record.width,
                        "height": record.height,
                        "reference_asset_count": len(reference_assets),
                        "v3_owned_output": True,
                    },
                )
            )
        if not candidates:
            raise ValueError("V3 production provider could not persist any generated image outputs.")
        return GenerationResponse(
            candidates=candidates,
            provider_metadata={
                "provider_name": self.provider_name,
                "provider_version": self.provider_version,
                "runtime_mode": "production_image_generation",
                "actual_provider": str(getattr(result, "provider", provider_name)),
                "actual_model": str(getattr(result, "model", "") or ""),
                "reference_asset_count": len(reference_assets),
            },
            warnings=warnings,
        )

    async def _generate_with_app_provider(self, provider_name: str, app_request):
        provider = self._app_provider(provider_name)
        return await provider.generate(app_request)

    def _build_app_request(self, request: GenerationRequest):
        from app import schemas as app_schemas

        image_request_cls = getattr(app_schemas, "ImageGenerationRequest")
        prompt_plan_cls = getattr(app_schemas, "Image" + "PromptPlan")

        reference_assets = self._reference_assets(request)
        asset_plan = self._asset_plan(reference_assets)
        provider_name = self._select_provider(reference_assets)
        size = self._size_for_request(request)
        prompt_plan = prompt_plan_cls(
            main_subject=request.asset_spec.purpose if request.asset_spec else request.prompt_compilation.asset_id,
            scene=self._scene_for_request(request),
            style=", ".join(request.prompt_compilation.style_notes),
            composition=self._composition_for_request(request),
            brand_constraints=list(request.prompt_compilation.hard_constraints),
            negative_constraints=self._negative_constraints(request),
            text={},
            count=1,
            size=size,
            quality=self._quality_for_request(request),
            output_format="png",
            variables={
                "generation_prompt": self._generation_prompt(request, reference_assets),
                "asset_plan": asset_plan,
                "v3_prompt_compilation_id": request.prompt_compilation.prompt_compilation_id,
                "v3_generation_plan_id": request.generation_plan.generation_plan_id,
                "v3_provider_strategy": request.generation_plan.provider_strategy.value,
            },
        )
        return (
            image_request_cls(
                prompt_plan=prompt_plan,
                asset_ids=[item["asset_id"] for item in asset_plan.get("assets", [])],
                asset_mode="advanced" if reference_assets else "basic",
                asset_plan=asset_plan if reference_assets else None,
                provider_preference=provider_name,
                idempotency_key=stable_id(
                    "v3_image",
                    request.metadata.get("job_id"),
                    request.generation_plan.asset_id,
                    request.prompt_compilation.prompt_compilation_id,
                ),
                trace_id=stable_id("trace", request.metadata.get("job_id"), request.generation_plan.asset_id),
            ),
            provider_name,
            reference_assets,
        )

    def _app_provider(self, provider_name: str):
        if provider_name == "doubao_image":
            from app.providers.doubao_image import DoubaoImageProvider

            return DoubaoImageProvider()
        if provider_name == "gemini_image":
            from app.providers.gemini_image import GeminiImageProvider

            return GeminiImageProvider()
        from app.providers.openai_image import OpenAIGPTImageProvider

        return OpenAIGPTImageProvider()

    def _select_provider(self, reference_assets: list[dict[str, Any]]) -> str:
        from app.config import settings

        self._import_v1_v2_provider_config(settings)
        default_provider = str(settings.default_image_provider or "openai_gpt_image")
        if reference_assets:
            ordered = [default_provider, "openai_gpt_image", "gemini_image", "doubao_image"]
        else:
            ordered = [default_provider, "openai_gpt_image", "doubao_image", "gemini_image"]
        errors: list[str] = []
        for provider_name in _dedupe(ordered):
            if provider_name == "mock_image":
                continue
            if provider_name == "openai_gpt_image":
                if settings.openai_api_key:
                    return provider_name
                errors.append("OPENAI_API_KEY is not configured")
            elif provider_name == "doubao_image":
                if reference_assets:
                    errors.append("DOUBAO_IMAGE_API_KEY cannot be used with uploaded reference images")
                    continue
                if settings.doubao_image_api_key:
                    return provider_name
                errors.append("DOUBAO_IMAGE_API_KEY is not configured")
            elif provider_name == "gemini_image":
                if settings.gemini_image_api_key and settings.gemini_image_generation_enabled:
                    return provider_name
                errors.append("GEMINI_IMAGE_API_KEY is not configured or Gemini image generation is disabled")
        raise ValueError(
            "No configured real image provider is available for V3 generation. "
            "Reuse the V1/V2 provider settings by configuring OPENAI_API_KEY/OPENAI_BASE_URL, "
            "DOUBAO_IMAGE_API_KEY/DOUBAO_IMAGE_BASE_URL, or GEMINI_IMAGE_API_KEY. "
            f"Checked: {'; '.join(_dedupe(errors))}."
        )

    def _import_v1_v2_provider_config(self, settings) -> None:
        if not settings.openai_api_key and getattr(settings, "lab_openai_api_key", None):
            settings.openai_api_key = settings.lab_openai_api_key
        if not settings.openai_base_url and getattr(settings, "lab_openai_base_url", None):
            settings.openai_base_url = settings.lab_openai_base_url
        if not settings.doubao_image_api_key and getattr(settings, "lab_doubao_vision_api_key", None):
            settings.doubao_image_api_key = settings.lab_doubao_vision_api_key
        if not settings.doubao_image_base_url and getattr(settings, "lab_doubao_vision_base_url", None):
            settings.doubao_image_base_url = settings.lab_doubao_vision_base_url

    def _reference_assets(self, request: GenerationRequest) -> list[dict[str, Any]]:
        raw_assets = request.metadata.get("uploaded_assets")
        if not isinstance(raw_assets, list):
            raw_assets = request.generation_plan.metadata.get("uploaded_assets", [])
        assets: list[dict[str, Any]] = []
        for item in raw_assets if isinstance(raw_assets, list) else []:
            data = item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item or {})
            path = data.get("file_path")
            if not path:
                continue
            try:
                file_path = Path(str(path))
            except TypeError:
                continue
            if not file_path.exists() or not file_path.is_file():
                continue
            assets.append(
                {
                    "asset_id": str(data.get("asset_id") or file_path.stem),
                    "role": str(data.get("role") or "unknown_reference"),
                    "filename": data.get("filename") or file_path.name,
                    "mime_type": data.get("mime_type"),
                    "file_path": str(file_path),
                    "uri": data.get("uri"),
                    "metadata": data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
                }
            )
        return assets[:6]

    def _asset_plan(self, reference_assets: list[dict[str, Any]]) -> dict[str, Any]:
        assets = []
        for index, asset in enumerate(reference_assets):
            assets.append(
                {
                    "asset_id": asset["asset_id"],
                    "role": _v1_reference_role(asset.get("role")),
                    "priority": 100 - index,
                    "provider_input_mode": "reference_image",
                    "storage_path": asset["file_path"],
                    "filename": asset.get("filename"),
                    "mime_type": asset.get("mime_type"),
                    "prompt_constraints": [
                        "Use this uploaded image as visual evidence for product identity, material, style, or composition."
                    ],
                    "negative_constraints": [],
                }
            )
        return {
            "asset_mode": "advanced",
            "assets": assets,
            "provider_requirements": {"needs_image_reference": bool(assets), "needs_image_edit": False},
            "provider_input_plan": {
                "operation": "image_edit_with_reference_images" if assets else "generate",
                "reference_image_asset_ids": [item["asset_id"] for item in assets],
                "reference_image_count": len(assets),
                "requires_image_reference": bool(assets),
            },
        }

    def _generation_prompt(self, request: GenerationRequest, reference_assets: list[dict[str, Any]]) -> str:
        prompt = request.prompt_compilation
        asset = request.asset_spec
        layout = request.layout_plan
        parts = [
            "Create a polished, directly usable commercial image asset.",
            f"Visual direction: {prompt.visual_prompt}",
            f"Asset purpose: {asset.purpose}" if asset else "",
            f"Platform: {asset.platform.value}; aspect ratio: {asset.aspect_ratio}" if asset else "",
            f"Composition: {layout.product_area.position}" if layout else "",
            f"Visual hierarchy: {', '.join(layout.visual_hierarchy)}" if layout and layout.visual_hierarchy else "",
            "Reserve clean blank areas for later UI/text overlay outside the generated pixels.",
            "Do not add any new visible text, captions, typography, icons, badges, seals, claim strips, infographic footers, or product claims inside the image.",
            "Only preserve text already visible on the supplied product label if it remains in frame; do not translate, rewrite, enlarge, or invent label copy.",
            "Preserve supplied product facts, visible product identity, logos, material cues, and proportions.",
            f"Style notes: {', '.join(prompt.style_notes)}" if prompt.style_notes else "",
            f"Layout notes: {', '.join(prompt.layout_notes)}" if prompt.layout_notes else "",
            f"Hard constraints: {'; '.join(prompt.hard_constraints)}" if prompt.hard_constraints else "",
        ]
        if reference_assets:
            reference_lines = [
                f"{index + 1}. {asset.get('role') or 'reference'} - {asset.get('filename') or asset.get('asset_id')}"
                for index, asset in enumerate(reference_assets)
            ]
            parts.append("Uploaded reference images must guide the result:\n" + "\n".join(reference_lines))
        if prompt.negative_prompt:
            parts.append(f"Avoid: {prompt.negative_prompt}")
        return "\n".join(part for part in parts if str(part or "").strip())

    def _negative_constraints(self, request: GenerationRequest) -> list[str]:
        values = [
            "new visible text",
            "invented captions",
            "typography overlays",
            "infographic icons",
            "claim badges",
            "bottom feature strips",
            "unsupported product claims",
            "unreadable text",
            "fake brand marks",
            "distorted product identity",
            "cluttered composition",
        ]
        if request.prompt_compilation.negative_prompt:
            values.extend(part.strip() for part in request.prompt_compilation.negative_prompt.split(",") if part.strip())
        return list(dict.fromkeys(values))

    def _scene_for_request(self, request: GenerationRequest) -> str | None:
        if request.layout_plan and request.layout_plan.background_strategy:
            return request.layout_plan.background_strategy
        if request.asset_spec:
            return request.asset_spec.purpose
        return None

    def _composition_for_request(self, request: GenerationRequest) -> str | None:
        layout = request.layout_plan
        if not layout:
            return None
        notes = [layout.product_area.position, *layout.visual_hierarchy]
        return ", ".join(item for item in notes if item)

    def _size_for_request(self, request: GenerationRequest) -> str:
        ratio = str((request.asset_spec.aspect_ratio if request.asset_spec else "") or "").strip()
        mapping = {
            "1:1": "1024x1024",
            "2:3": "1024x1536",
            "3:4": "1024x1536",
            "4:5": "1024x1536",
            "9:16": "1024x1536",
            "3:2": "1536x1024",
            "4:3": "1536x1024",
            "5:4": "1536x1024",
            "16:9": "1536x1024",
        }
        return mapping.get(ratio, "1024x1024")

    def _quality_for_request(self, request: GenerationRequest) -> str:
        quality_mode = str(request.metadata.get("quality_mode") or request.generation_plan.metadata.get("quality_mode") or "standard")
        return "high" if quality_mode == "strict" else "medium"


def _run_async_blocking(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:
            result["error"] = exc

    thread = threading.Thread(target=runner, name="v3-production-provider", daemon=True)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _v1_reference_role(role: str | None) -> str:
    mapping = {
        "product_reference": "subject_reference",
        "unknown_reference": "subject_reference",
        "logo_reference": "logo_overlay",
        "face_reference": "portrait_identity",
        "background_reference": "background_reference",
        "composition_reference": "composition_reference",
        "style_reference": "style_reference",
        "color_reference": "style_reference",
        "negative_reference": "negative_reference",
    }
    return mapping.get(str(role or ""), "subject_reference")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
