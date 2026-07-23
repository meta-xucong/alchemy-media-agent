# Doc190 — Character Card left/right 45° face-view canonicalization

## Status

Supersedes the historical `face.reverse_three_quarter = rear three-quarter`
interpretation in older Doc189-era notes and tests. Doc192 further supersedes
the opposite-45° reference-routing details in this document: the current
right/front 45° chain is front winner + 90° profile pose-depth authority +
right_front_25 bridge, not left45-as-driver and not 25°-before-profile.

## Problem

The Character Card Face Identity module needs standardized modeling-card views:

1. straight front;
2. left/front-side 45°;
3. side/profile 90°;
4. right/front-side 45°;
5. rear head.

Earlier implementation overloaded `reverse_three_quarter` as a rear or
back-of-head dominant view. That is wrong for the face-view card matrix. It
causes the fourth face slot to become a back-view image instead of the opposite
front 45° evidence card.

The same defect also exposed a crop/scale gap: a slot can satisfy the rough
angle while drifting from the approved front card into a tight beauty close-up
or a looser half-body crop. Character Card Face Identity cards are comparison
evidence, so all face-view slots must share the same modeling-card framing.

## Canonical slot meaning

The persisted slot key remains unchanged for compatibility:

| Slot key | Canonical meaning |
| --- | --- |
| `face.front` / `standard_front` | straight-on front head-and-upper-shoulders card |
| `face.front_three_quarter` / `three_quarter` | left/front-side 45° head-and-upper-shoulders card |
| `face.profile` / `profile` | 90° side-profile head-and-upper-shoulders card |
| `face.reverse_three_quarter` / `reverse_three_quarter` | opposite right/front-side 45° head-and-upper-shoulders card |
| `face.rear_head` / `rear_head` | rear-head / back-of-head card |

`reverse_three_quarter` is therefore a legacy internal name only. UI and review
language should present it as “右前45° / opposite front-side 45°”, not the
ambiguous historical “反侧前方”.

## Prompt contract

For non-front Face Identity slots the Doc186 reference-led slot-delta principle
still applies:

- do not repeat the full first-front identity prompt;
- use approved root/winner references for stable identity, age, complexion and
  material continuity;
- renderer-facing language should mainly describe the view-angle delta.

All Face Identity view slots must use one compact modeling-card framing rule:
match the approved front/card-family camera distance, head size, head-top
margin, upper-shoulders cutoff, collar line, white padding and vertical 2:3
head-neck-upper-shoulders crop. They must not become tight face close-ups,
half-body crops or torso portraits. Eye-line, chin line, neckline, bottom cutoff
and similar details are review signals, not renderer-facing hard-wording
requirements. Visible front-side 25°/45° cards must keep the face readable for
identity comparison while allowing natural face-box size and position changes
from head rotation; profile and rear-head cards preserve comparable head/hair
silhouette scale without face-area wording. This framing cue is part of the
slot delta contract; it is not a return to the heavy first-front identity
prompt.

For `three_quarter`, the positive renderer direction must express the
left/front-side 45° view and include observable same-side direction cues: the
left ear on image-left, nose/gaze toward image-right, front-side depth, and a
smaller far eye while both eyes remain visible. A generic phrase such as
`left-front 45°` is not enough by itself, because it can still randomly flip to
the opposite side. The prompt should be concise: aim for a natural 40°-50°
family, visibly deeper than the 25° bridge, not straight-front, pure profile,
rear/back or opposite-side.

For `reverse_three_quarter`, the positive renderer direction must express the
opposite front-side 45° view and must not describe a rear view, back-of-head
dominant view, or over-the-shoulder view. It must also include an observable
opposite-side ear cue plus a nose/gaze direction cue, for example: the
right ear on image-right, nose/gaze toward image-left, front-side depth, and a
smaller far eye while both eyes remain visible. This prevents the slot from
duplicating the already approved left/front-side 45° card. It must be an
independent opposite-side view derived from the approved front identity, not a
horizontal flip, copied left-side face or literal mirror. Natural left/right
facial and hair asymmetry must remain available to the model. It must match the
approved card-family framing, but it must not require the detected face
rectangle to match another angle. The approved 90° profile is the pose-depth
guide, while the right 25° bridge is only same-side identity/asymmetry support.

## Provider/MCP framing-reference transport

For Character Card Face Identity continuation slots, the shared materializer
must also pass one approved full-frame card as a framing-only reference. This
reference is not an identity-feature crop and must not be treated as a
wardrobe, lighting, scene or beauty-template source. It exists only to anchor
camera distance, head size, head-top margin, upper-shoulders crop,
shoulder-line white padding, plain white field and clean card boundaries.

The selected framing reference is deterministic:

- `three_quarter` and `profile` use the first reviewed generated winner in the
  bounded serial evidence set;
- `reverse_three_quarter` uses the original approved front card as the
  full-frame card-framing reference, the approved 90° profile as the primary
  pose-depth authority, and the approved right_front_25 bridge only as the
  same-side identity/framing bridge, admitted as feature/identity evidence
  rather than pose-geometry evidence. It must not receive a pixel-mirrored copy
  of the left/front-side 45° card, must not route through left45 as the
  opposite-side driver, and must not let the 25° bridge dominate the final yaw.
  The right/front-side 45° card is independently generated from the approved
  identity while still matching the approved crop and scale;
- `rear_head` uses the latest reviewed generated winner in the bounded serial
  evidence set.

This framing reference replaces the same source's second pose-geometry crop
inside the existing 2/3/5 Provider/MCP budget. The total input count does not
increase, ordinary portrait identity jobs continue to use Doc95 derivative
evidence, and only `character_card_face_identity` continuation stages can emit
`character_card_full_frame_framing_reference`.

The full-frame framing reference is evidence routing only. It is not a new
Provider, not an image repair, not a private reviewer, not a new identity truth,
and not a mirrored derivative. The source asset id remains the approved
generated card, and the evidence scope remains `card_framing`.

For `reverse_three_quarter`, the concrete 5-reference Provider/MCP budget is:

1. root uploaded identity pose-geometry evidence;
2. approved `standard_front` feature-detail evidence;
3. approved `standard_front` full-frame card-framing evidence;
4. approved `profile` pose-geometry evidence;
5. approved `right_front_25` same-side feature/identity bridge evidence.

This keeps the right/front 45° identity anchored on the front winner, uses the
90° profile for real view-depth calibration, keeps right_front_25 as a
same-side bridge rather than the target yaw, and prevents pixel-mirroring,
left45 side-chain drift, or shallow 25° collapse.

## Resume checkpoint contract

Failed Character Card preparation is append-only and resumable, but a resume
must not blindly trust historical accepted views that were produced under older
slot semantics. Before continuing a failed Character Card pack, the shared
Product API host must re-check the active Face Identity view prefix against the
current card contract:

- `standard_front` must still read as a front card;
- `three_quarter` must read as the fixed left/front-side 45° card;
- `profile` must read as a true 90° side profile;
- `reverse_three_quarter` must read as the independent opposite right/front-side
  45° card, must match the approved `three_quarter` card framing without
  copying or flipping it, and must depend on valid front, `three_quarter` and
  profile checkpoints;
- once any checkpoint fails the current view contract, that view and all later
  views are discarded from the resume prefix and regenerated with a fresh
  bounded candidate budget.

This rule is deliberately stricter than legacy pack persistence. It protects
newer runs from old accepted-but-noncanonical 45° outputs that would otherwise
contaminate profile, opposite 45°, Expression Set and Body Silhouette stages.
It does not mutate or delete the historical pack record; it only controls which
views are eligible to seed the next append-only preparation version.

Each selected Face Identity winner must be persisted immediately as a resumable
pack checkpoint before the service starts the next view. MCP materialization is
intentionally one-use evidence: once a submitted artifact is consumed into a
reviewed candidate, the system must not need to consume that handoff again just
because the process is paused, times out, or enters the next pending MCP slot.
The checkpoint may remain `failed` until the full module reaches final review,
but its active view prefix is authoritative for resume after it passes the
current card-contract re-check above. This prevents an accepted right/front 45°
candidate from being lost when the next rear-head handoff is waiting for user
materialization.

For timeout recovery, the complete evidence chain is `root upload + reviewed
winner outputs`. `professional_anchor_reference_assets` contains only reviewed
winner outputs by design; the original root remains on the uploaded-asset
binding. The first left/front 45° slot must therefore be recoverable with one
winner reference asset as long as the uploaded root is present, because its real
evidence chain is still root + front winner.

## Review contract

Shared Vision `pose_compliance` for Character Card Face Identity means
face-view slot geometry:

- fail if any Face Identity view slot changes crop/scale from the approved
  card family, including tight face close-ups, big-head crops, missing
  head-adjacent hair silhouette/head-top margin, missing neck/upper
  shoulders/collar line, or half-body framing;
- fail if a slot reveals a chest/torso panel or loses the lower white padding
  that makes the head-and-upper-shoulders card family comparable;
- fail if a later face-view slot becomes softer, closer, or more vignetted than
  the approved front/left45 cards, including faded hair boundaries;
- fail if `three_quarter` is not the left/front-side 45° slot;
- fail if `reverse_three_quarter` reads as rear three-quarter, back-of-head,
  or the subject is mostly turned away;
- fail if `reverse_three_quarter` repeats the same visible side as the existing
  left/front-side `three_quarter` card instead of becoming an independent
  opposite-side view;
