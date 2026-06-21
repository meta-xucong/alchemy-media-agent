from __future__ import annotations

from app.services.output_storage import read_output_preview, read_output_thumbnail


def read_history_thumbnail(output_id: str) -> tuple[bytes, str] | None:
    return read_output_thumbnail(output_id)


def read_history_preview(output_id: str) -> tuple[bytes, str] | None:
    return read_output_preview(output_id)
