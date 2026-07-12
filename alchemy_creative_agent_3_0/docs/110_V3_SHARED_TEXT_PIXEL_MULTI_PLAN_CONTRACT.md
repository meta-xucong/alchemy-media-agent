# 110 V3 Shared Text-Pixel Multi-Plan Contract

Status: additive shared-runtime contract; production activation remains off.

## 1. Scope

This document extends Doc107 with an ordered collection of independently bound
`CopyRenderPlan` values. It is V3 foundation work: templates may map their own
approved intent to this contract, while the shared runtime owns composition,
final-pixel review, bounded repair, retry signaling, lineage, and delivery
resolution.

The contract contains no template role, platform, marketplace, category, or
suite vocabulary.

## 2. Activation marker

Before scenario planning allocates concrete generated assets, a template may
provide only this opaque internal marker:

```text
internal_copy_render_plan_present = true
```

The Brain receives only that boolean. It may cause the scenario-neutral
`text_pixel_delivery` capability to enter the frozen plan, but it must not
receive copy text, locale, source lineage, template role, or platform data.
The marker cannot activate a capability after the plan freezes.

## 3. Multi-plan envelope

After planning supplies concrete source assets or outputs, an internal template
mapper may provide exactly one of these mutually exclusive fields:

```text
copy_render_plan: CopyRenderPlan
copy_render_plans: [CopyRenderPlan, ...]
```

`CopyRenderPlanBatch` validates the multi-plan form. Every member must have a
unique plan ID and a unique source asset or output lineage. The Product API
binds every member to the exact frozen activation-plan ID before generation.

Existing single-plan callers keep `copy_render_plan` and their
`text_pixel_delivery` result shape. The multi-plan form exposes a new
`text_pixel_delivery_batch` result, and each resolved generated asset carries
its own `text_pixel_delivery` metadata with the current delivery output.

## 4. Shared execution and recovery

```text
frozen plan + CopyRenderPlanBatch
-> one resolved source asset/output for each plan
-> shared deterministic composition per plan
-> OCR/layout/safe-area/claim review per plan
-> at most one deterministic repair per plan
-> existing shared generation-retry signal only when that plan has
   frozen-contract background/readability failure
-> append-only per-plan delivery history
```

`TextPixelDeliveryRuntime.deliver_many()` owns the collection execution.
Templates must not implement their own loops around the legacy single-plan
renderer, OCR, repair, or retry behavior.

When a shared generation retry occurs, the Product API merges each plan's
attempt chain independently. A failed retry preserves any earlier passed
delivery for that same plan and never overwrites a different asset's delivery.

## 5. Production gate

The multi-plan contract does not enable production text delivery. These remain
mandatory before activation:

- deployment-approved, versioned fonts for `en-US`, `zh-CN`, and `ru-RU`;
- Tesseract with `eng`, `chi_sim`, and `rus` language data in the deployed
  runtime; and
- owner-approved real Provider Gate C/D fixtures and recorded visual review.

Until then, runtime gates remain off and planned plans report non-delivery
states such as `planned_only`; they must not be presented as final text pixels.

## 6. Compatibility and acceptance

The additive implementation is covered by shared tests for:

- opaque pre-plan activation marker followed by frozen-plan binding;
- single-plan compatibility and gate-off `planned_only` behavior;
- independent multi-plan binding and source-lineage uniqueness;
- per-asset batch delivery resolution; and
- append-only, per-plan retry merging.

Consumer branches must rebase onto the mainline integration commit and map
their own approved intent to the shared envelope. They may not add template
specific font, OCR, provider, repair, or retry implementations.
