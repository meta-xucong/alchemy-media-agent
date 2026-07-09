# Alchemy Creative Agent 3.0

Alchemy Creative Agent 3.0 is a new, independent product direction for `alchemy-media-agent`.

Its goal is to benchmark the output quality and product completeness of Lovart-like AI design agents while keeping the user experience radically simpler: users should only need to describe what they want in natural language, and the system should automatically expand that intent into a commercially usable, brand-consistent visual asset series.

## Product Positioning

Alchemy Creative Agent 3.0 is not a canvas tool, node workflow tool, or professional design workstation.

It is intended to become an AI commercial visual production agent for non-design users, including:

- small restaurant owners
- local service businesses
- individual e-commerce sellers
- personal entrepreneurs
- operators who need posters, product images, social media covers, and promotional assets but do not understand AI tools, design software, prompts, model parameters, or workflow graphs

The product should behave like an automated creative team:

- commercial strategist
- brand designer
- art director
- photographer
- copywriter
- layout designer
- image generation operator
- quality reviewer
- refinement specialist

The user sees a simple natural-language input. The system performs the complex creative workflow internally.

## Strict Independence Principle

Version 3.0 is a fully independent program area.

It must not directly depend on, import from, or call runtime parameters, interfaces, services, schemas, APIs, frontend state, upload flows, history flows, job records, provider controls, or internal modules from V1, V2, or Alchemy Lab.

If V3 needs behavior, patterns, or utilities from V2, they must be copied into this directory, renamed where appropriate, reviewed, and adapted as V3-owned code.

V3 may use V1/V2/Alchemy Lab only as historical product or interaction references, not as runtime dependencies.

See:

```text
alchemy_creative_agent_3_0/docs/00_ROOT_RULES.md
alchemy_creative_agent_3_0/docs/15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md
```

## Product Boundary

V3 is an independent product area inside the larger site.

Allowed shared platform layer:

```text
same domain
same homepage / site shell
same server / deployment environment
same top-level navigation page
same base visual tokens if they are pure CSS primitives
```

V3-owned layer:

```text
independent title-bar entry
independent V3 UI
independent V3 backend APIs
independent V3 runtime
independent V3 schemas
independent V3 agents
independent V3 provider contracts
independent V3 uploads
independent V3 jobs
independent V3 history
independent V3 local cache keys
independent V3 generation and export flow
```

## Core Product Goal

Input:

```text
Help me create a summer promotion image series for a milk tea shop. Make it clean, fresh, commercial, and suitable for Xiaohongshu and delivery platforms.
```

Expected system behavior:

```text
1. Understand business context.
2. Build a commercial creative brief.
3. Read or create brand memory.
4. Decide the visual direction.
5. Plan a series of assets.
6. Plan layout and typography.
7. Compile generation prompts.
8. Apply style / brand / layout consistency controls.
9. Generate multiple candidates.
10. Score, critique, refine, and regenerate when needed.
11. Export a usable commercial asset pack.
12. Save successful style decisions back into brand memory.
```

Expected output:

```text
- main campaign poster
- Xiaohongshu cover
- delivery platform product image
- WeChat Moments poster
- store display image
- reusable brand style profile
```

## Document Index

Core docs:

```text
alchemy_creative_agent_3_0/docs/00_ROOT_RULES.md
alchemy_creative_agent_3_0/docs/01_PRODUCT_VISION.md
alchemy_creative_agent_3_0/docs/02_SYSTEM_ARCHITECTURE.md
alchemy_creative_agent_3_0/docs/03_AGENT_AND_MODULE_SPEC.md
alchemy_creative_agent_3_0/docs/04_OPEN_SOURCE_REFERENCE_MAP.md
alchemy_creative_agent_3_0/docs/05_DEVELOPMENT_ROADMAP.md
alchemy_creative_agent_3_0/docs/06_CODEX_TASK_PROMPT.md
```

Development contract docs:

```text
alchemy_creative_agent_3_0/docs/07_SCHEMA_CONTRACTS.md
alchemy_creative_agent_3_0/docs/08_GOLDEN_CASES.md
alchemy_creative_agent_3_0/docs/09_RULES_AND_DEFAULTS.md
alchemy_creative_agent_3_0/docs/10_BRAND_MEMORY_SPEC.md
alchemy_creative_agent_3_0/docs/11_EVALUATION_AND_REFINEMENT_SPEC.md
alchemy_creative_agent_3_0/docs/12_PROVIDER_INTERFACES.md
alchemy_creative_agent_3_0/docs/16_V3_FOUNDATION_EXECUTION_GUARDRAILS.md
```

