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


@pytest.mark.parametrize("flag,value", [("--outputs-per-job", 0), ("--outputs-per-job", 50001),
    ("--job-shared-bytes", -1), ("--job-shared-bytes", 65537)])
def test_fanout_and_shared_payload_are_bounded(flag, value):
    result = subprocess.run([sys.executable, str(SCRIPT), flag, str(value)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "outputs-per-job <= 50000" in result.stderr


@pytest.mark.parametrize("mode", ["cold", "prepare", "hot"])
def test_all_measurement_workers_refuse_mismatched_fanout_marker(tmp_path, mode):
    import json
    (tmp_path / ".history-read-fixture.json").write_text(json.dumps({"schema": 2,
        "surface": "v1", "rows": 10, "owner_mode": "balanced", "outputs_per_job": 1,
        "job_shared_bytes": 0}), encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), "--worker", mode, "--surface", "v1",
        "--rows", "10", "--fixture", str(tmp_path), "--outputs-per-job", "10",
        "--result", str(tmp_path / "report.json")], capture_output=True, text=True)
    assert result.returncode != 0
    assert "matching synthetic-fixture marker" in result.stderr
    assert not (tmp_path / "report.json").exists()


def test_fanout_groups_job_and_session_and_preserves_truth_order():
    spec = importlib.util.spec_from_file_location("history_benchmark_fanout_test", SCRIPT)
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    args = SimpleNamespace(rows=8, outputs_per_job=4, owner_mode="balanced", surface="v1",
        include_mock=False, session_id="ses_benchmark_1", offset=0, limit=50)
    assert benchmark.job_id(3, args) != benchmark.job_id(4, args)
    assert benchmark.job_id(4, args) == benchmark.job_id(7, args)
    assert benchmark.expected(args, 42) == {"total": 2,
        "ids": [benchmark.output_id(6), benchmark.output_id(4)]}


def test_storage_census_counts_payload_bytes_without_reading_images(tmp_path):
    code = '''
import importlib.util
from pathlib import Path
import sqlite3
import sys
spec = importlib.util.spec_from_file_location("census_test", sys.argv[1])
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
root = Path(sys.argv[2])
image = root / "v1/generated_images/job_benchmark000000000000/out_benchmark000000000000.png"
image.parent.mkdir(parents=True)
image.write_bytes(bench.PNG_SHAPED_STUB)
database = root / "v1/repository.sqlite3"
with sqlite3.connect(database) as connection:
    connection.execute("CREATE TABLE v1_read_sources(payload TEXT)")
    connection.execute("INSERT INTO v1_read_sources VALUES(?)", ("é",))
attempts = bench.reject_generated_content_reads(root)
observed = bench.fixture_storage(root)
assert observed["bytes_by_suffix"][".png"] == 68
assert observed["databases"][0]["tables"]["v1_read_sources"] == {"rows": 1, "payload_bytes": 2}
assert attempts == {"generated_file_content_opens": 0, "image_codec_calls": 0}
'''
    result = subprocess.run([sys.executable, "-c", code, str(SCRIPT), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_network_guard_rejects_connection_attempts_before_io(tmp_path):
    code = '''
import importlib.util
import socket
import sys
spec = importlib.util.spec_from_file_location("network_guard_test", sys.argv[1])
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
bench.forbid_network_and_dotenv()
for operation in (lambda: socket.create_connection(("127.0.0.1", 1)),
                  lambda: socket.socket().connect(("127.0.0.1", 1)),
                  lambda: socket.socket().connect_ex(("127.0.0.1", 1))):
    try:
        operation()
    except AssertionError as exc:
        assert "attempted network access" in str(exc)
    else:
        raise AssertionError("Network connection was not rejected")
'''
    result = subprocess.run([sys.executable, "-c", code, str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_request_guard_blocks_source_reads_and_directory_scans(tmp_path):
    code = '''
import importlib.util
import os
from pathlib import Path
import sys
spec = importlib.util.spec_from_file_location("source_guard_test", sys.argv[1])
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
root = Path(sys.argv[2])
source = root / "image_history.jsonl"
source.write_text("synthetic", encoding="utf-8")
attempts, active = bench.reject_request_source_scans(root)
assert source.stat().st_size == 9
for operation in (source.read_text, lambda: os.scandir(root)):
    try:
        operation()
    except AssertionError:
        pass
    else:
        raise AssertionError("Request source scan was allowed")
assert attempts == {"legacy_source_content_opens": 1, "directory_scan_attempts": 1}
active[0] = False
assert source.read_text() == "synthetic"
assert len(bench.fixture_storage(root)["databases"]) == 0
'''
    result = subprocess.run([sys.executable, "-c", code, str(SCRIPT), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
