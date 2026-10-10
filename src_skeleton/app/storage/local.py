from __future__ import annotations

import base64
import heapq
import json
import math
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import settings
from app.repositories.sqlite_json import connect


class LegacyHistoryImportError(ValueError):
    """A retryable legacy-source failure with no source payload in its message."""

    def __init__(self, line_number: int, reason: str):
        self.line_number = line_number
        self.reason = reason
        super().__init__(f"Legacy history import failed at line {line_number}: {reason}")


_STRICT_HISTORY_IMPORTER_ID = "v1.history.jsonl"
_STRICT_HISTORY_IMPORTER_VERSION = 1


class LocalMediaStore:
    def __init__(self, root: Path | None = None):
        self.root = root or settings.media_storage_root

    @property
    def generated_root(self) -> Path:
        return self.root / "generated_images"

    @property
    def asset_root(self) -> Path:
        return self.root / "assets"

    @property
    def thumbnail_root(self) -> Path:
        return self.root / "thumbnails"

    @property
    def preview_root(self) -> Path:
        return self.root / "previews"

    @property
    def history_file(self) -> Path:
        return self.root / "history" / "outputs.jsonl"

    def save_base64_output(self, *, job_id: str, output_id: str, b64_json: str, output_format: str) -> str:
        ext = "jpg" if output_format == "jpeg" else output_format
        output_dir = self.generated_root / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{output_id}.{ext}"
        path.write_bytes(base64.b64decode(b64_json))
        self.ensure_thumbnail(output_id=output_id, source_path=path)
        self.ensure_preview(output_id=output_id, source_path=path)
        return f"/v1/outputs/{output_id}/download"

    def save_asset_bytes(self, *, asset_id: str, filename: str, content: bytes) -> Path:
        target_dir = self.asset_root / asset_id
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_filename(filename)
        path = target_dir / safe_name
        path.write_bytes(content)
        return path

    def find_asset_file(self, asset_id: str) -> Path | None:
        target_dir = self.asset_root / asset_id
        if not target_dir.exists():
            return None
        for path in target_dir.iterdir():
            if path.is_file() and not path.name.startswith("."):
                return path
        return None

    def asset_url(self, asset_id: str) -> str:
        return f"/v1/assets/{asset_id}/content"

    def thumbnail_url(self, output_id: str) -> str:
        return f"/v1/outputs/{output_id}/thumbnail"

    def thumbnail_path(self, output_id: str) -> Path:
        return self.thumbnail_root / f"{output_id}.jpg"

    def preview_url(self, output_id: str) -> str:
        return f"/v1/outputs/{output_id}/preview"

    def preview_path(self, output_id: str) -> Path:
        return self.preview_root / f"{output_id}.webp"

    def ensure_thumbnail(self, *, output_id: str, source_path: Path, max_size: tuple[int, int] = (512, 512)) -> Path:
        thumbnail_path = self.thumbnail_path(output_id)
        if thumbnail_path.exists():
            try:
                if thumbnail_path.stat().st_mtime >= source_path.stat().st_mtime:
                    return thumbnail_path
            except OSError:
                pass

        try:
            from PIL import Image, ImageOps

            self.thumbnail_root.mkdir(parents=True, exist_ok=True)
            with Image.open(source_path) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
                image = _flatten_for_jpeg(image)
                temporary_path = thumbnail_path.with_suffix(".tmp.jpg")
                image.save(temporary_path, "JPEG", quality=82, optimize=True, progressive=True)
                temporary_path.replace(thumbnail_path)
                return thumbnail_path
        except Exception:
            return source_path

    def ensure_preview(self, *, output_id: str, source_path: Path, max_size: tuple[int, int] = (1600, 1600)) -> Path:
        preview_path = self.preview_path(output_id)
        if preview_path.exists():
            try:
                if preview_path.stat().st_mtime >= source_path.stat().st_mtime:
                    return preview_path
            except OSError:
                pass

        try:
            from PIL import Image, ImageOps

            self.preview_root.mkdir(parents=True, exist_ok=True)
            with Image.open(source_path) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
                if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
                    image = image.convert("RGBA")
                    temporary_path = preview_path.with_suffix(".tmp.webp")
                    image.save(temporary_path, "WEBP", quality=84, method=6)
                else:
                    temporary_path = preview_path.with_suffix(".tmp.webp")
                    image.convert("RGB").save(temporary_path, "WEBP", quality=84, method=6)
                temporary_path.replace(preview_path)
                return preview_path
        except Exception:
            return source_path

    def output_path(self, *, job_id: str, output_id: str, output_format: str) -> Path:
        ext = "jpg" if output_format == "jpeg" else output_format
        return self.generated_root / job_id / f"{output_id}.{ext}"

    def save_history_record(self, record: dict[str, Any]) -> None:
        self._ensure_history_index()
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        connection = connect(self.root / "repository.sqlite3")
        try:
            with connection:
                self._upsert_history_index(connection, record)
        finally:
            connection.close()
        with self.history_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def iter_history_records(
        self,
        *,
        limit: int = 50,
        session_id: str | None = None,
        include_missing: bool = False,
    ) -> Iterator[dict[str, Any]]:
        self._ensure_history_index()
        safe_limit = max(0, int(limit))
        if safe_limit == 0:
            return
        connection = connect(self.root / "repository.sqlite3")
        yielded = 0
        try:
            if session_id:
                cursor = connection.execute(
                    "SELECT payload FROM v1_history_records WHERE session_id=? "
                    "ORDER BY created_epoch DESC, sequence ASC",
                    (session_id,),
                )
            else:
                cursor = connection.execute(
                    "SELECT payload FROM v1_history_records ORDER BY created_epoch DESC, sequence ASC"
                )
            for row in cursor:
                record = json.loads(row[0])
                output_id = record.get("id")
                if not output_id:
                    continue
                output_format = record.get("format") or "png"
                path = self.output_path(job_id=record.get("job_id", ""), output_id=output_id, output_format=output_format)
                if not path.exists() and not include_missing:
                    continue
                record["source"] = "manifest"
                record["thumbnail_url"] = self.thumbnail_url(output_id)
                record["preview_url"] = self.preview_url(output_id)
                record["url"] = f"/v1/outputs/{output_id}/download"
                yield record
                yielded += 1
                if yielded >= safe_limit:
                    break
        finally:
            connection.close()

    def get_history_record(self, output_id: str, *, include_missing: bool = False) -> dict[str, Any] | None:
        """Read one indexed history manifest without applying the page window."""
        self._ensure_history_index()
        connection = connect(self.root / "repository.sqlite3")
        try:
            return self.get_history_record_on(
                connection,
                output_id,
                include_missing=include_missing,
            )
        finally:
            connection.close()

    def get_history_record_on(
        self,
        connection: sqlite3.Connection,
        output_id: str,
        *,
        include_missing: bool = False,
    ) -> dict[str, Any] | None:
        """Read one indexed history manifest using a caller-owned connection."""
        row = connection.execute(
            "SELECT records.payload, evidence.owner_id, evidence.owner_conflict "
            "FROM v1_history_records AS records "
            "LEFT JOIN v1_history_owner_evidence AS evidence USING(output_id) "
            "WHERE records.output_id=?",
            (str(output_id),),
        ).fetchone()
        if row is None:
            return None
        record = json.loads(row[0])
        if bool(row[2]):
            record["_veyra_owner_conflict"] = True
        elif row[1] is not None:
            record["veyra_user_id"] = int(row[1])
        output_format = record.get("format") or "png"
        path = self.output_path(
            job_id=record.get("job_id", ""),
            output_id=str(output_id),
            output_format=output_format,
        )
        if not include_missing and not path.exists():
            return None
        record["source"] = "manifest"
        record["thumbnail_url"] = self.thumbnail_url(str(output_id))
        record["preview_url"] = self.preview_url(str(output_id))
        record["url"] = f"/v1/outputs/{output_id}/download"
        return record

    def list_history_records(self, *, limit: int = 50, session_id: str | None = None) -> list[dict[str, Any]]:
        return list(self.iter_history_records(limit=limit, session_id=session_id))

    def list_generated_output_records(self, *, limit: int = 50) -> list[dict[str, Any]]:
        outputs_root = self.generated_root
        if not outputs_root.exists():
            return []
        safe_limit = max(0, int(limit))
        if safe_limit == 0:
            return []
        records: list[tuple[float, int, dict[str, Any]]] = []
        sequence = 0
        for path in outputs_root.glob("job_*/*"):
            if not path.is_file() or path.name.startswith("."):
                continue
            output_format = _format_from_suffix(path.suffix)
            if output_format not in {"png", "jpeg", "webp"}:
                continue
            job_id = path.parent.name
            output_id = path.stem
            if not _looks_like_generated_job_id(job_id) or not _looks_like_generated_output_id(output_id):
                continue
            try:
                updated_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
            except OSError:
                continue
            record = {
                    "id": output_id,
                    "job_id": job_id,
                    "url": f"/v1/outputs/{output_id}/download",
                    "thumbnail_url": self.thumbnail_url(output_id),
                    "preview_url": self.preview_url(output_id),
                    "format": output_format,
                    "provider": "local_filesystem",
                    "model": "recovered-output",
                    "prompt": "历史图片（从本地输出目录恢复，原始提示词不可用）",
                    "final_prompt": "历史图片（从本地输出目录恢复，原始提示词不可用）",
                    "created_at": updated_at,
                    "updated_at": updated_at,
                    "source": "filesystem",
                }
            item = (_record_timestamp(record), -sequence, record)
            sequence += 1
            if len(records) < safe_limit:
                heapq.heappush(records, item)
            elif item[:2] > records[0][:2]:
                heapq.heapreplace(records, item)
        return [item[2] for item in sorted(records, key=lambda item: item[:2], reverse=True)]

    def delete_output_file(self, *, output_id: str, job_id: str | None = None, output_format: str | None = None) -> bool:
        deleted_any = False
        generated_root = self.generated_root.resolve()

        def delete_candidate(target: Path) -> None:
            nonlocal deleted_any
            if not target.exists():
                return
            resolved = target.resolve()
            if generated_root not in resolved.parents:
                return
            try:
                target.unlink()
            except FileNotFoundError:
                # Another cleanup may have removed it after the existence
                # check. Treat that as an idempotent no-op.
                return
            deleted_any = True

        if job_id and output_format:
            delete_candidate(self.output_path(job_id=job_id, output_id=output_id, output_format=output_format))
        if self.generated_root.exists():
            for job_directory in self.generated_root.iterdir():
                if not job_directory.is_dir():
                    continue
                for path in job_directory.iterdir():
                    if path.stem == output_id and _format_from_suffix(path.suffix) in {"png", "jpeg", "webp"}:
                        delete_candidate(path)
                # Keep empty directories. Writers create them before opening
                # the output file; removing a just-emptied directory here can
                # race a different output's paused write in the same Job.
        self.delete_thumbnail(output_id)
        self.delete_preview(output_id)
        return deleted_any

    def delete_thumbnail(self, output_id: str) -> bool:
        thumbnail_path = self.thumbnail_path(output_id)
        if not thumbnail_path.exists():
            return False

        thumbnail_root = self.thumbnail_root.resolve()
        resolved = thumbnail_path.resolve()
        if thumbnail_root not in resolved.parents:
            return False

        thumbnail_path.unlink(missing_ok=True)
        return True

    def delete_preview(self, output_id: str) -> bool:
        preview_path = self.preview_path(output_id)
        if not preview_path.exists():
            return False

        preview_root = self.preview_root.resolve()
        resolved = preview_path.resolve()
        if preview_root not in resolved.parents:
            return False

        preview_path.unlink(missing_ok=True)
        return True

    def delete_history_record(self, output_id: str) -> int:
        self._ensure_history_index()
        removed = 0
        if self.history_file.exists():
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", newline="", dir=self.history_file.parent, delete=False
            ) as target:
                temporary = Path(target.name)
                with self.history_file.open("r", encoding="utf-8") as source:
                    for line in source:
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            target.write(line)
                            continue
                        if record.get("id") == output_id:
                            removed += 1
                            continue
                        target.write(line if line.endswith("\n") else line + "\n")
            if removed:
                temporary.replace(self.history_file)
            else:
                temporary.unlink(missing_ok=True)
        connection = connect(self.root / "repository.sqlite3")
        try:
            with connection:
                deleted_rows = connection.execute(
                    "DELETE FROM v1_history_records WHERE output_id=?", (output_id,)
                ).rowcount
                connection.execute(
                    "DELETE FROM v1_history_owner_evidence WHERE output_id=?", (output_id,)
                )
        finally:
            connection.close()
        return max(removed, int(deleted_rows or 0))

    def _ensure_history_index(self) -> None:
        connection = connect(self.root / "repository.sqlite3")
        try:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS v1_history_records (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    output_id TEXT NOT NULL UNIQUE,
                    session_id TEXT,
                    created_epoch REAL NOT NULL,
                    updated_epoch REAL NOT NULL,
                    payload TEXT NOT NULL
                )"""
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS v1_history_page_idx "
                "ON v1_history_records(session_id, created_epoch DESC, sequence ASC)"
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS v1_history_owner_evidence (
                    output_id TEXT PRIMARY KEY,
                    owner_id INTEGER NOT NULL,
                    owner_conflict INTEGER NOT NULL DEFAULT 0
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS v1_history_state (
                    state_key TEXT PRIMARY KEY,
                    state_value TEXT NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS v1_import_receipts (
                    namespace TEXT PRIMARY KEY, importer_id TEXT NOT NULL,
                    importer_version INTEGER NOT NULL, record_count INTEGER NOT NULL,
                    completed_at TEXT NOT NULL
                )"""
            )
            history_imported = connection.execute(
                "SELECT 1 FROM v1_history_state WHERE state_key='jsonl_imported'"
            ).fetchone() is not None
            owner_evidence_backfilled = connection.execute(
                "SELECT 1 FROM v1_history_state WHERE state_key='owner_evidence_backfilled'"
            ).fetchone() is not None
            if history_imported and owner_evidence_backfilled:
                return
            with connection:
                # Serialize initializers before observing migration state. A
                # waiter must not replay a source after another import commits.
                connection.execute("BEGIN IMMEDIATE")
                history_imported = connection.execute(
                    "SELECT 1 FROM v1_history_state WHERE state_key='jsonl_imported'"
                ).fetchone() is not None
                owner_evidence_backfilled = connection.execute(
                    "SELECT 1 FROM v1_history_state WHERE state_key='owner_evidence_backfilled'"
                ).fetchone() is not None
                if history_imported and owner_evidence_backfilled:
                    return
                strict_receipt_exists = connection.execute(
                    "SELECT 1 FROM v1_import_receipts WHERE namespace='history'"
                ).fetchone() is not None
                if (
                    (owner_evidence_backfilled and not history_imported)
                    or (history_imported and not owner_evidence_backfilled and strict_receipt_exists)
                ):
                    # This partial state must not fall through to first import:
                    # doing so could replay stale source rows or refresh
                    # authorization evidence from a source after a strict
                    # receipt proves both markers were committed atomically.
                    raise LegacyHistoryImportError(0, "import_state_inconsistent")
                if not history_imported and strict_receipt_exists:
                    raise LegacyHistoryImportError(0, "import_state_inconsistent")
                try:
                    source = self.history_file.open("rb")
                except FileNotFoundError:
                    # No source is not proof of a completed import. An empty
                    # store still works, and a later restored source is checked.
                    return
                except OSError:
                    raise LegacyHistoryImportError(0, "source_access_error") from None
                line_number = 0
                imported_count = 0
                try:
                    with source:
                        for line_number, line in enumerate(source, start=1):
                            if not line.strip():
                                continue
                            record = _parse_legacy_history_record(line, line_number)
                            if history_imported:
                                # Existing completion is authoritative: backfill
                                # owner evidence only, never resurrect deleted rows.
                                self._upsert_history_owner_evidence(connection, record)
                            else:
                                self._upsert_history_index(connection, record)
                                imported_count += 1
                except OSError:
                    raise LegacyHistoryImportError(line_number + 1, "source_read_error") from None
                connection.execute(
                    "INSERT OR REPLACE INTO v1_history_state(state_key, state_value) VALUES('jsonl_imported', '1')"
                )
                connection.execute(
                    "INSERT OR REPLACE INTO v1_history_state(state_key, state_value) "
                    "VALUES('owner_evidence_backfilled', '1')"
                )
                if not history_imported:
                    completed_at = datetime.now(timezone.utc).isoformat()
                    connection.execute(
                        """INSERT INTO v1_import_receipts(
                               namespace, importer_id, importer_version, record_count, completed_at
                           ) VALUES('history', ?, ?, ?, ?)""",
                        (_STRICT_HISTORY_IMPORTER_ID, _STRICT_HISTORY_IMPORTER_VERSION, imported_count, completed_at),
                    )
        finally:
            connection.close()

    @staticmethod
    def _upsert_history_owner_evidence(connection: sqlite3.Connection, record: dict[str, Any]) -> None:
        output_id = str(record.get("id") or "").strip()
        owner_id = _history_owner_id(record)
        if not output_id or owner_id is None:
            return
        existing = connection.execute(
            "SELECT owner_id, owner_conflict FROM v1_history_owner_evidence WHERE output_id=?",
            (output_id,),
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO v1_history_owner_evidence(output_id, owner_id) VALUES(?, ?)",
                (output_id, owner_id),
            )
        elif int(existing[0]) != owner_id and not existing[1]:
            connection.execute(
                "UPDATE v1_history_owner_evidence SET owner_conflict=1 WHERE output_id=?",
                (output_id,),
            )

    @staticmethod
    def _upsert_history_index(connection: sqlite3.Connection, record: dict[str, Any]) -> None:
        output_id = str(record.get("id") or "").strip()
        if not output_id:
            return
        LocalMediaStore._upsert_history_owner_evidence(connection, record)
        source_timestamp = _record_timestamp(record)
        created_epoch = source_timestamp
        # The previous in-memory dedupe chose the later source record by the
        # same created_at-or-updated_at timestamp used for display ordering.
        updated_epoch = source_timestamp
        existing = connection.execute(
            "SELECT payload FROM v1_history_records WHERE output_id=?", (output_id,)
        ).fetchone()
        incoming_owner = _history_owner_id(record)
        if existing:
            existing_record = json.loads(existing[0])
            existing_owner = _history_owner_id(existing_record)
            # A recovery/manifest duplicate with no owner cannot erase the
            # explicit account attribution of a durable history record.
            if existing_owner is not None and incoming_owner is None:
                return
        connection.execute(
            """INSERT INTO v1_history_records(output_id, session_id, created_epoch, updated_epoch, payload)
               VALUES(?, ?, ?, ?, ?)
               ON CONFLICT(output_id) DO UPDATE SET
                 session_id=excluded.session_id, created_epoch=excluded.created_epoch,
                 updated_epoch=excluded.updated_epoch, payload=excluded.payload
               WHERE excluded.updated_epoch >= v1_history_records.updated_epoch
                  OR (json_extract(v1_history_records.payload, '$.veyra_user_id') IS NULL
                      AND json_extract(excluded.payload, '$.veyra_user_id') IS NOT NULL)""",
            (
                output_id,
                str(record.get("session_id") or "") or None,
                created_epoch,
                updated_epoch,
                json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            ),
        )


    def find_output_file(self, output_id: str) -> tuple[Path, str, str] | None:
        outputs_root = self.generated_root
        if not outputs_root.exists():
            return None
        for path in outputs_root.glob(f"*/{output_id}.*"):
            output_format = _format_from_suffix(path.suffix)
            if output_format:
                return path, output_format, path.parent.name
        return None


