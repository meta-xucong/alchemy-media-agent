"""Worker sizing respects operator settings and container CPU limits."""
from __future__ import annotations

import pytest

from app.browse_compute import (
    BoundedBrowseCompute,
    effective_cpu_count,
    resolve_browse_compute_workers,
)


@pytest.mark.parametrize(
    ("raw_value", "available_cpus", "expected"),
    [
        (None, 2, 2),
        ("", 8, 2),
        ("0", 8, 0),
        ("4", 8, 4),
        ("8", 4, 4),
        (None, 1, 1),
        ("invalid", 8, 2),
        ("-1", 8, 2),
    ],
)
def test_worker_setting_scales_to_effective_cpu_limit(raw_value, available_cpus, expected):
    assert resolve_browse_compute_workers(
        raw_value, available_cpus=available_cpus
    ) == expected


def test_effective_cpu_count_uses_cgroup_v2_quota_and_affinity(tmp_path):
    (tmp_path / "cpu.max").write_text("250000 100000\n", encoding="ascii")
    assert effective_cpu_count(affinity_count=8, cgroup_root=tmp_path) == 2


def test_effective_cpu_count_uses_cgroup_v1_quota_when_v2_is_absent(tmp_path):
    cpu_dir = tmp_path / "cpu"
    cpu_dir.mkdir()
    (cpu_dir / "cpu.cfs_quota_us").write_text("350000\n", encoding="ascii")
    (cpu_dir / "cpu.cfs_period_us").write_text("100000\n", encoding="ascii")
    assert effective_cpu_count(affinity_count=8, cgroup_root=tmp_path) == 3


def test_effective_cpu_count_ignores_unlimited_or_invalid_quota(tmp_path):
    (tmp_path / "cpu.max").write_text("max 100000\n", encoding="ascii")
    assert effective_cpu_count(affinity_count=6, cgroup_root=tmp_path) == 6
    (tmp_path / "cpu.max").write_text("invalid\n", encoding="ascii")
    assert effective_cpu_count(affinity_count=6, cgroup_root=tmp_path) == 6


def test_browse_compute_accepts_more_than_two_workers_without_starting_children():
    pool = BoundedBrowseCompute(4)
    try:
        assert pool.workers == 4
        assert pool.max_pending == 5
    finally:
        pool.shutdown()
