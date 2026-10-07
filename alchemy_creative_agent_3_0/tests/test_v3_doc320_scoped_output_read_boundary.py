from __future__ import annotations

import base64
import json
from io import BytesIO

from PIL import Image

import alchemy_creative_agent_3_0.app.product_api.outputs as outputs_module
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore


def _png_base64() -> str:
    image = Image.new("RGB", (32, 32), (120, 150, 180))
    output = BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def _save(store: V3GeneratedOutputStore, output_id: str, *, project_id: str) -> None:
    store.save_base64_output(
        job_id="job_doc320",
        candidate_id=output_id,
        asset_id=output_id,
        provider="test",
        model="test",
        output_id=output_id,
        encoded_image=_png_base64(),
        metadata={"project_id": project_id},
    )


def test_list_by_job_limit_is_optional_and_bounded(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    for index in range(3):
        _save(store, f"v3_output_{index:020x}", project_id="project_doc320")

    assert len(store.list_by_job("job_doc320", limit=2)) == 2
    assert len(store.list_by_job("job_doc320")) == 3


def test_scoped_locator_rebuilds_after_out_of_band_metadata_change(tmp_path) -> None:
    root = tmp_path / "outputs"
    store = V3GeneratedOutputStore(root)
    output_id = "v3_output_00000000000000000001"
    _save(store, output_id, project_id="project_old")

    assert [item.output_id for item in store.list_by_project("project_old")] == [output_id]

    record_path = root / output_id / "output.json"
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    payload["metadata"]["project_id"] = "project_new"
    record_path.write_text(json.dumps(payload), encoding="utf-8")

    assert store.list_by_project("project_old") == []
    assert [item.output_id for item in store.list_by_project("project_new")] == [output_id]


def test_project_and_declared_jobs_share_one_batch_catalog_lookup(tmp_path, monkeypatch) -> None:
    root = tmp_path / "outputs"
    store = V3GeneratedOutputStore(root)
    linked_id = "v3_output_00000000000000000011"
    legacy_id = "v3_output_00000000000000000012"
    unrelated_id = "v3_output_00000000000000000013"
    for output_id, project_id in (
        (linked_id, "project_batch"),
        (legacy_id, "project_batch"),
        (unrelated_id, "project_other"),
    ):
        _save(store, output_id, project_id=project_id)

    legacy_path = root / legacy_id / "output.json"
    legacy_payload = json.loads(legacy_path.read_text(encoding="utf-8"))
    legacy_payload["metadata"].pop("project_id", None)
    legacy_payload["job_id"] = "job_legacy_declared"
    legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    scans = 0
    original = outputs_module._iter_output_record_paths

    def counted_scan(storage_root):
        nonlocal scans
        scans += 1
        yield from original(storage_root)

    monkeypatch.setattr(outputs_module, "_iter_output_record_paths", counted_scan)
    records = store.list_by_project_and_jobs(
        "project_batch",
        ["job_legacy_declared", "job_empty_1", "job_empty_2"],
    )

    assert {item.output_id for item in records} == {linked_id, legacy_id}
    assert scans == 1


def test_oversized_project_job_batch_enumerates_directory_once(tmp_path, monkeypatch) -> None:
    root = tmp_path / "outputs"
    store = V3GeneratedOutputStore(root)
    for index in range(3):
        _save(store, f"v3_output_{index:020x}", project_id="project_large_batch")

    scans = 0
    original = outputs_module._iter_output_record_paths

    def counted_scan(storage_root):
        nonlocal scans
        scans += 1
        yield from original(storage_root)

    monkeypatch.setattr(outputs_module, "_iter_output_record_paths", counted_scan)
    monkeypatch.setattr(outputs_module, "_OUTPUT_SCOPED_INDEX_MAX_RECORDS", 2)

    records = store.list_by_project_and_jobs(
        "project_large_batch",
        ["job_doc320", "job_missing_1", "job_missing_2"],
    )

    assert len(records) == 3
    assert scans == 1


def test_batch_lookup_preserves_all_outputs_beyond_home_sentinel(tmp_path) -> None:
    root = tmp_path / "outputs"
    store = V3GeneratedOutputStore(root)
    project_id = "project_batch_4098"
    job_id = "job_batch_4098"
    expected_ids = []
    for index in range(4098):
        output_id = f"v3_output_{index:020x}"
        expected_ids.append(output_id)
        output_dir = root / output_id
        output_dir.mkdir(parents=True)
        (output_dir / "output.json").write_text(
            json.dumps({
                "output_id": output_id,
                "job_id": job_id,
                "candidate_id": f"candidate_{index}",
                "asset_id": f"asset_{index}",
                "provider": "test",
                "model": "test",
                "metadata": {"project_id": project_id},
                "created_at": f"2026-09-{(index % 28) + 1:02d}T00:00:00+00:00",
            }),
            encoding="utf-8",
        )

    assert len(store.list_by_project_and_jobs(project_id, [job_id], limit=4096)) == 4096
    assert len(store.list_by_project_and_jobs(project_id, [job_id], limit=4097)) == 4097
    complete = store.list_by_project_and_jobs(project_id, [job_id])
    assert len(complete) == 4098
    assert {record.output_id for record in complete} == set(expected_ids)


def test_output_closure_reuses_revision_aware_original_hash_validation(tmp_path, monkeypatch) -> None:
    from pathlib import Path

    from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService

    root = tmp_path / "outputs"
    store = V3GeneratedOutputStore(root)
    output_id = "v3_output_00000000000000000021"
    _save(store, output_id, project_id="project_closure_cache")
    record = store.get_output(output_id)
    assert record is not None
    expected = str(record.metadata["content_sha256"])
    original_path = root / output_id / "original.png"
    service = object.__new__(V3ProductApiService)
    service.output_store = store
    store._integrity_validation_cache.clear()  # noqa: SLF001

    read_count = 0
    original_read_bytes = Path.read_bytes

    def counted_read_bytes(path):
        nonlocal read_count
        if path == original_path:
            read_count += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", counted_read_bytes)
    closure = {"outputs": [{"output_id": output_id, "content_sha256": expected}]}

    assert service._output_store_closure_files_match(closure, [record])
    assert read_count == 1
    assert service._output_store_closure_files_match(closure, [record])
    assert read_count == 1

    original_path.write_bytes(b"changed file bytes")
    assert not service._output_store_closure_files_match(closure, [record])
    assert read_count == 2

