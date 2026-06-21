# 06 Codex Task Prompt

Use this prompt when assigning the first Alchemy Creative Agent 3.0 implementation task to Codex.

---

## TASK: Implement Independent Alchemy Creative Agent 3.0 Foundation

You are implementing the first foundation milestone for `Alchemy Creative Agent 3.0` inside the `alchemy-media-agent` repository.

This is a new, independent program area.

Read these documents first:

```text
alchemy_creative_agent_3_0/README.md
alchemy_creative_agent_3_0/docs/00_ROOT_RULES.md
alchemy_creative_agent_3_0/docs/01_PRODUCT_VISION.md
alchemy_creative_agent_3_0/docs/02_SYSTEM_ARCHITECTURE.md
alchemy_creative_agent_3_0/docs/03_AGENT_AND_MODULE_SPEC.md
alchemy_creative_agent_3_0/docs/04_OPEN_SOURCE_REFERENCE_MAP.md
alchemy_creative_agent_3_0/docs/05_DEVELOPMENT_ROADMAP.md
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

Recommended structure:

```text
alchemy_creative_agent_3_0/app/
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
    test_end_to_end_planning.py
```

If the repository has an existing test convention that makes another test location necessary, keep the V3 tests clearly scoped under a V3-only test directory.

## Required Schemas

Implement Pydantic models or equivalent typed schemas for:

```text
CreativeJob
CommercialBrief
BrandProfile
CreativePlan
SeriesPlan
AssetSpec
LayoutPlan
PromptCompilationResult
ConditionPlan
GenerationPlan
CandidateResult
EvaluationReport
RefinementPlan
CommercialAssetPack
MemoryUpdate
```

Minimum model requirements:

- every model has a `metadata: dict` field where useful
- every major model has an id or stable name where useful
- schemas are serializable
- schemas can round-trip through dict/json where practical

## Required Pipeline

Implement a V3-owned planning pipeline:

```text
run_creative_planning(user_input: str, optional_brand_id: str | None = None) -> CommercialAssetPack or PlanningResult
```

The first implementation may return a planning result instead of real generated images.

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
9. Evaluation layer creates an evaluation plan or mock EvaluationReport.
10. AssetPackager creates a planning manifest.
```

## First-Pass Agent Behavior

Use deterministic rule-based or lightweight stub behavior for the first pass.

Do not add hidden LLM calls unless the repository already has a V3-approved LLM abstraction.

The first pass must be testable offline.

Examples:

- detect `奶茶` as beverage / milk tea
- detect `烧烤` as restaurant / barbecue
- detect `小红书` as platform with 4:5 recommendation
- detect `外卖` or `美团` as delivery platform with 1:1 recommendation
- use default clean commercial layout if no template is supplied

## Required Commercial Defaults

Include rule-based defaults for common platforms:

```text
xiaohongshu → 4:5
wechat_moments → 3:4 or 4:5
delivery_app → 1:1
ecommerce_main → 1:1
store_screen → 16:9
```

Include first-pass industry defaults for:

```text
beverage / milk tea
restaurant / barbecue
restaurant / hotpot
ecommerce / product
local_service / beauty
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

## Required Brand Memory Behavior

First pass may use in-memory or local JSON storage.

Required behavior:

```text
1. If no brand_id is supplied, create a temporary BrandProfile from the CommercialBrief.
2. If brand_id is supplied and exists, load it.
3. BrandProfile influences CreativePlan and PromptCompilationResult.
4. Do not update brand memory with rejected or mock candidates by default.
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

## Required Tests

Add tests for:

```text
1. schemas serialize and validate
2. Chinese milk tea request produces beverage brief
3. Xiaohongshu request creates 4:5 asset
4. delivery platform request creates 1:1 asset
5. LayoutPlan uses html_overlay text policy
6. PromptCompilationResult includes no-fake-text provider note
7. BrandProfile influences prompt compilation
8. End-to-end planning pipeline completes without V2 imports
9. V3 files do not import forbidden V2 modules
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
EvaluationReport or EvaluationPlan
CommercialAssetPack manifest
```

without importing or calling V1/V2 runtime code.