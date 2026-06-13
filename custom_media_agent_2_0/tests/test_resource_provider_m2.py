from __future__ import annotations

import asyncio

from app.providers.evolinkai import load_seed_cases
from app.config import settings
from app.providers.evolinkai import EVOLINKAI_PROVIDER_ID, build_evolinkai_provider
from app.repositories import repository
from app.services.bootstrap import bootstrap_v2_repository
from app.services.case_thumbnail_prewarm import case_preview_asset_path, prewarm_case_thumbnails
from app.services.case_index_store import load_case_index, save_case_index
from app.services.case_preview_urls import normalize_case_preview_url
from app.services.github_source import github_archive_url, github_blob_url, github_commit_api_url
import app.services.resource_sync as resource_sync
from app.services.resource_sync_scheduler import ResourceSyncScheduler
from app.services.case_parser import MarkdownCaseDocument, parse_evolinkai_markdown_cases


def test_markdown_case_parser_handles_repo_heading_and_prompt() -> None:
    markdown = """
# Example

### Case 113: [E-commerce Main Image - Luxury Amber Perfume Ad](https://x.com/example/status/1) (by [@x](https://x.com/x))

| Output |
| :----: |
| <img src="https://example.com/output.jpg" width="300" alt="Output image"> |

**Prompt:**

```
A luxurious cinematic product photograph of a classic rectangular perfume bottle, centered slightly to the right, dramatic warm lighting, premium commercial ad, photorealistic, high contrast, refined typography, no watermark.
```
"""
    cases = parse_evolinkai_markdown_cases(
        [MarkdownCaseDocument(path="cases/ecommerce.md", text=markdown)],
        source_version="test-sha",
    )
    assert len(cases) == 1
    case = cases[0]
    assert case.category == "ecommerce"
    assert case.title == "E-commerce Main Image - Luxury Amber Perfume Ad"
    assert case.preview_url == "https://example.com/output.jpg"
    assert "premium" in case.style_tags
    assert "ecommerce" in case.use_case_tags
    assert case.prompt_atoms["subject"]
    assert case.index_version.endswith("test-sha")


def test_markdown_case_parser_handles_markdown_image_preview() -> None:
    markdown = """
# Example

### Case 100: [Action Storyboard Sheet](https://x.com/example/status/2) (by [@x](https://x.com/x))

![Action Storyboard Sheet](../../images/comparison_case100/output.jpg)

**Prompt:**
```
Create a compact storyboard sheet with high-speed action readability and cinematic panel flow.
```
"""
    cases = parse_evolinkai_markdown_cases(
        [MarkdownCaseDocument(path="cases/comparison.md", text=markdown)],
        source_version="test-sha",
    )

    assert len(cases) == 1
    assert cases[0].preview_url == "/api/v2/case-thumbnails/images/comparison_case100/output.jpg"


def test_markdown_case_parser_normalizes_raw_github_preview_to_local_thumbnail() -> None:
    markdown = """
# Example

### Case 147: [Editorial Osaka Six Sweatshirt Ad](https://x.com/example/status/3) (by [@x](https://x.com/x))

| Output |
| :----: |
| <img src="https://raw.githubusercontent.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts/main/images/poster_case147/output.jpg" width="300" alt="Output image"> |

**Prompt:**
```
Create a clean editorial fashion advertisement poster with a pale studio background and bold typography.
```
"""
    cases = parse_evolinkai_markdown_cases(
        [MarkdownCaseDocument(path="cases/poster.md", text=markdown)],
        source_version="test-sha",
    )

    assert len(cases) == 1
    assert cases[0].preview_url == "/api/v2/case-thumbnails/images/poster_case147/output.jpg"


def test_configured_github_source_builds_fork_urls(monkeypatch) -> None:
    object.__setattr__(
        settings,
        "github_provider_source_uri",
        "https://github.com/meta-xucong/awesome-gpt-image-2-API-and-Prompts",
    )
    try:
        assert (
            github_archive_url()
            == "https://github.com/meta-xucong/awesome-gpt-image-2-API-and-Prompts/archive/refs/heads/main.zip"
        )
        assert (
            github_commit_api_url()
            == "https://api.github.com/repos/meta-xucong/awesome-gpt-image-2-API-and-Prompts/commits/main"
        )
        assert (
            github_blob_url("cases/poster.md")
            == "https://github.com/meta-xucong/awesome-gpt-image-2-API-and-Prompts/blob/main/cases/poster.md"
        )
    finally:
        object.__setattr__(
            settings,
            "github_provider_source_uri",
            "https://github.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts",
        )


