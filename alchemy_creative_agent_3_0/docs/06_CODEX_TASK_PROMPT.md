# 06 Codex Task Prompt

Use this prompt when assigning the first Alchemy Creative Agent 3.0 implementation task to Codex.

---

## TASK: Implement Independent Alchemy Creative Agent 3.0 Foundation

You are implementing the first foundation milestone for `Alchemy Creative Agent 3.0` inside the `alchemy-media-agent` repository.

This is a new, independent program area.

## Read These Documents First

Core docs:

```text
alchemy_creative_agent_3_0/README.md
alchemy_creative_agent_3_0/docs/00_ROOT_RULES.md
alchemy_creative_agent_3_0/docs/01_PRODUCT_VISION.md
alchemy_creative_agent_3_0/docs/02_SYSTEM_ARCHITECTURE.md
alchemy_creative_agent_3_0/docs/03_AGENT_AND_MODULE_SPEC.md
alchemy_creative_agent_3_0/docs/04_OPEN_SOURCE_REFERENCE_MAP.md
alchemy_creative_agent_3_0/docs/05_DEVELOPMENT_ROADMAP.md
```

Development contract docs:

```text
alchemy_creative_agent_3_0/docs/07_SCHEMA_CONTRACTS.md
alchemy_creative_agent_3_0/docs/08_GOLDEN_CASES.md
alchemy_creative_agent_3_0/docs/09_RULES_AND_DEFAULTS.md
alchemy_creative_agent_3_0/docs/10_BRAND_MEMORY_SPEC.md
alchemy_creative_agent_3_0/docs/11_EVALUATION_AND_REFINEMENT_SPEC.md
alchemy_creative_agent_3_0/docs/12_PROVIDER_INTERFACES.md
alchemy_creative_agent_3_0/docs/13_STEP_BY_STEP_DELIVERY_PLAN.md
```

Phase 2 / Phase 3 prompts are for later and should not be implemented in this task:

```text
alchemy_creative_agent_3_0/docs/14_CODEX_TASK_PROMPTS_PHASE_2_AND_3.md
```

## Objective

Build the V3 independent skeleton and planning pipeline.

The goal is not to generate real images yet.

The goal is to make a natural-language commercial visual request flow through V3-owned schemas and agents into a complete, auditable generation plan without importing or calling V1/V2 runtime code.

## Absolute Independence Rules

1. Do not import from V1 or V2 runtime modules.
2. Do not call V1 or V2 services.
3. Do not use V2 `ImagePromptPlan` as a V3 core schema.
4. Do not write V3 state into V2 `user_variables`.
5. Do not call V2 prompt transform code.
6. If behavior from V2 is useful, copy it into V3, rename it, adapt it, and test it as V3-owned code.
7. V3 must be able to run its tests without loading V2 runtime modules.

Forbidden examples:

```python
from custom_media_agent_2_0.app.services.generation import ...
from custom_media_agent_2_0.app.services.prompt_transform import ...
from custom_media_agent_2_0.app.models import ...
```

## Target Directory

Create V3 code under:

```text
alchemy_creative_agent_3_0/app/
```

Create V3 tests under:

```text
alchemy_creative_agent_3_0/tests/
```

Recommended structure:

```text
alchemy_creative_agent_3_0/
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
    layout_engine/
      __init__.py
      planner.py
    prompt_compiler/
      __init__.py
      compiler.py
    condition_engine/
      __init__.py
      providers.py
    generation_router/
      __init__.py
      router.py
    evaluation/
      __init__.py
      scorers.py
      refine_policy.py
    asset_pack/
      __init__.py
      packager.py
  tests/
    test_schemas.py
    test_rules_and_defaults.py
    test_golden_cases.py
    test_end_to_end_planning.py
    test_no_v2_imports.py
```

If the repository has an existing test convention that makes another test location necessary, keep the V3 tests clearly scoped under a V3-only test directory.

