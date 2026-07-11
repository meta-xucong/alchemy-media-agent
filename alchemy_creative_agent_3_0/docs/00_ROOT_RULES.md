# 00 Root Rules

This document defines the non-negotiable development rules for Alchemy Creative Agent 3.0.

## 1. Version 3.0 Is a Fully Independent Program

Alchemy Creative Agent 3.0 must be treated as a new, independent program area.

It is not an incremental patch on V1 or V2.

It must have its own:

- source directory
- frontend entry area
- backend runtime entrypoints
- schemas
- service interfaces
- agent contracts
- provider contracts
- configuration objects
- tests
- documentation
- product UI flow

The root directory is:

```text
alchemy_creative_agent_3_0/
```

All V3-owned implementation and documentation must live under this directory unless a future design document explicitly authorizes a separate V3-only package location.

## 2. V3 Runtime Independence Is Mandatory

V3 code must not import from V1 or V2 runtime modules.

Forbidden examples:

```python
from custom_media_agent_2_0.app.services.generation import ...
from custom_media_agent_2_0.app.services.prompt_transform import ...
from custom_media_agent_2_0.app.models import ...
```

Forbidden dependency patterns:

- direct imports from V1 / V2
- calling V1 / V2 services at runtime
- sharing V2 provider parameters by reference
- reading V2 configuration as V3 runtime configuration
- relying on V2 `ImagePromptPlan` as a V3 core schema
- writing V3 state into V2 `user_variables`
- treating V2 prompt transform as a hidden backend dependency
- coupling V3 UI state to V1/V2 UI state
- routing V3 frontend actions through V1/V2 API contracts

## 3. Copy, Rename, Own

If V3 needs behavior from V2, it must copy the relevant logic into V3 and own it.

Required process:

```text
1. Identify the V2 behavior that is useful.
2. Copy only the minimal necessary implementation or schema concept.
3. Move it into the V3 directory.
4. Rename it into V3 terminology.
5. Remove V2-specific assumptions.
6. Add V3 tests.
7. Document the copied origin and reason.
8. Treat the copied code as V3-owned code after migration.
```

Acceptable example:

```text
V2 concept: PromptTransformResult
V3-owned concept: PromptCompilationResult
```

Unacceptable example:

```text
V3 imports PromptTransformResult directly from V2.
```

This rule applies equally to:

- backend code
- frontend components
- provider adapters
- prompt helpers
- schema objects
- configuration defaults
- tests
- UI flow logic

## 4. V2 Is Historical Reference Only

V2 can be used as reference material for:

- naming lessons
- prompt transform lessons
- provider integration lessons
- test style
- implementation risks
- UI lessons

But V2 must not be used as V3 runtime infrastructure.

V3 must be able to run, test, and evolve without V2 being loaded.

## 5. Product Boundary: Separate App Area, Shared Platform Shell Only

V3 must have its own frontend entry and UI flow.

Required product shape:

```text
Shared home page / site shell
  └── independent V3 title-bar entry
        └── V3-owned UI
              └── V3-owned backend APIs
                    └── V3-owned runtime and agents
```

V3 may share only platform-level infrastructure with the existing product:

```text
allowed shared layer:
- same domain
- same home page / top-level shell
- same user account identity if the host product already has one
- same balance / credit system
- same deployment server
- same deployment environment
- same observability or platform logging if needed later
```

V3 must not share product runtime logic with V1/V2:

```text
forbidden shared layer:
- V1/V2 generation APIs
- V1/V2 prompt schemas
- V1/V2 frontend workflow components as runtime dependency
- V1/V2 provider parameter objects
- V1/V2 image generation state
- V1/V2 template runtime contracts
- V1/V2 user_variables
```

If V3 needs access to the shared balance system, it must do so through a narrow platform adapter owned by V3, for example:

```text
V3BalanceAdapter
```

The adapter contract must be documented and testable. V3 business logic must not know V1/V2 internals.

