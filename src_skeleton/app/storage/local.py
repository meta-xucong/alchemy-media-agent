from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings


class LocalMediaStore:
    def __init__(self, root: Path | None = None):
        self.root = root or settings.media_storage_root

    @property
    def generated_root(self) -> Path:
        return self.root / "generated_images"

    @property
    def thumbnail_root(self) -> Path:
        return self.root / "thumbnails"

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
        return f"/v1/outputs/{output_id}/download"

    def thumbnail_url(self, output_id: str) -> str:
        return f"/v1/outputs/{output_id}/thumbnail"

    def thumbnail_path(self, output_id: str) -> Path:
        return self.thumbnail_root / f"{output_id}.jpg"

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

    def output_path(self, *, job_id: str, output_id: str, output_format: str) -> Path:
        ext = "jpg" if output_format == "jpeg" else output_format
        return self.generated_root / job_id / f"{output_id}.{ext}"

    def save_history_record(self, record: dict[str, Any]) -> None:
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with self.history_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def list_history_records(self, *, limit: int = 50, session_id: str | None = None) -> list[dict[str, Any]]:
        if not self.history_file.exists():
            return []
        records_by_output: dict[str, dict[str, Any]] = {}
        for line in self.history_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            output_id = record.get("id")
            if not output_id:
                continue
            if session_id and record.get("session_id") != session_id:
                continue
            output_format = record.get("format") or "png"
            path = self.output_path(job_id=record.get("job_id", ""), output_id=output_id, output_format=output_format)
            if not path.exists():
                continue
            record["source"] = "manifest"
            record["thumbnail_url"] = self.thumbnail_url(output_id)
            existing = records_by_output.get(output_id)
            if existing is None or _record_timestamp(record) >= _record_timestamp(existing):
                records_by_output[output_id] = record
        records = sorted(records_by_output.values(), key=_record_timestamp, reverse=True)
        return records[:limit]

    def delete_output_file(self, *, output_id: str, job_id: str | None = None, output_format: str | None = None) -> bool:
        target: Path | None = None
        if job_id and output_format:
            candidate = self.output_path(job_id=job_id, output_id=output_id, output_format=output_format)
            if candidate.exists():
                target = candidate
        if target is None:
            found = self.find_output_file(output_id)
            if found:
                target = found[0]
        if target is None:
            return False

        generated_root = self.generated_root.resolve()
        resolved = target.resolve()
        if generated_root not in resolved.parents:
            return False

        target.unlink(missing_ok=True)
        self.delete_thumbnail(output_id)
        parent = target.parent
        try:
            if parent != generated_root and parent.parent == generated_root and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass
        return True

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

    def delete_history_record(self, output_id: str) -> int:
        if not self.history_file.exists():
            return 0
        kept_lines: list[str] = []
        removed = 0
        for line in self.history_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                kept_lines.append(line)
                continue
            if record.get("id") == output_id:
                removed += 1
                continue
            kept_lines.append(line)
        if removed:
            self.history_file.write_text(("\n".join(kept_lines) + "\n") if kept_lines else "", encoding="utf-8")
        return removed

    def find_output_file(self, output_id: str) -> tuple[Path, str, str] | None:
        outputs_root = self.generated_root
        if not outputs_root.exists():
            return None
        for path in outputs_root.glob(f"*/{output_id}.*"):
            output_format = _format_from_suffix(path.suffix)
            if output_format:
                return path, output_format, path.parent.name
        return None


def _format_from_suffix(suffix: str) -> str | None:
    normalized = suffix.lower().lstrip(".")
    if normalized == "jpg":
        return "jpeg"
    if normalized in {"png", "jpeg", "webp", "mp4"}:
        return normalized
    return None


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
