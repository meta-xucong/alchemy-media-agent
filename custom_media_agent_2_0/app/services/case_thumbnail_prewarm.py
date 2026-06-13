from __future__ import annotations

from dataclasses import dataclass

from app.repositories import repository
from app.services.bootstrap import bootstrap_v2_repository
from app.services.case_assets import read_case_thumbnail


@dataclass(frozen=True)
class CaseThumbnailPrewarmResult:
    variant: str
    attempted: int
    succeeded: int
    failed: int
    skipped: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "variant": self.variant,
            "attempted": self.attempted,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
        }


def prewarm_case_thumbnails(*, variant: str = "grid", limit: int = 0) -> CaseThumbnailPrewarmResult:
    bootstrap_v2_repository(seed_cases=True)
    asset_paths = _template_asset_paths(limit=limit)
    attempted = 0
    succeeded = 0
    failed = 0
    for asset_path in asset_paths:
        attempted += 1
        if read_case_thumbnail(asset_path, variant=variant):
            succeeded += 1
        else:
            failed += 1
    return CaseThumbnailPrewarmResult(
        variant=variant,
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        skipped=max(0, len(repository.list_cases(active_only=True)) - attempted),
    )


def _template_asset_paths(*, limit: int = 0) -> list[str]:
    cases = repository.list_cases(active_only=True)
    cases.sort(key=lambda case: (-case.quality_score, case.category, case.title, case.case_id))
    paths: list[str] = []
    seen: set[str] = set()
    for case in cases:
        asset_path = case_preview_asset_path(case.preview_url)
        if not asset_path or asset_path in seen:
            continue
        paths.append(asset_path)
        seen.add(asset_path)
        if limit > 0 and len(paths) >= limit:
            break
    return paths


def case_preview_asset_path(url: str | None) -> str:
    if not url:
        return ""
    normalized = str(url)
    thumbnail_marker = "/case-thumbnails/"
    if thumbnail_marker in normalized:
        path = normalized.split(thumbnail_marker, 1)[1].split("#", 1)[0].split("?", 1)[0].lstrip("/")
        if path.startswith(("grid/", "preview/")):
            path = path.split("/", 1)[1]
        return path
    asset_marker = "/case-assets/"
    if asset_marker in normalized:
        return normalized.split(asset_marker, 1)[1].split("#", 1)[0].split("?", 1)[0].lstrip("/")
    if normalized.startswith("../images/"):
        return normalized.replace("../", "", 1)
    for marker in (
        "/awesome-gpt-image-2-API-and-Prompts/main/",
        "/awesome-gpt-image-2-API-and-Prompts/blob/main/",
        "/awesome-gpt-image-2-API-and-Prompts/raw/main/",
    ):
        if marker in normalized:
            return normalized.split(marker, 1)[1].split("#", 1)[0].split("?", 1)[0].lstrip("/")
    return ""
