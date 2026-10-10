from __future__ import annotations

import os

# Keep test imports offline. ONNX Runtime can initialize native telemetry before
# its Python disable_telemetry_events() API is callable, so set the process-level
# opt-out before importing pytest or any application/SDK module. CI and local
# test commands also set these variables before the interpreter starts.
os.environ["ORT_DISABLE_TELEMETRY"] = "1"
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"

import pytest


@pytest.fixture(autouse=True)
def isolate_v2_repository_database(tmp_path):
    """Keep repository.reset() scoped to a per-test SQLite database."""
    from app.config import settings

    original_data_dir = settings.data_dir
    object.__setattr__(settings, "data_dir", tmp_path)
    try:
        yield
    finally:
        object.__setattr__(settings, "data_dir", original_data_dir)
