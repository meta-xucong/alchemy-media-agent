# Function Contracts

This file defines the expected function contracts for the V2 Conjure prompt enhancement layer.

---

## 1. Internal Types

### `ConjureTransformMode`

Allowed values:

- `off`
- `stable`
- `enhanced`
- `exploration`

### `ConjureTransportKind`

Allowed values:

- `unchanged`
- `embedded_prompt`
- `separate_text`

---

## 2. `ConjureTransformInput`

Fields:

- `prompt`: current V2 prompt
- `user_prompt`: original user request
- `mode`: transform mode
- `prompt_plan_mode`: V2 run mode
- `provider_hint`: selected provider or requested provider
- `template_locked`: whether Template Lock is active
- `selected_case_titles`: optional case titles for metadata
- `max_prompt_chars`: max prompt length

---

## 3. `ConjureTransformResult`

Fields:

- `final_prompt`
- `separate_text`
- `transport_kind`
- `mode`
- `constraints`
- `base_prompt`
- `changed`
- `warnings`
- `metadata`

---

## 4. `extract_prompt_constraints(prompt)`

Input:

- prompt string

Output:

- list of constraint strings

Behavior:

- detect title/font requirements
- detect target audience
- detect color requirements
- detect limitation clauses
- remove duplicates while preserving order

Reference:

`kadevin/ilab-gpt-conjure/codex_image/prompt_guard.py`

---

## 5. `build_prompt_guard_text(constraints)`

Input:

- list of constraints

Output:

- preservation text string

Behavior:

- describe that the prompt may be expanded but original constraints must be preserved
- include extracted hard constraints

Reference:

`kadevin/ilab-gpt-conjure/codex_image/prompt_guard.py`

---

## 6. `build_original_prompt_text()`

Input:

- none

Output:

- text that instructs downstream model to use the original prompt without changes

Reference:

`kadevin/ilab-gpt-conjure/codex_image/prompt_guard.py`

---

## 7. `build_guarded_prompt(prompt, guard_text)`

Input:

- prompt string
- preservation text string

Output:

- combined prompt string

Behavior:

- if preservation text is empty, return prompt
- otherwise prepend preservation text and then include original prompt

Reference:

`kadevin/ilab-gpt-conjure/codex_image/prompt_guard.py`

---

## 8. `select_transport(prompt, guard_text, provider_hint)`

Input:

- prompt string
- preservation text string
- provider hint string

Output:

- final prompt
- optional separate preservation text
- transport kind

Behavior:

- for simple image providers, embed preservation text into prompt
- for response-style providers, return preservation text separately
- for disabled mode, return prompt unchanged

Reference:

`kadevin/ilab-gpt-conjure/codex_image/webui/executor_transport.py`

---

## 9. `transform_prompt(input)`

Input:

- `ConjureTransformInput`

Output:

- `ConjureTransformResult`

Behavior:

- off: unchanged
- stable: preserve prompt
- enhanced: apply constraint preservation
- exploration: first implementation may reuse enhanced behavior

---

## 10. `apply_conjure_transform_to_prompt_plan(...)`

Input:

- `ImagePromptPlan`
- user prompt
- provider hint
- template lock flag
- selected cases

Output:

- updated `ImagePromptPlan`

Behavior:

- create transform input
- call transform service
- update `prompt_plan.prompt`
- append metadata into `prompt_plan.user_variables`
