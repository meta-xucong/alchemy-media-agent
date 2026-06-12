from __future__ import annotations

from urllib.parse import unquote, urlparse
from urllib.parse import quote


def normalize_case_preview_url(url: str | None) -> str | None:
    cleaned = str(url or "").strip()
    if not cleaned:
        return None
    if cleaned.startswith("/api/v2/"):
        return cleaned
    repo_asset_path = _github_repo_image_path(cleaned)
    if repo_asset_path:
        return _case_thumbnail_url(repo_asset_path)
    lowered = cleaned.lower()
    if lowered.startswith(("http://", "https://", "data:")):
        return cleaned
    asset_path = cleaned.replace("\\", "/").split("#", 1)[0].split("?", 1)[0]
    while asset_path.startswith("./"):
        asset_path = asset_path[2:]
    while asset_path.startswith("../"):
        asset_path = asset_path[3:]
    asset_path = asset_path.lstrip("/")
    if asset_path.startswith("images/") and ".." not in asset_path.split("/"):
        return _case_thumbnail_url(asset_path)
    return cleaned


def has_serviceable_case_preview_url(url: str | None) -> bool:
    normalized = normalize_case_preview_url(url)
    return bool(normalized and normalized == str(url or "").strip())


def _case_thumbnail_url(asset_path: str) -> str:
    return f"/api/v2/case-thumbnails/{quote(asset_path, safe='/')}"


def _github_repo_image_path(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path_parts = [unquote(part) for part in parsed.path.replace("\\", "/").split("/") if part]
    if host == "raw.githubusercontent.com":
        if len(path_parts) < 4:
            return None
        owner, repo = path_parts[0].lower(), path_parts[1].lower()
        if owner != "evolinkai" or repo != "awesome-gpt-image-2-api-and-prompts":
            return None
        return _image_path_from_parts(path_parts[2:])
    if host == "github.com":
        if len(path_parts) < 6:
            return None
        owner, repo = path_parts[0].lower(), path_parts[1].lower()
        if owner != "evolinkai" or repo != "awesome-gpt-image-2-api-and-prompts":
            return None
        return _image_path_from_parts(path_parts[4:] if path_parts[2] == "blob" else path_parts[2:])
    return None


def _image_path_from_parts(parts: list[str]) -> str | None:
    try:
        image_index = parts.index("images")
    except ValueError:
        return None
    image_path = "/".join(parts[image_index:])
    if ".." in image_path.split("/"):
        return None
    return image_path if image_path.startswith("images/") else None
