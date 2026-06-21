# 03 Agent and Module Spec

This document defines the recommended V3 agent roles, module boundaries, schemas, and first-pass implementation structure.

## 1. Target Directory Structure

Recommended first-pass directory structure:

```text
alchemy_creative_agent_3_0/
  README.md
  docs/
    00_ROOT_RULES.md
    01_PRODUCT_VISION.md
    02_SYSTEM_ARCHITECTURE.md
    03_AGENT_AND_MODULE_SPEC.md
    04_OPEN_SOURCE_REFERENCE_MAP.md
    05_DEVELOPMENT_ROADMAP.md
    06_CODEX_TASK_PROMPT.md
  app/
    __init__.py
    creative_core/
      __init__.py
      orchestrator.py
      pipeline.py
      context.py
    schemas/
      __init__.py
      creative_job.py
      commercial_brief.py
      brand_profile.py
      creative_plan.py
      series_plan.py
      layout_plan.py
      prompt_compilation.py
      condition_plan.py
      generation_plan.py
      evaluation.py
      asset_pack.py
    agents/
      __init__.py
      base.py
      intent_agent.py
      commercial_strategy_agent.py
      brand_memory_agent.py
      creative_director_agent.py
      series_planner_agent.py
      layout_agent.py
      prompt_compiler_agent.py
      generation_router_agent.py
      critic_refiner_agent.py
    brand_memory/
      __init__.py
      store.py
      profile_service.py
      preference_update.py
      reference_assets.py
    layout_engine/
      __init__.py
      planner.py
      typography.py
      html_renderer.py
      svg_renderer.py
    prompt_compiler/
      __init__.py
      compiler.py
      constraints.py
      provider_notes.py
    condition_engine/
      __init__.py
      providers.py
      style_condition.py
      layout_condition.py
      identity_condition.py
    generation_router/
      __init__.py
      router.py
      providers.py
      candidates.py
    evaluation/
      __init__.py
      scorers.py
      commercial_critic.py
      brand_consistency.py
      refine_policy.py
    asset_pack/
      __init__.py
      packager.py
      manifest.py
    tests/
      test_schemas.py
      test_intent_agent.py
      test_commercial_brief.py
      test_brand_memory.py
      test_creative_plan.py
      test_series_planner.py
      test_layout_plan.py
      test_prompt_compiler.py
      test_condition_plan.py
      test_generation_plan.py
      test_evaluation_report.py
      test_refinement_policy.py
      test_end_to_end_planning.py
```

This directory is intentionally independent from V1 and V2.

## 2. Agent Contracts

All agents should follow a simple contract:

```python
class AgentResult(BaseModel):
    output: object
    reasoning_summary: str | None = None
    metadata: dict = Field(default_factory=dict)
```

Do not store hidden decision-making without metadata.

Each agent should accept structured inputs and produce structured outputs.

## 3. IntentAgent

### Responsibility

Convert raw natural-language user input into a structured `CreativeJob` and initial task interpretation.

### Inputs

```text
raw_user_input
optional_brand_id
optional_template_id
optional_uploaded_assets
locale
```

### Outputs

```text
CreativeJob
```

### Required Inferences

- language
- industry guess
- asset type guess
- requested platforms
- explicit constraints
- implicit constraints
- whether clarification is required

### Clarification Policy

Default behavior: avoid asking follow-up questions unless the task cannot be executed safely or meaningfully.

For small-business users, the system should make reasonable defaults.

## 4. CommercialStrategyAgent

### Responsibility

Convert `CreativeJob` into `CommercialBrief`.

### Inputs

```text
CreativeJob
optional BrandProfile
optional template hints
```

### Outputs

```text
CommercialBrief
```

### Required Fields

- industry
- scenario
- business goal
- target audience
- target platform
- conversion objective
- selling points
- emotional tone
- copywriting strategy
- commercial risks

### Example

Input:

```text
“帮我做一个火锅店冬季套餐推广图。”
```

Output should include:

```text
industry: restaurant / hotpot
scenario: winter set meal promotion
business_goal: drive local conversion
visual_hook: warm, abundant, appetite-driven
copy_strategy: clear offer + dish richness + urgency
```

## 5. BrandMemoryAgent

### Responsibility

Read, create, summarize, and update brand memory.

### Inputs

```text
CreativeJob
CommercialBrief
optional brand_id
optional user-selected assets
```

### Outputs

```text
BrandProfile
MemoryUpdate
```

### BrandProfile Should Store

- brand name
- industry
- visual tone
- color palette
- layout preference
- typography preference
- copywriting tone
- reference assets
- previous successful outputs
- rejected styles
- platform history

### Update Policy

Do not update brand memory with every generated candidate.

Update only from:

- accepted final outputs
- user-selected outputs
- high-scoring candidates
- explicit user preference

## 6. CreativeDirectorAgent

### Responsibility

Create the overall visual and creative direction.

### Inputs

```text
CreativeJob
CommercialBrief
BrandProfile
optional template references
```

### Outputs

```text
CreativePlan
```

### CreativePlan Should Include

- campaign concept
- visual direction
- emotional tone
- composition strategy
- lighting strategy
- material / prop suggestions
- camera / illustration style
- color usage
- commercial copy strategy
- consistency strategy
- risk notes

### Design Principle

The Creative Director Agent should behave like an art director plus commercial strategist, not like a prompt expander.

