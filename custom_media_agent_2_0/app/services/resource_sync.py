from __future__ import annotations

from typing import Literal

from app.config import settings
from app.providers.evolinkai import EVOLINKAI_PROVIDER_ID, build_evolinkai_provider, load_seed_cases
from app.repositories import repository
from app.repositories.memory import utc_now
from app.schemas import ProviderSyncRun, ResourceProvider
from app.services.case_index_store import save_case_index
from app.services.case_parser import parse_evolinkai_markdown_cases
from app.services.github_archive import fetch_evolinkai_github_cases, fetch_evolinkai_source_version
from app.services.ids import new_id


SyncMode = Literal["auto", "seed", "remote"]


def list_resource_providers() -> list[ResourceProvider]:
    ensure_default_provider()
    return repository.list_providers()


def ensure_default_provider() -> ResourceProvider:
    provider = repository.get_provider(EVOLINKAI_PROVIDER_ID)
    if provider:
        return provider
    return repository.upsert_provider(build_evolinkai_provider())


def sync_resource_provider(provider_id: str, mode: SyncMode = "auto") -> ProviderSyncRun:
    provider = repository.get_provider(provider_id)
    if not provider:
        if provider_id == EVOLINKAI_PROVIDER_ID:
            provider = ensure_default_provider()
        else:
            raise KeyError(f"Unknown resource provider: {provider_id}")

    started_at = utc_now()
    sync_run = ProviderSyncRun(
        sync_run_id=new_id("sync"),
        provider_id=provider.provider_id,
        status="fetching",
        started_at=started_at,
    )
    repository.save_sync_run(sync_run)

    if provider.provider_id != EVOLINKAI_PROVIDER_ID:
        failed = sync_run.model_copy(
            update={
                "status": "failed",
                "finished_at": utc_now(),
                "error": {
                    "error_code": "provider_not_supported",
                    "message": f"Provider {provider.provider_id} does not have an adapter yet.",
                    "retryable": False,
                },
            }
        )
        return repository.save_sync_run(failed)

    try:
        if _should_use_remote(mode):
            source_version = fetch_evolinkai_source_version()
            expected_index_version = f"{provider.provider_id}:{source_version}"
            current_cases = repository.list_cases(active_only=True)
            if provider.active_index_version == expected_index_version and current_cases:
                finished_at = utc_now()
                completed = sync_run.model_copy(
                    update={
                        "status": "completed",
                        "source_version": source_version,
                        "finished_at": finished_at,
                        "stats": {
                            "cases_published": len(current_cases),
                            "adapter": "github_commit_check",
                            "index_version": expected_index_version,
                            "case_index_path": str(settings.case_index_path),
                            "skipped": True,
                            "skip_reason": "local index already matches GitHub main commit",
                        },
                    }
                )
                repository.upsert_provider(provider.model_copy(update={"last_sync_at": finished_at}))
                return repository.save_sync_run(completed)
        source_version, cases, adapter = _load_provider_cases(mode)
    except Exception as exc:
        failed = sync_run.model_copy(
            update={
                "status": "failed",
                "finished_at": utc_now(),
                "error": {
                    "error_code": "provider_sync_failed",
                    "message": str(exc),
                    "retryable": True,
                    "safe_fallback": "Keep the previously active case index.",
                },
            }
        )
        return repository.save_sync_run(failed)

    if not cases:
        failed = sync_run.model_copy(
            update={
                "status": "failed",
                "finished_at": utc_now(),
                "error": {
                    "error_code": "empty_case_index",
                    "message": "Provider sync produced no PromptCase records.",
                    "retryable": True,
                    "safe_fallback": "Keep the previously active case index.",
                },
            }
        )
        return repository.save_sync_run(failed)

    repository.replace_cases_for_provider(provider.provider_id, cases)
    index_path = save_case_index(cases)
    finished_at = utc_now()
    updated_provider = provider.model_copy(
        update={
            "last_sync_at": finished_at,
            "active_index_version": cases[0].index_version if cases else None,
        }
    )
    repository.upsert_provider(updated_provider)
    completed = sync_run.model_copy(
        update={
            "status": "completed",
            "source_version": source_version,
            "finished_at": finished_at,
            "stats": {
                "cases_published": len(cases),
                "adapter": adapter,
                "index_version": cases[0].index_version if cases else None,
                "case_index_path": str(index_path),
            },
        }
    )
    return repository.save_sync_run(completed)


def get_sync_run(sync_run_id: str) -> ProviderSyncRun | None:
    return repository.get_sync_run(sync_run_id)


def _load_provider_cases(mode: SyncMode) -> tuple[str, list, str]:
    resolved_mode = mode
    if mode == "auto":
        resolved_mode = "remote" if settings.enable_remote_github_sync else "seed"

    if resolved_mode == "remote":
        source_version, documents = fetch_evolinkai_github_cases()
        cases = parse_evolinkai_markdown_cases(documents, source_version=source_version)
        return source_version, cases, "github_archive"

    source_version, cases = load_seed_cases()
    return source_version, cases, "seed_snapshot"


def _should_use_remote(mode: SyncMode) -> bool:
    if mode == "remote":
        return True
    return mode == "auto" and settings.enable_remote_github_sync
