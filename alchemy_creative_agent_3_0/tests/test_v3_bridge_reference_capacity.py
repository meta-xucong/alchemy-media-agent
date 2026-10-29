import hashlib
import struct
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    ProjectReferenceSourceType,
    ProjectReferenceStatus,
)
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService


def _png_with_exact_size(path: Path, *, width: int, height: int, target_bytes: int) -> bytes:
    import io

    stream = io.BytesIO()
    Image.new("RGB", (width, height), (20, 40, 60)).save(stream, format="PNG")
    content = stream.getvalue()
    padding = target_bytes - len(content) - 12
    assert padding > 0
    chunk_data = b"x" * padding
    chunk = struct.pack(">I", len(chunk_data)) + b"tEXt" + chunk_data
    chunk += struct.pack(">I", zlib.crc32(b"tEXt" + chunk_data) & 0xFFFFFFFF)
    content = content[:-12] + chunk + content[-12:]
    assert len(content) == target_bytes
    path.write_bytes(content)
    return content


def test_project_reference_admission_accepts_bridge_current_capacity(tmp_path):
    path = tmp_path / "reference.png"
    original = _png_with_exact_size(path, width=1024, height=1536, target_bytes=2_976_403)
    upload = SimpleNamespace(
        file_path=str(path), mime_type="image/png", content_sha256=hashlib.sha256(original).hexdigest(),
    )
    project = SimpleNamespace(reference_assets=[SimpleNamespace(
        project_id="project-1", asset_ref_id="asset-1", status=ProjectReferenceStatus.ACTIVE,
        source_type=ProjectReferenceSourceType.UPLOADED,
    )])
    service = object.__new__(V3ProjectModeService)
    service._render_bridge_project = lambda _project_id, _owner_id: project
    service._standard_project_source_tombstones = lambda _project: set()
    service._reference_visible_to_owner = lambda _reference, _owner: True
    service._require_ready_uploaded_reference = lambda _asset_id, _policy: upload

    result = service.render_bridge_references(
        project_id="project-1", owner_user_id=7, uploaded_asset_ids=["asset-1"],
    )

    assert result == [upload]
    assert path.read_bytes() == original