## 6. V3 Has Its Own Product Contract

V3 is not just a prompt enhancement layer.

V3 product contract:

```text
Natural language input
→ commercial brief
→ brand memory
→ creative plan
→ asset series plan
→ layout plan
→ prompt compilation
→ conditioning plan
→ generation plan
→ candidate scoring
→ refinement loop
→ commercial asset pack
```

The V3 system must be designed around commercial visual output, not just image generation.

## 7. User Simplicity Is Mandatory

The target user is not a designer or AI expert.

The user must not be required to understand:

- prompt engineering
- model names
- seeds
- samplers
- LoRA
- ControlNet
- IP-Adapter
- workflow graphs
- canvas editing
- layer systems
- typography systems

Agents may use these internally, but the user experience must stay natural-language-first.

## 8. Central Brain + Multi-Agent Framework Is Mandatory

V3 must continue the central-brain + multi-agent architecture.

The central brain owns orchestration:

```text
Central Creative Brain
  → task interpretation
  → agent routing
  → vertical sub-agent selection
  → capability activation intent
  → template and generation strategy
  → scoring and refinement policy
  → asset pack assembly
```

Specialized agents own execution of specific responsibilities:

```text
Intent Agent
Commercial Strategy Agent
Brand Memory Agent
Creative Director Agent
Series Planner Agent
Layout Agent
Prompt Compiler Agent
Generation Router Agent
Critic / Refiner Agent
Asset Packager Agent
```

The architecture must preserve future extensibility for vertical sub-agents.

Examples of future vertical sub-agent families:

```text
EcommerceAgentFamily
BrandIPAgentFamily
AIMangaDramaAgentFamily
RestaurantAgentFamily
LocalServiceAgentFamily
EducationAgentFamily
HospitalityAgentFamily
```

Vertical agents must attach to the V3 framework through V3-owned extension interfaces, not through ad-hoc code paths.

## 9. Vertical Sub-Agent Extensibility Must Be Reserved

V3 should support future industry-specific agent packs.

A vertical agent pack may customize:

- intent rules
- industry defaults
- commercial strategy
- creative direction
- series planning
- layout templates
- prompt compilation
- scoring rules
- capability profiles and generation strategy within Doc100 renderer limits
- asset pack formats

