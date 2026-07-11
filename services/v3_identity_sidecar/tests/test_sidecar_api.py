import asyncio
import base64
from io import BytesIO
import json
from pathlib import Path

import httpx
from PIL import Image

from sidecar.config import SidecarSettings
from sidecar.contracts import BackendCapabilities, BackendGenerationResult, BackendImage
from sidecar.main import create_app


def _png_bytes(color=(82, 126, 148)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (96, 96), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _manifest(*, repair: bool = False, idempotency_key: str = "idem-1") -> dict:
    return {
        "contract_version": "doc98-v1",
        "operation": "identity_reference_generation",
        "backend_family": "photomaker",
        "model": "photomaker-v2",
        "prompt": "The same person in a clean editorial portrait.",
        "negative_constraints": ["identity drift", "plastic skin"],
        "count": 1,
        "size": "1024x1536",
        "quality": "high",
        "output_format": "png",
        "idempotency_key": idempotency_key,
        "trace_id": "trace-1",
        "input_fidelity": "high",
        "reference_manifest": [
            {
                "field": "reference_0",
                "asset_id": "portrait-root",
                "truth_layer": "portrait_identity_truth",
            }
        ],
        "requested_capabilities": {
            "identity_conditioning": True,
            "multi_reference": False,
            "identity_native_local_repair": repair,
        },
        "repair": {
            "active": repair,
            "canvas_field": "canvas" if repair else None,
            "mask_field": "mask" if repair else None,
        },
    }


def _settings(tmp_path: Path) -> SidecarSettings:
    return SidecarSettings(
        api_key="test-key",
        provider_family="photomaker",
        model_name="photomaker-v2",
        model_license_confirmed=True,
        workflow_path=tmp_path / "unused.json",
        max_file_bytes=1_000_000,
        max_total_upload_bytes=2_000_000,
        idempotency_ttl_seconds=60,
    )


class FakeBackend:
    def __init__(self) -> None:
        self.calls = 0

    async def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            configured=True,
            healthy=True,
            identity_conditioning=True,
            multi_reference=True,
            identity_native_local_repair=True,
            max_reference_images=3,
            provider="photomaker",
            model="photomaker-v2",
            backend="fake",
        )

    async def generate(self, manifest, references, *, canvas=None, mask=None):  # noqa: ANN001
        self.calls += 1
        assert all(path.is_file() for path in references)
        if manifest.repair.active:
            assert canvas is not None and canvas.is_file()
            assert mask is not None and mask.is_file()
        return BackendGenerationResult(
            provider="photomaker",
            model="photomaker-v2",
            images=[BackendImage(content=_png_bytes(), mime_type="image/png", width=96, height=96)],
            metadata={"fake_backend": True},
        )


class SlowFakeBackend(FakeBackend):
    async def generate(self, manifest, references, *, canvas=None, mask=None):  # noqa: ANN001
        await asyncio.sleep(0.05)
        return await super().generate(manifest, references, canvas=canvas, mask=mask)


class BrokenBackend(FakeBackend):
    async def generate(self, manifest, references, *, canvas=None, mask=None):  # noqa: ANN001
        raise RuntimeError("private backend failure details")


async def _request(app, method: str, path: str, **kwargs):  # noqa: ANN001
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://sidecar.test") as client:
        return await client.request(method, path, **kwargs)


def test_capabilities_require_auth_and_return_backend_truth(tmp_path) -> None:
    backend = FakeBackend()
    app = create_app(_settings(tmp_path), backend=backend)

    unauthorized = asyncio.run(_request(app, "GET", "/v1/capabilities"))
    response = asyncio.run(
        _request(app, "GET", "/v1/capabilities", headers={"Authorization": "Bearer test-key"})
    )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json()["capabilities"] == {
        "identity_conditioning": True,
        "multi_reference": True,
        "identity_native_local_repair": True,
    }


def test_generate_validates_multipart_and_returns_doc98_shape(tmp_path) -> None:
    backend = FakeBackend()
    app = create_app(_settings(tmp_path), backend=backend)
    files = [
        ("manifest", (None, json.dumps(_manifest()), "application/json")),
        ("reference_0", ("portrait.png", _png_bytes(), "image/png")),
    ]

    response = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/identity/generate",
            headers={"Authorization": "Bearer test-key"},
            files=files,
        )
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["provider"] == "photomaker"
    assert payload["model"] == "photomaker-v2"
    assert base64.b64decode(payload["outputs"][0]["b64_json"]) == _png_bytes()
    assert payload["metadata"]["reference_count"] == 1
    assert backend.calls == 1


def test_idempotent_duplicate_request_reuses_result(tmp_path) -> None:
    backend = FakeBackend()
    app = create_app(_settings(tmp_path), backend=backend)

    def call():
        return asyncio.run(
            _request(
                app,
                "POST",
                "/v1/identity/generate",
                headers={"Authorization": "Bearer test-key"},
                files=[
                    ("manifest", (None, json.dumps(_manifest()), "application/json")),
                    ("reference_0", ("portrait.png", _png_bytes(), "image/png")),
                ],
            )
        )

    first = call()
    second = call()

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert backend.calls == 1


