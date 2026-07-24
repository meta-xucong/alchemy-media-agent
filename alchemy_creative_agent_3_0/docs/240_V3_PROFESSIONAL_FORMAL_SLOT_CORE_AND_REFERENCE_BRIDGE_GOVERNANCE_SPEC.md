# Doc240: V3 Professional Formal Slot Core and Reference Bridge Governance

## Status and authority

This document supersedes any older Character Card wording that lets a formal
Professional slot be completed by first-pass success, boolean review flags, or
hard-coded candidate counts.

It is a governance and contract document only.  It does not authorize runtime
changes, Provider/MCP generation, slot writes, receipt migration, or activation.

The immediate purpose is to close the architecture contract before Task 2+ work:
Face Identity, Expression Set, and Body Silhouette must share one formal slot
acceptance skeleton, while 25-35 degree bridge images remain auxiliary reference
evidence.

## Product baseline

Professional Character Card work has three different concepts that must not be
mixed:

1. Formal slots: outputs that may become official Character Card / visual asset
   slots and later participate in activation or project binding.
2. Auxiliary bridge references: intermediate images used only to help later
   formal views, especially 25-35 degree left/right bridge images for 45 degree
   views.
3. Historical compatibility collections: already generated official outputs
   that may be safely collected for readback, but cannot claim the standard
   three-candidate flow.

The formal product flow remains:

```text
candidate 1 -> shared review
candidate 2 -> shared review
candidate 3 -> shared review
winner selection -> slot receipt -> reload/readback -> safe public projection
```

Every formal slot must prove this flow with real reviewed attempts.  A field such
as `candidate_attempt_count=3` or `review_verified=True` is not proof.

## Layer model

### Core

Core owns the formal acceptance skeleton:

```text
CandidateRun(s)
-> generic shared Vision / identity / framing / parity review
-> winner selection
-> formal slot receipt
-> durable reload/readback
-> safe public projection
```

Core is shared by formal Face Identity, Expression Set, and Body Silhouette
slots.  It must not know MCP handoff mechanics, retry storage internals, or
emotion/view-specific scoring recipes.

Core facts required for a formal receipt:

- module and slot/view identity;
- acceptance mode;
- true reviewed candidate count from actual attempts;
- candidate IDs and output IDs for the reviewed set and final winner;
- winner selection owner and result;
- generic shared Vision status and safe public dimensions;
- prompt/reference parity;
- framing/identity evidence required by the slot family;
- retry/repair budget and actual bounded repair count;
- reload/public projection proof without prompt, path, raw Provider response, or
  private MCP artifact fields.

### Enhanced profile

Enhanced profiles define the slot-specific quality meaning while reusing Core:

- Face Identity view profiles: front, 45 degree left/right, profile, rear/head
  geometry, direction, occlusion, and rear-head profile rules.
- Expression profiles: laugh, anger, sad, and explicit smile affect evidence.
- Body profiles: front/side/rear full-body silhouette and source-class evidence.

Enhanced profiles may fail a candidate before winner selection, but they may not
implement their own candidate loop, winner selection, receipt projection,
lifecycle, activation, or public projection.

### Auxiliary

Auxiliary owns reliability, compatibility, and supporting references:

- MCP handoff, operation IDs, checkpoint recovery, CAS/locking, exact lookup, and
  stale-handoff protection;
- historical/legacy readback compatibility;
- target-only existing-output collection;
- 25-35 degree bridge/reference images used as evidence for later formal views.

Auxiliary must protect Core identity and replay safety, but it must not create a
replacement formal run, lower formal candidate count, relabel historical output
as standard, or let an intermediate bridge satisfy activation.

## Acceptance modes

### `standard_three_candidate`

This is the only formal completion mode for Professional slots.

Applies to:

- Face Identity formal slots such as `face.front`, 45 degree left/right,
  profile, and rear/head formal views;
- Expression Set formal slots such as `expression.laugh`, `expression.anger`,
  `expression.sad`, and explicit `expression.smile` when requested as a formal
  output;
- Body Silhouette formal slots.

Requirements:

- exactly three real candidate attempts for the same module/slot/round;
- each candidate has shared review evidence;
- rejected candidates remain append-only;
- winner is selected by the shared Core selection policy plus the relevant
  Enhanced profile;
- `reviewed_candidate_count` comes from the real attempt list, not a constant;
- receipt persists, reloads, and projects publicly as formal standard evidence.

Formal mode must not stop at the first passing candidate.

