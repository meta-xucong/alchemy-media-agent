from app.repositories.memory import InMemoryV2Repository
from app.schemas import PromptCase
import app.services.bootstrap as bootstrap


def _case(case_id="case", active=True):
    return PromptCase(case_id=case_id, provider_id="fixture", index_version="fixture-v1",
                      title="Fixture", category="fixture", source_url="https://example.test",
                      raw_prompt="Fixture", is_active=active)


def test_active_case_exists_without_decoding_catalog(tmp_path, monkeypatch):
    repo = InMemoryV2Repository(tmp_path / "repository.sqlite3")
    repo.upsert_cases(_case(f"case-{index}") for index in range(1000))
    monkeypatch.setattr(bootstrap, "repository", repo)
    monkeypatch.setattr(repo, "get_provider", lambda _: object())

    def forbidden(*args, **kwargs):
        raise AssertionError("Warm bootstrap must not decode or list the catalog")

    monkeypatch.setattr(repo, "list_cases", forbidden)
    monkeypatch.setattr(repo.prompt_cases, "_validator", forbidden)
    monkeypatch.setattr(bootstrap, "load_case_index", forbidden)
    monkeypatch.setattr(bootstrap, "sync_resource_provider", forbidden)
    bootstrap.bootstrap_v2_repository()


def test_inactive_only_repository_retains_persisted_index_recovery(tmp_path, monkeypatch):
    repo = InMemoryV2Repository(tmp_path / "repository.sqlite3")
    repo.upsert_cases([_case("inactive", active=False)])
    monkeypatch.setattr(bootstrap, "repository", repo)
    monkeypatch.setattr(repo, "get_provider", lambda _: None)
    monkeypatch.setattr(repo, "upsert_provider", lambda provider: provider)
    monkeypatch.setattr(bootstrap, "load_case_index", lambda: [_case("recovered")])
    bootstrap.bootstrap_v2_repository()
    assert repo.get_case("recovered") == _case("recovered")


def test_empty_repository_preserves_seed_and_seed_disabled_paths(tmp_path, monkeypatch):
    repo = InMemoryV2Repository(tmp_path / "repository.sqlite3")
    monkeypatch.setattr(bootstrap, "repository", repo)
    monkeypatch.setattr(repo, "get_provider", lambda _: object())
    monkeypatch.setattr(bootstrap, "load_case_index", lambda: [])
    calls = []
    monkeypatch.setattr(bootstrap, "sync_resource_provider", lambda provider, **kw: calls.append(kw))
    bootstrap.bootstrap_v2_repository(seed_cases=False)
    assert calls == []
    bootstrap.bootstrap_v2_repository()
    assert calls == [{"mode": "seed"}]


def test_warm_case_detail_decodes_only_the_requested_case(tmp_path, monkeypatch):
    import app.services.case_intelligence as intelligence

    repo = InMemoryV2Repository(tmp_path / "repository.sqlite3")
    repo.upsert_cases(_case(f"case-{index}") for index in range(1000))
    monkeypatch.setattr(bootstrap, "repository", repo)
    monkeypatch.setattr(intelligence, "repository", repo)
    monkeypatch.setattr(repo, "get_provider", lambda _: object())
    original = repo.prompt_cases._validator
    decoded = []

    def validate(payload):
        decoded.append(1)
        return original(payload)

    monkeypatch.setattr(repo.prompt_cases, "_validator", validate)
    assert intelligence.get_prompt_case("case-500") == _case("case-500")
    assert decoded == [1]
