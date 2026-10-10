from __future__ import annotations

import json
import math
import sqlite3
import threading
import tempfile
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.config import settings
from app.repositories import repository
from app.schemas import ImageHistoryItem, ImageHistoryResponse, ImageJob, ImageOutput
from app.services.favorites import delete_favorite, list_favorite_ids
from app.services.output_storage import delete_output_storage

_HISTORY_DATABASES: OrderedDict[str, None] = OrderedDict()
_HISTORY_SCHEMA_LOCK = threading.Lock()
_HISTORY_DATABASES_MAX = 8


class LegacyHistoryImportError(ValueError):
    """A legacy source could not be imported; its contents must not be exposed."""


def persist_image_job_history(job: ImageJob) -> None:
    if not settings.persist_image_history:
        return
    if not job.outputs:
        return
    _ensure_history_index()
    settings.image_history_path.parent.mkdir(parents=True, exist_ok=True)
    items: list[ImageHistoryItem] = []
    items = [
        ImageHistoryItem(
                output_id=output.output_id,
                job_id=job.job_id,
                run_id=job.run_id,
                status=job.status,
                provider_id=job.provider_id,
                model=job.model,
                mode=job.prompt_plan.mode,
                template_case_id=_template_case_id(job),
                prompt=_generation_prompt(job),
                url=output.url,
                thumbnail_url=_thumbnail_url(output),
                preview_url=_preview_url(output),
                score=output.score,
                metadata=_history_metadata(job, output),
                created_at=output.created_at,
                updated_at=job.updated_at,
            )
        for output in job.outputs
    ]
    if items:
        connection = _history_connect()
        try:
            with connection:
                for item in items:
                    _upsert_history_item(connection, item)
        finally:
            connection.close()
        with settings.image_history_path.open("a", encoding="utf-8") as handle:
            for item in items:
                handle.write(item.model_dump_json())
                handle.write("\n")


def list_image_history(
    limit: int = 50,
    *,
    offset: int = 0,
    veyra_user_id: int | None = None,
    include_legacy_public: bool = True,
    include_all: bool = False,
) -> ImageHistoryResponse:
    _ensure_history_index()
    safe_offset = max(0, offset)
    if not include_all and veyra_user_id is None and settings.veyra_auth_enabled:
        return ImageHistoryResponse(items=[], total=0)
    clauses: list[str] = []
    params: list[Any] = []
    if not include_all and veyra_user_id is not None:
        if include_legacy_public:
            clauses.append("(owner_id=? OR owner_id IS NULL)")
            params.append(veyra_user_id)
        else:
            clauses.append("owner_id=?")
            params.append(veyra_user_id)
    where_sql = " WHERE " + " AND ".join(clauses) if clauses else ""
    connection = _history_connect()
    try:
        total = int(connection.execute("SELECT COUNT(*) FROM v2_image_history" + where_sql, params).fetchone()[0])
        rows = list(connection.execute(
            "SELECT payload FROM v2_image_history" + where_sql +
            " ORDER BY created_epoch DESC, job_id DESC LIMIT ? OFFSET ?",
            [*params, max(0, int(limit)), safe_offset],
        ))
        history_items = [ImageHistoryItem.model_validate_json(row[0]) for row in rows]
        favorite_ids = list_favorite_ids(
            veyra_user_id=veyra_user_id,
            include_legacy_public=include_legacy_public,
            include_all=include_all,
            output_ids=[item.output_id for item in history_items],
        )
        items = []
        for item in history_items:
            item = _with_veyra_history_access(
                _normalize_thumbnail_url(item),
                veyra_user_id=veyra_user_id,
                include_all=include_all,
            )
            items.append(item.model_copy(update={"favorite": item.output_id in favorite_ids}))
        return ImageHistoryResponse(items=items, total=total)
    finally:
        connection.close()


def get_image_history_item(output_id: str) -> ImageHistoryItem | None:
    _ensure_history_index()
    connection = _history_connect()
    try:
        row = connection.execute(
            "SELECT payload FROM v2_image_history WHERE output_id=?", (output_id,)
        ).fetchone()
        return ImageHistoryItem.model_validate_json(row[0]) if row else None
    finally:
        connection.close()


