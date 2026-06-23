"""Brand consistency helpers."""

from __future__ import annotations

from ..schemas import BrandProfile, PromptCompilationResult


def brand_tone_is_present(brand_profile: BrandProfile, prompt: PromptCompilationResult) -> bool:
    prompt_text = " ".join(prompt.style_notes + [prompt.visual_prompt])
    return any(tone in prompt_text for tone in brand_profile.visual_tone)

