# Doc196: V3 Character Card Laugh Positive Expression Migration

Status: design recorded; implementation must not resume image generation until the focused contract tests exist and pass.

## Why this exists

The Professional Character Card Expression Set previously treated `expression.smile` as the default positive expression. Fresh MCP validation showed that this is a weak default for a reusable modeling card:

- a polite smile is often too close to `expression.neutral`;
- mouth-only smiles can pass superficial visual quality while lacking emotional value;
- downstream video and motion use needs a stronger positive keyframe than a static social smile;
- retrying with more words such as "more smile" or "childlike innocence" masks the root contract problem.

The product direction is therefore:

```text
Professional Character Card default positive deliverable = expression.laugh.
General user-requested smile remains supported as a lower-intensity expression intent.
```

This is a contract migration, not a global mechanical rename.

## Current frozen validation state

Fresh validation root:

```text
.controlled-validation/character-card-mcp-standard-modeling-20260722-doc189-fresh
```

Current official Character Card state:

- Face Identity: active, with seven official slots written.
- Expression Set: not accepted.
- Body Silhouette: not started.
- Current positive-expression artifacts and handoffs were produced under the old `expression.smile` contract and are frozen as historical evidence only.

Frozen smile evidence includes:

- `mcp_handoff_7802dabab0`
- `mcp_handoff_8f0421e5a3`
- generated MCP artifacts under `.controlled-validation/.../mcp-artifacts/`

These smile candidates must not be promoted, relabeled, or reused as `expression.laugh` winners. Append-only history may show them as superseded/stale after migration. They are specifically non-count failed evidence for the neutral-collapse/mouth-only-smile regression: the canonical prompt still targeted a gentle smile, but the pixels read close to neutral, with no reliable mouth-eye/periocular laugh evidence.

The last observed blocked status was:

```text
stage=expression_set
slot=expression.smile
failure=character_card_stage_prompt_contract_invalid
official pending_handoffs=[]
```

This is not a reason to keep retrying smile. It is evidence that the old default positive slot and resume/prompt-contract assumptions need to be migrated.

## Scope ownership

Follow the repository foundation-vs-specialized governance:

- V3 foundation owns shared affective-expression quality, Human Realism interaction, cross-channel expression coherence, anti-fake-expression review, candidate comparison, bounded repair, and Provider/MCP-equivalent receipts.
- The concrete expression receipt projection lives in the shared visual-cluster foundation layer (`shared_capabilities.visual_cluster.expression_review`). It owns score dimensions, blocking issue-code projection, evidence-code projection, and `face.front` framing-delta tolerance for positive expression receipts.
- Age handling is an auxiliary condition inside shared Human Realism and expression quality. It must not become a child-specific shared branch or a case recipe.
- Character Card owns the Professional deliverable map and slot lifecycle only. It may request `expression.laugh` as the default positive slot, but it must not add a private Provider, Brain, Vision, review, scoring, or retry path.
- Product API Host may adapt shared review output to Character Card slot requests, but it must not define laugh-specific score floors, expression issue gates, or framing tolerances. It must consume the shared receipt and pass receipt evidence/issue codes through losslessly.
- User-uploaded child references may inform abstract expression evidence and age coherence, but must not become a second identity reference, hair lock, clothing lock, or local prompt recipe.

## Slot migration

New Professional Character Card default Expression Set:

```text
expression.neutral
expression.laugh
expression.anger
expression.sad
```

`expression.smile` becomes:

- a supported non-default expression intent when a user explicitly requests it;
- a legacy readable slot for older cards and serialized metadata;
- a superseded/stale historical artifact when it belongs to an interrupted old Professional default run.

New Brain, Provider, MCP, route, lifecycle, and frontend default paths must not emit `expression.smile` as the Professional positive slot.

Compatibility boundary:

- Old cards containing `expression.smile` remain readable.
- Old public projections may label historical smile as legacy/superseded.
- Old smile output must not satisfy a new `expression.laugh` activation requirement.
- A user-explicit `expression=smile` request uses a single-slot extension path. It may write `expression.smile` as optional history, but it does not run the default Professional Expression Set and it cannot satisfy or replace `expression.laugh`.
- Migration must not alter Standard Mode, General, E-Commerce, Photography, ordinary Anchor Pack, or user-authored explicit smile prompts.

## Laugh intent contract

`laugh` is not a fixed big-mouth pose. It is a positive affect continuum suitable for a static keyframe:

- `intensity`: restrained / moderate / high
- `arousal`: low-mid / mid / high
- `phase`: onset / peak / release
- `spontaneity`: posed / natural / candid-like
- `social_context`: camera-aware / interaction-aware / performance-aware
- `gaze_engagement`
- `periocular_affect`
- `lower_lid_cheek_coupling`
- `mouth_corner_lift`
- `lip_parting`
- `teeth_visibility`
- `jaw_relaxation`
- `brow_state`
- `head_pose_energy`
- `age_coherence`
- `identity_preservation`
- `style_mood_owned_by_prompt`
- `video_motion_hint`

For the current six-year-old validation case, the target is:

```text
mid-arousal naturally amused laugh, not an exaggerated open-mouth laugh.
```

