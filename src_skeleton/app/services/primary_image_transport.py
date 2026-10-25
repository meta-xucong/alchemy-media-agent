"""V1/Lab adapter. Product state and billing stay outside the neutral ledger."""
from __future__ import annotations

import base64
import hashlib
import mimetypes

from app.config import settings
from app.schemas import GenerationOutput, ImageGenerationRequest, JobStatus, ProviderError
from app.repositories import repository
from app.storage import media_store
from app.services.asset_planning import reference_image_paths

KEY = "primary_image_transport"


class PrimaryFinalizationInProgress(RuntimeError):
    """Cancellation must not hide pixels once an idempotent debit may commit."""



def primary_enabled(product):
    from render_bridge_primary import PrimarySettings
    return PrimarySettings.from_env(product=product).enabled


def transport_for(product):
    from render_bridge_primary import PrimarySettings, PrimaryTransport
    return PrimaryTransport(PrimarySettings.from_env(product=product))


def product_for(job):
    return "lab" if str(job.idempotency_key or "").startswith("lab:") else "v1"


def frozen_request(job):
    value = job.raw_response_summary.get(KEY, {}).get("request")
    return ImageGenerationRequest.model_validate(value) if value else None


def _legacy_primary_request(job, request, index, *, edit=False):
    from render_bridge_primary import PrimaryRequest, Reference
    from app.providers.openai_image import OpenAIGPTImageProvider
    plan = request.prompt_plan
    variables = plan.variables or {}
    paths = reference_image_paths(request.asset_plan, max_images=10000)
    # Basic source assets are not merely prompt hints.
    if not request.asset_plan:
        for asset_id in request.asset_ids:
            path = media_store.find_asset_file(asset_id)
            if path is None:
                raise ValueError("Primary image reference is unavailable")
            paths.append(path)
    refs = tuple(Reference(content=p.read_bytes(), mime_type=mimetypes.guess_type(str(p))[0] or "application/octet-stream") for p in paths)
    hard = {"output_format": plan.output_format}
    if plan.quality != "auto":
        hard["quality"] = plan.quality
    if plan.transparent_background or plan.background == "transparent":
        hard["transparent_background"] = True
    if plan.output_compression is not None:
        hard["output_compression"] = plan.output_compression
    if plan.moderation not in {None, "auto"}:
        hard["moderation"] = plan.moderation
    if variables.get("identity_repair_mask_path") or variables.get("mask"):
        hard["mask"] = True
    if variables.get("input_fidelity_required") or variables.get("input_fidelity"):
        hard["input_fidelity"] = variables.get("input_fidelity") or "high"
    if variables.get("seed") is not None:
        hard["seed"] = variables["seed"]
    if variables.get("exact_dimensions"):
        hard["exact_dimensions"] = True
    if edit or request.source_output_id:
        hard["edit_source"] = True
    if request.asset_plan:
        hard["asset_fusion"] = request.asset_plan
    if refs:
        hard["reference_semantics"] = "reference_images"
    width, height = 1024, 1024
    if plan.size:
        try:
            width, height = map(int, plan.size.lower().replace("×", "x").split("x"))
        except (ValueError, AttributeError):
            hard["size"] = plan.size
    return PrimaryRequest(
        product=product_for(job), owner_id=str(request.veyra_user_id or job.session_id or "anonymous"),
        unit_id=f"{job.id}:{index}", prompt=OpenAIGPTImageProvider()._render_prompt(plan),
        parameters={"width": width, "height": height, "image_options": {"schema_version": "1", "quality": "auto", "output_format": plan.output_format}},
        references=refs, hard_requirements=hard,
    )


