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

It must not directly depend on, import from, or call runtime parameters, interfaces, services, schemas, or internal modules from V1 or V2.

If V3 needs behavior, patterns, or utilities from V2, they must be copied into this directory, renamed where appropriate, reviewed, and adapted as V3-owned code.

V3 may use V1/V2 only as historical reference, not as runtime dependency.

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
same balance / credit system
same server / deployment environment
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