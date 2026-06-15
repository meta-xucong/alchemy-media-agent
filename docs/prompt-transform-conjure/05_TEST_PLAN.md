# 05 Test Plan

This document defines tests for the Prompt Transform Layer.

## 1. Guard Tests

File:

```text
custom_media_agent_2_0/tests/test_prompt_transform_guard.py
```

Cases:

### 1.1 Extract color constraint

Input:

```text
生成产品海报，配色：黑金色，目标人群为高端商务用户
```

Expected constraints include:

```text
色彩：黑金色
目标人群：高端商务用户
```

### 1.2 Extract title/font constraint

Input:

```text
标题字体要Q版圆润可爱
```

Expected constraints include:

```text
标题字体/标题设计：标题字体要Q版圆润可爱
```

### 1.3 Extract limit constraint

Input:

```text
限制：不要出现真人，不要出现品牌logo
```

Expected constraints include:

```text
限制：不要出现真人，不要出现品牌logo
```

### 1.4 Dedupe

Repeated constraints should appear only once.

## 2. Mode Tests

File:

```text
custom_media_agent_2_0/tests/test_prompt_transform_modes.py
```

Cases:

```text
stable -> original
enhanced -> strict
exploration -> off
unknown -> enhanced
```

## 3. Transformer Tests

File:

```text
custom_media_agent_2_0/tests/test_prompt_transform_transformer.py
```

### 3.1 Stable preserves prompt

Input:

```text
A clean product photo of a ceramic mug
```

Expected:

```text
result.fidelity_mode == "original"
result.final_prompt contains original prompt
no creative additions
```

### 3.2 Enhanced applies guard

Input:

```text
生成一张海报，配色：蓝白色，禁止出现真人
```

Expected:

```text
result.fidelity_mode == "strict"
constraints not empty
guard_instructions contains 提示词保真规则
transport_prompt contains 用户原始提示词
```

### 3.3 Exploration does not pretend source has variants

Input:

```text
A futuristic city
```

Expected:

```text
result.fidelity_mode == "off"
result.final_prompt == original prompt
metadata marks exploration as phase1_no_variant
```

## 4. Prompt Plan Integration Tests

File:

```text
custom_media_agent_2_0/tests/test_prompt_transform_generation_integration.py
```

### 4.1 Writes generation_prompt

Given an `ImagePromptPlan`:

```python
ImagePromptPlan(
    plan_id="plan_test",
    mode="smart_enhance",
    prompt="生成产品图，配色：黑金色",
    user_variables={"prompt_transform_mode": "enhanced"},
)
```

Expected:

```python
new_plan.prompt == original prompt
new_plan.user_variables["generation_prompt"] != ""
new_plan.user_variables["prompt_transform"]["mode"] == "enhanced"
```

### 4.2 Provider receives transformed prompt

Mock provider should receive a prompt plan with:

```text
user_variables.generation_prompt
```

### 4.3 Fallback provider uses same transformed plan

If primary provider fails and mock fallback runs, fallback should receive the transformed prompt plan, not the original.

## 5. Regression Tests

Ensure no existing behavior breaks:

- OpenAI provider still reads `generation_prompt` first.
- Doubao provider still reads `generation_prompt` first.
- `plan.prompt` remains original for audit/history.
- image history still records user prompt and final provider input metadata.

## 6. Non-goals for Phase 1 Tests

Do not test:

- LLM rewrite quality
- image critic quality
- visual planning
- prompt scoring
- UI toggles

Those are not part of the reference-source-aligned phase.
