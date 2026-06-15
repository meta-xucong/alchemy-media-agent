# Prompt Transform Layer - Conjure Integration

This folder contains the development documents for adding a Conjure-inspired prompt enhancement layer to Alchemy Media Agent V2.

Reference repository:

https://github.com/kadevin/ilab-gpt-conjure

Important scope note:

The public reference source mainly provides prompt fidelity, prompt guard, prompt template, provider payload, and revised-prompt handling patterns. It does not expose a separate hidden LLM expand/rewrite/refine pipeline. The first implementation should therefore reuse the public prompt-guard and fidelity behavior instead of inventing a new prompt rewriting system.

---

## Target V2 Flow

Current:

`V2 -> ImagePromptPlan -> Safety -> Image Provider`

Target:

`V2 -> ImagePromptPlan -> Conjure Prompt Transform -> Safety -> Image Provider`

The transform runs before safety so the safety service checks the final prompt.

---

## Three Modes

### stable

Preserve the V2/template prompt as much as possible.

Use for template-sensitive tasks.

### enhanced

Apply source-compatible prompt guard behavior:

- extract hard constraints
- build preservation text
- embed or pass preservation text according to provider capability
- record metadata

This should be the default once the feature is enabled.

### exploration

Reserved for a future V2-native variant mode.

It may initially reuse enhanced behavior or remain disabled.

---

## Documents

Read in this order:

1. `00_ROOT_RULES.md`
2. `01_SOURCE_REUSE_MAP.md`
3. `02_CODE_STRUCTURE.md`
4. `03_IMPLEMENTATION_GUIDE.md`
5. `04_FUNCTION_CONTRACTS.md`
6. `05_TEST_PLAN.md`
7. `06_CODEX_TASKS.md`

---

## Development Rule

Codex should inspect the reference source before writing code, especially:

- `codex_image/prompt_guard.py`
- `codex_image/webui/executor_transport.py`
- `codex_image/webui/executor.py`
- `codex_image/webui/prompt_templates.py`

The implementation should adapt these public behaviors into V2 instead of creating unrelated prompt logic.
