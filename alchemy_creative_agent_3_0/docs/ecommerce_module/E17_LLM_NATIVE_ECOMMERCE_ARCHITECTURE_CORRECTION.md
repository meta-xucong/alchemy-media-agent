# E17 LLM-Native E-Commerce Architecture Correction

Status: active migration authority for new E-Commerce jobs
Scope: E-Commerce specialized template and its narrowly required shared seams

## Decision

New E-Commerce jobs are not directed by a platform-slot table, category shot
table, fixed camera/crop rule, default selling-point sentence, local layout
plan, or post-generation compositor.

```text
seller request + product references + sourced facts + explicit user choices
  + versioned platform constraints
-> E-Commerce factual context (no visual recipe)
-> remote V3 Central Brain
-> LLM-decided per-output image intent in natural language
-> GPT Image 2 renders each complete image
-> shared visual review and bounded provider-native revision
-> append-only delivery history and current output per opaque E-Commerce slot
```

Structured objects only carry facts, evidence provenance, user-approved
literal copy, hard constraints, output identity, and the LLM's own returned
decision. They must never encode a locally authored creative answer such as a
camera angle, headline rectangle, product box, blank callout lane, category
default shot, or fallback marketing phrase.

## What is retired for new jobs

- `MarketplaceRuleEngine.image_slots` as an automatic deliverable map;
- category `default_slot_priority` and per-slot evidence mappings as a visual
  recipe;
- `SellingPointToImagePlanner` and `SLOT_GOALS` as a source of output roles;
- `EcommerceAgentFamily` construction of fixed recipe/role/camera/crop data;
- default audience, buyer motivation, selling point, and promotional copy
  invented by local code;
- `CopyRenderPlan`, fonts, OCR composition, safe areas, external overlays,
  deterministic text repair, and text-pixel activation.

Historical records containing those fields remain readable. They do not grant
a forward execution path and are never silently converted into a new job's
creative plan.

## Responsibilities

E-Commerce owns the factual context supplied to the Brain: product truth and
reference bindings; seller-supplied audience, claims, approved literal copy,
locales, and goals; category evidence questions; versioned platform constraints
and provenance; per-output opaque slot lineage and UI presentation.

It may say that a shopper must be able to judge material, scale, use, or a
supported claim. It cannot decide that an output is a macro, lifestyle frame,
or a label in a named visual lane.

Shared runtime remains the sole owner of Brain invocation, provider selection,
GPT Image 2 materialization, review, bounded revision/retry, final delivery
selection, and history. A generic template policy flag may require a real
remote Brain for a template, but General and Photography behavior must remain
unchanged.

## Remote-Brain requirement

Because the old deterministic fallback is exactly the behavior being removed,
an E-Commerce job that needs creative direction fails closed when the remote
Brain is unavailable or returns an incomplete image-set decision. It must not
fall back to static recipes. Test doubles may emulate a remote Brain in tests,
but they must be explicitly labelled as test providers.

The selected output count and explicit canvas requirement remain user controls.
The Brain must return one natural-language intent for each requested output. A
mismatch is a planning error, not permission for local code to fill roles.

## Platform and category knowledge

Platform rules are versioned evidence, not a permanent hard-coded style
catalog. A record may state a confirmed constraint, market, source status, and
review obligation. The Brain decides how to satisfy it for this product.

Category records are evidence prompts such as “can a shopper judge fit and
material?” or “are ports and scale intelligible?” They are optional Brain and
review context. They cannot prescribe a shot order, camera, scene, phrase, or
layout.

## Continuation and text compatibility

Doc105 continuation keeps a stable `slot_id`, but new slot IDs are opaque
output identities (`ecommerce_output_1`, etc.), not semantic platform or
category recipes. The delivered output's LLM-generated intent is displayed
with it.

Doc111 remains authoritative for in-image text: exact approved literal copy
is passed once to the Brain/provider, final pixels are inspected, and any
repair is a bounded provider-native revision. No local text operation exists.

## Migration gates

1. New planning contains no static slot/recipe/camera/crop/default-copy fields.
2. A remote Brain receives only factual E-Commerce context and returns a
   complete per-output plan matching the requested count.
3. The vertical pack turns that plan into opaque output identities; it never
   invents or fills an intent.
4. General and Photography tests prove their Brain payloads and role plans do
   not gain E-Commerce terms or behavior.
5. Legacy text-pixel calls remain read-compatible but cannot reach fonts, OCR,
   canvas, composition, or a provider-output replacement.
6. Real Provider Gate C/D remains required before production readiness.

## Migration ownership

The E-Commerce branch owns the context builder, planner/vertical replacement,
E-Commerce UI wording, docs, and E-Commerce tests. It may make only the
minimal shared changes required for opaque Brain context and a template-scoped
remote-Brain requirement. It must not alter General or Photography art
direction, provider behavior, or review/retry ownership.
