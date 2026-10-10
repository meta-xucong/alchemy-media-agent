from datetime import datetime, timezone
import gc
import threading
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


def test_concurrent_v2_output_deletes_do_not_restore_each_others_reference(tmp_path):
    db_path = tmp_path / "v2.sqlite3"
    first = InMemoryV2Repository(database_path=db_path)
    created = datetime.now(timezone.utc)
    outputs = [
        ImageOutput(output_id="output-delete-a", job_id="job-delete-race", url="/a", created_at=created),
        ImageOutput(output_id="output-delete-b", job_id="job-delete-race", url="/b", created_at=created),
    ]
    first.save_image_job(ImageJob(
        job_id="job-delete-race",
        status="completed",
        provider_id="provider",
        model="model",
        prompt_plan=ImagePromptPlan(plan_id="plan", mode="smart_enhance", prompt="test"),
        outputs=outputs,
        created_at=created,
        updated_at=created,
    ))
    repositories = [InMemoryV2Repository(database_path=db_path) for _ in outputs]
    barrier = threading.Barrier(2)
    errors = []

    def delete(repo, output_id):
        try:
            barrier.wait(timeout=2)
            repo.delete_output(output_id)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=delete, args=(repo, output.output_id)) for repo, output in zip(repositories, outputs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)
        assert not thread.is_alive()

    assert errors == []
    assert InMemoryV2Repository(database_path=db_path).get_image_job("job-delete-race").outputs == []
