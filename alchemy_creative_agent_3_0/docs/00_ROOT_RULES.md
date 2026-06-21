# 00 Root Rules

This document defines the non-negotiable development rules for Alchemy Creative Agent 3.0.

## 1. Version 3.0 Is a Fully Independent Program

Alchemy Creative Agent 3.0 must be treated as a new, independent program area.

It is not an incremental patch on V1 or V2.

It must have its own:

- source directory
- schemas
- service interfaces
- agent contracts
- provider contracts
- configuration objects
- tests
- documentation
- runtime entrypoints

The root directory is:

```text
alchemy_creative_agent_3_0/
```

All V3-owned implementation and documentation must live under this directory unless a future design document explicitly authorizes a separate V3-only package location.

## 2. No Runtime Dependency on V1 or V2

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

## 3. Copy, Rename, Own

If V3 needs behavior from V2, it must copy the relevant logic into V3 and own it.

Required process:

```text
1. Identify the V2 behavior that is useful.
2. Copy only the minimal necessary implementation or schema concept.
3. Rename it into V3 terminology.
4. Remove V2-specific assumptions.
5. Add V3 tests.
6. Document the copied origin and reason.
7. Treat the copied code as V3-owned code after migration.
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

## 4. V2 Is Historical Reference Only

V2 can be used as reference material for:

- naming lessons
- prompt transform lessons
- provider integration lessons
- test style
- implementation risks

But V2 must not be used as V3 runtime infrastructure.

V3 must be able to run, test, and evolve without V2 being loaded.

## 5. V3 Has Its Own Product Contract

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

## 6. User Simplicity Is Mandatory

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

## 7. Agent Decisions Must Be Explicit and Auditable

Although the user experience should be simple, internal decisions must be structured and auditable.

Every major generation run should preserve:

- original user input
- inferred industry
- inferred commercial goal
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

## 8. Brand Consistency Is a First-Class Goal

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

## 9. Commercial Usability Comes Before Artistic Exploration

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

## 10. Prefer External Text Rendering for Commercial Posters

For commercial posters, especially Chinese posters, image models should not be trusted to render all final text directly.

Preferred pattern:

```text
image model generates product / background / atmosphere
+ layout engine creates text regions
+ HTML / SVG / Canvas renderer renders accurate text
```

The image generation layer should reserve clean regions for text when required.

## 11. External Open-Source Projects Are Providers, Not the Core

Projects such as IP-Adapter, InstantStyle, ControlNet, PosterLLaVA, ImageReward, GenPilot, Fooocus, ComfyUI, and Diffusers may be studied or integrated later.

They must be treated as optional capability providers, not as the architecture itself.

V3 owns the core interfaces.

External projects may implement V3 interfaces such as:

- StyleConditionProvider
- LayoutConditionProvider
- ScoringProvider
- GenerationProvider
- PromptOptimizationProvider
- WorkflowSidecarProvider

## 12. No Premature Heavy Dependency

Do not add heavy GPU dependencies in the first implementation unless the specific milestone requires it.

The first goal is to establish the product contract, schemas, agent interfaces, and testable planning pipeline.

Heavy model integrations should be sidecars or optional providers.

## 13. Tests Are Required for Contracts

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

## 14. Definition of Done for V3 Foundation

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
```

## 15. Strategic Reminder

Do not build a Lovart clone.

Build an agentic commercial visual production system that is simpler for non-design users and stronger in vertical commercial use cases.