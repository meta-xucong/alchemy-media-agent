from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.repositories import repository


def test_alchemy_no_longer_exposes_legacy_video_job_routes() -> None:
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "video_detachment"}).json()["id"]

    create_response = client.post(
        "/v1/video/jobs",
        json={
            "session_id": session_id,
            "task_type": "text_to_video",
            "prompt": "A short moving product scene.",
        },
    )
    status_response = client.get("/v1/video/jobs/job_legacy_video_123456")

    assert create_response.status_code == 404
    assert status_response.status_code == 404


def test_video_message_is_redirected_without_creating_an_image_job() -> None:
    client = TestClient(app)
    session_id = client.post("/v1/sessions", json={"project_id": "video_detachment"}).json()["id"]
    before_job_ids = set(repository.jobs)

    for payload in (
        {"text": "生成一个短视频", "target": "auto"},
        {"text": "anything", "target": "video"},
    ):
        response = client.post(f"/v1/sessions/{session_id}/messages", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["job_ids"] == []
        assert "aiself" in body["assistant_text"]
        assert "图片生成任务" not in body["assistant_text"]

    assert set(repository.jobs) == before_job_ids


def test_provider_catalog_and_openapi_do_not_publish_legacy_video_capability() -> None:
    client = TestClient(app)

    providers = client.get("/v1/providers")
    assert providers.status_code == 200
    provider_body = providers.json()
    assert "video" not in provider_body
    assert all(item["provider"] != "seedance" for item in provider_body["providers"])

    openapi_text = (Path(__file__).resolve().parents[1] / "specs" / "openapi.yaml").read_text(encoding="utf-8")
    assert "/v1/video/jobs" not in openapi_text
    assert "CreateVideoJobRequest" not in openapi_text
    assert "VideoProvider" not in openapi_text
