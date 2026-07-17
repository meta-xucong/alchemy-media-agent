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

The Brain must resolve the preference as a whole photographic decision:

- neutral-to-slightly-warm white balance rather than a yellow/amber cast;
- a modestly brighter, clean, naturally light complexion with believable tonal variation;
- fine-grained, irregular real skin texture and restrained matte highlights;
- preserved facial identity, age, expression, and scene lighting logic.

“Modestly brighter” means a small aesthetic lift within the Brain's whole-image
judgement, not a numeric exposure or skin-lightness target. The requirement is intentionally semantic. The local runtime does not classify
ethnicity, add complexion words, choose a palette, alter pixels, or create a
skin-specific retry.

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
5. General, E-Commerce, Photography, adult, young-person, and low-key scenes
   continue using the same shared capability without leakage.

The blue-dress commercial sample is a controlled visual comparison, not a new
child-specific acceptance rule.

## Relationship to earlier documents

Doc148 remains authoritative for scene-balanced complexion and generic review
evidence. Doc159 only resolves the boundary between natural realism and an
explicit commercial brightness preference. Doc72 remains historical and cannot
activate this behaviour through ethnicity or East Asian keywords.
