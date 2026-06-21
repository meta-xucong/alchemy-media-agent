# 13 Step-by-Step Delivery Plan

This document converts the V3 roadmap into concrete development waves.

The goal is to let the project move step by step without re-discussing architecture before every Codex task.

## 1. Version Naming

For implementation planning, use the following development waves:

```text
V3.0 Foundation
V3.1 Brand Consistency Foundation
V3.2 Generation Loop MVP
V3.3 Commercial Poster Rendering
V3.4 Reference Conditioning Sidecars
V3.5 Product API and Minimal UX
```

This document focuses especially on V3.1 and V3.2 because they are the second and third development waves after the foundation.

## 2. V3.0 Foundation

### Goal

Build an independent planning-only V3 program.

### User-Facing Capability

The user can input a natural-language request, and the system can produce a full commercial planning chain.

No real image generation is required.

### Internal Capability

```text
Natural language
→ CreativeJob
→ CommercialBrief
→ temporary BrandProfile
→ CreativePlan
→ SeriesPlan
→ LayoutPlan
→ PromptCompilationResult
→ ConditionPlan
→ GenerationPlan
→ EvaluationReport / planning evaluation
→ CommercialAssetPack manifest
```

### Required Modules

```text
schemas
agents
creative_core
brand_memory minimal
layout_engine minimal
prompt_compiler minimal
condition_engine noop
generation_router planning-only
evaluation mock
asset_pack manifest
```

### Acceptance Criteria

```text
1. No V1/V2 runtime imports.
2. All core schemas exist.
3. Golden cases produce expected planning structures.
4. Tests pass offline.
5. No real image generation is attempted.
```

### Output Status

Codex should report:

```text
V3_FOUNDATION_STATUS: COMPLETE or INCOMPLETE
INDEPENDENCE_STATUS: PASS or FAIL
TEST_STATUS: PASS or FAIL
```

## 3. V3.1 Brand Consistency Foundation

This is the second development wave.

### Goal

Make brand memory and commercial consistency operational, even before real image generation is added.

### Why This Comes Second

The product's core advantage is not raw model power.

It is:

```text
brand consistency
commercial structure
repeatable style direction
series coherence
```

Therefore, after the foundation exists, the next step is to make brand memory influence every creative decision.

### User-Facing Capability

The user can say:

```text
沿用上次奶茶店清爽风格，做一个端午节活动图。
```

The system can load an existing BrandProfile and produce a new plan that preserves brand tone.

### Required Functional Additions

#### 3.1.1 Persistent BrandProfile Store

Implement V3-owned JSON storage:

```text
alchemy_creative_agent_3_0/data/brand_memory/brands/brand_<id>.json
```

Required behavior:

```text
create brand profile
save brand profile
load brand profile
handle missing brand id with temporary fallback and warning
```

#### 3.1.2 Brand Influence in CreativePlan

CreativePlan must use:

```text
BrandProfile.visual_tone
BrandProfile.color_palette
BrandProfile.layout_preference
BrandProfile.copywriting_tone
BrandProfile.rejected_style_tags
```

#### 3.1.3 Brand Influence in PromptCompilationResult

PromptCompilationResult must include:

```text
brand style notes
brand color notes
negative style constraints
consistency strategy
```

#### 3.1.4 Brand Influence in LayoutPlan

LayoutPlan should use:

```text
layout_preference
typography_preference
platform_history
```

#### 3.1.5 MemoryUpdate Proposal

When an output is accepted or planning-only pass is structurally valid, create a proposed MemoryUpdate.

Do not apply updates from mock rejected outputs.

#### 3.1.6 Continuation Request Support

Detect continuation phrases:

```text
沿用上次风格
继续上次
保持之前风格
还是那个风格
同一个品牌风格
```

If brand_id exists, load it.

If brand_id is missing, create a temporary profile with warning metadata.

### Required Tests

```text
test_brand_profile_save_and_load
test_missing_brand_id_falls_back_to_temporary_profile
test_brand_profile_influences_creative_plan
test_brand_profile_influences_prompt_compilation
test_rejected_style_tags_in_negative_direction
test_continuation_request_loads_brand_profile
test_mock_rejected_candidate_does_not_update_memory
test_memory_update_is_proposed_for_accepted_output
```

### V3.1 Out of Scope

```text
real image generation
real visual embedding extraction
real IP-Adapter / InstantStyle
real database migration
UI asset library
```

### V3.1 Acceptance Criteria

```text
1. Persistent BrandProfile store works.
2. Existing BrandProfile changes the creative plan.
3. Existing BrandProfile changes prompt compilation.
4. Continuation requests are handled deterministically.
5. MemoryUpdate proposal exists but is not blindly applied.
6. Tests pass without V2 imports.
```

## 4. V3.2 Generation Loop MVP

This is the third development wave.

### Goal

Turn the planning engine into a closed-loop generation system.

V3.2 may still use mock image generation if real providers are not ready, but the candidate loop must become real in structure.

### User-Facing Capability

The user can request a commercial asset series, and the system can:

```text
create multiple candidates
score candidates
choose the best
retry weak plans or weak candidates
package final outputs or mock outputs with metadata
```

