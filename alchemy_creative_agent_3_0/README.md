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

For E-Commerce and production-closure work, read documents 23, 24, 25, 26, 27,
and 28 before
coding. The intended sequence is: finish the V3 foundation gaps, migrate V1/V2
strengths as V3-owned shared capabilities, build the commercial shared frontend
shell without activating E-Commerce, keep General Creative policy-neutral, then
build E-Commerce as a Scenario Pack inside the shared V3 workspace, then close
the real uploaded-asset and export-manifest loop.

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

V3.8 E-Commerce Scenario Pack
  Implement E-Commerce from document 26 after the shared frontend shell exists; activate its dedicated card/workspace inside the V3 Scenario Hub only after backend contracts and tests pass.

V3.8A E-Commerce Asset Upload and Export Closure
  Implement document 28: V3-owned uploads, real uploaded-asset resolution for shared capabilities, and downloadable E-Commerce export manifests.

V3.8B Provider/Output Production Closure
  Implemented in the current V3.8B closure: V3-owned real image generation via the same configured V1/V2 provider base URLs/API keys, V3 output storage, preview/download routes, frontend one-click image generation, and generated asset records in export manifests. ZIP/batch packaging can remain a later enhancement.

V3.8C E-Commerce Recipe-To-Generated-Series Optimization
  Connect E-Commerce recipes to real multi-image generated series so one simple commerce request becomes a mature suite with distinct main, feature, scenario, detail, trust, and cover slots.

V3.8D Productized Module Workspaces And Capability Audit
  Apply document 31: keep the V3 home card/history-first, then make General Creative and E-Commerce feel like distinct beginner-facing modules, hide engineering language, emphasize generated images, and audit that V1/V2-derived shared capabilities are active behind the scenes.

V3.9 Future Specialization Packs
  Optional unless explicitly requested. Detailed new-media, private-community, brand-IP, AI manga-drama, and other pack-specific workflows require their own accepted specifications.
```

Current implementation status:

```text
Documents 00-31: implemented, reconciled, audited, or actively governing the accepted current-stage scope.
V3.8A: complete and verified.
V3.8B: provider/output production closure implemented and verified for real image generation.
V3.8C: E-Commerce recipes now drive generated multi-image suite slots.
V3.8D: productized module-specific workspaces and shared-capability audit govern the current frontend polish pass.
V3.9: future boundary, not a defect in the current implementation.
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
