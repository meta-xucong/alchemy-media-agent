from datetime import datetime, timezone

from types import SimpleNamespace

import app.services.image_history as image_history
from app.schemas import ImageHistoryItem
from app.services.image_history import list_image_history


def _history_item(output_id: str, created_at: datetime, updated_at: datetime | None = None) -> ImageHistoryItem:
    return ImageHistoryItem(
        output_id=output_id,
        job_id=f"job-{output_id}",
        provider_id="provider",
        model="model",
        prompt="prompt",
        url=f"/outputs/{output_id}",
        created_at=created_at,
        updated_at=updated_at or created_at,
    )


def test_history_page_uses_migrated_sqlite_index_and_preserves_latest_duplicate(
    tmp_path, monkeypatch
):
    history_path = tmp_path / "image_history.jsonl"
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [_history_item(f"out-{index:04d}", base.replace(day=1)) for index in range(20)]
    rows.append(_history_item("out-0000", base.replace(day=1), base.replace(day=3)))
    history_path.write_text("\n".join(item.model_dump_json() for item in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        image_history,
        "settings",
        SimpleNamespace(image_history_path=history_path, veyra_auth_enabled=False),
    )

    def forbidden_read_text(*_args, **_kwargs):
        raise AssertionError("history index must not load the whole JSONL file")

    monkeypatch.setattr(type(history_path), "read_text", forbidden_read_text)
    response = image_history.list_image_history(limit=5, offset=3, include_all=True)

    assert response.total == 20
    assert [item.output_id for item in response.items] == [
        "out-0016", "out-0015", "out-0014", "out-0013", "out-0012"
    ]
    newest = image_history.list_image_history(limit=20, include_all=True)
    latest_item = next(item for item in newest.items if item.output_id == "out-0000")
    assert latest_item.created_at == base.replace(day=1)
    assert latest_item.updated_at == base.replace(day=3)
