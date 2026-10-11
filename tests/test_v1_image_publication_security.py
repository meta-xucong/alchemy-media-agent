"""Offline publication/privacy regressions; all records and images are synthetic."""
from __future__ import annotations

import asyncio
import base64
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from threading import Event, Thread
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException
from PIL import Image
from starlette.requests import Request

from app import main
from app.repositories import history_index as index, repository
from app.repositories.output_publication import reserve_output
from app.schemas import GenerationJob, GenerationOutput, ImageGenerationRequest, ImagePromptPlan, JobStatus, Session
from app.services import image_service
from app.storage import media_store


OWNER, OTHER = 41, 77
OUTPUT = "out_123456789abc"
JOB = "job_123456789abc"
SESSION = "publication-session"


def request():
    return Request({"type": "http", "method": "GET", "scheme": "http", "path": "/", "headers": [],
                    "server": ("testserver", 80), "client": ("testclient", 123), "query_string": b"", "app": main.app})


def png():
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "red").save(buffer, "PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def generation_job(*, outputs=None, lab=False):
    return GenerationJob(id=JOB, session_id=SESSION, job_type="image", status="generating",
                         trace_id="synthetic", created_at="2026-01-01T00:00:00Z",
                         updated_at="2026-01-01T00:00:00Z", outputs=outputs or [],
                         idempotency_key="lab:synthetic" if lab else None)


def output(*, owner=OWNER, job_id=JOB):
    return GenerationOutput(id=OUTPUT, job_id=job_id, url=f"/v1/outputs/{OUTPUT}/download",
                            metadata={"veyra_user_id": owner})


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    monkeypatch.setattr(main.settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main.settings, "media_acceleration_enabled", False)
    async def context(_request, authorization=""):
        return {"authenticated": True, "user_id": int(authorization or OWNER), "is_admin": False}
    monkeypatch.setattr(main, "_veyra_history_context", context)
    repository.save_session(Session(id=SESSION, project_id="synthetic", created_at="2026-01-01T00:00:00Z",
                                    veyra_user_id=OTHER))
    repository.save_job(generation_job())
    index.prepare_history_index(media_store)
    return tmp_path


def write_managed(*, owner=OWNER):
    return media_store.save_base64_output(job_id=JOB, output_id=OUTPUT, b64_json=png(),
                                         output_format="png", owner_id=owner)


def read_page(**kwargs):
    return index.read_history_page(media_store, surface=kwargs.pop("surface", "v1"), **kwargs)


def assert_hidden():
    for owner in (None, OWNER, OTHER):
        assert read_page(owner_id=owner) == ([], 0)
        assert read_page(owner_id=owner, session_id=SESSION) == ([], 0)
        assert read_page(surface="lab", owner_id=owner, include_mock=True) == ([], 0)
    assert read_page(all_owners=True) == ([], 0)


@pytest.mark.parametrize("auth_enabled", [True, False])
def test_reservation_is_committed_before_bytes_and_blocks_all_media(isolated, monkeypatch, auth_enabled):
    monkeypatch.setattr(main.settings, "veyra_auth_enabled", auth_enabled)
    path = media_store.output_path(job_id=JOB, output_id=OUTPUT, output_format="png")
    original = Path.write_bytes
    def intercepted(target, data):
        if target == path:
            assert not path.exists()
            assert media_store.output_publication_blocked(OUTPUT)
            assert_hidden()
            for handler in (main.download_output, main.thumbnail_output, main.preview_output):
                with pytest.raises(HTTPException) as error:
                    asyncio.run(handler(OUTPUT, request(), str(OTHER)))
                assert error.value.status_code == 404
        return original(target, data)
    monkeypatch.setattr(Path, "write_bytes", intercepted)
    write_managed()
    assert path.exists() and media_store.thumbnail_path(OUTPUT).exists() and media_store.preview_path(OUTPUT).exists()
    assert_hidden()
    with pytest.raises(HTTPException):
        main._resolve_output_file(OUTPUT)


@pytest.mark.parametrize("lab", [False, True])
def test_publication_commit_changes_only_correct_owner_and_surface(isolated, lab):
    pending = generation_job(lab=lab)
    repository.save_job(pending)
    write_managed()
    assert_hidden()
    pending.outputs = [output()]
    pending.status = JobStatus.ready
    repository.save_job(pending)
    assert not media_store.output_publication_blocked(OUTPUT)
    assert read_page(owner_id=OTHER) == ([], 0)
    if lab:
        assert read_page(all_owners=True) == ([], 0)
        media_store.save_history_record({"id": OUTPUT, "job_id": JOB, "format": "png", "veyra_user_id": OWNER,
                                        "source_app": index.LAB_PROJECT, "created_at": pending.created_at})
        assert read_page(surface="lab", owner_id=OWNER)[1] == 1
        assert read_page(surface="lab", owner_id=OTHER) == ([], 0)
    else:
        assert read_page(owner_id=OWNER)[1] == 1
        assert read_page(owner_id=OWNER, session_id=SESSION)[1] == 1
        assert read_page(all_owners=True)[1] == 1
    for handler in (main.download_output, main.thumbnail_output, main.preview_output):
        assert asyncio.run(handler(OUTPUT, request(), str(OWNER))).status_code == 200
        with pytest.raises(HTTPException) as error:
            asyncio.run(handler(OUTPUT, request(), str(OTHER)))
        assert error.value.status_code == 403


@pytest.mark.parametrize("phase", ["reserved", "bytes", "billing_cancel", "canonical_missing", "canonical_owner", "canonical_job"])
def test_interruption_and_mismatched_authority_stay_hidden(isolated, phase):
    if phase == "reserved":
        reserve_output(media_store.root / "repository.sqlite3", output_id=OUTPUT, job_id=JOB, owner_id=OWNER)
    else:
        write_managed()
    if phase == "billing_cancel":
        value = generation_job(outputs=[output()])
        image_service._discard_job_outputs(value)
        assert value.outputs == []
    elif phase == "canonical_missing":
        repository.save_job(generation_job(outputs=[output()]))
        del repository.outputs[OUTPUT]
    elif phase.startswith("canonical_"):
        repository.outputs[OUTPUT] = output(owner=OTHER if phase == "canonical_owner" else OWNER,
                                            job_id="job_wrong" if phase == "canonical_job" else JOB)
    assert media_store.output_publication_blocked(OUTPUT)
    assert_hidden()
    with pytest.raises(HTTPException):
        asyncio.run(main.download_output(OUTPUT, request(), str(OWNER)))


def test_reservation_retries_are_identity_bound_and_published_bytes_not_overwritten(isolated):
    write_managed()
    with pytest.raises(ValueError):
        write_managed()  # interrupted generations must retry with a fresh ID
    for values in ({"job_id": JOB, "owner_id": OTHER}, {"job_id": "job_other", "owner_id": OWNER}):
        with pytest.raises(ValueError):
            reserve_output(media_store.root / "repository.sqlite3", output_id=OUTPUT, **values)
    repository.save_job(generation_job(outputs=[output()]))
    with pytest.raises(ValueError):
        write_managed()
    del repository.outputs[OUTPUT]
    with pytest.raises(ValueError):
        write_managed()
    with pytest.raises(ValueError):
        reserve_output(media_store.root / "repository.sqlite3", output_id=OUTPUT, job_id=JOB, owner_id=OTHER)


def test_ownerless_generation_requires_publication_and_never_infers_session_owner(isolated):
    write_managed(owner=None)
    assert_hidden()
    repository.save_job(generation_job(outputs=[output(owner=None)]))
    assert read_page(owner_id=OWNER)[1] == read_page(owner_id=OTHER)[1] == 1
    assert read_page()[1] == 1


def test_legacy_orphan_and_published_ownerless_records_stay_public(isolated):
    del repository.jobs[JOB]
    path = media_store.output_path(job_id=JOB, output_id=OUTPUT, output_format="png")
    path.parent.mkdir(parents=True)
    path.write_bytes(base64.b64decode(png()))
    index.reconcile_history_files(media_store)
    assert read_page(owner_id=OWNER)[1] == 1
    assert asyncio.run(main.download_output(OUTPUT, request(), str(OTHER))).status_code == 200
    # Merely learning the Job exists makes the unmatched bare file unknown.
    repository.save_job(generation_job())
    assert_hidden()
    with pytest.raises(HTTPException):
        asyncio.run(main.download_output(OUTPUT, request(), str(OTHER)))
    # An actual legacy per-output publication, even ownerless, is still public.
    repository.save_job(generation_job(outputs=[output(owner=None)]))
    assert read_page(owner_id=OWNER)[1] == read_page(owner_id=OTHER)[1] == 1


def test_generation_boundary_passes_explicit_request_owner(isolated, monkeypatch):
    monkeypatch.setattr(image_service, "make_id", lambda _prefix: OUTPUT)
    monkeypatch.setattr(image_service, "review_image_output", lambda *_args: None)
    job = generation_job()
    values = image_service._store_outputs(job, [{"b64_json": png()}], request=ImageGenerationRequest(
        prompt_plan=ImagePromptPlan(main_subject="synthetic"), veyra_user_id=OWNER))
    assert_hidden()
    assert values[0].metadata["veyra_user_id"] == OWNER
    job.outputs = values
    repository.save_job(job)
    assert not media_store.output_publication_blocked(OUTPUT)
    assert read_page(owner_id=OTHER) == ([], 0)


def test_deleted_canonical_keeps_claim_retry_without_read_bypass(isolated, monkeypatch):
    write_managed()
    repository.save_job(generation_job(outputs=[output()]))
    original = repository.finish_output_delete_claim
    def interrupted(*_args, **_kwargs):
        raise RuntimeError("synthetic interruption after canonical deletion")
    monkeypatch.setattr(repository, "finish_output_delete_claim", interrupted)
    with pytest.raises(RuntimeError):
        asyncio.run(main.delete_image_history_item(OUTPUT, request(), str(OWNER)))
    assert repository.get_output(OUTPUT) is None
    assert repository.get_output_delete_claim(OUTPUT) is not None
    assert media_store.output_publication_blocked(OUTPUT)
    with pytest.raises(HTTPException):
        asyncio.run(main.download_output(OUTPUT, request(), str(OWNER)))
    with pytest.raises(HTTPException):
        asyncio.run(main.delete_image_history_item(OUTPUT, request(), str(OTHER)))
    monkeypatch.setattr(repository, "finish_output_delete_claim", original)
    assert asyncio.run(main.delete_image_history_item(OUTPUT, request(), str(OWNER)))["ok"] is True
    assert repository.get_output_delete_claim(OUTPUT) is None
    assert media_store.output_publication_blocked(OUTPUT)
    assert_hidden()


@pytest.mark.parametrize("published", [False, True])
@pytest.mark.parametrize("absolute", [False, True])
def test_anonymous_share_guard_precedes_cache_hit_and_local_source(isolated, published, absolute):
    write_managed()
    if published:
        repository.save_job(generation_job(outputs=[output()]))
    value = f"/v1/outputs/{OUTPUT}/download"
    if absolute:
        value = "http://testserver" + value
    cache = main._share_save_image_cache_path("http://testserver" + f"/v1/outputs/{OUTPUT}/download")
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"preexisting private cache must never be returned")
    with pytest.raises(HTTPException) as error:
        main.image_share_save_image(request(), value)
    assert error.value.status_code == 404
    image = main._load_share_preview_image(request(), value)
    assert image.size != (8, 8)  # existing safe public fallback, not synthetic bytes
    assert cache.read_bytes() == b"preexisting private cache must never be returned"


