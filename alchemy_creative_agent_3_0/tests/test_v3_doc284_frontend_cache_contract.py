from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "src_skeleton" / "app" / "static" / "app.js"
MOBILE = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"


def test_desktop_v3_cache_is_account_scoped_and_fail_closed() -> None:
    source = DESKTOP.read_text(encoding="utf-8")

    assert "function v3CacheStorageKey" in source
    assert "function clearV3LocalCaches" in source
    assert "v3ProjectFetchLimit = v3ProjectHomePageSize" in source
    assert "v3State.projects = mergeV3ProjectItems(localItems, []);" not in source
    assert "v3State.imageHistoryLoaded = false;" in source
    assert "loadV3Projects({ silent: false, loadMore: true })" in source
    assert "next_cursor" in source
    assert "has_more" in source


def test_mobile_v3_cache_is_account_scoped_and_output_failure_is_retryable() -> None:
    source = MOBILE.read_text(encoding="utf-8")

    assert "function mobileV3CacheStorageKey" in source
    assert "function clearMobileV3Caches" in source
    assert "mobileV3ProjectFetchLimit = mobileV3ProjectPageSize" in source
    assert "mobileV3State.outputError" in source
    assert "loadMobileV3Projects({ silent: false, loadMore: true })" in source
    assert "next_cursor" in source
    assert "has_more" in source
    assert "mobileV3State.outputsLoaded = true;\n    renderMobileV3ProjectCards();\n    const fallbackCount" not in source
