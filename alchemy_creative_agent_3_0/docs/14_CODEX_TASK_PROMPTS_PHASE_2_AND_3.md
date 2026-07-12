# 14 Codex Task Prompts: Phase 2 and Phase 3

> **Current text-image direction (2026-07-13):** [Doc111](111_V3_PROVIDER_NATIVE_TEXT_AND_ECOMMERCE_CREATIVE_DIRECTION_CORRECTION.md) supersedes any external-overlay, local-font, fixed-copy-region, or deterministic text-rendering task instruction in this historical handoff. New work uses LLM creative direction and provider-native complete-image generation.

This document provides ready-to-use Codex prompts for the second and third V3 development waves.

Use these only after V3.0 foundation is implemented and accepted.

---

# Phase 2 Prompt: V3.1 Brand Consistency Foundation

## TASK: Implement V3.1 Brand Consistency Foundation

You are implementing the second development wave for Alchemy Creative Agent 3.0.

Before starting, read:

```text
alchemy_creative_agent_3_0/README.md
alchemy_creative_agent_3_0/docs/00_ROOT_RULES.md
alchemy_creative_agent_3_0/docs/07_SCHEMA_CONTRACTS.md
alchemy_creative_agent_3_0/docs/08_GOLDEN_CASES.md
alchemy_creative_agent_3_0/docs/09_RULES_AND_DEFAULTS.md
alchemy_creative_agent_3_0/docs/10_BRAND_MEMORY_SPEC.md
alchemy_creative_agent_3_0/docs/13_STEP_BY_STEP_DELIVERY_PLAN.md
alchemy_creative_agent_3_0/docs/15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md
```

## Objective

Implement persistent V3-owned brand memory and make BrandProfile influence the creative planning pipeline.

Keep V3 independent and preserve the central-brain + vertical agent extension architecture from V3.0.

Do not implement real image generation yet.

## Independence Rules

1. Do not import from V1/V2 runtime modules.
2. Do not read V2 user_variables.
3. Do not call V2 prompt transform.
4. Do not use V2 ImagePromptPlan.
5. Do not route V3 behavior through V1/V2 APIs.
6. V3.1 brand memory must be stored under V3-owned storage.
7. Vertical agent packs must remain V3-owned extensions.

## Required Deliverables

### 1. JSON Brand Store

Implement V3-owned JSON brand storage:

```text
alchemy_creative_agent_3_0/data/brand_memory/brands/
```

Required behavior:

```text
create BrandProfile
save BrandProfile
load BrandProfile by brand_id
return temporary fallback if brand_id is missing or unknown
record warning metadata for missing brand_id
```

### 2. BrandProfile Creation From Brief

When no brand exists:

```text
CommercialBrief → temporary BrandProfile
```

Include:

```text
industry
visual_tone
platform_history
copywriting_tone
layout_preference
color_palette defaults
selected_vertical_pack metadata if useful
```

### 3. Brand Influence on CreativePlan

CreativeDirectorAgent must use:

```text
BrandProfile.visual_tone
BrandProfile.color_palette
BrandProfile.layout_preference
BrandProfile.copywriting_tone
BrandProfile.rejected_style_tags
selected VerticalAgentPack metadata
```

### 4. Brand Influence on PromptCompilationResult

PromptCompilerAgent must include:

```text
brand tone notes
brand color notes
negative style constraints
consistency strategy
vertical pack notes if any
```

### 5. Continuation Request Support

Detect phrases such as:

```text
沿用上次风格
继续上次
保持之前风格
还是那个风格
同一个品牌风格
```

Behavior:

```text
if optional_brand_id exists and is found: load persistent BrandProfile
if optional_brand_id missing: create temporary profile and warning metadata
```

### 6. MemoryUpdate Proposal

Create proposed MemoryUpdate for accepted or structurally valid planning outputs.

Do not apply updates by default.

Do not update memory for rejected/mock failed candidates.

### 7. Vertical Pack Compatibility

Brand memory must remain compatible with the vertical agent registry.

Required behavior:

```text
selected vertical pack metadata is preserved
brand profiles can store industry and style data without locking to one vertical pack
DefaultCommercialPack fallback still works
```

## Required Tests

Add or update tests:

```text
test_brand_profile_save_and_load
test_missing_brand_id_falls_back_to_temporary_profile
test_brand_profile_created_from_commercial_brief
test_brand_profile_influences_creative_plan
test_brand_profile_influences_prompt_compilation
test_rejected_style_tags_in_negative_direction
test_continuation_request_loads_brand_profile
test_continuation_without_brand_id_warns_and_uses_temporary_profile
test_memory_update_is_proposed_not_applied_by_default
test_mock_rejected_candidate_does_not_update_memory
test_brand_memory_preserves_selected_vertical_pack_metadata
test_default_vertical_pack_still_works_with_brand_memory
test_v3_1_no_v2_imports
```

## Out of Scope

Do not implement:

```text
real image generation
IP-Adapter
InstantStyle
ControlNet
ImageReward
ComfyUI sidecar
production database
full UI
full vertical agent specialization
real balance charging
```

## Acceptance Criteria

Report:

```text
V3_1_BRAND_MEMORY_STATUS: COMPLETE or INCOMPLETE
INDEPENDENCE_STATUS: PASS or FAIL
VERTICAL_AGENT_COMPATIBILITY_STATUS: PASS or FAIL
TEST_STATUS: PASS or FAIL
```

Success requires:

```text
1. Persistent BrandProfile store works.
2. BrandProfile influences CreativePlan.
3. BrandProfile influences PromptCompilationResult.
4. Continuation requests are handled.
5. MemoryUpdate proposal exists.
6. Vertical pack metadata remains compatible.
7. All tests pass without V1/V2 runtime imports.
```