def primary_request(job, request, index, *, edit=False):
    from dataclasses import replace
    from render_bridge_primary import PrimaryError, Reference
    from render_bridge_primary.codex_adapter import CODEX_ADAPTER_VERSION, codex_cli_adaptation

    version = job.raw_response_summary.get(KEY, {}).get("adapter_version")
    if version not in {None, CODEX_ADAPTER_VERSION}:
        raise PrimaryError("unsupported_frozen_adapter_version")
    unit = _legacy_primary_request(job, request, index, edit=edit)
    if version is None:
        return unit  # Existing durable identities retain their exact original digest.
    plan = request.prompt_plan
    variables = plan.variables or {}
    hard = dict(unit.hard_requirements)
    for key in ("quality", "output_format", "output_compression", "transparent_background",
                "size", "exact_dimensions", "seed", "input_fidelity"):
        hard.pop(key, None)
    if variables.get("input_fidelity_required"):
        hard["input_fidelity_required"] = True
    refs = unit.references
    if edit or request.source_output_id:
        source = media_store.find_output_file(request.source_output_id) if request.source_output_id else None
        if source is None:
            raise PrimaryError("primary_edit_source_unavailable")
        output = repository.get_output(request.source_output_id)
        source_job = repository.get_job(output.job_id) if output else None
        if (not output or not source_job or source_job.session_id != job.session_id
                or output.metadata.get("veyra_user_id") != request.veyra_user_id
                or source[2] != source_job.id or media_store.output_publication_blocked(output.id)):
            raise PrimaryError("primary_edit_source_not_accessible")
        path = source[0]
        source_ref = Reference(content=path.read_bytes(), mime_type=mimetypes.guess_type(str(path))[0] or "application/octet-stream")
        if source_ref not in refs:
            refs = (source_ref,) + refs
        hard.pop("edit_source", None)
    if refs:
        hard.pop("reference_semantics", None)
        hard["reference_fusion"] = True
    params = {key: getattr(plan, key) for key in (
        "quality", "size", "output_format", "output_compression", "background", "transparent_background", "count")}
    wire, _ = codex_cli_adaptation(params, len(refs))
    wire["codex_adapter"] = CODEX_ADAPTER_VERSION
    return replace(unit, parameters=wire, hard_requirements=hard, references=refs)


async def run_primary(job, request, *, edit=False):
    """Return False only for excluded legacy paths; otherwise mutate product job."""
    existing = job.raw_response_summary.get(KEY)
    if not existing and (request.provider_preference or settings.default_image_provider) == "mock_image":
        return False
    if not existing and not primary_enabled(product_for(job)):
        return False
    async with transport_for(product_for(job)) as transport:
        return await _run_owned(job, request, edit=edit, transport=transport, existing=existing)


async def _run_owned(job, request, *, edit, transport, existing):
    from app.services import image_service
    from app.providers.registry import registry
    if existing:
        request = frozen_request(job)
        edit = bool(existing.get("edit"))
    else:
        from render_bridge_primary.codex_adapter import CODEX_ADAPTER_VERSION
        job.raw_response_summary[KEY] = {"adapter_version": CODEX_ADAPTER_VERSION,
                                         "request": request.model_dump(mode="json"), "edit": edit, "units": {}}
        repository.save_job(job)
    state = job.raw_response_summary[KEY]
    outputs = list(job.outputs) or [GenerationOutput.model_validate(value) for value in state.get("outputs", [])]
    for index in range(request.prompt_plan.count):
        unit = primary_request(job, request, index, edit=edit)
        output_id = "out_" + hashlib.sha256(f"{job.id}:primary:{index}".encode()).hexdigest()[:32]
        if any(output.id == output_id for output in outputs):
            continue
        result = await transport.resolve(unit)
        current = repository.get_job(job.id)
        if current and current.status == JobStatus.canceled:
            job.status = JobStatus.canceled
            return True
        state["units"][str(index)] = dict(result.provenance)
        repository.save_job(job)
        if result.route == "bridge":
            job.provider = result.provenance.get("actual_provider") or "render_bridge"
            job.model = result.provenance.get("actual_model") or "unknown"
            if result.image is None:
                job.status = JobStatus.canceled if result.state == "canceled" else JobStatus.failed if result.state in {"failed", "expired"} else JobStatus.generating
                job.error = ProviderError(code=f"bridge_{result.state}", message="Render Bridge owns this image; resume the same task.", retryable=False)
                return True
            image = result.image
            item = {"b64_json": base64.b64encode(image.content).decode(), "format": image.mime_type.split("/")[-1], "width": image.width, "height": image.height,
                    "primary_output_id": output_id, "bridge_original": True, "sha256": image.sha256, "original_size": len(image.content), "primary_provenance": dict(result.provenance)}
            outputs.extend(image_service._store_outputs(job, [item], request=request))
        else:
            provider = await registry.select_image(request.provider_preference)
            single = request.model_copy(update={"prompt_plan": request.prompt_plan.model_copy(update={"count": 1})})
            job.provider = provider.name
            if single.asset_plan:
                image_service.validate_asset_plan_with_provider(single.asset_plan, await provider.capabilities())
            job.cost_estimate = await provider.estimate_cost(single)
            if not transport.claim_api(unit):
                job.status = JobStatus.generating
                job.error = ProviderError(code="api_execution_unknown", message="The original provider execution requires reconciliation.", retryable=False)
                return True
            try:
                generated = await provider.edit(single) if edit else await provider.generate(single)
            except Exception:
                job.status = JobStatus.generating
                job.error = ProviderError(code="api_execution_unknown", message="The original provider execution requires reconciliation.", retryable=False)
                return True
            current = repository.get_job(job.id)
            if current and current.status == JobStatus.canceled:
                job.status = JobStatus.canceled
                return True
            if len(generated.outputs) != 1:
                job.status = JobStatus.failed
                job.error = ProviderError(code="primary_output_count_mismatch", message="Provider returned an unexpected output count.", retryable=False)
                return True
            job.provider, job.model = generated.provider, generated.model
            item = {**generated.outputs[0], "primary_output_id": output_id, "primary_provenance": dict(result.provenance)}
            outputs.extend(image_service._store_outputs(job, [item], request=request))
        # Job.outputs is publication authority. Keep partial/before-billing
        # materializations only in the private recovery checkpoint.
        state["outputs"] = [output.model_dump(mode="json") for output in outputs]
        job.outputs = []
        repository.save_job(job)
    job.outputs = outputs
    job.status, job.error = JobStatus.ready, None
    return True


