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

The detailed, post-E24 director-method completion sequence is maintained in
`E11_ECOMMERCE_DIRECTOR_METHOD_COMPLETION_ROADMAP.md`. This document retains
the module-wide development method and technology boundary; E11 defines the
ordered implementation contracts for the fact ledger, category directors,
delivery scopes, UI, fixture acceptance, and future A+ work.

### E0 Documentation and governance

Deliver this document family, update repository rules, and record the existing
baseline. No runtime behavior change.

### E1 Contract freeze

Finalize platform profile, localization, category pack, recipe, copy, review,
and export contracts. Add schema compatibility tests.

### E2 Planner hardening

Implement the two-axis platform/category planner, requested-count behavior,
unknown-fact handling, and slot differentiation.

### E3 First five category packs

Add apparel, beauty, electronics, home/kitchen, and food/beverage profiles.
Keep them data-driven and separate from shared visual plugins.

### E4 Platform and localization profiles

Add versioned Amazon, Ozon, Taobao/Tmall, TikTok Shop, and Shopify profiles.
Add `en-US`, `ru-RU`, and `zh-CN` copy paths. Keep policy updates configurable.

### E5 Review, copy, and export closure

Connect commerce review, copy-planning signals, best-result selection, and
platform-aware export metadata. Literal copy, when explicitly approved, is
passed only through Doc111 provider-native complete-image generation; this
module must not use local composition, fonts, OCR, coordinates, safe areas, or
text-specific retry loops, and must not claim production text delivery before
Doc111 Provider Gate C/D is accepted.

### E6 Dedicated workspace UI

Implement the beginner-facing E-Commerce workspace. Render per-slot
continuation only after the Doc105 route, lifecycle, delivery resolver, and
browser tests exist; do not pre-stage a cosmetic or disabled redo control.

### E7 Real-output acceptance

Run a fixture matrix with real product images, inspect final files, verify
provider behavior, and pass the template activation gate.

E7 is a coordinated integration phase. It requires the Doc104 foundation gates
for enforced activation runtime, real provider/review, and General project
continuation, plus Doc105 slot-continuation and Doc111 provider-native
complete-image text acceptance; it is not part of this branch's isolated
implementation scope.

## Recommended technology stack

| Concern | Existing/recommended choice |
| --- | --- |
| Runtime | Python 3, existing V3 application runtime |
| Contracts | Existing typed Python contracts/models; additive fields only |
| Planning | Existing V3 Brain + Scenario Runtime + factual/policy guardrails; LLM owns creative direction |
| Capabilities | V3 Visual Capability Cluster and activation planner |
| Rendering | GPT Image 2 through the existing V3 provider adapter |
| Image inspection | Existing V3 provider/review interfaces and Doc111 real-output acceptance |
| Persistence | Existing Project Store/Job records; versioned profile metadata |
| Frontend | Existing V3 project/workspace shell and image-first components |
| Tests | pytest, compileall, frontend syntax checks, browser smoke tests |
| Configuration | Versioned JSON/Python data contracts with explicit profile status |

Do not add a new framework, provider SDK, database, or frontend application
unless an E-Commerce requirement cannot be met by the existing V3 stack and a
compatibility proposal is accepted.

## Commit boundaries

Recommended commits:

1. E00-E11 docs and governance.
2. contracts and compatibility fixtures.
3. profile registry and planner.
4. category packs.
5. localization/copy path.
6. review/retry/export.
7. workspace UI.
8. real-output acceptance fixes.
9. Director-method phases D1-D7, each independently tested and documented in
   E11.
