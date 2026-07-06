# 13 Step-by-Step Delivery Plan

This document converts the V3 roadmap into concrete development waves.

The goal is to let the project move step by step without re-discussing architecture before every Codex task.

## Current Project Mode Supersession

Documents 32-68 supersede the older E-Commerce-first V3.8 ordering.

The accepted current direction is:

```text
Project Mode foundation first
General Template project loop first
E-Commerce active only after Project Mode document 42 unfreeze
template selection before project creation after document 45
project detail split into persistent display and one production entry after document 47
LLM reasoning and reusable visual enhancement are upgraded by documents 48-68
future templates activated only through a template registry and accepted specs
```

This is not a rewrite of the V3 foundation. Project Mode wraps the existing V3
job, provider, Scenario Pack, Product API, and shared capability layers.
Document 50 further clarifies that reusable visual enhancement must be owned by
one V3-native Visual Capability Cluster under the shared capability layer, while
the V3 Brain uses one direct LLM checkpoint path with deterministic fallback.
Document 51 extends that cluster with commercial-grade consistency modules:
strong selected-image references, identity/product/brand locks, visual review,
auto retry, best-output selection, and template-specific consistency policy.
Documents 52-66 turn that Lovart-gap closure into executable layers:
post-generation visual review, auto-retry guardrails, General Template variation
modes, real vision inspection, human identity/natural-variation balance,
E-Commerce lifestyle/count/watermark QA, and the Doc58 Identity Anchor +
Strong Reference Loop + General Suite Director closure. Documents 59-64 extend
that closure into mode-aware role differentiation, product slot/label QA,
portrait Lovart benchmarking, portrait-suite role separation, image-edit
provider stability, and the next real-output commercial quality review layer.
Doc64 closes the broader commercial-quality review loop. Doc65 is the latest
authority for reducing AI-face feel in photoreal human outputs through an
independent Human Photorealism / Anti-AI Face layer that can later be reused by
Photography Special-Tuning. Doc66 is the latest closure pass for selected
reference packages, real-review signal packaging, candidate-scoped retry, and
mode-specific quality priorities.
Doc67 remains the boundary and quality-hardening authority: before further tuning, it
cleans up visual-module boundary drift so CentralCreativeBrain and fallback
Brain consume cluster outputs instead of rebuilding child-module logic; then it
refines existing module standards, prompt rules, retry signals, tests, and real
validation criteria.
Doc68 is the casebook-guided tuning base authority: it distills V2 case patterns
and GPT-Image-2 prompt-pattern evidence into compact V3-owned photographic
recipes, then extends existing visual-cluster modules instead of adding
duplicate feature modules.
Doc69 is the latest prompt-atom absorption authority: it keeps Doc68's
architecture, then makes camera, light, texture, reference-truth, product-truth,
negative, and review atom stacks explicit inside the same visual_cluster
casebook helper.
Doc70 is the latest narrow human-realism tuning authority: it keeps Doc69's
module structure and specifically reduces polished AI beauty-face feel through
real-camera imperfection, skin/fabric/hair texture, and anti-beauty-app rules.
Doc71 is the latest attractive-realism balance authority: it keeps Doc70's
anti-AI-face pressure, then restores healthy clear complexion, soft natural
bounce light, fresh summer brightness, and flattering color balance without
skin whitening, face reshaping, or beauty-filter smoothing.
Doc72 is the latest East Asian portrait aesthetic guard authority: it keeps
Doc71's attractive-realism balance, then prevents unnecessary dark/tan/gray skin
in East Asian fresh portrait requests and guards natural head, neck, shoulder,
and upper-body proportions in close crops.
Doc73 is the latest text-only human-suite identity authority: user-selected or
uploaded references always win, but when no user reference exists the first
generated human portrait output becomes a temporary hard identity anchor for
later outputs in the same job.
Doc74 is the latest complex-prompt fidelity authority: detailed prompts keep
more source detail, explicit negative-prompt sections are split into negative
constraints, and provider prompts are warned not to simplify complex cinematic
human scenes into generic portraits.
Doc75 is the latest identity hero, suite director, and strict review closure
authority: V3 must pick or honor a strong identity master, direct the set through
mode-specific visual duties, and strictly review generated outputs with bounded
retry for identity drift, role collapse, AI-face feel, proportion failure,
watermark/text artifacts, and weak commercial finish.
Doc76 is the latest placement-governance authority: universal visual quality
belongs in the V3 foundation, General Template remains simple and
scenario-neutral, and professional suite/package definitions belong in
specialized templates such as E-Commerce, Photography, Brand, and New Media.
Doc77 is the latest foundation-quality tuning authority for real visual review
and aesthetic stability. It extends the Visual Capability Cluster, vision
inspection, provider prompt consumption, and Product API review/retry paths
without adding specialized deliverable maps to General Template.
Doc78 is the final foundation tuning plan before the next specialized-template
phase. It targets long-term subject identity, selected-reference continuity,
beautiful but realistic human rendering, and facial-feature aesthetic
integrity without turning General Template into a professional photography
package.

