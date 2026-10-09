from datetime import datetime, timezone
import gc
import weakref

from app.repositories.memory import InMemoryV2Repository
from app.schemas import FeedbackEvent, ImageJob, ImageOutput, ImagePromptPlan, ResourceProvider


def test_v2_repository_records_survive_reopen_and_feedback_is_atomic(tmp_path):
    db_path = tmp_path / "v2.sqlite3"
    first = InMemoryV2Repository(database_path=db_path)
    provider = ResourceProvider(
        provider_id="provider-durable",
        provider_type="http",
        source_uri="https://example.test",
        display_name="provider",
    )
    output = ImageOutput(
        output_id="output-durable",
        job_id="job-durable",
        url="/output",
        created_at=datetime.now(timezone.utc),
    )
    job = ImageJob(
        job_id="job-durable",
        status="completed",
        provider_id=provider.provider_id,
        model="image-model",
        prompt_plan=ImagePromptPlan(plan_id="plan", mode="smart_enhance", prompt="test"),
        outputs=[output],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    first.upsert_provider(provider)
    first.save_image_job(job)

    feedback = FeedbackEvent(
        feedback_id="feedback-durable",
        output_id=output.output_id,
        feedback_type="selected",
        created_at=datetime.now(timezone.utc),
    )
    first.save_feedback(feedback)

    reopened = InMemoryV2Repository(database_path=db_path)
    assert reopened.get_provider(provider.provider_id) == provider
    restored_job = reopened.get_image_job(job.job_id)
    assert restored_job is not None
    assert restored_job.outputs[0].selected_by_user is True
    assert reopened.get_output(output.output_id).selected_by_user is True
    assert reopened.feedback_events[feedback.feedback_id] == feedback


def test_v2_reset_does_not_require_loading_repository_rows(tmp_path):
    repo = InMemoryV2Repository(database_path=tmp_path / "v2.sqlite3")
    repo.upsert_provider(
        ResourceProvider(
            provider_id="provider-reset",
            provider_type="http",
            source_uri="https://example.test",
            display_name="provider",
        )
    )

    repo.reset()

    assert repo.list_providers() == []


def test_v2_repository_does_not_retain_decoded_records(tmp_path):
    repo = InMemoryV2Repository(database_path=tmp_path / "v2.sqlite3")
    provider = ResourceProvider(
        provider_id="provider-ephemeral",
        provider_type="http",
        source_uri="https://example.test",
        display_name="provider",
    )
    repo.upsert_provider(provider)
    restored = repo.get_provider(provider.provider_id)
    reference = weakref.ref(restored)

    del restored
    gc.collect()

    assert reference() is None
