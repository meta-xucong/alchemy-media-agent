from __future__ import annotations

from typing import Any

from app.services.image_service import create_image_job as create_image_job_service

try:
    from agents import Agent, function_tool
except ModuleNotFoundError:
    Agent = None

    def function_tool(func):
        return func


@function_tool
async def create_image_job(prompt_plan: dict, asset_ids: list[str] | None = None, provider_preference: str | None = None) -> dict:
    job = await create_image_job_service(
        session_id=prompt_plan.get("session_id", "agent_session"),
        prompt=prompt_plan.get("main_subject") or prompt_plan.get("prompt") or "",
        asset_ids=asset_ids or [],
        count=prompt_plan.get("count", 1),
        size=prompt_plan.get("size", "1024x1024"),
        quality=prompt_plan.get("quality", "auto"),
        output_format=prompt_plan.get("output_format", "png"),
        background=prompt_plan.get("background"),
        moderation=prompt_plan.get("moderation"),
        output_compression=prompt_plan.get("output_compression"),
        provider_preference=provider_preference,
    )
    return {"job_id": job.id, "provider": job.provider, "model": job.model, "output_count": len(job.outputs), "status": job.status}


if Agent is not None:
    runtime_manager_agent: Any = Agent(
        name="RuntimeManagerAgent",
        instructions=(
            "你是定制化图片生成平台的运行时调度 Agent。"
            "判断用户意图，必要时调用 create_image_job。"
            "输出前不要编造生成结果。"
        ),
        tools=[create_image_job],
    )
else:
    runtime_manager_agent = None
