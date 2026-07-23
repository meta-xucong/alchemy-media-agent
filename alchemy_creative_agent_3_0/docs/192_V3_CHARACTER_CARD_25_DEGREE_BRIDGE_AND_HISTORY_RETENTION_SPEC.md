# Doc192 — Character Card 25° Bridge Views and Candidate History Retention

Status: implementation spec for Professional Character Card Face Identity.

Supersedes the part of Doc190/Doc191 that implied the final left/right 45°
cards should be generated directly from the front card and a side/profile chain.
Doc190/Doc191 remain authoritative for no-mirror, fixed-card framing, and
left/right 45° semantics.

## Problem

Real validation showed that the renderer repeatedly produced clean,
commercial-looking right-front portraits that were not bad images, but were
only shallow 20–30° views.  Treating those pixels as failed 45° candidates
wastes useful side-specific evidence and makes the system retry the same hard
jump from front to 45°.

This is not an MCP-vs-Provider problem.  It is a Face Identity staging problem:
the model needs side-specific transition evidence before the final 45° card.

## Canonical Face Identity order

Character Card Face Identity now uses this append-only order:

1. `standard_front` → `face.front`
2. `left_front_25` → `face.left_front_25`
3. `three_quarter` → `face.front_three_quarter`
4. `profile` → `face.profile`
5. `right_front_25` → `face.right_front_25`
6. `reverse_three_quarter` → `face.reverse_three_quarter`
7. `rear_head` → `face.rear_head`

The two 25° views are bridge slots.  They are visible and reviewable because
they are useful modeling evidence, but the final standard 45° cards remain the
official left/right three-quarter modeling cards.

For 45° generation, the matching 25° card is an identity/framing bridge only,
not a yaw target.  Renderer-facing prompts must say that the 45° card should
turn visibly deeper than the 25° bridge while staying in the front-side
three-quarter family.  They must also state the intended modeling-card depth
in plain visual language: compose a new card closer to side-profile depth than
to the shallow 25° bridge, while still avoiding a pure profile, and do not
reuse the 25° bridge pose with only the pupils looking sideways.  The profile
card is the stronger pose-depth reference; the 25° bridge remains only an
identity/framing/scale bridge.  The renderer-facing language may use observable
modeling-card cues such as head/neck/shoulder line rotating together, nose tip
leaving the face centerline, one cheek plane clearly receding, the far eye
smaller and partly compressed by the nose bridge, and the near ear becoming the
side cue.  Review gates remain soft slot-separation guards: they should reject
a collapse back into the 25°/near-front pose, but they must not become
precision protractor checks.

## Angle gates

- 25° bridge slots must be visibly beyond a straight front card, but not yet
  full 45°.  The renderer-facing prompt should now describe a natural
  25–30° front-side transition rather than using an artificial hard 38–42°
  compensation target.  It should ask for measurable but moderate face-depth
  cues: facial centerline slightly off center, nose bridge and gaze following
  the requested side, the near cheek slightly broader, the far cheek subtly
  narrower, the far eye slightly narrower while both eyes remain visible, the
  matching ear beginning to show, and the head itself turning instead of only
  shifting the eyes.  A good commercial bridge card should not be rejected
  merely because the detector estimates a slightly softer or deeper angle.
- The local face-yaw heuristic is a soft slot-separation guard, not a precision
  angle ruler.  It must prevent front/25°/45°/profile/rear slot collapse, but it
  must not reject a commercially strong modeling card merely because detector
  landmarks estimate a slightly different angle.  The current accepted 25°
  bridge window is a relaxed `0.060–0.240` magnitude range: tiny near-front
  turns still fail, while borderline bridge cards are allowed into shared
  quality review.
- 25° and 45° visible face cards must preserve the approved front card's
  modeling-card scale family.  The renderer-facing prompt should ask for the
  same foreground card scale, similar head-top margin, stable neck/collar-line
  height and upper-shoulder cutoff while allowing natural face-box projection
  changes caused by yaw.  It should prevent obvious zoom jumps, half-body
  expansion, tight face close-ups, head top drift, and shoulder-line mismatch,
  not demand exact pixel equality or cross-angle face-box equality.
- Face-box parity is no longer a hard acceptance gate for Character Card
  angle slots.  25°/45°/90° head turns naturally change the detector rectangle
  and face-box position even when the visible modeling-card crop is correct.
  The face-box comparison may remain as an internal diagnostic, but official
  slot acceptance must use full-card foreground framing: head-top margin,
  complete head/hair silhouette, subject scale, collar/upper-shoulder cutoff,
  white padding and absence of close-up/half-body drift.  Eye-line, chin line,
  neckline and bottom cutoff are useful review signals, but they must not become
  mandatory renderer-facing wording or brittle prompt-string checks. Shared
  Vision remains responsible for identity, face readability, visual quality and
  angle readability.
