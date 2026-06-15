# Codex Task List

This file is the recommended task order for Codex implementation.

---

## Task 0 - Read Reference Source

Before coding, inspect these files from `kadevin/ilab-gpt-conjure`:

1. `codex_image/prompt_guard.py`
2. `codex_image/webui/executor_transport.py`
3. `codex_image/webui/executor.py`
4. `codex_image/webui/prompt_templates.py`
5. `codex_image/client_types.py`
6. `codex_image/openai_images_client.py`
7. `codex_image/codex_responses_client.py`

Goal:

Understand the actual public behavior. Do not assume hidden expand/rewrite/refine source code exists.

---

## Task 1 - Create Package Skeleton

Create:

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

Acceptance:

- Package imports cleanly.
- No runtime integration yet.

---

## Task 2 - Implement Source Guard Adapter

Implement `source_guard.py` from the behavior of `codex_image/prompt_guard.py`.

Acceptance:

- Constraint extraction works for title, color, audience, and limitation text.
- Duplicate constraints are removed.
- Guarded prompt construction works.

---

## Task 3 - Implement Fidelity Adapter

Implement `fidelity.py` from the behavior of `codex_image/webui/executor_transport.py`.

Acceptance:

- stable, enhanced, off, and exploration modes normalize correctly.
- Provider transport mode is deterministic.
- Unknown mode falls back safely.

---

## Task 4 - Implement Transformer

Implement `transformer.py`.

Acceptance:

- disabled returns unchanged prompt.
- stable records metadata without changing prompt.
- enhanced records constraints and applies guard behavior.
- exploration is either disabled or explicitly routed to enhanced.

---

## Task 5 - Implement V2 Integration Helper

Implement `integration.py`.

Acceptance:

- Accepts `ImagePromptPlan`.
- Returns copied plan with updated prompt.
- Stores metadata in `user_variables.conjure_transform`.
- Preserves existing plan fields.

---

## Task 6 - Add Config

Add config in `custom_media_agent_2_0/app/config.py`.

Suggested settings:

- `V2_CONJURE_PROMPT_TRANSFORM_ENABLED`
- `V2_CONJURE_PROMPT_TRANSFORM_DEFAULT_MODE`
- `V2_CONJURE_PROMPT_TRANSFORM_TEMPLATE_MODE`
- `V2_CONJURE_PROMPT_TRANSFORM_MAX_PROMPT_CHARS`
- `V2_CONJURE_PROMPT_TRANSFORM_STORE_METADATA`

Acceptance:

- Defaults keep current V2 behavior unchanged.

---

## Task 7 - Integrate Runtime

Target file:

`custom_media_agent_2_0/app/agents/runtime.py`

Insert transform immediately after `compose_prompt_plan(...)` and before safety checking.

Acceptance:

- Safety check sees transformed prompt.
- Image job uses the same transformed prompt.
- When feature is disabled, no behavior change.

---

## Task 8 - Add Tests

Create tests under:

`custom_media_agent_2_0/tests/services/prompt_transform_conjure/`

Acceptance:

- Unit tests pass.
- Runtime integration tests pass.
- Existing test suite still passes.

---

## Task 9 - Manual QA

Run manual prompts covering:

- title text
- target audience
- color requirement
- no text requirement
- template customize
- uploaded reference image
- ecommerce/product
- poster

Acceptance:

- Stable mode preserves original prompt shape.
- Enhanced mode preserves hard constraints more clearly.
- Template Lock is not removed.
