from __future__ import annotations

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
