# V2 Reference Content Delivery Assurance Plan

## 1. Objective and boundary

Make V2 able to prove, not merely assume, that an uploaded reference image was
used in the way the user intended.  The immediate target is information-dense
commercial source images such as menus, posters, price lists, promotion cards,
and catalogue pages.

This plan is V2-only.  It preserves the existing FastAPI endpoints, V2 task
queue, creative-run controller, selected-template rule, native V2 storage, and
OpenAI-compatible provider adapter.  It does not change V2 authentication or
billing, and does not rewrite the orchestration framework.

The governing rule remains:

```text
Selected case controls the frame.
Uploaded material has explicit, field-level authority inside that frame.
No output is deliverable merely because the provider accepted an image.
```

## 2. Evidence from the reproduced failure

The replay established two separate facts:

1. The historical failure path hard-cropped the effective provider prompt to
   5,600 characters.  The repaired path sent a 6,407-character effective
   prompt, passed its integrity preflight, used the native `images.edit` route
   with the reference image, and received a live image.
2. The live result was still not a usable menu: it invented or corrupted copy
   and menu facts, and it was marked `needs_review` because reference adherence
   cannot be established from transport metadata alone.

Therefore prompt truncation is real and fixed, but it is not the whole quality
contract.  A successful edit request is necessary evidence, not sufficient
evidence of faithful delivery.

## 3. Current design gaps

| Layer | Current behaviour | Defect | Consequence |
| --- | --- | --- | --- |
| Intent | Asset role, fusion mode, and template lock are inferred in separate steps. | A composite source can be treated as a generic reference even when its copy and facts are the product. | Source authority is implicit and can be diluted. |
| Source understanding | `composite_content_source` is described in prompt text. | There is no structured OCR/vision evidence manifest for dates, prices, dishes, offers, CTA, or source-image relationships. | The image model must infer dense business content from pixels and prose. |
| Prompt compilation | The repaired compiler prevents hard cropping. | It still gives a generative model a large prose obligation rather than an executable field contract. | Required information can be invented, omitted, or reordered. |
| Provider materialization | Required reference images use the native edit path. | Capability selection is generic; hard-reference fidelity is not negotiated or audited per model. | A provider can accept the image but apply it loosely. |
| Template lock | The selected case correctly owns the frame. | There is no explicit field-level arbitration between template-owned layout and source-owned business facts. | A visually plausible generic template can replace source truth. |
| Output review | Metadata review detects that adherence is unverified. | The current review agent has no pixel-capable comparison and does not gate delivery. | A bad result is retained as if it were a candidate of equal quality. |
| Retry | Retries focus on technical failure. | No bounded semantic retry is driven by detected missing source facts. | The system never attempts a targeted repair. |
| Dense typography | All content is delegated to image synthesis. | Generative image text is inherently unreliable for menus, prices, dates, and legal/offer copy. | Hallucinated or unreadable customer-facing text. |

## 4. Modular target design

Add a V2-native `reference_delivery` capability package.  Each module consumes
and returns small typed contracts; no module calls API routes outside V2.

```text
request + assets
  -> ReferenceIntentResolver
  -> SourceEvidenceExtractor
  -> TemplateAuthorityBridge
  -> PromptIntegrityCompiler (existing)
  -> ProviderCapabilityMaterializer
  -> image provider
  -> VisualEvidenceReviewer
  -> DeliveryGate / SemanticRetryCoordinator
  -> V2 output history
```

### 4.1 `reference_intent.py`: canonical source authority

This pure module resolves one canonical `ReferenceIntentContract` per asset
before prompt composition.  It removes conflicts between an upload's stored
role, request role, user notes, and inferred fusion mode.

Core fields:

```python
usage_mode: Literal[
    "subject_identity", "product_identity", "logo_exact", "background",
    "style", "composition", "composite_content", "source_layout"
]
authority: Literal["required", "strong", "advisory"]
source_owned_fields: list[str]
template_owned_fields: list[str]
provider_input_required: bool
source_layout_policy: Literal["never", "only_if_unlocked", "required"]
```