def test_warm_concurrent_reader_cannot_observe_paused_managed_writer(isolated, monkeypatch):
    paused, resume = Event(), Event()
    original = Path.write_bytes
    path = media_store.output_path(job_id=JOB, output_id=OUTPUT, output_format="png")
    errors = []
    def pause_after_bytes(target, data):
        result = original(target, data)
        if target == path:
            paused.set()
            assert resume.wait(5)
        return result
    monkeypatch.setattr(Path, "write_bytes", pause_after_bytes)
    def writer():
        try:
            write_managed()
        except BaseException as error:
            errors.append(error)
    thread = Thread(target=writer)
    thread.start()
    try:
        assert paused.wait(5)
        # Explicit inventory sees the bytes before the later file dirty marker.
        index.reconcile_history_files(media_store)
        assert_hidden()
        with pytest.raises(HTTPException):
            asyncio.run(main.download_output(OUTPUT, request(), str(OTHER)))
    finally:
        resume.set()
        thread.join(5)
    assert not thread.is_alive() and not errors


def test_initial_inventory_never_recovers_managed_pending_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.save_job(generation_job())
    write_managed()
    index.prepare_history_index(media_store)
    assert_hidden()
    assert media_store.list_generated_output_records() == []


@pytest.mark.parametrize("failure", ["reservation", "bytes"])
def test_failed_materialization_never_exposes_partial_output(isolated, monkeypatch, failure):
    from app.repositories import output_publication

    def fail(*_args, **_kwargs):
        raise OSError("synthetic storage interruption")
    if failure == "reservation":
        monkeypatch.setattr(output_publication, "reserve_output", fail)
    else:
        monkeypatch.setattr(Path, "write_bytes", fail)
    with pytest.raises(OSError):
        write_managed()
    assert not media_store.output_path(job_id=JOB, output_id=OUTPUT, output_format="png").exists()
    if failure == "bytes":
        assert media_store.output_publication_blocked(OUTPUT)
    assert_hidden()


