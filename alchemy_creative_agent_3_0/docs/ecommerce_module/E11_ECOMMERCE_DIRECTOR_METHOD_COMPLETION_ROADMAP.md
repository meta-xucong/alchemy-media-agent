# E11 E-Commerce Director-Method Completion Roadmap

Status: formal development roadmap.

Scope: E-Commerce specialized template only.

Default policy: evidence-first listing delivery.
Companion baseline: E02 platform evidence, E03 category packs, E08 acceptance
matrix, E10 external Amazon apparel benchmark, Doc104/Doc105 shared-runtime
contracts.

## 1. Decision and objective

The E-Commerce module will use one common **director method** across product
categories. This absorbs the useful workflow lesson from the external Amazon
apparel benchmark without turning a single skill's aesthetics into product
policy or a universal V3 feature.

```text
product fact ledger
→ verified placement constraint
→ category evidence map
→ selected delivery scope
→ independent slot recipe
→ shared generation / review / retry
→ final delivery and publish checks
```

The method is common **inside E-Commerce**. It must not make General Template
into a listing-suite builder, and it must not duplicate shared Product Identity,
Human Realism, Provider, Review, or Retry behavior.

## 2. Current baseline

The following is already implemented and remains the compatibility baseline:

| Area | Current behavior |
| --- | --- |
| Platform profile | Separates verified constraints from documented operation, internal strategy, and seller configuration. Amazon main-image baseline is the current narrow verified visual constraint. |
| Default strategy | `evidence_first`; `scene_story`, `information_rich`, `content_hook`, and `brand_story` are explicit secondary-role choices. |
| Current suite selector | `recommended`, `listing_core`, `listing_full`, and `detail_supplement` remain compatible slot-selection preferences. D3 maps them to `listing_only` and adds separate API/metadata delivery scopes for A+, content, and storefront planning. |
| Product truth | Product Fact Ledger v1 carries source, verification, channel, and slot bindings into each recipe. `unverified_visual_facts` remains a compatible supplier-spec alias and creates export publish-check attention; D4 adds persisted owner confirmation. |
| Apparel director | Garments receive a seven-role evidence sequence: primary, worn front, back/side, detail, real wear, fit/size, and styling versatility. Garment guidance is suppressed for shoes and bags. |
| Benchmark | E10 records an external Amazon apparel quality bar without copying external images or using pixel matching. E24 covers the planning contract. |
| Text / continuation | E-Commerce passes approved literal copy, claims, locale, and creative intent only through Doc111 provider-native complete-image generation. Per-slot continuation remains governed by shared Doc105 routes. |

## 3. Default user behavior after D3-D4 completion

For an ordinary E-Commerce request, the system must behave as follows:

1. Default to `listing_only` and `evidence_first`.
2. Freeze sourced product facts before prompt composition.
3. Apply only verified placement constraints for the chosen platform/market.
4. Choose the category's proof roles in order of buyer uncertainty reduction.
5. Generate one independent recipe per role, with a distinct business purpose
   and explicit product-fact bindings.
6. Show pending fact confirmation, claim review, text review, and delivery
   warnings before export.

For a garment with four requested images, the default order is: primary,
worn-front, back/side, and detail. A lifestyle image is not discarded; it is
selected when the user requests more images or chooses a relevant strategy.

`listing_plus_a_plus`, content, storefront, and campaign outputs must be an
explicit scope choice. They never silently replace a listing main image or
claim production provider-native text delivery before Doc111 Gate C/D.

## 4. Delivery phases

### D0 — freeze this roadmap and migration boundary

Status: complete with E11.

- Preserve existing scalar fields and `unverified_visual_facts` behavior.
- Make all new contracts additive and E-Commerce namespaced.
- Keep all role metadata readable for historical jobs.
- Prove General Template has no E-Commerce fields, prompts, or suite metadata.

Acceptance: documentation review, focused isolation tests, `git diff --check`.

### D1 — structured Product Fact Ledger

Status: implemented and verified on the E-Commerce branch.

Replace the current list-only fact representation with an additive ledger that
can carry one record per product fact:

```text
fact_id
label / normalized value
source_type: reference_visible | supplier_spec | user_confirmed | derived_blocked
verification: verified | requires_confirmation | blocked
visual_channels: product | package | construction | material | copy
allowed_slot_ids
claim_eligible
review_requirement
```

