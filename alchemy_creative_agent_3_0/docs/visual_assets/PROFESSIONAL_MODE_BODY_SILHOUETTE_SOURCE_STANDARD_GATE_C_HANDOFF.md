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

## 7. Gate D append-only refresh entry status

The original Gate C wording treated the append-only Body Silhouette refresh
entry as a future design concern. That wording is superseded by the
`body-silhouette-append-only-refresh` lifecycle gate: Gate C now provides an
explicit Body-owner refresh entry for active `body.front_full`,
`body.side_full`, and `body.rear_full` slots.

The implemented refresh entry is still not a controlled modeling refresh,
visual acceptance, activation, Host/MCP/ImageGen run, downstream product-image
change, provider-cap change, UI change, storage migration, grade, or
commercial certification. It only creates a pending append-only Body
Silhouette refresh review state through the existing three-candidate shared
review -> formal slot receipt -> winner-selected lifecycle.

Lifecycle invariants:

1. Existing active Body slots, old active output ids, and old formal receipts
   remain readable and are not rewritten, recomputed, superseded, or activated
   by the refresh entry.
2. A pending `reviewing` refresh cannot be silently overwritten. Re-entry while
   reviewing fails closed with a refresh-pending error.
3. A `blocked` refresh may start a new explicit refresh revision after a
   theory-first correction, so a failed review does not become a permanent
   deadlock. The new revision remains append-only and still cannot activate
   without a later explicit activation authority.
4. The refresh path remains scene-neutral: no fixed age, fixed head/body ratio,
   swimwear, poolside, kidswear, E-Commerce, wardrobe, pose, lighting, camera,
   expression, downstream prompt, provider-route, or product recipe is added.
5. Ordinary `prepare_body_silhouette` keeps the active/winner skip semantics;
   `retry_failed_slot` is not expanded into refresh authority.

A later Gate D controlled modeling refresh may use this entry, but that gate
must still be separately approved and must separately verify candidate
generation, visual review, pending winners, mutation boundaries, and explicit
activation eligibility before any active Body slot is replaced.

## 8. Gate C reviewer correction after initial blocked implementation

Initial implementation commit `b6703f2` was blocked and must be treated as a
superseded feature-branch attempt, not as an approved merge candidate.

The corrected authority model is:

1. `score_dimensions` are not proof.  A Body candidate only satisfies the
   source standard when the shared review receipt carries both the closed
   dimension name and the Body-owner closed verified evidence code for that
   dimension.  A declared dimension without the corresponding verified evidence
   code remains fail-closed.
   The Body-owner `professional_body_silhouette_source_standard_v1` contract
   uses `dimension_score_floor=0.80` only as a new-candidate review eligibility
   floor for emitting those verified evidence codes.  It is not a grade,
   commercial certification, downstream runtime field, migration rule, or
   historical asset invalidation rule.  Missing, non-finite, non-numeric, or
   below-floor scores do not emit verified evidence.
2. Body Silhouette owns the source-standard vocabulary under
   `visual_assets`.  Shared Vision may project the Body-owner allowlist for the
   Body stage, but it does not globally own or apply Professional Body
   Silhouette source standards.
3. Cross-view parity is not a single-candidate dimension.  It is owned by the
   Body three-slot formal acceptance/card-level gate after front, side, and rear
   slot receipts exist.  That gate requires the server-owned positive evidence
   code `body_silhouette_cross_view_parity_verified`; absence of a mismatch
   issue is not enough.  Per-slot source proof stays limited to per-image body
   chain, stage-aware proportion, neck/shoulder continuity, torso/limb/joint
   plausibility, and stance/ground contact.
4. Historical active or winner-selected Body slots remain readable.  Existing
   persisted formal receipts are validated as durable receipts and are not
   retroactively recomputed through the new candidate proof.
5. Prompt projection remains scene-neutral.  It may expose the Body-owner source
   standard and closed issue vocabulary to shared review, but it must not add a
   six-year-old, swimwear, poolside, kidswear, E-Commerce, commercial-grade, or
   fixed-ratio recipe.

6. The earlier `professional_body_silhouette_wardrobe_v1` runtime contract is
   superseded for new Body Silhouette source-standard candidates.  New Body
   stage metadata, bounded recovery prompts, and shared review projection must
   not require or emit fixed white top, shorts, barefoot, skirt/dress
   prohibition, or any other wardrobe recipe.  Body source visibility may be
   requested only in scene-neutral terms needed to review body chain,
   stage-aware proportion, head-neck-shoulder continuity, torso/limb/joint
   plausibility, stance, ground contact, and cross-view parity.  This does not
   rewrite or invalidate historical active Body receipts.

