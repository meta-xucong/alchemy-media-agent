"""Prompt builders for remote V3 LLM Brain runs."""

from __future__ import annotations

import json

from .contracts import BrainRunRequest


SYSTEM_PROMPT = """You are the V3 Creative OS planning brain. Return JSON only.
Do not reveal hidden reasoning. Summarize decisions as user-friendly studio notes.
Use the same language as the user's request; use Simplified Chinese for Chinese requests.
Use only the provided project context. Only selected outputs may become positive style anchors.
Unselected candidates are history only. Keep ecommerce-specific logic out unless the template explicitly requests it.
For general_template/general_creative, use subject/scene/style/lighting language by default.
Do not introduce product, packaging, label, CTA, selling-point, offer, or ad-copy concepts unless the user explicitly asks for a product/ecommerce image.
Each returned prompt plan must preserve one complete image per output; do not plan collages, split screens, contact sheets, storyboards, comparison panels, or multi-panel layouts unless the user explicitly asks for that format.
Keep every list concise: 2-5 short items. Do not wrap the JSON in markdown fences."""


def build_remote_payload(request: BrainRunRequest) -> str:
    payload = {
        "task": "prepare_pre_generation_image_reasoning",
        "stage": request.stage,
        "user_input": request.user_input,
        "scenario_id": request.scenario_id,
        "template_id": request.template_id,
        "project_id": request.project_id,
        "requested_image_count": request.requested_image_count,
        "requested_image_size": request.requested_image_size,
        "reasoning_depth": request.reasoning_depth,
        "project_context": request.project_context,
        "selected_output_assets": request.selected_output_assets,
        "reference_assets": request.reference_assets,
        "uploaded_assets": request.uploaded_assets,
        "shared_capabilities": request.shared_capabilities,
        "product_profile": request.product_profile,
        "return_schema": {
            "intent_summary": {
                "user_goal": "string",
                "scene": "string",
                "audience": "string|null",
                "output_use": "string",
                "visual_mood": ["string"],
                "must_keep": ["string"],
                "avoid": ["string"],
            },
            "project_memory_digest": {
                "has_project_context": "boolean",
                "selected_reference_count": "integer",
                "uploaded_reference_count": "integer",
                "positive_style_rules": ["string"],
                "continuity_rules": ["string"],
                "negative_rules": ["string"],
            },
            "image_set_plan": {
                "set_goal": "string",
                "image_count": "integer 1-4",
                "size": "string|null",
                "shot_plan": ["string"],
                "composition_rules": ["string"],
                "quality_bar": ["string"],
            },
            "prompt_guidance": {
                "optimized_direction": "string",
                "visual_direction_addons": ["string"],
                "style_notes": ["string"],
                "layout_notes": ["string"],
                "hard_constraints": ["string"],
                "negative_prompt_addons": ["string"],
                "consistency_strategy": "string|null",
            },
            "prompt_review": {
                "status": "passed|warning",
                "checks": ["string"],
                "fixes_applied": ["string"],
                "warnings": ["string"],
            },
            "user_visible_summary": {
                "headline": "short user-facing sentence",
                "done": ["short user-facing phrases"],
                "next": ["short user-facing phrases"],
                "progress_messages": ["short progress messages"],
            },
            "checkpoints": [
                {
                    "checkpoint_id": "intent|context|visual_strategy|prompt_guidance|pre_generation_review|post_generation_review",
                    "stage": "string",
                    "status": "completed|warning",
                    "summary": "short user-friendly planning note",
                    "inputs": ["short input facts"],
                    "outputs": ["short output decisions"],
                    "warnings": ["short warnings"],
                    "metadata": {},
                }
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
