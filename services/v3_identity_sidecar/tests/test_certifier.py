import base64
from io import BytesIO
import json
from pathlib import Path

import httpx
from PIL import Image

from tools import certify


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (96, 128), (76, 114, 137)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_certifier_runs_the_fixed_five_view_matrix_and_writes_report(tmp_path, monkeypatch) -> None:
    reference = tmp_path / "reference.png"
    reference.write_bytes(_png_bytes())
    generation_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal generation_calls
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "provider": "photomaker",
                    "model": "photomaker-v2",
                    "capabilities": {"identity_conditioning": True, "multi_reference": True},
                    "limits": {"max_reference_images": 3},
                },
            )
        generation_calls += 1
        assert b"doc98-v1" in request.read()
        return httpx.Response(
            200,
            json={
                "provider": "photomaker",
                "model": "photomaker-v2",
                "outputs": [
                    {
                        "b64_json": base64.b64encode(_png_bytes()).decode("ascii"),
                        "mime_type": "image/png",
                        "format": "png",
                        "width": 96,
                        "height": 128,
                    }
                ],
            },
        )

    monkeypatch.setattr(
        certify,
        "_identity_metric",
        lambda output, references: {"status": "pass", "calibrated_score": 0.86},
    )
    output_dir = tmp_path / "certification"
    report = certify.run_certification(
        certify.CertificationConfig(
            endpoint="http://sidecar.test",
            api_key="test-key",
            references=[reference],
            output_dir=output_dir,
        ),
        transport=httpx.MockTransport(handler),
    )

    assert generation_calls == 5
    assert [case["role"] for case in report["cases"]] == [item[0] for item in certify.VIEW_MATRIX]
    assert report["summary"]["minimum_identity_score"] == 0.86
    assert report["summary"]["identity_gate_passed"] is True
    assert report["summary"]["manual_review_required"] is True
    assert report["summary"]["quality_claim_allowed"] is False
    assert all(Path(case["output_path"]).is_file() for case in report["cases"])
    saved = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert saved["schema_version"] == "doc99-certification-v1"