### `target_only_existing_candidate_collection`

This mode is for controlled collection of an already generated official output.

It may be used only when the target output/candidate/job/handoff/result identity
is unique and already exists.  It must not create a job, candidate, handoff, or
output.

It cannot:

- satisfy `standard_three_candidate`;
- activate a module;
- be relabeled as formal three-candidate completion;
- be mixed into a new formal candidate count.

### `auxiliary_first_pass_reference`

This mode is for bridge/reference artifacts, especially left/right 25-35 degree
transition images used to help later 45 degree formal slots.

Allowed behavior:

- may stop at the first passing bridge candidate;
- may persist as append-only auxiliary evidence;
- may be referenced by a later formal slot as view/identity/framing evidence.

Forbidden behavior:

- cannot become a formal `face.*` slot;
- cannot enter the official active material library as a formal view;
- cannot satisfy activation;
- cannot satisfy `standard_three_candidate`;
- cannot let a 45 degree formal slot bypass its own three-candidate review.

## Reuse relationship

```text
                       +------------------------------+
                       | Formal Slot Acceptance Core  |
                       | candidate x3 -> review       |
                       | winner -> receipt -> reload  |
                       +---------------+--------------+
                                       |
          +----------------------------+----------------------------+
          |                            |                            |
  Face Identity profile        Expression profile           Body profile
  view geometry/direction      affect evidence              silhouette/source
          |                            |                            |
          +----------------------------+----------------------------+
                                       |
                       Safe public projection / activation policy

Auxiliary adapters sit outside this Core:
MCP recovery, target-only collection, legacy readback, 25-35 bridge references.
```

## Current migration points

These are known implementation areas to inspect in Task 2+; this document does
not change them.

1. `SlotAcceptanceCore`
   - Keep as the formal candidate/review/winner decision surface.
   - Remove slot-specific lifecycle or quality code from Core; inject Enhanced
     profile gates.

2. `AnchorPackPreparationService`
   - Formal Face Identity MCP paths currently stop at first MCP pass.
   - Formal views must use standard three-candidate mode.
   - 25-35 degree bridge outputs need an explicit auxiliary mode separate from
     formal Face slots.

3. `AnchorView` and `IdentityAnchorPackVersion`
   - Need formal shared receipt fields or a canonical linked receipt model.
   - Must not rely on `review_verified=True` or `candidate_attempt_count=3` as
     formal proof.

4. `apply_face_identity_pack_to_card`
   - Must project real formal receipts to Character Card face slots.
   - Must not turn auxiliary bridge views into formal active slots.

5. `project_character_card_slot_success_receipt`
   - Should become/consume the shared formal receipt projection for Face,
     Expression, and Body, not just Expression/Body.
   - Must reject target-only and auxiliary modes for module activation.

6. `expression_review` helpers
   - Expression affect evidence belongs to Enhanced.
   - Shared framing/parity/generic Vision receipt checks used by all formal
     slots should move to a module-neutral Core receipt layer.

7. Product API / MCP bridge
   - Operation, handoff, checkpoint, and stale-handoff logic remain Auxiliary.
   - Auxiliary recovery must never advance the formal candidate index, create a
     replacement run, or lower the formal candidate requirement.

## Test matrix required before real validation

Task 2+ must add deterministic tests before any real Provider/MCP generation:

- Face roles x acceptance modes:
  - legal formal three-candidate receipt passes;
  - fewer than three reviewed attempts fails;
  - target-only fails formal activation;
  - auxiliary bridge fails formal activation;
  - 25-35 bridge can be referenced by 45 degree but cannot satisfy 45 degree.
- Expression slots x acceptance modes:
  - laugh/anger/sad/smile share Core receipt rules;
  - emotion evidence stays in Enhanced profiles;
  - target-only remains visible as non-standard.
- Body slots x acceptance modes:
  - formal three-candidate receipt required for activation;
  - missing parity/framing/generic review fails closed.
- Projection/reload:
  - winner/output/slot/module identities survive catalog reload;
  - public projection exposes only safe receipt summaries;
  - legacy/unclassified receipts remain non-standard.

## Non-goals

This document does not:

- run MCP or Provider;
- migrate existing evidence;
- rewrite old receipts;
- activate or deactivate any module;
- delete historical handoffs, jobs, outputs, or pack versions;
- decide whether current historical images are visually good enough.

Real validation may resume only after this governance contract is reviewed and
the follow-up implementation tasks are explicitly authorized.
