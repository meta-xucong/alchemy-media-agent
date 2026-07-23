# Doc199 — Character Card Expression Shared Vision Contract

Date: 2026-07-24

## 1. Problem

After Doc198 fixed MCP candidate prompt/reference parity, the fresh
`expression.laugh` artifact could be consumed by the workflow, but the first
candidate was rejected by shared review as `fail_retryable` with broad issue
codes:

```text
human_expression_context
professional_pose_noncompliance
```

The generated image was visually a real open-mouth laugh candidate with strong
identity continuity and high technical quality. The important discovery was
not that this single image must pass. The discovery was that the real Vision
contract did not ask for the expression-specific dimensions introduced by
Doc196.

## 2. Root cause

`ProfessionalModeRuntimeBridge.character_card_stage_metadata()` already carries
the `laugh_intent_contract` and `expression_framing_contract`.

However, shared Vision's Professional review projection only exposed the
generic face identity dimensions:

- identity readability;
- developmental-age coherence;
- human realism;
- prompt-owned channel obedience;
- pose compliance;
- visual quality.

It did not expose:

- mouth-eye coherence;
- gaze engagement;
- periocular affect;
- cheek/jaw coupling;
- jaw relaxation;
- arousal/intensity coherence;
- spontaneity/asymmetry;
- expression age coherence;
- expression identity preservation;
- front-card expression framing parity and deltas.

As a result, real review could collapse a laugh slot into generic pose or
human-expression-context findings rather than producing the structured
affective-expression receipt that Character Card slot acceptance requires.

## 3. Correct contract

For `scope=character_card_expression_set` and a `laugh_intent_contract`,
`active_review_contract()` must expose the foundation-owned expression review
schema to Vision:

- score dimensions come from shared `expression_review.py` constants;
- blocking issue codes come from the same foundation module;
- face.front framing delta dimensions are listed explicitly;
- the Professional review prompt must explain that natural mouth opening,
  age-coherent teeth visibility, cheek lift, and small head/shoulder energy can
  be correct expression evidence.

For expression slots, `pose_compliance` must not mean "do not change the
neutral face." It means the reference card keeps comparable face.front scale,
crop, head-top margin, eye-line, shoulder span, background treatment,
lighting/white-balance continuity, and identity readability.

## 4. Scope

This is a shared Vision contract projection fix:

- no new Provider;
- no new reviewer;
- no private Character Card scoring;
- no prompt-generation retry increase;
- no relaxation of laugh receipt gates.

Character Card still consumes the shared `AffectiveExpressionReviewReceipt`;
Provider and MCP still feed the same output metadata and review pipeline.

## 5. Tests

Doc199 adds coverage that:

- `active_review_contract()` exposes laugh expression dimensions and issue
  codes to shared Vision;
- the enforced inspection prompt distinguishes valid laugh affect from generic
  pose failure while still preserving the face.front card skeleton.
