# Conjure Integration - Root Development Rules

This document defines the root rules for adding the Conjure-inspired prompt enhancement layer into Alchemy Media Agent V2.

The reference repository is:

https://github.com/kadevin/ilab-gpt-conjure

Important correction: the reference repository is a GPT-image-2 WebUI/workbench. Its reusable open-source value for our V2 enhancement layer is mainly prompt fidelity, prompt guarding, prompt template management, provider payload shaping, and queue/provider boundary patterns.

It does not expose a separate LLM-based expand/rewrite/refine algorithm. Codex must not pretend such an algorithm exists in the reference source.

---

## 1. Fundamental Rule

Use the reference repository as the source of truth for these behaviors:

1. Prompt fidelity modes.
2. Prompt guard instruction construction.
3. Constraint extraction from user prompt text.
4. Original-prompt preservation behavior.
5. Guarded prompt wrapping when the image API does not support a separate instructions field.
6. Prompt template import, normalization, categorization, and metadata handling.
7. Image provider payload shape and revised-prompt capture.

Do not redesign these behaviors unless the current V2 runtime requires a small adapter.

---

## 2. Code Reuse Scope

Codex should inspect and reuse/adapt these source files first:

- `codex_image/prompt_guard.py`
- `codex_image/webui/executor_transport.py`
- `codex_image/webui/executor.py`
- `codex_image/webui/prompt_templates.py`
- `codex_image/client_types.py`
- `codex_image/openai_images_client.py`
- `codex_image/codex_responses_client.py`

If direct source copy is used, preserve license attribution and verify compatibility first. The reference repository declares AGPL-3.0-only. If direct copy is not acceptable for this project, implement a behavior-compatible adapter from the same public behavior.

---

## 3. What Must Not Be Invented as Reference Behavior

The following must not be documented or implemented as if it comes from `ilab-gpt-conjure`:

- A hidden LLM prompt expansion engine.
- A hidden rewrite/refine chain.
- A hidden visual planning system.
- A hidden image critic loop.
- A hidden prompt scoring model.

If Alchemy V2 later adds these, label them as V2-native extensions, not Conjure source reuse.

---

## 4. V2 Boundary

V2 remains responsible for:

- User intent understanding.
- Case/template retrieval.
- Template Lock and Visual Grammar Lock.
- Base `ImagePromptPlan` creation.
- Safety check.
- Provider job creation.

The new enhancement layer is responsible only for:

- Prompt fidelity mode routing.
- Constraint extraction.
- Guard instruction generation.
- Guarded prompt construction.
- Optional prompt-template pack normalization/import support.
- Metadata recording of what was changed or preserved.

---

## 5. Required Insertion Point

The enhancement layer must run after V2 creates `ImagePromptPlan` and before safety check and image generation.

Current V2 order:

```
compose_prompt_plan -> safety_check -> create_image_job
```

Target order:

```
compose_prompt_plan -> apply_conjure_prompt_transform -> safety_check -> create_image_job
```

This ensures the safety service checks the actual final prompt that will be sent to the image provider.

---

## 6. Mode Mapping

Use three V2-facing modes:

1. `stable`: preserve original/template prompt as much as possible.
2. `enhanced`: apply strict prompt guard behavior and constraint preservation.
3. `exploration`: V2-native optional extension for variants. This is not directly provided by the reference source.

The stable/enhanced modes should be implemented first.

---

## 7. Final Rule

The first implementation target is not a creative generator. It is a provider-safe prompt fidelity and prompt guard layer inspired by and adapted from the public `ilab-gpt-conjure` source.