The controlled modeling refresh gate is still separate: no modeling
regeneration, slot activation, Host/MCP/ImageGen, business record, or
downstream runtime behavior is authorized by this handoff or by the append-only
refresh entry alone.

## 9. Body refresh source-mode closure

The first body-source admission implementation (`caea911`) separated Face
Identity references from Body-owner evidence, and the follow-up
`strict_body_source_repair` closure (`05908f5`) correctly prevented
`user_described` or face-only inference from masquerading as observed Body
truth.  That observed-only wording is now narrowed: it applies to the
`reference_assisted` source mode only.  It must not be interpreted as a global
precondition that blocks Alchemy from generating Body Silhouette candidates
when no observed body reference is available.

New Body Silhouette refresh work must use a server-owned, closed source-mode
contract:

```text
body_refresh_source_mode:
  reference_assisted
  inference_first
```

The mode is resolved by the Character Card / Visual Asset Library owning
layer.  It is never accepted from client metadata, raw `body_facts`, a file
path, a filename, an output id, provider payload, or free prompt prose.

### 9.1 `reference_assisted`

`reference_assisted` is used only when the server resolver admits a ready
Body-only source for the current Body Silhouette refresh/card request.  The
source may be a similar-person full-body proportion reference supplied for
body modeling; it is not required to be, and must not be represented as, the
same person as the current Character Card subject.  Its reference admission
must be computed by the server and must prove all of the following:

- source class is `observed`;
- role is `body_proportion_reference`;
- `metadata.reference_truth_layer` is `body_proportion_truth`;
- consent or rights provenance is present;
- the source provenance is bound to the current Professional Character Card
  Body refresh/card request as Body-only proportion evidence, not as same-person
  identity evidence.

The admitted Body reference may be projected only as Body-owner evidence for
body scale, neck/shoulder transition, torso/limb proportion,
developmental-stage coherence, stance/ground contact, and cross-view support.
It is not Face Identity truth and must not lock wardrobe, pose, lighting,
camera, expression, background, scene, product identity, swimwear, poolside,
kidswear, E-Commerce, Photography, or General deliverable semantics.
The current subject's Face Identity remains owned by the existing Character
Card Face Identity references; a similar-person Body reference cannot replace,
override, or weaken those Face Identity references.

Client-provided `body_reference_admission`, raw metadata, user-described body
facts, paths, URLs, provider payloads, asset ids, or output ids cannot make a
request `reference_assisted` and cannot create observed Body truth.

### 9.2 `inference_first`

`inference_first` is the valid Body Silhouette modeling path when no admitted
Body reference is available.  It allows Alchemy to generate
`body.front_full`, `body.side_full`, and `body.rear_full` candidates from Face
Identity continuity plus server-owned body-model context and the universal Body
Silhouette source standard.

The minimum closed context for `inference_first` is:

- active Face Identity continuity references;
- the current Character Card subject boundary;
- server-owned age-stage/body-context if such typed context exists;
- otherwise a scene-neutral `system_inferred_body_model` context that does not
  claim a specific observed age, body measurement, body vector, or body truth.

`inference_first` must not carry `body_evidence_ids`,
`body_proportion_reference`, `body_proportion_truth`, observed source claims,
biometric vectors, raw user text, paths, URLs, provider payloads, asset ids, or
output ids as Body truth.  User-described body facts may remain ordinary
provenance/direction where older public contracts allow them, but they cannot
be injected into Provider prompts or elevated to certified Body evidence.

The success condition for `inference_first` is review proof, not source proof:
three-slot candidates may be generated, but a pending refresh may form only
after shared review, Body source-standard positive evidence, formal slot
receipts, and card-level cross-view parity all pass.  A generated image is not
an accepted Body slot by itself, and absence of an observed reference is not an
entry blocker for this mode.

### 9.3 Shared acceptance and compatibility rules

Both source modes must preserve:

1. Face Identity and Body Silhouette ownership separation.  Face references are
   identity continuity evidence, not body truth.
2. Existing active Body slots, historical receipts, and old readback records.
   They remain append-only readable and are not invalidated, migrated,
   recomputed, relabelled as observed, or overwritten by source-mode changes.
3. Append-only pending refresh state and explicit activation.  No source mode
   may replace active Body slots without a later activation gate.