def test_public_share_legacy_cache_is_rechecked_after_owner_authority_changes(isolated):
    path = media_store.output_path(job_id=JOB, output_id=OUTPUT, output_format="png")
    path.parent.mkdir(parents=True)
    path.write_bytes(base64.b64decode(png()))
    repository.save_job(generation_job(outputs=[output(owner=None)]))
    value = f"http://testserver/v1/outputs/{OUTPUT}/download"
    assert main._load_share_preview_image(request(), value).size == (8, 8)
    response = main.image_share_save_image(request(), value)
    assert response.status_code == 200
    assert Path(response.path).is_file()
    repository.save_job(generation_job(outputs=[output(owner=OWNER)]))
    with pytest.raises(HTTPException):
        main.image_share_save_image(request(), value)
    assert main._load_share_preview_image(request(), value).size != (8, 8)


def test_explicit_prepared_empty_store_accepts_first_native_manifest(isolated):
    write_managed()
    repository.save_job(generation_job(outputs=[output()]))
    image_service._persist_history_records(repository.get_job(JOB))
    assert read_page(owner_id=OWNER)[1] == 1
    assert read_page(owner_id=OTHER) == ([], 0)


def test_image_publication_rule_preserves_unmarked_legacy_video_lookup(isolated):
    path = media_store.generated_root / JOB / f"{OUTPUT}.mp4"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic legacy video")
    index.reconcile_history_files(media_store)
    assert read_page(all_owners=True) == ([], 0)
    assert not media_store.output_publication_blocked(OUTPUT)
    assert main._resolve_output_file(OUTPUT) == (path, "mp4")


