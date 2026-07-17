"""Conservative V2 pixel-file and delivery-contract review.

The reviewer never claims semantic reference adherence from transport success.
It can verify local raster readability and deterministic-overlay receipts now;
vision/OCR implementations can be plugged into the same result contract later.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.schemas import ImageJob, ImageOutput, ImageReviewDecision


def apply_reference_delivery_review(
    output: ImageOutput,
    job: ImageJob,
    baseline: ImageReviewDecision,
) -> ImageReviewDecision:
    variables = job.prompt_plan.user_variables or {}
    contract = variables.get("reference_delivery") if isinstance(variables.get("reference_delivery"), dict) else {}
    if not contract:
        return baseline
    acceptance = contract.get("acceptance") if isinstance(contract.get("acceptance"), dict) else {}
    if not acceptance.get("requires_pixel_review"):
        return baseline

    notes = list(baseline.notes)
    risks = list(baseline.detected_risks)
    directives = list(baseline.revision_directives)
    score = min(float(baseline.score), 0.78)
    decision = baseline.decision
    file_check = _readable_image_file(output.metadata)
    if not file_check["readable"]:
        decision = "retry_recommended"
        score = min(score, 0.4)
        risks.append("reference_delivery_output_unreadable")
        directives.append("Regenerate because the local V2 output file is missing or unreadable.")
    else:
        notes.append(
            f"Reference delivery pixel-file check passed ({file_check['width']}x{file_check['height']})."
        )
        evidence_capture = contract.get("evidence_capture") if isinstance(contract.get("evidence_capture"), dict) else {}
        if acceptance.get("requires_source_text_evidence") and not acceptance.get("source_text_evidence_ready"):
            decision = "needs_review" if decision != "retry_recommended" else decision
            score = min(score, 0.55)
            capture_status = str(evidence_capture.get("status") or "not_captured")
            risks.append(
                "source_text_evidence_unavailable"
                if capture_status in {"unavailable", "failed"}
                else "source_text_evidence_missing"
            )
            directives.append(
                "Do not auto-deliver information-dense source content until V2 has captured source text evidence and verified its rendering."
            )
        overlay = output.metadata.get("deterministic_text_overlay") if isinstance(output.metadata, dict) else None
        required_field_ids = [str(item) for item in acceptance.get("required_field_ids", []) if str(item or "")]
        verified_ids = set(_overlay_verified_field_ids(overlay))
        missing_fields = [item for item in required_field_ids if item not in verified_ids]
        if missing_fields:
            # A pixel-capable OCR/vision plugin may later replace this
            # deterministic-overlay evidence.  Until then it is intentionally
            # conservative: a hard source fact cannot be auto-delivered.
            decision = "needs_review" if decision != "retry_recommended" else decision
            score = min(score, 0.68)
            risks.extend(["required_source_text_unverified", "reference_pixel_review_unavailable"])
            directives.append(
                "Verify source text and reference adherence with the V2 pixel reviewer, or render verified source copy through deterministic text overlay."
            )
        elif required_field_ids:
            notes.append("All required source-text fields have deterministic overlay verification receipts.")
            risks = [item for item in risks if item not in {"required_source_text_unverified", "reference_pixel_review_unavailable"}]

    return baseline.model_copy(
        update={
            "decision": decision,
            "score": score,
            "notes": _dedupe(notes),
            "detected_risks": _dedupe(risks),
            "revision_directives": _dedupe(directives),
            "reviewer": "reference-delivery-reviewer",
            "analysis_mode": "pixel_file_and_contract",
        }
    )


def _readable_image_file(metadata: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(metadata.get("storage_path") or ""))
    if not path.is_file():
        return {"readable": False, "width": None, "height": None}
    try:
        from PIL import Image

        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return {"readable": image.width > 0 and image.height > 0, "width": image.width, "height": image.height}
    except (OSError, ValueError):
        return {"readable": False, "width": None, "height": None}


def _overlay_verified_field_ids(overlay: Any) -> list[str]:
    if not isinstance(overlay, dict) or not overlay.get("applied"):
        return []
    return [str(item) for item in overlay.get("verified_field_ids", []) if str(item or "")]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