Requirements:

- `unverified_visual_facts` remains a backward-compatible input alias and is
  materialized as `supplier_spec + requires_confirmation` records.
- A fact marked `derived_blocked` cannot enter a prompt, overlay copy, or
  export claim.
- `claim_eligible` is opt-in and remains true only for a verified
  `reference_visible` or `user_confirmed` fact. It never bypasses the existing
  claim-review gate.
- Each recipe receives the minimal relevant facts, not an arbitrary truncated
  list; main, back, detail, and size slots can therefore be reviewed against
  the right evidence.
- No biometric vector, provider control, or shared schema migration is added.

Delivered: `ProductFactRecord` is additive to `ProductTruthLock`; the planner
binds only non-blocked facts to compatible slots; Copy Bridge suppresses
blocked wording; Critic and export manifests surface pending confirmation and
blocked-fact withholding. Historical locks without the ledger load with an
empty ledger.

Acceptance: fact-source/slot-binding unit tests, old product profiles remain
readable, and no unsupported fact reaches copy, a recipe, or an export binding.

### D2 — complete first-wave category directors

Status: implemented and verified on the E-Commerce branch.

Retain the common director flow but supply data-driven evidence maps per
category. No category receives a shared-runtime branch.

| Category | Required proof sequence |
| --- | --- |
| Garments | primary, fit, construction, detail, wear context, fit/size, styling alternatives |
| Beauty/skincare | package, texture/application, confirmed ingredients/benefits when available, routine/use boundary, close detail |
| Electronics/3C | silhouette, ports/controls, included items, scale/dimensions, compatible use context, verified specification proof |
| Home/kitchen | form/material, scale in space, function, capacity only when confirmed, cleaning/storage/use evidence |
| Food/beverage | package/label, contents/serving, portion/quantity, consumption context, ingredient facts only when supplied |

Requirements:

- Each slot has a plain-language purpose, fact bindings, review checks, and
  differentiation key.
- A garment rule must not leak to shoes/bags; a beauty or food rule must not
  leak to electronics, and so on.
- Requested image count selects the highest-value proof roles without changing
  platform compliance semantics.

Acceptance: one planning fixture per category, cross-category isolation tests,
and a full E-Commerce regression matrix.

Delivered: each of the five first-wave categories now has a declarative,
E-Commerce-only slot director carrying buyer questions, human-presence policy,
text-role intent, product-truth fields, purpose, fact-channel intent, review
checks, and differentiation key. Recipe and export metadata retain that
lineage. Shoes and bags use accessory directors rather than garment guidance.

### D3 — explicit delivery scopes

Status: implemented and verified on the E-Commerce branch.

Add an E-Commerce-only, additive scope contract:

```text
listing_only                 # default
listing_plus_a_plus_planning # plans modules; no text-pixel delivery promise
content_assets               # ad / creator / content-cover roles
storefront_assets            # merchant/theme placement required
```

Requirements:

- Each scope owns a different deliverable map; role names cannot be silently
  reused across listing and A+ placement.
- The current `suite_scope` metadata remains readable and maps safely to the
  new contract.
- A+ modules require explicit merchant/category/market placement context.
- Listing-only remains simple for beginners.

Acceptance: scope selection and compatibility tests; General Template remains
unchanged; no clickable continuation or text-delivery affordance before shared
runtime gates exist.

Delivered: `listing_only` is now the default E-Commerce delivery scope.
Existing suite-scope metadata maps backward-compatibly without changing the
current UI control. A+, content, and storefront scopes own distinct role IDs;
A+ and storefront plans require placement/category/market context and produce
an attention state with no substituted listing roles when it is absent. The
contract records that it does not promise text pixels. No Project Mode public
schema, General Template, provider, or continuation route changed.

### D4 — workspace fact and suite review

Status: in progress; persisted fact-decision backend is implemented.

Expose only beginner-useful controls and warnings:

- confirm or remove supplier facts that the reference does not show;
- show “this image proves” and “this fact needs confirmation” per slot;
- select delivery scope and expression strategy separately;
- show review blockers before export in plain language.

Do not expose raw prompt internals, provider knobs, confidence scores, or
disabled cosmetic actions.

