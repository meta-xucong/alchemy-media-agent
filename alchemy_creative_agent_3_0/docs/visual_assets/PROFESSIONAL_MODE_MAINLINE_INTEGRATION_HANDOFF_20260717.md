# Professional Mode Mainline Integration Handoff

## Purpose

This record closes the backend integration seam for the first Professional
Mode release. It does not enable the browser experience, claim real-pixel
quality, or open a production gate.

Professional Mode is an explicit request mode. It is not inferred from
keywords and it never falls back to Standard or General when its identity
asset is unavailable.

## Mainline flow

```text
explicit professional_mode + project-scoped People Asset
  -> server-owned active asset and anchor-pack binding
  -> typed reference-channel admission
  -> Remote Central Brain receives safe People Asset evidence
  -> shared CapabilityActivationPlan and frozen execution envelope
  -> canonical prompt/reference binding
  -> shared Provider / review / bounded retry / final delivery
```

The Professional Mode layer owns asset lifecycle, view evidence, version,
activation, and admission. It does not write creative prompt prose, choose a
Provider, run review or retry, or store a second candidate/delivery history.

## Public backend contract

The Product API accepts:

- `professional_mode`: `standard` or explicit `professional`;
- `people_asset_id`: a project-scoped active People Asset for Professional
  Mode;
- optional `professional_identity_view_ids`, validated against the active
  anchor pack.

Standard requests reject Professional-only fields. Professional requests with
no active asset, invalid views, unsafe reference admission, unavailable
enforced planning, or evidence mismatch return a structured blocked result.
They do not create a Standard/General substitute job.

The service resolves asset state from the server catalog. Client-supplied
binding records, local paths, raw prompt fragments, Provider identifiers, and
review instructions are not accepted as authority.

## Evidence and identity continuity

The runtime uses one stable job identity across the asset binding, Brain task
profile, frozen activation plan, canonical prompt receipts, and downstream
provenance. The Remote Brain receives safe People Asset binding/admission
evidence, while private server records remain outside its request payload.

Each materialization operation preserves the typed reference evidence and
canonical prompt hash. The shared runtime validates exact, ordered, Brain-signed
receipts before Provider execution. Provider, review, retry, and final delivery
therefore consume the same frozen evidence rather than reconstructing a second
Professional Mode interpretation.

## Isolation guarantees

- Standard and ordinary General requests contain no Professional Mode metadata
  or People Asset lookup.
- E-Commerce and Photography retain their own explicit template ownership and
  do not receive People Asset behavior implicitly.
- Professional Mode cannot invoke a local Provider, private Brain, private
  reviewer, private retry loop, or private delivery store.
- No frontend route was added by this backend integration; the browser remains
  closed for this mode until a separate UX and M5 acceptance is approved.

## Verification completed

- Professional Mode focused and mainline seam tests: 64 passed.
- Affected runtime/activation/Project Mode/Doc102 checkpoint tests: 80 passed.
- Short-checkout full V3 regression baseline: 861 passed before the final
  integration rerun; the final integrated run is required before merge.
- `compileall`, frontend `node --check`, and `git diff --check` are required
  merge gates.

These are code-contract results only. No real Provider request, real image,
M5 identity-quality result, Gate C/D result, or production certification is
claimed here.

## Next owner: Professional Mode anchor-pack session

The feature session may now rebase its remaining work onto the merged mainline
commit and continue only with M5 planning/evidence. It must not re-create the
backend seam or introduce a second generation architecture.