async def finish_primary(job, request):
    state = job.raw_response_summary.get(KEY)
    if not state:
        return
    async with transport_for(product_for(job)) as transport:
        for index in range(request.prompt_plan.count):
            unit = primary_request(job, request, index, edit=bool(state.get("edit")))
            result = await transport.resolve(unit)
            if result.route == "bridge":
                await transport.acknowledge(unit, registration_ref=f"{job.id}:{index}")
            else:
                transport.complete_api(unit)

async def resume_primary_job(job_id):
    from app.services.image_service import _run_image_request
    job = repository.get_job(job_id)
    if not job or not frozen_request(job):
        return job
    if job.status == JobStatus.ready:
        # History may have been interrupted after the ready checkpoint.
        from app.services.image_service import _persist_history_records
        _persist_history_records(job)
        try:
            await finish_primary(job, frozen_request(job))
        except Exception:
            pass  # ACK is retryable; do not turn a published image into a failure.
        return job
    if job.status in {JobStatus.failed, JobStatus.canceled, JobStatus.rejected}:
        return job
    return await _run_image_request(job, frozen_request(job), edit=bool(job.raw_response_summary[KEY].get("edit")))


async def cancel_primary_job(job_id):
    job = repository.get_job(job_id)
    if not job or not frozen_request(job) or job.status in {JobStatus.ready, JobStatus.failed, JobStatus.rejected}:
        return job
    job.status = JobStatus.canceled
    saved = repository.save_job(job)  # Atomically refuses cancellation after billing entry.
    if saved.status != JobStatus.canceled:
        raise PrimaryFinalizationInProgress("Image billing finalization is already in progress.")
    request = frozen_request(job)
    async with transport_for(product_for(job)) as transport:
        owner = str(request.veyra_user_id or job.session_id or "anonymous")
        for unit_id in transport.bindings_for(product_for(job), owner, f"{job.id}:"):
            try:
                await transport.cancel_binding(product_for(job), owner, unit_id)
            except Exception:
                pass  # Never resubmit or invoke API after uncertain cancellation.
    return repository.get_job(job.id)


def public_image_job(job):
    """Project safe route evidence without changing the durable recovery record."""
    if job is None or not job.raw_response_summary.get(KEY):
        return job
    state = job.raw_response_summary[KEY]
    allowed = {
        "policy_version", "product", "profile", "route", "state", "reason", "origin_key",
        "execution_key", "task_id", "receipt_id", "attempt_id", "execution_profile_id",
        "execution_profile_revision", "actual_provider", "provider_evidence", "actual_model",
        "model_evidence", "queue_count", "queue_limit", "queue_observed_at", "queue_snapshot_diagnostic",
    }
    units = {}
    for index, provenance in state.get("units", {}).items():
        safe = {key: value for key, value in provenance.items() if key in allowed}
        if isinstance(provenance.get("image"), dict):
            safe["image"] = {key: value for key, value in provenance["image"].items()
                             if key in {"sha256", "mime_type", "width", "height", "size"}}
        units[index] = safe
    summary = {**job.raw_response_summary, KEY: {"units": units, "billing_finalizing": bool(state.get("billing_finalizing"))}}
    return job.model_copy(update={"raw_response_summary": summary}, deep=True)
