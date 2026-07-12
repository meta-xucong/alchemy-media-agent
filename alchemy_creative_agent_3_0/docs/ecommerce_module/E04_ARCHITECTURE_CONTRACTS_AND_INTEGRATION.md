# E04 Architecture, Contracts, and Integration Map

## Runtime position

```text
Project
  → ecommerce_template
    → ecommerce Scenario Pack
      → commerce profile + product truth
      → platform/category suite planner
      → V3 Brain and frozen capability plan
      → provider generation
      → review/retry/selection
      → commerce export manifest
```

The E-Commerce module is a specialized policy and deliverable layer. It does
not call providers directly and does not fork the central runtime.

Doc104 is the integration gate authority after this package is rebased onto the
current foundation: every production E-Commerce job must retain the frozen
capability activation plan supplied by the shared runtime. This module may
configure E-Commerce-owned profiles and recipes, but may not alter activation,
provider, shared review, or retry semantics.

Doc105 freezes the E-Commerce slot-continuation boundary. It is the authority
for a user-directed replacement of a single suite role. Doc111 is the current
text-delivery authority: literal approved copy is a provider-native complete
image requirement, never a local typography/OCR/composition workflow.

## Existing code ownership

| Existing location | E-Commerce responsibility |
| --- | --- |
| `app/scenario_packs/ecommerce/contracts.py` | commerce contracts |
| `product_truth.py` | immutable facts, unknowns, review obligations |
| `marketplace_rules.py` | versioned platform profiles |
| `commerce_brief.py` | audience, motivations, pain points, trust |
| `selling_point_planner.py` | selling points to slot recipes |
| `copy_bridge.py` | short visual copy bridge |
| `commerce_critic.py` | commerce review signals |
| `export_packager.py` | platform-aware export metadata |
| `app/project_mode/templates` | template activation and project gate |

## Required data flow

```text
user request + uploaded refs
→ product truth
→ commerce brief
→ platform profile
→ category pack
→ suite recipes
→ capability activation intent
→ frozen plan
→ generation/review/retry
→ selected delivery outputs
→ export manifest
```

## Contract rules

1. Public contracts remain product-level. No seed, sampler, provider, model,
   node graph, or low-level image-control fields.
2. The full user prompt remains lossless; only duplicated framework guidance
   may be compacted.
3. Product facts, platform profile version, category pack version, recipe IDs,
   capability plan ID, review outcome, and export status are auditable.
4. Template-specific fields are namespaced under the E-Commerce project profile.
5. Historical records without newer fields remain readable.
6. Every job requires a project ID and product reference or an explicitly
   confirmed text-only product brief.
7. Optional `commerce_profile.metadata.copy_locale` and legacy
   `commerce_profile.metadata.overlay_copy` are E-Commerce-only planning
   signals. When absent, locale resolves from platform/market; user-approved
   literal copy remains subject to slot text policy and claim review. Under
   Doc111 it is passed only as a provider-native complete-image requirement.
   It does not add General Template semantics, local overlay rendering,
   `CopyRenderPlan`, fonts, OCR, coordinates, safe areas, or template retries.
8. A single-role replacement must use the future Doc105 namespaced child-job
   action. It may not reuse select/delete or internal retry, must keep the
   parent immutable, and must inherit the frozen parent plan unless authorized
   new evidence produces the one bounded recorded amendment.
9. Historical local text-pixel inputs remain readable but must return the
   structured `provider_native_required` state. Production text delivery still
   requires real authorized-material Doc111 Provider Gate C/D evidence.
10. Optional `commerce_profile.price_positioning` is an E-Commerce visual
    planning signal with controlled `value`, `balanced`, and `premium` values.
    It may guide composition, feature proof, material detail, and lighting,
    but it must not create price, discount, savings, award, certification, or
    provenance claims.
11. Each recipe keeps three distinct inputs: `platform_compliance_intent`,
    `evidence_intent`, and `creative_strategy`. A platform constraint may be
    called a marketplace rule only when its source/evidence tier supports that
    statement. In the current baseline, Amazon's primary-image constraints are
    verified; most other platform visual direction remains non-policy guidance.
12. Optional `commerce_profile.metadata.creative_strategy` is an
    E-Commerce-only seller choice (`evidence_first`, `scene_story`,
    `information_rich`, `content_hook`, or `brand_story`). It may affect only
    compatible secondary roles and can never override a verified primary-image
    restriction, product truth, review, retry, provider, or General Template
    contract.
14. The current additive `unverified_visual_facts` alias materializes as
    E-Commerce fact-ledger entries that require confirmation. It produces
    critic and export publish-check attention today; D4 will add a persisted
    user-confirmation UI. A fact marked blocked must not enter a recipe,
    overlay copy, or export binding.

## Compatibility rule

Existing E-Commerce APIs and fields must remain readable. New fields are
optional until the activation gate requires them. The module may add profile
versions, recipe metadata, and export metadata without changing General
Template semantics.

Historical jobs without Doc105 lineage stay readable but are not eligible for
per-slot continuation. The workspace must not render a slot-redo control until
the mainline route, lifecycle, delivery resolver, and browser tests in Doc105
exist.

## Shared gateway-managed failover

`OPENAI_IMAGE_GATEWAY_MANAGED_FAILOVER` is a foundation provider-runtime mode,
not an E-Commerce setting. When the deployment enables it for a gateway that
owns line failover, backoff, and health routing, one logical image output has
one in-flight request and the shared runtime records its terminal result.

E-Commerce must not add a second template-local retry loop or change provider
timeouts in this mode. The gateway budget is deployment-owned; the E-Commerce
module continues to use the governed generation/review/retry path unchanged.

## Forbidden integration patterns

- importing V1/V2/Lab runtime modules;
- provider calls from category/platform code;
- platform branches inside Central Brain;
- marketplace slot names inside General Template;
- category-specific rules inside Human Realism or Product Identity plugins;
- frontend-only activation of a locked or unavailable template;
- rewriting historical project records in place.
