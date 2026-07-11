import asyncio
from io import BytesIO
import json
from pathlib import Path

import httpx
from PIL import Image

from sidecar.backends.comfyui import ComfyUIIdentityBackend
from sidecar.config import SidecarSettings
from sidecar.contracts import IdentityGenerationManifest


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (128, 96), (71, 109, 132)).save(buffer, format="PNG")
    return buffer.getvalue()


def _workflow(path: Path, *, references: int = 2, repair: bool = False) -> Path:
    payload = {
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "${prompt}"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "${negative_prompt}"}},
        "3": {"class_type": "LoadImage", "inputs": {"image": "${reference_0}"}},
        "4": {
            "class_type": "KSampler",
            "inputs": {"seed": "${seed}", "width": "${width}", "height": "${height}"},
        },
    }
    if references > 1:
        payload["5"] = {"class_type": "LoadImage", "inputs": {"image": "${reference_1}"}}
    if repair:
        payload["6"] = {"class_type": "LoadImage", "inputs": {"image": "${canvas}"}}
        payload["7"] = {"class_type": "LoadImageMask", "inputs": {"image": "${mask}"}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _settings(tmp_path: Path, *, license_confirmed: bool = True) -> SidecarSettings:
    return SidecarSettings(
        provider_family="photomaker",
        model_name="photomaker-v2",
        model_license_confirmed=license_confirmed,
        identity_conditioning_confirmed=True,
        workflow_path=_workflow(tmp_path / "identity.json"),
        comfyui_base_url="http://comfy.test",
        capability_ttl_seconds=0,
        poll_interval_seconds=0.01,
        request_timeout_seconds=30,
        max_references=3,
    )


def _manifest() -> IdentityGenerationManifest:
    return IdentityGenerationManifest.model_validate(
        {
            "contract_version": "doc98-v1",
            "operation": "identity_reference_generation",
            "backend_family": "photomaker",
            "model": "photomaker-v2",
            "prompt": "The same person in a daylight portrait.",
            "negative_constraints": ["identity drift"],
            "count": 1,
            "size": "1024x1536",
            "quality": "high",
            "output_format": "png",
            "idempotency_key": "idem-comfy",
            "trace_id": "trace-comfy",
            "input_fidelity": "high",
            "reference_manifest": [
                {"field": "reference_0", "truth_layer": "portrait_identity_truth"},
                {"field": "reference_1", "truth_layer": "portrait_identity_truth"},
            ],
            "requested_capabilities": {
                "identity_conditioning": True,
                "multi_reference": True,
                "identity_native_local_repair": False,
            },
        }
    )


def test_capabilities_require_license_workflow_tokens_and_live_comfyui(tmp_path) -> None:
    config = _settings(tmp_path, license_confirmed=False)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/system_stats":
            return httpx.Response(200, json={"devices": [{"name": "gpu"}]})
        return httpx.Response(
            200,
            json={name: {} for name in ("CLIPTextEncode", "LoadImage", "KSampler")},
        )

    backend = ComfyUIIdentityBackend(config, transport=httpx.MockTransport(handler))
    blocked = asyncio.run(backend.capabilities())
    config.model_license_confirmed = True
    ready = asyncio.run(backend.capabilities())

    assert blocked.identity_conditioning is False
    assert "licenses" in str(blocked.reason).lower()
    assert ready.identity_conditioning is True
    assert ready.multi_reference is True
    assert ready.max_reference_images == 2
    assert len(requests) == 2


def test_comfyui_backend_uploads_renders_polls_and_downloads(tmp_path) -> None:
    config = _settings(tmp_path)
    reference_a = tmp_path / "a.png"
    reference_b = tmp_path / "b.png"
    reference_a.write_bytes(_png_bytes())
    reference_b.write_bytes(_png_bytes())
    uploads = 0
    queued_workflow = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal uploads, queued_workflow
        if request.method == "GET" and request.url.path == "/system_stats":
            return httpx.Response(200, json={"devices": [{"name": "gpu"}]})
        if request.method == "GET" and request.url.path == "/object_info":
            return httpx.Response(
                200,
                json={name: {} for name in ("CLIPTextEncode", "LoadImage", "KSampler")},
            )
        if request.method == "POST" and request.url.path == "/upload/image":
            uploads += 1
            return httpx.Response(200, json={"name": f"uploaded_{uploads}.png", "subfolder": "alchemy"})
        if request.method == "POST" and request.url.path == "/prompt":
            queued_workflow = json.loads(request.content)["prompt"]
            return httpx.Response(200, json={"prompt_id": "prompt-123"})
        if request.method == "GET" and request.url.path == "/history/prompt-123":
            return httpx.Response(
                200,
                json={
                    "prompt-123": {
                        "status": {"status_str": "success", "completed": True},
                        "outputs": {
                            "9": {
                                "images": [
                                    {"filename": "result.png", "subfolder": "", "type": "output"}
                                ]
                            }
                        },
                    }
                },
            )
        if request.method == "GET" and request.url.path == "/view":
            return httpx.Response(200, content=_png_bytes(), headers={"content-type": "image/png"})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    backend = ComfyUIIdentityBackend(config, transport=httpx.MockTransport(handler))
    result = asyncio.run(backend.generate(_manifest(), [reference_a, reference_b]))

    assert uploads == 2
    assert queued_workflow["1"]["inputs"]["text"] == "The same person in a daylight portrait."
    assert queued_workflow["3"]["inputs"]["image"] == "alchemy/uploaded_1.png"
    assert queued_workflow["5"]["inputs"]["image"] == "alchemy/uploaded_2.png"
    assert queued_workflow["4"]["inputs"]["width"] == 1024
    assert queued_workflow["4"]["inputs"]["height"] == 1536
    assert result.images[0].width == 128
    assert result.images[0].height == 96
    assert result.metadata["reference_count"] == 2
    assert len(result.metadata["workflow_sha256"]) == 64


def test_comfyui_capabilities_do_not_claim_identity_for_invalid_workflow(tmp_path) -> None:
    workflow = tmp_path / "invalid.json"
    workflow.write_text(json.dumps({"1": {"inputs": {"text": "${prompt}"}}}), encoding="utf-8")
    config = SidecarSettings(
        model_license_confirmed=True,
        identity_conditioning_confirmed=True,
        workflow_path=workflow,
        comfyui_base_url="http://comfy.test",
    )
    backend = ComfyUIIdentityBackend(config, transport=httpx.MockTransport(lambda request: httpx.Response(200)))

    capabilities = asyncio.run(backend.capabilities())

    assert capabilities.configured is False
    assert capabilities.identity_conditioning is False
    assert "reference_0" in str(capabilities.reason)


def test_comfyui_capabilities_fail_when_a_workflow_node_is_not_installed(tmp_path) -> None:
    config = _settings(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/system_stats":
            return httpx.Response(200, json={"devices": [{"name": "gpu"}]})
        return httpx.Response(200, json={"CLIPTextEncode": {}, "LoadImage": {}})

    backend = ComfyUIIdentityBackend(config, transport=httpx.MockTransport(handler))
    capabilities = asyncio.run(backend.capabilities())

    assert capabilities.healthy is False
    assert capabilities.identity_conditioning is False
    assert "KSampler" in str(capabilities.reason)


def test_local_repair_requires_a_separate_operator_confirmation(tmp_path) -> None:
    config = _settings(tmp_path)
    config.repair_workflow_path = _workflow(tmp_path / "repair.json", repair=True)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/system_stats":
            return httpx.Response(200, json={"devices": [{"name": "gpu"}]})
        return httpx.Response(
            200,
            json={name: {} for name in ("CLIPTextEncode", "LoadImage", "LoadImageMask", "KSampler")},
        )

    backend = ComfyUIIdentityBackend(config, transport=httpx.MockTransport(handler))
    unconfirmed = asyncio.run(backend.capabilities())
    config.identity_local_repair_confirmed = True
    confirmed = asyncio.run(backend.capabilities())

    assert unconfirmed.identity_conditioning is True
    assert unconfirmed.identity_native_local_repair is False
    assert confirmed.identity_native_local_repair is True
