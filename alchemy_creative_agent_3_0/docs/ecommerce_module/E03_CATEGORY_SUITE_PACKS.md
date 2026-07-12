# E03 Category Suite Packs and Evidence Maps

## Completed D2 category pack contract

Each first-wave category pack declares:

```text
category_id
display_name
buyer_questions
required_evidence
optional_evidence
default_slot_roles
human_presence_policy
text_roles
product_truth_fields
review_checks
```

Each runtime slot now resolves to a category director with a stable ID,
plain-language purpose, evidence target, fact channels, review checks,
differentiation key, and scene direction. Those fields are copied into recipe
and export metadata for audit; they are not provider controls or General
Template behavior.

## First-release category packs

| Category | Required evidence | Default roles |
| --- | --- | --- |
| Apparel/shoes/bags | fit, front/back/side, material, scale, wear context | hero, front, back, worn, detail, size, styling |
| Beauty/skincare | package, texture, application, usage boundary, ingredients if confirmed | hero, texture, application, benefit, package, routine, detail |
| Electronics/3C | silhouette, ports, dimensions, included items, real use | hero, angle, ports, hand-scale, desk/use, accessories, spec |
| Home/kitchen | size, material, capacity, function, cleaning/storage | hero, space, size, material, function, capacity, use |
| Food/beverage | package, serving, contents, portion, truthful ingredient cues | hero, serving, detail, portion, use, package, trust |

For shoes and bags, the E-Commerce category retains related evidence coverage
but uses accessory-specific form, closure, side, hardware, scale, and real-use
directors. It must never inherit garment-on-model, garment-fit, or garment
construction instructions.

Second-wave packs may include jewelry/accessories, furniture/decor,
sports/outdoor, pet, and baby products after the first five pass review.

## Semantic slot vocabulary

```text
main_image
feature_highlight
angle_or_back
detail_proof
usage_scene
scale_or_size
comparison_or_trust
package_or_accessories
social_cover
```

These are semantic roles, not literal runtime slot IDs. Current runtime IDs
such as `feature_image_1`, `feature_image_2`, `detail_image`, and
`trust_comparison_image` map to them through the E-Commerce planner. Each
selected slot must be mapped to one business goal such as `click`,
`understand`, `trust`, `compare`, `desire`, or `remember`.

## Product-category adaptation

The pack must be evidence-aware. Examples:

- If no confirmed size exists, do not generate a measurement diagram with
  invented numbers; use a relative-scale scene or mark the slot unavailable.
- If a product has no confirmed human-use context, a person may demonstrate
  generic interaction but must not imply a medical, safety, or performance claim.
- If packaging text is unreadable in the source, preserve the visible design
  without fabricating legible copy.

## Garment evidence sequence

The apparel pack turns a garment into distinct buyer-proof roles rather than
repeating the same model pose:

```text
primary silhouette
→ worn front fit
→ back or side construction
→ textile / embroidery / hardware detail
→ real wear context
→ fit or size evidence
→ truthful styling alternatives
```

This is an E-Commerce category sequence, not an Amazon policy claim. Amazon
main-image restrictions remain a separate verified constraint; the remaining
roles are selected to make apparel fit, construction, material, and use
legible. It applies to garments, not automatically to shoes or bags that share
the first-release umbrella category. The detailed external benchmark and visual
acceptance rubric are in `E10_EXTERNAL_AMAZON_APPAREL_BENCHMARK.md`.

## Suite count behavior

Default count is category/platform dependent, but user-requested count wins.
When count is smaller than the default, select the highest-value roles using:

```text
verified placement constraint
→ product evidence coverage
→ buyer uncertainty reduction
→ visual differentiation
```

When count is larger, add optional roles without duplicating the same scene.

## Suite differentiation gate

Within one suite, two images fail differentiation when they share the same
purpose, camera relationship, scene logic, and selling point without a clear
reason. Variation means useful evidence variation, not random decoration.

## D2 implementation boundary

The category director is declarative E-Commerce planning data only. It may
choose what a product suite should prove, but it may not change shared Product
Identity, Human Realism, Provider, Review/Retry, OCR, typography, or platform
compliance rules. Human-presence policy describes the business role only; any
real-person rendering is still governed by the shared Human Realism capability.
