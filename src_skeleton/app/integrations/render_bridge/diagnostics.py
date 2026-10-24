"""Read-only evidence, deliberately separate from admission and execution gates.

No Bridge runtime imports, local CLI access, persistence, or credential discovery.
The only outbound request is the operator-requested existing capabilities GET.
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .client import BridgeError
from .options import image_options_projection


ProfileId = Literal["fake-image", "codex-image", "midjourney-manual"]
Code = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")]
PROFILE_IDS = {"fake-image", "codex-image", "midjourney-manual"}
MAX_REPORT_BYTES = 65536


class Projection(BaseModel):
    # Additive fields are ignored, never reflected. Unknown versions are rejected.
    model_config = ConfigDict(extra="ignore", strict=True)


class DoctorProducer(Projection):
    name: Literal["alchemy-render-bridge"]
    version: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9.+_-]+$")


class DoctorCheck(Projection):
    id: Code
    status: Literal["pass", "attention", "fail", "not_checked"]
    evidence: Literal["configuration", "local_probe", "operator_declaration", "not_checked"]
    code: Code
    next_step: str = Field(max_length=1000)


class DoctorReport(Projection):
    schema_version: Literal["1"]
    kind: Literal["render_bridge_doctor"]
    producer: DoctorProducer
    outcome: Literal["ready", "attention", "invalid"]
    profiles: list[ProfileId] = Field(max_length=3)
    checks: list[DoctorCheck] = Field(min_length=1, max_length=32)
    real_generation_verified: Literal[False]
    login_verified: Literal[False]


ParameterName = Annotated[str, Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")]


class ParameterContract(Projection):
    schema_version: Literal["1"]
    accepted_parameters: list[ParameterName] = Field(max_length=16)
    required_parameters: list[ParameterName] = Field(max_length=16)
    dimension_semantics: Literal["exact_output_match", "original_dimensions_recorded"]
    executor_control: Literal["deterministic_fixture", "text_instruction_only", "manual_user_selected"]
    seed_semantics: Literal["accepted_not_applied", "text_instruction_only", "manual_user_selected"]
    reference_semantics: Literal["hash_checked_not_conditioning", "local_image_input_unverified", "not_supported"]
    unsupported_parameters: list[ParameterName] = Field(max_length=16)


def capabilities_projection(value):
    """Accept older v1 capabilities without inventing missing parameter support."""
    if not isinstance(value, dict) or value.get("schema_version") != "1":
        raise BridgeError("unsupported_capabilities_version", retryable=False)
    profiles = value.get("profiles")
    if not isinstance(profiles, list) or len(profiles) > 32:
        raise BridgeError("invalid_bridge_capabilities", retryable=False)
    result = []
    seen = set()
    for profile in profiles:
        if not isinstance(profile, dict):
            raise BridgeError("invalid_bridge_capabilities", retryable=False)
        profile_id = profile.get("execution_profile_id")
        # New profile types do not silently become supported by this Alchemy.
        if not isinstance(profile_id, str) or profile_id not in PROFILE_IDS:
            continue
        if profile_id in seen or profile.get("operation") != "image.generate":
            raise BridgeError("invalid_bridge_capabilities", retryable=False)
        seen.add(profile_id)
        revision = profile.get("execution_profile_revision")
        if not isinstance(revision, str) or not revision.isascii() or not revision.isdigit() or len(revision) > 10:
            raise BridgeError("invalid_bridge_capabilities", retryable=False)
        raw_contract = profile.get("parameter_contract")
        contract, state = None, "unavailable"
        if raw_contract is not None:
            try:
                contract = ParameterContract.model_validate(raw_contract).model_dump()
                state = "available"
            except ValidationError:
                # Preserve usable v1 server admission data, not inferred support.
                state = "unsupported_or_invalid"
        image_contract = image_options_projection(profile.get("image_options_contract"))
        mode = profile.get("execution_mode")
        validation = profile.get("validation")
        result.append({
            "execution_profile_id": profile_id, "execution_profile_revision": revision,
            "execution_mode": mode if isinstance(mode, str) and mode in {"automatic", "manual"} else "unknown",
            "validation": validation if isinstance(validation, str) and validation in {"isolated_fake_only", "local_validation_pending"} else "unknown",
            "production_verified": False, "parameter_contract": contract,
            "parameter_contract_state": state,
            "image_options_contract": image_contract,
            "image_options_contract_state": ("available" if image_contract else
                "unsupported_or_invalid" if "image_options_contract" in profile else "unavailable"),
        })
    return result


def install_diagnostics_routes(app, *, config, actor, require_write, get_service):
    from .routes import HEADERS, PREFIX, STATIC

    router = APIRouter()
    base = {
        "schema_version": "1", "real_generation_verified": False,
        "native_real_profile_support": True,
        "native_real_profile_scope": "development_review_only",
        "local_cli": {"status": "not_checked", "reason": "browser_cannot_probe_remote_agent"},
    }

    @router.get(PREFIX + "/diagnostics")
    async def local_status(request: Request):
        await actor(request)
        return JSONResponse({**base, "source": "alchemy_server_configuration", "mode": config.mode,
            "configured_profiles": list(config.profiles), "native_enabled": config.native_enabled,
            "native_profiles": list(config.native_profiles), "formal_delivery": False,
            "configuration_error": config.config_error}, headers=HEADERS)

    @router.get(PREFIX + "/diagnostics/server")
    async def server_status(request: Request):
        await actor(request)
        result = {**base, "source": "configured_bridge_http", "connection": "unavailable",
                  "code": None, "profiles": []}
        try:
            svc = get_service()
            # Uses only the already-configured source endpoint and credential.
            # No CLI/node discovery, task creation, or profile mutations.
            value = await svc.client.capabilities()
            result.update(profiles=capabilities_projection(value), connection="ok")
        except BridgeError as exc:
            code = exc.code if exc.code in {
                "bridge_unreachable", "bridge_request_failed", "bridge_response_too_large",
                "invalid_bridge_response", "unsupported_capabilities_version", "invalid_bridge_capabilities",
            } else "bridge_request_failed"
            result.update(code=code, connection="incompatible" if code in {
                "invalid_bridge_response", "unsupported_capabilities_version", "invalid_bridge_capabilities",
            } else "unavailable")
        except HTTPException:
            result["code"] = "bridge_not_available"
        return JSONResponse(result, headers=HEADERS)

    @router.post(PREFIX + "/diagnostics/report")
    async def import_report(request: Request):
        await actor(request)
        require_write(request)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_REPORT_BYTES:
                raise HTTPException(413, detail={"code": "doctor_report_too_large"})
        try:
            report = DoctorReport.model_validate_json(body)
            if len(set(report.profiles)) != len(report.profiles) or len({c.id for c in report.checks}) != len(report.checks):
                raise ValueError()
        except (ValidationError, ValueError):
            raise HTTPException(422, detail={"code": "invalid_doctor_report"}) from None
        return JSONResponse({"schema_version": "1", "source": "user_imported_local_report",
            "verified_by_server": False, "authorization_effect": "none", "report": report.model_dump()}, headers=HEADERS)

    @router.get("/render-bridge-diagnostics", include_in_schema=False)
    async def page():
        return FileResponse(STATIC / "diagnostics.html", headers={**HEADERS, "Content-Security-Policy":
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"})

    @router.get("/render-bridge-diagnostics/assets/diagnostics.js", include_in_schema=False)
    async def script():
        return FileResponse(STATIC / "diagnostics.js", headers=HEADERS)

    app.include_router(router)
