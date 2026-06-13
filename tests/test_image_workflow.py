import asyncio

import pytest

from app.providers.base import ProviderRuntimeError
from app.providers.mock_image import MockImageProvider
from app.repositories import repository
from app.schemas import CostEstimate, ImageGenerationResult, ReviseImageRequest
import app.services.image_service as image_service
from app.services.image_service import create_image_job, revise_image_job, run_submitted_image_job, submit_image_job
from app.storage import media_store


@pytest.fixture(autouse=True)
def isolate_repository_and_media_store(tmp_path, monkeypatch):
    original_default_provider = image_service.settings.default_image_provider
    original_default_model = image_service.settings.default_image_model
    original_mock_enabled = image_service.settings.mock_image_provider_enabled
    original_openai_key = image_service.settings.openai_api_key
    original_gemini_key = image_service.settings.gemini_image_api_key
    original_llm_enabled = image_service.settings.llm_prompt_planning_enabled
    monkeypatch.setattr(media_store, "root", tmp_path)
    monkeypatch.setitem(image_service.registry.image_providers, "mock_image", MockImageProvider())
    image_service.settings.default_image_provider = "mock_image"
    image_service.settings.default_image_model = "mock-image-v1"
    image_service.settings.mock_image_provider_enabled = True
    image_service.settings.openai_api_key = None
    image_service.settings.gemini_image_api_key = None
    image_service.settings.llm_prompt_planning_enabled = False
    repository.reset()
    yield
    repository.reset()
    image_service.settings.default_image_provider = original_default_provider
    image_service.settings.default_image_model = original_default_model
    image_service.settings.mock_image_provider_enabled = original_mock_enabled
    image_service.settings.openai_api_key = original_openai_key
    image_service.settings.gemini_image_api_key = original_gemini_key
    image_service.settings.llm_prompt_planning_enabled = original_llm_enabled


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
    assert job.prompt_plan.size is None
    assert job.cost_estimate is not None
    assert job.outputs[0].score is not None
    assert job.outputs[0].url.startswith("/v1/outputs/")


def test_create_image_job_rejects_blank_prompt():
    with pytest.raises(ValueError, match="提示词"):
        asyncio.run(create_image_job(session_id="ses_test", prompt="   "))


def test_create_image_job_preserves_manual_size_only():
    default_job = asyncio.run(
        create_image_job(
            session_id="ses_test",
            prompt="生成 1 张咖啡新品海报。",
        )
    )
    manual_job = asyncio.run(
        create_image_job(
            session_id="ses_test",
            prompt="生成 1 张咖啡新品海报。",
            size="1536x1024",
        )
    )

    assert default_job.prompt_plan is not None
    assert default_job.prompt_plan.size is None
    assert manual_job.prompt_plan is not None
    assert manual_job.prompt_plan.size == "1536x1024"


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


def test_submit_image_job_returns_generating_then_background_completes():
    prepared = asyncio.run(
        submit_image_job(
            session_id="ses_test",
            prompt="生成 1 张后台任务海报。",
            count=1,
        )
    )

    assert prepared.job.status == "generating"
    assert prepared.job.outputs == []
    assert prepared.request is not None
    assert prepared.job.raw_response_summary["async_submission"] is True
    assert prepared.job.prompt_plan.variables["prompt_planning_pending"] is True

    completed = asyncio.run(run_submitted_image_job(prepared.job.id, prepared.request, edit=prepared.edit))

    assert completed is not None
    assert completed.status == "ready"
    assert len(completed.outputs) == 1
    assert completed.prompt_plan.variables["prompt_planning_pending"] is False
    assert repository.get_job(prepared.job.id).status == "ready"
    assert media_store.list_history_records(limit=10)[0]["job_id"] == prepared.job.id


def test_submitted_image_job_background_failure_is_terminal(monkeypatch):
    async def fail_provider(job, request, provider, *, edit):
        raise RuntimeError("simulated disconnected worker")

    prepared = asyncio.run(
        submit_image_job(
            session_id="ses_test",
            prompt="生成 1 张会失败的后台任务海报。",
            count=1,
        )
    )
    assert prepared.request is not None
    monkeypatch.setattr(image_service, "_try_image_provider", fail_provider)

    completed = asyncio.run(run_submitted_image_job(prepared.job.id, prepared.request, edit=prepared.edit))

    assert completed is not None
    assert completed.status == "failed"
    assert completed.error is not None
    assert completed.error.code == "background_job_failed"
    assert repository.get_job(prepared.job.id).status == "failed"


def test_revise_image_job_creates_version_child():
    job = asyncio.run(create_image_job(session_id="ses_test", prompt="生成 1 张咖啡海报。"))
    source_output = job.outputs[0]
    image_service.settings.default_image_provider = "openai_gpt_image"

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
    assert revision.raw_response_summary["requested_image_provider"] == "mock_image"
    assert revision.raw_response_summary["source_output_id"] == source_output.id
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
    assert job.provider == "openai_gpt_image"
    assert "primary_provider" not in job.error.detail


