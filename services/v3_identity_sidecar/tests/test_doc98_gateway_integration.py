import asyncio
import base64
from io import BytesIO
from pathlib import Path
import sys

import httpx
from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src_skeleton"))

from app.config import settings as v3_settings  # noqa: E402
from app.providers.identity_sidecar import IdentityNativeSidecarProvider  # noqa: E402
from app.schemas import ImageGenerationRequest, ImagePromptPlan  # noqa: E402
from sidecar.config import SidecarSettings  # noqa: E402
from sidecar.contracts import BackendCapabilities, BackendGenerationResult, BackendImage  # noqa: E402
from sidecar.main import create_app  # noqa: E402


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (96, 96), (92, 121, 139)).save(buffer, format="PNG")
    return buffer.getvalue()


class GatewayBackend:
    async def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            configured=True,
            healthy=True,
            identity_conditioning=True,
            multi_reference=True,
            identity_native_local_repair=False,
            max_reference_images=3,
            provider="photomaker",
            model="photomaker-v2",
            backend="fake-gpu",
        )

    async def generate(self, manifest, references, *, canvas=None, mask=None):  # noqa: ANN001
        assert manifest.contract_version == "doc98-v1"
        assert references[0].is_file()
        return BackendGenerationResult(
            provider="photomaker",
            model="photomaker-v2",
            images=[BackendImage(content=_png_bytes(), mime_type="image/png", width=96, height=96)],
        )


def test_doc98_provider_round_trips_the_doc99_gateway(tmp_path, monkeypatch) -> None:
    config = SidecarSettings(
        api_key="gateway-key",
        provider_family="photomaker",
        model_name="photomaker-v2",
        model_license_confirmed=True,
        identity_conditioning_confirmed=True,
        workflow_path=tmp_path / "unused.json",
    )
    gateway = create_app(config, backend=GatewayBackend())
    transport = httpx.ASGITransport(app=gateway)
    reference = tmp_path / "portrait.png"
    reference.write_bytes(_png_bytes())
    asset_plan = {
        "assets": [
            {
                "asset_id": "portrait-root",
                "role": "portrait_identity",
                "priority": 100,
                "provider_input_mode": "reference_image",
                "storage_path": str(reference),
                "mime_type": "image/png",
                "reference_truth_layer": "portrait_identity_truth",
                "truth_layers": ["portrait_identity_truth"],
            }
        ]
    }
    request = ImageGenerationRequest(
        prompt_plan=ImagePromptPlan(
            main_subject="same person portrait",
            negative_constraints=["identity drift"],
            size="1024x1536",
            variables={"generation_prompt": "The same person in a new editorial portrait.", "asset_plan": asset_plan},
        ),
        asset_ids=["portrait-root"],
        asset_mode="advanced",
        asset_plan=asset_plan,
        provider_preference="identity_native_sidecar",
        idempotency_key="gateway-roundtrip",
        trace_id="trace-gateway",
    )
    monkeypatch.setattr(v3_settings, "v3_identity_sidecar_enabled", True)
    monkeypatch.setattr(v3_settings, "v3_identity_sidecar_base_url", "http://gateway.test")
    monkeypatch.setattr(v3_settings, "v3_identity_sidecar_api_key", "gateway-key")
    monkeypatch.setattr(v3_settings, "v3_identity_sidecar_provider", "photomaker")
    monkeypatch.setattr(v3_settings, "v3_identity_sidecar_model", "photomaker-v2")
    monkeypatch.setattr(v3_settings, "v3_identity_sidecar_health_ttl_seconds", 0.0)

    provider = IdentityNativeSidecarProvider(transport=transport)
    result = asyncio.run(provider.generate(request))

    assert result.provider == "identity_native_sidecar:photomaker"
    assert base64.b64decode(result.outputs[0]["b64_json"]) == _png_bytes()
    assert result.outputs[0]["identity_native_provider"] is True
    assert result.raw_response_summary["contract_version"] == "doc98-v1"
