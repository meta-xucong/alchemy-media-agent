# E03 Category Evidence Contexts

## Category context contract

Each category record declares:

```text
category_id
display_name
buyer_questions
required_product_facts
claim_risk_cues
review_checks
source_version
```

It helps the remote Brain and final review understand what a shopper may need
to judge. It must not prescribe scenes, cameras, angles, people, copy,
layouts, output roles, or output order.

## First-release evidence records

| Category | Example buyer questions |
| --- | --- |
| Apparel/shoes/bags | Can fit, material, scale, and relevant sides be judged truthfully? |
| Beauty/skincare | Can package, texture/application, and only confirmed usage facts be judged? |
| Electronics/3C | Are silhouette, ports, dimensions, included items, and real use intelligible? |
| Home/kitchen | Are size, material, capacity, function, and storage/use facts intelligible? |
| Food/beverage | Are package, serving, contents, portion, and confirmed ingredients truthful? |

Jewellery, furniture, sports/outdoor, pet, and baby categories are added only
after the same evidence-first review; they are not a new set of local shot
recipes.

## Product-category adaptation

- If a size, capacity, ingredient, compatibility, or quantity is unconfirmed,
  the context says it is unknown. Neither the E-Commerce module nor the Brain
  may claim it as fact.
- If human use is relevant, the Brain may decide whether a person is useful.
  Any visible person still uses the shared Human Realism capability; E-Commerce
  does not implement a person-rendering branch.
- If source packaging text is unreadable, preserve its visual evidence without
  inventing legible copy or a specification.

## Requested-count behaviour

The user controls the requested count. The remote Brain must return exactly
one distinct natural-language intent per requested output. A mismatch is a
planning error and fails closed; local code may not rank, trim, expand, or fill
the image set from a category default.

## Differentiation review

Review can flag redundant evidence or indistinguishable outputs. The shared
provider-native revision path gives that observation back to the Brain/provider
within its bounded retry contract. E-Commerce never substitutes a local role
or shot to repair the set.
