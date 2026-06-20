from __future__ import annotations

from app.services.alchemy_lab_reference_policy import lab_reference_prompt_block


def append_lab_reference_prompt(base_prompt: str, reference_plan: dict | None) -> str:
    block = lab_reference_prompt_block(reference_plan)
    if not block:
        return base_prompt
    return f"{base_prompt}\n{block}".strip()
