# 15 Product Boundary and Vertical Agent Architecture

This document records product-shape decisions that are not only technical implementation details.

These decisions are part of the V3 foundation contract.

## 1. Final Product Boundary Decision

Alchemy Creative Agent 3.0 is a separate product area.

It is not a sub-mode inside V1 or V2.

It is not a prompt transform extension.

It is not a hidden backend feature inside the existing generation flow.

It must have:

```text
independent frontend entry
independent V3 UI
independent V3 backend APIs
independent V3 runtime
independent V3 schemas
independent V3 agents
independent V3 provider contracts
independent V3 tests
```

## 2. Relationship With Existing Product

V3 may share platform-level infrastructure with the existing product.

Allowed shared platform layer:

```text
same domain
same homepage / site shell
same title bar / navigation container
same user account system if needed
same balance / credit system
same server / deployment environment
same platform observability later
```

Forbidden shared product/runtime layer:

```text
V1/V2 generation runtime
V1/V2 prompt transform runtime
V1/V2 ImagePromptPlan
V1/V2 provider parameter objects
V1/V2 frontend workflow state
V1/V2 API contracts for generation
V1/V2 template runtime contracts
V1/V2 user_variables
```

## 3. Frontend Product Shape

The frontend should expose V3 as its own title-bar entry.

Example:

```text
Home / shared site shell
  ├── existing product tabs
  ├── Alchemy Lab if present
  └── Alchemy Creative Agent 3.0
```

Clicking the V3 entry should open a V3-owned UI.

The V3 UI should not reuse old workflow screens as runtime dependencies.

V3 UI can visually follow the same design language, but the implementation should be V3-owned.

## 4. Backend Product Shape

The V3 frontend should communicate with V3-owned backend routes.

Recommended future route namespace:

```text
/api/v3/creative-agent/*
```

Possible endpoints later:

```text
POST /api/v3/creative-agent/jobs
GET  /api/v3/creative-agent/jobs/{job_id}
POST /api/v3/creative-agent/jobs/{job_id}/generate
POST /api/v3/creative-agent/jobs/{job_id}/select
GET  /api/v3/creative-agent/brands/{brand_id}
POST /api/v3/creative-agent/brands
```

V3 backend routes should call V3 Creative Core, not V1/V2 generation routes.

## 5. Shared Balance System Boundary

V3 can use the same balance / credit system as the rest of the product.

But balance access must be isolated through a V3-owned adapter.

Recommended interface:

```text
V3BalanceAdapter
```

Responsibilities:

```text
check available credits
estimate operation cost
reserve credits later
commit credits later
refund credits on provider failure later
```

Rules:

```text
1. Creative Core should call V3BalanceAdapter, not old product internals.
2. V3BalanceAdapter can bridge to the shared balance system.
3. V3 tests should mock V3BalanceAdapter.
4. V3 business logic should remain independent from the shared balance implementation.
```

## 6. Shared Deployment Boundary

V3 can be deployed on the same server.

But deployment does not imply runtime coupling.

Allowed:

```text
same server
same process later if necessary
same container later if necessary
same reverse proxy
same domain
```

Still required:

```text
separate route namespace
separate V3 modules
separate V3 config
separate V3 tests
separate V3 runtime entrypoints
```

## 7. Central Brain + Multi-Agent Framework

V3 continues the central-brain + multi-agent direction.

Core pattern:

```text
Central Creative Brain
  ↓
Base Agent Layer
  ↓
Vertical Agent Pack Layer
  ↓
Provider Layer
  ↓
Evaluation / Refinement Layer
```

The central brain is responsible for orchestration.

It should not become one huge prompt.

It decides:

```text
which task this is
which vertical agent pack applies
which agents should run
which providers should be used
how many candidates to create
how to score
when to refine
what to package
what to save into brand memory
```

## 8. Base Agent Layer

Base agents are universal across industries:

```text
IntentAgent
CommercialStrategyAgent
BrandMemoryAgent
CreativeDirectorAgent
SeriesPlannerAgent
LayoutAgent
PromptCompilerAgent
GenerationRouterAgent
CriticRefinerAgent
AssetPackagerAgent
```

These agents define the default commercial visual pipeline.

They should work even when no vertical pack is available.

## 9. Vertical Agent Pack Layer

Future industry-specific behavior should be implemented through vertical agent packs.

Examples:

```text
EcommerceAgentFamily
BrandIPAgentFamily
AIMangaDramaAgentFamily
RestaurantAgentFamily
LocalServiceAgentFamily
EducationAgentFamily
HospitalityAgentFamily
```

Each vertical pack can specialize:

```text
industry detection
commercial strategy
creative plan
asset series plan
layout rules
copywriting structure
prompt compilation
provider routing
scoring rules
asset export format
```

