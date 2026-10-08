"""Owner-side suspension points for output browsing; never worker handlers."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BrowseScope:
    projects: tuple[Any, ...]


@dataclass(frozen=True)
class BrowseOutputs:
    """Bind every prefetched output, including rows without a candidate Job."""
    records: list[Any]


@dataclass(frozen=True)
class BrowseJobRead:
    job_id: str
    output_records: list[Any] | None


@dataclass(frozen=True)
class BrowseCheckpoint:
    """Revalidate the read scope before any reconciliation/projection runs."""


def drive_browse_reads(steps, product_service):
    """Existing synchronous callers keep identical owner-side behavior."""
    value = None
    error = None
    try:
        while True:
            try:
                step = steps.throw(error) if error is not None else steps.send(value)
            except StopIteration as done:
                return done.value
            value = None
            error = None
            if isinstance(step, BrowseJobRead):
                try:
                    value = product_service.get_job_read_snapshot(
                        step.job_id, output_records=step.output_records,
                    )
                except Exception as exc:
                    error = exc
    finally:
        steps.close()