4. Downstream General, Photography, and E-Commerce isolation.  Runtime
   body-only projection consumes active Body slots after activation; it does
   not choose the refresh source mode.
5. Provider cap and Provider role isolation.  `reference_assisted` may add one
   Body-only reference; `inference_first` may not fabricate one.
6. Scene-neutral source standards.  No six-year-old, swimwear, poolside,
   kidswear, E-Commerce, wardrobe, pose, lighting, camera, expression, or fixed
   head/body-ratio recipe is introduced.

`source_standard_evidence_missing` is a candidate-review proof failure.  It is
not the same as “observed Body reference missing.”  A candidate can fail
because shared review did not produce required Body source-standard evidence;
that failure must remain distinguishable from a `reference_assisted` source
admission failure.

Any older handoff wording that implied all strict Body Silhouette refreshes
require observed `body_proportion_reference` / `body_proportion_truth` is
superseded by this section.  Observed Body-only admission is required for
`reference_assisted`; it is not required for `inference_first`.

## 10. MCP Body materialization channel contract closure

The MCP materialization route uses the same Professional Character Card Body
Silhouette ownership rules as the Provider route.  The MCP handoff store is a
transport relay for a frozen canonical prompt and reference hashes; it does
not own Body source standards, Face Identity, candidate acceptance, or
activation.

The Body-owner MCP materialization channel contract is:

```text
contract_version:
  professional_body_silhouette_mcp_materialization_channel_v1
scope:
  professional_character_card_body_silhouette_mcp_materialization_only
source modes:
  inference_first
  reference_assisted
```

Allowed Body-owned channels are limited to:

- body proportion;
- body scale;
- neck/shoulder continuity;
- torso/limb relationship;
- developmental-stage body context;
- stance/ground contact;
- cross-view body parity.

The current Character Card Face Identity references remain identity-continuity
evidence only.  They may preserve the same person and approved hair-continuity
evidence, but they do not become Body truth, wardrobe truth, pose truth, scene
truth, lighting truth, camera truth, or downstream product truth.

All non-Body-owned channels must remain unspecified by the Body Silhouette MCP
handoff.  In particular, Body MCP handoff prompts and rendering contracts must
not author wardrobe, attire, formal or business styling, suit/headshot
language, facial expression, professional pose, scene, studio, lighting,
camera, background, product, General, Photography, or E-Commerce recipes.
Negative or scene-neutral wording that explicitly leaves those channels
unspecified is allowed as governance language; it is not evidence that the Body
handoff owns those channels.

The fail-closed boundary is intentionally two-layered:

1. The Body Silhouette planning/recovery contract must only ask the Brain or
   bounded recovery path for Body-owned channels.
2. The MCP materialization boundary must reject a stale frozen handoff before
   MCP handoff creation when the canonical prompt carries old wardrobe,
   formal/business, expression/professional-pose, or scene/studio channel
   findings.

This section supersedes any older Body MCP handoff behavior that allowed
`professional_body_silhouette_wardrobe_v1`, formal/business styling,
expression/professional-pose language, or studio/scene/camera/lighting recipe
to enter a new Body Silhouette MCP handoff.

This closure does not change the standard three-candidate requirement, shared
review, Body source-standard positive evidence, formal slot receipt,
card-level cross-view parity, pending refresh, explicit activation, downstream
General/Photography/E-Commerce projection, provider cap, or any real
Host/MCP/ImageGen authorization.  It authorizes no real generation by itself.

## 11. MCP stale-pending and Brain normal-prompt correction note

This note records a narrow correction model for the Body Silhouette MCP route.
It does not add a new Body source standard, prompt recipe, quality threshold, or
activation rule.

Observed mismatch:

1. A fresh `inference_first` Body Silhouette MCP refresh can fail before MCP
   handoff creation because the normal Brain canonical prompt still carries
   non-Body-owned channels such as scene/studio styling or expression/professional
   pose language.
2. A fresh Body refresh lifecycle can share the same MCP operation identity as a
   historical pending handoff for the same slot and candidate.  That makes the
   public evidence ambiguous: a stale pending handoff can look like the current
   lifecycle unless the refresh attempt/revision identity is server-owned and
   explicit.

Owning-layer correction boundaries:

- Brain normal planning metadata, canonical prompt context, bounded Body
  recovery, and provider-prompt finalization must all use the same Body-owner
  key: `professional_body_silhouette_source_contract`.  Body stages must not
  project the broad `professional_face_identity_quality_contract` into the
  frozen render context or Brain request metadata.  Historical Body records
  that stored Body-owned subcontracts under the Face key remain readable only
  by extracting those Body fields into the Body-owner contract shape.
