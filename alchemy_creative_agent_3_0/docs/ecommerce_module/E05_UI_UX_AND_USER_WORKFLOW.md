# E05 E-Commerce Workspace UI/UX and User Workflow

## User promise

The user uploads a product, chooses where it will be sold, confirms facts and
request constraints, then receives an image-first set. The user never has to
see provider names, prompts, manifests, capability graphs, or local recipes.

## Primary flow

```text
select/create product project
-> upload product images
-> confirm product facts and unknown-fact warnings
-> choose platform/market and category evidence context
-> choose requested output count
-> enter the request and optional approved literal copy / locale
-> generate through the remote Central Brain
-> select/reject an individual output or continue it with feedback
-> export selected images
```

## Required workspace regions

1. Product-reference area.
2. Confirmed facts and unknown-fact warnings.
3. Platform and market selector.
4. Category evidence selector.
5. Request composer and requested-count control.
6. Optional seller facts, approved literal copy, and locale controls.
7. Image-first output board with the Brain-returned purpose in plain language.
8. Per-output select, reject, and continuation actions.
9. Export panel with publish-check summary and evidence provenance.

The UI must not offer a suite scope, role selector, shot preset, overlay-copy
mode, coordinate, font, or any cosmetic button that implies a local creative
plan exists.

## Progressive disclosure

The default view shows product, platform, category, count, request, and
generate. Advanced controls may expose seller-provided audience, must-keep
facts, claims to avoid, reference notes, exact approved copy, language/units,
and requested canvas. These are facts or constraints, not a visual recipe.

## Continuation

Selected images become positive references only after user selection. Rejected
directions become correction feedback. A continuation preserves the opaque
output ID and append-only history; it does not recreate a named platform or
category slot. Retry-superseded candidates remain folded from the delivery
board.

## UI quality rules

- Images remain visually primary.
- Every card shows one short Brain-returned purpose statement.
- Locked or unavailable remote-Brain/continuation features cannot appear
  executable.
- Platform/category selection and constraint provenance remain visible in the
  run summary.
- Mobile layout keeps images and next actions above dense metadata.
- General Template does not render E-Commerce controls, output IDs, platform
  semantics, or continuation language.
