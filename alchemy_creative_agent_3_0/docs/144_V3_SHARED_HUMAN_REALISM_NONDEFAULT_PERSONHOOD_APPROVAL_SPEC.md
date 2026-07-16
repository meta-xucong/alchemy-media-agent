# Doc144 — V3 Shared Human Realism Non-default Personhood Approval

Status: **active shared-foundation refinement authority.** This document
calibrates the existing Doc139/142/143 Remote Brain re-signing decision. It
does not add a new capability, template, Provider, reviewer, retry loop,
reference channel, or demographic-specific route.

## 1. Controlled comparison finding

The Doc143 Local MCP comparisons used the same canonical prompt and reference
contract that the normal Provider route receives.

- An ordinary adult, face-visible sample showed substantially more believable
  photographic skin material than the earlier painterly/oily regression.
- The blue-dress young-person sample preserved the product and rendered a
  credible child, but still selected a familiar, commercially presentational
  smile/lower-face expression.

The latter is not a missing Human Realism activation, a children-specific
defect, or a reason to make a local expression recipe. The frozen capability,
two Remote Brain passes and reference admission were all present. The exposed
gap is narrower: a remote re-signer could formally approve a candidate that
uses a default polished portrait behaviour when the user did not actually
request that behaviour.

## 2. One universal approval rule

The existing `human_naturalness_decision` remains the only re-signing receipt:

```text
approved | rewritten
```

For every active Human Realism job, **approved** now has this high-level
meaning:

```text
The complete Brain-authored image direction already represents a particular
person naturally present in the user-owned situation. It does not use a
default commercial-presentational expression or universally beautified
portrait as a substitute for unspecified identity or expression.
```

If that bar is not met, only the Remote Brain may set `rewritten` and produce
a new complete, situation-owned renderer prompt. The runtime records and
binds that complete output; it never generates the replacement wording.

This rule is universal. It applies to a young person, adult, older person,
product-on-person scene, portrait, lifestyle scene or photography template in
exactly the same way. It preserves a deliberate smile, glamour treatment or
editorial pose whenever the user explicitly asks for one.

## 3. Explicit non-solutions

Doc144 prohibits the following shortcuts:

- child, teen, apparel, ethnicity, template or commercial-image branches;
- keyword/regex detection of smiles, mouth shape, facial geometry, age,
  beauty or skin features;
- local prompt suffixes, negative lists, pose/expression defaults, face
  scoring, image retouching or a second renderer call;
- treating the source garment as person identity truth;
- forcing an artificial imperfection in order to claim realism.

Without a portrait identity reference, a system cannot promise a particular
real individual. The requirement is instead that the Brain not silently fill
that missing identity with the same generic stock portrait. When a user
supplies a portrait reference, Doc93 identity ownership continues to govern.

## 4. Execution boundary

```text
frozen Human Realism semantic contract
-> Remote Brain canonical finalizer
-> existing independent Remote Brain re-signer
   (approve only if non-default personhood is already resolved;
    otherwise rewrite the complete prompt)
-> exact canonical materializer prompt
-> existing shared vision/hybrid review and bounded retry
```

The calibration is sent to the Brain both in its general operating authority
and immediately beside the re-signing response contract. This reduces the
chance that a large frozen context hides the decision standard. It is still a
semantic deliberation instruction, not renderer text, a prompt fragment or a
new structured creative field.

Doc143's pixel-review attestation and existing generic Human Realism issue
dimensions are unchanged. A local Codex-native MCP comparison remains
`conversation_only_not_certified`; it can demonstrate exact canonical-prompt
parity and qualitative direction, but it cannot replace the shared
vision/hybrid delivery verdict.

## 5. Required regressions and acceptance

1. The re-sign payload must state the high approval bar while carrying the
   first Brain candidate unchanged; no local rewrite mechanism may appear.
2. A remote `rewritten` response must remain the exact final prompt observed
   by the normal materializer and Local MCP relay.
3. Product-only, stylized and non-Human-Realism jobs must not gain a new
   re-sign path.
4. General, E-Commerce and Photography remain isolated from person-expression
   rules; they consume only the shared frozen result.
5. Re-run ordinary adult and blue-dress controlled comparisons through the
   same plan/finalize/re-sign boundary. Assess expression specificity and
   photographic material qualitatively; do not claim a certified visual
   verdict without the shared vision/hybrid route.

This refinement is accepted only when it improves the shared Brain decision
boundary without turning isolated visual symptoms into a brittle prompt list.

## 6. 2026-07-16 controlled status

The code-level closure is green: the focused Human Realism/review/retry
regression passed 105 tests, the complete V3 suite passed 779 tests, and the
Codex-native canonical prompt/reference parity suite passed 33 tests.

> **Doc147 compatibility note (fresh jobs):** Doc144's Brain-only
> non-default-personhood approval remains in force. Doc147 advances the
> frozen shared contract to v4 so the existing shared pixel-review path also
> attests expression ownership. It adds no local expression prompt logic.

The face-visible ordinary-adult Local MCP comparison is supportive, not
certifying: its canonical Brain plan used both signing stages and the output
showed camera-like facial and skin material without the earlier obvious
oily/painterly surface. The original blue-dress Local MCP comparison remains
the evidence for this document's gap: age, dress, hands and lighting were
credible, while the face still selected a familiar presentational smile.

After the Doc144 implementation, two bounded attempts to obtain a fresh
blue-dress Brain plan stopped before image generation because the remote Brain
returned an invalid response. Neither attempt created a renderer operation or
used a fallback. The next visual comparison is therefore explicitly pending a
fresh `llm_used=true` / `fallback_used=false` plan. It must use the same
authorized product reference and no local prompt workaround.

Safe transport diagnosis subsequently narrowed this external hold further.
The configured remote Brain is reachable and returned valid JSON for both a
text-only planning request and a simplified request with one reference-shaped
asset. The real blue-dress V3 request reached the `plan` stage with one
uploaded/reference asset and a roughly 6.3KB frozen payload, but the remote
model response failed JSON parsing with an `Expecting ',' delimiter` error.
No raw response, prompt, asset path, endpoint or credential was retained in
the record.

Doc145 now supplies a narrower shared transport remedy: before any accepted
Brain decision exists, the same frozen request may receive exactly one
serialization-only re-answer from the same remote Brain. It is not a local
syntax repair, a creative re-plan, or a renderer retry. The subsequent
controlled run completed the unchanged Doc144 path; its acceptance evidence is
recorded in Doc146. The remote route can still fail closed if the initial and
recovery answers are both unusable.

> **Fresh-contract note (Doc148):** Doc144's individual-person approval
> calibration remains in force. Fresh enforced contracts now use v5 to add a
> separate reference/user-owned complexion and scene-balance requirement; it
> does not create an age, apparel, or culture-specific rule.
