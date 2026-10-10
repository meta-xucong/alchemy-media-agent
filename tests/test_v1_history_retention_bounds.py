from app.storage.local import LocalMediaStore


def test_v1_history_legacy_import_and_delete_do_not_read_whole_file(tmp_path, monkeypatch):
    store = LocalMediaStore(tmp_path)
    output_dir = store.generated_root / "job_000001"
    output_dir.mkdir(parents=True)
    for index in range(30):
        output_id = f"out_{index:04d}"
        (output_dir / f"{output_id}.png").write_bytes(b"x")
        store.save_history_record(
            {
                "id": output_id,
                "job_id": "job_000001",
                "session_id": "session-a",
                "format": "png",
                "created_at": f"2026-10-09T00:{index:02d}:00+00:00",
            }
        )

    def forbidden_read_text(*_args, **_kwargs):
        raise AssertionError("V1 history must stream instead of read_text")

    monkeypatch.setattr(type(store.history_file), "read_text", forbidden_read_text)
    page = store.list_history_records(limit=4, session_id="session-a")
    assert len(page) == 4
    assert page[0]["id"] == "out_0029"
    assert store.delete_history_record("out_0029") == 1
    assert len(store.list_history_records(limit=100, session_id="session-a")) == 29


def test_v1_filesystem_recovery_retains_only_requested_top_window(tmp_path):
    store = LocalMediaStore(tmp_path)
    for index in range(40):
        job_id = f"job_{index:012d}"
        output_id = f"out_{index:012d}"
        path = store.output_path(job_id=job_id, output_id=output_id, output_format="png")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")

    recovered = store.list_generated_output_records(limit=5)

    assert len(recovered) == 5
    assert len({item["id"] for item in recovered}) == 5


def test_v1_history_uses_source_timestamp_fallback_and_duplicate_precedence(tmp_path):
    store = LocalMediaStore(tmp_path)
    records = [
        {
            "id": "out_fallback_0001",
            "job_id": "job_fallback_0001",
            "format": "png",
            "updated_at": "2026-03-01T00:00:00+00:00",
            "prompt": "updated timestamp fallback",
        },
        {
            "id": "out_duplicate_001",
            "job_id": "job_duplicate_001",
            "format": "png",
            "created_at": "2026-04-01T00:00:00+00:00",
            "updated_at": "2026-04-10T00:00:00+00:00",
            "prompt": "later updated timestamp, earlier source timestamp",
        },
        {
            "id": "out_duplicate_001",
            "job_id": "job_duplicate_001",
            "format": "png",
            "created_at": "2026-04-02T00:00:00+00:00",
            "updated_at": "2026-04-03T00:00:00+00:00",
            "prompt": "source timestamp winner",
        },
    ]
    for record in records:
        path = store.output_path(
            job_id=record["job_id"], output_id=record["id"], output_format="png"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
        store.save_history_record(record)

    history = store.list_history_records(limit=10)
    by_id = {item["id"]: item for item in history}

    assert history[0]["id"] == "out_duplicate_001"
    assert by_id["out_duplicate_001"]["prompt"] == "source timestamp winner"
    assert by_id["out_fallback_0001"]["updated_at"] == "2026-03-01T00:00:00+00:00"
