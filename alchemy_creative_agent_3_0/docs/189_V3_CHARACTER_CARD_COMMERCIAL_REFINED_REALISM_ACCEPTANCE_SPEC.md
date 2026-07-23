# Doc189: V3 Character Card Commercial-Refined Realism Acceptance

## Status and authority

```text
AUTHORITATIVE_CHARACTER_CARD_COMMERCIAL_REFINED_REALISM
COMMERCIAL_RETOUCH_IS_ALLOWED_WHEN_IDENTITY_AND_MATERIALITY_HOLD
NO_PRIVATE_PROVIDER_BRAIN_VISION_RETRY_OR_STORAGE
NO_STANDARD_GENERAL_ECOMMERCE_PHOTOGRAPHY_LEAKAGE
```

This document extends Docs178, 184, 185, 186, 187 and 188.

Doc188 still owns fixed Face Identity card framing, vertical 2:3 size parity,
plain white reference-card background, front-pose normalization, MCP/Provider
common materialization, and bounded resume. Doc189 supersedes only the narrow
reading that a commercially refined portrait is automatically too polished to
be valid identity evidence.

Current authority:

```text
Commercial refinement is allowed.
Identity drift, developmental-age drift, waxy/plastic smoothing, dirty finish,
wrong crop, wrong pose and prompt-owned channel violation are not allowed.
```

## 1. Problem found in validation

The Doc188 MCP validation proved that the transport layer was now mostly
correct: Remote Brain produced handoffs, MCP generated pixels, materialization
entered the same output/review/slot pipeline, and images were normalized to
the frozen 1024x1536 card size.

The remaining block was product calibration. Several images were already close
to commercially usable model-card photos, but the combined generation/review
language pushed too hard toward "evidence" and away from the desired
commercially refined finish. Shared Vision could then treat ordinary
high-key skin, cool-white complexion, subtle studio retouch, straight hair or
plain shirt continuity as AI polish/source leakage rather than acceptable
commercial identity-card presentation.

That is not the desired bar. A Professional Character Card is not a rough
documentary record. It is a reusable commercial visual asset.

## 2. Correct target

For Character Card Face Identity, the target is:

- clean, bright, high-key commercial studio reference-card photo;
- beautiful but not generic;
- refined but not plastic;
- fair/cool-white complexion through neutral white balance and clean exposure,
  not bleaching or oily/waxy smoothing;
- subtle professional retouch allowed when natural skin/hair/lip/eye material
  remains camera-observed;
- source identity feature relationships preserved before generic prettiness;
- user-owned developmental age preserved as a whole-person stage;
- fixed vertical 2:3 head, neck and upper-shoulder card crop;
- front slot straight enough for identity comparison, while allowing minor
  natural asymmetry.

## 3. Generation contract

The Brain-facing Character Card Face Identity contract must include a
commercial-refined realism policy:

```text
commercial_refinement_policy:
  clean_high_key_commercial_retouch_allowed_without_identity_or_materiality_loss

beauty_realism_balance:
  preserve_commercial_beauty_without_generic_ai_face_or_rough_documentary_skin

complexion_semantics:
  cool_white_or_fair_means_neutral_white_balance_luminous_clean_exposure_not_bleaching

source_channel_tolerance:
  plain_hair_and_neutral_wardrobe_continuity_allowed_when_it_supports_identity_comparison

front_pose_tolerance:
  minor_natural_asymmetry_allowed_but_not_nonfront_view
```

These fields are semantic contracts. They are not static prompt fragments and
must not become child-specific morphology recipes.

### 3.1 Later-slot prompt minimization

Doc186 remains authoritative for Character Card slot-delta prompt
minimization:

```text
The reference evidence chain stays intact.
Only repeated renderer-facing person-definition prose is minimized.
```

