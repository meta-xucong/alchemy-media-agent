from concurrent.futures import ThreadPoolExecutor

from app.services.alchemy_lab_style_search import _BoundedObjectCache


def test_lab_style_derived_cache_has_dual_budget():
    cache = _BoundedObjectCache(max_entries=2, max_bytes=2500, max_entry_bytes=1500)
    cache["one"] = CounterLike({"a": 1, "b": 2})
    cache["two"] = {"tokens": {str(index) for index in range(30)}}
    cache["three"] = "new value"
    cache["large"] = "x" * 8000

    assert len(cache) <= 2
    assert "large" not in cache
    assert cache.accounted_bytes <= 2500


def test_lab_style_cache_concurrent_access_keeps_budgets_consistent():
    cache = _BoundedObjectCache(max_entries=16, max_bytes=5000, max_entry_bytes=2000)

    def exercise(worker: int):
        for index in range(300):
            key = str((worker * 17 + index) % 24)
            cache[key] = {"worker": worker, "value": index}
            cache.get(str((worker * 13 + index) % 24))

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(exercise, range(8)))

    assert len(cache) <= 16
    assert cache.accounted_bytes <= 5000


class CounterLike(dict):
    pass