## Required Schemas

Implement the schema contracts in:

```text
alchemy_creative_agent_3_0/docs/07_SCHEMA_CONTRACTS.md
```

Required schemas:

```text
CreativeJob
CommercialBrief
BrandProfile
ReferenceAsset
CreativePlan
SeriesPlan
AssetSpec
LayoutPlan
LayoutRegion
PromptCompilationResult
ConditionPlan
ConditionSpec
GenerationPlan
CandidateResult
EvaluationReport
EvaluationProblem
RefinementPlan
CommercialAssetPack
PackagedAsset
MemoryUpdate
PlanningResult
```

Minimum model requirements:

- every major model has metadata where useful
- every major model has an id or stable name where useful
- schemas are JSON serializable
- schemas can round-trip through dict/json where practical
- scores are normalized between 0.0 and 1.0

## Required Pipeline

Implement a V3-owned planning pipeline:

```text
run_creative_planning(user_input: str, optional_brand_id: str | None = None) -> PlanningResult
```

The first implementation should return a planning result, not real generated images.

The pipeline should do:

```text
1. IntentAgent creates CreativeJob.
2. CommercialStrategyAgent creates CommercialBrief.
3. BrandMemoryAgent creates or loads BrandProfile.
4. CreativeDirectorAgent creates CreativePlan.
5. SeriesPlannerAgent creates SeriesPlan.
6. LayoutAgent creates LayoutPlan for each AssetSpec.
7. PromptCompilerAgent creates PromptCompilationResult for each asset.
8. GenerationRouterAgent creates ConditionPlan and GenerationPlan.
9. Evaluation layer creates deterministic planning EvaluationReport.
10. AssetPackager creates CommercialAssetPack manifest.
11. PlanningResult wraps the full chain.
```

## First-Pass Agent Behavior

Use deterministic rule-based or lightweight stub behavior for the first pass.

Do not add hidden LLM calls unless the repository already has a V3-approved LLM abstraction.

The first pass must be testable offline.

Use the rules from:

```text
alchemy_creative_agent_3_0/docs/09_RULES_AND_DEFAULTS.md
```

Examples:

- detect `奶茶` as `beverage`
- detect `烧烤` as `restaurant_barbecue`
- detect `火锅` as `restaurant_hotpot`
- detect `美甲` as `local_service_beauty`
- detect `淘宝主图` as `ecommerce_product`
- detect `小红书` as platform `xiaohongshu` with `4:5`
- detect `外卖` or `美团` as delivery platform with `1:1`
- use default commercial layout if no template is supplied

## Required Golden Case Behavior

Implement tests based on:

```text
alchemy_creative_agent_3_0/docs/08_GOLDEN_CASES.md
```

At minimum, support these golden cases:

```text
1. milk tea + Xiaohongshu + delivery
2. barbecue + WeChat Moments + Meituan
3. hotpot + default platforms
4. beauty / nail salon + Xiaohongshu + WeChat
5. e-commerce headphones + Taobao
6. brand continuation request
7. minimal input defaults
8. explicit Chinese poster text with html_overlay
9. unknown industry but clear platform
```

## Required Commercial Defaults

Include rule-based defaults for common platforms:

```text
xiaohongshu → 4:5
wechat_moments → 4:5 first-pass default
delivery_app → 1:1
meituan → 1:1
eleme → 1:1
taobao / ecommerce_generic → 1:1
store_screen → 16:9
```

Include first-pass industry defaults for:

```text
beverage
restaurant_barbecue
restaurant_hotpot
restaurant_general
ecommerce_product
local_service_beauty
hospitality
unknown
```

## Required Text Rendering Policy

For poster-like commercial assets, default to:

```text
text_rendering = html_overlay
```

The prompt compiler should include a provider note such as:

```text
Generate the product / background / atmosphere only. Reserve clean regions for real text overlay. Do not render fake final Chinese text inside the image.
```