The image should show engaged eyes, mild lower-lid and cheek participation, relaxed jaw, natural asymmetry, appropriate teeth/lip state, and a small amount of head/body energy while preserving the six-year-old identity and commercial refined quality.

## Framing contract

Every Expression Set output must inherit the approved `face.front` modeling-card skeleton:

- `1024x1536` / vertical `2:3` card format;
- clean white studio background;
- the same camera distance and lens-feel family;
- the same head, neck, and upper-shoulder crop boundary;
- comparable subject scale;
- comparable eye-line and center position;
- comparable lighting and white balance.

Expression Set may change only:

- facial affect;
- small natural head/shoulder micro-energy needed by the expression;
- expression-dependent mouth, cheek, jaw, eye, brow and gaze behavior.

Expression Set must not drift into:

- full-body or half-body cards;
- side-body or profile pose;
- tilted theatrical body action;
- copied framing from user-provided reference examples;
- different background, lighting, color temperature, wardrobe, or scene.

For each candidate, the shared receipt should record normalized framing evidence:

- `face_area_ratio`;
- `top_margin`;
- `bottom_margin`;
- `eye_line`;
- `center_x`;
- `shoulder_span`;
- `head_yaw`;
- `head_pitch`;
- `framing_delta_from_neutral_front`;

The Character Card Host consumes these as shared receipt deltas, not as local
pixel scoring.  The normalized projection must expose:

- `face_area_delta_from_front`;
- `top_margin_delta_from_front`;
- `bottom_margin_delta_from_front`;
- `eye_line_delta_from_front`;
- `center_x_delta_from_front`;
- `shoulder_span_delta_from_front`;
- `head_yaw_delta_from_front`;
- `head_pitch_delta_from_front`.

Missing delta receipt fields fail closed as
`professional_character_card_expression_framing_receipt_missing`.  Deltas
outside the Professional front-card tolerance fail as
`professional_character_card_expression_framing_drift`.

Framing drift outside the slot tolerance must fail or receive at most one bounded local repair through the existing shared retry path. The framing check must use the neutral `face.front` winner as the only baseline. It must not project unrelated expression-reference framing onto the card.

## Reference example abstraction rule

Human reference examples used for expression analysis are not identity, hair, wardrobe, lighting, background, crop, or composition references.

They may provide abstract expression evidence only:

- medium-intensity laugh: engaged gaze, mild lower-lid/cheek coupling, moderate teeth/lip state, relaxed jaw;
- high-arousal laugh: stronger mouth opening, brighter eyes, and body-energy tendency as a separate intensity endpoint;
- age-coherent child expression: lively attention without adultized presenter expression or plastic symmetry.

The current six-year-old card starts with a medium-intensity laugh keyframe inside the locked front-card framing. High-arousal laugh can be a later explicit variant, not the default positive slot.

## Calibration harness before fresh validation

Before any new real MCP handoff is started, add a reproducible calibration harness that:

1. uses the active `face.front` neutral winner as the only baseline;
2. freezes framing, identity, lighting, white balance, and crop;
3. varies only structured laugh intent: intensity, arousal, and phase;
4. allows at most three candidates and one bounded repair;
5. records prompt hash, framing receipt, expression evidence receipt, and shared human/vision verdict;
6. covers at least three materially different cases before relying on the six-year-old fixture:
   - adult male;
   - adult female;
   - child.

If mouth-eye coherence, periocular/gaze affect, cheek/jaw coupling, and laugh arousal/phase evidence are not established, the candidate must fail even when overall visual quality or prompt-level review is approved.

## Shared review and receipt requirements

Provider and MCP must share one review/winner/receipt path.

The expression review receipt must project losslessly into Character Card slot acceptance and include evidence for:

- `mouth_eye_coherence`
- `gaze_engagement`
- `periocular_affect`
- `cheek_lift`
- `jaw_relaxation`
- `arousal_intensity_coherence`
- `spontaneity_asymmetry`
- `age_coherence`
- `expression_identity_preservation`
- `video_motion_hint`

Issue codes must include at least:

- `mouth_only_smile`
- `detached_gaze`
- `frozen_periocular_region`
- `plastic_expression_symmetry`
- `adultized_child_expression`
- `laugh_intensity_mismatch`
- `laugh_phase_unclear`

A candidate must not become `expression.laugh` winner when overall visual quality is high but mouth-eye coherence, gaze engagement, or periocular affect evidence is missing. The reviewer must use the neutral `face.front` baseline as a delta reference instead of applying fixed absolute facial geometry.

Eye narrowing is not a universal hard gate. Age, eye shape, laugh intensity, phase, and requested style determine whether lower-lid/periocular evidence is sufficient.

The shared expression receipt must remain structured.  It cannot be flattened
only into `evidence_codes`.  Public review and stage receipts must preserve:

- `owner=v3_shared_visual_cluster`;
- `contract_version=v3_affective_expression_review_receipt_v1`;
- `status`;
- `expression`;
- `framing_baseline=face.front`;
- `evidence_codes`;
- `issue_codes`;
- `score_dimensions`;
- `framing_delta_dimensions`.

Provider and MCP materialization paths must round-trip the same receipt shape
through candidate review, slot acceptance, and stage-level
`CharacterCardSharedRuntimeReceipt`.

## Required implementation plan

1. Add focused contract tests before resuming generation:
   - new Professional cards default to `expression.laugh`, not `expression.smile`;
   - legacy cards with `expression.smile` remain readable;
   - old smile candidates cannot activate `expression.laugh`;
   - explicit user-requested smile remains supported outside the Professional default positive slot;
   - explicit user-requested smile has a callable single-slot service/Host path and cannot satisfy laugh activation;
   - Provider and MCP both pass the same laugh intent and review receipt fields;
   - Character Card Host cannot write a laugh winner if shared expression evidence reports mouth-only or detached-gaze issues.
   - frozen candidate2/3 style neutral-collapse evidence remains append-only history and cannot be counted as a current positive-expression slot.
2. Migrate Character Card slot constants, labels, lifecycle checks, resume logic, public status projection, and frontend status labels.
3. Extend the shared expression/Human Realism contract in the foundation layer, not in Character Card local recipes.
4. Add receipt projection tests for laugh evidence and issue codes.
5. Add stale/superseded handling for interrupted smile handoffs and artifacts.
6. Run focused Character Card, Professional, Provider/MCP, compile, frontend syntax, and diff checks.
7. Only after tests pass, restart fresh MCP validation from the Expression Set positive slot as `expression.laugh`.

## Migration checklist

The migration is complete only when every row below has a focused test:

| Layer | Required change | Non-regression proof |
| --- | --- | --- |
| Character Card model | New default expression slots expose `neutral/laugh/anger/sad`; legacy `smile` remains readable as stale history. | New card has no default smile; legacy smile card validates. |
| Character Card lifecycle | Activation requires current default slots only; stale `smile` cannot satisfy `laugh`. | Old smile winner plus missing laugh still blocks activation. |
| Expression request contract | New default positive request is `expression.laugh`; explicit `expression.smile` remains valid only when user-owned. | Default prepare loop emits laugh; explicit smile request still validates. |
| Explicit smile path | User-requested smile uses a single-slot extension path and does not run the default Expression Set. | Service/lifecycle test writes `expression.smile` while `expression.laugh` remains empty and activation still fails. |
| Shared Host intent | Host provides laugh intent, not smile intent, for Professional positive slot. | Host slot-intent map has laugh/anger/sad and no default smile. |
| Brain context | Laugh/framing contracts are injected only for Professional Character Card expression stage. | General requests do not receive Character Card laugh/framing context. |
| Brain adapter scope check | Final prompt must match the requested expression slot and reject neutral prompt for laugh. | Laugh prompt passes; neutral/old smile prompt fails for laugh slot. |
| MCP prompt freshness | MCP resume accepts laugh handoffs and rejects stale smile handoffs for the laugh slot. | `_character_card_stage_mcp_prompt_current` distinguishes laugh from smile. |
| Shared review receipt | Shared Vision score card and issue codes are losslessly projected into expression evidence codes and blocking issue codes. | Laugh candidate cannot pass without expression evidence; mouth-only/neutral collapse blocks. |
| Structured receipt round-trip | Candidate review and stage receipt preserve the shared expression receipt object, not only string evidence codes. | Review-to-stage round-trip test asserts owner/status/score/framing dimensions survive for Provider/MCP-equivalent paths. |
| Framing receipt | Expression candidates inherit the `face.front` card skeleton and expose framing parity plus numeric delta evidence. | Framing baseline is `face.front`; missing delta receipt fails closed; over-tolerance delta blocks or triggers bounded repair. |
| Governance placement | Positive-expression evidence, score floors, issue mapping, and framing delta tolerance stay in shared visual-cluster foundation. | Source-level regression fails if Character Card or Product Host reintroduces private laugh scoring/gating. |
| Frontend projection | UI labels the positive default as laugh and treats smile as legacy/history, not a current required card slot. | Static frontend test shows `expression.laugh` and no default `expression.smile` slot. |
| Validation harness | Adult male, adult female, and child cases use the same shared laugh evidence and framing receipt contract. | Materially different fixtures vary identity/age intent and scores while asserting the same evidence-code set and gate behavior, with no child-specific branch. |

## Explicit non-goals

- Do not continue materializing `expression.smile` pending handoffs.
- Do not relabel any smile candidate as laugh.
- Do not start anger, sad, or body before the laugh migration is tested.
- Do not create child-specific shared prompt recipes.
- Do not add private Provider, Brain, Vision, review, retry, or storage paths.
- Do not weaken shared Vision or the Character Card receipt gate.

## Superseded/conflicting prior docs

Doc178 introduced the Character Card module and its original Expression Set slot map. Any Doc178 language implying `expression.smile` is the default Professional positive expression is superseded by this document.

Doc182/Doc187/Doc195 resume and MCP handoff pacing rules still apply, but any examples or expectations that name `expression.smile` as the default positive slot must be treated as legacy-only after this migration.

Doc152/Doc153 shared smile authenticity remains valid for ordinary user-requested smiles. It is not a default Professional Character Card deliverable map.