---

# Phase 3 Prompt: V3.2 Generation Loop MVP

## TASK: Implement V3.2 Generation Loop MVP

You are implementing the third development wave for Alchemy Creative Agent 3.0.

Before starting, read:

```text
alchemy_creative_agent_3_0/README.md
alchemy_creative_agent_3_0/docs/00_ROOT_RULES.md
alchemy_creative_agent_3_0/docs/07_SCHEMA_CONTRACTS.md
alchemy_creative_agent_3_0/docs/10_BRAND_MEMORY_SPEC.md
alchemy_creative_agent_3_0/docs/11_EVALUATION_AND_REFINEMENT_SPEC.md
alchemy_creative_agent_3_0/docs/12_PROVIDER_INTERFACES.md
alchemy_creative_agent_3_0/docs/13_STEP_BY_STEP_DELIVERY_PLAN.md
alchemy_creative_agent_3_0/docs/15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md
```

## Objective

Implement the first real generation loop structure.

The system should create candidates, score candidates, select the best candidate, produce refinement plans for weak candidates, and package selected outputs.

Real image generation is optional. Mock generation is acceptable if no provider is ready.

Keep the generation loop under the Central Creative Brain and preserve vertical agent pack extension points.

## Independence Rules

1. Do not import from V1/V2 runtime modules.
2. Do not call V1/V2 generation services.
3. Do not call V2 prompt transform.
4. Do not store V3 state in V2 structures.
5. Provider interfaces must be V3-owned.
6. Do not route V3 generation through V1/V2 APIs.
7. Do not couple generation loop behavior to V1/V2 frontend state.

## Required Deliverables

### 1. GenerationProvider Interface

Implement:

```text
GenerationProvider
PlanningOnlyGenerationProvider
MockGenerationProvider
```

MockGenerationProvider should return deterministic CandidateResult objects.

### 2. Scoring Execution

Implement:

```text
MockScoringProvider
RuleBasedPlanningScorer
```

EvaluationReport must include:

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

Use the formula and thresholds from:

```text
11_EVALUATION_AND_REFINEMENT_SPEC.md
```

### 3. Candidate Ranking

Implement ranking:

```text
1. remove hard failures
2. sort by overall_score desc
3. tie-break commercial_score
4. tie-break brand_consistency_score
5. tie-break text_region_score
```

### 4. RefinementPlan Generation

Implement rule-based repairs for:

```text
missing_text_region
fake_text_risk
missing_product_area
brand_style_missing
platform_ratio_mismatch
commercial_hook_missing
```

### 5. Retry Loop

Implement:

```text
max_refine_rounds: 2
```

If a candidate is weak and retry budget remains:

```text
EvaluationReport → RefinementPlan → update plan → generate new candidate
```

The update can be lightweight and deterministic.

### 6. AssetPack With Selected Candidate

CommercialAssetPack must include:

```text
selected candidate
asset metadata
layout_plan_id
prompt_compilation_id
evaluation_id
warnings
manifest
brand_memory_update proposal when accepted
selected vertical pack metadata
```

### 7. MemoryUpdate Interaction

Accepted candidates may produce proposed MemoryUpdate.

Rejected candidates must not update memory.

Default behavior:

```text
propose only, do not apply automatically
```

### 8. Vertical Pack Evaluation Hook

Selected vertical packs may optionally adjust scoring policy through a V3-owned hook.

First-pass hook may be no-op.

Required examples to preserve for future:

```text
EcommerceAgentFamily can later weight product visibility higher.
RestaurantAgentFamily can later weight appetite and cleanliness higher.
BrandIPAgentFamily can later weight character consistency higher.
AIMangaDramaAgentFamily can later weight scene continuity higher.
```

## Required Tests

Add or update tests:

```text
test_mock_generation_creates_candidates
test_candidates_are_scored
test_overall_score_formula
test_best_candidate_is_selected
test_hard_failure_candidate_is_not_selected
test_retry_creates_refinement_plan
test_retry_budget_is_respected
test_missing_text_region_repair
test_fake_text_risk_repair
test_brand_style_missing_repair
test_asset_pack_contains_selected_candidate
test_asset_pack_preserves_selected_vertical_pack_metadata
test_accepted_candidate_proposes_memory_update
test_rejected_candidate_does_not_update_memory
test_vertical_pack_evaluation_hook_noop_by_default
test_generation_loop_runs_without_v2_imports
```

## Out of Scope

Do not implement yet:

```text
IP-Adapter
InstantStyle
ControlNet
ImageReward
ComfyUI sidecar
production renderer
full UI
video generation
full vertical agent specialization
real balance charging
```

A real image provider may be added only if it is trivial and does not break V3 independence, but mock generation is acceptable for this milestone.

## Acceptance Criteria

Report:

```text
V3_2_GENERATION_LOOP_STATUS: COMPLETE or INCOMPLETE
INDEPENDENCE_STATUS: PASS or FAIL
VERTICAL_AGENT_HOOK_STATUS: PASS or FAIL
TEST_STATUS: PASS or FAIL
```

Success requires:

```text
1. Candidate loop exists.
2. Candidates are scored.
3. Best candidate is selected.
4. Weak candidates can produce RefinementPlan.
5. Retry budget is enforced.
6. AssetPack includes selected candidate metadata.
7. MemoryUpdate proposal is connected.
8. Vertical evaluation hook exists as no-op or functional extension.
9. Tests pass without V1/V2 runtime imports.
```
