# E09 Implementation Log and Parallel-Safe Delivery Record

## Purpose

Record independently deliverable E-Commerce milestones, their boundary, test
evidence, and integration dependency. This log does not replace the roadmap;
it makes later rebase and integration decisions auditable.

## E1 — category and marketplace planning baseline

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Versioned category profiles for apparel, beauty, electronics, home/kitchen,
  and food/beverage.
- Category aliases and evidence/review metadata.
- Ozon marketplace profile with a product-evidence default suite. Later source
  review explicitly removed the unsupported scene-led platform default.
- Category-priority selection when a requested image count constrains a suite.

Boundary:

- Only `app/scenario_packs/ecommerce/` and E-Commerce tests changed.
- No Central Brain, provider, shared capability, Project Mode public contract,
  General Template, or shared frontend changes.

Verification:

```text
focused E-Commerce tests: 15 passed
full V3 tests: 401 passed
```

Commit: `1ddda11`

## E2 — localization, copy review, and export metadata

Status: implemented and verified on `codex/ecommerce-module-docs`.

Goal:

```text
versioned locale profile
→ slot-safe copy plan
→ metadata-only copy/claim review
→ locale-aware export manifest
```

Rules:

- The first release does not invent translations. It uses user-supplied localized
  copy when present and otherwise marks derived copy for localization review.
- Main images remain text-forbidden when the platform slot policy requires it.
- Exact product names, trademarks, measurements, and confirmed claims remain
  protected data.
- No OCR renderer, provider path, or public API change belongs to this milestone.

Delivered:

- Versioned `en-US`, `ru-RU`, and `zh-CN` locale resolution from platform,
  market, or explicit user locale.
- Slot-safe copy plans: main/hero slots reject overlay text; other slots record
  text, source, locale, truncation, and review state.
- User-supplied localized copy is preserved within slot limits.
- Derived non-English copy is explicitly marked for native-language review
  rather than presented as a translated claim.
- Commerce Critic and export metadata carry localization-review state.

Verification:

```text
focused E-Commerce tests: 19 passed
full V3 tests: 405 passed
```

Integration dependency: none beyond normal rebase before integration.

## E9 — safe parallel-work boundary audit

Status: complete after rebase onto `origin/main` at Doc103.

Independent work completed on this branch:

- platform/category planning profiles and recipe metadata;
- locale/copy/claim review metadata;
- category evidence and suite-differentiation review;
- export lineage and publish-check summaries;
- E-Commerce-only focused tests and documentation.

Work intentionally deferred to coordinated integration:

- frozen activation-plan enforcement, provider contribution consumption, and
  shared visual review/retry behavior;
- OCR or final typography renderer integration;
- Project Mode/public API schema changes and E-Commerce workspace UI;
- real-provider product fixtures, visual manual review, and browser continuity;
- production template activation.

The current upstream authority is
`docs/103_V3_ECOMMERCE_DEVELOPMENT_ENTRY_AND_RUNTIME_GOVERNANCE_CLOSURE_SPEC.md`.
It confirms that the deferred items require the shared foundation gates rather
than additional isolated template-local code.

## E10 — E-Commerce workspace delivery panel

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Added Ozon and Pinduoduo to the E-Commerce platform selector.
- The E-Commerce workspace now renders planned slot purpose and category
  evidence, rather than only the generic suite label.
- It renders export preparation, profile version, per-slot copy review state,
  and the concise publish-check list already returned by the E-Commerce API.
- The UI remains E-Commerce-only: General Template does not render platform,
  export, or professional commerce suite data.

Verification:

```text
Project Mode E-Commerce focused tests: 12 passed
full V3 tests: 508 passed
commercial frontend shell tests: 8 passed
JavaScript syntax: passed
```

Integration dependency: browser click-through and real product/provider
acceptance remain Doc103 coordinated gates.

## E11 — E-Commerce project identity integrity

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Corrected the Project Mode memory-summary default so that a new E-Commerce
  project with no user-confirmed visual style is labeled `电商模板`, rather than
  inheriting the General Template's former `通用创意` fallback.
- Kept the frontend fallback template-aware for client-side project summaries
  and for a project detail that has not yet received a memory summary.
- Added a backend regression test covering both the newly created project and
  its recent-project summary.

Verification:

```text
Project Mode + E-Commerce focused tests: 61 passed
full V3 tests: 509 passed
commercial frontend shell tests: 8 passed
browser regression: created an E-Commerce project and verified the visible
style chip is 电商模板; console errors: none
JavaScript syntax: passed
```

