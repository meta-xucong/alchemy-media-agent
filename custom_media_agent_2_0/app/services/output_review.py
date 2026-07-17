from __future__ import annotations

from app.repositories.memory import utc_now
from app.schemas import ImageJob, ImageOutput, ImageReviewDecision
from app.services.ids import new_id
from app.services.visual_review_agent import apply_visual_review_agent


def review_image_job(job: ImageJob) -> ImageJob:
    reviewed_outputs = [
        output.model_copy(update={"review": review_output(output, job)})
        for output in job.outputs
    ]
    return job.model_copy(update={"outputs": reviewed_outputs, "updated_at": utc_now()})


def review_output(output: ImageOutput, job: ImageJob) -> ImageReviewDecision:
    notes: list[str] = []
    risks: list[str] = []
    directives: list[str] = []
    score = 0.72
    decision = "needs_review"

    if job.status == "failed" or job.error:
        score = 0.2
        decision = "failed"
        notes.append("V2 image provider reported a failed job.")
        directives.append("Retry after provider configuration or prompt constraints are checked.")
    elif output.metadata.get("live"):
        score = 0.86
        decision = "pass"
        notes.append("Live provider output completed and is ready for human visual review.")
    elif output.metadata.get("mock"):
        score = 0.62
        decision = "needs_review"
        notes.append("Mock output is useful for workflow testing but not a final visual asset.")
        directives.append("Run with a live image provider before customer delivery.")

    if output.metadata.get("fallback_from"):
        score = min(score, 0.58)
        decision = "retry_recommended"
        risks.append("live_provider_fallback")
        directives.append("Retry live generation or inspect the V2 provider error.")

    if not job.prompt_plan.prompt.strip():
        score = min(score, 0.35)
        decision = "retry_recommended"
        risks.append("empty_prompt")
        directives.append("Regenerate after composing a non-empty prompt plan.")

    if "watermark" not in job.prompt_plan.negative_prompt.lower():
        risks.append("negative_prompt_missing_watermark_guard")
        notes.append("Negative prompt does not explicitly mention watermark avoidance.")
    user_variables = job.prompt_plan.user_variables or {}
    provider_input_plan = user_variables.get("provider_input_plan") if isinstance(user_variables.get("provider_input_plan"), dict) else {}
    if user_variables.get("template_lock_enabled"):
        notes.append("Template Lock was active; selected case should remain the highest-priority visual frame.")
    visual_grammar = user_variables.get("visual_grammar_contract") if isinstance(user_variables.get("visual_grammar_contract"), dict) else {}
    if visual_grammar:
        mode = visual_grammar.get("mode") or "visual_grammar_lock"
        strength = visual_grammar.get("lock_strength") or "unknown"
        notes.append(f"Visual Grammar Lock active: {mode} with {strength} strength.")
        if visual_grammar.get("source_layout_risk", {}).get("detected"):
            risks.append("uploaded_source_layout_must_not_override_visual_grammar")
            directives.append("Verify the output did not copy the uploaded source layout over the visual grammar anchor.")
        information_integrity = (
            visual_grammar.get("information_integrity")
            if isinstance(visual_grammar.get("information_integrity"), dict)
            else {}
        )
        if information_integrity.get("active"):
            notes.append("Information Integrity Lock active; business-critical poster/menu content should be preserved.")
            risks.append("information_dense_content_may_be_incomplete")
            if information_integrity.get("qr_intent"):
                directives.append(
                    "Verify source item imagery, names, key copy, prices, counts, purchase offers, delivery/add-on/gift rules, requested CTA/contact, and real source QR are retained or equivalently condensed."
                )
            else:
                directives.append(
                    "Verify source item imagery, names, key copy, prices, counts, purchase offers, delivery/add-on/gift rules, and requested CTA/contact are retained or equivalently condensed; flag invented QR codes or empty scan placeholders."
                )
    if provider_input_plan.get("requires_image_reference"):
        reference_count = int(provider_input_plan.get("reference_image_count") or 0)
        notes.append(f"Provider input image plan requires {reference_count} uploaded reference image(s).")
        if output.metadata.get("live"):
            # A transport success proves only that the provider accepted the
            # references.  Without a pixel-capable reviewer it cannot prove
            # that the generated image actually followed them.
            score = min(score, 0.78)
            decision = "needs_review"
            risks.append("reference_adherence_unverified")
            directives.append(
                "Verify visible reference adherence against the declared asset roles, placement targets, and preserve/replace intent before marking this result as passed."
            )
        output_input_count = len(output.metadata.get("input_images") or [])
        if output_input_count < reference_count:
            score = min(score, 0.55)
            decision = "retry_recommended"
            risks.append("provider_input_images_missing")
            directives.append("Retry with a provider path that sends required uploaded reference images.")
    placement_targets = provider_input_plan.get("placement_targets") if isinstance(provider_input_plan, dict) else []
    if isinstance(placement_targets, list) and placement_targets:
        notes.append(f"Asset fusion plan includes {len(placement_targets)} placement target(s).")
        for target in placement_targets[:4]:
            if not isinstance(target, dict):
                continue
            if target.get("fusion_mode") == "logo_product_surface":
                notes.append(f"Uploaded logo is expected on scene surface: {target.get('target_label') or target.get('target_surface')}.")
                if not output.metadata.get("input_images"):
                    score = min(score, 0.5)
                    decision = "retry_recommended"
                    risks.append("logo_surface_reference_missing")
                    directives.append("Retry with uploaded logo passed as a provider reference image for the target surface.")
    review_expectations = provider_input_plan.get("review_expectations") if isinstance(provider_input_plan, dict) else []
    if isinstance(review_expectations, list) and review_expectations:
        notes.append("Review expectations: " + ", ".join(str(item) for item in review_expectations[:5]) + ".")

    baseline = ImageReviewDecision(
        review_id=new_id("review"),
        output_id=output.output_id,
        decision=decision,  # type: ignore[arg-type]
        score=score,
        notes=notes,
        detected_risks=risks,
        revision_directives=_dedupe(directives),
        created_at=utc_now(),
    )
    return apply_visual_review_agent(output, job, baseline)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique
