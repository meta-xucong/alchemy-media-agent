# E05 E-Commerce Workspace UI/UX and User Workflow

## User promise

The user should be able to upload a product, choose where it will be sold,
choose a product type, and receive a labeled image suite without seeing
providers, prompts, manifests, capability graphs, or internal job IDs.

## Primary flow

```text
select/create product project
→ upload product images
→ confirm detected product facts
→ choose platform/market
→ choose product category
→ choose complete suite or selected roles
→ enter one-sentence request
→ review proposed suite
→ generate
→ select/reject individual results
→ review folded history and delivery warnings
→ export selected images
```

## Required workspace regions

1. Product reference area.
2. Confirmed product facts and unknown-fact warnings.
3. Platform and market selector.
4. Category selector.
5. Suite scope and slot selector.
6. One-sentence request composer.
7. Optional selling-point and copy-language controls.
8. Image-first suite board with slot labels.
9. Selection, rejection, and folded-history actions; per-slot redo remains
   unavailable until the shared Doc105 continuation route is accepted.
10. Export panel with publish-check summary.

## Progressive disclosure

Default view shows only product, platform, category, suite scope, request, and
generate. Advanced controls may expose:

- product visual positioning (value, balanced, or premium presentation);
- target audience;
- keywords;
- competitor/style reference notes;
- must-keep facts;
- claims to avoid;
- exact copy;
- language and units;
- requested aspect ratio.
- suite expression strategy: evidence first (default), scene story,
  information-rich, content hook, or brand story.

The current scope selector remains `recommended`, `listing_core`,
`listing_full`, or `detail_supplement`. D3 will introduce the separate
`listing_only`, A+, content, and storefront delivery-scope contract; those
future values must not be presented as current UI behavior.

## Beginner-facing language

Use “商品主图”, “卖点图”, “使用场景”, “细节证明”, “尺寸/规格”, and “导出前
检查”. Hide “recipe”, “capability”, “provider”, “manifest”, “activation plan”,
and raw export filenames.

## Project continuation

Selected images become positive references only after user selection. Rejected
directions become negative feedback. Retry-superseded candidates remain in
folded history and do not occupy the final delivery board.

## UI quality rules

- Generated images remain visually primary.
- Every card explains its purpose in one short sentence.
- Planned suite rows separately explain “本图证明” (buyer evidence), optional
  “表达方式” (seller-selected strategy), and a platform primary-image
  restriction only when verified. A scene label is never shown as an Ozon or
  other marketplace policy claim.
- The expression-strategy control is advanced and defaults to evidence-first.
  Its hint explains that it cannot override verified main-image rules.
- A slot may be selected or rejected today. User-directed single-slot redo is
  unavailable until Doc105 supplies its append-only route, lifecycle, resolver,
  and browser coverage.
- Platform/category choices are visible in the run summary.
- Locked or unavailable features cannot appear executable.
- Mobile layout keeps images and next actions above dense metadata.
