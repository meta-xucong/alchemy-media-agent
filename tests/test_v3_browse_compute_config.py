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


def test_effective_cpu_count_reads_nested_cgroup_and_stricter_ancestor(tmp_path):
    cgroup_root = tmp_path / "cgroup"
    leaf = cgroup_root / "system.slice" / "alchemy.service" / "api.scope"
    leaf.mkdir(parents=True)
    (cgroup_root / "cpu.max").write_text("600000 100000\n", encoding="ascii")
    (cgroup_root / "system.slice" / "cpu.max").write_text("400000 100000\n", encoding="ascii")
    (cgroup_root / "system.slice" / "alchemy.service" / "cpu.max").write_text(
        "200000 100000\n", encoding="ascii"
    )
    (leaf / "cpu.max").write_text("max 100000\n", encoding="ascii")
    proc_cgroup = tmp_path / "proc-cgroup"
    proc_cgroup.write_text("0::/system.slice/alchemy.service/api.scope\n", encoding="ascii")
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text(
        "42 31 0:26 / /sys/fs/cgroup ro,nosuid - cgroup2 cgroup rw\n",
        encoding="ascii",
    )

    assert effective_cpu_count(
        affinity_count=8,
        cgroup_root=cgroup_root,
        proc_cgroup_path=proc_cgroup,
        mountinfo_path=mountinfo,
    ) == 2


def test_effective_cpu_count_ignores_unrelated_legacy_fallback_when_cgroup_is_mapped(tmp_path):
    cgroup_root = tmp_path / "cgroup"
    service = cgroup_root / "system.slice" / "api.service"
    service.mkdir(parents=True)
    (service / "cpu.max").write_text("400000 100000\n", encoding="ascii")

    # This legacy-looking path is unrelated to the process's mapped cgroup.
    unrelated = cgroup_root / "cpu"
    unrelated.mkdir()
    (unrelated / "cpu.max").write_text("100000 100000\n", encoding="ascii")

    proc_cgroup = tmp_path / "proc-cgroup"
    proc_cgroup.write_text("0::/system.slice/api.service\n", encoding="ascii")
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text(
        "42 31 0:26 / /sys/fs/cgroup ro,nosuid - cgroup2 cgroup rw\n",
        encoding="ascii",
    )

    assert effective_cpu_count(
        affinity_count=8,
        cgroup_root=cgroup_root,
        proc_cgroup_path=proc_cgroup,
        mountinfo_path=mountinfo,
    ) == 4


def test_effective_cpu_count_reads_nested_cgroup_v1_cpu_controller(tmp_path):
    cgroup_root = tmp_path / "cgroup"
    cpu_root = cgroup_root / "cpu,cpuacct"
    leaf = cpu_root / "docker" / "container-id" / "service"
    leaf.mkdir(parents=True)
    (cpu_root / "cpu.cfs_quota_us").write_text("500000\n", encoding="ascii")
    (cpu_root / "cpu.cfs_period_us").write_text("100000\n", encoding="ascii")
    (cpu_root / "docker" / "cpu.cfs_quota_us").write_text("300000\n", encoding="ascii")
    (cpu_root / "docker" / "cpu.cfs_period_us").write_text("100000\n", encoding="ascii")
    (leaf / "cpu.cfs_quota_us").write_text("max\n", encoding="ascii")
    (leaf / "cpu.cfs_period_us").write_text("100000\n", encoding="ascii")
    proc_cgroup = tmp_path / "proc-cgroup"
    proc_cgroup.write_text(
        "5:cpu,cpuacct:/docker/container-id/service\n", encoding="ascii"
    )
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text(
        "42 31 0:27 / /sys/fs/cgroup/cpu,cpuacct rw - cgroup cgroup rw,cpu,cpuacct\n",
        encoding="ascii",
    )

    assert effective_cpu_count(
        affinity_count=8,
        cgroup_root=cgroup_root,
        proc_cgroup_path=proc_cgroup,
        mountinfo_path=mountinfo,
    ) == 3


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