Rules:

- A selected template continues to own composition, hierarchy, lighting, and
  layout by default.
- A menu/poster marked `composite_content` owns the extracted business facts
  and source-image-to-copy correspondence, but not the source layout unless
  the user explicitly unlocks it.
- A logo or exact product/face is a hard input; it must not silently degrade to
  a style cue.
- Conflicts are recorded as a safe reason code rather than silently resolved.

Integration point: enrich the output of `asset_binding.py`; retain its current
public data shape and add the contract under `asset_context`.

### 4.2 `source_evidence.py`: extract facts before generation

This module turns a dense source into a `SourceEvidenceManifest`.  It should be
provider-independent and pluggable: local OCR first, then an approved vision
extractor only when needed.

The manifest stores structured fields, confidence, bounding regions, and
content hashes:

```python
critical_copy: list[EvidenceField]       # heading, dish, date, price, CTA
visual_items: list[EvidenceItem]         # food/product image, logo, QR intent
relationships: list[EvidenceRelation]    # dish -> copy, offer -> price
language: str | None
source_fingerprint: str
```

Raw source image bytes remain in existing V2 storage.  Exact copy needed by a
queued run is retained only in the V2 task's protected request state; logs,
metrics, and review summaries contain field identifiers, hashes, and counts,
never full user copy.

Low-confidence extraction is not silently invented.  It produces
`needs_confirmation` or a visible editable field list before chargeable
generation.

### 4.3 `template_authority_bridge.py`: map facts to template slots

This module converts the intent contract and source evidence into a
`DeliveryContract`:

```python
required_facts: list[RequiredFact]
required_visual_items: list[RequiredVisual]
layout_owner: "template" | "source"
text_rendering_mode: "generative" | "deterministic_overlay"
acceptance_rules: list[AcceptanceRule]
```

It enforces field-level ownership rather than choosing either whole source or
whole template.  For a selected menu template, the template provides the
frame; source evidence provides exact named dishes, dates, prices, offer terms,
and intended food-image correspondence.

## 5. Provider and rendering improvements

### 5.1 `provider_capabilities.py`

Add a small capability map for each V2 image provider and model.  The existing
adapter continues to call the same `images.generate`/`images.edit` methods,
but materializes only supported fidelity controls.

- Required reference contracts force the edit route and assert the number and
  order of provider input images.
- If the selected model supports an edit-fidelity parameter, materialize it
  only for hard identity/content contracts.  Do not send unsupported keys.
- Persist a safe request receipt: operation type, model, input count,
  capability profile, parameter names, prompt hash, and elapsed time.
- If the model cannot meet a hard contract, fail before provider billing or
  route to a configured compatible provider; never quietly downgrade to
  text-only generation.

Integration point: keep `openai_gpt_image_2.py`; extract its capability and
kwargs decisions into the new module.  No route or schema rewrite is needed.

### 5.2 `copy_safe_compositor.py`

Dense typography must not rely on diffusion rendering.  For menus, schedules,
prices, promotional rules, CTA, addresses, or legal text:

1. Generate the visual background, food/product imagery, and non-text design.
2. Use a V2-native deterministic compositor (Pillow/SVG/HTML renderer) to
   place approved extracted copy into template text slots.
3. Re-open the finished PNG and run the same visual review.

This is not a framework change: it is an optional postprocess provider used
only when `DeliveryContract.text_rendering_mode == "deterministic_overlay"`.
It is the only reliable way to preserve exact CJK text, dates, prices, and
offer conditions.

## 6. Pixel-based acceptance and bounded repair

### 6.1 `visual_evidence_review.py`

Replace metadata-only acceptance with a pluggable pixel reviewer.  It receives
the generated output, the delivery contract, source evidence, and optional
template visual grammar.  It returns a `VisualEvidenceReport`, including:

