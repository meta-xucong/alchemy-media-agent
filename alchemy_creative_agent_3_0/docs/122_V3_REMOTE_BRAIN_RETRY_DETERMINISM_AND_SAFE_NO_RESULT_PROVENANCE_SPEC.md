# Doc122 V3 Remote-Brain Retry Determinism and Safe No-Result Provenance

> **Doc135 refinement:** deterministic retry means deterministic evidence,
> binding and budget—not a deterministic local replacement prompt. The remote
> Brain alone converts accepted retry evidence into renderer language.

Status: corrective shared-foundation authority discovered during the controlled
Doc121 General reference acceptance. It applies to all V3 templates and does
not add a child, apparel, product, E-Commerce, Photography, or General prompt
branch.

## 0. Observed defect

A General real-image job successfully used a remote Central Brain and obtained
Provider pixels. Its bounded visual retry then ran a second remote Brain call
instead of reusing the already verified, server-pinned creative result. The
retry could therefore be blocked before it reached the Provider, while its
history reported only `retry_generation_returned_no_result`.

E-Commerce and Photography already froze their verified remote creative answer
for execution. Limiting that invariant to specialized templates made General
less deterministic and obscured whether a retry was stopped before a Provider
request.

## 1. Corrected invariant

1. Every server-owned Job that has a verified remote Brain result and frozen
   capability plan binds that result at planning time, independent of template.
2. Generation and every bounded visual retry reuse that exact verified result.
   Only the existing frozen, issue-scoped repair channel may change.
3. A retry whose Scenario Runtime result has no generation payload records a
   safe pre-Provider outcome: runtime state, a generic reason code, and the
   already-safe remote-Brain projection when present.
4. Such a record must not claim that a Provider request, vision review, retry
   pixel, or delivery exists. It must not retain raw prompt text, endpoint,
   credential, or upstream exception details.

## 2. Boundaries

- This preserves the original remote creative decision; it does not replace
  the Brain with a static local recipe or deterministic creative fallback.
- The Provider still receives one normal materialization request per bounded
  retry. Gateway retry ownership and shared review/retry limits do not change.
- The rule is subject- and scenario-neutral. It does not create clothing,
  child, hand, face, product, or layout-specific repair language.

## 3. Required regression

- A General job using a test remote Brain must issue the Brain call once during
  planning and reuse the bound answer during mock generation.
- A no-result retry must distinguish a pre-Provider remote-Brain/capability
  block from an unclassified no-result state using safe provenance only.

## 4. Acceptance consequence

The prior append-only acceptance attempt remains historical evidence: its
first Provider pixel and verified hybrid review are valid, but its retry
failure cannot be attributed beyond the old generic no-result record. A new
controlled acceptance run is required to prove the corrected General retry
uses the bound Brain result and reaches the existing shared Provider/review
path.
