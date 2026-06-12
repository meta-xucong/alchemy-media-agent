from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, urlparse

from app.config import settings


DEFAULT_GITHUB_PROVIDER_SOURCE_URI = "https://github.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts"
DEFAULT_GITHUB_BRANCH = "main"


@dataclass(frozen=True)
class GitHubRepoSource:
    owner: str
    repo: str
    branch: str = DEFAULT_GITHUB_BRANCH

    @property
    def repo_key(self) -> tuple[str, str]:
        return (self.owner.lower(), self.repo.lower())


def configured_github_source() -> GitHubRepoSource:
    return _parse_source_uri(settings.github_provider_source_uri or DEFAULT_GITHUB_PROVIDER_SOURCE_URI)


def github_archive_url() -> str:
    source = configured_github_source()
    branch = quote(source.branch, safe="/")
    return f"https://github.com/{source.owner}/{source.repo}/archive/refs/heads/{branch}.zip"


def github_commit_api_url() -> str:
    source = configured_github_source()
    branch = quote(source.branch, safe="")
    return f"https://api.github.com/repos/{source.owner}/{source.repo}/commits/{branch}"


def github_blob_url(path: str) -> str:
    source = configured_github_source()
    branch = quote(source.branch, safe="/")
    return f"https://github.com/{source.owner}/{source.repo}/blob/{branch}/{path.lstrip('/')}"


def allowed_case_repo_keys() -> set[tuple[str, str]]:
    keys = {configured_github_source().repo_key}
    keys.add(_parse_source_uri(DEFAULT_GITHUB_PROVIDER_SOURCE_URI).repo_key)
    return keys


def _parse_source_uri(uri: str) -> GitHubRepoSource:
    cleaned = str(uri or "").strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError(f"Unsupported GitHub source URI: {uri}")
    parts = [part for part in parsed.path.replace("\\", "/").split("/") if part]
    if len(parts) < 2:
        raise ValueError(f"GitHub source URI must include owner and repo: {uri}")
    owner = parts[0]
    repo = parts[1][:-4] if parts[1].lower().endswith(".git") else parts[1]
    branch = DEFAULT_GITHUB_BRANCH
    if len(parts) >= 4 and parts[2] in {"tree", "blob"}:
        branch = "/".join(parts[3:]) or DEFAULT_GITHUB_BRANCH
    return GitHubRepoSource(owner=owner, repo=repo, branch=branch)