Step-by-step delivery docs:

```text
alchemy_creative_agent_3_0/docs/13_STEP_BY_STEP_DELIVERY_PLAN.md
alchemy_creative_agent_3_0/docs/14_CODEX_TASK_PROMPTS_PHASE_2_AND_3.md
```

Product boundary and extensibility docs:

```text
alchemy_creative_agent_3_0/docs/15_PRODUCT_BOUNDARY_AND_VERTICAL_AGENT_ARCHITECTURE.md
```

Scenario platform and product integration docs:

```text
alchemy_creative_agent_3_0/docs/17_SCENARIO_PACK_PLATFORM_EXTENSION_SPEC.md
alchemy_creative_agent_3_0/docs/18_GENERAL_CREATIVE_PRODUCT_AND_RUNTIME_SPEC.md
alchemy_creative_agent_3_0/docs/19_GENERAL_CREATIVE_QUICK_START_PRESETS_SPEC.md
alchemy_creative_agent_3_0/docs/20_GENERAL_COMMON_SCENE_EXECUTION_AND_CONTRACT_CLOSURE_SPEC.md
alchemy_creative_agent_3_0/docs/21_V3_PRODUCT_INTEGRATION_EXECUTION_PROMPT.md
alchemy_creative_agent_3_0/docs/22_FULL_ROADMAP_ONE_SHOT_EXECUTION_SPEC.md
alchemy_creative_agent_3_0/docs/22_ONE_SHOT_DEV_AGENT_HANDOFF.md
alchemy_creative_agent_3_0/docs/23_ONE_SHOT_DEV_AGENT_HANDOFF.md
alchemy_creative_agent_3_0/docs/23_V3_FOUNDATION_GAP_AUDIT_AND_COMPLETION_SPEC.md
alchemy_creative_agent_3_0/docs/24_V3_SHARED_CAPABILITY_MODULES_FROM_V1_V2_SPEC.md
alchemy_creative_agent_3_0/docs/25_GENERAL_CREATIVE_DOC_DELTA_FOR_SHARED_CAPABILITIES.md
alchemy_creative_agent_3_0/docs/26_ECOMMERCE_SCENARIO_PACK_AND_COMMERCE_CAPABILITY_SPEC.md
alchemy_creative_agent_3_0/docs/27_V3_COMMERCIAL_FRONTEND_SHELL_AND_PAGE_SPEC.md
alchemy_creative_agent_3_0/docs/28_V3_ASSET_UPLOAD_AND_EXPORT_CLOSURE_SPEC.md
alchemy_creative_agent_3_0/docs/29_V3_DEVELOPMENT_DOCUMENT_EXECUTION_AUDIT.md
alchemy_creative_agent_3_0/docs/30_V3_HOME_FIRST_CARD_AND_HISTORY_FRONTEND_FIX_SPEC.md
alchemy_creative_agent_3_0/docs/31_V3_PRODUCTIZED_MODULE_WORKSPACES_AND_CAPABILITY_AUDIT_SPEC.md
alchemy_creative_agent_3_0/docs/32_V3_PROJECT_MODE_CORE_CONTROL_SPEC.md
alchemy_creative_agent_3_0/docs/33_V3_PROJECT_MODE_COMPATIBILITY_AND_MIGRATION_SPEC.md
alchemy_creative_agent_3_0/docs/34_V3_PROJECT_CONTRACT_AND_CONTEXT_SPEC.md
alchemy_creative_agent_3_0/docs/35_V3_PROJECT_FIRST_FRONTEND_UX_SPEC.md
alchemy_creative_agent_3_0/docs/36_V3_GENERAL_TEMPLATE_PROJECT_FLOW_SPEC.md
alchemy_creative_agent_3_0/docs/37_V3_TEMPLATE_INTERFACE_AND_AUDIT_SPEC.md
alchemy_creative_agent_3_0/docs/38_V3_PROJECT_WORKSPACE_CONTINUATION_UX_AND_STATE_SPEC.md
alchemy_creative_agent_3_0/docs/39_V3_PROJECT_CONTEXT_ASSET_AND_FEEDBACK_PERSISTENCE_SPEC.md
alchemy_creative_agent_3_0/docs/40_V3_PROJECT_TO_BRAND_MEMORY_CONFIRMATION_SPEC.md
alchemy_creative_agent_3_0/docs/41_V3_TEMPLATE_MANIFEST_REGISTRY_AND_ACTIVATION_GATE_SPEC.md
alchemy_creative_agent_3_0/docs/42_V3_ECOMMERCE_TEMPLATE_PROJECT_MODE_UNFREEZE_SPEC.md
alchemy_creative_agent_3_0/docs/43_V3_PROJECT_MODE_PRODUCT_EXPERIENCE_QUALITY_GATE_SPEC.md
alchemy_creative_agent_3_0/docs/44_V3_PROJECT_MODE_PRE_DEVELOPMENT_READINESS_HANDOFF.md
alchemy_creative_agent_3_0/docs/45_V3_TEMPLATE_FIRST_WORKSPACE_AND_DELETE_UX_SPEC.md
alchemy_creative_agent_3_0/docs/46_V3_PROJECT_WORKSPACE_SCENE_SUBPAGES_AND_SELECTION_UX_PATCH_SPEC.md
alchemy_creative_agent_3_0/docs/47_V3_SINGLE_PRODUCTION_ENTRY_AND_SUITE_FLOW_SPEC.md
alchemy_creative_agent_3_0/docs/48_V3_LLM_BRAIN_ADAPTER_AND_PRE_GENERATION_REASONING_SPEC.md
alchemy_creative_agent_3_0/docs/49_V3_GENERAL_TEMPLATE_PROMPT_DEPRODUCTIZATION_BUGFIX_SPEC.md
alchemy_creative_agent_3_0/docs/50_V3_NATIVE_VISUAL_CAPABILITY_CLUSTER_AND_CHECKPOINT_BRAIN_SPEC.md
alchemy_creative_agent_3_0/docs/51_V3_VISUAL_CONSISTENCY_PRO_AND_LOVART_GAP_CLOSURE_SPEC.md
alchemy_creative_agent_3_0/docs/52_V3_POST_GENERATION_VISUAL_REVIEW_RETRY_AND_SUITE_DIRECTOR_SPEC.md
alchemy_creative_agent_3_0/docs/53_V3_VISUAL_AUTO_RETRY_EXECUTION_GUARDRAILS_SPEC.md
alchemy_creative_agent_3_0/docs/54_V3_GENERAL_VARIATION_DIRECTOR_AND_MODE_SELECTOR_SPEC.md
alchemy_creative_agent_3_0/docs/55_V3_POST_GENERATION_VISION_INSPECTION_AND_REVIEW_SPEC.md
alchemy_creative_agent_3_0/docs/56_V3_HUMAN_NATURAL_VARIATION_AND_IDENTITY_BALANCE_SPEC.md
alchemy_creative_agent_3_0/docs/57_V3_ECOMMERCE_LIFESTYLE_COUNT_AND_WATERMARK_QA_SPEC.md
alchemy_creative_agent_3_0/docs/58_V3_IDENTITY_ANCHOR_STRONG_REFERENCE_AND_SUITE_DIRECTOR_SPEC.md
alchemy_creative_agent_3_0/docs/59_V3_MODE_AWARE_ROLE_DIRECTOR_AND_SUITE_DIFFERENTIATION_SPEC.md
alchemy_creative_agent_3_0/docs/60_V3_ECOMMERCE_PRODUCT_SUITE_SLOT_AND_LABEL_QA_SPEC.md
alchemy_creative_agent_3_0/docs/61_V3_PORTRAIT_COMMERCIAL_CONSISTENCY_AND_LOVART_BENCHMARK_SPEC.md
alchemy_creative_agent_3_0/docs/62_V3_PORTRAIT_SUITE_DIRECTOR_AND_NATURAL_ROLE_SEPARATION_SPEC.md
alchemy_creative_agent_3_0/docs/63_V3_IMAGE_EDIT_PROVIDER_HEALTH_COOLDOWN_AND_FALLBACK_SPEC.md
alchemy_creative_agent_3_0/docs/64_V3_LOVART_LEVEL_COMMERCIAL_QUALITY_CLOSURE_SPEC.md
alchemy_creative_agent_3_0/docs/65_V3_HUMAN_PHOTOREALISM_AND_ANTI_AI_FACE_LAYER_SPEC.md
alchemy_creative_agent_3_0/docs/66_V3_STRONG_REFERENCE_REAL_REVIEW_AND_PRECISE_RETRY_CLOSURE_SPEC.md
alchemy_creative_agent_3_0/docs/67_V3_VISUAL_BOUNDARY_AND_QUALITY_REINFORCEMENT_SPEC.md
alchemy_creative_agent_3_0/docs/68_V3_CASEBOOK_GUIDED_PHOTOGRAPHIC_RECIPE_TUNING_SPEC.md
alchemy_creative_agent_3_0/docs/68A_V3_CASEBOOK_DISTILLATION_REFERENCE.md
alchemy_creative_agent_3_0/docs/68B_V3_FOUR_MODE_RECIPE_MATRIX.md
alchemy_creative_agent_3_0/docs/68C_V3_DOC68_VALIDATION_AND_ACCEPTANCE_MATRIX.md
```