def _parse_legacy_history_record(line: bytes, line_number: int) -> dict[str, Any]:
    try:
        record = json.loads(
            line.decode("utf-8"),
            parse_constant=_reject_json_constant,
            parse_float=_finite_json_float,
            object_pairs_hook=_unique_json_object,
        )
    except (ValueError, UnicodeError, RecursionError):
        # Decoder messages and chained exceptions can contain source material.
        raise LegacyHistoryImportError(line_number, "invalid_json") from None
    if not _valid_legacy_history_record(record):
        raise LegacyHistoryImportError(line_number, "invalid_record") from None
    try:
        # JSON escapes can decode to lone surrogates, even from valid UTF-8
        # source bytes. They cannot be persisted as a lossless SQLite payload.
        json.dumps(record, ensure_ascii=False).encode("utf-8")
    except (UnicodeError, RecursionError):
        raise LegacyHistoryImportError(line_number, "invalid_record") from None
    return record


def _reject_json_constant(_value: str) -> None:
    raise ValueError("Non-finite JSON number")


def _finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("Non-finite JSON number")
    return parsed


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _valid_legacy_history_record(record: Any) -> bool:
    # Historical manifests may omit everything except the output ID. Validate
    # present known fields without synthesizing defaults or dropping metadata.
    if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"].strip():
        return False
    if "\x00" in record["id"]:
        return False
    if "job_id" in record and (not isinstance(record["job_id"], str) or "\x00" in record["job_id"]):
        return False
    for field in (
        "session_id", "format", "created_at", "updated_at", "url", "thumbnail_url", "preview_url",
        "provider", "model", "requested_provider", "requested_model", "asset_mode", "original_prompt",
        "final_prompt", "prompt", "size", "version_parent_id", "source_app", "idempotency_key",
        "work_intensity", "work_intensity_label", "record_label", "source",
    ):
        if record.get(field) is not None and not isinstance(record[field], str):
            return False
    for field in ("width", "height"):
        if record.get(field) is not None and type(record[field]) is not int:
            return False
    for field in (
        "provider_fallback", "asset_plan", "provider_input_plan", "visual_review", "prompt_plan", "alchemy_lab",
    ):
        if record.get(field) is not None and not isinstance(record[field], dict):
            return False
    for field in ("asset_intents", "asset_vision_profiles"):
        if record.get(field) is not None and (
            not isinstance(record[field], list) or any(not isinstance(item, dict) for item in record[field])
        ):
            return False
    for field in ("veyra_legacy_public", "can_delete", "favorite", "_veyra_owner_conflict"):
        if field in record and type(record[field]) is not bool:
            return False
    owner = record.get("veyra_user_id")
    if owner is None or owner == "":
        return True
    if isinstance(owner, str):
        owner = owner.strip()
        if not owner:
            return True
        if re.fullmatch(r"\+?[0-9]+", owner) is None:
            return False
        try:
            owner = int(owner)
        except ValueError:
            return False
    # Preserve ownerless zero and legacy integer strings, but never coerce an
    # invalid explicit owner into public/ownerless history or a different owner.
    # Even integral floats may already have rounded a different source owner.
    return type(owner) is int and 0 <= owner <= 2**63 - 1


