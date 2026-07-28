# Professional Mode Body Silhouette Source Standard Upgrade Gate Plan

Status: **DOCUMENT_ONLY_REVIEWER_GATE_REQUEST**

This document is a proposed next gate after the accepted downstream
body-only projection work. It does not change runtime behavior, Character Card
generation, Body Silhouette slots, review, activation, storage, provider
materialization, prompts, planning, Host/MCP/ImageGen, or formal delivery
records.

## 1. Problem statement

Recent Professional poolside output review showed a useful but incomplete
improvement:

- the downstream Professional runtime now correctly projects active Body
  Silhouette evidence as a body-only reference for visible/full-body outputs;
- generated outputs improved in pose stability, body continuity, and reduced
  pasted-face/body artifacts;
- however, the remaining mismatch against real commercial model references is
  now dominated by the quality of the active Body Silhouette source itself.

The key distinction is:

```text
Fixed downstream pipe:
  active Body Silhouette now reaches Professional visible/full-body outputs.

Still unresolved source quality:
  the active Body Silhouette may itself encode a doll-like, rounded,
  shortened, or overly card-like body proportion.
```

If the source body evidence is not realistic enough, downstream E-Commerce,
Photography, and General Professional outputs can only inherit a cleaner
version of that same limitation. The next gate should therefore evaluate the
Body Silhouette source standard rather than adding more E-Commerce prompt
workarounds.

## 2. Current conclusion from visual comparison

The user-provided real model references indicate that the current active Body
Silhouette can be materially different from real photographed human proportions:

- real children may still have relatively large heads, but the neck, shoulders,
  torso, limbs, stance, and camera relationship form a single coherent body
  chain;
- the current Body Silhouette front view is clean and useful as a model-card
  reference, but it trends more simplified, rounded, and character-card-like
  than the real commercial references;
- the most visible remaining defects are not face identity defects. They are
  body source realism defects: head-body scale, head-neck-shoulder transition,
  torso/limb proportion, leg length/mass, stance, and cross-view body parity.

This does not mean the existing Body Silhouette asset is invalid under its
current contract. It means the current contract is too weak to support a claim
of high-realism commercial full-body body-proportion certification.

## 3. Scope boundary

### In scope for the next document/design gate

- Define a universal Body Silhouette source-standard upgrade proposal.
- Keep the standard scene-neutral and person-stage-aware.
- Preserve Face Identity standards unless a separate face-specific defect is
  proven.
- Focus on Body Silhouette `body.front_full`, `body.side_full`, and
  `body.rear_full`.
- Define future review dimensions and acceptance evidence needed before any
  production behavior changes.

### Out of scope for this gate

- No runtime implementation.
- No prompt patch.
- No provider cap change.
- No downstream E-Commerce, Photography, or General special recipe.
- No kidswear, swimwear, poolside, or six-year-old-specific rule.
- No new grade, activation state, or persisted certification field.
- No change to existing active Body Silhouette assets.
- No Character Card generation, slot, review, activation, or storage change
  until a later reviewer-approved implementation gate.

## 4. Why face standards should stay stable for now

The latest evidence points to Face Identity being mostly functional:

- same-person face continuity improved after the earlier identity-reference
  work;
- the strongest residual issue appears when the face is placed onto a full
  body, not when the face is viewed as a face-only identity crop;
- changing face standards now risks destabilizing an already useful identity
  layer.

Therefore the next gate should not broaden into Face Identity redesign.

Proposed rule:

```text
Face Identity remains the identity truth owner.
Body Silhouette becomes stronger body-chain evidence.
Neither layer may silently take over the other layer.
```

## 5. Universal body standard, not a child-specific recipe

The standard must work for any modeled person:

- child;
- teen;
- adult;
- elderly person;
- petite, tall, slim, strong, plus-size, or otherwise diverse body types;
- different gender presentations;
- different clothing categories and later downstream scenes.

It must not encode a fixed numeric ratio such as "six heads tall" or "six-year
old child proportion." Instead, it should encode visual coherence dimensions
that can be judged relative to the person stage and source evidence:

```text
developmental / age-stage coherence
head-neck-shoulder continuity
torso-limb skeletal plausibility
stance and ground contact
cross-view body parity
face-to-body integration plausibility
commercial full-body usability
```

These are general human-body quality dimensions, not scene recipes.

## 6. Proposed Body Silhouette source-standard dimensions

The next reviewer-approved design phase should turn the following into a
versioned source-standard contract.

### 6.1 Body-chain coherence

The head, neck, shoulders, torso, pelvis, limbs, hands/feet, and stance should
read as one connected body.

Failure examples:

- oversized or undersized head relative to body;
- head appearing pasted onto shoulders;
- compressed neck;
- shoulders too narrow, too broad, too high, or too slope-less for the person;
- torso and limbs not matching the apparent face age/stage;
- doll-like or mannequin-like full-body result.

### 6.2 Stage-aware proportion

The body should match the person's stage without hard-coded numeric ratios.

The standard should verify:

- plausible child/teen/adult/elder stage;
- plausible limb length and mass for that stage;
- no accidental adultification of a child body;
- no over-infantilization of an older child, teen, or adult;
- no generic "cute doll" body when the request requires a real person.

### 6.3 Neck, shoulders, and upper torso

This is the main area where pasted-face/body artifacts become visible.

The standard should verify:

- visible or structurally inferable neck support;
- natural shoulder width and slope;
- plausible upper torso volume;
- no hidden or collapsed neck caused by hair, clothing, or framing;
- cross-view support from side and rear views.

### 6.4 Torso, limbs, and joints

The standard should verify:

- torso length and width;
- arm and leg segment balance;
- knee, ankle, elbow, wrist, hand, and foot plausibility;
- non-rubbery limbs;
- natural joint placement;
- left/right symmetry unless pose-owned and plausible.

### 6.5 Stance and weight

Even neutral Body Silhouette references must have believable physical balance:

- feet contact ground plausibly;
- weight-bearing is clear;
- knees and ankles align naturally;
- body centerline is not collapsed or floating;
- full-body pose is neutral enough for reuse, but not so rigid that it becomes
  a cardboard model card.

### 6.6 Cross-view parity

The three views should describe the same body:

- front view: full-body proportion and limb/torso relation;
- side view: body depth, neck projection, chest/back/pelvis relation;
- rear view: rear neck/shoulder/back/leg continuity;
- all views: same stage, same build, same silhouette family.

## 7. Source-class interpretation

Existing source classes must remain provenance, not automatic certification.

```text
observed:
  user supplied or otherwise observed full-body evidence.
  Stronger raw evidence, but still requires review.

user_described:
  directional constraints only.
  Cannot certify body realism by itself.

brain_inferred:
  useful when no observed body exists, but weaker for high-realism commercial
  certification.
```

The next design should avoid the mistake of treating `observed`,
`user_described`, or `brain_inferred` as an automatic quality grade.

## 8. Proposed future gates

### Gate A — document contract design

Define the Body Silhouette source-standard contract and the review evidence
required to judge it. This may be a Doc178 follow-up or a new visual-assets
document.

Deliverables:

- final source-standard dimensions;
- pass/fail issue vocabulary;
- isolation from Face Identity;
- historical compatibility rules;
- no runtime behavior changes.

### Gate B — deterministic review contract tests

Only after Gate A approval:

- add deterministic tests for contract parsing and issue classification;
- verify no downstream runtime change;
- verify no change to existing active assets;
- verify no child/swimwear/poolside-specific branch.

### Gate C — Body Silhouette regeneration/review implementation

Only after Gate B approval:

- update the Body Silhouette generation/review owner if approved;
- keep front/side/rear slot lifecycle intact unless explicitly reviewed;
- do not add grades or certifications without a lifecycle and migration plan.

### Gate D — controlled modeling-card refresh

Only after implementation and review gates:

- create new Body Silhouette candidates for the active Character Card;
- review against the upgraded standard;
- activate only if the new front/side/rear views pass;
- preserve historical assets append-only.

### Gate E — downstream validation

Only after a refreshed active Body Silhouette exists:

- rerun Professional General/Photography/E-Commerce planning-only;
- verify body-only projection and provider refs remain under cap;
- run controlled visual review for at least one visible/full-body output per
  module before claiming the upgraded source improves downstream imagery.

## 9. Compatibility and migration

Until a later gate changes runtime state, existing Body Silhouette assets:

- remain active if already active;
- remain readable;
- remain valid under their original contract;
- must not be retroactively marked failed;
- must not gain a new grade or certification field;
- must not be used to claim commercial body realism beyond the evidence they
  actually passed.

If a future stricter standard is approved, historical assets should be treated
as:

```text
legacy_body_silhouette_valid_for_current_contract
not_automatically_certified_for_upgraded_body_realism
```

This distinction prevents breaking old workflows while avoiding overclaiming.

## 10. Test and acceptance matrix for a future implementation gate

| Area | Required proof |
| --- | --- |
| Face isolation | Face Identity tests remain unchanged; Body Silhouette cannot change facial geometry truth. |
| Body source standard | Front/side/rear body views are evaluated against scene-neutral body-chain dimensions. |
| Source class | `observed`, `user_described`, and `brain_inferred` do not automatically certify quality. |
| Cross-view parity | front/side/rear describe the same body stage and build. |
| Historical assets | existing active assets remain readable; no automatic invalidation. |
| Downstream projection | existing body-only runtime projection still consumes active slots without channel leakage. |
| General isolation | no General Template scenario recipe or user prompt keyword gate is added. |
| Specialized isolation | no E-Commerce/Photography child, swimwear, poolside, or product-specific body recipe is added. |
| Provider cap | max provider references remain unchanged. |
| Visual acceptance | controlled visual review proves reduced head-body mismatch and pasted-face/body effect before any production claim. |

## 11. Reviewer decision requested

Reviewer should decide:

1. Is the next owning layer correctly identified as Body Silhouette source
   standard / review design, rather than downstream E-Commerce prompt tuning?
2. Is it acceptable to keep Face Identity standards unchanged for this phase?
3. Are the proposed body dimensions universal enough and not overfit to the
   recent child swimwear case?
4. Should the next allowed work be document-only Gate A, or should this remain
   a deferred diagnostic note until more visual evidence is collected?
5. If Gate A is approved, which document should become the source authority:
   a Doc178 follow-up or a separate Body Silhouette source-standard document?

## 12. Current stop condition

This document asks for reviewer direction only.

Do not implement, regenerate Body Silhouette, change Character Card lifecycle,
modify Face Identity, run planning-only, run Host/MCP/ImageGen, write formal
receipt/slot/activation, or change existing assets until reviewer explicitly
opens the next gate.