Implementation agents must not use the foundation prompt alone when the goal is
to build the user-facing 3.0 product. For Scenario Hub, General Creative UI, and
shared-shell integration work, read documents 17 through 23 after the foundation
documents, then read documents 27, 30, and 31 for the current commercial
frontend and productized-workspace target. The full-roadmap one-shot document
and handoff documents are execution bridges for Alchemy Dev Agent / Alchemy Dev
Lab. Document 27 is the commercial frontend shell and page specification; it
supersedes the minimal UI contract as the implementation target for real
user-facing pages.

For current Project Mode work, read documents 32 through 66 after the foundation
and Scenario Platform documents. The intended sequence is: keep V3 independent,
wrap existing jobs into projects, finish the General Template project loop,
persist selected references and feedback, add explicit Brand Memory confirmation,
enforce template activation gates, pass the product experience quality gate, and
use the pre-development handoff before coding. Document 45 is the template-first
frontend interaction correction: template selection happens before project
creation, project detail separates persistent outputs from step-based actions,
and soft archive/remove controls are required. Document 46 is the acceptance
patch for distinct child scenes, direct image selection, restored-output
selection, and folded workflow/prompt artifacts. Document 47 supersedes the
four-step project action card presentation with one beginner-facing production
entry for continuing a project and generating a visual suite. Document 48 adds
V3-owned LLM reasoning before generation. Document 49 fixes General Template
prompt cleanliness after real-image validation. Document 50 is the current
visual/brain architecture authority: reusable visual enhancement must be
consolidated into one V3-native Visual Capability Cluster, and the V3 Brain
must use one direct checkpoint path without Claude Code expert/provider mode.
Documents 51 through 66 are the current Lovart-gap improvement chain: visual
consistency, post-generation review, bounded auto retry, the four General
Template modes, real image inspection, human natural variation, E-Commerce
visual QA, strong identity anchors, and mode-aware role differentiation.
Documents 60 through 68 extend that chain with product slot/label QA, portrait
commercial benchmark validation, stronger portrait-suite role separation,
image-edit provider stability, and the next commercial quality closure layer
for real-output review, suite coverage auditing, issue-specific retry, and
human photorealism / anti-AI-face rendering control. Document 66 adds selected
reference closure packages, real-review signal packages, candidate-scoped retry
signals, and four-mode quality profiles. Document 67 cleans up visual-module
boundaries before further tuning. Document 68 adds V3-owned casebook-guided
photographic recipes distilled from V2 and GPT-Image-2 prompt patterns, while
extending existing visual-cluster modules instead of creating duplicate
functionality.
E-Commerce is now unfrozen only
inside Project Mode through document 42; future templates still require their
own accepted specs, registry activation, and document 43 quality gate checks.