- fail if `reverse_three_quarter` is produced from a pixel-mirrored copy,
  horizontal flip, or literal left45 copy rather than the approved front
  identity and real opposite-side view;
- pass only when it reads as the opposite front-side 45° modeling card with
  enough face visible for identity comparison;
- keep `rear_head` as the only slot where the face is intentionally hidden, and
  judge its scale through the back-of-head hair outline, neck, upper shoulders
  and back collar line rather than face-area proportion.

The Product API Host also applies a deterministic local framing-parity gate for
the left/right 45° face slots before a reviewed candidate can become a
Character Card winner:

- `three_quarter` must locally read as the fixed first/front-side 45° direction;
  if the model randomly mirrors the side, it fails with
  `professional_face_card_view_direction_parity_failed`;
- `reverse_three_quarter` must locally read as the independent opposite
  front-side 45° direction; if it is the same side as the approved
  `three_quarter` card, it fails with
  `professional_face_card_opposite_45_side_failed`;
- both front-side 45° slots must also have enough local view-angle depth. A
  shallow, almost-front card may fail if it cannot serve as a distinct 45°
  modeling slot, but the gate must not reject a commercially strong card merely
  because the estimated angle is a little softer or deeper than ideal.  The old
  exact `0.18–0.34` detector window and hard "reject 20–30°" language are
  superseded by Doc192: the local yaw metric is a soft slot-separation guard,
  not a precision angle ruler, and should accept commercially strong front-side
  45° cards inside the current relaxed range when direction, crop, identity and
  visual quality fit;
- the historical requirement that `three_quarter` / `reverse_three_quarter`
  hard-compare detected face-box area with another angle is superseded by
  Doc192.  Face-box area may be logged as a diagnostic, but it must not decide
  cross-angle slot acceptance because yaw naturally changes the detector box;
- the old default 5% maximum relative face-area delta is superseded by Doc192
  for Character Card 25°/45° visible face slots.  Use Doc192's full-card
  foreground framing gate to reject close-ups, half-body expansion, head-top
  drift and shoulder-line mismatch;
- all later Face Identity cards also compare the white-card foreground framing
  against the approved card family. This deterministic non-biometric gate
  checks subject top margin and foreground height so a later view cannot become
  a closer, lower, or looser crop even when its detected face area happens to be
  near the baseline;
- foreground-card height drift is capped at 10%, head-top margin drift at 0.045
  normalized image height, shoulder-line/bottom-padding drift at 0.055
  normalized image height, and left/right 45° foreground width drift at 28%;
- a failed-pack resume applies the same current view-direction and framing
  checks to historical accepted checkpoints before they are allowed to seed
  profile, opposite 45°, rear, Expression Set or Body Silhouette stages;
- if local detection is unavailable, times out, or the delta exceeds the
  threshold, the candidate remains non-deliverable with
  `professional_face_card_framing_metric_unavailable`,
  `professional_face_card_framing_parity_failed`,
  `professional_face_card_head_top_margin_parity_failed`, or
  `professional_face_card_subject_scale_parity_failed`.

This gate records only ephemeral detection status plus normalized face/foreground
box ratios for the current review decision. It does not persist biometric
embeddings and does not create a private reviewer.

For `rear_head`, the face is intentionally hidden and output facial landmarks
are expected to be unavailable. The Host must therefore not apply the visible
face-card identity floor literally to rear-head pixels. It should accept a
shared Vision `verified/pass` rear-head candidate when commercial clarity,
pose compliance, age coherence, neutral capture and non-face continuity
evidence (hair mass, crown, neck, shoulders and back collar line) meet the
rear-head floor. This does not weaken `standard_front`, `three_quarter`,
`profile` or `reverse_three_quarter`.

## Compatibility

No new Provider, Brain, Vision, retry or storage path is introduced. Provider
and MCP continue to consume the same canonical prompt, reference evidence,
handoff/receipt and shared Vision result. The only change is the canonical
meaning and validation of the historical `reverse_three_quarter` slot.

## Brain latency guardrail

Character Card non-front face slots are weak reference-led deltas. They should
not wait behind the full remote Brain transport timeout used by first-image or
general creative planning. The runtime may apply a short transport-only timeout
cap to these requests, then use the bounded slot-delta recovery path when the
remote Brain is slow or unavailable.

This timeout cap is not prompt context and must not be serialized into the
Brain payload. It does not affect `standard_front`, General, E-Commerce,
Photography, Expression Set, Body Silhouette, or ordinary Anchor Pack work.

The recovery path is still a Remote Brain continuity path, not a local prompt
builder. Any recovered `VisualTaskProfile` and reference-channel ownership
receipt must keep `decision_owner=remote_brain` so the shared reference policy,
portrait identity and Human Realism executors remain active and auditable.