But every vertical pack must use V3 standard schemas.

## 10. VerticalAgentPack Contract

Recommended first-pass contract:

```python
class VerticalAgentPack:
    name: str
    supported_industries: list[str]
    supported_scenarios: list[str]

    def match(self, creative_job, commercial_brief | None) -> float:
        ...

    def refine_commercial_brief(self, context):
        ...

    def refine_creative_plan(self, context):
        ...

    def refine_series_plan(self, context):
        ...

    def refine_layout_plan(self, context):
        ...

    def refine_prompt_compilation(self, context):
        ...

    def refine_evaluation_policy(self, context):
        ...
```

First-pass implementation can return no-op refinements.

The point is to reserve the extension structure.

## 11. VerticalAgentRegistry

Recommended module:

```text
alchemy_creative_agent_3_0/app/vertical_agents/registry.py
```

Responsibilities:

```text
register vertical packs
select the best pack for a job
fallback to DefaultCommercialPack
record selected pack in metadata
```

First-pass behavior:

```text
always return DefaultCommercialPack unless a simple rule matches a stub pack
```

Later behavior:

```text
select EcommerceAgentFamily for ecommerce_product
select RestaurantAgentFamily for restaurant_* industries
select BrandIPAgentFamily for brand character / mascot / IP tasks
select AIMangaDramaAgentFamily for AI manga / drama scene tasks
```

## 12. Important Future Vertical Directions

### 12.1 EcommerceAgentFamily

Focus:

```text
platform conversion
product clarity
feature selling points
SKU consistency
main image / detail image / comparison image
```

Possible assets:

```text
taobao main image
product feature image
comparison banner
promotion square image
product detail header
```

### 12.2 BrandIPAgentFamily

Focus:

```text
brand character consistency
mascot design
IP world-building
character pose and expression variants
brand storytelling assets
```

Possible assets:

```text
brand mascot card
IP expression pack
social poster
campaign character key visual
```

### 12.3 AIMangaDramaAgentFamily

Focus:

```text
character consistency
scene continuity
episode card generation
comic / drama visual sequence
storyboard-like image packs
```

Possible assets:

```text
character sheet
scene key visual
episode poster
short drama cover
comic panel concept image
```

### 12.4 RestaurantAgentFamily

Focus:

```text
appetite
clean food photography
local conversion
platform-appropriate restaurant promotion
```

Possible assets:

```text
main poster
delivery cover
group-buying image
WeChat poster
store screen image
```

## 13. Extension Rule

Vertical packs should extend V3 through these points:

```text
CommercialBrief refinement
CreativePlan refinement
SeriesPlan refinement
LayoutPlan refinement
PromptCompilationResult refinement
GenerationPlan refinement
EvaluationReport / RefinementPlan policy
```

They should not bypass:

```text
BrandProfile
LayoutPlan
PromptCompilationResult
GenerationPlan
EvaluationReport
CommercialAssetPack
```

This preserves the V3 system as one coherent framework.

## 14. UI Implication of Vertical Packs

The default UI should remain simple.

Users should not need to manually choose complex vertical packs.

The system can infer the vertical pack from natural language.

Later, advanced UI may expose simple product modes such as:

```text
电商图
品牌 IP
餐饮海报
AI 漫剧
本地生活
```

But these are product modes, not technical workflow nodes.

## 15. V3.0 Requirements From This Document

V3.0 foundation should reserve:

```text
1. app_shell package or documented placeholder
2. platform_adapters package or documented placeholder
3. central_brain / Creative Core orchestrator
4. vertical_agents registry
5. DefaultCommercialPack
6. metadata field for selected_vertical_pack
7. tests that verify no V1/V2 dependency
```

V3.0 does not need to implement full frontend UI.

But it must not block the future independent UI entry and route namespace.

## 16. V3.1 Requirements From This Document

V3.1 should make vertical pack selection influence brand consistency when relevant.

Examples:

```text
RestaurantAgentFamily later can prefer appetite and food clarity.
EcommerceAgentFamily later can prefer product clarity and feature labels.
```

V3.1 may still keep non-default packs as stubs.

## 17. V3.2 Requirements From This Document

V3.2 should allow vertical packs to influence scoring and refinement.

Examples:

```text
EcommerceAgentFamily can score product visibility higher.
RestaurantAgentFamily can score appetite and cleanliness higher.
BrandIPAgentFamily can score character consistency higher later.
```

## 18. Non-Negotiable Summary

```text
V3 is independent.
V3 owns its UI.
V3 owns its backend.
V3 owns its agents.
V3 may share domain/homepage/balance/server only through explicit boundaries.
V3 continues central brain + multi-agent architecture.
V3 reserves vertical sub-agent packs for ecommerce, brand IP, AI manga drama, restaurants, and future industries.
```