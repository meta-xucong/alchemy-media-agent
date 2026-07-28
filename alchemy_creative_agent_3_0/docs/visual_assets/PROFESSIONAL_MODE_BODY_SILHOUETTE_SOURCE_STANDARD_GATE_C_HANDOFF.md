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

## 9. Strict refresh source-admission closure

The first body-source admission implementation (`caea911`) separated Face
Identity references from Body-owner evidence, but its strict refresh path still
accepted `user_described` provenance.  That wording and behavior are narrowed
by the follow-up `strict_body_source_repair` source-admission closure
(`05908f5`): a strict body-proportion repair refresh may certify only a
server-resolved `observed` source that is ready and projected as
`body_proportion_reference` with `body_proportion_truth`.

This is a source-authority rule, not a prompt recipe:

1. `brain_inferred` and `user_described` remain readable historical/public
   provenance classes and may still be used by ordinary non-certifying
   `prepare_body_silhouette` flows where existing compatibility allows them.
   They do not provide approved body truth for strict body-proportion repair.
2. `user_described` body facts are direction/provenance only.  Raw body facts,
   prompt prose, paths, URLs, provider payloads, asset ids, or biometric
   vectors must not become Provider-facing body evidence and must not be used
   to form an activation-certifiable strict refresh.
3. A strict refresh without a server-resolved ready Body-only source must
   fail closed before generation/review.  It must not create body candidates,
   pending refresh winners, formal activation eligibility, or downstream
   product-image body certification.
4. Observed strict refresh input must keep Body and Face ownership separate:
   the Body source may enter only as `body_proportion_reference` /
   `body_proportion_truth`, while Face Identity references remain identity
   references.  A legacy or generic `full_body_reference`, `body_reference`, or
   `body_full_reference` is not enough for strict body-proportion repair unless
   it is first resolved by the server into the closed Body-only truth role.
5. Existing active Body slots, historical receipts, and old readback records
   are not invalidated, migrated, recomputed, or rewritten by this stricter
   rule.  The new fail-closed behavior applies to new strict refresh attempts
   and their candidate/winner formation only.

Any older handoff wording that implied a broad refresh could be certified from
`user_described` or face-only inference is superseded by this section.  The
section does not add runtime grade, commercial certification, scene-specific
age/wardrobe/poolside/E-Commerce rules, Provider cap changes, downstream
projection changes, or activation authority.