def _history_owner_id(record: dict[str, Any]) -> int | None:
    try:
        owner_id = int(record.get("veyra_user_id") or 0)
    except (TypeError, ValueError):
        return None
    return owner_id if owner_id > 0 else None


def _format_from_suffix(suffix: str) -> str | None:
    normalized = suffix.lower().lstrip(".")
    if normalized == "jpg":
        return "jpeg"
    if normalized in {"png", "jpeg", "webp", "mp4"}:
        return normalized
    return None


def _looks_like_generated_job_id(value: str) -> bool:
    return re.fullmatch(r"job_[A-Za-z0-9]{12,}", value or "") is not None


def _looks_like_generated_output_id(value: str) -> bool:
    return re.fullmatch(r"out_[A-Za-z0-9]{12,}", value or "") is not None


def _safe_filename(filename: str) -> str:
    stem = Path(filename or "asset").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    return cleaned or "asset.bin"


def _flatten_for_jpeg(image):
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        from PIL import Image

        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        flattened = Image.new("RGB", rgba.size, (255, 255, 255))
        flattened.paste(rgba, mask=alpha)
        return flattened
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _record_timestamp(record: dict[str, Any]) -> float:
    value = record.get("created_at") or record.get("updated_at")
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return 0.0


media_store = LocalMediaStore()