## 7. SeriesPlannerAgent

### Responsibility

Decide which asset variants should be generated.

### Inputs

```text
CreativePlan
CommercialBrief
BrandProfile
```

### Outputs

```text
SeriesPlan
```

### Example Asset Types

- main poster
- social media cover
- delivery app cover
- e-commerce product image
- group-buying image
- store display screen
- WeChat Moments poster
- detail page banner

### Platform Defaults

Suggested defaults:

```text
xiaohongshu: 4:5
wechat_moments: 3:4 or 4:5
delivery_app: 1:1
ecommerce_main: 1:1
store_screen: 16:9
poster_print: 3:4 or A-series later
```

## 8. LayoutAgent

### Responsibility

Create `LayoutPlan` for each asset.

### Inputs

```text
AssetSpec
CreativePlan
CommercialBrief
BrandProfile
```

### Outputs

```text
LayoutPlan
```

### LayoutPlan Should Include

- aspect ratio
- visual hierarchy
- product area
- text areas
- logo area
- CTA area
- reserved clean regions
- typography strategy
- rendering mode

### Text Rendering Policy

For commercial posters, default to:

```text
text_rendering = html_overlay
```

The image prompt should tell the model to avoid fake text and reserve clean text areas.

## 9. PromptCompilerAgent

### Responsibility

Compile creative and layout structures into provider-neutral image generation prompts.

### Inputs

```text
CreativePlan
LayoutPlan
BrandProfile
ConditionPlan
ProviderCapability
```

### Outputs

```text
PromptCompilationResult
```

### PromptCompilationResult Should Include

- visual prompt
- negative prompt
- hard constraints
- text policy
- style notes
- layout notes
- provider notes
- metadata

### Important

This is the V3 successor to the V2 prompt transform idea, but it must be V3-owned.

Do not import V2 prompt transform code.

If any V2 behavior is needed, copy it into V3 and rename it under V3 concepts.

## 10. GenerationRouterAgent

### Responsibility

Choose the generation backend and strategy.

### Inputs

```text
PromptCompilationResult
ConditionPlan
GenerationPlan
ProviderCapabilities
```

### Outputs

```text
GenerationExecutionPlan
CandidateResult list later
```

### Routing Logic Examples

```text
Need clean Chinese poster text:
  generate no-text visual + HTML/SVG overlay

Need brand reference style:
  use StyleConditionProvider

Need layout control:
  use LayoutConditionProvider

Need identity consistency:
  use IdentityConditionProvider

Need fast baseline:
  use default image provider
```

## 11. CriticRefinerAgent

### Responsibility

Evaluate candidates and produce refinement actions.

### Inputs

```text
CandidateResult
EvaluationReport
CreativePlan
LayoutPlan
BrandProfile
```

### Outputs

```text
RefinementPlan
```

### RefinementPlan Should Include

- accept / retry / reject
- problems
- root causes
- prompt modifications
- layout modifications
- condition modifications
- provider modifications
- next generation plan

### Example Problems

```text
product is too small
style drifted away from brand profile
background is too cluttered
text area is not clean enough
food does not look appetizing
composition is not platform-friendly
```

## 12. Provider Interfaces

### 12.1 StyleConditionProvider

Used for brand style consistency.

Possible future implementations:

- InstantStyleProvider
- IPAdapterProvider
- SimpleReferenceImageProvider
- NoopStyleProvider

### 12.2 LayoutConditionProvider

Used for structure and composition control.

Possible future implementations:

- ControlNetProvider
- RuleBasedLayoutMapProvider
- PosterLayoutProvider
- NoopLayoutProvider

### 12.3 ScoringProvider

Used for candidate scoring.

Possible future implementations:

- ImageRewardProvider
- VisionLLMCommercialCritic
- BrandConsistencyScorer
- RuleBasedLayoutScorer

### 12.4 GenerationProvider

Used for image generation.

Possible future implementations:

- GPTImageProvider
- FluxProvider
- RecraftProvider
- SDXLProvider
- ComfyUISidecarProvider
- DiffusersProvider

## 13. First-Pass Implementation Scope

The first implementation should not integrate every heavy model.

First-pass scope:

```text
1. V3 directory structure.
2. V3 schemas.
3. Rule-based or LLM-stub agents.
4. BrandProfile in local JSON store.
5. CreativePlan and SeriesPlan generation.
6. LayoutPlan generation with external text policy.
7. PromptCompilationResult generation.
8. GenerationPlan without real heavy sidecars.
9. EvaluationReport schema and mock scorers.
10. End-to-end planning test.
```

## 14. What Not To Do

Do not:

- call V2 generation directly
- import V2 prompt transform directly
- reuse V2 schemas by reference
- add ComfyUI as the first dependency
- expose model parameters to default users
- make the user choose IP-Adapter / ControlNet manually
- depend on GPU-heavy models before core contracts exist

## 15. End-to-End Planning Example

Input:

```text
“帮我做一组烧烤店夜宵促销图，干净高级一点，适合朋友圈和美团。”
```

Expected V3 internal outputs:

```text
CreativeJob
CommercialBrief
BrandProfile
CreativePlan
SeriesPlan
LayoutPlan x N
PromptCompilationResult x N
ConditionPlan x N
GenerationPlan
EvaluationPlan
CommercialAssetPack manifest
```

This planning pipeline should be testable before real image generation is connected.