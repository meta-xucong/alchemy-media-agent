# Professional Mode Body Silhouette Realism Diagnostic Note

Status: **DEFERRED_DESIGN_DIAGNOSTIC_NOTE_FOR_REVIEWER_GATE**

Owner boundary: Professional visual-assets documentation / future Doc178
follow-up research. This note is not a runtime contract.

Hard boundary for the current gate:

- do not modify Character Card generation;
- do not modify Body Silhouette slot definitions;
- do not modify Body Silhouette review, activation, or asset storage;
- do not introduce new runtime fields, receipt fields, grades, or downstream
  behavior;
- do not run planning-only, Host/MCP/ImageGen, or formal delivery writes.

This note records a diagnosis and a possible future direction only. It must be
reviewed before any document commit, and a later implementation gate would
require a separate reviewer approval.

## 1. Why this note exists

Recent Professional E-Commerce poolside validation showed that passing Face
Identity and passing the current Body Silhouette runtime projection are not
enough to guarantee a natural full-body commercial human result.

The visible issue was not primarily that the face identity was missing. The
face was recognizable, and Body Silhouette evidence was correctly projected
into Professional E-Commerce, Photography, and General visible/full-body
planning paths. The remaining issue was that the generated full-body result
could still feel like a correct face attached to a less convincing body.

User-provided real child model references made the mismatch clearer:

- real child bodies can have a relatively large child head while still feeling
  natural because the neck, shoulders, torso, limbs, stance, and camera relation
  form one coherent body chain;
- the current active Body Silhouette front view is usable as a clean model-card
  body reference, but it trends more doll-like / younger / rounder than the
  real commercial child-model examples;
- the downstream swimwear result inherited body evidence correctly, but the
  source body evidence itself was not strong enough to visually certify
  high-realism commercial body proportion.

This note therefore identifies a future research target: stronger body-realism
evaluation for Body Silhouette evidence. It does **not** authorize changing the
current Body Silhouette production lifecycle.

## 2. Current standard and why it exists

Doc178 currently defines Body Silhouette as an independent Character Card
module with three slots:

```text
body.front_full
body.side_full
body.rear_full
```

Its current purpose is sound:

1. provide clean full-body front/side/rear references;
2. keep the person tied to the approved Face Identity;
3. preserve age/presentation continuity;
4. avoid inheriting wardrobe, lighting, background, camera, expression, or
   scene into later deliverables;
5. use neutral model-card clothing and white background so body evidence is
   reusable across modules;
6. retain three-candidate bounded generation and shared review before formal
   slot activation.

The current source classes are also correct:

```text
observed        # user supplied full-body evidence
user_described  # user supplied explicit body constraints
brain_inferred  # no body evidence; Brain inferred body from face/age/intent
```

The current system is useful as a first-generation model-card workflow. The
diagnostic concern is narrower: the current pass state should not be overread
as proof that every visible/full-body commercial scene will have strong
real-world body proportion fidelity.

## 3. Existing runtime projection remains authoritative

The already-approved Professional runtime body-only projection remains the
current runtime authority:

- Professional visible/full-body outputs may consume active Body Silhouette as
  body-only evidence;
- face-only/local detail/non-human outputs do not require Body Silhouette;
- Body Silhouette must not be projected as face, product, wardrobe, pose,
  lighting, camera, background, expression, or scene truth;
- downstream E-Commerce, Photography, and General must not add scenario-specific
  body workarounds.

This note does not change that runtime projection and does not add a new
downstream gate.

## 4. Keep Face Identity stable

Face Identity should not be broadly changed by this diagnosis.

Face Identity owns:

- same-person facial geometry;
- facial feature relationships;
- face view coverage;
- hair/face continuity to the degree already allowed by existing contracts;
- face-level age direction.

The observed defect is not that Face Identity failed to identify the person.
The concern is whether the body evidence visually carries the already-approved
face in full-body contexts. Changing Face Identity would risk destabilizing a
layer that is already doing its job.

## 5. Body evidence observation dimensions

If a future reviewer-approved Body Silhouette research phase is opened, it
should evaluate scene-neutral body evidence dimensions. These are observation
dimensions, not current runtime fields and not current Body Silhouette review
requirements.

