from __future__ import annotations

from app.schemas import ImagePromptPlan, ScoreReport


def score_image_output(plan: ImagePromptPlan, output_format: str, width: int | None, height: int | None) -> ScoreReport:
    notes: list[str] = []
    technical = 1.0
    if output_format not in {"png", "jpeg", "webp"}:
        technical = 0.4
        notes.append("Unsupported output format.")
    if width is None or height is None:
        technical = min(technical, 0.7)
        notes.append("Output dimensions were not reported by provider.")
    return ScoreReport(
        prompt_adherence=0.85 if plan.main_subject else 0.5,
        asset_consistency=0.85 if plan.variables.get("asset_ids") else 0.75,
        text_quality=0.75 if plan.text.get("required") else 0.9,
        composition=0.85,
        subject_integrity=0.85,
        safety=1.0,
        technical=technical,
        notes=notes,
    )
