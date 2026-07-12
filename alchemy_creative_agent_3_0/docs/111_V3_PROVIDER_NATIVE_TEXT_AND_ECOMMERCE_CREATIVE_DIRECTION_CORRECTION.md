# 111 V3 Provider-Native Text And E-Commerce Creative-Direction Correction

Status: active architecture correction. Provider-native image generation is
the only forward production path for in-image copy. The deterministic
text-pixel compositor is legacy/read-compatible only and must not be extended,
certified, or selected for new jobs.

## 1. Product decision

V3 is an LLM-led creative system. A user describes the desired image, the LLM
reasons about the full brief, and the selected image provider renders the
complete image. When copy belongs in the image, the provider renders that copy
as part of the image; V3 must not add it afterwards with fonts, HTML, SVG,
canvas coordinates, or a template-owned raster compositor.

`gpt-image-2` is the default provider-native target for this path. Literal
copy, when supplied or approved, is expressed in the LLM/provider creative
brief in plain language. The model decides its typography, visual integration,
and placement in the context of the image. A system may request exact wording,
but it may not turn that request into a local pixel overlay.

This is not a relaxation of quality. It changes the quality mechanism:

```text
user request + factual constraints
-> LLM creative reasoning and provider-native image brief
-> GPT Image 2 generate or edit of the complete image
-> final-pixel vision/OCR review
-> LLM/provider-native targeted revision when needed
-> append-only candidate history and one current delivery
```

Review is observational. It may reject or formulate a revision request; it
never paints corrective copy into the asset.

## 2. What remains structured, and what does not

The correction does not remove all contracts. The following are factual or
governance controls and remain valid:

- source-aware product facts, claim restrictions, and product-reference truth;
- platform evidence and text-forbidden policy, clearly marked as versioned
  evidence rather than live legal advice;
- output lineage, selected-result continuity, append-only history, and bounded
  provider retry/revision ownership;
- final-pixel review for unwanted text, requested literal copy, product truth,
  visual quality, and policy outcomes.

The following are not acceptable as a forward creative or rendering contract:

- local font selection, font manifests, glyph fallbacks, and deterministic
  post-generation rasterization;
- HTML/SVG/canvas text layers, editable external-copy manifests, or a render
  requirement inferred from an image asset;
- normalized text rectangles, fixed headline/CTA coordinates, blank
  callout-lane instructions, or a fixed product box used to force a provider
  composition;
- automatic truncation or slot-derived promotional wording;
- a generic/shared catalogue of E-Commerce slot visuals, camera positions, or
  retry language.

## 3. Foundation and specialized-template boundary

Foundation owns provider-native prompt materialization, generic visual review,
final-pixel text inspection, provider-native revision, and output history. It
does not own an E-Commerce role, marketplace slot, product-copy recipe, or
fixed layout.

E-Commerce owns a professional suite's business evidence: product facts,
buyer questions, explicit user choices, category knowledge, and versioned
platform constraints. These are inputs to LLM reasoning, not a rigid image
recipe. An E-Commerce role may say that a shopper should understand material,
scale, use context, or a supported claim; it must not prescribe a fixed crop,
coordinate, blank area, post-render copy operation, or canned sentence.

General Template stays scenario-neutral. It gains no E-Commerce fields,
marketplace policy, slot names, or bundle director as part of this migration.

## 4. Text intent contract

New jobs use a provider-native text intent:

- `forbidden`: instruct the provider to produce no added text and inspect final
  pixels for unwanted text;
- `requested`: pass the user-approved literal wording to the LLM/provider
  creative brief and require it to appear once, legibly, with no extra text;
- `optional`: let the LLM decide whether text improves the requested image;
  no default promotional phrase is invented.

Text intent is never a font, coordinate, safe-area, or overlay schema. Locale
and claim provenance remain available to the reviewer, but do not constrain
the provider with a local rendering recipe. A failed requested-text review
becomes a bounded provider-native revision request, never a local patch.

## 5. Migration and compatibility

Historical output manifests, `CopyRenderPlan` records, and deterministic
text-pixel delivery records remain readable. They are archival provenance, not
an available fallback. New jobs must not activate `text_pixel_delivery`, bind a
`CopyRenderPlan`, set `requires_text_overlay`, or emit an editable external
text render spec.

The following documents are superseded for forward implementation only:

| Historical contract | Correction |
| --- | --- |
| Doc105 sections 6-8 | Keep continuation; replace deterministic typography with provider-native text and observational review. |
| Doc107 | Do not integrate or certify the deterministic compositor as a production path. |
| Doc110 | Do not create multi-plan compositor batches; preserve only historical read compatibility. |
| E12-E15 | Documentation-branch handoffs are obsolete for forward text delivery and must not merge unchanged. |
| E16 text-delivery references | A+ planning may carry a provider-native creative brief, but cannot invoke a local renderer or promise pixels before provider review. |

E00-E11, E12-E16, tests, and implementation logs must be updated to cite this
document before another E-Commerce text feature is accepted.

## 6. Audit findings and required code correction

The audit found five coupled legacy paths:

1. `AssetSpec.requires_text_overlay=True`, `LayoutAgent`, and planning scorers
   manufacture text regions and reward them by default.
2. `PromptCompilerAgent` tells the image provider not to render final text and
   requests later external overlays, even when a text-capable provider is
   selected.
3. `text_pixel_delivery` activation, `CopyRenderPlan`, the deterministic
   compositor, and the planned production-font work implement a competing
   renderer.
4. E-Commerce `CopyBridge`, `SellingPointToImagePlanner`, and export metadata
   derive/truncate slot copy before the LLM has made a creative decision.
5. `EcommerceAgentFamily` and shared `ModeAwareRoleDirector` impose fixed
   product boxes, label lanes, slot camera/crop recipes, and E-Commerce retry
   language. The shared occurrence also violates the V3 foundation boundary.

Migration requirements:

- default all new assets to provider-native or no-text rendering and omit text
  regions unless retained solely for historical reading;
- compile exact approved text into the provider prompt when present, otherwise
  prohibit invented marketing text by default;
- remove E-Commerce fixed geometry and external-label wording from active
  prompt/layout paths; retain buyer-evidence goals only;
- remove deterministic text capability activation from new jobs and expose no
  route that can select it as a fallback;
- relocate or retire E-Commerce-specific role defaults from shared Visual
  Capability code;
- add tests proving no new job produces an external overlay plan, no derived
  copy is silently generated or truncated, text-forbidden images are reviewed
  as final pixels, and General Template remains free of E-Commerce semantics.

## 7. Release gate

Production readiness now means real provider-native evidence, not font
installation. Before claiming production text delivery, retain authorized
fixtures showing requested `en-US`, `zh-CN`, and `ru-RU` copy, a text-forbidden
case, a failed-provider or failed-review bounded revision, final-pixel
inspection, product-fact/claim provenance, and human visual acceptance.

No font/OCR deployment record may be used to claim that a local compositor is
approved. OCR remains useful as an inspection tool only when its real deployed
availability and language coverage are evidenced.
