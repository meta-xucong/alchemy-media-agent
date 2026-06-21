# 05 Development Roadmap

This document defines the recommended phased roadmap for Alchemy Creative Agent 3.0.

The roadmap intentionally starts with contracts, schemas, and planning flow before heavy model integrations.

## 1. Roadmap Principle

Do not start by integrating every advanced model.

Start by creating a clean, independent V3 product core.

Recommended order:

```text
1. Independent V3 foundation
2. Creative planning pipeline
3. Brand memory
4. Candidate scoring and refinement
5. Layout and external text rendering
6. Reference conditioning
7. Asset series packaging
8. Heavy provider sidecars
```

## 2. V3.0 Foundation: Creative Core

### Goal

Create the independent V3 program foundation.

### Deliverables

```text
alchemy_creative_agent_3_0/app/
  creative_core/
  schemas/
  agents/
  prompt_compiler/
  tests/
```

### Required Capabilities

- create `CreativeJob` from natural language input
- create `CommercialBrief`
- create `CreativePlan`
- create `SeriesPlan`
- create `LayoutPlan`
- create `PromptCompilationResult`
- create `ConditionPlan`
- create `GenerationPlan`
- create metadata for every stage
- run end-to-end planning without calling V2

### Not Included

- real GPU sidecars
- real IP-Adapter / InstantStyle
- real ControlNet
- real ImageReward
- production file rendering
- video generation

### Acceptance Criteria

```text
1. V3 imports no V1/V2 runtime modules.
2. V3 has its own schemas.
3. Natural language input can produce a complete planning chain.
4. Unit tests cover schemas and planning flow.
5. End-to-end planning test passes.
6. All output has auditable metadata.
```

## 3. V3.1 Brand Memory + Consistency Engine

### Goal

Make brand and image-feature consistency a first-class capability.

### Deliverables

```text
brand_memory/
  store.py
  profile_service.py
  preference_update.py
  reference_assets.py
```

### Required Capabilities

- create a new brand profile from user input
- read existing brand profile by brand id
- store brand tone
- store color palette
- store copywriting tone
- store layout preference
- store reference asset metadata
- update profile based on accepted outputs
- mark rejected styles

### First-Pass Storage

Use a simple V3-owned JSON or SQLite store.

Do not depend on V2 state storage.

### Acceptance Criteria

```text
1. BrandProfile can be created, saved, loaded, and updated.
2. CreativePlan changes when BrandProfile exists.
3. Brand consistency metadata appears in PromptCompilationResult.
4. Tests cover memory creation and update policy.
```

## 4. V3.2 Candidate Scoring + Auto Refine Loop

### Goal

Improve output reliability by generating candidates, scoring them, and refining weak results.

### Deliverables

```text
evaluation/
  scorers.py
  commercial_critic.py
  brand_consistency.py
  refine_policy.py
```

### Required Capabilities

- normalize candidate results
- score candidates with mock or lightweight scorers
- produce `EvaluationReport`
- select best candidate
- create `RefinementPlan` when below threshold
- run up to configured max refine rounds
- preserve refinement metadata

### Scoring Dimensions

```text
aesthetic_score
commercial_score
brand_consistency_score
layout_score
text_region_score
platform_fit_score
overall_score
```

### First-Pass Implementation

Use deterministic mock scoring and rule-based commercial critique.

Real ImageReward or vision-model scoring can be added later.

### Acceptance Criteria

```text
1. Candidate list can be ranked.
2. Weak candidate triggers RefinementPlan.
3. Accepted candidate generates MemoryUpdate proposal.
4. Refinement metadata is recorded.
5. Tests cover accept, retry, and exhausted-retry behavior.
```

## 5. V3.3 Layout Engine + External Text Rendering

### Goal

Make commercial poster structure and Chinese text accuracy reliable.

### Deliverables

```text
layout_engine/
  planner.py
  typography.py
  html_renderer.py
  svg_renderer.py
```

### Required Capabilities

- create platform-specific layout plans
- reserve text regions
- separate visual generation from final text rendering
- generate HTML or SVG overlay plan
- support Chinese text accurately
- produce editable asset metadata

### Text Strategy

Default poster strategy:

```text
1. Generate no-final-text visual background / product image.
2. Reserve clean regions.
3. Render title, price, CTA, brand name, and details with HTML/SVG/Canvas.
```

### Acceptance Criteria

```text
1. LayoutPlan includes text regions and hierarchy.
2. PromptCompilationResult instructs image model not to render fake final text.
3. HTML/SVG renderer can create a simple poster overlay.
4. Tests cover Chinese text preservation.
```

