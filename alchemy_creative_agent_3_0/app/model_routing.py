"""Pure model routing rules shared by the V3 Brain and visual review."""

from __future__ import annotations

import os


V3_FINAL_FALLBACK_MODEL = "gpt-6.1-sol"


def model_protocol(model: str | None) -> str | None:
    normalized = str(model or "").strip().lower()
    if normalized.startswith("claude-"):
        return "anthropic"
    if normalized.startswith(("gpt-", "o1", "o3", "o4", "deepseek-", "kimi-", "doubao-")):
        return "openai"
    return None


def build_v3_model_candidates(
    primary_model: str | None,
    backup_model: str | None,
) -> tuple[tuple[str, str], ...]:
    """Build the V3 route in the same order for Brain and visual review.

    The configured primary always leads. Kimi remains the first fallback,
    followed by the configured Brain backup (deduplicated), and GPT-6.1-Sol
    remains the final fallback.
    """

    primary = str(primary_model or "claude-sonnet-5-5").strip() or "claude-sonnet-5-5"
    backup = str(backup_model or "kimi-k3").strip() or "kimi-k3"
    models: list[str] = []
    seen: set[str] = set()
    for model in (primary, "kimi-k3", backup, V3_FINAL_FALLBACK_MODEL):
        normalized = model.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        models.append(model)
    return tuple((model_protocol(model) or "unsupported", model) for model in models)


def v3_gateway_credentials() -> tuple[str | None, str | None]:
    """Read and normalize the only supported V3 model gateway credentials."""

    raw_key = os.getenv("LLM_GATEWAY_API_KEY")
    api_key = str(raw_key).strip().lstrip("\ufeff").strip() if raw_key is not None else ""
    raw_base_url = os.getenv("LLM_GATEWAY_BASE_URL")
    base_url = str(raw_base_url).strip() if raw_base_url is not None else ""
    return api_key or None, base_url or None