## 1. Version Naming

For implementation planning, use the following development waves:

```text
V3.0 Foundation
V3.1 Brand Consistency Foundation
V3.2 Generation Loop MVP
V3.3 Commercial Poster Rendering
V3.4 Reference Conditioning Sidecars
V3.5 Product API and Minimal UX
V3.6 Scenario Hub and General Creative Product Integration
V3.6C Commercial Frontend Shell and Scenario Workspace
V3.6C-1 Home-First V3 Frontend Correction
V3.7 General Creative With Shared Capabilities
V3.8 Project Mode Foundation
V3.8A Project Mode Compatibility And Contracts
V3.8B Project-First Frontend And General Template Loop
V3.8C Project Mode Template Interface And Audit
V3.8D Project Workspace Continuation UX
V3.8E Project Context Asset And Feedback Persistence
V3.8F Project To Brand Memory Confirmation
V3.8G Template Manifest Registry And Activation Gate
V3.8H Project Mode Product Experience Quality Gate
V3.8I Project Mode Pre-Development Readiness Handoff
V3.9 E-Commerce Template Project Mode Unfreeze
V3.9A Template-First Workspace And Delete UX Correction
V3.9B Single Production Entry And Suite Flow Correction
V3.9C LLM Brain And General Prompt Cleanliness
V3.9D Native Visual Capability Cluster And Checkpoint Brain
V3.9E Visual Consistency Pro And Lovart Gap Closure
V3.9F Post-Generation Review, Auto Retry, And Variation Modes
V3.9G Human/E-Commerce Visual QA Refinement
V3.9H Identity Anchor, Strong Reference Loop, And General Suite Director
V3.9I Mode-Aware Role Director And Suite Differentiation
V3.9J Lovart-Level Commercial Quality Closure
V3.9K Human Photorealism And Anti-AI Face Layer
V3.9L Strong Reference Real Review And Precise Retry Closure
V3.9M Visual Boundary Cleanup And Quality Reinforcement
V3.9N Casebook-Guided Photographic Recipe Tuning
V3.9O Prompt Atom Realism And Reference Absorption
V3.9P Human Real-Camera AI Feel Reduction Tuning
V3.9Q East Asian Fair Complexion And Proportion Guard
V3.9R First Output Identity Anchor For Text-Only Human Suites
V3.9S Complex Prompt Fidelity And Negative Prompt Absorption
V3.9T Identity Hero, Suite Director, And Strict Review Closure
V3.9U Foundation Vs Specialized Template Governance
V3.9V Real Visual Review And Aesthetic Stability Foundation
V3.9W Long-Term Identity And Beautiful Realism Final Tuning
V3.10 Future Specialization Packs (optional unless explicitly requested)
```

This document now defines the complete current-stage delivery route from V3.0
Foundation through Project Mode. Older V3.1 / V3.2 worker prompts remain useful
historical phase prompts, but they must not cause a one-shot run to stop before
the later required product, UI, and Project Mode waves are complete.

### 1.1 Project Mode Document Map

Use this map when a Codex implementation task begins from the current stage:

```text
32 -> Project Mode core philosophy and long-term control rules.
33 -> Compatibility and migration rules; Project wraps Job and does not replace it.
34 -> ProjectRecord, ProjectContextPackage, timeline, and minimum API contracts.
35 -> Project-first frontend UX; home opens projects, not standalone jobs.
36 -> General Template project flow; first active template and policy-neutral loop.
37 -> Template interface and audit; future templates remain locked.
38 -> Next frontend phase; project workspace continuation UX and state model.
39 -> Implemented Project Mode persistence; references, selected outputs, unselection, rejection feedback, and context snapshots.
40 -> Implemented memory phase; explicit project-to-Brand-Memory confirmation.
41 -> Implemented Template registry phase; activation gate for all future templates.
42 -> Implemented E-Commerce unfreeze phase; project-aware commerce suite generation.
43 -> Product experience quality gate; architecture, beginner UX, complete loop, image-first high-value content.
44 -> Development-entry handoff; materials, code map, tests, manual QA, and exact first coding boundary.
45 -> Current UX correction; template-first creation, two-region project detail, step-based actions, and soft archive/remove controls.
46 -> Scene-subpage selection patch; direct image selection, restored-output selection, and folded workflow artifacts.
47 -> Current continuation UX authority; replace four step cards with one production entry for generating another visual suite.
48 -> V3-owned LLM Brain Adapter; pre-generation reasoning, prompt review, and strong selected-output reference bridge.
49 -> General Template prompt deproductization bugfix; pure General image prompts must not inherit product-poster wording unless product intent is explicit.
50 -> Current visual/brain architecture authority; consolidate reusable visual enhancement into one V3-native Visual Capability Cluster and upgrade the LLM Brain into direct multi-stage checkpoints. Claude Code expert/provider mode is forbidden.
51 -> Current commercial consistency authority; add strong selected-image references, explicit identity/product/brand locks, output visual review, auto retry patches, best-output selection, negative visual memory, and template consistency policy under the Visual Capability Cluster.
52 -> Post-generation visual review, retry, and suite-director foundation; generated outputs must be reviewed before the system presents a commercial result.
53 -> Auto-retry execution guardrails; retries must be bounded, failure-specific, and must not loop blindly.
54 -> General Template variation modes; automatic or manual choice among similar candidates, delivery suite, creative exploration, and format/layout adaptation.
55 -> Real vision inspection authority; generated images must be inspected as images, not only by prompt metadata.
56 -> Human identity/natural-variation balance; preserve recognizable identity while allowing natural expression, pose, angle, crop, and styling variation.
57 -> E-Commerce lifestyle/count/watermark QA; product suites need stronger lifestyle diversity, count control, and watermark rejection.
58 -> Latest Lovart-gap closure authority; selected outputs become project Identity Anchors, continuation uses strong references, batches are reviewed for identity drift/over-cloning, and General Template suites receive purposeful image roles.
59 -> Latest four-mode execution authority; similar candidates, suite expansion, creative exploration, and format/layout adaptation must produce different role recipes, prompts, reviews, retries, and beginner summaries.
60 -> E-Commerce product-suite slot and label QA; product roles, label/logo fidelity, and commercial product slot coverage are acceptance gates.
61 -> Portrait commercial consistency and Lovart benchmark protocol; real portrait suites are compared against identity, variation, role separation, and commercial finish criteria.
62 -> Portrait suite director and natural role separation; delivery-suite portrait roles receive stronger expression, gaze, pose, crop, and scene-depth lanes.
63 -> Image-edit provider health and bounded fallback; strong-reference continuation must not hang indefinitely when upstream image-edit lanes flap.
64 -> Latest commercial-quality closure authority; real generated outputs are reviewed for reference continuity, suite role coverage, commercial finish, artifacts, and issue-specific retry actions.
65 -> Latest human photorealism authority; photoreal people receive realistic skin/expression guidance, anti-AI-face review, strong-reference artifact correction, and future Photography Special-Tuning reuse contracts.
66 -> Latest closure authority; selected outputs are packaged into strong-reference closure, real review emits candidate-scoped signals, retry is issue/candidate scoped, and the four modes expose different quality profiles.
67 -> Latest boundary and quality authority; central/fallback Brain must not instantiate visual child modules, ecommerce role metadata belongs in the ecommerce template path, and existing visual modules receive stricter realism, role, prompt, retry, and real-validation standards.
68 -> Latest casebook-guided recipe authority; V2/GPT-Image-2 prompt experience is distilled into V3-owned visual-cluster recipes for human realism, four-mode role overlays, product lifestyle context, provider prompt consumption, and validation matrices without duplicating modules.
69 -> Latest prompt-atom absorption authority; camera, light, texture, reference, product truth, negative, and review atoms are explicit in visual-cluster recipes.
70 -> Latest human AI-feel reduction authority; real-camera skin, hair, fabric, asymmetry, anti-beauty-app, and anti-face-geometry pressure are applied without changing the architecture.
71 -> Latest attractive-realism balance authority; human portraits must stay real and textured while recovering healthy bright complexion, clean bounce light, fresh expression, and flattering summer color.
72 -> Latest East Asian fair-complexion and proportion guard authority; fresh East Asian portraits should not be unnecessarily darkened/tanned/gray when the user did not ask for it, and close portrait crops must preserve natural head/neck/shoulder/body scale.
73 -> Latest text-only human-suite identity authority; manual user references have priority, otherwise the first generated portrait becomes the hard identity anchor for subsequent outputs in the same job.
74 -> Latest complex prompt fidelity authority; explicit negative prompt sections are split out and detailed action/wardrobe/environment/camera requirements are preserved for provider prompts.
75 -> Latest identity hero and strict suite closure authority; identity master selection, purposeful suite roles, strict visual pass conditions, and Doc75 retryable quality issue codes close the General Template commercial-quality loop.
76 -> Latest placement-governance authority; foundation quality capabilities are shared, General Template stays scenario-neutral, and professional deliverable maps belong to specialized templates.
77 -> Latest foundation-quality tuning authority for stronger real visual review, aesthetic stability issue codes, provider prompt consumption, and bounded retry patches under Doc76 placement rules.
78 -> Final foundation tuning plan before specialized-template work; long-term subject identity, beautiful realism balance, and facial-feature aesthetic integrity must reach 85%+ without adding vertical package roles to General Template.
80 -> Provider-reference upload compression authority; large reference images are compressed only for upstream provider input while originals, previews, and archives stay unchanged.
81 -> Provider-failure retry and Project status sync authority; zero-candidate provider failures receive a bounded fresh provider retry before blocked, while final failures are written to Project timeline and shown clearly in the frontend.
82 -> Project-output reconciliation authority; generated output files must self-heal back into Project timeline, project output history, and frontend recovery when background generation is interrupted after image files are written.
```