- 45° slots should be visibly deeper than the matching 25° bridge and still
  read as left/right front-side modeling cards, but angle is a soft target, not
  a hard rejection ruler.  The current local yaw window is relaxed to roughly
  `0.150–0.380` magnitude and checks the requested nose/gaze direction directly
  rather than requiring the coarse detector `view_hint` label to equal
  `*_three_quarter`.  A commercially strong card should pass when identity,
  side direction, crop, face visibility, and clean image quality are strong,
  even if the yaw is a little softer or deeper than ideal.  Only obvious
  straight-front, pure side-profile, back/rear, same-side/opposite-side wrong,
  mirrored, or materially inconsistent crops should fail.
- When shared Vision verifies a Character Card 45° candidate as pass/warning
  and the local detector also labels it as a three-quarter face slot with the
  correct left/right sign, the Host should not reject it only because the
  numeric yaw magnitude falls slightly below the nominal 45° threshold.  Local
  geometry is a safety guard; shared pixel review remains the primary
  quality/readability authority.  A hard near-front floor still remains:
  detector magnitudes below roughly `0.10` fail even if the coarse label says
  three-quarter, because those images are too close to front to serve as a
  distinct 45° modeling slot.
- Left/right are independent captures.  The right-side bridge and right 45°
  must preserve natural left/right face and hair asymmetry, not copy or mirror
  the left side.
- Character Card score floors may use a tiny numeric epsilon for model/float
  jitter, currently `0.005`, when all other review evidence passes.  This is a
  tolerance against accidental retries such as `0.8776` versus a `0.88` floor;
  it is not a broad quality relaxation and must not rescue genuinely weak
  identity, age, realism, pose, or commercial clarity scores.
- The strict 90° `profile` slot must use cross-angle identity continuity
  rather than a front-facing geometry target as the decisive gate.  A verified,
  commercially clean side-profile card may expose only one eye contour, nose,
  lips, ear, hair mass, jaw/neck and shoulder continuity, so the local
  objective identity metric may score lower than front/45° comparisons.  If
  shared Vision returns `fail_retryable` only for
  `identity_metric_below_commercial_target`, the Host may contextualize that
  issue for `profile` only and let the normal profile floors, prompt/reference
  parity, pose readability, developmental-age coherence, real-skin quality,
  and full-card foreground framing decide.  This does not apply to front,
  25°, 45°, ordinary projects, or any candidate with additional quality,
  policy, framing, side-direction, or identity-drift issues.

## Reference routing

The shared Provider/MCP materialization path remains one path.  Only the final
pixel outlet differs.

Reference evidence is bounded per slot:

- `left_front_25`: root + front winner.
- `three_quarter`: root + front winner + left_front_25 winner.
- `profile`: root + front winner + left 45° winner.
- `right_front_25`: root + front winner + profile winner.
- `reverse_three_quarter`: root + front winner + profile winner + right_front_25 winner.
- `rear_head`: root + front winner + profile winner + right 45° winner.

Provider-native derivative budgets remain capped; full-frame card-framing
evidence is still used only as card scale/crop evidence, never as a scene,
wardrobe, lighting, or style anchor.

For `reverse_three_quarter`, reference order and derivative role are semantic,
not cosmetic: the approved front card remains first so it can anchor identity
and card-family framing; the approved 90° profile is placed before the 25°
bridge because it is the only generated pose-depth authority; the approved
right_front_25 bridge comes after profile and is admitted as same-side
feature/identity evidence rather than another pose-geometry target.
This supersedes any older Doc190 wording that routed the opposite 45° through
the left/front 45° card or placed the 25° bridge before the profile depth
reference.

## Candidate history retention

All generated candidate images, including failed 25°/45° attempts and other
non-final intermediate artifacts, must be retained in storage.  Failed-candidate
receipts may expose only public-safe identifiers (`output_id`, `candidate_id`,
slot/view role, candidate index, failure code, and optional MCP handoff id).
They must not expose raw prompts, local paths, provider responses, API keys, or
private reference bindings.

This prepares the frontend for an "all history" display without weakening
Professional fail-closed behavior.

Browser-facing projections may expose a safe `candidate_history` list on the
latest preparation record.  This is not the official Character Card slot grid:
it is a future all-history feed for intermediate and failed candidates.  The
standard grid remains winner-only.

## MCP foreground materialization cadence

MCP and Provider share the same Brain plan, canonical prompt, reference
evidence, output storage, Vision review, winner selection, and slot-writing
contract.  MCP differs only at the final pixel materialization outlet.

