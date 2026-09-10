# V3 Remote Brain Stage Budget and Finalizer Handoff Integrity

Status: implementation in progress; this document records the correction
model for the residual timeout defect found during Doc295 real-image
validation.

## 1. Scope

This is V3 foundation transport/runtime work. It covers the shared remote
Brain execution budget used by General Template and professional templates
before any renderer/provider operation. It does not change prompt ownership,
visual quality thresholds, template deliverable maps, or the selected Brain
model/provider.

The triggering validation was the same original adult-woman supermarket and
beverage-aisle direction used by Doc295. The corrected source projection and
typed capability routing reached the remote Brain, but the run stopped before
image generation with:

- `llm_used=true` and `fallback_used=false`;
- `remote_brain_stage=provider_prompt_finalize`;
- a `read_timeout` after only `65.379` seconds remained;
- the shared `520` second logical budget reported `exhausted`;
- no image Provider request was started.

This evidence means the upstream Brain route was reached and the fail-closed
boundary worked, but the local stage-budget guard did not preserve its own
declared finalizer handoff window.

## 2. Theory-first correction model

### Intended behavior

For an enforced real-image request:

1. Brain planning may use only the planning portion of the shared logical
   budget.
2. Streaming progress grace may extend a planning transport only inside that
   planning portion.
3. A fixed handoff reserve remains available for the canonical finalizer.
4. The canonical finalizer must complete before any image Provider request is
   permitted.
5. If the budget or finalizer fails, the job blocks with safe lifecycle facts;
   it must not invent a local prompt, silently shorten the user direction, or
   start a partial generation.

### Observed mismatch and owning layer

| Mismatch | Owner | Cause |
| --- | --- | --- |
| Planning could consume the finalizer reserve while tokens were still arriving | shared Brain provider transport | `_effective_timeout_seconds()` subtracted the reserve from the hard timeout, but `_call_with_timeout()` used the full logical deadline as its progress-grace ceiling |
| Finalizer received only the residual 65-second window | shared Brain budget boundary | repeated semantic progress could keep extending the planning worker up to the full execution deadline |
| No image was emitted | Product API / provider gate | correct fail-closed behavior; this is evidence to preserve, not a defect to bypass |

The upstream Aiself/Brain endpoint remains an external dependency. Its slow
response is allowed to cause a bounded block, but it must not defeat the local
handoff invariant.

### Authority decisions

- The shared logical deadline remains the transport authority.
- The stage-aware planning ceiling is the authority for progress grace when a
  finalizer reserve applies.
- The remote Brain remains the only semantic author of renderer prompts.
- The existing one-shot recovery policy remains bounded by the same budget.
- No retry, prompt truncation, threshold relaxation, or local creative
  fallback is added to make a real run appear successful.

## 3. Minimal complete repair

1. Compute the planning hard timeout and its absolute stage ceiling from the
   same budget snapshot.
2. Pass that ceiling into the outer transport deadline guard.
3. Keep the full logical deadline as the ceiling only for stages without a
   reserved downstream handoff, including the canonical finalizer itself.
4. Add deterministic regression tests proving semantic progress cannot cross
   the reserved handoff and that existing no-reserve grace behavior remains
   intact.
5. Re-run the full Doc295 offline matrix, then repeat one guarded local
   real-image run with the exact original prompt and inspect the prompt
   receipts, module activation, provider request boundary, and pixels.

## 4. Non-goals and safety boundaries

- no change to Aiself credentials, endpoint, model, or reasoning policy;
- no local prompt author or keyword-based prompt acceptance;
- no reduction of Brain output requirements or visual review thresholds;
- no bypass of canonical prompt sign-off;
- no deletion or cleanup of prior validation evidence;
- no deployment until the candidate SHA passes offline audit and controlled
  real-image validation.

## 5. Acceptance evidence

The final record must include the changed files, independent read-only audit,
focused and broader test results, exact prompt hash and length, local real
run outcome, finalizer/provider boundary facts, visual inspection, commit SHA,
GitHub push verification, and governed VPS release/health verification.

The implementation must preserve General Template neutrality and the Doc295
typed-product-fact boundary while repairing only the shared Brain transport
budget.