Current code-stage priority:

```text
1. Keep 38, 39, and 41 verified while continuing Project Mode development.
2. Keep 40 verified so cross-project brand reuse remains explicit and user-confirmed.
3. Keep the template registry gate in place before activating any future template.
4. Use 43 as the final product-experience gate before accepting any phase.
5. Use 44 before starting code so all materials, scope, tests, and QA steps are ready.
6. Implement 45 before future template work; the user-facing order is Template -> Project -> Project Workspace.
7. Apply 47 after 46; project continuation uses one "continue generating suite" entry, while image selection and Brand Memory stay on the project page.
8. Apply 48 after 47 when pre-generation reasoning is needed; it must stay V3-owned and independent from V1/V2 runtime.
9. Apply 49 after 48 before further real-image tuning; General Template prompt text must stay subject/scene oriented and E-Commerce-only product wording must remain gated.
10. Apply 50 after 49 before deeper visual consistency work; all reusable visual enhancement must be grouped under the V3 shared capability cluster, and the Brain must use one direct checkpoint path.
11. Apply 51 after 50 for Lovart-gap closure; selected images become strong references, identity/product/brand locks become explicit contracts, generated outputs receive review reports, retryable failures use retry patches, and best outputs are selected for commercial delivery.
12. Apply 52-55 after 51 when generated images must be inspected and corrected automatically; retry execution must be bounded and vision-backed.
13. Apply 56 after 55 for human projects; identity must stay recognizable without cloning every face, pose, expression, or camera angle.
14. Apply 57 after 55 for E-Commerce projects; lifestyle diversity, requested count, and watermark rejection become acceptance gates.
15. Apply 58 after 54-56 for General Template Lovart-level continuity; selected images become Identity Anchors and suite outputs must have purposeful roles.
16. Apply 59 after 58 before the next role-director coding pass; the four modes must become functionally different in role recipes, prompts, review, retry, and beginner summaries.
17. Apply 60-63 to harden product QA, portrait benchmarking, portrait-suite role separation, and image-edit stability.
18. Apply 64 after 63 for the next Lovart-quality pass; review actual generated images, audit suite role coverage, evaluate reference continuity, and generate issue-specific retry plans.
19. Apply 65 after 64 for human photorealism; reduce AI-face feel while preserving identity, commercial appeal, and future Photography Special-Tuning module reuse.
20. Apply 66 after 65 for the next Lovart-gap closure; package selected references, expose real-review signals, use candidate-scoped retry, and make four-mode quality priorities explicit.
21. Apply 67 after 66 before adding more modules; clean up visual boundary drift, then tune existing visual modules for stricter Lovart-level quality.
22. Apply 68 after 67 when quality needs more photographic knowledge; add only V3-owned recipe helpers under the Visual Capability Cluster and extend existing modules rather than adding duplicate feature modules.
23. Apply 69-75 as narrow human/product prompt-quality tuning passes inside the same Visual Capability Cluster, prompt compiler, and generation loop; Doc75 is the latest identity hero, suite director, and strict review closure authority.
24. Apply 76 before adding or moving future visual-generation features; classify each change as foundation, General Template, or specialized template work, and keep professional suite/package definitions out of General Template.
25. Apply 77 only as foundation-quality tuning: strengthen real review and aesthetic stability in the Visual Capability Cluster, vision inspector, provider prompt, and review/retry paths without adding vertical suite roles.
26. Apply 78 as the final foundation-quality tuning pass before V3.10: improve long-term identity continuity and beautiful realism balance, preserve facial-feature beauty, and keep implementation inside the existing foundation layers.
27. Apply 80 when uploaded or selected reference images are sent to image-edit providers; provider input copies may be compressed but user-facing originals must remain untouched.
28. Apply 81 whenever real provider generation can fail before any candidate image exists; this is provider-failure recovery, not visual-quality retry, and must stay bounded under Doc53 loop-safety rules.
29. Treat 42 as implemented; do not start V3.10 or another template without its own accepted spec and document 43 gate.
```