Integration dependency: none. This is a Project Mode presentation correction;
it does not alter generation routing, provider behavior, schemas, or General
Template deliverables.

## E12 — direct category selection for suite planning

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Added a visible product-category choice to the E-Commerce workspace for the
  five current category packs: apparel, beauty, electronics, home/kitchen, and
  food/beverage.
- The selection now reaches the existing `commerce_profile_patch` as
  `product_category`, so the category planner can use the correct evidence
  targets and slot priority without a new API field.
- The default remains automatic detection, and reset returns the control to
  that non-invasive default.

Verification:

```text
E-Commerce workspace focused tests: 3 passed
full V3 tests: 510 passed
commercial frontend shell tests: 8 passed
JavaScript syntax: passed
```

Integration dependency: none. This uses the existing namespaced commerce
profile patch and changes neither shared provider behavior nor General
Template controls.

## E13 — visible platform and category confirmation

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- The E-Commerce run summary now derives the resolved category from the
  planner's recipe lineage (with product-truth fallback).
- Platform/market and resolved category are placed ahead of optional selling
  point details, ensuring they remain visible within the compact progress
  summary.
- Category labels are translated into the five workspace-facing pack names;
  an unknown but explicit category remains visible rather than silently
  becoming generic.

Verification:

```text
E-Commerce workspace focused tests: 3 passed
full V3 tests: 510 passed
commercial frontend shell tests: 8 passed
JavaScript syntax: passed
```

Integration dependency: none. This is a display-only confirmation of existing
planner output and introduces no shared contract or routing change.

## E14 — visible suite-scope choice and confirmation

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Added an E-Commerce-only suite-scope choice for the existing slot request:
  recommended-by-preset, core listing, complete listing, or detail/scene
  supplementation.
- The choice maps only to the existing `suite_slot_request` and commerce
  profile metadata. It does not add a Project Mode schema field, alter
  provider behavior, or expose controls in the General Template.
- The selected scope is retained in the existing job metadata and shown in the
  compact E-Commerce run summary, so a user can confirm the requested package
  before interpreting planned slots or export checks.

Verification:

```text
Project Mode E-Commerce focused tests: 15 passed
full V3 tests: 511 passed
commercial frontend shell tests: 8 passed
JavaScript syntax: passed
```

Integration dependency: none. The existing namespaced request and metadata
surfaces are used without expanding the public contract.

## E15 — generation-ready suite preview

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Added an immediate, accessible preview below the E-Commerce suite-scope
  selector. It tells the user which role labels will be prioritized before
  they start generation.
- The preview updates when either the suite scope or the existing quick goal
  changes, and it reuses the exact slot mapping sent to the existing request.
- No planning behavior, public contract, provider route, or General Template
  control changed.

Verification:

```text
Project Mode E-Commerce focused tests: 15 passed
full V3 tests: 511 passed
commercial frontend shell tests: 8 passed
JavaScript syntax: passed
```

Integration dependency: none.

## E16 — target-audience planning control

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Added the existing E-Commerce profile's optional target-audience field to
  advanced product information, with a beginner-facing example.
- The workspace now sends that value through the already supported
  `target_audience` profile field, and the E-Commerce summary shows the first
  two planned audience cues returned by the existing commerce brief.
- Added an end-to-end Project Mode regression proving the field persists on
  the project profile and is used by the E-Commerce planner. No schema,
  provider, or shared-routing change was required.

Verification:

```text
Project Mode E-Commerce focused tests: 16 passed
full V3 tests: 512 passed
commercial frontend shell tests: 8 passed
JavaScript syntax: passed
```

Integration dependency: none. This exposes an established compatibility field
rather than expanding the public contract.

## E17 — language and approved-copy planning controls

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Added optional English (US), Simplified Chinese, and Russian planning
  controls, plus a short user-supplied copy field, to the E-Commerce advanced
  workspace.
- Routed only the existing E-Commerce profile metadata keys
  `copy_locale` and `overlay_copy` into the existing E-Commerce scenario
  parameters. Older projects retain platform/market locale inference.
- The existing copy bridge remains the policy owner: the regression proves an
  Amazon main image rejects the supplied overlay while the requested benefit
  image accepts it. Existing claim review still applies.
- Updated the architecture document to point to current Doc104 governance.

Boundary:

- This is copy planning and review metadata, not a promise of final pixel
  typography. Deterministic text rendering, OCR, provider acceptance, and live
  browser validation remain Doc104 coordinated gates.
- No activation, provider, shared review/retry, General Template interface, or
  public schema changed.

Verification:

```text
Project Mode E-Commerce focused tests: 18 passed
full V3 tests: 516 passed
commercial frontend shell tests: 8 passed
JavaScript syntax: passed
```

Integration dependency: no new dependency for this compatible planning path;
the final typography/visual-acceptance path remains coordinated.

## E18 — per-slot continuation interface audit

Status: coordination handoff prepared; no interface implementation was added.

Evidence:

- The current workspace has whole-job creation/generation and per-result
  select/delete actions, but no user-facing `regenerate slot` action.
- Product API retries are internal bounded quality recovery. They are not a
  user-directed replacement of one E-Commerce suite role.
- There is no Project Mode public route that accepts a parent job plus an
  E-Commerce slot identity for a new, append-only continuation attempt.

Required coordinated contract:

```text
parent E-Commerce job + slot ID + optional correction note
→ child continuation job (never mutates parent history)
→ inherit the parent's frozen capability plan by default
→ allow only a recorded bounded plan amendment when new evidence requires it
→ generate/review/retry through the shared runtime
→ fold superseded candidates and preserve final delivery count
```

Compatibility proposal:

- Add a namespaced Project Mode action only after foundation-owner agreement;
  do not overload select/delete or internal retry endpoints.
- Keep all existing jobs and exports readable. A legacy job without a parent
  continuation link simply remains non-regenerable at the slot level.
- Do not expose a disabled or cosmetic "redo this image" button before that
  action and its frozen-plan semantics exist.

Integration dependency: this is a Doc104 Section 9 public interface and
shared retry/append-only-history coordination item. It requires the mainline
foundation owner before implementation or production activation.

## E22 — initial platform-specific slot visual grammar (superseded)

Status: superseded by E23 source-evidence correction.

E22 introduced a versioned internal visual-intent field and the corresponding
workspace display. It incorrectly allowed platform-level defaults to imply that
Ozon universally preferred scene-led images and that other marketplace visual
grammars were stable across placements. Those values must not be used as
platform-policy evidence. Historical E22 jobs remain readable through the
legacy field; new jobs use the three-layer E23 model below.

Verification:

```text
focused E-Commerce platform/UI tests: 30 passed
full V3 tests: 531 passed
commercial frontend shell + provider contract tests: 50 passed
JavaScript syntax, Python compile, and diff checks: passed
```

Integration dependency: none beyond normal rebase before integration. Profile
research/review and real-provider acceptance remain activation-gate work.

## E23 — evidence-led marketplace profile correction

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Replaced platform-wide art-direction assumptions with separately recorded
  buyer evidence, verified platform compliance intent, and explicit
  seller-selected creative strategy.
- Recorded Amazon primary-image constraints as verified baseline evidence;
  retained no visual-policy override for Ozon, Taobao/Tmall, JD, PDD, TikTok
  Shop, and Shopify unless future primary-source review establishes one.
- Added a backward-compatible workspace control for the optional strategy and
  labels that keep evidence, strategy, and verified constraints distinct; a
  strategy label appears on a slot only when that strategy actually applies.
- Added contract/planner/UI tests for Amazon primary compliance, optional Ozon
  scene story, TikTok content-hook scope, Project Mode metadata forwarding,
  and historical job readability.

Verification:

```text
focused E-Commerce / Project Mode / workspace tests: 88 passed
full V3 tests: 532 passed
commercial frontend shell + provider contract tests: 50 passed
JavaScript syntax, Python compile, and diff checks: passed
```

Evidence sources and profile update policy are maintained in E02. This
milestone does not claim marketplace approval, text-pixel delivery, or
real-provider activation acceptance.
## E20 — product visual-positioning planning control

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Exposed the existing optional `price_positioning` project-profile field as a
  simple E-Commerce-only visual choice: value, balanced, or premium.
- The planner carries the normalized choice from the commerce brief into every
  selected recipe, where it guides proof, composition, material detail, and
  lighting. The workspace shows the resulting plan label on each suite row.
- Each controlled direction expressly rejects discounts, price comparisons,
  savings, awards, certifications, and unsupported luxury provenance. It is
  not a product price, compliance, or market-status claim.
- The Project Mode regression proves the old profile field persists and reaches
  the E-Commerce recipes; no shared schema, provider, activation, retry, or
  General Template behavior changed.

Verification:

```text
focused E-Commerce/Project Mode tests: 22 passed
full V3 tests: 523 passed
commercial frontend shell + provider contract tests: 50 passed
JavaScript syntax and diff checks: passed
```

Integration dependency: none beyond normal rebase before integration. The
separate Doc105 continuation route/lifecycle/resolver dependency remains
unchanged.

