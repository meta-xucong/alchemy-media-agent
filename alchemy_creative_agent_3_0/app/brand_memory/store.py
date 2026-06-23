"""V3-owned JSON store for brand profiles."""

from __future__ import annotations

import json
from pathlib import Path

from ..schemas import BrandProfile


DEFAULT_BRAND_STORE_ROOT = Path(__file__).resolve().parents[2] / "data" / "brand_memory"


class BrandProfileStore:
    """Small V3-owned JSON store used by foundation tests and later phases."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or DEFAULT_BRAND_STORE_ROOT
        self.brands_dir = self.root / "brands"

    def _path_for(self, brand_id: str) -> Path:
        return self.brands_dir / f"{brand_id}.json"

    def exists(self, brand_id: str) -> bool:
        return self._path_for(brand_id).exists()

    def load(self, brand_id: str) -> BrandProfile | None:
        path = self._path_for(brand_id)
        if not path.exists():
            return None
        return BrandProfile.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, profile: BrandProfile) -> BrandProfile:
        self.brands_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(profile.brand_id)
        path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        return profile

    def list_brand_ids(self) -> list[str]:
        if not self.brands_dir.exists():
            return []
        return sorted(path.stem for path in self.brands_dir.glob("brand_*.json"))

    def raw_json(self, brand_id: str) -> dict:
        path = self._path_for(brand_id)
        return json.loads(path.read_text(encoding="utf-8"))

