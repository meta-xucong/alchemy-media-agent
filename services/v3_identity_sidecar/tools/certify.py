from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx


VIEW_MATRIX = (
    ("front_closeup", "Front-facing realistic head-and-shoulders portrait, neutral natural expression, direct eye contact."),
    ("left_three_quarter", "Left three-quarter realistic portrait, natural expression, editorial daylight."),
    ("right_profile", "Right profile realistic portrait, recognizable same person, natural lens perspective."),
    ("half_body", "Half-body realistic portrait, natural pose and expression, clean commercial photography."),
    ("environmental", "Environmental realistic portrait of the same person, wider camera distance, coherent natural light."),
)


@dataclass(frozen=True)
class CertificationConfig:
    endpoint: str
    api_key: str | None
    references: list[Path]
    output_dir: Path
    timeout_seconds: float = 600.0
    size: str = "1024x1536"
    identity_threshold: float = 0.82


def run_certification(
    config: CertificationConfig,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
    with httpx.Client(
        base_url=config.endpoint.rstrip("/"),
        headers=headers,
        timeout=config.timeout_seconds,
        transport=transport,
    ) as client:
        capability_response = client.get("/v1/capabilities")
        capability_response.raise_for_status()
        capabilities = capability_response.json()
        if not bool((capabilities.get("capabilities") or {}).get("identity_conditioning")):
            raise RuntimeError(f"Sidecar is not identity-ready: {capabilities.get('reason') or capabilities}")
        max_references = int((capabilities.get("limits") or {}).get("max_reference_images") or 1)
        references = [path.resolve() for path in config.references[:max_references] if path.is_file()]
        if not references:
            raise FileNotFoundError("No readable portrait reference was provided.")
        cases: list[dict[str, Any]] = []
        for role, prompt in VIEW_MATRIX:
            trace_id = f"cert-{role}-{uuid4().hex[:12]}"
            manifest = _manifest(capabilities, references, prompt, trace_id, config.size)
            files: list[tuple[str, tuple[Any, ...]]] = [
                ("manifest", (None, json.dumps(manifest, ensure_ascii=False), "application/json"))
            ]
            handles = []
            try:
                for index, path in enumerate(references):
                    handle = path.open("rb")
                    handles.append(handle)
                    files.append((f"reference_{index}", (path.name, handle, _mime_type(path))))
                response = client.post("/v1/identity/generate", files=files)
                response.raise_for_status()
            finally:
                for handle in handles:
                    handle.close()
            payload = response.json()
            output = (payload.get("outputs") or [None])[0]
            if not isinstance(output, dict) or not output.get("b64_json"):
                raise RuntimeError(f"Certification case {role} returned no image.")
            suffix = _suffix(output.get("format"), output.get("mime_type"))
            output_path = config.output_dir / f"{role}{suffix}"
            output_path.write_bytes(base64.b64decode(output["b64_json"], validate=True))
            metric = _identity_metric(output_path, references)
            score = metric.get("calibrated_score")
            cases.append(
                {
                    "role": role,
                    "prompt": prompt,
                    "output_path": str(output_path),
                    "provider": payload.get("provider"),
                    "model": payload.get("model"),
                    "width": output.get("width"),
                    "height": output.get("height"),
                    "identity_metric": metric,
                    "identity_pass": isinstance(score, (int, float)) and score >= config.identity_threshold,
                }
            )

    scores = [case["identity_metric"].get("calibrated_score") for case in cases]
    scores = [float(score) for score in scores if isinstance(score, (int, float))]
    objective_available = len(scores) == len(cases)
    report = {
        "schema_version": "doc99-certification-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": config.endpoint,
        "capabilities": capabilities,
        "reference_count": len(references),
        "identity_threshold": config.identity_threshold,
        "cases": cases,
        "summary": {
            "case_count": len(cases),
            "objective_metric_available": objective_available,
            "minimum_identity_score": min(scores) if objective_available else None,
            "mean_identity_score": sum(scores) / len(scores) if objective_available else None,
            "identity_gate_passed": objective_available and min(scores) >= config.identity_threshold,
            "manual_review_required": True,
            "quality_claim_allowed": False,
        },
    }
    report_path = config.output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _manifest(capabilities: dict[str, Any], references: list[Path], prompt: str, trace_id: str, size: str) -> dict[str, Any]:
    return {
        "contract_version": "doc98-v1",
        "operation": "identity_reference_generation",
        "backend_family": capabilities.get("provider") or "custom",
        "model": capabilities.get("model") or "identity-native",
        "prompt": prompt,
        "negative_constraints": [
            "identity drift",
            "generic replacement face",
            "plastic skin",
            "over-smoothed skin",
            "facial anatomy distortion",
        ],
        "count": 1,
        "size": size,
        "quality": "high",
        "output_format": "png",
        "idempotency_key": trace_id,
        "trace_id": trace_id,
        "input_fidelity": "high",
        "reference_manifest": [
            {
                "field": f"reference_{index}",
                "asset_id": f"cert-reference-{index}",
                "truth_layer": "portrait_identity_truth",
            }
            for index, _path in enumerate(references)
        ],
        "requested_capabilities": {
            "identity_conditioning": True,
            "multi_reference": len(references) > 1,
            "identity_native_local_repair": False,
        },
        "repair": {"active": False, "canvas_field": None, "mask_field": None},
    }


def _identity_metric(output: Path, references: list[Path]) -> dict[str, Any]:
    try:
        from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.identity_metric import (
            SFaceIdentityMetricProvider,
        )

        provider = SFaceIdentityMetricProvider()
        result = provider.evaluate(output, references)
        return result.model_dump(mode="json")
    except Exception as exc:
        return {"status": "unavailable", "reason_codes": ["identity_metric_unavailable"], "error": str(exc)[:180]}


def _mime_type(path: Path) -> str:
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(path.suffix.lower(), "image/png")


def _suffix(output_format: Any, mime_type: Any) -> str:
    value = f"{output_format or ''} {mime_type or ''}".lower()
    if "jpeg" in value or "jpg" in value:
        return ".jpg"
    if "webp" in value:
        return ".webp"
    return ".png"


def main() -> int:
    parser = argparse.ArgumentParser(description="Certify a Doc98 identity sidecar with a fixed five-view matrix.")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--api-key")
    parser.add_argument("--reference", action="append", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--size", default="1024x1536")
    parser.add_argument("--identity-threshold", type=float, default=0.82)
    args = parser.parse_args()
    report = run_certification(
        CertificationConfig(
            endpoint=args.endpoint,
            api_key=args.api_key,
            references=args.reference,
            output_dir=args.output_dir,
            timeout_seconds=args.timeout_seconds,
            size=args.size,
            identity_threshold=args.identity_threshold,
        )
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["identity_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
