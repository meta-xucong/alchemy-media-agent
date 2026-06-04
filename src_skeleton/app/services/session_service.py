from __future__ import annotations

from app.repositories import repository
from app.schemas import CreateSessionRequest, MessageRequest, MessageResponse, Session
from app.services.image_service import create_image_job
from app.services.utils import make_id, now_iso
from app.services.video_service import create_video_job


def create_session(request: CreateSessionRequest) -> Session:
    return repository.save_session(
        Session(
            id=make_id("ses"),
            project_id=request.project_id,
            title=request.title,
            orchestration_mode=request.orchestration_mode,
            created_at=now_iso(),
        )
    )


async def handle_message(session_id: str, request: MessageRequest) -> MessageResponse:
    target = _resolve_target(request)
    job_ids: list[str] = []
    if target == "image":
        job = await create_image_job(
            session_id=session_id,
            prompt=request.text,
            asset_ids=request.asset_ids,
            count=int(request.preferences.get("count", 1)),
            provider_preference=request.preferences.get("provider_preference"),
        )
        job_ids.append(job.id)
        assistant_text = "已创建图片生成任务。"
    elif target == "video":
        job = await create_video_job(
            session_id=session_id,
            task_type=request.preferences.get("task_type", "text_to_video"),
            prompt=request.text,
            asset_ids=request.asset_ids,
            provider_preference=request.preferences.get("provider_preference"),
        )
        job_ids.append(job.id)
        assistant_text = "已保存视频生成请求；视频能力仍处于实验性预留状态。"
    else:
        assistant_text = "我可以帮你创建生图任务、继续炼金或保存视频生成请求。"
    return MessageResponse(message_id=make_id("msg"), assistant_text=assistant_text, job_ids=job_ids)


def _resolve_target(request: MessageRequest) -> str:
    if request.target != "auto":
        return request.target
    if "视频" in request.text or "video" in request.text.lower():
        return "video"
    if any(token in request.text for token in ["生成", "图片", "海报", "主图", "封面"]):
        return "image"
    return "chat"