@pytest.mark.parametrize("auth_enabled", [True, False])
@pytest.mark.parametrize("canonical", [True, False])
def test_dirty_removed_publication_cannot_authorize_from_stale_job_source(isolated, monkeypatch, auth_enabled, canonical):
    monkeypatch.setattr(main.settings, "veyra_auth_enabled", auth_enabled)
    value = generation_job(outputs=[output(owner=None)])
    if canonical:
        repository.save_job(value)
    else:
        repository.jobs[JOB] = value
    path = media_store.output_path(job_id=JOB, output_id=OUTPUT, output_format="png")
    path.parent.mkdir(parents=True)
    path.write_bytes(base64.b64decode(png()))
    index.reconcile_history_files(media_store)
    assert read_page(owner_id=OTHER)[1] == 1
    # Remove actual publication while leaving the indexed Job copy stale.
    repository.jobs[JOB] = generation_job()
    if canonical:
        del repository.outputs[OUTPUT]
    for handler in (main.download_output, main.thumbnail_output, main.preview_output):
        with pytest.raises(HTTPException) as error:
            asyncio.run(handler(OUTPUT, request(), str(OTHER)))
        assert error.value.status_code in (403, 404)
    with pytest.raises(HTTPException):
        main._resolve_output_file(OUTPUT)
    assert_hidden()


@pytest.mark.parametrize("wrapper", ["save-image", "poster"])
def test_share_wrapper_inputs_never_reuse_cached_media(isolated, wrapper):
    inner = f"http://testserver/v1/outputs/{OUTPUT}/download"
    value = "http://testserver/share/" + wrapper + "?" + urlencode({"image": inner})
    cache = main._share_save_image_cache_path(value)
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"nested private image")
    with pytest.raises(HTTPException):
        main.image_share_save_image(request(), value)
    assert main._load_share_preview_image(request(), value).size != (8, 8)
    assert cache.read_bytes() == b"nested private image"
    assert cache.parent.name == "publication_v2"


