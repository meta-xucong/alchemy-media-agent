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
    07_SCHEMA_CONTRACTS.md
    08_GOLDEN_CASES.md
    09_RULES_AND_DEFAULTS.md
    10_BRAND_MEMORY_SPEC.md
    11_EVALUATION_AND_REFINEMENT_SPEC.md
    12_PROVIDER_INTERFACES.md
    13_STEP_BY_STEP_DELIVERY_PLAN.md
    14_CODEX_TASK_PROMPTS_PHASE_2_AND_3.md
    15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md
  app/
    __init__.py
    app_shell/
      __init__.py
      routes.py
      navigation.py
      ui_contracts.py
    platform_adapters/
      __init__.py
      account_adapter.py
      balance_adapter.py
      deployment_adapter.py
    creative_core/
      __init__.py
      orchestrator.py
      pipeline.py
      context.py
      central_brain.py
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
      asset_packager_agent.py
    vertical_agents/
      __init__.py
      registry.py
      base.py
      default_commercial_pack.py
      ecommerce_pack.py
      brand_ip_pack.py
      ai_manga_drama_pack.py
      restaurant_pack.py
      local_service_pack.py
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
    test_rules_and_defaults.py
    test_golden_cases.py
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
    test_app_boundary.py
    test_vertical_agent_registry.py
    test_end_to_end_planning.py
    test_no_v2_imports.py
```

This directory is intentionally independent from V1 and V2.

## 2. App Shell and Product Boundary Modules

### 2.1 app_shell

The `app_shell` package reserves V3's independent product entry and UI contract.

V3 frontend requirements:

```text
1. V3 appears as an independent title-bar entry.
2. Entering V3 opens V3-owned UI.
3. V3 UI calls V3-owned backend APIs.
4. V3 UI state is not coupled to V1/V2 UI state.
5. V3 may coexist on the same domain and home page.
```

First-pass backend docs may create contracts only. Full UI implementation can come later.

### 2.2 platform_adapters

`platform_adapters` isolates the few allowed shared platform dependencies.

Allowed shared systems:

```text
account identity
balance / credit system
deployment environment
platform logging later
```

Adapters:

```text
V3AccountAdapter
V3BalanceAdapter
V3DeploymentAdapter
```

Rules:

```text
1. V3 business logic must not know V1/V2 internals.
2. Shared balance access must go through V3BalanceAdapter.
3. Shared account access must go through V3AccountAdapter.
4. Adapters must be narrow and testable.
```

## 3. Agent Contracts

All agents should follow a simple contract:

```python
class AgentResult(BaseModel):
    output: object
    reasoning_summary: str | None = None
    metadata: dict = Field(default_factory=dict)
```

Do not store hidden decision-making without metadata.

Each agent should accept structured inputs and produce structured outputs.

## 4. Central Creative Brain

The central brain is the orchestrator of the V3 multi-agent system.

Recommended implementation:

```text
creative_core/central_brain.py
creative_core/orchestrator.py
creative_core/pipeline.py
```

Responsibilities:

```text
1. accept user input
2. create pipeline context
3. select vertical agent pack
4. call base agents in order
5. call vertical overrides when registered
6. route provider decisions
7. coordinate evaluation and refinement
8. assemble asset pack
9. preserve metadata
```

The central brain must not become a monolithic prompt expander.

It is an orchestrator.

## 5. Vertical Agent Pack System

V3 must reserve extension points for future industry-specific sub-agents.

Recommended interface:

```python
class VerticalAgentPack:
    name: str
    supported_industries: list[str]
    supported_scenarios: list[str]

    def refine_commercial_brief(self, context): ...
    def refine_creative_plan(self, context): ...
    def refine_series_plan(self, context): ...
    def refine_layout_plan(self, context): ...
    def refine_prompt_compilation(self, context): ...
    def refine_evaluation_policy(self, context): ...
```

First-pass implementation may include only:

```text
DefaultCommercialPack
```

Reserve stubs for:

```text
EcommerceAgentFamily
BrandIPAgentFamily
AIMangaDramaAgentFamily
RestaurantAgentFamily
LocalServiceAgentFamily
```

Rules:

```text
1. Vertical packs extend V3 standard contracts.
2. Vertical packs must not fork the runtime.
3. Vertical packs must not import V1/V2.
4. Vertical packs must preserve metadata showing which pack was selected.
5. If no pack matches, use DefaultCommercialPack.
```

## 6. IntentAgent

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

## 7. CommercialStrategyAgent

### Responsibility

Convert `CreativeJob` into `CommercialBrief`.

### Inputs

```text
CreativeJob
optional BrandProfile
optional template hints
selected VerticalAgentPack
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

## 8. BrandMemoryAgent

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

## 9. CreativeDirectorAgent

### Responsibility

Create the overall visual and creative direction.

### Inputs

```text
CreativeJob
CommercialBrief
BrandProfile
selected VerticalAgentPack
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

## 10. SeriesPlannerAgent

### Responsibility

Decide which asset variants should be generated.

### Inputs

```text
CreativePlan
CommercialBrief
BrandProfile
selected VerticalAgentPack
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
- brand IP character card later
- AI manga drama scene card later

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

## 11. LayoutAgent

### Responsibility

Create `LayoutPlan` for each asset.

### Inputs

```text
AssetSpec
CreativePlan
CommercialBrief
BrandProfile
selected VerticalAgentPack
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

## 12. PromptCompilerAgent

### Responsibility

Compile creative and layout structures into provider-neutral image generation prompts.

### Inputs

```text
CreativePlan
LayoutPlan
BrandProfile
ConditionPlan
ProviderCapability
selected VerticalAgentPack
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

