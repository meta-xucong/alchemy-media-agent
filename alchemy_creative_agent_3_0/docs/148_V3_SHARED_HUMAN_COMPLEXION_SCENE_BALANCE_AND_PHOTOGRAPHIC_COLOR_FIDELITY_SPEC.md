# Doc148 — V3 Shared Human Complexion, Scene Balance, and Photographic Color Fidelity

## Status

Implementation specification for the shared Human Realism capability. This is
a foundation-quality refinement, not a child, apparel, portrait, marketplace,
or template feature.

## Observed gap

The Doc143–147 chain now makes a person read as situation-specific, naturally
expressed, and materially photographic. Controlled product/lifestyle examples
can nevertheless retain an incidental warm, yellow, dark, muddy, or otherwise
unbalanced complexion rendering. That is not a request to change a person's
ethnicity or make everyone lighter. It is a failure to reconcile the
person's reference- or user-owned complexion with the color relationship of
the whole photographed scene.

The gap is architectural: fresh Human Realism contracts require photographic
material, but do not explicitly require the Remote Brain to resolve
complexion and scene color together, then have the shared pixel reviewer
attest that obligation. Historical detailed labels may describe past results,
but they must not become a new prompt vocabulary.

## Decision

Advance fresh enforced Human Realism from semantic contract v4 to v5. Freeze
one additional shared semantic requirement:

```text
complexion_rendering_requirement =
  preserve_reference_or_user_owned_complexion_with_scene_balanced_color
```

The requirement means:

- preserve complexion identity where a reference or user intent owns it;
- retain legitimate scene lighting, exposure, mood, and color design;
- resolve face/skin color and tonal separation as natural photographic
  material rather than allowing incidental casts, muddy darkening, or generic
  beauty retouch to decide it;
- keep the image's requested aesthetic rather than forcing a high-key or
  commercial look.

It does **not** mean whitening, a preferred skin color, a brightness target,
a demographic classifier, a color-code palette, a beauty filter, or a local
postprocess correction.

## Authoritative execution path

```text
frozen user intent + reference truth + capability execution envelope
  -> Remote Central Brain authors the complete direction
  -> canonical prompt finalization
  -> independent Human Realism v5 re-sign by the Remote Brain
  -> canonical Provider / exact Local MCP relay
  -> shared vision or hybrid pixel review
  -> normalized shared evidence
  -> existing bounded Brain whole-direction retry
  -> existing final-winner selection
```

The Remote Brain is the sole author of the final renderer prompt. The local
runtime may freeze, validate, transport, hash, and reject invalid contracts;
it may never append a complexion phrase, compare skin wording, select a
palette, alter pixels, or create a complexion-specific retry.

## Human Realism v5 contract

Fresh enforced real-person and human-detail jobs emit exactly the v5 semantic
contract fields accepted by Scenario Runtime. The existing broad review
dimension `human_skin_or_retouch` remains the only shared surface for this
evidence. No new color-specific review code is added.

For a visible person, the shared pixel attestation covers:

1. individual personhood;
2. situation-owned expression when applicable;
3. reference- or user-owned complexion rendered with scene-balanced color;
4. photographic human material.

For a hand/skin-detail-only image, personhood and expression remain
`not_applicable`; complexion/material remain applicable as universal surface
quality obligations. This is a scope distinction, not a second capability.

The vision/hybrid reviewer can report only existing generic dimensions. A
non-certifying, inconsistent, missing, or metadata-only answer withholds
delivery under the existing shared truth rules.

## Remote Brain duties

When v5 is active, the Brain must make the complexion decision as part of the
whole image it authors. It must preserve user-owned/reference-owned identity,
respect the requested photographic mood, and prevent scene color from
accidentally making the person look unhealthy, overly dark, washed out, or
plastic. It must not reveal a checklist or append a repair phrase.

During `provider_prompt_human_naturalness_resign`, the Brain retains a
candidate only if that complete direction already satisfies all frozen Human
Realism v5 obligations. Otherwise it returns `rewritten` with a complete
replacement direction. It never returns a diff or relies on a local caller to
apply a complexion patch.

## Review and retry duties

The enforced reviewer receives the frozen v5 authenticity contract and
assesses it from pixels. A `human_skin_or_retouch` concern is normalized
evidence only. The existing shared bounded retry takes that evidence back to
the Brain's complete-direction finalization; no route may construct a local
skin, color, warmth, lightness, or retouch retry instruction.

## Compatibility, isolation, and historical records

- v4 and older jobs remain readable but are not silently recertified as v5.
- Historical detailed complexion labels remain read-only aliases of
  `human_skin_or_retouch`; fresh enforced contracts do not emit them.
- General, E-Commerce, and Photography receive the identical shared contract
  only when their normal evidence activates Human Realism. Their scenarios,
  deliverable maps, and controls do not change.
- Stylized/non-human work is outside this contract unless existing shared
  semantic evidence activates Human Realism.

## Explicit prohibitions

Do not introduce:

- child/kidswear, adult, East Asian, product, fashion, E-Commerce, or
  Photography complexion branches;
- regex/keyword decisions over skin-color language or fixed numerical color,
  exposure, saturation, lightness, or tone targets;
- local prompt suffixes, negative prompts, retry wording, image filters, LUTs,
  or pixel postprocessing;
- a separate color reviewer, Provider route, Brain, retry loop, delivery path,
  or storage surface;
- a provider-side substitute that bypasses the Brain-signed canonical prompt.

## Required regression and acceptance

1. Fresh real-person and detail Human Realism guidance freezes v5 with the
   same generic complexion requirement across ordinary adult, young person,
   person/object interaction, and low-key contexts; it contains no named
   demographic, palette, or prompt-fragment data.
2. Scenario Runtime accepts only v5 for fresh enforced projection and passes
   it unchanged to finalization, re-signing, and shared review.
3. The Remote Brain receives a semantic whole-image obligation, may rewrite a
   candidate completely, and has no local completion path.
4. The reviewer receives the fifth frozen obligation; a generic
   `human_skin_or_retouch` retry signal remains normalized evidence with no
   renderer prose.
5. Historical v4 remains readable but cannot certify fresh v5 delivery.
6. Prove canonical Provider and Local MCP prompt/reference parity, General /
   E-Commerce / Photography isolation, focused Human Realism coverage, full
   V3 regression, static checks, and one controlled authorized blue-dress
   comparison using the exact v5 Brain-signed relay.

## Relationship to earlier documents

Doc136, Doc138, Doc143, Doc144, and Doc147 remain authoritative for their
respective historical decisions. Their fresh-contract references are
superseded by this v5 refinement only where a newly created Human Realism
contract is concerned. Doc147's expression ownership remains unchanged; v5
adds an orthogonal complexion/scene-balance obligation and does not reopen an
expression or child-specific design.
