#!/usr/bin/env python3
"""V3 storage maintenance.

The default operation is read-only. ``--apply`` moves only proven-safe
objects into a quarantine directory. Failed terminal jobs and their output
records expire from the user-visible V3 store after the configured failure
retention; successful deliveries and project/upload records are untouched.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Iterable


JOB_ID_RE = re.compile(r"^job_[A-Za-z0-9_-]+$")
OUTPUT_ID_RE = re.compile(r"^v3_output_[a-f0-9]{20}$")
MOCK_PROVIDERS = {"v3_mock_contract_fixture", "mock", "test"}
CACHE_DIRS = ("provider_reference_cache", "share_cache")
FAILURE_STATUSES = {"failed", "blocked", "not_found"}


@dataclass
class Inventory:
    project_job_ids: set[str] = field(default_factory=set)
    project_output_ids: set[str] = field(default_factory=set)
    history_output_ids: set[str] = field(default_factory=set)
    job_output_ids: set[str] = field(default_factory=set)
    mcp_job_ids: set[str] = field(default_factory=set)
    mcp_output_ids: set[str] = field(default_factory=set)
    job_records: dict[str, dict[str, Any]] = field(default_factory=dict)
    output_records: dict[str, dict[str, Any]] = field(default_factory=dict)
    unreadable: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Candidate:
    kind: str
    path: Path
    size: int
    reason: str


def _json(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, (dict, list)) else None


def _walk_ids(value: Any, *, jobs: set[str], outputs: set[str]) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _walk_ids(item, jobs=jobs, outputs=outputs)
    elif isinstance(value, list):
        for item in value:
            _walk_ids(item, jobs=jobs, outputs=outputs)
    elif isinstance(value, str):
        if JOB_ID_RE.fullmatch(value):
            jobs.add(value)
        elif OUTPUT_ID_RE.fullmatch(value):
            outputs.add(value)


def _files(root: Path, pattern: str = "*.json") -> Iterable[Path]:
    if root.exists():
        yield from (path for path in root.rglob(pattern) if path.is_file())


def build_inventory(root: Path) -> Inventory:
    inventory = Inventory()
    for path in _files(root / "v3_projects"):
        value = _json(path)
        if value is None:
            inventory.unreadable.append(str(path))
            continue
        _walk_ids(value, jobs=inventory.project_job_ids, outputs=inventory.project_output_ids)

    history = root / "history" / "outputs.jsonl"
    if history.exists():
        try:
            for line in history.read_text(encoding="utf-8", errors="strict").splitlines():
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                _walk_ids(value, jobs=set(), outputs=inventory.history_output_ids)
        except (OSError, UnicodeDecodeError):
            inventory.unreadable.append(str(history))

    for path in _files(root / "v3_jobs"):
        value = _json(path)
        if value is None:
            inventory.unreadable.append(str(path))
            continue
        job_id = str(value.get("job_id") or path.stem)
        if JOB_ID_RE.fullmatch(job_id):
            inventory.job_records[job_id] = value
        _walk_ids(value, jobs=set(), outputs=inventory.job_output_ids)

    for path in _files(root / "v3_outputs"):
        if path.name != "output.json":
            continue
        value = _json(path)
        if value is None:
            inventory.unreadable.append(str(path))
            continue
        output_id = str(value.get("output_id") or path.parent.name)
        if OUTPUT_ID_RE.fullmatch(output_id):
            inventory.output_records[output_id] = value

    for path in _files(root / "v3_mcp_materializations"):
        value = _json(path)
        if value is None:
            continue
        _walk_ids(value, jobs=inventory.mcp_job_ids, outputs=inventory.mcp_output_ids)
    return inventory


def _old_enough(path: Path, *, cutoff: timedelta, now: datetime) -> bool:
    """Use the newest file mtime, never a directory mtime, for retention."""

    files = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()]
    if not files:
        return False
    newest = max(item.stat().st_mtime for item in files)
    return now - datetime.fromtimestamp(newest, tz=timezone.utc) >= cutoff


def _record_expired(record: dict[str, Any], *, retention_days: int, now: datetime) -> bool:
    """Expire only existing terminal failure states using their last update."""

    if str(record.get("status") or "").strip().lower() not in FAILURE_STATUSES:
        return False
    value = str(record.get("updated_at") or record.get("created_at") or "").strip()
    if not value:
        return False
    try:
        updated_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return now - updated_at.astimezone(timezone.utc) >= timedelta(days=max(1, retention_days))


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _mock_job(job: dict[str, Any]) -> bool:
    provider = str(job.get("provider") or "")
    if provider in MOCK_PROVIDERS:
        return True
    request = job.get("request")
    if isinstance(request, dict) and str(request.get("provider") or "") in MOCK_PROVIDERS:
        return True
    return False


def candidates(
    root: Path,
    inventory: Inventory,
    *,
    retention_days: int,
    failure_retention_days: int = 7,
    now: datetime,
) -> list[Candidate]:
    result: list[Candidate] = []
    cutoff = timedelta(days=max(1, retention_days))
    for name in CACHE_DIRS:
        cache_root = root / name
        for path in cache_root.rglob("*") if cache_root.exists() else ():
            if path.is_file() and _old_enough(path, cutoff=cutoff, now=now):
                result.append(Candidate("cache", path, path.stat().st_size, f"expired_{name}"))

    referenced_jobs = inventory.project_job_ids | inventory.mcp_job_ids
    referenced_outputs = (
        inventory.project_output_ids
        | inventory.history_output_ids
        | inventory.job_output_ids
        | inventory.mcp_output_ids
    )
    expired_failed_jobs: set[str] = set()
    for job_id, record in inventory.job_records.items():
        path = root / "v3_jobs" / f"{job_id}.json"
        if path.exists() and _record_expired(record, retention_days=failure_retention_days, now=now):
            expired_failed_jobs.add(job_id)
            result.append(Candidate("expired_failed_job", path, _size(path), "expired_terminal_failure"))
    for job_id, record in inventory.job_records.items():
        path = root / "v3_jobs" / f"{job_id}.json"
        if job_id in expired_failed_jobs or job_id in referenced_jobs or not _mock_job(record) or not path.exists():
            continue
        if _old_enough(path, cutoff=cutoff, now=now):
            result.append(Candidate("mock_job", path, _size(path), "unreferenced_mock_job"))
    for output_id, record in inventory.output_records.items():
        path = root / "v3_outputs" / output_id
        if path.exists() and str(record.get("job_id") or "") in expired_failed_jobs:
            result.append(Candidate("expired_failed_output", path, _size(path), "expired_terminal_failure"))
            continue
        if output_id in referenced_outputs or not path.exists():
            continue
        if str(record.get("provider") or "") not in MOCK_PROVIDERS:
            continue
        if _old_enough(path, cutoff=cutoff, now=now):
            result.append(Candidate("mock_output", path, _size(path), "unreferenced_mock_output"))
    return result


def delete_expired_failures(root: Path, items: list[Candidate]) -> list[str]:
    """Delete only expired failed jobs/outputs after their seven-day window."""

    deleted: list[str] = []
    for item in items:
        if item.kind not in {"expired_failed_job", "expired_failed_output"}:
            continue
        _safe_child(root, item.path)
        if item.path.is_dir():
            shutil.rmtree(item.path)
        elif item.path.exists():
            item.path.unlink()
        deleted.append(str(item.path.relative_to(root)))
    return deleted


def _safe_child(root: Path, path: Path) -> None:
    resolved_root = root.resolve()
    resolved = path.resolve()
    if resolved == resolved_root or resolved_root not in resolved.parents:
        raise ValueError(f"refusing path outside storage root: {path}")


def quarantine(root: Path, items: list[Candidate], *, now: datetime) -> Path | None:
    if not items:
        return None
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    trash = root / ".v3_maintenance_trash" / stamp
    trash.mkdir(parents=True, exist_ok=False)
    manifest: list[dict[str, Any]] = []
    for item in items:
        _safe_child(root, item.path)
        relative = item.path.relative_to(root)
        target = trash / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(item.path), str(target))
        manifest.append({"kind": item.kind, "path": str(relative), "size": item.size, "reason": item.reason})
    (trash / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return trash


def purge_trash(root: Path, *, retention_days: int, now: datetime) -> list[str]:
    trash_root = root / ".v3_maintenance_trash"
    removed: list[str] = []
    if not trash_root.exists():
        return removed
    cutoff = timedelta(days=max(1, retention_days))
    for path in trash_root.iterdir():
        if path.is_dir() and now - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) >= cutoff:
            _safe_child(root, path)
            shutil.rmtree(path)
            removed.append(str(path))
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="V1 V3 media storage root")
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--failure-retention-days", type=int, default=7)
    parser.add_argument("--trash-retention-days", type=int, default=7)
    parser.add_argument("--apply", action="store_true", help="quarantine proven-safe candidates")
    parser.add_argument("--purge-trash", action="store_true", help="delete quarantine batches older than retention")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"storage root does not exist: {root}")
    now = datetime.now(timezone.utc)
    inventory = build_inventory(root)
    items = candidates(
        root,
        inventory,
        retention_days=args.retention_days,
        failure_retention_days=args.failure_retention_days,
        now=now,
    )
    report = {
        "root": str(root),
        "generated_at": now.isoformat(),
        "counts": {
            "projects_jobs": len(inventory.project_job_ids),
            "projects_outputs": len(inventory.project_output_ids),
            "jobs": len(inventory.job_records),
            "outputs": len(inventory.output_records),
            "history_outputs": len(inventory.history_output_ids),
            "unreadable": len(inventory.unreadable),
            "candidates": len(items),
        },
        "candidates": [
            {"kind": item.kind, "path": str(item.path.relative_to(root)), "size": item.size, "reason": item.reason}
            for item in items
        ],
        "unreadable": inventory.unreadable,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.apply:
        failure_items = [item for item in items if item.kind.startswith("expired_failed_")]
        quarantine_path = quarantine(root, [item for item in items if item not in failure_items], now=now)
        if quarantine_path:
            print(json.dumps({"quarantined_to": str(quarantine_path)}, ensure_ascii=False))
        print(json.dumps({"deleted_expired_failures": delete_expired_failures(root, failure_items)}, ensure_ascii=False))
    if args.purge_trash:
        print(json.dumps({"purged": purge_trash(root, retention_days=args.trash_retention_days, now=now)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
