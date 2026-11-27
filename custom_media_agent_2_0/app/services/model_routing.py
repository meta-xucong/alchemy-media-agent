"""The configured V2 model queue, shared by planning and visual review."""
from __future__ import annotations

from urllib.parse import urlsplit


AISELF_WOKEY_CLAUDE_MODEL = "claude-sonnet-5-5-alchemy-structured"


def resolve_claude_model(config, model: str) -> str:
    base_url = getattr(config, "llm_gateway_base_url", None)
    if model.strip().lower().startswith("claude-") and base_url:
        gateway = urlsplit(base_url.strip())
        if gateway.scheme == "https" and gateway.hostname == "aiself.vip":
            return AISELF_WOKEY_CLAUDE_MODEL
    return model


def configured_fallback_models(config, *, exclude_model: str | None = None) -> list[str]:
    primary = resolve_claude_model(config, (exclude_model or config.claude_orchestrator_model or "").strip())
    models = list(config.claude_orchestrator_fallback_models or ())
    legacy_model = getattr(config, "claude_orchestrator_fallback_model", None)
    if legacy_model:
        models.append(legacy_model)
    resolved = (resolve_claude_model(config, str(model).strip()) for model in models)
    return list(dict.fromkeys(model for model in resolved if model and model != primary))


def visual_review_models(config) -> list[str]:
    # A pixel review uses the same configured multimodal primary as the Brain.
    primary = resolve_claude_model(
        config, (config.claude_orchestrator_multimodal_model or config.claude_orchestrator_model or "").strip()
    )
    candidates = list(dict.fromkeys([*([primary] if primary else []),
                                    *configured_fallback_models(config, exclude_model=primary)]))
    # The user's review policy keeps GPT as the final option in that queue.
    return [m for m in candidates if not m.lower().startswith("gpt-")] + [m for m in candidates if m.lower().startswith("gpt-")]
