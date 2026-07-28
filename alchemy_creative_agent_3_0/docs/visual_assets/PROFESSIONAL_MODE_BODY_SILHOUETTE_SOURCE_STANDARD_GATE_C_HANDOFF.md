# Professional Mode Body Silhouette Source Standard Gate C Handoff

Status: **GATE_C_THEORY_FIRST_IMPLEMENTATION_HANDOFF_UNDER_REVIEW**

This handoff is append-only documentation for the Gate C code/design branch.
It records the intended owning-layer correction before any controlled
modeling-card refresh. It does not authorize real Body Silhouette generation,
planning-only, Host/MCP/ImageGen, formal slot activation, or business writes.

## 1. Intended behavior

Professional Character Card Body Silhouette should keep the existing Doc178
three-slot lifecycle:

```text
body.front_full
body.side_full
body.rear_full
```

Each slot still uses:

```text
three candidates → shared review → formal slot receipt → winner_selected
→ explicit activation only after all required Body slots are reviewed
```

The upgraded source-standard review should make a Body Silhouette candidate
prove general body-chain evidence before it can become the formal slot winner.

The source standard must remain universal:

- no fixed child ratio;
- no six-year-old rule;
- no swimwear, poolside, kidswear, E-Commerce, Photography, or General recipe;
- no runtime grade or commercial certification.

## 2. Observed mismatch

Downstream Professional body-only projection is now working: active Body
Silhouette can reach General, Photography, and E-Commerce visible/full-body
outputs as a body-only reference.

The remaining visual issue is source quality. If the active Body Silhouette is
doll-like, has weak head-neck-shoulder continuity, or has simplified
torso/limb/stance structure, downstream outputs may still show head-body
mismatch or pasted-face/body artifacts.

The current Body Silhouette formal slot enhanced proof is too coarse. It
checks source class, face reference scope, generic shared review pass, and
`body_silhouette_profile_eligible`, but it does not require the Gate A source
standard dimensions to be present in shared review evidence.

## 3. Owning layer

The owning layer is:

```text
Professional Character Card Body Silhouette source-standard review contract
```

Supporting layers:

- shared Vision / Human Realism may expose general human-body review issue
  semantics;
- Character Card Body Silhouette owns using those semantics to decide slot
  winner eligibility;
- downstream body-only projection consumes only active reviewed Body
  Silhouette slots and remains unchanged.

Non-owning layers:

- Face Identity does not change;
- E-Commerce/Photography/General do not add body prompt workarounds;
- Provider cap and materialization are unchanged;
- formal slot core keeps standard three-candidate acceptance.

## 4. Minimal complete fix

The minimal complete fix is not a new generation pipeline. It is a stricter
review/receipt proof for the existing Body Silhouette stage:

1. Define closed, scene-neutral Body Silhouette source-standard dimensions:
   body-chain coherence, stage-aware proportion, head-neck-shoulder
   continuity, torso/limb/joint plausibility, stance/ground-contact, and
   cross-view parity readiness.
2. Surface those dimensions in the existing shared review contract for
   `body_silhouette` only.
3. Project those dimensions into the existing generic shared visual review
   receipt when shared review observes them.
4. Require the Body Silhouette formal slot enhanced proof to see all required
   dimensions and no source-standard blocking issue before a candidate is
   eligible.
5. Preserve source class as provenance only:
   `observed`, `user_described`, and `brain_inferred` do not certify quality.
6. Preserve historical compatibility:
   existing active slots stay readable; new stricter proof only applies to new
   Gate C candidate/winner formation.

## 5. Explicit non-fixes

This gate must not:

- append local prompt text such as "make the head smaller";
- hard-code an age, head-count ratio, or child-body recipe;
- create a `commercial` grade or certification field;
- change Body Silhouette slots;
- change activation semantics;
- regenerate any Body Silhouette candidate;
- modify downstream E-Commerce/Photography/General behavior;
- modify provider cap;
- read or write `.media_storage`, `.controlled-validation`, jobs, receipts,
  slots, activations, or business storage.

## 6. Deterministic test expectations

Gate C tests should prove:

- shared review contract exposes the Gate A dimensions only for Body
  Silhouette;
- Body formal slot receipt blocks when the source-standard dimensions are
  missing;
- Body formal slot receipt blocks when a source-standard issue is present;
- Body formal slot receipt records source class only as provenance evidence;
- Face Identity and Expression Set tests remain isolated;
- historical Body slots remain readable without auto-migration;
- activation still requires existing formal slot receipts and explicit user
  confirmation;
- no downstream body-only projection, provider cap, runtime grade, planning, or
  Host behavior changes.

## 7. Refresh gate remains separate

After code and deterministic tests pass, a later controlled modeling-card
refresh gate may be requested. That gate must still use existing append-only
candidate/winner/slot lifecycle and must preserve all historical active Body
Silhouette evidence until new candidates pass visual review and explicit
activation.
