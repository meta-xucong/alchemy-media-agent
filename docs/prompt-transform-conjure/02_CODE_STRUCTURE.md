# 02 Code Structure

This document defines the code structure Codex should implement for the V2 Prompt Transform Layer.

The implementation must be source-aligned with `kadevin/ilab-gpt-conjure`.

## 1. Target Directory

Create a new service package:

```text
custom_media_agent_2_0/app/services/prompt_transform/
  __init__.py
  models.py
  guard.py
  modes.py
  transport.py
  transformer.py
  template_importer.py
  snippets.py
  reference_inputs.py
  metadata.py
```

Create tests:

```text
custom_media_agent_2_0/tests/test_prompt_transform_guard.py
custom_media_agent_2_0/tests/test_prompt_transform_modes.py
custom_media_agent_2_0/tests/test_prompt_transform_transformer.py
custom_media_agent_2_0/tests/test_prompt_transform_generation_integration.py
```

If this repository uses a different test folder layout, follow the existing convention but keep these test names.

## 2. Module Responsibilities

### 2.1 `models.py`

Define internal models.

Recommended Pydantic models:

```python
from typing import Literal
from pydantic import BaseModel, Field

PromptTransformMode = Literal["stable", "enhanced", "exploration"]
PromptFidelityMode = Literal["original", "strict", "off"]

class PromptTransformRequest(BaseModel):
    prompt: str
    mode: PromptTransformMode = "enhanced"
    provider: str | None = None
    api_mode: str | None = None
    user_variables: dict = Field(default_factory=dict)
    provider_parameters: dict = Field(default_factory=dict)

class PromptTransformResult(BaseModel):
    original_prompt: str
    final_prompt: str
    mode: PromptTransformMode
    fidelity_mode: PromptFidelityMode
    constraints: list[str] = Field(default_factory=list)
    guard_instructions: str = ""
    transport_prompt: str = ""
    transport_instructions: str | None = None
    changed: bool = False
    metadata: dict = Field(default_factory=dict)
```

### 2.2 `guard.py`

Port or adapt behavior from:

```text
codex_image/prompt_guard.py
```

Required functions:

```python
def extract_prompt_constraints(prompt: str) -> list[str]: ...
def build_prompt_guard_instructions(constraints: list[str]) -> str: ...
def build_original_prompt_instructions() -> str: ...
def build_guarded_prompt(prompt: str, instructions: str) -> str: ...
```

Implementation rule:

- Keep behavior equivalent to reference.
- Do not add new constraint categories in the first pass.
- Keep all regex behavior test-covered.

### 2.3 `modes.py`

Map Alchemy modes to Conjure fidelity modes.

```python
def normalize_transform_mode(value: str | None) -> PromptTransformMode: ...
def mode_to_fidelity(mode: PromptTransformMode) -> PromptFidelityMode: ...
```

Mapping:

```text
stable      -> original
enhanced    -> strict
exploration -> off
```

Rationale:

- Stable means protect the exact V2/template prompt.
- Enhanced means allow the image engine to improve while preserving hard constraints.
- Exploration means do not apply guard wrapping; any variants are V2-native later.

### 2.4 `transport.py`

Adapt behavior from:

```text
codex_image/webui/executor_transport.py
```

Required functions:

```python
def normalize_prompt_fidelity(value: str | None) -> PromptFidelityMode: ...
def prompt_for_transport(prompt: str, *, provider: str | None, api_mode: str | None, prompt_fidelity: PromptFidelityMode, instructions: str) -> str: ...
def instructions_for_transport(*, provider: str | None, api_mode: str | None, instructions: str) -> str | None: ...
```

Alchemy simplification:

- If provider uses a raw Images API and does not support separate instructions, wrap instructions into prompt.
- If provider supports a separate instructions field, return instructions separately.
- For first pass, because existing V2 providers call `client.images.generate/edit` directly, write the final transport prompt into `generation_prompt`.

### 2.5 `transformer.py`

Main public API.

```python
def transform_prompt(request: PromptTransformRequest) -> PromptTransformResult: ...
def transform_prompt_plan(prompt_plan, *, mode: str | None = None, provider: str | None = None) -> tuple[object, PromptTransformResult]: ...
```

`transform_prompt()` behavior:

```text
1. normalize mode
2. map mode to fidelity
3. extract constraints
4. build guard instructions
5. build transport prompt
6. return result with metadata
```

No LLM call in first implementation.

### 2.6 `template_importer.py`

Adapt from:

```text
codex_image/webui/prompt_templates.py
```

Required behavior:

- JSON prompt pack import
- Markdown prompt pack import
- category normalization
- title/content/tag normalization
- variable extraction from `{{ variable }}`

Do not wire this into runtime generation in the first PR unless needed.

### 2.7 `snippets.py`

Adapt from:

```text
codex_image/webui/prompt_snippets.py
```

Required behavior:

- snippet payload normalization
- tag cleanup
- duplicate tag prevention
- max length limits

Do not wire this into runtime generation in the first PR unless needed.

### 2.8 `reference_inputs.py`

Adapt useful parts from:

```text
codex_image/webui/executor_inputs.py
```

Required behavior if implemented:

- file to data URL
- image mime sniffing
- dedupe reference asset IDs

This module is optional in phase 1 because Alchemy already has uploaded asset handling.

### 2.9 `metadata.py`

Create metadata helpers.

```python
def prompt_transform_metadata(result: PromptTransformResult) -> dict: ...
```

Must include:

```json
{
  "prompt_transform": {
    "enabled": true,
    "source": "ilab-gpt-conjure-inspired",
    "mode": "enhanced",
    "fidelity_mode": "strict",
    "constraints": [],
    "changed": true
  }
}
```

## 3. Integration Point

Modify:

```text
custom_media_agent_2_0/app/services/generation.py
```

Current flow:

```python
result = await provider.generate(
    V2ImageProviderRequest(
        run_id=request.run_id,
        prompt_plan=request.prompt_plan,
        input_images=request.input_images,
    )
)
```

Target flow:

```python
from app.services.prompt_transform.transformer import transform_prompt_plan

transformed_plan, transform_result = transform_prompt_plan(
    request.prompt_plan,
    mode=request.prompt_plan.user_variables.get("prompt_transform_mode"),
    provider=provider.name,
)

result = await provider.generate(
    V2ImageProviderRequest(
        run_id=request.run_id,
        prompt_plan=transformed_plan,
        input_images=request.input_images,
    )
)
```

Important:

- Do not overwrite `prompt_plan.prompt`.
- Write final prompt to `prompt_plan.user_variables["generation_prompt"]`.
- Store transform metadata in `prompt_plan.user_variables["prompt_transform"]`.

## 4. Provider Compatibility

Existing providers already support this pattern.

Known provider behavior:

```text
OpenAI provider: uses plan.user_variables["generation_prompt"] or plan.prompt
Doubao provider: uses plan.user_variables["generation_prompt"] or plan.prompt
```

Therefore the enhancement layer should not require provider changes in phase 1.

## 5. Settings

Add config only if needed.

Suggested environment variables:

```text
V2_PROMPT_TRANSFORM_ENABLED=true
V2_PROMPT_TRANSFORM_DEFAULT_MODE=enhanced
```

If adding settings is too invasive, use `prompt_plan.user_variables["prompt_transform_mode"]` first.

## 6. Phase 1 Deliverables

Codex should implement in this order:

1. `models.py`
2. `guard.py`
3. `modes.py`
4. `transport.py`
5. `transformer.py`
6. unit tests for guard/mode/transformer
7. generation.py integration
8. integration test using mock provider

Do not implement UI or database persistence in phase 1.