Current Project Mode implementation status:

```text
Documents 32-38 and 43-44 are implemented or reconciled for the project-first
General Template loop.
Document 39 is implemented for project references, selected output state,
unselection, rejection feedback, project context snapshots, and friendly
timeline events.
Document 41 is implemented with a V3-owned template manifest registry,
backend activation gate, structured activation errors, and tests for General,
E-Commerce, and future placeholder boundaries.
Document 40 is implemented for explicit project-to-brand-style confirmation:
proposal creation does not write Brand Memory, and only the user's confirm
action creates or appends a persistent BrandProfile.
Document 42 is implemented for E-Commerce Project Mode unfreeze: E-Commerce
Template is active through the registry, project jobs require product
references, commerce profile data is project-scoped, and the frontend has a
distinct beginner-facing E-Commerce workspace.
Document 45 is implemented for template-first home flow, two-region project
workspace hierarchy, step-based action panels, and beginner-facing soft
archive/remove controls.
Document 46 is an implemented Project Workspace acceptance patch: generated images must be directly selectable
into confirmed references, restored outputs must remain selectable after restart,
and workflow/prompt details must be folded and beginner-friendly. Its four-card
presentation is superseded by document 47.
Document 47 is the current UX authority for project continuation: project pages
keep image-first outputs, confirmed references, workflow artifacts, and Brand
Memory on the main page, while continuation is handled by one "continue
generating suite" production entry and one simple making page.
Document 48 is implemented for V3-owned LLM reasoning and selected-output
reference bridging. Document 49 is implemented for General Template prompt
deproductization. Documents 50 through 68 govern the current visual/brain
upgrade chain: one native Visual Capability Cluster, direct checkpoint Brain,
real review/retry, four-mode continuation, human/product consistency, identity
anchors, strong selected-output references, mode-aware role differentiation,
provider-stable strong-reference continuation, and Lovart-level commercial
quality closure. Document 65 is the reusable human photorealism layer for
General Template now and future Photography Special-Tuning later. Document 66
closes the selected-reference integration gap. Document 67 reinforces module
boundaries and quality standards. Document 68 turns casebook/prompt experience
into compact V3-owned photographic recipes consumed by those same modules.
```