Because MCP requires a visible user/tool handoff, it must not pre-create all
three candidate handoffs for a slot in one opaque batch.  When one candidate
returns `mcp_materialization_pending`, the Character Card preparation must:

1. persist a failed/resumable checkpoint for the current slot;
2. expose only the current candidate handoff id for materialization;
3. pause without creating candidate 2/3 or downstream-slot handoffs;
4. after a submitted artifact is consumed and reviewed, continue to the next
   candidate only if the submitted pixels fail the shared review gate;
5. select the submitted candidate immediately when it passes; do not keep
   generating extra MCP candidates merely for batch-style ranking;
6. for MCP Character Card Face Identity, pause after each successful
   supplementary slot checkpoint instead of immediately starting the next
   angle.  The public asset must show the newly filled slot first, and the next
   explicit resume starts the following slot;
7. stop after the existing three-candidate budget is exhausted.

This preserves the three-attempt safety budget while making progress legible in
the frontend: one visible generated image, one shared review decision, one next
step.  Historical handoff records and generated images remain retained for the
future all-history panel, but stale or downstream handoffs must not be treated
as active resume work.

Provider-mode controlled hosts may still run through all slots in one call.
MCP mode is intentionally more granular because every slot involves a visible
tool handoff and user-observable progress.  A later profile, opposite-side,
expression, or body failure must not hide an already reviewed Face Identity
winner from the beginner-facing Character Card grid.

If the same slot is replanned with the same operation id, prompt hash, and
reference fingerprint after a prior handoff has already been consumed, MCP must
create a new handoff revision rather than returning the consumed record.  This
keeps history append-only while allowing a clean rerun of the same formal slot.
Pending or submitted records with the same contract are still reused so a
normal refresh does not duplicate work.

Face Identity has one extra public-state requirement: when the shared
preparation result contains an MCP checkpoint, the Visual Asset Library must
project that checkpoint onto `character_card.pending_mcp_handoff_ids` and
surface `mcp_materialization_pending` / `mcp_review_pending` as the current
failure code.  Earlier same-slot failures, such as a first candidate rejected
for pose, remain in append-only candidate history, but they must not hide the
current action from the frontend.  A submitted/pending handoff that is no
longer the current slot checkpoint is history only; it must not be treated as
active resume work or shown as the next user action.

When a submitted MCP artifact has already been consumed and a generated job
exists for the same operation id, stage, capture scope and reference evidence,
resume must consume that generated job even if the job request metadata no
longer carries the handoff id.  The handoff store remains the contract source:
the handoff must be `consumed`, and the frozen prompt/reference contract must
still match the current slot.  This prevents a visible image from being
generated, reviewed, and then lost from the Character Card grid merely because
the durable result moved from handoff state into normal generated-job state.
Prompt-current checks must accept equivalent card-scale language, such as
`same head size`, `same camera distance`, `approved front card framing`,
`card-family framing`, `upper-shoulders cutoff`, or equivalent Chinese wording,
when the rest of the frozen framing contract is present.  They must not turn a
stable design rule into brittle string matching. The prompt-current gate checks
only four durable ideas: target slot, reference-role map, compact card framing,
and obvious wrong-view rejection.
The same applies to bridge-angle language: `25-degree`, `25 degree`, and
natural ranges such as `25 to 30 degrees` or `25–30°` all express the same
bridge-slot contract when the side direction, transition role, and framing
terms are present.

## 2026-07-23 simplification audit

Earlier Doc190/Doc192 wording accidentally encouraged layered prompt stacking:
fixed framing, eye-line, chin line, neckline, bottom cutoff, hair boundary,
angle signs, bridge semantics and quality negatives were repeated in Brain
instructions, fallback prompts and local validators. This created a brittle
loop: a semantically correct prompt could fail because it missed a synonym, and
the fallback prompt became long enough to confuse angle generation.

Current authority is simpler:

1. The first front card remains the rich identity-definition prompt.
2. Every later face slot is reference-led and uses only a short view-delta
   prompt.
3. 25° bridge slots are retained, but they are support evidence, not another
   heavy prompt recipe.
4. 45° slots use a soft angle family, exact left/right direction cues, and
   wrong-view rejection; numerical yaw is only a slot-separation guard.
5. Provider and MCP share the same canonical prompt, reference evidence and
   review/writeback contract.
6. Prompt validators must reject missing target/reference/framing semantics or
   obvious wrong-view leaks, but must not require large synonym lists.
7. Face-localization gates apply only to identity-detail references
   (`feature_detail` / `head_geometry`). Pose-depth and card-framing references
   are allowed to be `not_applicable` for face localization because their job
   is yaw/crop guidance, not face-detail extraction. This is a scope fix, not a
   quality relaxation: identity-detail references still fail closed if they are
   not actually face-localized.