def test_preview_normalizer_accepts_configured_fork_and_original_repo() -> None:
    object.__setattr__(
        settings,
        "github_provider_source_uri",
        "https://github.com/meta-xucong/awesome-gpt-image-2-API-and-Prompts",
    )
    try:
        assert (
            normalize_case_preview_url(
                "https://raw.githubusercontent.com/meta-xucong/awesome-gpt-image-2-API-and-Prompts/main/images/poster_case147/output.jpg"
            )
            == "/api/v2/case-thumbnails/images/poster_case147/output.jpg"
        )
        assert (
            normalize_case_preview_url(
                "https://raw.githubusercontent.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts/main/images/poster_case147/output.jpg"
            )
            == "/api/v2/case-thumbnails/images/poster_case147/output.jpg"
        )
    finally:
        object.__setattr__(
            settings,
            "github_provider_source_uri",
            "https://github.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts",
        )


def test_case_index_store_roundtrip(tmp_path) -> None:
    _, cases = load_seed_cases()
    index_path = tmp_path / "case_index.json"
    save_case_index(cases, path=index_path)
    loaded = load_case_index(path=index_path)
    assert len(loaded) == len(cases)
    assert loaded[0].case_id == cases[0].case_id
    assert loaded[0].license_policy.raw_image_final_use_allowed is False


def test_case_index_store_normalizes_legacy_raw_github_previews(tmp_path) -> None:
    _, cases = load_seed_cases()
    index_path = tmp_path / "case_index.json"
    legacy_case = cases[0].model_copy(
        update={
            "preview_url": "https://raw.githubusercontent.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts/main/images/poster_case147/output.jpg"
        }
    )
    save_case_index([legacy_case], path=index_path)

    loaded = load_case_index(path=index_path)

    assert loaded[0].preview_url == "/api/v2/case-thumbnails/images/poster_case147/output.jpg"


def test_bootstrap_can_reload_persisted_case_index(tmp_path) -> None:
    _, cases = load_seed_cases()
    index_path = tmp_path / "case_index.json"
    save_case_index(cases, path=index_path)

    original_path = settings.case_index_path
    object.__setattr__(settings, "case_index_path", index_path)
    try:
        repository.reset()
        bootstrap_v2_repository(seed_cases=True, use_persisted_index=True)
        loaded_cases = repository.list_cases()
        provider = repository.get_provider(EVOLINKAI_PROVIDER_ID)
    finally:
        object.__setattr__(settings, "case_index_path", original_path)

    assert len(loaded_cases) == len(cases)
    assert provider is not None
    assert provider.active_index_version == cases[0].index_version


def test_remote_sync_skips_archive_download_when_local_index_is_current(monkeypatch) -> None:
    repository.reset()
    _, seed_cases = load_seed_cases()
    expected_source_version = "github-same123"
    expected_index_version = f"{EVOLINKAI_PROVIDER_ID}:{expected_source_version}"
    current_cases = [
        case.model_copy(update={"index_version": expected_index_version, "preview_url": "/api/v2/case-thumbnails/images/current/output.jpg"})
        for case in seed_cases
    ]
    repository.upsert_provider(build_evolinkai_provider().model_copy(update={"active_index_version": expected_index_version}))
    repository.replace_cases_for_provider(EVOLINKAI_PROVIDER_ID, current_cases)

    monkeypatch.setattr(resource_sync, "fetch_evolinkai_source_version", lambda: expected_source_version)

    def fail_archive_download():
        raise AssertionError("archive download should be skipped when commit already matches")

    monkeypatch.setattr(resource_sync, "fetch_evolinkai_github_cases", fail_archive_download)

    sync = resource_sync.sync_resource_provider(EVOLINKAI_PROVIDER_ID, mode="remote")

    assert sync.status == "completed"
    assert sync.stats["skipped"] is True
    assert sync.stats["adapter"] == "github_commit_check"
    assert sync.stats["cases_published"] == len(current_cases)


def test_remote_sync_rebuilds_current_index_when_previews_are_missing(monkeypatch) -> None:
    repository.reset()
    _, seed_cases = load_seed_cases()
    expected_source_version = "github-same123"
    expected_index_version = f"{EVOLINKAI_PROVIDER_ID}:{expected_source_version}"
    current_cases = [case.model_copy(update={"index_version": expected_index_version, "preview_url": None}) for case in seed_cases]
    rebuilt_cases = [
        case.model_copy(update={"index_version": expected_index_version, "preview_url": "../images/fixed/output.jpg"})
        for case in seed_cases
    ]
    repository.upsert_provider(build_evolinkai_provider().model_copy(update={"active_index_version": expected_index_version}))
    repository.replace_cases_for_provider(EVOLINKAI_PROVIDER_ID, current_cases)

    monkeypatch.setattr(resource_sync, "fetch_evolinkai_source_version", lambda: expected_source_version)
    monkeypatch.setattr(
        resource_sync,
        "fetch_evolinkai_github_cases",
        lambda: (expected_source_version, [MarkdownCaseDocument(path="cases/poster.md", text="unused")]),
    )
    monkeypatch.setattr(resource_sync, "parse_evolinkai_markdown_cases", lambda documents, source_version: rebuilt_cases)

    sync = resource_sync.sync_resource_provider(EVOLINKAI_PROVIDER_ID, mode="remote")

    assert sync.status == "completed"
    assert sync.stats.get("skipped") is not True
    assert all(case.preview_url for case in repository.list_cases(active_only=True))


