# Doc147 — V3 Shared Human Expression Ownership and Authenticity Gate

## Status

Implementation specification. It extends the existing shared Human Realism
capability, Remote Brain signing, and shared pixel-review/retry path. It does
not add a template, a specialist route, a new provider, or a child/apparel
capability.

## Problem

Some generated people can be anatomically credible and conventionally
photorealistic while still being immediately recognizable as generative work:
an unrequested, polished, presentation-ready smile is reused as the default
answer to an underspecified human moment. The problem is not that smiling is
unreal. It is that a stock display expression can replace the individual,
situation-owned presence required by the image.

Doc144 already directs the Remote Brain not to fill an unspecified expression
with a default commercial presentation. The remaining gap is execution truth:
the frozen pixel-review contract presently verifies individual personhood and
photographic materiality, but does not separately require the reviewer to
decide whether the expression belongs to the visible situation.

## Architecture decision

Keep the existing path unchanged:

```text
frozen V3 intent / reference truth / capability plan
  -> Remote Central Brain authors whole-image direction
  -> Remote Brain canonical-prompt finalization
  -> Human Realism independent re-sign
  -> GPT Image 2 or the canonical Local MCP comparison relay
  -> shared vision/hybrid review
  -> normalized evidence only
  -> Remote Brain whole-direction rewrite for one existing bounded retry
  -> shared final-winner selection
```

No stage may locally choose an expression, infer a smile from text with a
rule, append a positive/negative expression phrase, or repair a face with a
keyword list.

## Fresh Human Realism contract

New enforced jobs use `v3_human_realism_semantic_v4`. Alongside the existing
personhood and photographic-material obligations, it freezes one orthogonal
semantic requirement:

```text
expression_ownership_requirement =
  situation_owned_unless_explicit_user_direction
```

Its meaning is deliberately narrow:

- An expression explicitly requested by the user remains user-owned and must
  be respected.
- When the user has not specified one, the Remote Brain must choose an
  expression/reaction that belongs to the person, action, attention and mood
  it authors for the complete image.
- An absent expression is intentional creative latitude, not a blank that
  must be filled with positive affect. Pleasantness of the setting or desired
  visual polish is not by itself a reason to invent a display smile, nor may
  the Brain invent a decorative action merely to justify one.
- It does not prohibit a smile, prescribe a substitute expression, inspect
  facial landmarks, or create an age-, culture-, apparel- or template-specific
  default.

The shared review vocabulary gains only the broad dimension
`human_expression_context`. It means the pixels do or do not support a
situation-owned expression. It is evidence for the Brain, never Provider
prompt text. Historical labels such as old smile-related review codes may be
read and normalized into this dimension for compatibility, but are not emitted
by new enforced contracts.

## Remote Brain duties

The Brain remains the sole owner of final renderer language.

1. In planning and canonical finalization, it reconciles the frozen expression
   ownership requirement with user intent, reference truth, setting, action,
   photographic mood and other resolved constraints.
   When expression is unspecified, it keeps the person ordinarily present
   unless an independently useful moment gives the affect a reason; it does
   not manufacture a pleasing expression to improve commercial presentation.
2. In `provider_prompt_human_naturalness_resign`, it retains a candidate only
   when its expression is user-authorized or visibly situation-owned. Otherwise
   it returns `rewritten` and authors a complete replacement prompt.
3. The local runtime validates the signed result and cardinality. It must not
   compare wording, attach an expression suffix, or decide whether a smile is
   allowed.

## Shared pixel-review duties

When the active Human Realism contract requires expression ownership, the
vision/hybrid reviewer must attest from pixels whether the visible expression
reads as a natural response within the frozen user goal and rendered setting,
rather than a generic display pose. It returns only:

```text
pass | retry_recommended | not_verifiable
```

and the frozen generic review dimensions. A missing, invalid, inconsistent or
metadata-only attestation remains non-certifying. `human_expression_context`
may cause the existing shared bounded retry, but cannot generate a local retry
phrase.

## Retry and selection

The existing one-retry limit and append-only history remain authoritative. A
retry carries normalized evidence into canonical-prompt finalization; the
Remote Brain rewrites the whole image direction and the independent re-sign
still applies. Final-winner selection consumes the existing shared review
truth. No second expression-specific retry, provider route, candidate store or
selection algorithm is introduced.

## Compatibility and isolation

- Historical v3 Human Realism records remain readable. They are not silently
  recertified as v4.
- The `hand_or_skin_detail` scope records `not_applicable`; it does not pretend
  that an absent face has an expression.
- General, E-Commerce and Photography receive the same shared capability when
  a real visible person is already activated. Their deliverable semantics do
  not change.
- Stylized/non-human requests remain outside the real-person contract unless
  the existing Remote Brain/capability activation evidence independently
  activates Human Realism.

## Explicit prohibitions

The implementation must not add:

- a child, kidswear, model, portrait, E-Commerce or Photography expression
  branch;
- smile/teeth/eye/mouth/face-shape regex matching or thresholds;
- a local expression classifier, prompt suffix, negative prompt, or retry
  wording;
- a static alternate-expression catalogue;
- a new Brain, Provider, review, retry, result-selection or storage path.

## Required regression and acceptance

1. Fresh enforced Human Realism freezes the v4 expression ownership contract
   and the generic expression-context review dimension.
2. The Remote Brain receives the requirement but no local expression recipe;
   an explicit user expression is preserved, while an unspecified default pose
   may be fully rewritten only by the Brain.
3. Vision/hybrid review treats a `human_expression_context` retry recommendation
   as normalized shared evidence with no renderer prose.
4. Missing/metadata-only review remains non-certifying.
5. Cover ordinary adult, young person, person/object interaction and low-key
   person contexts with the identical shared contract; prove General,
   E-Commerce and Photography isolation.
6. Run focused Human Realism/Brain/review/retry tests, Local MCP parity,
   complete V3 regression, static checks, and one controlled blue-dress
   comparison through the exact Brain-signed prompt/reference relay.

## Audit decision

Doc147 is a minimal shared contract enhancement. It treats expression as an
orthogonal semantic ownership concern, not as a collection of facial details.
The Remote Brain keeps creative judgement and the vision reviewer keeps pixel
verification; deterministic code only freezes, validates, transports and
audits those decisions.