def test_gemini_runtime_failure_records_openai_fallback(monkeypatch):
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    original_llm_enabled = image_service.settings.llm_prompt_planning_enabled
    image_service.settings.llm_prompt_planning_enabled = False

    class FailingGemini:
        name = "gemini_image"

        async def estimate_cost(self, request):
            return CostEstimate(provider=self.name, model="gemini-3-pro-image-preview")

        async def generate(self, request):
            raise ProviderRuntimeError(
                "Gemini image generation returned an error.",
                provider=self.name,
                detail={"status_code": 404, "body": "model not found"},
            )

    class SuccessfulOpenAI:
        name = "openai_gpt_image"

        async def estimate_cost(self, request):
            return CostEstimate(provider=self.name, model="gpt-image-2")

        async def generate(self, request):
            return ImageGenerationResult(
                provider=self.name,
                model="gpt-image-2",
                outputs=[{"b64_json": png_b64, "format": "png", "width": 1, "height": 1}],
            )

    async def fake_select_image(provider_name=None):
        if provider_name == "gemini_image":
            return FailingGemini()
        if provider_name == "openai_gpt_image":
            return SuccessfulOpenAI()
        raise AssertionError(provider_name)

    monkeypatch.setattr(image_service.registry, "select_image", fake_select_image)
    monkeypatch.setattr(image_service.registry, "alternate_image_name", lambda provider: "openai_gpt_image" if provider == "gemini_image" else None)

    try:
        job = asyncio.run(
            create_image_job(
                session_id="ses_test",
                prompt="生成 1 张极简茶饮海报。",
                provider_preference="gemini_image",
                work_intensity="swift",
            )
        )
    finally:
        image_service.settings.llm_prompt_planning_enabled = original_llm_enabled

    fallback = job.raw_response_summary["image_provider_fallback"]
    assert job.status == "ready"
    assert job.provider == "openai_gpt_image"
    assert job.model == "gpt-image-2"
    assert job.raw_response_summary["requested_image_provider"] == "gemini_image"
    assert fallback["from"] == "gemini_image"
    assert fallback["to"] == "openai_gpt_image"
    assert job.outputs[0].metadata["requested_provider"] == "gemini_image"
    assert job.outputs[0].metadata["actual_provider"] == "openai_gpt_image"
    assert job.outputs[0].metadata["provider_fallback"]["to"] == "openai_gpt_image"

    history = media_store.list_history_records(limit=10)
    assert history[0]["requested_provider"] == "gemini_image"
    assert history[0]["provider"] == "openai_gpt_image"
    assert history[0]["provider_fallback"]["from"] == "gemini_image"


def test_failed_image_fallback_preserves_primary_and_fallback_diagnostics(monkeypatch):
    class FailingProvider:
        def __init__(self, name: str, model: str, message: str):
            self.name = name
            self.model = model
            self.message = message

        async def estimate_cost(self, request):
            return CostEstimate(provider=self.name, model=self.model)

        async def generate(self, request):
            raise ProviderRuntimeError(
                self.message,
                provider=self.name,
                detail={"model": self.model, "reason": self.message},
            )

    async def fake_select_image(provider_name=None):
        if provider_name == "openai_gpt_image":
            return FailingProvider("openai_gpt_image", "gpt-image-2", "OpenAI reference route unavailable")
        if provider_name == "gemini_image":
            return FailingProvider("gemini_image", "gemini-3-pro-image-preview", "Gemini model not found")
        raise AssertionError(provider_name)

    monkeypatch.setattr(image_service.registry, "select_image", fake_select_image)
    monkeypatch.setattr(image_service.registry, "alternate_image_name", lambda provider: "gemini_image" if provider == "openai_gpt_image" else None)

    job = asyncio.run(
        create_image_job(
            session_id="ses_test",
            prompt="生成 1 张错误诊断测试图。",
            provider_preference="openai_gpt_image",
            work_intensity="swift",
        )
    )

    assert job.status == "failed"
    assert job.provider == "gemini_image"
    assert job.error is not None
    assert job.error.detail["primary_provider"] == "openai_gpt_image"
    assert job.error.detail["primary_error_message"] == "OpenAI reference route unavailable"
    assert job.error.detail["primary_error_detail"]["model"] == "gpt-image-2"
    assert job.error.detail["fallback_provider"] == "gemini_image"
    assert job.error.detail["fallback_error_message"] == "Gemini model not found"


def test_safety_rejected_prompt_does_not_call_provider():
    job = asyncio.run(create_image_job(session_id="ses_test", prompt="生成 1 张违法素材。"))

    assert job.status == "rejected"
    assert job.error is not None
    assert job.error.code == "safety_rejected"
    assert job.outputs == []