## 2. V3.0 Foundation

### Goal

Build an independent planning-only V3 program.

V3.0 must also reserve the product boundary and extension architecture:

```text
independent V3 product entry contract
V3-owned backend API boundary contract
central brain / Creative Core
vertical agent registry
DefaultCommercialPack
platform adapter stubs for account / balance / deployment
```

### User-Facing Capability

The user can input a natural-language request, and the system can produce a full commercial planning chain.

No real image generation is required.

No full frontend UI is required.

### Internal Capability

```text
Natural language
→ CentralCreativeBrain
→ CreativeJob
→ CommercialBrief
→ selected vertical agent pack metadata
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
app_shell contract stubs
platform_adapters contract stubs
schemas
agents
vertical_agents registry + DefaultCommercialPack
creative_core / central brain
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
6. V3 app shell contract reserves an independent title-bar entry.
7. V3 route contract reserves /api/v3/creative-agent namespace.
8. Platform adapter stubs exist for account / balance / deployment.
9. CentralCreativeBrain orchestrates the planning pipeline.
10. VerticalAgentRegistry selects DefaultCommercialPack fallback.
11. Selected vertical pack metadata is included in PlanningResult or pipeline metadata.
```

### Output Status

Codex should report:

```text
V3_FOUNDATION_STATUS: COMPLETE or INCOMPLETE
INDEPENDENCE_STATUS: PASS or FAIL
APP_BOUNDARY_STATUS: PASS or FAIL
VERTICAL_AGENT_EXTENSION_STATUS: PASS or FAIL
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

#### 3.1.7 Vertical Pack Awareness

Brand memory logic should remain compatible with vertical packs.

Examples:

```text
RestaurantPack can later emphasize food cleanliness and appetite.
EcommercePack can later emphasize product consistency and SKU clarity.
BrandIPPack can later emphasize character consistency.
```

V3.1 may keep non-default packs as stubs.

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
test_brand_memory_works_with_selected_vertical_pack_metadata
```

