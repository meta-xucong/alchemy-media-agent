from __future__ import annotations

from app.providers.evolinkai import load_seed_cases
from app.config import settings
from app.providers.evolinkai import EVOLINKAI_PROVIDER_ID, build_evolinkai_provider
from app.repositories import repository
from app.services.bootstrap import bootstrap_v2_repository
from app.services.case_index_store import load_case_index, save_case_index
import app.services.resource_sync as resource_sync
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


def test_case_index_store_roundtrip(tmp_path) -> None:
    _, cases = load_seed_cases()
    index_path = tmp_path / "case_index.json"
    save_case_index(cases, path=index_path)
    loaded = load_case_index(path=index_path)
    assert len(loaded) == len(cases)
    assert loaded[0].case_id == cases[0].case_id
    assert loaded[0].license_policy.raw_image_final_use_allowed is False


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
    current_cases = [case.model_copy(update={"index_version": expected_index_version}) for case in seed_cases]
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