## Implementation Waves

```text
V3.0 Foundation
  Independent planning-only skeleton, schemas, agents, rule-based pipeline, tests.

V3.1 Brand Consistency Foundation
  Persistent V3-owned brand memory, continuation behavior, brand influence on plans and prompts.

V3.2 Generation Loop MVP
  Candidate generation abstraction, scoring, ranking, refinement plan, selected asset packaging.

V3.3 Commercial Poster Rendering
  HTML/SVG text overlay and accurate Chinese commercial poster rendering.

V3.4 Reference Conditioning Sidecars
  Optional IP-Adapter / InstantStyle / ControlNet / ImageReward / ComfyUI-style providers.

V3.5 Product API and Minimal UX
  Simple natural-language product API and user-facing flow.

V3.6 Scenario Pack Framework and V3 Home UI
  Shared-shell 3.0 navigation entry, registry-driven scenario hub, General Creative available card, and placeholder cards for later vertical packs.

V3.6A Foundation Gap Completion
  Complete the Scenario Pack platform, Scenario Runtime, scenario-aware product contracts, and richer job lifecycle records described in document 23.

V3.6B Shared Capability Foundation
  Rewrite useful V1/V2 abilities as V3-owned shared capability modules, including asset analysis, asset binding, case retrieval, visual grammar locking, information integrity, prompt constraints, output review, and history references.

V3.6C Commercial Frontend Shell and Scenario Workspace
  Build the commercial shared-shell frontend target described in document 27: V1/V2/Alchemy Lab/V3 navigation, V3 Scenario Hub, card-module interaction, General Creative workspace, and placeholder boundaries.

V3.6C-1 Home-First V3 Frontend Correction
  Apply document 30: V3 shares only the outer page/navigation, while its home, history, state, uploads, jobs, generation, selection, and export flow remain V3-owned. The first V3 screen shows only agent cards and V3 history; detailed workspaces open after a card/history click.

V3.7 General Creative With Shared Capabilities
  Finish General Creative against documents 18, 19, 20, and 25 while keeping it policy-neutral and free of marketplace-specific logic.

V3.8 Project Mode Foundation
  Apply documents 32-37: Project becomes the main design-chain layer, General Template is the active project template, and E-Commerce/future templates start behind activation gates.

V3.8A Project Mode Compatibility And Contracts
  Apply documents 33 and 34: keep ScenarioRuntime, ScenarioPack, ProductJobRecord, provider layer, and shared capabilities intact while adding Project Store, Project API, Project Context Builder, and project contracts.

V3.8B Project-First Frontend And General Template Loop
  Apply documents 35 and 36: V3 home opens projects, project detail contains template work, and General Template can generate inside a project with selected-output continuation.

V3.8C Project Mode Template Interface And Audit
  Apply document 37: keep General Template active, route all templates through the registry, and audit template boundaries before deeper project continuation work. E-Commerce stays gated here until the later document 42 unfreeze.

V3.8D Project Workspace Continuation UX
  Apply document 38: project detail becomes the continuation surface, with useful references, selected outputs, timeline, and beginner-facing next actions.

V3.8E Project Context Asset And Feedback Persistence
  Apply document 39: persist uploaded references, selected generated outputs, unselected outputs, rejected directions, and project context summaries.

V3.8F Project To Brand Memory Confirmation
  Implemented document 40: let users explicitly save confirmed project style into Brand Memory without automatic writes.

V3.8G Template Manifest Registry And Activation Gate
  Implemented document 41: templates activate only through a V3-owned registry, backend gate, template-specific spec, and tests.

V3.8H Project Mode Product Experience Quality Gate
  Apply document 43: every Project Mode phase must preserve architecture, stay beginner-friendly, complete its promised loop, and prioritize images while showing useful plain-language work results.

V3.8I Project Mode Pre-Development Readiness Handoff
  Apply document 44 before coding: confirm materials, scope, file map, test plan, manual QA, and the exact first implementation boundary.

V3.9 E-Commerce Template Project Mode Unfreeze
  Apply document 42 only after Project Mode is stable: E-Commerce becomes a project-aware template for product-image suite generation.

V3.9A Project Workspace Scene Subpages And Selection UX Patch
  Apply document 46 after document 45: each project action card opens a distinct child scene, generated images can be selected directly, restored outputs can enter project context after restart, and workflow/prompt artifacts are folded for optional review.

V3.9B Single Production Entry And Suite Flow
  Apply document 47 after document 46: replace the four project action cards with one production entry; project outputs, image selection, workflow artifacts, and Brand Memory stay on the project page.

V3.9C LLM Brain And General Prompt Cleanliness
  Implemented documents 48 and 49: use a V3-owned LLM Brain before generation,
  bridge selected outputs as strong references, and keep General Template
  prompts free of product/E-Commerce wording unless the user explicitly asks for
  it.

V3.9D Native Visual Capability Cluster And Checkpoint Brain
  Apply document 50: consolidate reusable visual enhancement under one V3-owned
  Visual Capability Cluster and upgrade the Brain into direct multi-stage
  checkpoints. Do not add Claude Code expert/provider mode.

V3.9E Visual Consistency, Review, Modes, And Role Differentiation
  Apply documents 51 through 59: selected-output strong references, identity
  and product locks, real post-generation review, bounded auto retry, four
  General Template modes, natural human variation, E-Commerce visual QA,
  identity anchors, and mode-aware role-specific suite differentiation.

V3.9F Commercial Quality Closure And Lovart Benchmark Hardening
  Apply documents 60 through 64: product slot/label QA, portrait commercial
  benchmark validation, stronger portrait-suite direction, image-edit provider
  stability, real-output quality review, suite coverage auditing, and
  issue-specific retry planning.

V3.9G Human Photorealism And Photography-Reusable Anti-AI Face Layer
  Apply document 65: add an independent Visual Capability Cluster submodule for
  realistic human skin, expression, minor asymmetry, anti-AI-face review, and
  future Photography Special-Tuning reuse.

V3.9H Strong Reference Real Review And Precise Retry Closure
  Apply document 66: package selected-reference closure, real-review signals,
  candidate-scoped retry, and mode-specific quality profiles under the existing
  V3 Visual Capability Cluster and Product API review/retry path.

V3.9I Casebook-Guided Photographic Recipe Tuning
  Apply document 68: distill V2 casebook and GPT-Image-2 prompt-pattern
  experience into V3-owned visual-cluster recipes for photoreal humans,
  four-mode role direction, product lifestyle context, provider prompt
  consumption, and validation matrices. Extend existing modules; do not add
  duplicate visual frameworks.

V3.10 Future Specialization Packs
  Optional unless explicitly requested. Detailed new-media, private-community, brand-IP, AI manga-drama, and other pack-specific workflows require their own accepted specifications.
```