## E19 — Doc105 and gateway-managed failover synchronization

Status: integrated into the E-Commerce branch documentation; implementation
waits for the mainline continuation route/lifecycle/resolver.

Delivered:

- Rebasing onto `origin/main` at `f1552a2` brings the accepted Doc105 slot
  continuation and text-pixel delivery contract, plus the shared gateway
  managed-failover provider mode.
- E04 and the roadmap now reference Doc105: E-Commerce owns copy intent and
  suite roles, while final typography/OCR and user-directed child-job lineage
  remain shared-runtime work.
- The deployment-only gateway-managed failover mode is recorded as a
  foundation constraint. E-Commerce must not add another retry loop or change
  provider timeout behavior when it is enabled.

Verified mainline boundary:

- The named `ecommerce-slots/{slot_id}/continuations` route, handler,
  lifecycle, and delivery resolver are not yet present.
- Mainline contract tests explicitly require no slot-redo path or button in the
  workspace before those shared pieces and browser tests are implemented.

Integration dependency: wait for the Doc105 route/lifecycle/resolver
implementation. At that point, add the E-Commerce request body, result-card
control, and feature tests without changing shared provider, frozen-plan, or
review/retry semantics.

Verification:

```text
Doc105 contract + E-Commerce Project Mode focused tests: 20 passed
full V3 tests: 519 passed
commercial frontend shell + provider contract tests: 50 passed
JavaScript syntax: passed
```

## E8 — category normalization and conditional evidence

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Added common-category aliases for bags, beauty products, keyboards/phones,
  lighting, organizers, and storage.
- Recognizes desk lamps as home/kitchen for suite planning.
- Distinguishes conditional evidence such as capacity/quantity from required
  home-product evidence, preventing false missing-evidence warnings.
- Maintains platform-first conversion ordering: primary image, core benefit,
  then category scene/detail extensions.

Verification:

```text
focused E-Commerce tests: 34 passed
full V3 tests: 420 passed
```

Integration dependency: none beyond normal rebase before integration.

## E7 — profile-driven text policy and primary-slot protection

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Text-forbidden and text-enabled roles are now declared by the selected
  marketplace profile rather than globally by the copy bridge.
- Copy plans record the profile as the policy owner.
- Requested-count selection keeps the platform's first/hero role before adding
  category-specific evidence roles.

Verification:

```text
focused E-Commerce tests: 32 passed
full V3 tests: 418 passed
```

Integration dependency: none beyond normal rebase before integration.

## E6 — publish-check and export summary closure

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Export metadata now exposes a concise, plain-language publish-check list.
- The list combines product-truth confirmation, profile verification, locale
  review, claim evidence, category evidence, and suite-differentiation signals.
- Export status derives from the same check list; no publishing endpoint or
  automatic marketplace action was added.

Verification:

```text
focused E-Commerce tests: 30 passed
full V3 tests: 416 passed
```

Integration dependency: none beyond normal rebase before integration.

## E5 — claim-safe copy review

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Risk-sensitive words and supplied unsupported claims are detected in every
  overlay-copy plan.
- Risky copy stays visible to the user but the affected recipe, critic report,
  export file, and export package require claim review.
- Safe copy remains metadata-ready; no compliance or approval promise is made.

Verification:

```text
focused E-Commerce tests: 28 passed
full V3 tests: 414 passed
```

Integration dependency: none beyond normal rebase before integration.

## E4 — platform profile governance and export lineage

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Platform profiles now carry an internal identifier, version, status, update
  time, and source/review note.
- Planning and export metadata freeze the platform profile lineage per suite.
- Export records retain associated category profile versions and copy locale.
- The public E-Commerce summary continues to reject low-level generation terms;
  an initial internal naming collision was detected by regression tests and
  corrected before commit.

Verification:

```text
focused E-Commerce tests: 25 passed
full V3 tests: 411 passed
```

Integration dependency: none beyond normal rebase before integration.

## E3 — category evidence coverage and suite differentiation

Status: implemented and verified on `codex/ecommerce-module-docs`.

Delivered:

- Category profiles now map commerce slots to buyer evidence such as product
  silhouette, material, application, use context, portion, size, and ports.
- Each recipe carries category evidence targets for audit and future UI display.
- Commerce Critic flags missing evidence caused by a constrained requested count.
- Commerce Critic flags two roles with the same business goal and selling point.
- Uploaded-image bookkeeping is excluded from seller-facing selling points.

Verification:

```text
focused E-Commerce tests: 23 passed
full V3 tests: 409 passed
```

Integration dependency: none beyond normal rebase before integration.
