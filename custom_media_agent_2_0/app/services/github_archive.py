from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.services.case_parser import MarkdownCaseDocument
from app.services.github_source import github_archive_url, github_commit_api_url


CANONICAL_CASE_FILES = {
    "cases/ad-creative.md",
    "cases/character.md",
    "cases/comparison.md",
    "cases/ecommerce.md",
    "cases/portrait.md",
    "cases/poster.md",
    "cases/ui.md",
}


def fetch_evolinkai_github_cases() -> tuple[str, list[MarkdownCaseDocument]]:
    timeout = httpx.Timeout(settings.github_sync_timeout_seconds)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        source_version = _fetch_commit_sha(client)
        response = client.get(github_archive_url())
        response.raise_for_status()
    documents = _extract_case_markdown(response.content)
    if not documents:
        raise RuntimeError("GitHub archive did not contain cases/*.md files.")
    settings.remote_snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = settings.remote_snapshot_dir / f"{source_version}.zip"
    snapshot_path.write_bytes(response.content)
    return source_version, documents


def fetch_evolinkai_source_version() -> str:
    timeout = httpx.Timeout(settings.github_sync_timeout_seconds)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        return _fetch_commit_sha(client)


def _fetch_commit_sha(client: httpx.Client) -> str:
    try:
        response = client.get(github_commit_api_url(), headers={"Accept": "application/vnd.github+json"})
        response.raise_for_status()
        payload = response.json()
        sha = str(payload.get("sha") or "")[:12]
        if sha:
            return f"github-{sha}"
    except Exception:
        pass
    return "github-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _extract_case_markdown(zip_bytes: bytes) -> list[MarkdownCaseDocument]:
    documents: list[MarkdownCaseDocument] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for info in archive.infolist():
            normalized = info.filename.replace("\\", "/")
            parts = normalized.split("/", 1)
            relative = parts[1] if len(parts) == 2 else normalized
            if relative not in CANONICAL_CASE_FILES:
                continue
            with archive.open(info) as file:
                text = file.read().decode("utf-8")
            documents.append(MarkdownCaseDocument(path=relative, text=text))
    documents.sort(key=lambda item: item.path)
    return documents
