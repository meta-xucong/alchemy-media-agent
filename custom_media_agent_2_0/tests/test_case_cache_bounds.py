from concurrent.futures import ThreadPoolExecutor

from app.services.case_intelligence import _BoundedObjectCache


def test_case_derived_cache_enforces_entry_byte_and_lru_limits():
    cache = _BoundedObjectCache(max_entries=2, max_bytes=10000, max_entry_bytes=6000)
    cache["first"] = {"tokens": {str(index) for index in range(20)}}
    cache["second"] = {"tokens": {str(index) for index in range(20, 40)}}
    assert cache.get("first")
    cache["third"] = {"tokens": {str(index) for index in range(40, 60)}}
    cache["too-large"] = "x" * 10000

    assert len(cache) <= 2
    assert "first" in cache
    assert "second" not in cache
    assert "too-large" not in cache
    assert cache.accounted_bytes <= 10000


def test_case_cache_concurrent_access_keeps_budgets_consistent():
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