## 13. GenerationRouterAgent

### Responsibility

Choose the generation backend and strategy.

### Inputs

```text
PromptCompilationResult
ConditionPlan
GenerationPlan
ProviderCapabilities
selected VerticalAgentPack
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

## 14. CriticRefinerAgent

### Responsibility

Evaluate candidates and produce refinement actions.

### Inputs

```text
CandidateResult
EvaluationReport
CreativePlan
LayoutPlan
BrandProfile
selected VerticalAgentPack
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

## 15. Provider Interfaces

### 15.1 StyleConditionProvider

Used for brand style consistency.

Possible future implementations:

- InstantStyleProvider
- IPAdapterProvider
- SimpleReferenceImageProvider
- NoopStyleProvider

### 15.2 LayoutConditionProvider

Used for structure and composition control.

Possible future implementations:

- ControlNetProvider
- RuleBasedLayoutMapProvider
- PosterLayoutProvider
- NoopLayoutProvider

### 15.3 ScoringProvider

Used for candidate scoring.

Possible future implementations:

- ImageRewardProvider
- VisionLLMCommercialCritic
- BrandConsistencyScorer
- RuleBasedLayoutScorer

### 15.4 GenerationProvider

Used for image generation.

Possible future implementations:

- GPTImageProvider
- FluxProvider
- RecraftProvider
- SDXLProvider
- ComfyUISidecarProvider
- DiffusersProvider

## 16. First-Pass Implementation Scope

The first implementation should not integrate every heavy model.

First-pass scope:

```text
1. V3 directory structure.
2. V3 schemas.
3. Rule-based or LLM-stub agents.
4. CentralCreativeBrain / Creative Core orchestration.
5. DefaultCommercialPack + vertical agent registry stub.
6. App shell and platform adapter contracts only.
7. BrandProfile in local JSON store.
8. CreativePlan and SeriesPlan generation.
9. LayoutPlan generation with external text policy.
10. PromptCompilationResult generation.
11. GenerationPlan without real heavy sidecars.
12. EvaluationReport schema and mock scorers.
13. End-to-end planning test.
14. No V1/V2 import test.
```

## 17. What Not To Do

Do not:

- call V2 generation directly
- import V2 prompt transform directly
- reuse V2 schemas by reference
- route V3 frontend through V1/V2 APIs
- couple V3 UI state to V1/V2 UI state
- add ComfyUI as the first dependency
- expose model parameters to default users
- make the user choose IP-Adapter / ControlNet manually
- depend on GPU-heavy models before core contracts exist

## 18. End-to-End Planning Example

Input:

```text
“帮我做一组烧烤店夜宵促销图，干净高级一点，适合朋友圈和美团。”
```

Expected V3 internal outputs:

```text
CreativeJob
CommercialBrief
SelectedVerticalAgentPack
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

## 19. Debug Handoff: T003-DEBUG-1 Boundary Failure

### Failure Diagnosis

The failed V3.5 Product API and Minimal UX attempt was rejected because the
worker edited implementation and test files outside the task boundary. The
offending changes were rolled back by orchestration. This was a file-scope
violation, not evidence that the V3.5 product API design was invalid.

### Retry Repair Instructions

The next retry must receive explicit edit scope for the implementation paths it
needs before changing code. Minimum scope for a complete V3.5 repair is:

```text
alchemy_creative_agent_3_0/app/product_api/**
alchemy_creative_agent_3_0/app/app_shell/**
alchemy_creative_agent_3_0/app/platform_adapters/**
alchemy_creative_agent_3_0/tests/test_v3_product_api_minimal_ux.py
any package __init__.py files that must export those modules
```

If that scope is not granted, the retry must not recreate product API or UI code
in unrelated allowed files. It should return blocked with the missing paths.

When scope is granted, the repair must preserve the V3 product boundary:

```text
API namespace: /api/v3/creative-agent/*
balance access: V3BalanceAdapter only
frontend entry: V3-owned UI route independent from V1/V2 flows
generation controls: do not expose seed, sampler, LoRA, ControlNet map,
IP-Adapter scale, or node graph to default users
verification: python -B -m pytest alchemy_creative_agent_3_0/tests
```

## 20. Debug Handoff: T002-DEBUG-1 V3 Test Collection Failure

### Failure Diagnosis

The scoped V3 pytest command failed during collection, before executing the 81
V3 tests, because a generated legacy temp directory was left under
`alchemy_creative_agent_3_0/tests/_tmp_legacy_basetemp_t002` and Windows denied
`os.scandir` access to that path. This was a test-artifact collection problem,
not a V3 vertical-pack selection regression.

The beverage routing regression was already covered by a focused test asserting
that a milk-tea/beverage request with delivery-channel wording selects the
default commercial pack instead of the restaurant pack.

### Retry Repair Instructions

Future retries must keep generated test outputs out of pytest collection. The
V3 test suite owns a local `conftest.py` collection guard that ignores
`alchemy_creative_agent_3_0/tests/_runtime_*`, `_tmp_*`, and `__pycache__`
directories. If another generated artifact blocks collection, extend that guard
inside `alchemy_creative_agent_3_0/tests/conftest.py` instead of editing
top-level pytest configuration or deleting unrelated worktree files.

The next repair attempt should verify both:

```text
python -B -m pytest alchemy_creative_agent_3_0/tests
git status --short
```
