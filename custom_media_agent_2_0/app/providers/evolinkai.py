from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings
from app.schemas import LicensePolicy, PromptCase, ResourceProvider


EVOLINKAI_PROVIDER_ID = "github_evolinkai_gpt_image_cases"


def build_evolinkai_provider() -> ResourceProvider:
    manifest: dict[str, Any] = {
        "provider_id": EVOLINKAI_PROVIDER_ID,
        "provider_type": "github_repository",
        "source_uri": settings.github_provider_source_uri,
        "display_name": "EvoLinkAI GPT Image Cases",
        "sync_mode": "scheduled_and_manual",
        "sync_interval_minutes": settings.resource_sync_interval_minutes,
        "update_detection": {"type": "git_commit_sha", "branch": "main"},
        "parser": {
            "type": "markdown_case_parser",
            "include_paths": ["cases/*.md", "images/**", "data/ingested_tweets.json"],
            "canonical_language": "en",
            "dedupe_multilingual_duplicates": True,
        },
        "capabilities": {
            "template_gallery": True,
            "smart_retrieval": True,
            "asset_preview": True,
            "prompt_atoms": True,
        },
        "license_policy": {
            "source_license": "Repository-declared license, treated as case-level policy input",
            "raw_image_final_use_allowed": False,
            "style_learning_allowed": True,
            "commercial_use_requires_safety_check": True,
        },
        "risk_policy": {
            "default_for_unknown_assets": "inspiration_only",
            "block_protected_ip_copying": True,
            "block_unlicensed_logo_copying": True,
        },
    }
    return ResourceProvider(
        provider_id=EVOLINKAI_PROVIDER_ID,
        provider_type="github_repository",
        source_uri=settings.github_provider_source_uri,
        display_name="EvoLinkAI GPT Image Cases",
        enabled=True,
        manifest=manifest,
    )


def load_seed_cases(seed_path: Path | None = None) -> tuple[str, list[PromptCase]]:
    path = seed_path or settings.provider_seed_path
    payload = json.loads(path.read_text(encoding="utf-8"))
    source_version = payload["source_version"]
    index_version = f"{EVOLINKAI_PROVIDER_ID}:{source_version}"
    cases = [
        PromptCase(
            case_id=item["case_id"],
            provider_id=payload["provider_id"],
            index_version=index_version,
            source_url=item["source_url"],
            title=item["title"],
            category=item["category"],
            summary=item.get("summary", ""),
            preview_url=item.get("preview_url"),
            raw_prompt=item["raw_prompt"],
            prompt_atoms=item.get("prompt_atoms", {}),
            visual_features=item.get("visual_features", {}),
            style_tags=item.get("style_tags", []),
            use_case_tags=item.get("use_case_tags", []),
            risk_tags=item.get("risk_tags", []),
            license_policy=LicensePolicy(),
            quality_score=item.get("quality_score", 0.5),
        )
        for item in payload["cases"]
    ]
    return source_version, cases
