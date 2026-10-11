from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="The standalone benchmark uses Linux process metrics")
SCRIPT = Path(__file__).resolve().parents[1] / "scripts/benchmark_history_reads.py"


@pytest.mark.parametrize("interval", [0, 10001])
def test_diagnostic_vm_interval_is_bounded(interval):
    result = subprocess.run([sys.executable, str(SCRIPT), "--vm-step-interval", str(interval)],
        capture_output=True, text=True)
    assert result.returncode != 0
    assert "1 <= vm-step-interval <= 10000" in result.stderr


def test_seed_worker_refuses_existing_directory_without_touching_source(tmp_path):
    fixture = tmp_path / "existing"
    fixture.mkdir()
    source = fixture / "outputs.jsonl"
    source.write_text("existing data must not be touched", encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), "--worker", "seed", "--surface", "v1",
        "--rows", "1", "--fixture", str(fixture), "--result", str(tmp_path / "report.json")],
        capture_output=True, text=True)
    assert result.returncode != 0
    assert source.read_text(encoding="utf-8") == "existing data must not be touched"
    assert not (fixture / ".history-read-fixture.json").exists()


def test_read_worker_refuses_unmarked_directory(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT), "--worker", "hot", "--surface", "v1",
        "--rows", "1", "--fixture", str(tmp_path), "--result", str(tmp_path / "report.json")],
        capture_output=True, text=True)
    assert result.returncode != 0
    assert "synthetic-fixture marker" in result.stderr
    assert not (tmp_path / "report.json").exists()


def test_old_owner_lab_fixture_keeps_oldest_record_nonmock():
    spec = importlib.util.spec_from_file_location("history_benchmark_test", SCRIPT)
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    args = SimpleNamespace(rows=50000, owner_mode="old-owner", surface="lab", include_mock=False,
        session_id=None, offset=0, limit=50)
    assert benchmark.is_mock(0, "old-owner") is False
    assert benchmark.expected(args, 42) == {"total": 1, "ids": [benchmark.output_id(0)]}


def test_fixture_ids_match_real_filesystem_recovery_contract():
    import re
    spec = importlib.util.spec_from_file_location("history_benchmark_ids_test", SCRIPT)
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    for index in (0, 99, 49999):
        assert re.fullmatch(r"out_[A-Za-z0-9]{12,}", benchmark.output_id(index))
        assert re.fullmatch(r"job_[A-Za-z0-9]{12,}", f"job_benchmark{index:012d}")


def test_generated_content_guard_rejects_bytes_but_allows_metadata(tmp_path):
    code = '''
import importlib.util
from pathlib import Path
import sys
spec = importlib.util.spec_from_file_location("guard_test", sys.argv[1])
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
root = Path(sys.argv[2])
image = root / "v1/generated_images/job_benchmark000000000000/out_benchmark000000000000.png"
image.parent.mkdir(parents=True)
image.write_bytes(bench.PNG_SHAPED_STUB)
attempts = bench.reject_generated_content_reads(root)
assert image.stat().st_size == 68
try:
    image.read_bytes()
except AssertionError:
    pass
else:
    raise AssertionError("Generated contents were readable")
assert attempts == {"generated_file_content_opens": 1, "image_codec_calls": 0}
'''
    result = subprocess.run([sys.executable, "-c", code, str(SCRIPT), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