### V3.1 Out of Scope

```text
real image generation
real visual embedding extraction
real IP-Adapter / InstantStyle
real database migration
UI asset library
full vertical agent specialization
```

### V3.1 Acceptance Criteria

```text
1. Persistent BrandProfile store works.
2. Existing BrandProfile changes the creative plan.
3. Existing BrandProfile changes prompt compilation.
4. Continuation requests are handled deterministically.
5. MemoryUpdate proposal exists but is not blindly applied.
6. Tests pass without V2 imports.
7. Brand memory remains compatible with vertical pack metadata.
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

#### 4.2.7 Vertical Pack Scoring Hooks

V3.2 should allow selected vertical packs to influence evaluation policy.

Examples:

```text
EcommercePack can weight product clarity higher later.
RestaurantPack can weight appetite and cleanliness higher later.
BrandIPPack can weight character consistency higher later.
AIMangaDramaPack can weight scene continuity higher later.
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
test_selected_vertical_pack_can_adjust_evaluation_policy_stub
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
full vertical agent specialization
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
9. Vertical pack evaluation hook is reserved.
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

Expose V3 as an independent product API and minimal V3 UI.

### API Concepts

```text
brand
creative job
asset series
candidate
selected result
style continuation
balance estimate
```

### Required Product Boundary

```text
1. V3 has independent title-bar entry.
2. V3 frontend uses V3-owned routes.
3. V3 backend route namespace is /api/v3/creative-agent/*.
4. Shared balance is accessed only through V3BalanceAdapter.
5. Existing V1/V2 generation routes are not used.
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
1. User can create a creative job through V3 API.
2. User can retrieve planning/generation status through V3 API.
3. User can select a result.
4. Selected result can update brand memory.
5. V3 UI entry is independent from V1/V2 UI flows.
```

## 8. V3.6 Scenario Pack Framework and V3 Home UI

### Goal

Expose V3 as a registry-driven scenario hub inside the shared site shell.

This wave is governed by:

```text
17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md
18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md
19_GENERAL_CREATIVE_QUICK_START_PRESETS_SPEC.md
20_GENERAL_COMMON_SCENE_EXECUTION_AND_CONTRACT_CLOSURE_SPEC.md
21_V3_PRODUCT_INTEGRATION_EXECUTION_PROMPT.md
27_V3_COMMERCIAL_FRONTEND_SHELL_AND_PAGE_SPEC.md
30_V3_HOME_FIRST_CARD_AND_HISTORY_FRONTEND_FIX_SPEC.md
31_V3_PRODUCTIZED_MODULE_WORKSPACES_AND_CAPABILITY_AUDIT_SPEC.md
```

This wave is **not part of the current one-shot acceptance target** unless the
user explicitly requests dedicated vertical-pack development. Current-stage
one-shot runs must keep ecommerce, new media, private community, and brand IP as
placeholder cards only.

### Future Priority Order

```text
1. EcommerceAgentFamily
2. NewMediaMarketingAgentFamily
3. PrivateCommunityOperationsAgentFamily
4. BrandIPOperationsAgentFamily
5. AIMangaDramaAgentFamily
6. LocalServiceAgentFamily
```

### Current-Stage Boundary

```text
current one-shot stage:
  build Scenario Hub
  build General Creative
  keep specialization cards as placeholders

future optional stage:
  implement pack-specific forms
  implement pack-owned agents
  implement pack-owned API behavior
  implement pack-specific generation/evaluation strategies
```