Current implementation status:

```text
Documents 00-37: implemented, reconciled, audited, or actively governing the accepted current-stage scope.
Documents 38-47: implemented or governing project continuation, context persistence, Brand Memory confirmation, template activation, E-Commerce unfreeze, product experience quality gates, development-entry handoff, template-first UX, scene-subpage/selection behavior, and the single production entry UX.
Documents 48-49: implemented for V3-owned LLM reasoning and General Template prompt cleanliness.
Documents 50-59: implemented or governing the native Visual Capability Cluster, real review/retry, four-mode continuation, human/product consistency, identity anchors, strong selected-output reference loops, and mode-aware role differentiation.
Documents 60-63: implemented or governing product-suite QA, portrait Lovart benchmarking, portrait-suite role separation, and image-edit provider stability.
Document 64: commercial-quality closure authority for real-output quality review, reference continuity evaluation, suite role coverage auditing, and issue-specific retry.
Document 65: human photorealism authority for reducing AI-face feel while preserving commercial appeal and module reuse for future Photography Special-Tuning.
Document 66: selected-reference closure and precise retry authority.
Document 67: visual boundary cleanup and quality-reinforcement authority.
Document 68: current casebook-guided recipe tuning authority for improving photographic realism, four-mode differentiation, product lifestyle context, and validation without duplicating modules.
Documents 69-78: prompt-atom absorption, anti-AI-face tuning, East Asian fair-complexion/proportion guardrails, complex prompt fidelity, identity anchors, and foundation-vs-specialized governance.
Documents 80-82: provider reference upload compression, provider failure retry/status sync, and project output reconciliation/frontend recovery.
Document 83: retry-delivery presentation and uploaded portrait reference conflict-closure authority. Main result surfaces must respect requested image count, show final delivery outputs only, keep retry-superseded originals in folded history, and let uploaded portrait identity-critical traits win over conflicting prompt aesthetics unless the user explicitly requests a new identity.
Documents 84-90: structured appearance identity, image-to-image reference truth, portrait bone-structure locks, identity/style separation, portrait reference balance, portrait stability testing, and General Template advanced reference priority controls.
Document 91: current Human Realism Plugin governance. Real-human rendering, anti-AI-face rules, child/model realism, and cross-template human realism activation belong in the shared Visual Capability Cluster; identity truth remains owned by the portrait identity/reference modules.
V3.8 Project Mode: current accepted architecture.
General Template: first active project template.
E-Commerce Template: active only through Project Mode and the template registry; product references are required before E-Commerce jobs can be created.
V3.10: future boundary, not a defect in the current implementation.
```

