# Doc302 - V3 Background Generation Typed Continuation Repair

## Status

Implemented on the V3 mainline. This document records the correction model
for the VPS failure observed on 2026-09-13 and the acceptance boundary for the
follow-up real-image run.

## Observed mismatch

The project planning Job was created and persisted correctly, but its
background worker failed before Brain or the image provider was called. The
worker copied its internal claim fields and the persisted `require_real_images`
intent into the public-shaped Generate metadata. The tightened public Generate
guard correctly rejected those fields as server-owned, so a legal internal
continuation was misclassified as an invalid browser request and the Job ended
blocked without pixels.

## Authority and correction

The Job record remains authoritative for real-image intent and the project
context. Public Generate accepts product-level options only. The in-process
worker now:

1. validates and strips the persisted real-render markers from the
   browser-shaped follow-up payload;
2. carries the bounded auto-retry opt-out only in a typed
   `GenerateContinuation`;
3. binds the continuation to the exact Job and generated background attempt;
4. calls the existing project/Product service continuation seam; and
5. keeps the public Generate guard active, including rejection of forged
   markers, review controls, and retry controls.

Invalid worker payloads are rejected before the worker claims the Job. Existing
failed Jobs and their evidence remain append-only; retry acceptance must create
a new Job through the same project flow.

## Acceptance

- Unit/regression tests prove the public boundary still rejects runtime
  metadata and the worker receives a clean product payload plus a bound typed
  continuation.
- Compile and focused V3 tests must pass before release.
- VPS acceptance requires a new real-image Job from the preserved project,
  evidence of Brain/provider entry, and a delivered output; the original
  blocked Job is not reused or overwritten.