def delete_image_history_item(output_id: str) -> dict[str, Any]:
    _ensure_history_index()
    removed_records = 0
    newest_removed: ImageHistoryItem | None = None
    if settings.image_history_path.exists():
        path = settings.image_history_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
            temp_path = Path(handle.name)
            with path.open("r", encoding="utf-8") as source:
                for line in source:
                    try:
                        item = ImageHistoryItem.model_validate_json(line)
                    except (json.JSONDecodeError, ValueError):
                        handle.write(line)
                        continue
                    if item.output_id != output_id:
                        handle.write(line if line.endswith("\n") else line + "\n")
                        continue
                    removed_records += 1
                    if newest_removed is None or _timestamp(item.updated_at) >= _timestamp(newest_removed.updated_at):
                        newest_removed = item
        if removed_records:
            temp_path.replace(path)
        else:
            temp_path.unlink(missing_ok=True)

    connection = _history_connect()
    try:
        with connection:
            row = connection.execute(
                "SELECT payload FROM v2_image_history WHERE output_id=?", (output_id,)
            ).fetchone()
            if row and newest_removed is None:
                newest_removed = ImageHistoryItem.model_validate_json(row[0])
            connection.execute("DELETE FROM v2_image_history WHERE output_id=?", (output_id,))
    finally:
        connection.close()

    output = repository.delete_output(output_id)
    metadata = dict(newest_removed.metadata if newest_removed else output.metadata if output else {})
    storage_result = delete_output_storage(output_id, metadata)
    removed_output = bool(output)
    if not removed_records and not removed_output and not any(storage_result.values()):
        return {
            "ok": False,
            "output_id": output_id,
            "removed_history_records": 0,
            "removed_favorites": 0,
            "removed_repository_output": False,
            **storage_result,
        }
    removed_favorites = delete_favorite(output_id)
    return {
        "ok": True,
        "output_id": output_id,
        "removed_history_records": removed_records,
        "removed_favorites": removed_favorites,
        "removed_repository_output": removed_output,
        **storage_result,
    }


def _history_connect() -> sqlite3.Connection:
    db_path = settings.image_history_path.with_name("image_history_index.sqlite3")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=3.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=3000")
    key = str(db_path.resolve())
    if key not in _HISTORY_DATABASES:
        with _HISTORY_SCHEMA_LOCK:
            if key not in _HISTORY_DATABASES:
                try:
                    connection.execute("PRAGMA journal_mode=WAL")
                    connection.execute(
                        """CREATE TABLE IF NOT EXISTS v2_image_history (
                            output_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, owner_id INTEGER,
                            created_epoch REAL NOT NULL, updated_epoch REAL NOT NULL, payload TEXT NOT NULL
                        )"""
                    )
                    connection.execute(
                        "CREATE INDEX IF NOT EXISTS v2_image_history_page_idx "
                        "ON v2_image_history(owner_id, created_epoch DESC, job_id DESC)"
                    )
                    connection.execute(
                        """CREATE TABLE IF NOT EXISTS v2_image_history_migration (
                            migration_key TEXT PRIMARY KEY, completed_at TEXT NOT NULL
                        )"""
                    )
                    _HISTORY_DATABASES[key] = None
                    _HISTORY_DATABASES.move_to_end(key)
                    while len(_HISTORY_DATABASES) > _HISTORY_DATABASES_MAX:
                        _HISTORY_DATABASES.popitem(last=False)
                except Exception:
                    connection.close()
                    raise
    return connection