- OCR match coverage for required text, dates, prices, quantities, and CTA;
- required food/product/logo presence and source-to-copy correspondence;
- template-frame compliance without accidental source-layout copying;
- readable-text, clipped-text, garbling, and date-sequence checks;
- reference adherence score, missing field identifiers, and reviewer version.

Outcomes are `pass`, `retry_recommended`, `needs_user_confirmation`, or
`failed_delivery_contract`.  A live provider result with an unverified hard
reference can never be promoted automatically to `pass`.

The reviewer has two implementations behind one interface:

- deterministic OCR/layout rules for dense-text artifacts;
- an approved vision reviewer for subject/product/style correspondence.

When no pixel reviewer is configured, V2 retains the current conservative
`needs_review` state and must not label the result deliverable.

### 6.2 `semantic_retry.py`

Permit one bounded repair attempt only when the report identifies a repairable
failure.  The retry prompt is generated from structured missing field IDs and
review directives, not by replaying or appending the full user prompt.

Examples:

- OCR mismatch -> regenerate visual layer with reduced text, then apply
  deterministic text overlay.
- missing hard product/logo/face -> retry with the same native input image and
  a capability profile requiring high fidelity when supported.
- structural template failure -> retry with the template contract only.

Keep all candidates internally, score them with the same reviewer, and expose
only the best passing delivery output.  Do not retry moderation, billing,
authentication, or unknown provider failures.

## 7. Minimal integration map

| Existing V2 component | Change | New module |
| --- | --- | --- |
| `services/asset_binding.py` | Emit canonical source-authority contract. | `reference_intent.py` |
| `services/prompting.py` | Compile delivery contract sections without crop or duplication. | `template_authority_bridge.py` |
| `providers/images/openai_gpt_image_2.py` | Capability-negotiate edit parameters and request receipt. | `provider_capabilities.py` |
| `services/generation.py` | Invoke review gate and bounded semantic retry. | `semantic_retry.py` |
| `services/output_review.py` | Delegate pixel verification; no metadata-only delivery pass. | `visual_evidence_review.py` |
| `services/output_storage.py` | Optionally apply deterministic copy overlay before final save. | `copy_safe_compositor.py` |

`app/main.py`, the public V2 endpoints, task queue schema, Veyra boundary, and
existing selected-case selection remain unchanged.  New contracts can travel
inside existing `prompt_plan.user_variables` and output metadata during the
first rollout; a database migration is not required.

## 8. Rollout order and acceptance tests

### Phase A — observable, no behavioural change

- Add canonical contracts and safe request receipts.
- Emit shadow `SourceEvidenceManifest` and reviewer reports.
- Add fixture tests for hard subject, logo, style, composition, and composite
  menu/poster sources.

### Phase B — prevent false delivery

- Enable the pixel review gate for hard references and dense text.
- Retain current generation, but block automatic delivery on unverified or
  failed contracts.
- Verify no V2 route or storage namespace outside V2 is touched.

### Phase C — improve output fidelity

- Enable capability-negotiated edit fidelity and one semantic retry.
- Enable deterministic typography overlay for information-dense templates.
- Compare candidate outputs and deliver only the highest passing result.

Required regression assertions:

1. Full user intent is never silently cropped; budget overflow fails before a
   provider call.
2. A hard reference always reaches a compatible native provider edit path.
3. A source menu with required copy cannot receive `pass` when OCR detects
   missing, garbled, or reordered critical fields.
4. A selected template keeps its frame unless an explicit source-layout unlock
   is present.
5. One semantic retry is the maximum; no mock/text-only downgrade is allowed.
6. Review telemetry contains no full prompt, source image, token, or raw
   provider payload.

## 9. Success metric

The system succeeds when a run can answer, with stored evidence: which source
facts were required, which provider inputs were sent, which facts appeared in
the final pixels, which candidate won, and why it was safe to deliver.  A
visually plausible but fabricated menu must fail this contract rather than be
mistaken for a successful generation.
