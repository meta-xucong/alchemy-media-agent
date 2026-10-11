from __future__ import annotations

from app.schemas import ImageHistoryItem


def positive_owner(value):
    try:
        result = int(value or 0)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _job_prompt(job) -> str | None:
    if not job.prompt_plan:
        return None
    generation_prompt = job.prompt_plan.variables.get("generation_prompt") if job.prompt_plan.variables else None
    if generation_prompt:
        return str(generation_prompt)
    parts = [
        job.prompt_plan.main_subject,
        job.prompt_plan.scene,
        job.prompt_plan.style,
        job.prompt_plan.composition,
    ]
    return "，".join(part for part in parts if part)


def _job_asset_intents(job) -> list[dict]:
    if not job.asset_plan:
        return []
    return [
        {
            "asset_id": item.get("asset_id"),
            "role": item.get("role"),
            "role_label": item.get("role_label"),
            "priority": item.get("priority"),
            "preservation": item.get("preservation"),
            "strength": item.get("strength"),
        }
        for item in job.asset_plan.get("assets", [])
    ]


def _job_asset_vision_profiles(job) -> list[dict]:
    if not job.asset_plan:
        return []
    profiles = []
    for item in job.asset_plan.get("assets", []):
        profile = item.get("vision_profile")
        if profile:
            profiles.append(profile)
    return profiles


def _job_provider_input_plan(job) -> dict | None:
    if not job.asset_plan:
        return None
    value = job.asset_plan.get("provider_input_plan")
    return dict(value) if isinstance(value, dict) else None


def _job_work_intensity(job) -> str | None:
    if not job.prompt_plan or not job.prompt_plan.variables:
        return None
    value = job.prompt_plan.variables.get("work_intensity")
    return str(value) if value else None


def _job_work_intensity_label(job) -> str | None:
    if not job.prompt_plan or not job.prompt_plan.variables:
        return None
    value = job.prompt_plan.variables.get("work_intensity_label")
    return str(value) if value else None


def _job_requested_provider(job) -> str | None:
    value = job.raw_response_summary.get("requested_image_provider") if job.raw_response_summary else None
    return str(value) if value else None


def _job_requested_model(job) -> str | None:
    value = job.raw_response_summary.get("requested_image_model") if job.raw_response_summary else None
    return str(value) if value else None


def job_history_item(job, output, store) -> ImageHistoryItem:
    return ImageHistoryItem(
        id=output.id,
        job_id=job.id,
        session_id=job.session_id,
        url=output.url,
        thumbnail_url=store.thumbnail_url(output.id),
        preview_url=store.preview_url(output.id),
        format=output.format,
        width=output.width,
        height=output.height,
        provider=job.provider,
        model=job.model,
        requested_provider=_job_requested_provider(job),
        requested_model=_job_requested_model(job),
        provider_fallback=job.raw_response_summary.get("image_provider_fallback") if job.raw_response_summary else None,
        asset_mode=job.asset_mode,
        asset_intents=_job_asset_intents(job),
        asset_plan=job.asset_plan,
        asset_vision_profiles=_job_asset_vision_profiles(job),
        provider_input_plan=_job_provider_input_plan(job),
        visual_review=output.visual_review.model_dump() if output.visual_review else None,
        prompt_plan=job.prompt_plan.variables.get("advanced_prompt_plan") if job.prompt_plan and job.prompt_plan.variables else None,
        original_prompt=job.provenance.get("original_prompt") if job.provenance else None,
        final_prompt=_job_prompt(job),
        work_intensity=_job_work_intensity(job),
        work_intensity_label=_job_work_intensity_label(job),
        prompt=_job_prompt(job),
        size=job.prompt_plan.size if job.prompt_plan else None,
        version_parent_id=output.version_parent_id,
        veyra_user_id=positive_owner(output.metadata.get("veyra_user_id") if isinstance(output.metadata, dict) else None),
        favorite=False,
        created_at=job.created_at,
        updated_at=job.updated_at,
        source="repository",
    )