### 5.1 Developmental body proportion coherence

The body should be coherent with the current person stage and face age
direction.

This should not become a fixed head-count rule. It is a stage-aware visual
judgment:

- head size relative to body should not feel oversized or shrunken;
- shoulders should plausibly match the head, neck, torso, and age stage;
- torso length and width should not feel compressed, inflated, or cylindrical;
- arms and legs should have plausible length and mass for the person stage;
- the result should avoid doll-like, mannequin-like, over-stylized, or
  prematurely adultized proportions.

### 5.2 Head-neck-shoulder continuity

The body evidence should show that the face can naturally sit on the body.

Future review research may inspect:

- visible or structurally clear neck support;
- natural shoulder slope and shoulder width;
- no compressed neck;
- no head floating above or pressing into shoulders;
- no hair or clothing shape that hides all important neck/shoulder evidence;
- side/rear views confirming the same head-neck-shoulder relationship.

This is a Body evidence observation. It must not authorize Body Silhouette to
change Face Identity.

### 5.3 Torso-limb skeletal plausibility

The body should show plausible human structure, not only a clean silhouette.

Future review research may inspect:

- chest/ribcage/waist proportion appropriate to the person stage;
- upper/lower leg proportion;
- upper/lower arm proportion;
- knee, ankle, elbow, wrist, hand, and foot plausibility;
- no rubbery, over-smoothed, plastic, or inflated limb structure;
- no major left/right asymmetry unless pose-owned and plausible.

### 5.4 Stance, ground contact, and body chain

Even a neutral model-card body should have believable physical weight.

Future review research may inspect:

- feet contact the ground believably;
- centerline and weight distribution are plausible;
- head, shoulders, pelvis, knees, and feet form one coherent body chain;
- full-body posture is not overly stiff, collapsed, or card-like in a way that
  would make later dynamic scenes brittle.

### 5.5 Cross-view parity

The three Body Silhouette views should describe the same body:

- front view: overall proportion, shoulder width, torso width, limb length;
- side view: neck projection, chest/back thickness, pelvis/leg relation,
  posture and body depth;
- rear view: rear neck, shoulders/back, hair-body separation, leg proportion,
  and stance continuity.

This is a future visual-review research direction. It is not a current slot
activation rule.

## 6. Future grade discussion is non-runtime only

A future research phase may consider whether Body Silhouette evidence should
have human-readable quality labels such as:

```text
basic
realistic
commercial
```

For the current gate, these names are only discussion labels. They are not
approved field names, not receipt fields, not activation states, and not
downstream runtime authority.

This note must not introduce:

- `body_silhouette_grade`;
- `commercial_body_certified`;
- any new persisted certification field;
- any automatic reinterpretation of historical assets.

Historical Body Silhouette assets remain readable exactly under their existing
contracts. Any future grade system would need its own owner, lifecycle, receipt,
activation, migration, and isolation tests before implementation.

## 7. Source class must not become certification authority

The source class records evidence provenance. It must not by itself certify
commercial body quality.

### observed

User supplied full-body evidence. This can provide stronger raw evidence, but
it still requires visual review. Observed source does not automatically mean
commercial body quality.

### user_described

User supplied explicit build/proportion constraints. This provides directional
constraints only. It cannot by itself support stronger certification than the
reviewed visual evidence.

### brain_inferred

No full-body evidence exists. Brain inferred the body from face identity,
developmental stage, and intent.

This remains useful, but it is not equivalent to observed full-body evidence.
Commercial usefulness, if ever introduced as a future concept, must be decided
by independent visual review evidence, not by source class alone.

## 8. Relationship to shared Human Realism

Shared Human Realism may own general issue/review semantics such as:

- head-body scale mismatch;
- compressed neck/shoulders;
- head-neck-shoulder discontinuity;
- doll-like or mannequin-like human body;
- limb/joint plausibility issues.

These must remain scene-neutral shared review semantics. They must not become
six-year-old, swimwear, kidswear, poolside, E-Commerce, or Photography-specific
recipes.

Body Silhouette may be observed through those general issue semantics in a
future review phase, but this document does not move pixel gates, retry
authority, or scene recipes into Body Silhouette.

