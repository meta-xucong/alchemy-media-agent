# Doc261 - V3 Project Reference Authority And Continuation UX Contract

## 1. Scope And Ownership

This is a shared V3 project-workspace UX correction. It improves how existing
project evidence is explained and displayed. It does not change provider
inputs, prompt ownership, image generation, review, retry, delivery, or
project persistence authority.

The shared runtime remains authoritative for reference admission and channel
policy. This document only requires the public workspace to preserve those
already-persisted distinctions instead of flattening them into one generic
"reference" gallery.

## 2. Correction Model

The old workspace presentation placed active uploaded references and selected
generated outputs in one "confirmed reference" board. That is misleading:

- an uploaded product image is source truth for product appearance;
- a bound visual asset is a separate identity authority;
- a generated image is a user-selected continuation anchor, not source truth.

A selected generated output must never appear to replace, compete with, or
become indistinguishable from an uploaded input image.

## 3. Public Information Architecture

Every project workspace presents these concepts separately:

1. **Visual assets in this project**
   - Existing explicit project bindings remain in their dedicated panel.
   - They represent the selected reusable asset version, not project uploads
     and not generated-output continuation.

2. **Original input references**
   - Only active project references with `source_type=uploaded`.
   - Each card shows the existing public label and use-policy purpose.
   - They are described as generation evidence, such as product appearance,
     composition, lighting, or identity, rather than as a generated result.
   - Removing one means "stop using as generation evidence"; it does not
     delete the upload or a historical output.

3. **Selected continuation directions**
   - Only active project references with `source_type=generated_selected`,
     plus legacy selected-output records that do not yet have a persisted
     generated reference.
   - A card states that it came from a project result and only carries the
     continuation channels admitted by existing reference policy.
   - It cannot override uploaded source truth or a bound visual asset.
   - Removing one means "stop continuing from this result".

4. **Project outputs and review records**
   - Formal delivery outputs remain in the project-output gallery.
   - A user may explicitly promote a formal result to a continuation direction.
   - Review-only, rejected, or withheld images stay out of both input and
     continuation groups.
   - Workflow history remains in the collapsed project records area; it is not
     a reference-input gallery.

## 4. Required Desktop And Mobile Behavior

Desktop and mobile must use the same source classification:

```text
uploaded -> original input references
generated_selected -> selected continuation directions
legacy selected output without generated reference -> selected continuation directions
review-only/rejected/inactive -> not a current reference
```

The UI must visibly label the two groups. It must not use one ambiguous board
or one aggregate count that makes a product source image and a generated
continuation image appear equivalent.

Compact project summaries, compose cards, review steps, selection steps, and
continuation steps follow the same distinction. A count of uploaded source
truth must not be presented as a count of selected continuation directions.
For an older project that still contains duplicate active product references,
the public workspace also shows one original-input card per
`content_sha256` while the server repairs the durable project record.

The promotion action on an output is named "set as continuation direction".
It is an explicit user decision. It does not mutate original-input evidence,
visual-asset bindings, or review authority.

## 5. Compatibility And Safety

- Existing `ProjectReferenceAsset.source_type` and `OutputRef` records remain
  the source of public grouping truth.
- Legacy selected-output records are projected only when no equivalent active
  generated reference exists.
- This correction adds no client-owned authority. The browser cannot claim a
  source type, reference policy, or provider admission that the server did not
  persist.
- The public UI continues to exclude private paths, hashes, prompt text,
  provider payloads, and review internals.

## 6. Acceptance Criteria

1. An uploaded swimwear product image appears only under original input
   references, with its product purpose visible.
2. A bound people visual asset remains in the dedicated visual-assets panel.
3. A selected generated image appears only under selected continuation
   directions and is clearly marked as a project result.
4. A project result can be promoted or removed without deleting or relabeling
   the uploaded product source.
5. Review-only images cannot become continuation directions.
6. Desktop and mobile source grouping regressions pass without changes to
   generation, provider, review, or persistence contracts.