Acceptance: browser/UI tests covering confirmation persistence, role clarity,
scope selection, historical job readability, and mobile image-first layout.

Current increment: E-Commerce profile metadata can persist a `confirmed` or
`removed` decision by fact ID or normalized fact value. On a later plan,
confirmation promotes only a pending fact to `user_confirmed`; removal
withholds it. The remaining D4 work is the beginner-facing, clickable review
surface that writes these existing metadata decisions without exposing prompts
or provider controls.

### D5 — owner-approved real-output fixture harness

Status: can start fixture design after D1; real execution depends on shared
Provider/Review readiness.

Build a registry of project-owned, consented product fixtures. Each fixture
stores source facts, role map, platform/placement target, allowed claims, and
a human-scored acceptance record. E10 is the first benchmark card, not a
stored image fixture.

Every real run must score:

- product fidelity against each fact binding;
- role differentiation and appropriate framing;
- platform primary-image constraints where verified;
- human/fabric/object realism through shared review;
- approved literal-copy and claim correctness through the shared
  provider-native complete-image acceptance path when text is present; and
- final-delivery versus retry-superseded closure.

Acceptance: real Provider/Review Gate C evidence, bounded terminal behavior,
and no fixture marked passed solely from planner metadata or image similarity.

### D6 — A+ module builder and provider-native text delivery closure

Status: blocked on real authorized-material Doc111 Provider Gate C/D evidence.

Only after D3-D5 and Doc104/Doc105 gates are accepted:

- turn `listing_plus_a_plus_planning` modules into approved E-Commerce A+
  recipes;
- pass only product facts, user-approved literal copy, claim/platform
  constraints, and creative intent to the shared provider-native complete-image
  path; and
- validate the resulting delivery through the shared Doc111 acceptance path.

This phase must not create local text pixels, use local fonts/OCR/coordinates/
safe areas, or claim that an external marketplace will approve the result.

### D7 — per-slot continuation integration

Status: blocked on mainline Doc105 route, lifecycle, resolver, and browser
tests.

After mainline delivers the shared append-only continuation action, E-Commerce
adds only its namespaced request body, result-card control, and planner-aware
correction context. It must inherit the frozen parent capability plan by
default and reuse the shared generation/review/retry path.

## 5. Ownership and dependency matrix

| Capability | Owner | E-Commerce responsibility |
| --- | --- | --- |
| Fact ledger, category proof map, scope selection, suite UI | E-Commerce | Implement and test on this branch. |
| Product identity, Human Realism, image quality | Shared V3 foundation | Consume through existing activation/review paths; do not fork. |
| Provider materialization and shared review/retries | Shared V3 foundation | Supply facts, approved literal copy, claim/platform constraints, and creative intent only. |
| Listing and A+ deliverable roles | E-Commerce | Own the map, explain it to users, and retain metadata. |
| Marketplace policy verification | E-Commerce profile governance | Record source/evidence tier; avoid unsupported claims. |
| Slot continuation lifecycle/resolver | Mainline Doc105 | Integrate only after the shared action is accepted. |

## 6. Non-negotiable guardrails

1. “Common director method” does not mean one visual style, one model, or one
   marketing phrase across products.
2. No generated image can upgrade an unverified fact to verified product truth.
3. Platform policy, internal creative strategy, and category evidence remain
   separately stored and separately displayed.
4. Listing main images remain protected from A+/campaign logic.
5. An external reference demonstrates quality direction; it never authorizes
   asset copying, pixel matching, or unsupported product claims.
6. General Template stays scenario-neutral.
7. Every phase requires focused tests, full regression proportionate to risk,
   a clean diff, and a dedicated-branch commit/rebase/push.

## 7. Completion criteria

The director method is complete only when:

1. D1-D4 are implemented with backward compatibility.
2. All first-wave categories have source-aware proof maps and isolation tests.
3. Listing, A+, content, and storefront scopes are explicit and do not leak.
4. Real owner-approved fixtures pass shared Provider/Review Gate C/D evidence.
5. Text-enabled delivery passes the Doc111 provider-native complete-image Gate C/D.
6. Doc105 continuation works through the shared route without template-local
   retries or history mutation.
7. General Template and shared foundation boundaries remain demonstrably clean.
