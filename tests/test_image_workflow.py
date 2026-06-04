import asyncio

import pytest

from app.repositories import repository
from app.schemas import ReviseImageRequest
from app.services.image_service import create_image_job, revise_image_job
from app.storage import media_store


@pytest.fixture(autouse=True)
def isolate_repository_and_media_store(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    yield
    repository.reset()


def test_create_image_job_batch_outputs_and_persisted_metadata():
    job = asyncio.run(
        create_image_job(
            session_id="ses_test",
            prompt="生成 4 张竖版咖啡新品海报，日系清爽风格。",
            count=4,
        )
    )

    assert job.status == "ready"
    assert job.provider == "mock_image"
    assert len(job.outputs) == 4
    assert job.prompt_plan is not None
    assert job.prompt_plan.size == "1024x1536"
    assert job.cost_estimate is not None
    assert job.outputs[0].score is not None
    assert job.outputs[0].url.startswith("/v1/outputs/")


def test_image_job_idempotency_returns_existing_job():
    first = asyncio.run(
        create_image_job(
            session_id="ses_test",
            prompt="生成 1 张电商主图。",
            idempotency_key="fixed-key",
        )
    )
    second = asyncio.run(
        create_image_job(
            session_id="ses_test",
            prompt="生成 1 张电商主图。",
            idempotency_key="fixed-key",
        )
    )

    assert first.id == second.id
    assert len(repository.jobs) == 1


def test_revise_image_job_creates_version_child():
    job = asyncio.run(create_image_job(session_id="ses_test", prompt="生成 1 张咖啡海报。"))
    source_output = job.outputs[0]

    revision = asyncio.run(
        revise_image_job(
            job.id,
            ReviseImageRequest(output_id=source_output.id, feedback="保持构图，把背景改成冬天。"),
        )
    )

    assert revision is not None
    assert revision.status == "ready"
    assert revision.version_parent_id == source_output.id
    assert revision.outputs[0].version_parent_id == source_output.id
    assert "prompt_patch" in revision.raw_response_summary


def test_revise_image_job_rejects_output_from_another_job():
    first = asyncio.run(create_image_job(session_id="ses_test", prompt="生成 1 张咖啡海报。"))
    second = asyncio.run(create_image_job(session_id="ses_test", prompt="生成 1 张电商主图。"))

    revision = asyncio.run(
        revise_image_job(
            first.id,
            ReviseImageRequest(output_id=second.outputs[0].id, feedback="保持构图，把背景改成冬天。"),
        )
    )

    assert revision is None


def test_mock_provider_outputs_matching_file_formats():
    png = asyncio.run(create_image_job(session_id="ses_test", prompt="生成 PNG 图。", output_format="png"))
    jpeg = asyncio.run(create_image_job(session_id="ses_test", prompt="生成 JPEG 图。", output_format="jpeg"))
    webp = asyncio.run(create_image_job(session_id="ses_test", prompt="生成 WEBP 图。", output_format="webp"))

    from app.storage import media_store

    assert media_store.output_path(job_id=png.id, output_id=png.outputs[0].id, output_format="png").read_bytes().startswith(b"\x89PNG")
    assert media_store.output_path(job_id=jpeg.id, output_id=jpeg.outputs[0].id, output_format="jpeg").read_bytes().startswith(b"\xff\xd8")
    assert media_store.output_path(job_id=webp.id, output_id=webp.outputs[0].id, output_format="webp").read_bytes().startswith(b"RIFF")


def test_explicit_unconfigured_provider_is_not_silently_bypassed():
    job = asyncio.run(
        create_image_job(
            session_id="ses_test",
            prompt="生成 1 张咖啡海报。",
            provider_preference="openai_gpt_image",
        )
    )

    assert job.status == "provider_not_configured"
    assert job.error is not None
    assert job.error.code == "provider_not_configured"
    assert job.provider in {"openai_gpt_image", "gemini_image"}
    assert job.error.detail["primary_provider"] == "openai_gpt_image"


def test_safety_rejected_prompt_does_not_call_provider():
    job = asyncio.run(create_image_job(session_id="ses_test", prompt="生成 1 张违法素材。"))

    assert job.status == "rejected"
    assert job.error is not None
    assert job.error.code == "safety_rejected"
    assert job.outputs == []