### Required Functional Additions

#### 4.2.1 Candidate Generation Abstraction

Implement:

```text
GenerationProvider
PlanningOnlyGenerationProvider
MockGenerationProvider
```

MockGenerationProvider should create deterministic CandidateResult objects.

If a real image provider is available and simple to wire, it can be added behind the interface, but it is not required.

#### 4.2.2 Candidate Ranking

Implement ranking policy:

```text
1. remove hard failures
2. sort by overall_score desc
3. tie-break commercial_score
4. tie-break brand_consistency_score
5. tie-break text_region_score
```

#### 4.2.3 Evaluation Execution

Run evaluation per candidate.

Use the formula from:

```text
11_EVALUATION_AND_REFINEMENT_SPEC.md
```

#### 4.2.4 Refinement Loop Execution

Implement:

```text
max_refine_rounds: 2
```

For weak candidates:

```text
EvaluationReport → RefinementPlan → updated prompt/layout/condition/generation plan → new candidate
```

V3.2 can implement rule-based refinements only.

#### 4.2.5 AssetPack Output

CommercialAssetPack should include:

```text
selected candidate
asset metadata
prompt_compilation_id
layout_plan_id
evaluation_id
warnings
manifest
```

#### 4.2.6 Brand Memory Interaction

If candidate is accepted:

```text
propose MemoryUpdate
optionally apply MemoryUpdate if configured
```

Default:

```text
propose only
```

### Required Tests

```text
test_mock_generation_creates_candidates
test_candidates_are_scored
test_best_candidate_is_selected
test_hard_failure_candidate_is_not_selected
test_retry_creates_refinement_plan
test_retry_budget_is_respected
test_asset_pack_contains_selected_candidate
test_accepted_candidate_proposes_memory_update
test_rejected_candidate_does_not_update_memory
test_generation_loop_runs_without_v2_imports
```

### V3.2 Out of Scope

```text
IP-Adapter
InstantStyle
ControlNet
ImageReward
ComfyUI sidecar
production-grade rendering
full UI
video
```

### V3.2 Acceptance Criteria

```text
1. Generation loop exists.
2. CandidateResult list exists per asset.
3. EvaluationReport is produced per candidate.
4. Best candidate selection works.
5. RefinementPlan is produced for weak candidates.
6. AssetPack contains final selected candidates.
7. Brand memory update proposal is connected.
8. Tests pass without V2 imports.
```

## 5. V3.3 Commercial Poster Rendering

### Goal

Make Chinese commercial poster output more reliable by separating image generation from final text rendering.

### Required Capabilities

```text
HTML/SVG render spec
exact Chinese text preservation
layout-based text overlay
simple poster composition output
manifest with editable text layers
```

### Required Modules

```text
layout_engine/html_renderer.py
layout_engine/svg_renderer.py
asset_pack/render_manifest.py
```

### Acceptance Criteria

```text
1. Explicit Chinese text is preserved exactly.
2. Poster-like assets use external text overlay.
3. HTML or SVG output can be produced from LayoutPlan.
4. Text layer metadata is included in asset manifest.
```

## 6. V3.4 Reference Conditioning Sidecars

### Goal

Add optional style/layout consistency providers.

### Provider Priorities

```text
1. SimpleReferenceStyleProvider
2. ImageRewardProvider or equivalent scoring provider
3. IPAdapterProvider
4. InstantStyleProvider
5. ControlNetProvider
6. ComfyUISidecarProvider or DiffusersProvider
```

### Acceptance Criteria

```text
1. Providers are optional.
2. Core tests pass without GPU dependencies.
3. Reference assets influence ConditionPlan.
4. Style and layout conditions can be routed through provider interfaces.
```

## 7. V3.5 Product API and Minimal UX

### Goal

Expose V3 as a product API and optional minimal UI.

### API Concepts

```text
brand
creative job
asset series
candidate
selected result
style continuation
```

### Do Not Expose by Default

```text
seed
sampler
LoRA
ControlNet map
IP-Adapter scale
node graph
```

### Acceptance Criteria

```text
1. User can create a creative job through API.
2. User can retrieve planning/generation status.
3. User can select a result.
4. Selected result can update brand memory.
```

## 8. Sequential Execution Rule

Do not start V3.2 before V3.1 is accepted.

Do not start V3.3 before V3.2 has stable asset pack outputs.

Do not start V3.4 heavy providers before V3 provider interfaces are stable.

## 9. Development Gate Checklist

Before moving from V3.0 to V3.1:

```text
schemas pass
planning pipeline passes
golden cases pass
no V2 imports
```

Before moving from V3.1 to V3.2:

```text
brand memory store passes
continuation behavior passes
brand influence tests pass
memory update proposal passes
```

Before moving from V3.2 to V3.3:

```text
candidate loop passes
scoring passes
refinement plan passes
asset pack contains selected candidate
```

Before moving from V3.3 to V3.4:

```text
text render spec passes
Chinese text exact preservation passes
render manifest passes
```

## 10. Strategic Reminder

The user experience should remain simple at every stage.

Internal complexity may grow, but the default user flow remains:

```text
natural language input → commercial visual asset series
```