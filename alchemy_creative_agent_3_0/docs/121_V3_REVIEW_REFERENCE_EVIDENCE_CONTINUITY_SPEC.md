# Doc121 V3 Review Reference Evidence Continuity

Status: corrective shared-foundation authority discovered during the controlled
Doc118/Doc120 General reference acceptance. It does not create a child,
apparel, product, commerce, photography, or General-template-specific branch.

## 0. Observed defect

The V3 Provider materializer correctly admitted an uploaded reference and sent
it to the image-edit request.  Its candidate audit recorded that materialized
input.  The subsequent real-pixel reviewer, however, only received planning
metadata and not the exact admitted source asset.  It could therefore inspect
the generated pixels but could not certify whether reference-owned facts were
preserved.  A review that says no reference was supplied must not be used as a
reference-truth conclusion.

## 1. Corrected invariant

For every generated candidate that received Provider pixels from an admitted
reference operation:

1. Post-generation review receives the same V3-owned, job-scoped uploaded
   source asset(s) that the candidate's materialization audit identifies.
2. The reviewer receives no reference when its candidate has no admitted
   `pixels_received` reference operation, even if the Job later contains
   other uploads or project history.
3. Only exact root upload IDs from the Job request are eligible.  Derived
   identifiers are evidence links, not a permission to read an arbitrary
   local file.
4. The reference file path and materialization audit remain internal review
   evidence.  Public Job, history, candidate, and browser projections expose
   only their existing safe review/provider summaries.

## 2. Review-certification consequences

- A real `vision_model` or `hybrid` pass/warning can support reference truth
  only when the reviewer had the admitted reference evidence it needed.
- If source evidence is unavailable, the automated result is
  manual/non-certifying.  It must not claim exact
  identity/product/reference preservation or fabricate an equivalence pass.
- Review/retry remains bounded and append-only.  This change neither creates
  a second Provider request nor changes the frozen repair scope.

## 3. Boundaries

- This is a shared evidence-continuity rule for every reference-conditioned
  V3 path.  It has no subject, age, garment, product, or template-specific
  vocabulary.
- It does not reconstruct prompt text, copy static recipes, restore local
  OCR/font/overlay behavior, or change gateway routing.
- It does not grant review a broader source channel than the one admitted by
  the Provider materializer.

## 4. Required regression

The Product API regression must prove that a ready, job-owned asset is passed
to the reviewer only when its candidate audit says `admitted` plus
`pixels_received`, and that a different/unadmitted Job upload cannot enter
the reviewer metadata.  The public metadata redaction regression remains
required for the internal materialization audit.

## 5. Acceptance consequence

Earlier append-only outputs remain historical evidence.  They are not
retrospectively reclassified.  A controlled reinspection may use this fix to
evaluate their pixels with the previously admitted source reference; a new
image generation is justified only after that reinspection demonstrates that
the shared reviewer has the correct evidence continuity.
