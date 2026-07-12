# E10 External Amazon Apparel Benchmark and Visual Acceptance Card

## Purpose and handling

This card records lessons from a user-supplied external demonstration of an
Amazon apparel image-generation workflow. The source screenshots remain outside
the repository and are **not** copied, redistributed, or used as pixel-match
fixtures. The retained benchmark is the deliverable logic and quality bar, not
the brand, person, garment, wording, or composition of any individual image.

Use it for two jobs:

1. verify that the E-Commerce apparel planner creates a purposeful suite rather
   than seven variations of one pose; and
2. run a future real-provider visual acceptance fixture with a consented,
   project-owned garment reference.

It does not create an Amazon approval claim. The verified Amazon primary-image
baseline and its category/region exceptions remain governed by E02.

## What the external case demonstrates

The useful pattern is a two-layer delivery map:

```text
one product truth lock
→ seven listing evidence images
→ seven A+ narrative/layout modules
```

The reference succeeds when it makes the same garment recognisable across
studio, model, close-detail, back-construction, and lifestyle views. It also
shows a coherent campaign model/style direction, restrained readable copy, and
role-level prompts instead of one generic “make a product image” instruction.

The following observations are **not** accepted as proof by themselves:

- text looks legible in an image screenshot;
- a fabric composition or benefit is rendered as text;
- a back-construction feature appears in a generated image but was not visible
  in the reference; or
- a scene or three-look composition is aesthetically successful.

Those still require supplied product facts, Doc111 provider-native
complete-image acceptance, and real-provider review.

## Product truth contract learned from the case

For apparel, split facts into three sources before planning:

| Fact class | Example | Runtime treatment |
| --- | --- | --- |
| Reference-visible, immutable | stripe direction/scale, collar, placket, cropped silhouette, embroidery placement | Bind as product truth on every slot and review it visually. |
| Supplier-confirmed but not visible | a back pintuck, hidden lining, exact composition | Keep it as product truth only with `unverified_visual_facts`; current export attention requires review, while D4 adds persisted owner confirmation. |
| Marketing or unconfirmed claim | comfort, performance, premium quality | Do not turn it into image copy or a visual assertion without evidence. |

The optional E-Commerce input `unverified_visual_facts` is additive. It does
not weaken a supplied reference. It currently produces critic and export
publish-check attention rather than allowing a generator to “prove” the fact;
D4 will add persisted owner confirmation.

## Current Amazon apparel listing map

The implemented apparel suite uses these seven listing roles:

| Slot | Buyer proof | Quality bar |
| --- | --- | --- |
| `main_image` | complete primary garment identity | Obey the verified Amazon main-image baseline; no text or campaign treatment. |
| `feature_image_1` | front worn fit | Natural posture; garment, not props or model styling, remains legible. |
| `feature_image_2` | back or side construction | A genuinely distinct view; do not invent a back detail. |
| `detail_image` | fabric, embroidery, stitching, or hardware | Macro framing preserves pattern scale and correct placement. |
| `scenario_image` | believable adult wear context | Real fabric drape and human proportions; the garment stays recognisable. |
| `size_spec_image` | fit, relative scale, or supplied sizing | No fabricated measurements or size chart. |
| `trust_comparison_image` | truthful styling versatility | Distinct outfits may show the same garment; no comparative performance or certification claim. |

This map is category-owned. It is deliberately separate from Amazon’s narrow
primary-image constraint and from the shared Human Realism, Product Identity,
Provider, Review, and Retry layers.

## A+ modules are a separate future deliverable map

The external case also demonstrates seven A+-style narrative modules: an
occasion-led hero, styling alternatives, feature/detail explanation,
construction proof, and coordinated campaign imagery. They are valuable
direction for a future E-Commerce A+ scope, but are **not** currently exposed
as an approved output contract.

Before such a scope is added, it needs:

1. an explicit placement choice distinct from listing images;
2. merchant/category/market confirmation of the target A+ module rules;
3. Doc111 provider-native complete-image acceptance for any approved literal
   copy and claims; and
4. a bounded real-provider acceptance run.

Until then, the planner may use `scene_story`, `information_rich`, or
`brand_story` only as an auditable secondary-image strategy. It must not claim
that a generated text layout is A+-ready.

## Acceptance fixture and scoring

The automated planning fixture is
`test_v3_ecommerce_e24_amazon_apparel_benchmark.py`. A real fixture must use a
project-owned reference garment and record source evidence for every fact.
Score each selected output pass/fail, not by pixel similarity:

| Gate | Pass condition |
| --- | --- |
| Product fidelity | Color, pattern direction/scale, collar, placket, silhouette, and visible embroidery/trim match the source. |
| Construction truth | Back/side/hidden details appear only when evidence exists or the product owner explicitly confirms them. |
| Suite differentiation | Each image proves its mapped role; no duplicate model pose or redundant crop substitutes for a detail/back/fit proof. |
| Amazon primary | Main image satisfies the verified primary-image baseline and category/region check. |
| Human realism | Hands, face, fit, fabric drape, and posture are commercially believable through the shared Human Realism path. |
| Text and claims | Main image has no text. Any secondary/A+ copy is user-approved literal text passed only through the Doc111 provider-native complete-image path; production use remains blocked until Gate C/D. |
| Delivery closure | Review/retry history is bounded, superseded attempts are folded, and only final selected outputs are surfaced. |

An output fails the fixture if any hard product-fidelity, primary-image, or
unverified-construction gate fails. A visually attractive image never offsets
a product-truth or provider-native literal-copy acceptance failure.

## Integration boundary

Implemented now in E-Commerce only:

- apparel slot-specific guidance and distinct default evidence roles;
- Amazon apparel listing map includes a dedicated detail role and replaces the
  generic campaign cover in the default listing suite;
- `unverified_visual_facts` metadata and pre-delivery critic attention; and
- unit coverage for the role map and confirmation requirement.

The first-release category registry still groups apparel, shoes, and bags for
high-level evidence coverage. Garment-specific prompt guidance is explicitly
suppressed for shoes and bags, so this benchmark does not turn into a
cross-category default.

Still shared-runtime or future-template work:

- provider-native complete-image text acceptance and Doc111 Gate C/D evidence;
- real-provider visual review and acceptance; and
- a separately scoped A+ module builder, placement rules, and UI.
