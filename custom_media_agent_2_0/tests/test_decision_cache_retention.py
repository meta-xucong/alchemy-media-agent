from pathlib import Path

from app.config import settings
import app.services.claude_orchestrator as brain


def test_decision_cache_is_bounded_and_legacy_json_is_not_loaded(tmp_path, monkeypatch):
    legacy_path = tmp_path / "claude_orchestrator_cache.json"
    legacy_bytes = b'{"legacy":"do not import"}'
    legacy_path.write_bytes(legacy_bytes)
    object.__setattr__(settings, "claude_orchestrator_cache_path", legacy_path)
    monkeypatch.setattr(brain, "_DECISION_CACHE_MAX_ENTRIES", 8, raising=False)
    monkeypatch.setattr(brain, "_DECISION_CACHE_MAX_BYTES", 16 * 1024, raising=False)
    monkeypatch.setattr(brain, "_DECISION_CACHE_MAX_ENTRY_BYTES", 2 * 1024, raising=False)

    for index in range(12):
        brain._write_cached_decision(
            f"key-{index:02d}",
            {"mode": "smart_enhance", "final_prompt": "x" * 100},
            metadata={"sample": index},
        )
    brain._write_cached_decision("too-large", {"value": "x" * 4096}, metadata={})

    cache = brain._read_cache_store()
    assert len(cache) == 8
    assert "too-large" not in cache
    assert "legacy" not in cache
    assert legacy_path.read_bytes() == legacy_bytes
    assert legacy_path.with_name("claude_orchestrator_cache.sqlite3").exists()
