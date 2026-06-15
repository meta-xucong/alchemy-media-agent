# Prompt Transform Layer for V2

This folder contains Codex-ready development documents for adding a source-aligned prompt transform layer to Alchemy Media Agent V2.

Reference repository:

```text
https://github.com/kadevin/ilab-gpt-conjure
```

## Important Scope Correction

The reference repository does **not** expose a hidden LLM-based `expand -> rewrite -> refine` algorithm.

Its reusable public value for this project is mainly:

- prompt fidelity modes
- prompt guard instruction construction
- user constraint extraction
- original prompt preservation
- guarded prompt wrapping
- prompt template import and normalization
- prompt snippet management
- image/reference input handling patterns
- provider payload shaping and prompt transport boundaries

Therefore the first implementation target is not a creative prompt generator. It is a **provider-safe prompt fidelity and guard layer** for V2.

## Target Runtime Position

```text
V2 compose_prompt_plan
  -> apply_conjure_prompt_transform
  -> safety_check
  -> create_image_job
  -> provider.generate
```

The transform layer must run after V2 creates `ImagePromptPlan` and before safety checking / image generation.

## Key Runtime Rule

Do not overwrite:

```text
ImagePromptPlan.prompt
```

Write the final provider-facing prompt to:

```text
ImagePromptPlan.user_variables["generation_prompt"]
```

Store metadata in:

```text
ImagePromptPlan.user_variables["prompt_transform"]
```

## Documents

Read in this order:

```text
00_ROOT_RULES.md
01_SOURCE_REUSE_MAP.md
02_CODE_STRUCTURE.md
03_IMPLEMENTATION_STEPS.md
04_API_CONTRACTS.md
05_TEST_PLAN.md
06_CODEX_TASK_PROMPT.md
```

## Three V2-Facing Modes

```text
stable      -> preserve original/template prompt as much as possible
enhanced    -> apply strict prompt guard behavior and constraint preservation
exploration -> V2-native future variant path; not directly provided by the reference source
```

## Phase 1 Non-goals

Do not implement these as if they came from `ilab-gpt-conjure`:

- hidden LLM rewrite chain
- image critic loop
- visual planning system
- prompt scoring model
- photography-specific optimizer

These can be future Alchemy-native extensions, but they are outside the source-aligned phase.