def _upsert_history_item(connection: sqlite3.Connection, item: ImageHistoryItem) -> None:
    created_epoch = _timestamp(item.created_at)
    updated_epoch = _timestamp(item.updated_at)
    connection.execute(
        """INSERT INTO v2_image_history(output_id, job_id, owner_id, created_epoch, updated_epoch, payload)
           VALUES(?, ?, ?, ?, ?, ?)
           ON CONFLICT(output_id) DO UPDATE SET
             job_id=excluded.job_id, owner_id=excluded.owner_id,
             created_epoch=excluded.created_epoch, updated_epoch=excluded.updated_epoch,
             payload=excluded.payload
           WHERE excluded.updated_epoch >= v2_image_history.updated_epoch""",
        (
            item.output_id,
            item.job_id,
            _veyra_user_id(item.metadata),
            created_epoch,
            updated_epoch,
            item.model_dump_json(),
        ),
    )


def _ensure_history_index() -> None:
    """Atomically import complete legacy JSONL once, one validated record at a time."""
    connection = _history_connect()
    try:
        # Completed databases must not replay their source or need a write lock.
        if connection.execute(
            "SELECT 1 FROM v2_image_history_migration WHERE migration_key='jsonl'"
        ).fetchone():
            return
        # Serialize the marker check with the import, even in autocommit mode.
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute(
            "SELECT 1 FROM v2_image_history_migration WHERE migration_key='jsonl'"
        ).fetchone():
            connection.commit()
            return
        path = settings.image_history_path
        try:
            path.stat()
        except FileNotFoundError:
            # A source restored later still needs its first import.
            connection.commit()
            return
        except OSError:
            raise LegacyHistoryImportError("Legacy V2 image history could not be read.") from None
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        json.loads(
                            line,
                            parse_float=_finite_json_float,
                            parse_constant=_finite_json_float,
                            object_pairs_hook=_unique_json_object,
                        )
                        # Preserve the schema's JSON coercions and Unicode checks.
                        item = ImageHistoryItem.model_validate_json(line)
                        if any(not value.strip() or "\x00" in value for value in (item.output_id, item.job_id)):
                            raise ValueError("History identity is invalid.")
                        owner_id = _legacy_history_owner_id(item.metadata)
                        previous = connection.execute(
                            "SELECT owner_id FROM v2_image_history WHERE output_id=?", (item.output_id,)
                        ).fetchone()
                        # An ambiguous legacy duplicate must not change who can
                        # see an output, even when it would win by timestamp.
                        if previous and previous[0] != owner_id:
                            raise ValueError("History output owners must agree.")
                        _upsert_history_item(connection, item)
                    except (ValueError, OverflowError, RecursionError):
                        raise LegacyHistoryImportError(
                            f"Legacy V2 image history has an invalid record at line {line_number}."
                        ) from None
        except UnicodeError:
            raise LegacyHistoryImportError("Legacy V2 image history is not valid UTF-8.") from None
        except OSError:
            raise LegacyHistoryImportError("Legacy V2 image history could not be read.") from None
        connection.execute(
            "INSERT INTO v2_image_history_migration(migration_key, completed_at) VALUES('jsonl', ?)",
            (datetime.now().astimezone().isoformat(),),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _finite_json_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("History JSON numbers must be finite.")
    return number


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("History JSON object fields must be unique.")
        result[key] = value
    return result


def _legacy_history_owner_id(metadata: dict[str, Any]) -> int | None:
    value = metadata.get("veyra_user_id")
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    # Float tokens can lose owner identity before validation through rounding.
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("History owner must be an integer.")
    if isinstance(value, str):
        value = value.strip().removeprefix("+")
        if not value.isascii() or not value.isdecimal():
            raise ValueError("History owner must be a decimal integer.")
    owner_id = int(value)
    if not 0 <= owner_id <= 2**63 - 1:
        raise ValueError("History owner must be a nonnegative SQLite integer.")
    return owner_id or None


def _template_case_id(job: ImageJob) -> str | None:
    value = job.prompt_plan.user_variables.get("primary_case_id")
    return str(value) if value else None


def _history_metadata(job: ImageJob, output: ImageOutput) -> dict[str, Any]:
    metadata = dict(output.metadata)
    user_variables = job.prompt_plan.user_variables or {}
    metadata.setdefault("original_prompt", str(user_variables.get("user_prompt") or ""))
    metadata.setdefault("final_prompt", _generation_prompt(job))
    if user_variables.get("prompt_transform"):
        metadata.setdefault("prompt_transform", user_variables["prompt_transform"])
    if job.prompt_plan.negative_prompt:
        metadata.setdefault("negative_prompt", job.prompt_plan.negative_prompt)
    if job.prompt_plan.explanation:
        metadata.setdefault("prompt_explanation", job.prompt_plan.explanation)
    if user_variables.get("orchestrator_decision_id"):
        metadata.setdefault("orchestrator_decision_id", str(user_variables["orchestrator_decision_id"]))
    if user_variables.get("orchestrator_provider"):
        metadata.setdefault("orchestrator_provider", str(user_variables["orchestrator_provider"]))
    if user_variables.get("prompt_source"):
        metadata.setdefault("prompt_source", str(user_variables["prompt_source"]))
    metadata.setdefault("claude_final_prompt_used", bool(user_variables.get("claude_final_prompt_used")))
    for key in [
        "template_lock_enabled",
        "template_lock_contract",
        "task_relationship_model",
        "asset_frame_strategy",
        "asset_binding_plan",
        "provider_input_plan",
        "uploaded_assets",
        "provider_input_asset_ids",
    ]:
        if key in user_variables:
            metadata.setdefault(key, user_variables[key])
    return metadata


def _generation_prompt(job: ImageJob) -> str:
    return str((job.prompt_plan.user_variables or {}).get("generation_prompt") or job.prompt_plan.prompt)


def _thumbnail_url(output: ImageOutput) -> str | None:
    if output.metadata.get("native_v2_storage"):
        return _thumbnail_endpoint(output.output_id)
    if output.metadata.get("mock"):
        return output.metadata.get("thumbnail_url")
    return _thumbnail_endpoint(output.output_id)


def _preview_url(output: ImageOutput) -> str | None:
    if output.metadata.get("native_v2_storage"):
        return _preview_endpoint(output.output_id)
    if output.metadata.get("mock"):
        return output.metadata.get("preview_url") or output.metadata.get("thumbnail_url")
    return _preview_endpoint(output.output_id)


def _normalize_thumbnail_url(item: ImageHistoryItem) -> ImageHistoryItem:
    if item.metadata.get("native_v2_storage"):
        return item.model_copy(update={"thumbnail_url": _thumbnail_endpoint(item.output_id), "preview_url": _preview_endpoint(item.output_id)})
    if item.metadata.get("mock"):
        return item
    return item.model_copy(update={"thumbnail_url": _thumbnail_endpoint(item.output_id), "preview_url": _preview_endpoint(item.output_id)})


def _with_veyra_history_access(
    item: ImageHistoryItem,
    *,
    veyra_user_id: int | None,
    include_all: bool,
) -> ImageHistoryItem:
    owner_id = _veyra_user_id(item.metadata)
    can_delete = _can_delete_veyra_history(owner_id, veyra_user_id=veyra_user_id, include_all=include_all)
    if owner_id is not None:
        return item.model_copy(update={"can_delete": can_delete})
    metadata = dict(item.metadata)
    metadata.setdefault("veyra_legacy_public", True)
    metadata.setdefault("record_label", "旧版生图记录")
    return item.model_copy(
        update={
            "metadata": metadata,
            "veyra_legacy_public": True,
            "record_label": "旧版生图记录",
            "can_delete": can_delete,
        }
    )


def _can_delete_veyra_history(owner_id: int | None, *, veyra_user_id: int | None, include_all: bool) -> bool:
    if not settings.veyra_auth_enabled:
        return True
    if include_all:
        return True
    return owner_id is not None and owner_id == veyra_user_id


def _thumbnail_endpoint(output_id: str) -> str:
    return f"/api/v2/image/history/{quote(output_id, safe='')}/thumbnail"


def _preview_endpoint(output_id: str) -> str:
    return f"/api/v2/image/history/{quote(output_id, safe='')}/preview"


def _timestamp(value: datetime) -> float:
    return value.timestamp()


def _veyra_user_id(metadata: dict[str, Any]) -> int | None:
    try:
        value = int(metadata.get("veyra_user_id") or 0)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None
