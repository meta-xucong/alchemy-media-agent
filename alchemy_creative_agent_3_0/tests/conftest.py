"""Pytest collection guards for V3-owned test artifacts."""

from __future__ import annotations

from pathlib import Path
import pytest


_GENERATED_TEST_DIR_PREFIXES = ("_runtime_", "_tmp_")
_GENERATED_TEST_DIR_NAMES = {"__pycache__"}


@pytest.fixture(autouse=True)
def _disable_live_v3_vision_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep ordinary tests offline; vision tests may opt in or inject a fake."""
    monkeypatch.setenv("V3_VISION_INSPECTION_ENABLED", "false")


def pytest_ignore_collect(collection_path: Path, config: object) -> bool:
    """Avoid descending into generated runtime and legacy temp folders."""
    if not collection_path.is_dir():
        return False
    name = collection_path.name
    return name in _GENERATED_TEST_DIR_NAMES or name.startswith(_GENERATED_TEST_DIR_PREFIXES)
