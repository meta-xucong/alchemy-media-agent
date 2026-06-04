import asyncio

import pytest

from app.repositories import repository
from app.services.video_service import create_video_job


@pytest.fixture(autouse=True)
def reset_repository():
    repository.reset()
    yield
    repository.reset()


def test_video_job_preserves_request_when_provider_not_configured():
    job = asyncio.run(
        create_video_job(
            session_id="ses_test",
            task_type="image_to_video",
            prompt="让这张咖啡海报变成 6 秒镜头。",
            asset_ids=["asset_cover_image"],
        )
    )

    assert job.job_type == "video"
    assert job.status == "provider_not_configured"
    assert job.error is not None
    assert job.error.code == "provider_not_configured"
    assert job.video_request is not None
    assert job.video_request.asset_ids == ["asset_cover_image"]
    assert repository.video_requests[job.id]["prompt"] == "让这张咖啡海报变成 6 秒镜头。"
