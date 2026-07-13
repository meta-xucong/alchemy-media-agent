# E01 E-Commerce Module Scope, Goals, and Boundary

> New-job authority: E17 and Doc111 override any historical static-suite or
> local-text wording in this document family.

## Product promise

Turn a product reference and a short request into a coherent, reviewable,
platform-aware commerce image set. The remote Central Brain decides what each
image should show for that specific product. The workspace explains the
returned intent in plain language and can continue one opaque output without
restarting the project.

## In scope

- Product-truth extraction and user correction.
- Versioned platform constraint evidence and category evidence questions.
- Seller-provided audience, claims, goals, locale, and approved literal copy.
- Passing factual E-Commerce context to the remote Central Brain.
- Binding each Brain-returned intent to an opaque output identity.
- Provider-native complete-image generation, shared review, bounded retry,
  selection, continuation, and export.

## Out of scope

- Guaranteed marketplace approval, sales lift, legal compliance, or automatic
  marketplace publishing.
- Local category classification that chooses a visual answer.
- Static platform/category slot maps, shot orders, scenes, cameras, crops,
  default audiences, selling points, or promotional phrases.
- Local font, overlay, canvas, OCR, text-repair, or post-generation compositor.
- A provider runtime, project store, or shared visual-quality fork.
- Moving E-Commerce deliverables into General Template or shared visual plugins.

## Layer ownership

| Layer | Owns | Must not own |
| --- | --- | --- |
| V3 foundation | Brain, provider-native generation, shared quality review, retry, reference integrity | marketplace deliverable maps or local text rendering |
| General Template | neutral images and simple product scenes | listing suites, platform assumptions, opaque E-Commerce output lineage |
| E-Commerce Template | factual commerce context, output lineage, E-Commerce UI and export | a local art director or rendering implementation |
| Platform profile | sourced market/content/claim/text constraints | slots, typography coordinates, or generation provider choice |
| Category evidence | buyer questions and review cues | shot order, scene, people, text, camera, or layout |
| Product truth | confirmed facts and unknowns | invented claims, specifications, or visual decisions |

## Context-to-image model

```text
product truth + seller-approved facts + user request + requested count
+ platform constraint evidence + category evidence questions
+ locale / approved literal copy
-> remote Central Brain returns one natural-language intent per output
-> provider-native complete images + shared review/revision
```

Structured fields transport facts, evidence provenance, exact user-approved
copy, hard constraints, output IDs, and the Brain's own result only. They may
not contain a locally authored creative answer.

## Non-negotiable product rules

1. Product shape, quantity, label, logo, colour, material, and visible
   structure are preserved unless the user explicitly requests a redesign.
2. Unknown facts remain unknown. The system must not invent capacity,
   certification, ingredients, performance, warranty, audience, or claim.
3. A verified platform restriction applies only as evidence for the actual
   request; it cannot become a default suite or universal style.
4. Approved copy is sent to the Brain/provider as a provider-native
   requirement and judged from final pixels. It is never locally overlaid.
5. Retry outputs remain append-only internally; delivery surfaces show only
   the final requested count.
6. Each delivered output keeps the Brain-returned intent and an opaque output
   ID. Local code never supplies a missing role or image direction.
