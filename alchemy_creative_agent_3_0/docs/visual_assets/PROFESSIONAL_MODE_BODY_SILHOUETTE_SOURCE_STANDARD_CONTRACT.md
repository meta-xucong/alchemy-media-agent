# Professional Mode Body Silhouette Source Standard Contract

Status: **DOCUMENT_ONLY_GATE_A_UNDER_REVIEW**

This document is a Doc178 follow-up design contract for Body Silhouette source
quality. It defines scene-neutral review semantics for existing and future
`body.front_full`, `body.side_full`, and `body.rear_full` Character Card body
views.

It does **not** authorize implementation, regeneration, prompt changes,
runtime field changes, grades, receipts, activation changes, storage changes,
planning-only validation, Host/MCP/ImageGen calls, formal receipts, slots, or
activation.

## 1. Authority and non-authority

### 1.1 Current authority retained

The following authorities remain unchanged:

- Doc178 owns the Character Card module lifecycle and slot template.
- Face Identity owns face/head identity evidence.
- Expression Set owns expression slots.
- Body Silhouette owns body-shape/body-continuity evidence.
- The already-approved downstream body-only projection owns how active Body
  Silhouette evidence is consumed by Professional visible/full-body outputs.
- Shared Human Realism may own general human-realism issue vocabulary, but not
  Character Card lifecycle or scenario recipes.

### 1.2 What this document owns

This document owns a proposed source-standard contract for evaluating whether
Body Silhouette evidence is visually strong enough as body-chain evidence.

It defines:

- universal source-standard dimensions for `body.front_full`,
  `body.side_full`, and `body.rear_full`;
- the meaning of body-chain, stage-aware proportion, head-neck-shoulder,
  torso/limb/joint, stance/ground-contact, and cross-view parity evidence;
- the boundary between Body Silhouette and Face Identity;
- how `observed`, `user_described`, and `brain_inferred` should be interpreted
  as provenance only;
- compatibility rules for historical assets.

### 1.3 What this document does not own

This document does not own:

- Character Card generation prompts;
- Body Silhouette slot definitions;
- Body Silhouette review implementation;
- Body Silhouette activation or storage;
- runtime fields, grades, receipts, or migrations;
- downstream E-Commerce, Photography, or General prompt rules;
- Provider cap changes;
- Host/MCP/ImageGen execution;
- formal project delivery records.

## 2. Why this contract is needed

The downstream Professional body-only projection has closed the runtime
transport problem: active Body Silhouette evidence can now reach Professional
visible/full-body image generation as a body-only reference.

The remaining quality problem is source quality:

```text
If Body Silhouette is clean but doll-like,
downstream output can become clean but doll-like.

If Body Silhouette has weak neck/shoulder/body-chain evidence,
downstream output can still show a pasted-face/body feeling.
```

The correct next layer is therefore the Body Silhouette source standard, not
another downstream E-Commerce prompt workaround.

## 3. Body Silhouette purpose

Body Silhouette exists to provide reusable body evidence for a People Asset.
It is not a fashion photo, scene photo, product photo, or pose library.

It should preserve:

```text
body scale
head-to-body relationship
neck and shoulder transition
torso and limb proportion
stage-aware body coherence
front/side/rear body parity
```

It must not preserve or transfer:

```text
wardrobe
scene
background
lighting
camera angle
expression
pose recipe
product identity
```

Body Silhouette should make it easier for later Professional outputs to place
the approved face on a plausible body without making later modules inherit a
white-background modeling card.

## 4. Scope of body views

The source standard applies to these existing Doc178 slots:

```text
body.front_full
body.side_full
body.rear_full
```

No new slot is introduced by this document.

### 4.1 `body.front_full`

Primary evidence for:

- front-facing head-body relationship;
- shoulder width and slope;
- torso width and length;
- arm and leg proportion;
- stance and weight distribution;
- feet/ground contact;
- general person-stage body coherence.

### 4.2 `body.side_full`

Primary evidence for:

- neck projection and head support;
- chest/back/pelvis depth;
- body thickness;
- posture;
- knee/ankle relation from profile;
- side-view continuity with the front body.

### 4.3 `body.rear_full`

Primary evidence for:

- rear head/neck/shoulder transition;
- back and shoulder continuity;
- rear torso/leg relation;
- hair-body separation;
- rear stance and ground contact;
- parity with front and side views.

## 5. Universal source-standard dimensions

The standard must be person-stage-aware and scene-neutral. It must not encode a
fixed head-count ratio, child-specific recipe, swimwear rule, poolside rule,
kidswear rule, or E-Commerce-specific body style.

### 5.1 Body-chain coherence

The body should read as one connected physical organism.

Required evidence:

- head, neck, shoulders, torso, pelvis, limbs, hands/feet, and stance align as
  one plausible body chain;