But every vertical agent pack must still use the V3 shared contracts:

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
CommercialAssetPack
```

Vertical packs must not fork the whole V3 runtime.

They extend V3; they do not replace it.

## 10. Agent Decisions Must Be Explicit and Auditable

Although the user experience should be simple, internal decisions must be structured and auditable.

Every major generation run should preserve:

- original user input
- inferred industry
- inferred commercial goal
- selected vertical agent pack if any
- brand profile used
- creative plan
- layout plan
- prompt compilation result
- provider selected
- reference conditioning used
- candidate scores
- critique results
- refinement steps
- final asset manifest

No hidden expand/rewrite/refine behavior should exist without metadata.

## 11. Brand Consistency Is a First-Class Goal

Every V3 module must respect the long-term goal of brand and image-feature consistency.

The system should preserve and reuse:

- brand colors
- visual tone
- layout preferences
- photographic style
- illustration style
- copywriting tone
- product appearance
- successful prior outputs
- user selections and rejections

A beautiful one-off image is not enough. V3 should produce a consistent commercial visual series.

For portrait image-to-image, consistency must be balanced rather than
single-axis. Uploaded portraits preserve recognizable identity, user-approved
outputs preserve positive visual direction, and the current prompt preserves
task mood and art direction. Do not improve one axis by breaking the other two.

For real human, model, fashion, kidswear, hand-held product, product-on-person,
or lifestyle images with visible people, V3 must route realism and anti-AI-face
guidance through the shared Human Realism Plugin in the Visual Capability
Cluster when the Doc101 capability activation plan confirms real-human evidence.
This applies even when the primary template subject is a product. Disable it
when no person is present or when the user explicitly requests anime, cartoon,
CG, illustration, toy, doll, mascot, or another non-photoreal human style.

## 12. Commercial Usability Comes Before Artistic Exploration

V3 is not an experimental art generator by default.

Default outputs should prioritize:

- product clarity
- readable composition
- realistic commercial value
- platform suitability
- text accuracy
- brand consistency
- conversion-oriented layout

Experimental styles may exist later, but they must not weaken the default commercial workflow.

## 13. Prefer External Text Rendering for Commercial Posters

For commercial posters, especially Chinese posters, image models should not be trusted to render all final text directly.

Preferred pattern:

```text
image model generates product / background / atmosphere
+ layout engine creates text regions
+ HTML / SVG / Canvas renderer renders accurate text
```

The image generation layer should reserve clean regions for text when required.

## 14. External Open-Source Projects Are Providers, Not the Core

Projects such as IP-Adapter, InstantStyle, ControlNet, PosterLLaVA, ImageReward, GenPilot, Fooocus, ComfyUI, and Diffusers may be studied or integrated later.

They must be treated as optional capability providers, not as the architecture itself.

V3 owns the core interfaces.

External projects may implement V3 interfaces such as:

- StyleConditionProvider
- LayoutConditionProvider
- ScoringProvider
- PromptOptimizationProvider
- WorkflowSidecarProvider

Doc100 supersedes any older implication that an optional external image model
may become the V3 production final-pixel renderer. External visual extensions
are analysis, conditioning, scoring, or research providers unless a later root
rule explicitly replaces Doc100.

## 15. No Premature Heavy Dependency

Do not add heavy GPU dependencies in the first implementation unless the specific milestone requires it.

The first goal is to establish the product contract, schemas, agent interfaces, and testable planning pipeline.

Heavy model integrations should be sidecars or optional providers.

## 16. Tests Are Required for Contracts

Every V3 core contract should have tests.

Minimum test categories:

- schema validation
- intent parsing
- brief building
- brand memory read/write
- creative plan generation
- series planning
- layout plan generation
- prompt compilation
- provider routing
- scoring report normalization
- refinement policy
- app boundary / no V1/V2 imports
- vertical sub-agent registry behavior when implemented

## 17. Definition of Done for V3 Foundation

V3 foundation is ready when:

```text
1. A natural-language input can become a structured CreativeJob.
2. The CreativeJob can become a CommercialBrief.
3. The CommercialBrief can become a CreativePlan.
4. The CreativePlan can become a SeriesPlan.
5. Each series item can become a LayoutPlan and PromptCompilationResult.
6. The system can produce a GenerationPlan without calling V2.
7. All outputs include auditable metadata.
8. Unit tests cover every core contract.
9. V3 has no runtime dependency on V1/V2.
10. V3 has a reserved independent app shell / API boundary.
11. V3 has a central-brain + multi-agent extension structure.
```

## 18. Reference Channel And Prompt Ownership

Doc93 is the current foundation authority for reference inheritance.

Hard rule:

```text
Reference role decides what may be inherited.
Per-channel policy decides inheritance strength.
Explicit current-prompt instructions own styling channels.
Human Realism improves rendering and cannot expand inheritance rights.
```

An ordinary uploaded portrait reference defaults to:

```text
hard: underlying identity geometry and facial-feature relationships
medium: body identity and natural complexion direction when relevant
soft: broad hair direction only when the prompt is silent
prompt-owned: makeup, hair styling, wardrobe, lighting, color, scene, camera,
mood, art direction, and whole-image style
```

Do not add new hard-coded provider, closure, project-context, or retry wording
that turns `preserve_person_identity` into a hair, wardrobe, light, scene, or
style lock. Use the V3-native Reference Channel Policy child module defined by
Doc93.

## 19. Universal Visual Capability Rule

Doc94 is the authority for shared visual-runtime generality.

Historical scene, wardrobe, demographic, marketplace, or subject-category
cases may be used as regression fixtures. They must not become named runtime
profiles, keyword branches, default prompt recipes, or Central Brain rules.
Shared behavior must be expressed through orthogonal visual variables such as
identity geometry, age fidelity, exposure key, contrast, color temperature,
complexion preservation, skin specularity, texture, and prompt-owned channels.

Any new shared visual rule must pass a three-scene reuse test. If it cannot
improve at least three unrelated scenes without category vocabulary, it belongs
in a future specialized Scenario Pack or in tests, not in the shared cluster.

## 20. Portrait Identity Evidence And Delivery Rule

Doc95 is the authority for identity-only portrait evidence and reviewed result
selection. The shared runtime must preserve complementary feature-detail and
head-geometry evidence, protect the complete identity-critical prompt block,
compare generated output with reference truth, and treat retries as candidates.
A later retry must never replace a stronger earlier result merely because it is
newer. Multi-image sets are compared per asset role whenever review evidence
supports that mapping.

## 21. High-Fidelity Identity Execution

Doc96 is the authority for measurable same-person execution. Strong portrait or
product identity references must request high provider input fidelity when the
provider supports it. Unsupported capability fallback must be explicit and
must not be inferred from transient 5xx, timeout, rate-limit, or connection
errors.

Portrait identity metrics may calculate face representations ephemerally for a
single review operation. They must never persist embeddings or biometric
vectors in Project, Brand Memory, output metadata, logs, or APIs. When identity
review fails, Doc100 requires a bounded whole-image GPT Image 2 rerender with a
stronger ranked reference pack. No local generative model, sidecar, face swap,
or regional pixel replacement may create the production deliverable. The
rerender must beat the prior candidate and preserve prompt-owned channels before
it can be delivered.

The user prompt remains lossless. Prompt cleanup may remove only duplicated
framework-owned guidance.

## 22. Subject Continuity Asset And Repair Routing

Doc97 governs long-running subject reference selection. The Visual Capability
Cluster must package uploaded truth, explicit user selections, and reviewed
generated support as separate authority levels. Explicit selection is the next
generation's operational master, while uploaded truth remains the immutable root
guard whenever available. Generated support must not silently replace root truth.

Reference selection must be bounded, view-aware, auditable, and reusable across
unrelated portrait or product scenes. Face embeddings remain ephemeral and must
not be persisted. Retain the best reviewed output and use bounded GPT Image 2
regeneration from the ranked subject asset pack. Stale sidecar capability flags
must never unlock another final-pixel renderer.

## 22.1 Production Renderer Boundary

Doc100 is the current production rendering authority. GPT Image 2 API is the
sole final-pixel renderer for V3. Local CPU/GPU tools may contribute analysis
metadata only; they may not repaint, composite, patch, or replace delivered
pixels. Doc98 and Doc99 are isolated research records and are not production
provider contracts.

## 22.2 Capability Activation And Hot-Plug Boundary

Doc101 is the current authority for reusable visual capability activation.
Central Brain must emit a structured multi-label task profile and capability
activation intent. The Capability Activation Planner validates manifests,
evidence, dependencies, conflicts, template policy, user controls, and budget,
then freezes one plan for generation, review, and retry.

Foundation-owned does not mean always enabled. Inactive plugins contribute no
prompt clauses, review checks, retry reasons, project memory, or user-facing
explanations. New governed plugins must register through the Visual Capability
Registry and remain reusable across templates without changing Central Brain,
Project Mode, Product API, or the GPT Image 2 provider path.

General Template remains broad and scenario-neutral. Specialized templates own
professional deliverable maps, capability profiles, and domain acceptance
criteria.

## 23. Strategic Reminder

Do not build a Lovart clone.

Build an agentic commercial visual production system that is simpler for non-design users and stronger in vertical commercial use cases.

The user-facing product should feel like:

```text
one natural-language request → AI-operated commercial creative team → brand-consistent asset series
```
