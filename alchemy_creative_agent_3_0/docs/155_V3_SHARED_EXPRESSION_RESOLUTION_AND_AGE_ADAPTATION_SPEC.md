# Doc155 — V3 Shared Expression Resolution and Age Adaptation

Status: implementation target for the shared Human Realism foundation

## 1. Purpose

The previous Human Realism contracts correctly rejected a generic, interchangeable
commercial smile, but real outputs still sometimes converged on the same polished
open-mouth presenter expression. This document tightens the semantic resolution
that the remote Brain must perform before it signs a canonical image direction.

The goal is not to ban smiling. The goal is to prevent a pleasant commercial
request from being silently rendered as the same showroom smile across people,
ages, and scenes.

## 2. Architecture ownership

This is a shared Foundation change. It is not a kidswear module, child-face
module, ecommerce recipe, photography recipe, or provider-specific prompt patch.

The runtime freezes one additional Human Realism semantic obligation:

```text
expression_resolution_requirement
  = individual_situation_not_stock_geometry
```

For a real visible person, the obligation means that a generic request such as
“gentle”, “natural”, “joyful”, or “friendly” is an emotional intention. The Brain
must decide the complete visible response from the person, attention, action,
timing, and situation. It must not infer a repeated open-mouth or tooth-showing
geometry merely because the frame is attractive, commercial, or front-facing.

An explicitly requested physical expression remains user-owned. A genuine smile
may pass when it belongs to the visible moment. The rule does not force a neutral
face and does not select from a fixed list of alternate expressions.

## 3. Brain and renderer boundary

The remote V3 Brain remains the author of the complete canonical provider prompt.
The shared runtime may freeze, validate, transport, and audit the semantic
contract, but it must not append expression wording, enumerate facial features,
choose a smile variant, classify a face with regex, or run a local expression
repair loop.

The shared pixel reviewer may return the existing broad
`human_expression_context` evidence when the result is a physically plausible
but interchangeable presenter smile. It must not expose a renderer patch or a
fixed replacement expression. Any bounded retry continues through the existing
Brain-owned whole-prompt rewrite path.

## 4. Age adaptation

Age is an explicit user/reference fact and remains governed by the existing
`identity_age_fidelity` and age-appropriate safety semantics. The same Human
Realism contract is used for adults, approximately ten-year-old children, and
approximately six-year-old children. The Brain adapts the complete person and
situation to the stated age; the runtime does not introduce an age-specific
prompt recipe or child-only expression branch.

The acceptance requirement is therefore comparative rather than lexical: with
the same scene conditions and only the requested age changed, the result must
remain age-appropriate while expression resolution continues to be owned by the
same shared semantic contract.

## 5. Compatibility and document authority

Docs 147, 152, and 153 remain historical evidence for expression ownership and
the hard review gate. Doc155 is the current refinement for expression resolution
and upgrades the live semantic contract from
`v3_human_realism_semantic_v5` to `v3_human_realism_semantic_v6` by adding the
single field above. Existing history remains readable; it is not silently
re-certified under the new contract.

No earlier document authorizes a local smile catalogue, structured facial prompt
stack, or child-specific branch. Any such interpretation is superseded by this
document and the Foundation governance in Docs 76, 77, 91, 94, and 153.

## 6. Acceptance matrix

The code and controlled visual evaluation must cover:

1. adult, approximately ten-year-old, and approximately six-year-old real people;
2. at least three materially different scenes, including commercial studio and
   ordinary outdoor context;
3. generic pleasant/gentle wording, where a smile remains allowed but a repeated
   presenter geometry is not accepted as the only interpretation;
4. an explicit physical smile request, which remains user-owned;
5. Brain-owned canonical prompt provenance and no local prompt additions;
6. shared vision/hybrid review and bounded retry, with metadata-only outputs
   withheld from certification.

The five-image comparison requested for this release reuses the four earlier
blue-dress studio conditions and the earlier garden condition, changes the age
to approximately six, and records the result as a comparative Human Realism
fixture. It is evidence for age adaptation and expression convergence; it is
not a new child-specific production gate.
