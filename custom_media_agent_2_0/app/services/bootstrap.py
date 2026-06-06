from __future__ import annotations

from app.providers.evolinkai import EVOLINKAI_PROVIDER_ID, build_evolinkai_provider
from app.repositories import repository
from app.services.case_index_store import load_case_index
from app.services.resource_sync import sync_resource_provider


def bootstrap_v2_repository(seed_cases: bool = True, use_persisted_index: bool = True) -> None:
    if not repository.get_provider(EVOLINKAI_PROVIDER_ID):
        repository.upsert_provider(build_evolinkai_provider())
    if seed_cases and not repository.list_cases():
        if use_persisted_index:
            persisted_cases = load_case_index()
            if persisted_cases:
                repository.replace_cases_for_provider(EVOLINKAI_PROVIDER_ID, persisted_cases)
                provider = repository.get_provider(EVOLINKAI_PROVIDER_ID)
                if provider:
                    repository.upsert_provider(
                        provider.model_copy(update={"active_index_version": persisted_cases[0].index_version})
                    )
                return
        sync_resource_provider(EVOLINKAI_PROVIDER_ID, mode="seed")