### Acceptance Criteria For This Future Optional Wave

```text
1. Vertical packs extend V3 standard schemas.
2. Vertical packs do not fork the runtime.
3. Vertical pack selection is automatic from intent and brief.
4. Vertical pack metadata appears in PlanningResult / GenerationResult.
5. Tests prove default fallback still works.
```

## 15. Sequential Execution Rule

Do not start V3.2 before V3.1 is accepted.

Do not start V3.3 before V3.2 has stable asset pack outputs.

Do not start V3.4 heavy providers before V3 provider interfaces are stable.

Do not start V3.5 frontend/API integration before V3.2 asset pack contracts are stable.

Do not start V3.6 Scenario Hub integration before V3.5 API and minimal UX routes are stable.

Do not start V3.6C commercial frontend shell before V3 route namespace, Scenario
Hub contracts, Product API, Scenario Runtime, and shared capability foundation
are stable.

Do not start V3.8 Project Mode Foundation before General Creative and the V3
commercial frontend shell are stable enough to wrap jobs into projects.

Do not start V3.8D Project Workspace Continuation UX before Project Mode APIs,
project records, project timeline, and General Template project job creation are
accepted.

Do not start V3.8E Project Context Asset And Feedback Persistence before the
project workspace has a clear useful-reference, output-selection, and
continuation interaction model.

Do not start V3.8F Project To Brand Memory Confirmation before selected outputs
and active project references are persisted correctly.

Do not start V3.8G Template Manifest Registry And Activation Gate before the
General Template project loop and pre-Doc42 E-Commerce locked state are both
verified.

Do not accept V3.8H Project Mode Product Experience Quality Gate before the
current project workspace is reviewed against architecture fit, beginner
friendliness, functional completeness, and image-first high-value content.

Do not start a code implementation run before V3.8I Project Mode
Pre-Development Readiness Handoff confirms the exact first implementation
boundary, code map, test commands, manual QA, and non-goals.

Historical Doc42 gate: do not start V3.9 E-Commerce Template Project Mode
Unfreeze before documents 38, 39, 41, 43, and 44 are implemented and accepted.
Document 40 is recommended first when cross-project brand consistency is
required. This gate has now been satisfied for the current implementation.

Do not start V3.10 full vertical packs before V3.9 E-Commerce or another
template-specific accepted spec proves the template activation gate works.
Also do not start V3.10 visual-heavy template work before document 50 is either
implemented or explicitly scoped out by a later accepted spec, because all
future templates must share the same V3-native Visual Capability Cluster.

Even after Project Mode is accepted, future specialization packs remain
separate explicit phases. A normal current-stage one-shot run must stop at the
requested phase boundary plus final audit/smoke validation when all required
gates pass.

## 16. Development Gate Checklist

Before moving from V3.0 to V3.1:

```text
schemas pass
planning pipeline passes
golden cases pass
app boundary stubs pass
vertical registry stub passes
no V2 imports
```

Before moving from V3.1 to V3.2:

```text
brand memory store passes
continuation behavior passes
brand influence tests pass
memory update proposal passes
vertical metadata compatibility passes
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

Before moving from V3.4 to V3.5:

```text
provider interface tests pass
optional sidecar failure degrades gracefully
asset pack contract remains stable
```

Before moving from V3.5 to V3.6:

```text
V3 route namespace passes
V3 UI entry is independent
V3BalanceAdapter boundary is tested
docs 17, 18, 19, 20, and 21 are indexed
Scenario Hub registry contract is accepted
General Creative product/runtime contract is accepted
placeholder card boundary is accepted
```

Before moving from V3.6 to V3.6C:

```text
Scenario Hub cards render from registry data
General Creative card opens the workspace entry
placeholder cards cannot execute jobs
V1, V2, and Alchemy Lab smoke tests pass
no pack-specific vertical workflow has leaked into the current stage
```

Before moving from V3.6C to V3.7:

```text
commercial frontend shell loads
V3 Scenario Hub renders from registry data
General Creative workspace is usable
future placeholder templates cannot create jobs
V1, V2, and Alchemy Lab smoke paths still load
desktop and mobile visual QA pass
```

Before moving from V3.7 to V3.8:

```text
General Creative shared-capability UI is product-language only
General Creative remains policy-neutral
no marketplace or Amazon logic appears in General Creative defaults
project-first direction from documents 32-37 is accepted
E-Commerce remains outside Project Mode until the later Doc42 unfreeze gate
existing job/provider/shared capability tests pass
```

Before moving from V3.8 to V3.8A:

```text
Project Mode is confirmed as an application layer over existing jobs
ScenarioRuntime, ScenarioPack, ProductJobRecord, provider layer, and shared capabilities remain intact
Project Store, Project API, and Project Context Builder are planned or implemented
old job history remains compatible as a source
no V1/V2/Lab runtime dependency is introduced
```

Before moving from V3.8A to V3.8B:

```text
ProjectRecord and ProjectContextPackage contracts are accepted
project APIs create/list/read project records
project jobs require project_id
General Template remains the only active template
E-Commerce remains locked until Doc42; future templates are visible but locked
```

Before moving from V3.8B to V3.8C:

```text
V3 home shows project cards and project history
project detail opens before template work
General Template can create project jobs
selected outputs can enter project context
locked templates cannot create jobs
normal UI hides engineering language
```

Before moving from V3.8C to V3.8D:

```text
template interface rules are accepted
only General Template is active before Doc42
E-Commerce remains locked by backend and frontend before Doc42
Project Mode docs 32-37 are reconciled with docs 29-31
existing V3 tests pass
```

Before moving from V3.8D to V3.9:

```text
project detail is the main continuation surface
active project references persist after refresh
selected outputs influence future project jobs
unselected outputs do not pollute positive context
negative feedback can affect future context
template registry blocks locked templates
product experience quality gate passes
pre-development handoff is complete
General Template project loop remains stable
E-Commerce unfreeze spec in document 42 is accepted
```

Before moving from V3.9 to V3.10:

```text
E-Commerce Template is active only through Project Mode
E-Commerce workspace is visibly different from General Template
E-Commerce project jobs require project_id
E-Commerce project jobs support text-only generation and use product image/reference evidence as a stronger optional consistency lock
E-Commerce generated suite outputs are visible and selectable
General Template remains policy-neutral
Brand Memory is not updated without confirmation
template activation gate has proven isolation
document 50 visual cluster / checkpoint brain gate is implemented
documents 51-65 visual consistency / review / retry / variation / identity /
mode-aware role differentiation / provider stability / commercial quality /
human photorealism gates
are implemented
document 56 human identity balance gate is implemented for human projects
document 57 e-commerce QA gate is implemented for product projects
document 58 Identity Anchor / Strong Reference / Suite Director gate is
implemented for General Template continuation projects
document 59 Mode-Aware Role Director gate is implemented so the four General
Template modes do not collapse into the same suite behavior
document 60 E-Commerce product-suite slot and label QA gate is implemented
document 61 portrait Lovart benchmark protocol is implemented and recorded
document 62 portrait-suite role separation is implemented
document 63 image-edit provider stability and bounded waiting are implemented
document 64 commercial-quality review, suite coverage audit, and issue-specific
retry planning are implemented
document 65 Human Photorealism / Anti-AI Face Layer is implemented for
photoreal human outputs and remains reusable by future Photography Special-Tuning
document 66 selected-reference closure and precise retry packaging is implemented
document 67 visual boundary cleanup and quality reinforcement is implemented
document 68 casebook-guided photographic recipe tuning is implemented when the
current phase requires another Lovart-quality pass
document 82 project-output reconciliation is implemented so interrupted
background generation cannot leave real output files detached from the Project
timeline or frontend output board
```

## 17. Strategic Reminder

The user experience should remain simple at every stage.

Internal complexity may grow, but the default user flow remains:

```text
natural language input -> commercial visual asset series
```

The product boundary remains:

```text
shared domain / homepage / balance / server
+
independent V3 UI / backend / runtime / agents
```
