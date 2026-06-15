# Architecture - Conjure Prompt Transform Layer

This document defines the source-aligned architecture for adding a Conjure-inspired prompt transform layer to Alchemy Media Agent V2.

It supersedes earlier generic `expand -> rewrite -> refine` wording.

## 1. Scope

The reference repository is:

```text
https://github.com/kadevin/ilab-gpt-conjure
```

The reusable source-backed capabilities are:

1. prompt constraint extraction
2. prompt guard instruction construction
3. original prompt preservation behavior
4. guarded prompt wrapping
5. prompt fidelity mode routing
6. prompt template import / normalization
7. prompt snippet normalization
8. provider prompt transport boundaries

The reference source does not provide a hidden LLM rewrite engine. Do not implement one as part of phase 1.

## 2. Target Flow

Current V2 flow:

```text
compose_prompt_plan -> safety_check -> create_image_job
```

Target V2 flow:

```text
compose_prompt_plan -> apply_conjure_prompt_transform -> safety_check -> create_image_job
```

The transform must run before safety so the actual final provider-facing prompt is safety-checked.

## 3. Runtime Boundary

V2 owns:

- user intent understanding
- case/template retrieval
- Template Lock
- Visual Grammar Lock
- `ImagePromptPlan` construction
- safety check
- provider job creation

Prompt Transform Layer owns:

- transform mode routing
- hard constraint extraction
- prompt guard instruction construction
- original prompt preservation
- guarded prompt wrapping
- provider-facing final prompt metadata

## 4. Data Boundary

Input:

```text
ImagePromptPlan
```

Do not overwrite:

```text
ImagePromptPlan.prompt
```

Write provider-facing prompt to:

```text
ImagePromptPlan.user_variables["generation_prompt"]
```

Store transform metadata in:

```text
ImagePromptPlan.user_variables["prompt_transform"]
```

## 5. Three Modes

### 5.1 stable

Goal: preserve current V2/template prompt as much as possible.

Mapping:

```text
stable -> original fidelity
```

Behavior:

- do not add creative content
- preserve prompt structure
- use original-prompt preservation instruction behavior when needed

### 5.2 enhanced

Goal: preserve hard constraints while making provider submission safer.

Mapping:

```text
enhanced -> strict fidelity
```

Behavior:

- extract constraints
- build prompt guard instructions
- wrap prompt when the provider cannot accept separate instructions

### 5.3 exploration

Goal: reserve a future V2-native variant path.

Mapping:

```text
exploration -> off fidelity in phase 1
```

Behavior in phase 1:

- do not generate variants
- do not invent hidden Conjure behavior
- return prompt unchanged except metadata

## 6. Source Reference Map

Primary files to inspect and adapt:

```text
codex_image/prompt_guard.py
codex_image/webui/executor_transport.py
codex_image/webui/executor.py
codex_image/webui/prompt_templates.py
codex_image/webui/prompt_snippets.py
codex_image/webui/executor_inputs.py
```

## 7. Proposed Package

```text
custom_media_agent_2_0/app/services/prompt_transform/
  __init__.py
  models.py
  guard.py
  modes.py
  transport.py
  transformer.py
  metadata.py
  template_importer.py
  snippets.py
  reference_inputs.py
```

## 8. Provider Compatibility

Existing providers already use:

```python
plan.user_variables.get("generation_prompt") or plan.prompt
```

So phase 1 should not require provider code changes.

## 9. Success Criteria

- Stable mode preserves the original/template prompt.
- Enhanced mode extracts constraints and applies guarded prompt behavior.
- `ImagePromptPlan.prompt` remains unchanged.
- Final provider-facing prompt is stored in `user_variables["generation_prompt"]`.
- Transform metadata is visible in output history through `user_variables["prompt_transform"]`.
- No hidden LLM rewrite/refine/critic behavior is introduced.
