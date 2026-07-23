# Doc197 — Character Card Expression Slot-Delta Recovery

Date: 2026-07-24

## 1. Problem

Fresh MCP validation after Doc196 correctly requested the new Professional
Character Card positive slot, `expression.laugh`, but no image handoff was
created because the Remote Brain timed out before returning a canonical
provider prompt.

The failure was pre-materialization:

- slot target was correct: `expression.laugh`;
- request size was small;
- only one approved `face.front` reference was used;
- no Provider/MCP pixel request was sent;
- no shared Vision verdict existed.

Therefore this is not an image quality failure and not a policy rejection. It
is a missing recovery seam for reference-led Character Card expression slots.

## 2. Design authority

This document supersedes any older Character Card wording that implies every
post-front slot must wait indefinitely for a fresh Remote Brain canonical
prompt before a materialization handoff can exist.

The updated rule is:

```text
Remote Brain owns creative semantics by default.
For already-frozen Character Card derivative slots, a bounded reference-led
slot-delta recovery may create one concise canonical prompt if Remote Brain
times out, but pixels still must pass the same Provider/MCP store and shared
Vision/review gate.
```

This is not a second Brain, a local reviewer, or a template-specific quality
shortcut.

## 3. Scope

Allowed:

- Professional Character Card only;
- `professional_character_card_preparation=true`;
- `stage=expression_set`;
- slot keys:
  - `expression.laugh`;
  - explicit optional `expression.smile`;
  - `expression.anger`;
  - `expression.sad`;
- exactly one current output request;
- at least one approved `face.front` reference asset;
- shared `reference_led_slot_delta_contract.slot_delta_type=expression`;
- shared Provider or MCP materialization;
- shared Vision/expression review receipt gate.

Forbidden:

- General / E-Commerce / Photography fallback;
- first identity-defining face.front recovery;
- relabeling old `expression.smile` candidates as `expression.laugh`;
- starting anger/sad/body before laugh acceptance in the current validation;
- accepting a prompt-level approval as a pixel-level expression pass.

## 4. Prompt recovery contract

The recovered prompt is intentionally short. It inherits the approved
`face.front` card as the source of:

- identity;
- card framing;
- camera distance;
- crop;
- background treatment;
- lighting direction and white balance;
- complexion channel;
- wardrobe/style channel;
- visual finish;
- skin/material continuity.

The recovery layer must not write case-specific aesthetic language such as
cool/fair complexion, bright commercial lighting, child-only styling bans, or
any fixed mood. Those channels are owned by the approved `face.front` winner
and the current request. This keeps Doc197 compatible with adult, teen, child,
warm-toned, low-key, editorial, and commercial-clean cards without turning the
current six-year-old validation case into a shared default recipe.

It changes only:

- facial expression;
- very small natural head/shoulder energy.

For `expression.laugh`, the intended positive slot is a medium-arousal amused
keyframe with engaged gaze, periocular affect, cheek/jaw participation,
natural mouth opening or age-appropriate teeth visibility, and slight
spontaneous asymmetry. It must not collapse into a polite smile or neutral
face.

## 5. Review and receipt

Recovery only creates a canonical prompt. It does not select a winner.

Every resulting Provider/MCP artifact must still pass the existing shared
Character Card stage path:

```text
canonical prompt
  -> Provider/MCP materialization
  -> output store
  -> shared Vision / affective-expression review
  -> structured receipt projection
  -> Character Card slot acceptance
```

For laugh, the shared expression receipt remains mandatory. Mouth-only,
detached-gaze, frozen-periocular, framing-drift, or neutral-collapse evidence
must block the slot.

## 6. Compatibility

- `expression.laugh` remains the Professional default positive slot.
- Old `expression.smile` data remains readable as legacy/stale history.
- Explicit user-requested smile can still be prepared as an optional single
  slot, but cannot satisfy or activate `expression.laugh`.
- Provider and MCP remain equivalent materialization channels.

## 7. Tests

Doc197 adds regression coverage for:

- `expression.laugh` Brain timeout recovery;
- explicit smile recovery without becoming laugh;
- Character Card-only transport timeout;
- fail-closed behavior when the approved front reference is missing.
- cross-age / cross-style leakage prevention for recovered expression prompts;
- face-slot recovery prompts inheriting front-card style channels instead of
  hard-coding child, cool-fair, bright-light, or commercial-clean wording.
