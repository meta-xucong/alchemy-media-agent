# E03 Category Suite Packs and Evidence Maps

## Category pack contract

Each category pack declares:

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

It defines what must be shown, not merely a visual style.

## First-release category packs

| Category | Required evidence | Default roles |
| --- | --- | --- |
| Apparel/shoes/bags | fit, front/back/side, material, scale, wear context | hero, front, back, worn, detail, size, styling |
| Beauty/skincare | package, texture, application, usage boundary, ingredients if confirmed | hero, texture, application, benefit, package, routine, detail |
| Electronics/3C | silhouette, ports, dimensions, included items, real use | hero, angle, ports, hand-scale, desk/use, accessories, spec |
| Home/kitchen | size, material, capacity, function, cleaning/storage | hero, space, size, material, function, capacity, use |
| Food/beverage | package, serving, contents, portion, truthful ingredient cues | hero, serving, detail, portion, use, package, trust |

Second-wave packs may include jewelry/accessories, furniture/decor,
sports/outdoor, pet, and baby products after the first five pass review.

## Shared slot vocabulary

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

Category packs may rename a role for the UI, but internal slot IDs stay stable.
Each selected slot must be mapped to one business goal such as `click`,
`understand`, `trust`, `compare`, `desire`, or `remember`.

## Product-category adaptation

The pack must be evidence-aware. Examples:

- If no confirmed size exists, do not generate a measurement diagram with
  invented numbers; use a relative-scale scene or mark the slot unavailable.
- If a product has no confirmed human-use context, a person may demonstrate
  generic interaction but must not imply a medical, safety, or performance claim.
- If packaging text is unreadable in the source, preserve the visible design
  without fabricating legible copy.

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