When exact Chinese text appears in user input, preserve it in LayoutPlan metadata or explicit text fields and do not ask the image model to render it as final text.

## Required Brand Memory Behavior

First pass may use in-memory or local JSON storage.

Required behavior:

```text
1. If no brand_id is supplied, create a temporary BrandProfile from the CommercialBrief.
2. If brand_id is supplied and exists, load it from V3-owned storage.
3. If brand_id is supplied but missing, create temporary BrandProfile and warning metadata.
4. BrandProfile influences CreativePlan and PromptCompilationResult.
5. Do not update brand memory with rejected or mock candidates by default.
```

Use the behavior from:

```text
alchemy_creative_agent_3_0/docs/10_BRAND_MEMORY_SPEC.md
```

## Required Evaluation Behavior

First pass may use mock scorers.

Required normalized fields:

```text
aesthetic_score
commercial_score
brand_consistency_score
layout_score
text_region_score
platform_fit_score
overall_score
recommendation
problems
```

Use the formula, thresholds, and problem codes from:

```text
alchemy_creative_agent_3_0/docs/11_EVALUATION_AND_REFINEMENT_SPEC.md
```

In V3.0 foundation, recommendation may be `planning_only` when no real candidates are generated.

## Required Provider Behavior

Implement Noop or PlanningOnly providers from:

```text
alchemy_creative_agent_3_0/docs/12_PROVIDER_INTERFACES.md
```

Required first-pass providers:

```text
PlanningOnlyGenerationProvider
NoopStyleConditionProvider
NoopLayoutConditionProvider
NoopIdentityConditionProvider
MockScoringProvider
NoopRendererProvider
```

Do not integrate heavy providers in this task.

## Required Tests

Add tests for:

```text
1. schemas serialize and validate
2. rule mappings for industry / platform / visual tone
3. golden cases produce expected structures
4. Chinese milk tea request produces beverage brief
5. Xiaohongshu request creates 4:5 asset
6. delivery platform request creates 1:1 asset
7. LayoutPlan uses html_overlay text policy
8. explicit Chinese text is preserved for overlay
9. PromptCompilationResult includes no-fake-text provider note
10. BrandProfile influences prompt compilation
11. PlanningResult contains full chain
12. End-to-end planning pipeline completes without V2 imports
13. V3 files do not import forbidden V2 modules
```

## Out of Scope for First Task

Do not implement yet:

```text
real image generation
real IP-Adapter
real InstantStyle
real ControlNet
real ImageReward
real ComfyUI sidecar
video generation
canvas UI
node workflow UI
production database migration
```

## Implementation Quality Rules

- Keep V3 code readable and explicit.
- Keep agent outputs structured.
- Preserve metadata.
- Avoid hidden side effects.
- Do not invent undocumented runtime dependencies.
- Do not overfit to a single provider.
- Prefer provider-neutral contracts.
- Keep tests deterministic.
- Do not implement V3.1 or V3.2 tasks in this phase unless necessary for the V3.0 contracts.

## Final Output Required From Codex

After implementation, report:

```text
V3_FOUNDATION_STATUS: COMPLETE or INCOMPLETE
INDEPENDENCE_STATUS: PASS or FAIL
TEST_STATUS: PASS or FAIL
```

Also summarize:

```text
- files created
- schemas implemented
- pipeline behavior
- tests added
- any known limitations
```

## Success Definition

The task is successful when a rough user request such as:

```text
帮我做一组奶茶店夏季新品促销图，要清爽、高级一点，适合小红书和外卖平台。
```

can produce a full V3-owned planning chain:

```text
CreativeJob
CommercialBrief
BrandProfile
CreativePlan
SeriesPlan
LayoutPlan
PromptCompilationResult
ConditionPlan
GenerationPlan
EvaluationReport
CommercialAssetPack manifest
PlanningResult
```

without importing or calling V1/V2 runtime code.