## High-Level Architecture

```text
Shared Home Page / Site Shell
  └── Alchemy Creative Agent 3.0 title-bar entry
        └── V3 Frontend App
              └── V3 API Layer
                    └── Central Creative Brain
                          ↓
Natural Language Input
  ↓
Intent Understanding Agent
  ↓
Commercial Brief Builder
  ↓
Brand Memory Engine
  ↓
Creative Director Agent
  ↓
Series Planner
  ↓
Layout & Typography Planner
  ↓
Prompt Compiler
  ↓
Reference Conditioning Engine
  ↓
Generation Router
  ↓
Candidate Scoring + Critic + Refinement Loop
  ↓
Commercial Asset Pack
```

## Vertical Agent Extensibility

V3 keeps the central-brain + multi-agent framework and reserves vertical sub-agent packs for future industries:

```text
EcommerceAgentFamily
BrandIPAgentFamily
AIMangaDramaAgentFamily
RestaurantAgentFamily
LocalServiceAgentFamily
EducationAgentFamily
HospitalityAgentFamily
```

These vertical packs extend the V3 framework through standard contracts. They must not fork the runtime.

## Strategic Direction

Do not build a Lovart clone.

Build a simpler, vertical, agentic commercial image production system that absorbs the strongest ideas from Lovart-like platforms:

- one-prompt asset series generation
- brand consistency
- multi-agent creative planning
- automatic layout planning
- prompt compilation
- reference-image conditioning
- candidate scoring
- automatic refinement
- reusable brand memory
- future vertical industry agent packs

The product should be easier than Lovart for non-design users because the user does not need to operate a design workflow. The AI agents should operate the workflow internally.
