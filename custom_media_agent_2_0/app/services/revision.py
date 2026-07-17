from __future__ import annotations

from app.repositories import repository
from app.schemas import CreateCreativeRunRequest, CreateRevisionRunRequest


class RevisionSourceError(KeyError):
    pass


def build_revision_request(output_id: str, body: CreateRevisionRunRequest) -> CreateCreativeRunRequest:
    output = repository.get_output(output_id)
    if not output:
        raise RevisionSourceError("output_not_found")
    job = repository.get_image_job(output.job_id)
    if not job:
        raise RevisionSourceError("job_not_found")

    review = output.review
    directives = list(review.revision_directives if review else [])
    feedback = body.feedback.strip()
    reason = "; ".join([*directives, feedback] or ["Improve the previous result while preserving the original client goal."])
    original_user_prompt = str((job.prompt_plan.user_variables or {}).get("user_prompt") or "").strip()
    if not original_user_prompt:
        original_user_prompt = job.prompt_plan.prompt
    revision_source = {
        "source_output_id": output.output_id,
        "source_job_id": job.job_id,
        "source_run_id": job.run_id,
        "source_prompt": job.prompt_plan.prompt,
        "review_decision": review.decision if review else None,
        "review_score": review.score if review else None,
        "revision_directives": directives,
        "feedback": feedback,
    }
    output_params = {
        **job.prompt_plan.provider_parameters,
        **body.output,
        "revision_source": revision_source,
    }
    if body.provider_hint:
        output_params["provider_hint"] = body.provider_hint
    return CreateCreativeRunRequest(
        user_prompt="\n".join(
            [
                "Create a revised image generation plan based on a previous Custom Media Agent 2.0 output.",
                f"Revision reason: {reason}",
                "Preserve the original client intent and selected-case strategy unless the review reason requires changing it.",
                f"Original client request: {original_user_prompt}",
            ]
        ),
        mode_hint="revision",
        output=output_params,
    )
