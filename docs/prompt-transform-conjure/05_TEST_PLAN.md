# Test Plan

This file defines the required tests before enabling the V2 Conjure prompt enhancement layer.

---

## 1. Unit Tests - Source Guard

File:

`custom_media_agent_2_0/tests/services/prompt_transform_conjure/test_source_guard.py`

Cases:

1. Extract title/font constraint.
2. Extract target audience.
3. Extract color constraint.
4. Extract limit clause.
5. Remove duplicate constraints.
6. Empty prompt returns empty list.
7. Guard text includes all constraints.
8. Guarded prompt returns original prompt when guard text is empty.

Reference behavior:

`kadevin/ilab-gpt-conjure/codex_image/prompt_guard.py`

---

## 2. Unit Tests - Fidelity

File:

`custom_media_agent_2_0/tests/services/prompt_transform_conjure/test_fidelity.py`

Cases:

1. Unknown mode falls back to configured default.
2. Stable maps to original-like behavior.
3. Enhanced maps to strict-like behavior.
4. Off returns unchanged prompt.
5. Provider without separate text support embeds guard text.
6. Provider with separate text support keeps prompt clean and returns separate text.

Reference behavior:

`kadevin/ilab-gpt-conjure/codex_image/webui/executor_transport.py`

---

## 3. Unit Tests - Transformer

File:

`custom_media_agent_2_0/tests/services/prompt_transform_conjure/test_transformer.py`

Cases:

1. Disabled transform returns original prompt.
2. Stable mode does not change prompt meaning.
3. Enhanced mode extracts constraints from user prompt.
4. Enhanced mode extracts constraints from V2 prompt.
5. Enhanced mode records metadata.
6. Long prompt is capped by configured max length.
7. Template lock prompt keeps TEMPLATE LOCK text.
8. Exploration mode returns enhanced behavior or explicit inactive warning.

---

## 4. Integration Tests - Prompt Plan

File:

`custom_media_agent_2_0/tests/services/prompt_transform_conjure/test_integration.py`

Cases:

1. `ImagePromptPlan` returns updated copy.
2. Original `ImagePromptPlan` object is not mutated in place.
3. Metadata is written to `user_variables.conjure_transform`.
4. Base prompt and final prompt are both recorded.
5. Existing `user_variables` keys are preserved.
6. Existing `negative_prompt`, `style_basis`, `provider_parameters`, `risk_notes`, and `explanation` are preserved.

---

## 5. Runtime Tests

Target:

`custom_media_agent_2_0/app/agents/runtime.py`

Cases:

1. With feature disabled, current V2 behavior is unchanged.
2. With stable mode enabled, prompt remains template-safe.
3. With enhanced mode enabled, prompt metadata contains extracted constraints.
4. Safety service receives the transformed prompt plan.
5. Image job receives the same prompt plan that safety checked.

---

## 6. Regression Tests

Important V2 features that must continue working:

- template customize mode
- smart enhance mode
- revision mode
- batch mode
- uploaded asset binding
- Template Lock
- Visual Grammar Lock
- provider input images
- prompt safety check
- image history

---

## 7. Manual QA Checklist

Run at least these manual cases:

1. Pure text prompt with color requirement.
2. Prompt with required title text.
3. Prompt with target audience.
4. Template-customize run.
5. Uploaded reference image run.
6. Product/ecommerce prompt.
7. Poster prompt with text.
8. Prompt that says no text.

Expected result:

- Stable mode should keep the original prompt shape.
- Enhanced mode should preserve hard constraints more clearly.
- No mode should remove Template Lock wording.
