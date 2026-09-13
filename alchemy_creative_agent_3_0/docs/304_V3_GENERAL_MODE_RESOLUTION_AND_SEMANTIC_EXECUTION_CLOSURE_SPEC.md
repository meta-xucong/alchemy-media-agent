# V3 General Mode Resolution and Semantic Execution Closure

Status: implementation plan and acceptance contract
Scope: V3 foundation/runtime for `general_template` multi-image generation
Baseline: `4b50c383f4af46ff9c58b06575e6e63f2c53b2e6`

## 1. Objective

The four General generation modes must remain effective from the current user
request through the frozen Runtime contract, Brain finalizer, Provider request,
output receipt, and public review. A stale project preference or a compatibility
alias must not silently change the selected mode. A completed canonical prompt
must also carry auditable evidence for the exact per-output variation semantics
that the frozen contract assigned.

This is foundation/runtime work. It does not add vertical deliverable maps to
General Template and does not change the Core candidate-to-slot acceptance path.

## 2. Observed defects

The code audit and the first controlled VPS selection run found four defects:

1. `variation_mode_override` can disagree with a stale
   `effective_variation_mode`; Project Mode prefers the override while Runtime,
   Brain, and some context projections prefer the stale effective value.
2. Alias canonicalization is duplicated. `creative_explore` and
   `similar_options` can reach downstream role directors as unknown values and
   fall back to `delivery_suite`.
3. General Project/Context role metadata and the active Doc59 role plan are
   separate projections. A generated output can therefore be labelled with a
   generic `template_deliverable_*` identity even though the active mode has a
   mode-specific role plan.
4. The Brain variation receipt proves contract digest and output index only. It
   does not prove that the finalizer acknowledged the exact semantic purpose and
   axes for that output. The selection review also contains an unreachable
   distance-risk predicate.

## 3. Authoritative correction model

For a fresh General request, mode resolution is deterministic and server-owned:

```text
explicit variation_mode_override
  > explicit non-auto variation_mode
  > explicit continuation_mode
  > explicit/inferred user mode
  > frozen variation_execution_mode (reuse only)
  > persisted effective/default
```

`effective_variation_mode` is a derived compatibility value. It cannot override
a current explicit choice. Once Runtime freezes a contract, its canonical mode
and digest are authoritative. If a new explicit override conflicts with a
reused contract, the request stops with a binding error; it must not continue
with a stale contract.

One shared Python resolver owns canonical values and aliases. All Python mode
consumers use it. The browser keeps the same canonical values and sends the
manual choice as `variation_mode_override` in the immutable job metadata; the
server remains the final authority.

## 4. Semantic execution closure

For an enforced General multi-image job:

- Runtime freezes the canonical mode binding and typed variation contract.
- The finalizer must return one exact semantic receipt per output. In addition
  to the existing contract digest/index binding, the receipt includes the
  contract output purpose and ordered neutral variation axes for that index.
- The provider and Product API continue to consume the Brain's complete prompt;
  no local prompt suffix is introduced. They may project the server-owned mode
  binding and role identity for audit/reconciliation only.
- Public review remains prompt-text-free, but it is approved only when the
  finalizer receipt set covers every requested output and matches the frozen
  contract. Missing or conflicting semantic evidence blocks approval.
- General role identity is projected from the active mode plan to the
  per-output deliverable binding. Historical Doc58 records remain readable and
  are never rewritten.

The semantic receipt is evidence, not a second creative author. It does not
permit internal role names or framework metadata to leak into renderer prompt
text.

## 5. Mode-specific acceptance

| Mode | Required visual contract | Minimum evidence |
|---|---|---|
| `selection_candidates` | Same direction/subject, micro distance, no scene change, small comparable axes | distinct purpose/axis receipts; no duplicate role binding; review predicate can flag collapse |
| `delivery_suite` | One coherent direction with different image duties | active Doc59 role plan bound per output; every role index covered |
| `creative_exploration` | Distinct concepts while preserving the requested subject | canonical mode and unique creative-direction receipts |
| `format_layout_adaptation` | Same idea with crop/layout/negative-space changes | canonical mode, per-output layout role, and no reliance on one copied job-level size as proof |

Real image acceptance must inspect the resulting pixels. Contract and receipt
tests are necessary but cannot be reported as visual quality proof.

## 6. Test and rollout gates

1. Add failing regression tests for stale effective mode versus explicit
   override, all compatibility aliases, contract reuse conflicts, selection
   review collapse, and semantic receipt mismatch.
2. Run focused unit/contract tests, then the bounded V3 mode regression set.
   The known slow mock-generation test is reported separately if it exceeds
   the bounded test budget; it is not silently counted as passed.
3. Run an independent read-only audit on the frozen diff.
4. Commit and push the verified mainline milestone.
5. Deploy the exact full commit to VPS and run one controlled real job for each
   of the four General modes using the previously approved safe comparison
   project. Preserve all job/output evidence append-only.
6. Download and inspect the final images. Report per-mode quality, provider/
   Brain status, any limitation (especially layout canvas constraints), and
   whether the user can begin acceptance.

## 7. Non-goals

- No prompt keyword patching to mask an authority or persistence defect.
- No new ecommerce, photography, or campaign deliverable map in General.
- No deletion or rewriting of historical VPS jobs, outputs, or evidence.
- No biometric persistence; visual identity metrics, if used by existing review,
  remain ephemeral and outside this repair.
