from __future__ import annotations

import base64
import json
from io import BytesIO

from PIL import Image

from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore


def _png_base64() -> str:
    image = Image.new("RGB", (32, 32), (120, 150, 180))
    output = BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def _save(store: V3GeneratedOutputStore, output_id: str, *, project_id: str) -> None:
    store.save_base64_output(
        job_id="job_doc320",
        candidate_id=output_id,
        asset_id=output_id,
        provider="test",
        model="test",
        output_id=output_id,
        encoded_image=_png_base64(),
        metadata={"project_id": project_id},
    )


def test_list_by_job_limit_is_optional_and_bounded(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    for index in range(3):
        _save(store, f"v3_output_{index:020x}", project_id="project_doc320")

    assert len(store.list_by_job("job_doc320", limit=2)) == 2
    assert len(store.list_by_job("job_doc320")) == 3


def test_scoped_locator_rebuilds_after_out_of_band_metadata_change(tmp_path) -> None:
    root = tmp_path / "outputs"
    store = V3GeneratedOutputStore(root)
    output_id = "v3_output_00000000000000000001"
    _save(store, output_id, project_id="project_old")

    assert [item.output_id for item in store.list_by_project("project_old")] == [output_id]

    record_path = root / output_id / "output.json"
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    payload["metadata"]["project_id"] = "project_new"
    record_path.write_text(json.dumps(payload), encoding="utf-8")

    assert store.list_by_project("project_old") == []
    assert [item.output_id for item in store.list_by_project("project_new")] == [output_id]

