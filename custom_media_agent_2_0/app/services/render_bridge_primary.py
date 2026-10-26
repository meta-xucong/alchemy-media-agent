"""V2-native adapter; imports only the product-neutral Bridge transport."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import sqlite3
import time
from contextlib import contextmanager
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
    record = {"adapter_version": "codex_cli_imagegen_v1",
              "request": request.model_dump(mode="json"), "job_id": job_id,
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
    transport_provenance = getattr(result, "provenance", {})
    if isinstance(transport_provenance, dict):
        for key in ("attempt_id", "deadline"):
            value = transport_provenance.get(key)
            if value is not None:
                provenance[key] = value
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
    def __init__(self, state: str, *, terminal: bool = False, deadline: str | None = None):
        self.state, self.terminal, self.deadline = state, terminal, deadline
        super().__init__(state)


def ensure_not_cancelled(job_id: str):
    job = repository.get_image_job(job_id)
    if job is not None and job.status == "cancelled":
        raise BridgeWait("canceled", terminal=True)


def _codex_cli_adaptation(params: dict, reference_count: int) -> tuple[dict, dict]:
    from render_bridge_primary.codex_adapter import codex_cli_adaptation
    return codex_cli_adaptation(params, reference_count)

def _legacy_unit_request(record: dict, index: int):
    request = primary_request(record)
    params = dict(request.parameters)
    requirements = dict(request.hard_requirements)
    width, height = params.get("width", 1024), params.get("height", 1024)
    size = str(params.get("size") or "")
    if "x" in size:
        try:
            width, height = (int(value) for value in size.split("x", 1))
        except ValueError:
            requirements["size"] = size
    elif size and size not in {"auto", "default"}:
        requirements["size"] = size
    if params.get("aspect_ratio"):
        requirements["aspect_ratio"] = params["aspect_ratio"]
    if any(params.get(key) not in {None, "", "auto", "default"} for key in ("size", "width", "height")):
        requirements["exact_dimensions"] = True
    # Never discard meaningful provider options merely because the wire lacks them.
    for key, value in params.items():
        if key not in {"count", "width", "height", "size", "seed", "provider_hint", "aspect_ratio"} and value is not None:
            requirements[key] = value
    wire = {"width": int(width), "height": int(height)}
    if "seed" in params:
        wire["seed"] = params["seed"]
    if "output_format" in params or "quality" in params:
        wire["image_options"] = {"schema_version": "1", "quality": params.get("quality", "auto"),
                                 "output_format": params.get("output_format", "png")}
    return replace(request, unit_id=f"{record['job_id']}:{index}", parameters=wire, hard_requirements=requirements)


def _normalized_unit_request(record: dict, index: int, *, versioned: bool):
    request = primary_request(record)
    requirements = dict(request.hard_requirements)
    requirements.pop("input_fidelity", None)
    wire, _ = _codex_cli_adaptation(dict(request.parameters), len(request.references))
    if versioned:
        wire["codex_adapter"] = "codex_cli_imagegen_v1"
    return replace(request, unit_id=f"{record['job_id']}:{index}", parameters=wire,
                   hard_requirements=requirements)


def _unit_request(record: dict, index: int, client=None):
    """Reconstruct frozen semantics, never upgrade an already journaled unit."""
    from render_bridge_primary import PrimaryError
    version = record.get("adapter_version")
    if version == "codex_cli_imagegen_v1":
        return _normalized_unit_request(record, index, versioned=True)
    if version is not None:
        raise PrimaryError("unsupported_frozen_adapter_version")
    # PR38 and PR39 both wrote unversioned frozen records. Their existing
    # journal digest, not current capabilities, is the authority for recovery.
    try:
        legacy = _legacy_unit_request(record, index)
    except (ValueError, TypeError):
        # PR39 normalization accepted some values that PR38 could not parse.
        # They may resume only if their exact PR39 digest was already journaled.
        if client is not None:
            matched = client.match_existing_request((
                _normalized_unit_request(record, index, versioned=False),))
            if matched is not None:
                return matched
        raise PrimaryError("legacy_request_invalid") from None
    if client is not None:
        matched = client.match_existing_request((legacy,
            _normalized_unit_request(record, index, versioned=False)))
        if matched is not None:
            return matched
    # No journal means no known admission. Preserve the older strict contract
    # rather than silently weakening an unversioned request's original intent.
    return legacy


def _count(record: dict) -> int:
    return max(1, min(int(frozen_request(record).prompt_plan.provider_parameters.get("count", 1)), 8))


def _cache_path(record: dict, index: int) -> Path:
    return _path(f"result:{record['job_id']}:{index}")


@contextmanager
def _cleanup_db():
    path = settings.data_dir / 'render_bridge_primary' / 'cleanup.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=1)
    try:
        with db:
            db.execute('CREATE TABLE IF NOT EXISTS cleanup (job_id TEXT PRIMARY KEY, checked_at REAL NOT NULL DEFAULT 0)')
            yield db
    finally:
        db.close()


def request_cache_cleanup(job_id: str):
    """Durable intent, not permission to erase pending generation/settlement."""
    if not _path(f'job:{job_id}').exists(): return
    with _cleanup_db() as db:
        db.execute('INSERT OR IGNORE INTO cleanup(job_id) VALUES(?)', (job_id,))


def _retire_completed_cache(record, client):
    job = repository.get_image_job(record['job_id'])
    if job is None or job.status != 'completed': return False
    if not record.get('cache_retired'):
        # Synthetic test transports need not implement storage lifecycle hooks.
        retire = getattr(client, 'retire_units', None)
        if retire is None or not retire(tuple(_unit_request(record, i, client) for i in range(_count(record)))):
            return False
    record = dict(record, cache_retired=True, references=[])
    keys = [f"job:{record['job_id']}"]
    if record.get('queue_task_id'): keys.append(f"task:{record['queue_task_id']}")
    for key in keys:
        path = _path(key)
        temporary = path.with_suffix(f'.{os.getpid()}.retire.tmp')
        with temporary.open('w', encoding='utf-8') as handle:
            json.dump(record, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    for index in range(_count(record)):
        _cache_path(record, index).unlink(missing_ok=True)
    with _cleanup_db() as db:
        db.execute('DELETE FROM cleanup WHERE job_id=?', (record['job_id'],))
    return True


def cleanup_published_job_cache(job_id: str):
    """No-network deletion hook; pending ACK keeps bytes for later maintenance."""
    record = load_frozen(job_id)
    if record is None: return False
    request_cache_cleanup(job_id)
    from render_bridge_primary import PrimarySettings, PrimaryTransport, PrimaryError
    try:
        client = PrimaryTransport(PrimarySettings.from_env(product='v2'), client=object())
        return _retire_completed_cache(record, client)
    except PrimaryError:
        logging.getLogger(__name__).warning('V2 Bridge completed-cache cleanup deferred by its safety guard')
        return False


async def maintain_completed_caches(limit=8):
    """Bounded existing-worker maintenance; ACK only, never render or bill."""
    path = settings.data_dir / 'render_bridge_primary' / 'cleanup.sqlite3'
    if not path.exists(): return 0
    with _cleanup_db() as db:
        jobs = db.execute('SELECT job_id FROM cleanup ORDER BY checked_at, job_id LIMIT ?',
                          (max(0, min(int(limit), 32)),)).fetchall()
    completed = 0
    for (job_id,) in jobs:
        with _cleanup_db() as db:
            db.execute('UPDATE cleanup SET checked_at=? WHERE job_id=?', (time.time(), job_id))
        try:
            record = load_frozen(job_id)
            job = repository.get_image_job(job_id)
            if record is None or job is None or job.status != 'completed': continue
            if await acknowledge(record): completed += 1
        except (ValueError, KeyError, TypeError):
            # A malformed historical cache stays protected. It cannot stop the
            # ordinary queue worker or authorize a fresh image/debit attempt.
            logging.getLogger(__name__).warning('V2 Bridge malformed completed cache retained for inspection')
    return completed


async def generate(record: dict, select_provider):
    """Per-output routing; earlier accepted/completed units are never regenerated."""
    client = transport(record["job_id"])
    try:
        return await _generate(record, select_provider, client)
    finally:
        await client.close()


async def _generate(record: dict, select_provider, client):
    from app.providers.images import V2ImageProviderRequest
    if record.get('cache_retired'):
        raise BridgeWait('bridge_cache_retired', terminal=True)
    request = frozen_request(record)
    all_outputs = []
    providers = []
    for index in range(_count(record)):
        task_queue.ensure_current_claim()
        ensure_not_cancelled(record["job_id"])
        from render_bridge_primary import PrimaryError
        try:
            unit = _unit_request(record, index, client)
        except PrimaryError as exc:
            raise BridgeWait(exc.code, terminal=True) from exc
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
                    provenance = getattr(decision, "provenance", {})
                    raise BridgeWait(decision.state, terminal=terminal,
                                     deadline=provenance.get("deadline") if isinstance(provenance, dict) else None)
                adaptation = None
                if (unit.parameters.get("codex_adapter") == "codex_cli_imagegen_v1" or
                        unit.digest == _normalized_unit_request(record, index, versioned=False).digest):
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
        request_cache_cleanup(record['job_id'])
        await _acknowledge(record)
    except (PrimaryError, BridgeError, OSError, sqlite3.Error):
        # Native output/debit is already durable; ACK outage cannot undo success.
        return False
    return True


async def _acknowledge(record: dict):
    client = transport()
    try:
        if record.get('cache_retired'):
            _retire_completed_cache(record, client)
            return
        for index in range(_count(record)):
            task_queue.ensure_current_claim()
            cached = V2ImageProviderResult.model_validate_json(_cache_path(record, index).read_text(encoding="utf-8"))
            unit = _unit_request(record, index, client)
            if cached.provider == "render_bridge":
                await client.acknowledge(unit, registration_ref=f"v2:{record['job_id']}:{index}")
            else:
                client.complete_api(unit)
        _retire_completed_cache(record, client)
    finally:
        await client.close()


async def cancel(record: dict):
    client = transport()
    try:
        for index in range(_count(record)):
            unit = _unit_request(record, index, client)
            if client.has_binding(unit):
                await client.cancel(unit)
    finally:
        await client.close()