## 6. V3.4 Reference Conditioning Sidecar Interface

### Goal

Prepare V3 for style, layout, identity, and product consistency providers.

### Deliverables

```text
condition_engine/
  providers.py
  style_condition.py
  layout_condition.py
  identity_condition.py
```

### Required Capabilities

- define provider interfaces
- select reference assets from BrandProfile
- create style condition plan
- create layout condition plan
- create identity condition plan
- support Noop providers for tests

### Future Provider Candidates

```text
IPAdapterProvider
InstantStyleProvider
ControlNetProvider
PhotoMakerProvider
InstantIDProvider
ComfyUISidecarProvider
DiffusersProvider
```

### Acceptance Criteria

```text
1. ConditionPlan is provider-neutral.
2. Noop providers pass tests.
3. Provider routing can choose style/layout/identity providers.
4. No heavy GPU dependency is required for foundation tests.
```

## 7. V3.5 Commercial Asset Pack

### Goal

Output usable multi-platform commercial asset series.

### Deliverables

```text
asset_pack/
  packager.py
  manifest.py
  platform_adapter.py
```

### Required Capabilities

- package final outputs by platform
- name assets clearly
- include aspect ratio
- include commercial purpose
- include final copy text
- include brand consistency notes
- include generation metadata
- create reusable brand memory update

### Example Asset Pack

```text
main_poster_4x5.png
xiaohongshu_cover_4x5.png
delivery_cover_1x1.png
wechat_moments_3x4.png
store_screen_16x9.png
manifest.json
brand_update.json
```

### Acceptance Criteria

```text
1. Asset manifest is generated.
2. Every asset has platform and purpose metadata.
3. Brand memory update is included.
4. Tests cover pack generation.
```

## 8. V3.6 Heavy Provider Integration

### Goal

Integrate real advanced providers after core contracts are stable.

### Candidate Integrations

```text
ImageRewardProvider
IPAdapterProvider
InstantStyleProvider
ControlNetProvider
ComfyUISidecarProvider
DiffusersProvider
```

### Integration Rules

- providers must implement V3 interfaces
- providers must be optional
- heavy dependencies must not block core tests
- sidecars are preferred for GPU workflows
- provider failures must degrade gracefully

### Acceptance Criteria

```text
1. At least one real scoring provider works.
2. At least one reference-style provider works.
3. Provider can be disabled without breaking V3 foundation.
4. Tests separate core tests from integration tests.
```

## 9. V3.7 Product API Layer

### Goal

Expose V3 as a simple service API.

### Recommended Endpoints

```text
POST /v3/creative-jobs
GET  /v3/creative-jobs/{job_id}
POST /v3/creative-jobs/{job_id}/generate
POST /v3/creative-jobs/{job_id}/select
GET  /v3/brands/{brand_id}
POST /v3/brands
```

### API Principle

The API should expose product concepts, not model concepts.

Expose:

```text
brand
campaign
asset series
platform
style continuation
selected result
```

Do not expose by default:

```text
sampler
seed
adapter scale
ControlNet type
LoRA weight
node graph
```

## 10. V3.8 Minimal User Interface Later

### Goal

Create a simple natural-language UI after backend flow is stable.

### UI Principle

Default UI should be a chat/input-first production flow:

```text
Input request
→ show generated asset series
→ allow select / regenerate / continue style
```

No professional design UI is required in V3 foundation.

## 11. Milestone Summary

```text
V3.0  Creative Core foundation
V3.1  Brand Memory + Consistency Engine
V3.2  Candidate Scoring + Auto Refine Loop
V3.3  Layout Engine + External Text Rendering
V3.4  Reference Conditioning Provider Interfaces
V3.5  Commercial Asset Pack
V3.6  Heavy Provider Integrations
V3.7  Product API Layer
V3.8  Minimal User Interface
```

## 12. Recommended First Codex Task

The first Codex task should not implement image generation.

It should implement:

```text
V3 independent skeleton
+ schemas
+ rule-based planning pipeline
+ tests
```

Reason:

```text
If the contracts are wrong, advanced model integration will only create a fragile system.
```

## 13. Definition of Success for the Next Development Step

The next development step succeeds if Codex can run:

```text
Natural language input
→ CreativeJob
→ CommercialBrief
→ BrandProfile
→ CreativePlan
→ SeriesPlan
→ LayoutPlan
→ PromptCompilationResult
→ ConditionPlan
→ GenerationPlan
```

without importing or calling V2.