# 04 API Contracts

This document defines contracts for the Prompt Transform Layer.

## 1. Public Entry Point

```python
from app.services.prompt_transform.transformer import transform_prompt_plan
```

Signature:

```python
def transform_prompt_plan(
    prompt_plan: ImagePromptPlan,
    *,
    mode: str | None = None,
    provider: str | None = None,
    api_mode: str | None = None,
) -> tuple[ImagePromptPlan, PromptTransformResult]:
    ...
```

## 2. Input Contract

Input is existing V2 `ImagePromptPlan`.

Relevant fields:

```python
class ImagePromptPlan(BaseModel):
    plan_id: str
    mode: Literal["template_customize", "smart_enhance", "revision", "batch"]
    prompt: str
    negative_prompt: str = ""
    style_basis: list[dict[str, Any]]
    user_variables: dict[str, Any]
    provider_parameters: dict[str, Any]
    risk_notes: list[str]
    explanation: str = ""
```

## 3. Output Contract

Return a copied `ImagePromptPlan`.

Do not overwrite:

```text
prompt_plan.prompt
```

Write transformed prompt to:

```text
prompt_plan.user_variables["generation_prompt"]
```

Write metadata to:

```text
prompt_plan.user_variables["prompt_transform"]
```

## 4. Metadata Contract

```json
{
  "enabled": true,
  "source": "ilab-gpt-conjure-inspired",
  "reference_files": [
    "codex_image/prompt_guard.py",
    "codex_image/webui/executor_transport.py"
  ],
  "mode": "enhanced",
  "fidelity_mode": "strict",
  "original_prompt": "...",
  "final_prompt": "...",
  "transport_prompt": "...",
  "transport_instructions": null,
  "constraints": [],
  "guard_applied": true,
  "changed": true
}
```

## 5. Mode Contract

### 5.1 Stable

Input:

```text
prompt = user/template prompt
mode = stable
```

Expected:

```text
fidelity_mode = original
final prompt preserves original text
no extra creative rewrite
```

### 5.2 Enhanced

Input:

```text
prompt = V2 base prompt
mode = enhanced
```

Expected:

```text
fidelity_mode = strict
constraints extracted
guard instructions built
guarded prompt used when needed
```

### 5.3 Exploration

Input:

```text
prompt = V2 base prompt
mode = exploration
```

Expected phase 1 behavior:

```text
fidelity_mode = off
prompt returned unchanged except metadata
```

Exploration variants are future V2-native features.

## 6. Provider Contract

The transform layer should be provider-safe.

Existing providers already follow:

```python
plan.user_variables.get("generation_prompt") or plan.prompt
```

So provider code should not need changes in phase 1.

## 7. Failure Contract

On transform failure:

- Do not fail image generation by default.
- Fall back to original `prompt_plan`.
- Record metadata:

```json
{
  "enabled": true,
  "failed": true,
  "error": "..."
}
```

Add a strict setting later if failure should block generation.
