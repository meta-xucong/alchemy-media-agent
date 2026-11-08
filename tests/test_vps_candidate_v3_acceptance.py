from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts import vps_candidate_v3_smoke as smoke
from scripts import vps_candidate_v3_bridge_preflight as bridge_preflight


def test_candidate_workflow_defaults_failed_empty_api_unknown_exemption_off():
    workflow = yaml.safe_load(
        Path(".github/workflows/guarded-vps-candidate-v3-smoke.yml").read_text(encoding="utf-8")
    )
    triggers = workflow.get("on", workflow.get(True))
    inputs = triggers["workflow_dispatch"]["inputs"]

    assert inputs["allow_failed_empty_v2_api_unknowns"]["default"] is False
    assert "list-v2-api-unknown-job-ids" in Path(
        ".github/workflows/guarded-vps-candidate-v3-smoke.yml"
    ).read_text(encoding="utf-8")


def _delivery_item(**changes):
    item = {
        "project_id": "project-1",
        "job_id": "job-1",
        "output_id": "output-1",
        "preview_url": "/api/v3/creative-agent/outputs/output-1/preview",
        "download_url": "/api/v3/creative-agent/outputs/output-1/download",
        "delivery_state": "final_delivery",
        "review_mode": "vision_model",
        "review_status": "pass",
        "verification_state": "verified",
        "certification_state": "certified",
        "public_delivery_state": "ready",
    }
    item.update(changes)
    return item


def test_candidate_delivery_uses_only_the_single_verified_public_delivery_item():
    outputs = {
        "items": [_delivery_item()],
        "review_items": [_delivery_item(output_id="review-only", public_delivery_state="withheld_manual_confirmation")],
        "history_items": [_delivery_item(output_id="retry-superseded", delivery_state="superseded")],
    }

    assert smoke._final_delivery_item(outputs, "project-1", "job-1")["output_id"] == "output-1"


@pytest.mark.parametrize(
    "changes",
    [
        {"review_mode": "rule_only"},
        {"review_status": "manual_review"},
        {"verification_state": "unverified"},
        {"certification_state": "blocked"},
        {"public_delivery_state": "withheld_manual_confirmation"},
    ],
)
def test_candidate_delivery_rejects_unverified_or_withheld_outputs(changes):
    with pytest.raises(smoke.SafeApiError) as caught:
        smoke._final_delivery_item({"items": [_delivery_item(**changes)]}, "project-1", "job-1")

    assert caught.value.code == "candidate_v3_delivery_output_not_certified"


def test_candidate_delivery_rejects_review_only_delivery_state():
    with pytest.raises(smoke.SafeApiError) as caught:
        smoke._final_delivery_item(
            {"items": [_delivery_item(delivery_state="review_only")]}, "project-1", "job-1"
        )

    assert caught.value.code == "candidate_v3_delivery_output_binding_invalid"


def test_candidate_delivery_rejects_history_only_fallback_and_duplicate_outputs():
    with pytest.raises(smoke.SafeApiError) as history_only:
        smoke._final_delivery_item(
            {"items": [], "review_items": [_delivery_item()], "history_items": [_delivery_item()]},
            "project-1",
            "job-1",
        )
    assert history_only.value.code == "candidate_v3_delivery_output_count_invalid"

    with pytest.raises(smoke.SafeApiError) as duplicate:
        smoke._final_delivery_item(
            {"items": [_delivery_item(), _delivery_item(output_id="output-2")]},
            "project-1",
            "job-1",
        )
    assert duplicate.value.code == "candidate_v3_delivery_output_count_invalid"


def test_candidate_delivery_requires_project_job_and_canonical_web_urls():
    with pytest.raises(smoke.SafeApiError) as wrong_job:
        smoke._final_delivery_item({"items": [_delivery_item(job_id="other-job")]}, "project-1", "job-1")
    assert wrong_job.value.code == "candidate_v3_delivery_output_count_invalid"

    with pytest.raises(smoke.SafeApiError) as wrong_project:
        smoke._final_delivery_item({"items": [_delivery_item(project_id="other-project")]}, "project-1", "job-1")
    assert wrong_project.value.code == "candidate_v3_delivery_output_binding_invalid"

    with pytest.raises(smoke.SafeApiError) as wrong_url:
        smoke._final_delivery_item({"items": [_delivery_item(download_url="https://example.test/image.png")]}, "project-1", "job-1")
    assert wrong_url.value.code == "candidate_v3_delivery_output_binding_invalid"


