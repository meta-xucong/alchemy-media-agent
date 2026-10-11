"""Synthetic read-plan/decoding contracts; never starts providers or app lifespan."""

from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

from app.schemas import ImageHistoryItem
import app.services.image_history as history


def _fixture(tmp_path, monkeypatch, count):
    path = tmp_path / "history.jsonl"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(history, "settings", SimpleNamespace(
        image_history_path=path, veyra_auth_enabled=True,
    ))
    monkeypatch.setattr(history, "list_favorite_ids", lambda **kwargs: {
        output_id for output_id in kwargs["output_ids"] if output_id.endswith("0")
    })
    history._ensure_history_index()
    item = ImageHistoryItem(
        output_id="fixture", job_id="fixture", provider_id="fixture", model="fixture",
        prompt="Synthetic fixture", url="/fixture",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    ).model_dump(mode="json")

    def rows():
        for index in range(count):
            owner = (None, 1, 2)[index % 3]
            output_id = f"out-{index:06d}"
            # Repeated timestamps and job IDs deliberately exercise tie order.
            job_id = f"job-{index // 6:06d}"
            payload = {**item, "output_id": output_id, "job_id": job_id,
                       "metadata": {} if owner is None else {"veyra_user_id": owner}}
            yield output_id, job_id, owner, index // 12, index // 12, json.dumps(payload)

    connection = history._history_connect()
    with connection:
        connection.executemany("INSERT INTO v2_image_history VALUES(?,?,?,?,?,?)", rows())
    connection.close()


@pytest.mark.parametrize("scope", ["all", "own_public", "own"])
def test_page_query_uses_ordered_index_without_global_sort(tmp_path, monkeypatch, scope):
    _fixture(tmp_path, monkeypatch, 120)
    statements = []
    connect = history._history_connect

    def traced_connect(**kwargs):
        connection = connect(**kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(history, "_history_connect", traced_connect)
    kwargs = {"include_all": True} if scope == "all" else {
        "veyra_user_id": 1, "include_legacy_public": scope == "own_public",
    }
    response = history.list_image_history(limit=24, **kwargs)
    assert len(response.items) == 24
    page_query = next(sql for sql in statements if sql.lstrip().startswith("SELECT payload"))
    connection = connect()
    try:
        plan = [row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + page_query)]
    finally:
        connection.close()
    assert not any("TEMP B-TREE" in step for step in plan), plan
    assert any("USING INDEX" in step for step in plan), plan
    if scope == "own_public":
        assert any("MERGE (UNION ALL)" in step for step in plan), plan


@pytest.mark.parametrize("scope", ["all", "own_public", "own", "missing"])
def test_page_preserves_baseline_scope_sort_ties_offsets_and_favorites(tmp_path, monkeypatch, scope):
    _fixture(tmp_path, monkeypatch, 121)
    kwargs = {"include_all": True} if scope == "all" else (
        {} if scope == "missing" else {
            "veyra_user_id": 1, "include_legacy_public": scope == "own_public",
        }
    )
    where, parameters = "", []
    if scope == "own_public":
        where, parameters = " WHERE (owner_id=? OR owner_id IS NULL)", [1]
    elif scope == "own":
        where, parameters = " WHERE owner_id=?", [1]
    connection = history._history_connect()
    try:
        # NOT INDEXED preserves the old global table-scan tie order. The old
        # owner OR planner uses the owner index and owner-first/public-second.
        table = "v2_image_history NOT INDEXED" if scope == "all" else "v2_image_history"
        expected = [json.loads(row[0]) for row in connection.execute(
            "SELECT payload FROM " + table + where + " ORDER BY created_epoch DESC, job_id DESC",
            parameters,
        )]
    finally:
        connection.close()
    if scope == "missing":
        expected = []
    for offset in (0, 1, 23, 24, 77, 120, 999):
        result = history.list_image_history(limit=24, offset=offset, **kwargs)
        assert result.total == len(expected)
        assert [item.output_id for item in result.items] == [
            item["output_id"] for item in expected[offset:offset + 24]
        ]
        for item in result.items:
            owner = item.metadata.get("veyra_user_id")
            assert item.favorite == item.output_id.endswith("0")
            assert item.can_delete == (scope == "all" or owner == 1)
            assert item.veyra_legacy_public == (owner is None)
            assert item.thumbnail_url.endswith(f"/{item.output_id}/thumbnail")


@pytest.mark.parametrize("count", [1000, 10000, 100000])
def test_page_decoding_is_independent_of_history_size(tmp_path, monkeypatch, count):
    _fixture(tmp_path, monkeypatch, count)
    original = ImageHistoryItem.model_validate_json
    decoded = []

    def validate(payload):
        decoded.append(1)
        return original(payload)

    monkeypatch.setattr(ImageHistoryItem, "model_validate_json", validate)
    for limit in (1, 24):
        for kwargs in ({"include_all": True}, {"veyra_user_id": 1}):
            decoded.clear()
            result = history.list_image_history(limit=limit, **kwargs)
            assert len(result.items) == len(decoded) == limit
        decoded.clear()
        assert history.list_image_history(limit=limit).items == []
        assert decoded == []


def test_count_and_page_share_one_snapshot(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch, 30)
    connect = history._history_connect
    read_count = history.read_history_count

    def read_then_delete(connection, **kwargs):
        value = read_count(connection, **kwargs)
        writer = connect()
        with writer:
            writer.execute("DELETE FROM v2_image_history")
        writer.close()
        return value

    monkeypatch.setattr(history, "read_history_count", read_then_delete)
    response = history.list_image_history(limit=24, include_all=True)
    assert response.total == 30
    assert len(response.items) == 24


def test_auth_disabled_retains_global_history_and_delete_contract(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch, 30)
    history.settings.veyra_auth_enabled = False
    result = history.list_image_history(limit=24)
    assert result.total == 30
    assert len(result.items) == 24
    assert all(item.can_delete for item in result.items)


def test_exact_total_and_page_do_not_step_through_all_visible_history(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch, 100000)
    connect = history._history_connect
    steps = 0

    def step():
        nonlocal steps
        steps += 1
        return 0

    def instrumented(**kwargs):
        connection = connect(**kwargs)
        connection.set_progress_handler(step, 1)
        return connection

    monkeypatch.setattr(history, "_history_connect", instrumented)
    result = history.list_image_history(limit=24, veyra_user_id=1)
    assert result.total == 66667
    assert len(result.items) == 24
    assert steps < 2000