## 9. Downstream usage policy stays unchanged

Downstream Professional modules should not add scenario-specific workarounds for
this defect.

Current policy remains:

- E-Commerce consumes product truth and body-only evidence where applicable;
- Photography consumes body-only evidence where applicable;
- General Professional consumes body-only evidence where applicable;
- Standard and non-Professional General do not read Professional Body
  Silhouette;
- no module may use Body Silhouette as face, wardrobe, pose, lighting, camera,
  background, expression, scene, or product truth.

Any future strict high-realism body mode would need a separate approved runtime
contract. This note does not add one.

## 10. Backward compatibility

No backward compatibility change is proposed in this gate.

Existing Body Silhouette assets:

- keep their current state;
- keep their current source class;
- keep their current review receipts;
- keep their current activation status;
- remain readable by the already-approved body-only runtime projection.

This note must not mark historical active body slots as failed, uncertified, or
commercial/non-commercial in runtime data. It only records that the current
evidence should not be verbally overclaimed beyond its existing review scope.

## 11. Deferred research stages

These stages are future candidates only. They are not approved for the current
turn.

### Deferred Stage A — document closure

- reviewer decides whether this diagnostic note may be committed;
- reviewer decides whether older wording needs a future narrowed/superseded
  note;
- no code or runtime behavior changes.

### Deferred Stage B — review contract design

Only after separate approval:

- define whether general Human Realism issue codes are sufficient;
- decide whether any Body Silhouette-specific review receipt is necessary;
- define owner, lifecycle, migration, and isolation boundaries.

### Deferred Stage C — deterministic tests

Only after separate approval:

- Face Identity remains unaffected;
- no swimwear/kidswear/poolside-specific prompt fragments;
- source class does not certify quality alone;
- body evidence observation dimensions remain scene-neutral;
- current runtime body-only projection continues to work.

### Deferred Stage D — controlled visual acceptance

Only after document, code, deterministic tests, and planning-only gates:

- compare Body Silhouette front/side/rear against approved general body
  observation criteria;
- compare downstream E-Commerce/Photography/General visible-body outputs against
  body continuity;
- do not claim formal delivery completion until visual review passes.

## 12. Non-goals

This note does not:

- change Face Identity standards;
- change Character Card generation;
- change Body Silhouette generation prompts;
- change Body Silhouette slots;
- change Body Silhouette review or activation;
- change existing Body Silhouette assets;
- add runtime grade fields;
- add downstream strict mode;
- change E-Commerce product truth selection;
- change provider cap;
- add child/swimwear/poolside rules to shared Human Realism;
- add local prompt patches to downstream modules;
- authorize planning-only, Host/MCP/ImageGen, formal receipts, slots, or
  activations.

## 13. Reviewer questions

Reviewer should decide:

1. Is this diagnostic note correctly downgraded from implementation design to
   future research / document-only observation?
2. Is the owning diagnosis acceptable: Face Identity remains stable, current
   body-only runtime projection remains valid, and future work belongs to a
   Body Silhouette / shared review documentation gate?
3. Are the proposed observation dimensions scene-neutral enough to avoid a
   six-year-old, swimwear, kidswear, or E-Commerce-specific standard?
4. Should the grade discussion remain in this note as non-runtime vocabulary,
   or be removed entirely until an owner/lifecycle exists?
5. Which document family should own any future follow-up: Doc178 follow-up in
   `docs/visual_assets`, or a shared Human Realism issue-code document?
6. Is this document now safe to commit as a deferred diagnostic note, or should
   it be revised again before commit?

## 14. Current conclusion

The current Body Silhouette standard was reasonable as a clean first-generation
model-card body workflow. The recent poolside case shows that downstream
visible/full-body Professional results may still expose body-realism limits when
the active Body Silhouette is `brain_inferred` and visually more doll-like than
real commercial human references.

The immediate correction is **not** to patch E-Commerce prompts or alter Face
Identity. The immediate action is only to record this as a deferred Body
Silhouette / shared-review design concern and ask reviewer whether a future
document gate should be opened.

Until a separate reviewer approval exists, no Character Card, Body Silhouette,
runtime, review, activation, or downstream behavior may change because of this
note.
