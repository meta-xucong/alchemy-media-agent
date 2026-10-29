"""V3's canonical-request adapter, not a planning/router/native-gateway replacement."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import mimetypes
import sqlite3
import time
from dataclasses import replace
from pathlib import Path

from app.providers.base import ProviderRuntimeError
from app.schemas import ImageGenerationResult
from app.services.asset_planning import reference_image_paths

CONTEXT = "v3_bridge_primary_context"
PROVENANCE = "render_bridge_primary"
POLL_SECONDS = 1.0
# V3 gives each provider request a 300-second outer budget, including the
# existing 15-second finalization margin. Keep Bridge polling inside it.
POLL_BUDGET_SECONDS = 285.0



class BatchAdmissionGate:
    """Per-job durable cancellation, serialized with the next unit admission.

    The database is separate from the neutral unit journal. Holding this tiny
    per-job transaction through initial resolve prevents a cancellation from
    missing a concurrently admitted next unit. Other jobs do not share a lock.
    """
    def __init__(self, settings, owner_id, job_id):
        key = hashlib.sha256((str(owner_id) + "\0" + str(job_id)).encode()).hexdigest()
        self.path = settings.state_dir / "v3_batches" / (key + ".sqlite3")

    async def __aenter__(self):
        def acquire():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.path, timeout=120, check_same_thread=False)
            db.execute("CREATE TABLE IF NOT EXISTS batch (id INTEGER PRIMARY KEY, canceled INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO batch VALUES (1, 0)")
            db.commit()
            db.execute("BEGIN IMMEDIATE")
            return db
        acquisition = asyncio.create_task(asyncio.to_thread(acquire))
        try:
            self.db = await asyncio.shield(acquisition)
        except BaseException:
            # A canceled waiter must not leave a background SQLite writer lock.
            db = await acquisition
            db.close()
            raise
        return self

    @property
    def canceled(self):
        return bool(self.db.execute("SELECT canceled FROM batch WHERE id=1").fetchone()[0])

    def cancel(self):
        self.db.execute("UPDATE batch SET canceled=1 WHERE id=1")

    def assert_current(self):
        if self.canceled:
            raise _error("bridge_batch_cancel_requested")

    async def __aexit__(self, *_):
        self.db.commit()
        self.db.close()


def _gate_for(settings, app_request):
    context = dict(app_request.prompt_plan.variables.get(CONTEXT) or {})
    return BatchAdmissionGate(settings, context.get("owner_id"), context.get("job_id"))


def _error(code, provenance=None, *, provider="render_bridge", message=None, api_error_type=None):
    code = str(code)
    if provider == "render_bridge" and not code.startswith("bridge_"):
        code = "bridge_" + code
    not_submitted = isinstance(provenance, dict) and provenance.get("reason") == "bridge_store_busy"
    if message is None:
        message = (
            "Render Bridge input storage stayed busy; no remote image task was created. Retry the request later."
            if not_submitted else
            "The existing image execution must be recovered; no API fallback was called."
        )
    outcome = (
        {"request_state": "not_submitted", "retryability": "safe_to_retry"}
        if not_submitted else
        {"request_state": "accepted_unknown", "retryability": "status_required"}
    )
    return ProviderRuntimeError(
        message,
        provider=provider, detail={
            "failure_code": code, "transport_retry_terminal": True,
            "transport_retry_owner": "render_bridge_primary",
            "transport_outcome": outcome,
            PROVENANCE: dict(provenance or {}),
            **({"api_error_type": api_error_type} if api_error_type else {}),
        },
    )


def _source_request(app_request, *, native_defaults=False):
    from render_bridge_primary import PrimaryRequest, Reference

    plan = app_request.prompt_plan
    variables = dict(plan.variables or {})
    context = dict(variables.get(CONTEXT) or {})
    if not context.get("unit_id") or not context.get("owner_id") or not context.get("job_id"):
        raise _error("bridge_unit_identity_missing")
    asset_plan = app_request.asset_plan or variables.get("asset_plan") or {}
    assets = asset_plan.get("assets", [])
    paths = reference_image_paths(asset_plan, max_images=max(1, len(assets) + 1))
    canvas = variables.get("identity_repair_canvas_path")
    if canvas:
        paths = [Path(str(canvas)), *paths]
    references = tuple(Reference(Path(path).read_bytes(), mimetypes.guess_type(str(path))[0] or "application/octet-stream") for path in paths)
    # Do not let a missing materialized file silently become text-only generation.
    if any(item.get("provider_input_mode") == "reference_image" and not reference_image_paths({"assets": [item]}, max_images=1)
           for item in assets):
        raise _error("bridge_reference_materialization_missing")
    size = str("1024x1024" if native_defaults else plan.size or "1024x1024").split("x")
    if len(size) != 2 or not all(part.isdigit() for part in size):
        raise _error("bridge_invalid_frozen_dimensions")
    input_plan = asset_plan.get("provider_input_plan") or {}
    truth_layers = input_plan.get("reference_truth_layers") or []
    strong_identity = context.get("strong_identity") or any(
        isinstance(item, dict) and "identity" in str(item.get("truth_layer", ""))
        for item in truth_layers
    )
    hard = {
        "output_format": plan.output_format,
        "transparent_background": bool(plan.transparent_background or plan.background == "transparent"),
        "background": plan.background if plan.background not in (None, "auto") else None,
        "output_compression": plan.output_compression,
        "mask": (hashlib.sha256(Path(str(variables["identity_repair_mask_path"])).read_bytes()).hexdigest()
                 if variables.get("identity_repair_mask_path") else None),
        "input_fidelity": variables.get("input_fidelity"),
        "input_fidelity_required": bool(variables.get("input_fidelity_required")),
        "strong_identity": bool(strong_identity),
        "reference_fusion": bool(context.get("reference_fusion") or len(references) > 1),
        "required_reference_conditioning": any(
            item.get("provider_input_required") is True or item.get("strength") == "hard"
            for item in assets if item.get("provider_input_mode") == "reference_image"
        ),
        "moderation": plan.moderation if plan.moderation not in (None, "auto") else None,
    }
    # Preserve every explicitly requested typed option, including future hard
    # options that this adapter cannot faithfully translate. They must reject
    # admission, not disappear from a hint-only prompt.
    for key, value in dict(variables.get("provider_image_options") or {}).items():
        if key not in {"schema_version", "quality", "output_format", "size"}:
            hard["option_" + key] = value
    return PrimaryRequest(
        product="v3", owner_id=context["owner_id"], unit_id=context["unit_id"],
        prompt=str(variables.get("generation_prompt") or ""),
        parameters={"width": int(size[0]), "height": int(size[1]),
                    "image_options": {"schema_version": "1", "quality": plan.quality, "output_format": plan.output_format}},
        references=references, hard_requirements=hard,
    )


def _codex_transparency_supported(capabilities, profile):
    if not isinstance(capabilities, dict):
        return False
    profiles = capabilities.get("profiles")
    if not isinstance(profiles, list):
        return False
    selected = next((item for item in profiles
                     if isinstance(item, dict) and item.get("execution_profile_id") == profile
                     and item.get("execution_profile_revision") == "1"), None)
    if not selected:
        return False
    parameter_contract = selected.get("parameter_contract")
    if not isinstance(parameter_contract, dict):
        return False
    adapter = parameter_contract.get("codex_adapter")
    if not isinstance(adapter, dict):
        return False
    options = adapter.get("image_options_contract")
    if not isinstance(options, dict):
        return False
    transparency = options.get("transparent_background")
    if not isinstance(transparency, dict):
        return False
    values = transparency.get("values")
    return isinstance(values, list) and any(type(value) is bool and value is True for value in values)


def request_for(app_request, transport=None, capabilities=None):
    """New units opt in; durable legacy digests remain authoritative on replay.

    Unsupported rendering, fidelity, and identity hints use Codex native
    defaults as best-effort semantics. Masks, postprocessing, and unknown
    operations are not equivalent to prompt/reference hints and stay gated.
    """
    from render_bridge_primary.codex_adapter import CODEX_ADAPTER_VERSION, codex_cli_adaptation

    source = _source_request(app_request, native_defaults=True)
    plan = app_request.prompt_plan
    options = dict(plan.variables.get("provider_image_options") or {})
    background = plan.background if plan.background not in (None, "auto") else options.get("background")
    params = {**options, "background": background,
              "transparent_background": bool(plan.transparent_background or
                  options.get("transparent_background") is True or
                  options.get("background") == "transparent" or
                  plan.background == "transparent")}
    wire, _ = codex_cli_adaptation(params, len(source.references))
    wire["codex_adapter"] = CODEX_ADAPTER_VERSION
    requested_wire = dict(wire)
    requested_transparency = params["transparent_background"]
    profile = transport.settings.profile if transport is not None else "codex-image"
    if requested_transparency and not _codex_transparency_supported(capabilities, profile):
        image_options = dict(wire.get("image_options") or {})
        image_options.pop("transparent_background", None)
        if set(image_options) <= {"schema_version"}:
            wire.pop("image_options", None)
        else:
            wire["image_options"] = image_options
    prior_optional = {"quality", "size", "width", "height", "aspect_ratio", "output_format",
                      "output_compression", "seed", "input_fidelity", "background",
                      "transparent_background"}
    optional = prior_optional | {
        "moderation", "count", "provider_hint", "strong_identity",
        "input_fidelity_required", "required_reference_conditioning",
    }
    # These are guarantees/options, not separate image operations. Keep every
    # materialized reference and let Codex ImageGen apply its native defaults.
    native_default_requirements = {
        "strong_identity", "input_fidelity_required", "required_reference_conditioning",
    }
    requirements = {key: value for key, value in source.hard_requirements.items()
                    if key not in optional and key not in native_default_requirements
                    and not (key.startswith("option_") and key[7:] in optional)}
    asset_plan = app_request.asset_plan or plan.variables.get("asset_plan") or {}
    assets = asset_plan.get("assets", [])
    if ((asset_plan.get("requirements") or {}).get("needs_postprocess") or
            (asset_plan.get("provider_input_plan") or {}).get("requires_postprocess") or
            any(item.get("provider_input_mode") == "postprocess_only" or item.get("postprocess_steps")
                for item in assets)):
        requirements["deterministic_postprocess"] = True
    if any(item.get("provider_input_mode") == "mask_edit_source" for item in assets):
        requirements["mask_edit"] = True
    native = replace(source, parameters=wire, hard_requirements=requirements)
    if transport is not None:
        # Invalid legacy dimensions had no admissible legacy request. Still
        # allow exact recovery of a previously normalized native unit.
        try:
            legacy = _source_request(app_request)
        except ProviderRuntimeError as exc:
            if exc.detail.get("failure_code") != "bridge_invalid_frozen_dimensions":
                raise
            candidates = (native,)
        else:
            # Preserve exact recovery for pre-defaulting V3 journals. Historical
            # tasks keep their original capability contract and payload.
            prior_requirements = {
                key: value for key, value in source.hard_requirements.items()
                if key not in prior_optional and not (key.startswith("option_") and key[7:] in prior_optional)
            }
            prior_params = {**options, "background": plan.background,
                            "transparent_background": bool(plan.transparent_background or
                                options.get("transparent_background") is True or
                                plan.background == "transparent")}
            prior_wire = codex_cli_adaptation(prior_params, len(source.references))[0]
            prior_native = replace(source, parameters={**prior_wire, "codex_adapter": CODEX_ADAPTER_VERSION},
                                  hard_requirements=prior_requirements)
            supported_native = replace(source, parameters=requested_wire,
                                       hard_requirements=requirements)
            candidates = (legacy, prior_native, supported_native, native)
        matched = transport.match_existing_request(candidates)
        if matched is not None:
            return matched
    return native


def output_id(provenance):
    key = str(provenance.get("execution_key") or provenance.get("origin_key") or "")
    if not key:
        raise _error("bridge_checkpoint_identity_missing")
    return "v3_output_" + hashlib.sha256(key.encode()).hexdigest()[:20]


def _projection(result):
    projection = {"route": result.route, "state": result.state, "reason": result.reason,
                  "origin_key": result.origin_key, "execution_key": result.execution_key,
                  "task_id": result.task_id, "receipt_id": result.receipt_id}
    rejection = result.provenance.get("capability_rejection")
    if isinstance(rejection, dict):
        projection["capability_rejection"] = rejection
    return projection


def _cached_result(record, provenance):
    return ImageGenerationResult(provider=record.provider, model=record.model or "",
        outputs=[{"b64_json": base64.b64encode(Path(record.file_path).read_bytes()).decode(),
                  "mime_type": record.mime_type, "format": record.output_format,
                  "width": record.width, "height": record.height, PROVENANCE: provenance}])


def _durable_original(record, result, *, allow_pending_ack=False):
    allowed_states = {"acked"} if result.route == "bridge" else {"api_completed"}
    if allow_pending_ack and result.route == "bridge":
        allowed_states.add("artifacts_ready")
    if result.state not in allowed_states:
        return False
    metadata = record.metadata or {}
    if metadata.get("render_bridge_primary_checkpoint_complete") is not True:
        return False
    if metadata.get(PROVENANCE, {}).get("execution_key") != result.execution_key:
        return False
    try:
        content_hash = hashlib.sha256(Path(record.file_path).read_bytes()).hexdigest()
    except OSError:
        return False
    expected = metadata.get("content_sha256")
    if not expected or content_hash != expected:
        return False
    if result.route == "bridge":
        return content_hash == result.provenance.get("image", {}).get("sha256")
    return True


async def retire_checkpoint(app_request, record):
    """Best-effort duplicate cleanup, never a new execution or native deletion."""
    from render_bridge_primary import PrimarySettings, PrimaryTransport
    if not (record.metadata or {}).get(PROVENANCE):
        return False
    transport = PrimaryTransport(PrimarySettings.from_env(product="v3"))
    try:
        request = request_for(app_request, transport)
        # No resolve/network here: cleanup must not admit an unbound task.
        result = transport.cached_result(request)
        if result is None:
            return False
        return _durable_original(record, result, allow_pending_ack=True) and transport.request_retirement([request])
    finally:
        await transport.close()


async def generate(app_request, legacy_generate, output_store):
    from render_bridge_primary import PrimarySettings, PrimaryTransport, PrimaryError
    from render_bridge_primary.http import BridgeError

    settings = PrimarySettings.from_env(product="v3")
    # Preserve disabled legacy behavior, but never hide an existing durable unit.
    if not settings.enabled and not (settings.state_dir / "primary.sqlite3").exists():
        return await legacy_generate(app_request)
    transport = PrimaryTransport(settings)
    try:
        capabilities = None
        plan = app_request.prompt_plan
        options = dict(plan.variables.get("provider_image_options") or {})
        transparency_requested = bool(plan.transparent_background or
            options.get("transparent_background") is True or
            options.get("background") == "transparent" or plan.background == "transparent")
        if transparency_requested:
            try:
                capabilities = await transport.client.capabilities()
            except BridgeError:
                # Capability uncertainty means use the CLI's native default;
                # the normal resolve call remains authoritative for availability.
                capabilities = None
        request = request_for(app_request, transport, capabilities=capabilities)
        deadline = time.monotonic() + POLL_BUDGET_SECONDS
        context = dict(app_request.prompt_plan.variables.get(CONTEXT) or {})
        async with _gate_for(settings, app_request) as gate:
            gate.assert_current()
            owned_batch = transport.bindings_for("v3", request.owner_id, context["job_id"] + ":")
            use_legacy = not settings.enabled and not transport.has_unit(request) and not owned_batch
            result = None if use_legacy else await transport.resolve(request)
        if use_legacy:
            return await legacy_generate(app_request)
        while result.route == "bridge" and result.image is None and result.state in {
            "queued", "running", "bridge_submission_unknown", "execution_unknown", "awaiting_user",
        } and time.monotonic() < deadline:
            await asyncio.sleep(POLL_SECONDS)
            result = await transport.resolve(request)
        provenance = _projection(result)
        existing = output_store.get_output(output_id(provenance))
        if existing is not None:
            if (existing.metadata or {}).get(PROVENANCE, {}).get("execution_key") != result.execution_key:
                raise _error("bridge_checkpoint_binding_mismatch")
            if result.route == "bridge" and result.image is None:
                # Retirement is legal only after the owning native checkpoint
                # completed. Missing/deleted/corrupt originals never re-render.
                if not _durable_original(existing, result):
                    raise _error("bridge_checkpoint_original_unavailable", provenance)
            return _cached_result(existing, provenance)
        if result.route == "bridge" and result.image is None:
            if result.state in {
                "queued", "running", "bridge_submission_unknown", "execution_unknown", "awaiting_user",
            }:
                raise _error("bridge_wait_budget_exhausted", provenance)
            raise _error(result.state, provenance)
        if result.route == "api":
            async with _gate_for(settings, app_request) as gate:
                gate.assert_current()
                if not transport.claim_api(request):
                    raise _error(
                        "api_execution_unknown", provenance, provider="api",
                        message="An API fallback may already be in progress or accepted; check its outcome before retrying. automatic retry is disabled.",
                    )
            try:
                response = await legacy_generate(app_request)
            except asyncio.CancelledError as exc:
                raise _error(
                    "api_execution_unknown", provenance, provider="api",
                    message="The API fallback was interrupted; its execution outcome cannot be verified, so automatic retry is disabled.",
                    api_error_type=exc.__class__.__name__,
                ) from None
            except Exception as exc:
                raise _error(
                    "api_execution_unknown", provenance, provider="api",
                    message="The API fallback failed or was interrupted; its execution outcome cannot be verified, so automatic retry is disabled.",
                    api_error_type=exc.__class__.__name__,
                ) from None
            if len(response.outputs) != 1 or not response.outputs[0].get("b64_json"):
                raise _error(
                    "api_output_contract_invalid", provenance, provider="api",
                    message="The API fallback returned an unusable image response; its execution outcome must be checked before retrying.",
                )
            for output in response.outputs:
                output[PROVENANCE] = provenance
            return response
        if result.image is None:
            raise _error(result.state, provenance)
        image = result.image
        return ImageGenerationResult(provider="render_bridge", model=settings.profile,
            outputs=[{"b64_json": base64.b64encode(image.content).decode(), "mime_type": image.mime_type,
                      "format": image.mime_type.split("/")[-1], "width": image.width, "height": image.height,
                      "original_sha256": image.sha256, PROVENANCE: provenance}],
            raw_response_summary={PROVENANCE: provenance})
    except PrimaryError as exc:
        raise _error(exc.code) from None
    finally:
        await transport.close()


async def checkpoint(app_request, record):
    """ACK only after the normal V3 candidate output checkpoint exists."""
    from render_bridge_primary import PrimarySettings, PrimaryTransport

    provenance = (record.metadata or {}).get(PROVENANCE)
    if not provenance:
        return
    transport = PrimaryTransport(PrimarySettings.from_env(product="v3"))
    try:
        request = request_for(app_request, transport)
        if provenance["route"] == "api":
            transport.complete_api(request)
        else:
            # ACK failures do not discard durable pixels or force regeneration.
            try:
                await transport.acknowledge(request, record.output_id)
            except Exception:
                pass
    finally:
        await transport.close()


async def assert_bridge_checkpoint_current(app_request, output_store=None):
    """Reconcile the durable cancellation latch without submitting a new unit."""
    from render_bridge_primary import PrimarySettings, PrimaryTransport, PrimaryError

    settings = PrimarySettings.from_env(product="v3")
    transport = PrimaryTransport(settings)
    try:
        request = request_for(app_request, transport)
        async with _gate_for(settings, app_request) as gate:
            gate.assert_current()
        if not transport.has_unit(request):
            raise _error("bridge_checkpoint_binding_missing")
        result = await transport.resolve(request)
        if result.route != "bridge":
            raise _error("bridge_checkpoint_not_current", _projection(result))
        if result.image is None:
            native = output_store.get_output(output_id(_projection(result))) if output_store is not None else None
            if native is None or not _durable_original(native, result):
                raise _error("bridge_checkpoint_not_current", _projection(result))
    except PrimaryError as exc:
        raise _error(exc.code) from None
    finally:
        await transport.close()
