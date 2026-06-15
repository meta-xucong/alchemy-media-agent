# Code Structure Plan

This document defines the file-level implementation plan for the V2 Conjure prompt enhancement layer.

Target package:

`custom_media_agent_2_0/app/services/prompt_transform_conjure/`

---

## 1. Package Files

Create these files:

- `__init__.py`
- `types.py`
- `config.py`
- `source_guard.py`
- `fidelity.py`
- `transformer.py`
- `integration.py`
- `telemetry.py`

---

## 2. Responsibilities

### `types.py`

Defines internal service types:

- transform mode
- transport mode
- transform input
- transform result

Do not change public API schemas in the first implementation.

### `config.py`

Reads and normalizes feature flags:

- feature enabled
- default mode
- template mode
- max prompt length
- metadata storage flag

Suggested defaults:

- feature enabled: false
- default mode: enhanced
- template mode: stable
- max prompt length: 4200
- store metadata: true

### `source_guard.py`

Adapter for the public Conjure prompt guard behavior.

Reference source:

`codex_image/prompt_guard.py`

Functions:

- extract constraints
- build preservation text
- build original prompt preservation text
- wrap prompt with preservation text

### `fidelity.py`

Adapter for Conjure prompt fidelity behavior.

Reference source:

`codex_image/webui/executor_transport.py`

Functions:

- normalize mode
- map V2 mode to fidelity behavior
- choose provider transport style

### `transformer.py`

Core transform service.

Main function:

`transform_prompt(input) -> result`

Behavior:

- disabled: return original prompt
- stable: preserve prompt
- enhanced: apply constraint preservation
- exploration: initially reuse enhanced behavior or stay disabled

### `integration.py`

V2 integration layer.

Main function:

`apply_conjure_transform_to_prompt_plan(...)`

Behavior:

- accept existing `ImagePromptPlan`
- call transform service
- return updated `ImagePromptPlan`
- store transform metadata in `user_variables`

### `telemetry.py`

Builds safe transform metadata for debugging and history.

---

## 3. Runtime Insertion Point

Target file:

`custom_media_agent_2_0/app/agents/runtime.py`

Insert the transform after `compose_prompt_plan(...)` and before the safety service.

Reason:

The safety service should evaluate the exact prompt that will be sent to the image provider.

---

## 4. Metadata Location

Use:

`prompt_plan.user_variables["conjure_transform"]`

Required metadata:

- enabled
- mode
- source repo
- base prompt
- final prompt
- extracted constraints
- transport kind
- applied flag
- warnings

---

## 5. Tests

Create tests under:

`custom_media_agent_2_0/tests/services/prompt_transform_conjure/`

Test files:

- `test_source_guard.py`
- `test_fidelity.py`
- `test_transformer.py`
- `test_integration.py`

---

## 6. First PR Scope

First PR includes:

- package skeleton
- source guard adapter
- stable mode
- enhanced mode
- runtime integration
- tests

Keep exploration mode as a stub unless explicitly enabled later.
