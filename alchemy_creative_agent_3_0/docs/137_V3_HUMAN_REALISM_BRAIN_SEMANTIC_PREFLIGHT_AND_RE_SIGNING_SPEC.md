# Doc137 — V3 Human Realism Brain Semantic Preflight and Re-signing

Status: **active shared-foundation implementation authority.**

This document extends Docs 91–96, 128, 134–136. It corrects the remaining
quality gap observed in the controlled blue-dress Local MCP comparison. It
does not create a child, apparel, E-Commerce, Photography, or General
Template-specific creative route.

## 1. Finding

The blue-dress comparison reached the correct forward boundary:

```text
admitted product truth
-> remote Brain planning
-> enforced Human Realism activation
-> typed Human Realism semantic contract
-> remote Brain canonical Provider prompt
-> exact Local MCP prompt/reference relay
```

The generated image was age-appropriate, photographic, and materially more
coherent than the historical result. It nevertheless retained a common
synthetic-commercial tendency: face and skin were overly regular and smooth,
while the garment and overall composition were only approximately faithful.

This is not evidence that the garment's illustrated surface turned the whole
image cartoon. Nor is it a reason to append face, hand, skin, child, camera,
or product keyword lists after planning. The remaining gap is that the final
Brain signer had a typed obligation but no required, auditable confirmation
that it had silently assessed the *whole image* against that obligation before
approving the renderer-facing sentence.

## 2. Non-negotiable ownership rule

```text
Frozen facts and shared semantic obligations
-> Brain silently evaluates whole-image plausibility
-> Brain writes and approves one complete canonical prompt
-> Provider/MCP relays that exact string unchanged
```

Only the remote Brain may write, revise, or approve renderer-facing creative
language. The shared runtime may validate a typed sign-off receipt, preserve
facts and references, and block an incomplete answer. It must never translate
Human Realism, reviewer findings, or product facts into a local prompt patch.

## 3. Semantic preflight contract

When an enforced plan actively contains `human_realism`, final Brain signing
must include a `final_prompt_semantic_preflight` requirement. It is a small,
non-creative control contract:

```json
{
  "required": true,
  "scope": "whole_image_human_photographic_plausibility",
  "owner": "remote_v3_llm_brain",
  "revision_mode": "rewrite_complete_canonical_prompt"
}
```

Before it returns a prompt, the Brain must silently reconcile the active
Human Realism contract with the user direction, admitted references and
frozen facts. The preflight is holistic: age/reference truth, natural human
presence, physical scene integration, and the requested photographic mood
must work together. It is not a renderer checklist and it must not require
the Brain to echo internal axes, issue codes, or safety scaffolding.

The Brain returns one audit-only receipt per output:

```json
{
  "output_index": 1,
  "prompt": "one complete Brain-authored natural-language image instruction",
  "review_status": "approved",
  "semantic_preflight_status": "approved"
}
```

For a new enforced Human Realism job, missing, duplicate, mismatched or
non-approved receipts block before materialization with
`human_realism_semantic_preflight_missing`. A defaulted model field is not
enough: the remote JSON response must explicitly contain the receipt. Legacy
records remain readable without it and cannot be re-certified by this rule.

## 4. Retry and pixel-review boundary

When a vision/hybrid review requests the one bounded retry, the retry carries
the frozen Human Realism contract and normalized review dimensions as
non-creative evidence. The Brain performs the same semantic preflight again,
then rewrites the complete canonical prompt if it can resolve the observed
whole-image problem. Local code may not append repair prose, translate a
dimension into a word list, or reuse the previous prompt with a suffix.

`metadata_only` and Local MCP remain non-certifying. Local MCP may prove
canonical prompt/reference parity and support a controlled visual comparison,
but it cannot produce a Project delivery, pixel-review verdict, retry history
or production-Gate credit.

## 5. Product coverage is separate from Human Realism

Human Realism improves how a visible person is rendered. It does not invent a
product framing requirement. A complete garment view, unobscured construction
evidence, or multi-output coverage must come from explicit user intent or the
selected specialized template's deliverable contract.

The blue-dress comparison asked for a mid-shot. Its partial lower-skirt
coverage is therefore a product-intent limitation of that request, not a
reason to add product-crop recipes to the shared human capability.

## 6. Prohibited remedies

The following are prohibited in the forward path:

- local prompt suffixes such as skin, pore, hand, smile, face, age, camera or
  garment word bundles;
- child/kidswear-specific prompt branches, review routes or Providers;
- regex/keyword results becoming a renderer style decision;
- deterministic selection of facial asymmetry, pose, crop, lighting or
  expression;
- local interpretation of a visual issue into retry language;
- treating an audit receipt as a pixel-quality certification.

Evidence admission may still recognize a direct visible-person or explicit
no-person declaration. It cannot own creative wording or override the remote
Brain's frozen rendering intent.

## 7. Required verification

| Case | Required result |
| --- | --- |
| Enforced visible real person | Brain payload requires a semantic preflight and every signed output explicitly approves it. |
| Missing receipt | Job blocks before any Provider materialization. |
| Product-only / no person | No Human Realism preflight is required merely because a garment exists. |
| Object-surface artwork | Photographic whole-image intent remains independent of the surface fact. |
| Retry | Frozen review dimensions cause a new Brain sign-off, never local repair prose. |
| Web / Local MCP relay | Both receive the same approved canonical string and admitted reference hashes. |
| Cross-scene regression | Adult portrait, real person with product, ordinary non-human product, and the blue-dress regression remain isolated from template-specific recipes. |

## 8. Acceptance interpretation

A blue-dress Local MCP rerun may demonstrate that the active shared planning
and exact relay now produce a more credible image. It is still a
`conversation_only_not_certified` comparison. Production quality certification
requires the normal Web Provider, shared vision/hybrid review, bounded
Brain-owned retry and final delivery path when that upstream is available.