def test_concurrent_idempotent_requests_share_one_gpu_operation(tmp_path) -> None:
    backend = SlowFakeBackend()
    app = create_app(_settings(tmp_path), backend=backend)

    async def run_pair():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://sidecar.test",
        ) as client:
            async def call():
                return await client.post(
                    "/v1/identity/generate",
                    headers={"Authorization": "Bearer test-key"},
                    files=[
                        ("manifest", (None, json.dumps(_manifest(idempotency_key="same-concurrent")), "application/json")),
                        ("reference_0", ("portrait.png", _png_bytes(), "image/png")),
                    ],
                )

            return await asyncio.gather(call(), call())

    first, second = asyncio.run(run_pair())

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert backend.calls == 1


def test_active_repair_requires_and_forwards_canvas_and_mask(tmp_path) -> None:
    backend = FakeBackend()
    app = create_app(_settings(tmp_path), backend=backend)
    headers = {"Authorization": "Bearer test-key"}
    incomplete = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/identity/generate",
            headers=headers,
            files=[
                ("manifest", (None, json.dumps(_manifest(repair=True)), "application/json")),
                ("reference_0", ("portrait.png", _png_bytes(), "image/png")),
            ],
        )
    )
    complete = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/identity/generate",
            headers=headers,
            files=[
                ("manifest", (None, json.dumps(_manifest(repair=True)), "application/json")),
                ("reference_0", ("portrait.png", _png_bytes(), "image/png")),
                ("canvas", ("canvas.png", _png_bytes((120, 100, 90)), "image/png")),
                ("mask", ("mask.png", _png_bytes((255, 255, 255)), "image/png")),
            ],
        )
    )

    assert incomplete.status_code == 400
    assert complete.status_code == 200
    assert complete.json()["metadata"]["repair_active"] is True
    assert backend.calls == 1


def test_invalid_or_oversized_reference_is_rejected_before_backend(tmp_path) -> None:
    config = _settings(tmp_path)
    config.max_file_bytes = 128
    backend = FakeBackend()
    app = create_app(config, backend=backend)
    headers = {"Authorization": "Bearer test-key"}
    invalid = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/identity/generate",
            headers=headers,
            files=[
                ("manifest", (None, json.dumps(_manifest(idempotency_key="invalid")), "application/json")),
                ("reference_0", ("portrait.png", b"not-an-image", "image/png")),
            ],
        )
    )
    oversized = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/identity/generate",
            headers=headers,
            files=[
                ("manifest", (None, json.dumps(_manifest(idempotency_key="oversized")), "application/json")),
                ("reference_0", ("portrait.png", _png_bytes(), "image/png")),
            ],
        )
    )

    assert invalid.status_code == 400
    assert oversized.status_code == 413
    assert backend.calls == 0


def test_duplicate_multipart_fields_and_oversized_body_are_rejected_early(tmp_path) -> None:
    config = _settings(tmp_path)
    backend = FakeBackend()
    app = create_app(config, backend=backend)
    headers = {"Authorization": "Bearer test-key"}
    duplicate = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/identity/generate",
            headers=headers,
            files=[
                ("manifest", (None, json.dumps(_manifest(idempotency_key="duplicate")), "application/json")),
                ("reference_0", ("first.png", _png_bytes(), "image/png")),
                ("reference_0", ("second.png", _png_bytes(), "image/png")),
            ],
        )
    )
    config.max_total_upload_bytes = 64
    config.max_prompt_chars = 1000
    oversized_body = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/identity/generate",
            headers=headers,
            files=[
                ("manifest", (None, json.dumps(_manifest(idempotency_key="body-limit")), "application/json")),
                ("reference_0", ("huge.png", b"x" * 700_000, "image/png")),
            ],
        )
    )

    assert duplicate.status_code == 400
    assert "unique" in duplicate.text
    assert oversized_body.status_code == 413
    assert backend.calls == 0


def test_manifest_requires_portrait_identity_truth(tmp_path) -> None:
    backend = FakeBackend()
    app = create_app(_settings(tmp_path), backend=backend)
    manifest = _manifest(idempotency_key="bad-truth")
    manifest["reference_manifest"][0]["truth_layer"] = "style_context_truth"

    response = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/identity/generate",
            headers={"Authorization": "Bearer test-key"},
            files=[
                ("manifest", (None, json.dumps(manifest), "application/json")),
                ("reference_0", ("portrait.png", _png_bytes(), "image/png")),
            ],
        )
    )

    assert response.status_code == 400
    assert backend.calls == 0


def test_unexpected_backend_error_is_structured_and_redacted(tmp_path) -> None:
    app = create_app(_settings(tmp_path), backend=BrokenBackend())

    async def call():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://sidecar.test",
        ) as client:
            return await client.post(
                "/v1/identity/generate",
                headers={"Authorization": "Bearer test-key"},
                files=[
                    ("manifest", (None, json.dumps(_manifest(idempotency_key="broken")), "application/json")),
                    ("reference_0", ("portrait.png", _png_bytes(), "image/png")),
                ],
            )

    response = asyncio.run(call())

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == "identity_sidecar_internal_error"
    assert "private backend failure details" not in response.text
