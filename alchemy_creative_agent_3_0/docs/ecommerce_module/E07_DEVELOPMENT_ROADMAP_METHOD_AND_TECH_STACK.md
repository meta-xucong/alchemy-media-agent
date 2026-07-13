# E07 Development Roadmap, Method, and Technology Stack

## Development method

Use small, reversible milestones on the isolated branch:

1. inspect current contract and tests;
2. define one narrow schema or profile;
3. implement in the E-Commerce layer;
4. add focused tests;
5. run regression tests;
6. review diff for boundary leakage;
7. commit and push the feature branch;
8. rebase on `origin/main` before each integration milestone.

Shared schema, public component, provider, or dependency changes require a
compatibility note before implementation.

## Milestones

### E0 Documentation and governance

Deliver this document family, update repository rules, and record the existing
baseline. No runtime behavior change.

### E1 Contract freeze

Finalize factual platform evidence, localization context, category evidence,
opaque output lineage, copy provenance, review, and export contracts. Preserve
legacy recipe fields for reading only. Add schema compatibility tests.

### E2 Brain-context migration

Replace deterministic platform/category suite planning with factual,
evidence-provenance context for the remote Central Brain. The Brain—not local
code—decides one natural-language image intent for each user-requested output.

### E3 First five category evidence packs

Add apparel, beauty, electronics, home/kitchen, and food/beverage evidence
questions. They must not contain shot orders, fixed scenes, camera rules, or
fallback copy.

### E4 Platform and localization evidence

Add versioned Amazon, Ozon, Taobao/Tmall, TikTok Shop, and Shopify constraints
with provenance. Locale and approved copy are provider-native inputs; no
localization path may manufacture a slogan or text layout.

### E5 Review, copy, and export closure

Connect observational commerce review, provider-native text inspection,
bounded provider revision, best-result selection, and export metadata.

### E6 Dedicated workspace UI

Implement the beginner-facing E-Commerce workspace and per-slot continuation.

### E7 Real-output acceptance

Run a fixture matrix with real product images, inspect final files, verify
provider behavior, and pass the template activation gate.

E7 is a coordinated integration phase. It requires the Doc103 foundation gates
for enforced activation runtime, real provider/review, and General project
continuation; it is not part of this branch's isolated implementation scope.

## Recommended technology stack

| Concern | Existing/recommended choice |
| --- | --- |
| Runtime | Python 3, existing V3 application runtime |
| Contracts | Existing typed Python contracts/models; additive fields only |
| Planning | Existing V3 Brain + Scenario Runtime + factual/policy guardrails; LLM owns creative direction |
| Capabilities | V3 Visual Capability Cluster and activation planner |
| Rendering | GPT Image 2 through the existing V3 provider adapter |
| Image inspection | Existing V3 vision/review interfaces and provider-native final-pixel validation |
| Persistence | Existing Project Store/Job records; versioned profile metadata |
| Frontend | Existing V3 project/workspace shell and image-first components |
| Tests | pytest, compileall, frontend syntax checks, browser smoke tests |
| Configuration | Versioned JSON/Python data contracts with explicit profile status |

Do not add a new framework, provider SDK, database, or frontend application
unless an E-Commerce requirement cannot be met by the existing V3 stack and a
compatibility proposal is accepted.

## Commit boundaries

Recommended commits:

1. E00-E08 docs and governance.
2. contracts and compatibility fixtures.
3. profile/evidence registry and factual-context builder.
4. category packs.
5. localization/copy path.
6. review/retry/export.
7. workspace UI.
8. real-output acceptance fixes.