- the head does not appear pasted onto the body;
- body mass and limb length feel coherent with the face age/stage;
- no obvious doll, mannequin, inflatable, or card-stand body effect.

Potential issues:

```text
head_body_scale_mismatch
pasted_head_body_boundary
doll_like_body_chain
mannequin_body_chain
body_chain_discontinuity
```

These issue names are review vocabulary candidates only. They are not runtime
fields in this gate.

### 5.2 Stage-aware proportion

The body should match the person stage implied by approved identity evidence
and user-authorized body evidence.

Required evidence:

- child bodies remain age-appropriate without becoming infantile or doll-like;
- teen/adult/elder bodies do not inherit childlike proportions unless
  explicitly supported by evidence;
- diverse body types remain valid when coherent with source evidence;
- no numeric ratio is treated as universal truth.

Potential issues:

```text
stage_incoherent_body_proportion
over_infantilized_body
accidental_adultification
generic_model_body_override
```

### 5.3 Head-neck-shoulder continuity

This is the highest-risk area for pasted-face/body artifacts.

Required evidence:

- neck support is visible or structurally inferable;
- shoulder width is plausible relative to head, torso, and stage;
- shoulder slope is natural;
- the head does not float above, press into, or detach from the shoulders;
- hair or clothing does not hide all critical neck/shoulder evidence.

Potential issues:

```text
compressed_neck_shoulders
floating_head
neck_support_missing
shoulder_width_incoherent
head_neck_shoulder_discontinuity
```

### 5.4 Torso, limbs, and joints

The Body Silhouette should carry enough skeletal plausibility to guide later
visible/full-body generation.

Required evidence:

- torso length, width, and volume are plausible;
- arms and legs have plausible segment lengths and mass;
- knees, ankles, elbows, wrists, hands, and feet are not rubbery or misplaced;
- left/right asymmetry is either minimal or pose-plausible;
- limb scale remains coherent across front/side/rear views.

Potential issues:

```text
torso_compression
limb_length_incoherence
joint_placement_error
rubbery_limb_structure
left_right_body_asymmetry
```

### 5.5 Stance and ground contact

Neutral model-card body evidence still needs physical weight.

Required evidence:

- feet contact the ground plausibly;
- balance and weight-bearing are clear;
- knees, ankles, pelvis, shoulders, and head align naturally;
- the body is not floating, collapsing, or leaning impossibly;
- stance is reusable and neutral without becoming a stiff cardboard cutout.

Potential issues:

```text
floating_body
implausible_ground_contact
collapsed_weight_bearing
cardboard_stance
stance_centerline_error
```

### 5.6 Cross-view parity

The three body views must describe the same person body.

Required evidence:

- front, side, and rear views share the same stage, build, height family, and
  body mass;
- side depth matches front width and rear shape;
- rear neck/shoulder/back relation matches front/side head-neck-shoulder
  evidence;
- leg and arm proportions remain consistent across views;
- no view silently changes the person into a different build.

Potential issues:

```text
cross_view_body_parity_mismatch
front_side_body_depth_conflict
rear_body_build_conflict
view_specific_age_stage_drift
```

## 6. Source-class semantics

`body_source` remains provenance only. It does not certify quality.

### 6.1 `observed`

Meaning:

- user supplied or otherwise admitted full-body evidence exists.

Rules:

- stronger raw evidence may be available;
- review is still required;
- observed source does not automatically mean realistic or commercial-ready.

### 6.2 `user_described`

Meaning:

- user supplied body/build/proportion constraints in words.

Rules:

- useful as directional input;
- cannot certify visual body realism by itself;
- cannot override reviewed visual evidence unless the product contract gives it
  authority.

### 6.3 `brain_inferred`

Meaning:

- no full-body visual evidence or precise user body evidence exists;
- Brain inferred body direction from identity, stage, and intent.

Rules:

- valid for producing a Body Silhouette under the existing lifecycle;
- this wording does not assign a quality grade or certification;
- weaker for high-realism source confidence;
- must not be overclaimed as observed body truth.

Throughout this document, terms such as "commercial" or "commercial-ready"
describe a possible user-facing visual quality goal. They do not create a
runtime field, receipt value, activation state, grade, or certification.

## 7. Face Identity and Body Silhouette boundary

Face Identity remains the facial identity truth owner.

Face Identity owns:

- face geometry;
- facial-feature relationships;
- same-person facial continuity;
- approved face views and expression-compatible identity anchors.

Body Silhouette owns:

- body scale;
- head-body relationship as a body-chain issue;
- neck/shoulder transition;
- torso/limb proportion;
- stance and ground contact;
- front/side/rear body parity.

Boundary rules:

1. Body Silhouette must not alter Face Identity facial geometry.
2. Face Identity must not be treated as precise body-proportion evidence.
3. Face-to-body integration is reviewed as a Body Silhouette evidence concern,
   not as permission for Body Silhouette to redesign the face.
4. If a later output has a recognizable face but a pasted-body feeling, the
   owning diagnosis should first separate face identity continuity from
   body-chain continuity.

## 8. Relationship to downstream body-only projection

The existing Professional body-only runtime projection remains current.

This source-standard contract does not change:

- body-only reference channel;
- provider cap;
- per-output body requirement receipt;
- E-Commerce product truth selection;
- Photography deliverable roles;
- General Professional neutrality;
- Host or MCP materialization behavior.

Future upgraded Body Silhouette evidence, if approved and activated, would be
consumed through the same body-only projection path. Downstream modules should
not add local prompt fixes such as "make the head smaller" or scenario-specific
body recipes.

## 9. Relationship to shared Human Realism

Shared Human Realism may own general issue-code semantics for human realism,
including head-body mismatch, neck/shoulder compression, body-chain
discontinuity, and doll-like body structure.

Shared Human Realism must not own:

- Character Card Body Silhouette lifecycle;
- Body Silhouette slot generation;
- activation;
- storage;
- a child, swimwear, poolside, or E-Commerce-specific body recipe.

If later implementation needs shared issue codes, those codes must be general
human-body review semantics and prove isolation across materially different
person/scene types.

## 10. Historical compatibility

Historical Body Silhouette assets remain readable and valid under the contract
they originally passed.

This document must not:

- invalidate existing active Body Silhouette slots;
- mark historical slots as failed;
- introduce `commercial` grade or certification state;
- trigger automatic migration;
- alter activation receipts;
- change downstream behavior for existing assets.

If a future stricter standard is approved, old assets may be described as:

```text
legacy_body_silhouette_valid_for_current_contract
not_automatically_certified_for_upgraded_source_standard
```

That distinction is descriptive only unless a later migration gate creates a
real migration process.

## 11. Conflict and compatibility with existing documents

### 11.1 Doc178

Doc178 remains authoritative for Character Card modules and the
front/side/rear Body Silhouette slot template.

This document is a follow-up source-standard design. It does not rewrite the
Doc178 lifecycle.

### 11.2 Body Proportion Runtime Projection Design

The runtime projection design remains authoritative for downstream consumption
of active Body Silhouette evidence.

This document is upstream of that projection. It asks whether the source body
evidence itself should be held to a stronger standard before it becomes active.

### 11.3 Body Silhouette Realism Diagnostic Note

The earlier diagnostic note recorded why this issue exists. This document turns
that diagnosis into a proposed source-standard contract.

The diagnostic note remains historical context. This document should become the
review target for Gate A if reviewer approves it.

### 11.4 Professional root-plus-face wording

Older Professional wording that implies root portrait plus selected face winner
is enough for every Professional human output remains narrowed by the body-only
runtime projection design:

- face-only and local detail outputs may still use the Face Identity path;
- visible/full-body Professional outputs need body-only evidence when
  applicable;
- source-standard quality is a separate upstream concern.

## 12. Future Gate B test matrix

This document is not a test implementation. If reviewer opens Gate B, the test
matrix should prove:

| Area | Required proof |
| --- | --- |
| Document parsing | contract dimensions and issue vocabulary are stable and scene-neutral. |
| Face isolation | Face Identity fields and tests are unchanged. |
| Body ownership | Body Silhouette owns body-chain evidence only. |
| Source class | `observed`, `user_described`, and `brain_inferred` do not certify quality by themselves. |
| No grade authority | no runtime `commercial` grade or certification field appears. |
| Historical compatibility | old active body slots remain readable and are not auto-invalidated. |
| Shared review isolation | any issue vocabulary stays human-general, not child/swimwear/poolside-specific. |
| Downstream projection parity | body-only projection remains unchanged and does not inherit wardrobe/pose/scene. |
| No runtime mutation | no planning, Host, MCP, receipt, slot, activation, or business write occurs in document/test gates. |

## 13. Future implementation acceptance outline

Only after separate reviewer approval, a future implementation may need to
prove:

1. front/side/rear Body Silhouette candidates are judged against the source
   standard;
2. review issue evidence is visible and append-only;
3. no grades or certifications exist without a lifecycle;
4. historical assets remain readable;
5. regenerated/updated Body Silhouette views improve downstream visible-body
   outputs in controlled visual review;
6. Face Identity remains stable;
7. downstream modules continue using body-only projection, not prompt patches.

## 14. Current stop condition

This Gate A document requests reviewer review only.

Do not implement code, regenerate Body Silhouette, update Character Card
generation prompts, change slots, change review/activation/storage, run
planning-only, run Host/MCP/ImageGen, or write formal project records until a
separate reviewer gate explicitly allows it.