@pytest.mark.parametrize("response_status", [200, 302, 401, 403, 404, 503])
def test_v2_share_reads_only_anonymous_route_and_revalidates_cache(isolated, monkeypatch, response_status):
    import httpx

    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)

    value = "http://testserver/api/v2/outputs/out_synthetic/download"
    v2_root = isolated / "v2"
    path = v2_root / "outputs" / "job_synthetic" / "out_synthetic.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(base64.b64decode(png()))
    monkeypatch.setenv("V2_STORAGE_DIR", str(v2_root))
    cache = main._share_save_image_cache_path(value)
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"old V2 private cache must be revalidated")
    calls = []
    @contextmanager
    def authorized_route(client, method, url, **kwargs):
        calls.append((url, kwargs))
        assert method == "GET" and not client.follow_redirects
        assert not kwargs.get("headers") and not kwargs.get("cookies")
        yield httpx.Response(response_status, content=base64.b64decode(png()),
                             request=httpx.Request("GET", str(url)))
    monkeypatch.setattr(httpx.Client, "stream", authorized_route)
    result = main.image_share_save_image(request(), value)
    assert result.status_code == 200 and len(calls) == 1
    rendered = Image.open(BytesIO(result.body))
    assert (rendered.size == (8, 8)) is (response_status == 200)
    assert cache.read_bytes() == b"old V2 private cache must be revalidated"


@pytest.mark.parametrize("prefix", ["static", "mobile-static"])
@pytest.mark.parametrize("encoded", [False, True])
def test_share_static_paths_cannot_escape_public_root_or_reuse_unsafe_cache(isolated, monkeypatch, prefix, encoded):
    public_root = isolated / "public"
    public_root.mkdir()
    fallback = public_root / "showcase" / "city-poster.jpg"
    fallback.parent.mkdir()
    Image.new("RGB", (20, 20), "blue").save(fallback)
    monkeypatch.setattr(main, "STATIC_DIR", public_root)
    monkeypatch.setattr(main, "MOBILE_STATIC_DIR", public_root)
    private = isolated / "private.png"
    private.write_bytes(base64.b64decode(png()))
    traversal = "%2e%2e" if encoded else ".."
    value = f"http://testserver/{prefix}/{traversal}/private.png"
    cache = main._share_save_image_cache_path(value)
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"unsafe prior cache")
    with pytest.raises(HTTPException):
        main.image_share_save_image(request(), value)
    assert main._load_share_preview_image(request(), value).size == (20, 20)
    assert cache.read_bytes() == b"unsafe prior cache"


@pytest.mark.parametrize("output_id", ["*", "out_*", "?", "[o]*", "..", "../private", "out\\private", "out\x00private"])
def test_untrusted_output_ids_never_expand_legacy_lookup(isolated, output_id):
    write_managed()
    for handler in (main.download_output, main.thumbnail_output, main.preview_output):
        with pytest.raises(HTTPException) as error:
            asyncio.run(handler(output_id, request(), str(OTHER)))
        assert error.value.status_code == 404
    assert media_store.find_output_file(output_id) is None
    with pytest.raises(HTTPException):
        main._resolve_output_file(output_id)


def test_unknown_direct_id_revalidates_new_unindexed_file_parent_job(isolated):
    path = media_store.output_path(job_id=JOB, output_id=OUTPUT, output_format="png")
    path.parent.mkdir(parents=True)
    path.write_bytes(base64.b64decode(png()))  # intentionally no managed marker/inventory update
    for handler in (main.download_output, main.thumbnail_output, main.preview_output):
        with pytest.raises(HTTPException):
            asyncio.run(handler(OUTPUT, request(), str(OTHER)))
    value = f"http://testserver/v1/outputs/{OUTPUT}/download"
    cache = main._share_save_image_cache_path(value)
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"unknown unpublished cached image")
    with pytest.raises(HTTPException):
        main.image_share_save_image(request(), value)


def test_share_wildcard_and_storage_symlinks_cannot_select_private_bytes(isolated):
    write_managed()
    with pytest.raises(HTTPException):
        main.image_share_save_image(request(), "/v1/outputs/*/download")
    assert main._load_share_preview_image(request(), "/v1/outputs/*/download").size != (8, 8)
    outside = isolated / "outside.png"
    outside.write_bytes(base64.b64decode(png()))
    candidate = media_store.generated_root / JOB / "legacy-link.png"
    candidate.symlink_to(outside)
    assert media_store.find_output_file("legacy-link") is None


def test_protected_media_and_share_responses_do_not_allow_public_caching(isolated):
    write_managed()
    repository.save_job(generation_job(outputs=[output()]))
    for handler in (main.download_output, main.thumbnail_output, main.preview_output):
        response = asyncio.run(handler(OUTPUT, request(), str(OWNER)))
        assert response.headers["cache-control"] == "private, no-store"
    response = main.image_share_save_image(request(), "/static/showcase/city-poster.jpg")
    assert response.headers["cache-control"] == "private, no-store"
