"""V2-native adapter; imports only the product-neutral Bridge transport."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.repositories import repository
from app.providers.images.base import V2ImageProviderOutput, V2ImageProviderResult
from app.schemas import CreateImageJobRequest
from app.services import task_queue
from app.services.uploaded_assets import uploaded_asset_path


def transport(job_id: str | None = None):
    from render_bridge_primary import PrimarySettings, PrimaryTransport
    config = PrimarySettings.from_env(product="v2")
    client = PrimaryTransport(config)
    async def fence_request(_request):
        task_queue.ensure_current_claim()
        if job_id is not None:
            ensure_not_cancelled(job_id)
    client.client.http.event_hooks["request"].append(fence_request)
    return client


def enabled() -> bool:
    # Do not initialize a transport ledger merely to inspect configuration.
    from render_bridge_primary import PrimarySettings
    return PrimarySettings.from_env(product="v2").enabled


def _path(key: str) -> Path:
    return settings.data_dir / "render_bridge_primary" / "requests" / (hashlib.sha256(key.encode()).hexdigest() + ".json")


def load_frozen(job_id: str | None = None) -> dict | None:
    claim = task_queue.current_claim()
    key = f"task:{claim.task_id}" if claim is not None and job_id is None else f"job:{job_id}"
    path = _path(key)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def frozen_request(record: dict) -> CreateImageJobRequest:
    return CreateImageJobRequest.model_validate(record["request"])


def freeze(request: CreateImageJobRequest, job_id: str, created_at: datetime, qr: bool) -> dict:
    existing = load_frozen() if task_queue.current_claim() else load_frozen(job_id)
    if existing is not None:
        return existing
    references = []
    requirements = {}
    for image in request.input_images:
        if not image.provider_input_required:
            continue
        path = uploaded_asset_path(image.asset_id)
        if path is None or not path.is_file():
            requirements["missing_reference"] = True
            continue
        references.append({"content": base64.b64encode(path.read_bytes()).decode(), "mime_type": image.mime_type or "image/png"})
        if image.constraint_strength in {"strong", "required"}:
            requirements["reference_fusion"] = True
            requirements["input_fidelity"] = "high"
    variables = request.prompt_plan.user_variables
    delivery = variables.get("reference_delivery") or {}
    if qr or (isinstance(delivery, dict) and (delivery.get("deterministic_text_overlay") or {}).get("items")):
        requirements["deterministic_postprocess"] = True
    record = {"request": request.model_dump(mode="json"), "job_id": job_id,
              "created_at": created_at.isoformat(), "qr": qr, "references": references,
              "requirements": requirements, "queue_task_id": task_queue.current_claim().task_id if task_queue.current_claim() else None}
    def persist():
        keys = [f"job:{job_id}"]
        claim = task_queue.current_claim()
        if claim is not None:
            keys.append(f"task:{claim.task_id}")
        for key in keys:
            target = _path(key)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(f".{os.getpid()}.tmp")
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(record, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
    task_queue.persist_claimed_operation(persist)
    return record


def primary_request(record: dict):
    from render_bridge_primary import PrimaryRequest, Reference
    request = frozen_request(record)
    params = dict(request.prompt_plan.provider_parameters)
    requirements = dict(record["requirements"])
    prompt = str(request.prompt_plan.user_variables.get("generation_prompt") or request.prompt_plan.prompt)
    if request.prompt_plan.negative_prompt:
        prompt += "\nNegative constraints:\n" + request.prompt_plan.negative_prompt
    return PrimaryRequest(product="v2", owner_id=str(request.veyra_user_id or "local"),
        unit_id=record["job_id"], prompt=prompt, parameters=params,
        references=tuple(Reference(content=base64.b64decode(ref["content"]), mime_type=ref["mime_type"]) for ref in record["references"]),
        hard_requirements=requirements)


def provider_result(result, *, parameter_adaptation: dict | None = None) -> V2ImageProviderResult:
    image = result.image
    provenance = {key: getattr(result, key, None) for key in ("route", "state", "reason", "origin_key", "task_id", "receipt_id", "execution_key")}
    if parameter_adaptation:
        provenance["parameter_adaptation"] = parameter_adaptation
    return V2ImageProviderResult(provider="render_bridge", model="render-bridge-primary",
        outputs=[V2ImageProviderOutput(b64_json=base64.b64encode(image.content).decode(),
            mime_type=image.mime_type, format=image.mime_type.split("/")[-1], width=image.width, height=image.height,
            metadata={"render_bridge_primary": provenance, "original_sha256": image.sha256,
                      "width": image.width, "height": image.height, "original_size_bytes": len(image.content),
                      "preserve_original_bytes": True})],
        raw_response_summary={"render_bridge_primary": provenance})


class BridgeWait(Exception):
    def __init__(self, state: str, *, terminal: bool = False):
        self.state, self.terminal = state, terminal
        super().__init__(state)


def ensure_not_cancelled(job_id: str):
    job = repository.get_image_job(job_id)
    if job is not None and job.status == "cancelled":
        raise BridgeWait("canceled", terminal=True)


def _codex_cli_adaptation(params: dict, reference_count: int) -> tuple[dict, dict]:
    # Codex's imagegen tool exposes only prompt, up to five local references,
    # and transparent_background. All other Alchemy provider controls are
    # deliberately normalized to the native tool/model defaults on this copy;
    # the frozen request remains untouched for a proven pre-admission API route.
    background = str(params.get("background") or "").strip().lower()
    transparent = params.get("transparent_background") is True or background == "transparent"
    wire = {}
    if transparent:
        wire["image_options"] = {"schema_version": "1", "transparent_background": True}
    adaptation = {
        "adapter": "codex_cli_imagegen_v1",
        "defaults_applied": {
            key: ("per_unit" if key == "count" else "profile" if key == "provider_hint" else "native_default")
            for key, value in params.items()
            if value is not None and key not in {"background", "transparent_background"}
        },
        "transparent_background_requested": transparent,
        "transparent_background_mapping": "codex_cli_version_gated_or_default",
        "reference_count": reference_count,
    }
    return wire, adaptation


def _unit_request(record: dict, index: int):
    request = primary_request(record)
    requirements = dict(request.hard_requirements)
    requirements.pop("input_fidelity", None)  # gpt-image-2 uses high input fidelity by default.
    # Reference fusion is represented by the actual localImage inputs, not by a
    # separate Codex CLI flag. More than five references remain untruncated and
    # are rejected by the advertised profile limit before Bridge submission.
    wire, _ = _codex_cli_adaptation(dict(request.parameters), len(request.references))
    return replace(request, unit_id=f"{record['job_id']}:{index}", parameters=wire,
                   hard_requirements=requirements)


def _count(record: dict) -> int:
    return max(1, min(int(frozen_request(record).prompt_plan.provider_parameters.get("count", 1)), 8))


def _cache_path(record: dict, index: int) -> Path:
    return _path(f"result:{record['job_id']}:{index}")


async def generate(record: dict, select_provider):
    """Per-output routing; earlier accepted/completed units are never regenerated."""
    client = transport(record["job_id"])
    try:
        return await _generate(record, select_provider, client)
    finally:
        await client.close()


async def _generate(record: dict, select_provider, client):
    from app.providers.images import V2ImageProviderRequest
    request = frozen_request(record)
    all_outputs = []
    providers = []
    for index in range(_count(record)):
        task_queue.ensure_current_claim()
        ensure_not_cancelled(record["job_id"])
        unit = _unit_request(record, index)
        cache = _cache_path(record, index)
        if cache.exists():
            result = V2ImageProviderResult.model_validate_json(cache.read_text(encoding="utf-8"))
            for output in result.outputs:
                if output.metadata.get("preserve_original_bytes"):
                    content = base64.b64decode(output.b64_json, validate=True)
                    if hashlib.sha256(content).hexdigest() != output.metadata.get("original_sha256"):
                        raise BridgeWait("bridge_cached_original_integrity_failed", terminal=True)
        else:
            from render_bridge_primary import PrimaryError
            try:
                decision = await client.resolve(unit)
            except PrimaryError as exc:
                raise BridgeWait(exc.code, terminal=True) from exc
            task_queue.ensure_current_claim()
            ensure_not_cancelled(record["job_id"])
            if decision.route == "bridge":
                if decision.image is None:
                    terminal = decision.state in {"failed", "canceled", "cancelled", "expired", "rejected", "manual_review_required"}
                    raise BridgeWait(decision.state, terminal=terminal)
                _, adaptation = _codex_cli_adaptation(dict(request.prompt_plan.provider_parameters), len(unit.references))
                result = provider_result(decision, parameter_adaptation=adaptation)
            else:
                required = [image for image in request.input_images if image.provider_input_required]
                if len(required) != len(record["references"]):
                    raise BridgeWait("frozen_reference_missing", terminal=True)
                for image, reference in zip(required, record["references"], strict=True):
                    path = uploaded_asset_path(image.asset_id)
                    if path is None or not path.is_file() or path.read_bytes() != base64.b64decode(reference["content"]):
                        raise BridgeWait("frozen_reference_changed", terminal=True)
                provider = await select_provider(request.provider_hint)
                ensure_not_cancelled(record["job_id"])
                if not task_queue.persist_claimed_operation(lambda: client.claim_api(unit)):
                    raise BridgeWait("api_execution_unknown", terminal=True)
                params = dict(request.prompt_plan.provider_parameters)
                params["count"] = 1
                task_queue.ensure_current_claim()
                result = await provider.generate(V2ImageProviderRequest(run_id=request.run_id,
                    prompt_plan=request.prompt_plan.model_copy(update={"provider_parameters": params}),
                    input_images=request.input_images))
                if len(result.outputs) != 1:
                    raise BridgeWait("api_output_count_mismatch", terminal=True)
                for output in result.outputs:
                    output.metadata["render_bridge_primary"] = {
                        "route": "api", "reason": decision.reason, "execution_key": decision.execution_key,
                        "origin_key": decision.origin_key}
            def persist():
                cache.parent.mkdir(parents=True, exist_ok=True)
                temporary = cache.with_suffix(f".{os.getpid()}.tmp")
                with temporary.open("w", encoding="utf-8") as handle:
                    handle.write(result.model_dump_json())
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, cache)
            task_queue.persist_claimed_operation(persist)
        all_outputs.extend(result.outputs)
        providers.append(result.provider)
    return V2ImageProviderResult(provider=providers[0] if len(set(providers)) == 1 else "render_bridge_primary_mixed",
        model=result.model, outputs=all_outputs, raw_response_summary={"render_bridge_primary": True})


async def acknowledge(record: dict):
    from render_bridge_primary import PrimaryError
    from render_bridge_primary.http import BridgeError
    try:
        await _acknowledge(record)
    except (PrimaryError, BridgeError, OSError):
        # Native output/debit is already durable; ACK outage cannot undo success.
        return False
    return True


async def _acknowledge(record: dict):
    client = transport()
    try:
        for index in range(_count(record)):
            task_queue.ensure_current_claim()
            cached = V2ImageProviderResult.model_validate_json(_cache_path(record, index).read_text(encoding="utf-8"))
            unit = _unit_request(record, index)
            if cached.provider == "render_bridge":
                await client.acknowledge(unit, registration_ref=f"v2:{record['job_id']}:{index}")
            else:
                client.complete_api(unit)
    finally:
        await client.close()


async def cancel(record: dict):
    client = transport()
    try:
        for index in range(_count(record)):
            unit = _unit_request(record, index)
            if client.has_binding(unit):
                await client.cancel(unit)
    finally:
        await client.close()