def test_remote_sync_rebuilds_current_index_when_previews_are_repo_relative(monkeypatch) -> None:
    repository.reset()
    _, seed_cases = load_seed_cases()
    expected_source_version = "github-same123"
    expected_index_version = f"{EVOLINKAI_PROVIDER_ID}:{expected_source_version}"
    current_cases = [
        case.model_copy(update={"index_version": expected_index_version, "preview_url": "../images/current/output.jpg"})
        for case in seed_cases
    ]
    rebuilt_cases = [
        case.model_copy(update={"index_version": expected_index_version, "preview_url": "/api/v2/case-thumbnails/images/fixed/output.jpg"})
        for case in seed_cases
    ]
    repository.upsert_provider(build_evolinkai_provider().model_copy(update={"active_index_version": expected_index_version}))
    repository.replace_cases_for_provider(EVOLINKAI_PROVIDER_ID, current_cases)

    monkeypatch.setattr(resource_sync, "fetch_evolinkai_source_version", lambda: expected_source_version)
    monkeypatch.setattr(
        resource_sync,
        "fetch_evolinkai_github_cases",
        lambda: (expected_source_version, [MarkdownCaseDocument(path="cases/poster.md", text="unused")]),
    )
    monkeypatch.setattr(resource_sync, "parse_evolinkai_markdown_cases", lambda documents, source_version: rebuilt_cases)

    sync = resource_sync.sync_resource_provider(EVOLINKAI_PROVIDER_ID, mode="remote")

    assert sync.status == "completed"
    assert sync.stats.get("skipped") is not True
    assert all(case.preview_url.startswith("/api/v2/case-thumbnails/") for case in repository.list_cases(active_only=True))


def test_resource_sync_scheduler_uses_configured_interval(monkeypatch) -> None:
    object.__setattr__(settings, "resource_sync_interval_minutes", 7)
    scheduler = ResourceSyncScheduler()
    intervals = []

    async def fake_wait_for(awaitable, timeout):
        intervals.append(timeout)
        stop_event.set()
        return await awaitable

    stop_event = asyncio.Event()
    monkeypatch.setattr("app.services.resource_sync_scheduler.asyncio.wait_for", fake_wait_for)

    asyncio.run(scheduler.run_forever(stop_event))

    assert intervals == [420]


def test_case_thumbnail_prewarm_extracts_asset_paths() -> None:
    assert (
        case_preview_asset_path("/api/v2/case-thumbnails/images/poster_case147/output.jpg")
        == "images/poster_case147/output.jpg"
    )
    assert (
        case_preview_asset_path("/api/v2/case-thumbnails/grid/images/poster_case147/output.jpg")
        == "images/poster_case147/output.jpg"
    )
    assert case_preview_asset_path("../images/poster_case147/output.jpg") == "images/poster_case147/output.jpg"
    assert (
        case_preview_asset_path(
            "https://raw.githubusercontent.com/meta-xucong/awesome-gpt-image-2-API-and-Prompts/main/images/poster_case147/output.jpg"
        )
        == "images/poster_case147/output.jpg"
    )


def test_case_thumbnail_prewarm_uses_current_cases(monkeypatch) -> None:
    repository.reset()
    _, seed_cases = load_seed_cases()
    current_cases = [
        seed_cases[0].model_copy(update={"preview_url": "/api/v2/case-thumbnails/images/poster_case147/output.jpg"}),
        seed_cases[1].model_copy(update={"preview_url": "/api/v2/case-thumbnails/grid/images/poster_case147/output.jpg"}),
        seed_cases[2].model_copy(update={"preview_url": None}),
    ]
    repository.upsert_provider(build_evolinkai_provider().model_copy(update={"active_index_version": current_cases[0].index_version}))
    repository.replace_cases_for_provider(EVOLINKAI_PROVIDER_ID, current_cases)
    calls = []

    def fake_read_case_thumbnail(asset_path: str, variant: str = "grid"):
        calls.append((asset_path, variant))
        return b"thumb", "image/webp"

    monkeypatch.setattr("app.services.case_thumbnail_prewarm.bootstrap_v2_repository", lambda seed_cases=True: None)
    monkeypatch.setattr("app.services.case_thumbnail_prewarm.read_case_thumbnail", fake_read_case_thumbnail)

    result = prewarm_case_thumbnails(variant="grid", limit=0)

    assert result.succeeded == 1
    assert result.failed == 0
    assert result.skipped == 2
    assert calls == [("images/poster_case147/output.jpg", "grid")]
