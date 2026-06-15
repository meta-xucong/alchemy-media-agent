# 03 Implementation Steps

This is the Codex task list for implementing the Prompt Transform Layer.

## Phase 0: Read Source Before Coding

Before writing code, Codex must inspect:

```text
Reference:
kadevin/ilab-gpt-conjure/codex_image/prompt_guard.py
kadevin/ilab-gpt-conjure/codex_image/webui/executor_transport.py
kadevin/ilab-gpt-conjure/codex_image/webui/executor.py
kadevin/ilab-gpt-conjure/codex_image/webui/prompt_templates.py
kadevin/ilab-gpt-conjure/codex_image/webui/prompt_snippets.py

Alchemy:
custom_media_agent_2_0/app/schemas.py
custom_media_agent_2_0/app/services/generation.py
custom_media_agent_2_0/app/providers/images/base.py
custom_media_agent_2_0/app/providers/images/openai_gpt_image_2.py
custom_media_agent_2_0/app/providers/images/doubao_image.py
```

## Phase 1: Add Prompt Transform Package

Create:

```text
custom_media_agent_2_0/app/services/prompt_transform/
```

Files:

```text
__init__.py
models.py
guard.py
modes.py
transport.py
transformer.py
metadata.py
```

Optional:

```text
template_importer.py
snippets.py
reference_inputs.py
```

## Phase 2: Implement Guard Logic

Port/adapt `prompt_guard.py`.

Acceptance criteria:

- `extract_prompt_constraints()` extracts title/font, target audience, color, and limits.
- `build_prompt_guard_instructions()` produces a Chinese guard instruction block.
- `build_original_prompt_instructions()` produces original-prompt mode instructions.
- `build_guarded_prompt()` appends instructions above the original prompt.

## Phase 3: Implement Mode Logic

Implement:

```python
normalize_transform_mode()
mode_to_fidelity()
```

Rules:

```text
stable      -> original
enhanced    -> strict
exploration -> off
```

Out-of-range values default to `enhanced`.

## Phase 4: Implement Transport Logic

Port/adapt `executor_transport.py` behavior.

Implement:

```python
normalize_prompt_fidelity()
prompt_for_transport()
instructions_for_transport()
```

For first pass:

- `stable`: return original prompt or guarded original instruction.
- `enhanced`: return guarded prompt when provider cannot accept separate instructions.
- `exploration`: return prompt unchanged; variants are future work.

## Phase 5: Implement Transformer API

Implement:

```python
def transform_prompt(request: PromptTransformRequest) -> PromptTransformResult
```

Algorithm:

```text
input prompt
  -> normalize mode
  -> map to fidelity
  -> extract constraints
  -> build guard instructions
  -> build transport prompt / instructions
  -> return result
```

Then implement:

```python
def transform_prompt_plan(prompt_plan, *, mode=None, provider=None):
    ...
```

Expected behavior:

- Read base prompt from `prompt_plan.user_variables["generation_prompt"]` if present, else `prompt_plan.prompt`.
- Do not mutate original object unless project style allows.
- Prefer `model_copy(deep=True)` if Pydantic v2 is available.
- Write final prompt into `new_plan.user_variables["generation_prompt"]`.
- Store metadata in `new_plan.user_variables["prompt_transform"]`.
- Return `(new_plan, result)`.

Pseudo-code:

```python
def transform_prompt_plan(prompt_plan, *, mode=None, provider=None):
    base_prompt = str(prompt_plan.user_variables.get("generation_prompt") or prompt_plan.prompt)
    transform_request = PromptTransformRequest(
        prompt=base_prompt,
        mode=mode or prompt_plan.user_variables.get("prompt_transform_mode") or "enhanced",
        provider=provider,
        user_variables=prompt_plan.user_variables,
        provider_parameters=prompt_plan.provider_parameters,
    )
    result = transform_prompt(transform_request)

    new_plan = prompt_plan.model_copy(deep=True)
    new_plan.user_variables["generation_prompt"] = result.transport_prompt or result.final_prompt
    new_plan.user_variables["prompt_transform"] = prompt_transform_metadata(result)
    return new_plan, result
```

## Phase 6: Integrate Into `generation.py`

Insertion point:

```text
custom_media_agent_2_0/app/services/generation.py
```

Before calling:

```python
provider.generate(V2ImageProviderRequest(...))
```

Create transformed plan:

```python
transformed_plan, transform_result = transform_prompt_plan(
    request.prompt_plan,
    mode=request.prompt_plan.user_variables.get("prompt_transform_mode"),
    provider=provider.name,
)
```

Then pass:

```python
prompt_plan=transformed_plan
```

Also use transformed plan for fallback provider.

Phase 1 can transform once before the `try` block and reuse it for primary and fallback providers.

## Phase 7: Preserve History and Metadata

In output metadata, preserve:

```text
prompt_transform.original_prompt
prompt_transform.final_prompt
prompt_transform.mode
prompt_transform.fidelity_mode
prompt_transform.constraints
prompt_transform.guard_applied
```

No database schema change is required if this is stored in `prompt_plan.user_variables`.

## Phase 8: Add Tests

Add tests for:

- constraint extraction
- guarded prompt construction
- mode mapping
- stable mode no semantic transformation
- enhanced mode guard injection
- generation.py uses transformed prompt plan
- provider still receives `generation_prompt`

## Phase 9: Do Not Build Yet

Do not implement in phase 1:

- UI toggle
- template importer UI
- prompt snippet UI
- image critic
- LLM rewrite/refine
- variant generation
- scoring model

These can be phase 2+ features.
