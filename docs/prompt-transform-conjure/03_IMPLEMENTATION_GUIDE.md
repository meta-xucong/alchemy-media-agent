# Implementation Guide

This guide tells Codex how to implement the V2 Conjure prompt enhancement layer step by step.

The implementation should start from the public source behavior in `kadevin/ilab-gpt-conjure`, especially prompt guard and prompt fidelity handling.

---

## 1. Step 1 - Create Package Skeleton

Create package:

`custom_media_agent_2_0/app/services/prompt_transform_conjure/`

Files:

- `__init__.py`
- `types.py`
- `config.py`
- `source_guard.py`
- `fidelity.py`
- `transformer.py`
- `integration.py`
- `telemetry.py`

---

## 2. Step 2 - Implement `source_guard.py`

Reference file:

`kadevin/ilab-gpt-conjure/codex_image/prompt_guard.py`

Implement behavior-compatible functions:

- `extract_prompt_constraints(prompt)`
- `build_prompt_guard_text(constraints)`
- `build_original_prompt_text()`
- `build_guarded_prompt(prompt, guard_text)`

The marker strategy should stay close to the reference source:

- title/font markers
- color markers
- limit markers
- target audience extraction
- duplicate removal

---

## 3. Step 3 - Implement `fidelity.py`

Reference file:

`kadevin/ilab-gpt-conjure/codex_image/webui/executor_transport.py`

Implement behavior-compatible mode routing.

V2 mode mapping:

- stable -> original-like preservation
- enhanced -> strict-like preservation
- exploration -> V2 extension, initially same as enhanced or disabled

Transport decision:

- If provider supports separate preservation text, keep prompt unchanged and return preservation text separately.
- If provider only accepts prompt text, embed preservation text into the prompt.
- If mode is disabled or off, return prompt unchanged.

---

## 4. Step 4 - Implement `transformer.py`

Main function:

`transform_prompt(input) -> result`

Behavior by mode:

### disabled
Return original prompt.

### stable
Normalize whitespace only. Record metadata.

### enhanced
Extract constraints from user prompt and V2 prompt. Build preservation text. Apply transport strategy. Record metadata.

### exploration
For the first implementation, either call enhanced behavior or return a clear warning that exploration is not active.

---

## 5. Step 5 - Implement `integration.py`

Target existing type:

`ImagePromptPlan`

Integration behavior:

1. Read current prompt from `prompt_plan.prompt`.
2. Build transform input.
3. Call `transform_prompt`.
4. Return a copied prompt plan with updated prompt.
5. Store transform metadata under `user_variables["conjure_transform"]`.

No schema change is required for first implementation.

---

## 6. Step 6 - Modify V2 Runtime

Target file:

`custom_media_agent_2_0/app/agents/runtime.py`

Add import:

`from app.services.prompt_transform_conjure.integration import apply_conjure_transform_to_prompt_plan`

Insert after `compose_prompt_plan(...)` and before `run_safety_check(...)`.

The safety service must evaluate the transformed prompt.

---

## 7. Step 7 - Add Config

Target file:

`custom_media_agent_2_0/app/config.py`

Add settings with safe defaults:

- transform enabled: false
- default mode: enhanced
- template mode: stable
- max prompt chars: 4200
- store metadata: true

Do not enable globally by default in the first PR.

---

## 8. Step 8 - Add Tests

Test package:

`custom_media_agent_2_0/tests/services/prompt_transform_conjure/`

Required tests:

- constraint extraction
- stable mode keeps prompt unchanged
- enhanced mode adds preservation behavior
- metadata is saved
- integration runs before safety by checking runtime output metadata

---

## 9. Definition of Done

The task is complete when:

- V2 can run with transform disabled and behavior remains unchanged.
- V2 can run stable mode and preserve original prompt.
- V2 can run enhanced mode and record extracted constraints.
- Runtime metadata shows base prompt and final prompt.
- Existing tests pass.
