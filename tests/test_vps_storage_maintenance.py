from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path

import importlib.util
import sys


_MODULE_PATH = Path(__file__).parents[1] / "ops" / "vps-storage-maintenance" / "v3_storage_maintenance.py"
_SPEC = importlib.util.spec_from_file_location("vps_storage_maintenance", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
build_inventory = _MODULE.build_inventory
candidates = _MODULE.candidates
quarantine = _MODULE.quarantine
Candidate = _MODULE.Candidate


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_only_old_unreferenced_mock_records_are_candidates(tmp_path: Path) -> None:
    root = tmp_path / "media"
    _write(root / "v3_projects/project_abc/project.json", {"job_ids": ["job_keep"]})
    _write(root / "v3_jobs/job_keep.json", {"job_id": "job_keep", "provider": "openai_gpt_image"})
    _write(root / "v3_jobs/job_mock.json", {"job_id": "job_mock", "provider": "v3_mock_contract_fixture"})
    _write(root / "v3_outputs/v3_output_aaaaaaaaaaaaaaaaaaaa/output.json", {
        "output_id": "v3_output_aaaaaaaaaaaaaaaaaaaa",
        "job_id": "job_mock",
        "provider": "v3_mock_contract_fixture",
    })
    inventory = build_inventory(root)
    old = datetime.now(timezone.utc) - timedelta(days=45)
    for path in (root / "v3_jobs/job_mock.json", root / "v3_outputs/v3_output_aaaaaaaaaaaaaaaaaaaa/output.json"):
        path.touch()
        os.utime(path, (old.timestamp(), old.timestamp()))
    items = candidates(root, inventory, retention_days=30, now=datetime.now(timezone.utc))
    assert {item.kind for item in items} == {"mock_job", "mock_output"}


def test_quarantine_is_reversible_and_stays_under_root(tmp_path: Path) -> None:
    root = tmp_path / "media"
    candidate = root / "share_cache/old.bin"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"old")
    now = datetime.now(timezone.utc)
    batch = quarantine(root, [Candidate("cache", candidate, 3, "expired_share_cache")], now=now)
    assert batch is not None
    assert not candidate.exists()
    assert (batch / "share_cache/old.bin").read_bytes() == b"old"
    manifest = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    assert manifest[0]["reason"] == "expired_share_cache"