def test_candidate_acceptance_requires_the_bridge_route():
    smoke._require_bridge_route("bridge")

    with pytest.raises(smoke.SafeApiError) as caught:
        smoke._require_bridge_route("api")

    assert caught.value.code == "candidate_v3_bridge_route_not_confirmed"


def test_candidate_acceptance_checks_preview_and_download_as_images():
    image = b"\x89PNG\r\n\x1a\n" + (b"x" * 1024)
    headers = {"content-type": "image/png; charset=binary"}
    smoke._validate_image_response(image, headers, kind="preview")
    smoke._validate_image_response(image, headers, kind="download")

    with pytest.raises(smoke.SafeApiError) as caught:
        smoke._validate_image_response(image, {"content-type": "application/octet-stream"}, kind="download")
    assert caught.value.code == "candidate_v3_download_invalid"


def _bridge_capabilities(*, admission=True, profiles=None):
    return {
        "admission": {"accepting_new_tasks": admission},
        "limits": {"max_input_bytes": 1024 * 1024, "max_input_image_pixels": 16 * 1024 * 1024},
        "profiles": profiles or [
            {
                "execution_profile_id": "codex-image",
                "execution_profile_revision": "1",
                "limits": {"max_dimension": 4096, "max_image_pixels": 16 * 1024 * 1024},
                "parameter_contract": {
                    "codex_adapter": {
                        "values": ["codex_cli_imagegen_v1"],
                        "image_options_contract": {
                            "quality": {"values": ["auto"]},
                            "output_format": {"values": ["png"]},
                            "references": {"max_count": 5},
                        },
                    }
                },
            }
        ],
    }


def test_candidate_preflight_requires_enabled_codex_profile_and_open_admission():
    settings = SimpleNamespace(
        enabled=True,
        profile="codex-image",
        base_url="https://bridge.example.test",
        token="hidden",
        workspace="primary",
    )
    bridge_preflight.validate_candidate_v3_bridge_state(settings, _bridge_capabilities())

    with pytest.raises(bridge_preflight.CandidateBridgePreflightError) as disabled:
        bridge_preflight.validate_candidate_v3_bridge_state(
            SimpleNamespace(**{**settings.__dict__, "enabled": False}), _bridge_capabilities()
        )
    assert disabled.value.code == "candidate_bridge_profile_not_enabled"

    with pytest.raises(bridge_preflight.CandidateBridgePreflightError) as closed:
        bridge_preflight.validate_candidate_v3_bridge_state(settings, _bridge_capabilities(admission=False))
    assert closed.value.code == "candidate_bridge_admission_not_open"


def test_candidate_preflight_requires_codex_adapter_advertisement():
    settings = SimpleNamespace(
        enabled=True,
        profile="codex-image",
        base_url="https://bridge.example.test",
        token="hidden",
        workspace="primary",
    )
    unsupported = _bridge_capabilities(
        profiles=[
            {
                "execution_profile_id": "codex-image",
                "execution_profile_revision": "1",
                "limits": {"max_dimension": 4096, "max_image_pixels": 16 * 1024 * 1024},
                "parameter_contract": {"codex_adapter": {"values": []}},
            }
        ]
    )

    with pytest.raises(bridge_preflight.CandidateBridgePreflightError) as caught:
        bridge_preflight.validate_candidate_v3_bridge_state(settings, unsupported)

    assert caught.value.code == "candidate_bridge_request_unsupported"
    assert caught.value.diagnostic == "code=adapter_not_advertised"


def test_candidate_preflight_does_not_require_api_only_codex_defaults():
    settings = SimpleNamespace(
        enabled=True,
        profile="codex-image",
        base_url="https://bridge.example.test",
        token="hidden",
        workspace="primary",
    )
    capabilities = _bridge_capabilities()
    capabilities["profiles"][0]["parameter_contract"]["codex_adapter"][
        "image_options_contract"
    ] = {"references": {"max_count": 5}}

    bridge_preflight.validate_candidate_v3_bridge_state(settings, capabilities)
