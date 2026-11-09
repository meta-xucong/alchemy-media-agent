"""The configured V2 model queue, shared by planning and visual review."""
from __future__ import annotations


def configured_fallback_models(config, *, exclude_model: str | None = None) -> list[str]:
    primary = (exclude_model or config.claude_orchestrator_model or "").strip()
    models = list(config.claude_orchestrator_fallback_models or ())
    if config.claude_orchestrator_fallback_model:
        models.append(config.claude_orchestrator_fallback_model)
    return list(dict.fromkeys(str(model).strip() for model in models
                             if str(model).strip() and str(model).strip() != primary))


def visual_review_models(config) -> list[str]:
    # A pixel review uses the same configured multimodal primary as the Brain.
    primary = (config.claude_orchestrator_multimodal_model or config.claude_orchestrator_model or "").strip()
    candidates = list(dict.fromkeys([*([primary] if primary else []),
                                    *configured_fallback_models(config, exclude_model=primary)]))
    # The user's review policy keeps GPT as the final option in that queue.
    return [m for m in candidates if not m.lower().startswith("gpt-")] + [m for m in candidates if m.lower().startswith("gpt-")]