- Body finalizer human-realism/naturalness receipts are audit receipts for
  whole-body plausibility and real-person material coherence inside the
  Body-owned source-standard scope.  They must not reintroduce expression,
  scene, studio, wardrobe/attire, camera, lighting, or style channel ownership
  into Body prompts.
- Brain normal canonical prompt finalization must use the same Body-owner
  channel contract as Body recovery and MCP materialization.  Body prompts may
  own body proportion, body scale, neck/shoulder continuity, torso/limb
  relationship, developmental-stage body context, stance/ground contact, and
  cross-view body parity.  Face references remain identity-continuity evidence
  only.  Non-Body channels remain unspecified.
- Face Identity and Expression Set prompt finalization keep the existing Face
  quality contract.  The Body correction must not remove or weaken Face-owned
  model-card/identity capabilities where those stages own them.
- MCP operation identity for Body refresh must include a server-owned refresh
  attempt/revision identity.  Two distinct refresh lifecycles for the same
  card/slot/candidate must not collide.  Within one server-issued attempt, the
  candidate request and any exact-current candidate resume request must produce
  a stable operation identity.  A new `refresh_body_silhouette()` invocation
  produces a new server-owned attempt identity; this note does not claim that a
  complete Body refresh-resume entry exists.  Historical exact-current resume
  behavior remains readable and compatible.
- Public evidence may record closed equality/hash/phase facts only.  It must
  not expose raw prompts, paths, URLs, provider payloads, asset IDs, output IDs,
  or raw MCP operation IDs.
- Adapter prompt-scope validation and MCP materialization findings are
  defense-in-depth boundaries.  They must catch stale non-Body channel drift
  before handoff creation, but they are not the source authority and must not be
  used to mask a Face/Body context projection defect.

This correction keeps the existing standard three-candidate requirement, shared
review, source-standard positive evidence, formal receipt, card-level
cross-view parity, pending refresh, and explicit activation authority.  It does
not authorize a real MCP/ImageGen run and does not permit clearing old pending
handoffs as a substitute for identity separation.

## 12. Request-scoped Body refresh presentation intent

This note records a narrow request-owned presentation contract for Professional
Character Card Body Silhouette refresh.  It exists because the Body source
standard correctly leaves non-Body-owned channels unspecified, while the
modeling-card presentation still needs a stable neutral display convention when
the user is reviewing front/side/rear body structure.

The closed contract is `body_refresh_presentation_intent` with
`contract_version=professional_body_refresh_presentation_intent_v1`.  It is
server-owned and may only be injected by the strict Professional Body
Silhouette refresh request/lifecycle.  Client metadata, raw body facts,
arbitrary dictionaries, unknown fields, wrong types, or the superseded
`professional_body_silhouette_wardrobe_v1` payload cannot create or override
this intent.

The only currently allowed declared values are:

- `top_presentation=short_sleeve_top`;
- `bottom_presentation=shorts`;
- `footwear_presentation=barefoot`.

These values are modeling-card presentation controls only.  They are not Body
proportion truth, not Face Identity truth, not age truth, not observed source
evidence, not Body source-standard proof, not formal receipt evidence, and not
activation authority.  They must not be copied into Character Card Body source
contracts, Body source admission, Face Identity evidence, shared Human Realism,
General, Photography, E-Commerce, ordinary MCP handoff, downstream body-only
projection, or business delivery records.

If the strict Body refresh request does not declare
`body_refresh_presentation_intent`, the MCP rendering contract must carry the
closed sentinel `status=unspecified`.  The system must not infer a fixed top,
bottom, or footwear presentation from unspecified state, and it must not revive
the old wardrobe contract to fill the gap.

This contract is compatible with both `inference_first` and
`reference_assisted` Body refresh source modes.  In `reference_assisted`, any
similar-person Body reference remains body-only proportion evidence and still
does not become current-person identity or presentation truth.  In
`inference_first`, the intent remains a request-scoped display constraint and
does not fabricate body truth.

All non-Body modules remain isolated.  Face Identity and Expression Set keep
their own stage contracts; General, Photography, and E-Commerce must not read
or require `body_refresh_presentation_intent`.  This note does not change the
standard three-candidate requirement, shared review, Body source-standard
positive evidence, formal slot receipt, card-level cross-view parity, pending
refresh, explicit activation, provider cap, Brain route, MCP route, or any
real generation authorization.
