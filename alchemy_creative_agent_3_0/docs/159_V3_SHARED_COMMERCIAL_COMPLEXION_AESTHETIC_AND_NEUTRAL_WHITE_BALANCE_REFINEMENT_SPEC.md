# Doc159 — V3 Shared Commercial Complexion Aesthetic and Neutral White-Balance Refinement

## Status

Implemented shared Human Realism refinement. This is a foundation semantic
adjustment inside the existing Human Realism → Remote Brain → canonical prompt
path. It does not create a child, East Asian, apparel, E-Commerce, or
Photography capability.

## Observed gap

The current shared contract correctly prevents plastic skin, bleaching, and
accidental warm or muddy scene casts. In bright kidswear and other consumer
model imagery, it can nevertheless be interpreted too conservatively: the
person remains realistic but reads warmer or darker than the intended
commercial presentation. A cool backdrop makes that warm complexion shift even
more visible.

The missing distinction is:

```text
unwanted whitening filter ≠ an explicitly owned commercial preference for a
cleaner, brighter, fairer presentation
```

## Decision

The Remote Brain may honour a brighter/fairer complexion when it is owned by
the user brief or a clearly declared target-market presentation context. For
the user's East Asian commercial audience, this allows the expected bright,
clean product-image aesthetic without turning ethnicity into a runtime rule.

This is a semantic understanding of a commercial reference and preference, not
an instruction to reuse the adult sample as a global skin template. A supplied
reference may guide complexion, white balance, and skin material only when the
user explicitly assigns that role. It must not transfer the reference person's
identity, age, face, hair, wardrobe, scene, or mood.

The Brain must resolve the preference as a whole photographic decision. The
explicitly user-owned hue and undertone are authoritative; this document does
not impose a universal warm, cool, peach or pink complexion:

- a user-requested cool or cool-neutral fair presentation remains cool-neutral,
  without a compensatory peach, amber, golden or generic warm-beauty bias;
- a user-requested warmer, darker, tanned, documentary, historical or
  mood-specific complexion remains owned by that request;
- when hue or undertone is not assigned, scene-balanced neutrality is used
  instead of inventing warmth or coolness;
- a modestly brighter, clean and naturally light complexion when that
  brightness is explicitly owned by the brief;
- brightness coming from clean scene light rather than lifted exposure;
- fine-grained, irregular real skin texture and restrained matte highlights
  that follow facial planes instead of diffusing across the whole face;
- the person's complexion remaining visually stable when the set, backdrop, or
  practical light carries a blue, yellow, green, or other color cast;
- subtle camera-resolved, nonuniform skin variation remaining visible at the
  delivered scale instead of a uniformly airbrushed surface;
- preserved facial identity, age, expression, and scene lighting logic.

The decision applies only when a visible person or model is part of a
commercial presentation, or when the user explicitly asks for this complexion
direction. Product-only images, unrelated creative work, documentary scenes,
and low-key work must not receive a hidden commercial complexion treatment.

“Modestly brighter” means a small aesthetic lift within the Brain's whole-image
judgement, not a numeric exposure or skin-lightness target. The requirement is intentionally semantic. The local runtime does not classify
ethnicity, add complexion words, choose a palette, alter pixels, or create a
skin-specific retry.

The adult standard sample that motivated this refinement is evidence of the
desired commercial finish—neutral lightness, low yellow/orange saturation,
controlled highlights, and believable micro-variation—not a runtime reference,
identity anchor, fixed palette, or universal treatment.

When the commercial complexion decision is active, the Brain must perform a
silent completeness check before returning its final provider prompt. The
complete natural-language direction must carry the resolved user-owned hue and
undertone, separation from scene cast, and face-plane highlight behavior; a
generic word such as “natural” or “fair” alone is not sufficient. This is a
Brain self-check, not a local string validator or a prompt suffix.

## Authoritative path

```text
user brief + reference truth + declared market/aesthetic context
  → shared Human Realism contract
  → Remote Brain whole-image judgement
  → canonical Provider prompt and Human Naturalness re-sign
  → GPT Image 2 or exact Local MCP relay
  → existing shared pixel review/retry/final winner
```

The final prompt still comes entirely from the Brain. The new instruction is a
semantic ownership clarification, not a hidden local prompt suffix.

## Non-goals and prohibitions

- No East Asian or kidswear-specific runtime branch.
- No regex or keyword rule deciding skin colour or commercial fairness.
- No fixed RGB/HSL/lightness/saturation target.
- No whitening, face recolouring, skin smoothing, LUT, or pixel postprocess.
- No new Provider, Brain, reviewer, retry loop, or delivery path.
- No override of an explicit reference-owned complexion or user-requested mood.
- No forcing a bright commercial treatment into dark, documentary, traditional,
  or otherwise user-owned low-key work.

## Required regression

The focused contract must prove that:

1. the Brain instruction recognises explicit user/market brightness preference;
2. it rejects ethnicity-only inference, bleaching, plastic highlights, and
   local skin repair;
3. the frozen Human Realism contract remains demographic-neutral;
4. Brain-owned execution carries no local complexion prompt fragments;
5. A complexion reference is limited to complexion/white-balance/material
   semantics and cannot transfer identity or other reference-owned channels;
6. commercial complexion direction prefers neutral hue before additional
   brightness, separates complexion material from scene color cast, keeps
   camera-resolved microvariation, and preserves face-plane highlights rather
   than a global sheen;
7. General, E-Commerce, Photography, adult, young-person, and low-key scenes
   continue using the same shared capability without leakage.

The blue-dress commercial sample is a controlled visual comparison, not a new
child-specific acceptance rule.

## Relationship to earlier documents

Doc148 remains authoritative for scene-balanced complexion and generic review
evidence. Doc159 only resolves the boundary between natural realism and an
explicit commercial brightness preference. Doc72 remains historical and cannot
activate this behaviour through ethnicity or East Asian keywords.

## Final acceptance closure

The earlier controlled comparison established the material-realism part of
this foundation capability, but its fixed warm-language conclusion is
superseded by the user-owned-undertone correction above. The current accepted
contract is:

- complexion follows the explicit user-owned hue and undertone without an
  automatic warm or cool bias, and does not become yellow, orange, muddy or
  artificially bleached;
- skin retains age-appropriate, camera-resolved variation and restrained
  face-plane highlights without oily shine, waxiness, or uniform airbrushing;
- the person's complexion remains stable when the set or practical light is
  strongly colored, while the scene itself keeps its requested color;
- an adult reference may guide complexion and skin finish only when the user
  explicitly assigns that channel; it never transfers adult identity, age,
  facial structure, hair, wardrobe, pose, scene, or mood;
- a full-body child commercial image is compared against the adult close-up
  for complexion direction and material principles, not literal pixel identity
  or identical texture scale.

The earlier blue-dress MCP comparison scored approximately 8.8/10 against the
adult standard sample's 9.2/10. Later zero-reference controlled evidence showed
that the old fixed `peach-pink` and `neutral-to-slightly-warm` wording could
still override an explicit cool-fair request. That conclusion is therefore
reopened and corrected by Doc170 evidence; the material-realism protections
remain valid, while fixed warmth is no longer authoritative.