This means later Face Identity views, Expression Set slots and Body Silhouette
slots may still receive the approved source/winner reference evidence required
by the existing serial modeling design. They must not, however, repeatedly
copy the first `face.front` identity-definition prompt into each later
renderer prompt. Stable person facts such as identity, developmental stage,
complexion direction, material finish and age-appropriate presentation are
carried by approved references and typed contracts. The renderer-facing prompt
should mainly state the current slot delta: view angle, expression, or body
pose/view.

This is not a reference-budget reduction, not a local prompt rewrite, and not a
weaker review standard. It is a Brain-signed reference-led delta contract meant
to reduce moderation risk, token cost and prompt collisions while preserving
the original Professional Character Card design.

### 3.2 View-angle and card-shape acceptance

Face Identity slots are standardized modeling cards, not free portrait
variants. The following are hard slot-shape requirements:

- `face.front`: true straight-on front capture, not merely the source pose;
- `face.front_three_quarter`: clear left/front-side three-quarter /
  approximately 45-degree head view, with an observable left-side cue rather
  than a random 45-degree flip;
- `face.profile`: clear side-profile / approximately 90-degree head view;
- `face.reverse_three_quarter`: historical slot key, now superseded to mean
  the opposite right/front-side three-quarter / approximately 45-degree head
  view. It must not be a rear three-quarter, over-the-shoulder, or
  back-of-head view;
- `face.rear_head`: clear rear-head view;
- every Face Identity slot keeps the same vertical 2:3 card shape, white
  reference field, and head/neck/upper-shoulder crop;
- every non-front Face Identity slot keeps the approved front-card scale:
  same camera distance and head size, complete head-adjacent hair silhouette
  around the cranium, similar head-top margin, visible neck/upper
  shoulders/collar line, no tight face close-up and no half-body crop. Long
  hair may crop naturally below the upper shoulders instead of expanding the
  card into a looser torso/half-body frame.

The review dimension `pose_compliance` means face-view slot geometry for
Character Card Face Identity. It does not ask the reviewer to judge full-body
pose, body proportion or fashion-model posture; those belong to Body
Silhouette. Missing or low face-view `pose_compliance` must fail the candidate
even when identity and beauty are otherwise strong.

## 4. Shared Vision calibration

Shared Vision must not fail a Character Card Face Identity output solely
because it has:

- clean commercial skin;
- high-key white background;
- cool-white or fair commercial complexion;
- subtle studio retouch;
- plain shirt or hair continuity that helps identity comparison;
- small natural facial asymmetry in an otherwise front-facing card.

Shared Vision must still fail:

- recognizably different person;
- distinctive feature loss;
- age/developmental-stage drift;
- waxy, plastic, poreless, smeared or dirty skin/hair/detail;
- doll-like child rendering;
- non-front pose for `standard_front`;
- wrong crop, wrong background, or prompt-owned channel violation.

## 5. Host acceptance

The Product API host still requires verified shared Vision output and a
`pass`/`warning` verdict. It must not convert unverified pixels, fail-final
pixels, or private local judgments into accepted Character Card slots.

The extra Character Card gate should be balanced:

- same-person readability and distinctive-feature readability remain primary;
- visual and technical finish must be commercial-grade, but not artificially
  set to near-perfect 0.96 thresholds;
- human realism means "no plastic/smeared AI output", not "rough skin";
- prompt-owned view/crop/background obedience is required;
- face-view `pose_compliance` is required for every Face Identity slot;
- front-pose compliance tolerates small natural asymmetry but not a turned
  face.

## 6. Non-goals

This change does not:

- alter Standard Mode;
- alter General, E-Commerce or Photography deliverable logic;
- create a second Provider, Brain, Vision, retry or storage path;
- bypass shared Vision;
- activate any asset without reviewed winner and user confirmation;
- introduce a child-only hardcoded recipe.

## 7. Acceptance

1. Focused Character Card/Professional tests pass.
2. Provider contract tests pass.
3. Compile/static checks pass.
4. Fresh MCP validation from the authorized source image reaches Brain,
   materializes 1024x1536 images, records shared Vision receipts, and either
   selects a `face.front` winner or reports a real pixel-quality blocker.
