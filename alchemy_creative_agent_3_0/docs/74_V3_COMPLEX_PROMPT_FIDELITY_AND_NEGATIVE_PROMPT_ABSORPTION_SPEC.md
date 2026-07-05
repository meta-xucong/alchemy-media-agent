# 74 V3 Complex Prompt Fidelity And Negative Prompt Absorption Spec

## 1. Purpose

Doc74 fixes a prompt-fidelity gap found while testing detailed human photography
requests.

Complex prompts often contain:

```text
precise scene
body pose
hand interaction
wardrobe
hair/accessories
background actors
environment atmosphere
camera/lens language
color mood
aspect ratio
explicit negative prompt section
```

The old prompt compiler preserved the user request, but it could:

```text
truncate long detailed requests too aggressively
treat an explicit negative prompt section as part of the positive scene
fail to warn the provider not to simplify the detailed request into a generic portrait
```

Doc74 makes complex prompt handling stricter without changing the V3 framework.

## 2. Architecture Boundary

Doc74 stays in existing prompt language and prompt compiler paths:

```text
creative_core.prompt_language
agents.prompt_compiler_agent
generation_router provider final prompt via hard_constraints
```

It must not:

```text
add a new LLM brain mode
add a new visual module
change Project Mode
call V1/V2 runtime code
rewrite the provider layer
```

## 3. Required Behavior

### 3.1 Split Explicit Negative Sections

If the user writes a section such as:

```text
负面提示词：
...
```

V3 must:

```text
remove that section from positive visual_prompt
split its items into negative_prompt
preserve the main positive prompt before the marker
```

Supported markers include:

```text
负面提示词
反向提示词
负面词
反向词
negative prompt
negative:
avoid:
```

### 3.2 Preserve Complex Prompt Detail

For long or highly specific prompts, V3 must add hard constraints:

```text
Preserve the user's detailed scene literally: action, pose, hand interaction,
wardrobe, hair/accessories, environment, camera angle, lens style, color mood,
air/water atmosphere, and aspect ratio must remain visible.

Do not simplify a detailed cinematic portrait request into a generic beauty
portrait, studio portrait, fashion poster, or unrelated close-up.

Treat the explicit negative prompt section only as things to avoid, never as
desired image content.
```

### 3.3 Increase User Prompt Retention

The user request section used by PromptCompiler should keep enough text for
detailed scene descriptions. The accepted limit is raised from 500 characters to
1800 normalized characters.

## 4. Tests

Doc74 focused tests must verify:

```text
Chinese "负面提示词" section is split correctly
positive visual_prompt keeps fountain square, water touch, cream-yellow dress,
35mm documentary style, and vertical 3:4 details
negative_prompt includes oily skin, silicone face, abnormal water splash,
deformed fingers, wrong dress structure, anime/CG/3D render, etc.
negative terms do not appear in visual_prompt
complex-prompt hard constraints are present
```

## 5. Real Validation Prompt

The real validation prompt is the user's evening fountain-square portrait
request:

```text
young Chinese woman at an evening city fountain square, leaning forward,
touching fountain water, cream-yellow chiffon dress, barefoot on wet stone,
short black hair, jewelry, children/crowd/warm lights, low-angle 35mm
documentary portrait, blue-gray evening with warm yellow light, wet air, film
grain, vertical 3:4, with explicit negative prompt section.
```

## 6. Acceptance Criteria

Doc74 is complete when:

```text
1. Complex detailed prompts are not aggressively truncated.
2. Explicit negative prompt sections are not treated as desired content.
3. Provider-facing prompt includes detail-preservation hard constraints.
4. Focused and regression tests pass.
5. A real GPT image 2 validation run is produced from the user's prompt.
6. The output is evaluated for prompt fidelity, hand/water/dress/anatomy quality,
   natural human realism, and overall commercial/photographic finish.
```
